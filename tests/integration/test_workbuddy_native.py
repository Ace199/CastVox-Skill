import io
import json
import os
import unittest
import urllib.error
from unittest.mock import patch

from tests.integration.test_harness_resume import HarnessResume
from makesound import harness_resume
from makesound.errors import MakeSoundError
from makesound.questions import Questions


class WorkBuddyNative(HarnessResume):
    def env(self, suffix='one'):
        return {'CODEBUDDY_SESSION_ID': 'workbuddy-session-' + suffix,
                'WORKBUDDY_CONFIG_DIR': 'C:/test/workbuddy',
                'CODEBUDDY_SERVICE_PROXY_URL': 'http://127.0.0.1:12345/internal/hooks/services/invoke',
                'CODEBUDDY_GATEWAY_PASSWORD': 'test-private-gateway-' + suffix}

    def adapter(self):
        from makesound import workbuddy_native
        return workbuddy_native

    def test_register_own_identity_without_persisting_password(self):
        with patch.dict(os.environ, self.env(), clear=True):
            harness_resume.register_environment(self.core, self.qid)
            harness_resume.register_environment(self.core, self.qid)
        path = self.core.managed_path(f'.makesound/studio/{self.qid}/wake-target.json')
        self.assertTrue(path.is_file(), 'WorkBuddy was not registered')
        self.assertEqual(json.loads(path.read_text())['harness'], 'workbuddy_task')
        self.assertNotIn('test-private-gateway', path.read_text())
        with patch.dict(os.environ, self.env('two'), clear=True), self.assertRaises(MakeSoundError):
            harness_resume.register_environment(self.core, self.qid)

    def test_partial_ambiguous_and_remote_environments_rejected(self):
        for change in [{'CODEBUDDY_GATEWAY_PASSWORD': ''}, {'CODEX_THREAD_ID': self.thread},
                       {'CODEBUDDY_SERVICE_PROXY_URL': 'https://example.com/internal/hooks/services/invoke'},
                       {'CODEBUDDY_SERVICE_PROXY_URL': 'http://127.0.0.1:12345/other'},
                       {'CODEBUDDY_GATEWAY_PASSWORD': 'bad\r\nheader'}]:
            with patch.dict(os.environ, {**self.env(), **change}, clear=True), self.assertRaises(MakeSoundError):
                if 'CODEX_THREAD_ID' in change:
                    harness_resume.register_environment(self.core, self.qid)
                else:
                    self.adapter().environment_target()

    def test_saved_before_send_deduplicated_and_no_secret_in_receipt(self):
        with patch.dict(os.environ, self.env(), clear=True):
            harness_resume.register_environment(self.core, self.qid)
            with self.assertRaises(MakeSoundError):
                harness_resume.notify(self.core, self.qid)
            Questions(self.core).submit(self.qid, {'r': self.voice})
            with patch('makesound.workbuddy_task.complete', return_value={'status': 'awaiting_task'}) as send:
                result = harness_resume.notify(self.core, self.qid)
                self.assertEqual(result['status'], 'awaiting_task')
                harness_resume.notify(self.core, self.qid)
                send.assert_called_once()
                self.assertIn(self.qid, send.call_args.args[1])
                self.assertNotIn('test-private-gateway', json.dumps(result))

    def test_changed_environment_rejected_before_network(self):
        adapter = self.adapter()
        with patch.dict(os.environ, self.env(), clear=True):
            target = adapter.environment_target()
        with patch.dict(os.environ, self.env('two'), clear=True), self.assertRaises(MakeSoundError):
            adapter.send(target, 'do not send to another chat')

    def test_workbuddy_cannot_use_detached_launcher(self):
        from makesound.studio_session import start
        with patch.dict(os.environ, self.env(), clear=True), patch('subprocess.Popen') as spawn:
            with self.assertRaises(MakeSoundError) as caught:
                start(self.core, self.qid)
            self.assertEqual(caught.exception.code, 'managed_launch_required')
            spawn.assert_not_called()

    def test_reply_uses_exact_session_auth_and_requires_explicit_receipt(self):
        adapter = self.adapter()
        with patch.dict(os.environ, self.env(), clear=True):
            target = adapter.environment_target()
            with patch.object(adapter, '_request', side_effect=[
                    {'sessionId': target['session_id'], 'writerOccupied': True}, {'delivered': True}]) as request:
                self.assertEqual(adapter.send(target, 'binding completed')['status'], 'delivered')
                self.assertEqual(request.call_args_list[1].args[1],
                                 '/api/v1/sessions/workbuddy-session-one/reply')
                self.assertEqual(request.call_args_list[1].kwargs['body'], {'text': 'binding completed'})

    def test_live_mismatch_prevents_post(self):
        adapter = self.adapter()
        with patch.dict(os.environ, self.env(), clear=True):
            target = adapter.environment_target()
            with patch.object(adapter, '_request', return_value={'sessionId': 'another-session'}) as request:
                with self.assertRaises(MakeSoundError):
                    adapter.send(target, 'do not switch chats')
                request.assert_called_once()

    def test_http_transport_auth_and_wrapped_acknowledgement(self):
        adapter = self.adapter()
        with patch.dict(os.environ, self.env(), clear=True):
            target = adapter.environment_target()
            with patch.object(adapter.urllib.request, 'build_opener') as build:
                response = build.return_value.open.return_value.__enter__.return_value
                response.read.return_value = b'{"data":{"delivered":true}}'
                self.assertEqual(adapter._request(target, '/api/v1/sessions/own/reply', body={'text': 'test'}),
                                 {'delivered': True})
                req = build.return_value.open.call_args.args[0]
                self.assertEqual(req.get_header('Authorization'), 'Bearer test-private-gateway-one')
                self.assertEqual(req.get_method(), 'POST')
                self.assertEqual(json.loads(req.data), {'text': 'test'})
                self.assertTrue(any(isinstance(arg, adapter._NoRedirect) for arg in build.call_args.args))

    def test_explicit_host_rejection_and_uncertain_response_are_distinct(self):
        adapter = self.adapter()
        with patch.dict(os.environ, self.env(), clear=True):
            target = adapter.environment_target()
            for code, status in [(401, 'failed'), (409, 'failed'), (500, 'unknown')]:
                with patch.object(adapter, '_request', side_effect=[
                        {'sessionId': target['session_id']},
                        urllib.error.HTTPError('http://127.0.0.1', code, 'rejected', {}, None)]):
                    self.assertEqual(adapter.send(target, 'test')['status'], status)

    def test_timeout_preserves_answer_and_no_retry(self):
        self.adapter()
        with patch.dict(os.environ, self.env(), clear=True):
            harness_resume.register_environment(self.core, self.qid)
            Questions(self.core).submit(self.qid, {'r': self.voice})
            with patch('makesound.workbuddy_task.complete', side_effect=TimeoutError) as send:
                self.assertEqual(harness_resume.notify(self.core, self.qid)['status'], 'unknown')
                harness_resume.notify(self.core, self.qid)
                send.assert_called_once()
            self.assertEqual(Questions(self.core).read(self.qid)['status'], 'answered')


if __name__ == '__main__':
    unittest.main()
