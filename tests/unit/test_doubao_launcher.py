import importlib
import unittest


class DoubaoLauncher(unittest.TestCase):
    def test_new_app_cannot_inherit_another_harness_identity(self):
        try:
            module = importlib.import_module('scripts.doubao_start_bridge')
        except ModuleNotFoundError:
            module = None
        self.assertIsNotNone(module, 'Clean Doubao launcher is missing')
        original = {'CODEX_THREAD_ID': 'other-chat', 'CLAUDE_CODE_MESSAGING_TOKEN': 'private',
                    'KIMI_AGENT_CLIENT_ID': 'kimiwork', 'WORKBUDDY_CONFIG_DIR': 'other',
                    'MCP_VM_CONVERSATION_ID': 'old-chat', 'DOUBAO_OFFICE_APP_ID': 'old-app',
                    'PATH': 'normal-path', 'SystemRoot': 'C:\\Windows'}
        cleaned = module.clean_environment(original)
        self.assertEqual(cleaned, {'PATH': 'normal-path', 'SystemRoot': 'C:\\Windows'})
        self.assertIn('CODEX_THREAD_ID', original)
