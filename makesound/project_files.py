"""Local task workspaces and verified audition delivery; never calls a provider."""
import argparse
import json
import re
import shutil
import sys
from pathlib import Path
from urllib.parse import quote

from . import validation as v
from .core_v16 import ProjectCore
from .errors import MakeSoundError, require
from .storage import atomic_write, digest, file_lock, read_json, reject_links


def _name(value):
    require(isinstance(value, str) and 0 < len(value) <= 100, 'unsafe_path', 'Expected a short file name.')
    require(not re.search(r'[<>:"/\\|?*\x00-\x1f]', value) and value not in {'.', '..'}
            and not value.endswith((' ', '.'))
            and value.split('.')[0].upper() not in {'CON', 'PRN', 'AUX', 'NUL',
                *{f'COM{i}' for i in range(1, 10)}, *{f'LPT{i}' for i in range(1, 10)}},
            'unsafe_path', 'File name contains unsafe or reserved characters.')
    return value


def _delivery(core, title):
    path = core.root / '配音' / _name(title)
    reject_links(path)
    require(path.resolve().is_relative_to(core.root), 'unsafe_path', 'Delivery must stay inside the project.')
    return path


def workspace(core, task_id, title):
    """Prepare one stable workspace per task; reuse returned paths across batches."""
    v.identifier(task_id)
    delivery = _delivery(core, title)
    folder = core.managed_path(f'.makesound/workspace/{task_id}')
    with file_lock(core.managed_path('.makesound/workspace.lock')):
        meta = folder / 'task.json'
        if meta.exists():
            require(read_json(meta)['title'] == title, 'task_conflict', 'Task already has a different title.')
        else:
            for existing in core.directory.glob('workspace/*/task.json'):
                reject_links(existing)
                require(read_json(existing)['title'] != title, 'task_conflict', 'Choose a distinct title for a different task.')
            atomic_write(meta, {'task_id': task_id, 'title': title})
        inputs = core.managed_path(f'.makesound/workspace/{task_id}/inputs')
        inputs.mkdir(parents=True, exist_ok=True)
    return {'task_id': task_id, 'title': title, 'inputs_dir': str(inputs),
            'delivery_dir': str(delivery), 'network_calls': 0}


def _references(value, paths):
    if isinstance(value, str):
        return value.replace('\\', '/') in paths
    if isinstance(value, dict):
        return any(_references(item, paths) for item in value.values())
    if isinstance(value, list):
        return any(_references(item, paths) for item in value)
    return False


def organize(core, task_id, title, names):
    """Archive explicitly reviewed root JSON inputs; never move managed state/audio."""
    info = workspace(core, task_id, title)
    require(isinstance(names, list) and len(names) == len(set(names)), 'invalid_data', 'Provide distinct input names.')
    folder = core.managed_path(f'.makesound/workspace/{task_id}')
    journal_path = folder / 'organization.json'
    with file_lock(folder / 'organization.lock'):
        journal = read_json(journal_path) if journal_path.exists() else {'files': []}
        known = {row['from']: row for row in journal['files']}
        pending = []
        for name in names:
            _name(name)
            require(Path(name).suffix == '.json', 'invalid_data', 'Only reviewed JSON inputs may be archived.')
            source, target = core.root / name, Path(info['inputs_dir']) / name
            reject_links(source); reject_links(target)
            require(source.resolve().parent == core.root and target.resolve().is_relative_to(folder.resolve()),
                    'unsafe_path', 'Archive paths escape the task workspace.')
            if not source.exists():
                require(name in known and target.is_file() and digest(target.read_bytes().hex()) == known[name]['hash'],
                        'not_found', 'Input is missing and has no verified archive.')
                continue
            require(source.is_file(), 'invalid_data', 'Input must be a regular file.')
            require(not target.exists(), 'file_conflict', 'Archive destination already exists; nothing was moved.')
            paths = {name, str(source).replace('\\', '/')}
            # Frozen records are immutable; refuse rather than rewrite their paths.
            for record in core.directory.rglob('*.json'):
                reject_links(record)
                if folder not in record.parents:
                    require(not _references(read_json(record), paths), 'input_in_use',
                            'A managed record references this input; leave its original path intact.')
            pending.append((source, target, {'from': name, 'to': target.relative_to(core.root).as_posix(),
                                             'hash': digest(source.read_bytes().hex())}))
        # Commit recovery information before moving; every target was preflighted.
        for _, _, row in pending:
            known[row['from']] = row
        journal['files'] = list(known.values())
        atomic_write(journal_path, journal)
        for source, target, row in pending:
            require(digest(source.read_bytes().hex()) == row['hash'], 'input_changed', 'Input changed during organization.')
            source.rename(target)
        # Only remove empty legacy export folders. Never move/delete legacy files.
        legacy = core.root / 'outputs' / 'audio'
        reject_links(legacy)
        if legacy.exists():
            for path in sorted(legacy.rglob('*'), key=lambda p: len(p.parts), reverse=True):
                reject_links(path)
                require(path.resolve().is_relative_to(legacy.resolve()), 'unsafe_path', 'Legacy path escaped exports.')
                if path.is_dir() and not any(path.iterdir()):
                    path.rmdir()
            if not any(legacy.iterdir()):
                legacy.rmdir()
            parent = core.root / 'outputs'
            if not any(parent.iterdir()):
                parent.rmdir()
    return {**info, 'archived_count': len(journal['files']), 'migration_record': str(journal_path)}


