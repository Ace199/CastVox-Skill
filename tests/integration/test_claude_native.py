import json
import io
import os
import unittest
from unittest.mock import patch

from tests.integration.test_harness_resume import HarnessResume
from makesound import harness_resume
from makesound.errors import MakeSoundError
from makesound.questions import Questions


class ClaudeNative(HarnessResume):
    def env(self, suffix='one'):
        return {'CLAUDE_CODE_MESSAGING_SOCKET': '\\\\.\\pipe\\LOCAL\\cc-msg-' + suffix,
                'CLAUDE_CODE_MESSAGING_TOKEN': 'test-private-token-' + suffix}

    def register(self):
        self.assertTrue(hasattr(harness_resume, 'register_environment'), 'Claude automatic registration is missing')
        harness_resume.register_environment(self.core, self.qid)

    def test_register_does_not_persist_token_and_rejects_other_window(self):
        with patch.dict(os.environ, self.env(), clear=True):
            self.register()
            self.register()
        target = self.core.managed_path(f'.makesound/studio/{self.qid}/wake-target.json')
        self.assertNotIn('test-private-token', target.read_text())
        self.assertEqual(json.loads(target.read_text())['harness'], 'claude_native')
        with patch.dict(os.environ, self.env('two'), clear=True), self.assertRaises(MakeSoundError):
            self.register()

    def test_ambiguous_or_partial_environment_is_rejected(self):
        for env in [{**self.env(), 'CODEX_THREAD_ID': self.thread},
                    {'CLAUDE_CODE_MESSAGING_SOCKET': self.env()['CLAUDE_CODE_MESSAGING_SOCKET']}]:
            with patch.dict(os.environ, env, clear=True), self.assertRaises(MakeSoundError):
                self.register()

    def test_native_notification_saved_first_deduplicated_and_no_secret_receipt(self):
        with patch.dict(os.environ, self.env(), clear=True):
            self.register()
            with self.assertRaises(MakeSoundError):
                harness_resume.notify(self.core, self.qid)
            Questions(self.core).submit(self.qid, {'r': self.voice})
            with patch('makesound.claude_native.send', return_value={'status': 'sent_unconfirmed'}) as send:
                result = harness_resume.notify(self.core, self.qid)
                self.assertEqual(result['status'], 'sent_unconfirmed')
                harness_resume.notify(self.core, self.qid)
                send.assert_called_once()
                self.assertIn(self.qid, send.call_args.args[1])
                self.assertNotIn('test-private-token', json.dumps(result))

    def test_send_rejects_changed_environment(self):
        with patch.dict(os.environ, self.env(), clear=True):
            self.register()
        target = json.loads(self.core.managed_path(f'.makesound/studio/{self.qid}/wake-target.json').read_text())
        from makesound.claude_native import send
        with patch.dict(os.environ, self.env('two'), clear=True), self.assertRaises(MakeSoundError):
            send(target, 'must not reach another window')

    def test_native_failure_preserves_answer(self):
        with patch.dict(os.environ, self.env(), clear=True):
            self.register()
            Questions(self.core).submit(self.qid, {'r': self.voice})
            with patch('makesound.claude_native.send', side_effect=TimeoutError) as send:
                self.assertEqual(harness_resume.notify(self.core, self.qid)['status'], 'unknown')
                harness_resume.notify(self.core, self.qid)
                send.assert_called_once()
            self.assertEqual(Questions(self.core).read(self.qid)['status'], 'answered')

    def test_launcher_does_not_reuse_live_server_from_unbound_environment(self):
        from makesound.studio_session import start
        folder = self.core.managed_path(f'.makesound/studio/{self.qid}')
        folder.mkdir(parents=True)
        (folder / 'session.json').write_text(json.dumps({'url': 'http://127.0.0.1:12345',
            'question_id': self.qid, 'pid': 123}))
        module = ('export const session = Object.freeze(' + json.dumps({'question_id': self.qid}) + ');').encode()
        with patch.dict(os.environ, self.env(), clear=True), patch('urllib.request.OpenerDirector.open',
                return_value=io.BytesIO(module)), self.assertRaises(MakeSoundError) as caught:
            start(self.core, self.qid)
        self.assertEqual(caught.exception.code, 'session_mismatch')
        self.assertFalse((folder / 'wake-target.json').exists())
