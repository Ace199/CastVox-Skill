import unittest
from host_bridge import Bridge, BridgeError


class Application:
    def start(self, operation, payload, request_id):
        return {'protocol_version': '1.0', 'status': 'waiting', 'task_id': 'task-one',
                'revision': 0, 'data': {'choices': ['A', 'B']}, 'error': None, 'handle': 'private',
                'url': 'http://127.0.0.1:12345', 'resource': {'task_id': 'task-one'}}

    def wait(self, handle, timeout, cancel_event):
        return {'protocol_version': '1.0', 'status': 'completed', 'task_id': 'task-one',
                'revision': 1, 'data': {'selected': 'B'}, 'error': None}

    def read(self, resource):
        return self.wait(None, 0, None)

    def close(self):
        pass


class ProtocolTests(unittest.TestCase):
    def test_versioned_start_wait_read_have_same_envelope_and_legacy_stays_unchanged(self):
        with Bridge({'forms': Application()}) as bridge:
            args = {'protocol_version': '1.0', 'application': 'forms', 'operation': 'choose',
                    'payload': {}, 'request_id': 'one'}
            ready = bridge.call('host_bridge_start', args)
            self.assertEqual(ready['status'], 'waiting')
            self.assertEqual(ready['application'], 'forms')
            self.assertEqual(ready['wait_tool']['arguments']['protocol_version'], '1.0')
            saved = bridge.call('host_bridge_wait', ready['wait_tool']['arguments'])
            self.assertEqual(saved['data'], {'selected': 'B'})
            self.assertEqual(saved['task_id'], ready['task_id'])
            read = bridge.call('host_bridge_read', {'protocol_version': '1.0', 'application': 'forms', 'resource': ready['resource']})
            self.assertEqual(read['data'], saved['data'])

    def test_bad_adapter_result_and_unsupported_version_are_rejected(self):
        class Broken(Application):
            def wait(self, *args):
                return {**super().wait(*args), 'data': ['not-an-object']}
        with Bridge({'forms': Broken()}) as bridge:
            args = {'protocol_version': '1.0', 'application': 'forms', 'operation': 'choose', 'payload': {}, 'request_id': 'one'}
            ready = bridge.call('host_bridge_start', args)
            with self.assertRaises(BridgeError):
                bridge.call('host_bridge_wait', ready['wait_tool']['arguments'])
            with self.assertRaises(BridgeError) as ctx:
                bridge.call('host_bridge_start', {**args, 'protocol_version': '99'})
            self.assertEqual(ctx.exception.code, 'unsupported_protocol')

    def test_mcp_error_has_standard_envelope_without_breaking_old_error_fields(self):
        from host_bridge.protocol import error_result
        error = BridgeError('unknown_application', 'Application is not registered.')
        value = error_result(error, {'protocol_version': '1.0', 'application': 'unknown'})
        self.assertEqual(value['status'], 'failed')
        self.assertEqual(value['error']['code'], 'unknown_application')
        self.assertFalse(value['error']['retryable'])
        self.assertEqual(error_result(error, {})['status'], 'error')

    def test_version_negotiation_does_not_recreate_existing_legacy_task(self):
        class Counted(Application):
            count = 0
            def start(self, *args):
                self.count += 1
                return super().start(*args)
        app = Counted()
        with Bridge({'forms': app}) as bridge:
            args = {'application': 'forms', 'operation': 'choose', 'payload': {}, 'request_id': 'one'}
            old = bridge.call('host_bridge_start', args)
            new = bridge.call('host_bridge_start', {**args, 'protocol_version': '1.0'})
            self.assertEqual(new['handle'], old['handle'])
            self.assertEqual(app.count, 1)

    def test_adapter_cannot_deliver_another_tasks_result_to_waiter(self):
        class WrongTask(Application):
            def wait(self, *args):
                return {**super().wait(*args), 'task_id': 'different-task'}
        with Bridge({'forms': WrongTask()}) as bridge:
            ready = bridge.call('host_bridge_start', {'protocol_version': '1.0', 'application': 'forms',
                'operation': 'choose', 'payload': {}, 'request_id': 'one'})
            with self.assertRaises(BridgeError) as ctx:
                bridge.call('host_bridge_wait', ready['wait_tool']['arguments'])
            self.assertEqual(ctx.exception.code, 'task_mismatch')

    def test_json_boundary_and_identifiers_match_documented_submission_contract(self):
        from host_bridge.protocol import identifier, json_object, loads, submission
        self.assertEqual(identifier('a' * 128), 'a' * 128)
        for text in ('a' * 129, '../outside', ''):
            with self.assertRaises(BridgeError):
                identifier(text)
        for text in ('{"a":1,"a":2}', '{"number":NaN}', '{"number":Infinity}'):
            with self.assertRaises(BridgeError):
                loads(text)
        with self.assertRaises(BridgeError):
            json_object({'text': '中' * 400000})
        with self.assertRaises(BridgeError):
            submission({'protocol_version': '1.0', 'task_id': 'task_one', 'submission_id': 'click_one',
                        'expected_revision': True, 'action': 'complete', 'data': {}})
