"""Persistent offline Question/Answer handoff, without pretending to wake an agent."""
from datetime import datetime, timedelta, timezone

from . import validation as v
from .core_v16 import uid
from .errors import require
from .storage import atomic_write, file_lock, read_json
import copy


class Questions:
    def __init__(self, core):
        self.core = core

    def _path(self, qid):
        v.identifier(qid)
        return self.core.managed_path(f".makesound/questions/{qid}.json")

    def create(self, job_id, harness_session_id, roles, *, ttl_seconds=86400, role_metadata=None):
        v.identifier(job_id)
        v.identifier(harness_session_id)
        require(isinstance(roles, list) and bool(roles) and len(set(roles)) == len(roles))
        for role in roles:
            v.identifier(role)
        metadata = {} if role_metadata is None else copy.deepcopy(role_metadata)
        require(isinstance(metadata, dict) and set(metadata) <= set(roles))
        for meta in metadata.values():
            v.shape(meta, {'display_name', 'appearance_summary', 'recommended_voice_description', 'recommended_project_voice_id', 'gender_requirement'})
            for key, value in meta.items():
                v.text(value)
                if key == 'recommended_project_voice_id':
                    v.identifier(value)
                if key == 'gender_requirement':
                    require(value in {'male', 'female', 'other'})
        v.no_secrets(metadata)
        require(type(ttl_seconds) is int and 1 <= ttl_seconds <= 604800)
        obj = {"question_id": uid("q_"), "job_id": job_id, "harness_session_id": harness_session_id,
               "roles": roles[:], 'role_metadata': metadata, 'assignments': {}, "status": "pending", "answer": None, "claimed_by": None,
               "expires_at": (datetime.now(timezone.utc) + timedelta(seconds=ttl_seconds)).isoformat()}
        atomic_write(self._path(obj["question_id"]), obj)
        return obj

    def read(self, qid):
        return read_json(self._path(qid))

    def assign(self, qid, role_id, voice_id, revision):
        path = self._path(qid)
        with file_lock(path.with_suffix('.lock')):
            obj = self.read(qid)
            require(obj['status'] == 'pending', 'answer_immutable', 'Question has already been answered.')
            require(datetime.now(timezone.utc) < datetime.fromisoformat(obj['expires_at']), 'question_expired', 'Question TTL expired.')
            require(role_id in obj['roles'], 'missing_roles', 'Unknown role.')
            preset = self.core.read()
            require(type(revision) is int and revision == preset['revision'], 'revision_conflict', 'Reload the project.')
            bindings = obj.setdefault('assignments', {})
            if voice_id is None:
                bindings.pop(role_id, None)
            else:
                resolved = self.core.resolve(explicit=voice_id, preset=preset)
                voice = preset['voices'][voice_id]
                bindings[role_id] = {'project_voice_id': voice_id, 'resolved': resolved,
                    'snapshot': {'project_voice_id': voice_id, 'name': voice['name'], 'category': voice['category'],
                                 'source': copy.deepcopy(voice['source']), 'settings': copy.deepcopy(voice['settings'])}}
            atomic_write(path, obj)
            return {'saved': True}

    def submit(self, qid, assignments, *, revision=None, replace_assignments=False):
        # Explicit chat choices may replace an earlier Studio draft, but callers
        # must supply a reviewed project revision. Ordinary Studio keeps snapshots.
        require(type(replace_assignments) is bool)
        require(not replace_assignments or revision is not None, 'revision_required', 'Explicit choices require a reviewed revision.')
        path = self._path(qid)
        with file_lock(path.with_suffix(".lock")):
            obj = self.read(qid)
            require(obj["status"] == "pending", "answer_immutable", "Question has already been answered.")
            require(datetime.now(timezone.utc) < datetime.fromisoformat(obj["expires_at"]), "question_expired", "Question TTL expired.")
            require(isinstance(assignments, dict) and set(assignments) == set(obj["roles"]), "missing_roles", "Assign all required roles.")
            preset = self.core.read()
            if revision is not None:
                require(type(revision) is int and revision == preset['revision'], 'revision_conflict', 'Reload the project.')
            resolved = {}
            for role, vid in assignments.items():
                require(not replace_assignments or vid is not None, 'voice_unavailable', 'Explicit chat choices cannot silently use a default.')
                binding = None if replace_assignments else obj.get('assignments', {}).get(role)
                if isinstance(vid, dict):
                    v.shape(vid, {'default_slot'}, {'default_slot'})
                    slot = vid['default_slot']
                    require(slot in {'general', 'male', 'female'}, 'invalid_default', 'Unknown default slot.')
                    resolved[role] = self.core.resolve(gender=None if slot == 'general' else slot, preset=preset)
                    require(resolved[role]['status'] == 'ready', 'voice_unavailable', 'Default voice is unavailable.')
                elif binding:
                    require(binding['project_voice_id'] == vid, 'assignment_conflict', 'Role assignment changed; reload the question.')
                    resolved[role] = copy.deepcopy(binding['resolved'])
                else:
                    resolved[role] = self.core.resolve(explicit=vid, preset=preset)
            if replace_assignments:
                obj['assignments'] = {role: {'project_voice_id': value['project_voice_id'],
                    'resolved': copy.deepcopy(value),
                    'snapshot': {'project_voice_id': value['project_voice_id'], 'name': value['name'],
                                 'category': preset['voices'].get(value['project_voice_id'], {}).get('category', 'other'),
                                 'source': copy.deepcopy(value['source']), 'settings': copy.deepcopy(value['effective_settings'])}}
                    for role, value in resolved.items()}
            obj["answer"] = {"answer_id": uid("a_"), "question_id": qid, "job_id": obj["job_id"],
                             "project_id": preset["project_id"], "assignments": dict(assignments), "resolved": resolved}
            v.no_secrets(obj)
            obj["status"] = "answered"
            atomic_write(path, obj)
            return {"answer": obj["answer"], "resume_status": "saved_for_claim", "agent_resumed": False}

    def claim(self, qid, harness_session_id):
        v.identifier(harness_session_id)
        path = self._path(qid)
        with file_lock(path.with_suffix(".lock")):
            obj = self.read(qid)
            require(obj["harness_session_id"] == harness_session_id, "session_mismatch", "Answer belongs to another Harness session.")
            require(obj["status"] == "answered", "not_answered", "No answer is ready.")
            require(obj["claimed_by"] is None, "already_claimed", "Answer was already claimed.")
            obj["claimed_by"] = harness_session_id
            atomic_write(path, obj)
            return obj["answer"]

    @staticmethod
    def management_complete():
        return {"status": "management_saved", "agent_resumed": False, "network_calls": 0}
