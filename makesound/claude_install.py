"""One-command host installation of the skill and generic task bridge."""
import argparse
import json
from pathlib import Path
import sys

if sys.version_info < (3, 11):
    print(json.dumps({'status': 'error', 'code': 'python_unsupported', 'message': 'Run the host installer with Python 3.11+.'}))
    raise SystemExit(2)

from .claude_cowork import link_skill
from .claude_host_setup import install as install_mcp
from .errors import MakeSoundError, require
from .storage import read_json, reject_links


def profile_candidates():
    home = Path.home()
    if sys.platform == 'win32':
        return [home / 'AppData/Local/Claude-3p', home / 'AppData/Roaming/Claude']
    if sys.platform == 'darwin':
        return [home / 'Library/Application Support/Claude']
    return []


def _plugins(base):
    parent = base / 'local-agent-mode-sessions/skills-plugin'
    if not parent.is_dir():
        return []
    reject_links(parent)
    found = []
    # Two known account/session levels only. Never recurse over user files.
    for candidate in parent.glob('*/*'):
        if not candidate.is_dir():
            continue
        reject_links(candidate)
        if (candidate / 'manifest.json').is_file() and (candidate / '.claude-plugin/plugin.json').is_file():
            marker = read_json(candidate / '.claude-plugin/plugin.json')
            if marker.get('name') == 'anthropic-skills' and (candidate / 'skills').is_dir():
                found.append(candidate)
    return found


def discover(*, app_data=None, plugin_root=None):
    bases = [Path(app_data)] if app_data is not None else profile_candidates()
    matches = []
    for base in bases:
        require(base.is_absolute(), 'unsafe_path', 'Use an absolute Claude App data directory.')
        config = base / 'claude_desktop_config.json'
        if not config.is_file():
            continue
        reject_links(config)
        if plugin_root is not None:
            candidate = Path(plugin_root)
            require(candidate.is_absolute() and candidate.resolve().is_relative_to(base.resolve()),
                    'unsafe_path', 'Select the skill plugin inside the chosen Claude App data directory.')
            candidates = [candidate] if candidate in _plugins(base) else []
        else:
            candidates = _plugins(base)
        matches.extend((base, item) for item in candidates)
    require(bool(matches), 'installation_not_found',
            'No supported local Cowork skill store and config pair found. Open Claude Cowork first; for another App location pass --app-data. This installer does not upload account skills.')
    require(len(matches) == 1, 'ambiguous_installation',
            'Multiple Claude profiles/accounts found. Select --app-data and, when needed, --plugin-root; no files were changed.')
    return matches[0]


def install(*, app_data=None, plugin_root=None, allowed_root=None, backup_dir=None, check=False):
    require(sys.version_info >= (3, 11), 'python_unsupported', 'Run the installer on the host with Python 3.11+.')
    base, plugin = discover(app_data=app_data, plugin_root=plugin_root)
    config = base / 'claude_desktop_config.json'
    existing = read_json(config)
    require(isinstance(existing, dict) and isinstance(existing.get('mcpServers', {}), dict),
            'invalid_config', 'Expected a Desktop config object with an optional mcpServers map.')
    inherited_root = None
    scripts = Path(__file__).resolve().parent.parent / 'scripts'
    for name, script, tail in [('host_bridge', 'host_bridge.py', ['--application', 'soundmaker']),
                               ('soundmaker_host', 'claude_host_bridge.py', [])]:
        entry = existing.get('mcpServers', {}).get(name)
        if isinstance(entry, dict):
            args = entry.get('args')
            if (isinstance(args, list) and len(args) == 5 + len(tail)
                    and args[:4] == ['-X', 'utf8', str(scripts / script), '--allowed-root']
                    and args[5:] == tail and isinstance(args[4], str)):
                expected = {'command': sys.executable, 'args': args, 'env': {'PYTHONUTF8': '1'}}
                if entry == expected:
                    inherited_root = args[4]
                    break
    root = Path(allowed_root or inherited_root or Path.home() / 'Documents/SoundMaker/projects')
    require(root.is_absolute(), 'unsafe_path', 'Use an absolute host project directory.')
    backups = Path(backup_dir) if backup_dir else Path.home() / '.config/soundmaker/backups'
    result = {'status': 'plan', 'app_data': str(base), 'plugin_root': str(plugin), 'allowed_root': str(root),
              'mcp_server': 'host_bridge', 'application': 'soundmaker',
              'app_load_verified': False, 'requires_reload': True}
    if check:
        return result
    result['skill'] = link_skill(plugin, backup_dir=backups / 'claude-cowork')
    try:
        result['mcp'] = install_mcp(base / 'claude_desktop_config.json', root,
                                    backup_dir=backups / 'claude-host', generic_bridge=True)
    except (MakeSoundError, OSError) as error:
        return {**result, 'status': 'partial_install', 'code': getattr(error, 'code', 'installation_failed'),
                'message': 'Skill link is installed, but MCP configuration failed. Existing configuration was preserved; correct the conflict and rerun.'}
    return {**result, 'status': 'installed', 'next_step': 'Reload local MCP or reopen Claude, then call host_bridge_status. No audio was generated.'}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--app-data')
    parser.add_argument('--plugin-root')
    parser.add_argument('--allowed-root')
    parser.add_argument('--check', action='store_true', help='Resolve installation targets only; do not write or claim App connectivity.')
    args = parser.parse_args()
    try:
        result = install(**vars(args))
        print(json.dumps(result, ensure_ascii=False))
        return 2 if result['status'] == 'partial_install' else 0
    except (MakeSoundError, OSError, ValueError) as error:
        print(json.dumps({'status': 'error', 'code': getattr(error, 'code', 'installation_failed'),
                          'message': str(error) if isinstance(error, MakeSoundError) else 'Cannot read or update the selected local installation.'}))
        return 2


if __name__ == '__main__':
    raise SystemExit(main())
