"""Agent-curated candidates and reviewable auditions; no synthesis or automatic binding."""
import copy
from datetime import datetime, timezone

from . import validation as v
from .core_v16 import uid
from .errors import MakeSoundError, require
from .providers import effective, source_valid, performance_directives
from .inline_controls import request_text
from .questions import Questions
from .storage import atomic_write, read_json, digest, file_lock


def _pending(core, qid):
    question = Questions(core).read(qid)
    require(question['status'] == 'pending', 'answer_immutable', 'Question has already been answered.')
    require(datetime.now(timezone.utc) < datetime.fromisoformat(question['expires_at']),
            'question_expired', 'Question TTL expired.')
    return question


def _path(core, selection_id):
    v.identifier(selection_id)
    return core.managed_path(f'.makesound/voice-selections/{selection_id}.json')


def _verified_audio(core, saved):
    from .providers import duration
    if saved.get('status') != 'success':
        return None
    try:
        audio = core.managed_path(saved['path'])
        if digest(audio.read_bytes().hex()) == saved['audio_hash'] and duration(audio) == saved['duration_seconds']:
            return audio
    except (OSError, ValueError, KeyError, MakeSoundError):
        pass
    return None


def create(core, qid, recommendations, revision):
    """Import 1–3 verified candidates per supplied role, in one preset revision.

    recommendations maps role IDs to objects with name/category/source/reason/
    evidence_url and optional settings. Evidence is supplied by the caller; this
    function does not query or certify the provider catalog.
    """
    question = _pending(core, qid)
    require(isinstance(recommendations, dict) and bool(recommendations)
            and set(recommendations) <= set(question['roles']), 'missing_roles', 'Use declared roles.')
    handoff = read_json(core.managed_path(f'.makesound/handoffs/{qid}.json'))
    require(handoff['question_id'] == qid and handoff['harness_session_id'] == question['harness_session_id'],
            'session_mismatch', 'Handoff differs from Question.')
    normalized = {}
    for role, candidates in recommendations.items():
        require(isinstance(candidates, list) and 1 <= len(candidates) <= 3,
                'candidate_limit', 'Recommend one to three candidates per role.')
        normalized[role] = []
        for candidate in candidates:
            v.shape(candidate, {'name', 'category', 'source', 'settings', 'reason', 'evidence_url'},
                    {'name', 'category', 'source', 'reason', 'evidence_url'})
            source_valid(candidate['source'])
            require(candidate['category'] in {'male', 'female', 'other'})
            for key in ('reason', 'evidence_url'):
                v.text(candidate[key])
            require(candidate['evidence_url'].startswith(('https://', 'http://')), 'invalid_data', 'Supply catalog evidence URL.')
            normalized[role].append({**copy.deepcopy(candidate), 'name': v.name(candidate['name']),
                                     'settings': effective(candidate['source'], candidate.get('settings'))})
    v.no_secrets(normalized)
    candidates_out = {}

    def change(preset):
        for role, candidates in normalized.items():
            candidates_out[role] = []
            for candidate in candidates:
                existing = next((vid for vid, item in preset['voices'].items()
                                 if not item['deleted'] and item['source'] == candidate['source']
                                 and item['settings'] == candidate['settings']), None)
                if existing is None:
                    existing = uid('pv_')
                    names = {item['name'] for item in preset['voices'].values() if not item['deleted']}
                    name, suffix = candidate['name'], 2
                    while name in names:
                        name = v.name(f"{candidate['name'][:70]} ({suffix})")
                        suffix += 1
                    preset['voices'][existing] = {'name': name, 'category': candidate['category'],
                        'source': copy.deepcopy(candidate['source']), 'settings': copy.deepcopy(candidate['settings']),
                        'deleted': False, 'preview': None}
                elif preset['voices'][existing]['category'] == 'other' and candidate['category'] in {'male', 'female'}:
                    # Fill a classification supplied from catalog or explicit request,
                    # keeping the original ID, preview and bindings.
                    preset['voices'][existing]['category'] = candidate['category']
                if any(item['project_voice_id'] == existing for item in candidates_out[role]):
                    continue
                candidates_out[role].append({'project_voice_id': existing,
                    'name': preset['voices'][existing]['name'],
                    'category': preset['voices'][existing]['category'],
                    'reason': candidate['reason'], 'evidence_url': candidate['evidence_url'],
                    'source': copy.deepcopy(candidate['source']), 'settings': copy.deepcopy(candidate['settings'])})

    # Validate the complete batch before the single CAS write; no partial imports.
    preset = core._update(change, revision)
    selection = {'selection_id': uid('selection_'), 'question_id': qid, 'project_id': preset['project_id'],
                 'candidates': candidates_out, 'manifest': copy.deepcopy(handoff['manifest'])}
    atomic_write(_path(core, selection['selection_id']), selection)
    return selection


