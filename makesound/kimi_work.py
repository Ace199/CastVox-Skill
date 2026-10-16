"""Kimi Work 3.2.8 local control. Never infer an origin from chat recency."""
import hashlib
from contextlib import closing
import json
import os
from pathlib import Path
import shlex
import sqlite3
import subprocess
from urllib.parse import urlsplit

from .errors import require


def _endpoint(lock_path):
    require(lock_path.is_file(), 'harness_unavailable', 'Kimi Work is not available.')
    data = json.loads(lock_path.read_text(encoding='utf-8'))
    endpoint = data.get('controlEndpoint', {})
    parsed = urlsplit(endpoint.get('url', ''))
    require(parsed.scheme == 'ws' and parsed.hostname == '127.0.0.1' and parsed.port
            and not parsed.username and not parsed.password and parsed.path == '/control'
            and not parsed.query and not parsed.fragment, 'invalid_target', 'Expected local Kimi control.')
    token = endpoint.get('auth', {}).get('token')
    require(isinstance(token, str) and token and '\r' not in token and '\n' not in token
            and isinstance(data.get('generationId'), str) and data['generationId'],
            'invalid_target', 'Kimi control identity is incomplete.')
    return data['generationId'], endpoint['url'], hashlib.sha256(token.encode()).hexdigest(), token


def _pending_launch(wire, qid, project):
    with wire.open('rb') as stream:
        size = stream.seek(0, 2)
        stream.seek(max(0, size - 2 * 1024 * 1024))
        if stream.tell():
            stream.readline()
        lines = stream.read().decode('utf-8').splitlines()
    calls = {}
    for line in lines:
        try:
            event = json.loads(line).get('event', {})
        except (ValueError, AttributeError):
            continue
        call_id = event.get('toolCallId')
        if event.get('type') == 'tool.result':
            calls.pop(call_id, None)
        elif event.get('type') == 'tool.call' and event.get('name') in {'Bash', 'Shell'} and call_id:
            calls[call_id] = event.get('args', {}).get('command', '')
    for command in calls.values():
        try:
            tokens = shlex.split(command)
            module, question, target = tokens.index('-m'), tokens.index('--question'), tokens.index('--project')
            if (tokens[module + 1] == 'makesound.studio_session' and tokens[question + 1] == qid
                    and Path(tokens[target + 1]).resolve() == project):
                return True
        except (ValueError, IndexError, TypeError):
            continue
    return False


def environment_target(core, qid):
    if os.environ.get('KIMI_AGENT_CLIENT_ID') != 'kimiwork':
        return None
    require(core is not None and qid, 'harness_unavailable', 'Kimi registration needs the exact binding task.')
    share = os.environ.get('KIMI_SHARE_DIR')
    require(bool(share) and Path(share).is_absolute(), 'harness_unavailable', 'Kimi share directory is missing.')
    base = Path(share).resolve() / 'daimon'
    home = (base / 'runtime/kimi-code/home/sessions').resolve()
    matches = []
    for lock in (base / 'agents').glob('*/state-root.lock'):
        db = lock.parent / 'sessions/hosted-logical/conversations.sqlite'
        if not db.is_file():
            continue
        with closing(sqlite3.connect(db.as_uri() + '?mode=ro', uri=True, timeout=2)) as connection:
            rows = connection.execute('SELECT agent_id, conversation_key, workspace_path, kernel_records_path FROM conversations')
            for agent, key, workspace, records in rows:
                if not records or not workspace or Path(workspace).resolve() != core.root.resolve():
                    continue
                wire = Path(records).resolve()
                if wire.is_relative_to(home) and wire.is_file() and _pending_launch(wire, qid, core.root.resolve()):
                    matches.append((lock, agent, key))
    require(len(matches) == 1, 'harness_unavailable',
            'Cannot uniquely identify the originating Kimi tool call; no notification target was guessed.')
    lock, agent, key = matches[0]
    generation, url, fingerprint, _ = _endpoint(lock)
    require(isinstance(agent, str) and isinstance(key, str) and key.startswith(f'agent:{agent}:')
            and len(key) < 4096, 'invalid_target', 'Invalid Kimi conversation identity.')
    return {'harness': 'kimi_work', 'lock_path': str(lock), 'agent_id': agent,
            'conversation_key': key, 'generation_id': generation, 'endpoint_url': url,
            'token_fingerprint': fingerprint,
            'node_path': os.environ.get('DAIMON_BUNDLE_NODE_BIN', ''),
            'package_root': os.environ.get('DAIMON_ADAPTER_PACKAGE_ROOT', '')}


def send(target, message):
    generation, url, fingerprint, token = _endpoint(Path(target['lock_path']))
    require((generation, url, fingerprint) == (target['generation_id'], target['endpoint_url'], target['token_fingerprint']),
            'session_mismatch', 'The originating Kimi runtime has changed; no notification sent.')
    node, package = Path(target['node_path']), Path(target['package_root'])
    require(node.is_file() and (package / 'node_modules/ws').is_dir(),
            'harness_unavailable', 'The original Kimi runtime is unavailable.')
    script = Path(__file__).resolve().parent.parent / 'scripts/kimi_work_control.cjs'
    payload = {'url': url, 'token': token, 'ws_module': str(package / 'node_modules/ws'),
               'agent_id': target['agent_id'], 'conversation_key': target['conversation_key'], 'message': message}
    result = subprocess.run([str(node), str(script)], input=json.dumps(payload).encode('utf-8'),
                            capture_output=True, timeout=15,
                            creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0)
    if result.returncode != 0:
        return {'status': 'unknown'}
    try:
        receipt = json.loads(result.stdout)
    except (ValueError, UnicodeError):
        return {'status': 'unknown'}
    require(receipt.get('status') in {'queued', 'unknown', 'failed'}, 'delivery_failed', 'Invalid Kimi receipt.')
    return {k: receipt[k] for k in ('status', 'turn_id') if k in receipt}
