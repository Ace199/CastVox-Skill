import importlib.util
import json
from pathlib import Path
import unittest
from unittest.mock import patch


class WorkBuddyProbe(unittest.TestCase):
    def load_probe(self):
        path = Path(__file__).resolve().parents[2] / 'scripts/workbuddy_probe.py'
        self.assertTrue(path.is_file(), 'WorkBuddy environment probe is missing')
        spec = importlib.util.spec_from_file_location('workbuddy_probe', path)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module

    def test_reports_session_without_exposing_credentials_or_proxy_query(self):
        probe = self.load_probe()
        env = {
            'CODEBUDDY_SESSION_ID': 'test-origin-session',
            'CODEBUDDY_SERVICE_PROXY_URL': 'http://127.0.0.1:1234/internal/hooks/services/invoke?token=PRIVATE',
            'CODEBUDDY_AUTH_TOKEN': 'PRIVATE',
            'MINIMAX_API_KEY': 'PRIVATE',
        }
        result = probe.inspect_environment(env)
        self.assertEqual(result['session_id'], 'test-origin-session')
        self.assertEqual(result['service_proxy_origin'], 'http://127.0.0.1:1234')
        self.assertNotIn('PRIVATE', json.dumps(result))
        self.assertNotIn('MINIMAX_API_KEY', json.dumps(result))
        self.assertFalse(result['wake_verified'])

    def test_codex_environment_does_not_claim_workbuddy_ready(self):
        result = self.load_probe().inspect_environment({'CODEX_THREAD_ID': 'other-host'})
        self.assertEqual(result['status'], 'run_inside_workbuddy')
        self.assertIsNone(result['session_id'])

    def test_nonlocal_and_credential_urls_are_never_reported_as_usable(self):
        probe = self.load_probe()
        for url in ['https://example.com/invoke', 'http://user:PRIVATE@127.0.0.1:4/invoke',
                    'http://127.0.0.1:bad/invoke', 'not a URL']:
            result = probe.inspect_environment({'CODEBUDDY_SESSION_ID': 'own-session',
                                                'CODEBUDDY_SERVICE_PROXY_URL': url})
            self.assertIsNone(result['service_proxy_origin'])
            self.assertNotIn('PRIVATE', json.dumps(result))

    def test_probe_performs_no_network_or_synthesis(self):
        probe = self.load_probe()
        with patch('socket.socket', side_effect=AssertionError('No network allowed')):
            result = probe.inspect_environment({'CODEBUDDY_SESSION_ID': 'own-session'})
        self.assertEqual(result['status'], 'environment_captured')


if __name__ == '__main__':
    unittest.main()
