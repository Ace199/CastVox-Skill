import { clone, same, stableJson, normalizeName, text } from './validation.js';
import { controlCapability } from './capabilities.js';

export const categories = ['male', 'female', 'other'];
export const slots = ['general', 'male', 'female'];
export const slotNames = { general: '默认声音', male: '默认男声', female: '默认女声' };
export const activeVoices = data => Object.values(data?.voices ?? {}).filter(voice => !voice.deleted);
export const signature = voice => stableJson({ source: voice.source, effective_settings: voice.settings });
export const voiceSnapshot = voice => clone({ project_voice_id: voice.id, name: voice.name, category: voice.category, source: voice.source, settings: voice.settings });
export function defaultVoice(data, slot, refs = data.defaults) {
  const saved = refs[slot] === data.defaults[slot] && data.default_snapshots?.[slot];
  if (saved) return { ...saved, id: saved.project_voice_id, deleted: false };
  const voice = data.voices[refs[slot]];
  return voice && !voice.deleted && (slot === 'general' || voice.category === slot) ? voice : null;
}
export function defaultDisplayVoice(data, slot, refs = data.defaults) {
  return defaultVoice(data, slot, refs) ?? data.voices[refs[slot]] ?? null;
}
export function normalizedDefaults(data, refs = data.defaults) {
  return Object.fromEntries(slots.map(slot => [slot, defaultVoice(data, slot, refs)?.id ?? null]));
}
export function neutralSettings(source, providers) {
  return Object.fromEntries(['speed', 'pitch'].flatMap(key => {
    const cap = controlCapability(source, providers, key); return cap.enabled ? [[key, cap.neutral]] : [];
  }));
}
export function editDraft(voice, providers) {
  const result = { name: voice.name, category: voice.category };
  for (const key of ['speed', 'pitch']) result[key] = voice.settings[key] ?? (controlCapability(voice.source, providers, key).enabled ? controlCapability(voice.source, providers, key).neutral : '');
  return result;
}
const comparable = draft => draft ? { ...draft, speed: draft.speed === '' ? '' : Number(draft.speed), pitch: draft.pitch === '' ? '' : Number(draft.pitch) } : null;
export const editorDirty = state => !same(comparable(state.editor.draft), comparable(state.editor.baseline));
export function validateName(data, name, exceptId = null) {
  name = normalizeName(name);
  if (activeVoices(data).some(voice => voice.id !== exceptId && normalizeName(voice.name) === name)) throw new Error('项目内已有同名声音；请使用另一个名称，不会覆盖现有声音。');
  return name;
}
export function validateSettings(voice, draft, providers) {
  if (Object.keys(draft).some(key => !['name', 'category', 'speed', 'pitch'].includes(key))) throw new Error('声音来源只读；更换来源请添加新声音。');
  if (!categories.includes(draft.category)) throw new Error('请选择男声、女声或其他分类。');
  const settings = clone(voice.settings), baseline = editDraft(voice, providers);
  for (const key of ['speed', 'pitch']) {
    const cap = controlCapability(voice.source, providers, key);
    const value = draft[key] === '' ? NaN : Number(draft[key]);
    if (!cap.enabled) {
      if (!same(comparable({ ...baseline, [key]: draft[key] })[key], comparable(baseline)[key])) throw new Error(`${key} 能力未验证，不能修改。`);
      continue;
    }
    const steps = cap.step === 'any' ? 0 : (value - cap.min) / cap.step;
    if (!Number.isFinite(value) || value < cap.min || value > cap.max || Math.abs(steps - Math.round(steps)) > 1e-7) throw new Error(`${key === 'speed' ? '语速' : '声调'}必须符合能力描述器的范围和步长。`);
    if (Object.hasOwn(voice.settings, key) || value !== cap.neutral) settings[key] = value;
  }
  return settings;
}
export function previewStatus(voice, player = {}) {
  if (!voice?.preview) return { kind: 'none', playable: false, text: '无试听：首次生成符合条件的配音片段后可试听。' };
  if (voice.preview.available === false || (player.voiceId === voice.id && player.sampleId === voice.preview.sample_id && player.status === 'error')) return { kind: 'unavailable', playable: false, text: '试听文件不可用；不会调用 TTS。' };
  const stale = voice.preview.backend_status ? voice.preview.backend_status === 'before_adjustment' : voice.preview.signature !== signature(voice);
  return { kind: stale ? 'stale' : 'valid', playable: true, text: `${stale ? '调整前试听' : '当前参数试听'}${voice.preview.mock ? ' · 示例音频' : ''}` };
}
export function resolveRole(state, role) {
  if (role.assignment) {
    if (!role.assignment.snapshot?.source?.voice_id) return { error: '明确分配不可用，请重新选择；不会自动回退。' };
    return { project_voice_id: role.assignment.project_voice_id, snapshot: clone(role.assignment.snapshot), via: 'explicit' };
  }
  const gender = ['male', 'female'].includes(role.gender_requirement) ? role.gender_requirement : null;
  const candidate = gender && defaultVoice(state.data, gender);
  const general = defaultVoice(state.data, 'general');
  const voice = candidate || general;
  return voice ? { project_voice_id: voice.id, snapshot: voiceSnapshot(voice), via: candidate ? `default_${gender}` : 'default_general' } : { error: '未分配' };
}
export function buildAnswer(state) {
  if (!state.data?.question?.question_id || !state.data.question.job_id) throw new Error('当前没有有效 Studio Question；可以管理项目，不会通知 Harness。');
  const assignments = state.roles.map(role => ({ role_id: role.id, role_name: role.name, required: role.required !== false, ...resolveRole(state, role) }));
  const missing = assignments.filter(role => role.required && role.error);
  if (missing.length) throw new Error(`请完成必要角色：${missing.map(role => role.role_name).join('、')}`);
  const payload = { mock: state.data.mode !== 'persistent', schema_version: state.data.mode === 'persistent' ? 'studio-answer-v16' : 'studio-answer-ui-mock-v1', project_id: state.data.project.id, ...state.data.question,
    expected_revision: state.data.revision, assignments, defaults: clone(state.data.defaults) };
  let hash = 2166136261; for (const char of stableJson(payload)) hash = Math.imul(hash ^ char.charCodeAt(0), 16777619) >>> 0;
  return { ...payload, answer_id: `MOCK_ANSWER_${hash}` };
}
export function validateNewVoice(draft, providers) {
  const provider = providers.find(item => item.id === draft.provider);
  if (!provider?.models.some(model => model.id === draft.model)) throw new Error('请选择该厂商已配置的模型。');
  text(draft.voiceId);
  if (provider.identifier_pattern && !new RegExp(provider.identifier_pattern).test(draft.voiceId)) throw new Error('音色标识不符合当前厂商的本地格式要求。');
  if (!categories.includes(draft.category)) throw new Error('请明确选择声音分类。');
  const source = { provider: draft.provider, region: provider.region ?? 'configured', model: draft.model, voice_id: draft.voiceId };
  const settings = neutralSettings(source, providers);
  const parameters = { name: draft.name, category: draft.category,
    speed: draft.speed ?? settings.speed ?? '', pitch: draft.pitch ?? settings.pitch ?? '' };
  return { source, category: draft.category, settings: validateSettings({ source, settings }, parameters, providers) };
}