def reuse_report(core, selection_id, question_id=None, *, targets=None):
    """Report intact selected auditions by original sentence; no plan or synthesis.

    With complete final targets, only matching performance is reusable. Without
    targets this is an inventory, marked performance_checked=False.
    """
    from .generation import Generation
    selection = read_json(_path(core, selection_id))
    require(selection['project_id'] == core.read()['project_id'], 'project_mismatch', 'Selection belongs to another project.')
    qid = question_id or selection['question_id']
    question = Questions(core).read(qid)
    require(question['status'] == 'answered' and question.get('answer'), 'not_answered', 'Select final voices before checking reuse.')
    handoff = read_json(core.managed_path(f'.makesound/handoffs/{qid}.json'))
    require(handoff['question_id'] == qid and handoff['harness_session_id'] == question['harness_session_id']
            and handoff['manifest'] == selection['manifest'], 'plan_changed', 'Task manuscript differs from audition.')
    originals = {s['sentence_id']: s for s in selection['manifest']['segments']}
    if targets is not None:
        require(isinstance(targets, dict) and set(targets) == set(originals),
                'plan_coverage', 'Final targets must cover every original sentence.')
        targets = copy.deepcopy(targets)
        for sid, target in targets.items():
            v.shape(target, {'provider_directives', 'inline_controls'})
            resolved = question['answer']['resolved'][originals[sid]['role_id']]
            target['provider_directives'] = performance_directives(resolved['source'], target.get('provider_directives'))
            target.setdefault('inline_controls', [])
            request_text({'source': resolved['source'], 'text': originals[sid]['text'],
                          'inline_controls': target['inline_controls']})
    reusable = {}
    engine = Generation(core)
    # Only this project's small audition records, never program or user directories.
    for path in sorted(core.managed_path('.makesound/voice-selections').glob('audition_*.json')):
        if path.name.endswith('.request.json'):
            continue
        try:
            sample = read_json(path)
            if sample.get('selection_id') != selection_id or not sample.get('frozen_result'):
                continue
            reviewed = {k: val for k, val in sample.items() if k not in {'review_hash', 'frozen_result'}}
            require(sample['review_hash'] == digest(reviewed), 'plan_changed', 'Audition record changed.')
            source = originals[sample['source_sentence_id']]
            require(sample['question_id'] == selection['question_id'] and sample['role_id'] == source['role_id'],
                    'plan_changed', 'Audition provenance differs.')
            resolved = question['answer']['resolved'][source['role_id']]
            jid = sample['frozen_result']['job_id']
            snapshot = engine.load(jid)
            state = read_json(core.managed_path(f'.makesound/jobs/{jid}/state.json'))
            for chunk in snapshot['chunks']:
                if (chunk['text'] != source['text'] or chunk['role_id'] != source['role_id']
                        or chunk['source'] != resolved['source']
                        or chunk['effective_settings'] != resolved['effective_settings']):
                    continue
                if targets is not None:
                    target = targets[source['sentence_id']]
                    if (chunk.get('provider_directives', {}) != target['provider_directives']
                            or chunk.get('inline_controls', []) != target['inline_controls']):
                        continue
                saved = state['chunks'].get(chunk['chunk_id'], {})
                audio = _verified_audio(core, saved)
                if audio is None:
                    continue
                reusable[source['sentence_id']] = {
                    'sentence_id': source['sentence_id'], 'role_id': source['role_id'], 'text': source['text'],
                    'project_voice_id': resolved['project_voice_id'], 'source': chunk['source'],
                    'effective_settings': chunk['effective_settings'],
                    'provider_directives': chunk.get('provider_directives', {}),
                    'inline_controls': chunk.get('inline_controls', []), 'pause_ms': chunk['pause_ms'],
                    'audio_path': str(audio), 'audio_hash': saved['audio_hash'],
                    'speech_seconds': saved.get('speech_seconds'), 'duration_seconds': saved['duration_seconds'],
                    'job_id': jid, 'chunk_id': chunk['chunk_id'], 'subtitle_status': saved.get('subtitle_status')}
        except (OSError, ValueError, TypeError, KeyError, MakeSoundError):
            continue  # Damaged or unfinished audio is never reported as reusable.
    return {'selection_id': selection_id, 'question_id': qid,
            'performance_checked': targets is not None,
            'reusable': [reusable[sid] for sid in originals if sid in reusable],
            'remaining_sentence_ids': [sid for sid in originals if sid not in reusable],
            'network_calls': 0, 'paid_execution_authorized': False}


