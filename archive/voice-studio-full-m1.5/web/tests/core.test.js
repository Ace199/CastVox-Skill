import test from 'node:test';
import assert from 'node:assert/strict';
import { createStore } from '../js/store.js';
import { createEventLog } from '../js/events.js';
import { createMockApi } from '../js/api.js';
import { boundRoleNumbers, selectionGender } from '../js/voice-presentation.js';
import { voiceCategory } from '../js/modules/project-library.js';
import { filterCatalog, catalogAttributes } from '../js/catalog.js';
import { createCatalogLoader } from '../js/catalog-loader.js';
import { editorSignature, previewBlocker, defaultSaveBlocker } from '../js/editor.js';

test('Mock API returns isolated fixtures and logs success', async () => {
  const log = createEventLog(); const api = createMockApi(log);
  const data = await api.loadWorkspace();
  assert.equal(data.project.id, 'MOCK_PROJECT_A');
  assert.equal(data.voices.length, 3);
  data.voices.length = 0;
  assert.equal((await api.loadWorkspace()).voices.length, 3);
  assert.equal(log.getEntries().at(-1).name, 'api.workspace.success');
});
test('Mock API rejects errors and unknown projects with object identity', async () => {
  const log = createEventLog(); const api = createMockApi(log);
  await assert.rejects(api.loadWorkspace({ simulateError: true }), /模拟加载失败/);
  await assert.rejects(api.loadWorkspace({ projectId: 'INVALID' }), /不存在/);
  assert.equal(log.getEntries().at(-1).objectId, 'INVALID');
  assert.ok(log.getEntries().at(-1).error);
});
test('Store protects snapshots and supports subscription lifecycle', () => {
  const store = createStore(); const actions = [];
  const unsubscribe = store.subscribe((_state, action) => actions.push(action));
  const data = { project: { id: 'A' } };
  store.dispatch({ type: 'LOAD_START' }); store.dispatch({ type: 'LOAD_SUCCESS', data });
  data.project.id = 'MUTATED';
  const snapshot = store.getState(); snapshot.data.project.id = 'MUTATED';
  assert.equal(store.getState().data.project.id, 'A');
  store.dispatch({ type: 'SET_TAB', tab: 'basic' });
  store.dispatch({ type: 'TOGGLE_DEBUG' });
  assert.equal(store.getState().ui.debugOpen, true);
  assert.equal(store.getState().ui.tab, 'basic');
  assert.throws(() => store.dispatch({ type: 'SET_TAB', tab: 'invalid' }));
  assert.throws(() => store.dispatch({ type: 'INVALID' }));
  unsubscribe(); const count = actions.length;
  store.dispatch({ type: 'LOAD_FAILURE', error: '模拟错误' });
  assert.equal(actions.length, count); assert.equal(store.getState().status, 'error');
});
test('Event log is bounded, isolated, clearable and unsubscribable', () => {
  const log = createEventLog(); let notifications = 0;
  const unsubscribe = log.subscribe(() => notifications++);
  for (let n = 0; n < 105; n++) log.record({ name: 'test', objectId: String(n), error: n === 104 ? new Error('模拟错误') : null });
  const entries = log.getEntries(); assert.equal(entries.length, 100); assert.equal(entries[0].objectId, '5');
  entries[0].name = 'changed'; assert.equal(log.getEntries()[0].name, 'test');
  assert.equal(entries.at(-1).error, '模拟错误');
  unsubscribe(); log.clear(); assert.equal(log.getEntries().length, 0); assert.equal(notifications, 105);
});

test('Voice category uses attributed metadata, never names', () => {
  assert.equal(voiceCategory({ name: '女声音1', gender: 'unknown', provenance: 'mock' }), 'other');
  assert.equal(voiceCategory({ name: '男声', gender: 'female', provenance: 'mock' }), 'female');
  assert.equal(voiceCategory({ name: '女声', gender: 'male' }), 'other');
  assert.equal(voiceCategory({ gender: 'other', provenance: 'mock' }), 'other');
});

