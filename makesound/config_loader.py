"""Read-only credentials. The secret is never included in repr or summaries."""

import os
from dataclasses import dataclass, field
from urllib.parse import urlsplit

from .errors import MakeSoundError, require
from .storage import read_json

HOST_REGIONS = {"api.minimax.cn": "cn", "api.minimaxi.com": "cn",
                "api-bj.minimaxi.com": "cn", "api.minimax.io": "international"}


@dataclass(frozen=True)
class MiniMaxConfig:
    region: str
    base_url: str
    api_key: str = field(repr=False)
    sources: dict = field(default_factory=dict)

    def summary(self):
        return {"region": self.region, "base_url": self.base_url,
                "api_key_present": bool(self.api_key), "sources": self.sources,
                "authentication": "NOT RUN", "network_calls": 0}


def load_minimax(path, environ=None):
    env = os.environ if environ is None else environ
    obj = read_json(path) if path.exists() else {}
    require(isinstance(obj, dict), "invalid_credentials", "MiniMax configuration root must be an object.")
    values, sources = {}, {}
    for key in ("api_key", "region", "base_url"):
        envkey = "MINIMAX_" + key.upper()
        values[key] = env[envkey] if envkey in env else obj.get(key)
        sources[key] = "environment" if envkey in env else "file"
    require(all(isinstance(x, str) and x.strip() for x in values.values()),
            "config_missing", "MiniMax api_key, region and base_url must be explicitly configured.")
    require(values["api_key"] == values["api_key"].strip() and not any(c.isspace() for c in values["api_key"]),
            "invalid_credentials", "MiniMax key has invalid formatting.")
    region = values["region"].strip().lower()
    require(region in {"cn", "international"}, "invalid_region", "Region must be cn or international.")
    try:
        url = urlsplit(values["base_url"])
        valid = (url.scheme == "https" and url.hostname in HOST_REGIONS and url.port in (None, 443)
                 and url.username is None and url.password is None and not url.query and not url.fragment
                 and url.path in ("", "/"))
    except ValueError:
        valid = False
    require(valid, "invalid_base_url", "MiniMax base URL must be an approved HTTPS regional origin without credentials, path or query.")
    require(HOST_REGIONS[url.hostname] == region, "region_mismatch", "MiniMax region and base URL conflict.")
    return MiniMaxConfig(region, "https://" + url.hostname, values["api_key"], sources)
