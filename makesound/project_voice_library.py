"""Project-only aliases. Rebind requires CAS plus explicit confirmation."""

import copy

from . import validation as v
from .errors import require
from .preset_store import now


class ProjectVoiceLibrary:
    def __init__(self, preset):
        self.preset = preset

    def add(self, alias, voice, revision, *, set_default=False, settings=None):
        alias = v.name(alias)
        v.voice(voice)
        v.project_settings(settings or {})

        def change(obj):
            require(alias not in obj["named_voices"], "alias_exists", "Alias already exists; use confirmed rebind.")
            obj["named_voices"][alias] = copy.deepcopy(voice)
            if set_default:
                obj["default_voice"] = {"ref": {"kind": "project_alias", "name": alias}, "voice_settings": {}}
            from .preset_store import merge
            obj["project_settings"] = merge(obj["project_settings"], settings or {})
            obj["audit"].append({"action": "alias_add", "alias": alias, "at": now()})
        return self.preset.update(change, revision)[0]

    def rebind(self, alias, voice, revision, *, confirmed=False, expected_old=None):
        alias = v.name(alias)
        v.voice(voice)
        require(confirmed and expected_old is not None, "confirmation_required", "Rebinding requires confirmation of the previous reference and revision.")

        def change(obj):
            require(alias in obj["named_voices"], "not_found", "Alias does not exist.")
            old = obj["named_voices"][alias]
            require(old["ref"] == expected_old, "reference_conflict", "Alias target changed; reload and confirm again.")
            obj["named_voices"][alias] = copy.deepcopy(voice)
            obj["audit"].append({"action": "alias_rebind", "alias": alias, "old": old["ref"], "new": voice["ref"], "at": now()})
        return self.preset.update(change, revision)[0]

    def rename(self, alias, new_name, revision):
        alias, new_name = v.name(alias), v.name(new_name)

        def change(obj):
            require(alias in obj["named_voices"], "not_found", "Alias does not exist.")
            require(new_name not in obj["named_voices"], "alias_exists", "New alias already exists.")
            obj["named_voices"][new_name] = obj["named_voices"].pop(alias)
            default = obj["default_voice"]
            if default and default["ref"] == {"kind": "project_alias", "name": alias}:
                default["ref"]["name"] = new_name
            obj["audit"].append({"action": "alias_rename", "alias": alias, "new_name": new_name, "at": now()})
        return self.preset.update(change, revision)[0]

    def remove(self, alias, revision):
        alias = v.name(alias)

        def change(obj):
            require(alias in obj["named_voices"], "not_found", "Alias does not exist.")
            default = obj["default_voice"]
            require(not default or default["ref"] != {"kind": "project_alias", "name": alias}, "referenced", "Alias is referenced by the project default.")
            del obj["named_voices"][alias]
            obj["audit"].append({"action": "alias_remove", "alias": alias, "at": now()})
        return self.preset.update(change, revision)[0]