test('Project card, detail context and preview states are independent', async () => {
  const store = createStore(); const data = await createMockApi(createEventLog()).loadWorkspace();
  store.dispatch({ type: 'LOAD_SUCCESS', data });
  store.dispatch({ type: 'SELECT_PROJECT_VOICE', voiceId: 'MOCK_VOICE_A' });
  assert.equal(store.getState().ui.tab, 'basic');
  assert.equal(store.getState().ui.detailVoiceId, null);
  store.dispatch({ type: 'OPEN_VOICE_SETTINGS', voiceId: 'MOCK_VOICE_B' });
  assert.equal(store.getState().ui.tab, 'basic');
  assert.equal(store.getState().ui.detailVoiceId, 'MOCK_VOICE_B');
  store.dispatch({ type: 'PREVIEW_STATE', voiceId: 'MOCK_VOICE_A', status: 'error', error: '模拟音频错误' });
  assert.equal(store.getState().ui.detailVoiceId, 'MOCK_VOICE_B');
  assert.equal(store.getState().ui.preview.error, '模拟音频错误');
  assert.throws(() => store.dispatch({ type: 'OPEN_VOICE_SETTINGS', voiceId: 'INVALID' }));
  assert.throws(() => store.dispatch({ type: 'PREVIEW_STATE', voiceId: 'MOCK_VOICE_A', status: 'INVALID' }));
  assert.deepEqual(store.getState().data.roles, data.roles);
});

test('Role assignment and rebinding preserve independent parameters and immutable Agent input', async () => {
  const store = createStore(); const data = await createMockApi(createEventLog()).loadWorkspace();
  store.dispatch({ type: 'LOAD_SUCCESS', data });
  const original = structuredClone(store.getState().data);
  store.dispatch({ type: 'SELECT_ROLE', roleId: 'MOCK_ROLE_A' });
  store.dispatch({ type: 'ASSIGN_TARGET_VOICE', voiceId: 'MOCK_VOICE_A' });
  store.dispatch({ type: 'SELECT_ROLE', roleId: 'MOCK_ROLE_B' });
  assert.equal(store.getState().ui.selectedVoiceId, 'MOCK_VOICE_B');
  store.dispatch({ type: 'ASSIGN_TARGET_VOICE', voiceId: 'MOCK_VOICE_A' });
  assert.equal(store.getState().task.selections.MOCK_ROLE_B.parameters.speed, 0.9);
  store.dispatch({ type: 'SELECT_ROLE', roleId: 'MOCK_ROLE_A' });
  assert.equal(store.getState().task.selections.MOCK_ROLE_A.parameters.speed, 1.1);
  store.dispatch({ type: 'ASSIGN_TARGET_VOICE', voiceId: 'MOCK_VOICE_C' });
  assert.equal(store.getState().task.selections.MOCK_ROLE_B.voiceId, 'MOCK_VOICE_A');
  assert.equal(store.getState().task.selections.MOCK_ROLE_N.voiceId, null);
  const beforeSettings = store.getState().task;
  store.dispatch({ type: 'OPEN_VOICE_SETTINGS', voiceId: 'MOCK_VOICE_B' });
  store.dispatch({ type: 'PREVIEW_STATE', voiceId: 'MOCK_VOICE_A', status: 'playing' });
  assert.deepEqual(store.getState().task, beforeSettings);
  assert.deepEqual(store.getState().data, original);
  assert.equal(store.getState().projectDefault.saved, null);
  assert.throws(() => store.dispatch({ type: 'SELECT_ROLE', roleId: 'OTHER_JOB_ROLE' }));
  assert.throws(() => store.dispatch({ type: 'ASSIGN_TARGET_VOICE', voiceId: 'INVALID' }));
});

