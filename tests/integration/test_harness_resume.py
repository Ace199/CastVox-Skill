import subprocess
import unittest
from types import SimpleNamespace
from unittest.mock import patch

from tests.helpers import Fixture
from tests.unit.test_v16 import SOURCE
from makesound.core_v16 import ProjectCore
from makesound.questions import Questions
from makesound.offline_harness import prepare
from makesound.harness_resume import register, notify
from makesound.errors import MakeSoundError


class HarnessResume(Fixture, unittest.TestCase):
    def setUp(self):
        super().setUp()
        self.core = ProjectCore(self.a)
        _, self.voice = self.core.add_voice('test', 'other', SOURCE, 0)
        self.qid = prepare(self.core, {'roles': ['r'], 'segments': [
            {'paragraph_id': 'p', 'sentence_id': 's', 'role_id': 'r', 'text': 'test'}]})['question_id']
        self.thread = '01a140ba-6302-71a2-ae92-bb03233f2d2c'

    def test_saved_before_queue_and_duplicate_is_not_resent(self):
        register(self.core, self.qid, self.thread)
        with self.assertRaises(MakeSoundError):
            notify(self.core, self.qid)
        Questions(self.core).submit(self.qid, {'r': self.voice})
        with patch('makesound.harness_resume.queue_command', return_value=['stub']) as command, patch(
                'makesound.harness_resume.subprocess.run', return_value=SimpleNamespace(returncode=0)) as run:
            self.assertEqual(notify(self.core, self.qid)['status'], 'queued')
            self.assertEqual(notify(self.core, self.qid)['status'], 'queued')
            run.assert_called_once()
            self.assertEqual(command.call_args.args[0], self.thread)
            self.assertIn(self.qid, command.call_args.args[1])
        with self.assertRaises(MakeSoundError):
            register(self.core, self.qid, '01a140ba-6302-71a2-ae92-bb03233f2d2d')

    def test_timeout_preserves_answer_and_never_blindly_retries(self):
        register(self.core, self.qid, self.thread)
        Questions(self.core).submit(self.qid, {'r': self.voice})
        with patch('makesound.harness_resume.queue_command', return_value=['stub']), patch(
                'makesound.harness_resume.subprocess.run', side_effect=subprocess.TimeoutExpired('stub', 20)) as run:
            self.assertEqual(notify(self.core, self.qid)['status'], 'unknown')
            notify(self.core, self.qid)
            run.assert_called_once()
        self.assertEqual(Questions(self.core).read(self.qid)['status'], 'answered')

    def test_no_target_does_not_send(self):
        self.assertEqual(notify(self.core, self.qid)['status'], 'unavailable')
