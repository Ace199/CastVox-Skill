"""Real loopback HTTP contract with a fake WorkBuddy host; no model or provider."""
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import os
import threading
import unittest
from unittest.mock import patch

from makesound.errors import MakeSoundError
from makesound.workbuddy_native import environment_target, send
from makesound.core_v16 import ProjectCore
from makesound.offline_harness import prepare
from makesound.questions import Questions
from makesound.harness_resume import _register_target, notify
from tests.helpers import Fixture


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *args):
        pass

    def respond(self, value, status=200):
        data = json.dumps(value).encode()
        self.send_response(status)
        self.send_header('Content-Type', 'application/json')
        self.send_header('Content-Length', str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def do_GET(self):
        if self.headers.get('Authorization') != 'Bearer fixture-private-gateway':
            return self.respond({'error': {}}, 401)
        self.respond({'data': {'sessionId': self.server.live_id, 'writerOccupied': True}})

    def do_POST(self):
        body = json.loads(self.rfile.read(int(self.headers['Content-Length'])))
        self.server.posts.append({'path': self.path, 'body': body,
                                  'authenticated': self.headers.get('Authorization') == 'Bearer fixture-private-gateway'})
        if self.server.drop_response:
            self.close_connection = True
            return
        if self.server.redirect:
            self.send_response(307)
            self.send_header('Location', '/must-not-follow')
            self.send_header('Content-Length', '0')
            self.end_headers()
            return
        self.respond({'data': {'delivered': True}})


class WorkBuddyTransport(Fixture, unittest.TestCase):
    def setUp(self):
        super().setUp()
        # Only the in-process loopback fake host is used in this test module.
        self.net.stop()
        self.server = ThreadingHTTPServer(('127.0.0.1', 0), Handler)
        self.server.live_id = 'own-session'
        self.server.posts = []
        self.server.redirect = False
        self.server.drop_response = False
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        self.env = {'WORKBUDDY_CONFIG_DIR': 'fixture-only', 'CODEBUDDY_SESSION_ID': 'own-session',
                    'CODEBUDDY_GATEWAY_PASSWORD': 'fixture-private-gateway',
                    'CODEBUDDY_SERVICE_PROXY_URL':
                    f'http://127.0.0.1:{self.server.server_port}/internal/hooks/services/invoke'}

    def tearDown(self):
        self.server.shutdown()
        self.server.server_close()
        self.thread.join(timeout=2)

    def test_real_authenticated_reply_is_addressed_to_original_session(self):
        with patch.dict(os.environ, self.env, clear=True):
            self.assertEqual(send(environment_target(), 'binding complete'), {'status': 'delivered'})
        self.assertEqual(self.server.posts, [{'path': '/api/v1/sessions/own-session/reply',
                         'body': {'text': 'binding complete'}, 'authenticated': True}])

    def test_switched_live_session_never_receives_post(self):
        self.server.live_id = 'other-window'
        with patch.dict(os.environ, self.env, clear=True), self.assertRaises(MakeSoundError):
            send(environment_target(), 'must not send')
        self.assertEqual(self.server.posts, [])

    def test_redirect_never_forwards_credential_or_repeats_post(self):
        self.server.redirect = True
        with patch.dict(os.environ, self.env, clear=True):
            self.assertEqual(send(environment_target(), 'binding complete'), {'status': 'unknown'})
        self.assertEqual(len(self.server.posts), 1)

    def test_legacy_engine_target_is_not_resent_by_production_notifier(self):
        core = ProjectCore(self.a)
        _, voice = core.add_voice('fixture', 'other',
            {'provider': 'fake', 'region': 'test', 'model': 'fake-v1', 'voice_id': 'FAKE_VOICE_A'}, 0)
        qid = prepare(core, {'roles': ['r'], 'segments': [
            {'paragraph_id': 'p', 'sentence_id': 's', 'role_id': 'r', 'text': 'fixture'}]})['question_id']
        self.server.drop_response = True
        with patch.dict(os.environ, self.env, clear=True):
            _register_target(core, qid, {**environment_target(), 'question_id': qid})
            Questions(core).submit(qid, {'r': voice})
            self.assertEqual(notify(core, qid)['status'], 'unavailable')
            self.assertEqual(notify(core, qid)['status'], 'unavailable')
        self.assertEqual(len(self.server.posts), 0)
        self.assertEqual(Questions(core).read(qid)['status'], 'answered')
        receipt = core.managed_path(f'.makesound/studio/{qid}/wake-receipt.json').read_text()
        self.assertNotIn('fixture-private-gateway', receipt)


if __name__ == '__main__':
    unittest.main()
