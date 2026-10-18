import unittest
import threading
from concurrent.futures import ThreadPoolExecutor


class DummyApplication:
    def start(self, operation, payload, request_id):
        return {'handle': 'app-handle', 'url': 'http://127.0.0.1:12345', 'operation': operation}

    def wait(self, handle, timeout, cancel_event):
        return {'status': 'completed', 'value': 'plain form result'}

    def read(self, resource):
        return {'status': 'completed', 'value': resource}

    def close(self):
        pass


class GenericBridgeTests(unittest.TestCase):
    def test_non_soundmaker_application_can_start_wait_read(self):
        from host_bridge import Bridge
        with Bridge({'forms': DummyApplication()}) as bridge:
            names = [x['name'] for x in bridge.tools()]
            self.assertEqual(names, ['host_bridge_status', 'host_bridge_start', 'host_bridge_wait', 'host_bridge_read'])
            ready = bridge.call('host_bridge_start', {'application': 'forms', 'operation': 'review', 'payload': {}, 'request_id': 'one'})
            self.assertEqual(ready['wait_tool']['name'], 'host_bridge_wait')
            result = bridge.call('host_bridge_wait', ready['wait_tool']['arguments'])
            self.assertEqual(result['value'], 'plain form result')
            self.assertEqual(bridge.call('host_bridge_read', {'application': 'forms', 'resource': {'id': 'x'}})['value'], {'id': 'x'})

    def test_unknown_application_or_handle_cannot_execute_and_arguments_validated(self):
        from host_bridge import Bridge, BridgeError
        with Bridge({'forms': DummyApplication()}) as bridge:
            for tool, args in [('host_bridge_start', {'application': 'shell', 'operation': 'exec', 'payload': {}, 'request_id': 'x'}),
                               ('host_bridge_wait', {'handle': 'forged'}),
                               ('host_bridge_wait', {'handle': [], 'timeout': 2}),
                               ('host_bridge_status', {'command': 'anything'})]:
                with self.assertRaises(BridgeError):
                    bridge.call(tool, args)

    def test_retry_reuses_handle_and_changed_payload_is_rejected(self):
        from host_bridge import Bridge, BridgeError
        with Bridge({'forms': DummyApplication()}) as bridge:
            args = {'application': 'forms', 'operation': 'review', 'payload': {}, 'request_id': 'one'}
            ready = bridge.call('host_bridge_start', args)
            self.assertEqual(bridge.call('host_bridge_start', args), ready)
            with self.assertRaises(BridgeError):
                bridge.call('host_bridge_start', {**args, 'payload': {'different': True}})

    def test_cancel_and_duplicate_wait_do_not_close_other_applications(self):
        from host_bridge import Bridge, BridgeError
        entered = threading.Event()
        class WaitingApplication(DummyApplication):
            def wait(self, handle, timeout, cancel_event):
                entered.set()
                cancel_event.wait(2)
                return {'status': 'cancelled' if cancel_event.is_set() else 'waiting'}
        with Bridge({'forms': WaitingApplication()}) as bridge, ThreadPoolExecutor(max_workers=1) as pool:
            ready = bridge.call('host_bridge_start', {'application': 'forms', 'operation': 'review', 'payload': {}, 'request_id': 'one'})
            event = threading.Event()
            pending = pool.submit(bridge.call, 'host_bridge_wait', {'handle': ready['handle']}, cancel_event=event)
            self.assertTrue(entered.wait(1))
            try:
                with self.assertRaises(BridgeError) as ctx:
                    bridge.call('host_bridge_wait', {'handle': ready['handle'], 'timeout': 0})
                self.assertEqual(ctx.exception.code, 'already_waiting')
            finally:
                event.set()
            self.assertEqual(pending.result(timeout=2)['status'], 'cancelled')
            self.assertEqual(bridge.call('host_bridge_status', {})['status'], 'ready')
