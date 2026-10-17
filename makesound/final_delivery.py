"""Review remaining work and publish verified PCM audio locally, without synthesis."""
import argparse
import copy
import json
import re
import shutil
import sys
import tempfile
import wave
from pathlib import Path

from . import validation as v
from .core_v16 import ProjectCore
from .errors import MakeSoundError, require
from .generation import Generation, timestamp
from .performance_plan import propose, render
from .project_files import workspace, _delivery, _name, refresh_index
from .questions import Questions
from .storage import atomic_write, read_json, digest, file_lock, reject_links
from .voice_selection import targets_from_items, reuse_report, _verified_audio


def review(core, question_id, items, *, selection_id=None, sentence_ids=None):
    targets_from_items(core, question_id, items)
    report = (reuse_report(core, selection_id, question_id, items=items) if selection_id else
              {'reusable': [], 'remaining_sentence_ids': [item['sentence_id'] for item in items]})
    remaining = report['remaining_sentence_ids']
    if not remaining:
        return {'status': 'ready_to_publish', 'reusable': report['reusable'], 'remaining_sentence_ids': [], 'network_calls': 0}
    selected = remaining[:5] if sentence_ids is None else sentence_ids
    require(selected and set(selected) <= set(remaining), 'plan_coverage', 'Select only remaining sentences.')
    batch = propose(core, question_id, [item for item in items if item['sentence_id'] in selected], sentence_ids=selected)
    return {**{k: batch[k] for k in ('plan_id', 'plan_hash', 'job_id', 'question_id', 'sentence_ids', 'status')},
            'review': render(batch), 'reusable_sentence_ids': [r['sentence_id'] for r in report['reusable']],
            'remaining_sentence_ids': remaining, 'items_hash': digest(items), 'network_calls': 0}


def _safe_label(value):
    return re.sub(r'[<>:"/\\|?*\x00-\x1f]', '_', value).rstrip(' .')[:35] or '角色'


def _srt(rows, offset=0):
    return '\n'.join(f"{i}\n{timestamp(row['start'] + offset)} --> {timestamp(row['end'] + offset)}\n{row['text']}\n"
                     for i, row in enumerate(rows, 1))


