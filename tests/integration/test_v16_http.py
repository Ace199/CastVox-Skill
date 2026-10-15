import http.client
import json
import socket
import threading
import unittest
from unittest.mock import patch

from makesound.core_v16 import ProjectCore
from makesound.generation import Generation
from makesound.studio_backend import StudioBackend
from studio_v16_server import create_server
from tests.helpers import Fixture
from tests.unit.test_v16 import SOURCE


class V16HTTP(Fixture, unittest.TestCase):
    def setUp(self):
        super().setUp()
        self.core = ProjectCore(self.a)
        self.backend = StudioBackend(self.core, config_paths={}, allow_fake=True)
        self.server = create_server(self.backend)
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        def cleanup():
            self.server.shutdown()
            self.server.server_close()
            self.thread.join(timeout=3)
        self.addCleanup(cleanup)
        # Permit only this test's loopback server; all other destinations trip.
        self.net.stop()
        original = socket.socket.connect
        port = self.server.server_port
        def local_only(sock, address):
            if address != ("127.0.0.1", port):
                raise AssertionError("External network forbidden")
            return original(sock, address)
        self.local_net = patch.object(socket.socket, "connect", local_only)
        self.local_net.start()
        self.addCleanup(self.local_net.stop)

    def request(self, path, body=None, headers=None, raw=None):
        port = self.server.server_port
        defaults = {"Authorization": "Bearer " + self.server.session_token,
                    "Origin": f"http://127.0.0.1:{port}", "X-CSRF-Token": self.server.csrf_token,
                    "Content-Type": "application/json"}
        defaults.update(headers or {})
        connection = http.client.HTTPConnection("127.0.0.1", port, timeout=3)
        try:
            payload = raw if raw is not None else json.dumps(body) if body is not None else None
            connection.request("POST" if body is not None or raw is not None else "GET", path, payload, defaults)
            response = connection.getresponse()
            content = response.read()
            return response.status, content, dict(response.getheaders())
        finally:
            connection.close()

    def add(self, **changes):
        body = {"name": "声音", "category": "male", "source": SOURCE, "revision": 0, **changes}
        status, raw, _ = self.request("/api/v16/voices/add", body)
        return status, json.loads(raw)

    def test_management_endpoints_revision_models_capabilities_no_synthesis(self):
        with patch("makesound.providers.FakeProvider.synthesize", side_effect=AssertionError("No synthesis permitted")):
            status, raw, _ = self.request("/api/v16/providers")
            self.assertEqual(status, 200)
            providers = json.loads(raw)["providers"]
            self.assertEqual(providers[-1]["capabilities"]["pitch"]["unit"], "semitone")
            self.assertEqual(providers[0]["capabilities"], {})
            status, result = self.add()
            self.assertEqual(status, 200)
            vid = result["project_voice_id"]
            for action, body in [("defaults", {"defaults": {"male": vid}, "revision": 1}),
                                 ("voices/edit", {"project_voice_id": vid, "patch": {"name": "新名"}, "revision": 2}),
                                 ("settings", {"settings": {"export_mode": "whole"}, "revision": 3})]:
                status, _, _ = self.request("/api/v16/" + action, body)
                self.assertEqual(status, 200)
            status, _, _ = self.request("/api/v16/defaults", {"defaults": {"general": None}, "revision": 0})
            self.assertEqual(status, 409)
            status, raw, _ = self.request("/api/v16/complete", {})
            self.assertFalse(json.loads(raw)["agent_resumed"])
            status, raw, _ = self.request("/api/v16/state")
            state = json.loads(raw)
            self.assertEqual(state["effective_defaults"]["male"], vid)
            self.assertEqual(state["preset"]["revision"], 4)

    def test_missing_token_csrf_bad_origin_host_and_remote_origin(self):
        for headers in ({"Authorization": ""}, {"Origin": "https://evil.invalid"}, {"Host": "evil.invalid"}):
            self.assertEqual(self.request("/api/v16/state", headers=headers)[0], 403)
        for headers in ({"X-CSRF-Token": ""}, {"Origin": ""}, {"Authorization": "Bearer wrong"}):
            self.assertEqual(self.request("/api/v16/complete", {}, headers=headers)[0], 403)
        self.assertEqual(self.request("/api/providers", headers={"Authorization": ""})[0], 403)

    def test_malformed_duplicate_oversize_and_no_synthesis_endpoint(self):
        for raw in ("[]", "{broken", '{"revision":0,"revision":1}', '{"x":NaN}'):
            self.assertEqual(self.request("/api/v16/complete", raw=raw)[0], 400)
        self.assertEqual(self.request("/api/v16/complete", {}, headers={"Content-Length": "1048577"})[0], 400)
        self.assertEqual(self.request("/api/v16/run", {})[0], 404)
        self.assertEqual(self.request("/api/v16/state?path=../../credentials")[0], 400)

    def test_models_exact_source_fixed_model_validation_and_secret_rejection(self):
        status, result = self.add(source={**SOURCE, "model": "unconfigured"})
        self.assertEqual(status, 400)
        self.assertEqual(result["error"], "model_not_configured")
        self.assertEqual(self.add(source={**SOURCE, "region": "wrong"})[0], 400)
        self.assertEqual(self.add(source={**SOURCE, "api_key": "DO_NOT_RETURN"})[0], 400)
        self.assertFalse(self.core.path.exists())

    def test_answer_persistence_and_no_waiting_management_resume_claim(self):
        _, result = self.add()
        vid = result["project_voice_id"]
        question = self.backend.questions.create("job_wait", "session_harness", ["r"])
        status, raw, _ = self.request("/api/v16/questions/" + question["question_id"])
        self.assertEqual(status, 200)
        self.assertEqual(json.loads(raw)["roles"], ["r"])
        self.assertNotIn("session_harness", raw.decode("utf-8"))
        status, raw, _ = self.request("/api/v16/answers", {"question_id": question["question_id"], "assignments": {"r": vid}})
        self.assertEqual(status, 200)
        self.assertFalse(json.loads(raw)["agent_resumed"])
        self.assertEqual(self.backend.questions.read(question["question_id"])["status"], "answered")
        self.assertEqual(self.request("/api/v16/answers", {"question_id": question["question_id"], "assignments": {"r": vid}})[0], 409)

    def test_preview_bytes_and_arbitrary_file_access_denied(self):
        _, result = self.add()
        vid = result["project_voice_id"]
        self.assertEqual(self.request("/api/v16/preview/" + vid)[0], 404)
        engine = Generation(self.core)
        snap = engine.freeze([{"paragraph_id": "p", "sentence_id": "s", "text": "原稿", "project_voice_id": vid}], confirmed=True, authorized=True)
        engine.run(snap["job_id"])
        status, audio, headers = self.request("/api/v16/preview/" + vid)
        self.assertEqual(status, 200)
        self.assertTrue(audio.startswith(b"RIFF"))
        self.assertEqual(headers["Content-Type"], "audio/wav")
        for path in ("/api/v16/preview/../../credentials", "/../makesound/core_v16.py", "/tests/test.py"):
            self.assertIn(self.request(path)[0], {400, 404})


if __name__ == "__main__":
    unittest.main()
