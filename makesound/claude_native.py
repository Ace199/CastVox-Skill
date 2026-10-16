"""Own-session Claude messaging. Tokens stay in inherited process environments."""
import hashlib
import json
import os
from pathlib import Path
import socket
import subprocess
import uuid

from .errors import require


def environment_target():
    address = os.environ.get('CLAUDE_CODE_MESSAGING_SOCKET', '')
    token = os.environ.get('CLAUDE_CODE_MESSAGING_TOKEN', '')
    if not address and not token:
        return None
    require(bool(address and token), 'harness_unavailable', 'Claude messaging environment is incomplete.')
    validate_address(address)
    return {'harness': 'claude_native', 'socket': address,
            'token_fingerprint': hashlib.sha256(token.encode()).hexdigest()}


def validate_address(address):
    require(isinstance(address, str) and '\n' not in address and '\r' not in address,
            'invalid_target', 'Invalid Claude message address.')
    if os.name == 'nt':
        require(address.startswith('\\\\.\\pipe\\LOCAL\\cc-msg-') and len(address) > 23,
                'invalid_target', 'Expected a local Claude named pipe.')
    else:
        require(Path(address).is_absolute(), 'invalid_target', 'Expected an absolute Unix socket path.')


_WINDOWS_SEND = r'''
$ErrorActionPreference = 'Stop'
$inputData = [Console]::In.ReadToEnd() | ConvertFrom-Json
$pipe = [System.IO.Pipes.NamedPipeClientStream]::new('.', $inputData.address.Substring(9), [System.IO.Pipes.PipeDirection]::Out)
try {
  $pipe.Connect(5000)
  $writer = [System.IO.StreamWriter]::new($pipe, [System.Text.UTF8Encoding]::new($false), 4096, $true)
  try { $writer.Write($inputData.lines); $writer.Flush() } finally { $writer.Dispose() }
} catch { exit 1 } finally { $pipe.Dispose() }
'''


def send(target, message):
    current = environment_target()
    require(current is not None and all(target.get(k) == v for k, v in current.items()),
            'session_mismatch', 'Claude sender no longer belongs to this binding session.')
    message_id = 'cc-msg-' + uuid.uuid4().hex
    lines = '\n'.join(json.dumps(value, ensure_ascii=True) for value in [
        {'type': 'auth', 'token': os.environ['CLAUDE_CODE_MESSAGING_TOKEN']},
        {'type': 'user', 'message': {'role': 'user', 'content': message},
         'priority': 'next', 'msgV': 1, 'msg_id': message_id}]) + '\n'
    if os.name == 'nt':
        powershell = Path(os.environ.get('SystemRoot', r'C:\Windows')) / 'System32/WindowsPowerShell/v1.0/powershell.exe'
        result = subprocess.run([str(powershell), '-NoProfile', '-NonInteractive', '-Command', _WINDOWS_SEND],
                                input=json.dumps({'address': current['socket'], 'lines': lines}).encode('ascii'),
                                capture_output=True, timeout=10, creationflags=subprocess.CREATE_NO_WINDOW)
        require(result.returncode == 0, 'delivery_failed', 'Claude message pipe was unavailable.')
    else:
        with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as connection:
            connection.settimeout(5)
            connection.connect(current['socket'])
            connection.sendall(lines.encode('utf-8'))
    # The native stream does not acknowledge delivery or inbound permission decisions.
    return {'status': 'sent_unconfirmed', 'message_id': message_id}
