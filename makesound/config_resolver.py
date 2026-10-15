"""Pure, offline resolution shared by every Harness."""

import copy

from . import validation as v
from .errors import MakeSoundError, require
from .preset_store import merge

SUGGESTIONS = {"export_mode": "paragraph", "subtitle_enabled": True, "subtitle_type": "sentence",
               "script_processing": "narration_only", "audio_format": "mp3",
               "pause": {"sentence_ms": 300, "paragraph_ms": 800}}
VOICE_DEFAULTS = {"speed": 1.0, "volume": 1.0, "pitch": 0, "emotion": "auto"}


def validate_request(request):
    v.shape(request, {"job_id", "voice_alias", "voice", "voice_settings", "project_settings", "constraints", "studio_submission", "assignments"})
    if "voice_alias" in request:
        v.name(request["voice_alias"])
    if "voice" in request:
        v.voice(request["voice"])
    require(not ("voice" in request and "voice_alias" in request), message="Choose an explicit voice or alias, not both.")
    if "job_id" in request:
        v.identifier(request["job_id"])
    v.voice_settings(request.get("voice_settings", {}))
    v.project_settings(request.get("project_settings", {}))
    constraints = request.get("constraints", {})
    v.shape(constraints, {"gender", "tags"})
    if "gender" in constraints:
        require(isinstance(constraints["gender"], str) and constraints["gender"] in {"female", "male", "other"})
    if "tags" in constraints:
        require(isinstance(constraints["tags"], list))
        for tag in constraints["tags"]:
            v.text(tag, 80)
    if "assignments" in request:
        require(isinstance(request["assignments"], list) and len(request["assignments"]) <= 10000)
        targets = set()
        for assignment in request["assignments"]:
            v.shape(assignment, {"target", "voice_alias", "voice"}, {"target"})
            v.identifier(assignment["target"])
            require(assignment["target"] not in targets, message="Duplicate assignment target.")
            targets.add(assignment["target"])
            validate_request({k: item for k, item in assignment.items() if k != "target"})
    sub = request.get("studio_submission")
    if sub is not None:
        v.shape(sub, {"status", "question_id", "answer_id", "job_id", "project_id", "voice", "voice_settings", "project_settings", "clear_constraints"}, {"status"})
        require(sub["status"] in {"pending", "applied", "cancelled", "expired"})
        if sub["status"] == "applied":
            for key in ("question_id", "answer_id", "job_id", "project_id", "voice"):
                require(key in sub, message="Applied Studio selection requires transaction identity.")
            for key in ("question_id", "answer_id", "job_id", "project_id"):
                v.identifier(sub[key])
            v.voice(sub["voice"])
            v.voice_settings(sub.get("voice_settings", {}))
            v.project_settings(sub.get("project_settings", {}))
            require(type(sub.get("clear_constraints", False)) is bool)
    v.no_secrets(request)


def _concrete(selected, project, assets, region):
    selected = copy.deepcopy(selected)
    ref = selected["ref"]
    if ref["kind"] == "project_alias":
        require(ref["name"] in project["named_voices"], "missing_alias", "Default alias does not exist.")
        target = project["named_voices"][ref["name"]]
        selected = merge(target, {k: x for k, x in selected.items() if k != "ref"})
        ref = selected["ref"]
    availability = "unknown"
    if ref["kind"] == "global_asset":
        require(ref["asset_id"] in assets, "missing_asset", "Referenced global asset does not exist.")
        asset = assets[ref["asset_id"]]
        availability = asset["availability"]
        attrs = merge(asset["metadata"], selected.get("metadata", {}))
        concrete = {"provider": asset["provider"], "region": asset["region"], "voice_id": asset["voice_id"], "asset_id": ref["asset_id"]}
    else:
        concrete = {key: ref[key] for key in ("provider", "region", "voice_id")}
        attrs = selected.get("metadata", {})
    if concrete["region"] == "configured":
        require(region in v.REGIONS, "region_required", "Voice reference requires an explicit configured region.")
        concrete["region"] = region
    require(region is None or concrete["region"] == region, "region_mismatch", "Selected voice belongs to another configured region.")
    require(availability not in {"expired", "unavailable"}, "voice_unavailable", "Voice requires repair; no substitute was selected.")
    concrete.update(voice_settings=merge(VOICE_DEFAULTS, selected.get("voice_settings", {})), metadata=attrs, availability=availability)
    return concrete


