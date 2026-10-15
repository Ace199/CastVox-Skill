import copy
import json
import os
import stat
import unittest
from pathlib import Path
from unittest.mock import patch

from makesound import validation as v
from makesound.config_loader import load_minimax
from makesound.errors import MakeSoundError
from makesound.jobs import JobStore
from makesound.preset_store import for_project, legacy_view
from makesound.storage import JsonStore, atomic_write, project_id, project_root, read_json
from tests.helpers import Fixture, asset, voice


class M1Rules(Fixture, unittest.TestCase):
    def test_CFG01_no_default_readonly(self):
        before = set(self.root.rglob("*"))
        result = self.app.resolve(self.a)
        self.assertEqual(result["status"], "needs_setup")
        self.assertEqual(set(self.root.rglob("*")), before)

    def test_CFG02_direct_default_without_alias_and_restart(self):
        self.configured()
        obj = for_project(self.a).read()
        self.assertEqual(obj["named_voices"], {})
        from makesound.service import MakeSound
        self.assertEqual(MakeSound(self.loc, region="cn").resolve(self.a)["bindings"][0]["voice"]["voice_id"], "FAKE_VOICE_A")

    def test_CFG03_project_alias_isolation(self):
        self.app.alias("add", self.a, "女声音1", 0, voice=voice("FAKE_A", "female"))
        self.app.alias("add", self.b, "女声音1", 0, voice=voice("FAKE_B", "female"))
        for root, expected in [(self.a, "FAKE_A"), (self.b, "FAKE_B")]:
            result = self.app.resolve(root, {"voice_alias": "女声音1", "project_settings": {"model": "fixture"}})
            self.assertEqual(result["bindings"][0]["voice"]["voice_id"], expected)

    def test_CFG04_rebind_requires_confirmation_old_ref_and_revision(self):
        self.app.alias("add", self.a, "女声音1", 0, voice=voice())
        for kwargs, revision, code in [({}, 1, "confirmation_required"),
                                       ({"confirmed": True, "expected_old": voice()["ref"]}, 0, "revision_conflict"),
                                       ({"confirmed": True, "expected_old": voice("WRONG")["ref"]}, 1, "reference_conflict")]:
            with self.assertRaises(MakeSoundError) as cm:
                self.app.alias("rebind", self.a, "女声音1", revision, voice=voice("FAKE_B"), **kwargs)
            self.assertEqual(cm.exception.code, code)

    def test_CFG05_snapshot_is_frozen_after_rebind(self):
        self.app.alias("add", self.a, "女声音1", 0, voice=voice(), set_default=True, settings={"model": "fixture"})
        frozen = self.app.snapshot(self.a)
        self.app.alias("rebind", self.a, "女声音1", 1, voice=voice("FAKE_B"), confirmed=True, expected_old=voice()["ref"])
        self.assertEqual(self.app.resolve(self.a)["bindings"][0]["voice"]["voice_id"], "FAKE_B")
        self.assertEqual(self.app.jobs.load(frozen["job_id"])["resolution"]["bindings"][0]["voice"]["voice_id"], "FAKE_VOICE_A")
        with self.assertRaises(MakeSoundError):
            self.app.jobs.create(self.app.resolve(self.a), job_id=frozen["job_id"])

    def test_CFG06_sample_delete_does_not_delete_id_or_references(self):
        sample = self.root / "fake.wav"
        sample.write_bytes(b"FAKE-NOT-A-REAL-RECORDING")
        _, item = self.app.register_asset(asset(), sample)
        managed = Path(item["sample"]["managed_path"])
        self.app.set_default(voice(item["asset_id"], kind="global_asset"), {"model": "fixture"}, 0, self.a)
        self.app.sample_delete(item["asset_id"], True)
        self.assertFalse(managed.exists())
        self.assertTrue(sample.exists())
        self.assertEqual(self.app.resolve(self.a)["bindings"][0]["voice"]["voice_id"], "FAKE_EXISTING_VOICE")
        self.assertTrue(self.app.asset_references(item["asset_id"]))
        with self.assertRaises(MakeSoundError) as cm:
            self.app.delete_asset(item["asset_id"], 2, confirmed=True, known_projects_confirmed=True)
        self.assertEqual(cm.exception.code, "referenced")

    def test_CFG07_global_unique_asset_name_and_source(self):
        _, one = self.app.register_asset(asset("café"))
        with self.assertRaises(MakeSoundError):
            self.app.register_asset(asset("cafe\u0301", "design"))
        _, two = self.app.register_asset(asset("设计资产", "design"))
        self.assertNotEqual(one["asset_id"], two["asset_id"])
        self.assertEqual(two["source_type"], "design")
        self.assertEqual(two["registration"], "local_existing_id")

    def test_CFG08_constraints_do_not_fall_back_to_wrong_default(self):
        self.configured(gender="male")
        result = self.app.resolve(self.a, {"constraints": {"gender": "female"}})
        self.assertEqual(result["status"], "needs_studio")
        self.assertEqual(result["bindings"], [])

    def test_CFG09_missing_alias_requests_studio_and_male_filter(self):
        self.configured()
        result = self.app.resolve(self.a, {"voice_alias": "男声音1"})
        self.assertEqual(result["status"], "needs_studio")
        self.assertEqual(result["missing_alias"], "男声音1")
        self.assertEqual(result["filters"], {"gender": "male"})

    def test_CFG10_applied_studio_final_selection_and_transaction_match(self):
        self.configured()
        self.app.alias("add", self.a, "女声音1", 1, voice=voice("EXPLICIT", "female"))
        request = {"job_id": "job_fixture", "voice_alias": "女声音1", "constraints": {"gender": "female"},
                   "studio_submission": {"status": "applied", "question_id": "q1", "answer_id": "a1", "job_id": "job_fixture",
                                         "project_id": project_id(self.a), "voice": voice("STUDIO_MALE", "male"), "clear_constraints": True}}
        result = self.app.resolve(self.a, request)
        self.assertEqual(result["bindings"][0]["voice"]["voice_id"], "STUDIO_MALE")
        request["studio_submission"]["project_id"] = project_id(self.b)
        with self.assertRaises(MakeSoundError):
            self.app.resolve(self.a, request)

    def test_pending_studio_never_becomes_ready(self):
        self.configured()
        for status in ("pending", "cancelled", "expired"):
            self.assertEqual(self.app.resolve(self.a, {"studio_submission": {"status": status}})["status"], "needs_studio")

    def test_CFG11_voice_and_project_settings_are_independent(self):
        self.configured()
        self.app.patch_settings({"export_mode": "sentence", "subtitle_enabled": False}, 1, self.a)
        self.app.alias("add", self.a, "男声音1", 2, voice=voice("MALE", "male"))
        result = self.app.resolve(self.a, {"voice_alias": "男声音1", "voice_settings": {"speed": 1.2}})
        self.assertEqual(result["project_settings"]["export_mode"], "sentence")
        self.assertFalse(result["project_settings"]["subtitle_enabled"])
        self.assertEqual(result["bindings"][0]["voice"]["voice_settings"]["speed"], 1.2)
        self.assertEqual(for_project(self.a).read()["default_voice"]["ref"]["voice_id"], "FAKE_VOICE_A")

    def test_global_fallback_and_project_override_field_merge(self):
        self.app.set_default(voice("GLOBAL"), {"model": "fixture", "pause": {"sentence_ms": 200}}, 0)
        self.assertEqual(self.app.resolve(self.a)["bindings"][0]["source"], "global_default")
        self.app.patch_settings({"pause": {"paragraph_ms": 900}}, 0, self.a)
        result = self.app.resolve(self.a)
        self.assertEqual(result["project_settings"]["pause"], {"sentence_ms": 200, "paragraph_ms": 900})
        self.app.set_default(voice("PROJECT"), {}, 1, self.a)
        self.assertEqual(self.app.resolve(self.a)["bindings"][0]["source"], "project_default")

    def test_second_paragraph_alias_binding_without_audio(self):
        self.configured()
        self.app.alias("add", self.a, "男声音1", 1, voice=voice("VOICE_B", "male"))
        result = self.app.resolve(self.a, {"assignments": [{"target": "p001"}, {"target": "p002", "voice_alias": "男声音1"}]})
        self.assertEqual([b["voice"]["voice_id"] for b in result["bindings"]], ["FAKE_VOICE_A", "VOICE_B"])

    def test_CFG17_no_implicit_project_and_no_relative_root(self):
        self.assertEqual(self.app.resolve()["status"], "needs_setup")
        for path in (None, Path("relative"), Path.home(), self.root / "missing"):
            with self.assertRaises(MakeSoundError):
                project_root(path)

    def test_CFG18_legacy_readonly_and_non_destructive_migration(self):
        path = self.a / ".makesound/preset.json"
        old = {"schema_version": "1.1", "preset_name": "Legacy", "provider": "minimax", "model": "fixture", "voice_id": "LEGACY",
               "voice": {"speed": 1.3}, "export": {"mode": "sentence", "subtitle_enabled": True}, "future_field": {"retain": 1}}
        atomic_write(path, old)
        before = path.read_bytes()
        result = self.app.resolve(self.a)
        self.assertEqual(result["bindings"][0]["voice"]["voice_id"], "LEGACY")
        self.assertEqual(result["project_settings"]["export_mode"], "sentence")
        with self.assertRaises(MakeSoundError):
            self.app.patch_settings({"export_mode": "paragraph"}, 0, self.a)
        exported = for_project(self.a, "cn").export_migration("cn")
        self.assertEqual(path.read_bytes(), before)
        self.assertEqual(read_json(Path(exported["backup"])), old)
        migrated = read_json(Path(exported["output"]))
        self.assertEqual(migrated["compatibility"]["original"]["future_field"], {"retain": 1})
        self.assertEqual(migrated["project_settings"]["model"], "fixture")
        with self.assertRaises(MakeSoundError):
            legacy_view(old, None)

    def test_invalid_schema_and_unknown_fields_are_not_ignored(self):
        initial = for_project(self.a).read()
        for change in ({"schema_version": "9"}, {"session_preference": {}}, {"revision": True}):
            obj = copy.deepcopy(initial)
            obj.update(change)
            atomic_write(self.a / ".makesound/preset.json", obj)
            with self.assertRaises(MakeSoundError):
                self.app.resolve(self.a)

    def test_nonobject_request_is_rejected_even_when_empty(self):
        for request in ([], False, ""):
            with self.assertRaises(MakeSoundError):
                self.app.resolve(self.a, request)

    def test_alias_rename_updates_default_and_referenced_remove_is_blocked(self):
        self.app.alias("add", self.a, "旧名", 0, voice=voice(), set_default=True)
        self.app.alias("rename", self.a, "旧名", 1, new_name="新名")
        self.assertEqual(for_project(self.a).read()["default_voice"]["ref"]["name"], "新名")
        with self.assertRaises(MakeSoundError):
            self.app.alias("remove", self.a, "新名", 2)

    def test_unknown_gender_is_not_a_verified_match(self):
        self.configured(gender="unknown")
        self.assertEqual(self.app.resolve(self.a, {"constraints": {"gender": "female"}})["status"], "needs_studio")
        with self.assertRaises(MakeSoundError):
            v.metadata({"gender": "female"})

    def test_explicit_voice_without_model_does_not_use_suggested_model(self):
        result = self.app.resolve(self.a, {"voice": voice()})
        self.assertEqual(result["status"], "needs_setup")
        self.assertEqual(result["missing_fields"], ["model"])

    def test_alias_add_and_default_save_are_one_atomic_update(self):
        path = self.a / ".makesound/preset.json"
        with patch("makesound.storage.os.replace", side_effect=PermissionError()):
            with self.assertRaises(MakeSoundError):
                self.app.alias("add", self.a, "合并保存", 0, voice=voice(), set_default=True)
        self.assertFalse(path.exists())
        self.app.alias("add", self.a, "合并保存", 0, voice=voice(), set_default=True)
        obj = for_project(self.a).read()
        self.assertEqual(obj["revision"], 1)
        self.assertIn("合并保存", obj["named_voices"])
        self.assertEqual(obj["default_voice"]["ref"], {"kind": "project_alias", "name": "合并保存"})

    def test_asset_rename_revision_and_unreferenced_delete(self):
        _, a = self.app.register_asset(asset("资产一"))
        _, b = self.app.register_asset(asset("资产二", "design"))
        with self.assertRaises(MakeSoundError):
            self.app.registry.rename(a["asset_id"], "资产二", 2)
        with self.assertRaises(MakeSoundError):
            self.app.registry.rename(a["asset_id"], "新名字", 1)
        self.app.registry.rename(a["asset_id"], "新名字", 2)
        self.app.delete_asset(b["asset_id"], 3, confirmed=True, known_projects_confirmed=True)
        obj = self.app.registry.read()
        self.assertEqual(obj["assets"][a["asset_id"]]["display_name"], "新名字")
        self.assertNotIn(b["asset_id"], obj["assets"])

    def test_global_asset_shared_by_two_projects_and_sample_not_duplicated(self):
        _, a = self.app.register_asset(asset())
        item = voice(a["asset_id"], kind="global_asset")
        for root in (self.a, self.b):
            self.app.alias("add", root, "同名音色", 0, voice=item, set_default=True, settings={"model": "fixture"})
        self.assertEqual(len(self.app.registry.read()["assets"]), 1)
        self.assertEqual(len(self.app.asset_references(a["asset_id"])), 2)

    def test_global_only_resolution_does_not_write_project(self):
        self.app.set_default(voice("GLOBAL"), {"model": "fixture"}, 0)
        self.assertEqual(self.app.resolve()["status"], "ready")
        self.assertFalse((self.a / ".makesound").exists())

    def test_invalid_voice_ranges_and_bool_rejected(self):
        for values in ({"speed": True}, {"speed": .49}, {"volume": 0}, {"pitch": 13}, {"speed": float("nan")}, {"tts_secret": "bad"}):
            with self.assertRaises(MakeSoundError):
                v.voice_settings(values)

    def test_expired_asset_blocks_resolution(self):
        item = asset()
        item["availability"] = "expired"
        _, registered = self.app.register_asset(item)
        self.app.set_default(voice(registered["asset_id"], kind="global_asset"), {"model": "fixture"}, 0, self.a)
        self.assertEqual(self.app.resolve(self.a)["reason"], "voice_unavailable")

    def test_asset_deletion_checks_job_and_requires_inventory_acknowledgment(self):
        _, registered = self.app.register_asset(asset())
        aid = registered["asset_id"]
        with self.assertRaises(MakeSoundError):
            self.app.delete_asset(aid, 1, confirmed=True)
        self.app.snapshot(self.a, {"voice": voice(aid, kind="global_asset"), "project_settings": {"model": "fixture"}})
        with self.assertRaises(MakeSoundError) as cm:
            self.app.delete_asset(aid, 1, confirmed=True, known_projects_confirmed=True)
        self.assertEqual(cm.exception.code, "referenced")

    def test_snapshot_corruption_detected(self):
        self.configured()
        snap = self.app.snapshot(self.a)
        path = self.loc.data_dir / "jobs" / snap["job_id"] / "snapshot.json"
        raw = read_json(path)
        raw["resolution"]["bindings"][0]["voice"]["voice_id"] = "CHANGED"
        atomic_write(path, raw)
        with self.assertRaises(MakeSoundError) as cm:
            self.app.jobs.load(snap["job_id"])
        self.assertEqual(cm.exception.code, "snapshot_corrupt")

    def test_sensitive_metadata_and_url_values_rejected(self):
        for val in ({"nested": [{"Authorization": "hidden"}]}, {"message": "Bearer fixture-secret-value"}):
            item = asset()
            item["consent"] = val
            with self.assertRaises(MakeSoundError):
                self.app.register_asset(item)


