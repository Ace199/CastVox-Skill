"""Stable JSON CLI for M1. There are no network or speech-generation commands."""

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

from . import __version__, validation as v
from .config_loader import load_minimax
from .config_resolver import validate_request
from .errors import MakeSoundError, require
from .jobs import validate_snapshot
from .preset_store import for_project
from .service import MakeSound
from .storage import Locations, read_json
from .voice_registry import asset_summary, validate_registry


class Parser(argparse.ArgumentParser):
    def error(self, message):
        # argparse's default error can echo secrets supplied as an unknown option/value.
        raise MakeSoundError("cli_usage", "Invalid command arguments; use --help for supported options.")


def build_parser():
    parser = Parser(prog="makesound", description="MakeSoundSkill M1: offline data/configuration only")
    parser.add_argument("--version", action="version", version=__version__)
    commands = parser.add_subparsers(dest="command", required=True, parser_class=Parser)
    common = argparse.ArgumentParser(add_help=False)
    common.add_argument("--json", action="store_true", help="JSON is always the output format")
    common.add_argument("--project", help="Explicit absolute trusted project root")
    common.add_argument("--region", choices=["cn", "international"], help="Explicit region for configured/legacy references; does not read credentials")
    common.add_argument("--data-dir", type=Path)
    common.add_argument("--global-config", type=Path)
    common.add_argument("--minimax-config", type=Path)

    def leaf(parent, name):
        return parent.add_parser(name, parents=[common])

    def group(parent, name, dest):
        return parent.add_parser(name).add_subparsers(dest=dest, required=True, parser_class=Parser)

    leaf(commands, "doctor")
    config = group(commands, "config", "operation")
    leaf(config, "resolve").add_argument("--request", type=Path)
    leaf(config, "show").add_argument("--global", dest="global_scope", action="store_true")
    for operation in ("set-default", "settings"):
        p = leaf(config, operation)
        p.add_argument("--global", dest="global_scope", action="store_true")
        p.add_argument("--expected-revision", type=int, required=True)
        p.add_argument("--settings", type=Path, required=operation == "settings")
        if operation == "set-default":
            p.add_argument("--voice", type=Path, required=True, help="Voice object JSON; not a raw ID")
    p = leaf(config, "migrate")
    p.add_argument("--global", dest="global_scope", action="store_true")
    p.add_argument("--confirm", action="store_true")

    voices = group(commands, "voices", "category")
    assets = group(voices, "assets", "operation")
    p = leaf(assets, "list")
    p.add_argument("--show-local-paths", action="store_true")
    p = leaf(assets, "register")
    p.add_argument("--file", type=Path, required=True)
    p.add_argument("--sample", type=Path)
    for op in ("rename", "delete", "references", "sample-delete"):
        p = leaf(assets, op)
        p.add_argument("asset_id")
        if op == "rename":
            p.add_argument("--name", required=True)
        if op in {"rename", "delete"}:
            p.add_argument("--expected-revision", type=int, required=True)
        if op in {"delete", "sample-delete"}:
            p.add_argument("--confirm", action="store_true")
        if op == "delete":
            p.add_argument("--known-projects-only", action="store_true", help="Acknowledge unregistered/external project references cannot be discovered")
    aliases = group(voices, "aliases", "operation")
    leaf(aliases, "list")
    for op in ("add", "rebind", "rename", "remove"):
        p = leaf(aliases, op)
        p.add_argument("name")
        p.add_argument("--expected-revision", type=int, required=True)
        if op in {"add", "rebind"}:
            p.add_argument("--voice", type=Path, required=True)
        if op == "add":
            p.add_argument("--set-default", action="store_true")
            p.add_argument("--settings", type=Path)
        if op == "rebind":
            p.add_argument("--confirm", action="store_true")
            p.add_argument("--expected-old-ref", type=Path, required=True)
        if op == "rename":
            p.add_argument("--new-name", required=True)
    p = leaf(voices, "list")
    p.add_argument("--source", choices=["official"], default="official")

    jobs = group(commands, "jobs", "operation")
    p = leaf(jobs, "snapshot")
    p.add_argument("--request", type=Path)
    p.add_argument("--source-hash", default="")
    p = leaf(jobs, "status")
    p.add_argument("job_id")
    schema = group(commands, "schema", "operation")
    p = leaf(schema, "validate")
    p.add_argument("--kind", choices=["preset", "asset-registry", "request", "snapshot"], required=True)
    p.add_argument("--file", type=Path, required=True)
    return parser


def safe_preset(obj):
    return {k: value for k, value in obj.items() if k not in {"compatibility", "audit"}}


def doctor(locations):
    result = {"status": "ok", "version": __version__, "python": sys.version.split()[0],
              "network_calls": 0, "provider_authentication": "NOT RUN", "checks": {}}
    try:
        result["minimax"] = load_minimax(locations.minimax_config).summary()
    except MakeSoundError as exc:
        result["minimax"] = {"status": "invalid", "code": exc.code, "api_key_disclosed": False}
        result["status"] = "attention_required"
    for command in ("ffmpeg", "ffprobe", "git", "codex", "claude"):
        found = shutil.which(command)
        result["checks"][command] = {"available_on_path": bool(found)}
    result["checks"]["python_supported"] = sys.version_info >= (3, 11)
    if not result["checks"]["python_supported"]:
        result["status"] = "attention_required"
    return result


