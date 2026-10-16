"""Studio-only tests; isolated temp files and a fake editor, no Core tests."""
import http.client
import json
from pathlib import Path
import sys
import tempfile
import threading
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from studio_config_editor import open_config, open_default_config, config_path
from studio_server import Handler, ThreadingHTTPServer


class ConfigEditorTests(unittest.TestCase):
    def setUp(self):
        base = Path(__file__).resolve().parents[2] / '.studio-test-tmp'
        base.mkdir(exist_ok=True)
        self.tmp = tempfile.TemporaryDirectory(dir=base)
        self.root = Path(self.tmp.name)
        self.opened = []

    def tearDown(self):
        assert self.root.resolve().is_relative_to(Path(__file__).resolve().parents[2] / '.studio-test-tmp')
        self.tmp.cleanup()

    def test_create_template_and_open(self):
        result = open_config('minimax', self.root, self.opened.append)
        path = self.root / 'minimax/config.json'
        self.assertEqual(self.opened, [path])
        self.assertTrue(result['created'])
        self.assertEqual(json.loads(path.read_text()), {
            'api_key': 'YOUR_API_KEY_HERE', 'region': 'cn',
            'base_url': 'https://api.minimax.cn',
            'models': ['speech-2.8-hd', 'speech-2.8-turbo', 'speech-2.6-hd', 'speech-2.6-turbo',
                       'speech-02-hd', 'speech-02-turbo', 'speech-01-hd', 'speech-01-turbo'],
            'default_model': 'speech-2.8-hd'})
        self.assertNotIn('api_key', json.dumps(result))

    def test_existing_file_unchanged_even_invalid_json(self):
        path = self.root / 'minimax/config.json'; path.parent.mkdir()
        original = b'{"api_key":"TEST_SECRET", invalid-json'
        path.write_bytes(original)
        result = open_config('minimax', self.root, self.opened.append)
        self.assertEqual(path.read_bytes(), original)
        self.assertFalse(result['created'])
        self.assertNotIn('TEST_SECRET', json.dumps(result))

    def test_open_default_config_opens_existing_project_preset_without_rewriting(self):
        preset = self.root / '.makesound' / 'preset.v1.6.json'
        preset.parent.mkdir()
        original = '{"schema_version":"1.6","defaults":{"general":null}}\n'
        preset.write_text(original, encoding='utf-8')
        result = open_default_config(self.root, self.opened.append)
        self.assertEqual(self.opened, [preset])
        self.assertTrue(result['ok'])
        self.assertEqual(preset.read_text(encoding='utf-8'), original)

    def test_repeat_create_preserves_user_edits(self):
        open_config('minimax', self.root, self.opened.append)
        path = self.root / 'minimax/config.json'; path.write_text('{"models":["USER_MODEL"]}')
        open_config('minimax', self.root, self.opened.append)
        self.assertEqual(path.read_text(), '{"models":["USER_MODEL"]}')

    def test_unknown_provider_does_not_write(self):
        for provider in ('../minimax', 'other'):
            with self.assertRaises(ValueError):
                open_config(provider, self.root, self.opened.append)
        self.assertEqual(list(self.root.iterdir()), [])
        self.assertEqual(config_path('volcengine'), Path.home() / '.config/volcengine/config.json')

    def test_volc_template_uses_distinct_auth_resource_and_model(self):
        result = open_config('volcengine', self.root, self.opened.append)
        path = self.root / 'volcengine/config.json'
        config = json.loads(path.read_text(encoding='utf-8'))
        self.assertTrue(result['created'])
        self.assertEqual(self.opened, [path])
        self.assertEqual(config, {
            'auth_mode': 'api_key', 'api_key': 'YOUR_VOLCENGINE_API_KEY_HERE',
            'region': 'cn', 'base_url': 'https://openspeech.bytedance.com',
            'tts_endpoint': '/api/v3/tts/unidirectional', 'resource_id': 'seed-tts-2.0',
            'models': ['seed-tts-2.0-standard'], 'default_model': 'seed-tts-2.0-standard'})
        self.assertNotIn('api_key', json.dumps(result))
        path.write_bytes(b'{"access_key":"LEGACY_SECRET", broken')
        again = open_config('volcengine', self.root, self.opened.append)
        self.assertFalse(again['created'])
        self.assertEqual(path.read_bytes(), b'{"access_key":"LEGACY_SECRET", broken')

    def test_existing_volc_fixture_can_open_without_changes(self):
        path = self.root / 'volcengine/config.json'; path.parent.mkdir(); path.write_text('{}')
        open_config('volcengine', self.root, self.opened.append)
        self.assertEqual(self.opened, [path]); self.assertEqual(path.read_text(), '{}')

    def test_editor_failure_retains_template_and_safe_error(self):
        def fail(_): raise OSError('SECRET must not leak')
        result = open_config('minimax', self.root, fail)
        self.assertFalse(result['ok']); self.assertTrue(result['created'])
        self.assertNotIn('SECRET', json.dumps(result))

    def test_http_requires_same_origin_and_allowlisted_body(self):
        server = ThreadingHTTPServer(('127.0.0.1', 0), Handler); server.config_dir = self.root
        thread = threading.Thread(target=server.serve_forever, daemon=True); thread.start()
        host = f'127.0.0.1:{server.server_port}'
        def request(body, headers):
            conn = http.client.HTTPConnection(host)
            conn.request('POST', '/api/providers/open-config', json.dumps(body), headers)
            response = conn.getresponse(); status, data = response.status, response.read(); conn.close()
            return status, data
        headers = {'Origin': f'http://{host}', 'Content-Type': 'application/json', 'X-Studio-Action': 'open-config'}
        try:
            with patch('studio_config_editor.launch_editor', side_effect=self.opened.append):
                self.assertEqual(request({'provider': 'minimax'}, {**headers, 'Origin': 'https://example.com'})[0], 403)
                self.assertEqual(request({'provider': 'minimax'}, {})[0], 403)
                self.assertFalse(json.loads(request({'provider': 'minimax', 'path': 'arbitrary'}, headers)[1])['ok'])
                self.assertEqual(self.opened, [])
                status, data = request({'provider': 'minimax'}, headers)
                self.assertEqual(status, 200); self.assertTrue(json.loads(data)['ok'])
                self.assertEqual(len(self.opened), 1)
                self.assertNotIn(b'api_key', data)
        finally:
            server.shutdown(); server.server_close(); thread.join()

    def test_static_modules_ignore_old_cache_validators(self):
        server = ThreadingHTTPServer(('127.0.0.1', 0), Handler); server.config_dir = self.root
        thread = threading.Thread(target=server.serve_forever, daemon=True); thread.start()
        try:
            conn = http.client.HTTPConnection('127.0.0.1', server.server_port)
            conn.request('GET', '/js/providers.js', headers={'If-Modified-Since': 'Wed, 01 Jan 2031 00:00:00 GMT'})
            response = conn.getresponse(); body = response.read()
            self.assertEqual(response.status, 200)
            self.assertIn('no-store', response.getheader('Cache-Control'))
            self.assertIn(b'export async function openProviderConfig', body)
            conn.close()
        finally:
            server.shutdown(); server.server_close(); thread.join()


if __name__ == '__main__':
    unittest.main()
