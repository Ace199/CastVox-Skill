"""Strict local protocol validation; these are not MiniMax request schemas."""

import math
import re
import unicodedata

from .errors import require

REGIONS = {"cn", "international"}
AVAILABILITY = {"unknown", "pending_activation", "available", "unavailable", "expired"}
SETTINGS = {"model", "export_mode", "subtitle_enabled", "subtitle_type", "script_processing", "audio_format", "pause"}
VOICE_SETTINGS = {"speed", "volume", "pitch", "emotion"}
SENSITIVE = re.compile(r"api.?key|access.?key|authorization|password|secret|token|credential", re.I)


def no_secrets(value):
    if isinstance(value, dict):
        require(all(isinstance(k, str) and not SENSITIVE.search(k) for k in value),
                "sensitive_data", "Secrets and credential fields cannot be stored in business data.")
        for item in value.values():
            no_secrets(item)
    elif isinstance(value, list):
        for item in value:
            no_secrets(item)
    elif isinstance(value, str):
        require(not re.search(r"(?i)bearer\s+\S+|\bsk-[a-zA-Z0-9_-]{12,}", value),
                "sensitive_data", "Credential-like values cannot be stored in business data.")
    elif isinstance(value, float):
        require(math.isfinite(value))


def shape(value, allowed, required=()):
    require(isinstance(value, dict), message="Expected an object.")
    require(set(value) <= set(allowed) and set(required) <= set(value), message="Missing or unsupported object fields.")


def text(value, maximum=256):
    require(isinstance(value, str) and 0 < len(value) <= maximum and value == value.strip()
            and not any(ord(c) < 32 for c in value), message="Invalid text field.")


def name(value):
    text(value, 120)
    return unicodedata.normalize("NFC", value)


def identifier(value):
    text(value)
    require(re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_-]{0,255}", value) is not None, message="Invalid identifier.")


def reference(value, allow_alias=False):
    require(isinstance(value, dict))
    kind = value.get("kind")
    if kind == "provider_voice":
        shape(value, {"kind", "provider", "region", "voice_id"}, {"kind", "provider", "region", "voice_id"})
        require(value["provider"] == "minimax", message="Unsupported provider.")
        require(value["region"] in REGIONS | {"configured"}, message="Unsupported region.")
        identifier(value["voice_id"])
    elif kind == "global_asset":
        shape(value, {"kind", "asset_id"}, {"kind", "asset_id"})
        identifier(value["asset_id"])
    else:
        require(allow_alias and kind == "project_alias", message="Unsupported voice reference.")
        shape(value, {"kind", "name"}, {"kind", "name"})
        require(value["name"] == name(value["name"]), message="Alias must be NFC-normalized.")


def voice_settings(value):
    shape(value, VOICE_SETTINGS)
    for key, lo, hi, strict_lo in [("speed", .5, 2, False), ("volume", 0, 10, True), ("pitch", -12, 12, False)]:
        if key in value:
            x = value[key]
            require(type(x) in (int, float) and math.isfinite(x) and lo <= x <= hi
                    and (not strict_lo or x > lo), message="Voice parameter is out of range.")
    if "emotion" in value:
        text(value["emotion"], 32)


def metadata(value):
    shape(value, {"gender", "tags", "source", "description", "checked_at"})
    if "gender" in value:
        require(value["gender"] in {"female", "male", "unknown", "other"}, message="Invalid gender metadata.")
    if "tags" in value:
        require(isinstance(value["tags"], list) and len(value["tags"]) <= 50)
        for tag in value["tags"]:
            text(tag, 80)
    for key in ("source", "description", "checked_at"):
        if key in value:
            text(value[key], 2000)
    if value.get("gender", "unknown") != "unknown" or value.get("tags"):
        require(bool(value.get("source")), message="Voice attributes require a provenance source.")
    no_secrets(value)


def voice(value, allow_alias=False):
    shape(value, {"ref", "voice_settings", "metadata"}, {"ref"})
    reference(value["ref"], allow_alias)
    voice_settings(value.get("voice_settings", {}))
    metadata(value.get("metadata", {}))
    no_secrets(value)


def project_settings(value):
    shape(value, SETTINGS)
    for key, options in {"export_mode": {"whole", "paragraph", "sentence"},
                         "subtitle_type": {"sentence", "word"},
                         "script_processing": {"narration_only", "verbatim", "rewrite"},
                         "audio_format": {"mp3", "wav", "flac", "pcm"}}.items():
        if key in value:
            require(isinstance(value[key], str) and value[key] in options, message="Invalid project setting.")
    if "subtitle_enabled" in value:
        require(type(value["subtitle_enabled"]) is bool)
    if "model" in value:
        text(value["model"], 128)
    if "pause" in value:
        shape(value["pause"], {"sentence_ms", "paragraph_ms"})
        for x in value["pause"].values():
            require(type(x) is int and 0 <= x <= 99990, message="Invalid pause duration.")


def preset(value, global_scope=False):
    shape(value, {"schema_version", "revision", "project_id", "project_settings", "default_voice", "named_voices", "audit", "compatibility"},
          {"schema_version", "revision", "project_settings", "default_voice", "named_voices", "audit"})
    require(value["schema_version"] == "1.2", "schema_version", "Unsupported schema version.")
    require(type(value["revision"]) is int and value["revision"] >= 0)
    if "project_id" in value:
        identifier(value["project_id"])
    project_settings(value["project_settings"])
    require(isinstance(value["named_voices"], dict))
    require(not global_scope or not value["named_voices"], message="Global defaults do not own project aliases.")
    for alias, item in value["named_voices"].items():
        require(alias == name(alias), message="Alias must be normalized.")
        voice(item)
    if value["default_voice"] is not None:
        voice(value["default_voice"], not global_scope)
        ref = value["default_voice"]["ref"]
        if ref["kind"] == "project_alias":
            require(ref["name"] in value["named_voices"], "dangling_default", "Default references a missing alias.")
    require(isinstance(value["audit"], list))
    no_secrets(value)
