"""Prepare a fake binding task; launch it separately from Kimi's own Bash tool."""
import argparse
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from makesound.core_v16 import ProjectCore
from makesound.offline_harness import prepare


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--project', required=True)
    args = parser.parse_args()
    core = ProjectCore(Path(args.project).resolve())
    _, voice = core.add_voice('Kimi恢复测试音色（不生成音频）', 'other',
        {'provider': 'fake', 'region': 'test', 'model': 'fake-v1', 'voice_id': 'FAKE_VOICE_A'}, 0)
    qid = prepare(core, {'roles': ['test_narrator'], 'segments': [
        {'paragraph_id': 'p1', 'sentence_id': 's1', 'role_id': 'test_narrator',
         'text': 'SM_KIMI_BINDING_01：仅测试绑定后恢复原聊天，不调用任何配音服务。'}]})['question_id']
    print(json.dumps({'project': str(core.root), 'question_id': qid, 'voice_id': voice,
                      'test_id': 'SM_KIMI_BINDING_01'}))


if __name__ == '__main__':
    main()
