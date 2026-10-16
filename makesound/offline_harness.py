"""Explicit local Fake-only handoff usable from Codex or Claude Code terminals.

No SDK, polling daemon, real vendor client, or automatic wakeup is implied.
"""
import argparse
import json
import sys
from pathlib import Path

from . import validation as v
from .core_v16 import ProjectCore, uid
from .errors import MakeSoundError, require
from .generation import Generation
from .questions import Questions
from .storage import atomic_write, file_lock, read_json


def prepare(core, manifest):
    v.shape(manifest, {'roles', 'role_metadata', 'segments'}, {'roles', 'segments'})
    v.no_secrets(manifest)
    require(isinstance(manifest['segments'], list) and bool(manifest['segments']))
    for segment in manifest['segments']:
        require(isinstance(segment, dict) and segment.get('role_id') in manifest['roles'], 'missing_roles', 'Each sentence needs a declared role.')
    jid, session = uid('job_'), uid('session_')
    question = Questions(core).create(jid, session, manifest['roles'], role_metadata=manifest.get('role_metadata'))
    atomic_write(core.managed_path(f'.makesound/handoffs/{question["question_id"]}.json'),
                 {'question_id': question['question_id'], 'harness_session_id': session, 'manifest': manifest})
    return {'status': 'needs_studio', 'question_id': question['question_id'], 'job_id': jid,
            'offline_only': True, 'agent_resumed': False}


def resume(core, qid, *, confirmed=False, authorized=False, retry_failed=False):
    require(confirmed is True and authorized is True, 'authorization_required', 'Confirm the manuscript and authorize this offline Fake task.')
    handoff_path = core.managed_path(f'.makesound/handoffs/{qid}.json')
    # Serialize claim + freeze across separate terminal invocations.
    with file_lock(handoff_path.with_suffix('.lock')):
        handoff = read_json(handoff_path)
        require(handoff['question_id'] == qid, 'project_mismatch', 'Handoff differs.')
        questions = Questions(core)
        question = questions.read(qid)
        require(question['harness_session_id'] == handoff['harness_session_id'], 'session_mismatch', 'Handoff session differs.')
        if question['status'] == 'pending':
            return {'status': 'waiting_for_answer', 'question_id': qid, 'offline_only': True}
        # This entry point is intentionally incapable of charging a real Provider.
        require(all(r['source']['provider'] == 'fake' for r in question['answer']['resolved'].values()),
                'offline_only', 'The offline harness accepts Fake voices only.')
        if question['claimed_by'] is None:
            questions.claim(qid, handoff['harness_session_id'])
        else:
            require(question['claimed_by'] == handoff['harness_session_id'], 'session_mismatch', 'Answer claimed elsewhere.')
        engine = Generation(core)
        snapshot_path = core.managed_path(f'.makesound/jobs/{question["job_id"]}/snapshot.json')
        if snapshot_path.exists():
            snapshot = engine.load(question['job_id'])
        else:
            snapshot = engine.freeze_from_answer(qid, handoff['harness_session_id'], handoff['manifest']['segments'],
                                                 confirmed=True, authorized=True)
        result = engine.run(snapshot['job_id'], retry_failed=retry_failed)
        return {'status': result['status'], 'job_id': snapshot['job_id'], 'result': result,
                'fake_calls_this_run': engine.fake.calls, 'offline_only': True}


def main(argv=None):
    if hasattr(sys.stdout, 'reconfigure'):
        sys.stdout.reconfigure(encoding='utf-8')
    parser = argparse.ArgumentParser(description='Local Fake-only Studio handoff; no paid API')
    parser.add_argument('action', choices=['prepare', 'continue', 'status'])
    parser.add_argument('--project', required=True)
    parser.add_argument('--manifest', type=Path)
    parser.add_argument('--question')
    parser.add_argument('--confirmed', action='store_true')
    parser.add_argument('--authorize-fake', action='store_true')
    parser.add_argument('--retry-failed', action='store_true')
    args = parser.parse_args(argv)
    try:
        core = ProjectCore(args.project)
        if args.action == 'prepare':
            require(args.manifest is not None, 'manifest_required', 'Provide a structured manuscript.')
            core.read()
            result = prepare(core, read_json(args.manifest))
        else:
            v.identifier(args.question)
            if args.action == 'status':
                question = Questions(core).read(args.question)
                result = {'question_id': args.question, 'status': question['status'], 'claimed': question['claimed_by'] is not None}
            else:
                result = resume(core, args.question, confirmed=args.confirmed, authorized=args.authorize_fake, retry_failed=args.retry_failed)
        print(json.dumps(result, ensure_ascii=False))
        return 0
    except (MakeSoundError, OSError, ValueError, TypeError, KeyError) as exc:
        print(json.dumps({'status': 'error', 'code': exc.code if isinstance(exc, MakeSoundError) else 'invalid_local_data',
                          'message': 'Offline task could not continue; repair the indicated local input.'}))
        return 2


if __name__ == '__main__':
    raise SystemExit(main())
