"""Start an already-closed Windows Doubao with temporary loopback debugging."""
import json
import os
from pathlib import Path
import socket
import subprocess
import time
import urllib.request
from urllib.parse import urlsplit


def clean_environment(environment):
    prefixes = ('CODEX_', 'CLAUDE_', 'KIMI_', 'DAIMON_', 'WORKBUDDY_', 'DOUBAO_OFFICE_')
    return {k: v for k, v in environment.items()
            if not k.upper().startswith(prefixes) and k.upper() != 'MCP_VM_CONVERSATION_ID'}


def main():
    if os.name != 'nt':
        raise SystemExit('This launcher supports Windows only.')
    home = Path.home()
    binary = home / 'AppData/Local/Doubao/Application/app/Doubao.exe'
    if not binary.is_file():
        raise SystemExit('The verified Doubao executable is missing.')
    powershell = Path(os.environ.get('SystemRoot', r'C:\Windows')) / 'System32/WindowsPowerShell/v1.0/powershell.exe'
    command = "$ErrorActionPreference = 'Stop'; @(Get-CimInstance Win32_Process -Filter \"name = 'Doubao.exe'\" -ErrorAction Stop | Select-Object -ExpandProperty ProcessId) | ConvertTo-Json -Compress"
    check = subprocess.run([str(powershell), '-NoProfile', '-NonInteractive', '-Command', command],
                           capture_output=True, timeout=10, creationflags=subprocess.CREATE_NO_WINDOW)
    if check.returncode:
        raise SystemExit('Cannot verify that Doubao has exited; no launch attempted.')
    raw = check.stdout.decode('utf-8-sig').strip()
    running = json.loads(raw) if raw else []
    # Refuse every same-named process, including one whose executable path cannot be read.
    if running:
        raise SystemExit('Exit Doubao normally first; this launcher never terminates user tasks.')
    with socket.socket() as listener:
        listener.bind(('127.0.0.1', 0))
        port = listener.getsockname()[1]
    process = subprocess.Popen([str(binary), '--remote-debugging-address=127.0.0.1', f'--remote-debugging-port={port}'],
                               env=clean_environment(os.environ), stdin=subprocess.DEVNULL,
                               stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                               creationflags=subprocess.DETACHED_PROCESS | subprocess.CREATE_NO_WINDOW)
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
    version = None
    deadline = time.monotonic() + 25
    while time.monotonic() < deadline:
        try:
            with opener.open(f'http://127.0.0.1:{port}/json/version', timeout=1) as response:
                version = json.load(response)
            break
        except (OSError, ValueError):
            time.sleep(.25)
    if not version:
        raise SystemExit('Debug endpoint not ready; app left running, no automatic retry.')
    browser = urlsplit(version.get('webSocketDebuggerUrl', ''))
    if browser.scheme != 'ws' or browser.hostname != '127.0.0.1' or browser.port != port:
        raise SystemExit('Unexpected browser endpoint; bridge not configured.')
    network = subprocess.run([str(powershell), '-NoProfile', '-NonInteractive', '-Command',
        f'@(Get-NetTCPConnection -LocalPort {port} -State Listen -ErrorAction Stop | Select-Object -ExpandProperty LocalAddress) | ConvertTo-Json -Compress'],
        capture_output=True, timeout=10, creationflags=subprocess.CREATE_NO_WINDOW)
    if network.returncode:
        raise SystemExit('Cannot verify loopback binding; bridge not configured.')
    addresses = json.loads(network.stdout.decode('utf-8-sig'))
    if isinstance(addresses, str):
        addresses = [addresses]
    if not addresses or any(a != '127.0.0.1' for a in addresses):
        raise SystemExit('Non-loopback listener; bridge not configured.')
    config = {'endpoint': f'http://127.0.0.1:{port}', 'browser_path': browser.path,
              'profile_path': str(home / 'AppData/Local/Doubao/User Data/Default')}
    destination = Path(__file__).resolve().parents[1] / '.makesound/doubao-bridge.json'
    destination.parent.mkdir(exist_ok=True)
    temporary = destination.with_suffix('.tmp')
    temporary.write_text(json.dumps(config, indent=2), encoding='utf-8')
    temporary.replace(destination)
    print(json.dumps({'started': True, 'pid': process.pid, 'endpoint': config['endpoint'],
                      'loopback_verified': True, 'inherited_harness_identity': False}))


if __name__ == '__main__':
    main()
