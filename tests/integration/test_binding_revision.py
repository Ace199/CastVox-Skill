import copy
import json
import subprocess
import sys
import unittest
from datetime import datetime, timedelta, timezone

from makesound.core_v16 import ProjectCore
from makesound.errors import MakeSoundError
from makesound.offline_harness import prepare
from makesound.questions import Questions
from makesound.storage import atomic_write, read_json
from tests.helpers import Fixture
from tests.unit.test_v16 import SOURCE


class BindingRevision(Fixture, unittest.TestCase):
    def setUp(self):
        super().setUp()
        self.core = ProjectCore(self.a)
        _, self.first = self.core.add_voice('原声音', 'male', SOURCE, 0)
        _, self.second = self.core.add_voice('新声音', 'male', {**SOURCE, 'voice_id': 'second'}, 1)
        self.core.save_defaults({'general': self.first}, 2)
        self.manifest = {'roles': ['a', 'b'], 'segments': [
            {'paragraph_id': 'p1', 'sentence_id': 's1', 'role_id': 'a', 'text': '甲'},
            {'paragraph_id': 'p1', 'sentence_id': 's2', 'role_id': 'b', 'text': '乙'},
            {'paragraph_id': 'p1', 'sentence_id': 's3', 'role_id': 'a', 'text': '丙'}]}
        self.qid = prepare(self.core, self.manifest)['question_id']
        self.questions = Questions(self.core)
        self.questions.submit(self.qid, {'a': {'default_slot': 'general'}, 'b': self.first})

    def error(self, code, call):
        with self.assertRaises(MakeSoundError) as caught:
            call()
        self.assertEqual(caught.exception.code, code)

    def submit_existing(self, qid):
        question = self.questions.read(qid)
        return self.questions.submit(qid, {role: binding['project_voice_id']
            for role, binding in question['assignments'].items()})

    def test_default_and_deleted_binding_keep_original_snapshot(self):
        from makesound.binding_revision import create, compare
        old = copy.deepcopy(self.questions.read(self.qid))
        self.core.edit_voice(self.first, {'settings': {'speed': 1.2}, 'deleted': True}, 3)
        self.core.save_defaults({'general': self.second}, 4)
        result = create(self.core, self.qid)
        qid = result['question_id']
        pending = self.questions.read(qid)
        for role in ['a', 'b']:
            self.assertEqual(pending['assignments'][role]['resolved'], old['answer']['resolved'][role])
        self.submit_existing(qid)
        self.assertEqual(compare(self.core, qid)['changed_roles'], [])
        self.assertEqual(self.questions.read(self.qid), old)

    def test_changed_voice_reports_only_affected_sentences_and_preserves_job(self):
        from makesound.binding_revision import create, compare
        from makesound.generation import Generation
        old = self.questions.read(self.qid)
        self.questions.claim(self.qid, old['harness_session_id'])
        engine = Generation(self.core)
        snapshot = engine.freeze_from_answer(self.qid, old['harness_session_id'],
            self.manifest['segments'], confirmed=True, authorized=True)
        audio = self.a / 'outputs/audio/old.wav'
        audio.parent.mkdir(parents=True)
        audio.write_bytes(b'historical-audio-untouched')
        old = self.questions.read(self.qid)
        qid = create(self.core, self.qid)['question_id']
        self.questions.assign(qid, 'a', self.second, self.core.read()['revision'])
        self.submit_existing(qid)
        result = compare(self.core, qid)
        self.assertEqual(result['changed_roles'], ['a'])
        self.assertEqual(result['affected_sentence_ids'], ['s1', 's3'])
        self.assertEqual(result['source_question_id'], self.qid)
        self.assertEqual(self.questions.read(self.qid), old)
        self.assertEqual(engine.load(snapshot['job_id']), snapshot)
        self.assertEqual(audio.read_bytes(), b'historical-audio-untouched')
        self.assertEqual(list((self.a / '.makesound/jobs').iterdir()),
                         [self.a / '.makesound/jobs' / snapshot['job_id']])

    def test_pending_is_idempotent_expired_is_replaced_and_submitted_can_revise(self):
        from makesound.binding_revision import create
        first = create(self.core, self.qid)
        self.assertEqual(create(self.core, self.qid), first)
        pending = self.questions.read(first['question_id'])
        pending['expires_at'] = (datetime.now(timezone.utc) - timedelta(seconds=1)).isoformat()
        atomic_write(self.questions._path(first['question_id']), pending)
        second = create(self.core, self.qid)
        self.assertNotEqual(second['question_id'], first['question_id'])
        self.submit_existing(second['question_id'])
        third = create(self.core, second['question_id'])
        self.assertEqual(third['source_answer_id'], self.questions.read(second['question_id'])['answer']['answer_id'])
        self.assertNotEqual(third['question_id'], second['question_id'])

    def test_source_session_project_and_manuscript_are_validated(self):
        from makesound.binding_revision import create, compare
        q = self.questions.read(self.qid)
        bad = copy.deepcopy(q)
        bad['answer']['project_id'] = 'different'
        atomic_write(self.questions._path(self.qid), bad)
        self.error('project_mismatch', lambda: create(self.core, self.qid))
        atomic_write(self.questions._path(self.qid), q)
        path = self.core.managed_path(f'.makesound/handoffs/{self.qid}.json')
        handoff = read_json(path)
        bad_handoff = copy.deepcopy(handoff)
        bad_handoff['harness_session_id'] = 'another_session'
        atomic_write(path, bad_handoff)
        self.error('session_mismatch', lambda: create(self.core, self.qid))
        atomic_write(path, handoff)
        revised = create(self.core, self.qid)['question_id']
        self.submit_existing(revised)
        bad_handoff = copy.deepcopy(handoff)
        bad_handoff['manifest']['segments'][0]['text'] = '改稿'
        atomic_write(path, bad_handoff)
        self.error('plan_changed', lambda: compare(self.core, revised))

    def test_reselecting_same_card_updates_parameters_but_editing_library_does_not(self):
        from makesound.binding_revision import create, compare
        qid = create(self.core, self.qid)['question_id']
        self.core.edit_voice(self.first, {'settings': {'speed': 1.2}}, 3)
        self.questions.assign(qid, 'a', self.first, 4)
        self.submit_existing(qid)
        result = compare(self.core, qid)
        self.assertEqual(result['changed_roles'], ['a'])
        self.assertEqual(self.questions.read(qid)['answer']['resolved']['b']['effective_settings']['speed'], 1.0)

    def test_pending_revision_tampering_is_rejected_and_unanswered_source_cannot_revise(self):
        from makesound.binding_revision import create
        qid = create(self.core, self.qid)['question_id']
        self.error('not_answered', lambda: create(self.core, qid))
        path = self.core.managed_path(f'.makesound/handoffs/{qid}.json')
        handoff = read_json(path)
        handoff['manifest']['segments'][0]['text'] = '不能用修订修改原稿'
        atomic_write(path, handoff)
        self.error('plan_changed', lambda: create(self.core, self.qid))

    def test_cli_prepare_and_status_do_not_generate(self):
        def run(action, qid):
            result = subprocess.run([sys.executable, '-m', 'makesound.binding_revision', action,
                '--project', str(self.a), '--question', qid], capture_output=True, encoding='utf-8', timeout=20)
            self.assertEqual(result.returncode, 0, result.stderr)
            return json.loads(result.stdout)
        prepared = run('prepare', self.qid)
        pending = run('status', prepared['question_id'])
        self.assertFalse(pending['comparison_ready'])
        self.assertFalse((self.a / '.makesound/jobs').exists())
        self.submit_existing(prepared['question_id'])
        submitted = run('status', prepared['question_id'])
        self.assertTrue(submitted['comparison_ready'])
        self.assertFalse(submitted['paid_execution_authorized'])
        self.assertEqual(submitted['affected_sentence_ids'], [])

    def test_reopening_original_link_follows_latest_submitted_revision(self):
        from makesound.binding_revision import create
        revised = create(self.core, self.qid)['question_id']
        self.questions.assign(revised, 'a', self.second, self.core.read()['revision'])
        self.submit_existing(revised)
        next_revision = create(self.core, self.qid)
        self.assertEqual(next_revision['source_question_id'], revised)
        self.assertEqual(self.questions.read(next_revision['question_id'])['assignments']['a']['project_voice_id'], self.second)
        self.assertEqual(create(self.core, self.qid), next_revision)
        self.assertEqual(create(self.core, revised), next_revision)
