import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from tests.helpers import ROOT
from makesound.errors import MakeSoundError


class CoworkLink(unittest.TestCase):
    def setUp(self):
        (ROOT / '.test-tmp').mkdir(exist_ok=True)
        self.tmp = tempfile.TemporaryDirectory(dir=ROOT / '.test-tmp')
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.plugin = self.root / '插件 空间'
        (self.plugin / '.claude-plugin').mkdir(parents=True)
        (self.plugin / 'skills').mkdir()
        (self.plugin / '.claude-plugin/plugin.json').write_text('{"name":"anthropic-skills"}')
        self.manifest = self.plugin / 'manifest.json'
        self.original = {'lastUpdated': 1, 'skills': [{'name': 'docx', 'enabled': True, 'creatorType': 'anthropic'}]}
        self.manifest.write_text(json.dumps(self.original))
        self.backups = self.root / 'backups'

    def install(self):
        from makesound.claude_cowork import link_skill
        return link_skill(self.plugin, backup_dir=self.backups)

    def test_link_and_user_entry_preserve_existing_skills_and_backup(self):
        result = self.install()
        target = self.plugin / 'skills/soundmaker-dubbing'
        self.assertEqual(target.resolve(), (ROOT / 'skills/soundmaker-dubbing').resolve())
        manifest = json.loads(self.manifest.read_text())
        self.assertEqual(manifest['skills'][0], self.original['skills'][0])
        entry = manifest['skills'][1]
        self.assertEqual(entry['creatorType'], 'user')
        self.assertFalse(entry['syncManaged'])
        self.assertTrue(entry['enabled'])
        self.assertEqual(json.loads(Path(result['manifest_backup']).read_text()), self.original)
        self.assertFalse(result['host_load_verified'])
        # Remove only the link before TemporaryDirectory cleanup.
        self.addCleanup(lambda: os.rmdir(target) if os.name == 'nt' else target.unlink())
        before = self.manifest.read_bytes()
        self.assertEqual(self.install()['status'], 'already_linked')
        self.assertEqual(self.manifest.read_bytes(), before)

    def test_existing_copy_is_never_overwritten(self):
        target = self.plugin / 'skills/soundmaker-dubbing'
        target.mkdir()
        (target / 'SKILL.md').write_text('user copy')
        with self.assertRaises(MakeSoundError):
            self.install()
        self.assertEqual((target / 'SKILL.md').read_text(), 'user copy')
        self.assertEqual(json.loads(self.manifest.read_text()), self.original)

    def test_wrong_plugin_and_manifest_conflicts_fail_before_linking(self):
        for mutation in ('plugin', 'entry'):
            with self.subTest(mutation=mutation):
                if mutation == 'plugin':
                    (self.plugin / '.claude-plugin/plugin.json').write_text('{"name":"other-plugin"}')
                else:
                    (self.plugin / '.claude-plugin/plugin.json').write_text('{"name":"anthropic-skills"}')
                    self.manifest.write_text(json.dumps({'skills': [{'name': 'soundmaker-dubbing', 'creatorType': 'anthropic'}]}))
                with self.assertRaises(MakeSoundError):
                    self.install()
                self.assertFalse((self.plugin / 'skills/soundmaker-dubbing').exists())

    def test_failed_manifest_write_removes_only_new_link_and_keeps_backup(self):
        with patch('makesound.claude_cowork.atomic_write', side_effect=OSError('test write failure')):
            with self.assertRaises(OSError):
                self.install()
        self.assertFalse((self.plugin / 'skills/soundmaker-dubbing').exists())
        self.assertTrue((ROOT / 'skills/soundmaker-dubbing/SKILL.md').is_file())
        self.assertEqual(json.loads(self.manifest.read_text()), self.original)
        backups = list(self.backups.glob('manifest-*.json'))
        self.assertEqual(len(backups), 1)
        self.assertEqual(json.loads(backups[0].read_text()), self.original)

    def test_backup_inside_plugin_is_rejected(self):
        from makesound.claude_cowork import link_skill
        with self.assertRaises(MakeSoundError):
            link_skill(self.plugin, backup_dir=self.plugin / 'backups')
        self.assertFalse((self.plugin / 'skills/soundmaker-dubbing').exists())


if __name__ == '__main__':
    unittest.main()
