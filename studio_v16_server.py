"""Optional secured V1.6 server. Does not change the existing UI or its Mock server."""
import argparse
import hmac
import json
import secrets
from http.server import ThreadingHTTPServer
from urllib.parse import urlsplit

from makesound.core_v16 import ProjectCore
from makesound.errors import MakeSoundError, require
from makesound.studio_backend import StudioBackend
from makesound.storage import _pairs
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
        self._json({"error": code, "message": "Request was rejected; reload configuration or repair the indicated field."}, status)

    def do_GET(self):
        path = urlsplit(self.path).path
        if not path.startswith("/api/"):
            return super().do_GET()
        try:
            self._guard()
            require(not urlsplit(self.path).query, "invalid_request", "API query parameters are not supported.")
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
            require(path.path.startswith("/api/v16/") and not path.query, "not_found", "Unknown endpoint.")
            result = self.server.backend.dispatch(path.path.removeprefix("/api/v16/"), body)
            self._json(result)
        except Exception as exc:
            self._failure(exc)


def create_server(backend, port=0):
    server = ThreadingHTTPServer(("127.0.0.1", port), Handler)
    server.backend = backend
    server.session_token = secrets.token_urlsafe(32)
    server.csrf_token = secrets.token_urlsafe(32)
    server.config_dir = None
    return server


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--project", required=True)
    parser.add_argument("--port", type=int, default=0)
    parser.add_argument("--fake", action="store_true", help="Expose offline Fake model for testing")
    args = parser.parse_args()
    backend = StudioBackend(ProjectCore(args.project), allow_fake=args.fake)
    backend.core.read()
    server = create_server(backend, args.port)
    print(json.dumps({"url": f"http://127.0.0.1:{server.server_port}", "session_token": server.session_token,
                      "csrf_token": server.csrf_token, "synthesis": "not_exposed"}), flush=True)
    server.serve_forever()


if __name__ == "__main__":
    main()
