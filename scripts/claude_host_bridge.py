"""Entry point launched by Claude Desktop on the host, never inside VM Bash."""
import json
from pathlib import Path
import sys

if sys.version_info < (3, 11):
    # stdout belongs exclusively to MCP; startup diagnostics go to stderr.
    print(json.dumps({'code': 'python_unsupported', 'message': 'Use host Python 3.11+.'}), file=sys.stderr)
    raise SystemExit(2)

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from makesound.claude_host_bridge import main

if __name__ == '__main__':
    main()
