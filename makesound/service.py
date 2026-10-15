"""Coordinates registry and project edits without knowing any Harness SDK."""

import copy
from contextlib import contextmanager
from pathlib import Path

from . import validation as v
from .config_resolver import resolve
from .errors import MakeSoundError, require
from .jobs import JobStore
from .preset_store import PresetStore, empty_preset, for_project
from .project_voice_library import ProjectVoiceLibrary
from .storage import JsonStore, file_lock, project_root, read_json
from .voice_registry import VoiceRegistry


def _validate_index(obj):
    v.shape(obj, {"revision", "schema_version", "projects"}, {"revision", "schema_version", "projects"})
    require(obj["schema_version"] == "1.2" and type(obj["revision"]) is int and obj["revision"] >= 0)
    require(isinstance(obj["projects"], list) and all(isinstance(x, str) and Path(x).is_absolute() for x in obj["projects"]))


class MakeSound:
    def __init__(self, locations, *, region=None):
        require(locations.global_config.resolve() != locations.minimax_config.resolve(),
                "protected_credentials", "Business configuration cannot overwrite the MiniMax credential file.")
        self.locations, self.region = locations, region
        self.registry = VoiceRegistry(locations.data_dir)
        self.global_preset = PresetStore(locations.global_config, global_scope=True, region=region)
        self.jobs = JobStore(locations.data_dir)
        self.index = JsonStore(locations.data_dir / "project-index.json", {"schema_version": "1.2", "revision": 0, "projects": []}, _validate_index)

    @contextmanager
    def editing(self, project=None):
        """All supported mutations use this lock; readonly resolution creates no lock file."""
        with file_lock(self.locations.data_dir / ".operations.lock"):
            if project is not None:
                root = project_root(project)

                def track(obj):
                    if str(root) not in obj["projects"]:
                        obj["projects"].append(str(root))
                # Record before committing a project edit: failure can only over-report references.
                self.index.update(track)
            yield

    def check_voice(self, item, *, allow_alias=False, project=None):
        v.voice(item, allow_alias)
        ref = item["ref"]
        if ref["kind"] == "global_asset":
            require(ref["asset_id"] in self.registry.read()["assets"], "missing_asset", "Global asset does not exist.")
        elif ref["kind"] == "project_alias":
            require(project is not None and ref["name"] in for_project(project, self.region).read()["named_voices"], "missing_alias", "Default alias does not exist.")
        elif self.region:
            require(ref["region"] in {self.region, "configured"}, "region_mismatch", "Voice belongs to another configured region.")

    def set_default(self, item, settings, revision, project=None):
        with self.editing(project):
            self.check_voice(item, allow_alias=project is not None, project=project)
            store = for_project(project, self.region) if project else self.global_preset
            return store.set_default(item, settings, revision)

    def patch_settings(self, settings, revision, project=None):
        with self.editing(project):
            store = for_project(project, self.region) if project else self.global_preset
            return store.patch_settings(settings, revision)

    def alias(self, action, project, alias, revision, **kwargs):
        with self.editing(project):
            if "voice" in kwargs:
                self.check_voice(kwargs["voice"])
            library = ProjectVoiceLibrary(for_project(project, self.region))
            return getattr(library, action)(alias, revision=revision, **kwargs)

    def resolve(self, project=None, request=None):
        preset = for_project(project, self.region).read() if project is not None else empty_preset()
        return resolve(preset, self.global_preset.read(), self.registry.read(), request, region=self.region)

    def snapshot(self, project=None, request=None, source_hash=""):
        with self.editing():
            resolution = self.resolve(project, request)
            return self.jobs.create(resolution, source_hash, (request or {}).get("job_id"))

    def register_asset(self, item, sample_path=None):
        with self.editing():
            return self.registry.register(item, sample_path)

    def sample_delete(self, aid, confirmed=False):
        with self.editing():
            return self.registry.sample_delete(aid, confirmed=confirmed)

    def asset_references(self, aid):
        v.identifier(aid)
        result = []

        def visit(value, origin):
            if isinstance(value, dict):
                if value.get("kind") == "global_asset" and value.get("asset_id") == aid or value.get("asset_id") == aid and "voice_id" in value:
                    result.append(origin)
                for child in value.values():
                    visit(child, origin)
            elif isinstance(value, list):
                for child in value:
                    visit(child, origin)
        if self.locations.global_config.exists():
            visit(read_json(self.locations.global_config), "global_default")
        for root in self.index.read()["projects"]:
            path = project_root(root) / ".makesound/preset.json"
            if path.exists():
                visit(read_json(path), "project:" + for_project(root, self.region).pid)
        for path in self.jobs.root.glob("*/snapshot.json"):
            visit(read_json(path), "job:" + path.parent.name)
        return sorted(set(result))

    def delete_asset(self, aid, revision, *, confirmed=False, known_projects_confirmed=False):
        require(confirmed and known_projects_confirmed, "confirmation_required", "Confirm local asset deletion and the known-project inventory boundary.")
        with self.editing():
            refs = self.asset_references(aid)
            require(not refs, "referenced", "Asset is referenced; remove dependent references first.")

            def change(obj):
                require(aid in obj["assets"], "not_found", "Asset does not exist.")
                require(not obj["assets"][aid].get("sample") or not obj["assets"][aid]["sample"]["retained"],
                        "sample_retained", "Delete the retained sample explicitly before removing its local asset record.")
                del obj["assets"][aid]
            return self.registry.store.update(change, revision)[0]
