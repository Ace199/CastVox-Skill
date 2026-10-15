"""Loopback Studio: redacted model discovery and explicit local config opening.

No provider client or outbound networking. Existing credentials are never rewritten.
"""
import argparse
import json
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlsplit

WEB = Path(__file__).resolve().parent / 'web'
PROVIDERS = (
    dict(id='minimax', name='MiniMax', identifier_label='MiniMax Voice ID',
         url='https://www.minimax.cn/audio', identifier_pattern=r'^[A-Za-z0-9][A-Za-z0-9_-]{0,255}$',
         help='在 MiniMax 官网选择声音并复制 Voice ID；官网调节的参数不会随 ID 携带。',
         support='配置可用 · 合成未接入', identifier_hint='字母、数字、下划线或连字符，最长 256 字符'),
    dict(id='volcengine', name='火山引擎', identifier_label='音色标识（speaker）',
         url='https://docs.volcengine.com/docs/DoubaoVoice/Tasksubmission?lang=zh',
         identifier_pattern=None,
         help='参考豆包语音官方文档及控制台获取 speaker；resource_id 等字段尚待 Adapter 设计，不能套用 MiniMax 请求体。',
         support='配置支持待接入 · 不可合成', identifier_hint='只保存配置草稿；尚未实现厂商级格式或可用性验证'),
)

from makesound.provider_config import safe_text, read_models
from studio_config_editor import config_path, open_config

def provider_catalog(config_dir=None):
    result = []
    for spec in PROVIDERS:
        # Volcengine's credential location/schema is deliberately not invented.
        path = config_path(spec['id'], config_dir)
        editable = path is not None and (spec['id'] == 'minimax' or path.is_file())
        result.append({**spec, **read_models(path), 'source': 'mock_fixture' if config_dir else 'local_readonly', 'region': 'configured',
                       'config_edit': {'available': editable, 'reason': '' if editable else '火山引擎配置路径或模板尚未接入'}})
    return {'providers': result, 'business_mode': 'mock', 'network_calls': 0}

class Handler(SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(WEB), **kwargs)

    def log_message(self, *_):
        pass  # No raw paths, request fields, configuration values or secrets in logs.

    def end_headers(self):
        # Local ES modules are edited independently; never mix cached old exports
        # with a newly loaded importer during prototype development.
        self.send_header('Cache-Control', 'no-store')
        super().end_headers()

    def do_GET(self):
        origin = f'http://127.0.0.1:{self.server.server_port}'
        if self.headers.get('Host') not in {f'127.0.0.1:{self.server.server_port}', f'localhost:{self.server.server_port}'} or self.headers.get('Origin') not in (None, origin, origin.replace('127.0.0.1', 'localhost')):
            self.send_error(403); return
        if urlsplit(self.path).path == '/api/providers':
            payload = json.dumps(provider_catalog(self.server.config_dir), ensure_ascii=False).encode('utf-8')
            self.send_response(200); self.send_header('Content-Type', 'application/json; charset=utf-8'); self.send_header('Cache-Control', 'no-store'); self.send_header('X-Content-Type-Options', 'nosniff'); self.end_headers(); self.wfile.write(payload); return
        target = Path(self.translate_path(self.path)).resolve()
        if not target.is_relative_to(WEB) or target.is_dir() and urlsplit(self.path).path != '/' or target.relative_to(WEB).parts and target.relative_to(WEB).parts[0] not in ('index.html', 'css', 'js', 'assets') and target != WEB:
            self.send_error(404); return
        # Force a full response even for clients holding an old Last-Modified value.
        if 'If-Modified-Since' in self.headers:
            del self.headers['If-Modified-Since']
        super().do_GET()

    def list_directory(self, path):
        self.send_error(404); return None

    def do_HEAD(self):
        self.send_error(405)

    def do_POST(self):
        # Only same-origin JSON from our UI; no arbitrary file paths or contents accepted.
        host = self.headers.get('Host')
        if (host not in {f'127.0.0.1:{self.server.server_port}', f'localhost:{self.server.server_port}'}
                or self.headers.get('Origin') != f'http://{host}'
                or self.headers.get('X-Studio-Action') != 'open-config'
                or self.headers.get('Content-Type') != 'application/json'):
            self.send_error(403); return
        if self.path != '/api/providers/open-config':
            self.send_error(404); return
        try:
            length = int(self.headers.get('Content-Length', '0'))
            if not 0 < length <= 256:
                raise ValueError('无效请求')
            body = json.loads(self.rfile.read(length))
            if not isinstance(body, dict) or set(body) != {'provider'} or body['provider'] not in ('minimax', 'volcengine'):
                raise ValueError('无效厂商配置请求')
            result = open_config(body['provider'], self.server.config_dir)
        except ValueError:
            result = {'ok': False, 'message': '该厂商配置路径或模板尚未接入，或请求格式无效'}
        except OSError:
            result = {'ok': False, 'message': '无法创建或打开配置文件，请检查目录权限'}
        payload = json.dumps(result, ensure_ascii=False).encode('utf-8')
        self.send_response(200); self.send_header('Content-Type', 'application/json; charset=utf-8'); self.send_header('Cache-Control', 'no-store'); self.end_headers(); self.wfile.write(payload)

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--port', type=int, default=8766)
    parser.add_argument('--config-dir', type=Path, help='Explicit isolated provider model fixtures; never changes home credentials')
    args = parser.parse_args()
    server = ThreadingHTTPServer(('127.0.0.1', args.port), Handler)
    server.config_dir = args.config_dir.resolve() if args.config_dir else None
    print(f'Voice Studio: http://127.0.0.1:{args.port}/ (business writes: Mock; config: open/create on user request)', flush=True)
    server.serve_forever()

if __name__ == '__main__':
    main()
