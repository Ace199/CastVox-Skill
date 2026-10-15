import { hasCurrentPreview, editorSignature, findEditorVoice } from './editor.js';
import { voiceGender } from './voice-presentation.js';

export function normalizeSoundName(value) {
  if (typeof value !== 'string' || !value || value !== value.trim() || value.length > 120 || /[\x00-\x1f]/.test(value)) throw new Error('请输入音色名称（无首尾空格，1–120 字）');
  return value.normalize('NFC');
}

export function roleTarget(state) {
  const id = state.ui.target?.kind === 'role' ? state.ui.target.roleId : null;
  return id && state.task.jobId && Object.hasOwn(state.task.selections, id) ? { roleId: id, jobId: state.task.jobId } : null;
}
export function voiceSelection(state, draft) {
  const voice = findEditorVoice(state, draft.voiceKey);
  if (!voice) throw new Error('声音对象不可用');
  return { voiceId: voice.id, voiceKey: draft.voiceKey, voiceRef: draft.resolvedVoiceKey ?? draft.voiceKey, voiceName: voice.name, voiceGender: voiceGender(voice),
    avatar: state.ui.target?.kind === 'role' ? state.task.avatars?.[state.ui.target.roleId] : voice.avatar,
    parameters: { speed: draft.speed, volume: draft.volume, emotion: draft.emotion }, studioSettings: { model: draft.model, latex: draft.latex, normalize: draft.normalize, text: draft.text } };
}
export function reduceFlow(state, action) {
  if (action.type === 'FLOW_NAME') return { ...state, flow: { ...state.flow, name: action.value, confirmation: null, error: '' } };
  if (action.type === 'FLOW_STATUS') return { ...state, flow: { ...state.flow, ...action.patch } };
  if (action.type === 'FLOW_APPLY_ROLE') {
    if (!hasCurrentPreview(state, action.draft) || !action.target || action.target.jobId !== state.task.jobId || !Object.hasOwn(state.task.selections, action.target.roleId)) throw new Error('没有当前参数试听或有效任务角色');
    const selection = { ...voiceSelection(state, action.draft), voiceName: normalizeSoundName(action.name) };
    const key = `role:${state.task.jobId}:${action.target.roleId}`;
    return { ...state, task: { ...state.task, selections: { ...state.task.selections, [action.target.roleId]: selection } },
      editor: { ...state.editor, drafts: { ...state.editor.drafts, [key]: { ...structuredClone(action.draft), soundName: selection.voiceName } } } };
  }
  if (action.type === 'FLOW_PREPARE_DEFAULT') {
    if (state.ui.target?.kind !== 'default' || !hasCurrentPreview(state, action.draft)) throw new Error('请先选择默认目标并获取当前参数试听');
    const key = `default:${state.data.project.id}`;
    return { ...state, projectDefault: { ...state.projectDefault, draft: voiceSelection(state, action.draft), confirmation: null },
      editor: { activeKey: key, drafts: { ...state.editor.drafts, [key]: { ...structuredClone(action.draft), title: '项目默认草稿（需确认保存）' } } } };
  }
  if (action.type === 'LIBRARY_SYNC' || action.type === 'FLOW_LIBRARY_COMMIT') {
    if (state.data.project.id !== action.result.projectId) throw new Error('项目上下文已变化');
    const selections = Object.fromEntries(Object.entries(state.task.selections).map(([id, selection]) => [id, selection.voiceId && !selection.voiceRef ? { ...selection, voiceRef: state.data.voices.find(voice => voice.id === selection.voiceId)?.originVoiceKey ?? `project:${selection.voiceId}`, voiceName: state.data.voices.find(voice => voice.id === selection.voiceId)?.name } : selection]));
    if (action.type === 'FLOW_LIBRARY_COMMIT' && action.target?.jobId === state.task.jobId && Object.hasOwn(selections, action.target.roleId)) selections[action.target.roleId] = {
      ...action.selection, voiceId: action.result.voice.id, voiceName: action.result.voice.name, voiceKey: `project:${action.result.voice.id}`
    };
    const drafts = Object.fromEntries(Object.entries(state.editor.drafts).map(([key, draft]) => [key, draft.voiceKey?.startsWith('project:') ? { ...draft, resolvedVoiceKey: action.result.voices.find(voice => `project:${voice.id}` === draft.voiceKey)?.originVoiceKey ?? draft.resolvedVoiceKey ?? draft.voiceKey } : draft]));
    if (action.type === 'FLOW_LIBRARY_COMMIT' && action.target?.jobId === state.task.jobId && Object.hasOwn(selections, action.target.roleId)) {
      drafts[`role:${state.task.jobId}:${action.target.roleId}`] = { ...structuredClone(action.draft), voiceKey: `project:${action.result.voice.id}`, resolvedVoiceKey: action.result.voice.originVoiceKey ?? `project:${action.result.voice.id}`, soundName: action.result.voice.name };
    }
    return { ...state, libraryRevision: action.result.revision, data: { ...state.data, voices: structuredClone(action.result.voices) }, task: { ...state.task, selections }, editor: { ...state.editor, drafts } };
  }
  if (action.type === 'FLOW_SUMMARY') {
    const rows = (state.data.roles ?? []).filter(role => state.task.jobId).map(role => ({ name: role.name, ...structuredClone(state.task.selections[role.id]) }));
    return { ...state, flow: { ...state.flow, summary: rows } };
  }
  return state;
}

