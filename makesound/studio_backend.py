"""V1.6 Studio boundary. Management and answers cannot dispatch synthesis."""
import copy
from pathlib import Path

from . import validation as v
from .errors import require
from .providers import capabilities, source_valid
from .questions import Questions
from .storage import read_json


class StudioBackend:
    def __init__(self, core, *, config_paths=None, allow_fake=False, config_dir=None):
        self.core = core
        self.config_paths = config_paths if config_paths is not None else {
            provider: Path.home() / ".config" / provider / "config.json" for provider in ("minimax", "volcengine")}
        self.allow_fake = allow_fake
        self.config_dir = config_dir
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
            from studio_server import PROVIDERS
            from studio_config_editor import config_path
            spec = next(p for p in PROVIDERS if p['id'] == provider)
            editable = path is not None and Path(path) == config_path(provider, self.config_dir)
            public['models'] = [{**model, 'capabilities': capabilities({'provider': provider, 'region': region, 'model': model['id']})}
                                for model in public['models']]
            providers.append({**spec, "id": provider, **public, "region": region,
                              'config_edit': {'available': editable, 'reason': '' if editable else '配置路径由启动器控制',
                                              'environment': 'test' if self.config_dir else 'production'},
                              "synthesis_status": 'requires_explicit_job_authorization' if provider == 'minimax' else 'provider_not_implemented',
                              'support': 'Adapter 已实现 · 真实合成未验收' if provider == 'minimax' else spec['support'],
                              "capabilities": {}, "capability_status": 'documented_not_live_tested' if provider == 'minimax' and region == 'cn' else 'unverified'})
        if self.allow_fake:
            from .providers import FAKE_CAPABILITIES
            caps = {k: {**c, 'supported': True} for k, c in FAKE_CAPABILITIES.items()}
            providers.append({"id": "fake", 'name': 'Fake（离线静音）', 'help': '仅验证流程，不是真实配音',
                              'config_edit': {'available': False, 'reason': 'Fake 无凭据配置'},
                              "models": [{"id": "fake-v1", "name": "Offline Fake", 'capabilities': caps}],
                              "default_model": "fake-v1", "model_status": "configured", "region": "test",
                              "synthesis_status": "offline_only", "capabilities": copy.deepcopy(FAKE_CAPABILITIES), "capability_status": "verified_fake_only"})
        return {"providers": providers, "network_calls": 0}

    def state(self):
        obj = self.core.read()
        return {"preset": obj, 'project': {'id': obj['project_id'], 'name': self.core.root.name, 'path': str(self.core.root)},
                "active_voice_ids": [vid for vid, item in obj["voices"].items() if not item["deleted"]],
                "effective_defaults": {slot: vid if (item := obj["default_snapshots"].get(slot)) and
                                       (slot == "general" or slot == item["category"]) else None for slot, vid in obj["defaults"].items()},
                "previews": {vid: self.core.preview_state(vid) for vid in obj["voices"]},
                "management": self.questions.management_complete()}

    def add_voice(self, body):
        v.shape(body, {"name", "category", "source", "revision", 'settings'}, {"name", "category", "source", "revision"})
        source = body["source"]
        source_valid(source)
        provider = next((p for p in self.providers()["providers"] if p["id"] == source["provider"]), None)
        require(provider and provider["model_status"] == "configured", "model_not_configured", "Provider model configuration must be repaired.")
        require(source["model"] in {m["id"] for m in provider["models"]}, "model_not_configured", "Choose an explicitly configured model.")
        require(source["region"] == provider["region"], "region_mismatch", "Voice region must match the explicit provider configuration.")
        preset, vid = self.core.add_voice(body["name"], body["category"], source, body["revision"], settings=body.get('settings'))
        return {"preset": preset, "project_voice_id": vid}

    def question(self, question_id):
        obj = self.questions.read(question_id)
        return {**{key: copy.deepcopy(obj.get(key)) for key in ("question_id", "job_id", "roles", "status", "expires_at", "answer", 'role_metadata', 'assignments')},
                'claimed': obj.get('claimed_by') is not None}

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
            v.shape(body, {"question_id", "assignments", 'revision'}, {"question_id", "assignments"})
            return self.questions.submit(body["question_id"], body["assignments"], revision=body.get('revision'))
        if action == 'assignments':
            v.shape(body, {'question_id', 'role_id', 'project_voice_id', 'revision'}, {'question_id', 'role_id', 'project_voice_id', 'revision'})
            return self.questions.assign(body['question_id'], body['role_id'], body['project_voice_id'], body['revision'])
        if action == "complete":
            v.shape(body, set())
            return self.questions.management_complete()
        require(False, "not_found", "Unknown management action.")
