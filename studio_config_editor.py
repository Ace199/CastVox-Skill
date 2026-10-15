"""Local Studio file-opening helper. Never reads or overwrites credentials."""
import json
import os
from pathlib import Path
import subprocess


def config_path(provider, config_dir=None):
    if provider not in ('minimax', 'volcengine'):
        raise ValueError('未知厂商')
    if config_dir is not None:
        return Path(config_dir) / provider / 'config.json'
    if provider == 'minimax':
        return Path.home() / '.config' / 'minimax' / 'config.json'
    return None


def launch_editor(path):
    if os.name != 'nt':
        raise OSError('unsupported platform')
    # Explicit text editor: never execute a JSON file through its association.
    editor = Path(os.environ.get('SystemRoot', r'C:\Windows')) / 'System32' / 'notepad.exe'
    subprocess.Popen([str(editor), str(path.resolve())], close_fds=True)


def open_config(provider, config_dir=None, opener=None):
    path = config_path(provider, config_dir)
    if path is None:
        raise ValueError('火山引擎配置路径尚未接入')
    created = False
    if not path.exists():
        if provider != 'minimax':
            raise ValueError('火山引擎配置模板尚未接入，请先配置其文件路径和格式')
        path.parent.mkdir(parents=True, exist_ok=True)
        try:
            # Exclusive create also protects an existing file in concurrent requests.
            with path.open('x', encoding='utf-8') as file:
                json.dump({'api_key': 'write your own keys', 'region': 'cn',
                           'base_url': 'https://api.minimax.cn',
                           'models': [], 'default_model': None}, file, ensure_ascii=False, indent=2)
                file.write('\n')
            created = True
        except FileExistsError:
            pass
    if not path.is_file():
        raise ValueError('配置路径不是文件')
    try:
        (opener or launch_editor)(path)
    except OSError:
        return {'ok': False, 'created': created, 'message': ('配置已创建，但' if created else '') + '无法打开本地编辑器，请检查系统权限后重试'}
    return {'ok': True, 'created': created,
            'message': '已创建配置并请求在编辑器中打开；填写后点击“重新读取模型”' if created else '已请求在编辑器中打开配置；保存后点击“重新读取模型”'}
