"""Runnable choice-form application demonstrating a SoundMaker-free integration."""
import threading
from . import require
from .http import create_server
from .tasks import TaskStore

PAGE = '''<!doctype html><meta charset="utf-8"><title>Host Bridge form</title>
<h1></h1><select></select><button>提交选择</button><p role="status"></p>
<script type="module">
import {session} from '/host-bridge/session.js';
const headers={'Authorization':'Bearer '+session.token};
const state=await (await fetch(session.task_url,{headers})).json();
document.querySelector('h1').textContent=state.data.input?.title ?? '已保存';
for(const choice of state.data.input?.choices ?? []) {
  const option=document.createElement('option'); option.textContent=choice;
  document.querySelector('select').append(option);
}
const button=document.querySelector('button'); button.disabled=state.status!=='waiting';
let pending=null;
button.onclick=async()=>{
  pending ??= {protocol_version:'1.0',task_id:session.task_id,submission_id:crypto.randomUUID(),
    expected_revision:state.revision,action:'complete',data:{selected:document.querySelector('select').value}};
  button.disabled=true;
  try {
    const response=await fetch(session.submit_url,{method:'POST',headers:{...headers,
      'Content-Type':'application/json','X-CSRF-Token':session.csrf},body:JSON.stringify(pending)});
    const value=await response.json();
    if(!response.ok) throw new Error(value.error?.message ?? '提交失败');
    document.querySelector('p').textContent='已保存，可返回原会话。';
  } catch(error) {document.querySelector('p').textContent=error.message; button.disabled=false;}
};
</script>'''


class FormApplication:
    def __init__(self, directory):
        self.store = TaskStore(directory, 'forms')
        self.pages = {}

    def start(self, operation, payload, request_id):
        require(operation == 'choose', 'unknown_operation', 'The example supports choose only.')
        require(set(payload) == {'title', 'choices'} and isinstance(payload['title'], str)
                and isinstance(payload['choices'], list) and 1 <= len(payload['choices']) <= 20
                and all(isinstance(x, str) and x for x in payload['choices']), message='Provide a title and 1-20 choice strings.')
        value = self.store.create(operation, payload, request_id)
        task_id = value['task_id']
        if task_id not in self.pages and value['status'] == 'waiting':
            store = self.store
            class API:
                def read(self):
                    return store.read(task_id)

                def submit(self, body):
                    def validate(action, data, original):
                        if action == 'complete':
                            require(set(data) == {'selected'} and data['selected'] in original['choices'],
                                    'invalid_choice', 'Select one of the task choices.')
                    return store.submit(body, validate=validate)
            server = create_server(API(), PAGE)
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()
            self.pages[task_id] = (server, thread)
        server = self.pages.get(task_id)
        return {**value, 'handle': task_id, 'resource': {'task_id': task_id},
                'url': f'http://127.0.0.1:{server[0].server_port}' if server and value['status'] == 'waiting' else None}

    def wait(self, handle, timeout, cancel_event):
        return self.store.wait(handle, timeout, cancel_event)

    def read(self, resource):
        require(set(resource) == {'task_id'}, message='Read by task_id.')
        return self.store.read(resource['task_id'])

    def close(self):
        for server, thread in self.pages.values():
            server.shutdown()
            server.server_close()
            thread.join(timeout=3)
