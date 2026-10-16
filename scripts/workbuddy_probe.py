"""Run from WorkBuddy's own command tool. No network, model, or provider calls."""
import hashlib
import json
import os
from pathlib import Path
import sys
from urllib.parse import urlsplit


def inspect_environment(environ):
    session = environ.get('CODEBUDDY_SESSION_ID')
    if not isinstance(session, str) or not 0 < len(session) <= 128 or any(ord(c) < 32 for c in session):
        session = None
    origin = None
    proxy_route = None
    try:
        parsed = urlsplit(environ.get('CODEBUDDY_SERVICE_PROXY_URL', ''))
        if (parsed.scheme == 'http' and parsed.hostname in {'127.0.0.1', 'localhost', '::1'}
                and parsed.port and not parsed.username and not parsed.password):
            host = '[::1]' if parsed.hostname == '::1' else parsed.hostname
            origin = f'http://{host}:{parsed.port}'
            # Never echo arbitrary path/query/fragment: they can contain credentials.
            if parsed.path in {'/internal/hooks/services/invoke', '/internal/services/invoke'}:
                proxy_route = parsed.path
    except (ValueError, TypeError):
        pass
    return {
        'test_id': 'SM_WORKBUDDY_ENV_01',
        'status': 'environment_captured' if session else 'run_inside_workbuddy',
        'session_id': session,
        'service_proxy_origin': origin,
        'known_service_proxy_route': proxy_route,
        'host_markers_present': [name for name in (
            'WORKBUDDY_CONFIG_DIR', 'CODEBUDDY_PROJECT_DIR', 'CODEBUDDY_SESSION_ID',
            'CODEBUDDY_TOOL_CALL_ID', 'CODEBUDDY_SERVICE_PROXY_URL', 'CODEBUDDY_MCP_CONFIG',
        ) if environ.get(name)],
        'other_harness_present': any(environ.get(name) for name in (
            'CODEX_THREAD_ID', 'CLAUDE_CODE_MESSAGING_SOCKET', 'CLAUDE_CODE_MESSAGING_TOKEN',
        )),
        'wake_verified': False,
        'network_requests': 0,
        'synthesis_requests': 0,
    }


def main():
    result = inspect_environment(os.environ)
    if result['session_id']:
        root = Path(__file__).resolve().parents[1]
        folder = root / 'outputs' / 'workbuddy-probe'
        folder.mkdir(parents=True, exist_ok=True)
        filename = hashlib.sha256(result['session_id'].encode('utf-8')).hexdigest()[:20] + '.json'
        report = folder / filename
        report.write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
        result['report_path'] = str(report)
    else:
        result['next_step'] = 'Run this script using the command tool in the originating WorkBuddy chat.'
    print(json.dumps(result, ensure_ascii=True, indent=2))
    return 0 if result['session_id'] else 2


if __name__ == '__main__':
    sys.exit(main())
