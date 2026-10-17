import json
import unittest
from unittest.mock import patch

from tests.helpers import Fixture
from makesound.storage import atomic_write


class VoiceSelectionEntry(Fixture, unittest.TestCase):
    def config(self, provider='minimax', **patches):
        from studio_config_editor import config_path
        value = {'api_key': 'local-valid-key-123', 'region': 'cn',
                 'base_url': 'https://api.minimax.cn', 'models': ['speech-2.8-hd'],
                 'default_model': 'speech-2.8-hd'}
        if provider == 'volcengine':
            value.update(base_url='https://openspeech.bytedance.com', auth_mode='api_key',
                         resource_id='seed-tts-2.0', tts_endpoint='/api/v3/tts/unidirectional')
        value.update(patches)
        path = config_path(provider, self.root)
        atomic_write(path, value)
        return path

    def test_zero_one_two_and_unsupported_hidden(self):
        from makesound.voice_selection_entry import choices
        with patch('studio_config_editor.open_config', side_effect=AssertionError('must not open')):
            empty = choices(self.root, environ={})
            self.assertTrue(empty['config_required'])
            self.assertEqual([o['id'] for o in empty['options']], ['1', '2'])
            self.assertEqual(empty['options'][0]['label'], '自己配置声音')
            self.assertEqual(empty['options'][1]['providers'][0]['id'], '2.a')
            self.config('volcengine')
            self.assertTrue(choices(self.root, environ={})['config_required'])
            future = choices(self.root, environ={}, supported_providers=('minimax', 'volcengine'))
            self.assertEqual(future['default_provider'], 'volcengine')
            self.assertEqual(future['providers'][1]['verification'], 'static_only')
            self.config()
            single = choices(self.root, environ={})
            self.assertEqual(single['default_provider'], 'minimax')
            self.assertNotIn('volcengine', json.dumps(single))
            both = choices(self.root, environ={}, supported_providers=('minimax', 'volcengine'))
            self.assertIsNone(both['default_provider'])
            self.assertTrue(both['provider_choice_required'])
            self.assertEqual([p['id'] for p in both['options'][1]['providers']], ['2.a', '2.b'])
            self.assertNotIn('local-valid-key', json.dumps(both))

    def test_invalid_and_placeholder_are_not_configured(self):
        from makesound.voice_selection_entry import choices
        for value in ('YOUR_API_KEY_HERE', 'fake', 'placeholder', 'test', 'YOUR_REAL_KEY'):
            self.config(api_key=value)
            self.assertTrue(choices(self.root, environ={})['config_required'])
        path = self.config(default_model='missing')
        self.assertTrue(choices(self.root, environ={})['config_required'])
        self.config(region='international')
        self.assertTrue(choices(self.root, environ={})['config_required'])
        path.write_text('{broken', encoding='utf-8')
        self.assertTrue(choices(self.root, environ={})['config_required'])
        self.config(api_key='valid-local-key')
        self.assertTrue(choices(self.root, environ={'MINIMAX_API_KEY': 'YOUR_API_KEY_HERE'})['config_required'])

    def test_configure_explicit_create_no_overwrite_and_template_not_ready(self):
        from makesound.voice_selection_entry import configure, choices
        opened = []
        result = configure('minimax', self.root, opened.append)
        self.assertTrue(result['created'])
        self.assertEqual(str(opened[0]), result['config_path'])
        self.assertTrue(choices(self.root, environ={})['config_required'])
        path = self.config()
        original = path.read_bytes()
        configure('minimax', self.root, opened.append)
        self.assertEqual(path.read_bytes(), original)
        with self.assertRaises(ValueError):
            configure('volcengine', self.root, opened.append)

    def test_configured_models_without_default_offer_model_choice(self):
        from makesound.voice_selection_entry import choices
        self.config(models=['speech-2.8-hd', 'speech-2.8-turbo'], default_model=None)
        result = choices(self.root, environ={})
        self.assertEqual(result['default_provider'], 'minimax')
        self.assertTrue(result['providers'][0]['model_choice_required'])
        self.assertIsNone(result['providers'][0]['selected_model'])
        self.config(default_model=None)
        self.assertEqual(choices(self.root, environ={})['providers'][0]['selected_model'], 'speech-2.8-hd')
