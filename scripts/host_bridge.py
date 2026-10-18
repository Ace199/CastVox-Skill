"""Host task MCP entry; application adapters are explicitly enabled at startup."""
import argparse
from pathlib import Path
import sys

if sys.version_info < (3, 11):
    print('Host bridge requires Python 3.11+.', file=sys.stderr)
    raise SystemExit(2)

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from host_bridge import Bridge
from host_bridge.transport import serve


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--application', action='append', choices=['soundmaker', 'forms'], required=True)
    parser.add_argument('--allowed-root', action='append', required=True)
    args = parser.parse_args()
    applications = {}
    if 'soundmaker' in args.application:
        from makesound.host_application import SoundMakerApplication
        applications['soundmaker'] = SoundMakerApplication(args.allowed_root)
    if 'forms' in args.application:
        from host_bridge.example import FormApplication
        applications['forms'] = FormApplication(Path(args.allowed_root[0]) / 'host-bridge-forms')
    sys.stdin.reconfigure(encoding='utf-8')
    sys.stdout.reconfigure(encoding='utf-8')
    with Bridge(applications) as bridge:
        serve(bridge, sys.stdin, sys.stdout)


if __name__ == '__main__':
    main()
