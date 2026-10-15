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
from studio_config_editor import open_config, config_path
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
            'api_key': 'write your own keys', 'region': 'cn',
            'base_url': 'https://api.minimax.cn', 'models': [], 'default_model': None})
        self.assertNotIn('api_key', json.dumps(result))

    def test_existing_file_unchanged_even_invalid_json(self):
        path = self.root / 'minimax/config.json'; path.parent.mkdir()
        original = b'{"api_key":"TEST_SECRET", invalid-json'
        path.write_bytes(original)
        result = open_config('minimax', self.root, self.opened.append)
        self.assertEqual(path.read_bytes(), original)
        self.assertFalse(result['created'])
        self.assertNotIn('TEST_SECRET', json.dumps(result))

    def test_repeat_create_preserves_user_edits(self):
        open_config('minimax', self.root, self.opened.append)
        path = self.root / 'minimax/config.json'; path.write_text('{"models":["USER_MODEL"]}')
        open_config('minimax', self.root, self.opened.append)
        self.assertEqual(path.read_text(), '{"models":["USER_MODEL"]}')

    def test_unknown_provider_and_unconfigured_volc_do_not_write(self):
        for provider in ('../minimax', 'other', 'volcengine'):
            with self.assertRaises(ValueError):
                open_config(provider, self.root, self.opened.append)
        self.assertEqual(list(self.root.iterdir()), [])
        self.assertIsNone(config_path('volcengine'))

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
