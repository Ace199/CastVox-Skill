"""Open project voice management or editable binding versions. No synthesis."""
import argparse
import json
import os
from pathlib import Path
import subprocess
import sys
import threading
import time
import urllib.request

from .core_v16 import ProjectCore
from .questions import Questions
from .errors import MakeSoundError, require
from .ui_locale import resolve_ui_language


def _server_executable():
    # Windows venv python.exe can spawn a base interpreter that allocates a
    # console despite the parent's creation flags. Its matching GUI redirector
    # preserves the same environment without allocating that console.
    executable = Path(sys.executable)
    if os.name == 'nt' and executable.name.lower() == 'python.exe':
        windowless = executable.with_name('pythonw.exe')
        if windowless.is_file():
            return str(windowless)
    return sys.executable


def _editable_question(core, question_id):
    if question_id is None:
        return None
    question = Questions(core).read(question_id)
    if question['status'] == 'answered':
        from .binding_revision import create
        return create(core, question_id)['question_id']
    require(question['status'] == 'pending', 'invalid_question', 'Question cannot be edited.')
    return question_id


def start(core, question_id=None, *, codex_thread=None, allow_fake=False, ui_language=None):
    language = resolve_ui_language(ui_language)
    launch_question_id = question_id
    question_id = _editable_question(core, question_id)
    from .harness_resume import register_environment, environment_target
    identity = environment_target(codex_thread, core=core, qid=launch_question_id) if question_id else None
    require(not identity or identity.get('harness') not in {'workbuddy_native', 'workbuddy_task'},
            'managed_launch_required',
            'WorkBuddy must run python -m makesound.studio_session as a managed background command, not a detached child.')
    folder = core.managed_path(f'.makesound/studio/{question_id or "management"}')
    folder.mkdir(parents=True, exist_ok=True)
    record = folder / 'session.json'
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))

    def check(url):
        with opener.open(url + '/js/session.js', timeout=2) as response:
            module = response.read().decode('utf-8')
        session = json.loads(module.split('Object.freeze(', 1)[1].rsplit(');', 1)[0])
        return session if (session.get('question_id') == question_id and
                           (question_id is not None or session.get('project_id') == core.read()['project_id'])) else None

    if record.exists():
        saved = json.loads(record.read_text(encoding='utf-8'))
        # Only probe a locally generated loopback address.
        from urllib.parse import urlsplit
        parsed = urlsplit(saved['url'])
        require(parsed.scheme == 'http' and parsed.hostname == '127.0.0.1'
                and parsed.port and not parsed.username and not parsed.path, 'unsafe_path', 'Invalid session URL.')
        live = False
        try:
            live = check(saved['url'])
        except (OSError, ValueError, IndexError):
            pass
        if live:
            require(saved.get('launch_identity') == identity, 'session_mismatch',
                    'Existing Studio was started from a different harness environment. Close that session before launching again.')
            require(language is None or live.get('ui_language') == language, 'ui_language_mismatch',
                    'Existing Studio uses a different UI language. Change language in that window or close it before relaunching.')
            if question_id:
                register_environment(core, question_id, codex_thread, discovery_question_id=launch_question_id)
            return {k: v for k, v in saved.items() if k != 'launch_identity'}

    if question_id:
        register_environment(core, question_id, codex_thread, discovery_question_id=launch_question_id)

    server_script = Path(__file__).resolve().parent.parent / 'studio_v16_server.py'
    args = [_server_executable(), str(server_script), '--project', str(core.root)]
    if question_id:
        args.extend(['--question', question_id, '--once'])
    if allow_fake:
        args.append('--fake')
    if language is not None:
        args.extend(['--ui-language', language])
    options = {'creationflags': subprocess.CREATE_NO_WINDOW | subprocess.DETACHED_PROCESS} if os.name == 'nt' else {'start_new_session': True}
    out = folder / 'stdout.log'
    with out.open('w', encoding='utf-8') as stdout, (folder / 'stderr.log').open('w', encoding='utf-8') as stderr:
        process = subprocess.Popen(args, stdin=subprocess.DEVNULL, stdout=stdout, stderr=stderr, **options)
    try:
        deadline = time.monotonic() + 15
        while time.monotonic() < deadline:
            require(process.poll() is None, 'studio_start_failed', 'Studio exited during startup; inspect its local log.')
            lines = out.read_text(encoding='utf-8').splitlines()
            if lines:
                ready = json.loads(lines[0])
                if check(ready['url']):
                    result = {'url': ready['url'], 'question_id': question_id, 'pid': process.pid, 'once': bool(question_id),
                              'mode': 'binding' if question_id else 'management',
                              'source_question_id': Questions(core).read(question_id).get('source_question_id') if question_id else None,
                              'ui_language': language}
                    record.write_text(json.dumps({**result, 'launch_identity': identity}), encoding='utf-8')
                    return result
            time.sleep(.1)
        raise TimeoutError('Studio readiness check timed out.')
    except Exception:
        process.terminate()
        process.wait(timeout=5)
        raise


