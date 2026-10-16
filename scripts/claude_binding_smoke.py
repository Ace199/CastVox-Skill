"""Run inside the originating Claude Bash tool; creates only a fake binding fixture."""
import json
import os
from pathlib import Path
import sys
import uuid

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from makesound.core_v16 import ProjectCore
from makesound.offline_harness import prepare
from makesound.studio_session import start


def main():
    if not os.environ.get('CLAUDE_CODE_MESSAGING_TOKEN'):
        raise SystemExit('Run this script from the originating Claude Code Bash tool.')
    root = Path(__file__).resolve().parents[1] / 'outputs' / ('claude-binding-smoke-' + uuid.uuid4().hex[:10])
    root.mkdir(parents=True)
    core = ProjectCore(root)
    _, voice = core.add_voice('测试音色（不生成音频）', 'other',
        {'provider': 'fake', 'region': 'test', 'model': 'fake-v1', 'voice_id': 'FAKE_VOICE_A'}, 0)
    qid = prepare(core, {'roles': ['test_narrator'], 'segments': [
        {'paragraph_id': 'p1', 'sentence_id': 's1', 'role_id': 'test_narrator',
         'text': 'SM_CLAUDE_BINDING_02：仅测试网页绑定完成后的原会话恢复，不调用任何配音服务。'}]})['question_id']
    result = start(core, qid, allow_fake=True)
    result.update({'project': str(root), 'voice_id': voice, 'test_id': 'SM_CLAUDE_BINDING_02'})
    # Public test metadata only; inherited authentication is never serialized.
    (root.parent / 'claude-binding-smoke-latest.json').write_text(json.dumps(result, ensure_ascii=False), encoding='utf-8')
    print(json.dumps(result, ensure_ascii=True))


if __name__ == '__main__':
    main()
