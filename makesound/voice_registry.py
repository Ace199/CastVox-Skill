"""Local registration of existing clone/design IDs; no creation API is present."""

import copy
import os
import shutil
import uuid
from pathlib import Path

from . import validation as v
from .errors import MakeSoundError, require
from .preset_store import now
from .storage import JsonStore, read_json, reject_links


def validate_registry(obj):
    v.shape(obj, {"schema_version", "revision", "assets"}, {"schema_version", "revision", "assets"})
    require(obj["schema_version"] == "1.2", "schema_version", "Unsupported asset schema.")
    require(type(obj["revision"]) is int and obj["revision"] >= 0 and isinstance(obj["assets"], dict))
    names = set()
    for aid, asset in obj["assets"].items():
        v.identifier(aid)
        v.shape(asset, {"asset_id", "display_name", "source_type", "provider", "region", "voice_id", "created_at", "availability", "metadata", "sample", "design", "consent", "registration"},
                {"asset_id", "display_name", "source_type", "provider", "region", "voice_id", "created_at", "availability", "metadata", "sample", "registration"})
        require(asset["asset_id"] == aid and asset["source_type"] in {"clone", "design"})
        label = v.name(asset["display_name"])
        require(label == asset["display_name"] and label not in names, "name_conflict", "Global asset display names must be unique.")
        names.add(label)
        v.reference({"kind": "provider_voice", "provider": asset["provider"], "region": asset["region"], "voice_id": asset["voice_id"]})
        require(asset["region"] in v.REGIONS and asset["availability"] in v.AVAILABILITY)
        v.metadata(asset["metadata"])
        v.text(asset["created_at"])
        require(asset["registration"] == "local_existing_id", message="M1 only registers existing IDs locally.")
        if asset["sample"] is not None:
            v.shape(asset["sample"], {"managed_path", "retained"}, {"managed_path", "retained"})
            require(asset["source_type"] == "clone" and isinstance(asset["sample"]["managed_path"], str)
                    and type(asset["sample"]["retained"]) is bool)
        if "design" in asset:
            require(asset["source_type"] == "design" and isinstance(asset["design"], dict))
        if "consent" in asset:
            require(isinstance(asset["consent"], dict))
    v.no_secrets(obj)


class VoiceRegistry:
    def __init__(self, data_dir):
        self.root = data_dir / "voices"
        self.store = JsonStore(self.root / "assets.json", {"schema_version": "1.2", "revision": 0, "assets": {}}, validate_registry)

    def read(self):
        return self.store.read()

    def register(self, value, sample_path=None):
        v.shape(value, {"display_name", "source_type", "provider", "region", "voice_id", "availability", "metadata", "design", "consent"},
                {"display_name", "source_type", "provider", "region", "voice_id"})
        item = copy.deepcopy(value)
        item.update(asset_id="asset_" + uuid.uuid4().hex, created_at=now(), sample=None, registration="local_existing_id")
        item["display_name"] = v.name(item["display_name"])
        item.setdefault("availability", "unknown")
        item.setdefault("metadata", {})
        sample = None
        if sample_path is not None:
            sample = Path(sample_path)
            require(sample.is_absolute() and sample.is_file() and item["source_type"] == "clone",
                    "invalid_sample", "Only an explicit local clone sample file may be retained.")
            reject_links(sample)
            require(sample.stat().st_size <= 20 * 1024 * 1024, "invalid_sample", "Sample exceeds the local retention size limit.")
            item["sample"] = {"managed_path": str((self.root / "samples" / item["asset_id"] / "original.sample").resolve()), "retained": True}
        probe = {"schema_version": "1.2", "revision": 0, "assets": {item["asset_id"]: item}}
        validate_registry(probe)

        def change(obj):
            require(all(a["display_name"] != item["display_name"] for a in obj["assets"].values()), "name_conflict", "Global asset name already exists.")
            if sample:
                target = Path(item["sample"]["managed_path"])
                reject_links(target)
                target.parent.mkdir(parents=True, exist_ok=False)
                shutil.copyfile(sample, target)
            obj["assets"][item["asset_id"]] = item
        try:
            updated, _ = self.store.update(change)
        except BaseException:
            if item["sample"]:
                target = Path(item["sample"]["managed_path"])
                target.unlink(missing_ok=True)
                if target.parent.exists():
                    target.parent.rmdir()
            raise
        return updated, item

    def rename(self, aid, display_name, revision):
        label = v.name(display_name)

        def change(obj):
            require(aid in obj["assets"], "not_found", "Asset does not exist.")
            obj["assets"][aid]["display_name"] = label
        return self.store.update(change, revision)[0]

    def sample_delete(self, aid, *, confirmed=False):
        require(confirmed, "confirmation_required", "Confirm deletion of the retained local sample.")

        def change(obj):
            require(aid in obj["assets"], "not_found", "Asset does not exist.")
            sample = obj["assets"][aid]["sample"]
            require(sample is not None, "sample_missing", "Asset has no retained sample.")
            target = Path(sample["managed_path"])
            expected = (self.root / "samples" / aid / "original.sample").resolve()
            reject_links(target)
            require(target.resolve() == expected, "unsafe_path", "Sample path is outside the managed asset directory.")
            target.unlink(missing_ok=True)
            sample["retained"] = False
        # A crash after unlink may leave retained=true; reads report actual existence.
        return self.store.update(change)[0]


def asset_summary(asset, local_paths=False):
    sample = asset["sample"]
    result = {k: copy.deepcopy(asset[k]) for k in ("asset_id", "display_name", "source_type", "provider", "region", "voice_id", "availability", "registration")}
    result["sample_retained"] = bool(sample and sample["retained"] and Path(sample["managed_path"]).is_file())
    if local_paths and sample:
        result["sample_path"] = sample["managed_path"]
    return result