test('Default save requires current explicit confirmation and never mutates task selections', async () => {
  const store = createStore(); const data = await createMockApi(createEventLog()).loadWorkspace();
  store.dispatch({ type: 'LOAD_SUCCESS', data });
  const selections = store.getState().task.selections;
  store.dispatch({ type: 'SELECT_DEFAULT' });
  assert.throws(() => store.dispatch({ type: 'REQUEST_DEFAULT_SAVE' }));
  store.dispatch({ type: 'ASSIGN_TARGET_VOICE', voiceId: 'MOCK_VOICE_A' });
  assert.equal(store.getState().projectDefault.saved, null);
  assert.throws(() => store.dispatch({ type: 'CONFIRM_DEFAULT_SAVE' }));
  store.dispatch({ type: 'REQUEST_DEFAULT_SAVE' });
  store.dispatch({ type: 'CANCEL_DEFAULT_SAVE' });
  assert.equal(store.getState().projectDefault.draft.voiceId, 'MOCK_VOICE_A');
  assert.equal(store.getState().projectDefault.saved, null);
  store.dispatch({ type: 'REQUEST_DEFAULT_SAVE' });
  store.dispatch({ type: 'ASSIGN_TARGET_VOICE', voiceId: 'MOCK_VOICE_B' });
  assert.throws(() => store.dispatch({ type: 'CONFIRM_DEFAULT_SAVE' }));
  store.dispatch({ type: 'REQUEST_DEFAULT_SAVE' });
  store.dispatch({ type: 'CONFIRM_DEFAULT_SAVE' });
  assert.equal(store.getState().projectDefault.saved.voiceId, 'MOCK_VOICE_B');
  assert.equal(store.getState().projectDefault.revision, 1);
  assert.throws(() => store.dispatch({ type: 'CONFIRM_DEFAULT_SAVE' }));
  store.dispatch({ type: 'ASSIGN_TARGET_VOICE', voiceId: 'MOCK_VOICE_C' });
  store.dispatch({ type: 'DISCARD_DEFAULT_DRAFT' });
  assert.equal(store.getState().projectDefault.draft.voiceId, 'MOCK_VOICE_B');
  assert.equal(store.getState().ui.selectedVoiceId, 'MOCK_VOICE_B');
  assert.deepEqual(store.getState().task.selections, selections);
  assert.equal(store.getState().data.project.defaultVoice, null);
});

test('Changing targets retains default draft and roles; different jobs reload without leakage', async () => {
  const store = createStore(); const data = await createMockApi(createEventLog()).loadWorkspace();
  store.dispatch({ type: 'LOAD_SUCCESS', data });
  store.dispatch({ type: 'SELECT_DEFAULT' }); store.dispatch({ type: 'ASSIGN_TARGET_VOICE', voiceId: 'MOCK_VOICE_A' });
  store.dispatch({ type: 'SELECT_ROLE', roleId: 'MOCK_ROLE_N' }); store.dispatch({ type: 'ASSIGN_TARGET_VOICE', voiceId: 'MOCK_VOICE_B' });
  store.dispatch({ type: 'SELECT_DEFAULT' }); assert.equal(store.getState().ui.selectedVoiceId, 'MOCK_VOICE_A');
  assert.equal(store.getState().task.selections.MOCK_ROLE_N.voiceId, 'MOCK_VOICE_B');
  data.job.id = 'MOCK_OTHER_JOB'; store.dispatch({ type: 'LOAD_SUCCESS', data });
  assert.equal(store.getState().task.jobId, 'MOCK_OTHER_JOB');
  assert.equal(store.getState().task.selections.MOCK_ROLE_N.voiceId, null);
  assert.equal(store.getState().projectDefault.draft, null);
  data.job = null; store.dispatch({ type: 'LOAD_SUCCESS', data });
  assert.throws(() => store.dispatch({ type: 'SELECT_ROLE', roleId: 'MOCK_ROLE_A' }));
  store.dispatch({ type: 'SELECT_DEFAULT' }); store.dispatch({ type: 'ASSIGN_TARGET_VOICE', voiceId: 'MOCK_VOICE_A' });
  store.dispatch({ type: 'REQUEST_DEFAULT_SAVE' }); store.dispatch({ type: 'CONFIRM_DEFAULT_SAVE' });
  assert.deepEqual(store.getState().task.selections, {});
});

