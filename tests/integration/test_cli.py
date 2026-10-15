import json
import os
import subprocess
import sys
import time
import unittest
from pathlib import Path

from makesound.storage import read_json
from tests.helpers import Fixture, ROOT, voice


class CLIIntegration(Fixture, unittest.TestCase):
    def test_CLI01_full_alias_default_resolve_rebind_snapshot_flow(self):
        a = self.dump("voice-a.json", voice("VOICE_A", "female"))
        b = self.dump("voice-b.json", voice("VOICE_B", "male"))
        settings = self.dump("settings.json", {"model": "fixture"})
        oldref = self.dump("old-ref.json", voice("VOICE_A", "female")["ref"])
        result = self.cli("voices", "aliases", "add", "女声音1", "--voice", a, "--project", self.a,
                          "--expected-revision", 0, "--set-default", "--settings", settings)
        self.assertEqual(result.returncode, 0, result.stdout)
        self.assertEqual(json.loads(result.stdout)["revision"], 1)
        result = self.cli("jobs", "snapshot", "--project", self.a)
        snap = json.loads(result.stdout)
        self.assertEqual(snap["status"], "snapshot_only")
        result = self.cli("voices", "aliases", "rebind", "女声音1", "--project", self.a, "--voice", b,
                          "--expected-revision", 1, "--expected-old-ref", oldref)
        self.assertEqual(result.returncode, 2)
        self.assertEqual(json.loads(result.stdout)["code"], "confirmation_required")
        result = self.cli("voices", "aliases", "rebind", "女声音1", "--project", self.a, "--voice", b,
                          "--expected-revision", 1, "--expected-old-ref", oldref, "--confirm")
        self.assertEqual(result.returncode, 0, result.stdout)
        result = self.cli("config", "resolve", "--project", self.a)
        self.assertEqual(json.loads(result.stdout)["bindings"][0]["voice"]["voice_id"], "VOICE_B")
        result = self.cli("jobs", "status", snap["job_id"])
        self.assertEqual(json.loads(result.stdout)["resolution"]["bindings"][0]["voice"]["voice_id"], "VOICE_A")

    def test_CLI01_doctor_is_readonly_and_redacts_good_bad_credentials(self):
        secret = "fixture-DO-NOT-DISCLOSE"
        for base in ("https://api.minimax.cn", "https://" + secret + "@api.minimax.cn?token=" + secret):
            self.dump("凭据/config.json", {"api_key": secret, "region": "cn", "base_url": base})
            before = self.loc.minimax_config.read_bytes()
            result = self.cli("doctor")
            payload = json.loads(result.stdout)
            self.assertNotIn(secret, result.stdout + result.stderr)
            self.assertEqual(self.loc.minimax_config.read_bytes(), before)
            self.assertFalse(self.loc.data_dir.exists())
            self.assertEqual(payload["network_calls"], 0)

    def test_CLI01_unknown_arg_and_invalid_json_do_not_echo_payload(self):
        result = self.cli("config", "resolve", "--private-fixture-secret", "DO-NOT-ECHO")
        self.assertEqual(result.returncode, 2)
        self.assertNotIn("DO-NOT-ECHO", result.stdout + result.stderr)
        p = self.root / "broken.json"
        p.write_text('{"private":"DO-NOT-ECHO"', encoding="utf-8")
        result = self.cli("config", "resolve", "--request", p)
        self.assertNotIn("DO-NOT-ECHO", result.stdout + result.stderr)
        self.assertEqual(json.loads(result.stdout)["code"], "invalid_json")

    def test_CLI01_no_default_is_nonzero_machine_readable(self):
        before = set(self.root.rglob("*"))
        result = self.cli("config", "resolve", "--project", self.a)
        self.assertEqual(result.returncode, 2)
        self.assertEqual(json.loads(result.stdout)["status"], "needs_setup")
        self.assertEqual(before, set(self.root.rglob("*")))

    def test_CLI01_official_voice_list_cannot_call_provider(self):
        result = self.cli("voices", "list", "--source", "official")
        self.assertEqual(result.returncode, 2)
        self.assertEqual(json.loads(result.stdout)["code"], "not_implemented")

    def test_IO01_two_processes_revision_collision_one_wins(self):
        self.configured()
        script = '''import json,sys
from pathlib import Path
from makesound.storage import Locations
from makesound.service import MakeSound
from makesound.errors import MakeSoundError
app=MakeSound(Locations(Path(sys.argv[1]),Path(sys.argv[2]),Path(sys.argv[3])),region='cn')
try:
 app.patch_settings({'export_mode':sys.argv[5]},1,sys.argv[4]); print('saved')
except MakeSoundError as exc: print(exc.code)
'''
        args = [str(self.loc.data_dir), str(self.loc.global_config), str(self.loc.minimax_config), str(self.a)]
        procs = [subprocess.Popen([sys.executable, "-c", script, *args, mode], cwd=ROOT, stdout=subprocess.PIPE,
                                  stderr=subprocess.PIPE, text=True, encoding="utf-8") for mode in ("whole", "sentence")]
        outputs = [p.communicate(timeout=20)[0].strip() for p in procs]
        self.assertCountEqual(outputs, ["saved", "revision_conflict"])
        self.assertEqual(read_json(self.a / ".makesound/preset.json")["revision"], 2)

    def test_IO01_process_crash_releases_os_lock(self):
        from makesound.storage import file_lock
        lock = self.root / "crash.lock"
        script = "from pathlib import Path; from makesound.storage import file_lock; import sys,time; ctx=file_lock(Path(sys.argv[1])); ctx.__enter__(); print('locked',flush=True); time.sleep(20)"
        proc = subprocess.Popen([sys.executable, "-c", script, str(lock)], cwd=ROOT,
                                stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        try:
            self.assertEqual(proc.stdout.readline().strip(), "locked")
        finally:
            proc.kill()
            proc.communicate(timeout=5)
        with file_lock(lock, timeout=.5):
            self.assertTrue(lock.exists())

    def test_cli_network_tripwire_is_active(self):
        env = dict(os.environ, MAKESOUND_TEST_NO_NETWORK="1", PYTHONPATH=str(ROOT / "tests/support"))
        script = "import socket; socket.create_connection(('127.0.0.1', 9))"
        out = subprocess.run([sys.executable, "-c", script], cwd=ROOT, env=env, capture_output=True, text=True, timeout=5)
        self.assertNotEqual(out.returncode, 0)
        self.assertIn("NETWORK_FORBIDDEN_IN_M1_TEST", out.stderr)

    def test_cli_schema_validation_and_non_destructive_migrate(self):
        old = self.dump("项目 A/.makesound/preset.json", {"schema_version": "1.1", "voice_id": "LEGACY", "model": "fixture"})
        before = old.read_bytes()
        result = self.cli("config", "migrate", "--project", self.a, "--region", "cn", "--confirm")
        self.assertEqual(result.returncode, 0, result.stdout)
        dest = json.loads(result.stdout)["output"]
        result = self.cli("schema", "validate", "--kind", "preset", "--file", dest)
        self.assertEqual(result.returncode, 0, result.stdout)
        self.assertEqual(old.read_bytes(), before)
