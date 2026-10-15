import test from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { createMockApi } from '../js/api.js';
import { createStore, freshDraft } from '../js/store.js';
import { createController } from '../js/controller.js';
import { createEventLog } from '../js/events.js';
import { controlCapability } from '../js/capabilities.js';
import { activeVoices, buildAnswer, defaultVoice, editorDirty, previewStatus, resolveRole, signature } from '../js/voice-model.js';

const descriptors = ['minimax', 'volcengine'].map(id => ({ id, name: id, region: 'configured', source: 'mock_fixture', ...JSON.parse(readFileSync(new URL(`./fixtures/providers/${id}/config.json`, import.meta.url))) }));
async function setup() { const log = createEventLog(), api = createMockApi(log, descriptors), store = createStore(), providers = api.getProviders(); store.update({ providers, draft: freshDraft('minimax', providers[0].default_model) }); const controller = createController(store, api, log); await controller.load(); return { log, api, store, controller, providers }; }
function fill(store, name = '新声音', id = 'MOCK_NEW_ID', category = 'other') { store.edit('name', name); store.edit('voiceId', id); store.edit('category', category); }
async function saveDefaults(store, controller, values) { for (const [slot, id] of Object.entries(values)) store.editDefault(slot, id); controller.requestDefaults(); assert.equal(store.getState().confirmation.kind, 'defaults'); await controller.confirmDefaults(); }