export function validateNewVoiceFields(draft, providers, data = null) {
  const errors = {}, provider = providers.find(item => item.id === draft.provider);
  if (!provider) errors.provider = '请选择声音厂商。';
  if (!provider?.models.some(model => model.id === draft.model)) errors.model = '请选择该厂商已配置的模型。';
  try { validateName({ voices: {} }, draft.name); } catch (error) { errors.name = draft.name ? error.message : '请填写项目声音名称。'; }
  if (!errors.name && data) { try { validateName(data, draft.name); } catch (error) { errors.name = error.message; } }
  try { text(draft.voiceId); } catch (error) { errors.voiceId = draft.voiceId ? error.message : '请填写音色标识。'; }
  if (!errors.voiceId && provider?.identifier_pattern && !new RegExp(provider.identifier_pattern).test(draft.voiceId)) errors.voiceId = '音色标识不符合当前厂商的本地格式要求。';
  if (!categories.includes(draft.category)) errors.category = '请明确选择声音分类。';
  if (!errors.model) {
    const source = { provider: draft.provider, region: provider.region ?? 'configured', model: draft.model, voice_id: draft.voiceId }, settings = neutralSettings(source, providers);
    for (const key of ['speed', 'pitch']) {
      const cap = controlCapability(source, providers, key);
      if (!cap.enabled) continue;
      const value = draft[key] ?? settings[key] ?? cap.neutral, number = value === '' ? NaN : Number(value), steps = cap.step === 'any' ? 0 : (number - cap.min) / cap.step;
      if (!Number.isFinite(number) || number < cap.min || number > cap.max || Math.abs(steps - Math.round(steps)) > 1e-7) errors[key] = `${key === 'speed' ? '语速' : '声调'}必须符合能力描述器的范围和步长。`;
    }
  }
  return errors;
}
