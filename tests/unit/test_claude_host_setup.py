import json
from pathlib import Path
import unittest

from tests.helpers import Fixture, ROOT
from makesound.errors import MakeSoundError


class ClaudeHostSetup(Fixture, unittest.TestCase):
    def test_install_preserves_config_and_exact_backup_and_is_idempotent(self):
        from makesound.claude_host_setup import install
        before = {'deploymentMode': 'existing', 'preferences': {'keep': True},
                  'mcpServers': {'existing': {'command': 'keep-this'}}}
        config = self.dump('desktop.json', before)
        result = install(config, self.a, backup_dir=self.root / 'backups')
        self.assertEqual(json.loads(Path(result['backup']).read_text()), before)
        saved = json.loads(config.read_text())
        self.assertEqual(saved['preferences'], before['preferences'])
        self.assertEqual(saved['mcpServers']['existing'], before['mcpServers']['existing'])
        spec = saved['mcpServers']['soundmaker_host']
        self.assertIn(str(ROOT / 'scripts/claude_host_bridge.py'), spec['args'])
        self.assertIn(str(self.a.resolve()), spec['args'])
        content = config.read_bytes()
        self.assertEqual(install(config, self.a, backup_dir=self.root / 'backups')['status'], 'already_configured')
        self.assertEqual(config.read_bytes(), content)

    def test_existing_different_bridge_is_not_overwritten(self):
        from makesound.claude_host_setup import install
        config = self.dump('desktop.json', {'mcpServers': {'soundmaker_host': {'command': 'somebody-else'}}})
        before = config.read_bytes()
        with self.assertRaises(MakeSoundError):
            install(config, self.a, backup_dir=self.root / 'backups')
        self.assertEqual(config.read_bytes(), before)

    def test_generic_install_migrates_only_exact_owned_legacy_config(self):
        from makesound.claude_host_setup import install
        config = self.dump('desktop.json', {'mcpServers': {'other': {'command': 'preserve'}}})
        install(config, self.a, backup_dir=self.root / 'backups')
        before = config.read_bytes()
        result = install(config, self.a, backup_dir=self.root / 'backups', generic_bridge=True)
        self.assertEqual(Path(result['backup']).read_bytes(), before)
        data = json.loads(config.read_text())['mcpServers']
        self.assertNotIn('soundmaker_host', data)
        self.assertIn('host_bridge', data)
        self.assertEqual(data['other'], {'command': 'preserve'})
        self.assertIn('--application', data['host_bridge']['args'])
        self.assertEqual(install(config, self.a, backup_dir=self.root / 'backups', generic_bridge=True)['status'], 'already_configured')
