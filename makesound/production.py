from .inline_controls import request_text, request_identity
"""Explicit production planning/execution; never called by Studio submission."""
import argparse
import json
import sys
from pathlib import Path

from . import validation as v
from .core_v16 import ProjectCore
from .errors import MakeSoundError, require
from .generation import Generation
from .minimax_provider import MiniMaxProvider, normalize_subtitles, download_subtitles, HTTPSMiniMaxTransport
from .questions import Questions
from .storage import atomic_write, digest, file_lock, read_json


def plan(core, *, request_path=None, question_id=None, performance_plan=None, confirmed=False, audio_format=None):
    require(sum(value is not None for value in (request_path, question_id, performance_plan)) == 1,
            'invalid_data', 'Choose exactly one sentence array, Studio Question, or confirmed performance plan.')
    engine = Generation(core, output_format=audio_format)
    if performance_plan:
        from .performance_plan import execution_segments, read as read_performance_plan, select_segments
        v.identifier(performance_plan)
        require(audio_format is None, 'invalid_data', 'Output format is selected before performance-plan confirmation.')
        reviewed = read_performance_plan(core, performance_plan)
        require(reviewed['status'] == 'confirmed', 'confirmation_required',
                'Confirm the reviewed performance plan before creating a Job.')
        question_id = reviewed['question_id']
        handoff_path = core.managed_path(f'.makesound/handoffs/{question_id}.json')
        with file_lock(handoff_path.with_suffix('.lock')):
            handoff = read_json(handoff_path)
            questions = Questions(core)
            question = questions.read(question_id)
            require(reviewed['project_id'] == core.read()['project_id']
                    and reviewed.get('source_job_id', reviewed['job_id']) == question['job_id']
                    and reviewed['answer_id'] == question.get('answer', {}).get('answer_id'),
                    'plan_mismatch', 'Performance plan does not belong to the current Studio Answer.')
            require(handoff['question_id'] == question_id and handoff['harness_session_id'] == question['harness_session_id'],
                    'session_mismatch', 'Trusted task handoff differs.')
            source_segments = handoff.get('manifest', {}).get('segments')
            require(reviewed['manuscript_hash'] == digest(source_segments), 'plan_changed',
                    'The manuscript changed after the performance plan was reviewed.')
            if 'sentence_ids' in reviewed:
                require('source_job_id' in reviewed and reviewed['job_id'] != question['job_id'],
                        'plan_mismatch', 'A batch must have its own Job identity.')
                source_segments = select_segments(source_segments, reviewed['sentence_ids'])
            segments = execution_segments(reviewed)
            require([(item['paragraph_id'], item['sentence_id'], item['role_id'], item['text']) for item in segments]
                    == [(item['paragraph_id'], item['sentence_id'], item['role_id'], item['text']) for item in source_segments],
                    'plan_coverage', 'Performance plan no longer covers the source manuscript in order.')
            require(question['status'] == 'answered', 'not_answered', 'Complete Studio settings first.')
            if question['claimed_by'] is None:
                questions.claim(question_id, handoff['harness_session_id'])
            require(question['claimed_by'] in {None, handoff['harness_session_id']}, 'session_mismatch',
                    'Answer was claimed by another Harness session.')
            snapshot_path = core.managed_path(f'.makesound/jobs/{reviewed["job_id"]}/snapshot.json')
            snapshot = (engine.load(reviewed['job_id']) if snapshot_path.exists() else
                        engine.freeze_from_answer(question_id, handoff['harness_session_id'], segments,
                                                  confirmed=True, authorized=True, job_id=reviewed['job_id']))
            require(snapshot['segments'] == segments, 'snapshot_conflict',
                    'An existing frozen Job differs from the confirmed performance plan.')
    elif question_id:
        require(confirmed is True, 'authorization_required', 'Confirm the manuscript before creating a production plan.')
        v.identifier(question_id)
        handoff_path = core.managed_path(f'.makesound/handoffs/{question_id}.json')
        with file_lock(handoff_path.with_suffix('.lock')):
            handoff = read_json(handoff_path)
            questions = Questions(core)
            question = questions.read(question_id)
            require(handoff['question_id'] == question_id and handoff['harness_session_id'] == question['harness_session_id'],
                    'session_mismatch', 'Trusted task handoff differs.')
            require(question['status'] == 'answered', 'not_answered', 'Complete Studio settings first.')
            if question['claimed_by'] is None:
                questions.claim(question_id, handoff['harness_session_id'])
            snapshot_path = core.managed_path(f'.makesound/jobs/{question["job_id"]}/snapshot.json')
            snapshot = (engine.load(question['job_id']) if snapshot_path.exists() else
                        engine.freeze_from_answer(question_id, handoff['harness_session_id'], handoff['manifest']['segments'],
                                                  confirmed=True, authorized=True))
    else:
        require(confirmed is True, 'authorization_required', 'Confirm the manuscript before creating a production plan.')
        require(request_path is not None, 'manifest_required', 'Provide a sentence array or a persisted Question.')
        segments = read_json(Path(request_path))
        snapshot = engine.freeze(segments, confirmed=True, authorized=True)
    require(audio_format is None or snapshot['project_settings']['audio_format'] == audio_format,
            'snapshot_conflict', 'An existing frozen Job cannot change output format; prepare a new task.')
    return {'status': 'planned', 'job_id': snapshot['job_id'], 'snapshot_hash': snapshot['snapshot_hash'],
            'chunks': len(snapshot['chunks']), 'characters': sum(len(request_text(c)) for c in snapshot['chunks']),
            'providers': sorted({c['source']['provider'] for c in snapshot['chunks']}),
            'audio_format': snapshot['project_settings']['audio_format'], 'network_calls': 0,
            'paid_execution_authorized': False}


