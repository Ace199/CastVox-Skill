"""Install the no-synthesis host binding MCP in an explicit Desktop config."""
import argparse
import json
from pathlib import Path
import sys
import uuid

from .errors import MakeSoundError, require
from .storage import atomic_write, file_lock, project_root, read_json, reject_links


def install(desktop_config, allowed_root, *, backup_dir=None, generic_bridge=False):
    require(sys.version_info >= (3, 11), 'python_unsupported', 'Install with host Python 3.11+.')
    config = Path(desktop_config)
    require(config.is_absolute() and config.is_file(), 'invalid_config', 'Select the existing config actually used by Claude Desktop.')
    reject_links(config)
    root = Path(allowed_root)
    require(root.is_absolute(), 'unsafe_path', 'Configure an explicit absolute host project root.')
    reject_links(root)
    root.mkdir(parents=True, exist_ok=True)
    root = project_root(root)
    scripts = Path(__file__).resolve().parent.parent / 'scripts'
    entry = scripts / ('host_bridge.py' if generic_bridge else 'claude_host_bridge.py')
    require(entry.is_file(), 'runtime_not_configured', 'Host bridge entry point is missing.')
    spec = {'command': sys.executable, 'args': ['-X', 'utf8', str(entry), '--allowed-root', str(root)],
            'env': {'PYTHONUTF8': '1'}}
    name = 'host_bridge' if generic_bridge else 'soundmaker_host'
    if generic_bridge:
        spec['args'].extend(['--application', 'soundmaker'])
    backups = (Path(backup_dir) if backup_dir else Path.home() / '.config/soundmaker/backups/claude-host').resolve()
    with file_lock(backups / 'desktop-config.lock'):
        data = read_json(config)
        require(isinstance(data, dict) and isinstance(data.get('mcpServers', {}), dict),
                'invalid_config', 'Expected a Desktop configuration object with an optional mcpServers map.')
        servers = data.get('mcpServers', {})
        previous = servers.get(name)
        require(previous is None or previous == spec, 'config_conflict', 'A different bridge entry was preserved; review it before replacing.')
        legacy = servers.get('soundmaker_host') if generic_bridge else None
        expected_legacy = {'command': sys.executable,
            'args': ['-X', 'utf8', str(scripts / 'claude_host_bridge.py'), '--allowed-root', str(root)],
            'env': {'PYTHONUTF8': '1'}}
        require(legacy is None or legacy == expected_legacy, 'config_conflict',
                'A different legacy bridge configuration was preserved; select its existing interpreter and project root or review it explicitly.')
        if previous == spec and legacy is None:
            return {'status': 'already_configured', 'desktop_config': str(config), 'allowed_root': str(root),
                    'app_load_verified': False, 'requires_reload': True}
        before = config.read_bytes()
        backups.mkdir(parents=True, exist_ok=True)
        backup = backups / ('desktop-' + uuid.uuid4().hex + '.json')
        with backup.open('xb') as stream:
            stream.write(before)
        require(config.read_bytes() == before, 'revision_conflict', 'Desktop changed the config; retry after it becomes idle.')
        data.setdefault('mcpServers', {})[name] = spec
        if legacy is not None:
            del data['mcpServers']['soundmaker_host']
        atomic_write(config, data)
    return {'status': 'configured', 'desktop_config': str(config), 'allowed_root': str(root), 'backup': str(backup),
            'app_load_verified': False, 'requires_reload': True}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--desktop-config', required=True)
    parser.add_argument('--allowed-root', required=True)
    args = parser.parse_args()
    try:
        print(json.dumps(install(args.desktop_config, args.allowed_root), ensure_ascii=False))
        return 0
    except MakeSoundError as error:
        print(json.dumps({'status': 'error', 'code': error.code, 'message': str(error)}))
        return 2


if __name__ == '__main__':
    raise SystemExit(main())
