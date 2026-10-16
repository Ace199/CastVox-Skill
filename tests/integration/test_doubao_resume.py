import importlib
import json
import os
from unittest.mock import patch

from tests.integration.test_harness_resume import HarnessResume
from makesound import harness_resume
from makesound.errors import MakeSoundError
from makesound.questions import Questions


class DoubaoResume(HarnessResume):
    def setUp(self):
        super().setUp()
        try:
            self.adapter = importlib.import_module('makesound.doubao_resume')
        except ModuleNotFoundError:
            self.adapter = None
        self.env = {'DOUBAO_OFFICE_APP_ID': '582478', 'MCP_VM_CONVERSATION_ID': '38447362655653122'}
        self.bridge = self.root / 'bridge.json'
        self.bridge.write_text(json.dumps({'endpoint': 'http://127.0.0.1:19349', 'browser_path': '/devtools/browser/test',
                                          'profile_path': str(self.root / 'Default')}))
        self.info = {'conversation_id': self.env['MCP_VM_CONVERSATION_ID'], 'workspace': str(self.a),
                     'project_id': 'project-one', 'runtime_type': 2, 'app_id': '582478', 'sandbox_auth_type': 1}

    def require_adapter(self):
        self.assertIsNotNone(self.adapter, 'Doubao session adapter is missing')

    def register_doubao(self):
        self.require_adapter()
        with patch.dict(os.environ, self.env, clear=True), patch.object(self.adapter, 'BRIDGE_PATH', self.bridge), \
                patch.object(self.adapter, '_control', return_value=self.info):
            harness_resume.register_environment(self.core, self.qid)

    def test_origin_registered_without_credentials(self):
        self.register_doubao()
        target = json.loads(self.core.managed_path(f'.makesound/studio/{self.qid}/wake-target.json').read_text(encoding='utf-8'))
        self.assertEqual(target['harness'], 'doubao')
        self.assertEqual(target['conversation_id'], self.env['MCP_VM_CONVERSATION_ID'])
        self.assertEqual(target['workspace'], str(self.a))
        self.assertNotIn('token', json.dumps(target).lower())

    def test_rejects_invalid_identity_cross_project_and_multiple_harnesses(self):
        self.require_adapter()
        for env, info in [({**self.env, 'MCP_VM_CONVERSATION_ID': 'not-an-id'}, self.info),
                          ({**self.env, 'CODEX_THREAD_ID': self.thread}, self.info),
                          (self.env, {**self.info, 'workspace': str(self.b)}),
                          (self.env, {**self.info, 'runtime_type': 1}),
                          (self.env, {**self.info, 'conversation_id': '38447362655653123'})]:
            with self.subTest(env=tuple(env), info=info), patch.dict(os.environ, env, clear=True), \
                    patch.object(self.adapter, 'BRIDGE_PATH', self.bridge), \
                    patch.object(self.adapter, '_control', return_value=info), self.assertRaises(MakeSoundError):
                harness_resume.register_environment(self.core, self.qid)

    def test_answer_saved_before_send_and_duplicate_not_resent(self):
        self.register_doubao()
        with self.assertRaises(MakeSoundError):
            harness_resume.notify(self.core, self.qid)
        Questions(self.core).submit(self.qid, {'r': self.voice})
        with patch.object(self.adapter, 'send', return_value={'status': 'queued', 'run_id': 'test-run'}) as send:
            self.assertEqual(harness_resume.notify(self.core, self.qid)['status'], 'queued')
            harness_resume.notify(self.core, self.qid)
            send.assert_called_once()
            self.assertIn('not approval', send.call_args.args[1])

    def test_timeout_or_closed_app_retains_answer_and_never_retries(self):
        self.register_doubao()
        Questions(self.core).submit(self.qid, {'r': self.voice})
        with patch.object(self.adapter, 'send', side_effect=TimeoutError) as send:
            self.assertEqual(harness_resume.notify(self.core, self.qid)['status'], 'unknown')
            harness_resume.notify(self.core, self.qid)
            send.assert_called_once()
        self.assertEqual(Questions(self.core).read(self.qid)['status'], 'answered')

    def test_remote_endpoint_rejected_without_control_call(self):
        self.require_adapter()
        data = json.loads(self.bridge.read_text())
        data['endpoint'] = 'http://example.com:19349'
        self.bridge.write_text(json.dumps(data))
        with patch.dict(os.environ, self.env, clear=True), patch.object(self.adapter, 'BRIDGE_PATH', self.bridge), \
                patch.object(self.adapter, '_control') as control, self.assertRaises(MakeSoundError):
            self.adapter.environment_target(self.core, self.qid)
        control.assert_not_called()
