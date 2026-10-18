"""Offline macOS setup branch checks; actual macOS smoke checks are marked."""
import contextlib
import io
import json
import os
from pathlib import Path
import runpy
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

from tests.helpers import Fixture, ROOT
from makesound.media import MediaTools
from studio_config_editor import launch_editor, open_config


class MacOSSetup(Fixture, unittest.TestCase):
    def test_macos_opens_json_in_text_editor_without_shell_or_rewriting(self):
        path = self.root / '中文 空格配置.json'
        path.write_text('{"models":[]}', encoding='utf-8')
        with patch('studio_config_editor.sys.platform', 'darwin'), \
                patch('studio_config_editor.subprocess.run') as run:
            launch_editor(path)
        run.assert_called_once_with(['/usr/bin/open', '-t', str(path.resolve())],
                                    check=True, capture_output=True, timeout=10)
        self.assertEqual(path.read_text(encoding='utf-8'), '{"models":[]}')

    def test_macos_editor_failure_is_reported_without_disclosing_details(self):
        with patch('studio_config_editor.sys.platform', 'darwin'), \
                patch('studio_config_editor.subprocess.run', side_effect=subprocess.CalledProcessError(
                    1, ['/usr/bin/open'], stderr=b'PRIVATE_VALUE')):
            result = open_config('minimax', self.root)
        self.assertFalse(result['ok'])
        self.assertTrue(result['created'])
        self.assertNotIn('PRIVATE_VALUE', json.dumps(result))
        self.assertTrue((self.root / 'minimax/config.json').exists())

    def test_macos_editor_timeout_retains_existing_file(self):
        path = self.root / 'minimax/config.json'
        path.parent.mkdir()
        original = b'{"custom":"original"}\n'
        path.write_bytes(original)
        with patch('studio_config_editor.sys.platform', 'darwin'), \
                patch('studio_config_editor.subprocess.run', side_effect=subprocess.TimeoutExpired('open', 10)):
            result = open_config('minimax', self.root)
        self.assertFalse(result['ok'])
        self.assertFalse(result['created'])
        self.assertEqual(path.read_bytes(), original)

    def pair(self, name):
        folder = self.root / name
        folder.mkdir()
        for binary in ('ffmpeg', 'ffprobe'):
            path = folder / binary
            path.write_bytes(b'local-tool')
            path.chmod(0o755)
        return folder

    def test_macos_reuses_existing_pair_with_restricted_path(self):
        pair = self.pair('homebrew bin')
        with patch('makesound.media.sys.platform', 'darwin'), \
                patch('makesound.media.shutil.which', return_value=None), \
                patch('makesound.media._macos_media_dirs', return_value=(self.root / 'missing', pair)), \
                patch('makesound.media.subprocess.run', side_effect=AssertionError('Discovery must not run or install tools')):
            media = MediaTools()
        self.assertEqual(media.ffmpeg, str(pair / 'ffmpeg'))
        self.assertEqual(media.ffprobe, str(pair / 'ffprobe'))
        self.assertTrue(media.available)

    def test_macos_path_pair_and_explicit_paths_take_precedence(self):
        pair = self.pair('existing')
        with patch('makesound.media.sys.platform', 'darwin'), \
                patch('makesound.media.shutil.which', side_effect=lambda name: str(pair / name)), \
                patch('makesound.media._macos_media_dirs', side_effect=AssertionError('Already found')):
            self.assertTrue(MediaTools().available)
        with patch('makesound.media.sys.platform', 'darwin'), \
                patch('makesound.media._macos_media_dirs', side_effect=AssertionError('Explicit override')):
            media = MediaTools(ffmpeg='explicit-absent', ffprobe='explicit-absent')
        self.assertFalse(media.available)

    def test_incomplete_macos_pair_keeps_wav_fallback(self):
        pair = self.pair('incomplete')
        (pair / 'ffprobe').unlink()
        with patch('makesound.media.sys.platform', 'darwin'), \
                patch('makesound.media.shutil.which', return_value=None), \
                patch('makesound.media._macos_media_dirs', return_value=(pair,)):
            media = MediaTools()
        self.assertFalse(media.available)

    @unittest.skipUnless(os.name == 'posix', 'Native POSIX executable permission check')
    def test_macos_non_executable_pair_is_ignored(self):
        pair = self.pair('non executable')
        (pair / 'ffprobe').chmod(0o644)
        with patch('makesound.media.sys.platform', 'darwin'), \
                patch('makesound.media.shutil.which', return_value=None), \
                patch('makesound.media._macos_media_dirs', return_value=(pair,)):
            self.assertFalse(MediaTools().available)

    def test_media_check_reports_interpreter_and_rejects_old_python(self):
        from makesound.media import main
        out = io.StringIO()
        with patch('makesound.media.sys.version_info', (3, 10, 0)), contextlib.redirect_stdout(out):
            status = main()
        result = json.loads(out.getvalue())
        self.assertEqual(status, 2)
        self.assertEqual(result['status'], 'python_unsupported')
        self.assertEqual(result['python_executable'], sys.executable)
        self.assertFalse(result['python_supported'])

    def test_locator_reports_old_interpreter_without_searching(self):
        out = io.StringIO()
        with patch('sys.version_info', (3, 10, 0)), patch('sys.argv', ['runtime_location.py']), \
                contextlib.redirect_stdout(out), self.assertRaises(SystemExit) as caught:
            runpy.run_path(str(ROOT / 'skills/soundmaker-dubbing/scripts/runtime_location.py'), run_name='__main__')
        self.assertEqual(caught.exception.code, 2)
        self.assertEqual(json.loads(out.getvalue())['code'], 'python_unsupported')


