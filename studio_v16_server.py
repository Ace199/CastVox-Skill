"""Secured persistent Studio server; legacy studio_server.py remains an explicit Mock."""
import argparse
import hmac
import json
import secrets
import socket
import time
import threading
from pathlib import Path
from http.server import ThreadingHTTPServer
from urllib.parse import urlsplit

from makesound.core_v16 import ProjectCore
from makesound.errors import MakeSoundError, require
from makesound.studio_backend import StudioBackend
from makesound.storage import _pairs
from makesound.ui_locale import resolve_ui_language
from studio_server import Handler as StaticHandler


class Handler(StaticHandler):
    def _guard(self, write=False):
        port = self.server.server_port
        host = self.headers.get("Host")
        require(host in {f"127.0.0.1:{port}", f"localhost:{port}"}, "forbidden", "Invalid Host.")
        origin = self.headers.get("Origin")
        require(origin is None and not write or origin == f"http://{host}", "forbidden", "Invalid Origin.")
        require(hmac.compare_digest(self.headers.get("Authorization", ""), "Bearer " + self.server.session_token),
                "forbidden", "Session authorization is required.")
        if write:
            require(hmac.compare_digest(self.headers.get("X-CSRF-Token", ""), self.server.csrf_token),
                    "forbidden", "CSRF authorization is required.")

    def _json(self, obj, status=200):
        payload = json.dumps(obj, ensure_ascii=False, allow_nan=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(payload)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.end_headers()
        self.wfile.write(payload)

    def _failure(self, exc):
        code = exc.code if isinstance(exc, MakeSoundError) else "invalid_request"
        status = 403 if code == "forbidden" else 409 if code in {"revision_conflict", "answer_immutable"} else 404 if code == "not_found" else 400
        if urlsplit(self.path).path.startswith('/api/host-bridge/v1/'):
            from host_bridge import BridgeError
            from host_bridge.protocol import error_result
            self._json(error_result(BridgeError(code, 'Request rejected; inspect the protocol fields.'),
                                    {'protocol_version': '1.0'}, task_id=self.server.question_id,
                                    application='soundmaker'), status)
        else:
            self._json({"error": code, "message": "Request was rejected; reload configuration or repair the indicated field."}, status)
        # A rejected POST may still have unread bytes (including a dishonest
        # Content-Length). Closing immediately can reset TCP on Windows and lose
        # the error response. Send FIN first and drain only a bounded amount/time.
        self.close_connection = True
        try:
            self.wfile.flush()
            self.connection.shutdown(socket.SHUT_WR)
            self.connection.settimeout(.05)
            deadline, remaining = time.monotonic() + .05, 1024 * 1024
            while remaining > 0 and time.monotonic() < deadline:
                received = self.connection.recv(min(65536, remaining))
                if not received:
                    break
                remaining -= len(received)
        except OSError:
            pass

    def do_GET(self):
        path = urlsplit(self.path).path
        if path == '/js/session.js':
            host = self.headers.get('Host')
            if (host not in {f'127.0.0.1:{self.server.server_port}', f'localhost:{self.server.server_port}'}
                    or self.headers.get('Origin') not in {None, f'http://{host}'}
                    or self.headers.get('Sec-Fetch-Site') not in {None, 'same-origin', 'none'}):
                self.send_error(403)
                return
            payload = ('export const session = Object.freeze(' + json.dumps({
                'mode': 'persistent', 'token': self.server.session_token, 'csrf': self.server.csrf_token,
                'question_id': self.server.question_id, 'ui_language': self.server.ui_language,
                'project_id': self.server.backend.core.read()['project_id']}) + ');').encode('utf-8')
            self.send_response(200)
            self.send_header('Content-Type', 'text/javascript; charset=utf-8')
            self.send_header('Content-Length', str(len(payload)))
            self.send_header('Cross-Origin-Resource-Policy', 'same-origin')
            self.send_header('X-Content-Type-Options', 'nosniff')
            self.end_headers()
            self.wfile.write(payload)
            return
        if not path.startswith("/api/"):
            return super().do_GET()
        try:
            self._guard()
            require(not urlsplit(self.path).query, "invalid_request", "API query parameters are not supported.")
            if path == '/api/host-bridge/v1/task' and getattr(self.server, 'bridge_api', None):
                return self._json(self.server.bridge_api.read())
            if path in {"/api/providers", "/api/v16/providers"}:
                return self._json(self.server.backend.providers())
            if path == "/api/v16/state":
                return self._json(self.server.backend.state())
            if path.startswith("/api/v16/questions/"):
                return self._json(self.server.backend.question(path.removeprefix("/api/v16/questions/")))
            if path.startswith("/api/v16/preview/"):
                vid = path.removeprefix("/api/v16/preview/")
                from makesound.validation import identifier
                identifier(vid)
                require(vid in self.server.backend.core.read()["voices"], "not_found", "Voice does not exist.")
                state = self.server.backend.core.preview_state(vid)
                require(state["status"] in {"current", "before_adjustment"}, "not_found", "Preview is unavailable.")
                audio = self.server.backend.core.managed_path(state["preview"]["path"]).read_bytes()
                self.send_response(200)
                self.send_header("Content-Type", "audio/wav")
                self.send_header("Content-Length", str(len(audio)))
                self.send_header("Cache-Control", "no-store")
                self.send_header("X-Content-Type-Options", "nosniff")
                self.end_headers()
                self.wfile.write(audio)
                return
            require(False, "not_found", "Unknown endpoint.")
        except Exception as exc:
            self._failure(exc)

    def do_POST(self):
        try:
            self._guard(write=True)
            require(self.headers.get("Content-Type") == "application/json", "invalid_request", "Expected JSON.")
            length = int(self.headers.get("Content-Length", "-1"))
            require(0 < length <= 1024 * 1024 and not self.headers.get("Transfer-Encoding"), "invalid_request", "Invalid request size.")
            body = json.loads(self.rfile.read(length).decode("utf-8"), object_pairs_hook=_pairs,
                              parse_constant=lambda _: (_ for _ in ()).throw(ValueError()))
            path = urlsplit(self.path)
            if path.path == '/api/host-bridge/v1/submit' and not path.query and getattr(self.server, 'bridge_api', None):
                try:
                    return self._json(self.server.bridge_api.submit(body))
                except Exception as error:
                    from host_bridge import BridgeError
                    from host_bridge.protocol import error_result
                    if not isinstance(error, BridgeError):
                        error = BridgeError('invalid_request', 'Submission rejected; inspect the protocol fields.')
                    status = 409 if error.code in {'revision_conflict', 'submission_conflict', 'task_completed'} else 400
                    return self._json(error_result(error, {'protocol_version': '1.0'}, task_id=self.server.question_id,
                                                   application='soundmaker'), status)
            if path.path == '/api/providers/open-config' and not path.query:
                from studio_config_editor import open_config
                from makesound import validation as v
                v.shape(body, {'provider'}, {'provider'})
                require(body['provider'] in {'minimax', 'volcengine'})
                descriptor = next(p for p in self.server.backend.providers()['providers'] if p['id'] == body['provider'])
                from studio_config_editor import config_path
                require(descriptor['config_edit']['available'] and
                        self.server.backend.config_paths.get(body['provider']) == config_path(body['provider'], self.server.config_dir),
                        'forbidden', 'Configuration path is not enabled by this launcher.')
                return self._json(open_config(body['provider'], self.server.config_dir))
            if path.path == '/api/v16/defaults/open-config' and not path.query:
                from studio_config_editor import open_default_config
                from makesound import validation as v
                v.shape(body, set())
                return self._json(open_default_config(self.server.backend.core.root))
            require(path.path.startswith("/api/v16/") and not path.query, "not_found", "Unknown endpoint.")
            action = path.path.removeprefix("/api/v16/")
            if self.server.question_id:
                require(action != 'complete', 'missing_roles', 'Submit the task bindings first.')
                if action in {'answers', 'assignments'}:
                    require(body.get('question_id') == self.server.question_id,
                            'session_mismatch', 'This Studio belongs to a different question.')
            result = self.server.backend.dispatch(action, body)
            completed = self.server.close_after_answer and action == 'answers' and self.server.question_id
            if completed:
                result['session_complete'] = True
                from makesound.harness_resume import notify
                try:
                    result['wake'] = notify(self.server.backend.core, self.server.question_id)
                except Exception:
                    result['wake'] = {'status': 'failed'}
            try:
                self._json(result)
                if completed:
                    self.wfile.flush()
            finally:
                # Answer and notification are already processed. A closed browser
                # must not strand a managed host task on an immutable question.
                if completed:
                    threading.Thread(target=self.server.shutdown, daemon=True).start()
        except Exception as exc:
            self._failure(exc)


def create_server(backend, port=0, *, question_id=None, config_dir=None, close_after_answer=False, ui_language=None):
    language = resolve_ui_language(ui_language)
    require(not close_after_answer or question_id, 'missing_roles', 'One-session mode requires a Question.')
    if question_id:
        backend.question(question_id)
    server = ThreadingHTTPServer(("127.0.0.1", port), Handler)
    server.backend = backend
    server.session_token = secrets.token_urlsafe(32)
    server.csrf_token = secrets.token_urlsafe(32)
    server.config_dir = config_dir
    server.question_id = question_id
    server.close_after_answer = close_after_answer
    server.ui_language = language
    return server


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--project", required=True)
    parser.add_argument("--port", type=int, default=0)
    parser.add_argument("--fake", action="store_true", help="Expose offline Fake model for testing")
    parser.add_argument('--question', help='Existing persisted Question ID supplied by the trusted launcher')
    parser.add_argument('--once', action='store_true', help='Exit after successfully saving this Question answer')
    parser.add_argument('--config-dir', type=Path, help='Explicit isolated provider configuration directory')
    parser.add_argument('--ui-language', help='Chinese/English UI override (zh-CN or en); defaults to CASTVOX_UI_LANGUAGE handoff, then browser')
    args = parser.parse_args()
    from studio_config_editor import config_path
    directory = args.config_dir.resolve() if args.config_dir else None
    backend = StudioBackend(ProjectCore(args.project), allow_fake=args.fake, config_dir=directory,
                            config_paths={p: config_path(p, directory) for p in ('minimax', 'volcengine')})
    backend.core.read()
    server = create_server(backend, args.port, question_id=args.question, config_dir=directory,
                           close_after_answer=args.once, ui_language=args.ui_language)
    print(json.dumps({"url": f"http://127.0.0.1:{server.server_port}", 'mode': 'persistent',
                      'question_id': args.question, "synthesis": "not_exposed"}), flush=True)
    try:
        server.serve_forever()
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
