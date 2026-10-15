import { mountProjectLibrary } from './project-library.js';
import { mountRequirements } from './requirements.js';
import { mountSoundPool } from './sound-pool.js';
import { mountSettingsPanel } from './settings-panel.js';

export function mountWorkspace(root, store, log, loadCatalog, api) {
  root.innerHTML = `
    <div class="workspace-left">
      <section class="panel assignment-workspace" aria-label="项目音色库与当前需求">
        <section class="project-section" aria-labelledby="project-name">
          <span class="eyebrow">项目音色库</span><h2 id="project-name">正在加载</h2>
          <div id="project-voices"></div><p class="muted">下方添加更多 · 试听为本地 Mock 提示音，非真实音色</p>
          <p id="library-feedback" role="status" aria-live="polite"></p>
        </section>
        <section class="requirements-section" aria-labelledby="requirements-title"></section>
      </section>
      <section class="panel pool-panel" aria-labelledby="pool-title"></section>
    </div>
    <section class="panel settings" id="settings-panel" aria-label="声音详情面板">
      <div role="tablist" aria-label="声音设置">
        <button role="tab" id="tab-basic" aria-controls="settings-content" data-tab="basic">基础设置</button>
        <button role="tab" id="tab-explore" aria-controls="settings-content" data-tab="explore">探索更多</button>
        <button role="tab" id="tab-create" aria-controls="settings-content" data-tab="create">音色生成</button>
      </div>
      <div id="requirement-context"></div><div id="settings-content" role="tabpanel" tabindex="0"></div><p id="load-status" role="status"></p>
    </section>`;
  const unmountLibrary = mountProjectLibrary(root.querySelector('#project-voices'), store, log);
  const unmountRequirements = mountRequirements(root.querySelector('.requirements-section'), root.querySelector('#requirement-context'), store, log);
  const unmountPool = mountSoundPool(root.querySelector('.pool-panel'), store, log, loadCatalog);
  const unmountSettings = mountSettingsPanel(root.querySelector('#settings-content'), store, log, api);
  const tabs = [...root.querySelectorAll('[role=tab]')];
  const selectTab = tab => { store.dispatch({ type: 'SET_TAB', tab }); log.record({ name: 'ui.tab.changed', objectId: tab, result: '已切换' }); };
  tabs.forEach((button, index) => {
    button.addEventListener('click', () => selectTab(button.dataset.tab));
    button.addEventListener('keydown', event => {
      const next = { ArrowRight: (index + 1) % 3, ArrowLeft: (index + 2) % 3, Home: 0, End: 2 }[event.key];
      if (next === undefined) return;
      event.preventDefault(); selectTab(tabs[next].dataset.tab); tabs[next].focus();
    });
  });
  const render = (state, action) => {
    root.classList.toggle('pool-collapsed', state.ui.poolCollapsed);
    root.querySelector('#project-name').textContent = state.data?.project.name ?? '演示项目';
    root.querySelector('#load-status').textContent = state.status === 'error' ? state.error : state.status === 'ready' ? 'Mock 数据已加载 · 未连接真实服务' : '正在加载 Mock 数据…';
    tabs.forEach(button => { const active = button.dataset.tab === state.ui.tab; button.setAttribute('aria-selected', String(active)); button.tabIndex = active ? 0 : -1; });
    const content = root.querySelector('#settings-content');
    content.setAttribute('aria-labelledby', `tab-${state.ui.tab}`);
    const selected = state.data?.voices.find(voice => voice.id === state.ui.selectedVoiceId);
    const preview = state.ui.preview;
    const target = state.ui.target;
    const targetRole = state.data?.roles?.find(item => item.id === target?.roleId);
    const bound = targetRole && state.task.selections[targetRole.id]?.voiceId === selected?.id;
    root.querySelector('#library-feedback').textContent = preview.status === 'error' ? `模拟试听失败：${preview.error}` : preview.status === 'playing' ? '正在播放本地 Mock 提示音，非真实音色' : selected ? bound ? `${targetRole.name} 已分配：${selected.name}（仅本任务）` : target?.kind === 'default' ? `默认候选：${selected.name}；需确认保存` : `已选择：${selected.name}；未执行角色分配` : '';
    if (['OPEN_VOICE_SETTINGS', 'OPEN_POOL_SETTINGS'].includes(action)) {
      if (action === 'OPEN_VOICE_SETTINGS') log.record({ name: 'pool.collapse.changed', objectId: 'MOCK_CATALOG', result: '项目音色设置自动收起声音池' });
      log.record({ name: 'settings.basic.open', objectId: state.editor.activeKey, result: '基础设置已打开；窄屏定位下方设置长卡' });
      if (matchMedia('(max-width:850px)').matches) {
        root.querySelector('.settings').scrollIntoView({ block: 'start', behavior: 'instant' });
        content.focus({ preventScroll: true });
      }
    }
  };
  render(store.getState());
  const unsubscribe = store.subscribe(render);
  return () => { unmountLibrary(); unmountRequirements(); unmountPool(); unmountSettings(); unsubscribe(); };
}
