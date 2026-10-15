import { capabilities, emotions, findEditorVoice, previewBlocker, editorSignature } from '../editor.js';
import { renderCatalogDetail } from './sound-pool.js';
import { mountAssignmentActions } from './assignment-actions.js';

export function mountSettingsPanel(root, store, log, api) {
  root.innerHTML = `<section id="role-required" hidden><h2>请选择角色</h2><p>先在 02 当前需求中选择角色，再沿用该角色的信息调整声音。</p></section><div id="settings-metadata"></div><div id="settings-extras"><label>模型选择<select id="editor-model" aria-label="模型选择"></select></label><label>音色选择<select id="editor-voice" aria-label="音色选择"></select></label></div>
    <p id="editor-scope" class="muted"></p><fieldset id="editor-fields"><legend>声音参数草稿</legend>
      <label>情绪<select id="editor-emotion" aria-label="情绪" aria-describedby="emotion-compatibility"></select></label><p id="emotion-compatibility" role="status" class="muted"></p>
      <div class="editor-numbers"><label>语速<input id="editor-speed" aria-label="语速" type="range" min="0.5" max="2" step="0.1"><output id="speed-value"></output></label><label>音量<input id="editor-volume" aria-label="音量" type="range" min="0.1" max="10" step="0.1"><output id="volume-value"></output></label></div>
      <label class="editor-check"><input id="editor-latex" type="checkbox">LaTeX 公式朗读</label><label class="editor-check"><input id="editor-normalize" type="checkbox">中英文文本规范化</label>
      <label>试听文本<textarea id="editor-text" aria-label="试听文本" maxlength="2000" rows="3"></textarea></label><small>来自 Mock Agent 提取的完整句，可编辑；不修改原稿。</small>
      <p class="muted">本地 Mock 试听：仅播放同一提示音，不模拟音色或参数效果，无收费 API。</p><button type="button" id="editor-preview">生成模拟试听</button><p id="editor-blocker" class="muted"></p>
      <section aria-label="试听结果"><h3>试听结果</h3><p id="editor-preview-status" role="status">尚未试听</p><audio id="editor-audio" controls preload="none" hidden></audio></section>
    </fieldset><div id="assignment-actions"></div><div id="settings-placeholder" hidden><img class="placeholder-decoration" src="assets/studio-waves-v1.png" alt="" width="120" height="120"><h2>音色生成</h2><p>本阶段仅保留占位，不提供音色设计或复刻流程。</p></div>`;
  const unmountActions = mountAssignmentActions(root.querySelector('#assignment-actions'), store, api, log, document.querySelector('#complete-settings'));
  const model = root.querySelector('#editor-model'), voice = root.querySelector('#editor-voice'), emotion = root.querySelector('#editor-emotion');
  for (const [value, item] of Object.entries(capabilities)) { const option = document.createElement('option'); option.value = value; option.textContent = item.name; model.append(option); }
  for (const [value, label] of Object.entries(emotions)) { const option = document.createElement('option'); option.value = value; option.textContent = label; emotion.append(option); }
  const audio = root.querySelector('audio'); let activeKey = null, voiceListSignature = '';
  const change = (field, value) => {
    try {
      if (field === 'voiceKey' && !store.getState().editor.activeKey) {
        const index = value.indexOf(':'); const kind = value.slice(0, index), id = value.slice(index + 1);
        store.dispatch({ type: kind === 'project' ? 'OPEN_VOICE_SETTINGS' : 'OPEN_POOL_SETTINGS', voiceId: id }); store.dispatch({ type: 'SET_TAB', tab: 'explore' });
      } else store.dispatch({ type: 'EDIT_FIELD', field, value });
      log.record({ name: 'settings.edited', objectId: store.getState().editor.activeKey, result: `${field} 已更新未提交草稿` });
    } catch (error) { log.record({ name: 'settings.edit.failed', objectId: field, result: '拒绝', error }); }
  };
  model.onchange = () => change('model', model.value); voice.onchange = () => change('voiceKey', voice.value); emotion.onchange = () => change('emotion', emotion.value);
  for (const field of ['speed', 'volume', 'text', 'latex', 'normalize']) {
    const input = root.querySelector(`#editor-${field}`);
    input.addEventListener(['latex', 'normalize'].includes(field) ? 'change' : 'input', () => change(field, ['latex', 'normalize'].includes(field) ? input.checked : ['speed', 'volume'].includes(field) ? Number(input.value) : input.value));
  }
  root.querySelector('#editor-preview').onclick = async () => {
    const state = store.getState(), key = state.editor.activeKey, draft = state.editor.drafts[key];
    if (state.ui.tab === 'basic' && state.ui.target?.kind !== 'role') return;
    if (previewBlocker(state, draft) || draft.preview.status === 'loading') return;
    const signature = editorSignature(draft);
    log.record({ name: 'settings.preview.request', objectId: key, result: '主动生成本地模拟试听' });
    store.dispatch({ type: 'EDITOR_PREVIEW_START', key, signature });
    try {
      const result = await api.createPreview({ draft });
      if (store.getState().editor.drafts[key]) store.dispatch({ type: 'EDITOR_PREVIEW_SUCCESS', key, signature, result });
      log.record({ name: 'settings.preview.ready', objectId: key, result: '本地提示音已就绪；不模拟真实参数效果' });
    } catch (error) {
      if (store.getState().editor.drafts[key]) store.dispatch({ type: 'EDITOR_PREVIEW_FAILURE', key, signature, error: error.message });
      log.record({ name: 'settings.preview.failed', objectId: key, result: '模拟试听失败，保留草稿', error });
    }
  };
  audio.addEventListener('play', () => log.record({ name: 'settings.preview.play', objectId: activeKey, result: '本地提示音，非真实语音' }));
  audio.addEventListener('error', () => { root.querySelector('#editor-preview-status').textContent = '本地音频无法播放，请重新生成模拟试听'; log.record({ name: 'settings.preview.audio-error', objectId: activeKey, result: '本地音频失败' }); });
  const render = state => {
    const key = state.editor.activeKey, draft = state.editor.drafts[key];
    if (key !== activeKey) { audio.pause(); root.scrollTop = 0; activeKey = key; }
    const create = state.ui.tab === 'create';
    const role = state.ui.target?.kind === 'role' ? state.data?.roles.find(item => item.id === state.ui.target.roleId) : null;
    const blocked = state.ui.tab === 'basic' && !role;
    root.querySelector('#role-required').hidden = !blocked;
    root.closest('.settings').classList.toggle('awaiting-role', blocked);
    for (const selector of ['#settings-metadata', '#editor-scope', '#editor-fields', '#assignment-actions']) root.querySelector(selector).hidden = create || blocked;
    root.querySelector('#settings-placeholder').hidden = !create;
    root.querySelector('#settings-extras').hidden = state.ui.tab !== 'explore';
    if (create || blocked) { audio.pause(); return; }
    const items = [...(state.data?.voices ?? []).map(item => ({ ...item, kind: 'project' })), ...state.catalog.voices.map(item => ({ ...item, kind: 'pool' }))];
    const listSignature = JSON.stringify(items.map(item => [item.kind, item.id, item.name, item.availability]));
    if (listSignature !== voiceListSignature) {
      voiceListSignature = listSignature; voice.replaceChildren();
      const empty = document.createElement('option'); empty.value = ''; empty.textContent = '请选择声音'; empty.disabled = true; voice.append(empty);
      for (const item of items) { const option = document.createElement('option'); option.value = `${item.kind}:${item.id}`; option.textContent = `${item.kind === 'project' ? '项目库' : item.source === 'official' ? '官方 Mock' : '用户 Mock'} · ${item.name}${item.availability === 'unavailable' ? '（不可用）' : ''}`; option.disabled = item.availability === 'unavailable'; voice.append(option); }
    }
    const metadata = root.querySelector('#settings-metadata'); metadata.replaceChildren();
    const currentVoice = findEditorVoice(state, draft?.voiceKey);
    if (state.ui.tab === 'explore' && currentVoice && draft.voiceKey.startsWith('pool:')) { renderCatalogDetail(metadata, currentVoice, state); metadata.querySelector('h2')?.remove(); }
    else {
      const heading = document.createElement('h2'); heading.textContent = state.ui.tab === 'basic' ? '基础设置' : '探索更多';
      const name = document.createElement('p'); name.className = 'voice-context'; name.textContent = currentVoice ? `当前音色：${currentVoice.name}` : '请选择声音';
      const id = document.createElement('small'); id.textContent = currentVoice?.id ?? '';
      metadata.append(heading, name, id);
    }
    if (role) {
      const context = document.createElement('div'); context.className = 'role-editor-context';
      const icon = document.createElement('img'); icon.className = 'editor-role-avatar'; icon.src = state.task.avatars[role.id]; icon.alt = ''; icon.width = 48; icon.height = 48;
      const name = document.createElement('strong'); name.textContent = `当前角色：${role.name}`;
      context.append(icon, name); metadata.prepend(context);
    }
    root.querySelector('#editor-scope').textContent = draft ? `${draft.title} · 修改仅留在此对象草稿，未写入项目配置。` : '请选择对象后编辑。';
    root.querySelector('#editor-fields').disabled = !draft;
    model.disabled = !draft; voice.value = draft?.voiceKey ?? '';
    const previewButton = root.querySelector('#editor-preview');
    const loading = draft?.preview.status === 'loading';
    previewButton.setAttribute('aria-busy', String(loading));
    previewButton.textContent = loading ? '正在生成 Mock 试听…' : '生成模拟试听';
    if (!draft) { previewButton.disabled = true; audio.hidden = true; root.querySelector('#editor-preview-status').textContent = '尚未试听'; return; }
    model.value = draft.model; emotion.value = draft.emotion;
    const supported = capabilities[draft.model].emotions;
    for (const option of emotion.options) { option.disabled = !supported.includes(option.value); option.title = option.disabled ? `${capabilities[draft.model].name} 不支持此情绪` : ''; }
    const unsupported = Object.keys(emotions).filter(value => !supported.includes(value));
    root.querySelector('#emotion-compatibility').textContent = `${unsupported.length ? `此 Mock 模型不支持：${unsupported.map(value => emotions[value]).join('、')}。` : '此 Mock 模型支持全部列出的情绪。'}${supported.includes(draft.emotion) ? '' : '原情绪已保留，请主动选择兼容项。'}`;
    for (const field of ['speed', 'volume', 'text', 'latex', 'normalize']) {
      const input = root.querySelector(`#editor-${field}`);
      if (['latex', 'normalize'].includes(field)) input.checked = draft[field];
      else if (input.value !== String(draft[field])) input.value = draft[field];
    }
    root.querySelector('#speed-value').textContent = draft.speed; root.querySelector('#volume-value').textContent = draft.volume;
    const blocker = previewBlocker(state, draft);
    root.querySelector('#editor-blocker').textContent = blocker;
    root.querySelector('#editor-preview').disabled = !!blocker || draft.preview.status === 'loading';
    const old = draft.preview.signature && draft.preview.signature !== editorSignature(draft);
    const prior = draft.preview.url ? old ? '；旧参数试听仍可播放' : '；上次模拟试听仍可播放' : '';
    root.querySelector('#editor-preview-status').textContent = draft.preview.status === 'loading' ? `正在生成本地 Mock 试听…${prior}` : draft.preview.status === 'error' ? `模拟试听失败：${draft.preview.error}${prior}` : draft.preview.url ? `${old ? '旧参数试听 · 过期配置结果 · 参数已变化' : '当前参数模拟试听'}${draft.preview.cacheHit ? ' · 缓存命中' : ''} · ${draft.preview.duration} 秒本地提示音，非真实语音` : '尚未试听';
    audio.hidden = !draft.preview.url;
    if (draft.preview.url && audio.getAttribute('src') !== draft.preview.url) audio.src = draft.preview.url;
  };
  render(store.getState()); const unsubscribe = store.subscribe(render);
  return () => { audio.pause(); unmountActions(); unsubscribe(); };
}
