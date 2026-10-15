import test from 'node:test';
import assert from 'node:assert/strict';
import { spawnSync } from 'node:child_process';
import { createMockApi } from '../js/api.js';
import { createStore, buildAnswer } from '../js/store.js';
import { createController } from '../js/controller.js';
import { createEventLog } from '../js/events.js';
import { validateVoice, draftVoice, emptyDraft, toM1Voice } from '../js/validation.js';
import { readFileSync } from 'node:fs';
const fixture = provider => JSON.parse(readFileSync(new URL(`./fixtures/providers/${provider}/config.json`,import.meta.url)));
const providers = ['minimax','volcengine'].map(id => ({ id, ...fixture(id) }));
const model = id => providers.find(p => p.id === id).models[0].id;
const voice = (id,provider='minimax',category='other') => ({ ref:{kind:'provider_voice',provider,region:'configured',voice_id:id}, model:model(provider), metadata:{gender:category,source:'user_selected'}, voice_settings:{} });
async function setup() { const log=createEventLog(), api=createMockApi(log,providers), store=createStore(); const draft=emptyDraft('minimax',model('minimax')); store.update({providers,draft,baseline:structuredClone(draft)}); const controller=createController(store,api,log); await controller.load(); return {log,api,store,controller}; }
function fill(store,name='新声音',id='USER_ID',category='other') { store.edit('name',name);store.edit('voiceId',id);store.edit('category',category); }
test('identity/model do not imply performance parameters; classification is explicit',()=>{
  assert.throws(()=>draftVoice({...emptyDraft(),voiceId:'A',model:model('minimax')},'configured'),/分类/);
  assert.deepEqual(draftVoice({...emptyDraft(),voiceId:'A',model:model('minimax'),category:'male'},'configured'),voice('A','minimax','male'));
});
test('invalid IDs and incompatible M1 projections rejected',()=>{
  for(const id of ['',' abc','中文','a/b']) assert.throws(()=>validateVoice(voice(id)));
  assert.throws(()=>toM1Voice(voice('speaker_A','volcengine')),/M1/);
  assert.throws(()=>validateVoice({...voice('A'),performance_mode:'agent_auto'}));
});
test('add saves category and fixed model without updating project default',async()=>{
  const {store,controller}=await setup();fill(store,'女声示例','A','female');await controller.saveAlias();const s=store.getState();assert.equal(s.data.named_voices['女声示例'].metadata.gender,'female');assert.equal(s.data.named_voices['女声示例'].model,model('minimax'));assert.equal(s.data.default_voice,null);
});
test('rebind requires old ref and revision confirmation',async()=>{
  const {api}=await setup();const data=await api.load(),next=voice('NEW');await assert.rejects(api.saveAlias({name:'项目旁白',voice:next,expectedRevision:data.revision}),/确认/);
  const saved=await api.saveAlias({name:'项目旁白',voice:next,expectedRevision:0,confirmation:{name:'项目旁白',revision:0,old_ref:data.named_voices['项目旁白'].ref,new_voice:next}});assert.equal(saved.named_voices['项目旁白'].ref.voice_id,'NEW');
});
test('rename preserves uniqueness and old task snapshots',async()=>{
  const {store,controller}=await setup();store.selectRole('MOCK_ROLE_A');store.assign('项目旁白');const snapshot=store.getState().roles[0].binding;
  store.edit('name','对白音色');await controller.saveAlias();assert.match(store.getState().error,/已存在/);
  store.edit('name','新旁白');store.edit('voiceId','NEW');await controller.saveAlias();await controller.saveAlias(true);const s=store.getState();assert.equal(Object.hasOwn(s.data.named_voices,'项目旁白'),false);assert.equal(s.data.named_voices['新旁白'].ref.voice_id,'NEW');assert.deepEqual(s.roles[0].binding,snapshot);
});
test('provider switching isolates IDs/models and preserves recoverable drafts',async()=>{
  const {store}=await setup();fill(store,'未保存','MINIMAX_ID','male');store.switchProvider('volcengine');const s=store.getState();assert.equal(s.draft.voiceId,'');assert.equal(s.draft.model,model('volcengine'));assert.equal(s.draft.name,'未保存');assert.equal(s.providerDrafts.minimax.voiceId,'MINIMAX_ID');assert.equal(s.data.default_voice,null);
});
test('wrong provider model refused; mixed providers coexist only in Mock',async()=>{
  const {api}=await setup();await assert.rejects(api.saveAlias({name:'错配',voice:{...voice('A','volcengine'),model:model('minimax')},expectedRevision:0}),/模型/);
  const s=await api.saveAlias({name:'火山声',voice:voice('speaker_A','volcengine'),expectedRevision:0});assert.equal(s.named_voices['火山声'].ref.provider,'volcengine');assert.equal(s.named_voices['项目旁白'].ref.provider,'minimax');assert.equal(s.studio_schema_version,'1.5-mock');
});
test('saved models independent of config defaults; missing model lists not inferred',async()=>{
  const defs=structuredClone(providers),api=createMockApi(undefined,defs);const before=await api.load();defs[0].default_model=defs[0].models[1].id;const after=await api.load();assert.equal(after.named_voices['项目旁白'].model,before.named_voices['项目旁白'].model);
  const empty=createMockApi(undefined,[]);assert.deepEqual((await empty.load()).named_voices,{});await assert.rejects(empty.saveAlias({name:'A',voice:voice('A'),expectedRevision:0}),/模型/);
});
test('default requires confirmation and no alias, keeps role edit context',async()=>{
  const {api,store,controller}=await setup();const before=await api.load();await assert.rejects(api.saveDefault({voice:voice('D'),expectedRevision:0}),/确认/);
  store.selectRole('MOCK_ROLE_A');const draft=store.getState().draft;await controller.prepareDefaultFromAlias('对白音色');await controller.confirmDefault();assert.deepEqual(store.getState().draft,draft);assert.equal(store.getState().roles[0].binding,null);
  const saved=await api.saveDefault({voice:voice('V','volcengine'),expectedRevision:1,confirmed:true});assert.deepEqual(saved.named_voices,before.named_voices);assert.equal(saved.default_voice.ref.provider,'volcengine');
});
test('tabs preserve unsaved fields',async()=>{const {store}=await setup();fill(store);const before=store.getState().draft;store.update({activeTab:'tools'});store.update({activeTab:'add'});assert.deepEqual(store.getState().draft,before);});
test('role assignments keep independent avatars and model snapshots',async()=>{
  const {store}=await setup();store.selectRole('MOCK_ROLE_A');store.assign('项目旁白');const first=store.getState().roles[0];store.selectRole('MOCK_ROLE_B');store.assign('对白音色');store.selectRole('MOCK_ROLE_A');assert.deepEqual(store.getState().roles[0],first);assert.equal(store.getState().data.default_voice,null);
});
test('conflict/failure retain input; repeated clicks do not double-save',async()=>{
  const {api,store,controller,log}=await setup();fill(store);api.configureMock({failSave:true});await controller.saveAlias();assert.match(store.getState().error,/失败/);api.configureMock({conflict:true});await controller.saveAlias();assert.equal(store.getState().needsRefresh,true);await controller.load();await Promise.all([controller.saveAlias(),controller.saveAlias()]);assert.equal(store.getState().data.named_voices['新声音'].ref.voice_id,'USER_ID');assert.equal(log.getEntries().filter(e=>e.name==='alias.saved').length,1);
});
test('completion deduplicates Question/Answer Mock and never saves defaults',async()=>{
  const {api,store}=await setup();assert.throws(()=>buildAnswer(store.getState()));for(const role of store.getState().roles){store.selectRole(role.id);store.assign('项目旁白');}
  const answer=buildAnswer(store.getState()),[a,b]=await Promise.all([api.submitAnswer(answer),api.submitAnswer(answer)]);assert.deepEqual(a,b);assert.equal(a.answer.job_id,'MOCK_JOB_A');assert.ok(a.answer.answer_id);assert.equal((await api.load()).default_voice,null);assert.equal(a.protocol_status,'mock_adapter_not_m1_wire_protocol');
  await assert.rejects(api.submitAnswer({...answer,question_id:'wrong'}),/不匹配/);
});
test('management mode never claims Harness continuation',async()=>{const {api,store,controller}=await setup();api.configureMock({management:true});await controller.load();assert.throws(()=>buildAnswer(store.getState()),/管理模式/);});
test('prototype alias is an ordinary entry',async()=>{const {store,controller}=await setup();fill(store,'__proto__');await controller.saveAlias();assert.equal(store.getState().data.named_voices.__proto__.ref.voice_id,'USER_ID');});
test('MiniMax model/category adapter passes actual M1 validators unchanged',()=>{
  const record=voice('A','minimax','female');const result=spawnSync('python',['-c','import json,sys;from makesound.validation import voice,project_settings;x=json.load(sys.stdin);voice(x["voice"]);project_settings(x["settings"]);print("PASS")'],{cwd:new URL('../../',import.meta.url),input:JSON.stringify({voice:toM1Voice(record),settings:{model:record.model}}),encoding:'utf8',windowsHide:true,env:{...process.env,PYTHONDONTWRITEBYTECODE:'1'}});assert.equal(result.status,0,result.stderr);assert.match(result.stdout,/PASS/);
});
