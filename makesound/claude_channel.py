"""Session-owned stdio MCP channel; accepts only registered, durable Answers."""
import json
import secrets
import sys
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from .core_v16 import ProjectCore
from .errors import MakeSoundError, require
from .harness_resume import completion_message
from .questions import Questions
from .storage import atomic_write, file_lock, read_json


class Channel:
    def __init__(self, emit):
        self.emit = emit
        self.token = secrets.token_urlsafe(32)
        self.registered = {}
        self.sent = set()
        self.lock = threading.Lock()
        self.server = ThreadingHTTPServer(('127.0.0.1', 0), Handler)
        self.server.channel = self
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.server.shutdown()
        self.server.server_close()
        self.thread.join(timeout=2)

    def register(self, project, qid):
        core = ProjectCore(project)
        question = Questions(core).read(qid)
        require(question['status'] == 'pending', 'answer_immutable', 'Register before submitting the Answer.')
        target = {'harness': 'claude_channel', 'port': self.server.server_port,
                  'token': self.token, 'question_id': qid}
        path = core.managed_path(f'.makesound/studio/{qid}/wake-target.json')
        with self.lock, file_lock(path.with_suffix('.lock')):
            if qid in self.registered:
                require(self.registered[qid].root == core.root, 'session_mismatch', 'Question already registered.')
            if path.exists():
                require(read_json(path) == target, 'session_mismatch', 'Question belongs to another session.')
            else:
                atomic_write(path, target)
            self.registered[qid] = core
        return {'registered': True, 'question_id': qid, 'harness': 'claude_channel',
                'note': 'Keep this Claude session open. Registration alone does not prove channels are enabled.'}

    def deliver(self, token, qid, answer_id):
        require(isinstance(token, str) and secrets.compare_digest(token, self.token), 'forbidden', 'Invalid sender.')
        with self.lock:
            require(qid in self.registered, 'session_mismatch', 'Question is not owned by this channel.')
            core = self.registered[qid]
            question = Questions(core).read(qid)
            require(question['status'] == 'answered' and question.get('answer', {}).get('answer_id') == answer_id,
                    'not_answered', 'The saved Answer does not match.')
            key = (qid, answer_id)
            if key not in self.sent:
                # Unknown write outcome must never cause a blind duplicate notification.
                self.sent.add(key)
                self.emit({'jsonrpc': '2.0', 'method': 'notifications/claude/channel', 'params': {
                    'content': completion_message(core, qid, answer_id),
                    'meta': {'question_id': qid, 'answer_id': answer_id}}})
        return {'status': 'queued'}

    def rpc(self, method, params):
        if method == 'initialize':
            return {'protocolVersion': params.get('protocolVersion', '2025-03-26'),
                    'capabilities': {'tools': {}, 'experimental': {'claude/channel': {}}},
                    'serverInfo': {'name': 'soundmaker', 'version': '1.0.0'},
                    'instructions': 'For SoundMaker, register the pending binding Question in this session before opening Studio. '
                    'Binding notifications are not paid synthesis approval. Respond to events here in the original terminal.'}
        if method == 'ping':
            return {}
        if method == 'tools/list':
            return {'tools': [
                {'name': 'soundmaker_register_binding', 'description': 'Register a pending SoundMaker Question to this exact Claude session before launching Studio.',
                 'inputSchema': {'type': 'object', 'properties': {'project': {'type': 'string'}, 'question_id': {'type': 'string'}},
                                 'required': ['project', 'question_id'], 'additionalProperties': False}},
                {'name': 'soundmaker_test_wake', 'description': 'Only when the user requests a wake test: emit a fixed harmless event in this session after two seconds. No binding or synthesis.',
                 'inputSchema': {'type': 'object', 'properties': {}, 'additionalProperties': False}}]}
        if method == 'tools/call':
            try:
                args = params.get('arguments', {})
                if params['name'] == 'soundmaker_register_binding':
                    require(set(args) == {'project', 'question_id'}, 'invalid_request', 'Expected project and question_id.')
                    value = self.register(args['project'], args['question_id'])
                elif params['name'] == 'soundmaker_test_wake':
                    require(not args, 'invalid_request', 'No arguments expected.')
                    def test_event():
                        try:
                            self.emit({'jsonrpc': '2.0', 'method': 'notifications/claude/channel', 'params': {
                                'content': 'SoundMaker wake test SM_CLAUDE_WAKE_01. This is not binding or paid synthesis authorization. '
                                           'Do not call tools. Reply in this terminal: 收到唤醒测试 SM_CLAUDE_WAKE_01。',
                                'meta': {'test_id': 'SM_CLAUDE_WAKE_01'}}})
                        except (OSError, ValueError):
                            pass
                    timer = threading.Timer(2, test_event)
                    timer.daemon = True
                    timer.start()
                    value = {'test_scheduled': True, 'note': 'Wait for the channel event; scheduling is not proof of delivery.'}
                else:
                    raise ValueError('Unknown tool')
                return {'content': [{'type': 'text', 'text': json.dumps(value, ensure_ascii=False)}]}
            except Exception as exc:
                code = exc.code if isinstance(exc, MakeSoundError) else 'invalid_request'
                return {'isError': True, 'content': [{'type': 'text', 'text': code}]}
        raise ValueError('Method not found')


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *args):
        pass

    def do_POST(self):
        try:
            require(self.path == '/binding-complete' and not self.headers.get('Origin') and
                    not self.headers.get('Transfer-Encoding'), 'forbidden', 'Unsupported request.')
            length = int(self.headers.get('Content-Length', '-1'))
            require(0 < length < 4096, 'invalid_request', 'Invalid size.')
            token = self.headers.get('Authorization', '').removeprefix('Bearer ')
            body = json.loads(self.rfile.read(length))
            require(set(body) == {'question_id', 'answer_id'}, 'invalid_request', 'Unexpected fields.')
            value = self.server.channel.deliver(token, body['question_id'], body['answer_id'])
            status = 200
        except Exception:
            value, status = {'status': 'rejected'}, 400
        raw = json.dumps(value).encode('utf-8')
        self.send_response(status)
        self.send_header('Content-Type', 'application/json')
        self.send_header('Content-Length', str(len(raw)))
        self.end_headers()
        self.wfile.write(raw)


def main():
    sys.stdin.reconfigure(encoding='utf-8')
    sys.stdout.reconfigure(encoding='utf-8')
    output_lock = threading.Lock()
    def emit(value):
        with output_lock:
            print(json.dumps(value, ensure_ascii=False), flush=True)
    with Channel(emit) as channel:
        for line in sys.stdin:
            try:
                request = json.loads(line)
                if 'id' not in request:
                    continue
                result = channel.rpc(request['method'], request.get('params', {}))
                emit({'jsonrpc': '2.0', 'id': request['id'], 'result': result})
            except Exception:
                emit({'jsonrpc': '2.0', 'id': None, 'error': {'code': -32600, 'message': 'Invalid request'}})


if __name__ == '__main__':
    main()
