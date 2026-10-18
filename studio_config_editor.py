"""Local Studio file-opening helper. Never reads or overwrites credentials."""
import json
import os
from pathlib import Path
import subprocess
import sys


def config_path(provider, config_dir=None):
    if provider not in ('minimax', 'volcengine'):
        raise ValueError('未知厂商')
    if config_dir is not None:
        return Path(config_dir) / provider / 'config.json'
    return Path.home() / '.config' / provider / 'config.json'


def launch_editor(path):
    if sys.platform == 'darwin':
        # Force a text editor rather than the file's arbitrary JSON association.
        # open returns after LaunchServices accepts the request, not after editing.
        try:
            subprocess.run(['/usr/bin/open', '-t', str(path.resolve())],
                           check=True, capture_output=True, timeout=10)
        except (OSError, subprocess.SubprocessError):
            raise OSError('The macOS text editor could not be opened.') from None
        return
    if os.name != 'nt':
        raise OSError('unsupported platform')
    # Explicit text editor: never execute a JSON file through its association.
    editor = Path(os.environ.get('SystemRoot', r'C:\Windows')) / 'System32' / 'notepad.exe'
    subprocess.Popen([str(editor), str(path.resolve())], close_fds=True)


def open_config(provider, config_dir=None, opener=None):
    path = config_path(provider, config_dir)
    created = False
    if not path.exists():
        path.parent.mkdir(parents=True, exist_ok=True)
        try:
            # Exclusive create also protects an existing file in concurrent requests.
            with path.open('x', encoding='utf-8') as file:
                template = {'api_key': 'YOUR_API_KEY_HERE', 'region': 'cn',
                           '_api_key_comment': 'MiniMax API key. Replace the placeholder with your own key.',
                           '_region_comment': 'API region: cn = Mainland China, international = International. Select the region that matches your MiniMax API account.',
                           'base_url': 'https://api.minimax.cn',
                           '_base_url_comment': 'API origin. Use https://api.minimax.cn for cn or https://api.minimax.io for international. Must match region.',
                           'models': ['speech-2.8-hd', 'speech-2.8-turbo',
                                      'speech-2.6-hd', 'speech-2.6-turbo',
                                      'speech-02-hd', 'speech-02-turbo',
                                      'speech-01-hd', 'speech-01-turbo'],
                           '_models_comment': 'Available TTS models for CastVox. Keep model IDs supported by your MiniMax API account. Comment fields are for reference only and are not sent in API requests.',
                           'default_model': 'speech-2.8-hd',
                           '_default_model_comment': 'Default TTS model. Must match a model ID in models.'} if provider == 'minimax' else {
                    'auth_mode': 'api_key', 'api_key': 'YOUR_VOLCENGINE_API_KEY_HERE',
                    'region': 'cn', 'base_url': 'https://openspeech.bytedance.com',
                    'tts_endpoint': '/api/v3/tts/unidirectional', 'resource_id': 'seed-tts-2.0',
                    'models': ['seed-tts-2.0-standard'], 'default_model': 'seed-tts-2.0-standard'}
                json.dump(template, file, ensure_ascii=False, indent=2)
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


def open_default_config(project_root, opener=None):
    path = Path(project_root).resolve() / '.makesound' / 'preset.v1.6.json'
    if not path.is_file():
        return {'ok': False, 'message': '默认配置尚未创建；请先重新读取项目。'}
    try:
        (opener or launch_editor)(path)
    except OSError:
        return {'ok': False, 'message': '无法打开本地编辑器，请检查系统权限后重试'}
    return {'ok': True, 'message': '已请求在编辑器中打开默认配置；保存后点击“重新读取项目”'}
