"""Project files must never displace the default user credential location."""
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from makesound.config_loader import load_minimax
from makesound.errors import MakeSoundError
from makesound.storage import Locations
from makesound.voice_selection_entry import choices
from studio_config_editor import config_path


class MiniMaxConfigLocationTests(unittest.TestCase):
    def test_project_config_is_ignored_with_or_without_user_config(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            home, project = root / 'user', root / 'project'
            project.mkdir()
            config = dict(api_key='local-test-credential', region='cn',
                          base_url='https://api.minimaxi.com',
                          models=['speech-2.8-hd'], default_model='speech-2.8-hd')
            for name in ('config.json', 'config.example.json'):
                (project / name).write_text(json.dumps(config), encoding='utf-8')
            original = Path.cwd()
            try:
                os.chdir(project)
                with patch('pathlib.Path.home', return_value=home):
                    expected = home / '.config/minimax/config.json'
                    self.assertEqual(Locations.default().minimax_config, expected)
                    self.assertEqual(config_path('minimax'), expected)
                    with self.assertRaises(MakeSoundError) as failure:
                        load_minimax(expected, {})
                    self.assertEqual(failure.exception.code, 'config_missing')
                    self.assertFalse(choices(environ={})['providers'][0].get('configured', False))
                    expected.parent.mkdir(parents=True)
                    expected.write_text(json.dumps(config), encoding='utf-8')
                    self.assertEqual(load_minimax(expected, {}).api_key, config['api_key'])
                    summary = choices(environ={})
                    self.assertEqual(summary['default_provider'], 'minimax')
                    self.assertTrue(summary['providers'][0]['configured'])
                    self.assertEqual(summary['network_calls'], 0)
            finally:
                os.chdir(original)
