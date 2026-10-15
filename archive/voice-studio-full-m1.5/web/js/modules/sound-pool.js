import { filterCatalog, featureOptions, sourceLabel, catalogAttributes } from '../catalog.js';

export function mountSoundPool(panel, store, log, loadCatalog, createAudio = () => new Audio('assets/mock-preview.wav')) {
  const audio = createAudio();
  let activeId = null, operation = 0;
  const publish = (voiceId, status, error = '') => {
    store.dispatch({ type: 'POOL_PREVIEW_STATE', voiceId, status, error });
    log.record({ name: `pool.preview.${status}`, objectId: voiceId, result: '本地 Mock 提示音，非真实音色；不选中、不跳转、不分配', error });
  };
  const stop = () => {
    const id = activeId; activeId = null; operation++; audio.pause(); audio.currentTime = 0;
    if (id) publish(id, 'stopped');
  };
  const play = async voice => {
    if (store.getState().catalog.voices.find(item => item.id === voice.id)?.availability !== 'available') return;
    const same = activeId === voice.id; stop(); if (same) return;
    activeId = voice.id; const token = ++operation; publish(voice.id, 'loading');
    try { await audio.play(); if (token === operation) publish(voice.id, 'playing'); }
    catch (error) { if (token === operation) { activeId = null; publish(voice.id, 'error', error.message); } }
  };
  audio.addEventListener('ended', () => { if (activeId) { const id = activeId; activeId = null; operation++; publish(id, 'ended'); } });
  audio.addEventListener('error', () => { if (activeId) { const id = activeId; activeId = null; operation++; publish(id, 'error', '本地提示音加载失败'); } });
  panel.innerHTML = `<div class="pool-heading"><span class="eyebrow">03 / 声音池</span><h2 id="pool-title">探索更多声音</h2><button id="pool-toggle" type="button" aria-expanded="true" aria-controls="pool-body">收起声音池</button></div><div id="pool-body" class="pool-body">
    <div class="pool-filters"><label>关键词<input id="pool-query" aria-label="关键词" type="search" placeholder="名称、标签或 ID" autocomplete="off"></label><label>来源<select id="pool-source" aria-label="来源"><option value="all">全部来源</option><option value="official">官方音色（Mock）</option><option value="user">用户音色（Mock）</option></select></label><label>声音特征<select id="pool-feature" aria-label="声音特征"></select></label></div>
    <p id="pool-status" class="muted" role="status" aria-live="polite"></p>
    <div id="pool" class="voice-grid" role="region" aria-label="声音池列表，纵向滚动" tabindex="0"></div></div>`;
  panel.querySelector('#pool-toggle').onclick = () => {
    const value = !store.getState().ui.poolCollapsed;
    store.dispatch({ type: 'SET_POOL_COLLAPSED', value });
    log.record({ name: 'pool.collapse.changed', objectId: 'MOCK_CATALOG', result: value ? '用户收起声音池，保留筛选和列表位置' : '用户展开声音池' });
  };
  const list = panel.querySelector('#pool');
  const feature = panel.querySelector('#pool-feature');
  for (const [value, text] of featureOptions) { const option = document.createElement('option'); option.value = value; option.textContent = text; feature.append(option); }
  for (const [id, key, event] of [['pool-query', 'query', 'input'], ['pool-source', 'source', 'change'], ['pool-feature', 'feature', 'change']]) {
    panel.querySelector(`#${id}`).addEventListener(event, event => {
      store.dispatch({ type: 'SET_CATALOG_FILTER', key, value: event.target.value });
      log.record({ name: 'pool.filter.changed', objectId: key, result: event.target.value || '全部' });
    });
  }
  const text = (tag, value, className) => { const node = document.createElement(tag); node.textContent = value; if (className) node.className = className; return node; };
  const render = (state, action) => {
    panel.classList.toggle('is-collapsed', state.ui.poolCollapsed);
    panel.querySelector('#pool-body').hidden = state.ui.poolCollapsed;
    panel.querySelector('#pool-toggle').setAttribute('aria-expanded', String(!state.ui.poolCollapsed));
    panel.querySelector('#pool-toggle').textContent = state.ui.poolCollapsed ? '展开声音池' : '收起声音池';
    if (activeId && (state.ui.poolCollapsed || ['OPEN_VOICE_SETTINGS', 'OPEN_POOL_SETTINGS', 'CATALOG_LOAD_START', 'CATALOG_LOAD_FAILURE'].includes(action) || (action === 'PREVIEW_STATE' && state.ui.preview.status === 'loading') || !filterCatalog(state.catalog.voices, state.catalog.filters).some(item => item.id === activeId))) stop();
    if (action === 'POOL_PREVIEW_STATE') {
      for (const button of list.querySelectorAll('.pool-play')) {
        const pending = state.ui.poolPreview.voiceId === button.dataset.voiceId && ['loading', 'playing'].includes(state.ui.poolPreview.status);
        button.textContent = pending ? '■' : '▶';
        button.setAttribute('aria-label', `${pending ? '停止' : '试听'}声音池：${button.dataset.name}（本地 Mock 提示音）`);
        button.setAttribute('aria-pressed', String(pending));
        button.setAttribute('aria-busy', String(state.ui.poolPreview.voiceId === button.dataset.voiceId && state.ui.poolPreview.status === 'loading'));
      }
      panel.querySelector('#pool-status').textContent = state.ui.poolPreview.status === 'error' ? `Mock 播放失败：${state.ui.poolPreview.error}` : state.ui.poolPreview.status === 'loading' ? '正在加载本地 Mock 提示音…' : state.ui.poolPreview.status === 'playing' ? '正在播放本地 Mock 提示音，非真实音色；不打开设置。' : '播放已停止 · 单击选中，双击或 Enter 打开基础设置。';
      return;
    }
    if (action && !action.startsWith('CATALOG_') && !['SET_CATALOG_FILTER', 'SELECT_POOL_VOICE', 'OPEN_POOL_SETTINGS'].includes(action)) return;
    if (['SELECT_POOL_VOICE', 'OPEN_POOL_SETTINGS'].includes(action)) {
      for (const card of list.querySelectorAll('.pool-voice-card')) { const selected = state.catalog.selectedId === card.dataset.poolId; card.classList.toggle('is-selected', selected); card.querySelector('.pool-body-button').setAttribute('aria-pressed', String(selected)); }
      return;
    }
    for (const [id, key] of [['pool-query', 'query'], ['pool-source', 'source'], ['pool-feature', 'feature']]) panel.querySelector(`#${id}`).value = state.catalog.filters[key];
    list.replaceChildren();
    const { status, filters, voices, error } = state.catalog;
    list.setAttribute('aria-busy', String(status === 'loading'));
    const summary = panel.querySelector('#pool-status');
    if (status === 'idle' || status === 'loading') { summary.textContent = '正在加载本地 Mock 声音池…'; return; }
    if (status === 'error') {
      summary.textContent = error;
      const retry = text('button', '重新加载 Mock 声音池'); retry.type = 'button';
      retry.onclick = () => { log.record({ name: 'pool.retry', objectId: 'MOCK_CATALOG', result: '用户手动重试' }); void loadCatalog(); };
      list.append(retry); return;
    }
    const shown = filterCatalog(voices, filters);
    summary.textContent = `${shown.length} / ${voices.length} 个候选 · 单击选中，双击或 Enter 打开设置 · Mock`;
    if (!shown.length) { list.append(text('p', voices.length ? '没有匹配的声音，请调整筛选条件。' : '声音池暂无音色。可在 Debug Panel 恢复 Mock 数据。', 'pool-empty')); return; }
    for (const voice of shown) {
      const attributes = catalogAttributes(voice);
      const card = text('article', '', 'pool-voice-card'); card.dataset.poolId = voice.id;
      card.dataset.gender = attributes.gender;
      const body = text('button', '', 'pool-body-button'); body.type = 'button';
      card.classList.toggle('is-unavailable', voice.availability === 'unavailable');
      card.classList.toggle('is-selected', state.catalog.selectedId === voice.id);
      body.setAttribute('aria-pressed', String(state.catalog.selectedId === voice.id));
      body.setAttribute('aria-label', `选择声音池音色：${voice.name}${voice.availability === 'unavailable' ? '（不可用）' : ''}`);
      body.title = `${voice.name} · 单击选中；双击或 Enter 打开基础设置`;
      const image = document.createElement('img'); image.className = `pool-portrait voice-category-${attributes.gender === 'unknown' ? 'other' : attributes.gender}`;
      image.src = `assets/portrait-${['narrator', 'reader', 'soft'].includes(voice.portrait) ? voice.portrait : 'soft'}.svg`; image.alt = ''; image.width = 100; image.height = 76;
      const info = text('span', '', 'pool-info'); const name = text('strong', voice.name, 'pool-name'); name.title = voice.name;
      const labels = { male: '男声', female: '女声', unknown: '性别 unknown' };
      const tags = text('span', '', 'pool-tags');
      for (const label of [labels[attributes.gender], ...attributes.tags.slice(0, 2)]) tags.append(text('span', label, 'pool-tag'));
      info.append(name, text('small', sourceLabel(voice.source)), tags, text('small', voice.availability === 'unavailable' ? '不可用 · 可查看详情' : voice.availability === 'available' ? 'Mock 可用' : '可用性 unknown', 'pool-availability'));
      body.append(image, info); card.append(body);
      body.onclick = () => {
        store.dispatch({ type: 'SELECT_POOL_VOICE', voiceId: voice.id });
        log.record({ name: 'pool.voice.selected', objectId: voice.id, result: '仅选中候选，不打开设置、不绑定/保存' });
      };
      const open = () => { store.dispatch({ type: 'OPEN_POOL_SETTINGS', voiceId: voice.id }); log.record({ name: 'pool.settings.open', objectId: voice.id, result: '双击或 Enter 打开对应基础设置' }); };
      body.ondblclick = open;
      body.onkeydown = event => { if (event.key === 'Enter') { event.preventDefault(); open(); } };
      if (voice.availability === 'available') {
        const button = text('button', '▶', 'pool-play'); button.type = 'button'; button.dataset.voiceId = voice.id; button.dataset.name = voice.name;
        button.setAttribute('aria-label', `试听声音池：${voice.name}（本地 Mock 提示音）`); button.setAttribute('aria-pressed', 'false'); button.title = '播放本地 Mock 提示音';
        button.onclick = () => { void play(voice); }; card.append(button);
      }
      list.append(card);
    }
  };
  render(store.getState());
  const unsubscribe = store.subscribe(render);
  return () => { stop(); unsubscribe(); };
}