export function createAssignmentFlow(store, api, log) {
  let pending = false, sequence = 0;
  const current = () => { const state = store.getState(); return { state, draft: state.editor.drafts[state.editor.activeKey] }; };
  const status = patch => store.dispatch({ type: 'FLOW_STATUS', patch });
  return {
    applyRole() {
      const { state, draft } = current();
      store.dispatch({ type: 'FLOW_APPLY_ROLE', draft, target: roleTarget(state), name: state.flow.name });
      log.record({ name: 'flow.role.applied', objectId: roleTarget(state).roleId, result: '当前试听配置已应用，仅当前任务角色' });
      status({ message: `已加入当前角色池（仅当前任务）· ${normalizeSoundName(state.flow.name)}`, error: '' });
    },
    prepareDefault() {
      const { draft } = current(); store.dispatch({ type: 'FLOW_PREPARE_DEFAULT', draft }); store.dispatch({ type: 'REQUEST_DEFAULT_SAVE' });
    },
    async save(confirm = false) {
      if (pending) return;
      const { state, draft } = current();
      try {
        if (!hasCurrentPreview(state, draft)) throw new Error('请先获取当前参数对应的模拟试听');
        if (state.ui.target?.kind === 'default') throw new Error('默认声音必须通过独立保存确认');
        const name = normalizeSoundName(state.flow.name);
        const target = roleTarget(state);
        const saveKey = JSON.stringify([editorSignature(draft), name.normalize('NFC'), target]);
        if (state.flow.lastSaveKey === saveKey) { status({ message: '此配置已保存，重复点击没有再次写入', error: '' }); return; }
        const existing = state.data.voices.find(voice => voice.name.normalize('NFC') === name.normalize('NFC'));
        const expected = { voiceId: existing?.id, oldRef: existing?.originVoiceKey ?? (existing ? `project:${existing.id}` : null), revision: state.libraryRevision, saveKey };
        if (existing && (!confirm || JSON.stringify(state.flow.confirmation?.expected) !== JSON.stringify(expected))) {
          status({ confirmation: { expected, oldName: existing.name, oldRef: expected.oldRef, newRef: draft.resolvedVoiceKey ?? draft.voiceKey,
            oldParameters: existing.parameters ?? { speed: 1, volume: 1, emotion: 'auto' }, newParameters: { speed: draft.speed, volume: draft.volume, emotion: draft.emotion }, model: draft.model }, error: '' }); return;
        }
        const selection = voiceSelection(state, draft);
        pending = true; status({ status: 'saving', error: '', confirmation: null });
        const result = await api.saveProjectVoice({ name, draft: structuredClone(draft), metadata: { ...structuredClone(findEditorVoice(state, draft.voiceKey)), avatar: selection.avatar }, expectedRevision: state.libraryRevision,
          confirmation: existing ? expected : null, operationId: `MOCK_SAVE_${++sequence}` });
        store.dispatch({ type: 'FLOW_LIBRARY_COMMIT', result, draft, target, selection });
        status({ status: 'ready', lastSaveKey: saveKey, message: target?.jobId === store.getState().task.jobId ? '项目库 Mock 保存成功，并加入点击时选中的角色池' : '项目库 Mock 保存成功；未绑定任何其他角色', error: '' });
      } catch (error) {
        status({ status: 'error', error: error.message, confirmation: null });
        log.record({ name: 'flow.library.failed', objectId: state.data.project.id, result: '保存失败，草稿保留', error });
      } finally { pending = false; }
    },
    async refresh() {
      if (pending) return;
      const result = await api.getProjectLibrary(); store.dispatch({ type: 'LIBRARY_SYNC', result });
      status({ error: '', confirmation: null, status: 'ready', message: '已重新读取 revision，请重新预览并明确确认保存' });
      log.record({ name: 'flow.library.refreshed', objectId: result.projectId, result: `revision=${result.revision}` });
    }
  };
}
