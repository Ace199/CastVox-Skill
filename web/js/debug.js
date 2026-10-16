import { t, escapeHtml, translateMessage } from './i18n.js';
export function mountDebug(panel, toggle, store, api, controller, log) {
  panel.innerHTML = `<div class="section-heading"><h2 id="debug-title">Debug Panel</h2><button id="debug-close" type="button">${escapeHtml(t("关闭 Debug"))}</button></div><div class="debug-actions"><button id="debug-test" type="button">${escapeHtml(t("记录测试事件"))}</button><button id="debug-fail" type="button">${escapeHtml(t("下一次写入失败"))}</button><button id="debug-conflict" type="button">${escapeHtml(t("模拟 revision 冲突"))}</button><button id="debug-empty" type="button">${escapeHtml(t("模拟空项目"))}</button><button id="debug-clear" type="button">${escapeHtml(t("清空日志"))}</button></div><div class="debug-preview-controls"><label for="debug-preview-voice">${escapeHtml(t("Mock 试听对象"))}</label><select id="debug-preview-voice"></select><button id="debug-preview-none" type="button">${escapeHtml(t("模拟无试听"))}</button><button id="debug-preview-valid" type="button">${escapeHtml(t("模拟有效试听"))}</button><button id="debug-preview-stale" type="button">${escapeHtml(t("模拟调整前试听"))}</button><button id="debug-preview-unavailable" type="button">${escapeHtml(t("模拟文件不可用"))}</button></div><p class="small">${escapeHtml(t("仅内存 Mock；不会修改真实项目、凭据或 Agent 的多声音配置能力。"))}</p><div class="table-scroll"><table><caption>${escapeHtml(t("事件日志（最多 100 条）"))}</caption><thead><tr><th>${escapeHtml(t("事件名称"))}</th><th>${escapeHtml(t("对象 ID"))}</th><th>${escapeHtml(t("操作结果"))}</th><th>${escapeHtml(t("错误"))}</th></tr></thead><tbody id="event-rows"></tbody></table></div><details><summary>${escapeHtml(t("当前状态 / Mock 回答"))}</summary><pre id="state-view"></pre></details>`;
  toggle.hidden = false;
  toggle.onclick = () => store.update({ debugOpen: !store.getState().debugOpen });
  panel.querySelector('#debug-close').onclick = () => { store.update({ debugOpen: false }); toggle.focus(); };
  panel.querySelector('#debug-test').onclick = () => log.record({ name: 'debug.test', objectId: 'MOCK_PROJECT_A', result: t("测试事件成功") });
  panel.querySelector('#debug-fail').onclick = () => api.configureMock({ failSave: true });
  panel.querySelector('#debug-conflict').onclick = () => api.configureMock({ conflict: true });
  panel.querySelector('#debug-empty').onclick = () => { api.configureMock({ empty: true }); void controller.load(); };
  panel.querySelector('#debug-clear').onclick = () => log.clear();
  panel.querySelector('#debug-preview-voice').onchange = event => store.update({ debugVoiceId: event.target.value });
  for (const scenario of ['none', 'valid', 'stale', 'unavailable']) panel.querySelector(`#debug-preview-${scenario}`).onclick = () => { const id = panel.querySelector('#debug-preview-voice').value; if (id) void controller.setPreviewScenario(id, scenario); };
  const render = () => {
    const state = store.getState(); panel.hidden = !state.debugOpen; toggle.textContent = state.debugOpen ? t("关闭 Debug") : t("打开 Debug"); toggle.setAttribute('aria-expanded', String(state.debugOpen));
    const select = panel.querySelector('#debug-preview-voice'), voices = Object.values(state.data?.voices ?? {}).filter(voice => !voice.deleted), key = JSON.stringify(voices.map(voice => [voice.id, voice.name]));
    if (select.dataset.options !== key) { select.dataset.options = key; select.replaceChildren(...voices.map(voice => { const option = document.createElement('option'); option.value = voice.id; option.textContent = voice.name; return option; })); }
    select.value = state.debugVoiceId && voices.some(voice => voice.id === state.debugVoiceId) ? state.debugVoiceId : state.editor.id && voices.some(voice => voice.id === state.editor.id) ? state.editor.id : voices[0]?.id ?? '';
    panel.querySelector('#state-view').textContent = JSON.stringify(state, null, 2);
    panel.querySelector('#event-rows').replaceChildren(...log.getEntries().map(entry => { const row = document.createElement('tr'); for (const key of ['name', 'objectId', 'result', 'error']) { const cell = document.createElement('td'); cell.textContent = ['result', 'error'].includes(key) ? translateMessage(entry[key]) : entry[key]; row.append(cell); } return row; }));
  };
  const disposeStore = store.subscribe(render), disposeLog = log.subscribe(render); render();
  return () => { disposeStore(); disposeLog(); };
}