def repair_subtitles(core, job_id, chunk_id, subtitle_file, *, timing_source='reviewed_import'):
    v.identifier(job_id); v.identifier(chunk_id)
    engine = Generation(core)
    snapshot = engine.load(job_id)
    chunk = next((c for c in snapshot['chunks'] if c['chunk_id'] == chunk_id), None)
    require(chunk and chunk['source']['provider'] == 'minimax', 'not_found', 'Select an existing MiniMax chunk.')
    folder = core.managed_path(f'.makesound/jobs/{job_id}')
    with file_lock(folder / 'execution.lock'):
        state_path = folder / 'state.json'
        state = read_json(state_path)
        result = state['chunks'][chunk_id]
        require(result['status'] == 'success', 'artifact_repair_required', 'Restore the successful local audio before importing timing.')
        audio = core.managed_path(result['path'])
        from .providers import duration
        require(digest(audio.read_bytes().hex()) == result['audio_hash'] and duration(audio) == result['duration_seconds'],
                'artifact_repair_required', 'Local audio integrity differs.')
        rows = normalize_subtitles(read_json(Path(subtitle_file)), chunk['text'], result['speech_seconds'])
        # Serialize shared cache updates with synthesis/cache readers.
        with file_lock(audio.with_suffix('.lock')):
            metadata_path = audio.with_suffix('.json')
            metadata = read_json(metadata_path)
            require(metadata['audio_hash'] == result['audio_hash'], 'artifact_repair_required', 'Cache metadata differs.')
            patch = {'subtitles': rows, 'subtitle_status': 'verified_timing', 'timing_source': timing_source}
            _, receipt_path = MiniMaxProvider.receipt_paths(audio.with_suffix('.tmp'))
            if receipt_path.exists():
                receipt = read_json(receipt_path)
                receipt.pop('subtitle_error', None)
                atomic_write(receipt_path, {**receipt, **patch})
            metadata.pop('subtitle_error', None)
            atomic_write(metadata_path, {**metadata, **patch})
            state['chunks'][chunk_id].pop('subtitle_error', None)
            state['chunks'][chunk_id].update(patch)
            atomic_write(state_path, state)
        return {'status': 'timing_imported', 'job_id': job_id, 'chunk_id': chunk_id, 'network_calls': 0}


def retry_subtitle_download(core, job_id, chunk_id, *, transport=None, hosts=None):
    """Recover provider timing using GET only; never load credentials or dispatch TTS."""
    v.identifier(job_id); v.identifier(chunk_id)
    engine = Generation(core)
    snapshot = engine.load(job_id)
    chunk = next((item for item in snapshot['chunks'] if item['chunk_id'] == chunk_id), None)
    require(chunk and chunk['source']['provider'] == 'minimax', 'not_found', 'Select an existing MiniMax chunk.')
    folder = core.managed_path(f'.makesound/jobs/{job_id}')
    with file_lock(folder / 'execution.lock'):
        state = read_json(folder / 'state.json')
        result = state['chunks'][chunk_id]
        require(result.get('status') == 'success', 'artifact_repair_required', 'Restore the saved audio first.')
        audio = core.managed_path(result['path'])
        from .providers import duration
        require(digest(audio.read_bytes().hex()) == result['audio_hash'] and duration(audio) == result['duration_seconds'],
                'artifact_repair_required', 'Saved audio integrity differs.')
        _, receipt_path = MiniMaxProvider.receipt_paths(audio.with_suffix('.tmp'))
        receipt = read_json(receipt_path)
        require(receipt.get('request_hash') == request_identity(chunk),
                'artifact_repair_required', 'Subtitle receipt belongs to a different request.')
        require(receipt.get('subtitle_download_url'), 'subtitle_source_unavailable',
                'The original response did not retain a subtitle source; no synthesis was sent.')
        rows = download_subtitles(receipt['subtitle_download_url'], chunk['text'], result['speech_seconds'],
                                 transport=transport or HTTPSMiniMaxTransport(), hosts=hosts, inline_controls=chunk.get('inline_controls'))
        reviewed = folder / f'{chunk_id}.downloaded-timing.json'
        atomic_write(reviewed, [{'text': row['text'], 'time_begin': row['start'] * 1000, 'time_end': row['end'] * 1000} for row in rows])
    repair_subtitles(core, job_id, chunk_id, reviewed, timing_source='provider')
    return engine.export_existing(job_id)


