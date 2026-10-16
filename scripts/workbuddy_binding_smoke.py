"""Run inside the originating WorkBuddy command tool. Binding only; no synthesis."""
import json
import os
from pathlib import Path
import sys
import uuid

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from makesound.core_v16 import ProjectCore
from makesound.errors import MakeSoundError
from makesound.offline_harness import prepare
from makesound.studio_session import serve_managed
from makesound.workbuddy_task import environment_target


def main():
    try:
        target = environment_target()
        if target is None:
            raise MakeSoundError('harness_unavailable', 'Run this script inside WorkBuddy.')
    except Exception as exc:
        print(json.dumps({'test_id': 'SM_WORKBUDDY_BINDING_02', 'status': 'not_ready',
                          'error_code': exc.code if isinstance(exc, MakeSoundError) else 'host_check_failed',
                          'note': 'No message or audio was sent. Do not copy credentials from another session.'}))
        return 2
    root = Path(__file__).resolve().parents[1] / 'outputs' / ('workbuddy-binding-smoke-' + uuid.uuid4().hex[:10])
    root.mkdir(parents=True)
    core = ProjectCore(root)
    _, voice = core.add_voice('测试音色（不生成音频）', 'other',
        {'provider': 'fake', 'region': 'test', 'model': 'fake-v1', 'voice_id': 'FAKE_VOICE_A'}, 0)
    qid = prepare(core, {'roles': ['test_narrator'], 'segments': [
        {'paragraph_id': 'p1', 'sentence_id': 's1', 'role_id': 'test_narrator',
         'text': 'SM_WORKBUDDY_BINDING_02：仅测试网页绑定完成后的原聊天任务续跑，不调用配音服务。'}]})['question_id']
    def ready(result):
        result.update({'project': str(root), 'voice_id': voice, 'test_id': 'SM_WORKBUDDY_BINDING_02',
                       'resume_transport': 'managed_task_output'})
        (root.parent / 'workbuddy-binding-smoke-latest.json').write_text(
            json.dumps(result, ensure_ascii=False, indent=2), encoding='utf-8')
        print(json.dumps(result, ensure_ascii=True), flush=True)
    result = serve_managed(core, qid, allow_fake=True, on_ready=ready)
    print(json.dumps(result), flush=True)
    return 0


if __name__ == '__main__':
    sys.exit(main())
