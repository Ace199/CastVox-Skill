"""Three-role acceptance rehearsal; stop at draft reviews, never synthesize."""
import json
import unittest
from pathlib import Path
from unittest.mock import patch

from tests.helpers import Fixture
from tests.unit.test_v16 import SOURCE
from makesound.core_v16 import ProjectCore
from makesound.offline_harness import prepare
from makesound.questions import Questions
from makesound.performance_plan import propose
from makesound.voice_selection import create, audition


class MacbethEntryDryRun(Fixture, unittest.TestCase):
    def setUp(self):
        super().setUp()
        lines = [
            ('r1', '读《麦克白》时，我觉得预言像一面镜子，让人看见自己的欲望。'),
            ('r2', '我更在意他的选择：听见一种可能，为什么就要把它变成唯一的路？'),
            ('r3', '也许值得讨论的，是人在追逐权力时，怎样一步步失去对自己的约束。'),
            ('r1', '所以我们讨论命运时，也不能把一个人的责任全部交给预言。'),
            ('r2', '而文学最吸引我的地方，就是让我们看到选择背后的犹豫。'),
            ('r3', '读完再想想自己的选择，这场讨论也就有了意义。'),
        ]
        self.manifest = {'roles':['r1','r2','r3'], 'role_metadata':{
            role:{'display_name':name} for role,name in zip(['r1','r2','r3'],['阿文','小夏','老周'])},
            'segments':[{'paragraph_id':f'p{i}','sentence_id':f's{i}','role_id':role,'text':text}
                        for i,(role,text) in enumerate(lines,1)]}
        self.core = ProjectCore(self.a)
        # Belt and braces: no real adapter, fake synthesis or execution can run.
        for target in ('makesound.generation.Generation.run',
                       'makesound.providers.FakeProvider.synthesize',
                       'makesound.minimax_provider.MiniMaxProvider.__init__'):
            blocked = patch(target, side_effect=AssertionError('Generation forbidden in rehearsal'))
            blocked.start()
            self.addCleanup(blocked.stop)

    def assert_no_generation(self):
        self.assertFalse((self.a/'.makesound/jobs').exists())
        self.assertFalse((self.a/'.makesound/cache').exists())
        self.assertFalse((self.a/'outputs/audio').exists())

    def test_manual_existing_voices_stop_at_three_sentence_draft(self):
        assignments = {}
        for role in self.manifest['roles']:
            _, assignments[role] = self.core.add_voice('测试声音_'+role,'other',
                {**SOURCE,'voice_id':'TEST_'+role}, self.core.read()['revision'])
        self.core.read()  # Documented recipe A.
        revision_before_prepare = self.core.read()['revision']
        qid = prepare(self.core,self.manifest)['question_id']
        self.assertEqual(self.core.read()['revision'], revision_before_prepare)
        Questions(self.core).submit(qid,assignments,revision=self.core.read()['revision'],replace_assignments=True)
        answer = Questions(self.core).read(qid)
        ids = ['s1','s2','s3']
        draft = propose(self.core,qid,[{'sentence_id':sid,'emotion':'自动',
            'delivery_notes':'自然讨论','pause_after_ms':0} for sid in ids],sentence_ids=ids)
        self.assertEqual(draft['status'],'pending_confirmation')
        self.assertEqual(draft['sentence_ids'],ids)
        self.assertEqual(set(answer['answer']['assignments']),set(self.manifest['roles']))
        self.assert_no_generation()
        print(json.dumps({'route':1,'roles':3,'review_sentences':3,'question':'answered',
                          'review':'pending','generation_calls':0,'network_calls':0}))

    def test_recommended_voices_stop_before_binding_or_freezing(self):
        self.core.read()
        qid = prepare(self.core,self.manifest)['question_id']
        recs = {role:[{'name':'测试主选_'+role,'category':'other',
            'source':{**SOURCE,'voice_id':'TEST_'+role},'settings':{'speed':1.0,'pitch':0},
            'reason':'离线流程占位，不是实际听感推荐','evidence_url':'https://example.invalid/test-fixture'}]
            for role in self.manifest['roles']}
        selection = create(self.core,qid,recs,self.core.read()['revision'])
        for i,role in enumerate(self.manifest['roles'],1):
            sample = audition(self.core,selection['selection_id'],role,f's{i}')
            request = json.loads(Path(sample['request_path']).read_text(encoding='utf-8'))
            self.assertEqual(len(request),1)
            self.assertEqual(request[0]['text'],self.manifest['segments'][i-1]['text'])
            self.assertFalse(sample['paid_execution_authorized'])
        question = Questions(self.core).read(qid)
        self.assertEqual(question['status'],'pending')
        self.assertIsNone(question['answer'])
        self.assertEqual(len(self.core.read()['voices']),3)
        self.assert_no_generation()
        print(json.dumps({'route':2,'roles':3,'candidates':3,'audition_requests':3,
                          'question':'pending','generation_calls':0,'network_calls':0}))
