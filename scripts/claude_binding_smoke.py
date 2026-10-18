"""Run inside the originating Claude Bash tool; creates only a fake binding fixture."""
import json
import argparse
from pathlib import Path
import sys
import uuid

if sys.version_info < (3, 11):
    print(json.dumps({'status': 'error', 'code': 'python_unsupported',
                      'required_python': '3.11+',
                      'message': 'Use a confirmed Python 3.11+ interpreter in this execution environment. '
                                 'No runtime imports or test project creation were attempted.'}))
    raise SystemExit(2)

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from makesound.core_v16 import ProjectCore
from makesound.offline_harness import prepare
from makesound.studio_session import start
from makesound.claude_native import connection_status


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--surface', choices=('code', 'cowork'), default='code')
    args = parser.parse_args()
    connection = connection_status(args.surface)
    # Cowork workspace MCP commands may intentionally inherit no host variables.
    # Explicit tool-result mode needs a pending requesting call, not an invented
    # native/session identity. Code keeps its existing native preflight.
    tool_result = args.surface == 'cowork' and connection['status'] != 'available'
    if connection['status'] != 'available' and not tool_result:
        print(json.dumps(connection))
        return 2
    root = Path(__file__).resolve().parents[1] / 'outputs' / ('claude-binding-smoke-' + uuid.uuid4().hex[:10])
    root.mkdir(parents=True)
    core = ProjectCore(root)
    _, voice = core.add_voice('测试音色（不生成音频）', 'other',
        {'provider': 'fake', 'region': 'test', 'model': 'fake-v1', 'voice_id': 'FAKE_VOICE_A'}, 0)
    qid = prepare(core, {'roles': ['test_narrator'], 'segments': [
        {'paragraph_id': 'p1', 'sentence_id': 's1', 'role_id': 'test_narrator',
         'text': 'SM_CLAUDE_BINDING_02：仅测试网页绑定完成后的原会话恢复，不调用任何配音服务。'}]})['question_id']
    result = start(core, qid, allow_fake=True, completion_mode='tool-result' if tool_result else 'auto')
    result.update({'project': str(root), 'voice_id': voice, 'test_id': 'SM_CLAUDE_BINDING_02'})
    if tool_result:
        result.update(transport='pending_tool_result', next_action='Show and open the returned URL, then keep the original Cowork request waiting on wait_command.',
                      wait_command=[sys.executable, '-X', 'utf8', '-m', 'makesound.cowork_task',
                                    '--project', str(root), '--question', result['question_id'], '--timeout', '50'])
    # Public test metadata only; inherited authentication is never serialized.
    (root.parent / 'claude-binding-smoke-latest.json').write_text(json.dumps(result, ensure_ascii=False), encoding='utf-8')
    print(json.dumps(result, ensure_ascii=True))


if __name__ == '__main__':
    raise SystemExit(main())
