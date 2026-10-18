"""Concurrent stdio MCP transport, independent of application code."""
from concurrent.futures import ThreadPoolExecutor
import json
import threading
from . import BridgeError, require
from .protocol import error_result, loads


def serve(bridge, stdin, stdout, *, error_types=(BridgeError,), server_name='host-bridge', instructions='Show the application URL, then keep the original request waiting with host_bridge_wait. No external conversation messages.'):
    output_lock, task_lock = threading.Lock(), threading.Lock()
    tasks = {}
    def emit(value):
        with output_lock:
            stdout.write(json.dumps(value, ensure_ascii=False) + '\n')
            stdout.flush()
    def dispatch(request, event):
        identity = request['id']
        try:
            method, params = request.get('method'), request.get('params', {})
            if method == 'initialize':
                result = {'protocolVersion': params.get('protocolVersion', '2025-03-26'), 'capabilities': {'tools': {}},
                          'serverInfo': {'name': server_name, 'version': '1.0.0'}, 'instructions': instructions}
            elif method == 'ping':
                result = {}
            elif method == 'tools/list':
                result = {'tools': bridge.tools()}
            elif method == 'tools/call':
                try:
                    value = bridge.call(params.get('name'), params.get('arguments', {}), cancel_event=event)
                    result = {'content': [{'type': 'text', 'text': json.dumps(value, ensure_ascii=False)}]}
                except error_types as error:
                    value = error_result(error, params.get('arguments', {}))
                    result = {'isError': True, 'content': [{'type': 'text', 'text': json.dumps(value)}]}
            else:
                emit({'jsonrpc': '2.0', 'id': identity, 'error': {'code': -32601, 'message': 'Method not found'}})
                return
            emit({'jsonrpc': '2.0', 'id': identity, 'result': result})
        except Exception:
            emit({'jsonrpc': '2.0', 'id': identity, 'error': {'code': -32603, 'message': 'Host task request failed; saved results are preserved.'}})
        finally:
            with task_lock:
                tasks.pop(identity, None)
    with ThreadPoolExecutor(max_workers=8) as executor:
        try:
            for line in stdin:
                try:
                    require(len(line) <= 1048576, 'invalid_request', 'Request exceeds the bridge size limit.')
                    request = loads(line)
                    require(isinstance(request, dict) and request.get('jsonrpc') == '2.0', 'invalid_request', 'Invalid JSON-RPC request.')
                    if 'id' not in request:
                        if request.get('method') == 'notifications/cancelled':
                            with task_lock:
                                event = tasks.get(request.get('params', {}).get('requestId'))
                                if event:
                                    event.set()
                        continue
                    require(type(request['id']) in {str, int}, 'invalid_request', 'Expected a string or integer request ID.')
                    event = threading.Event()
                    with task_lock:
                        require(request['id'] not in tasks, 'invalid_request', 'Request ID is already active.')
                        tasks[request['id']] = event
                    executor.submit(dispatch, request, event)
                except Exception:
                    emit({'jsonrpc': '2.0', 'id': None, 'error': {'code': -32600, 'message': 'Invalid request'}})
        finally:
            with task_lock:
                for event in tasks.values():
                    event.set()
            bridge.close()