def publish_audition(core, task_id, title, audition_id):
    """Copy verified audio into a stable readable folder; repeats cannot overwrite edits."""
    from .voice_selection import audition_results
    info = workspace(core, task_id, title)
    result = audition_results(core, audition_id)
    sample = read_json(core.managed_path(f'.makesound/voice-selections/{audition_id}.json'))
    selection = read_json(core.managed_path(f".makesound/voice-selections/{sample['selection_id']}.json"))
    metadata = selection['manifest'].get('role_metadata', {})
    registry = core.managed_path(f'.makesound/workspace/{task_id}/auditions.json')
    with file_lock(registry.with_suffix('.lock')):
        records = read_json(registry) if registry.exists() else {}
        if audition_id not in records:
            records[audition_id] = {'number': max((r['number'] for r in records.values()), default=0) + 1}
        number = records[audition_id]['number']
        folder = _delivery(core, title) / '试听' / f'第{number:03}组'
        reject_links(folder)
        outputs = []
        order = {vid: i for i, vid in enumerate(sample['project_voice_ids'], 1)}
        for row in result['audio']:
            source = Path(row['audio_path'])
            # The original sentence ID is preserved; candidate order is separate.
            safe_voice = re.sub(r'[<>:"/\\|?*\x00-\x1f]', '_', row['name']).rstrip(' .') or '声音'
            role_name = metadata.get(row['role_id'], {}).get('display_name', row['role_id'])
            safe_role = re.sub(r'[<>:"/\\|?*\x00-\x1f]', '_', role_name).rstrip(' .') or '角色'
            name = f"{row['source_sentence_id']}_{safe_role}_{safe_voice}_候选{order[row['project_voice_id']]:02}.wav"
            _name(name)
            target = folder / name
            reject_links(target)
            require(not target.exists() or digest(target.read_bytes().hex()) == row['audio_hash'],
                    'file_conflict', 'Published audio changed; keep it and choose a new task/version.')
            outputs.append({**row, 'audio_path': str(target), 'source_path': str(source)})
        for row in outputs:
            target = Path(row['audio_path'])
            target.parent.mkdir(parents=True, exist_ok=True)
            if not target.exists():
                # Exclusive creation protects old deliveries from accidental replacement.
                with target.open('xb') as stream, Path(row['source_path']).open('rb') as source:
                    shutil.copyfileobj(source, stream)
            require(digest(target.read_bytes().hex()) == row['audio_hash'], 'artifact_repair_required', 'Delivery copy differs.')
        records[audition_id].update({'audio': outputs, 'unavailable': result['unavailable'], 'status': result['status']})
        atomic_write(registry, records)
    index = refresh_index(core, task_id, title)
    return {**info, **result, 'audio': outputs, 'delivery_dir': str(folder), 'index_path': index['index_path']}


def refresh_index(core, task_id, title):
    """Index actual delivery files only; the index does not assert task completion."""
    from .providers import duration
    info = workspace(core, task_id, title)
    folder = _delivery(core, title)
    target = folder / '文件索引.md'
    receipt = core.managed_path(f'.makesound/workspace/{task_id}/index.json')
    with file_lock(receipt.with_suffix('.lock')):
        reject_links(target)
        if target.exists():
            require(receipt.exists() and read_json(receipt)['hash'] == digest(target.read_bytes().hex()),
                    'file_conflict', 'Index was changed outside the tool; keep it for review.')
        rows = ['# 文件索引', '', f'任务：{title}', '',
                '本页按磁盘实际文件列出入口，不代表整稿已完成。试听、正式版本及缺失范围以交付说明和确认单为准。', '']
        count = 0
        if folder.exists():
            for path in sorted(folder.rglob('*')):
                reject_links(path)
                require(path.resolve().is_relative_to(folder.resolve()), 'unsafe_path', 'Index path escaped task.')
                if path.is_file() and path.suffix.lower() in {'.wav', '.srt', '.md'} and path != target:
                    relative = path.relative_to(folder).as_posix()
                    label = relative.replace('[', '（').replace(']', '）')
                    suffix = f'（{duration(path):.2f} 秒）' if path.suffix.lower() == '.wav' else ''
                    rows.append(f'- [{label}]({quote(relative, safe="/")}){suffix}')
                    count += 1
        if not count:
            rows.append('暂无交付文件。')
        payload = ('\n'.join(rows) + '\n').encode('utf-8')
        folder.mkdir(parents=True, exist_ok=True)
        # Same-task lock serializes tool updates; original audio/docs are untouched.
        temporary = folder / '.文件索引.tmp'
        reject_links(temporary)
        require(not temporary.exists(), 'file_conflict', 'Index temporary file already exists.')
        with temporary.open('xb') as stream:
            stream.write(payload)
        temporary.replace(target)
        atomic_write(receipt, {'hash': digest(payload.hex()), 'file_count': count})
    return {**info, 'index_path': str(target), 'file_count': count}


def main(argv=None):
    if hasattr(sys.stdout, 'reconfigure'):
        sys.stdout.reconfigure(encoding='utf-8')
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=['workspace', 'organize', 'publish-audition', 'index'])
    parser.add_argument('--project', required=True)
    parser.add_argument('--task', required=True)
    parser.add_argument('--title', required=True)
    parser.add_argument('--input', action='append', default=[])
    parser.add_argument('--audition')
    args = parser.parse_args(argv)
    try:
        core = ProjectCore(args.project)
        if args.action == 'organize':
            result = organize(core, args.task, args.title, args.input)
        elif args.action == 'publish-audition':
            result = publish_audition(core, args.task, args.title, args.audition)
        elif args.action == 'index':
            result = refresh_index(core, args.task, args.title)
        else:
            result = workspace(core, args.task, args.title)
        print(json.dumps(result, ensure_ascii=False))
        return 0
    except MakeSoundError as exc:
        print(json.dumps({'status': 'error', 'error': exc.code, 'message': str(exc)}, ensure_ascii=False))
        return 2


if __name__ == '__main__':
    raise SystemExit(main())
