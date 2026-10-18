"""SoundMaker adapter for the independent host_bridge task protocol."""
from host_bridge import BridgeError
from .claude_host_bridge import Bridge as BindingApplication
from .errors import MakeSoundError
from host_bridge.protocol import result, submission
from host_bridge.tasks import SubmissionJournal


class SoundMakerApplication:
    def __init__(self, allowed_roots):
        self.binding = BindingApplication(allowed_roots)

    def _call(self, name, args, **kwargs):
        try:
            return self.binding.call(name, args, **kwargs)
        except MakeSoundError as error:
            raise BridgeError(error.code, str(error)) from None

    def start(self, operation, payload, request_id):
        methods = {'prepare_binding': 'soundmaker_prepare_binding', 'open_binding': 'soundmaker_open_binding',
                   'smoke_binding': 'soundmaker_smoke_binding'}
        if operation not in methods:
            raise BridgeError('unknown_operation', 'Unknown SoundMaker binding operation; synthesis is not exposed.')
        args = dict(payload)
        if operation in {'prepare_binding', 'smoke_binding'}:
            if 'request_id' in args and args['request_id'] != request_id:
                raise BridgeError('request_conflict', 'Use the envelope request_id for this operation.')
            args['request_id'] = request_id
        value = self._call(methods[operation], args)
        resource = {key: value[key] for key in ('project_key', 'question_id', 'root_index')}
        record = self.binding.handles[value['handle']]
        if record['server'] is not None:
            record['server'].bridge_api = BindingSubmissionAPI(self, resource, record['core'])
        return {**value, 'resource': resource}

    def wait(self, handle, timeout, cancel_event):
        return self._call('soundmaker_wait_binding', {'handle': handle, 'timeout': timeout}, cancel_event=cancel_event)

    def read(self, resource):
        return {**self._call('soundmaker_read_binding', resource), 'resource': resource}

    def to_result(self, value):
        state = {'binding_open': 'waiting', 'pending': 'waiting', 'waiting': 'waiting',
                 'binding_saved': 'completed', 'cancelled': 'waiting'}.get(value.get('status'))
        if state is None:
            raise BridgeError('adapter_error', 'Unrecognized binding state.')
        data = {key: item for key, item in value.items() if key not in {'handle', 'url', 'wait_tool', 'resource'}}
        extra = {key: value[key] for key in ('handle', 'url', 'resource') if key in value}
        if value.get('status') == 'cancelled':
            extra['wait_cancelled'] = True
        return result(state, value['question_id'], data, application='soundmaker',
                      revision=1 if state == 'completed' else 0, **extra)

    def close(self):
        self.binding.close()


class BindingSubmissionAPI:
    """Translate v1 submissions to existing Question/Answer validation/storage."""
    def __init__(self, application, resource, core):
        self.application, self.resource, self.core = application, resource, core
        self.journal = SubmissionJournal(core.managed_path('.makesound/host-bridge/submissions'), 'soundmaker')

    def read(self):
        return self.application.to_result(self.application.read(self.resource))

    def submit(self, body):
        submission(body)
        if body['task_id'] != self.resource['question_id']:
            raise BridgeError('task_mismatch', 'This page belongs to another task.')
        def apply(value, recovering):
            if value['action'] != 'complete':
                raise BridgeError('unsupported_action', 'Binding tasks support complete only; close the page to leave a task pending.')
            data = value['data']
            if (set(data) - {'assignments', 'project_revision'} or not isinstance(data.get('assignments'), dict)):
                raise BridgeError('invalid_request', 'Binding data requires assignments and optional project_revision.')
            current = self.read()
            if current['status'] == 'completed':
                if not recovering or current['data']['answer']['assignments'] != data['assignments']:
                    raise BridgeError('task_completed', 'The saved binding is immutable; open an editable revision.')
            else:
                if current['revision'] != value['expected_revision']:
                    raise BridgeError('revision_conflict', 'Reload this task before submitting.')
                from .studio_backend import StudioBackend
                payload = {'question_id': value['task_id'], 'assignments': data['assignments']}
                if 'project_revision' in data:
                    payload['revision'] = data['project_revision']
                try:
                    StudioBackend(self.core).dispatch('answers', payload)
                except MakeSoundError as error:
                    raise BridgeError(error.code, str(error)) from None
            from .harness_resume import notify
            notify(self.core, value['task_id'])
            return self.read()
        return self.journal.commit(body, apply)
