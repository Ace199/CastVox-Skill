import io
import json
import os
import unittest
from unittest.mock import patch

from makesound.errors import MakeSoundError
from tests.helpers import Fixture


class UILocale(unittest.TestCase):
    def test_normalize_supported_tags_and_reject_other_input(self):
        from makesound.ui_locale import normalize_ui_language
        for raw, expected in [('zh', 'zh-CN'), ('zh-Hant-TW', 'zh-CN'),
                              (' ZH_cn ', 'zh-CN'), ('en-US', 'en'), ('EN_gb', 'en'),
                              (None, None), ('fr-FR', None), ('english', None),
                              ('en-<script>', None), ('', None), (42, None)]:
            with self.subTest(raw=raw):
                self.assertEqual(normalize_ui_language(raw), expected)

    def test_explicit_priority_env_and_no_os_guess(self):
        from makesound.ui_locale import resolve_ui_language
        with patch.dict(os.environ, {'CASTVOX_UI_LANGUAGE': 'zh-TW', 'LANG': 'en_US'}, clear=True):
            self.assertEqual(resolve_ui_language('en-GB'), 'en')
            self.assertEqual(resolve_ui_language(), 'zh-CN')
            with self.assertRaises(MakeSoundError):
                resolve_ui_language('fr')
        for env in [{}, {'LANG': 'zh_CN', 'LC_ALL': 'zh_CN'}, {'CASTVOX_UI_LANGUAGE': 'unknown'}]:
            with patch.dict(os.environ, env, clear=True):
                self.assertIsNone(resolve_ui_language())


class SessionLocale(Fixture, unittest.TestCase):
    def test_cli_passes_override_to_detached_and_managed_launch(self):
        from makesound import studio_session
        for managed in (False, True):
            env = {'WORKBUDDY_CONFIG_DIR': 'fixture'} if managed else {}
            method = 'serve_managed' if managed else 'start'
            env['USERPROFILE'] = str(self.root)
            with patch.dict(os.environ, env, clear=True), patch('sys.argv', [
                    'studio_session', '--project', str(self.a), '--question', 'q_fixture',
                    '--ui-language', 'en-GB']), patch.object(studio_session, method, return_value={}) as launch, \
                    patch('sys.stdout', io.StringIO()):
                studio_session.main()
            self.assertEqual(launch.call_args.kwargs['ui_language'], 'en-GB')

    def test_live_session_language_mismatch_preserves_session(self):
        from makesound.core_v16 import ProjectCore
        from makesound.offline_harness import prepare
        from makesound.studio_session import start
        core = ProjectCore(self.a)
        qid = prepare(core, {'roles': ['r'], 'segments': [
            {'paragraph_id': 'p', 'sentence_id': 's', 'role_id': 'r', 'text': 'test'}]})['question_id']
        folder = core.managed_path(f'.makesound/studio/{qid}')
        folder.mkdir(parents=True)
        record = folder / 'session.json'
        saved = {'url': 'http://127.0.0.1:12345', 'question_id': qid, 'pid': 123,
                 'launch_identity': None, 'ui_language': 'zh-CN'}
        record.write_text(json.dumps(saved))
        module = ('export const session = Object.freeze(' + json.dumps(
            {'question_id': qid, 'ui_language': 'zh-CN'}) + ');').encode()
        with patch.dict(os.environ, {}, clear=True), patch('urllib.request.OpenerDirector.open',
                side_effect=lambda *a, **k: io.BytesIO(module)), patch('subprocess.Popen') as spawn:
            with self.assertRaises(MakeSoundError) as caught:
                start(core, qid, ui_language='en')
            self.assertEqual(caught.exception.code, 'ui_language_mismatch')
            self.assertEqual(start(core, qid, ui_language='zh-TW')['pid'], 123)
            self.assertEqual(start(core, qid)['pid'], 123)
            spawn.assert_not_called()
        self.assertEqual(json.loads(record.read_text()), saved)
