import test from 'node:test';
import assert from 'node:assert/strict';
import { createStore } from '../js/store.js';
import { createMockApi } from '../js/api.js';
import { createEventLog } from '../js/events.js';
import { createAssignmentFlow } from '../js/assignment-flow.js';
import { editorSignature } from '../js/editor.js';

async function setup() {
  const log = createEventLog(), api = createMockApi(log), store = createStore();
  store.dispatch({ type: 'LOAD_SUCCESS', data: await api.loadWorkspace() });
  store.dispatch({ type: 'CATALOG_LOAD_SUCCESS', voices: await api.listCatalog() });
  return { log, api, store, flow: createAssignmentFlow(store, api, log) };
}
async function preview(store, api, id = 'MOCK_OFFICIAL_A') {
  store.dispatch({ type: 'OPEN_POOL_SETTINGS', voiceId: id });
  const key = store.getState().editor.activeKey, draft = store.getState().editor.drafts[key], signature = editorSignature(draft);
  store.dispatch({ type: 'EDITOR_PREVIEW_START', key, signature });
  const result = await api.createPreview({ draft });
  store.dispatch({ type: 'EDITOR_PREVIEW_SUCCESS', key, signature, result });
  return { draft, result };
}
test('Cache covers canonical voice, model, text and every effective setting; duplicate inflight requests coalesce', async () => {
  const { store, api, log } = await setup(); const { draft, result } = await preview(store, api);
  assert.equal(result.cacheHit, false); assert.equal((await api.createPreview({ draft })).cacheHit, true);
  const variants = [{ resolvedVoiceKey: 'pool:OTHER' }, { model: 'MOCK_STUDIO_LIGHT' }, { text: '另一条完整的试听句子。' }, { emotion: 'happy' }, { speed: 1.2 }, { volume: 1.2 }, { latex: true }, { normalize: false }];
  for (const change of variants) assert.equal((await api.createPreview({ draft: { ...draft, ...change } })).cacheHit, false);
  const duplicate = { ...draft, text: '并发请求使用同一条新的试听文本。' };
  const before = log.getEntries().filter(event => event.name === 'api.preview.success').length;
  const results = await Promise.all([api.createPreview({ draft: duplicate }), api.createPreview({ draft: duplicate })]);
  assert.equal(results[0].cacheKey, results[1].cacheKey);
  assert.equal(log.getEntries().filter(event => event.name === 'api.preview.success').length, before + 1);
  api.configureMock({ failPreview: true }); await assert.rejects(api.createPreview({ draft }), /模拟试听失败/);
  assert.equal((await api.createPreview({ draft })).cacheHit, true);
});
test('Current audition gates role application; stale result and invalid targets are rejected', async () => {
  const { store, api, flow } = await setup();
  await preview(store, api); assert.throws(() => flow.applyRole(), /有效任务角色/);
  store.dispatch({ type: 'SELECT_ROLE', roleId: 'MOCK_ROLE_A' }); await preview(store, api);
  const beforeB = store.getState().task.selections.MOCK_ROLE_B;
  store.dispatch({type:'FLOW_NAME',value:'晴朗叙述'}); flow.applyRole(); assert.equal(store.getState().task.selections.MOCK_ROLE_A.voiceRef, 'pool:MOCK_OFFICIAL_A');
  assert.deepEqual(store.getState().task.selections.MOCK_ROLE_B, beforeB);
  store.dispatch({ type: 'EDIT_FIELD', field: 'speed', value: 1.3 });
  assert.throws(() => flow.applyRole(), /当前参数试听/);
  assert.equal(store.getState().task.selections.MOCK_ROLE_A.parameters.speed, 1.1);
  store.dispatch({ type: 'SELECT_DEFAULT' }); await preview(store, api); assert.throws(() => flow.applyRole());
});
test('Library save is atomic with captured role, duplicate clicks do not create extra aliases', async () => {
  const { store, api, flow } = await setup();
  store.dispatch({ type: 'SELECT_ROLE', roleId: 'MOCK_ROLE_A' }); await preview(store, api);
  store.dispatch({ type: 'FLOW_NAME', value: '新项目声音' });
  const first = flow.save(), second = flow.save();
  store.dispatch({ type: 'SELECT_ROLE', roleId: 'MOCK_ROLE_N' }); await Promise.all([first, second]);
  assert.equal(store.getState().data.voices.length, 4); assert.equal(store.getState().libraryRevision, 1);
  assert.equal(store.getState().task.selections.MOCK_ROLE_A.voiceName, '新项目声音');
  assert.equal(store.getState().task.selections.MOCK_ROLE_N.voiceId, null);
  await preview(store, api); store.dispatch({ type: 'SELECT_ROLE', roleId: 'MOCK_ROLE_A' });
  assert.equal((await api.getProjectLibrary()).voices.length, 4);
});
test('Rebinding requires old reference and revision; conflict preserves draft and requires fresh confirmation', async () => {
  const { store, api, flow } = await setup();
  store.dispatch({ type: 'SELECT_ROLE', roleId: 'MOCK_ROLE_A' }); await preview(store, api, 'MOCK_OFFICIAL_B');
  store.dispatch({ type: 'FLOW_NAME', value: '温柔女声' });
  await flow.save(); assert.ok(store.getState().flow.confirmation);
  api.configureMock({ conflict: true }); await flow.save(true);
  assert.match(store.getState().flow.error, /revision 冲突/); assert.equal(store.getState().flow.confirmation, null);
  assert.equal(store.getState().data.voices.find(voice => voice.name === '温柔女声').originVoiceKey, undefined);
  await flow.refresh(); await flow.save(); assert.ok(store.getState().flow.confirmation);
  await flow.save(true);
  const state = store.getState();
  assert.equal(state.libraryRevision, 2);
  assert.equal(state.data.voices.find(voice => voice.name === '温柔女声').originVoiceKey, 'pool:MOCK_OFFICIAL_B');
  assert.equal(state.task.selections.MOCK_ROLE_B.voiceRef, 'project:MOCK_VOICE_B');
  assert.equal(state.task.selections.MOCK_ROLE_A.voiceRef, 'pool:MOCK_OFFICIAL_B');
  await flow.save(); assert.equal(store.getState().libraryRevision, 2);
});
test('Known save failure retries without partial application; management save does not invent a role', async () => {
  const { store, api, flow } = await setup();
  const data = store.getState().data; data.job = null; store.dispatch({ type: 'LOAD_SUCCESS', data });
  await preview(store, api); store.dispatch({ type: 'FLOW_NAME', value: '管理模式音色' });
  api.configureMock({ failSave: true }); await flow.save();
  assert.equal(store.getState().data.voices.length, 3); assert.match(store.getState().flow.error, /模拟保存失败/);
  await flow.save(); assert.equal(store.getState().data.voices.length, 4); assert.deepEqual(store.getState().task.selections, {});
});
test('Pool default must use explicit confirmation; summary shows pending roles accurately', async () => {
  const { store, api, flow } = await setup();
  store.dispatch({ type: 'SELECT_DEFAULT' }); await preview(store, api, 'MOCK_OFFICIAL_B');
  const before = store.getState().task;
  flow.prepareDefault(); assert.ok(store.getState().projectDefault.confirmation);
  assert.equal(store.getState().projectDefault.saved, null);
  store.dispatch({ type: 'CONFIRM_DEFAULT_SAVE' });
  assert.equal(store.getState().projectDefault.saved.voiceRef, 'pool:MOCK_OFFICIAL_B');
  assert.deepEqual(store.getState().task, before);
  store.dispatch({ type: 'FLOW_SUMMARY' }); assert.equal(store.getState().flow.summary.filter(row => !row.voiceId).length, 2);
});
test('Save API receipt replay and old-reference checks prevent duplicate or unconfirmed changes', async () => {
  const { store, api } = await setup(); const { draft } = await preview(store, api);
  const metadata = store.getState().catalog.voices[0];
  const request = { name: '幂等保存', draft, metadata, expectedRevision: 0, operationId: 'TEST_OPERATION' };
  const [a, b] = await Promise.all([api.saveProjectVoice(request), api.saveProjectVoice(request)]);
  assert.equal(a.revision, 1); assert.deepEqual(a, b); assert.equal((await api.getProjectLibrary()).voices.length, 4);
  await assert.rejects(api.saveProjectVoice({ ...request, name: '其他内容' }), /内容不一致/);
  await assert.rejects(api.saveProjectVoice({ ...request, operationId: 'NEW', name: '温柔女声', expectedRevision: 1 }), /明确确认/);
});

