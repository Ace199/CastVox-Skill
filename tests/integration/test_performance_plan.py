import json
import unittest

from tests.helpers import Fixture
from tests.unit.test_v16 import SOURCE
from makesound.core_v16 import ProjectCore
from makesound.errors import MakeSoundError
from makesound.offline_harness import prepare
from makesound.questions import Questions


class PerformancePlanHandoff(Fixture, unittest.TestCase):
    def setUp(self):
        super().setUp()
        self.core = ProjectCore(self.a)
        _, self.voice_id = self.core.add_voice('沉稳旁白', 'other', SOURCE, 0, {'speed': 1.2, 'pitch': 0})
        self.manifest = {
            'roles': ['narrator'],
            'segments': [
                {'paragraph_id': 'p1', 'sentence_id': 's1', 'role_id': 'narrator', 'text': '夜色渐浓。'},
                {'paragraph_id': 'p1', 'sentence_id': 's2', 'role_id': 'narrator', 'text': '城市仍在呼吸。'},
            ],
        }
        self.question_id = prepare(self.core, self.manifest)['question_id']
        Questions(self.core).submit(self.question_id, {'narrator': self.voice_id})

    def error(self, code, call):
        with self.assertRaises(MakeSoundError) as caught:
            call()
        self.assertEqual(caught.exception.code, code)

    def test_inline_controls_survive_review_confirmation_and_freeze(self):
        from makesound.performance_plan import propose, confirm, render
        from makesound.production import plan as production_plan
        from makesound.generation import Generation
        source = {**SOURCE, 'provider': 'minimax', 'region': 'cn', 'model': 'speech-2.8-hd'}
        _, voice = self.core.add_voice('标签声音', 'other', source, self.core.read()['revision'])
        qid = prepare(self.core, self.manifest)['question_id']
        Questions(self.core).submit(qid, {'narrator': voice})
        controls = [{'at': 0, 'sound': 'sighs'}, {'at': 2, 'pause_ms': 300}]
        items = [{'sentence_id': sid, 'emotion': '自动', 'delivery_notes': '按确认文本',
                  'pause_after_ms': 0, 'inline_controls': controls if sid == 's1' else []}
                 for sid in ('s1', 's2')]
        draft = propose(self.core, qid, items)
        self.assertIn('(sighs)夜色<#0.3#>渐浓。', render(draft))
        self.error('confirmation_required', lambda: production_plan(self.core, performance_plan=draft['plan_id']))
        confirm(self.core, draft['plan_id'], draft['plan_hash'])
        result = production_plan(self.core, performance_plan=draft['plan_id'])
        chunk = Generation(self.core).load(result['job_id'])['chunks'][0]
        self.assertEqual(chunk['inline_controls'], controls)
        self.assertEqual(chunk['text'], '夜色渐浓。')

    def test_external_plan_keeps_script_order_voice_snapshot_and_no_secrets(self):
        from makesound.performance_plan import propose, read, render

        plan = propose(self.core, self.question_id, [
            {'sentence_id': 's1', 'emotion': '沉稳', 'delivery_notes': '平和旁白。', 'pause_after_ms': 300},
            {'sentence_id': 's2', 'emotion': '大气', 'delivery_notes': '平稳收束。', 'pause_after_ms': 0},
        ])

        self.assertEqual(plan['status'], 'pending_confirmation')
        self.assertEqual([item['text'] for item in plan['segments']], ['夜色渐浓。', '城市仍在呼吸。'])
        self.assertEqual(plan['segments'][0]['voice_snapshot']['project_voice_id'], self.voice_id)
        self.assertEqual(plan['segments'][0]['voice_snapshot']['effective_settings'], {'speed': 1.2, 'pitch': 0})
        self.assertEqual(read(self.core, plan['plan_id']), plan)
        text = render(plan)
        self.assertIn('夜色渐浓。', text)
        self.assertIn('沉稳旁白', text)
        self.assertNotIn('PRIVATE', json.dumps(plan, ensure_ascii=False))

    def test_plan_requires_complete_unchanged_script_and_has_no_provider_call(self):
        from makesound.performance_plan import propose

        self.error('plan_coverage', lambda: propose(self.core, self.question_id, [
            {'sentence_id': 's1', 'emotion': '沉稳', 'delivery_notes': '平和旁白。', 'pause_after_ms': 0},
        ]))
        self.error('unsupported_directive', lambda: propose(self.core, self.question_id, [
            {'sentence_id': 's1', 'emotion': '沉稳', 'delivery_notes': '平和旁白。', 'pause_after_ms': 0,
             'provider_directives': {'emotion': 'sad'}},
            {'sentence_id': 's2', 'emotion': '沉稳', 'delivery_notes': '平和旁白。', 'pause_after_ms': 0},
        ]))

    def test_confirmation_binds_the_reviewed_hash_and_is_immutable(self):
        from makesound.performance_plan import propose, confirm, read

        plan = propose(self.core, self.question_id, [
            {'sentence_id': 's1', 'emotion': '沉稳', 'delivery_notes': '平和旁白。', 'pause_after_ms': 200},
            {'sentence_id': 's2', 'emotion': '大气', 'delivery_notes': '平稳收束。', 'pause_after_ms': 0},
        ])
        self.error('plan_changed', lambda: confirm(self.core, plan['plan_id'], 'different_hash'))
        confirmed = confirm(self.core, plan['plan_id'], plan['plan_hash'])
        self.assertEqual(confirmed['status'], 'confirmed')
        self.assertTrue(confirmed['confirmation_hash'])
        self.assertEqual(read(self.core, plan['plan_id']), confirmed)
        self.error('plan_immutable', lambda: confirm(self.core, plan['plan_id'], plan['plan_hash']))

    def test_only_a_confirmed_plan_can_freeze_the_answered_job_without_network(self):
        from makesound.performance_plan import propose, confirm
        from makesound.production import plan as production_plan
        from makesound.generation import Generation

        draft = propose(self.core, self.question_id, [
            {'sentence_id': 's1', 'emotion': '沉稳', 'delivery_notes': '平和旁白。', 'pause_after_ms': 400},
            {'sentence_id': 's2', 'emotion': '大气', 'delivery_notes': '平稳收束。', 'pause_after_ms': 0},
        ])
        self.error('confirmation_required', lambda: production_plan(self.core, performance_plan=draft['plan_id']))
        confirm(self.core, draft['plan_id'], draft['plan_hash'])
        result = production_plan(self.core, performance_plan=draft['plan_id'])
        snapshot = Generation(self.core).load(result['job_id'])
        self.assertEqual(result['status'], 'planned')
        self.assertFalse(result['paid_execution_authorized'])
        self.assertEqual([chunk['pause_ms'] for chunk in snapshot['chunks']], [400, 0])
        self.assertEqual(snapshot['chunks'][0]['project_voice_id'], self.voice_id)

    def test_completed_audio_and_srt_are_exported_to_the_project_output_directory(self):
        from makesound.generation import Generation

        engine = Generation(self.core)
        snapshot = engine.freeze([{
            'paragraph_id': 'p1', 'sentence_id': 's1', 'role_id': 'narrator', 'text': '项目交付音频。',
            'project_voice_id': self.voice_id,
        }], confirmed=True, authorized=True)
        state = engine.run(snapshot['job_id'])
        entry = state['exports'][0]
        self.assertTrue(entry['audio'].startswith(f'outputs/audio/{snapshot["job_id"]}/'))
        self.assertTrue(entry['subtitle'].startswith(f'outputs/audio/{snapshot["job_id"]}/'))
        self.assertTrue((self.core.root / entry['audio']).is_file())
        self.assertTrue(self.core.managed_path(f'.makesound/jobs/{snapshot["job_id"]}/snapshot.json').is_file())

    def test_default_name_is_frozen_even_if_library_voice_changes(self):
        from makesound.performance_plan import propose, render
        self.core.save_defaults({'general': self.voice_id}, self.core.read()['revision'])
        self.core.edit_voice(self.voice_id, {'name': '后来改名', 'deleted': True}, self.core.read()['revision'])
        qid = prepare(self.core, self.manifest)['question_id']
        Questions(self.core).submit(qid, {'narrator': {'default_slot': 'general'}})
        draft = propose(self.core, qid, [
            {'sentence_id': sid, 'emotion': '该模型不支持，不设置',
             'delivery_notes': '未核实支持，不设置', 'pause_after_ms': 0}
            for sid in ('s1', 's2')])
        self.assertEqual(draft['segments'][0]['voice_snapshot']['name'], '沉稳旁白')
        displayed = render(draft)
        self.assertNotIn('不支持', displayed)
        self.assertNotIn('未核实', displayed)
        self.assertNotIn('情绪参数', displayed)
        self.assertNotIn('语气词', displayed)

    def test_plan_uses_the_assignment_snapshot_name_after_a_later_voice_rename(self):
        from makesound.performance_plan import propose

        question_id = prepare(self.core, self.manifest)['question_id']
        questions = Questions(self.core)
        questions.assign(question_id, 'narrator', self.voice_id, self.core.read()['revision'])
        questions.submit(question_id, {'narrator': self.voice_id}, revision=self.core.read()['revision'])
        self.core.edit_voice(self.voice_id, {'name': '后来改名'}, self.core.read()['revision'])
        plan = propose(self.core, question_id, [
            {'sentence_id': 's1', 'emotion': '沉稳', 'delivery_notes': '平和旁白。', 'pause_after_ms': 0},
            {'sentence_id': 's2', 'emotion': '沉稳', 'delivery_notes': '平和旁白。', 'pause_after_ms': 0},
        ])
        self.assertEqual(plan['segments'][0]['voice_snapshot']['name'], '沉稳旁白')


if __name__ == '__main__':
    unittest.main()
