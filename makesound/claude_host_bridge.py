"""Host-owned MCP binding pages. No synthesis, shell execution, or VM paths."""
import argparse
import hashlib
import json
from pathlib import Path
import re
import sys
import threading
import uuid

from .core_v16 import ProjectCore
from .cowork_task import wait_for_binding
from .errors import MakeSoundError, require
from .harness_resume import register_tool_result
from .offline_harness import prepare
from .questions import Questions
from .storage import atomic_write, file_lock, project_root, read_json
from .studio_backend import StudioBackend
from .studio_session import _editable_question
from .ui_locale import resolve_ui_language
from studio_v16_server import create_server


def _key(value):
    require(isinstance(value, str) and re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_-]{0,79}', value),
            'invalid_key', 'Use a project/request key containing letters, digits, underscores or hyphens.')
    require(value.upper().split('.')[0] not in {'CON', 'PRN', 'AUX', 'NUL',
            *('COM' + str(i) for i in range(1, 10)), *('LPT' + str(i) for i in range(1, 10))},
            'invalid_key', 'Reserved project/request key.')
    return value


def _tool(name, description, properties, required=()):
    return {'name': name, 'description': description, 'inputSchema': {
        'type': 'object', 'properties': properties, 'required': list(required), 'additionalProperties': False}}


