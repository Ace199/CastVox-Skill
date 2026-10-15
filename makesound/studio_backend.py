"""V1.6 Studio boundary. Management and answers cannot dispatch synthesis."""
import copy
from pathlib import Path

from . import validation as v
from .errors import require
from .providers import capabilities, source_valid
from .questions import Questions
from .storage import read_json


class StudioBackend:
    def __init__(self, core, *, config_paths=None, allow_fake=False):
        self.core = core
        self.config_paths = config_paths if config_paths is not None else {
            "minimax": Path.home() / ".config/minimax/config.json"}
        self.allow_fake = allow_fake
        self.questions = Questions(core)

    def providers(self):
        from .provider_config import read_models
        providers = []
        for provider in ("minimax", "volcengine"):
            path = self.config_paths.get(provider)
            public = read_models(path)
            region = None
            try:
                value = read_json(path).get("region") if path else None
                if value in {"cn", "international"}:
                    region = value
            except Exception:
                pass
            providers.append({"id": provider, **public, "region": region, "synthesis_status": "provider_not_implemented",
                              "capabilities": {}, "capability_status": "unverified"})
        if self.allow_fake:
            from .providers import FAKE_CAPABILITIES
            providers.append({"id": "fake", "models": [{"id": "fake-v1", "name": "Offline Fake"}],
                              "default_model": "fake-v1", "model_status": "configured", "region": "test",
                              "synthesis_status": "offline_only", "capabilities": copy.deepcopy(FAKE_CAPABILITIES), "capability_status": "verified_fake_only"})
        return {"providers": providers, "network_calls": 0}

    def state(self):
        obj = self.core.read()
        return {"preset": obj, "active_voice_ids": [vid for vid, item in obj["voices"].items() if not item["deleted"]],
                "effective_defaults": {slot: vid if (item := obj["voices"].get(vid)) and not item["deleted"] and
                                       (slot == "general" or slot == item["category"]) else None for slot, vid in obj["defaults"].items()},
                "previews": {vid: self.core.preview_state(vid) for vid in obj["voices"]},
                "management": self.questions.management_complete()}

    def add_voice(self, body):
        v.shape(body, {"name", "category", "source", "revision"}, {"name", "category", "source", "revision"})
        source = body["source"]
        source_valid(source)
        provider = next((p for p in self.providers()["providers"] if p["id"] == source["provider"]), None)
        require(provider and provider["model_status"] == "configured", "model_not_configured", "Provider model configuration must be repaired.")
        require(source["model"] in {m["id"] for m in provider["models"]}, "model_not_configured", "Choose an explicitly configured model.")
        require(source["region"] == provider["region"], "region_mismatch", "Voice region must match the explicit provider configuration.")
        preset, vid = self.core.add_voice(body["name"], body["category"], source, body["revision"])
        return {"preset": preset, "project_voice_id": vid}

    def question(self, question_id):
        obj = self.questions.read(question_id)
        return {key: copy.deepcopy(obj[key]) for key in ("question_id", "job_id", "roles", "status", "expires_at", "answer")}

    def dispatch(self, action, body):
        require(isinstance(body, dict))
        v.no_secrets(body)
        if action == "voices/add":
            return self.add_voice(body)
        if action == "voices/edit":
            v.shape(body, {"project_voice_id", "patch", "revision"}, {"project_voice_id", "patch", "revision"})
            return {"preset": self.core.edit_voice(body["project_voice_id"], body["patch"], body["revision"])}
        if action in {"defaults", "settings"}:
            v.shape(body, {action, "revision"}, {action, "revision"})
            call = self.core.save_defaults if action == "defaults" else self.core.save_settings
            return {"preset": call(body[action], body["revision"])}
        if action == "answers":
            v.shape(body, {"question_id", "assignments"}, {"question_id", "assignments"})
            return self.questions.submit(body["question_id"], body["assignments"])
        if action == "complete":
            v.shape(body, set())
            return self.questions.management_complete()
        require(False, "not_found", "Unknown management action.")
