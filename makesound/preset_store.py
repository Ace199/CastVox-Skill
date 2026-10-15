"""Project/global presets and non-destructive 1.1 compatibility."""

import copy
from datetime import datetime, timezone

from . import validation as v
from .errors import MakeSoundError, require
from .storage import JsonStore, atomic_write, digest, file_lock, project_id, project_root, read_json, reject_links


def now():
    return datetime.now(timezone.utc).isoformat()


def empty_preset(pid=None):
    value = {"schema_version": "1.2", "revision": 0, "project_settings": {},
             "default_voice": None, "named_voices": {}, "audit": []}
    if pid:
        value["project_id"] = pid
    return value


def merge(base, overlay):
    result = copy.deepcopy(base)
    for key, value in overlay.items():
        result[key] = merge(result[key], value) if isinstance(value, dict) and isinstance(result.get(key), dict) else copy.deepcopy(value)
    return result


def legacy_view(value, region):
    require(isinstance(value, dict) and value.get("schema_version") == "1.1", "schema_version", "Unsupported preset schema.")
    v.no_secrets(value)
    require(region in v.REGIONS, "region_required", "An explicit region is required to read a legacy preset.")
    out = empty_preset()
    require(value.get("provider", "minimax") == "minimax", message="Unsupported legacy provider.")
    if value.get("voice_id"):
        out["default_voice"] = {"ref": {"kind": "provider_voice", "provider": "minimax", "region": region, "voice_id": value["voice_id"]},
                                "voice_settings": copy.deepcopy(value.get("voice", {}))}
    ex = value.get("export", {})
    v.shape(ex, {"mode", "format", "subtitle_enabled", "subtitle_type"})
    for old, new in {"mode": "export_mode", "format": "audio_format", "subtitle_enabled": "subtitle_enabled", "subtitle_type": "subtitle_type"}.items():
        if old in ex:
            out["project_settings"][new] = ex[old]
    for key in ("model", "script_processing", "pause"):
        if key in value:
            out["project_settings"][key] = copy.deepcopy(value[key])
    out["compatibility"] = {"original_schema": "1.1", "original": copy.deepcopy(value)}
    v.preset(out)
    return out


class PresetStore:
    def __init__(self, path, *, pid=None, global_scope=False, region=None):
        self.path, self.pid = path, pid
        self.global_scope, self.region = global_scope, region
        self.store = JsonStore(path, empty_preset(pid), self.validate)

    def validate(self, obj):
        v.preset(obj, self.global_scope)
        if self.pid:
            require(obj.get("project_id") == self.pid, "project_mismatch", "Preset belongs to a different project root.")

    def read(self):
        reject_links(self.path)
        if not self.path.exists():
            return empty_preset(self.pid)
        raw = read_json(self.path)
        if isinstance(raw, dict) and raw.get("schema_version") == "1.1":
            view = legacy_view(raw, self.region)
            if self.pid:
                view["project_id"] = self.pid
            self.validate(view)
            return view
        return self.store.read()

    def update(self, change, revision):
        require(type(revision) is int and revision >= 0, "revision_required", "An expected revision is required for preset updates.")
        if self.path.exists():
            raw = read_json(self.path)
            require(isinstance(raw, dict), message="Preset must be an object.")
            require(raw.get("schema_version") != "1.1", "migration_required", "Legacy presets are read-only; export a migration first.")
        return self.store.update(change, revision)

    def set_default(self, voice, settings, revision):
        if voice is not None:
            v.voice(voice, not self.global_scope)
        v.project_settings(settings)

        def change(obj):
            obj["default_voice"] = copy.deepcopy(voice)
            obj["project_settings"] = merge(obj["project_settings"], settings)
            obj["audit"].append({"action": "set_default", "at": now()})
        return self.update(change, revision)[0]

    def patch_settings(self, settings, revision):
        v.project_settings(settings)

        def change(obj):
            obj["project_settings"] = merge(obj["project_settings"], settings)
            obj["audit"].append({"action": "settings", "at": now()})
        return self.update(change, revision)[0]

    def export_migration(self, region):
        """Keep the active original intact; a reviewed destination must be activated manually."""
        with file_lock(self.path.with_suffix(self.path.suffix + ".lock")):
            original = read_json(self.path)
            view = legacy_view(original, region)
            if self.pid:
                view["project_id"] = self.pid
            view["audit"] = [{"action": "migration_export", "at": now()}]
            self.validate(view)
            backup = self.path.with_name(self.path.stem + ".v1.1-backup-" + digest(original)[:12] + ".json")
            destination = self.path.with_name(self.path.stem + ".v1.2.json")
            require(not destination.exists(), "already_exists", "Migration output already exists; review it before proceeding.")
            if backup.exists():
                require(read_json(backup) == original, "backup_conflict", "Existing migration backup differs.")
            else:
                atomic_write(backup, original)
            atomic_write(destination, view)
            return {"backup": str(backup), "output": str(destination), "active_original_unchanged": True}


def for_project(root, region=None):
    path = project_root(root)
    return PresetStore(path / ".makesound/preset.json", pid=project_id(path), region=region)
