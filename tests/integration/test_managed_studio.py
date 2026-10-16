import json
import io
import os
from contextlib import contextmanager
import threading
import urllib.request
import unittest
from unittest.mock import patch

from tests.helpers import Fixture
from makesound.core_v16 import ProjectCore
from makesound.offline_harness import prepare
from makesound.questions import Questions
from makesound.errors import MakeSoundError


class ManagedStudio(Fixture, unittest.TestCase):
    def test_workbuddy_cli_prints_final_task_result(self):
        from makesound import studio_session
        result = {'status': 'binding_saved', 'question_id': 'q_fixture', 'answer_id': 'a_fixture',
                  'project': str(self.a), 'next_action': 'Read saved Answer'}
        output = io.StringIO()
        with patch.dict(os.environ, {'WORKBUDDY_CONFIG_DIR': 'fixture'}), \
                patch('sys.argv', ['studio_session', '--project', str(self.a), '--question', 'q_fixture']), \
                patch.object(studio_session, 'serve_managed', return_value=result) as serve, \
                patch('sys.stdout', output):
            studio_session.main()
        self.assertEqual(json.loads(output.getvalue()), result)
        self.assertEqual(serve.call_args.args[1], 'q_fixture')

    def test_pending_is_checked_again_after_acquiring_launch_lock(self):
        from makesound.studio_session import serve_managed
        core = ProjectCore(self.a)
        _, voice = core.add_voice('fixture', 'other',
            {'provider': 'fake', 'region': 'test', 'model': 'fake-v1', 'voice_id': 'FAKE_VOICE_A'}, 0)
        qid = prepare(core, {'roles': ['r'], 'segments': [
            {'paragraph_id': 'p', 'sentence_id': 's', 'role_id': 'r', 'text': 'test'}]})['question_id']
        @contextmanager
        def completed_while_waiting(*args):
            Questions(core).submit(qid, {'r': voice})
            yield
        with patch.dict(os.environ, {}, clear=True), patch('makesound.storage.file_lock', completed_while_waiting), \
                patch('studio_v16_server.create_server', side_effect=AssertionError('Must not start an answered task')) as create:
            with self.assertRaises(MakeSoundError) as caught:
                serve_managed(core, qid, config_dir=self.root / 'providers')
            self.assertEqual(caught.exception.code, 'answer_immutable')
            create.assert_not_called()

    def test_managed_server_remains_alive_after_ready_until_host_stops_it(self):
        from makesound import studio_session
        self.assertTrue(hasattr(studio_session, 'serve_managed'), 'Managed Studio lifecycle is missing')
        self.net.stop()
        core = ProjectCore(self.a)
        _, voice = core.add_voice('fixture', 'other',
            {'provider': 'fake', 'region': 'test', 'model': 'fake-v1', 'voice_id': 'FAKE_VOICE_A'}, 0)
        qid = prepare(core, {'roles': ['r'], 'segments': [
            {'paragraph_id': 'p', 'sentence_id': 's', 'role_id': 'r', 'text': 'test'}]})['question_id']
        ready, failure, servers, results = [], [], [], []
        event = threading.Event()
        from studio_v16_server import create_server
        def capture_server(*args, **kwargs):
            server = create_server(*args, **kwargs)
            servers.append(server)
            return server
        def on_ready(result):
            ready.append(result)
            event.set()
        def run():
            try:
                results.append(studio_session.serve_managed(core, qid, allow_fake=True, on_ready=on_ready,
                                                           config_dir=self.root / 'providers'))
            except Exception as exc:
                failure.append(exc)
                event.set()
        entered, release = threading.Event(), threading.Event()
        responses, requester = [], None
        def delayed_notify(*args):
            entered.set()
            if not release.wait(5):
                raise TimeoutError('Fixture did not release notification')
            return {'status': 'delivered'}
        with patch.dict(os.environ, {}, clear=True), patch('studio_v16_server.create_server', side_effect=capture_server), \
                patch('makesound.harness_resume.notify', side_effect=delayed_notify):
            thread = threading.Thread(target=run, daemon=True)
            thread.start()
            try:
                self.assertTrue(event.wait(10), 'Studio did not become ready')
                self.assertEqual(failure, [])
                self.assertTrue(thread.is_alive(), 'Readiness must not finish the managed command')
                opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
                with opener.open(ready[0]['url'] + '/js/session.js', timeout=3) as response:
                    self.assertIn(qid, response.read().decode())
                self.assertEqual(ready[0]['lifecycle'], 'host_managed')
                record = json.loads(core.managed_path(f'.makesound/studio/{qid}/session.json').read_text())
                self.assertEqual(record['pid'], os.getpid())
                self.assertEqual(record['lifecycle'], 'host_managed')
                server = servers[0]
                def submit():
                    try:
                        request = urllib.request.Request(ready[0]['url'] + '/api/v16/answers',
                            data=json.dumps({'question_id': qid, 'assignments': {'r': voice}}).encode(),
                            headers={'Authorization': 'Bearer ' + server.session_token,
                                     'X-CSRF-Token': server.csrf_token, 'Origin': ready[0]['url'],
                                     'Content-Type': 'application/json'})
                        with opener.open(request, timeout=8) as response:
                            responses.append(json.loads(response.read()))
                    except Exception as exc:
                        failure.append(exc)
                requester = threading.Thread(target=submit, daemon=True)
                requester.start()
                self.assertTrue(entered.wait(5), 'HTTP completion did not reach notification')
                self.assertEqual(Questions(core).read(qid)['status'], 'answered')
                self.assertTrue(thread.is_alive(), 'Keep the host task alive while notify is in flight')
                release.set()
                requester.join(timeout=8)
                thread.join(timeout=5)
                self.assertEqual(failure, [])
                self.assertEqual(responses[0]['wake']['status'], 'delivered')
                self.assertFalse(thread.is_alive(), 'Managed task should end after HTTP completion')
                self.assertEqual(results[0]['status'], 'binding_saved')
                self.assertEqual(results[0]['question_id'], qid)
                self.assertEqual(results[0]['project'], str(core.root))
                self.assertEqual(results[0]['answer_id'], Questions(core).read(qid)['answer']['answer_id'])
                self.assertIn('Read this saved Answer', results[0]['next_action'])
            finally:
                release.set()
                if requester:
                    requester.join(timeout=8)
                for server in servers:
                    server.shutdown()
                thread.join(timeout=5)
            self.assertFalse(thread.is_alive())


if __name__ == '__main__':
    unittest.main()