test('Catalog Mock API isolates fixtures and supports failure and empty scenarios', async () => {
  const log = createEventLog(); const api = createMockApi(log);
  const voices = await api.listCatalog(); assert.equal(voices.length, 6);
  voices[0].tags.push('changed'); assert.equal((await api.listCatalog())[0].tags.includes('changed'), false);
  assert.deepEqual(await api.listCatalog({ empty: true }), []);
  await assert.rejects(api.listCatalog({ simulateError: true }), /声音池加载失败/);
  assert.equal(log.getEntries().at(-1).name, 'api.catalog.failure');
});

test('Catalog keyword, source and feature filters combine and never infer metadata', async () => {
  const voices = await createMockApi(createEventLog()).listCatalog();
  const filters = { query: '', source: 'all', feature: 'all' };
  assert.equal(filterCatalog(voices, filters).length, 6);
  assert.deepEqual(filterCatalog(voices, { query: '  轻柔 ', source: 'official', feature: 'female' }).map(voice => voice.id), ['MOCK_OFFICIAL_B']);
  assert.equal(filterCatalog(voices, { query: 'mock_official_a', source: 'all', feature: '青年' })[0].id, 'MOCK_OFFICIAL_A');
  assert.equal(filterCatalog(voices, { query: '甜美女声', source: 'user', feature: 'female' }).length, 0);
  assert.equal(filterCatalog(voices, { query: '甜美女声', source: 'user', feature: 'unknown' }).length, 1);
  assert.deepEqual(catalogAttributes({ name: '女声', gender: 'female', tags: ['温柔'] }), { gender: 'unknown', tags: [] });
});

test('Selecting pool candidates only changes viewing context, never task/default/project data', async () => {
  const api = createMockApi(createEventLog()); const store = createStore();
  store.dispatch({ type: 'LOAD_SUCCESS', data: await api.loadWorkspace() });
  store.dispatch({ type: 'SELECT_ROLE', roleId: 'MOCK_ROLE_A' });
  const before = store.getState();
  store.dispatch({ type: 'CATALOG_LOAD_SUCCESS', voices: await api.listCatalog() });
  store.dispatch({ type: 'OPEN_POOL_SETTINGS', voiceId: 'MOCK_USER_B' });
  assert.equal(store.getState().ui.detailKind, 'pool'); assert.equal(store.getState().ui.tab, 'basic');
  assert.deepEqual(store.getState().task, before.task); assert.deepEqual(store.getState().data, before.data);
  assert.deepEqual(store.getState().projectDefault, before.projectDefault);
  store.dispatch({ type: 'SET_CATALOG_FILTER', key: 'query', value: 'hidden' });
  assert.equal(store.getState().catalog.selectedId, 'MOCK_USER_B');
  assert.throws(() => store.dispatch({ type: 'SET_CATALOG_FILTER', key: 'feature', value: 'invented' }));
  assert.throws(() => store.dispatch({ type: 'OPEN_POOL_SETTINGS', voiceId: 'INVALID' }));
  store.dispatch({ type: 'OPEN_VOICE_SETTINGS', voiceId: 'MOCK_VOICE_A' });
  assert.equal(store.getState().ui.detailKind, 'project');
  store.dispatch({ type: 'CATALOG_LOAD_FAILURE', error: '失败' });
  assert.equal(store.getState().ui.detailVoiceId, 'MOCK_VOICE_A');
  assert.throws(() => store.dispatch({ type: 'OPEN_POOL_SETTINGS', voiceId: 'MOCK_USER_B' }));
});

test('Catalog loader ignores stale success/failure without resetting workspace', async () => {
  const store = createStore(); const pending = [];
  const api = { listCatalog: () => new Promise((resolve, reject) => pending.push({ resolve, reject })) };
  const load = createCatalogLoader(store, api);
  const first = load(); const second = load();
  assert.equal(store.getState().catalog.status, 'loading');
  pending[1].resolve([{ id: 'latest' }]); await second;
  pending[0].reject(new Error('stale')); await first;
  assert.equal(store.getState().catalog.voices[0].id, 'latest');
  const failed = load(); pending[2].reject(new Error('current failure')); await failed;
  assert.equal(store.getState().catalog.status, 'error'); assert.equal(store.getState().catalog.error, 'current failure');
});

