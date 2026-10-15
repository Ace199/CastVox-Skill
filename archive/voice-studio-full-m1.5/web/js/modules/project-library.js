import { boundRoleNumbers } from '../voice-presentation.js';
// Metadata only: names never determine gender. Unknown and unsupported values stay other.
export function voiceCategory(voice) {
  return ['male', 'female'].includes(voice.gender) && voice.provenance ? voice.gender : 'other';
}

export function mountProjectLibrary(root, store, log, createAudio = () => new Audio('assets/mock-preview.wav')) {
  const audio = createAudio();
  let activeId = null;
  let operation = 0;
  const publish = (voiceId, status, error = '') => {
    if (store.getState().data?.voices.some(voice => voice.id === voiceId)) store.dispatch({ type: 'PREVIEW_STATE', voiceId, status, error });
    log.record({ name: `library.preview.${status}`, objectId: voiceId, result: status === 'playing' ? '播放本地 Mock 提示音，非真实音色' : status, error });
  };
  const stop = () => {
    operation++;
    audio.pause(); audio.currentTime = 0;
    if (activeId) publish(activeId, 'stopped');
    activeId = null;
  };
  const preview = async voiceId => {
    const same = activeId === voiceId;
    stop();
    if (same) return;
    activeId = voiceId;
    const token = ++operation;
    publish(voiceId, 'loading');
    try {
      await audio.play();
      if (token === operation) publish(voiceId, 'playing');
    } catch (error) {
      if (token === operation) { activeId = null; publish(voiceId, 'error', error.message); }
    }
  };
  audio.addEventListener('ended', () => {
    if (activeId) { const id = activeId; activeId = null; operation++; publish(id, 'ended'); }
  });
  audio.addEventListener('error', () => {
    if (activeId) { const id = activeId; activeId = null; operation++; publish(id, 'error', '本地 Mock 音频无法播放'); }
  });
  const button = (className, text, label) => {
    const node = document.createElement('button'); node.type = 'button'; node.className = className;
    node.textContent = text; node.setAttribute('aria-label', label); return node;
  };
  const render = (state, action) => {
    if (activeId && action === 'POOL_PREVIEW_STATE' && state.ui.poolPreview?.status === 'loading') stop();
    if (!action || ['LOAD_START', 'LOAD_SUCCESS', 'LOAD_FAILURE', 'LIBRARY_SYNC', 'FLOW_LIBRARY_COMMIT'].includes(action)) {
      const scrollLeft = root.querySelector('.library-scroll')?.scrollLeft ?? 0;
      if (activeId) stop();
      root.replaceChildren();
      root.className = 'project-library';
      const number = document.createElement('span'); number.className = 'library-number'; number.textContent = '01'; number.setAttribute('aria-hidden', 'true');
      const labels = document.createElement('div'); labels.className = 'library-labels';
      const scroll = document.createElement('div'); scroll.className = 'library-scroll'; scroll.tabIndex = 0;
      scroll.setAttribute('role', 'region'); scroll.setAttribute('aria-label', '项目声音列表，男女行共用横向滚动');
      const voices = state.data?.voices ?? [];
      const groups = [['male', '男声'], ['female', '女声']];
      if (voices.some(voice => voiceCategory(voice) === 'other')) groups.push(['other', '其他']);
      for (const [category, label] of groups) {
        const heading = document.createElement('strong'); heading.className = 'row-label'; heading.textContent = label; labels.append(heading);
        const row = document.createElement('div'); row.className = 'library-row'; row.dataset.category = category;
        row.setAttribute('role', 'group'); row.setAttribute('aria-label', `${label}项目声音`);
        for (const voice of voices.filter(item => voiceCategory(item) === category)) {
          const card = document.createElement('article'); card.className = 'project-voice-card'; card.dataset.voiceId = voice.id;
          // Decorative original portraits are selected by ID, never used to infer voice attributes.
          const portraits = ['narrator', 'reader', 'soft'];
          const portrait = portraits[[...voice.id].reduce((sum, c) => sum + c.charCodeAt(0), 0) % portraits.length];
          const avatar = document.createElement('img'); avatar.className = `voice-avatar voice-category-${category}`; avatar.src = ['assets/portrait-narrator.svg', 'assets/portrait-reader.svg', 'assets/portrait-soft.svg'].includes(voice.avatar) ? voice.avatar : `assets/portrait-${portrait}.svg`; avatar.alt = ''; avatar.width = 36; avatar.height = 36;
          // Three sibling buttons: no nested interactive elements, and no bubbling card action.
          const body = button('voice-body', '', `选择项目声音：${voice.name}`);
          const play = button('voice-preview', '▶', `试听 ${voice.name}（本地 Mock 提示音）`);
          play.dataset.name = voice.name;
          const name = document.createElement('span'); name.className = 'voice-name'; name.textContent = voice.name;
          const marker = document.createElement('span'); marker.className = 'voice-role-markers'; marker.id = `voice-binding-${voice.id}`; marker.setAttribute('role', 'img'); body.setAttribute('aria-describedby', marker.id);
          body.append(marker, avatar, name); body.title = voice.name;
          const settings = button('voice-settings', '⚙', `设置 ${voice.name}`); settings.title = '打开基础设置';
          body.onclick = () => {
            const target = store.getState().ui.target;
            store.dispatch({ type: target ? 'ASSIGN_TARGET_VOICE' : 'SELECT_PROJECT_VOICE', voiceId: voice.id });
            log.record({ name: 'library.card.select', objectId: voice.id, result: target ? target.kind === 'role' ? `已绑定当前任务角色 ${target.roleId}` : '已更新项目默认草稿；尚未保存' : '已选择声音；请先选择角色或项目默认目标' });
            if (target) log.record({ name: target.kind === 'role' ? 'requirements.role.assigned' : 'requirements.default.draft', objectId: target.roleId ?? store.getState().data.project.id, result: `voiceId=${voice.id}；${target.kind === 'role' ? '仅当前任务' : '仅默认草稿，待确认'}` });
          };
          play.onclick = () => { void preview(voice.id); };
          settings.onclick = () => { store.dispatch({ type: 'OPEN_VOICE_SETTINGS', voiceId: voice.id }); log.record({ name: 'library.settings.open', objectId: voice.id, result: '已打开对应声音的基础设置' }); };
          card.append(body, play, settings); row.append(card);
        }
        if (!row.children.length) { const empty = document.createElement('span'); empty.className = 'library-empty'; empty.textContent = `暂无${label}项目声音`; row.append(empty); }
        scroll.append(row);
      }
      root.append(number, labels, scroll);
      scroll.scrollLeft = scrollLeft;
    }
    for (const card of root.querySelectorAll('.project-voice-card')) {
      const voice = state.data.voices.find(item => item.id === card.dataset.voiceId);
      const numbers = boundRoleNumbers(state, voice);
      const marker = card.querySelector('.voice-role-markers');
      marker.replaceChildren(); marker.dataset.gender = voiceCategory(voice); marker.classList.toggle('is-unbound', !numbers.length);
      marker.title = numbers.length ? `已绑定 02 角色：${numbers.join('、')}` : '尚未绑定当前任务角色';
      marker.setAttribute('aria-label', marker.title);
      if (numbers.length) {
        const visible = numbers.length <= 2 ? numbers.map(String) : [String(numbers[0]), `+${numbers.length - 1}`];
        for (const number of visible) { const badge = document.createElement('span'); badge.textContent = number; marker.append(badge); }
      }
      const selected = card.dataset.voiceId === state.ui.selectedVoiceId;
      card.classList.toggle('is-selected', selected);
      card.querySelector('.voice-body').setAttribute('aria-pressed', String(selected));
      const playing = card.dataset.voiceId === state.ui.preview.voiceId && ['loading', 'playing'].includes(state.ui.preview.status);
      const play = card.querySelector('.voice-preview');
      play.textContent = playing ? '■' : '▶';
      play.setAttribute('aria-label', `${playing ? '停止' : '试听'} ${play.dataset.name}（本地 Mock 提示音）`);
      play.setAttribute('aria-pressed', String(playing));
    }
  };
  render(store.getState());
  const unsubscribe = store.subscribe(render);
  return () => { stop(); unsubscribe(); };
}
