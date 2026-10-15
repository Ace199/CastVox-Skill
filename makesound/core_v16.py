"""Explicit V1.6 offline API. Legacy M1 files and entry points remain read-only here."""
import copy
import os
import shutil
import uuid
from pathlib import Path

from . import validation as v
from .errors import MakeSoundError, require
from .providers import capabilities, duration, effective, source_valid
from .storage import JsonStore, atomic_write, digest, file_lock, project_id, project_root, read_json, reject_links


def uid(prefix):
    return prefix + uuid.uuid4().hex


def signature(source, settings):
    return digest({"source": source, "settings": settings})


def initial(root):
    return {"schema_version": "1.6", "revision": 0, "project_id": project_id(root),
            "project_settings": {"export_mode": "paragraph", "subtitle_enabled": True,
                                 "subtitle_type": "sentence", "audio_format": "wav"},
            "voices": {}, "defaults": {"general": None, "male": None, "female": None}}


def validate(obj):
    require(isinstance(obj, dict) and obj.get("schema_version") == "1.6", "schema_version", "Expected V1.6 preset.")
    require(type(obj.get("revision")) is int and obj["revision"] >= 0)
    v.project_settings(obj["project_settings"])
    v.shape(obj["defaults"], {"general", "male", "female"}, {"general", "male", "female"})
    for ref in obj["defaults"].values():
        if ref is not None:
            v.identifier(ref)
    require(isinstance(obj["voices"], dict))
    names = set()
    for vid, item in obj["voices"].items():
        v.identifier(vid)
        require(item["name"] == v.name(item["name"]))
        require(item["category"] in {"male", "female", "other"} and type(item["deleted"]) is bool)
        source_valid(item["source"])
        require(effective(item["source"], item["settings"]) == item["settings"])
        if not item["deleted"]:
            require(item["name"] not in names, "name_conflict", "An active voice already has this name.")
            names.add(item["name"])
        require(item.get("preview") is None or isinstance(item["preview"], dict))
    v.no_secrets(obj)


