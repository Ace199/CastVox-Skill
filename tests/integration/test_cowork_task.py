"""Original Cowork tool-result handoff; no external messages or synthesis."""
import json
import io
import os
import threading
import unittest
from pathlib import Path
from unittest.mock import patch

from tests.integration.test_harness_resume import HarnessResume
from makesound import harness_resume
from makesound.errors import MakeSoundError
from makesound.questions import Questions


class CoworkTask(HarnessResume):
    def env(self, session='582efa3a'):
        config = self.a / 'local-agent-mode-sessions' / 'account' / session / '.claude'
        config.mkdir(parents=True, exist_ok=True)
        return {'CLAUDE_CODE_IS_COWORK': '1', 'CLAUDE_CONFIG_DIR': str(config)}

    def test_register_uses_session_scoped_identity_without_messaging_credentials(self):
        with patch.dict(os.environ, self.env(), clear=True):
            harness_resume.register_environment(self.core, self.qid)
        saved = self.core.managed_path(f'.makesound/studio/{self.qid}/wake-target.json').read_text()
        target = json.loads(saved)
        self.assertEqual(target['harness'], 'cowork_task')
        self.assertNotIn('CLAUDE_CONFIG_DIR', saved)
        self.assertNotIn('582efa3a', saved)
        with patch.dict(os.environ, self.env('123abcde'), clear=True), self.assertRaises(MakeSoundError):
            harness_resume.register_environment(self.core, self.qid)

    def test_wait_returns_only_after_answer_and_receipt_without_sending(self):
        from makesound.cowork_task import wait_for_binding
        with patch.dict(os.environ, self.env(), clear=True):
            harness_resume.register_environment(self.core, self.qid)
            self.assertEqual(wait_for_binding(self.core, self.qid, timeout=0)['status'], 'waiting')
            Questions(self.core).submit(self.qid, {'r': self.voice})
            self.assertEqual(wait_for_binding(self.core, self.qid, timeout=0)['status'], 'waiting')
            with patch('urllib.request.OpenerDirector.open', side_effect=AssertionError('No message dispatch')):
                self.assertEqual(harness_resume.notify(self.core, self.qid)['status'], 'awaiting_tool')
            result = wait_for_binding(self.core, self.qid, timeout=0)
            self.assertEqual(result['status'], 'binding_saved')
            self.assertEqual(result['answer_id'], Questions(self.core).read(self.qid)['answer']['answer_id'])
            self.assertFalse(result['agent_resumed'])
            self.assertIn('not authorization', result['next_action'])
            self.assertEqual(wait_for_binding(self.core, self.qid, timeout=0), result)

    def test_wait_rejects_other_session_and_invalid_timeout(self):
        from makesound.cowork_task import wait_for_binding
        with patch.dict(os.environ, self.env(), clear=True):
            harness_resume.register_environment(self.core, self.qid)
            for value in (-1, 56, float('nan'), True):
                with self.subTest(timeout=value), self.assertRaises(MakeSoundError):
                    wait_for_binding(self.core, self.qid, timeout=value)
        with patch.dict(os.environ, self.env('123abcde'), clear=True), self.assertRaises(MakeSoundError):
            wait_for_binding(self.core, self.qid, timeout=0)

    def test_shared_config_or_missing_origin_never_guesses_session(self):
        from makesound.cowork_task import environment_target
        for env in ({}, {'CLAUDE_CODE_IS_COWORK': '1'},
                    {'CLAUDE_CODE_IS_COWORK': '1', 'CLAUDE_CONFIG_DIR': str(Path.home() / '.claude')}):
            with self.subTest(env=env), patch.dict(os.environ, env, clear=True):
                self.assertIsNone(environment_target())

    def test_blocking_wait_observes_completion_in_original_request(self):
        from makesound.cowork_task import wait_for_binding
        with patch.dict(os.environ, self.env(), clear=True):
            harness_resume.register_environment(self.core, self.qid)
            def finish():
                Questions(self.core).submit(self.qid, {'r': self.voice})
                harness_resume.notify(self.core, self.qid)
            timer = threading.Timer(.1, finish)
            timer.start()
            try:
                result = wait_for_binding(self.core, self.qid, timeout=3)
            finally:
                timer.join(timeout=4)
            self.assertEqual(result['status'], 'binding_saved')

    def test_launcher_returns_wait_command_for_actual_question(self):
        from makesound.studio_session import start
        module = ('export const session = Object.freeze(' + json.dumps({'question_id': self.qid}) + ');').encode()
        def launch(args, **kwargs):
            kwargs['stdout'].write('{"url":"http://127.0.0.1:12345"}\n')
            kwargs['stdout'].flush()
            from unittest.mock import Mock
            process = Mock(pid=123)
            process.poll.return_value = None
            return process
        with patch.dict(os.environ, self.env(), clear=True), patch('makesound.studio_session.subprocess.Popen',
                side_effect=launch), patch('urllib.request.OpenerDirector.open', return_value=io.BytesIO(module)):
            result = start(self.core, self.qid)
        self.assertEqual(result['completion_transport'], 'pending_tool_result')
        command = result['wait_command']
        self.assertEqual(command[command.index('--question') + 1], result['question_id'])
        self.assertEqual(command[command.index('--project') + 1], str(self.core.root))
        self.assertNotIn('session_fingerprint', json.dumps(result))

    def test_workspace_service_can_return_binding_without_any_host_environment(self):
        from makesound.cowork_task import wait_for_binding
        with patch.dict(os.environ, {}, clear=True):
            harness_resume.register_tool_result(self.core, self.qid)
            Questions(self.core).submit(self.qid, {'r': self.voice})
            with patch('subprocess.run', side_effect=AssertionError('No external dispatch')):
                self.assertEqual(harness_resume.notify(self.core, self.qid)['status'], 'awaiting_tool')
            result = wait_for_binding(self.core, self.qid, timeout=0)
        self.assertEqual(result['status'], 'binding_saved')
        self.assertEqual(result['question_id'], self.qid)
        self.assertFalse(result['agent_resumed'])

    def test_portable_registration_never_takes_over_a_native_target(self):
        harness_resume.register(self.core, self.qid, self.thread)
        with self.assertRaises(MakeSoundError):
            harness_resume.register_tool_result(self.core, self.qid)

    def test_second_active_waiter_is_rejected_without_broadcast(self):
        from makesound.cowork_task import wait_for_binding
        from makesound.storage import file_lock
        harness_resume.register_tool_result(self.core, self.qid)
        lock = self.core.managed_path(f'.makesound/studio/{self.qid}/tool-result-wait.lock')
        with file_lock(lock):
            with self.assertRaises(MakeSoundError) as error:
                wait_for_binding(self.core, self.qid, timeout=0)
        self.assertEqual(error.exception.code, 'lock_timeout')

    def test_real_studio_process_and_http_complete_with_empty_host_environment(self):
        import socket
        import subprocess
        import urllib.request
        from concurrent.futures import ThreadPoolExecutor
        from makesound.studio_session import start
        from makesound.cowork_task import wait_for_binding
        self.net.stop()
        original_connect = socket.socket.connect
        def loopback_only(sock, address):
            if not isinstance(address, tuple) or address[0] != '127.0.0.1':
                raise AssertionError('External network forbidden')
            return original_connect(sock, address)
        processes = []
        original_popen = subprocess.Popen
        def launch(*args, **kwargs):
            process = original_popen(*args, **kwargs)
            processes.append(process)
            return process
        try:
            system_env = {key: os.environ[key] for key in ('SystemRoot', 'WINDIR', 'TEMP', 'TMP',
                          'USERPROFILE', 'HOME', 'HOMEDRIVE', 'HOMEPATH') if key in os.environ}
            with patch.dict(os.environ, system_env, clear=True), patch.object(socket.socket, 'connect', loopback_only), \
                    patch('makesound.studio_session.subprocess.Popen', side_effect=launch):
                try:
                    ready = start(self.core, self.qid, allow_fake=True, completion_mode='tool-result')
                except MakeSoundError as error:
                    log = self.core.managed_path(f'.makesound/studio/{self.qid}/stderr.log')
                    raise AssertionError(log.read_text(encoding='utf-8')[-1800:]) from error
                self.assertEqual(ready['completion_transport'], 'pending_tool_result')
                opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
                with opener.open(ready['url'] + '/js/session.js', timeout=3) as response:
                    module = response.read().decode('utf-8')
                session = json.loads(module.split('Object.freeze(', 1)[1].rsplit(');', 1)[0])
                request = urllib.request.Request(ready['url'] + '/api/v16/answers',
                    data=json.dumps({'question_id': ready['question_id'], 'assignments': {'r': self.voice}}).encode(),
                    headers={'Authorization': 'Bearer ' + session['token'], 'X-CSRF-Token': session['csrf'],
                             'Origin': ready['url'], 'Content-Type': 'application/json'})
                with ThreadPoolExecutor(max_workers=1) as executor:
                    waiting = executor.submit(wait_for_binding, self.core, ready['question_id'], timeout=3)
                    with opener.open(request, timeout=3) as response:
                        receipt = json.loads(response.read())
                    self.assertEqual(receipt['wake']['status'], 'awaiting_tool')
                    result = waiting.result(timeout=4)
                self.assertEqual(result['status'], 'binding_saved')
                self.assertEqual(result['answer_id'], Questions(self.core).read(ready['question_id'])['answer']['answer_id'])
                processes[0].wait(timeout=5)
        finally:
            for process in processes:
                if process.poll() is None:
                    process.terminate()
                    process.wait(timeout=5)
