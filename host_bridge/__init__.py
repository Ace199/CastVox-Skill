"""Application-neutral local task bridge. No SoundMaker imports or business data."""
import hashlib
import json
import math
import threading
import uuid


class BridgeError(Exception):
    def __init__(self, code, message):
        super().__init__(message)
        self.code = code


def require(condition, code='invalid_request', message='Invalid bridge request.'):
    if not condition:
        raise BridgeError(code, message)


def tool(name, description, properties, required=()):
    return {'name': name, 'description': description, 'inputSchema': {
        'type': 'object', 'properties': properties, 'required': list(required), 'additionalProperties': False}}


class Bridge:
    """Explicitly supplied applications implement start, wait, read and close.

    Applications own their UI, persistence and authorization. The bridge owns
    per-process handles, request routing, cancellation and pending tool results.
    It never loads an application/module/command supplied by a tool caller.
    """
    def __init__(self, applications):
        self.applications = dict(applications)
        self.lock = threading.RLock()
        self.handles, self.requests = {}, {}
        self.waiters = set()
        self.closed = False

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.close()

    def tools(self):
        string, obj = {'type': 'string'}, {'type': 'object'}
        tools = [
            tool('host_bridge_status', 'List registered local applications and bridge transport status.', {}),
            tool('host_bridge_start', 'Start a task in a registered host application. Show its returned URL, '
                 'then call wait_tool in this original request. This does not authorize further actions.',
                 {'application': string, 'operation': string, 'payload': obj, 'request_id': string},
                 ('application', 'operation', 'payload', 'request_id')),
            tool('host_bridge_wait', 'Wait for this task in the original MCP request. Retry waiting with the same handle. '
                 'No messages are sent to other conversations.',
                 {'handle': string, 'timeout': {'type': 'number', 'minimum': 0, 'maximum': 55}}, ('handle',)),
            tool('host_bridge_read', 'Read a known application resource after reconnecting; no new task or page.',
                 {'application': string, 'resource': obj}, ('application', 'resource'))]
        for item in tools:
            item['inputSchema']['properties']['protocol_version'] = {'type': 'string', 'enum': ['1.0']}
        return tools

    def _result(self, value, application, protocol_version, adapter):
        if protocol_version is None:
            return value
        from .protocol import validate_result
        require(isinstance(value, dict), 'adapter_error', 'Application must return an object.')
        if value.get('protocol_version') != protocol_version and hasattr(adapter, 'to_result'):
            value = adapter.to_result(value)
        value = {**value, 'application': application}
        return validate_result(value)

    def _started(self, value, handle, application, protocol_version, adapter):
        value = self._result(value, application, protocol_version, adapter)
        arguments = {'handle': handle, 'timeout': 50}
        if protocol_version is not None:
            arguments['protocol_version'] = protocol_version
        return {**value, 'handle': handle, 'application': application,
                'wait_tool': {'name': 'host_bridge_wait', 'arguments': arguments}}

    def call(self, name, args, *, cancel_event=None):
        spec = next((item['inputSchema'] for item in self.tools() if item['name'] == name), None)
        require(spec is not None, 'unknown_tool', 'Unknown bridge tool.')
        require(isinstance(args, dict) and set(args) <= set(spec['properties']) and set(spec['required']) <= set(args))
        for key, value in args.items():
            kind = spec['properties'][key]['type']
            require((kind == 'string' and isinstance(value, str) and bool(value)) or
                    (kind == 'object' and isinstance(value, dict)) or
                    (kind == 'number' and type(value) in {int, float} and math.isfinite(value) and 0 <= value <= 55))
        protocol_version = args.get('protocol_version')
        if protocol_version is not None:
            from .protocol import version
            version(protocol_version)
        require(not self.closed, 'bridge_closed', 'Bridge is closed; application results are preserved.')
        if name == 'host_bridge_status':
            value = {'status': 'ready', 'execution_environment': 'host', 'applications': sorted(self.applications),
                     'continuation': 'pending_mcp_tool_result', 'receiver_verified': False,
                     'supported_protocol_versions': ['1.0']}
            if protocol_version:
                from .protocol import result
                return result('ready', data=value)
            return value
        if name == 'host_bridge_wait':
            with self.lock:
                record = self.handles.get(args['handle'])
                require(record is not None, 'unknown_handle', 'Unknown process-scoped handle; read the known application resource.')
                require(not record['waiting'], 'already_waiting', 'This task already has an active waiter.')
                event = cancel_event if cancel_event is not None else threading.Event()
                record['waiting'] = True
                self.waiters.add(event)
            try:
                value = record['application'].wait(record['handle'], args.get('timeout', 50), event)
                negotiated = protocol_version or record['protocol_version']
                value = self._result(value, record['name'], negotiated, record['application'])
                if negotiated:
                    expected = self._result(record['value'], record['name'], negotiated, record['application'])
                    require(value['task_id'] == expected['task_id'], 'task_mismatch', 'Application returned a different task to this waiter.')
                return value
            finally:
                with self.lock:
                    record['waiting'] = False
                    self.waiters.discard(event)
        application = self.applications.get(args['application'])
        require(application is not None, 'unknown_application', 'Application is not registered on this host.')
        if name == 'host_bridge_read':
            value = application.read(args['resource'])
            return self._result(value, args['application'], protocol_version, application)
        try:
            digest = hashlib.sha256(json.dumps([args['operation'], args['payload']], sort_keys=True,
                                               allow_nan=False).encode()).hexdigest()
        except (ValueError, TypeError):
            raise BridgeError('invalid_request', 'Task payload must be finite JSON data.') from None
        key = (args['application'], args['request_id'])
        with self.lock:
            previous = self.requests.get(key)
            if previous:
                require(previous['digest'] == digest, 'request_conflict', 'Request ID already refers to different task data.')
                return self._started(previous['value'], previous['handle'], args['application'], protocol_version, application)
            value = application.start(args['operation'], args['payload'], args['request_id'])
            require(isinstance(value, dict) and isinstance(value.get('handle'), str), 'adapter_error', 'Application returned no task handle.')
            self._result(value, args['application'], protocol_version, application)
            handle = 'ht_' + uuid.uuid4().hex
            self.handles[handle] = {'application': application, 'name': args['application'],
                                    'protocol_version': protocol_version, 'handle': value['handle'], 'value': value, 'waiting': False}
            self.requests[key] = {'digest': digest, 'value': value, 'handle': handle}
            return self._started(value, handle, args['application'], protocol_version, application)

    def close(self):
        with self.lock:
            if self.closed:
                return
            self.closed = True
            for event in self.waiters:
                event.set()
        for application in self.applications.values():
            application.close()