def publish(core, task_id, title, question_id, items, job_ids, *, selection_id=None, version):
    """Require exact target coverage; remove recorded export silence, never guessed speech."""
    info = workspace(core, task_id, title)
    _name(version)
    targets = targets_from_items(core, question_id, items)
    question = Questions(core).read(question_id)
    manifest = read_json(core.managed_path(f'.makesound/handoffs/{question_id}.json'))['manifest']
    originals = {s['sentence_id']: s for s in manifest['segments']}
    item_map = {item['sentence_id']: item for item in items}
    require(isinstance(job_ids, list) and len(job_ids) == len(set(job_ids)), 'invalid_data', 'Provide distinct Jobs.')
    folder = _delivery(core, title) / version
    reject_links(folder)
    receipt = core.managed_path(f'.makesound/workspace/{task_id}/deliveries/{version}.json')
    identity = digest({'question_id': question_id, 'items': items, 'job_ids': job_ids, 'selection_id': selection_id})
    with file_lock(receipt.with_suffix('.lock')):
        if receipt.exists():
            saved = read_json(receipt)
            require(saved['identity'] == identity, 'file_conflict', 'Version already represents a different delivery.')
            for relative, expected in saved['files'].items():
                path = folder / relative
                reject_links(path)
                require(path.is_file() and digest(path.read_bytes().hex()) == expected,
                        'file_conflict', 'Published files changed or disappeared; preserve them and use a new version.')
            result = copy.deepcopy(saved['result'])
            return _index(core, task_id, title, result)
        require(not folder.exists(), 'file_conflict', 'Keep the existing version; choose a new version name.')
        found = {}
        if selection_id:
            for row in reuse_report(core, selection_id, question_id, items=items)['reusable']:
                found[row['sentence_id']] = {**row, 'kind': '复用试听'}
        engine = Generation(core)
        for jid in job_ids:
            v.identifier(jid)
            snapshot = engine.load(jid)
            state = read_json(core.managed_path(f'.makesound/jobs/{jid}/state.json'))
            for chunk in snapshot['chunks']:
                sid = chunk['sentence_id']
                original = originals.get(sid)
                if original is None:
                    continue
                resolved = question['answer']['resolved'][original['role_id']]
                require(chunk['text'] == original['text'] and chunk.get('role_id') == original['role_id']
                        and chunk['source'] == resolved['source'] and chunk['effective_settings'] == resolved['effective_settings']
                        and chunk.get('provider_directives', {}) == targets[sid]['provider_directives']
                        and chunk.get('inline_controls', []) == targets[sid]['inline_controls'],
                        'performance_mismatch', 'Job content or actual performance differs from the final input.')
                audio_state = state['chunks'].get(chunk['chunk_id'], {})
                audio = _verified_audio(core, audio_state)
                if audio is None:
                    continue
                require(sid not in found or found[sid]['audio_hash'] == audio_state['audio_hash'],
                        'ambiguous_audio', 'Multiple different recordings cover the same sentence; select explicit sources.')
                found[sid] = {**audio_state, 'sentence_id': sid, 'role_id': original['role_id'], 'text': original['text'],
                              'audio_path': str(audio), 'job_id': jid, 'chunk_id': chunk['chunk_id'],
                              'provider_directives': chunk.get('provider_directives', {}), 'kind': '任务音频'}
        missing = [sid for sid in originals if sid not in found]
        require(not missing, 'delivery_incomplete', 'Missing verified audio for: ' + ', '.join(missing))
        # Preflight PCM and trusted speech boundaries before writing any version.
        pcm, encoding = [], None
        for sid, original in originals.items():
            row = found[sid]
            audio = core.managed_path(Path(row['audio_path']).relative_to(core.root).as_posix())
            with wave.open(str(audio), 'rb') as stream:
                fmt = (stream.getnchannels(), stream.getsampwidth(), stream.getframerate(), stream.getcomptype())
                require(fmt[0:2] == (1, 2) and fmt[3] == 'NONE' and (encoding is None or fmt == encoding),
                        'incompatible_audio', 'Delivery needs matching mono PCM WAV; no implicit conversion was performed.')
                encoding = fmt
                speech = row.get('speech_seconds')
                require(type(speech) in (int, float) and 0 < speech <= row['duration_seconds'],
                        'timing_unavailable', 'A trusted speech boundary is required to remove added silence.')
                frames = round(speech * fmt[2])
                require(frames <= stream.getnframes(), 'invalid_audio', 'Speech boundary exceeds saved audio.')
                data = stream.readframes(frames)
                require(len(data) == frames * fmt[0] * fmt[1], 'invalid_audio', 'Source audio is truncated.')
            saved = read_json(core.managed_path(f".makesound/jobs/{row['job_id']}/state.json"))['chunks'][row['chunk_id']]
            require(digest(audio.read_bytes().hex()) == row['audio_hash'], 'artifact_repair_required', 'Source changed during delivery.')
            subtitles = []
            if saved.get('subtitle_status') == 'verified_timing' and saved.get('subtitles'):
                from .minimax_provider import normalize_subtitles
                subtitles = normalize_subtitles([{'text': s['text'], 'time_begin': s['start'] * 1000,
                                                  'time_end': s['end'] * 1000} for s in saved['subtitles']],
                                                original['text'], speech)
            pcm.append((sid, row, data, frames / fmt[2], subtitles))
        work = core.managed_path(f'.makesound/workspace/{task_id}')
        stage = Path(tempfile.mkdtemp(prefix='assembly_', dir=work))
        result_rows, all_subtitles, elapsed = [], [], 0.0
        try:
            (stage / '分句').mkdir()
            merged = stage / '合并试听_全文.wav'
            with wave.open(str(merged), 'wb') as output:
                output.setnchannels(encoding[0]); output.setsampwidth(encoding[1]); output.setframerate(encoding[2])
                for number, (sid, row, data, seconds, subtitles) in enumerate(pcm, 1):
                    role = manifest.get('role_metadata', {}).get(row['role_id'], {}).get('display_name', row['role_id'])
                    relative = f'分句/{number:03}_{_safe_label(role)}_{sid}.wav'
                    with wave.open(str(stage / relative), 'wb') as part:
                        part.setnchannels(encoding[0]); part.setsampwidth(encoding[1]); part.setframerate(encoding[2]); part.writeframes(data)
                    output.writeframes(data)
                    subtitle_path = None
                    if subtitles:
                        subtitle_path = str(folder / Path(relative).with_suffix('.srt'))
                        (stage / Path(relative).with_suffix('.srt')).write_text(_srt(subtitles), encoding='utf-8')
                        all_subtitles.extend({**s, 'start': s['start'] + elapsed, 'end': s['end'] + elapsed} for s in subtitles)
                    pause = item_map[sid]['pause_after_ms'] if number < len(pcm) else 0
                    gap_frames = round(encoding[2] * pause / 1000)
                    output.writeframes(b'\0' * gap_frames * encoding[0] * encoding[1])
                    elapsed += seconds + gap_frames / encoding[2]
                    result_rows.append({'sentence_id': sid, 'audio_path': str(folder / relative), 'subtitle_path': subtitle_path,
                                        'duration_seconds': seconds, 'pause_after_ms': pause, 'kind': row['kind'],
                                        'emotion': targets[sid]['provider_directives'].get('emotion', '自动')})
            complete_subtitles = all(row['subtitle_path'] for row in result_rows)
            if complete_subtitles:
                (stage / '合并试听_全文.srt').write_text(_srt(all_subtitles), encoding='utf-8')
            script = '\n\n'.join(f"[{s['sentence_id']}] {s['text']}" for s in manifest['segments'])
            (stage / '剧本.md').write_text(f'# {title}\n\n{script}\n', encoding='utf-8')
            lines = [f'# 配音演绎单 · {version}', '', '按实际源音频及最终输入记录；段间停顿仅在合并音频追加一次。', '']
            for row in result_rows:
                resolved = question['answer']['resolved'][originals[row['sentence_id']]['role_id']]
                lines.extend([f"## {row['sentence_id']} · {resolved['name']}", '', originals[row['sentence_id']]['text'], '',
                              f"情绪：{row['emotion']}；语速：{resolved['effective_settings'].get('speed', '默认')}；声调：{resolved['effective_settings'].get('pitch', '默认')}；段后停顿：{row['pause_after_ms']} ms。", '',
                              f"实际发声控制：{json.dumps(targets[row['sentence_id']]['inline_controls'], ensure_ascii=False)}", ''])
            (stage / '配音演绎单.md').write_text('\n'.join(lines), encoding='utf-8')
            notes = [f'# 交付说明 · {version}', '', f'音频：全部 {len(result_rows)} 句已完成；合并时长 {elapsed:.3f} 秒。', '',
                     '字幕：完整。' if complete_subtitles else '字幕：未完整，缺失项未生成空字幕；不因此重新合成。', '',
                     '[合并音频](合并试听_全文.wav) · [演绎单](配音演绎单.md) · [剧本](剧本.md)', '']
            notes.extend(f"- {row['sentence_id']}：{row['emotion']}，{row['duration_seconds']:.3f} 秒，{row['kind']}，段后 {row['pause_after_ms']} ms。" for row in result_rows)
            (stage / '交付说明.md').write_text('\n'.join(notes) + '\n', encoding='utf-8')
            result = {'status': 'complete' if complete_subtitles else 'audio_ready_subtitles_missing',
                      'audio_status': 'complete', 'subtitle_status': 'complete' if complete_subtitles else 'missing',
                      'version_dir': str(folder), 'merged_audio_path': str(folder / merged.name),
                      'duration_seconds': elapsed, 'segments': result_rows, 'network_calls': 0,
                      'default_status': 'not_changed', 'review_path': str(folder / '配音演绎单.md')}
            files = {p.relative_to(stage).as_posix(): digest(p.read_bytes().hex()) for p in stage.rglob('*') if p.is_file()}
            mapping = [{'sentence_id': sid, 'job_id': row['job_id'], 'chunk_id': row['chunk_id'],
                        'source_hash': row['audio_hash']} for sid, row, *_ in pcm]
            folder.parent.mkdir(parents=True, exist_ok=True)
            stage.rename(folder)
            atomic_write(receipt, {'identity': identity, 'files': files, 'sources': mapping, 'result': result})
        finally:
            require(stage.resolve().is_relative_to(work.resolve()) and stage.name.startswith('assembly_'),
                    'unsafe_path', 'Temporary delivery escaped workspace.')
            if stage.exists():
                shutil.rmtree(stage)
        return _index(core, task_id, title, result)


