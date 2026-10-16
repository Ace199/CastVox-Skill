import hashlib
import unittest

from makesound.core_v16 import ProjectCore
from makesound.errors import MakeSoundError
from makesound.generation import Generation
from makesound.minimax_provider import MiniMaxProvider
from makesound.providers import capabilities, effective
from makesound.studio_backend import StudioBackend
from tests.helpers import Fixture
from tests.integration.test_minimax_media import REAL, StubTransport
from tests.unit.test_v16 import SOURCE


class AddVoiceSettings(Fixture, unittest.TestCase):
    def setUp(self):
        super().setUp()
        self.core = ProjectCore(self.a)
        self.config = self.dump('provider.json', {'api_key': 'PRIVATE_TEST_CREDENTIAL', 'region': 'cn',
            'base_url': 'https://api.minimax.cn', 'models': ['speech-2.8-hd', 'unknown-model'], 'default_model': 'speech-2.8-hd'})
        self.backend = StudioBackend(self.core, config_paths={'minimax': self.config}, allow_fake=True)

    def add(self, source, settings, name='新声音'):
        return self.backend.dispatch('voices/add', {'name': name, 'category': 'male', 'source': source,
                                                   'settings': settings, 'revision': self.core.read()['revision']})

    def test_add_custom_settings_persist_and_freeze_with_source(self):
        result = self.add(SOURCE, {'speed': 1.2, 'pitch': -3})
        vid = result['project_voice_id']
        self.assertEqual(ProjectCore(self.a).read()['voices'][vid]['settings'], {'speed': 1.2, 'pitch': -3})
        snapshot = Generation(self.core).freeze([{'paragraph_id': 'p', 'sentence_id': 's', 'text': '原文。', 'project_voice_id': vid}],
                                                confirmed=True, authorized=True)
        self.core.edit_voice(vid, {'settings': {'speed': 1.5}}, self.core.read()['revision'])
        self.assertEqual(snapshot['chunks'][0]['effective_settings']['speed'], 1.2)

    def test_minimax_documented_contract_accepts_real_parameters_without_live_claim(self):
        result = self.add(REAL, {'speed': 1.234, 'pitch': -3})
        self.assertEqual(result['preset']['voices'][result['project_voice_id']]['settings'], {'speed': 1.234, 'pitch': -3})
        metadata = self.backend.providers()['providers'][0]
        model = next(m for m in metadata['models'] if m['id'] == REAL['model'])
        self.assertEqual(model['capabilities']['speed']['step'], 'any')
        self.assertEqual(model['capabilities']['pitch']['step'], 1)
        self.assertFalse(model['capabilities']['speed']['live_verified'])
        self.assertFalse(next(m for m in metadata['models'] if m['id'] == 'unknown-model').get('capabilities'))

    def test_old_omitted_parameters_and_defaults_remain_readable_and_unchanged(self):
        preset, vid = self.core.add_voice('原有声音', 'male', REAL, 0)
        self.core.save_defaults({'general': vid}, preset['revision'])
        before = hashlib.sha256(self.core.path.read_bytes()).hexdigest()
        self.assertEqual(effective(REAL), {})
        self.backend.state()
        self.assertEqual(hashlib.sha256(self.core.path.read_bytes()).hexdigest(), before)
        self.assertEqual(self.core.read()['defaults']['general'], vid)
        self.assertEqual(self.core.read()['voices'][vid]['settings'], {})

    def test_invalid_or_unsupported_parameters_are_rejected_without_preset_write(self):
        for source, settings in [(REAL, {'speed': .49}), (REAL, {'speed': 2.01}), (REAL, {'speed': True}),
                                 (REAL, {'pitch': 1.5}), (REAL, {'pitch': 13}), (REAL, {'pitch': float('nan')}),
                                 ({**REAL, 'model': 'unknown-model'}, {'speed': 1}),
                                 ({**REAL, 'region': 'international'}, {'speed': 1})]:
            with self.subTest(settings=settings, region=source['region']), self.assertRaises(MakeSoundError):
                self.add(source, settings)
        self.assertFalse(self.core.path.exists())

    def test_minimax_request_maps_saved_settings_and_keeps_omitted_values_omitted(self):
        result = self.add(REAL, {'speed': 1.25, 'pitch': -3})
        vid = result['project_voice_id']
        snapshot = Generation(self.core).freeze([{'paragraph_id': 'p', 'sentence_id': 's', 'text': '原文。', 'project_voice_id': vid}],
                                                confirmed=True, authorized=True)
        transport = StubTransport()
        adapter = MiniMaxProvider(self.config, authorized_job_id=snapshot['job_id'], max_calls=1, max_characters=100,
                                  transport=transport, subtitle_hosts=['subtitles.example.test'], environ={})
        self.assertEqual(Generation(self.core, minimax=adapter).run(snapshot['job_id'])['status'], 'success')
        self.assertEqual(transport.requests[0][1]['body']['voice_setting'], {'voice_id': REAL['voice_id'], 'speed': 1.25, 'pitch': -3})
        self.assertEqual(effective(REAL, {'pitch': -12}), {'pitch': -12})
        self.assertEqual(capabilities({**REAL, 'model': 'unknown-model'}), {})


if __name__ == '__main__':
    unittest.main()