def _load(core, selection_id):
    selection = read_json(_path(core, selection_id))
    require(selection['project_id'] == core.read()['project_id'], 'project_mismatch', 'Selection belongs to another project.')
    _pending(core, selection['question_id'])
    handoff = read_json(core.managed_path(f".makesound/handoffs/{selection['question_id']}.json"))
    require(handoff['manifest'] == selection['manifest'], 'plan_changed', 'Manuscript changed; review a new selection.')
    return selection


def _unchanged(preset, candidate):
    voice = preset['voices'].get(candidate['project_voice_id'])
    require(voice and not voice['deleted'], 'voice_unavailable', 'Candidate was removed.')
    require(voice['source'] == candidate['source'] and voice['settings'] == candidate['settings'],
            'candidate_changed', 'Candidate changed; recreate and review the selection.')


def audition(core, selection_id, role_id, sentence_id, voice_ids=None, *, provider_directives=None, inline_controls=None):
    """Save a direct production request; caller reviews and authorizes it separately."""
    selection = _load(core, selection_id)
    candidates = selection['candidates'].get(role_id)
    require(candidates, 'missing_roles', 'Role has no recommendations.')
    selected = [c['project_voice_id'] for c in candidates] if voice_ids is None else voice_ids
    require(isinstance(selected, list) and 1 <= len(selected) <= 3 and len(set(selected)) == len(selected),
            'candidate_limit', 'Choose one to three distinct candidates.')
    by_id = {c['project_voice_id']: c for c in candidates}
    require(set(selected) <= set(by_id), 'voice_unavailable', 'Choose recommended project voices.')
    matches = [s for s in selection['manifest']['segments'] if s['sentence_id'] == sentence_id and s['role_id'] == role_id]
    require(len(matches) == 1, 'not_found', 'Choose one original sentence for this role.')
    source = matches[0]
    preset = core.read()
    request = []
    characters = 0
    require(all(by_id[vid]['settings'] == by_id[selected[0]]['settings'] for vid in selected),
            'comparison_settings', 'Compare candidates using the same speed and pitch.')
    for index, vid in enumerate(selected):
        _unchanged(preset, by_id[vid])
        directives = performance_directives(by_id[vid]['source'], provider_directives)
        characters += len(request_text({'source': by_id[vid]['source'], 'text': source['text'],
                                        'inline_controls': [] if inline_controls is None else inline_controls}))
        segment = {'paragraph_id': f'audition_{index}', 'sentence_id': f'audition_{index}',
                   'role_id': role_id, 'project_voice_id': vid, 'text': source['text']}
        if provider_directives is not None:
            segment['provider_directives'] = directives
        if inline_controls is not None:
            segment['inline_controls'] = copy.deepcopy(inline_controls)
        request.append(segment)
    aid = uid('audition_')
    request_path = core.managed_path(f'.makesound/voice-selections/{aid}.request.json')
    atomic_write(request_path, request)
    result = {'audition_id': aid, 'selection_id': selection_id, 'question_id': selection['question_id'],
              'role_id': role_id, 'source_sentence_id': sentence_id, 'source_paragraph_id': source['paragraph_id'],
              'request_path': str(request_path), 'project_voice_ids': selected, 'network_calls': 0,
              'chunks': len(request), 'characters': characters,
              'paid_execution_authorized': False, 'request_hash': digest(request)}
    result['review_hash'] = digest(result)
    atomic_write(core.managed_path(f'.makesound/voice-selections/{aid}.json'), result)
    return result


