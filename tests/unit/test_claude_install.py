import json
import unittest
from unittest.mock import patch

from tests.helpers import Fixture
from makesound.errors import MakeSoundError


class ClaudeInstall(Fixture, unittest.TestCase):
    def profile(self, name='Claude'):
        base = self.root / name
        plugin = base / 'local-agent-mode-sessions/skills-plugin/account/session'
        (plugin / 'skills').mkdir(parents=True)
        (plugin / '.claude-plugin').mkdir()
        (plugin / '.claude-plugin/plugin.json').write_text('{"name":"anthropic-skills"}')
        (plugin / 'manifest.json').write_text('{"skills":[]}')
        (base / 'claude_desktop_config.json').write_text('{"preferences":{"keep":true}}')
        return base, plugin

    def test_one_command_installs_both_and_repeat_is_idempotent(self):
        from makesound.claude_install import install
        base, plugin = self.profile()
        result = install(app_data=base, allowed_root=self.a, backup_dir=self.root / 'backup')
        self.assertEqual(result['status'], 'installed')
        self.assertTrue((plugin / 'skills/soundmaker-dubbing/SKILL.md').is_file())
        data = json.loads((base / 'claude_desktop_config.json').read_text())
        self.assertTrue(data['preferences']['keep'])
        self.assertIn('host_bridge', data['mcpServers'])
        self.assertFalse(result['app_load_verified'])
        again = install(app_data=base, allowed_root=self.a, backup_dir=self.root / 'backup')
        self.assertEqual(again['skill']['status'], 'already_linked')
        self.assertEqual(again['mcp']['status'], 'already_configured')

    def test_discovery_checks_fixed_profiles_and_rejects_ambiguity(self):
        from makesound.claude_install import discover
        base, plugin = self.profile()
        with patch('makesound.claude_install.profile_candidates', return_value=[base, self.root / 'missing']):
            self.assertEqual(discover(), (base, plugin))
        second, _ = self.profile('Claude-3p')
        with patch('makesound.claude_install.profile_candidates', return_value=[base, second]):
            with self.assertRaises(MakeSoundError) as ctx:
                discover()
        self.assertEqual(ctx.exception.code, 'ambiguous_installation')
        self.assertNotIn('mcpServers', json.loads((base / 'claude_desktop_config.json').read_text()))

    def test_check_only_does_not_write_and_multiple_accounts_require_selection(self):
        from makesound.claude_install import install, discover
        base, plugin = self.profile()
        result = install(app_data=base, allowed_root=self.root / 'not-created', check=True)
        self.assertEqual(result['status'], 'plan')
        self.assertFalse((plugin / 'skills/soundmaker-dubbing').exists())
        self.assertFalse((self.root / 'not-created').exists())
        extra = base / 'local-agent-mode-sessions/skills-plugin/other/session'
        (extra / 'skills').mkdir(parents=True)
        (extra / '.claude-plugin').mkdir()
        (extra / '.claude-plugin/plugin.json').write_text('{"name":"anthropic-skills"}')
        (extra / 'manifest.json').write_text('{"skills":[]}')
        with self.assertRaises(MakeSoundError):
            discover(app_data=base)
        self.assertEqual(discover(app_data=base, plugin_root=plugin), (base, plugin))

    def test_second_step_failure_is_reported_as_partial_not_success(self):
        from makesound.claude_install import install
        base, _ = self.profile()
        with patch('makesound.claude_install.install_mcp', side_effect=MakeSoundError('config_conflict', 'Preserved')):
            result = install(app_data=base, allowed_root=self.a, backup_dir=self.root / 'backup')
        self.assertEqual(result['status'], 'partial_install')
        self.assertEqual(result['code'], 'config_conflict')
        self.assertEqual(result['skill']['status'], 'linked')
        self.assertFalse(result['app_load_verified'])

    def test_upgrade_retains_existing_host_project_root_without_user_input(self):
        from makesound.claude_install import install
        from makesound.claude_host_setup import install as legacy_install
        base, _ = self.profile()
        config = base / 'claude_desktop_config.json'
        legacy_install(config, self.a, backup_dir=self.root / 'backup')
        result = install(app_data=base, backup_dir=self.root / 'backup')
        self.assertEqual(result['status'], 'installed')
        self.assertEqual(result['allowed_root'], str(self.a))
        data = json.loads(config.read_text())['mcpServers']
        self.assertEqual(set(data), {'host_bridge'})
