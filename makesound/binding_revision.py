"""Explicit, offline binding revisions. Opening a project never creates one.

Each revision preserves the previous Answer and any frozen Jobs. A prefilled
assignment is a saved snapshot, even if its library card was edited or deleted;
reselecting a card through Questions.assign opts into its current settings.
"""
import argparse
import copy
import json
import sys
from datetime import datetime, timezone

from .core_v16 import ProjectCore, uid
from .errors import MakeSoundError, require
from .questions import Questions
from .storage import atomic_write, digest, file_lock, read_json


def _handoff(core, qid):
    return core.managed_path(f'.makesound/handoffs/{qid}.json')


def _source(core, qid):
    question = Questions(core).read(qid)
    require(question['question_id'] == qid, 'project_mismatch', 'Question identity differs.')
    require(question['status'] == 'answered' and isinstance(question.get('answer'), dict),
            'not_answered', 'Only an answered binding can be revised.')
    answer = question['answer']
    require(answer['project_id'] == core.read()['project_id'] and answer['question_id'] == qid
            and answer['job_id'] == question['job_id'], 'project_mismatch', 'Answer belongs to another task or project.')
    handoff = read_json(_handoff(core, qid))
    require(handoff['question_id'] == qid, 'project_mismatch', 'Handoff identity differs.')
    require(handoff['harness_session_id'] == question['harness_session_id'],
            'session_mismatch', 'Handoff session differs.')
    manifest = handoff['manifest']
    require(manifest['roles'] == question['roles'] and set(answer['resolved']) == set(question['roles']),
            'plan_changed', 'Manuscript roles differ from the saved binding.')
    require(isinstance(manifest['segments'], list) and bool(manifest['segments']) and
            all(segment.get('role_id') in question['roles'] for segment in manifest['segments']),
            'plan_changed', 'Manuscript references unknown roles.')
    for value in answer['resolved'].values():
        require(value.get('status') == 'ready', 'voice_unavailable', 'Saved binding is incomplete.')
    snapshot_path = core.managed_path(f".makesound/jobs/{question['job_id']}/snapshot.json")
    if snapshot_path.exists():
        from .generation import Generation
        snapshot = Generation(core).load(question['job_id'])
        require(snapshot['segments'] == manifest['segments'], 'plan_changed', 'Manuscript differs from its frozen Job.')
    return question, handoff


def _result(question):
    return {'status': question['status'], 'question_id': question['question_id'],
            'job_id': question['job_id'], 'harness_session_id': question['harness_session_id'],
            'source_question_id': question['source_question_id'],
            'source_answer_id': question['source_answer_id'],
            'network_calls': 0, 'paid_execution_authorized': False}


def create(core, question_id):
    """Prepare an explicitly requested edit, reusing a still pending revision."""
    return _create(core, question_id, set())


def _create(core, question_id, visited):
    require(question_id not in visited, 'invalid_local_data', 'Binding revision chain contains a cycle.')
    visited.add(question_id)
    questions = Questions(core)
    # Reading validates identifiers before they are used in an index path.
    questions.read(question_id)
    index = core.managed_path(f'.makesound/binding-revisions/{question_id}.json')
    with file_lock(index.with_suffix('.lock')):
        source, handoff = _source(core, question_id)
        fingerprint = digest({'answer': source['answer'], 'manifest': handoff['manifest'],
                              'harness_session_id': source['harness_session_id']})
        if index.exists():
            saved = read_json(index)
            existing = questions.read(saved['question_id'])
            if existing['status'] == 'answered':
                _validate_revision(core, existing, source, handoff)
                # Reopening from the original link must continue from the newest
                # accepted choices, never silently restore the first Answer.
                return _create(core, existing['question_id'], visited)
            if (existing['status'] == 'pending' and
                    datetime.now(timezone.utc) < datetime.fromisoformat(existing['expires_at'])):
                require(existing.get('source_fingerprint') == fingerprint, 'plan_changed',
                        'Source binding or manuscript changed; prepare from the current task.')
                _validate_revision(core, existing, source, handoff)
                return _result(existing)
        question = questions.create(uid('job_'), source['harness_session_id'], source['roles'],
                                    role_metadata=source.get('role_metadata'))
        question.update({'source_question_id': question_id,
                         'source_answer_id': source['answer']['answer_id'],
                         'source_fingerprint': fingerprint})
        preset = core.read()
        for role, resolved in source['answer']['resolved'].items():
            vid = resolved['project_voice_id']
            question['assignments'][role] = {'project_voice_id': vid, 'resolved': copy.deepcopy(resolved),
                'snapshot': {'project_voice_id': vid, 'name': resolved['name'],
                             'category': preset['voices'].get(vid, {}).get('category', 'other'),
                             'source': copy.deepcopy(resolved['source']),
                             'settings': copy.deepcopy(resolved['effective_settings'])}}
        atomic_write(_handoff(core, question['question_id']),
                     {'question_id': question['question_id'],
                      'harness_session_id': question['harness_session_id'],
                      'source_question_id': question_id, 'source_answer_id': source['answer']['answer_id'],
                      'manifest': copy.deepcopy(handoff['manifest'])})
        atomic_write(questions._path(question['question_id']), question)
        atomic_write(index, {'question_id': question['question_id']})
        return _result(question)


