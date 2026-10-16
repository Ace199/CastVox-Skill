"""Run from the originating Doubao Shell; creates an isolated fake binding task."""
import json
import os
from pathlib import Path
import sys
import uuid

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from makesound.core_v16 import ProjectCore
from makesound.doubao_resume import _bridge, _control
from makesound.errors import require
from makesound.offline_harness import prepare
from makesound.studio_session import start


def main():
    cid = os.environ.get('MCP_VM_CONVERSATION_ID', '')
    require(os.environ.get('DOUBAO_OFFICE_APP_ID') == '582478' and cid.isdigit(),
            'harness_unavailable', 'Run from the originating Doubao Windows Shell.')
    info = _control('probe', {**_bridge(), 'conversation_id': cid})
    require(Path.cwd().resolve() == Path(info['workspace']).resolve(),
            'session_mismatch', 'Keep the originating Doubao project as the working directory.')
    root = Path.cwd() / '.soundmaker-smoke' / ('doubao-' + uuid.uuid4().hex[:10])
    root.mkdir(parents=True)
    core = ProjectCore(root)
    _, voice = core.add_voice('豆包接入测试音色（不生成音频）', 'other',
        {'provider': 'fake', 'region': 'test', 'model': 'fake-v1', 'voice_id': 'FAKE_VOICE_A'}, 0)
    qid = prepare(core, {'roles': ['test_narrator'], 'segments': [
        {'paragraph_id': 'p1', 'sentence_id': 's1', 'role_id': 'test_narrator',
         'text': 'SM_DOUBAO_BINDING_01：仅验证网页绑定完成后回到原聊天，不调用配音服务。'}]})['question_id']
    result = start(core, qid, allow_fake=True)
    result.update({'project': str(root), 'voice_id': voice, 'test_id': 'SM_DOUBAO_BINDING_01'})
    output = Path(__file__).resolve().parents[1] / 'outputs/doubao-binding-smoke-latest.json'
    output.parent.mkdir(exist_ok=True)
    output.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps(result, ensure_ascii=True))


if __name__ == '__main__':
    main()