class Bridge:
    def __init__(self, allowed_roots):
        require(bool(allowed_roots), 'project_required', 'Configure at least one explicit host project root.')
        self.roots = [project_root(value) for value in allowed_roots]
        self.lock = threading.RLock()
        self.records, self.handles = {}, {}
        self.waiters = set()
        self.closed = False

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.close()

    def tools(self):
        string = {'type': 'string'}
        location = {'project_key': string, 'root_index': {'type': 'integer', 'minimum': 0}}
        return [
            _tool('soundmaker_host_status', 'Check the host bridge. Does not scan files or generate audio.', {}),
            _tool('soundmaker_prepare_binding', 'Create/reuse a host Question from the supplied script and open its binding page. '
                  'Use the same request_id for retries; project_key is a logical name, never a VM or Windows path.',
                  {**location, 'request_id': string, 'script': {'type': 'object'}, 'ui_language': string},
                  ('project_key', 'request_id', 'script')),
            _tool('soundmaker_open_binding', 'Reopen a known host Question, preserving roles and bindings. '
                  'Answered Questions open an editable revision; this does not authorize generation.',
                  {**location, 'question_id': string, 'ui_language': string}, ('project_key', 'question_id')),
            _tool('soundmaker_read_binding', 'Read a known host Question and its saved Answer after reconnecting or when the user says Done. '
                  'Does not create a revision, launch a page, or generate audio.',
                  {**location, 'question_id': string}, ('project_key', 'question_id')),
            _tool('soundmaker_wait_binding', 'After showing the host URL, keep this original request waiting for the saved Answer. '
                  'waiting means wait again with the same handle; binding_saved includes the real Answer. No out-of-band messages.',
                  {'handle': string, 'timeout': {'type': 'number', 'minimum': 0, 'maximum': 55}}, ('handle',)),
            _tool('soundmaker_smoke_binding', 'Only for a user-requested no-fee binding test. Creates a Fake role on the host; '
                  'show the URL and use soundmaker_wait_binding. No audio generation.',
                  {'request_id': string, 'ui_language': string}, ('request_id',))]

    def _core(self, key, index=0, *, create=True):
        key = _key(key)
        require(type(index) is int and 0 <= index < len(self.roots), 'invalid_root', 'Unknown configured host project root.')
        folder = self.roots[index] / key
        # Validate existing ancestors before creating anything through a link.
        from .storage import reject_links
        reject_links(folder)
        if create:
            folder.mkdir(exist_ok=True)
        else:
            require(folder.is_dir(), 'not_found', 'The known host project does not exist.')
        return ProjectCore(folder)

    def call(self, name, args, *, cancel_event=None):
        spec = next((tool for tool in self.tools() if tool['name'] == name), None)
        require(spec is not None, 'unknown_tool', 'Unknown host binding tool.')
        schema = spec['inputSchema']
        require(isinstance(args, dict) and set(args) <= set(schema['properties'])
                and set(schema['required']) <= set(args), 'invalid_request', 'Unexpected or missing tool arguments.')
        require(not self.closed, 'bridge_closed', 'Host bridge is closed; saved bindings are preserved.')
        if name == 'soundmaker_host_status':
            return {'status': 'ready', 'execution_environment': 'host', 'python_version': sys.version.split()[0],
                    'project_root_count': len(self.roots), 'synthesis_available': False,
                    'continuation': 'pending_mcp_tool_result', 'receiver_verified': False}
        if name == 'soundmaker_wait_binding':
            with self.lock:
                record = self.handles.get(args['handle']) if isinstance(args['handle'], str) else None
                require(record is not None, 'unknown_handle', 'Unknown bridge handle; reopen the known project Question.')
                event = cancel_event if cancel_event is not None else threading.Event()
                self.waiters.add(event)
            try:
                result = wait_for_binding(record['core'], record['qid'], timeout=args.get('timeout', 50), cancel_event=event)
                if result['status'] == 'binding_saved':
                    result['answer'] = Questions(record['core']).read(record['qid'])['answer']
                return result
            finally:
                with self.lock:
                    self.waiters.discard(event)
        with self.lock:
            if name == 'soundmaker_smoke_binding':
                core = self._core('soundmaker-smoke')
                voices = core.read()['voices']
                voice = next((vid for vid, item in voices.items() if not item['deleted'] and
                              item['name'] == 'Host smoke voice (no synthesis)'), None)
                if voice is None:
                    _, voice = core.add_voice('Host smoke voice (no synthesis)', 'other', {
                        'provider': 'fake', 'region': 'test', 'model': 'fake-v1', 'voice_id': 'FAKE_HOST_SMOKE'}, core.read()['revision'])
                script = {'roles': ['test_narrator'], 'segments': [{'paragraph_id': 'p1', 'sentence_id': 's1',
                          'role_id': 'test_narrator', 'text': '仅测试主机网页绑定与原请求继续，不生成音频。'}]}
                result = self._prepare(core, args['request_id'], script, args.get('ui_language'), fake=True)
                return {**result, 'project_voice_id': voice, 'role_id': 'test_narrator', 'offline_only': True}
            require(name != 'soundmaker_prepare_binding' or args['project_key'] != 'soundmaker-smoke',
                    'reserved_project', 'The smoke project is reserved for no-fee tests.')
            core = self._core(args['project_key'], args.get('root_index', 0), create=name == 'soundmaker_prepare_binding')
            core.read()  # Keep host project identity checks; never rewrite a VM preset.
            if name == 'soundmaker_prepare_binding':
                return self._prepare(core, args['request_id'], args['script'], args.get('ui_language'))
            if name == 'soundmaker_read_binding':
                question = Questions(core).read(args['question_id'])
                return {'status': 'binding_saved' if question['status'] == 'answered' else question['status'],
                        'question_id': question['question_id'], 'answer': question.get('answer'),
                        'project_key': core.root.name, 'host_project_id': core.read()['project_id'],
                        'execution_environment': 'host', 'agent_resumed': False}
            return self._open(core, _editable_question(core, args['question_id']), args.get('ui_language'),
                              fake=args['project_key'] == 'soundmaker-smoke')

    def _prepare(self, core, request_id, script, language, *, fake=False):
        _key(request_id)
        digest = hashlib.sha256(json.dumps(script, ensure_ascii=False, sort_keys=True, allow_nan=False).encode()).hexdigest()
        path = core.managed_path(f'.makesound/host-bridge/requests/{request_id}.json')
        with file_lock(path.with_suffix('.lock')):
            if path.exists():
                saved = read_json(path)
                require(saved['script_hash'] == digest, 'request_conflict', 'This request_id already refers to a different script.')
                qid = saved['question_id']
            else:
                qid = prepare(core, script)['question_id']
                atomic_write(path, {'script_hash': digest, 'question_id': qid})
        return self._open(core, qid, language, fake=fake)

    def _open(self, core, qid, language, *, fake=False):
        language = resolve_ui_language(language)
        question = Questions(core).read(qid)
        key = (str(core.root), qid)
        handle = self.records.get(key)
        if handle is None:
            handle = 'hb_' + uuid.uuid4().hex
            record = {'core': core, 'qid': qid, 'server': None, 'thread': None, 'url': None}
            if question['status'] == 'pending':
                register_tool_result(core, qid)
                backend = StudioBackend(core, allow_fake=fake)
                server = create_server(backend, question_id=qid, close_after_answer=True, ui_language=language)
                thread = threading.Thread(target=server.serve_forever, daemon=True)
                thread.start()
                record.update(server=server, thread=thread, url=f'http://127.0.0.1:{server.server_port}')
            self.records[key], self.handles[handle] = handle, record
        record = self.handles[handle]
        return {'status': 'binding_saved' if question['status'] == 'answered' else 'binding_open',
                'handle': handle, 'question_id': qid, 'project_key': core.root.name,
                'host_project_id': core.read()['project_id'], 'root_index': self.roots.index(core.root.parent),
                'url': record['url'] if question['status'] == 'pending' else None,
                'execution_environment': 'host', 'transport': 'pending_mcp_tool_result',
                'wait_tool': {'name': 'soundmaker_wait_binding', 'arguments': {'handle': handle, 'timeout': 50}},
                'network_calls': 0, 'synthesis_calls': 0, 'receiver_verified': False}

    def close(self):
        with self.lock:
            self.closed = True
            for event in self.waiters:
                event.set()
            records = list(self.handles.values())
        for record in records:
            if record['server'] is not None:
                record['server'].shutdown()
                record['server'].server_close()
                record['thread'].join(timeout=3)


def serve(bridge, stdin, stdout):
    # Compatibility entry for already installed SoundMaker-specific MCP clients.
    from host_bridge.transport import serve as serve_transport
    return serve_transport(bridge, stdin, stdout, error_types=(MakeSoundError,), server_name='soundmaker-host',
        instructions='Host binding tools only; no synthesis. Show the URL, then wait with soundmaker_wait_binding.')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--allowed-root', action='append', required=True)
    args = parser.parse_args()
    sys.stdin.reconfigure(encoding='utf-8')
    sys.stdout.reconfigure(encoding='utf-8')
    with Bridge(args.allowed_root) as bridge:
        serve(bridge, sys.stdin, sys.stdout)


if __name__ == '__main__':
    main()
