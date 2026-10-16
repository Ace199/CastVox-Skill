import { clone, same } from './validation.js';
import { editorDirty, signature, validateNewVoiceFields, validateSettings, defaultVoice, slotNames, buildAnswer } from './voice-model.js';
import { defaultsDirty } from './store.js';
export function createController(store, api, log) {
  const addErrorField = message => /分类/.test(message) ? 'category' : /名称|同名/.test(message) ? 'name' : /模型/.test(message) ? 'model' : /语速/.test(message) ? 'speed' : /声调/.test(message) ? 'pitch' : 'voiceId';
  const fail = error => { const state = store.getState(); store.update({ busy: false, submitting: false, error: error.message, needsRefresh: state.needsRefresh || error.code === 'revision_conflict', confirmation: state.confirmation?.kind === 'restore-name' && error.code !== 'revision_conflict' ? state.confirmation : null }); log.record({ name: 'action.failed', objectId: state.editor.id ?? state.data?.project.id, result: '未完成，草稿保留', error }); };
  const protect = async (run, onFailure) => { if (store.getState().busy) return false; try { return await run(); } catch (error) { fail(error); onFailure?.(error); return false; } };
  const commit = (data, preserveBusy = false) => { const state = store.getState(); store.update({ ...(data.revision >= (state.data?.revision ?? -1) ? { data } : {}), ...(preserveBusy ? {} : { busy: false }), receipt: null, ...(defaultsDirty(state) ? {} : { defaultsDraft: clone(data.defaults) }) }); };
  const requireFresh = state => { if (state.needsRefresh) throw Object.assign(new Error('请先重新读取配置，再次保存。'), { code: 'revision_conflict' }); };
  const apiController = {
    async load() {
      if (store.getState().busy) return; store.update({ busy: true });
      try { const data = await api.load(), state = store.getState(); store.update({ data, roles: api.mode === 'persistent' ? data.roles : state.data ? state.roles : data.roles, defaultsDraft: state.data && defaultsDirty(state) ? state.defaultsDraft : clone(data.defaults), busy: false, status: 'ready', needsRefresh: false, confirmation: null, receipt: null, error: '', message: '' }); }
      catch (error) { fail(error); }
    },
    assign(id) {
      if (api.mode !== 'persistent' || store.getState().activeDefaultSlot) return store.assign(id);
      return protect(async () => { const state = store.getState(); requireFresh(state); if (!state.activeRoleId) return store.assign(id); store.update({ busy: true, error: '' });
        const data = await api.assignRole(state.activeRoleId, id, state.data.revision); commit(data); store.update({ roles: data.roles, message: '角色分配已保存', selectedVoiceId: id }); });
    },
    refreshProviders() { return protect(async () => { store.update({ busy: true }); const providers = await api.loadProviders(); store.update({ providers, busy: false, message: '模型已更新' }); }); },
    addVoice() {
      const state = store.getState(), draftErrors = validateNewVoiceFields(state.draft, state.providers, state.data);
      if (Object.keys(draftErrors).length) {
        const message = Object.values(draftErrors)[0];
        store.update({ draftErrors, draftTouched: { ...state.draftTouched, ...Object.fromEntries(Object.keys(draftErrors).map(field => [field, true])) }, error: message, addError: message });
        return Promise.resolve(false);
      }
      return protect(async () => { const current = store.getState(); requireFresh(current); store.update({ busy: true, error: '' }); const result = await api.addVoice({ draft: current.draft, expectedRevision: current.data.revision }); commit(result.data); store.resetDraft(); store.update({ message: '已添加项目声音', addError: null }); return true; }, error => {
        const latest = store.getState(), field = addErrorField(error.message);
        store.update({ addError: error.message, draftErrors: { ...latest.draftErrors, [field]: error.message }, draftTouched: { ...latest.draftTouched, [field]: true } });
      });
    },
    openSettings(id) {
      const state = store.getState(); if (state.busy) return;
      if (state.editor.id === id) { store.update({ activeTab: 'settings' }); return; }
      if (editorDirty(state)) { store.update({ confirmation: { kind: 'switch-edit', nextId: id }, error: '' }); return; }
      store.openEditor(id); log.record({ name: 'settings.open', objectId: id, result: '声音设置草稿已载入，来源只读' });
    },
    discardAndSwitch() { const nextId = store.getState().confirmation?.nextId; store.update({ confirmation: null }); if (nextId) store.openEditor(nextId); },
    saveAndSwitch() { const id = store.getState().confirmation?.nextId; return apiController.saveSettings(false, id); },
    saveSettings(confirmed = false, nextId = null) { return protect(async () => {
      const state = store.getState(); requireFresh(state); const voice = state.data.voices[state.editor.id]; if (!voice || voice.deleted) throw new Error('请选择活动声音。');
      validateSettings(voice, state.editor.draft, state.providers);
      const affected = ['male', 'female'].filter(slot => state.data.defaults[slot] === voice.id && state.editor.draft.category !== slot);
      const proposal = { id: voice.id, draft: clone(state.editor.draft), nextId };
      if (affected.length && (!confirmed || state.confirmation?.kind !== 'category' || !same(state.confirmation.proposal, proposal))) { store.update({ confirmation: { kind: 'category', proposal, affected }, error: '' }); return false; }
      store.update({ busy: true, confirmation: null, error: '' });
      const data = await api.saveVoice({ id: voice.id, draft: state.editor.draft, expectedSource: state.editor.source, expectedRevision: state.data.revision }); commit(data);
      store.openEditor(nextId ?? voice.id); store.update({ message: '修改已保存' }); return true;
    }); },
    requestDefaults() { const state = store.getState(); if (state.busy || !defaultsDirty(state)) return; store.update({ confirmation: { kind: 'defaults', defaults: clone(state.defaultsDraft), revision: state.data.revision }, error: '' }); },
    confirmDefaults() { return protect(async () => { const state = store.getState(), pending = state.confirmation; requireFresh(state); if (pending?.kind !== 'defaults') return; store.update({ busy: true, confirmation: null, error: '' }); const data = await api.saveDefaults({ defaults: pending.defaults, expectedRevision: pending.revision, confirmed: true }); store.update({ data, defaultsDraft: clone(data.defaults), busy: false, receipt: null, message: '默认设置已保存' }); }); },
    requestDelete(id) { const state = store.getState(), voice = state.data.voices[id]; if (state.busy || !voice || voice.deleted) return;
      const refs = { defaults: Object.keys(slotNames).filter(slot => state.data.defaults[slot] === id), roles: state.roles.filter(role => role.assignment?.project_voice_id === id).map(role => role.name), history: state.data.historical_references?.[id] ?? 0 };
      if (refs.defaults.length || refs.roles.length || refs.history) store.update({ confirmation: { kind: 'delete', id, refs, revision: state.data.revision }, error: '' }); else void apiController.deleteVoice(id, state.data.revision);
    },
    deleteVoice(id, revision) { return protect(async () => { const state = store.getState(); requireFresh(state); const voice = state.data.voices[id]; store.update({ busy: true, confirmation: null, error: '' }); const data = await api.deleteVoice({ id, expectedRevision: revision }); commit(data); const undo = { id, name: voice.name, deadline: Date.now() + 15000 }; store.update({ undo, ...(state.editor.id === id ? { editor: { id: null, draft: null, baseline: null, source: null } } : {}), message: '仅从项目库隐藏，引用和试听保留。可在 15 秒内撤销。' }); const timer = setTimeout(() => { if (store.getState().undo?.deadline === undo.deadline) store.update({ undo: null }); }, 15000); timer.unref?.(); return true; }); },
    undoDelete() { const state = store.getState(), undo = state.undo; if (!undo || state.busy) return; const voice = state.data.voices[undo.id]; const conflict = Object.values(state.data.voices).some(item => !item.deleted && item.name.normalize('NFC') === voice.name.normalize('NFC'));
      if (conflict) store.update({ confirmation: { kind: 'restore-name', id: voice.id, suggested: `${voice.name.slice(0, 110)}（恢复）` }, error: '' }); else void apiController.restoreVoice(voice.id, voice.name);
    },
    restoreVoice(id, name) { return protect(async () => { const state = store.getState(); requireFresh(state); store.update({ busy: true, error: '' }); const data = await api.restoreVoice({ id, name, expectedRevision: state.data.revision }); commit(data); store.update({ undo: null, confirmation: null, message: '声音已恢复；未覆盖删除后手动改选的默认。' }); return true; }); },
    updatePreview(id) {
      const state = store.getState(); if (state.previewSaving[id] || state.busy || !state.data.voices[id] || state.data.voices[id].deleted) return;
      const expectedSignature = signature(state.data.voices[id]); store.update({ previewSaving: { ...state.previewSaving, [id]: true }, error: '' });
      return api.updatePreview({ id, expectedSignature, expectedRevision: state.data.revision }).then(data => { commit(data, true); store.update({ message: '试听已更新' }); }).catch(error => { store.update({ error: error.message }); log.record({ name: 'preview.update.failed', objectId: id, result: '旧样本保留', error }); }).finally(() => store.update({ previewSaving: { ...store.getState().previewSaving, [id]: false } }));
    },
    setPreviewScenario(id, scenario) { return protect(async () => { const state = store.getState(); store.update({ busy: true }); const data = await api.setPreviewScenario({ id, scenario, expectedRevision: state.data.revision }); commit(data); }); },
    submit() { return protect(async () => { const state = store.getState(); if (state.receipt?.session_complete) return; requireFresh(state); if (api.mode === 'persistent' && !state.data.question) { store.update({ busy: true }); const receipt = await api.complete(); store.update({ busy: false, receipt, message: '项目管理已完成；未启动合成' }); return; } const answer = buildAnswer(state); store.update({ busy: true, submitting: true, error: '' }); const receipt = await api.submitAnswer(answer); store.update({ busy: false, submitting: false, receipt, message: receipt.session_complete ? (receipt.wake?.status === 'awaiting_task' ? '绑定已保存，已交回 WorkBuddy 后台任务。请返回原聊天查看后续结果。' : receipt.wake?.status === 'delivered' ? '绑定已保存，WorkBuddy 已确认向原会话投递。请返回聊天查看；若未继续，发送“完成了”。' : receipt.wake?.status === 'queued' ? '绑定已保存，已向原聊天发送完成消息。可以关闭此页面，返回聊天查看演绎单。' : receipt.wake?.status === 'sent_unconfirmed' ? '绑定已保存，通知已写入原会话，但尚未确认 Claude 接收或回复。请返回原聊天查看；若未继续，发送“完成了”。' : '绑定已保存，但未确认自动通知成功。可以关闭此页面，回到原聊天发送“完成了”。') : api.mode === 'persistent' ? '回答已保存，等待 Agent 领取；未启动合成' : '配置已模拟提交' }); }); }
  };
  return apiController;
}
