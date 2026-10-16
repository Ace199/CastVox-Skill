"""Legacy engine-only protocol probe; NOT a supported desktop resume path.

Production uses workbuddy_task. The desktop rejects this endpoint's output as
request-frame:zombie-prevented, despite the persisted model reply.
"""
import hashlib
import json
import os
import re
import urllib.error
import urllib.request
from urllib.parse import quote, urlsplit

from .errors import require


def environment_target():
    if not os.environ.get('WORKBUDDY_CONFIG_DIR'):
        return None
    session = os.environ.get('CODEBUDDY_SESSION_ID', '')
    password = os.environ.get('CODEBUDDY_GATEWAY_PASSWORD', '')
    try:
        parsed = urlsplit(os.environ.get('CODEBUDDY_SERVICE_PROXY_URL', ''))
        valid = (parsed.scheme == 'http' and parsed.hostname == '127.0.0.1' and parsed.port
                 and not parsed.username and not parsed.password and not parsed.query and not parsed.fragment
                 and parsed.path == '/internal/hooks/services/invoke')
    except ValueError:
        valid = False
    require(valid and re.fullmatch(r'[A-Za-z0-9_-]{1,128}', session) and
            0 < len(password) <= 4096 and all(32 <= ord(c) < 127 for c in password),
            'harness_unavailable',
            'WorkBuddy session identity or inherited gateway credential is unavailable. Run from its own command tool.')
    return {'harness': 'workbuddy_native', 'session_id': session,
            'origin': f'http://127.0.0.1:{parsed.port}',
            'token_fingerprint': hashlib.sha256(password.encode()).hexdigest()}


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def _request(target, path, *, body=None):
    headers = {'Authorization': 'Bearer ' + os.environ['CODEBUDDY_GATEWAY_PASSWORD'],
               'Content-Type': 'application/json'}
    data = None if body is None else json.dumps(body, ensure_ascii=False).encode('utf-8')
    request = urllib.request.Request(target['origin'] + path, data=data, headers=headers)
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}), _NoRedirect())
    with opener.open(request, timeout=20 if body is not None else 3) as response:
        raw = response.read(16385)
        require(len(raw) <= 16384, 'delivery_failed', 'Invalid WorkBuddy response size.')
        result = json.loads(raw)
    require(isinstance(result, dict) and isinstance(result.get('data'), dict) and not result.get('error'),
            'delivery_failed', 'WorkBuddy did not return a valid acknowledgement.')
    return result['data']


def check_live(target):
    current = environment_target()
    require(current is not None and all(target.get(k) == v for k, v in current.items()),
            'session_mismatch', 'WorkBuddy sender no longer belongs to this binding session.')
    result = _request(current, '/api/v1/sessions/live')
    require(result.get('sessionId') == current['session_id'], 'session_mismatch',
            'The originating WorkBuddy session is no longer live. No other chat was selected.')
    return current


def send(target, message):
    current = check_live(target)
    # The host checks the same session again, closing the race after the GET.
    try:
        result = _request(current, '/api/v1/sessions/' + quote(current['session_id'], safe='') + '/reply',
                          body={'text': message})
    except urllib.error.HTTPError as exc:
        return {'status': 'failed' if exc.code in {400, 401, 403, 404, 409} else 'unknown'}
    except Exception:
        # runDefault may already have consumed the reply, even if its response was lost.
        return {'status': 'unknown'}
    return {'status': 'delivered' if result.get('delivered') is True else 'unknown'}
