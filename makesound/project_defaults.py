"""Save an explicitly selected Answer voice as a V1.6 project default, offline."""
import argparse
import json
import sys

from .core_v16 import ProjectCore
from .questions import Questions
from .errors import MakeSoundError, require


def save_from_answer(core, question_id, revision, *, slot='general', role_id=None):
    require(slot in {'general', 'male', 'female'}, 'invalid_default', 'Choose a project default slot.')
    question = Questions(core).read(question_id)
    require(question['status'] == 'answered' and question.get('answer'), 'not_answered', 'Read a saved Answer first.')
    roles = question['answer']['resolved']
    if role_id is None:
        require(len(roles) == 1, 'missing_roles', 'Select which role should become the default.')
        role_id = next(iter(roles))
    require(role_id in roles, 'missing_roles', 'Select an answered role.')
    chosen = roles[role_id]
    preset = core.read()
    require(type(revision) is int and revision == preset['revision'], 'revision_conflict', 'Reload and review the project revision.')
    voice = preset['voices'].get(chosen['project_voice_id'])
    require(voice and not voice['deleted'] and voice['source'] == chosen['source']
            and voice['settings'] == chosen['effective_settings'],
            'binding_changed', 'The saved role and current project voice differ; review before changing defaults.')
    require(slot == 'general' or voice['category'] == slot, 'invalid_default', 'Default category does not match.')
    current = preset['default_snapshots'].get(slot)
    wanted = {'project_voice_id': chosen['project_voice_id'], **{k: voice[k] for k in ('name', 'category', 'source', 'settings')},
              'parameter_review_required': voice.get('parameter_review_required', False)}
    if current != wanted:
        preset = core.save_defaults({slot: chosen['project_voice_id']}, revision)
    return {'status': 'saved', 'revision': preset['revision'], 'defaults': preset['defaults'],
            'slot': slot, 'project_voice_id': chosen['project_voice_id'], 'network_calls': 0}


def main(argv=None):
    if hasattr(sys.stdout, 'reconfigure'):
        sys.stdout.reconfigure(encoding='utf-8')
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--project', required=True)
    parser.add_argument('--question', required=True)
    parser.add_argument('--revision', type=int, required=True)
    parser.add_argument('--slot', default='general', choices=['general', 'male', 'female'])
    parser.add_argument('--role')
    args = parser.parse_args(argv)
    try:
        print(json.dumps(save_from_answer(ProjectCore(args.project), args.question, args.revision,
                                          slot=args.slot, role_id=args.role), ensure_ascii=False))
        return 0
    except MakeSoundError as exc:
        print(json.dumps({'status': 'error', 'error': exc.code, 'message': str(exc)}, ensure_ascii=False))
        return 2


if __name__ == '__main__':
    raise SystemExit(main())