test('Save completing after a Job switch cannot bind the new Job even with identical role IDs', async () => {
  const { store, api, flow } = await setup();
  store.dispatch({ type: 'SELECT_ROLE', roleId: 'MOCK_ROLE_A' }); await preview(store, api);
  store.dispatch({ type: 'FLOW_NAME', value: '跨任务保存保护' }); const pending = flow.save();
  const data = await api.loadWorkspace(); data.job.id = 'MOCK_NEXT_JOB'; store.dispatch({ type: 'LOAD_SUCCESS', data });
  await pending;
  assert.equal(store.getState().task.jobId, 'MOCK_NEXT_JOB');
  assert.equal(store.getState().task.selections.MOCK_ROLE_A.voiceId, null);
  assert.equal(store.getState().data.voices.length, 4);
});


test('Role-pool naming is required and local to the task, without creating or changing project voices', async () => {
 const log=createEventLog(), api=createMockApi(log),store=createStore();store.dispatch({type:'LOAD_SUCCESS',data:await api.loadWorkspace()});
 store.dispatch({type:'CATALOG_LOAD_SUCCESS',voices:await api.listCatalog()});store.dispatch({type:'SELECT_ROLE',roleId:'MOCK_ROLE_A'});store.dispatch({type:'OPEN_POOL_SETTINGS',voiceId:'MOCK_OFFICIAL_B'});
 const flow=createAssignmentFlow(store,api,log);await preview(store,api);
 store.dispatch({type:'FLOW_NAME',value:''});const before=store.getState();assert.throws(()=>flow.applyRole(),/请输入音色名称/);assert.deepEqual(store.getState().task,before.task);
 store.dispatch({type:'FLOW_NAME',value:' 角色声 '});assert.throws(()=>flow.applyRole(),/无首尾空格/);
 store.dispatch({type:'FLOW_NAME',value:'主角专属声'});flow.applyRole();const after=store.getState();
 assert.equal(after.task.selections.MOCK_ROLE_A.voiceName,'主角专属声');assert.deepEqual(after.data,before.data);assert.deepEqual(after.projectDefault,before.projectDefault);assert.deepEqual(after.task.selections.MOCK_ROLE_B,before.task.selections.MOCK_ROLE_B);
});
