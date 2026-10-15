import json
import os
import socket
import subprocess
import sys
import tempfile
from pathlib import Path
from unittest.mock import patch

from makesound.service import MakeSound
from makesound.storage import Locations, atomic_write

ROOT = Path(__file__).resolve().parent.parent


def voice(vid="FAKE_VOICE_A", gender="unknown", kind="provider_voice"):
    if kind == "global_asset":
        return {"ref": {"kind": "global_asset", "asset_id": vid}, "voice_settings": {}}
    meta = {"gender": gender, "source": "fixture_user_confirmed"}
    return {"ref": {"kind": "provider_voice", "provider": "minimax", "region": "cn", "voice_id": vid},
            "voice_settings": {}, "metadata": meta}


def asset(label="测试资产", kind="clone"):
    return {"display_name": label, "source_type": kind, "provider": "minimax", "region": "cn",
            "voice_id": "FAKE_EXISTING_VOICE", "metadata": {"gender": "female", "source": "fixture_user_confirmed"}}


class Fixture:
    def setUp(self):
        scratch = ROOT / ".test-tmp"
        scratch.mkdir(exist_ok=True)
        # Keep all generated test data inside the authorized workspace.
        # Python 3.13's restricted tempfile ACLs cannot be used by this sandbox.
        import uuid
        self.temp_path = scratch / ("m1-" + uuid.uuid4().hex)
        self.temp_path.mkdir()
        import shutil
        def cleanup():
            target = self.temp_path.resolve()
            assert target.is_relative_to(scratch.resolve()) and target != scratch.resolve()
            shutil.rmtree(target)
        self.addCleanup(cleanup)
        self.root = self.temp_path
        self.a, self.b = self.root / "项目 A", self.root / "项目 B"
        self.a.mkdir()
        self.b.mkdir()
        self.loc = Locations(self.root / "用户数据", self.root / "全局/presets.json", self.root / "凭据/config.json")
        self.app = MakeSound(self.loc, region="cn")
        self.net = patch.object(socket.socket, "connect", side_effect=AssertionError("Network forbidden"))
        self.net.start()
        self.addCleanup(self.net.stop)

    def dump(self, name, obj):
        path = self.root / name
        atomic_write(path, obj)
        return path

    def configured(self, project=None, vid="FAKE_VOICE_A", gender="female"):
        return self.app.set_default(voice(vid, gender), {"model": "fixture-model"}, 0, project or self.a)

    def cli(self, *args):
        env = {k: v for k, v in os.environ.items() if not k.upper().startswith("MINIMAX")}
        env["MAKESOUND_TEST_NO_NETWORK"] = "1"
        env["PYTHONPATH"] = os.pathsep.join([str(ROOT / "tests/support"), str(ROOT)])
        command = [sys.executable, "-m", "makesound", *map(str, args), "--data-dir", str(self.loc.data_dir),
                   "--global-config", str(self.loc.global_config), "--minimax-config", str(self.loc.minimax_config), "--json"]
        return subprocess.run(command, cwd=ROOT, env=env, capture_output=True, encoding="utf-8", timeout=20)
