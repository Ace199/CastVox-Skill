import json
import os
from pathlib import Path
import shutil
import subprocess
import unittest


@unittest.skipUnless(shutil.which('node'), 'Node is required for the Kimi transport contract test')
class KimiTransport(unittest.TestCase):
    def test_delivery_acknowledgement_target_and_unknown_disconnect(self):
        root = Path(__file__).resolve().parents[2]
        payload = {'url': 'ws://127.0.0.1:1981/control', 'token': 'test-secret',
                   'ws_module': str(root / 'tests/support/kimi_ws_stub.cjs'),
                   'agent_id': 'main', 'conversation_key': 'origin-chat', 'message': 'binding done'}
        for mode, status in [('accepted', 'queued'), ('wrong-target', 'unknown'),
                             ('disconnect', 'unknown'), ('rejected', 'failed')]:
            with self.subTest(mode=mode):
                result = subprocess.run([shutil.which('node'), str(root / 'scripts/kimi_work_control.cjs')],
                    input=json.dumps(payload).encode(), capture_output=True, timeout=5,
                    env={**os.environ, 'SM_KIMI_TRANSPORT_CASE': mode},
                    creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0)
                self.assertEqual(result.returncode, 0)
                self.assertEqual(json.loads(result.stdout)['status'], status)
                self.assertNotIn(b'test-secret', result.stdout + result.stderr)
