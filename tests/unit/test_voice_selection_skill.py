"""Documentation contract for the two voice-selection entry points."""
import unittest
from tests.helpers import ROOT


class VoiceSelectionSkill(unittest.TestCase):
    def test_fixed_defaults_final_delivery_and_native_tool_evidence_are_explicit(self):
        root = ROOT / 'skills/soundmaker-dubbing'
        skill = (root / 'SKILL.md').read_text(encoding='utf-8')
        workflow = (root / 'references/workflow-api.md').read_text(encoding='utf-8')
        delivery = (root / 'references/delivery-layout.md').read_text(encoding='utf-8')
        self.assertIn('SystemList', skill)
        self.assertIn('实际 schema', skill)
        self.assertIn('makesound.project_defaults', workflow)
        self.assertIn('makesound.final_delivery review', workflow)
        self.assertIn('makesound.final_delivery publish', delivery)
        self.assertIn('speech_seconds', delivery)
        self.assertIn('emotion_not_mapped', workflow)
        self.assertIn('不笼统说全部完成', skill)
        self.assertIn('不再另建 final-performance-targets.json', workflow)

    def test_all_project_references_and_host_recovery_keep_route_boundaries(self):
        refs = ROOT / 'skills/soundmaker-dubbing/references'
        project_docs = ('workflow-api.md','voice-selection.md','performance-plan.md',
                        'delivery-layout.md','revision-and-recovery.md','minimax.md','studio.md','harness-resume.md')
        for name in project_docs:
            with self.subTest(document=name):
                text = (refs/name).read_text(encoding='utf-8')
                self.assertIn('选项 1/2', text)
                self.assertIn('选项 3', text)
                self.assertNotIn('主 Skill 第 0 节', text)
                self.assertNotIn("The main Skill's recipe D", text)
        for host in ('claude','codex','kimi','doubao','workbuddy'):
            with self.subTest(host=host):
                text = (refs/f'harnesses/{host}.md').read_text(encoding='utf-8')
                self.assertIn('选项 1/2', text)
                self.assertIn('选项 3', text)
                self.assertIn('question_id', text)
        recovery = (refs/'revision-and-recovery.md').read_text(encoding='utf-8')
        self.assertNotIn('python -m makesound.production run', recovery)
        provider = (refs/'minimax.md').read_text(encoding='utf-8')
        self.assertIn('已有检查结果', provider)

    def test_native_route_exits_project_workflow_and_handles_its_own_revisions(self):
        skill = (ROOT / 'skills/soundmaker-dubbing/SKILL.md').read_text(encoding='utf-8')
        self.assertLess(skill.index('## 1. 选择生成路径'), skill.index('按配方 A'))
        self.assertIn('不自动回退或切换', skill)
        self.assertIn('内置结果的修改、失败和交付仍走当前应用说明', skill)
        self.assertIn('完成后结束本次流程', skill)
        self.assertIn('只有选项 1/2 使用本节', skill)
        self.assertNotIn('局部修改直接进入 [修订与恢复]', skill)
        for host in ('kimi', 'doubao'):
            text = (ROOT / f'skills/soundmaker-dubbing/references/native-audio/{host}.md').read_text(encoding='utf-8')
            self.assertIn('失败', text)
            self.assertIn('不', text)
            self.assertNotIn('workflow-api.md', text)
            self.assertNotIn('delivery-layout.md', text)

    def test_native_audio_is_an_optional_separate_route(self):
        skill = (ROOT / 'skills/soundmaker-dubbing/SKILL.md').read_text(encoding='utf-8')
        self.assertIn('**3、使用当前应用内置工具生成音频**', skill)
        self.assertNotIn('audio_generation', skill)
        self.assertIn('当前会话实际可调用', skill)
        self.assertIn('选项 3 不走', skill)
        for host in ('kimi', 'doubao'):
            self.assertIn(f'references/native-audio/{host}.md', skill)
            text = (ROOT / f'skills/soundmaker-dubbing/references/native-audio/{host}.md').read_text(encoding='utf-8')
            for term in ('不加入项目声音库', '不创建', '实际工具', 'voice_id'):
                self.assertIn(term, text)
        doubao = (ROOT / 'skills/soundmaker-dubbing/references/native-audio/doubao.md').read_text(encoding='utf-8')
        kimi = (ROOT / 'skills/soundmaker-dubbing/references/native-audio/kimi.md').read_text(encoding='utf-8')
        self.assertIn('工具名为 `audio_generation`', kimi)
        self.assertIn('不套用 Kimi 的工具名', doubao)
        self.assertIn('用户提供', doubao)
        self.assertIn('1～120', doubao)

    def test_references_are_loaded_only_at_the_relevant_step(self):
        skill = (ROOT / 'skills/soundmaker-dubbing/SKILL.md').read_text(encoding='utf-8')
        self.assertIn('禁止预读', skill)
        self.assertIn('只有实际需要打开绑定/管理网页时', skill)
        self.assertIn('只读取当前宿主的一份', skill)
        self.assertIn('普通配音遇到错误也不自动转为源码排查', skill)
        self.assertNotIn('For WorkBuddy, first read', skill)
        self.assertNotIn('CLAUDE_CODE_MESSAGING_SOCKET', skill)
        self.assertNotIn('python -m makesound.production run --project', skill)
        provider = (ROOT / 'skills/soundmaker-dubbing/references/minimax.md').read_text(encoding='utf-8')
        self.assertIn("configure('minimax')", provider)
        self.assertIn('python -m makesound.production run --project', provider)
        index = (ROOT / 'skills/soundmaker-dubbing/references/harness-resume.md').read_text(encoding='utf-8')
        self.assertIn('不逐一打开', index)

    def test_main_flow_separates_candidate_and_bound_auditions(self):
        skill = (ROOT / 'skills/soundmaker-dubbing/SKILL.md').read_text(encoding='utf-8')
        self.assertNotIn('After all roles are bound, apply section 0 first', skill)
        self.assertNotIn('试听与剩余批次统一使用配方 D', skill)
        self.assertNotIn('下一步固定为 C → 选句 → D', skill)
        self.assertIn('候选试听使用', skill)
        self.assertIn('试听已覆盖全部原文', skill)
        self.assertIn('单人短口播', skill)
        self.assertIn('已有授权覆盖', skill)
        self.assertLess(skill.index('**1、自己配置声音'), skill.index('**2、推荐音色'))
        self.assertIn('references/workflow-api.md', skill)
        self.assertNotIn('python -X utf8 -c', skill)
        workflow = (ROOT / 'skills/soundmaker-dubbing/references/workflow-api.md').read_text(encoding='utf-8')
        for recipe in ('### A.', '### B.', '### C.', '### D.'):
            self.assertIn(recipe, workflow)

    def test_task_reopening_and_pause_are_explicit(self):
        skill = (ROOT / 'skills/soundmaker-dubbing/SKILL.md').read_text(encoding='utf-8')
        studio = (ROOT / 'skills/soundmaker-dubbing/references/studio.md').read_text(encoding='utf-8')
        recovery = (ROOT / 'skills/soundmaker-dubbing/references/revision-and-recovery.md').read_text(encoding='utf-8')
        self.assertLess(len(skill.splitlines()), 120)
        for term in ('立即暂停', '不继续 propose', '默认每角色推荐 2～3 个', '不能只给目录', '字幕失败'):
            self.assertIn(term, skill)
        for term in ('默认打开当前绑定任务', '预填旧 Answer', '实际新 question_id',
                     '只有明确要管理项目声音库', '--ui-language zh-CN'):
            self.assertIn(term, studio)
        self.assertNotIn('harnesses/claude.md', skill)
        self.assertIn('harnesses/claude.md', studio)
        self.assertIn('affected_sentence_ids', recovery)
        self.assertIn('create(core, question_id)', recovery)
        self.assertIn('compare(core, new_question_id)', recovery)

    def test_quick_selection_has_callable_reference_and_no_forced_studio(self):
        skill = (ROOT / 'skills/soundmaker-dubbing/SKILL.md').read_text(encoding='utf-8')
        self.assertIn('帮我选声音', skill)
        self.assertIn('使用我的声音', skill)
        self.assertIn('references/voice-selection.md', skill)
        self.assertNotIn('Otherwise, the agent must create a Question, start', skill)
        reference = (ROOT / 'skills/soundmaker-dubbing/references/voice-selection.md').read_text(encoding='utf-8')
        for term in ('makesound.voice_selection', 'create', 'audition', 'bind',
                     '最多', '3', 'get_voice', '付费', '同一句', 'confirmed=True'):
            self.assertIn(term, reference)