def dispatch(args):
    defaults = Locations.default()
    locations = Locations((args.data_dir or defaults.data_dir).absolute(),
                          (args.global_config or defaults.global_config).absolute(),
                          (args.minimax_config or defaults.minimax_config).absolute())
    if args.command == "doctor":
        return doctor(locations)
    app = MakeSound(locations, region=args.region)
    if args.command == "config":
        if args.operation == "resolve":
            return app.resolve(args.project, read_json(args.request) if args.request else None)
        require(bool(args.project) != bool(args.global_scope), "scope_required", "Choose exactly one of --project or --global.")
        store = for_project(args.project, args.region) if args.project else app.global_preset
        if args.operation == "show":
            return {"status": "ok", "preset": safe_preset(store.read())}
        if args.operation == "migrate":
            require(args.confirm, "confirmation_required", "Confirm non-destructive migration export.")
            with app.editing(args.project):
                return {"status": "migration_exported", **store.export_migration(args.region)}
        settings = read_json(args.settings) if args.settings else {}
        if args.operation == "set-default":
            updated = app.set_default(read_json(args.voice), settings, args.expected_revision, args.project)
        else:
            updated = app.patch_settings(settings, args.expected_revision, args.project)
        return {"status": "saved", "revision": updated["revision"], "preset": safe_preset(updated)}
    if args.command == "voices":
        if args.category == "list":
            raise MakeSoundError("not_implemented", "Official voice queries are deferred to the real Provider phase; no request was sent.")
        if args.category == "assets":
            if args.operation == "list":
                obj = app.registry.read()
                return {"status": "ok", "revision": obj["revision"], "assets": [asset_summary(x, args.show_local_paths) for x in obj["assets"].values()]}
            if args.operation == "register":
                obj, item = app.register_asset(read_json(args.file), args.sample)
                return {"status": "registered_local_only", "revision": obj["revision"], "asset": asset_summary(item), "network_calls": 0}
            if args.operation == "references":
                return {"status": "ok", "references": app.asset_references(args.asset_id), "scope": "managed_project_inventory_global_defaults_and_jobs"}
            if args.operation == "sample-delete":
                obj = app.sample_delete(args.asset_id, args.confirm)
            elif args.operation == "delete":
                obj = app.delete_asset(args.asset_id, args.expected_revision, confirmed=args.confirm, known_projects_confirmed=args.known_projects_only)
            else:
                with app.editing():
                    obj = app.registry.rename(args.asset_id, args.name, args.expected_revision)
            return {"status": "saved", "revision": obj["revision"], "network_calls": 0}
        require(args.project is not None, "project_required", "Project aliases require an explicit project root.")
        if args.operation == "list":
            obj = for_project(args.project, args.region).read()
            return {"status": "ok", "revision": obj["revision"], "project_id": obj["project_id"], "named_voices": obj["named_voices"]}
        kwargs = {}
        if args.operation in {"add", "rebind"}:
            kwargs["voice"] = read_json(args.voice)
        if args.operation == "add":
            kwargs.update(set_default=args.set_default, settings=read_json(args.settings) if args.settings else {})
        elif args.operation == "rebind":
            kwargs.update(confirmed=args.confirm, expected_old=read_json(args.expected_old_ref))
        elif args.operation == "rename":
            kwargs["new_name"] = args.new_name
        updated = app.alias(args.operation, args.project, args.name, args.expected_revision, **kwargs)
        return {"status": "saved", "revision": updated["revision"], "preset": safe_preset(updated)}
    if args.command == "jobs":
        if args.operation == "snapshot":
            return app.snapshot(args.project, read_json(args.request) if args.request else None, args.source_hash)
        return app.jobs.load(args.job_id)
    validators = {"preset": v.preset, "asset-registry": validate_registry, "request": validate_request, "snapshot": validate_snapshot}
    validators[args.kind](read_json(args.file))
    return {"status": "valid", "kind": args.kind}


def main(argv=None):
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    try:
        args = build_parser().parse_args(argv)
        result = dispatch(args)
        print(json.dumps({"schema_version": "1.2", **result}, ensure_ascii=False, allow_nan=False))
        return 0 if result.get("status") not in {"needs_setup", "needs_studio", "invalid", "attention_required"} else 2
    except MakeSoundError as exc:
        print(json.dumps({"schema_version": "1.2", "status": "error", "code": exc.code, "message": str(exc)}, ensure_ascii=False))
        print("makesound: " + exc.code, file=sys.stderr)
        return 2
    except (OSError, ValueError, TypeError, KeyError, RecursionError):
        print(json.dumps({"schema_version": "1.2", "status": "error", "code": "invalid_local_data", "message": "Local input or storage operation failed; sensitive details were suppressed."}))
        print("makesound: invalid_local_data", file=sys.stderr)
        return 2