class StorageAndCredentials(Fixture, unittest.TestCase):
    def test_credential_path_cannot_be_a_business_store(self):
        from makesound.service import MakeSound
        from makesound.storage import Locations
        with self.assertRaises(MakeSoundError) as cm:
            MakeSound(Locations(self.loc.data_dir, self.loc.minimax_config, self.loc.minimax_config))
        self.assertEqual(cm.exception.code, "protected_credentials")

    def test_empty_and_nonobject_credentials_are_not_accepted(self):
        for value in ({}, [], {"api_key": "fake", "base_url": "https://api.minimax.cn"}):
            path = self.dump("invalid-config.json", value)
            before = path.read_bytes()
            with self.assertRaises(MakeSoundError):
                load_minimax(path, {})
            self.assertEqual(path.read_bytes(), before)
    def test_REGION01_valid_loader_is_readonly_and_secret_repr_hidden(self):
        p = self.dump("config.json", {"api_key": "fixture-private-value", "region": "cn", "base_url": "https://api.minimax.cn", "extra": {"do_not_modify": 1}})
        before = p.read_bytes()
        conf = load_minimax(p, {})
        self.assertNotIn("fixture-private-value", repr(conf))
        self.assertNotIn("fixture-private-value", json.dumps(conf.summary()))
        self.assertEqual(p.read_bytes(), before)
        other = load_minimax(p, {"MINIMAX_REGION": "international", "MINIMAX_BASE_URL": "https://api.minimax.io"})
        self.assertEqual(other.region, "international")

    def test_REGION01_invalid_regions_and_credential_urls_are_safe(self):
        for changes, expected in [({"region": "international"}, "region_mismatch"),
                                   ({"base_url": "https://user:private@api.minimax.cn?token=hidden"}, "invalid_base_url"),
                                   ({"base_url": "https://api.minimax.cn/v1"}, "invalid_base_url"),
                                   ({"region": "unknown"}, "invalid_region")]:
            obj = {"api_key": "private", "region": "cn", "base_url": "https://api.minimax.cn", **changes}
            p = self.dump("config.json", obj)
            with self.assertRaises(MakeSoundError) as cm:
                load_minimax(p, {})
            self.assertEqual(cm.exception.code, expected)
            self.assertNotIn("private", str(cm.exception))

    def test_REGION01_cross_region_voice_and_configured_missing_region(self):
        item = voice()
        item["ref"]["region"] = "international"
        with self.assertRaises(MakeSoundError):
            self.app.set_default(item, {}, 0, self.a)
        item["ref"]["region"] = "configured"
        self.app.set_default(item, {"model": "fixture"}, 0, self.a)
        from makesound.service import MakeSound
        self.assertEqual(MakeSound(self.loc).resolve(self.a)["reason"], "region_required")

    def test_IO01_replace_failure_preserves_previous_file_and_cleans_temp(self):
        self.configured()
        p = self.a / ".makesound/preset.json"
        before = p.read_bytes()
        with patch("makesound.storage.os.replace", side_effect=PermissionError("fake sensitive path")):
            with self.assertRaises(MakeSoundError):
                self.app.patch_settings({"export_mode": "whole"}, 1, self.a)
        self.assertEqual(p.read_bytes(), before)
        self.assertEqual(list(p.parent.glob(".makesound-*.tmp")), [])

    def test_IO01_readonly_file(self):
        self.configured()
        p = self.a / ".makesound/preset.json"
        p.chmod(stat.S_IREAD)
        try:
            with self.assertRaises(MakeSoundError):
                self.app.patch_settings({"export_mode": "whole"}, 1, self.a)
        finally:
            p.chmod(stat.S_IWRITE | stat.S_IREAD)

    def test_IO01_duplicate_json_and_nan_are_rejected(self):
        p = self.root / "bad.json"
        for text in ('{"revision":0,"revision":1}', '{"x":NaN}'):
            p.write_text(text)
            with self.assertRaises(MakeSoundError):
                read_json(p)

    def test_IO01_missing_reads_do_not_create_directories(self):
        self.app.registry.read()
        self.app.global_preset.read()
        self.assertFalse(self.loc.data_dir.exists())
        self.assertFalse(self.loc.global_config.parent.exists())

    def test_sample_delete_cannot_escape_managed_directory(self):
        p = self.root / "original.wav"
        p.write_bytes(b"fake")
        _, item = self.app.register_asset(asset(), p)
        state = self.app.registry.read()
        state["assets"][item["asset_id"]]["sample"]["managed_path"] = str(p)
        atomic_write(self.app.registry.store.path, state)
        with self.assertRaises(MakeSoundError):
            self.app.sample_delete(item["asset_id"], True)
        self.assertTrue(p.exists())
