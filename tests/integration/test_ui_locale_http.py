import http.client
import json
import os
import threading
import unittest
from unittest.mock import patch

from tests.helpers import Fixture
from makesound.core_v16 import ProjectCore
from makesound.studio_backend import StudioBackend
from studio_v16_server import create_server


class LocaleHTTP(Fixture, unittest.TestCase):
    def test_managed_launch_carries_explicit_language_to_session_and_record(self):
        from makesound.offline_harness import prepare
        from makesound.studio_session import serve_managed
        core = ProjectCore(self.a)
        qid = prepare(core, {'roles': ['r'], 'segments': [
            {'paragraph_id': 'p', 'sentence_id': 's', 'role_id': 'r', 'text': 'test'}]})['question_id']
        self.net.stop()
        servers = []
        def capture(*args, **kwargs):
            server = create_server(*args, **kwargs)
            servers.append(server)
            return server
        def ready(result):
            try:
                self.assertEqual(result['ui_language'], 'en')
                self.assertEqual(servers[0].ui_language, 'en')
                record = json.loads(core.managed_path(f'.makesound/studio/{qid}/session.json').read_text())
                self.assertEqual(record['ui_language'], 'en')
            finally:
                servers[0].shutdown()
        with patch.dict(os.environ, {'CASTVOX_UI_LANGUAGE': 'zh-CN'}, clear=True), \
                patch('studio_v16_server.create_server', side_effect=capture):
            result = serve_managed(core, qid, ui_language='en-GB', on_ready=ready,
                                   config_dir=self.root / 'providers')
        self.assertEqual(result['status'], 'closed_without_answer')

    def test_unknown_env_is_not_exposed_and_invalid_explicit_fails_before_binding(self):
        from makesound.errors import MakeSoundError
        backend = StudioBackend(ProjectCore(self.a), config_paths={}, allow_fake=True)
        with patch.dict(os.environ, {'CASTVOX_UI_LANGUAGE': 'en-<script>'}, clear=True):
            server = create_server(backend)
            try:
                self.assertIsNone(server.ui_language)
            finally:
                server.server_close()
            with patch('studio_v16_server.ThreadingHTTPServer') as bind, self.assertRaises(MakeSoundError):
                create_server(backend, ui_language='en-<script>')
            bind.assert_not_called()

    def test_session_exposes_only_normalized_language_and_retains_origin_guard(self):
        self.net.stop()
        backend = StudioBackend(ProjectCore(self.a), config_paths={}, allow_fake=True)
        with patch.dict(os.environ, {'CASTVOX_UI_LANGUAGE': 'zh-Hant'}, clear=True):
            server = create_server(backend)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            connection = http.client.HTTPConnection('127.0.0.1', server.server_port, timeout=3)
            connection.request('GET', '/js/session.js')
            response = connection.getresponse()
            self.assertEqual(response.status, 200)
            module = response.read().decode()
            session = json.loads(module.split('Object.freeze(', 1)[1].rsplit(');', 1)[0])
            self.assertEqual(session['ui_language'], 'zh-CN')
            self.assertNotIn('CASTVOX_UI_LANGUAGE', module)
            connection.close()
            connection = http.client.HTTPConnection('127.0.0.1', server.server_port, timeout=3)
            connection.request('GET', '/js/session.js', headers={'Origin': 'https://evil.invalid'})
            response = connection.getresponse()
            self.assertEqual(response.status, 403)
            response.read()
            connection.close()
        finally:
            server.shutdown()
            server.server_close()
            thread.join(timeout=3)
