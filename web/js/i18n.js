import coreEnglish from './locales/en.js';
import extraEnglish from './locales/en-extra.js';
const english = { ...coreEnglish, ...extraEnglish };

let language = 'zh-CN';
const renderedMessages = new Map();
export function normalizeLocale(value) {
  if (typeof value !== 'string') return null;
  const tag = value.trim().replaceAll('_', '-').toLowerCase();
  if (!/^(zh|en)(?:-[a-z0-9]{1,8})*$/.test(tag)) return null;
  const base = tag.split('-')[0];
  return base === 'zh' ? 'zh-CN' : base === 'en' ? 'en' : null;
}
export function resolveLocale({ manual, host } = {}) {
  const selected = normalizeLocale(manual);
  if (selected) return { language: selected, source: 'manual' };
  const inherited = normalizeLocale(host);
  if (inherited) return { language: inherited, source: 'harness' };
  return { language: 'zh-CN', source: 'fallback' };
}
export const getLocale = () => language;
export function setLocale(value) { language = normalizeLocale(value) ?? 'zh-CN'; }
export function t(source, ...values) {
  const pattern = language === 'en' ? english[source] ?? source : source;
  // Replacement callbacks preserve dollar signs/braces and never evaluate user text.
  const result = pattern.replace(/\{(\d+)\}/g, (match, index) => index < values.length ? String(values[index]) : match);
  if (Object.hasOwn(english, source)) {
    if (renderedMessages.size >= 1000) renderedMessages.delete(renderedMessages.keys().next().value);
    renderedMessages.set(result, { source, values });
  }
  return result;
}
// Explicitly mark system labels inside messages that can outlive a language switch.
// User-owned interpolation values remain plain strings and are never translated.
export const term = source => Object.freeze({ toString: () => t(source) });
export function msg(parts, ...values) {
  return t(parts.reduce((key, part, index) => key + (index ? `{${index - 1}}` : '') + part, ''), ...values);
}
// Use only for application status/error/metadata, never project names or user content.
export function translateMessage(value) {
  const remembered = renderedMessages.get(value);
  return remembered ? t(remembered.source, ...remembered.values) : typeof value === 'string' ? t(value) : value;
}
export const escapeHtml = value => String(value).replace(/[&<>"']/g, char => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' })[char]);
