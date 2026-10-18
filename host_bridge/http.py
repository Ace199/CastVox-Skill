"""Reference loopback HTTP implementation of the application submission protocol."""
import hmac
import json
import secrets
import socket
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlsplit
from . import BridgeError, require
from .protocol import MAX_BYTES, error_result, loads, submission, validate_result

TASK_PATH = '/api/host-bridge/v1/task'
SUBMIT_PATH = '/api/host-bridge/v1/submit'


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *args):
        pass  # stdout belongs to MCP; no payload/token logging.

    def _guard(self, *, write=False, session=False):
        host = self.headers.get('Host')
        require(host in {f'127.0.0.1:{self.server.server_port}', f'localhost:{self.server.server_port}'},
                'forbidden', 'Invalid Host.')
        origin = self.headers.get('Origin')
        require(origin == f'http://{host}' or not write and origin is None, 'forbidden', 'Invalid Origin.')
        require(self.headers.get('Sec-Fetch-Site') in {None, 'same-origin', 'none'}, 'forbidden', 'Cross-site request rejected.')
        if not session:
            require(hmac.compare_digest(self.headers.get('Authorization', ''), 'Bearer ' + self.server.token),
                    'forbidden', 'Session authorization is required.')
        if write:
            require(hmac.compare_digest(self.headers.get('X-CSRF-Token', ''), self.server.csrf),
                    'forbidden', 'CSRF authorization is required.')

    def _send(self, body, status=200, content_type='application/json; charset=utf-8'):
        encoded = body.encode('utf-8')
        self.send_response(status)
        self.send_header('Content-Type', content_type)
        self.send_header('Content-Length', str(len(encoded)))
        self.send_header('Cache-Control', 'no-store')
        self.send_header('X-Content-Type-Options', 'nosniff')
        self.send_header('Cross-Origin-Resource-Policy', 'same-origin')
        self.end_headers()
        self.wfile.write(encoded)

    def _json(self, body, status=200):
        self._send(json.dumps(body, ensure_ascii=False, allow_nan=False), status)

    def _failure(self, error):
        if not isinstance(error, BridgeError):
            error = BridgeError('invalid_request', 'Request rejected; inspect the protocol fields.')
        status = 403 if error.code == 'forbidden' else 404 if error.code == 'not_found' else 409 if error.code in {
            'revision_conflict', 'submission_conflict', 'task_completed', 'request_conflict'} else 400
        self._json(error_result(error, {'protocol_version': '1.0'},
                                task_id=self.server.task_id, application=self.server.application), status)
        self.close_connection = True
        try:
            self.wfile.flush()
            self.connection.shutdown(socket.SHUT_WR)
            self.connection.settimeout(.05)
            deadline, remaining = time.monotonic() + .05, MAX_BYTES
            while remaining > 0 and time.monotonic() < deadline:
                received = self.connection.recv(min(65536, remaining))
                if not received:
                    break
                remaining -= len(received)
        except OSError:
            pass

    def do_GET(self):
        try:
            path = urlsplit(self.path)
            require(not path.query, message='Query parameters are not supported.')
            if path.path == '/':
                self._guard(session=True)
                return self._send(self.server.page, content_type='text/html; charset=utf-8')
            if path.path == '/host-bridge/session.js':
                self._guard(session=True)
                session = {'protocol_version': '1.0', 'task_id': self.server.api.read()['task_id'],
                           'token': self.server.token, 'csrf': self.server.csrf,
                           'task_url': TASK_PATH, 'submit_url': SUBMIT_PATH}
                return self._send('export const session = Object.freeze(' + json.dumps(session) + ');',
                                  content_type='text/javascript; charset=utf-8')
            self._guard()
            require(path.path == TASK_PATH, 'not_found', 'Unknown endpoint.')
            self._json(validate_result(self.server.api.read()))
        except Exception as error:
            self._failure(error)

    def do_POST(self):
        try:
            # Bound and consume the body before rejecting headers so a rejected
            # request receives its JSON error instead of a Windows TCP reset.
            self.connection.settimeout(5)
            length = int(self.headers.get('Content-Length', '-1'))
            require(0 < length <= MAX_BYTES and not self.headers.get('Transfer-Encoding'),
                    message='A bounded Content-Length is required; chunked requests are unsupported.')
            body = self.rfile.read(length)
            require(len(body) == length, message='Incomplete request body.')
            self._guard(write=True)
            require(self.headers.get('Content-Type', '').split(';')[0].strip() == 'application/json',
                    message='Expected application/json.')
            path = urlsplit(self.path)
            require(path.path == SUBMIT_PATH and not path.query, 'not_found', 'Unknown endpoint.')
            value = submission(loads(body))
            require(value['task_id'] == self.server.api.read()['task_id'], 'task_mismatch', 'This page belongs to another task.')
            saved = validate_result(self.server.api.submit(value))
            require(saved['task_id'] == self.server.task_id, 'task_mismatch', 'Application returned a different task.')
            self._json(saved)
        except Exception as error:
            self._failure(error)


def create_server(api, page, *, port=0):
    """api.read() and api.submit(body) must return validated v1 result envelopes."""
    initial = validate_result(api.read())
    server = ThreadingHTTPServer(('127.0.0.1', port), Handler)
    server.api, server.page = api, page
    server.task_id, server.application = initial['task_id'], initial.get('application')
    server.token, server.csrf = secrets.token_urlsafe(32), secrets.token_urlsafe(32)
    return server
