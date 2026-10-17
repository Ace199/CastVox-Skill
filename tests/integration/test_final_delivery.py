import copy
import unittest
import wave
from pathlib import Path

from tests.helpers import Fixture
from tests.unit.test_v16 import SOURCE
from makesound.core_v16 import ProjectCore
from makesound.offline_harness import prepare
from makesound.questions import Questions
from makesound.generation import Generation
from makesound.errors import MakeSoundError
from makesound.storage import atomic_write, read_json


class FinalDelivery(Fixture, unittest.TestCase):
    def setUp(self):
        super().setUp()
        self.core = ProjectCore(self.a)
        _, self.vid = self.core.add_voice('旁白声音', 'other', SOURCE, 0)
        self.manifest = {'roles': ['r1'], 'role_metadata': {'r1': {'display_name': '旁白'}},
                         'segments': [{'paragraph_id': 'p1', 'sentence_id': f's{i}',
                                       'role_id': 'r1', 'text': f'原句{i}。'} for i in (1, 2)]}
        self.qid = prepare(self.core, self.manifest)['question_id']
        Questions(self.core).submit(self.qid, {'r1': self.vid})
        self.items = [{'sentence_id': f's{i}', 'emotion': '自动', 'delivery_notes': '自然叙述',
                       'pause_after_ms': 400 if i == 1 else 0} for i in (1, 2)]

    def error(self, code, call):
        with self.assertRaises(MakeSoundError) as caught:
            call()
        self.assertEqual(caught.exception.code, code)

    def generate(self):
        from makesound.performance_plan import propose, confirm
        from makesound.production import plan
        review = propose(self.core, self.qid, self.items, sentence_ids=['s1', 's2'])
        confirm(self.core, review['plan_id'], review['plan_hash'])
        frozen = plan(self.core, performance_plan=review['plan_id'])
        state = Generation(self.core).run(frozen['job_id'])
        return frozen['job_id'], state

    def test_set_default_from_answer_is_v16_scoped_and_repeatable(self):
        from makesound.project_defaults import save_from_answer
        before = Questions(self.core).read(self.qid)
        result = save_from_answer(self.core, self.qid, self.core.read()['revision'])
        self.assertEqual(result['defaults']['general'], self.vid)
        again = save_from_answer(self.core, self.qid, self.core.read()['revision'])
        self.assertEqual(result['revision'], again['revision'])
        self.assertFalse((self.a / '.makesound/preset.json').exists())
        self.assertEqual(before, Questions(self.core).read(self.qid))
        self.core.edit_voice(self.vid, {'settings': {'speed': 0.8}}, self.core.read()['revision'])
        self.error('binding_changed', lambda: save_from_answer(self.core, self.qid, self.core.read()['revision']))

    def test_export_removes_only_recorded_tail_and_inserts_gap_once(self):
        from makesound.final_delivery import publish
        jid, state = self.generate()
        before = copy.deepcopy(state)
        result = publish(self.core, 'task1', '测试交付', self.qid, self.items, [jid], version='v01_初版')
        self.assertEqual(result['audio_status'], 'complete')
        self.assertEqual(result['subtitle_status'], 'missing')
        self.assertEqual(result['status'], 'audio_ready_subtitles_missing')
        self.assertAlmostEqual(result['duration_seconds'], 12.4, places=5)
        for row in result['segments']:
            with wave.open(row['audio_path'], 'rb') as f:
                self.assertEqual(f.getnframes() / f.getframerate(), 6.0)
        again = publish(self.core, 'task1', '测试交付', self.qid, self.items, [jid], version='v01_初版')
        self.assertEqual(again, result)
        self.assertEqual(read_json(self.core.managed_path(f'.makesound/jobs/{jid}/state.json')), before)
        Path(result['segments'][0]['audio_path']).write_bytes(b'user edit')
        self.error('file_conflict', lambda: publish(self.core, 'task1', '测试交付', self.qid, self.items, [jid], version='v01_初版'))

    def test_missing_or_mismatched_audio_never_gets_published(self):
        from makesound.final_delivery import publish
        jid, state = self.generate()
        state['chunks']['chunk_000001']['status'] = 'billing_unknown'
        atomic_write(self.core.managed_path(f'.makesound/jobs/{jid}/state.json'), state)
        self.error('delivery_incomplete', lambda: publish(self.core, 'task1', '测试交付', self.qid, self.items, [jid], version='v01'))
        self.assertFalse((self.a / '配音/测试交付/v01').exists())

    def test_emotion_codes_cannot_silently_become_automatic(self):
        from makesound.performance_plan import propose
        from makesound.voice_selection import targets_from_items
        items = copy.deepcopy(self.items)
        items[0]['emotion'] = 'calm'
        self.error('emotion_not_mapped', lambda: propose(self.core, self.qid, items))
        self.error('emotion_not_mapped', lambda: targets_from_items(self.core, self.qid, items))
        targets = targets_from_items(self.core, self.qid, self.items)
        self.assertEqual(targets['s1'], {'provider_directives': {}, 'inline_controls': []})

    def test_same_items_drive_reuse_generation_and_subtitle_delivery(self):
        from makesound.voice_selection import create, audition, freeze_audition, bind
        from makesound.final_delivery import review, publish
        from makesound.performance_plan import confirm
        from makesound.production import plan
        class OfflineMiniMax:
            def bind(self, *args):
                pass

            def synthesize(self, chunk, path, **kwargs):
                with wave.open(str(path), 'wb') as audio:
                    audio.setnchannels(1); audio.setsampwidth(2); audio.setframerate(32000)
                    audio.writeframes(b'\0\0' * (3200 + chunk['pause_ms'] * 32))
                return {'speech_seconds': .1, 'duration_seconds': .1 + chunk['pause_ms'] / 1000,
                        'subtitle_status': 'verified_timing',
                        'subtitles': [{'start': 0, 'end': .1, 'text': chunk['text']}]}
        qid = prepare(self.core, self.manifest)['question_id']
        source = {**SOURCE, 'provider': 'minimax', 'region': 'cn', 'model': 'speech-2.8-hd'}
        selection = create(self.core, qid, {'r1': [{'name': '候选', 'category': 'other', 'source': source,
                            'reason': 'test', 'evidence_url': 'https://example.test'}]}, self.core.read()['revision'])
        sample = audition(self.core, selection['selection_id'], 'r1', 's1', provider_directives={'emotion': 'calm'})
        frozen = freeze_audition(self.core, sample['audition_id'], sample['review_hash'], confirmed=True)
        Generation(self.core, minimax=OfflineMiniMax()).run(frozen['job_id'])
        bind(self.core, selection['selection_id'], {'r1': selection['candidates']['r1'][0]['project_voice_id']},
             self.core.read()['revision'], confirmed=True)
        items = copy.deepcopy(self.items)
        for item in items:
            item.update(emotion='calm', provider_directives={'emotion': 'calm'})
        batch = review(self.core, qid, items, selection_id=selection['selection_id'])
        self.assertEqual(batch['reusable_sentence_ids'], ['s1'])
        self.assertEqual(batch['sentence_ids'], ['s2'])
        confirm(self.core, batch['plan_id'], batch['plan_hash'])
        job = plan(self.core, performance_plan=batch['plan_id'])
        Generation(self.core, minimax=OfflineMiniMax()).run(job['job_id'])
        result = publish(self.core, 'task1', '测试交付', qid, items, [job['job_id']],
                         selection_id=selection['selection_id'], version='v01')
        self.assertEqual(result['status'], 'complete')
        self.assertAlmostEqual(result['duration_seconds'], .6)
        self.assertTrue(all(r['emotion'] == 'calm' for r in result['segments']))
        merged_srt = Path(result['merged_audio_path']).with_suffix('.srt').read_text(encoding='utf-8')
        self.assertIn('00:00:00,500 --> 00:00:00,600', merged_srt)
        changed = copy.deepcopy(items)
        changed[1].update(emotion='自动', provider_directives={})
        self.error('performance_mismatch', lambda: publish(self.core, 'task1', '测试交付', qid, changed,
                    [job['job_id']], selection_id=selection['selection_id'], version='v02'))
        self.assertFalse((self.a / '配音/测试交付/v02').exists())


if __name__ == '__main__':
    unittest.main()
