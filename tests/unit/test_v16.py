import copy
import json
import socket
import unittest
from concurrent.futures import ThreadPoolExecutor
from unittest.mock import patch

from makesound.core_v16 import ProjectCore
from makesound.errors import MakeSoundError
from makesound.generation import Generation
from makesound.providers import FakeProvider, duration, effective
from makesound.questions import Questions
from makesound.storage import atomic_write, read_json
from tests.helpers import Fixture, voice


SOURCE = {"provider": "fake", "region": "test", "model": "fake-v1", "voice_id": "fake-original"}


class V16(Fixture, unittest.TestCase):
    def setUp(self):
        super().setUp()
        self.core = ProjectCore(self.a)
        self.fake = FakeProvider()
        self.engine = Generation(self.core, self.fake)
        self.vid = self.add("旁白", "male")

    def add(self, name, category="other", source=None):
        return self.core.add_voice(name, category, source or SOURCE, self.core.read()["revision"])[1]

    def edit(self, patch, vid=None):
        return self.core.edit_voice(vid or self.vid, patch, self.core.read()["revision"])

    def defaults(self, **values):
        return self.core.save_defaults(values, self.core.read()["revision"])

    def segments(self, durations=(6,), voices=None):
        return [{"paragraph_id": "p1", "sentence_id": f"s{i}", "text": f" 原文 V1.6，句子{i}。[停顿] ",
                 "project_voice_id": (voices or [self.vid] * len(durations))[i], "fake_duration_seconds": seconds}
                for i, seconds in enumerate(durations)]

    def freeze(self, durations=(6,), voices=None):
        return self.engine.freeze(self.segments(durations, voices), confirmed=True, authorized=True)

    def run_job(self, durations=(6,), voices=None):
        snap = self.freeze(durations, voices)
        return snap, self.engine.run(snap["job_id"])

    def error(self, code, call):
        with self.assertRaises(MakeSoundError) as cm:
            call()
        self.assertEqual(cm.exception.code, code)

    def test_A_identity_source_readonly_duplicates_and_soft_delete(self):
        second = self.add("同源二")
        self.assertNotEqual(second, self.vid)
        self.edit({"name": "新名", "category": "female", "settings": {"speed": 1.2, "pitch": 2}})
        self.assertEqual(self.core.read()["voices"][self.vid]["source"], SOURCE)
        self.error("invalid_data", lambda: self.edit({"source": {**SOURCE, "model": "other"}}))
        self.defaults(general=self.vid)
        self.edit({"deleted": True})
        obj = self.core.read()
        self.assertTrue(obj["voices"][self.vid]["deleted"])
        self.assertEqual(obj["defaults"]["general"], self.vid)

    def test_A_normalized_name_uniqueness_undo_conflict(self):
        self.add("café")
        self.error("name_conflict", lambda: self.add("cafe\u0301"))
        self.edit({"deleted": True})
        self.add("旁白")
        self.error("name_conflict", lambda: self.edit({"deleted": False}))
        self.edit({"name": "恢复", "deleted": False})

    def test_B_order_no_gender_inference_and_empty_defaults(self):
        female = self.add("女声", "female")
        self.assertEqual(self.core.resolve()["status"], "needs_question")
        self.defaults(general=self.vid, female=female, male=None)
        self.assertEqual(self.core.resolve()["project_voice_id"], self.vid)
        self.assertEqual(self.core.resolve(gender="female")["project_voice_id"], female)
        self.assertEqual(self.core.resolve(explicit=self.vid, gender="female")["project_voice_id"], self.vid)
        self.defaults(general=None, female=None, male=None)
        self.assertEqual(self.core.resolve()["status"], "needs_question")

    def test_B_deleted_explicit_no_fallback_defaults_skip_and_undo(self):
        other = self.add("备用")
        self.defaults(general=other, male=self.vid)
        self.edit({"deleted": True})
        self.error("voice_unavailable", lambda: self.core.resolve(explicit=self.vid))
        self.assertEqual(self.core.resolve(gender="male")["project_voice_id"], other)
        self.edit({"deleted": False})
        self.assertEqual(self.core.resolve(gender="male")["project_voice_id"], self.vid)

    def test_B_category_default_mismatch_retains_reference(self):
        self.defaults(male=self.vid)
        self.edit({"category": "female"})
        self.assertEqual(self.core.resolve(gender="male")["status"], "needs_question")
        self.assertEqual(self.core.read()["defaults"]["male"], self.vid)

    def test_B_undo_never_overwrites_new_default(self):
        other = self.add("新默认", "male")
        self.defaults(male=self.vid)
        self.edit({"deleted": True})
        self.defaults(male=other)
        self.edit({"deleted": False})
        self.assertEqual(self.core.resolve(gender="male")["project_voice_id"], other)

    def test_C_unverified_parameters_steps_boundaries_and_override(self):
        for settings in ([], False, {"speed": True}, {"speed": .49}, {"pitch": 13}, {"speed": 1.15}, {"speed": float("nan")}):
            with self.assertRaises(MakeSoundError):
                effective(SOURCE, settings)
        for settings in ({"speed": .5, "pitch": -12}, {"speed": 2, "pitch": 12}):
            self.assertEqual(effective(SOURCE, settings), settings)
        real = {**SOURCE, "provider": "minimax", "region": "cn"}
        self.assertEqual(effective(real), {})
        self.error("parameter_unverified", lambda: effective(real, {"pitch": 0}))
        self.edit({"settings": {"speed": 1.2}})
        self.assertEqual(self.core.resolve(self.vid, overrides={"speed": 1.5})["effective_settings"]["speed"], 1.5)

    def test_C_frozen_job_survives_edits_defaults_delete_and_restart(self):
        snap = self.freeze()
        self.edit({"settings": {"speed": 1.3}, "deleted": True})
        self.defaults(general=None)
        restarted = Generation(ProjectCore(self.a), self.fake)
        self.assertEqual(restarted.load(snap["job_id"]), snap)
        self.assertEqual(restarted.run(snap["job_id"])["status"], "success")
        self.assertEqual(snap["chunks"][0]["effective_settings"]["speed"], 1)

    def test_D_order_boundaries_no_truncation(self):
        snap, result = self.run_job((4.999, 10.001, 5, 10))
        sample = self.core.preview_state(self.vid)["preview"]
        self.assertEqual(sample["source_chunk_id"], snap["chunks"][2]["chunk_id"])
        self.assertEqual(sample["duration_seconds"], 5)
        self.assertEqual(result["status"], "success")
        self.assertEqual(self.fake.calls, 4)

    def test_D_inclusive_ten_and_no_eligible_sample(self):
        self.run_job((10.001, 4.999))
        self.assertEqual(self.core.preview_state(self.vid)["status"], "missing")
        self.run_job((10,))
        self.assertEqual(self.core.preview_state(self.vid)["preview"]["duration_seconds"], 10)

    def test_D_independent_file_deleted_exports_cache_and_card_preserved(self):
        snap, state = self.run_job()
        sample = self.core.preview_state(self.vid)["preview"]
        original = self.core.managed_path(state["chunks"][snap["chunks"][0]["chunk_id"]]["path"])
        original.unlink()
        for item in state["exports"]:
            self.core.managed_path(item["audio"]).unlink()
        self.edit({"deleted": True})
        self.assertTrue(self.core.managed_path(sample["path"]).exists())
        self.assertEqual(self.core.preview_state(self.vid)["status"], "current")

    def test_D_rename_category_no_stale_speed_pitch_stale_revert(self):
        self.run_job()
        self.edit({"name": "改名", "category": "female"})
        self.assertEqual(self.core.preview_state(self.vid)["status"], "current")
        self.edit({"settings": {"speed": 1.2, "pitch": 2}})
        self.assertEqual(self.core.preview_state(self.vid)["status"], "before_adjustment")
        self.edit({"settings": {"speed": 1, "pitch": 0}})
        self.assertEqual(self.core.preview_state(self.vid)["status"], "current")

    def test_D_late_old_and_override_do_not_replace_new_preview(self):
        old = self.freeze((7,))
        self.edit({"settings": {"speed": 1.2}})
        self.run_job((8,))
        current = self.core.preview_state(self.vid)["preview"]
        self.engine.run(old["job_id"])
        segments = self.segments((9,))
        segments[0]["settings"] = {"speed": 1.5}
        temporary = self.engine.freeze(segments, confirmed=True, authorized=True)
        self.engine.run(temporary["job_id"])
        self.assertEqual(self.core.preview_state(self.vid)["preview"], current)

    def test_D_replacement_retains_old_file_and_no_repeated_overwrite(self):
        self.run_job()
        old = self.core.preview_state(self.vid)["preview"]
        self.edit({"settings": {"pitch": 1}})
        self.run_job((7,))
        new = self.core.preview_state(self.vid)["preview"]
        self.assertNotEqual(old["sample_id"], new["sample_id"])
        self.assertTrue(self.core.managed_path(old["path"]).exists())
        self.run_job((8,))
        self.assertEqual(self.core.preview_state(self.vid)["preview"], new)

    def test_D_copy_failure_and_metadata_failure_keep_old_preview(self):
        self.run_job()
        old = self.core.preview_state(self.vid)["preview"]
        self.edit({"settings": {"pitch": 1}})
        with patch("makesound.core_v16.shutil.copyfile", side_effect=OSError("PRIVATE_DO_NOT_LOG")):
            _, result = self.run_job((8,))
        self.assertEqual(result["status"], "success")
        self.assertEqual(result["preview_status"], "failed")
        self.assertEqual(self.core.preview_state(self.vid)["preview"], old)
        with patch("makesound.core_v16.atomic_write", side_effect=OSError("failure")):
            _, result = self.run_job((9,))
        self.assertEqual(result["status"], "success")
        self.assertEqual(self.core.preview_state(self.vid)["preview"], old)

    def test_D_corrupt_preview_replaced_without_extra_synthesis(self):
        snap, state = self.run_job()
        preview = self.core.preview_state(self.vid)["preview"]
        self.core.managed_path(preview["path"]).write_bytes(b"corrupt")
        self.assertEqual(self.core.preview_state(self.vid)["status"], "unavailable")
        count = self.fake.calls
        self.engine.run(snap["job_id"])
        self.assertEqual(self.fake.calls, count)
        self.assertEqual(self.core.preview_state(self.vid)["status"], "current")

    def test_D_out_of_order_completion_selects_manuscript_order(self):
        snap, state = self.run_job((6, 7, 8))
        self.edit({"settings": {"pitch": 1}})
        self.edit({"settings": {"pitch": 0}})
        def clear(obj):
            obj["voices"][self.vid]["preview"] = None
        self.core._update(clear, self.core.read()["revision"])
        reversed_results = dict(reversed(list(state["chunks"].items())))
        self.core.capture_preview(snap, reversed_results)
        self.assertEqual(self.core.preview_state(self.vid)["preview"]["source_chunk_id"], "chunk_000000")

    def test_E_multivoice_chunks_text_pause_srt_and_default_export(self):
        second = self.add("角色二")
        segments = self.segments((5, 6), [self.vid, second])
        segments[0]["pause_ms"] = 1500
        snap = self.engine.freeze(segments, confirmed=True, authorized=True)
        state = self.engine.run(snap["job_id"])
        self.assertEqual(snap["segments"], segments)
        self.assertEqual(len(snap["chunks"]), 2)
        self.assertEqual(len(state["exports"]), 1)
        entry = state["exports"][0]
        self.assertEqual(duration(self.core.managed_path(entry["audio"])), 12.5)
        text = self.core.managed_path(entry["subtitle"]).read_text(encoding="utf-8")
        self.assertIn("00:00:06,500 --> 00:00:12,500", text)
        self.assertIn(segments[0]["text"], text)
        self.assertNotEqual(self.core.preview_state(self.vid)["preview"]["path"], self.core.preview_state(second)["preview"]["path"])

    def test_E_settings_split_cache_no_merge_and_no_paid_adapter(self):
        segments = self.segments((6, 6))
        segments[1]["text"] = segments[0]["text"]
        segments[1]["settings"] = {"pitch": 1}
        snap = self.engine.freeze(segments, confirmed=True, authorized=True)
        state = self.engine.run(snap["job_id"])
        self.assertNotEqual(state["chunks"]["chunk_000000"]["path"], state["chunks"]["chunk_000001"]["path"])
        count = self.fake.calls
        same = self.engine.freeze(segments, confirmed=True, authorized=True)
        again = self.engine.run(same["job_id"])
        self.assertEqual(self.fake.calls, count)
        self.assertTrue(all(c["cache_hit"] for c in again["chunks"].values()))

    def test_E_retry_only_failed_preserves_success_restart(self):
        snap = self.freeze((6, 7))
        self.fake.fail_once.add("chunk_000001")
        state = self.engine.run(snap["job_id"])
        self.assertEqual(state["status"], "incomplete")
        count = self.fake.calls
        self.engine.run(snap["job_id"])
        self.assertEqual(self.fake.calls, count)
        state = Generation(ProjectCore(self.a), self.fake).run(snap["job_id"], retry_failed=True)
        self.assertEqual(state["status"], "success")
        self.assertEqual(self.fake.calls, count + 1)

    def test_E_billing_unknown_never_retries_even_explicit_retry(self):
        snap = self.freeze()
        self.fake.uncertain_once.add("chunk_000000")
        self.engine.run(snap["job_id"])
        count = self.fake.calls
        state = self.engine.run(snap["job_id"], retry_failed=True)
        self.assertEqual(self.fake.calls, count)
        self.assertEqual(state["chunks"]["chunk_000000"]["status"], "billing_unknown")

    def test_E_unclassified_provider_failure_never_blind_retries(self):
        snap = self.freeze()
        with patch.object(self.fake, "synthesize", side_effect=MakeSoundError("transport_timeout", "Unknown outcome")) as request:
            self.engine.run(snap["job_id"])
            result = self.engine.run(snap["job_id"], retry_failed=True)
            self.assertEqual(request.call_count, 1)
            self.assertEqual(result["chunks"]["chunk_000000"]["status"], "billing_unknown")

    def test_E_corrupt_cache_is_rejected_and_rebuilt_by_fake(self):
        snap, result = self.run_job()
        path = self.core.managed_path(result["chunks"]["chunk_000000"]["path"])
        payload = bytearray(path.read_bytes())
        payload[-1] = 1
        path.write_bytes(payload)
        count = self.fake.calls
        self.engine.run(snap["job_id"])
        self.assertEqual(self.fake.calls, count + 1)
        self.assertEqual(duration(path), 6)

    def test_D_preview_update_bumps_revision_and_stale_edit_cannot_lose_it(self):
        before = self.core.read()["revision"]
        self.run_job()
        self.error("revision_conflict", lambda: self.core.edit_voice(self.vid, {"name": "旧页面提交"}, before))
        self.assertEqual(self.core.preview_state(self.vid)["status"], "current")

    def test_E_question_answer_persist_frozen_claim_once_and_no_synthesis(self):
        questions = Questions(self.core)
        question = questions.create("job_pending", "session_harness", ["role1"])
        qid = question["question_id"]
        self.error("missing_roles", lambda: questions.submit(qid, {}))
        result = questions.submit(qid, {"role1": self.vid})
        self.assertFalse(result["agent_resumed"])
        self.assertEqual(self.fake.calls, 0)
        self.edit({"deleted": True})
        restart = Questions(ProjectCore(self.a))
        self.error("session_mismatch", lambda: restart.claim(qid, "wrong_session"))
        answer = restart.claim(qid, "session_harness")
        self.assertEqual(answer, result["answer"])
        self.error("already_claimed", lambda: restart.claim(qid, "session_harness"))
        self.error("answer_immutable", lambda: restart.submit(qid, {"role1": self.vid}))
        self.assertFalse(questions.management_complete()["agent_resumed"])

    def test_E_wait_timeout_not_ttl_and_expired_question(self):
        questions = Questions(self.core)
        q = questions.create("job_pending", "session_test", ["r"])
        self.assertEqual(questions.read(q["question_id"])["status"], "pending")
        self.error("not_answered", lambda: questions.claim(q["question_id"], "session_test"))
        q["expires_at"] = "2000-01-01T00:00:00+00:00"
        atomic_write(questions._path(q["question_id"]), q)
        self.error("question_expired", lambda: questions.submit(q["question_id"], {"r": self.vid}))

    def test_E_claimed_answer_generates_original_binding_after_delete(self):
        questions = Questions(self.core)
        question = questions.create("job_answered", "session_harness", ["r"])
        qid = question["question_id"]
        questions.submit(qid, {"r": self.vid})
        segments = [{"paragraph_id": "p", "sentence_id": "s", "role_id": "r", "text": "已确认原文"}]
        call = lambda: self.engine.freeze_from_answer(qid, "session_harness", segments, confirmed=True, authorized=True)
        self.error("answer_not_claimed", call)
        questions.claim(qid, "session_harness")
        self.edit({"deleted": True, "settings": {"pitch": 2}})
        snap = call()
        self.assertEqual(snap["job_id"], question["job_id"])
        self.assertEqual(snap["chunks"][0]["effective_settings"]["pitch"], 0)
        self.assertEqual(self.engine.run(snap["job_id"])["status"], "success")
        self.error("already_exists", call)

    def test_F_revision_concurrent_edits_one_wins_and_atomic_failure(self):
        revision = self.core.read()["revision"]
        def attempt(name):
            try:
                self.core.edit_voice(self.vid, {"name": name}, revision)
                return "ok"
            except MakeSoundError as exc:
                return exc.code
        with ThreadPoolExecutor(max_workers=2) as pool:
            self.assertCountEqual(list(pool.map(attempt, ["A", "B"])), ["ok", "revision_conflict"])
        before = self.core.path.read_bytes()
        with patch("makesound.storage.os.replace", side_effect=OSError("PRIVATE")):
            self.error("write_failed", lambda: self.edit({"name": "未提交"}))
        self.assertEqual(self.core.path.read_bytes(), before)
        self.assertEqual(list(self.core.directory.glob("*.tmp")), [])

    def test_F_migration_unknown_fields_default_mapping_backup_rollback(self):
        legacy = self.b / ".makesound/preset.json"
        old = {"schema_version": "1.2", "revision": 3, "named_voices": {"旧别名": voice()},
               "default_voice": voice(), "project_settings": {"model": "legacy-model"}, "audit": [], "unknown": {"keep": [1, 2]}}
        atomic_write(legacy, old)
        before = legacy.read_bytes()
        core = ProjectCore(self.b)
        self.error("migration_required", core.read)
        report = core.migrate()
        obj = core.read()
        self.assertEqual(read_json(__import__("pathlib").Path(report["backup"])), old)
        self.assertEqual(obj["compatibility"]["original"], old)
        self.assertEqual(obj["defaults"]["general"], obj["compatibility"]["aliases"]["旧别名"])
        first_id = obj["defaults"]["general"]
        core.rollback_migration(0)
        self.assertEqual(legacy.read_bytes(), before)
        core.migrate()
        self.assertEqual(core.read()["defaults"]["general"], first_id)

    def test_F_migration_11_direct_default_and_failure_no_active_data(self):
        legacy = self.b / ".makesound/preset.json"
        old = {"schema_version": "1.1", "voice_id": "OLD", "future": "keep", "voice": {"speed": 1.3}}
        atomic_write(legacy, old)
        core = ProjectCore(self.b)
        self.error("region_required", lambda: core.migrate(model="M"))
        self.assertFalse(core.path.exists())
        core.migrate(region="cn", model="M")
        obj = core.read()
        self.assertEqual(len(obj["voices"]), 1)
        self.assertEqual(obj["compatibility"]["original"], old)
        self.error("parameter_review_required", core.resolve)
        vid = obj["defaults"]["general"]
        self.assertEqual(obj["voices"][vid]["legacy_settings"], {"speed": 1.3})
        core.edit_voice(vid, {"acknowledge_unverified_settings": True}, 0)
        self.assertEqual(core.resolve()["source"]["voice_id"], "OLD")
        core.save_defaults({"general": None}, 1)
        self.error("rollback_conflict", lambda: core.rollback_migration(2))

    def test_F_secret_fields_paths_and_frozen_integrity(self):
        for source in ({**SOURCE, "api_key": "private"}, {**SOURCE, "voice_id": "Bearer private"}):
            with self.assertRaises(MakeSoundError):
                self.add("不可保存", source=source)
        for path in ("../escape.wav", str(self.root / "outside.wav"), ".makesound/../../escape.wav"):
            self.error("unsafe_path", lambda: self.core.managed_path(path))
        snap = self.freeze()
        path = self.core.directory / "jobs" / snap["job_id"] / "snapshot.json"
        broken = copy.deepcopy(snap)
        broken["chunks"][0]["text"] = "篡改"
        atomic_write(path, broken)
        self.error("snapshot_corrupt", lambda: self.engine.load(snap["job_id"]))

    def test_F_volcengine_no_fallback_or_real_network(self):
        vid = self.add("火山", source={**SOURCE, "provider": "volcengine", "region": "cn"})
        segments = [{"paragraph_id": "p1", "sentence_id": "s1", "text": "原文", "project_voice_id": vid}]
        snap = self.engine.freeze(segments, confirmed=True, authorized=True)
        state = self.engine.run(snap["job_id"])
        self.assertEqual(state["chunks"]["chunk_000000"]["error"], "provider_not_implemented")
        self.assertEqual(self.fake.calls, 0)

    def test_E_confirmed_authorization_and_unsupported_exports(self):
        self.error("authorization_required", lambda: self.engine.freeze(self.segments(), confirmed=True))
        self.core.save_settings({"audio_format": "mp3"}, self.core.read()["revision"])
        self.error("export_not_implemented", self.freeze)


if __name__ == "__main__":
    unittest.main()
