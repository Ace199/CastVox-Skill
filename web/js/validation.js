import { t, msg, term } from './i18n.js';
// Mirrors the relevant M1 shape/ranges; this does not alter the Python schema.
export const clone = value => structuredClone(value);
export const stableJson = value => JSON.stringify(value, (_key, item) => item && typeof item === 'object' && !Array.isArray(item) ? Object.fromEntries(Object.keys(item).sort().map(key => [key, item[key]])) : item);
export const same = (a, b) => stableJson(a) === stableJson(b);
export function text(value, max = 256) {
  if (typeof value !== 'string' || !value || value !== value.trim() || value.length > max || /[\x00-\x1f]/.test(value)) throw new Error(msg`请填写有效内容（无首尾空格，1–${max} 字）`);
  if (/bearer\s+\S+|\bsk-[a-z0-9_-]{12,}/i.test(value)) throw new Error(t("请勿粘贴 API 凭据；这里只接收音色名称与 Voice ID"));
  return value;
}
export const normalizeName = value => text(value, 120).normalize('NFC');
export function validateVoice(voice) {
  if (!voice || typeof voice !== 'object' || Array.isArray(voice) || Object.keys(voice).some(key => !['ref', 'voice_settings', 'metadata', 'model'].includes(key))) throw new Error(t("不支持的声音字段"));
  const ref = voice?.ref;
  if (!ref || Object.keys(ref).some(key => !['kind', 'provider', 'region', 'voice_id'].includes(key))) throw new Error(t("不支持的声音引用字段"));
  if (ref?.kind !== 'provider_voice' || !['minimax', 'volcengine'].includes(ref.provider) || !['cn', 'international', 'configured'].includes(ref.region)) throw new Error(t("无效的声音引用"));
  text(ref.voice_id);
  if (ref.provider === 'minimax' && !/^[A-Za-z0-9][A-Za-z0-9_-]{0,255}$/.test(ref.voice_id)) throw new Error(t("Voice ID 仅允许字母、数字、下划线和连字符，最长 256 字符"));
  const params = voice.voice_settings ?? {};
  if (typeof params !== 'object' || Array.isArray(params)) throw new Error(t("声音参数必须为对象"));
  if (Object.keys(params).some(key => !['speed', 'volume', 'emotion', 'pitch'].includes(key))) throw new Error(t("不支持的声音参数"));
  for (const [key, min, max] of [['speed', .5, 2], ['volume', Number.MIN_VALUE, 10], ['pitch', -12, 12]]) if (key in params && (typeof params[key] !== 'number' || !Number.isFinite(params[key]) || params[key] < min || params[key] > max)) throw new Error(msg`${key === 'speed' ? term("语速") : term("音量")}超出允许范围`);
  if (params.emotion !== undefined) text(params.emotion, 32);
  if (voice.model !== undefined) text(voice.model, 128);
  const metadata = voice.metadata ?? {};
  if (metadata.gender !== undefined && !['male', 'female', 'other', 'unknown'].includes(metadata.gender)) throw new Error(t("请选择声音分类"));
  if (metadata.source !== undefined) text(metadata.source, 2000);
  if (metadata.gender && metadata.gender !== 'unknown' && !metadata.source) throw new Error(t("分类需要明确来源"));
  return clone({ ref, voice_settings: params, ...(voice.model !== undefined ? { model: voice.model } : {}), ...(voice.metadata ? { metadata } : {}) });
}
export function draftVoice(draft, region) {
  if (!['male', 'female', 'other'].includes(draft.category)) throw new Error(t("请明确选择声音分类：男声 / 女声 / 其他"));
  text(draft.model, 128);
  return validateVoice({ ref: { kind: 'provider_voice', provider: draft.provider, region, voice_id: draft.voiceId }, model: draft.model, metadata: { gender: draft.category, source: 'user_selected' }, voice_settings: draft.preservedSettings ?? {} });
}
export const emptyDraft = (provider = 'minimax', model = '') => ({ name: '', voiceId: '', provider, model, category: '', preservedSettings: {} });
export function voiceDraft(name, voice) {
  return { name, voiceId: voice.ref.voice_id, provider: voice.ref.provider, model: voice.model ?? '', category: voice.metadata?.gender === 'unknown' ? 'other' : voice.metadata?.gender ?? '', preservedSettings: clone(voice.voice_settings ?? {}) };
}
export function toM1Voice(record) {
  if (record.ref.provider !== 'minimax') throw new Error(t("此厂商尚不能写入 M1 Schema"));
  const { model, ...voice } = validateVoice(record); return voice;
}
