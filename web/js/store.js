import { clone, same } from './validation.js';
import { editDraft, editorDirty, validateNewVoiceFields, voiceSnapshot } from './voice-model.js';
export { buildAnswer } from './voice-model.js';
export const freshDraft = (provider = 'minimax', model = '') => ({ provider, model, name: '', voiceId: '', category: '', speed: null, pitch: null });
export function createStore() {
  let state = { data: null, providers: [], status: 'idle', busy: false, error: '', message: '', needsRefresh: false, activeTab: 'add',
    draft: freshDraft(), providerDrafts: {}, draftTouched: {}, draftErrors: {}, roles: [], activeRoleId: null, activeDefaultSlot: null, selectedVoiceId: null,
    editor: { id: null, draft: null, baseline: null, source: null }, defaultsDraft: { general: null, male: null, female: null },
    confirmation: null, receipt: null, debugOpen: false, undo: null, previewSaving: {}, player: { voiceId: null, status: 'idle', sampleId: null, error: '' } };
  const listeners = new Set();
  const store = {
    getState: () => clone(state),
    update(patch) { state = { ...state, ...clone(patch) }; for (const listener of listeners) listener(this.getState()); },
    edit(field, value) { if (state.busy) return; const draft = { ...state.draft, ...(field === 'model' && value !== state.draft.model ? { speed: null, pitch: null } : {}), [field]: value }; this.update({ draft, providerDrafts: { ...state.providerDrafts, [draft.provider]: clone(draft) }, draftTouched: { ...state.draftTouched, [field]: true }, draftErrors: validateNewVoiceFields(draft, state.providers, state.data), error: '', message: '', addError: null }); },
    switchProvider(provider) {
      if (state.busy || !state.providers.some(p => p.id === provider)) return;
      const bank = { ...state.providerDrafts, [state.draft.provider]: clone(state.draft) };
      const draft = clone(bank[provider] ?? freshDraft(provider, state.providers.find(p => p.id === provider)?.default_model ?? ''));
      if (!state.providers.find(p => p.id === provider)?.models.some(m => m.id === draft.model)) draft.model = '';
      this.update({ draft, providerDrafts: bank, draftTouched: {}, draftErrors: {}, message: '已切换本厂商独立草稿；其他厂商的模型及 ID 不会串用。', error: '', addError: null });
    },
    resetDraft() { if (state.busy) return; const draft = freshDraft(state.draft.provider, state.providers.find(p => p.id === state.draft.provider)?.default_model ?? ''); this.update({ draft, providerDrafts: { ...state.providerDrafts, [draft.provider]: clone(draft) }, draftTouched: {}, draftErrors: {}, error: '', addError: null }); },
    selectRole(id) { if (state.busy || !state.roles.some(role => role.id === id)) return; this.update({ activeRoleId: id, activeDefaultSlot: null, message: '角色已选中；点击声音卡主体分配，不更改默认。' }); },
    selectDefault(slot) { if (state.busy || !['general', 'male', 'female'].includes(slot)) return; this.update({ activeDefaultSlot: slot, activeRoleId: null, message: '默认目标已选中；点击符合分类的声音，只更新草稿，之后需确认保存。' }); },
    assign(id) {
      if (state.busy) return; const voice = state.data.voices[id];
      if (state.activeDefaultSlot) {
        if (!voice || voice.deleted || state.activeDefaultSlot !== 'general' && voice.category !== state.activeDefaultSlot) { this.update({ error: '此声音不符合当前默认分类。' }); return; }
        this.editDefault(state.activeDefaultSlot, id); this.update({ selectedVoiceId: id, message: '默认草稿已选择；尚未保存，任务分配未改变。' }); return;
      }
      if (!state.activeRoleId) { this.update({ message: '请先选择当前任务角色；没有修改声音分配。' }); return; }
      if (!voice || voice.deleted) { this.update({ error: '已删除声音不可用于新的分配。' }); return; }
      const roles = state.roles.map(role => role.id === state.activeRoleId ? { ...role, assignment: { project_voice_id: id, snapshot: voiceSnapshot(voice) } } : role);
      this.update({ roles, selectedVoiceId: id, receipt: null, message: '✓ 已分配当前任务角色；默认设置未改变。' });
    },
    openEditor(id) {
      const voice = state.data.voices[id]; if (!voice || voice.deleted) return;
      const draft = editDraft(voice, state.providers);
      this.update({ activeTab: 'settings', editor: { id, draft, baseline: clone(draft), source: clone(voice.source) }, error: '' });
    },
    editSetting(key, value) { if (state.busy || !state.editor.id) return; this.update({ editor: { ...state.editor, draft: { ...state.editor.draft, [key]: value } }, error: '' }); },
    cancelEditor() { if (state.busy) return; if (state.editor.id && state.data.voices[state.editor.id] && !state.data.voices[state.editor.id].deleted) this.openEditor(state.editor.id); },
    editDefault(slot, id) { if (state.busy) return; this.update({ defaultsDraft: { ...state.defaultsDraft, [slot]: id || null }, error: '' }); },
    subscribe(listener) { listeners.add(listener); return () => listeners.delete(listener); }
  };
  return store;
}
export const isDirty = editorDirty;
export const defaultsDirty = state => !!state.data && !same(state.defaultsDraft, state.data.defaults);