def serve_managed(core, question_id=None, *, allow_fake=False, on_ready=None, config_dir=None, ui_language=None):
    """Serve in the host-owned command process until submission/host cancellation.

    WorkBuddy owns this command as a background task. No orphan child process,
    scheduled task, or Windows job breakaway is created.
    """
    from .harness_resume import environment_target, register_environment
    from .storage import atomic_write, file_lock
    from .studio_backend import StudioBackend
    from studio_config_editor import config_path
    from studio_v16_server import create_server
    language = resolve_ui_language(ui_language)
    launch_question_id = question_id
    question_id = _editable_question(core, question_id)
    identity = environment_target(core=core, qid=launch_question_id) if question_id else None
    folder = core.managed_path(f'.makesound/studio/{question_id or "management"}')
    folder.mkdir(parents=True, exist_ok=True)
    with file_lock(folder / 'managed-server.lock'):
        require(question_id is None or Questions(core).read(question_id)['status'] == 'pending',
                'answer_immutable', 'This task was answered while waiting to launch Studio.')
        if question_id:
            register_environment(core, question_id, discovery_question_id=launch_question_id)
        directory = Path(config_dir).resolve() if config_dir else None
        backend = StudioBackend(core, allow_fake=allow_fake, config_dir=directory,
                                config_paths={p: config_path(p, directory) for p in ('minimax', 'volcengine')})
        backend.core.read()
        server = create_server(backend, question_id=question_id, config_dir=directory, close_after_answer=bool(question_id),
                               ui_language=language)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            result = {'url': f'http://127.0.0.1:{server.server_port}', 'question_id': question_id,
                      'pid': os.getpid(), 'once': bool(question_id), 'lifecycle': 'host_managed', 'ui_language': language,
                      'source_question_id': Questions(core).read(question_id).get('source_question_id') if question_id else None,
                      'mode': 'binding' if question_id else 'management'}
            opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
            with opener.open(result['url'] + '/js/session.js', timeout=3) as response:
                module = response.read().decode('utf-8')
            session = json.loads(module.split('Object.freeze(', 1)[1].rsplit(');', 1)[0])
            require(session.get('question_id') == question_id, 'session_mismatch', 'Studio readiness differs.')
            require(question_id is not None or session.get('project_id') == core.read()['project_id'],
                    'project_mismatch', 'Management page belongs to another project.')
            atomic_write(folder / 'session.json', {**result, 'launch_identity': identity})
            if on_ready:
                on_ready(result)
            else:
                print(json.dumps(result), flush=True)
            # Keep the host task alive through Answer persistence AND notify()/HTTP response.
            # Question status alone is insufficient: it changes before notification finishes.
            thread.join()
            if question_id is None:
                return {'status': 'management_closed', 'project': str(core.root), 'question_id': None}
            saved = Questions(core).read(question_id)
            return {'status': 'binding_saved' if saved['status'] == 'answered' else 'closed_without_answer',
                    'question_id': question_id, 'project': str(core.root),
                    'answer_id': saved.get('answer', {}).get('answer_id') if saved.get('answer') else None,
                    'next_action': 'Read this saved Answer and continue in the originating chat with a performance plan for review. '
                                   'Do not synthesize audio or repeat an already processed Answer.'}
        finally:
            server.shutdown()
            server.server_close()
            thread.join(timeout=5)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--project', required=True)
    parser.add_argument('--question', help='Edit a task; answered tasks open a new binding version. Omit to view the project library.')
    parser.add_argument('--codex-thread', help='Exact originating chat UUID; defaults to CODEX_THREAD_ID')
    parser.add_argument('--ui-language', help='Chinese/English UI override (zh-CN or en); defaults to CASTVOX_UI_LANGUAGE handoff, then Chinese')
    args = parser.parse_args()
    try:
        if os.environ.get('WORKBUDDY_CONFIG_DIR'):
            require(not args.codex_thread, 'session_mismatch', 'WorkBuddy cannot target a Codex chat.')
            result = serve_managed(ProjectCore(args.project), args.question, ui_language=args.ui_language)
        else:
            result = start(ProjectCore(args.project), args.question, codex_thread=args.codex_thread,
                           ui_language=args.ui_language)
        print(json.dumps(result), flush=True)
        return 0
    except (MakeSoundError, OSError, TimeoutError) as exc:
        print(json.dumps({'status': 'error', 'code': exc.code if isinstance(exc, MakeSoundError) else 'studio_start_failed',
                          'message': 'Studio could not open; saved bindings and audio are preserved. Check the indicated state or host permissions.'}), flush=True)
        return 2


if __name__ == '__main__':
    raise SystemExit(main())
