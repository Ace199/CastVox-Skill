export const capabilities = {
  MOCK_STUDIO_FULL: { name: 'Mock 完整模型', emotions: ['auto', 'happy', 'sad', 'angry'] },
  MOCK_STUDIO_LIGHT: { name: 'Mock 轻量模型', emotions: ['auto', 'happy'] }
};
export const emotions = { auto: '自动', happy: '开心', sad: '悲伤', angry: '愤怒' };
export const sampleSentence = '清晨的第一束阳光穿过窗边的树叶，主角终于翻开那封等待已久的来信，并决定带着伙伴一起寻找故事背后的答案。';
export function findEditorVoice(state, key) {
  const split = key?.indexOf(':') ?? -1;
  if (split < 0) return null;
  const kind = key.slice(0, split), id = key.slice(split + 1);
  return (kind === 'project' ? state.data?.voices : kind === 'pool' ? state.catalog.voices : [])?.find(voice => voice.id === id) ?? null;
}
export function editorSignature(draft) {
  return JSON.stringify({ voice: draft.resolvedVoiceKey ?? draft.voiceKey, ...Object.fromEntries(['model', 'emotion', 'speed', 'volume', 'latex', 'normalize', 'text'].map(key => [key, draft[key]])) });
}
export function hasCurrentPreview(state, draft) {
  return !!draft && !previewBlocker(state, draft) && draft.preview.status === 'ready' && !!draft.preview.url && draft.preview.signature === editorSignature(draft);
}
export function previewBlocker(state, draft) {
  if (!draft || !findEditorVoice(state, draft.voiceKey)) return '请选择声音';
  if (findEditorVoice(state, draft.voiceKey).availability === 'unavailable') return '当前音色不可用，仅可查看和编辑草稿';
  if (!capabilities[draft.model]?.emotions.includes(draft.emotion)) return '当前模型不支持已选情绪，请主动选择兼容情绪';
  if (!draft.text.trim()) return '请填写试听文本';
  return '';
}
export function defaultSaveBlocker(state) {
  const draft = state.editor.drafts[`default:${state.data?.project.id}`];
  if (state.ui.target?.kind === 'default' && state.editor.activeKey && !state.editor.activeKey.startsWith('default:')) return '请使用试听区的默认保存确认，避免保存其他草稿';
  if (draft?.voiceKey?.startsWith('pool:') && !hasCurrentPreview(state, draft)) return '请先获取当前参数对应的模拟试听';
  if (draft && !capabilities[draft.model]?.emotions.includes(draft.emotion)) return '请先处理默认声音的模型情绪兼容性';
  return '';
}
export function activateEditor(state, action) {
  let key, title, voiceKey = null, parameters = {}, studio = {};
  const roleId = state.ui.target?.kind === 'role' && state.task.jobId ? state.ui.target.roleId : null;
  const role = state.data?.roles?.find(item => item.id === roleId);
  const selection = role && state.task.selections[roleId];
  const roleKey = role && `role:${state.task.jobId}:${roleId}`;
  const roleDraft = state.editor.drafts[roleKey];
  const belongsToRole = role && (state.editor.activeKey === roleKey || state.editor.activeKey?.endsWith(`@${state.task.jobId}:${roleId}`));
  const roleSeed = belongsToRole ? state.editor.drafts[state.editor.activeKey] : roleDraft;
  if (action.type === 'OPEN_VOICE_SETTINGS') {
    key = `project:${action.voiceId}`; title = '项目音色草稿'; voiceKey = key;
    parameters = state.data.voices.find(voice => voice.id === action.voiceId)?.parameters ?? {};
    studio = state.data.voices.find(voice => voice.id === action.voiceId)?.studioSettings ?? {};
  } else if (action.type === 'OPEN_POOL_SETTINGS') {
    key = `pool:${action.voiceId}`; title = '声音池候选草稿'; voiceKey = key;
  } else if (action.type === 'SELECT_ROLE' || (action.type === 'ASSIGN_TARGET_VOICE' && state.ui.target.kind === 'role')) {
    const id = state.ui.target.roleId;
    const selection = state.task.selections[id];
    key = `role:${state.task.jobId}:${id}`; title = `角色草稿：${state.data.roles.find(role => role.id === id).name}`;
    voiceKey = selection.voiceKey ?? (selection.voiceId ? `project:${selection.voiceId}` : null); parameters = selection.parameters; studio = selection.studioSettings ?? {};
  } else if (action.type === 'SELECT_DEFAULT' || action.type === 'DISCARD_DEFAULT_DRAFT' || action.type === 'ASSIGN_TARGET_VOICE') {
    key = `default:${state.data.project.id}`; title = '项目默认草稿（需确认保存）';
    voiceKey = state.projectDefault.draft?.voiceKey ?? (state.projectDefault.draft?.voiceId ? `project:${state.projectDefault.draft.voiceId}` : null);
    parameters = state.projectDefault.draft?.parameters ?? {}; studio = state.projectDefault.draft?.studioSettings ?? {};
  } else return state;
  if (role && ['OPEN_VOICE_SETTINGS', 'OPEN_POOL_SETTINGS'].includes(action.type)) {
    key = `${key}@${state.task.jobId}:${roleId}`;
    title = `${role.name} · ${title}`;
    parameters = selection.parameters;
    studio = selection.studioSettings ?? {};
    if (roleSeed) studio = { ...studio, ...Object.fromEntries(['model', 'emotion', 'speed', 'volume', 'latex', 'normalize', 'text'].map(field => [field, roleSeed[field]])) };
  }
  let draft = state.editor.drafts[key];
  if (!draft || action.type === 'DISCARD_DEFAULT_DRAFT') draft = { voiceKey, model: 'MOCK_STUDIO_FULL', emotion: 'auto', speed: 1, volume: 1, latex: false, normalize: true,
    text: role?.previewText ?? state.data?.agent?.previewText ?? sampleSentence, ...parameters, ...studio, title, preview: { status: 'idle', signature: null, url: null, error: '' } };
  else if (action.type === 'ASSIGN_TARGET_VOICE') draft = { ...draft, voiceKey };
  draft = { ...draft, soundName: draft.soundName ?? roleSeed?.soundName ?? selection?.voiceName ?? (selection?.voiceId ? findEditorVoice(state, `project:${selection.voiceId}`)?.name : role?.name) ?? '', resolvedVoiceKey: findEditorVoice(state, draft.voiceKey)?.originVoiceKey ?? draft.voiceKey };
  return { ...state, flow: { ...state.flow, name: draft.soundName }, editor: { activeKey: key, drafts: { ...state.editor.drafts, [key]: draft } } };
}
export function updateEditor(state, action) {
  const key = action.key ?? state.editor.activeKey;
  const draft = state.editor.drafts[key];
  if (!draft) throw new Error('没有可编辑的对象');
  let next;
  if (action.type === 'EDIT_FIELD') {
    const { field, value } = action;
    const valid = field === 'model' ? Object.hasOwn(capabilities, value) : field === 'emotion' ? Object.hasOwn(emotions, value) && capabilities[draft.model].emotions.includes(value)
      : field === 'speed' ? typeof value === 'number' && Number.isFinite(value) && value >= 0.5 && value <= 2
      : field === 'volume' ? typeof value === 'number' && Number.isFinite(value) && value > 0 && value <= 10
      : ['latex', 'normalize'].includes(field) ? typeof value === 'boolean'
      : field === 'text' ? typeof value === 'string' && value.length <= 2000
      : field === 'voiceKey' ? !!findEditorVoice(state, value) : false;
    if (!valid) throw new Error('无效或不兼容的编辑值');
    next = { ...draft, [field]: value, ...(field === 'voiceKey' ? { resolvedVoiceKey: findEditorVoice(state, value).originVoiceKey ?? value } : {}) };
  } else if (action.type === 'EDITOR_PREVIEW_START') next = { ...draft, preview: { ...draft.preview, status: 'loading', error: '', pendingSignature: action.signature } };
  else {
    if (draft.preview.pendingSignature !== action.signature) return state;
    next = { ...draft, preview: action.type === 'EDITOR_PREVIEW_SUCCESS' ? { status: 'ready', signature: action.signature, url: action.result.url, duration: action.result.duration, cacheHit: action.result.cacheHit ?? false, error: '' }
      : { ...draft.preview, status: 'error', error: action.error } };
  }
  const defaultKey = `default:${state.data?.project.id}`;
  return { ...state, editor: { ...state.editor, drafts: { ...state.editor.drafts, [key]: next } },
    ...(action.type === 'EDIT_FIELD' && key === defaultKey && findEditorVoice(state, next.voiceKey) ? {
      projectDefault: { ...state.projectDefault, draft: { voiceId: findEditorVoice(state, next.voiceKey).id, voiceKey: next.voiceKey, voiceName: findEditorVoice(state, next.voiceKey).name, parameters: { speed: next.speed, volume: next.volume, emotion: next.emotion },
        studioSettings: { model: next.model, latex: next.latex, normalize: next.normalize, text: next.text } }, confirmation: null }
    } : {}) };
}
