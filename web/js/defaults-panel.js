import { t, msg, escapeHtml, translateMessage } from './i18n.js';
import { defaultDisplayVoice, defaultVoice, slotNames, slots } from './voice-model.js';
import { defaultsDirty } from './store.js';
import { openDefaultConfig } from './providers.js';
export function mountDefaults(root, store, controller) {
  root.innerHTML = `<div class="defaults-heading"><div class="defaults-title-row"><h3>${escapeHtml(t("项目默认设置"))}</h3><button id="open-default-config" class="text-button" type="button">${escapeHtml(t("打开默认配置"))}</button></div></div><div class="default-cards" role="group" aria-label="${escapeHtml(t("项目默认声音卡片"))}">${slots.map(slotField).join('')}</div><span id="defaults-status" class="small" role="status"></span>`;
  for (const slot of slots) {
    root.querySelector(`#default-${slot}`).onclick = () => store.selectDefault(slot);
    root.querySelector(`#default-${slot}`).onkeydown = event => { const current = slots.indexOf(slot); let index; if (event.key === 'ArrowRight') index = (current + 1) % 3; else if (event.key === 'ArrowLeft') index = (current + 2) % 3; else if (event.key === 'Home') index = 0; else if (event.key === 'End') index = 2; else return; event.preventDefault(); store.selectDefault(slots[index]); root.querySelector(`#default-${slots[index]}`).focus(); };
    root.querySelector(`#clear-default-${slot}`).onclick = event => { event.stopPropagation(); store.editDefault(slot, null); };
  }
  root.querySelector('#open-default-config').onclick = async () => {
    const button = root.querySelector('#open-default-config'); button.disabled = true;
    try { root.querySelector('#defaults-status').textContent = translateMessage((await openDefaultConfig()).message); }
    catch (error) { root.querySelector('#defaults-status').textContent = translateMessage(error.message); }
    finally { button.disabled = store.getState().busy; }
  };
  const render = state => {
    if (!state.data) return;
    for (const slot of slots) {
      const target = root.querySelector(`#default-${slot}`), candidate = defaultVoice(state.data, slot, state.defaultsDraft), configured = defaultDisplayVoice(state.data, slot, state.defaultsDraft);
      target.closest('.default-card').classList.toggle('has-assignment', !!candidate);
      target.setAttribute('aria-pressed', String(state.activeDefaultSlot === slot)); target.disabled = state.busy;
      root.querySelector(`#default-${slot}-name`).textContent = configured?.name ?? t("未设置");
      const changed = state.defaultsDraft[slot] !== state.data.defaults[slot];
      root.querySelector(`#default-${slot}-state`).textContent = changed ? t("待保存") : '';
      target.title = msg`${slotNames[slot]}：${configured?.name ?? t("未设置")}；先点此卡，再选择项目声音。`;
      root.querySelector(`#clear-default-${slot}`).disabled = state.busy || !state.defaultsDraft[slot];
    }
    const dirty = defaultsDirty(state), invalid = slots.some(slot => state.defaultsDraft[slot] && !defaultVoice(state.data, slot, state.defaultsDraft));
    root.querySelector('#open-default-config').disabled = state.busy;
    root.querySelector('#defaults-status').textContent = invalid ? t("部分默认已失效，请重新选择。") : state.activeDefaultSlot ? msg`请选择${slotNames[state.activeDefaultSlot]}` : dirty ? t("默认设置已更改，点击“完成设置”后确认保存")  : '';
  };
  render(store.getState()); return store.subscribe(render);
}
function slotField(slot) {
  return `<article class="default-card" data-slot="${slot}"><button id="default-${slot}" class="default-target" type="button" aria-label="${escapeHtml(t("选择{0}", slotNames[slot]))}"><strong>${slotNames[slot]}</strong><span id="default-${slot}-name" class="default-card-name">${escapeHtml(t("未设置"))}</span><small id="default-${slot}-state">${escapeHtml(t("已保存"))}</small></button><button id="clear-default-${slot}" class="default-clear" type="button" aria-label="${escapeHtml(t("清空{0}", slotNames[slot]))}"><span aria-hidden="true">×</span></button></article>`;
}