def main(argv=None):
    if hasattr(sys.stdout, 'reconfigure'):
        sys.stdout.reconfigure(encoding='utf-8')
    parser = argparse.ArgumentParser(description='Plan and explicitly authorize bounded MiniMax synthesis, or repair local exports')
    parser.add_argument('action', choices=['plan', 'run', 'export', 'repair-audio', 'repair-subtitles', 'retry-subtitles'])
    parser.add_argument('--project', required=True)
    parser.add_argument('--request', type=Path)
    parser.add_argument('--question')
    parser.add_argument('--performance-plan')
    parser.add_argument('--job')
    parser.add_argument('--chunk')
    parser.add_argument('--subtitle-file', type=Path)
    parser.add_argument('--confirmed', action='store_true')
    parser.add_argument('--audio-format', choices=['wav', 'mp3'], help='Task output override for plan only; does not rewrite project defaults')
    parser.add_argument('--authorize-paid', action='store_true')
    parser.add_argument('--max-calls', type=int)
    parser.add_argument('--max-characters', type=int)
    parser.add_argument('--minimax-config', type=Path, default=Path.home() / '.config/minimax/config.json')
    parser.add_argument('--subtitle-host', action='append', default=None, help='Explicit trusted subtitle download hostname; no API Key is forwarded')
    parser.add_argument('--retry-local', action='store_true')
    args = parser.parse_args(argv)
    try:
        core = ProjectCore(args.project)
        require(args.audio_format is None or args.action == 'plan', 'invalid_data', 'Output format is selected when the Job is frozen.')
        if args.action == 'plan':
            require(sum(value is not None for value in (args.request, args.question, args.performance_plan)) == 1,
                    'invalid_data', 'Choose exactly one sentence array, Studio Question, or confirmed performance plan.')
            result = plan(core, request_path=args.request, question_id=args.question, performance_plan=args.performance_plan,
                          confirmed=args.confirmed, audio_format=args.audio_format)
        elif args.action == 'retry-subtitles':
            result = retry_subtitle_download(core, args.job, args.chunk, hosts=args.subtitle_host)
        elif args.action == 'repair-subtitles':
            require(args.subtitle_file is not None, 'subtitle_unavailable', 'Provide a reviewed subtitle JSON file.')
            result = repair_subtitles(core, args.job, args.chunk, args.subtitle_file)
        elif args.action == 'export':
            # A missing adapter prevents this entry point from making real calls.
            result = Generation(core).export_existing(args.job)
        elif args.action == 'repair-audio':
            v.identifier(args.job)
            budget = read_json(core.managed_path(f'.makesound/jobs/{args.job}/billing-budget.json'))
            class NoNetwork:
                def request(self, *_args, **_kwargs):
                    raise MakeSoundError('local_only', 'Network requests are disabled during local audio repair.')
            adapter = MiniMaxProvider(args.minimax_config, authorized_job_id=args.job, max_calls=budget['max_calls'],
                                      max_characters=budget['max_characters'], transport=NoNetwork(), environ={})
            result = Generation(core, minimax=adapter).run(args.job, retry_local=True)
        else:
            require(args.authorize_paid and args.max_calls and args.max_characters,
                    'authorization_required', 'Explicit paid authorization and request/character limits are required.')
            adapter = MiniMaxProvider(args.minimax_config, authorized_job_id=args.job,
                                      max_calls=args.max_calls, max_characters=args.max_characters, subtitle_hosts=args.subtitle_host)
            engine = Generation(core, minimax=adapter)
            snapshot = engine.load(args.job)
            require(all(c['source']['provider'] in {'minimax', 'fake'} for c in snapshot['chunks']),
                    'provider_not_implemented', 'This runner supports MiniMax and Fake only.')
            if not args.retry_local:
                for chunk in snapshot['chunks']:
                    if chunk['source']['provider'] == 'minimax':
                        adapter.preflight(chunk)
            result = engine.run(args.job, retry_failed=True, retry_local=args.retry_local)
        print(json.dumps(result, ensure_ascii=False, allow_nan=False))
        return 0 if result['status'] not in {'incomplete', 'export_incomplete'} else 2
    except (MakeSoundError, OSError, ValueError, TypeError, KeyError) as exc:
        print(json.dumps({'status': 'error', 'code': exc.code if isinstance(exc, MakeSoundError) else 'invalid_local_data',
                          'message': 'Task could not finish; repair the indicated input or reconcile the provider result.'}))
        return 2


if __name__ == '__main__':
    raise SystemExit(main())