def audition_results(core, audition_id):
    """Read verified candidate audio independently of subtitle/export success."""
    from .generation import Generation
    v.identifier(audition_id)
    sample = read_json(core.managed_path(f'.makesound/voice-selections/{audition_id}.json'))
    reviewed = {k: val for k, val in sample.items() if k not in {'review_hash', 'frozen_result'}}
    require(sample['review_hash'] == digest(reviewed), 'plan_changed', 'Audition record changed.')
    require(sample.get('frozen_result'), 'not_frozen', 'Freeze the reviewed audition before reading generated audio.')
    selection = read_json(_path(core, sample['selection_id']))
    require(selection['project_id'] == core.read()['project_id'] and sample['question_id'] == selection['question_id'],
            'project_mismatch', 'Audition belongs to a different task.')
    originals = [s for s in selection['manifest']['segments']
                 if s['sentence_id'] == sample['source_sentence_id'] and s['role_id'] == sample['role_id']]
    require(len(originals) == 1, 'plan_changed', 'Original audition sentence is missing or ambiguous.')
    original = originals[0]
    candidates = {c['project_voice_id']: c for c in selection['candidates'][sample['role_id']]}
    jid = sample['frozen_result']['job_id']
    snapshot = Generation(core).load(jid)
    require(len(snapshot['chunks']) == len(sample['project_voice_ids'])
            and {c['project_voice_id'] for c in snapshot['chunks']} == set(sample['project_voice_ids']),
            'plan_changed', 'Frozen audition coverage differs.')
    state_path = core.managed_path(f'.makesound/jobs/{jid}/state.json')
    state = read_json(state_path) if state_path.exists() else {'chunks': {}}
    audio_rows, unavailable = [], []
    for chunk in snapshot['chunks']:
        vid = chunk['project_voice_id']
        candidate = candidates.get(vid)
        require(vid in sample['project_voice_ids'] and candidate
                and chunk['text'] == original['text'] and chunk['role_id'] == original['role_id']
                and chunk['source'] == candidate['source'] and chunk['effective_settings'] == candidate['settings'],
                'plan_changed', 'Frozen candidate differs from the audition.')
        saved = state['chunks'].get(chunk['chunk_id'], {})
        audio = _verified_audio(core, saved)
        if audio is None:
            unavailable.append({'project_voice_id': vid, 'name': candidate['name'],
                                'status': saved.get('status', 'not_generated'),
                                'error': saved.get('error', 'audio_not_verified')})
            continue
        audio_rows.append({'project_voice_id': vid, 'name': candidate['name'],
                           'voice_id': chunk['source']['voice_id'], 'audio_path': str(audio),
                           'audio_hash': saved['audio_hash'], 'duration_seconds': saved['duration_seconds'],
                           'source_sentence_id': original['sentence_id'], 'role_id': original['role_id'],
                           'chunk_id': chunk['chunk_id'], 'subtitle_status': saved.get('subtitle_status', 'not_reported')})
    return {'audition_id': audition_id, 'job_id': jid,
            'status': 'audio_ready' if not unavailable else 'partial' if audio_rows else 'audio_unavailable',
            'audio_count': len(audio_rows), 'expected_audio_count': len(snapshot['chunks']),
            'audio': audio_rows, 'unavailable': unavailable, 'network_calls': 0}


def freeze_audition(core, audition_id, review_hash, *, confirmed=False):
    """Freeze exactly the displayed comparison, rechecking mutable project voices."""
    require(confirmed is True, 'confirmation_required', 'Confirm the displayed audition first.')
    v.identifier(audition_id)
    path = core.managed_path(f'.makesound/voice-selections/{audition_id}.json')
    with file_lock(path.with_suffix('.lock')):
        sample = read_json(path)
        reviewed = {k: value for k, value in sample.items() if k not in {'review_hash', 'frozen_result'}}
        require(sample['review_hash'] == review_hash == digest(reviewed), 'plan_changed', 'Audition review changed.')
        request_path = core.managed_path(f'.makesound/voice-selections/{audition_id}.request.json')
        require(str(request_path) == sample['request_path'] and digest(read_json(request_path)) == sample['request_hash'],
                'plan_changed', 'Audition text changed after review.')
        # Project mutations use this same lock; keep voice validation and freezing together.
        with file_lock(core.path.with_suffix(core.path.suffix + '.lock')):
            selection = _load(core, sample['selection_id'])
            preset = core.read()
            by_id = {c['project_voice_id']: c for c in selection['candidates'][sample['role_id']]}
            for vid in sample['project_voice_ids']:
                _unchanged(preset, by_id[vid])
            if 'frozen_result' not in sample:
                from .production import plan
                sample['frozen_result'] = plan(core, request_path=request_path, confirmed=True, audio_format='wav')
                atomic_write(path, sample)
            return copy.deepcopy(sample['frozen_result'])


def bind(core, selection_id, assignments, revision, confirmed=False):
    """Submit a complete explicit user choice, accepting existing project voices too."""
    require(confirmed is True, 'confirmation_required', 'Explicit final user selection is required.')
    with file_lock(core.path.with_suffix(core.path.suffix + '.lock')):
        return _bind(core, selection_id, assignments, revision)


def _bind(core, selection_id, assignments, revision):
    selection = _load(core, selection_id)
    question = Questions(core).read(selection['question_id'])
    require(isinstance(assignments, dict) and set(assignments) == set(question['roles']),
            'missing_roles', 'Select every role explicitly.')
    preset = core.read()
    require(type(revision) is int and revision == preset['revision'], 'revision_conflict', 'Reload the project.')
    for role, vid in assignments.items():
        v.identifier(vid)
        core.resolve(explicit=vid, preset=preset)
        for candidate in selection['candidates'].get(role, []):
            if candidate['project_voice_id'] == vid:
                _unchanged(preset, candidate)
    return Questions(core).submit(selection['question_id'], assignments, revision=revision, replace_assignments=True)
