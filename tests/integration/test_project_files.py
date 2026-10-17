import unittest
from pathlib import Path

from tests.helpers import Fixture
from makesound.core_v16 import ProjectCore
from makesound.generation import Generation
from makesound.storage import digest, read_json
from tests.unit.test_v16 import SOURCE


class ProjectFiles(Fixture, unittest.TestCase):
    def setUp(self):
        super().setUp()
        self.core = ProjectCore(self.a)

    def test_new_exports_stay_internal_and_old_paths_remain_readable(self):
        _, vid = self.core.add_voice('声音', 'other', SOURCE, 0)
        engine = Generation(self.core)
        snap = engine.freeze([{'paragraph_id': 'p1', 'sentence_id': 's1',
                              'text': '原文。', 'project_voice_id': vid}], confirmed=True, authorized=True)
        state = engine.run(snap['job_id'])
        self.assertEqual(state['status'], 'success')
        self.assertTrue(state['exports'][0]['audio'].startswith('.makesound/exports/audio/'))
        self.assertFalse((self.a / 'outputs').exists())
        old = self.core.output_path('outputs/audio/legacy/old.wav')
        old.parent.mkdir(parents=True)
        old.write_bytes(b'legacy')
        self.assertEqual(self.core.managed_path('outputs/audio/legacy/old.wav').read_bytes(), b'legacy')

    def test_workspace_and_explicit_migration_are_repeatable_and_preserve_bytes(self):
        from makesound.project_files import workspace, organize
        paths = workspace(self.core, 'task1', '身份曝光')
        self.assertTrue(Path(paths['inputs_dir']).is_relative_to(self.a / '.makesound'))
        self.assertEqual(Path(paths['delivery_dir']), self.a / '配音/身份曝光')
        original = b'{"roles": ["r1"]}\n'
        (self.a / 'manifest.json').write_bytes(original)
        (self.a / '用户原稿.txt').write_text('保留', encoding='utf-8')
        empty = self.a / 'outputs/audio/old-job'
        empty.mkdir(parents=True)
        result = organize(self.core, 'task1', '身份曝光', ['manifest.json'])
        self.assertEqual(result['archived_count'], 1)
        self.assertFalse((self.a / 'manifest.json').exists())
        self.assertEqual((Path(paths['inputs_dir']) / 'manifest.json').read_bytes(), original)
        self.assertTrue((self.a / '用户原稿.txt').exists())
        self.assertFalse((self.a / 'outputs').exists())
        self.assertEqual(organize(self.core, 'task1', '身份曝光', ['manifest.json'])['archived_count'], 1)
        journal = read_json(self.core.managed_path('.makesound/workspace/task1/organization.json'))
        self.assertEqual(journal['files'][0]['hash'], digest(original.hex()))

    def test_migration_preflights_conflicts_and_rejects_escapes(self):
        from makesound.project_files import workspace, organize
        from makesound.errors import MakeSoundError
        paths = workspace(self.core, 'task1', '身份曝光')
        for name in ('manifest.json', 'items.json'):
            (self.a / name).write_text('{}', encoding='utf-8')
        (Path(paths['inputs_dir']) / 'items.json').write_text('[]', encoding='utf-8')
        with self.assertRaises(MakeSoundError):
            organize(self.core, 'task1', '身份曝光', ['manifest.json', 'items.json'])
        self.assertTrue((self.a / 'manifest.json').exists())
        for title in ('../escape', 'CON', '..'):
            with self.assertRaises(MakeSoundError):
                workspace(self.core, 'unsafe', title)
        with self.assertRaises(MakeSoundError):
            organize(self.core, 'task1', '身份曝光', ['../escape.json'])

    def test_referenced_inputs_and_existing_legacy_exports_are_preserved(self):
        from makesound.project_files import organize
        from makesound.errors import MakeSoundError
        from makesound.storage import atomic_write
        source = self.a / 'manifest.json'
        source.write_text('{}', encoding='utf-8')
        record = self.core.managed_path('.makesound/jobs/old/reference.json')
        atomic_write(record, {'input': str(source)})
        with self.assertRaises(MakeSoundError) as caught:
            organize(self.core, 'task1', '身份曝光', ['manifest.json'])
        self.assertEqual(caught.exception.code, 'input_in_use')
        self.assertTrue(source.exists())
        old = self.core.output_path('outputs/audio/legacy/old.wav')
        old.parent.mkdir(parents=True)
        old.write_bytes(b'original-export')
        organize(self.core, 'task1', '身份曝光', [])
        self.assertEqual(old.read_bytes(), b'original-export')


if __name__ == '__main__':
    unittest.main()