def _validate_revision(core, question, source, source_handoff):
    require(question.get('source_answer_id') == source['answer']['answer_id'] and
            question.get('source_fingerprint') == digest({'answer': source['answer'],
                'manifest': source_handoff['manifest'], 'harness_session_id': source['harness_session_id']}),
            'plan_changed', 'Source binding or manuscript changed.')
    handoff = read_json(_handoff(core, question['question_id']))
    require(question['harness_session_id'] == source['harness_session_id'] == handoff['harness_session_id'],
            'session_mismatch', 'Revision session differs.')
    require(handoff['question_id'] == question['question_id'] and
            handoff.get('source_question_id') == source['question_id'] and
            handoff.get('source_answer_id') == source['answer']['answer_id'],
            'project_mismatch', 'Revision belongs to another task.')
    require(question['roles'] == source['roles'] and handoff['manifest'] == source_handoff['manifest'],
            'plan_changed', 'Revision manuscript changed.')
    return handoff


def compare(core, new_qid):
    """Report changed synthesis bindings and sentence scope, without generating."""
    question = Questions(core).read(new_qid)
    require(question.get('source_question_id'), 'not_revision', 'Question is not a binding revision.')
    source, source_handoff = _source(core, question['source_question_id'])
    handoff = _validate_revision(core, question, source, source_handoff)
    result = _result(question)
    if question['status'] == 'pending':
        return {**result, 'changed_roles': [], 'affected_sentence_ids': [], 'comparison_ready': False}
    require(question['status'] == 'answered', 'not_answered', 'No revised Answer is ready.')
    # Validate the new Answer project, job, role and manuscript identities too.
    _source(core, new_qid)
    def synthesis(binding):
        return {key: binding[key] for key in ('source', 'effective_settings')}
    changed = [role for role in question['roles']
               if synthesis(source['answer']['resolved'][role]) != synthesis(question['answer']['resolved'][role])]
    return {**result, 'comparison_ready': True, 'changed_roles': changed,
            'affected_sentence_ids': [segment['sentence_id'] for segment in handoff['manifest']['segments']
                                      if segment['role_id'] in changed]}


def main(argv=None):
    if hasattr(sys.stdout, 'reconfigure'):
        sys.stdout.reconfigure(encoding='utf-8')
    parser = argparse.ArgumentParser(description='Explicit offline role binding revision; no generation')
    parser.add_argument('action', choices=['prepare', 'status'])
    parser.add_argument('--project', required=True)
    parser.add_argument('--question', required=True)
    args = parser.parse_args(argv)
    try:
        core = ProjectCore(args.project)
        result = create(core, args.question) if args.action == 'prepare' else compare(core, args.question)
        print(json.dumps(result, ensure_ascii=False))
        return 0
    except (MakeSoundError, OSError, ValueError, TypeError, KeyError) as exc:
        print(json.dumps({'status': 'error', 'code': exc.code if isinstance(exc, MakeSoundError) else 'invalid_local_data',
                          'message': 'Binding revision could not continue; review the saved task input.'}))
        return 2


if __name__ == '__main__':
    raise SystemExit(main())
