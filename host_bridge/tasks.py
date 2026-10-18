"""Durable reference task/submission store; no application-specific fields."""
from contextlib import contextmanager
import hashlib
import json
from pathlib import Path
import sqlite3
import threading
import time
import uuid
from . import require
from .protocol import identifier, json_object, result, submission


def _encoded(value):
    return json.dumps(value, sort_keys=True, ensure_ascii=False, allow_nan=False)


class TaskStore:
    def __init__(self, directory, application):
        self.application = identifier(application)
        self.directory = Path(directory).absolute()
        self.path = self.directory / 'tasks.sqlite3'
        # Reject links at every existing component, including the database file.
        for item in [self.path, *self.path.parents]:
            require(not item.is_symlink() and not getattr(item, 'is_junction', lambda: False)(),
                    'unsafe_path', 'Task storage must not traverse directory links.')
        self.directory.mkdir(parents=True, exist_ok=True)
        with self._db() as db:
            db.executescript('''CREATE TABLE IF NOT EXISTS tasks (
                application TEXT NOT NULL, task_id TEXT PRIMARY KEY, request_id TEXT NOT NULL,
                digest TEXT NOT NULL, operation TEXT NOT NULL, payload TEXT NOT NULL, result TEXT NOT NULL,
                UNIQUE(application, request_id));
                CREATE TABLE IF NOT EXISTS submissions (
                application TEXT NOT NULL, task_id TEXT NOT NULL, submission_id TEXT NOT NULL,
                digest TEXT NOT NULL, result TEXT NOT NULL, PRIMARY KEY(application, task_id, submission_id));''')

    @contextmanager
    def _db(self):
        db = sqlite3.connect(self.path, timeout=5)
        try:
            with db:
                yield db
        finally:
            db.close()

    def create(self, operation, payload, request_id):
        identifier(request_id)
        identifier(operation)
        json_object(payload)
        digest = hashlib.sha256(_encoded([operation, payload]).encode()).hexdigest()
        with self._db() as db:
            db.execute('BEGIN IMMEDIATE')
            old = db.execute('SELECT digest,result FROM tasks WHERE application=? AND request_id=?',
                             (self.application, request_id)).fetchone()
            if old:
                require(old[0] == digest, 'request_conflict', 'Request ID already refers to different task data.')
                return json.loads(old[1])
            task_id = 'task_' + uuid.uuid4().hex
            value = result('waiting', task_id, {'input': payload}, application=self.application, revision=0)
            db.execute('INSERT INTO tasks VALUES (?,?,?,?,?,?,?)',
                       (self.application, task_id, request_id, digest, operation, _encoded(payload), _encoded(value)))
            return value

    def read(self, task_id):
        identifier(task_id)
        with self._db() as db:
            row = db.execute('SELECT result FROM tasks WHERE application=? AND task_id=?',
                             (self.application, task_id)).fetchone()
        require(row is not None, 'not_found', 'Task does not exist in this application.')
        return json.loads(row[0])

    def submit(self, body, *, validate=None):
        submission(body)
        digest = hashlib.sha256(_encoded(body).encode()).hexdigest()
        with self._db() as db:
            db.execute('BEGIN IMMEDIATE')
            row = db.execute('SELECT result,payload FROM tasks WHERE application=? AND task_id=?',
                             (self.application, body['task_id'])).fetchone()
            require(row is not None, 'not_found', 'Task does not exist in this application.')
            previous = db.execute('SELECT digest,result FROM submissions WHERE application=? AND task_id=? AND submission_id=?',
                                  (self.application, body['task_id'], body['submission_id'])).fetchone()
            if previous:
                require(previous[0] == digest, 'submission_conflict', 'Submission ID already refers to different data.')
                return json.loads(previous[1])
            current = json.loads(row[0])
            require(current['status'] == 'waiting', 'task_completed', 'Terminal task is immutable; start a new task to revise it.')
            require(current['revision'] == body['expected_revision'], 'revision_conflict', 'Reload the task before submitting.')
            if validate is not None:
                validate(body['action'], body['data'], json.loads(row[1]))
            value = result('completed' if body['action'] == 'complete' else 'cancelled', body['task_id'], body['data'],
                           application=self.application, revision=current['revision'] + 1)
            db.execute('UPDATE tasks SET result=? WHERE application=? AND task_id=?',
                       (_encoded(value), self.application, body['task_id']))
            db.execute('INSERT INTO submissions VALUES (?,?,?,?,?)',
                       (self.application, body['task_id'], body['submission_id'], digest, _encoded(value)))
        # Only return completion after the result and receipt commit together.
        return value

    def wait(self, task_id, timeout, cancel_event):
        deadline = time.monotonic() + timeout
        while True:
            value = self.read(task_id)
            if value['status'] != 'waiting':
                return value
            if cancel_event is not None and cancel_event.is_set():
                # A cancelled tool request does not cancel the user's task.
                return {**value, 'wait_cancelled': True}
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                return value
            (cancel_event or threading.Event()).wait(min(.1, remaining))


class SubmissionJournal(TaskStore):
    """Idempotency journal for applications with an existing durable store.

    apply(body, recovering) must implement recovery after its own commit. This
    cannot turn two unrelated databases into one atomic transaction.
    """
    def commit(self, body, apply):
        submission(body)
        digest = hashlib.sha256(_encoded(body).encode()).hexdigest()
        key = (self.application, body['task_id'], body['submission_id'])
        with self._db() as db:
            db.execute('BEGIN IMMEDIATE')
            old = db.execute('SELECT digest,result FROM submissions WHERE application=? AND task_id=? AND submission_id=?', key).fetchone()
            if old:
                require(old[0] == digest, 'submission_conflict', 'Submission ID already refers to different data.')
                if old[1]:
                    return json.loads(old[1])
            else:
                # Durable intent makes interrupted business commits recoverable.
                db.execute('INSERT INTO submissions VALUES (?,?,?,?,?)', (*key, digest, ''))
            db.commit()
            db.execute('BEGIN IMMEDIATE')
            latest = db.execute('SELECT result FROM submissions WHERE application=? AND task_id=? AND submission_id=?', key).fetchone()
            if latest[0]:
                return json.loads(latest[0])
            from .protocol import validate_result
            value = validate_result(apply(body, old is not None))
            db.execute('UPDATE submissions SET result=? WHERE application=? AND task_id=? AND submission_id=?',
                       (_encoded(value), *key))
        return value