export function renderCatalogDetail(content, voice, state) {
  const add = (tag, value, className) => { const node = document.createElement(tag); node.textContent = value; if (className) node.className = className; content.append(node); };
  const attributes = catalogAttributes(voice);
  content.replaceChildren();
  add('h2', '探索更多'); add('p', `当前音色：${voice.name}`, 'voice-context'); add('small', voice.id);
  add('p', `${sourceLabel(voice.source)} / 性别：${attributes.gender}`);
  add('p', `声音特征：${attributes.tags.length ? attributes.tags.join(' · ') : 'unknown'}`);
  add('p', `属性来源：${voice.provenance ?? 'unknown（未确认）'}`, 'muted');
  if (voice.availability === 'unavailable') add('p', `不可用：${voice.unavailableReason ?? '模拟不可用'}。当前仅可查看详情。`, 'unavailable-message');
  else add('p', voice.availability === 'available' ? 'Mock 可用状态，不代表真实 API 已验证。' : '可用性 unknown，尚未确认。', 'muted');
  if (!filterCatalog(state.catalog.voices, state.catalog.filters).some(item => item.id === voice.id)) add('p', '当前候选不在筛选结果中，详情仍保留。', 'muted');
  add('p', '选择候选不会自动保存或分配；显式应用与保存的结果见下方操作状态。', 'muted');
}

