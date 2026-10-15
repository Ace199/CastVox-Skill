"""Persistent offline Question/Answer handoff, without pretending to wake an agent."""
from datetime import datetime, timedelta, timezone

from . import validation as v
from .core_v16 import uid
from .errors import require
from .storage import atomic_write, file_lock, read_json


class Questions:
    def __init__(self, core):
        self.core = core

    def _path(self, qid):
        v.identifier(qid)
        return self.core.managed_path(f".makesound/questions/{qid}.json")

    def create(self, job_id, harness_session_id, roles, *, ttl_seconds=86400):
        v.identifier(job_id)
        v.identifier(harness_session_id)
        require(isinstance(roles, list) and bool(roles) and len(set(roles)) == len(roles))
        for role in roles:
            v.identifier(role)
        require(type(ttl_seconds) is int and 1 <= ttl_seconds <= 604800)
        obj = {"question_id": uid("q_"), "job_id": job_id, "harness_session_id": harness_session_id,
               "roles": roles[:], "status": "pending", "answer": None, "claimed_by": None,
               "expires_at": (datetime.now(timezone.utc) + timedelta(seconds=ttl_seconds)).isoformat()}
        atomic_write(self._path(obj["question_id"]), obj)
        return obj

    def read(self, qid):
        return read_json(self._path(qid))

    def submit(self, qid, assignments):
        path = self._path(qid)
        with file_lock(path.with_suffix(".lock")):
            obj = self.read(qid)
            require(obj["status"] == "pending", "answer_immutable", "Question has already been answered.")
            require(datetime.now(timezone.utc) < datetime.fromisoformat(obj["expires_at"]), "question_expired", "Question TTL expired.")
            require(isinstance(assignments, dict) and set(assignments) == set(obj["roles"]), "missing_roles", "Assign all required roles.")
            preset = self.core.read()
            resolved = {role: self.core.resolve(explicit=vid, preset=preset) for role, vid in assignments.items()}
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
