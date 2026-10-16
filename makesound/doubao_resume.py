"""Doubao Windows 2.32.5 local continuation. No copied credentials or cloud fallback."""
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
from urllib.parse import urlsplit

from .errors import require

BRIDGE_PATH = Path(__file__).resolve().parents[1] / '.makesound/doubao-bridge.json'


def _bridge():
    require(BRIDGE_PATH.is_file(), 'harness_unavailable', 'The temporary Doubao bridge is not configured.')
    data = json.loads(BRIDGE_PATH.read_text(encoding='utf-8'))
    address = urlsplit(data.get('endpoint', ''))
    require(address.scheme == 'http' and address.hostname == '127.0.0.1' and address.port
            and not address.username and not address.password and not address.path
            and not address.query and not address.fragment,
            'invalid_target', 'Expected a loopback Doubao endpoint.')
    require(re.fullmatch(r'/devtools/browser/[A-Za-z0-9-]+', data.get('browser_path', ''))
            and isinstance(data.get('profile_path'), str) and Path(data['profile_path']).is_absolute(),
            'invalid_target', 'Doubao instance identity is missing.')
    return {k: data[k] for k in ('endpoint', 'browser_path', 'profile_path')}


def _control(op, target, message=None):
    node = shutil.which('node')
    require(node is not None, 'harness_unavailable', 'Node.js 22+ is required for the local Doubao bridge.')
    payload = {'op': op, 'target': target}
    if message is not None:
        payload['message'] = message
    script = Path(__file__).resolve().parents[1] / 'scripts/doubao_control.cjs'
    result = subprocess.run([node, str(script)], input=json.dumps(payload).encode('utf-8'),
                            capture_output=True, timeout=35,
                            creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0)
    require(result.returncode == 0, 'harness_unavailable', 'Doubao bridge could not verify the original local session.')
    data = json.loads(result.stdout)
    require(isinstance(data, dict) and not data.get('error'), 'harness_unavailable', 'Doubao bridge is unavailable.')
    return data


def environment_target(core, qid):
    if not os.environ.get('DOUBAO_OFFICE_APP_ID'):
        return None
    require(core is not None and qid, 'harness_unavailable', 'Doubao registration requires an exact project and Question.')
    cid = os.environ.get('MCP_VM_CONVERSATION_ID', '')
    require(os.environ.get('DOUBAO_OFFICE_APP_ID') == '582478' and re.fullmatch(r'[0-9]{12,24}', cid),
            'invalid_target', 'The originating Doubao Windows identity is incomplete.')
    bridge = _bridge()
    info = _control('probe', {**bridge, 'conversation_id': cid})
    require(info.get('conversation_id') == cid and info.get('app_id') == '582478'
            and info.get('runtime_type') == 2 and bool(info.get('project_id'))
            and isinstance(info.get('workspace'), str) and Path(info['workspace']).is_absolute(),
            'session_mismatch', 'Doubao session or local execution context differs.')
    # A deliberately isolated test/task subproject may live inside the chat workspace.
    require(core.root.resolve().is_relative_to(Path(info['workspace']).resolve()),
            'session_mismatch', 'The task is outside the originating Doubao project.')
    return {'harness': 'doubao', **bridge, **{k: info[k] for k in
            ('conversation_id', 'workspace', 'project_id', 'runtime_type', 'app_id', 'sandbox_auth_type')}}


def send(target, message):
    bridge = _bridge()
    require(all(target.get(k) == v for k, v in bridge.items()),
            'session_mismatch', 'The original Doubao instance has changed.')
    result = _control('send', target, message)
    require(result.get('status') in {'queued', 'failed', 'unknown', 'busy'},
            'delivery_failed', 'Doubao returned an invalid receipt.')
    return {k: result[k] for k in ('status', 'run_id') if k in result}
