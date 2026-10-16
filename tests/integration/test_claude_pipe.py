"""Real Windows pipe and HTTP completion; no model or provider calls."""
import json
import os
import subprocess
import unittest
import uuid
from unittest.mock import patch

from tests.integration.test_v16_http import V16HTTP
from makesound.harness_resume import register_environment


@unittest.skipUnless(os.name == 'nt', 'Windows named pipe test')
class ClaudePipe(V16HTTP):
    def test_http_completion_reaches_only_registered_native_pipe(self):
        pipe = 'LOCAL\\cc-msg-test-' + uuid.uuid4().hex
        server_script = r'''
$ErrorActionPreference='Stop'
$p=[System.IO.Pipes.NamedPipeServerStream]::new('PIPE_NAME',[System.IO.Pipes.PipeDirection]::In)
try {
 [Console]::Out.WriteLine('ready')
 $p.WaitForConnection()
 $r=[System.IO.StreamReader]::new($p)
 [Console]::Out.WriteLine($r.ReadLine())
 [Console]::Out.WriteLine($r.ReadLine())
} finally { $p.Dispose() }
'''.replace('PIPE_NAME', pipe)
        process = subprocess.Popen(['powershell', '-NoProfile', '-NonInteractive', '-Command', server_script],
                                   stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
                                   creationflags=subprocess.CREATE_NO_WINDOW)
        try:
            self.assertEqual(process.stdout.readline().strip(), 'ready')
            _, voice = self.add()
            q = self.backend.questions.create('native_http', 'native_session', ['r'])
            qid = q['question_id']
            self.server.question_id = qid
            self.server.close_after_answer = True
            env = {'CLAUDE_CODE_MESSAGING_SOCKET': '\\\\.\\pipe\\' + pipe,
                   'CLAUDE_CODE_MESSAGING_TOKEN': 'fake-own-child-test-token', 'CODEX_THREAD_ID': ''}
            with patch.dict(os.environ, env):
                register_environment(self.core, qid)
                status, raw, _ = self.request('/api/v16/answers', {
                    'question_id': qid, 'assignments': {'r': voice['project_voice_id']}})
            self.assertEqual(status, 200)
            self.assertEqual(json.loads(raw)['wake']['status'], 'sent_unconfirmed')
            stdout, stderr = process.communicate(timeout=10)
            self.assertEqual(process.returncode, 0, stderr)
            auth, event = map(json.loads, stdout.splitlines())
            self.assertEqual(auth, {'type': 'auth', 'token': env['CLAUDE_CODE_MESSAGING_TOKEN']})
            self.assertIn(qid, event['message']['content'])
            self.assertIn('not approval', event['message']['content'])
            self.assertEqual(self.backend.questions.read(qid)['status'], 'answered')
            self.assertNotIn(env['CLAUDE_CODE_MESSAGING_TOKEN'], raw.decode())
        finally:
            if process.poll() is None:
                process.kill()
                process.wait(timeout=5)
            process.stdout.close()
            process.stderr.close()
