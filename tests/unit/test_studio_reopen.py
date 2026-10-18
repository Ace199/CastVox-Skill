import io
import json
import os
import unittest
from unittest.mock import Mock, patch

from tests.helpers import Fixture
from tests.unit.test_v16 import SOURCE
from makesound.core_v16 import ProjectCore
from makesound.offline_harness import prepare
from makesound.questions import Questions


class StudioReopen(Fixture, unittest.TestCase):
    @unittest.skipUnless(os.name == 'nt', 'Windows console redirector regression')
    def test_windows_server_uses_matching_windowless_interpreter(self):
        from makesound import studio_session
        executable = self.a / 'python.exe'
        windowless = self.a / 'pythonw.exe'
        executable.touch()
        with patch.object(studio_session.sys, 'executable', str(executable)):
            self.assertEqual(studio_session._server_executable(), str(executable))
            windowless.touch()
            self.assertEqual(studio_session._server_executable(), str(windowless))

    def test_management_launch_needs_no_question_or_host_registration(self):
        from makesound.studio_session import start
        core = ProjectCore(self.a)
        process = Mock(pid=123)
        process.poll.return_value = None
        def launch(args, **kwargs):
            self.assertNotIn('--question', args)
            self.assertNotIn('--once', args)
            kwargs['stdout'].write(json.dumps({'url': 'http://127.0.0.1:12345'}) + '\n')
            kwargs['stdout'].flush()
            return process
        opener = Mock()
        opener.open.side_effect = lambda *a, **k: io.BytesIO(('export const session = Object.freeze(' +
            json.dumps({'question_id':None,'ui_language':'zh-CN','project_id':core.read()['project_id']}) + ');').encode())
        with patch('makesound.studio_session.subprocess.Popen', side_effect=launch), \
                patch('makesound.studio_session._local_http_opener', return_value=opener), \
                patch('makesound.harness_resume.register_environment', side_effect=AssertionError('No fake task')), \
                patch('makesound.harness_resume.environment_target', side_effect=AssertionError('No host notification')):
            result = start(core, ui_language='zh-CN')
            self.assertIsNone(result['question_id'])
            self.assertFalse(result['once'])
            self.assertEqual(start(core, ui_language='zh-CN')['url'], result['url'])

    def test_answered_binding_launch_prepares_editable_revision(self):
        from makesound import studio_session
        core = ProjectCore(self.a)
        _, voice = core.add_voice('test', 'other', SOURCE, 0)
        qid = prepare(core, {'roles': ['r'], 'segments': [
            {'paragraph_id':'p', 'sentence_id':'s', 'role_id':'r', 'text':'原文'}]})['question_id']
        Questions(core).submit(qid, {'r':voice})
        old = Questions(core).read(qid)
        # Fail startup immediately after resolution, before any host/service work.
        with patch('makesound.harness_resume.environment_target', side_effect=RuntimeError('resolved')) as origin:
            with self.assertRaisesRegex(RuntimeError, 'resolved'):
                studio_session.start(core, qid)
        self.assertEqual(origin.call_args.kwargs['qid'], qid)
        from makesound.binding_revision import create
        draft = create(core, qid)
        self.assertNotEqual(draft['question_id'], qid)
        self.assertEqual(Questions(core).read(draft['question_id'])['status'], 'pending')
        self.assertEqual(Questions(core).read(qid), old)

    def test_cli_management_does_not_require_question(self):
        from makesound import studio_session
        with patch.dict(os.environ, {'WORKBUDDY_CONFIG_DIR':''}), \
                patch('sys.argv', ['studio_session', '--project', str(self.a)]), \
                patch.object(studio_session, 'start', return_value={'url':'http://127.0.0.1:12345'}) as start, \
                patch('sys.stdout', io.StringIO()):
            studio_session.main()
        self.assertIsNone(start.call_args.args[1])

    def test_cli_failure_is_sanitized_and_preserves_user_state(self):
        from makesound import studio_session
        from makesound.errors import MakeSoundError
        output = io.StringIO()
        with patch.dict(os.environ, {'WORKBUDDY_CONFIG_DIR':''}), \
                patch('sys.argv', ['studio_session', '--project', str(self.a)]), \
                patch.object(studio_session, 'start', side_effect=MakeSoundError('session_mismatch', 'private detail')), \
                patch('sys.stdout', output):
            self.assertEqual(studio_session.main(), 2)
        result = json.loads(output.getvalue())
        self.assertEqual(result['code'], 'session_mismatch')
        self.assertNotIn('private detail', output.getvalue())

    def test_revision_registers_new_id_using_original_command_identity(self):
        from makesound.harness_resume import register_environment
        core = ProjectCore(self.a)
        target = {'harness':'kimi_work', 'conversation_key':'origin'}
        with patch('makesound.harness_resume.environment_target', return_value=target) as discover, \
                patch('makesound.harness_resume._register_target') as save:
            register_environment(core, 'q_revision', discovery_question_id='q_original')
        self.assertEqual(discover.call_args.kwargs['qid'], 'q_original')
        self.assertEqual(save.call_args.args[1], 'q_revision')
        self.assertEqual(save.call_args.args[2]['question_id'], 'q_revision')
