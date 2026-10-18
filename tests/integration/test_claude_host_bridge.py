import json
import os
import queue
import socket
import subprocess
import sys
import threading
import unittest
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from unittest.mock import patch

from tests.helpers import Fixture, ROOT
from makesound.errors import MakeSoundError


class ClaudeHostBridge(Fixture, unittest.TestCase):
    def setUp(self):
        super().setUp()
        from makesound.claude_host_bridge import Bridge
        self.bridge = Bridge([self.a])
        self.addCleanup(self.bridge.close)
        self.net.stop()
        original = socket.socket.connect
        def local_only(sock, address):
            if address[0] != '127.0.0.1':
                raise AssertionError('External network forbidden')
            return original(sock, address)
        guard = patch.object(socket.socket, 'connect', local_only)
        guard.start()
        self.addCleanup(guard.stop)

    def test_host_page_survives_tool_calls_and_wait_returns_real_answer(self):
        with patch('makesound.providers.FakeProvider.synthesize', side_effect=AssertionError('No synthesis')):
            ready = self.bridge.call('soundmaker_smoke_binding', {'request_id': 'first'})
            self.assertEqual(self.bridge.call('soundmaker_host_status', {})['status'], 'ready')
            opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
            with opener.open(ready['url'] + '/js/session.js', timeout=3) as response:
                module = response.read().decode()
            session = json.loads(module.split('Object.freeze(', 1)[1].rsplit(');', 1)[0])
            with ThreadPoolExecutor(max_workers=1) as executor:
                pending = executor.submit(self.bridge.call, 'soundmaker_wait_binding', {'handle': ready['handle'], 'timeout': 3})
                req = urllib.request.Request(ready['url'] + '/api/v16/answers',
                    data=json.dumps({'question_id': ready['question_id'], 'assignments': {'test_narrator': ready['project_voice_id']}}).encode(),
                    headers={'Authorization': 'Bearer ' + session['token'], 'X-CSRF-Token': session['csrf'],
                             'Origin': ready['url'], 'Content-Type': 'application/json'})
                with opener.open(req, timeout=3) as response:
                    receipt = json.loads(response.read())
                result = pending.result(timeout=4)
            self.assertEqual(receipt['wake']['status'], 'awaiting_tool')
            self.assertEqual(result['status'], 'binding_saved')
            self.assertEqual(result['question_id'], ready['question_id'])
            self.assertEqual(result['answer_id'], result['answer']['answer_id'])
            self.assertFalse(result['agent_resumed'])
            self.assertEqual(self.bridge.call('soundmaker_wait_binding', {'handle': ready['handle'], 'timeout': 0}), result)

    def test_smoke_retry_does_not_create_more_questions(self):
        first = self.bridge.call('soundmaker_smoke_binding', {'request_id': 'same'})
        second = self.bridge.call('soundmaker_smoke_binding', {'request_id': 'same'})
        self.assertEqual(first['handle'], second['handle'])
        self.assertEqual(first['question_id'], second['question_id'])
        self.assertEqual(first['url'], second['url'])

    def test_handles_are_process_scoped_and_no_arbitrary_paths_or_generation_tools(self):
        ready = self.bridge.call('soundmaker_smoke_binding', {'request_id': 'one'})
        from makesound.claude_host_bridge import Bridge
        with Bridge([self.a]) as other:
            with self.assertRaises(MakeSoundError):
                other.call('soundmaker_wait_binding', {'handle': ready['handle'], 'timeout': 0})
        for args in ({'project_key': '../outside'}, {'project_key': str(self.b)}):
            with self.assertRaises(MakeSoundError):
                self.bridge.call('soundmaker_prepare_binding', {**args, 'request_id': 'x', 'script': {}})
        names = [tool['name'] for tool in self.bridge.tools()]
        self.assertNotIn('synthesize', ' '.join(names))

    def test_prepare_request_id_conflict_preserves_first_script(self):
        script = {'roles': ['r'], 'segments': [{'paragraph_id': 'p', 'sentence_id': 's', 'role_id': 'r', 'text': '原文'}]}
        first = self.bridge.call('soundmaker_prepare_binding', {'project_key': 'story', 'request_id': 'one', 'script': script})
        changed = {**script, 'segments': [{**script['segments'][0], 'text': '已改变'}]}
        with self.assertRaises(MakeSoundError):
            self.bridge.call('soundmaker_prepare_binding', {'project_key': 'story', 'request_id': 'one', 'script': changed})
        self.assertEqual(self.bridge.call('soundmaker_prepare_binding', {'project_key': 'story', 'request_id': 'one', 'script': script})['question_id'], first['question_id'])

    def test_cancel_wait_preserves_pending_question(self):
        ready = self.bridge.call('soundmaker_smoke_binding', {'request_id': 'cancel'})
        cancelled = threading.Event()
        cancelled.set()
        result = self.bridge.call('soundmaker_wait_binding', {'handle': ready['handle'], 'timeout': 50}, cancel_event=cancelled)
        self.assertEqual(result['status'], 'cancelled')
        self.assertFalse(result['agent_resumed'])

    def test_read_after_reconnect_preserves_saved_answer_without_revision(self):
        from makesound.questions import Questions
        ready = self.bridge.call('soundmaker_smoke_binding', {'request_id': 'read'})
        core = self.bridge.handles[ready['handle']]['core']
        Questions(core).submit(ready['question_id'], {'test_narrator': ready['project_voice_id']})
        before = sorted(core.managed_path('.makesound/questions').glob('*.json'))
        from makesound.claude_host_bridge import Bridge
        with Bridge([self.a]) as restarted:
            saved = restarted.call('soundmaker_read_binding', {'project_key': ready['project_key'], 'question_id': ready['question_id']})
        self.assertEqual(saved['status'], 'binding_saved')
        self.assertEqual(saved['answer']['answer_id'], Questions(core).read(ready['question_id'])['answer']['answer_id'])
        self.assertEqual(sorted(core.managed_path('.makesound/questions').glob('*.json')), before)

    def test_reopening_saved_binding_prefills_revision_and_preserves_old_answer(self):
        from makesound.questions import Questions
        ready = self.bridge.call('soundmaker_smoke_binding', {'request_id': 'reopen'})
        core = self.bridge.handles[ready['handle']]['core']
        Questions(core).submit(ready['question_id'], {'test_narrator': ready['project_voice_id']})
        previous = Questions(core).read(ready['question_id'])['answer']
        reopened = self.bridge.call('soundmaker_open_binding', {'project_key': ready['project_key'], 'question_id': ready['question_id']})
        draft = Questions(core).read(reopened['question_id'])
        self.assertNotEqual(reopened['question_id'], ready['question_id'])
        self.assertEqual(draft['source_question_id'], ready['question_id'])
        self.assertEqual(draft['assignments']['test_narrator']['project_voice_id'], ready['project_voice_id'])
        self.assertEqual(Questions(core).read(ready['question_id'])['answer'], previous)

    def test_real_stdio_process_keeps_page_and_routes_completion_by_request_id(self):
        self._stdio_roundtrip()

    def test_generic_stdio_routes_soundmaker_through_application_adapter(self):
        self._stdio_roundtrip(generic=True)

    def test_versioned_stdio_preserves_old_webpage_and_returns_standard_result(self):
        self._stdio_roundtrip(generic=True, versioned=True)

    def _stdio_roundtrip(self, *, generic=False, versioned=False):
        command = [sys.executable, '-X', 'utf8', str(ROOT / ('scripts/host_bridge.py' if generic else 'scripts/claude_host_bridge.py')), '--allowed-root', str(self.a)]
        if generic:
            command.extend(['--application', 'soundmaker'])
        process = subprocess.Popen(command, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            text=True, encoding='utf-8', creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0)
        responses = queue.Queue()
        def read():
            for line in process.stdout:
                responses.put(json.loads(line))
        reader = threading.Thread(target=read, daemon=True)
        reader.start()
        def send(identity, method, params):
            process.stdin.write(json.dumps({'jsonrpc': '2.0', 'id': identity, 'method': method, 'params': params}) + '\n')
            process.stdin.flush()
        def receive(identity):
            response = responses.get(timeout=5)
            self.assertEqual(response['id'], identity)
            return response['result']
        try:
            send(1, 'initialize', {'protocolVersion': '2025-03-26'})
            self.assertEqual(receive(1)['serverInfo']['name'], 'host-bridge' if generic else 'soundmaker-host')
            send(2, 'tools/call', {'name': 'host_bridge_start' if generic else 'soundmaker_smoke_binding',
                'arguments': {'application': 'soundmaker', 'operation': 'smoke_binding', 'payload': {}, 'request_id': 'wire',
                              **({'protocol_version': '1.0'} if versioned else {})}
                    if generic else {'request_id': 'wire'}})
            ready = json.loads(receive(2)['content'][0]['text'])
            business = ready['data'] if versioned else ready
            send(3, 'tools/call', {'name': ready['wait_tool']['name'], 'arguments': {**ready['wait_tool']['arguments'], 'timeout': 3}})
            send(4, 'ping', {})
            self.assertEqual(receive(4), {})  # A pending wait must not block other MCP requests.
            opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
            with opener.open(ready['url'] + '/js/session.js', timeout=3) as response:
                module = response.read().decode()
            session = json.loads(module.split('Object.freeze(', 1)[1].rsplit(');', 1)[0])
            request = urllib.request.Request(ready['url'] + '/api/v16/answers',
                data=json.dumps({'question_id': business['question_id'], 'assignments': {'test_narrator': business['project_voice_id']}}).encode(),
                headers={'Authorization': 'Bearer ' + session['token'], 'X-CSRF-Token': session['csrf'],
                         'Origin': ready['url'], 'Content-Type': 'application/json'})
            with opener.open(request, timeout=3) as response:
                self.assertEqual(response.status, 200)
            completed = json.loads(receive(3)['content'][0]['text'])
            self.assertEqual(completed['status'], 'completed' if versioned else 'binding_saved')
            saved = completed['data'] if versioned else completed
            self.assertEqual(saved['answer_id'], saved['answer']['answer_id'])
            if versioned:
                send(5, 'tools/call', {'name': 'host_bridge_read', 'arguments': {
                    'protocol_version': '1.0', 'application': 'unregistered', 'resource': {}}})
                failure = receive(5)
                self.assertTrue(failure['isError'])
                value = json.loads(failure['content'][0]['text'])
                self.assertEqual(value['status'], 'failed')
                self.assertEqual(value['error']['code'], 'unknown_application')
            process.stdin.close()
            process.wait(timeout=5)
            self.assertEqual(process.returncode, 0, process.stderr.read())
        finally:
            if process.poll() is None:
                process.terminate()
                process.wait(timeout=5)
            reader.join(timeout=2)
            process.stdout.close()
            process.stderr.close()
            if not process.stdin.closed:
                process.stdin.close()


if __name__ == '__main__':
    unittest.main()