class MacOSNativeSmoke(unittest.TestCase):
    """Run on a real Mac in CI; never launch editors or call voice providers."""

    @unittest.skipUnless(os.name == 'posix', 'Native POSIX filesystem check')
    def test_skill_symlink_and_posix_lock(self):
        from makesound.storage import file_lock
        base = ROOT / '.test-tmp'
        base.mkdir(exist_ok=True)
        with tempfile.TemporaryDirectory(dir=base) as temporary:
            folder = Path(temporary)
            link = folder / 'linked skill'
            link.symlink_to(ROOT / 'skills/soundmaker-dubbing', target_is_directory=True)
            locate = runpy.run_path(str(link / 'scripts/runtime_location.py'))['locate']
            self.assertEqual(locate(link), ROOT.resolve())
            with file_lock(folder / 'state.lock'):
                (folder / 'state.json').write_text('{}', encoding='utf-8')
            with file_lock(folder / 'state.lock'):
                self.assertEqual((folder / 'state.json').read_text(encoding='utf-8'), '{}')

    @unittest.skipUnless(sys.platform == 'darwin', 'Real macOS process and loopback smoke')
    def test_background_studio_starts_with_posix_options_and_stops(self):
        import urllib.request
        from makesound.core_v16 import ProjectCore
        from makesound.studio_session import start
        base = ROOT / '.test-tmp'
        base.mkdir(exist_ok=True)
        children = []
        original_popen = subprocess.Popen

        def track(args, **kwargs):
            self.assertTrue(kwargs.get('start_new_session'))
            self.assertNotIn('creationflags', kwargs)
            child = original_popen(args, **kwargs)
            children.append(child)
            return child

        with tempfile.TemporaryDirectory(dir=base) as temporary:
            try:
                with patch.dict(os.environ, {}, clear=True), \
                        patch('makesound.studio_session.subprocess.Popen', side_effect=track):
                    core = ProjectCore(Path(temporary))
                    ready = start(core, ui_language='en')
                    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
                    with opener.open(ready['url'] + '/js/session.js', timeout=5) as response:
                        module = response.read().decode('utf-8')
                    self.assertIn(core.read()['project_id'], module)
                    self.assertEqual(ready['mode'], 'management')
            finally:
                for child in children:
                    if child.poll() is None:
                        child.terminate()
                    child.wait(timeout=5)


if __name__ == '__main__':
    unittest.main()