def resolve(project, global_preset, registry, request=None, *, region=None):
    request = copy.deepcopy({} if request is None else request)
    validate_request(request)
    if region is not None:
        require(region in v.REGIONS, "invalid_region", "Unknown configured region.")
    sub = request.get("studio_submission")
    result = {"schema_version": "1.2", "status": "needs_setup", "readiness": "local_configuration_only",
              "project_id": project.get("project_id"), "revision": project["revision"],
              "network_calls": 0, "bindings": [], "warnings": [], "missing_fields": [], "filters": request.get("constraints", {})}
    if sub:
        if sub["status"] != "applied":
            return {**result, "status": "needs_studio", "reason": "studio_" + sub["status"]}
        require(sub["job_id"] == request.get("job_id") and sub["project_id"] == project.get("project_id"),
                "answer_mismatch", "Studio submission is not associated with this project and Job.")
        result["warnings"].append("studio_submission_is_caller_supplied_M1_not_a_verified_M3_transaction")
        result["studio_identity"] = {k: sub[k] for k in ("answer_id", "question_id", "job_id", "project_id")}
    settings = merge(SUGGESTIONS, global_preset["project_settings"])
    settings = merge(settings, project["project_settings"])
    settings = merge(settings, request.get("project_settings", {}))
    if sub:
        settings = merge(settings, sub.get("project_settings", {}))
    v.project_settings(settings)
    result["project_settings"] = settings
    constraints = {} if sub and sub.get("clear_constraints") else request.get("constraints", {})
    if constraints != request.get("constraints", {}):
        result["warnings"].append("constraints_explicitly_cleared_by_submitted_selection")

    def choose(selector):
        alias = selector.get("voice_alias")
        if sub:
            selected, source = sub["voice"], "studio_applied"
        elif "voice" in selector:
            selected, source = selector["voice"], "explicit_voice"
        elif alias is not None:
            alias = v.name(alias)
            if alias not in project["named_voices"]:
                filters = copy.deepcopy(request.get("constraints", {}))
                if "gender" not in filters:
                    if "男声" in alias:
                        filters["gender"] = "male"
                    elif "女声" in alias:
                        filters["gender"] = "female"
                return None, {"status": "needs_studio", "reason": "missing_alias", "missing_alias": alias, "filters": filters}
            selected, source = project["named_voices"][alias], "project_alias"
        elif project["default_voice"] is not None:
            selected, source = project["default_voice"], "project_default"
        elif global_preset["default_voice"] is not None:
            selected, source = global_preset["default_voice"], "global_default"
        else:
            return None, {"status": "needs_setup", "reason": "no_default", "missing_fields": ["voice"]}
        try:
            concrete = _concrete(selected, project, registry["assets"], region)
        except MakeSoundError as exc:
            return None, {"status": "needs_studio", "reason": exc.code}
        attrs = concrete["metadata"]
        matches = (not constraints.get("gender") or (bool(attrs.get("source")) and attrs.get("gender") == constraints["gender"]))
        matches = matches and set(constraints.get("tags", [])) <= set(attrs.get("tags", []))
        if not matches:
            return None, {"status": "needs_studio", "reason": "voice_constraints_unverified_or_conflicting", "filters": constraints}
        concrete["voice_settings"] = merge(concrete["voice_settings"], request.get("voice_settings", {}))
        if sub:
            concrete["voice_settings"] = merge(concrete["voice_settings"], sub.get("voice_settings", {}))
        v.voice_settings(concrete["voice_settings"])
        return {"voice": concrete, "source": source, "requested_alias": alias}, None

    targets = request.get("assignments") or [{"target": "default"}]
    for assignment in targets:
        selector = {k: item for k, item in request.items() if k in {"voice", "voice_alias"}}
        selector.update({k: item for k, item in assignment.items() if k in {"voice", "voice_alias"}})
        # An assignment's explicit selector replaces the task-level selector.
        if "voice_alias" in assignment:
            selector.pop("voice", None)
        if "voice" in assignment:
            selector.pop("voice_alias", None)
        binding, failure = choose(selector)
        if failure:
            return {**result, **failure, "bindings": []}
        result["bindings"].append({"target": assignment["target"], **binding})
    if not settings.get("model"):
        return {**result, "missing_fields": ["model"], "reason": "model_not_configured"}
    result["status"] = "ready"
    result["warnings"].append("provider_voice_availability_and_model_compatibility_NOT_RUN")
    return result
