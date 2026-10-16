from contextlib import closing
import json
import os
import sqlite3
from unittest.mock import patch

from tests.integration.test_harness_resume import HarnessResume
from makesound import harness_resume
from makesound.errors import MakeSoundError
from makesound.questions import Questions
from makesound import kimi_work


class KimiWork(HarnessResume):
    def setUp(self):
        super().setUp()
        self.share = self.root / 'kimi-share'
        self.agent = self.share / 'daimon/agents/main'
        self.agent.mkdir(parents=True)
        self.lock = self.agent / 'state-root.lock'
        self.lock.write_text(json.dumps({'generationId': 'generation-one', 'controlEndpoint': {
            'url': 'ws://127.0.0.1:1981/control', 'auth': {'token': 'private-local-token'}}}), encoding='utf-8')
        self.key = 'agent:main:main:conversation:1234'
        self.wire = self.share / 'daimon/runtime/kimi-code/home/sessions/wd_test/conv_test/agents/main/wire.jsonl'
        self.wire.parent.mkdir(parents=True)
        self.call = {'type': 'context.append_loop_event', 'event': {'type': 'tool.call',
            'toolCallId': 'origin-call', 'name': 'Bash', 'args': {'command':
                f'python -m makesound.studio_session --project "{self.a}" --question {self.qid}'}}}
        self.wire.write_text(json.dumps(self.call) + '\n', encoding='utf-8')
        db = self.agent / 'sessions/hosted-logical/conversations.sqlite'
        db.parent.mkdir(parents=True)
        with closing(sqlite3.connect(db)) as connection:
            connection.execute('CREATE TABLE conversations (agent_id, conversation_key, workspace_path, kernel_records_path)')
            connection.execute('INSERT INTO conversations VALUES (?, ?, ?, ?)',
                               ('main', self.key, str(self.a), str(self.wire)))
            connection.commit()
        self.env = {'KIMI_AGENT_CLIENT_ID': 'kimiwork', 'KIMI_SHARE_DIR': str(self.share)}

    def test_automatic_origin_uses_pending_call_and_persists_no_token(self):
        with patch.dict(os.environ, self.env, clear=True):
            harness_resume.register_environment(self.core, self.qid)
        text = self.core.managed_path(f'.makesound/studio/{self.qid}/wake-target.json').read_text()
        self.assertNotIn('private-local-token', text)
        self.assertEqual(json.loads(text)['conversation_key'], self.key)

    def test_does_not_guess_latest_conversation_or_completed_call(self):
        for text in ['', json.dumps(self.call) + '\n' + json.dumps({
                'type': 'context.append_loop_event', 'event': {'type': 'tool.result', 'toolCallId': 'origin-call'}})]:
            self.wire.write_text(text, encoding='utf-8')
            with patch.dict(os.environ, self.env, clear=True), self.assertRaises(MakeSoundError):
                kimi_work.environment_target(self.core, self.qid)

    def test_rejects_multiple_pending_origins(self):
        db = self.agent / 'sessions/hosted-logical/conversations.sqlite'
        with closing(sqlite3.connect(db)) as connection:
            connection.execute('INSERT INTO conversations VALUES (?, ?, ?, ?)',
                               ('main', self.key + '-other', str(self.a), str(self.wire)))
            connection.commit()
        with patch.dict(os.environ, self.env, clear=True), self.assertRaises(MakeSoundError):
            kimi_work.environment_target(self.core, self.qid)

    def test_kimi_cannot_override_another_harness(self):
        with patch.dict(os.environ, {**self.env, 'CODEX_THREAD_ID': self.thread}, clear=True), self.assertRaises(MakeSoundError):
            harness_resume.register_environment(self.core, self.qid)

    def test_saved_first_and_notifications_deduplicated(self):
        with patch.dict(os.environ, self.env, clear=True):
            harness_resume.register_environment(self.core, self.qid)
        with self.assertRaises(MakeSoundError):
            harness_resume.notify(self.core, self.qid)
        Questions(self.core).submit(self.qid, {'r': self.voice})
        with patch('makesound.kimi_work.send', return_value={'status': 'queued', 'turn_id': 'test-turn'}) as send:
            self.assertEqual(harness_resume.notify(self.core, self.qid)['status'], 'queued')
            harness_resume.notify(self.core, self.qid)
            send.assert_called_once()

    def test_restarted_runtime_cannot_receive_old_binding(self):
        with patch.dict(os.environ, self.env, clear=True):
            target = kimi_work.environment_target(self.core, self.qid)
        self.lock.write_text('{}', encoding='utf-8')
        with self.assertRaises(MakeSoundError):
            kimi_work.send(target, 'must not send')

    def test_remote_control_address_rejected(self):
        data = json.loads(self.lock.read_text())
        data['controlEndpoint']['url'] = 'ws://example.com:1981/control'
        self.lock.write_text(json.dumps(data), encoding='utf-8')
        with patch.dict(os.environ, self.env, clear=True), self.assertRaises(MakeSoundError):
            kimi_work.environment_target(self.core, self.qid)

    def test_unknown_delivery_never_retried_and_answer_retained(self):
        with patch.dict(os.environ, self.env, clear=True):
            harness_resume.register_environment(self.core, self.qid)
        Questions(self.core).submit(self.qid, {'r': self.voice})
        with patch('makesound.kimi_work.send', side_effect=TimeoutError) as send:
            self.assertEqual(harness_resume.notify(self.core, self.qid)['status'], 'unknown')
            harness_resume.notify(self.core, self.qid)
            send.assert_called_once()
        self.assertEqual(Questions(self.core).read(self.qid)['status'], 'answered')
