import { controlCapability } from './capabilities.js';
import { editorDirty, previewStatus } from './voice-model.js';

export function mountSettings(root, store, controller, player) {
  root.innerHTML = `<div id="settings-empty" class="empty-state">点击项目声音卡上的设置图标进行编辑。</div>
    <section id="settings-editor" hidden aria-labelledby="setting-title"><div class="settings-content"><div class="section-heading"><h2 id="setting-title">声音设置</h2><span id="settings-dirty" class="small"></span></div>
    <div class="settings-identity"><div><label for="setting-name">声音名称</label><input id="setting-name" maxlength="120" autocomplete="off"></div>
    <div><label for="setting-category">声音分类</label><select id="setting-category"><option value="male">男声</option><option value="female">女声</option><option value="other">其他</option></select></div></div>
    <div class="parameter-grid">${parameter('speed', '语速')}${parameter('pitch', '声调')}</div>
    <section class="source-card" aria-label="声音来源，只读"><h3>声音来源 <span>只读</span></h3><dl class="source-grid"><div><dt>厂商</dt><dd id="setting-provider"></dd></div><div><dt>区域</dt><dd id="setting-region"></dd></div><div><dt>模型</dt><dd id="setting-model"></dd></div><div><dt>Voice ID</dt><dd id="setting-voice-id"></dd></div></dl></section>
    <section class="settings-preview" aria-label="项目已有试听"><h3>项目试听</h3><p id="settings-preview-state" class="small"></p><div class="preview-actions"><button id="setting-play" type="button">播放试听</button><button id="update-preview" class="quiet" type="button">更新试听</button></div><p id="preview-update-status" class="small muted"></p></section>
    </div><div class="settings-footer"><button id="delete-current-voice" type="button" class="text-button danger" aria-label="从项目库删除此声音">删除声音</button><div class="save-actions"><button id="cancel-settings" type="button">取消</button><button id="save-settings" type="button" class="blue-button">保存修改</button></div></div></section>`;
  const get = id => root.querySelector(`#${id}`);
  get('setting-name').oninput = event => store.editSetting('name', event.target.value);
  get('setting-category').onchange = event => store.editSetting('category', event.target.value);
  for (const key of ['speed', 'pitch']) {
    for (const suffix of ['', '-range']) get(`setting-${key}${suffix}`).oninput = event => store.editSetting(key, event.target.value);
    get(`reset-${key}`).onclick = () => { const state = store.getState(), voice = state.data.voices[state.editor.id]; const cap = controlCapability(voice.source, state.providers, key); if (cap.enabled) store.editSetting(key, cap.neutral); };
  }
  get('cancel-settings').onclick = () => store.cancelEditor();
  get('save-settings').onclick = () => { void controller.saveSettings(); };
  get('setting-play').onclick = () => { void player.toggle(store.getState().editor.id); };
  get('update-preview').onclick = () => { void controller.updatePreview(store.getState().editor.id); };
  get('delete-current-voice').onclick = () => controller.requestDelete(store.getState().editor.id);
  const render = state => {
    const voice = state.data?.voices[state.editor.id], shown = voice && !voice.deleted;
    get('settings-empty').hidden = !!shown; get('settings-editor').hidden = !shown; if (!shown) return;
    const draft = state.editor.draft;
    get('setting-title').textContent = voice.name; get('settings-dirty').textContent = editorDirty(state) ? '未保存修改' : '已保存';
    for (const [id, value] of [['setting-name', draft.name], ['setting-category', draft.category]]) { if (get(id).value !== String(value)) get(id).value = value; get(id).disabled = state.busy; }
    for (const key of ['speed', 'pitch']) {
      const cap = controlCapability(voice.source, state.providers, key), input = get(`setting-${key}`), range = get(`setting-${key}-range`);
      get(`${key}-control`).disabled = state.busy || !cap.enabled;
      range.hidden = !cap.enabled;
      if (cap.enabled) {
        for (const node of [input, range]) for (const attribute of ['min', 'max', 'step']) node.setAttribute(attribute, cap[attribute]);
        range.step = cap.range_step ?? cap.step;
        range.value = draft[key] === '' ? cap.neutral : draft[key];
      } else for (const attribute of ['min', 'max', 'step']) input.removeAttribute(attribute);
      if (input.value !== String(draft[key])) input.value = draft[key];
      get(`${key}-capability`).textContent = cap.enabled ? `${cap.min}–${cap.max}${cap.unit ? ` ${cap.unit}` : ''}${cap.step === 'any' ? '' : ` · 步长 ${cap.step}`}${cap.live_verified === false ? ' · 文档范围，真实效果未验收' : ''}` : cap.reason;
    }
    for (const [key, value] of Object.entries(voice.source)) { const target = get(`setting-${key === 'voice_id' ? 'voice-id' : key}`); if (target) target.textContent = value; }
    const status = previewStatus(voice, state.player), changedParameters = ['speed', 'pitch'].some(key => String(draft[key]) !== String(state.editor.baseline[key]));
    get('settings-preview-state').textContent = status.playable && changedParameters ? '调整前试听 · 未保存' : status.text;
    const playing = state.player.voiceId === voice.id && state.player.status === 'playing';
    get('setting-play').disabled = state.busy || !status.playable;
    get('setting-play').textContent = playing ? '暂停试听' : state.player.voiceId === voice.id && state.player.status === 'paused' ? '继续试听' : '播放试听';
    get('update-preview').hidden = state.data?.mode === 'persistent';
    get('update-preview').disabled = state.busy || editorDirty(state) || !!state.previewSaving[voice.id];
    get('preview-update-status').textContent = state.previewSaving[voice.id] ? '更新中，旧样本仍可播放' : editorDirty(state) ? '请先保存修改' : '';
    for (const id of ['cancel-settings', 'save-settings']) get(id).disabled = state.busy || !editorDirty(state);
    get('delete-current-voice').disabled = state.busy;
  };
  render(store.getState()); return store.subscribe(render);
}
function parameter(key, label) {
  return `<div class="parameter-block"><fieldset id="${key}-control" class="parameter-control"><legend>${label}</legend><input id="setting-${key}-range" type="range" aria-label="${label}滑块"><div class="parameter-value"><input id="setting-${key}" type="number" aria-label="${label}数值" aria-describedby="${key}-capability"><button id="reset-${key}" class="quiet" type="button" aria-label="恢复${label}默认值">恢复默认</button></div></fieldset><p id="${key}-capability" class="small muted parameter-help"></p></div>`;
}
