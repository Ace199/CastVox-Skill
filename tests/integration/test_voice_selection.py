import copy
import unittest
from pathlib import Path
from datetime import datetime, timedelta, timezone

from makesound.core_v16 import ProjectCore
from makesound.errors import MakeSoundError
from makesound.offline_harness import prepare
from makesound.questions import Questions
from makesound.storage import atomic_write, read_json
from tests.helpers import Fixture
from tests.unit.test_v16 import SOURCE


class VoiceSelection(Fixture, unittest.TestCase):
    def setUp(self):
        super().setUp()
        self.core = ProjectCore(self.a)
        self.qid = prepare(self.core, {'roles': ['a'], 'segments': [
            {'paragraph_id': 'p1', 'sentence_id': 's1', 'role_id': 'a', 'text': '选择意味着什么？'}]})['question_id']
        self.recs = {'a': [self.rec('甲'), self.rec('乙', 'second')]}

    def rec(self, name, vid='fake-original'):
        return {'name': name, 'category': 'male', 'source': {**SOURCE, 'voice_id': vid},
                'reason': '沉稳', 'evidence_url': 'https://example.com/voices'}

    def error(self, code, call):
        with self.assertRaises(MakeSoundError) as caught:
            call()
        self.assertEqual(caught.exception.code, code)

    def test_limit_is_atomic_and_duplicates_reuse(self):
        from makesound.voice_selection import create
        before = self.core.read()
        self.error('candidate_limit', lambda: create(self.core, self.qid, {'a': [self.rec(str(i)) for i in range(4)]}, 0))
        self.assertEqual(self.core.read(), before)
        selection = create(self.core, self.qid, self.recs, 0)
        again = create(self.core, self.qid, self.recs, self.core.read()['revision'])
        self.assertEqual(selection['candidates'], again['candidates'])
        self.assertEqual(len(self.core.read()['voices']), 2)
        self.assertEqual(self.core.read()['defaults'], before['defaults'])
        self.assertIsNone(Questions(self.core).read(self.qid)['answer'])

    def test_audio_results_deliver_intact_auditions_despite_subtitle_export_failure(self):
        from makesound.voice_selection import create, audition, freeze_audition, audition_results
        from makesound.generation import Generation
        from unittest.mock import patch
        selection = create(self.core, self.qid, self.recs, 0)
        sample = audition(self.core, selection['selection_id'], 'a', 's1')
        self.assertEqual(sample['chunks'], 2)
        self.assertEqual(sample['characters'], len('选择意味着什么？') * 2)
        frozen = freeze_audition(self.core, sample['audition_id'], sample['review_hash'], confirmed=True)
        with patch.object(Generation, '_export', side_effect=MakeSoundError('subtitle_unavailable', 'No timing')):
            state = Generation(self.core).run(frozen['job_id'])
        self.assertEqual(state['status'], 'export_incomplete')
        with patch.object(Generation, 'run', side_effect=AssertionError('Read only')):
            result = audition_results(self.core, sample['audition_id'])
        self.assertEqual(result['status'], 'audio_ready')
        self.assertEqual(result['audio_count'], 2)
        self.assertEqual([r['name'] for r in result['audio']], ['甲', '乙'])
        self.assertTrue(all(r['source_sentence_id'] == 's1' for r in result['audio']))
        self.assertEqual(result['network_calls'], 0)
        Path(result['audio'][0]['audio_path']).write_bytes(b'corrupt')
        result = audition_results(self.core, sample['audition_id'])
        self.assertEqual(result['status'], 'partial')
        self.assertEqual(result['audio_count'], 1)
        self.assertEqual(len(result['unavailable']), 1)

    def test_candidate_auditions_share_reviewed_emotion_and_inline_controls(self):
        from makesound.voice_selection import create, audition, freeze_audition
        from makesound.generation import Generation
        recs = copy.deepcopy(self.recs)
        for c in recs['a']:
            c['source'].update(provider='minimax', region='cn', model='speech-2.8-hd')
        selection = create(self.core, self.qid, recs, 0)
        controls = [{'at': 0, 'sound': 'chuckle'}]
        sample = audition(self.core, selection['selection_id'], 'a', 's1',
                          provider_directives={'emotion': 'angry'}, inline_controls=controls)
        self.assertEqual(sample['characters'], (len('选择意味着什么？') + len('(chuckle)')) * 2)
        request = read_json(Path(sample['request_path']))
        self.assertEqual([s['provider_directives'] for s in request], [{'emotion': 'angry'}] * 2)
        self.assertEqual([s['inline_controls'] for s in request], [controls] * 2)
        frozen = freeze_audition(self.core, sample['audition_id'], sample['review_hash'], confirmed=True)
        self.assertEqual(Generation(self.core).load(frozen['job_id'])['chunks'][0]['provider_directives'], {'emotion': 'angry'})
        self.error('unsupported_directive', lambda: audition(self.core, selection['selection_id'], 'a', 's1',
                                                            provider_directives={'emotion': 'invented'}))

    def test_publish_audition_is_local_repeatable_and_preserves_delivery_edits(self):
        from makesound.voice_selection import create, audition, freeze_audition
        from makesound.generation import Generation
        from makesound.project_files import publish_audition, refresh_index
        from unittest.mock import patch
        selection = create(self.core, self.qid, self.recs, 0)
        sample = audition(self.core, selection['selection_id'], 'a', 's1')
        frozen = freeze_audition(self.core, sample['audition_id'], sample['review_hash'], confirmed=True)
        with patch.object(Generation, '_export', side_effect=MakeSoundError('subtitle_unavailable', 'No timing')):
            Generation(self.core).run(frozen['job_id'])
        with patch.object(Generation, 'run', side_effect=AssertionError('No synthesis')):
            result = publish_audition(self.core, 'task1', '身份曝光', sample['audition_id'])
            again = publish_audition(self.core, 'task1', '身份曝光', sample['audition_id'])
        self.assertEqual(result['audio'], again['audio'])
        self.assertEqual(result['audio_count'], 2)
        first = Path(result['audio'][0]['audio_path'])
        self.assertTrue(first.is_relative_to(self.a / '配音/身份曝光/试听/第001组'))
        self.assertIn('s1_', first.name)
        self.assertNotIn('pv_', first.name)
        self.assertEqual(first.read_bytes(), Path(result['audio'][0]['source_path']).read_bytes())
        self.assertTrue(Path(result['index_path']).is_file())
        Path(result['index_path']).write_text('用户修改索引', encoding='utf-8')
        self.error('file_conflict', lambda: refresh_index(self.core, 'task1', '身份曝光'))
        first.write_bytes('用户编辑音频'.encode('utf-8'))
        self.error('file_conflict', lambda: publish_audition(self.core, 'task1', '身份曝光', sample['audition_id']))
        self.assertEqual(first.read_bytes(), '用户编辑音频'.encode('utf-8'))

    def test_reuse_compares_final_emotion_and_inline_controls(self):
        from makesound.voice_selection import create, audition, freeze_audition, bind, reuse_report
        from makesound.generation import Generation
        import wave
        class OfflineMiniMax:
            def bind(self, *args):
                pass
            def synthesize(self, chunk, path, **kwargs):
                with wave.open(str(path), 'wb') as audio:
                    audio.setnchannels(1)
                    audio.setsampwidth(2)
                    audio.setframerate(32000)
                    audio.writeframes(b'\0\0' * 3200)
                return {'speech_seconds': .1, 'duration_seconds': .1, 'subtitle_status': 'verified_timing',
                        'subtitles': [{'start': 0, 'end': .1, 'text': chunk['text']}]}
        recs = copy.deepcopy(self.recs)
        for c in recs['a']:
            c['source'].update(provider='minimax', region='cn', model='speech-2.8-hd')
        selection = create(self.core, self.qid, recs, 0)
        sample = audition(self.core, selection['selection_id'], 'a', 's1', provider_directives={'emotion': 'angry'})
        frozen = freeze_audition(self.core, sample['audition_id'], sample['review_hash'], confirmed=True)
        self.assertEqual(Generation(self.core, minimax=OfflineMiniMax()).run(frozen['job_id'])['status'], 'success')
        bind(self.core, selection['selection_id'], {'a': selection['candidates']['a'][0]['project_voice_id']},
             self.core.read()['revision'], confirmed=True)
        report = reuse_report(self.core, selection['selection_id'], targets={'s1': {'provider_directives': {'emotion': 'angry'}}})
        self.assertTrue(report['performance_checked'])
        self.assertEqual(report['remaining_sentence_ids'], [])
        for target in ({'provider_directives': {'emotion': 'calm'}}, {},
                       {'provider_directives': {'emotion': 'angry'}, 'inline_controls': [{'at': 0, 'sound': 'chuckle'}]}):
            report = reuse_report(self.core, selection['selection_id'], targets={'s1': target})
            self.assertEqual(report['reusable'], [])
            self.assertEqual(report['remaining_sentence_ids'], ['s1'])
        self.assertFalse(reuse_report(self.core, selection['selection_id'])['performance_checked'])
        self.error('plan_coverage', lambda: reuse_report(self.core, selection['selection_id'], targets={}))

    def test_verified_category_fills_other_without_replacing_known_category(self):
        from makesound.voice_selection import create
        _, vid = self.core.add_voice('已入库', 'other', self.recs['a'][0]['source'], 0)
        first = create(self.core, self.qid, self.recs, 1)
        self.assertEqual(first['candidates']['a'][0]['project_voice_id'], vid)
        self.assertEqual(self.core.read()['voices'][vid]['category'], 'male')
        self.assertEqual(first['candidates']['a'][0]['category'], 'male')
        recs = copy.deepcopy(self.recs)
        recs['a'][0]['category'] = 'female'
        second = create(self.core, self.qid, recs, self.core.read()['revision'])
        self.assertEqual(second['candidates']['a'][0]['category'], 'male')

    def test_selected_auditions_report_verified_original_sentences_without_generation(self):
        from makesound.voice_selection import create, audition, freeze_audition, bind, reuse_report
        from makesound.generation import Generation
        selection = create(self.core, self.qid, self.recs, 0)
        sample = audition(self.core, selection['selection_id'], 'a', 's1')
        frozen = freeze_audition(self.core, sample['audition_id'], sample['review_hash'], confirmed=True)
        engine = Generation(self.core)
        engine.run(frozen['job_id'])
        vid = selection['candidates']['a'][1]['project_voice_id']
        bind(self.core, selection['selection_id'], {'a': vid}, self.core.read()['revision'], confirmed=True)
        from unittest.mock import patch
        with patch.object(Generation, 'run', side_effect=AssertionError('No synthesis')):
            report = reuse_report(self.core, selection['selection_id'])
        self.assertEqual(report['remaining_sentence_ids'], [])
        item = report['reusable'][0]
        self.assertEqual(item['sentence_id'], 's1')
        self.assertEqual(item['project_voice_id'], vid)
        self.assertEqual(item['provider_directives'], {})
        self.assertTrue(Path(item['audio_path']).is_file())
        Path(item['audio_path']).write_bytes(b'corrupt')
        report = reuse_report(self.core, selection['selection_id'])
        self.assertEqual(report['reusable'], [])
        self.assertEqual(report['remaining_sentence_ids'], ['s1'])

    def test_reuse_report_excludes_changed_binding_and_requires_final_selection(self):
        from makesound.voice_selection import create, audition, freeze_audition, bind, reuse_report
        from makesound.generation import Generation
        selection = create(self.core, self.qid, self.recs, 0)
        self.error('not_answered', lambda: reuse_report(self.core, selection['selection_id']))
        sample = audition(self.core, selection['selection_id'], 'a', 's1',
                          [selection['candidates']['a'][0]['project_voice_id']])
        frozen = freeze_audition(self.core, sample['audition_id'], sample['review_hash'], confirmed=True)
        Generation(self.core).run(frozen['job_id'])
        bind(self.core, selection['selection_id'], {'a': selection['candidates']['a'][1]['project_voice_id']},
             self.core.read()['revision'], confirmed=True)
        self.assertEqual(reuse_report(self.core, selection['selection_id'])['remaining_sentence_ids'], ['s1'])

    def test_ten_lines_reuse_three_selected_auditions_and_generate_only_seven(self):
        from makesound.voice_selection import create, audition, freeze_audition, bind, reuse_report
        from makesound.generation import Generation
        from makesound.providers import FakeProvider
        from makesound.performance_plan import propose, confirm
        from makesound.production import plan
        roles = ['a', 'b', 'c']
        segments = [{'paragraph_id': 'p', 'sentence_id': f's{i+1}', 'role_id': roles[i % 3],
                     'text': f'这是第{i+1}句原文。'} for i in range(10)]
        qid = prepare(self.core, {'roles': roles, 'segments': segments})['question_id']
        recs = {r: [self.rec(f'{r}{i}', f'{r}-{i}') for i in range(3)] for r in roles}
        selection = create(self.core, qid, recs, 0)
        fake = FakeProvider()
        for i, role in enumerate(roles):
            sample = audition(self.core, selection['selection_id'], role, f's{i+1}')
            frozen = freeze_audition(self.core, sample['audition_id'], sample['review_hash'], confirmed=True)
            self.assertEqual(Generation(self.core, fake=fake).run(frozen['job_id'])['status'], 'success')
        self.assertEqual(fake.calls, 9)
        assignments = {r: selection['candidates'][r][1]['project_voice_id'] for r in roles}
        bind(self.core, selection['selection_id'], assignments, self.core.read()['revision'], confirmed=True)
        report = reuse_report(self.core, selection['selection_id'],
                              targets={s['sentence_id']: {} for s in segments})
        self.assertTrue(report['performance_checked'])
        self.assertEqual([s['sentence_id'] for s in report['reusable']], ['s1', 's2', 's3'])
        remaining = report['remaining_sentence_ids']
        self.assertEqual(len(remaining), 7)
        delivered = {s['sentence_id'] for s in report['reusable']}
        for start in range(0, len(remaining), 5):
            ids = remaining[start:start+5]
            items = [{'sentence_id': sid, 'emotion': '自动', 'delivery_notes': '沿用声音',
                      'pause_after_ms': 0} for sid in ids]
            review = propose(self.core, qid, items, sentence_ids=ids)
            confirm(self.core, review['plan_id'], review['plan_hash'])
            frozen = plan(self.core, performance_plan=review['plan_id'])
            self.assertEqual(Generation(self.core, fake=fake).run(frozen['job_id'])['status'], 'success')
            delivered.update(ids)
        self.assertEqual(fake.calls, 16)  # Nine auditions + seven new lines.
        self.assertEqual(delivered, {s['sentence_id'] for s in segments})

    def test_audition_and_explicit_binding(self):
        from makesound.voice_selection import create, audition, bind
        from makesound.production import plan
        from makesound.generation import Generation
        selection = create(self.core, self.qid, self.recs, 0)
        original = Questions(self.core).read(self.qid)
        sample = audition(self.core, selection['selection_id'], 'a', 's1')
        request = read_json(Path(sample['request_path']))
        self.assertEqual([s['text'] for s in request], ['选择意味着什么？'] * 2)
        self.assertEqual(sample['source_sentence_id'], 's1')
        self.assertEqual(Questions(self.core).read(self.qid), original)
        result = plan(self.core, request_path=sample['request_path'], confirmed=True)
        self.assertEqual(Generation(self.core).run(result['job_id'])['status'], 'success')
        ids = [c['project_voice_id'] for c in selection['candidates']['a']]
        for vid in ids:
            self.assertEqual(self.core.preview_state(vid)['status'], 'current')
        self.error('confirmation_required', lambda: bind(self.core, selection['selection_id'], {'a': ids[0]}, self.core.read()['revision']))
        result = bind(self.core, selection['selection_id'], {'a': ids[0]}, self.core.read()['revision'], confirmed=True)
        self.assertEqual(result['answer']['assignments'], {'a': ids[0]})
        self.error('answer_immutable', lambda: audition(self.core, selection['selection_id'], 'a', 's1'))

    def test_deleted_name_collision_settings_and_expiry(self):
        from makesound.voice_selection import create, audition
        _, deleted = self.core.add_voice('甲', 'male', SOURCE, 0)
        self.core.edit_voice(deleted, {'deleted': True}, 1)
        self.core.add_voice('乙', 'male', {**SOURCE, 'voice_id': 'different'}, 2)
        selection = create(self.core, self.qid, self.recs, 3)
        ids = [c['project_voice_id'] for c in selection['candidates']['a']]
        self.assertNotIn(deleted, ids)
        self.assertTrue(self.core.read()['voices'][deleted]['deleted'])
        names = [v['name'] for v in self.core.read()['voices'].values() if not v['deleted']]
        self.assertEqual(len(names), len(set(names)))
        changed = copy.deepcopy(self.recs)
        changed['a'][0]['settings'] = {'speed': 1.2}
        newer = create(self.core, self.qid, changed, self.core.read()['revision'])
        self.assertNotEqual(newer['candidates']['a'][0]['project_voice_id'], ids[0])
        q = Questions(self.core).read(self.qid)
        q['expires_at'] = (datetime.now(timezone.utc) - timedelta(seconds=1)).isoformat()
        atomic_write(Questions(self.core)._path(self.qid), q)
        self.error('question_expired', lambda: audition(self.core, selection['selection_id'], 'a', 's1'))

    def test_subset_and_changed_candidates_rejected_and_existing_voice_can_bind(self):
        from makesound.voice_selection import create, audition, bind
        selection = create(self.core, self.qid, self.recs, 0)
        vid = selection['candidates']['a'][0]['project_voice_id']
        sample = audition(self.core, selection['selection_id'], 'a', 's1', [vid])
        self.assertEqual(len(read_json(Path(sample['request_path']))), 1)
        self.error('voice_unavailable', lambda: audition(self.core, selection['selection_id'], 'a', 's1', ['unknown']))
        self.core.edit_voice(vid, {'settings': {'speed': 1.2}}, self.core.read()['revision'])
        self.error('candidate_changed', lambda: audition(self.core, selection['selection_id'], 'a', 's1', [vid]))
        self.error('candidate_changed', lambda: bind(self.core, selection['selection_id'], {'a': vid},
                                                    self.core.read()['revision'], confirmed=True))
        _, own = self.core.add_voice('自有音色', 'other', {**SOURCE, 'voice_id': 'own'}, self.core.read()['revision'])
        result = bind(self.core, selection['selection_id'], {'a': own}, self.core.read()['revision'], confirmed=True)
        self.assertEqual(result['answer']['assignments'], {'a': own})

    def test_freeze_checks_reviewed_request_and_candidate_snapshot(self):
        from makesound.voice_selection import create, audition, freeze_audition
        selection = create(self.core, self.qid, self.recs, 0)
        sample = audition(self.core, selection['selection_id'], 'a', 's1')
        self.error('confirmation_required', lambda: freeze_audition(self.core, sample['audition_id'], sample['review_hash']))
        vid = sample['project_voice_ids'][0]
        self.core.edit_voice(vid, {'settings': {'speed': 1.2}}, self.core.read()['revision'])
        self.error('candidate_changed', lambda: freeze_audition(self.core, sample['audition_id'], sample['review_hash'], confirmed=True))
        self.core.edit_voice(vid, {'settings': {'speed': 1.0}}, self.core.read()['revision'])
        request = read_json(Path(sample['request_path']))
        request[0]['text'] = '不能悄悄改变试听原文'
        atomic_write(Path(sample['request_path']), request)
        self.error('plan_changed', lambda: freeze_audition(self.core, sample['audition_id'], sample['review_hash'], confirmed=True))

    def test_reviewed_audition_freeze_is_repeatable_and_cache_reused(self):
        from makesound.voice_selection import create, audition, freeze_audition
        from makesound.generation import Generation
        selection = create(self.core, self.qid, self.recs, 0)
        sample = audition(self.core, selection['selection_id'], 'a', 's1')
        first = freeze_audition(self.core, sample['audition_id'], sample['review_hash'], confirmed=True)
        self.assertEqual(first, freeze_audition(self.core, sample['audition_id'], sample['review_hash'], confirmed=True))
        engine = Generation(self.core)
        self.assertEqual(engine.run(first['job_id'])['status'], 'success')
        from makesound.production import plan
        again = plan(self.core, request_path=sample['request_path'], confirmed=True)
        engine = Generation(self.core)
        self.assertEqual(engine.run(again['job_id'])['status'], 'success')
        self.assertEqual(engine.fake.calls, 0)

    def test_changed_manuscript_and_unfair_comparison_rejected(self):
        from makesound.voice_selection import create, audition
        changed = copy.deepcopy(self.recs)
        changed['a'][0]['settings'] = {'speed': 1.2}
        selection = create(self.core, self.qid, changed, 0)
        self.error('comparison_settings', lambda: audition(self.core, selection['selection_id'], 'a', 's1'))
        handoff_path = self.core.managed_path(f'.makesound/handoffs/{self.qid}.json')
        handoff = read_json(handoff_path)
        handoff['manifest']['segments'][0]['text'] = '原文已修改'
        atomic_write(handoff_path, handoff)
        self.error('plan_changed', lambda: audition(self.core, selection['selection_id'], 'a', 's1'))

    def test_chat_final_choice_replaces_stale_web_draft(self):
        from makesound.voice_selection import create, bind
        selection = create(self.core, self.qid, self.recs, 0)
        first, second = [c['project_voice_id'] for c in selection['candidates']['a']]
        Questions(self.core).assign(self.qid, 'a', first, self.core.read()['revision'])
        result = bind(self.core, selection['selection_id'], {'a': second}, self.core.read()['revision'], confirmed=True)
        self.assertEqual(result['answer']['resolved']['a']['project_voice_id'], second)

    def test_chat_final_choice_uses_reviewed_settings_not_old_draft(self):
        from makesound.voice_selection import create, bind
        selection = create(self.core, self.qid, self.recs, 0)
        first = selection['candidates']['a'][0]['project_voice_id']
        Questions(self.core).assign(self.qid, 'a', first, self.core.read()['revision'])
        self.core.edit_voice(first, {'settings': {'speed': 1.2}}, self.core.read()['revision'])
        changed = copy.deepcopy(self.recs)
        changed['a'][0]['settings'] = {'speed': 1.2}
        newer = create(self.core, self.qid, changed, self.core.read()['revision'])
        result = bind(self.core, newer['selection_id'], {'a': first}, self.core.read()['revision'], confirmed=True)
        self.assertEqual(result['answer']['resolved']['a']['effective_settings']['speed'], 1.2)

    def test_documented_recipes_execute_end_to_end_without_webpage(self):
        import json
        import os
        import re
        import subprocess
        import sys
        from tests.helpers import ROOT
        reference = (ROOT / 'skills/soundmaker-dubbing/references/voice-selection.md').read_text(encoding='utf-8')
        recipes = re.findall(r'python -X utf8 -c "([^"]+)"', reference)
        env = {**os.environ, 'MAKESOUND_TEST_NO_NETWORK': '1',
               'PYTHONPATH': os.pathsep.join([str(ROOT / 'tests/support'), str(ROOT)])}
        def execute(function, *args):
            code = next(r for r in recipes if f'import {function};' in r)
            result = subprocess.run([sys.executable, '-X', 'utf8', '-c', code, *map(str, args)],
                                    cwd=ROOT, env=env, capture_output=True, encoding='utf-8', timeout=20)
            self.assertEqual(result.returncode, 0, result.stderr)
            return json.loads(result.stdout)
        recommendations = self.dump('recommendations.json', self.recs)
        selection = execute('create', self.a, self.qid, recommendations, 0)
        performance = self.dump('audition-performance.json', {'provider_directives': {}, 'inline_controls': []})
        sample = execute('audition', self.a, selection['selection_id'], 'a', 's1', 'null', performance)
        frozen = execute('freeze_audition', self.a, sample['audition_id'], sample['review_hash'])
        self.assertEqual(frozen['chunks'], 2)
        self.assertFalse(frozen['paid_execution_authorized'])
        results = execute('audition_results', self.a, sample['audition_id'])
        self.assertEqual(results['status'], 'audio_unavailable')
        self.assertEqual(results['expected_audio_count'], 2)
        assignments = self.dump('assignments.json', {'a': sample['project_voice_ids'][0]})
        bound = execute('bind', self.a, selection['selection_id'], assignments, self.core.read()['revision'])
        self.assertEqual(bound['answer']['assignments'], {'a': sample['project_voice_ids'][0]})
        targets = self.dump('final-performance-targets.json', {'s1': {}})
        report = execute('reuse_report', self.a, selection['selection_id'], self.qid, targets)
        self.assertTrue(report['performance_checked'])
        self.assertEqual(report['remaining_sentence_ids'], ['s1'])
