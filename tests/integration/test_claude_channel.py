import json
import unittest
import socket
from unittest.mock import patch

from makesound.claude_channel import Channel
from makesound.harness_resume import notify
from makesound.questions import Questions
from tests.integration.test_harness_resume import HarnessResume


class ClaudeChannel(HarnessResume):
    def test_registered_answer_emits_once_without_codex(self):
        self.net.stop()
        original = socket.socket.connect
        def local_only(sock, address):
            if address[0] != '127.0.0.1':
                raise AssertionError('External network forbidden')
            return original(sock, address)
        guard = patch.object(socket.socket, 'connect', local_only)
        guard.start()
        self.addCleanup(guard.stop)
        events = []
        with Channel(events.append) as channel:
            target = channel.register(str(self.core.root), self.qid)
            self.assertNotIn('token', target)
            Questions(self.core).submit(self.qid, {'r': self.voice})
            with patch('makesound.harness_resume.queue_command', side_effect=AssertionError('Wrong harness')):
                self.assertEqual(notify(self.core, self.qid)['status'], 'queued')
                self.assertEqual(notify(self.core, self.qid)['status'], 'queued')
            self.assertEqual(len(events), 1)
            self.assertEqual(events[0]['method'], 'notifications/claude/channel')
            self.assertIn(self.qid, events[0]['params']['content'])
            self.assertIn('not approval', events[0]['params']['content'])

    def test_wrong_token_unsaved_answer_and_duplicate_receiver(self):
        events = []
        with Channel(events.append) as channel:
            channel.register(str(self.core.root), self.qid)
            with self.assertRaises(Exception):
                channel.deliver('wrong', self.qid, 'wrong')
            with self.assertRaises(Exception):
                channel.deliver(channel.token, self.qid, 'wrong')
            answer = Questions(self.core).submit(self.qid, {'r': self.voice})
            saved = Questions(self.core).read(self.qid)['answer']['answer_id']
            channel.deliver(channel.token, self.qid, saved)
            channel.deliver(channel.token, self.qid, saved)
            self.assertEqual(len(events), 1)

    def test_target_cannot_be_hijacked_by_another_channel(self):
        with Channel(lambda event: None) as first, Channel(lambda event: None) as second:
            first.register(str(self.core.root), self.qid)
            with self.assertRaises(Exception):
                second.register(str(self.core.root), self.qid)

    def test_protocol_has_channel_capability_and_no_secret_in_tool_response(self):
        with Channel(lambda event: None) as channel:
            result = channel.rpc('initialize', {'protocolVersion': '2025-03-26'})
            self.assertIn('claude/channel', result['capabilities']['experimental'])
            tools = channel.rpc('tools/list', {})['tools']
            self.assertIn('soundmaker_register_binding', [tool['name'] for tool in tools])
            result = channel.rpc('tools/call', {'name': 'soundmaker_register_binding',
                                              'arguments': {'project': str(self.core.root), 'question_id': self.qid}})
            self.assertNotIn(channel.token, json.dumps(result))


if __name__ == '__main__':
    unittest.main()
