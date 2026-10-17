"""Best-effort original-session notification after durable binding submission."""
import os
import shutil
import subprocess
import tomllib
import uuid
import json
import urllib.request
import urllib.error
from pathlib import Path

from .errors import require
from .questions import Questions
from .storage import atomic_write, file_lock, read_json


def register_environment(core, qid, codex_thread=None, *, discovery_question_id=None):
    # A binding revision has a new identity, while the active host command still
    # contains the source Question ID. Discover the origin from that command.
    target = environment_target(codex_thread, core=core, qid=discovery_question_id or qid)
    if target:
        target['question_id'] = qid
        _register_target(core, qid, target)


def environment_target(codex_thread=None, *, core=None, qid=None):
    from .claude_native import environment_target as claude_target
    target = claude_target()
    thread = codex_thread or os.environ.get('CODEX_THREAD_ID')
    is_kimi = os.environ.get('KIMI_AGENT_CLIENT_ID') == 'kimiwork'
    is_workbuddy = bool(os.environ.get('WORKBUDDY_CONFIG_DIR'))
    is_doubao = bool(os.environ.get('DOUBAO_OFFICE_APP_ID'))
    require(sum(bool(value) for value in (target, thread, is_kimi, is_workbuddy, is_doubao)) <= 1,
            'session_mismatch', 'Multiple harness identities are present; use the originating harness environment.')
    if is_doubao:
        from .doubao_resume import environment_target as doubao_target
        return doubao_target(core, qid)
    if is_workbuddy:
        from .workbuddy_task import environment_target as workbuddy_target
        return workbuddy_target()
    if is_kimi:
        from .kimi_work import environment_target as kimi_target
        return kimi_target(core, qid)
    if target:
        return target
    if thread:
        require(str(uuid.UUID(thread)) == thread, 'invalid_thread', 'Expected an exact Codex thread UUID.')
        return {'harness': 'codex', 'thread_id': thread}
    return None


def register(core, qid, thread_id):
    if not thread_id:
        return
    require(str(uuid.UUID(thread_id)) == thread_id, 'invalid_thread', 'Expected an exact Codex thread UUID.')
    target = {'harness': 'codex', 'thread_id': thread_id, 'question_id': qid}
    _register_target(core, qid, target)


def _register_target(core, qid, target):
    Questions(core).read(qid)
    path = core.managed_path(f'.makesound/studio/{qid}/wake-target.json')
    with file_lock(path.with_suffix('.lock')):
        if path.exists():
            require(read_json(path) == target, 'session_mismatch', 'This question belongs to another chat.')
        else:
            atomic_write(path, target)


def queue_command(thread_id, message):
    executable = shutil.which('codex')
    require(executable is not None, 'harness_unavailable', 'Codex CLI is unavailable.')
    args = [executable]
    if Path(executable).suffix.lower() in {'.cmd', '.bat', '.ps1'}:
        entry = Path(executable).parent / 'node_modules/@openai/codex/bin/codex.js'
        node = shutil.which('node')
        require(entry.is_file() and node, 'harness_unavailable', 'Cannot safely invoke this CLI shim.')
        args = [node, str(entry)]
    # Compatibility with the installed CLI; never rewrite user configuration.
    config = Path(os.environ.get('CODEX_HOME', str(Path.home() / '.codex'))) / 'config.toml'
    if config.exists():
        value = tomllib.loads(config.read_text(encoding='utf-8')).get('features', {}).get('context_management')
        if isinstance(value, dict):
            args += ['-c', 'features.context_management=false']
    return args + ['queue', '--thread', thread_id, '--message', message]


def completion_message(core, qid, answer_id):
    return (f'[SoundMaker binding completed] project={core.root}; question_id={qid}; '
            f'answer_id={answer_id}. '
            'The user clicked Complete and the Answer is saved. Read the SoundMaker skill and this saved Answer; '
            'continue in this original chat with a performance plan for user review. '
            'This event is not approval of a new performance plan or authorization for paid synthesis. '
            'Do not repeat work if this Answer has already been processed.')


def notify(core, qid):
    folder = core.managed_path(f'.makesound/studio/{qid}')
    target_path, receipt = folder / 'wake-target.json', folder / 'wake-receipt.json'
    if not target_path.exists():
        return {'status': 'unavailable'}
    with file_lock(receipt.with_suffix('.lock')):
        if receipt.exists():
            return read_json(receipt)
        question = Questions(core).read(qid)
        require(question['status'] == 'answered' and question.get('answer'), 'not_answered', 'Save the binding first.')
        target = read_json(target_path)
        require(target['question_id'] == qid, 'session_mismatch', 'Wake target differs.')
        message = completion_message(core, qid, question['answer']['answer_id'])
        # A crash/timeout after dispatch may have queued the message. Never blindly resend.
        state = {'status': 'dispatching', 'question_id': qid, 'answer_id': question['answer']['answer_id']}
        atomic_write(receipt, state)
        try:
            if target['harness'] == 'doubao':
                from .doubao_resume import send
                state.update(send(target, message))
            elif target['harness'] == 'workbuddy_task':
                from .workbuddy_task import complete
                state.update(complete(target, message))
            elif target['harness'] == 'workbuddy_native':
                # Engine-only replies do not open a desktop request. Do not retry
                # legacy notifications through another route after unknown outcomes.
                state['status'] = 'unavailable'
            elif target['harness'] == 'kimi_work':
                from .kimi_work import send
                state.update(send(target, message))
            elif target['harness'] == 'claude_native':
                from .claude_native import send
                state.update(send(target, message))
            elif target['harness'] == 'claude_channel':
                port = target['port']
                require(type(port) is int and 0 < port < 65536, 'invalid_target', 'Invalid local channel port.')
                payload = json.dumps({'question_id': qid, 'answer_id': state['answer_id']}).encode('utf-8')
                request = urllib.request.Request(f'http://127.0.0.1:{port}/binding-complete', data=payload,
                    headers={'Authorization': 'Bearer ' + target['token'], 'Content-Type': 'application/json'})
                opener = urllib.request.build_opener(urllib.request.ProxyHandler({}), _NoRedirect())
                with opener.open(request, timeout=10) as response:
                    result = json.loads(response.read(4096))
                    require(result.get('status') == 'queued', 'delivery_failed', 'Channel did not acknowledge.')
                state['status'] = 'queued'
            else:
                require(target['harness'] == 'codex', 'harness_unavailable', 'Unknown harness.')
                args = queue_command(target['thread_id'], message)
                result = subprocess.run(args, capture_output=True, timeout=20,
                                        creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0)
                state['status'] = 'queued' if result.returncode == 0 else 'failed'
                state['exit_code'] = result.returncode
        except (subprocess.TimeoutExpired, TimeoutError):
            state['status'] = 'unknown'
        except Exception:
            state['status'] = 'failed'
        atomic_write(receipt, state)
        return state


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None
