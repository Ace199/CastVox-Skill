import json
import os
from unittest.mock import patch

from tests.integration.test_harness_resume import HarnessResume
from makesound import harness_resume
from makesound.questions import Questions
from makesound.errors import MakeSoundError


class WorkBuddyTask(HarnessResume):
    def env(self, session='origin-session'):
        return {'WORKBUDDY_CONFIG_DIR': 'fixture', 'CODEBUDDY_SESSION_ID': session}

    def test_default_registration_needs_no_gateway_credential(self):
        with patch.dict(os.environ, self.env(), clear=True):
            harness_resume.register_environment(self.core, self.qid)
        target = json.loads(self.core.managed_path(f'.makesound/studio/{self.qid}/wake-target.json').read_text())
        self.assertEqual(target['harness'], 'workbuddy_task')
        self.assertEqual(target['session_id'], 'origin-session')
        self.assertNotIn('token_fingerprint', target)

    def test_save_then_handoff_without_direct_engine_request(self):
        with patch.dict(os.environ, self.env(), clear=True):
            harness_resume.register_environment(self.core, self.qid)
            with self.assertRaises(MakeSoundError):
                harness_resume.notify(self.core, self.qid)
            Questions(self.core).submit(self.qid, {'r': self.voice})
            with patch('urllib.request.OpenerDirector.open', side_effect=AssertionError('No engine reply allowed')):
                self.assertEqual(harness_resume.notify(self.core, self.qid)['status'], 'awaiting_task')
                self.assertEqual(harness_resume.notify(self.core, self.qid)['status'], 'awaiting_task')

    def test_other_session_cannot_take_over_target(self):
        with patch.dict(os.environ, self.env(), clear=True):
            harness_resume.register_environment(self.core, self.qid)
        with patch.dict(os.environ, self.env('other-session'), clear=True), self.assertRaises(MakeSoundError):
            harness_resume.register_environment(self.core, self.qid)
