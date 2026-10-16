import { normalizeLocale, resolveLocale, setLocale, getLocale, t } from './i18n.js';

const preferenceKey = 'castvox.ui-language';
export function readPreference(storage) {
  try { const value = storage.getItem(preferenceKey); return normalizeLocale(value) ?? 'auto'; } catch { return 'auto'; }
}
export function savePreference(storage, value) {
  try { storage.setItem(preferenceKey, normalizeLocale(value) ?? 'auto'); } catch { /* A blocked browser store must not prevent switching. */ }
}
function browserStorage() { try { return localStorage; } catch { return null; } }
export function initialLocale(host) {
  const choice = readPreference(browserStorage());
  const resolved = resolveLocale({ manual: choice, host });
  setLocale(resolved.language); return { choice, ...resolved };
}
export function translatePageChrome() {
  document.documentElement.lang = getLocale();
  for (const node of document.querySelectorAll('[data-i18n]')) node.textContent = t(node.dataset.i18n);
  for (const node of document.querySelectorAll('[data-i18n-aria]')) node.setAttribute('aria-label', t(node.dataset.i18nAria));
}
export function mountLocaleControl(store, initial, host, redraw) {
  const control = document.querySelector('#ui-language');
  const buttons = [...control.querySelectorAll('button[data-language]')];
  let selected = initial;
  const render = state => {
    for (const button of buttons) {
      button.disabled = state.busy || !!state.configOpening || !!state.confirmation;
      button.setAttribute('aria-pressed', String(button.dataset.language === selected.language));
    }
    control.setAttribute('aria-label', t('界面语言'));
    control.title = t({ manual: '手动选择语言', harness: '使用启动时语言', fallback: '使用中文默认语言' }[selected.source]);
  };
  const apply = choice => {
    const state = store.getState(); if (state.busy || state.configOpening || state.confirmation) return;
    const next = resolveLocale({ manual: choice, host });
    selected = { choice, ...next }; savePreference(browserStorage(), choice);
    setLocale(next.language); translatePageChrome(); redraw(); render(store.getState());
  };
  for (const button of buttons) button.onclick = () => { apply(button.dataset.language); button.focus(); };
  render(store.getState()); const unsubscribe = store.subscribe(render);
  return () => { unsubscribe(); for (const button of buttons) button.onclick = null; };
}