test('Shared editor draft survives Tabs and keeps project, role and candidate settings independent', async () => {
  const store = createStore(), api = createMockApi(createEventLog());
  store.dispatch({ type: 'LOAD_SUCCESS', data: await api.loadWorkspace() });
  store.dispatch({ type: 'CATALOG_LOAD_SUCCESS', voices: await api.listCatalog() });
  const original = store.getState().data, task = store.getState().task;
  store.dispatch({ type: 'OPEN_VOICE_SETTINGS', voiceId: 'MOCK_VOICE_A' });
  store.dispatch({ type: 'EDIT_FIELD', field: 'speed', value: 1.6 });
  store.dispatch({ type: 'EDIT_FIELD', field: 'latex', value: true });
  store.dispatch({ type: 'SET_TAB', tab: 'explore' });
  assert.equal(store.getState().editor.drafts['project:MOCK_VOICE_A'].speed, 1.6);
  store.dispatch({ type: 'SELECT_ROLE', roleId: 'MOCK_ROLE_A' });
  assert.equal(store.getState().editor.drafts[store.getState().editor.activeKey].speed, 1.1);
  store.dispatch({ type: 'EDIT_FIELD', field: 'volume', value: 2.2 });
  store.dispatch({ type: 'SELECT_ROLE', roleId: 'MOCK_ROLE_B' });
  assert.equal(store.getState().editor.drafts[store.getState().editor.activeKey].volume, 0.8);
  store.dispatch({ type: 'SELECT_ROLE', roleId: 'MOCK_ROLE_A' });
  assert.equal(store.getState().editor.drafts[store.getState().editor.activeKey].volume, 2.2);
  store.dispatch({ type: 'OPEN_POOL_SETTINGS', voiceId: 'MOCK_OFFICIAL_A' });
  assert.equal(store.getState().editor.drafts[store.getState().editor.activeKey].speed, 1.1);
  store.dispatch({ type: 'OPEN_VOICE_SETTINGS', voiceId: 'MOCK_VOICE_A' });
  assert.equal(store.getState().editor.drafts[store.getState().editor.activeKey].speed, 1.1);
  assert.deepEqual(store.getState().data, original); assert.deepEqual(store.getState().task, task);
});

test('Model incompatibility preserves original emotion and requires an explicit compatible choice', async () => {
  const store = createStore(), api = createMockApi(createEventLog());
  store.dispatch({ type: 'LOAD_SUCCESS', data: await api.loadWorkspace() });
  store.dispatch({ type: 'OPEN_VOICE_SETTINGS', voiceId: 'MOCK_VOICE_A' });
  store.dispatch({ type: 'EDIT_FIELD', field: 'emotion', value: 'sad' });
  store.dispatch({ type: 'EDIT_FIELD', field: 'model', value: 'MOCK_STUDIO_LIGHT' });
  let state = store.getState(), draft = state.editor.drafts[state.editor.activeKey];
  assert.equal(draft.emotion, 'sad'); assert.match(previewBlocker(state, draft), /不支持/);
  assert.throws(() => store.dispatch({ type: 'EDIT_FIELD', field: 'emotion', value: 'angry' }));
  store.dispatch({ type: 'EDIT_FIELD', field: 'emotion', value: 'happy' });
  state = store.getState(); draft = state.editor.drafts[state.editor.activeKey]; assert.equal(previewBlocker(state, draft), '');
  for (const [field, value] of [['speed', 0], ['volume', 11], ['latex', 'yes'], ['text', 'a'.repeat(2001)], ['pitch', 1]]) assert.throws(() => store.dispatch({ type: 'EDIT_FIELD', field, value }));
});

