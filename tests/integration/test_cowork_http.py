import json
import os
from concurrent.futures import ThreadPoolExecutor
from unittest.mock import patch

from tests.integration.test_v16_http import V16HTTP
from makesound import harness_resume
from makesound.cowork_task import wait_for_binding


class CoworkHTTP(V16HTTP):
    def test_http_save_returns_answer_to_original_waiter_without_synthesis(self):
        config = self.a / 'local-agent-mode-sessions/account/582efa3a/.claude'
        config.mkdir(parents=True)
        env = {'CLAUDE_CODE_IS_COWORK': '1', 'CLAUDE_CONFIG_DIR': str(config)}
        with patch.dict(os.environ, env, clear=True), patch('makesound.providers.FakeProvider.synthesize',
                side_effect=AssertionError('No paid or fake synthesis')):
            _, voice = self.add()
            qid = self.backend.questions.create('cowork_http', 'origin', ['r'])['question_id']
            self.server.question_id = qid
            self.server.close_after_answer = True
            harness_resume.register_environment(self.core, qid)
            with ThreadPoolExecutor(max_workers=1) as executor:
                pending = executor.submit(wait_for_binding, self.core, qid, timeout=3)
                status, raw, _ = self.request('/api/v16/answers', {
                    'question_id': qid, 'assignments': {'r': voice['project_voice_id']}})
                self.assertEqual(status, 200)
                self.assertEqual(json.loads(raw)['wake']['status'], 'awaiting_tool')
                result = pending.result(timeout=4)
            self.assertEqual(result['status'], 'binding_saved')
            self.assertEqual(result['question_id'], qid)
            self.assertEqual(result['answer_id'], self.backend.questions.read(qid)['answer']['answer_id'])
            self.assertFalse(result['agent_resumed'])
