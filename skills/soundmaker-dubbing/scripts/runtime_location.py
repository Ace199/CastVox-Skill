"""Locate an installed runtime by skill link or local install record; never scan."""
import json
from pathlib import Path
import sys


def _runtime_root(path):
    return ((path / 'makesound/__init__.py').is_file()
            and (path / 'studio_v16_server.py').is_file()
            and (path / 'skills/soundmaker-dubbing/SKILL.md').is_file())


def locate(skill_dir=None, install_record=None):
    skill = Path(skill_dir) if skill_dir is not None else Path(__file__).parent.parent
    root = skill.resolve().parent.parent
    if _runtime_root(root):
        return root
    record = (Path(install_record) if install_record is not None
              else Path.home() / '.config/soundmaker/runtime.json')
    try:
        data = json.loads(record.read_text(encoding='utf-8-sig'))
        value = data.get('runtime_root') if isinstance(data, dict) else None
        if isinstance(value, str) and value and Path(value).is_absolute():
            root = Path(value).resolve(strict=True)
            if _runtime_root(root):
                return root
    except (OSError, ValueError):
        pass
    raise ValueError('Runtime link or local installation record is missing or invalid.')


def main():
    if sys.version_info < (3, 11):
        print(json.dumps({'status': 'error', 'code': 'python_unsupported',
                          'message': 'Use a Python 3.11+ interpreter; macOS may require python3 or the project virtual environment.'}))
        return 2
    try:
        result = {'status': 'ready', 'runtime_root': str(locate()),
                  'python_executable': sys.executable}
    except (OSError, ValueError):
        print(json.dumps({'status': 'error', 'code': 'runtime_not_configured',
                          'message': 'Repair the skill link or local installation record; no search was performed.'}))
        return 2
    print(json.dumps(result, ensure_ascii=False))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