test('Mock preview fingerprints reflect edits, remain scoped after context switches, and block unavailable voices', async () => {
  const store = createStore(), api = createMockApi(createEventLog());
  store.dispatch({ type: 'LOAD_SUCCESS', data: await api.loadWorkspace() });
  store.dispatch({ type: 'CATALOG_LOAD_SUCCESS', voices: await api.listCatalog() });
  store.dispatch({ type: 'OPEN_VOICE_SETTINGS', voiceId: 'MOCK_VOICE_A' });
  const key = store.getState().editor.activeKey; const draft = store.getState().editor.drafts[key]; const signature = editorSignature(draft);
  store.dispatch({ type: 'EDITOR_PREVIEW_START', key, signature });
  store.dispatch({ type: 'EDIT_FIELD', field: 'text', value: '参数已经改变，这是一条需要重新试听的完整句子。' });
  store.dispatch({ type: 'SELECT_ROLE', roleId: 'MOCK_ROLE_B' });
  store.dispatch({ type: 'EDITOR_PREVIEW_SUCCESS', key, signature, result: await api.createPreview({ draft }) });
  assert.notEqual(store.getState().editor.activeKey, key);
  assert.notEqual(editorSignature(store.getState().editor.drafts[key]), signature);
  assert.equal(store.getState().editor.drafts[key].preview.signature, signature);
  store.dispatch({ type: 'OPEN_POOL_SETTINGS', voiceId: 'MOCK_USER_B' });
  const state = store.getState(); assert.match(previewBlocker(state, state.editor.drafts[state.editor.activeKey]), /不可用/);
  await assert.rejects(api.createPreview({ draft, simulateError: true }), /模拟试听失败/);
});

test('Default parameter edits remain drafts until confirmation and discard restores saved settings', async () => {
  const store = createStore(), api = createMockApi(createEventLog());
  store.dispatch({ type: 'LOAD_SUCCESS', data: await api.loadWorkspace() });
  const task = store.getState().task;
  store.dispatch({ type: 'SELECT_DEFAULT' }); store.dispatch({ type: 'ASSIGN_TARGET_VOICE', voiceId: 'MOCK_VOICE_A' });
  store.dispatch({ type: 'EDIT_FIELD', field: 'speed', value: 1.4 });
  store.dispatch({ type: 'EDIT_FIELD', field: 'latex', value: true });
  assert.equal(store.getState().projectDefault.saved, null);
  store.dispatch({ type: 'REQUEST_DEFAULT_SAVE' }); store.dispatch({ type: 'CONFIRM_DEFAULT_SAVE' });
  assert.equal(store.getState().projectDefault.saved.parameters.speed, 1.4);
  assert.equal(store.getState().projectDefault.saved.studioSettings.latex, true);
  store.dispatch({ type: 'EDIT_FIELD', field: 'speed', value: 1.7 });
  store.dispatch({ type: 'DISCARD_DEFAULT_DRAFT' });
  assert.equal(store.getState().editor.drafts[store.getState().editor.activeKey].speed, 1.4);
  store.dispatch({ type: 'EDIT_FIELD', field: 'emotion', value: 'sad' });
  store.dispatch({ type: 'EDIT_FIELD', field: 'model', value: 'MOCK_STUDIO_LIGHT' });
  assert.match(defaultSaveBlocker(store.getState()), /兼容性/);
  assert.throws(() => store.dispatch({ type: 'REQUEST_DEFAULT_SAVE' }));
  assert.deepEqual(store.getState().task, task); assert.equal(store.getState().data.project.defaultVoice, null);
});


