"""Offline tests for Studio's allowlisted model-discovery adapter."""
import hashlib
import json
from pathlib import Path
import sys
import tempfile
import unittest
ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from studio_server import read_models, provider_catalog
from makesound.config_loader import load_minimax

class ProviderConfigTests(unittest.TestCase):
    def setUp(self):
        base = ROOT / '.studio-test-tmp'
        base.mkdir(exist_ok=True)
        self.tmp = tempfile.TemporaryDirectory(dir=base)
        self.path = Path(self.tmp.name) / 'config.json'
    def tearDown(self):
        assert Path(self.tmp.name).resolve().is_relative_to(ROOT)
        self.tmp.cleanup()
    def write(self, value):
        self.path.write_text(json.dumps(value), encoding='utf-8')
    def test_missing_models_is_not_authentication_failure(self):
        self.write({'api_key':'FAKE_SECRET_NEVER_RETURN','region':'cn','base_url':'https://api.minimax.cn'})
        result = read_models(self.path)
        self.assertEqual(result['model_status'], 'not_configured')
        self.assertNotIn('FAKE_SECRET', json.dumps(result))
    def test_missing_config_and_null_path(self):
        for path in (self.path, None):
            self.assertEqual(read_models(path)['model_status'], 'not_configured')
    def test_models_default_redaction_and_readonly(self):
        self.write({'api_key':'FAKE_SECRET_NEVER_RETURN','password':'HIDDEN','models':[{'id':'M_A','name':'模型 A','secret':'DO_NOT_RETURN'},'M_B'],'default_model':'M_B'})
        before = hashlib.sha256(self.path.read_bytes()).hexdigest()
        result = read_models(self.path)
        self.assertEqual(result['default_model'], 'M_B')
        self.assertEqual(result['models'], [{'id':'M_A','name':'模型 A'},{'id':'M_B','name':'M_B'}])
        self.assertEqual(hashlib.sha256(self.path.read_bytes()).hexdigest(), before)
        self.assertFalse(any(secret in json.dumps(result) for secret in ('FAKE_SECRET','HIDDEN','DO_NOT_RETURN','api_key','password')))
    def test_bad_default_does_not_select_another_model(self):
        self.write({'models':['A'],'default_model':'B'})
        result = read_models(self.path)
        self.assertEqual(result['model_status'], 'invalid_default')
        self.assertIsNone(result['default_model'])
    def test_bad_models_are_safe(self):
        for raw in ({}, [None], ['A','A'], [{'id':'A','name':' bearer SECRET'}]):
            self.write({'models':raw})
            self.assertEqual(read_models(self.path)['model_status'], 'invalid_model_config')
    def test_bad_json_never_returns_content(self):
        self.path.write_text('{"api_key":"FAKE_SECRET",', encoding='utf-8')
        result = read_models(self.path)
        self.assertEqual(result['model_status'], 'invalid_model_config')
        self.assertNotIn('FAKE_SECRET', json.dumps(result))
    def test_m1_loader_accepts_model_extensions_without_exposing_them(self):
        self.write({'api_key':'FAKE_SECRET_NEVER_RETURN','region':'cn','base_url':'https://api.minimax.cn','models':['A'],'default_model':'A'})
        config = load_minimax(self.path, environ={})
        self.assertEqual(config.region, 'cn')
        self.assertNotIn('FAKE_SECRET', repr(config) + json.dumps(config.summary()))
    def test_provider_fixtures_keep_volcengine_unimplemented(self):
        result = provider_catalog(ROOT / 'web/tests/fixtures/providers')
        self.assertEqual(result['network_calls'], 0)
        minimax, volc = result['providers']
        self.assertEqual(minimax['default_model'], 'MOCK_MINIMAX_HD')
        self.assertIn('待接入', volc['support'])
        self.assertIn('speaker', volc['identifier_label'])
        self.assertEqual(volc['source'], 'mock_fixture')
if __name__ == '__main__':
    unittest.main()
