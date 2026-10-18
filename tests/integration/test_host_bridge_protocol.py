import json
from pathlib import Path
import tempfile
import socket
import unittest
import urllib.error
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from unittest.mock import patch

from host_bridge import Bridge
from host_bridge.example import FormApplication
from tests.helpers import Fixture


def session_from(url):
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
    with opener.open(url + '/host-bridge/session.js', timeout=3) as response:
        text = response.read().decode()
    return opener, json.loads(text.split('Object.freeze(', 1)[1].rsplit(');', 1)[0])


def post(opener, url, session, body, *, origin=None):
    req = urllib.request.Request(url + '/api/host-bridge/v1/submit', data=json.dumps(body).encode(),
        headers={'Authorization': 'Bearer ' + session['token'], 'X-CSRF-Token': session['csrf'],
                 'Origin': origin or url, 'Content-Type': 'application/json'})
    with opener.open(req, timeout=3) as response:
        return json.loads(response.read())


class FormProtocol(unittest.TestCase):
    def setUp(self):
        scratch = Path(__file__).resolve().parents[2] / '.test-tmp'
        scratch.mkdir(exist_ok=True)
        self.temp = tempfile.TemporaryDirectory(dir=scratch)
        self.addCleanup(self.temp.cleanup)
        self.bridge = Bridge({'forms': FormApplication(Path(self.temp.name))})
        self.addCleanup(self.bridge.close)

    def test_real_form_http_commit_returns_to_waiter_and_survives_restart(self):
        args = {'protocol_version': '1.0', 'application': 'forms', 'operation': 'choose',
                'request_id': 'form-one', 'payload': {'title': '方案选择', 'choices': ['A', 'B']}}
        ready = self.bridge.call('host_bridge_start', args)
        opener, session = session_from(ready['url'])
        body = {'protocol_version': '1.0', 'task_id': ready['task_id'], 'submission_id': 'click-one',
                'expected_revision': ready['revision'], 'action': 'complete', 'data': {'selected': 'B'}}
        with ThreadPoolExecutor(max_workers=1) as pool:
            pending = pool.submit(self.bridge.call, 'host_bridge_wait', {**ready['wait_tool']['arguments'], 'timeout': 3})
            receipt = post(opener, ready['url'], session, body)
            saved = pending.result(timeout=4)
        self.assertEqual(receipt, saved)
        self.assertEqual(saved['status'], 'completed')
        self.assertEqual(post(opener, ready['url'], session, body), receipt)
        self.bridge.close()
        with Bridge({'forms': FormApplication(Path(self.temp.name))}) as restarted:
            read = restarted.call('host_bridge_read', {'protocol_version': '1.0', 'application': 'forms', 'resource': ready['resource']})
        self.assertEqual(read, saved)

    def test_bad_origin_task_revision_and_choice_do_not_complete_task(self):
        ready = self.bridge.call('host_bridge_start', {'protocol_version': '1.0', 'application': 'forms', 'operation': 'choose',
            'request_id': 'form-one', 'payload': {'title': '选择', 'choices': ['A']}})
        opener, session = session_from(ready['url'])
        body = {'protocol_version': '1.0', 'task_id': ready['task_id'], 'submission_id': 'one',
                'expected_revision': 0, 'action': 'complete', 'data': {'selected': 'A'}}
        for changed, origin, status in [(body, 'https://untrusted.example', 403),
            ({**body, 'task_id': 'task_other'}, None, 400), ({**body, 'expected_revision': 9}, None, 409),
            ({**body, 'data': {'selected': 'invalid'}}, None, 400)]:
            with self.assertRaises(urllib.error.HTTPError) as ctx:
                post(opener, ready['url'], session, changed, origin=origin)
            self.assertEqual(ctx.exception.code, status)
            value = json.loads(ctx.exception.read())
            self.assertEqual(value['status'], 'failed')
            self.assertTrue(value['error']['code'])
        self.assertEqual(self.bridge.call('host_bridge_wait', {'handle': ready['handle'], 'timeout': 0})['status'], 'waiting')


class SoundMakerProtocol(Fixture, unittest.TestCase):
    def setUp(self):
        super().setUp()
        self.net.stop()
        original = socket.socket.connect
        def local_only(sock, address):
            if address[0] != '127.0.0.1':
                raise AssertionError('External network forbidden')
            return original(sock, address)
        guard = patch.object(socket.socket, 'connect', local_only)
        guard.start()
        self.addCleanup(guard.stop)

    def test_v1_submission_preserves_legacy_answer_and_mcp_formats(self):
        from makesound.host_application import SoundMakerApplication
        application = SoundMakerApplication([self.a])
        with Bridge({'soundmaker': application}) as bridge:
            args = {'protocol_version': '1.0', 'application': 'soundmaker', 'operation': 'smoke_binding',
                    'request_id': 'new-protocol', 'payload': {}}
            ready = bridge.call('host_bridge_start', args)
            opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
            with opener.open(ready['url'] + '/js/session.js', timeout=3) as response:
                text = response.read().decode()
            session = json.loads(text.split('Object.freeze(', 1)[1].rsplit(');', 1)[0])
            body = {'protocol_version': '1.0', 'task_id': ready['task_id'], 'submission_id': 'one',
                    'expected_revision': 0, 'action': 'complete',
                    'data': {'assignments': {'test_narrator': ready['data']['project_voice_id']}}}
            with self.assertRaises(urllib.error.HTTPError) as ctx:
                post(opener, ready['url'], session, body, origin='https://untrusted.example')
            self.assertEqual(ctx.exception.code, 403)
            self.assertEqual(json.loads(ctx.exception.read())['status'], 'failed')
            with ThreadPoolExecutor(max_workers=1) as pool:
                pending = pool.submit(bridge.call, 'host_bridge_wait', {**ready['wait_tool']['arguments'], 'timeout': 3})
                receipt = post(opener, ready['url'], session, body)
                saved = pending.result(timeout=4)
            self.assertEqual(saved['status'], 'completed')
            self.assertEqual(saved['data']['answer_id'], receipt['data']['answer']['answer_id'])
            self.assertEqual(post(opener, ready['url'], session, body), receipt)
            legacy = bridge.call('host_bridge_read', {'application': 'soundmaker', 'resource': ready['resource']})
            self.assertEqual(legacy['status'], 'binding_saved')
            self.assertEqual(legacy['answer'], saved['data']['answer'])