test('stable IDs: same source/different names create independent cards; active duplicate cannot overwrite', async () => {
  const { store, controller } = await setup(); fill(store, '版本一'); await controller.addVoice(); const a = Object.values(store.getState().data.voices).find(v => v.name === '版本一'); fill(store, '版本二'); await controller.addVoice(); const b = Object.values(store.getState().data.voices).find(v => v.name === '版本二'); assert.notEqual(a.id, b.id); assert.deepEqual(a.source, b.source);
  fill(store, '版本一'); await controller.addVoice(); assert.match(store.getState().error, /同名/); assert.equal(activeVoices(store.getState().data).length, 5);
});
test('classification is explicit and names are NFC unique', async () => {
  const { store, controller } = await setup(); fill(store, 'é', 'A', ''); await controller.addVoice(); assert.match(store.getState().error, /分类/); store.edit('category', 'male'); await controller.addVoice(); fill(store, 'e\u0301', 'B', 'male'); await controller.addVoice(); assert.match(store.getState().error, /同名/);
});
test('provider drafts round trip without foreign IDs and cannot modify saved source', async () => {
  const { store } = await setup(); const source = structuredClone(store.getState().data.voices.pv_001.source); fill(store, 'A', 'MINIMAX_ONLY'); store.switchProvider('volcengine'); assert.equal(store.getState().draft.voiceId, ''); fill(store, 'B', 'VOLC_ONLY'); store.switchProvider('minimax'); assert.equal(store.getState().draft.voiceId, 'MINIMAX_ONLY'); store.switchProvider('volcengine'); assert.equal(store.getState().draft.voiceId, 'VOLC_ONLY'); assert.deepEqual(store.getState().data.voices.pv_001.source, source);
});
test('capabilities: real descriptors missing verification disable controls; Mock ranges are explicit', async () => {
  const { store, providers } = await setup(), source = store.getState().data.voices.pv_001.source;
  assert.equal(controlCapability(source, [], 'speed').enabled, false); const cap = controlCapability(source, providers, 'pitch'); assert.equal(cap.verification, 'mock_only'); assert.equal(cap.step, 1);
});
test('settings draft is isolated, cancel restores values, source is immutable', async () => {
  const { store, api, controller } = await setup(); controller.openSettings('pv_001'); store.editSetting('name', '未保存'); store.editSetting('speed', 1.2); assert.equal(store.getState().data.voices.pv_001.name, '项目旁白'); assert.equal(editorDirty(store.getState()), true); store.cancelEditor(); assert.equal(editorDirty(store.getState()), false);
  const state = store.getState(); await assert.rejects(api.saveVoice({ id: 'pv_001', draft: { ...state.editor.draft, source: {} }, expectedSource: state.editor.source, expectedRevision: state.data.revision }), /只读/);
});
test('range and step validation is descriptor driven', async () => {
  const { store, controller } = await setup(); controller.openSettings('pv_001'); store.editSetting('speed', 1.25); await controller.saveSettings(); assert.match(store.getState().error, /步长/); store.editSetting('speed', 1.2); store.editSetting('pitch', 2); await controller.saveSettings(); assert.equal(store.getState().data.voices.pv_001.settings.speed, 1.2); assert.equal(store.getState().data.voices.pv_001.settings.pitch, 2);
});
test('switching editor requires save or discard and failed save does not switch', async () => {
  const { store, controller } = await setup(); controller.openSettings('pv_001'); store.editSetting('name', '改名'); controller.openSettings('pv_002'); assert.equal(store.getState().confirmation.kind, 'switch-edit'); controller.discardAndSwitch(); assert.equal(store.getState().editor.id, 'pv_002'); assert.equal(store.getState().data.voices.pv_001.name, '项目旁白');
  store.editSetting('name', '对白新名'); controller.openSettings('pv_001'); await controller.saveAndSwitch(); assert.equal(store.getState().editor.id, 'pv_001'); assert.equal(store.getState().data.voices.pv_002.name, '对白新名');
});
test('rename/category preserve ID and preview signature; saved parameter changes mark stale and reverting clears it', async () => {
  const { store, controller } = await setup(); const original = store.getState().data.voices.pv_002.preview; controller.openSettings('pv_002'); store.editSetting('name', '新对白'); store.editSetting('category', 'other'); await controller.saveSettings(); assert.equal(previewStatus(store.getState().data.voices.pv_002).kind, 'valid'); assert.deepEqual(store.getState().data.voices.pv_002.preview, original);
  store.editSetting('speed', 1.3); await controller.saveSettings(); assert.equal(previewStatus(store.getState().data.voices.pv_002).kind, 'stale'); store.editSetting('speed', 1); await controller.saveSettings(); assert.equal(previewStatus(store.getState().data.voices.pv_002).kind, 'valid');
});
test('three optional defaults require confirmation and never bind task roles', async () => {
  const { store, controller, api } = await setup(); store.selectDefault('male'); store.assign('pv_002'); assert.equal(store.getState().defaultsDraft.male, null); store.assign('pv_001'); assert.equal(store.getState().defaultsDraft.male, 'pv_001'); assert.equal(store.getState().data.defaults.male, null); assert.equal(store.getState().roles[0].assignment, null);
  await assert.rejects(api.saveDefaults({ defaults: store.getState().defaultsDraft, expectedRevision: 0 }), /确认/); controller.requestDefaults(); await controller.confirmDefaults(); assert.equal(store.getState().data.defaults.male, 'pv_001');
});
test('default invalidation by category keeps raw reference and explicit task identity', async () => {
  const { store, controller } = await setup(); await saveDefaults(store, controller, { female: 'pv_002' }); store.selectRole('MOCK_ROLE_B'); store.assign('pv_002'); const assignment = store.getState().roles[1].assignment;
  controller.openSettings('pv_002'); store.editSetting('category', 'other'); await controller.saveSettings(); assert.equal(store.getState().confirmation.kind, 'category'); await controller.saveSettings(true, null); const state = store.getState(); assert.equal(state.data.defaults.female, 'pv_002'); assert.equal(defaultVoice(state.data, 'female'), null); assert.deepEqual(state.roles[1].assignment, assignment);
});
test('role resolution uses only explicit gender requirements, preserves invalid explicit assignments without fallback', async () => {
  const { store, controller } = await setup(); await saveDefaults(store, controller, { female: 'pv_002', general: 'pv_001' }); const state = store.getState(); assert.equal(resolveRole(state, state.roles[1]).via, 'default_female'); assert.equal(resolveRole(state, { name: '女王', gender_requirement: null, assignment: null }).via, 'default_general'); assert.ok(resolveRole(state, { assignment: { project_voice_id: 'missing', snapshot: null } }).error);
});
test('empty defaults do not block fully assigned required roles; missing required role blocks submission', async () => {
  const { store } = await setup(); assert.throws(() => buildAnswer(store.getState()), /必要角色/); for (const role of store.getState().roles) { store.selectRole(role.id); store.assign('pv_001'); } const answer = buildAnswer(store.getState()); assert.deepEqual(answer.defaults, { general: null, male: null, female: null }); assert.equal(answer.assignments.length, 3);
});
test('soft deletion retains record/preview/raw references/current assignment snapshot', async () => {
  const { store, controller } = await setup(); await saveDefaults(store, controller, { female: 'pv_002' }); store.selectRole('MOCK_ROLE_B'); store.assign('pv_002'); const before = store.getState(); controller.requestDelete('pv_002'); assert.equal(store.getState().confirmation.kind, 'delete'); await controller.deleteVoice('pv_002', before.data.revision); const after = store.getState(); assert.equal(after.data.voices.pv_002.deleted, true); assert.deepEqual(after.data.voices.pv_002.preview, before.data.voices.pv_002.preview); assert.deepEqual(after.roles, before.roles); assert.equal(defaultVoice(after.data, 'female'), null); assert.equal(resolveRole(after, after.roles[1]).via, 'explicit');
});
test('undo restores unchanged default reference but never overwrites a newly saved default', async () => {
  const { store, controller } = await setup(); await saveDefaults(store, controller, { general: 'pv_001' }); await controller.deleteVoice('pv_001', store.getState().data.revision); await saveDefaults(store, controller, { general: 'pv_002' }); await controller.restoreVoice('pv_001', '项目旁白'); assert.equal(store.getState().data.defaults.general, 'pv_002');
});
test('undo name conflict requires a new name and keeps both stable identities', async () => {
  const { store, controller } = await setup(); await controller.deleteVoice('pv_001', 0); fill(store, '项目旁白', 'NEW_SOURCE', 'male'); await controller.addVoice(); controller.undoDelete(); assert.equal(store.getState().confirmation.kind, 'restore-name'); await controller.restoreVoice('pv_001', '恢复的旁白'); assert.equal(store.getState().data.voices.pv_001.name, '恢复的旁白'); assert.equal(activeVoices(store.getState().data).filter(v => v.name === '项目旁白').length, 1);
});
test('preview saving retains old sample until success; late old-parameter results never replace it', async () => {
  const { api, providers } = await setup(), data = await api.load(), voice = data.voices.pv_002;
  const pending = api.updatePreview({ id: voice.id, expectedSignature: signature(voice), expectedRevision: data.revision });
  const draft = { name: voice.name, category: voice.category, speed: 1.4, pitch: 0 };
  await api.saveVoice({ id: voice.id, draft, expectedSource: voice.source, expectedRevision: data.revision }); await assert.rejects(pending, /参数|revision/); const latest = await api.load(); assert.deepEqual(latest.voices.pv_002.preview, voice.preview); assert.equal(previewStatus(latest.voices.pv_002).kind, 'stale');
});
test('update preview failure preserves old data; new matching sample clears stale', async () => {
  const { store, controller, api } = await setup(); controller.openSettings('pv_002'); store.editSetting('pitch', 2); await controller.saveSettings(); const old = store.getState().data.voices.pv_002.preview; api.configureMock({ failSave: true }); await controller.updatePreview('pv_002'); assert.deepEqual(store.getState().data.voices.pv_002.preview, old); await controller.updatePreview('pv_002'); assert.equal(previewStatus(store.getState().data.voices.pv_002).kind, 'valid');
});
test('Mock answer is immutable/deduplicated and does not save project defaults or resume real Harness', async () => {
  const { store, api, controller, log } = await setup(); for (const role of store.getState().roles) { store.selectRole(role.id); store.assign('pv_001'); } const answer = buildAnswer(store.getState()), [a, b] = await Promise.all([api.submitAnswer(answer), api.submitAnswer(answer)]); assert.deepEqual(a, b); assert.equal(a.mock, true); assert.equal(a.can_generate, false); assert.equal(log.getEntries().filter(e => e.name === 'answer.mock.submitted').length, 1); assert.deepEqual((await api.load()).defaults, { general: null, male: null, female: null });
  api.configureMock({ management: true }); await controller.load(); assert.throws(() => buildAnswer(store.getState()), /Question/);
});
test('revision/failure preserve settings draft for retry', async () => {
  const { store, api, controller } = await setup(); controller.openSettings('pv_001'); store.editSetting('name', '保留草稿'); api.configureMock({ conflict: true }); await controller.saveSettings(); assert.equal(store.getState().needsRefresh, true); assert.equal(store.getState().editor.draft.name, '保留草稿'); await controller.load(); await controller.saveSettings(); assert.equal(store.getState().data.voices.pv_001.name, '保留草稿');
});
test('local Mock wave fixtures have actual 6/7-second durations and are labeled synthetic', () => {
  for (const [name, seconds] of [['a', 6], ['b', 7]]) { const bytes = readFileSync(new URL(`../assets/mock-preview-${name}.wav`, import.meta.url)); assert.equal(bytes.toString('ascii', 0, 4), 'RIFF'); assert.equal(bytes.readUInt32LE(40) / bytes.readUInt32LE(28), seconds); }
});