def _index(core, task_id, title, result):
    try:
        result['index_path'] = refresh_index(core, task_id, title)['index_path']
        result['index_status'] = 'updated'
    except MakeSoundError as exc:
        result['index_status'], result['index_error'] = 'needs_review', exc.code
    return result


def main(argv=None):
    if hasattr(sys.stdout, 'reconfigure'):
        sys.stdout.reconfigure(encoding='utf-8')
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=['review', 'publish'])
    parser.add_argument('--project', required=True)
    parser.add_argument('--question', required=True)
    parser.add_argument('--items', type=Path, required=True)
    parser.add_argument('--selection')
    parser.add_argument('--sentence', action='append')
    parser.add_argument('--job', action='append', default=[])
    parser.add_argument('--task')
    parser.add_argument('--title')
    parser.add_argument('--version')
    args = parser.parse_args(argv)
    try:
        core, items = ProjectCore(args.project), read_json(args.items)
        if args.action == 'review':
            result = review(core, args.question, items, selection_id=args.selection, sentence_ids=args.sentence)
        else:
            require(args.task and args.title and args.version, 'invalid_data', 'Publishing needs task, title and version.')
            result = publish(core, args.task, args.title, args.question, items, args.job,
                             selection_id=args.selection, version=args.version)
        print(json.dumps(result, ensure_ascii=False))
        return 0
    except MakeSoundError as exc:
        print(json.dumps({'status': 'error', 'error': exc.code, 'message': str(exc)}, ensure_ascii=False))
        return 2


if __name__ == '__main__':
    raise SystemExit(main())
