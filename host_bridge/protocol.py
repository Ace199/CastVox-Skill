"""Host Bridge application protocol v1; independent of MCP wire versions."""
import json
import re
from . import BridgeError, require

VERSION = '1.0'
MAX_BYTES = 1024 * 1024
STATES = {'ready', 'waiting', 'completed', 'cancelled', 'failed'}


def json_object(value):
    require(isinstance(value, dict), message='Expected a JSON object.')
    stack = [(value, 0)]
    while stack:
        item, depth = stack.pop()
        require(depth <= 64, message='JSON nesting exceeds 64 levels.')
        if isinstance(item, dict):
            require(all(isinstance(key, str) for key in item), message='JSON object keys must be strings.')
            stack.extend((child, depth + 1) for child in item.values())
        elif isinstance(item, list):
            stack.extend((child, depth + 1) for child in item)
        else:
            require(item is None or type(item) in {str, bool, int, float}, message='Expected JSON data types.')
    try:
        encoded = json.dumps(value, ensure_ascii=False, allow_nan=False).encode('utf-8')
    except (TypeError, ValueError, UnicodeError):
        raise BridgeError('invalid_request', 'Expected finite JSON data.') from None
    require(len(encoded) <= MAX_BYTES, 'request_too_large', 'JSON exceeds 1 MiB.')
    return value


def identifier(value):
    require(isinstance(value, str) and re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_-]{0,127}', value),
            message='Use a 1-128 character identifier containing letters, digits, underscores or hyphens.')
    return value


def version(value):
    require(value == VERSION, 'unsupported_protocol', 'Supported application protocol: 1.0.')


def result(status, task_id=None, data=None, *, application=None, revision=None, error=None, **extra):
    value = {'protocol_version': VERSION, 'application': application, 'task_id': task_id,
             'status': status, 'revision': revision, 'data': {} if data is None else data, 'error': error, **extra}
    validate_result(value)
    return value


def validate_result(value):
    json_object(value)
    require({'protocol_version', 'status', 'task_id', 'revision', 'data', 'error'} <= set(value),
            'adapter_error', 'Application result is missing protocol fields.')
    version(value['protocol_version'])
    allowed = {'protocol_version', 'application', 'task_id', 'status', 'revision', 'data', 'error',
               'handle', 'url', 'resource', 'wait_tool', 'wait_cancelled'}
    require(set(value) <= allowed, 'adapter_error', 'Application-specific fields belong inside data.')
    require(isinstance(value['status'], str) and value['status'] in STATES and isinstance(value['data'], dict),
            'adapter_error', 'Invalid application result status or data.')
    require(value.get('application') is None or isinstance(value['application'], str) and bool(value['application']),
            'adapter_error', 'Invalid application name.')
    for key in ('handle',):
        require(key not in value or isinstance(value[key], str) and bool(value[key]), 'adapter_error', 'Invalid result handle.')
    require('url' not in value or value['url'] is None or isinstance(value['url'], str), 'adapter_error', 'Invalid result URL.')
    require('resource' not in value or isinstance(value['resource'], dict), 'adapter_error', 'Invalid result resource.')
    require('wait_cancelled' not in value or type(value['wait_cancelled']) is bool, 'adapter_error', 'Invalid wait cancellation flag.')
    require(value['revision'] is None or type(value['revision']) is int and value['revision'] >= 0,
            'adapter_error', 'Invalid application task revision.')
    require(value['task_id'] is None or isinstance(value['task_id'], str) and bool(value['task_id']),
            'adapter_error', 'Invalid durable task ID.')
    if value['status'] in {'waiting', 'completed', 'cancelled'}:
        require(value['task_id'] is not None and value['revision'] is not None,
                'adapter_error', 'Task results require durable task_id and revision.')
    error = value['error']
    require((value['status'] == 'failed') == (error is not None), 'adapter_error', 'Failed results require an error; other states require null.')
    if error is not None:
        require(isinstance(error, dict) and set(error) == {'code', 'message', 'retryable'}
                and isinstance(error['code'], str) and bool(error['code'])
                and isinstance(error['message'], str) and type(error['retryable']) is bool,
                'adapter_error', 'Invalid error object.')
    return value


def error_result(error, args, *, task_id=None, application=None):
    if not isinstance(args, dict) or 'protocol_version' not in args:
        return {'status': 'error', 'code': error.code, 'message': str(error)}
    application = application or args.get('application')
    if not isinstance(application, str):
        application = None
    return result('failed', task_id, application=application,
                  error={'code': error.code, 'message': str(error), 'retryable': False})


def submission(value):
    json_object(value)
    keys = {'protocol_version', 'task_id', 'submission_id', 'expected_revision', 'action', 'data'}
    require(set(value) == keys, message='Missing or unexpected submission fields.')
    version(value['protocol_version'])
    identifier(value['task_id'])
    identifier(value['submission_id'])
    require(type(value['expected_revision']) is int and value['expected_revision'] >= 0,
            message='expected_revision must be a nonnegative integer.')
    require(isinstance(value['action'], str) and value['action'] in {'complete', 'cancel'} and isinstance(value['data'], dict),
            message='Use complete/cancel and an object data payload.')
    return value


def pairs(items):
    obj = {}
    for key, value in items:
        require(key not in obj, message='Duplicate JSON keys are not allowed.')
        obj[key] = value
    return obj


def loads(value):
    try:
        return json.loads(value, object_pairs_hook=pairs,
                          parse_constant=lambda _: (_ for _ in ()).throw(ValueError()))
    except (ValueError, UnicodeError):
        raise BridgeError('invalid_request', 'Invalid JSON body.') from None
