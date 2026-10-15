export function mountDebugPanel(panel, toggle, store, log, api, loadCatalog) {
  panel.innerHTML = `<div class="debug-heading"><h2 id="debug-title">Debug Panel</h2><button id="debug-close">关闭 Debug</button></div><div class="debug-actions"><button id="debug-test">记录测试事件</button><button id="debug-load">测试 Mock 返回</button><button id="debug-error">测试 Mock 错误</button><button id="debug-clear">清空日志</button></div><p>开发工具 · 失败测试仅模拟错误，不访问外部服务。最多保留 100 条事件。</p><div class="table-scroll"><table><caption>事件日志</caption><thead><tr><th>时间</th><th>事件名称</th><th>对象 ID</th><th>操作结果</th><th>错误</th></tr></thead><tbody id="event-rows"></tbody></table></div><details><summary>当前状态</summary><pre id="state-view"></pre></details><p id="debug-status" role="status"></p>`;
  const update = () => {
    const state = store.getState();
    panel.hidden = !state.ui.debugOpen;
    toggle.setAttribute('aria-expanded', String(state.ui.debugOpen));
    toggle.textContent = state.ui.debugOpen ? '关闭 Debug' : '打开 Debug';
    panel.querySelector('#state-view').textContent = JSON.stringify(state, null, 2);
    panel.querySelector('#event-rows').replaceChildren(...log.getEntries().map(entry => {
      const row = document.createElement('tr');
      for (const value of [entry.time, entry.name, entry.objectId, entry.result, entry.error]) { const cell = document.createElement('td'); cell.textContent = value; row.append(cell); }
      return row;
    }));
  };
  toggle.hidden = false;
  toggle.onclick = () => store.dispatch({ type: 'TOGGLE_DEBUG' });
  panel.querySelector('#debug-close').onclick = () => { store.dispatch({ type: 'TOGGLE_DEBUG' }); toggle.focus(); };
  panel.querySelector('#debug-test').onclick = () => { log.record({ name: 'debug.test', objectId: 'MOCK_PROJECT_A', result: '测试事件成功' }); panel.querySelector('#debug-status').textContent = '测试事件已记录'; };
  panel.querySelector('#debug-clear').onclick = () => { log.clear(); panel.querySelector('#debug-status').textContent = '日志已清空'; };
  const testApi = async simulateError => {
    try { const data = await api.loadWorkspace({ simulateError }); panel.querySelector('#debug-status').textContent = `返回 ${data.voices.length} 个 Mock 声音`; }
    catch (error) { panel.querySelector('#debug-status').textContent = error.message; }
  };
  panel.querySelector('#debug-load').onclick = () => testApi(false);
  panel.querySelector('#debug-error').onclick = () => testApi(true);
  for (const [label, options] of [['声音池：模拟失败', { simulateError: true }], ['声音池：空列表', { empty: true }], ['声音池：恢复数据', {}]]) {
    const button = document.createElement('button'); button.type = 'button'; button.textContent = label;
    button.onclick = () => { void loadCatalog(options); };
    panel.querySelector('.debug-actions').append(button);
  }
  for (const [label, options] of [['下一次试听失败', { failPreview: true }], ['下一次保存失败', { failSave: true }], ['模拟项目库 revision 冲突', { conflict: true }]]) {
    const button = document.createElement('button'); button.type = 'button'; button.textContent = label;
    button.onclick = () => { api.configureMock(options); panel.querySelector('#debug-status').textContent = label + '已设置，仅影响 Mock 内存'; };
    panel.querySelector('.debug-actions').append(button);
  }
  const unsubscribeStore = store.subscribe(update);
  const unsubscribeLog = log.subscribe(update);
  update();
  return () => { unsubscribeStore(); unsubscribeLog(); };
}
