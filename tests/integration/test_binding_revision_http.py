"""Loopback-only role restoration and save, without synthesis or a real host."""
import json
import threading
import urllib.request
import unittest

from tests.helpers import Fixture
from tests.unit.test_v16 import SOURCE
from makesound.core_v16 import ProjectCore
from makesound.offline_harness import prepare
from makesound.questions import Questions
from makesound.binding_revision import create, compare
from makesound.studio_backend import StudioBackend
from studio_v16_server import create_server


class BindingRevisionHTTP(Fixture, unittest.TestCase):
    def test_reopened_task_retains_roles_bindings_and_saves_only_new_version(self):
        self.net.stop()
        core = ProjectCore(self.a)
        _, original = core.add_voice('原声', 'other', SOURCE, 0)
        _, replacement = core.add_voice('新声', 'other', {**SOURCE, 'voice_id':'replacement'}, 1)
        qid = prepare(core, {'roles':['a','b'], 'role_metadata':{
            'a':{'display_name':'阿文'}, 'b':{'display_name':'小夏'}}, 'segments':[
                {'paragraph_id':'p','sentence_id':'s1','role_id':'a','text':'原文一'},
                {'paragraph_id':'p','sentence_id':'s2','role_id':'b','text':'原文二'}]})['question_id']
        questions = Questions(core)
        questions.submit(qid, {'a':original,'b':original})
        before = questions.read(qid)
        revision = create(core, qid)['question_id']
        server = create_server(StudioBackend(core, config_paths={}, allow_fake=True), question_id=revision)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        origin = f'http://127.0.0.1:{server.server_port}'
        opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
        def request(path, data=None):
            req = urllib.request.Request(origin+path,
                data=json.dumps(data).encode() if data is not None else None,
                headers={'Authorization':'Bearer '+server.session_token, 'X-CSRF-Token':server.csrf_token,
                         'Origin':origin, 'Content-Type':'application/json'})
            with opener.open(req, timeout=3) as response:
                return json.loads(response.read())
        try:
            restored = request('/api/v16/questions/'+revision)
            self.assertEqual(restored['roles'], ['a','b'])
            self.assertEqual(restored['role_metadata']['a']['display_name'], '阿文')
            self.assertEqual(restored['assignments']['b']['snapshot']['name'], '原声')
            request('/api/v16/assignments', {'question_id':revision,'role_id':'a',
                'project_voice_id':replacement,'revision':core.read()['revision']})
            request('/api/v16/answers', {'question_id':revision,'assignments':{'a':replacement,'b':original},
                'revision':core.read()['revision']})
            self.assertEqual(compare(core,revision)['affected_sentence_ids'], ['s1'])
            self.assertEqual(questions.read(qid), before)
            latest = create(core,qid)['question_id']
            self.assertEqual(questions.read(latest)['assignments']['a']['project_voice_id'], replacement)
            self.assertFalse((self.a/'.makesound/jobs').exists())
        finally:
            server.shutdown()
            server.server_close()
            thread.join(timeout=5)