class ProjectCore:
    def __init__(self, root):
        self.root = project_root(root)
        self.directory = self.root / ".makesound"
        self.path = self.directory / "preset.v1.6.json"
        self.store = JsonStore(self.path, initial(self.root), self._validate)

    def _validate(self, obj):
        validate(obj)
        require(obj["project_id"] == project_id(self.root), "project_mismatch", "Preset belongs to another project.")

    def read(self):
        # Existing legacy projects cannot silently become empty V1.6 projects.
        require(self.path.exists() or not (self.directory / "preset.json").exists(),
                "migration_required", "Explicit legacy migration is required before V1.6 writes.")
        return self.store.read()

    def _update(self, change, revision):
        require(type(revision) is int and revision >= 0, "revision_required", "Expected revision is required.")
        self.read()
        return self.store.update(change, revision)[0]

    def add_voice(self, name, category, source, revision, settings=None):
        source_valid(source)
        item = {"name": v.name(name), "category": category, "source": copy.deepcopy(source),
                "settings": effective(source, settings), "deleted": False, "preview": None}
        vid = uid("pv_")
        def change(obj):
            obj["voices"][vid] = item
        return self._update(change, revision), vid

    def edit_voice(self, vid, patch, revision):
        v.identifier(vid)
        v.shape(patch, {"name", "category", "settings", "deleted", "acknowledge_unverified_settings"})
        def change(obj):
            require(vid in obj["voices"], "not_found", "Project voice does not exist.")
            item = obj["voices"][vid]
            for key, val in patch.items():
                if key == "acknowledge_unverified_settings":
                    require(val is True, message="Explicit acknowledgement must be true.")
                    item["parameter_review_required"] = False
                    continue
                item[key] = (v.name(val) if key == "name" else effective(item["source"], item["settings"], val)
                             if key == "settings" else copy.deepcopy(val))
        return self._update(change, revision)

    def save_defaults(self, defaults, revision):
        v.shape(defaults, {"general", "male", "female"})
        def change(obj):
            for slot, vid in defaults.items():
                if vid is not None:
                    v.identifier(vid)
                    item = obj["voices"].get(vid)
                    require(item and not item["deleted"] and (slot == "general" or slot == item["category"]),
                            "invalid_default", "Default must reference an active voice of the selected category.")
                obj["defaults"][slot] = vid
        return self._update(change, revision)

    def save_settings(self, settings, revision):
        v.project_settings(settings)
        def change(obj):
            obj["project_settings"].update(copy.deepcopy(settings))
        return self._update(change, revision)

    def resolve(self, explicit=None, gender=None, overrides=None, preset=None):
        obj = self.read() if preset is None else preset
        require(gender in {None, "male", "female", "other"})
        if explicit is not None:
            v.identifier(explicit)
            item = obj["voices"].get(explicit)
            require(item and not item["deleted"], "voice_unavailable", "Explicit voice is missing or deleted; choose or restore it.")
            vid = explicit
        else:
            vid = None
            for slot in ([gender] if gender in {"male", "female"} else []) + ["general"]:
                candidate = obj["defaults"].get(slot)
                item = obj["voices"].get(candidate)
                if item and not item["deleted"] and (slot == "general" or slot == item["category"]):
                    vid = candidate
                    break
            if vid is None:
                return {"status": "needs_question"}
            item = obj["voices"][vid]
        require(not item.get("parameter_review_required"), "parameter_review_required",
                "Legacy parameters remain preserved but unverified; explicitly acknowledge their omission before a new Job.")
        values = effective(item["source"], item["settings"], overrides)
        return {"status": "ready", "project_voice_id": vid, "source": copy.deepcopy(item["source"]),
                "effective_settings": values, "capability_validation": {"status": "validated", "descriptor": capabilities(item["source"])}}

    def managed_path(self, relative):
        require(isinstance(relative, str), "unsafe_path", "Expected a relative project path.")
        path = self.root / relative
        reject_links(path)
        require(not Path(relative).is_absolute() and path.resolve().is_relative_to(self.directory.resolve()),
                "unsafe_path", "Managed path escapes project data.")
        return path

    def preview_state(self, vid):
        item = self.read()["voices"][vid]
        sample = item["preview"]
        if sample is None:
            return {"status": "missing", "preview": None}
        try:
            measured = duration(self.managed_path(sample["path"]))
            require(5 <= measured <= 10 and abs(measured - sample["duration_seconds"]) < .001)
            require(sample.get("audio_hash") == digest(self.managed_path(sample["path"]).read_bytes().hex()))
        except (MakeSoundError, KeyError, TypeError, OSError):
            return {"status": "unavailable", "preview": copy.deepcopy(sample)}
        return {"status": "current" if sample["signature"] == signature(item["source"], item["settings"]) else "before_adjustment",
                "preview": copy.deepcopy(sample)}

    def capture_preview(self, snapshot, results):
        """Call on settled jobs, in manuscript order; serialize selection with all edits."""
        with file_lock(self.path.with_suffix(self.path.suffix + ".lock")):
            obj = self.read()
            changed = False
            for chunk in snapshot["chunks"]:
                result = results.get(chunk["chunk_id"], {})
                if result.get("status") != "success":
                    continue
                vid = chunk["project_voice_id"]
                item = obj["voices"].get(vid)
                if not item or item["deleted"]:
                    continue
                sig = signature(chunk["source"], chunk["effective_settings"])
                if sig != signature(item["source"], item["settings"]):
                    continue
                old = item["preview"]
                if old and old["signature"] == sig:
                    try:
                        old_path = self.managed_path(old["path"])
                        if (5 <= duration(old_path) <= 10 and duration(old_path) == old["duration_seconds"]
                                and old.get("audio_hash") == digest(old_path.read_bytes().hex())):
                            continue
                    except MakeSoundError:
                        pass
                original = self.managed_path(result["path"])
                seconds = duration(original)
                if not 5 <= seconds <= 10:
                    continue
                sid = uid("sample_")
                relative = f".makesound/previews/{vid}/{sid}.wav"
                target = self.managed_path(relative)
                target.parent.mkdir(parents=True, exist_ok=True)
                temporary = target.with_suffix(".tmp")
                try:
                    shutil.copyfile(original, temporary)
                    with temporary.open("r+b") as stream:
                        os.fsync(stream.fileno())
                    require(duration(temporary) == seconds, "invalid_audio", "Preview copy did not validate.")
                    os.replace(temporary, target)
                finally:
                    temporary.unlink(missing_ok=True)
                item["preview"] = {"sample_id": sid, "path": relative, "duration_seconds": seconds,
                                   "source_job_id": snapshot["job_id"], "source_chunk_id": chunk["chunk_id"],
                                   "source": copy.deepcopy(chunk["source"]), "effective_settings": copy.deepcopy(chunk["effective_settings"]),
                                   "signature": sig, "audio_hash": digest(target.read_bytes().hex())}
                changed = True
            if changed:
                obj["revision"] += 1
                self._validate(obj)
                atomic_write(self.path, obj)
        return changed

    def migrate(self, *, region=None, model=None, assets=None):
        """Export+activate separate V1.6 file; never alter legacy data or jobs."""
        from .preset_store import legacy_view
        legacy_path = self.directory / "preset.json"
        with file_lock(self.path.with_suffix(self.path.suffix + ".lock")):
            require(not self.path.exists(), "already_exists", "V1.6 data already exists.")
            raw = read_json(legacy_path)
            require(raw.get("schema_version") in {"1.1", "1.2"}, "schema_version", "Unsupported migration version.")
            v.no_secrets(raw)
            old = legacy_view(raw, region) if raw["schema_version"] == "1.1" else raw
            obj = initial(self.root)
            obj["project_settings"].update(old.get("project_settings", {}))
            obj["compatibility"] = {"original": copy.deepcopy(raw), "aliases": {}}
            mapping = obj["compatibility"]["aliases"]
            def convert(name, item):
                ref = item["ref"]
                if ref["kind"] == "global_asset":
                    require(ref["asset_id"] in (assets or {}), "missing_asset", "Migration needs the referenced global asset.")
                    record = assets[ref["asset_id"]]
                else:
                    record = ref
                require(record.get("region") != "configured" or region, "region_required", "Migration requires an explicit region.")
                source = {"provider": record["provider"], "region": region if record["region"] == "configured" else record["region"],
                          "model": model or old.get("project_settings", {}).get("model"), "voice_id": record["voice_id"]}
                require(source["model"], "model_required", "Migration requires an explicit model.")
                source_valid(source)
                vid = "pv_" + digest({"project": obj["project_id"], "name": name})[:32]
                # Unverified legacy parameters remain in compatibility, never become effective API settings.
                obj["voices"][vid] = {"name": name, "category": item.get("metadata", {}).get("gender", "other"),
                                      "source": source, "settings": effective(source), "deleted": False, "preview": None,
                                      "legacy_settings": copy.deepcopy(item.get("voice_settings", {})),
                                      "parameter_review_required": bool(item.get("voice_settings"))}
                if obj["voices"][vid]["category"] not in {"male", "female"}:
                    obj["voices"][vid]["category"] = "other"
                return vid
            for name, item in old.get("named_voices", {}).items():
                mapping[name] = convert(name, item)
            default = old.get("default_voice")
            if default:
                if default["ref"]["kind"] == "project_alias":
                    require(default["ref"]["name"] in mapping, "missing_alias", "Legacy default alias is missing.")
                    vid = mapping[default["ref"]["name"]]
                    # Alias-level overrides require a separate visible compatible record.
                    target = old["named_voices"][default["ref"]["name"]]
                    if default.get("voice_settings"):
                        selected = copy.deepcopy(target)
                        selected["voice_settings"] = {**target.get("voice_settings", {}), **default["voice_settings"]}
                        name = "兼容默认"
                        while name in mapping:
                            name += "_"
                        vid = convert(name, selected)
                else:
                    vid = next((mapping[name] for name, item in old.get("named_voices", {}).items() if item == default), None)
                    if vid is None:
                        name = "兼容默认"
                        while name in mapping:
                            name += "_"
                        vid = convert(name, default)
                obj["defaults"]["general"] = vid
            self._validate(obj)
            backup = self.directory / ("preset.pre-v16-" + digest(raw)[:16] + ".json")
            if backup.exists():
                require(read_json(backup) == raw, "backup_conflict", "Migration backup differs.")
            else:
                atomic_write(backup, raw)
            atomic_write(self.path, obj)
            return {"backup": str(backup), "active": str(self.path), "legacy_unchanged": True,
                    "warning": "Unverified legacy voice parameters are preserved in compatibility.original, not enabled."}

    def rollback_migration(self, revision):
        with file_lock(self.path.with_suffix(self.path.suffix + ".lock")):
            obj = self.read()
            require(obj["revision"] == revision == 0 and "compatibility" in obj,
                    "rollback_conflict", "Rollback only applies before V1.6 edits.")
            raw = read_json(self.directory / "preset.json")
            require(raw == obj["compatibility"]["original"], "rollback_conflict", "Legacy data changed after migration.")
            archived = self.directory / (uid("preset.v16-rollback-") + ".json")
            os.replace(self.path, archived)
            return {"archived": str(archived), "legacy_unchanged": True}
