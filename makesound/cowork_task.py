"""Return saved bindings through the originating Cowork command's tool result.

No out-of-band wake-up is attempted. A pending command must remain owned by
the original host request; the app must actually continue after its result.
"""
import argparse
import hashlib
import json
import math
import os
from pathlib import Path
import re
import time

from .errors import MakeSoundError, require
from .questions import Questions
from .storage import read_json, file_lock


def environment_target():
    if os.environ.get('CLAUDE_CODE_IS_COWORK', '').lower() not in {'1', 'true'}:
        return None
    directory = Path(os.environ.get('CLAUDE_CONFIG_DIR', ''))
    # This observed local build isolates each Cowork session's .claude directory.
    # A normal shared ~/.claude directory cannot identify an originating chat.
    if (not directory.is_absolute() or directory.name != '.claude'
            or not re.fullmatch(r'[0-9a-f]{8}', directory.parent.name)
            or 'local-agent-mode-sessions' not in directory.parts
            or not directory.is_dir()):
        return None
    canonical = str(directory.resolve())
    if os.name == 'nt':
        canonical = canonical.casefold()
    return {'harness': 'cowork_task',
            'session_fingerprint': hashlib.sha256(canonical.encode('utf-8')).hexdigest()}


def complete(target, message):
    if target.get('harness') == 'tool_result':
        # The tool transport returns to its requesting call. It sends nothing
        # to a named conversation and does not authenticate a chat from a path.
        return {'status': 'awaiting_tool', 'transport': 'pending_tool_result'}
    current = environment_target()
    require(current is not None and all(target.get(key) == value for key, value in current.items()),
            'session_mismatch', 'Cowork binding belongs to a different or unavailable originating session.')
    return {'status': 'awaiting_tool', 'transport': 'pending_tool_result'}


def wait_for_binding(core, qid, *, timeout=50, cancel_event=None):
    require(type(timeout) in {int, float} and math.isfinite(timeout) and 0 <= timeout <= 55,
            'invalid_timeout', 'Wait duration must be between 0 and 55 seconds.')
    folder = core.managed_path(f'.makesound/studio/{qid}')
    # Validate the Question identifier before accessing any target path.
    questions = Questions(core)
    questions.read(qid)
    # One active requesting command per Question; do not broadcast a completion
    # to multiple concurrent waiters. Later explicit reads remain idempotent.
    with file_lock(folder / 'tool-result-wait.lock', timeout=0):
        return _wait_for_binding(core, qid, folder, questions, timeout, cancel_event)


def _wait_for_binding(core, qid, folder, questions, timeout, cancel_event=None):
    target_path, receipt_path = folder / 'wake-target.json', folder / 'wake-receipt.json'
    require(target_path.is_file(), 'harness_unavailable', 'Start Studio from this Cowork session before waiting.')
    target = read_json(target_path)
    require(target.get('question_id') == qid and target.get('harness') in {'cowork_task', 'tool_result'},
            'session_mismatch', 'This binding does not use the originating Cowork tool-result transport.')
    complete(target, '')
    deadline = time.monotonic() + timeout
    while True:
        if cancel_event is not None and cancel_event.is_set():
            return {'status': 'cancelled', 'question_id': qid, 'agent_resumed': False}
        require(read_json(target_path) == target, 'session_mismatch', 'The binding target changed while waiting.')
        complete(target, '')
        question = questions.read(qid)
        answer = question.get('answer')
        receipt = read_json(receipt_path) if receipt_path.is_file() else None
        if question['status'] == 'answered' and answer and receipt and receipt.get('status') != 'dispatching':
            require(receipt.get('question_id') == qid and receipt.get('answer_id') == answer['answer_id'],
                    'session_mismatch', 'Completion receipt differs from the saved Answer.')
            return {'status': 'binding_saved', 'project': str(core.root), 'question_id': qid,
                    'answer_id': answer['answer_id'], 'transport': 'pending_tool_result', 'agent_resumed': False,
                    'next_action': 'Read this saved Answer in the originating request. Reuse accepted unchanged auditions; '
                                   'review only unfinished or affected items. This is not authorization for paid synthesis. '
                                   'Do not repeat an Answer already processed.'}
        if time.monotonic() >= deadline:
            return {'status': 'waiting', 'project': str(core.root), 'question_id': qid,
                    'transport': 'pending_tool_result', 'agent_resumed': False,
                    'next_action': 'If this original host request remains active, wait again on the same Question; '
                                   'do not start another Studio or claim that the model has resumed.'}
        time.sleep(min(.5, max(0, deadline - time.monotonic())))


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--project', required=True)
    parser.add_argument('--question', required=True)
    parser.add_argument('--timeout', type=float, default=50)
    args = parser.parse_args(argv)
    try:
        from .core_v16 import ProjectCore
        result = wait_for_binding(ProjectCore(args.project), args.question, timeout=args.timeout)
        print(json.dumps(result, ensure_ascii=False))
        return 0
    except MakeSoundError as error:
        print(json.dumps({'status': 'error', 'code': error.code, 'message': str(error)}))
        return 2


if __name__ == '__main__':
    raise SystemExit(main())
