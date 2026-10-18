"""Opt-in local-build Cowork skill link. Requires an explicitly verified plugin root.

This is a local development installation, not a Claude account upload or a
guarantee that a Desktop version will follow links or resume conversations.
"""
import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
import stat
from pathlib import Path
import subprocess
import uuid

from .errors import MakeSoundError, require
from .storage import atomic_write, file_lock, read_json


def _directory_link(source, target):
    if os.name != 'nt':
        target.symlink_to(source, target_is_directory=True)
        return
    powershell = Path(os.environ.get('SystemRoot', r'C:\Windows')) / 'System32/WindowsPowerShell/v1.0/powershell.exe'
    script = "$ErrorActionPreference='Stop'; $d=[Console]::In.ReadToEnd()|ConvertFrom-Json; New-Item -ItemType Junction -Path $d.target -Target $d.source | Out-Null"
    result = subprocess.run([str(powershell), '-NoProfile', '-NonInteractive', '-Command', script],
                            input=json.dumps({'source': str(source), 'target': str(target)}).encode('ascii'),
                            capture_output=True, timeout=15, creationflags=subprocess.CREATE_NO_WINDOW)
    require(result.returncode == 0, 'link_failed', 'Cannot create the local Cowork skill directory link.')


def _is_junction(path):
    # Path.is_junction was added in Python 3.12. The mount-point reparse tag
    # identifies our Windows directory junctions on supported Python 3.11 too.
    try:
        return os.name == 'nt' and path.lstat().st_reparse_tag == stat.IO_REPARSE_TAG_MOUNT_POINT
    except FileNotFoundError:
        return False


def link_skill(plugin_root, *, backup_dir=None):
    plugin = Path(plugin_root)
    require(plugin.is_absolute() and plugin.is_dir(), 'invalid_plugin', 'Provide the exact existing Cowork skill plugin directory.')
    plugin = plugin.resolve()
    require(read_json(plugin / '.claude-plugin/plugin.json').get('name') == 'anthropic-skills',
            'invalid_plugin', 'Expected the existing Desktop skill plugin; no directories were searched.')
    require((plugin / 'skills').is_dir(), 'invalid_plugin', 'The plugin has no skills directory.')
    source = Path(__file__).resolve().parent.parent / 'skills/soundmaker-dubbing'
    skill_text = (source / 'SKILL.md').read_text(encoding='utf-8')
    description = next(line[len('description: '):] for line in skill_text.splitlines() if line.startswith('description: '))
    target = plugin / 'skills/soundmaker-dubbing'
    manifest_path = plugin / 'manifest.json'
    backup_root = (Path(backup_dir) if backup_dir else Path.home() / '.config/soundmaker/backups/claude-cowork').resolve()
    require(backup_root != plugin and not backup_root.is_relative_to(plugin),
            'unsafe_path', 'Manifest backups must be outside the plugin directory.')
    lock_name = hashlib.sha256(str(plugin).encode()).hexdigest()[:16] + '.lock'
    with file_lock(backup_root / lock_name):
        manifest = read_json(manifest_path)
        require(isinstance(manifest.get('skills'), list), 'invalid_plugin', 'Expected an existing skill manifest.')
        entries = [item for item in manifest['skills'] if item.get('name') == 'soundmaker-dubbing']
        require(len(entries) <= 1 and all(item.get('creatorType') == 'user' and item.get('syncManaged') is False for item in entries),
                'skill_conflict', 'Existing managed skill entry cannot be replaced by a local link.')
        exists = target.exists() or target.is_symlink() or _is_junction(target)
        require(not exists or ((target.is_symlink() or _is_junction(target))
                               and target.resolve() == source.resolve()),
                'skill_conflict', 'Existing skill directory or different link was preserved. Back it up explicitly before replacement.')
        public = {'skill_path': str(target), 'runtime_root': str(source.parent.parent),
                  'host_load_verified': False, 'resume_verified': False}
        if exists and entries and entries[0].get('enabled') is True:
            return {**public, 'status': 'already_linked'}
        # Preserve exact original bytes before either installation mutation.
        before = manifest_path.read_bytes()
        backup_root.mkdir(parents=True, exist_ok=True)
        backup = backup_root / ('manifest-' + uuid.uuid4().hex + '.json')
        with backup.open('xb') as stream:
            stream.write(before)
        created = False
        try:
            if not exists:
                _directory_link(source, target)
                created = True
            require(target.resolve() == source.resolve(), 'link_failed', 'Installed skill link target differs.')
            require(hashlib.sha256((target / 'SKILL.md').read_bytes()).digest() == hashlib.sha256((source / 'SKILL.md').read_bytes()).digest(),
                    'link_failed', 'Installed skill content differs.')
            require(manifest_path.read_bytes() == before, 'revision_conflict', 'Desktop changed its skill manifest; retry after it becomes idle.')
            entry = {'skillId': 'soundmaker-dubbing', 'name': 'soundmaker-dubbing', 'description': description,
                     'creatorType': 'user', 'syncManaged': False,
                     'updatedAt': datetime.now(timezone.utc).isoformat(), 'enabled': True}
            manifest['skills'] = [entry if item.get('name') == 'soundmaker-dubbing' else item for item in manifest['skills']]
            if not entries:
                manifest['skills'].append(entry)
            manifest['lastUpdated'] = int(datetime.now(timezone.utc).timestamp() * 1000)
            atomic_write(manifest_path, manifest)
        except Exception:
            if created:
                # Remove the link itself only; never recurse into its target.
                if os.name == 'nt':
                    os.rmdir(target)
                else:
                    target.unlink()
            raise
        return {**public, 'status': 'linked', 'manifest_backup': str(backup)}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--plugin-root', required=True, help='Exact verified local Cowork skill plugin directory; never auto-discovered.')
    args = parser.parse_args(argv)
    try:
        print(json.dumps(link_skill(args.plugin_root), ensure_ascii=False))
        return 0
    except MakeSoundError as error:
        print(json.dumps({'status': 'error', 'code': error.code, 'message': str(error)}))
    except (OSError, subprocess.SubprocessError):
        print(json.dumps({'status': 'error', 'code': 'installation_failed', 'message': 'Local link installation failed; existing skill copies were not overwritten.'}))
    return 2


if __name__ == '__main__':
    raise SystemExit(main())