test('Quick default confirmation preserves role target and editor drafts, rejects stale revision', async () => {
  const api=createMockApi(), store=createStore(); store.dispatch({type:'LOAD_SUCCESS',data:await api.loadWorkspace()});
  store.dispatch({type:'SELECT_ROLE',roleId:'MOCK_ROLE_A'});
  const before=store.getState();
  store.dispatch({type:'QUICK_DEFAULT_OPEN'}); store.dispatch({type:'QUICK_DEFAULT_VOICE',voiceId:'MOCK_VOICE_B'});
  assert.equal(store.getState().projectDefault.saved,null);
  store.dispatch({type:'QUICK_DEFAULT_CANCEL'}); assert.equal(store.getState().projectDefault.saved,null);
  store.dispatch({type:'QUICK_DEFAULT_OPEN'}); store.dispatch({type:'QUICK_DEFAULT_VOICE',voiceId:'MOCK_VOICE_B'});
  store.dispatch({type:'QUICK_DEFAULT_CONFIRM'});
  const after=store.getState(); assert.equal(after.projectDefault.saved.voiceId,'MOCK_VOICE_B');
  assert.deepEqual(after.task,before.task); assert.deepEqual(after.editor,before.editor); assert.deepEqual(after.ui.target,before.ui.target);
  assert.equal(after.data.project.defaultVoice,null);
  store.dispatch({type:'QUICK_DEFAULT_OPEN'});
  const library=await api.getProjectLibrary(); store.dispatch({type:'LIBRARY_SYNC',result:{...library,revision:library.revision+1}});
  assert.throws(()=>store.dispatch({type:'QUICK_DEFAULT_CONFIRM'}),/确认已失效/);
});

test('Compact workflow opens Basic, collapses only project settings and retains catalogue filters', async () => {
  const api=createMockApi(), store=createStore();store.dispatch({type:'LOAD_SUCCESS',data:await api.loadWorkspace()});
  store.dispatch({type:'CATALOG_LOAD_SUCCESS',voices:await api.listCatalog()});
  store.dispatch({type:'SET_CATALOG_FILTER',key:'query',value:'清晰'});
  store.dispatch({type:'OPEN_POOL_SETTINGS',voiceId:'MOCK_OFFICIAL_A'});
  assert.equal(store.getState().ui.tab,'basic'); assert.equal(store.getState().ui.poolCollapsed,false);
  store.dispatch({type:'OPEN_VOICE_SETTINGS',voiceId:'MOCK_VOICE_A'});
  assert.equal(store.getState().ui.poolCollapsed,true);assert.equal(store.getState().ui.tab,'basic');
  store.dispatch({type:'SET_POOL_COLLAPSED',value:false}); assert.equal(store.getState().catalog.filters.query,'清晰');
  assert.throws(()=>store.dispatch({type:'SET_POOL_COLLAPSED',value:'false'}),/无效/);
});

test('Mock Harness requires a complete assignment and receives an isolated snapshot without network', async () => {
  const log=createEventLog(), api=createMockApi(log);
  await assert.rejects(api.notifyHarness({projectId:'P',jobId:'J',assignments:[{roleId:'A',voiceId:null}]}),/未通知 Harness/);
  const rows=[{roleId:'A',voiceId:'MOCK_VOICE_A',parameters:{speed:1}}];
  const result=await api.notifyHarness({projectId:'P',jobId:'J',assignments:rows});
  assert.equal(result.mock,true);assert.equal(result.status,'acknowledged');
  rows[0].parameters.speed=2;assert.equal(result.assignments[0].parameters.speed,1);
  assert.equal(log.getEntries().at(-1).name,'harness.mock.notified');
});


test('Single pool selection cannot activate settings or mutate role/default/editor; explicit open can', async () => {
  const api=createMockApi(),store=createStore();store.dispatch({type:'LOAD_SUCCESS',data:await api.loadWorkspace()});
  store.dispatch({type:'CATALOG_LOAD_SUCCESS',voices:await api.listCatalog()});
  store.dispatch({type:'OPEN_VOICE_SETTINGS',voiceId:'MOCK_VOICE_A'});store.dispatch({type:'SET_TAB',tab:'explore'});
  const before=store.getState();store.dispatch({type:'SELECT_POOL_VOICE',voiceId:'MOCK_OFFICIAL_B'});
  const selected=store.getState();assert.equal(selected.catalog.selectedId,'MOCK_OFFICIAL_B');
  assert.deepEqual(selected.ui,before.ui);assert.deepEqual(selected.editor,before.editor);assert.deepEqual(selected.task,before.task);assert.deepEqual(selected.projectDefault,before.projectDefault);
  store.dispatch({type:'OPEN_POOL_SETTINGS',voiceId:'MOCK_OFFICIAL_B'});
  assert.equal(store.getState().ui.tab,'basic');assert.equal(store.getState().editor.activeKey,'pool:MOCK_OFFICIAL_B');
  assert.throws(()=>store.dispatch({type:'POOL_PREVIEW_STATE',voiceId:'MOCK_USER_UNKNOWN',status:'loading'}),/未确认可用/);
  assert.throws(()=>store.dispatch({type:'POOL_PREVIEW_STATE',voiceId:'MOCK_USER_B',status:'loading'}),/未确认可用/);
});


