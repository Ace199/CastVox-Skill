import unittest
from unittest.mock import patch

from tests.helpers import Fixture
from tests.unit.test_v16 import SOURCE
from makesound.core_v16 import ProjectCore
from makesound.errors import MakeSoundError
from makesound.generation import Generation
from makesound.offline_harness import prepare, resume
from makesound.questions import Questions
from makesound.providers import duration


class StudioHandoff(Fixture, unittest.TestCase):
    def setUp(self):
        super().setUp()
        self.core = ProjectCore(self.a)
        self.preset, self.vid = self.core.add_voice('旁白', 'other', SOURCE, 0)
        self.manifest = {'roles': ['narrator'], 'role_metadata': {'narrator': {
            'display_name': '讲解者', 'appearance_summary': '任务提供的形象', 'recommended_voice_description': '平静清晰'}},
            'segments': [{'paragraph_id': 'p1', 'sentence_id': 's1', 'role_id': 'narrator', 'text': '保留原文。', 'pause_ms': 300},
                         {'paragraph_id': 'p1', 'sentence_id': 's2', 'role_id': 'narrator', 'text': '第二句。'}]}

    def error(self, code, call):
        with self.assertRaises(MakeSoundError) as caught:
            call()
        self.assertEqual(caught.exception.code, code)

    def test_role_metadata_assign_snapshot_delete_restart_and_resume(self):
        qid = prepare(self.core, self.manifest)['question_id']
        self.assertEqual(resume(self.core, qid, confirmed=True, authorized=True)['status'], 'waiting_for_answer')
        questions = Questions(self.core)
        questions.assign(qid, 'narrator', self.vid, 1)
        self.core.edit_voice(self.vid, {'settings': {'speed': 1.3}, 'deleted': True}, 1)
        with patch('makesound.providers.FakeProvider.synthesize', side_effect=AssertionError('Submission must not synthesize')):
            result = Questions(ProjectCore(self.a)).submit(qid, {'narrator': self.vid}, revision=2)
        self.assertFalse(result['agent_resumed'])
        self.assertEqual(result['answer']['resolved']['narrator']['effective_settings']['speed'], 1.0)
        result = resume(ProjectCore(self.a), qid, confirmed=True, authorized=True)
        self.assertEqual(result['status'], 'success')
        self.assertEqual(result['fake_calls_this_run'], 2)
        export = result['result']['exports'][0]
        self.assertEqual(duration(self.core.managed_path(export['audio'])), 12.3)
        self.assertIn('00:00:06,300 --> 00:00:12,300', self.core.managed_path(export['subtitle']).read_text(encoding='utf-8'))
        self.assertEqual(resume(ProjectCore(self.a), qid, confirmed=True, authorized=True)['fake_calls_this_run'], 0)
        self.assertEqual(questions.read(qid)['role_metadata'], self.manifest['role_metadata'])

    def test_revision_conflict_assignment_clear_and_answer_immutable(self):
        qid = prepare(self.core, self.manifest)['question_id']
        q = Questions(self.core)
        self.error('revision_conflict', lambda: q.assign(qid, 'narrator', self.vid, 0))
        q.assign(qid, 'narrator', self.vid, 1)
        q.assign(qid, 'narrator', None, 1)
        self.assertEqual(q.read(qid)['assignments'], {})
        self.error('revision_conflict', lambda: q.submit(qid, {'narrator': self.vid}, revision=0))
        q.submit(qid, {'narrator': self.vid}, revision=1)
        self.error('answer_immutable', lambda: q.assign(qid, 'narrator', self.vid, 1))

    def test_safe_failed_chunk_resumes_without_regenerating_success(self):
        qid = prepare(self.core, self.manifest)['question_id']
        q = Questions(self.core)
        q.submit(qid, {'narrator': self.vid})
        obj = q.read(qid)
        q.claim(qid, obj['harness_session_id'])
        engine = Generation(self.core)
        snap = engine.freeze_from_answer(qid, obj['harness_session_id'], self.manifest['segments'], confirmed=True, authorized=True)
        engine.fake.fail_once.add('chunk_000001')
        self.assertEqual(engine.run(snap['job_id'])['status'], 'incomplete')
        self.assertEqual(resume(ProjectCore(self.a), qid, confirmed=True, authorized=True)['status'], 'incomplete')
        resumed = resume(ProjectCore(self.a), qid, confirmed=True, authorized=True, retry_failed=True)
        self.assertEqual(resumed['status'], 'success')
        self.assertEqual(resumed['fake_calls_this_run'], 1)
        self.assertEqual(self.core.preview_state(self.vid)['status'], 'current')

    def test_unknown_billing_and_unconfirmed_are_blocked(self):
        qid = prepare(self.core, self.manifest)['question_id']
        self.error('authorization_required', lambda: resume(self.core, qid))
        q = Questions(self.core)
        q.submit(qid, {'narrator': self.vid})
        obj = q.read(qid)
        q.claim(qid, obj['harness_session_id'])
        engine = Generation(self.core)
        snap = engine.freeze_from_answer(qid, obj['harness_session_id'], self.manifest['segments'], confirmed=True, authorized=True)
        engine.fake.uncertain_once.add('chunk_000001')
        engine.run(snap['job_id'])
        resumed = resume(ProjectCore(self.a), qid, confirmed=True, authorized=True, retry_failed=True)
        self.assertEqual(resumed['status'], 'incomplete')
        self.assertEqual(resumed['fake_calls_this_run'], 0)

    def test_metadata_secret_and_undeclared_role_rejected(self):
        self.manifest['role_metadata']['narrator']['api_key'] = 'PRIVATE'
        with self.assertRaises(MakeSoundError):
            prepare(self.core, self.manifest)
        self.manifest['role_metadata']['narrator'].pop('api_key')
        self.manifest['segments'][0]['role_id'] = 'undeclared'
        self.error('missing_roles', lambda: prepare(self.core, self.manifest))

        self.manifest['segments'][0]['role_id'] = 'narrator'
        _, real_id = self.core.add_voice('真实厂商配置', 'other', {**SOURCE, 'provider': 'minimax', 'region': 'cn', 'model': 'unverified-model'}, 1)
        qid = prepare(self.core, self.manifest)['question_id']
        Questions(self.core).submit(qid, {'narrator': real_id})
        with patch('makesound.generation.Generation.run', side_effect=AssertionError('Real provider must never execute')):
            self.error('offline_only', lambda: resume(self.core, qid, confirmed=True, authorized=True))

    def test_whole_paragraph_sentence_exports_measure_duration_and_srt(self):
        self.manifest['segments'][1]['paragraph_id'] = 'p2'
        for mode, count in [('whole', 1), ('paragraph', 2), ('sentence', 2)]:
            with self.subTest(mode=mode):
                self.core.save_settings({'export_mode': mode}, self.core.read()['revision'])
                qid = prepare(self.core, self.manifest)['question_id']
                Questions(self.core).submit(qid, {'narrator': self.vid})
                result = resume(self.core, qid, confirmed=True, authorized=True)
                exports = result['result']['exports']
                self.assertEqual(len(exports), count)
                self.assertAlmostEqual(sum(duration(self.core.managed_path(e['audio'])) for e in exports), 12.3)
                self.assertEqual(sum(self.core.managed_path(e['subtitle']).read_text(encoding='utf-8').count(' --> ') for e in exports), 2)

    def test_restart_after_claim_before_freeze(self):
        qid = prepare(self.core, self.manifest)['question_id']
        q = Questions(self.core)
        q.submit(qid, {'narrator': self.vid})
        q.claim(qid, q.read(qid)['harness_session_id'])
        self.assertEqual(resume(ProjectCore(self.a), qid, confirmed=True, authorized=True)['status'], 'success')


if __name__ == '__main__':
    unittest.main()
