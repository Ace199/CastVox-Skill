"""Claude App mode checks must not discover or borrow another chat's identity."""
import contextlib
import io
import json
import os
import runpy
import sys
import unittest
from unittest.mock import patch
from tests.helpers import ROOT


class ClaudeAppConnection(unittest.TestCase):
    def check(self, surface, env):
        from makesound.claude_native import connection_status
        with patch.dict(os.environ, env, clear=True):
            return connection_status(surface)

    def test_code_reports_inherited_transport_without_exposing_identity(self):
        address = r'\\.\pipe\LOCAL\cc-msg-private-session'
        env = {'CLAUDE_CODE_MESSAGING_SOCKET': address,
               'CLAUDE_CODE_MESSAGING_TOKEN': 'private-token'}
        with patch('makesound.claude_native.os.name', 'nt'):
            result = self.check('code', env)
        self.assertEqual(result['status'], 'available')
        self.assertFalse(result['receiver_verified'])
        self.assertEqual(result['transport'], 'named_pipe')
        serialized = json.dumps(result)
        for secret in (address, 'private-token', 'token_fingerprint'):
            self.assertNotIn(secret, serialized)

    def test_absent_partial_and_invalid_environment_fail_without_search(self):
        for env, code in (({}, 'harness_unavailable'),
                          ({'CLAUDE_CODE_MESSAGING_TOKEN': 'private-token'}, 'harness_unavailable'),
                          ({'CLAUDE_CODE_MESSAGING_TOKEN': 'private-token',
                            'CLAUDE_CODE_MESSAGING_SOCKET': 'https://example.invalid'}, 'invalid_target')):
            with self.subTest(code=code), patch('makesound.claude_native.os.name', 'nt'):
                result = self.check('code', env)
                self.assertEqual(result['status'], 'unavailable')
                self.assertEqual(result['code'], code)
                self.assertNotIn('private-token', json.dumps(result))

    def test_chat_does_not_inherit_code_capability(self):
        from makesound.claude_native import connection_status
        for surface in ('chat',):
            with self.subTest(surface=surface), patch('makesound.claude_native.environment_target',
                    side_effect=AssertionError('Must not probe Code for another surface')):
                result = connection_status(surface)
            self.assertEqual(result['status'], 'unsupported_surface')
            self.assertFalse(result['receiver_verified'])

    def test_cowork_requires_actual_inherited_transport(self):
        self.assertEqual(self.check('cowork', {})['status'], 'unavailable')
        env = {'CLAUDE_CODE_MESSAGING_SOCKET': r'\\.\pipe\LOCAL\cc-msg-cowork-own',
               'CLAUDE_CODE_MESSAGING_TOKEN': 'private-cowork-token'}
        with patch('makesound.claude_native.os.name', 'nt'):
            result = self.check('cowork', env)
        self.assertEqual(result['status'], 'available')
        self.assertFalse(result['receiver_verified'])

    def test_cowork_reports_fallback_as_distinct_from_native_support(self):
        result = self.check('cowork', {})
        self.assertEqual(result['status'], 'unavailable')
        self.assertEqual(result['alternative_transport'], 'pending_tool_result')
        self.assertTrue(result['requires_pending_tool_call'])
        self.assertFalse(result['receiver_verified'])

    def test_cli_is_json_and_returns_nonzero_if_connection_is_unavailable(self):
        from makesound.claude_native import main
        output = io.StringIO()
        with patch.dict(os.environ, {}, clear=True), contextlib.redirect_stdout(output):
            code = main(['--surface', 'code'])
        self.assertEqual(code, 2)
        self.assertEqual(json.loads(output.getvalue())['status'], 'unavailable')


class ClaudeSmokePreflight(unittest.TestCase):
    def test_old_python_stops_before_runtime_imports_and_project_creation(self):
        import builtins
        original = builtins.__import__
        def checked_import(name, *args, **kwargs):
            if name.startswith('makesound'):
                raise AssertionError('Unsupported Python must stop before runtime imports')
            return original(name, *args, **kwargs)
        output = io.StringIO()
        with patch.object(sys, 'version_info', (3, 10, 12)), patch('builtins.__import__', checked_import), \
                contextlib.redirect_stdout(output), self.assertRaises(SystemExit) as stopped:
            runpy.run_path(str(ROOT / 'scripts/claude_binding_smoke.py'), run_name='__main__')
        self.assertEqual(stopped.exception.code, 2)
        self.assertEqual(json.loads(output.getvalue())['code'], 'python_unsupported')


if __name__ == '__main__':
    unittest.main()