test('Binding markers show all corresponding role numbers and preserve attributed voice color', async () => {
 const api=createMockApi(),store=createStore();store.dispatch({type:'LOAD_SUCCESS',data:await api.loadWorkspace()});
 let state=store.getState();const a=state.data.voices.find(v=>v.id==='MOCK_VOICE_A'),b=state.data.voices.find(v=>v.id==='MOCK_VOICE_B');
 assert.deepEqual(boundRoleNumbers(state,a),[]);assert.deepEqual(boundRoleNumbers(state,b),[2]);
 store.dispatch({type:'SELECT_ROLE',roleId:'MOCK_ROLE_A'});store.dispatch({type:'ASSIGN_TARGET_VOICE',voiceId:a.id});
 store.dispatch({type:'SELECT_ROLE',roleId:'MOCK_ROLE_N'});store.dispatch({type:'ASSIGN_TARGET_VOICE',voiceId:a.id});
 state=store.getState();assert.deepEqual(boundRoleNumbers(state,a),[1,3]);assert.equal(selectionGender(state,state.task.selections.MOCK_ROLE_A),'male');assert.equal(selectionGender(state,state.task.selections.MOCK_ROLE_B),'female');
 store.dispatch({type:'ASSIGN_TARGET_VOICE',voiceId:'MOCK_VOICE_C'});state=store.getState();assert.deepEqual(boundRoleNumbers(state,a),[1]);assert.equal(selectionGender(state,state.task.selections.MOCK_ROLE_N),'other');
});


test('Role identity, seeded parameters, names and randomized avatars remain scoped and stable', async () => {
 const api=createMockApi(),store=createStore(),data=await api.loadWorkspace();store.dispatch({type:'LOAD_SUCCESS',data});store.dispatch({type:'CATALOG_LOAD_SUCCESS',voices:await api.listCatalog()});
 const avatars=store.getState().task.avatars;assert.equal(Object.keys(avatars).length,3);
 store.dispatch({type:'SELECT_ROLE',roleId:'MOCK_ROLE_B'});assert.equal(store.getState().flow.name,'温柔女声');
 store.dispatch({type:'EDIT_FIELD',field:'speed',value:1.3});store.dispatch({type:'EDIT_FIELD',field:'text',value:'角色 B 的完整句。'});store.dispatch({type:'FLOW_NAME',value:'B 专属声'});
 store.dispatch({type:'OPEN_POOL_SETTINGS',voiceId:'MOCK_OFFICIAL_A'});let state=store.getState(),draft=state.editor.drafts[state.editor.activeKey];assert.equal(draft.speed,1.3);assert.equal(draft.volume,0.8);assert.equal(draft.text,'角色 B 的完整句。');assert.equal(state.flow.name,'B 专属声');
 store.dispatch({type:'SELECT_ROLE',roleId:'MOCK_ROLE_A'});store.dispatch({type:'OPEN_POOL_SETTINGS',voiceId:'MOCK_OFFICIAL_A'});state=store.getState();draft=state.editor.drafts[state.editor.activeKey];assert.equal(draft.speed,1.1);assert.equal(state.flow.name,'主角 A');
 store.dispatch({type:'SELECT_ROLE',roleId:'MOCK_ROLE_B'});store.dispatch({type:'OPEN_POOL_SETTINGS',voiceId:'MOCK_OFFICIAL_A'});state=store.getState();assert.equal(state.editor.drafts[state.editor.activeKey].speed,1.3);assert.equal(state.flow.name,'B 专属声');assert.deepEqual(state.task.avatars,avatars);
 store.dispatch({type:'LOAD_SUCCESS',data});assert.deepEqual(store.getState().task.avatars,avatars);
});
