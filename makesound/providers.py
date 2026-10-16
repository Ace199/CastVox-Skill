"""Shared validation and Fake adapter. Real adapters require explicit injection."""
import math
import wave
from decimal import Decimal

from .errors import MakeSoundError, require
from . import validation as v


FAKE_CAPABILITIES = {
    "speed": {"verified": True, "min": .5, "max": 2, "step": .1, "neutral": 1.0,
              "unit": "multiplier", "api_field": "speed"},
    "pitch": {"verified": True, "min": -12, "max": 12, "step": 1, "neutral": 0,
              "unit": "semitone", "api_field": "pitch"},
}

MINIMAX_DOCUMENTED_MODELS = frozenset({'speech-2.8-hd', 'speech-2.8-turbo', 'speech-2.6-hd', 'speech-2.6-turbo',
                                      'speech-02-hd', 'speech-02-turbo', 'speech-01-hd', 'speech-01-turbo'})
MINIMAX_CAPABILITIES = {
    'speed': {'supported': True, 'verified': True, 'min': .5, 'max': 2, 'step': 'any', 'range_step': .01,
              'neutral': 1.0, 'unit': '倍', 'api_field': 'speed', 'verification': 'official_docs_and_contract_tests',
              'live_verified': False, 'source_url': 'https://platform.minimax.cn/docs/api-reference/speech-t2a-http'},
    'pitch': {'supported': True, 'verified': True, 'min': -12, 'max': 12, 'step': 1,
              'neutral': 0, 'unit': '整数刻度', 'api_field': 'pitch', 'verification': 'official_docs_and_contract_tests',
              'live_verified': False, 'source_url': 'https://platform.minimax.cn/docs/api-reference/speech-t2a-http'},
}


def capabilities(source):
    import copy
    if source['provider'] == 'fake':
        return copy.deepcopy(FAKE_CAPABILITIES)
    if source['provider'] == 'minimax' and source['region'] == 'cn' and source['model'] in MINIMAX_DOCUMENTED_MODELS:
        return copy.deepcopy(MINIMAX_CAPABILITIES)
    return {}


def source_valid(source):
    v.shape(source, {"provider", "region", "model", "voice_id"},
            {"provider", "region", "model", "voice_id"})
    require(source["provider"] in {"fake", "minimax", "volcengine"}, "unknown_provider", "Unknown provider.")
    for val in source.values():
        v.text(val)
    v.no_secrets(source)
    if source["provider"] == "fake":
        require(source["region"] == "test" and source["model"] == "fake-v1", "model_not_configured", "Unknown Fake model or region.")
    else:
        require(source["region"] in {"cn", "international"}, "region_mismatch", "Provider region must be explicit.")


def effective(source, saved=None, override=None):
    source_valid(source)
    saved = {} if saved is None else saved
    override = {} if override is None else override
    v.shape(saved, {"speed", "pitch"})
    v.shape(override, {"speed", "pitch"})
    values = {**saved, **override}
    v.shape(values, {"speed", "pitch"})
    caps = capabilities(source)
    out = {}
    for key, val in values.items():
        require(key in caps and caps[key]["verified"], "parameter_unverified", "Parameter capability is not verified for this model.")
        cap = caps[key]
        require(type(val) in (int, float) and math.isfinite(val)
                and cap["min"] <= val <= cap["max"], "parameter_range", "Parameter is outside verified range.")
        require(cap['step'] == 'any' or (Decimal(str(val)) - Decimal(str(cap["min"]))) % Decimal(str(cap["step"])) == 0,
                "parameter_step", "Parameter does not match verified step.")
    for key, cap in caps.items():
        # Real legacy records/snapshots intentionally omitted Provider defaults.
        # Do not rewrite those to explicit values when adding new descriptors.
        if source['provider'] != 'fake' and key not in values:
            continue
        raw = values.get(key, cap["neutral"])
        out[key] = float(raw) if key == "speed" else int(raw)
    return out


def duration(path):
    """Measure decoded PCM frames; never trust an extension or supplied duration."""
    try:
        with wave.open(str(path), "rb") as audio:
            require(audio.getcomptype() == "NONE" and audio.getframerate() > 0,
                    "invalid_audio", "Audio is not supported PCM WAV.")
            frames = audio.getnframes()
            payload = audio.readframes(frames)
            require(len(payload) == frames * audio.getnchannels() * audio.getsampwidth(),
                    "invalid_audio", "Audio is truncated.")
            return frames / audio.getframerate()
    except (OSError, EOFError, wave.Error):
        raise MakeSoundError("invalid_audio", "Audio could not be measured.") from None


class FakeProvider:
    """Deterministic PCM silence with exact sentence timing; not speech quality QA."""
    def __init__(self):
        self.calls = 0
        self.fail_once = set()
        self.uncertain_once = set()

    def synthesize(self, chunk, path):
        require(chunk["source"]["provider"] == "fake", "provider_not_implemented", "This adapter only accepts fake sources.")
        self.calls += 1
        if chunk["chunk_id"] in self.uncertain_once:
            self.uncertain_once.remove(chunk["chunk_id"])
            raise MakeSoundError("billing_unknown", "Request outcome is unknown; explicit reconciliation is required.")
        if chunk["chunk_id"] in self.fail_once:
            self.fail_once.remove(chunk["chunk_id"])
            raise MakeSoundError("safe_retry", "Fake request failed before synthesis.")
        rate = 8000
        speech_frames = round(chunk["fake_duration_seconds"] * rate)
        pause_frames = round(chunk["pause_ms"] * rate / 1000)
        with wave.open(str(path), "wb") as audio:
            audio.setnchannels(1)
            audio.setsampwidth(2)
            audio.setframerate(rate)
            audio.writeframes(b"\x00\x00" * (speech_frames + pause_frames))
        return {"duration_seconds": duration(path), "speech_seconds": speech_frames / rate}


def adapter_for(source, fake, minimax=None):
    if source["provider"] == "fake":
        return fake
    if source['provider'] == 'minimax' and minimax is not None:
        return minimax
    raise MakeSoundError("provider_not_implemented", "Provider synthesis adapter is not implemented; no fallback was selected.")


def performance_directives(source, directives=None):
    directives = {} if directives is None else directives
    require(isinstance(directives, dict) and set(directives) <= {'emotion'},
            'unsupported_directive', 'Only documented emotion directives are supported.')
    if not directives:
        return {}
    allowed = {'happy', 'sad', 'angry', 'fearful', 'disgusted', 'surprised', 'calm'}
    if source['model'] in {'speech-2.6-hd', 'speech-2.6-turbo'}:
        allowed |= {'fluent', 'whisper'}
    require(source['provider'] == 'minimax' and source['model'] in MINIMAX_DOCUMENTED_MODELS
            and isinstance(directives.get('emotion'), str) and directives['emotion'] in allowed,
            'unsupported_directive', 'Emotion is unsupported by the selected model.')
    return dict(directives)
