"""Immutable configuration snapshots, not a generation or resume engine."""

import copy
import uuid

from . import validation as v
from .errors import require
from .preset_store import now
from .storage import atomic_write, digest, file_lock, read_json, reject_links


def validate_snapshot(obj):
    v.shape(obj, {"schema_version", "job_id", "project_id", "created_at", "source_hash", "resolution", "status", "snapshot_hash"},
            {"schema_version", "job_id", "project_id", "created_at", "source_hash", "resolution", "status", "snapshot_hash"})
    require(obj["schema_version"] == "1.2" and obj["status"] == "snapshot_only")
    v.identifier(obj["job_id"])
    require(isinstance(obj["source_hash"], str) and (obj["source_hash"] == "" or
            len(obj["source_hash"]) == 64 and all(c in "0123456789abcdef" for c in obj["source_hash"])))
    resolution = obj["resolution"]
    require(isinstance(resolution, dict) and resolution.get("status") == "ready")
    require(resolution.get("project_id") == obj["project_id"])
    v.project_settings(resolution.get("project_settings", {}))
    require(isinstance(resolution.get("bindings"), list) and bool(resolution["bindings"]))
    for binding in resolution["bindings"]:
        require(isinstance(binding, dict) and isinstance(binding.get("voice"), dict))
        v.identifier(binding.get("target"))
        concrete = binding["voice"]
        require(concrete.get("region") in v.REGIONS)
        v.reference({"kind": "provider_voice", **{key: concrete.get(key) for key in ("provider", "region", "voice_id")}})
        v.voice_settings(concrete.get("voice_settings", {}))
        v.metadata(concrete.get("metadata", {}))
    expected = digest({k: val for k, val in obj.items() if k != "snapshot_hash"})
    require(obj["snapshot_hash"] == expected, "snapshot_corrupt", "Snapshot integrity validation failed.")
    v.no_secrets(obj)


class JobStore:
    def __init__(self, root):
        self.root = root / "jobs"

    def create(self, resolution, source_hash="", job_id=None):
        require(resolution.get("status") == "ready", "not_ready", "Only a locally ready configuration can be frozen.")
        jid = job_id or "job_" + uuid.uuid4().hex
        v.identifier(jid)
        obj = {"schema_version": "1.2", "job_id": jid, "project_id": resolution.get("project_id"), "created_at": now(),
               "source_hash": source_hash, "resolution": copy.deepcopy(resolution), "status": "snapshot_only"}
        obj["snapshot_hash"] = digest(obj)
        validate_snapshot(obj)
        path = self.root / jid / "snapshot.json"
        with file_lock(self.root / ".snapshot.lock"):
            require(not path.exists(), "already_exists", "Job snapshot already exists; it cannot be overwritten.")
            atomic_write(path, obj)
        return obj

    def load(self, jid):
        v.identifier(jid)
        path = self.root / jid / "snapshot.json"
        reject_links(path)
        obj = read_json(path)
        validate_snapshot(obj)
        require(obj["job_id"] == jid, "snapshot_corrupt", "Job ID does not match the snapshot path.")
        return obj
