import unittest
from pathlib import Path
import tempfile
import threading
from concurrent.futures import ThreadPoolExecutor
from host_bridge import BridgeError


class TaskStoreTests(unittest.TestCase):
    def setUp(self):
        from host_bridge.tasks import TaskStore
        scratch = Path(__file__).resolve().parents[2] / '.test-tmp'
        scratch.mkdir(exist_ok=True)
        self.temp = tempfile.TemporaryDirectory(dir=scratch)
        self.addCleanup(self.temp.cleanup)
        self.store = TaskStore(Path(self.temp.name), 'forms')

    def test_commit_is_durable_and_duplicate_submission_returns_exact_same_receipt(self):
        from host_bridge.tasks import TaskStore
        task = self.store.create('choose', {'choices': ['A', 'B']}, 'request-one')
        body = {'protocol_version': '1.0', 'task_id': task['task_id'], 'submission_id': 'click-one',
                'expected_revision': 0, 'action': 'complete', 'data': {'selected': 'B'}}
        saved = self.store.submit(body)
        self.assertEqual(saved['status'], 'completed')
        restarted = TaskStore(Path(self.temp.name), 'forms')
        self.assertEqual(restarted.read(task['task_id']), saved)
        self.assertEqual(restarted.submit(body), saved)
        with self.assertRaises(BridgeError) as ctx:
            restarted.submit({**body, 'data': {'selected': 'A'}})
        self.assertEqual(ctx.exception.code, 'submission_conflict')

    def test_stale_revision_wrong_task_and_unsupported_action_leave_task_pending(self):
        task = self.store.create('choose', {}, 'one')
        body = {'protocol_version': '1.0', 'task_id': task['task_id'], 'submission_id': 'click-one',
                'expected_revision': 1, 'action': 'complete', 'data': {}}
        for changed in [body, {**body, 'task_id': '../outside'}, {**body, 'action': 'execute'}, {**body, 'extra': True}]:
            with self.assertRaises(BridgeError):
                self.store.submit(changed)
        self.assertEqual(self.store.read(task['task_id'])['status'], 'waiting')

    def test_create_retry_conflict_cancel_and_terminal_immutability(self):
        task = self.store.create('choose', {}, 'one')
        self.assertEqual(self.store.create('choose', {}, 'one'), task)
        with self.assertRaises(BridgeError):
            self.store.create('choose', {'different': True}, 'one')
        body = {'protocol_version': '1.0', 'task_id': task['task_id'], 'submission_id': 'cancel-one',
                'expected_revision': 0, 'action': 'cancel', 'data': {}}
        self.assertEqual(self.store.submit(body)['status'], 'cancelled')
        with self.assertRaises(BridgeError):
            self.store.submit({**body, 'submission_id': 'another', 'action': 'complete'})

    def test_concurrent_duplicate_submissions_commit_one_identical_result(self):
        task = self.store.create('choose', {}, 'one')
        body = {'protocol_version': '1.0', 'task_id': task['task_id'], 'submission_id': 'one',
                'expected_revision': 0, 'action': 'complete', 'data': {'selected': 'A'}}
        with ThreadPoolExecutor(max_workers=4) as pool:
            values = list(pool.map(self.store.submit, [body] * 4))
        self.assertTrue(all(item == values[0] for item in values))
        self.assertEqual(values[0]['revision'], 1)

    def test_cancelled_wait_preserves_task(self):
        task = self.store.create('choose', {}, 'one')
        event = threading.Event()
        event.set()
        value = self.store.wait(task['task_id'], 50, event)
        self.assertEqual(value['status'], 'waiting')
        self.assertTrue(value['wait_cancelled'])
        self.assertEqual(self.store.read(task['task_id']), task)

    def test_external_journal_recovers_business_commit_before_receipt(self):
        from host_bridge.tasks import SubmissionJournal
        journal = SubmissionJournal(Path(self.temp.name) / 'journal', 'forms')
        body = {'protocol_version': '1.0', 'task_id': 'task_one', 'submission_id': 'one',
                'expected_revision': 0, 'action': 'complete', 'data': {'selected': 'A'}}
        calls = []
        def apply(value, recovering):
            calls.append(recovering)
            if not recovering:
                raise RuntimeError('simulated interruption after business commit')
            from host_bridge.protocol import result
            return result('completed', value['task_id'], value['data'], revision=1, application='forms')
        with self.assertRaises(RuntimeError):
            journal.commit(body, apply)
        saved = journal.commit(body, apply)
        self.assertEqual(journal.commit(body, apply), saved)
        self.assertEqual(calls, [False, True])
