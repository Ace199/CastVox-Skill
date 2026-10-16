import { mountSections } from './sections.js';
import { mountDefaults } from './defaults-panel.js';
import { mountSettings } from './settings-panel.js';
import { mountAddParameters } from './add-parameters.js';
import { buildAnswer, defaultVoice, slotNames, validateNewVoiceFields } from './voice-model.js';
import { containDialogFocus } from './dialog-focus.js';
import { openProviderConfig } from './providers.js?v=config-editor-1';
export function mountStudio(root, store, controller, log, player) {
  root.innerHTML = `<section class="panel project-panel" aria-labelledby="project-name">
    <div class="section-heading"><span class="section-number">01</span><div><span class="eyebrow">项目已有声音</span><h2 id="project-name">正在读取项目</h2></div><button id="new-voice" type="button" class="quiet">添加声音</button></div>
    <div id="voice-list" role="region" aria-label="项目音色列表" tabindex="0"></div>
    <div id="undo-area" hidden><span id="undo-message"></span><button id="undo-delete" type="button" class="quiet">撤销删除</button></div>
    <section class="assignment-section" aria-labelledby="assignment-title">
      <div class="section-heading"><span class="section-number">02</span><h2 id="assignment-title">声音分配</h2></div>
      <section id="defaults-section" class="defaults-section" aria-label="项目默认设置"></section>
      <section class="requirements-section" aria-labelledby="requirements-title"><div class="requirements-heading"><h3 id="requirements-title">当前任务需求</h3><p id="role-context" class="small"></p></div><div id="role-strip" class="role-strip" role="region" aria-label="当前任务角色独立水平滚动" tabindex="0"></div></section>
    </section>
    <div class="completion"><button id="complete-settings" type="button" class="primary">完成设置 <span aria-hidden="true">→</span></button><p id="complete-reason" class="small"></p><p id="operation-status" role="status" aria-live="polite"></p><p id="operation-error" role="alert"></p><button id="reload-config" class="text-button" type="button">重新读取项目</button></div>
    <section id="answer-receipt" hidden><h3>配置已模拟提交</h3><p id="assignment-summary" class="small"></p></section>
  </section>
  <section class="panel editor-panel" aria-label="声音配置工具"><div class="tabs" role="tablist" aria-label="项目声音工具"><button id="tab-add" role="tab" aria-controls="panel-add" type="button">添加项目声音</button><button id="tab-settings" role="tab" aria-controls="panel-settings" type="button">声音设置</button><button id="tab-tools" role="tab" aria-controls="panel-tools" type="button">More Tools</button></div>
    <div id="panel-add" class="tool-panel" role="tabpanel" aria-labelledby="tab-add"><div class="add-content"><div class="section-heading"><h2>添加项目声音</h2><span class="eyebrow">01 / ADD</span><p class="provider-link"><a id="provider-link" class="official-link" target="_blank" rel="noopener noreferrer">前往厂商官网 ↗</a></p></div>
      <div class="identity-grid"><div class="provider-field"><label for="provider">声音厂商</label><select id="provider"></select><p id="provider-support" class="small"></p><p id="provider-help" class="small muted"></p></div><div class="model-field"><label for="voice-model">模型选择</label><select id="voice-model" aria-describedby="model-help"></select><div class="provider-action-row"><button id="reload-providers" class="text-button" type="button">重新读取模型</button><small id="model-help" class="status-warning"></small></div></div>
      <div class="name-field"><label for="voice-name">项目声音名称</label><input id="voice-name" maxlength="120" autocomplete="off" placeholder="例如：教程旁白"></div><div class="category-field"><label for="voice-category">声音分类</label><select id="voice-category"><option value="">请选择分类</option><option value="male">男声</option><option value="female">女声</option><option value="other">其他</option></select></div><div class="id-field"><label for="voice-id" id="voice-id-label">Voice ID</label><input id="voice-id" maxlength="256" autocomplete="off" spellcheck="false" aria-describedby="voice-id-help"><small id="voice-id-help"></small></div></div>
      <div id="add-parameters" aria-label="添加声音参数"></div></div><div class="add-footer save-actions"><p id="add-feedback" role="status" aria-live="polite"></p><button id="reset-draft" type="button" aria-label="清空此厂商草稿">清空草稿</button><button id="save-alias" type="button" class="blue-button">添加到项目库</button></div>
    </div><div id="panel-settings" class="tool-panel" role="tabpanel" aria-labelledby="tab-settings" hidden></div><div id="panel-tools" class="tool-panel" role="tabpanel" aria-labelledby="tab-tools" hidden><h2>More Tools</h2><p class="muted">预留工具区域 · 暂未提供功能</p></div>
  </section>
  <dialog id="add-error-dialog" role="alertdialog" aria-labelledby="add-error-title" aria-describedby="add-error-message"><button id="close-add-error" type="button" aria-label="关闭错误提示">×</button><span class="eyebrow">PLEASE CHECK</span><h2 id="add-error-title">未能添加声音</h2><p id="add-error-message"></p><button id="dismiss-add-error" type="button" class="blue-button" autofocus>返回修改</button></dialog>
  <dialog id="confirm-dialog" aria-labelledby="confirm-title"><h2 id="confirm-title"></h2><p id="confirm-copy"></p><p id="confirm-detail" class="small"></p><label id="restore-name-field" hidden>恢复后的名称<input id="restore-name" maxlength="120" autocomplete="off"></label><p id="dialog-error" class="danger" role="status"></p><div class="dialog-actions"><button id="cancel-confirm" type="button" autofocus>取消</button><button id="discard-edit" type="button" hidden>放弃并切换</button><button id="confirm-save" type="button" class="primary">确认</button></div></dialog>`;
  const get = id => root.querySelector(`#${id}`), dialog = get('confirm-dialog'); containDialogFocus(dialog);
  const addErrorDialog = get('add-error-dialog'); containDialogFocus(addErrorDialog);
  const dismissAddError = () => { addErrorDialog.close(); store.update({ addError: null }); const errors = store.getState().draftErrors; get(errors.category ? 'voice-category' : errors.name ? 'voice-name' : errors.model ? 'voice-model' : errors.speed ? 'add-speed' : errors.pitch ? 'add-pitch' : 'voice-id').focus(); };
  get('dismiss-add-error').onclick = dismissAddError; get('close-add-error').onclick = dismissAddError;
  addErrorDialog.oncancel = event => { event.preventDefault(); dismissAddError(); };
  const configButton = document.createElement('button'); configButton.id = 'open-provider-config'; configButton.type = 'button'; configButton.className = 'text-button'; configButton.textContent = '打开配置文件';
  const configStatus = document.createElement('p'); configStatus.id = 'provider-config-status'; configStatus.className = 'small'; configStatus.setAttribute('role', 'status');
  const configRow = document.createElement('div'); configRow.className = 'provider-action-row';
  configRow.append(configButton, get('provider-support'));
  get('provider').after(configRow, configStatus);
  configButton.onclick = async () => {
    if (store.getState().configOpening) return;
    const provider = store.getState().draft.provider; configStatus.textContent = '';
    store.update({ configOpening: true });
    try {
      const result = await openProviderConfig(provider);
      if (store.getState().draft.provider === provider) configStatus.textContent = `${store.getState().providers.find(p => p.id === provider)?.config_edit?.environment === 'test' ? '测试配置：' : ''}${result.message}`;
      log.record({ name: 'provider.config.open', objectId: provider, result: result.created ? '已新建模板并请求打开' : '已请求打开现有配置' });
    } catch (error) {
      if (store.getState().draft.provider === provider) configStatus.textContent = error.message;
      log.record({ name: 'provider.config.open', objectId: provider, result: '失败', error: error.message });
    } finally { store.update({ configOpening: false }); }
  };
  mountSections(root, store, controller, log, player); mountDefaults(get('defaults-section'), store, controller); mountSettings(get('panel-settings'), store, controller, player); mountAddParameters(get('add-parameters'), store);
  const fields = { 'voice-name': 'name', 'voice-id': 'voiceId', 'voice-model': 'model', 'voice-category': 'category' };
  for (const [id, field] of Object.entries(fields)) get(id).addEventListener(['voice-model', 'voice-category'].includes(id) ? 'change' : 'input', () => store.edit(field, get(id).value));
  get('provider').onchange = () => { configStatus.textContent = ''; store.switchProvider(get('provider').value); void controller.refreshProviders(); };
  get('reload-providers').onclick = () => { void controller.refreshProviders(); };
  const tabs = ['add', 'settings', 'tools'];
  for (const key of tabs) { get(`tab-${key}`).onclick = () => store.update({ activeTab: key }); get(`tab-${key}`).onkeydown = event => { let index = tabs.indexOf(key); if (event.key === 'ArrowLeft') index = (index + 2) % 3; else if (event.key === 'ArrowRight') index = (index + 1) % 3; else if (event.key === 'Home') index = 0; else if (event.key === 'End') index = 2; else return; event.preventDefault(); store.update({ activeTab: tabs[index] }); get(`tab-${tabs[index]}`).focus(); }; }
  get('new-voice').onclick = () => { store.update({ activeTab: 'add' }); get('voice-name').focus(); };
  get('save-alias').onclick = () => { void controller.addVoice(); }; get('reset-draft').onclick = () => store.resetDraft();
  get('reload-config').onclick = () => { void controller.load(); }; get('complete-settings').onclick = () => { void controller.submit(); };
  get('undo-delete').onclick = () => controller.undoDelete();
  const cancel = () => store.update({ confirmation: null, error: '' }); get('cancel-confirm').onclick = cancel; dialog.oncancel = event => { event.preventDefault(); cancel(); };
  get('discard-edit').onclick = () => controller.discardAndSwitch();
  get('confirm-save').onclick = () => { const pending = store.getState().confirmation; if (!pending) return;
    if (pending.kind === 'defaults') void controller.confirmDefaults();
    if (pending.kind === 'delete') void controller.deleteVoice(pending.id, pending.revision);
    if (pending.kind === 'switch-edit') void controller.saveAndSwitch();
    if (pending.kind === 'category') void controller.saveSettings(true, pending.proposal.nextId);
    if (pending.kind === 'restore-name') void controller.restoreVoice(pending.id, get('restore-name').value);
  };
  const options = (node, values) => { const key = JSON.stringify(values); if (node.dataset.options !== key) { node.dataset.options = key; node.replaceChildren(...values.map(([value, name]) => { const option = document.createElement('option'); option.value = value; option.textContent = name; return option; })); } };
  let pendingKey = '';
  const render = state => {
    get('project-name').textContent = state.data?.project.name ?? '正在读取项目';
    for (const key of tabs) { get(`tab-${key}`).setAttribute('aria-selected', String(state.activeTab === key)); get(`tab-${key}`).tabIndex = state.activeTab === key ? 0 : -1; get(`panel-${key}`).hidden = state.activeTab !== key; }
    const provider = state.providers.find(item => item.id === state.draft.provider);
    configButton.disabled = !!state.configOpening || state.busy || !provider || provider.config_edit?.available === false;
    configButton.textContent = state.configOpening ? '正在打开…' : '打开配置文件';
    configButton.title = provider?.config_edit?.reason || '打开当前厂商配置；缺失时创建模板，不覆盖已有文件';
    options(get('provider'), state.providers.map(item => [item.id, item.id === 'volcengine' ? `${item.name}【等待开发】` : item.name])); get('provider').value = state.draft.provider;
    options(get('voice-model'), [['', provider?.models.length ? '请选择模型' : '该厂商尚未配置可选模型'], ...(provider?.models ?? []).map(item => [item.id, item.name])]);
    for (const [id, key] of Object.entries(fields)) { const input = get(id); if (input.value !== String(state.draft[key])) input.value = state.draft[key]; input.disabled = state.busy; }
    get('provider').disabled = state.busy || !state.providers.length;
    get('provider-support').textContent = provider?.config_edit?.environment === 'test' ? '测试配置' : provider?.id === 'fake' ? '离线静音测试，不是真实配音' : provider?.id === 'volcengine' ? (provider?.config_edit?.available ? '合成待接入' : '配置支持待接入') : ''; get('provider-help').textContent = '';
    get('provider-support').classList.toggle('status-warning', provider?.id === 'volcengine');
    get('model-help').textContent = provider?.models.length ? '' : '尚未配置模型';
    get('voice-id-label').textContent = provider?.identifier_label ?? 'Voice ID / 音色标识'; get('voice-id-help').textContent = provider?.identifier_hint ?? '粘贴对应厂商的音色标识';
    get('provider-link').href = provider?.url ?? 'https://www.minimax.cn/audio'; get('provider-link').textContent = `前往 ${provider?.name ?? '厂商'} ↗`;
    for (const id of ['new-voice', 'save-alias', 'reset-draft', 'reload-providers', 'reload-config']) get(id).disabled = state.busy || !state.data;
    let reason = ''; try { if (!state.data) throw new Error('正在读取配置'); if (state.needsRefresh) throw new Error('请先重新读取项目'); if (!(state.data.mode === 'persistent' && !state.data.question)) buildAnswer(state); if (state.data.question?.status === 'answered') throw new Error(state.data.question.claimed ? '回答已被领取，请在 Agent 中查看任务' : '回答已保存，等待 Agent 领取'); } catch (error) { reason = error.message; }
    get('complete-settings').disabled = state.busy || !!reason || !!state.receipt?.session_complete;
    get('complete-settings').textContent = state.submitting ? '正在保存并通知聊天…' : state.receipt?.session_complete ? '绑定已完成，服务已断开，请关闭此页面' : '完成设置 →'; get('complete-settings').setAttribute('aria-busy', String(state.busy)); get('complete-reason').textContent = reason;
    get('operation-status').textContent = state.submitting ? '正在保存绑定并发送完成消息，请稍候，无需重复点击。' : state.busy ? '正在处理…' : state.message; get('operation-error').textContent = state.addError ? '' : state.error;
    const addFields = { provider: get('provider'), model: get('voice-model'), name: get('voice-name'), category: get('voice-category'), voiceId: get('voice-id'), speed: get('add-speed'), pitch: get('add-pitch') }, liveErrors = validateNewVoiceFields(state.draft, state.providers, state.data), requiredFields = new Set(['model', 'name', 'category', 'voiceId']);
    for (const [field, input] of Object.entries(addFields)) {
      const invalid = !!liveErrors[field] && (!!state.draftTouched?.[field] || requiredFields.has(field));
      input.setAttribute('aria-invalid', String(invalid));
      const label = field === 'speed' || field === 'pitch' ? get(`add-${field}-control`).querySelector('legend') : root.querySelector(`label[for="${input.id}"]`);
      label?.classList.toggle('field-invalid', invalid);
    }
    get('add-feedback').textContent = state.message === '已添加项目声音' ? state.message : '';
    get('add-feedback').classList.remove('danger');
    get('undo-area').hidden = !state.undo; get('undo-message').textContent = state.undo ? `“${state.undo.name}”已从项目库隐藏。` : ''; get('undo-delete').disabled = state.busy;
    get('answer-receipt').hidden = !state.receipt; get('assignment-summary').textContent = (state.receipt?.summary ?? (Array.isArray(state.receipt?.answer?.assignments) ? state.receipt.answer.assignments : [])).map(role => `${role.role_name}：${role.snapshot?.name ?? '可选未分配'}${role.via ? `（${role.via}）` : ''}`).join('；') ?? '';
    get('answer-receipt').querySelector('h3').textContent = state.data?.mode === 'persistent' ? (state.data.question ? '回答已保存，等待 Agent 领取' : '项目管理已完成') : '配置已模拟提交';
    get('project-name').title = state.data?.project.path ?? '';
    get('provider-link').hidden = !provider?.url;
    root.setAttribute('aria-busy', String(state.busy));
    const pending = state.confirmation;
    get('add-error-message').textContent = state.addError ?? '';
    if (state.addError && !pending) { if (!addErrorDialog.open) addErrorDialog.showModal(); }
    else if (addErrorDialog.open) addErrorDialog.close();
    if (!pending) { pendingKey = ''; if (dialog.open) dialog.close(); return; }
    const nextKey = JSON.stringify(pending); get('dialog-error').textContent = state.error;
    if (nextKey !== pendingKey) {
      pendingKey = nextKey; get('restore-name-field').hidden = pending.kind !== 'restore-name'; get('discard-edit').hidden = pending.kind !== 'switch-edit';
      let title = '', copy = '', detail = '', action = '';
      if (pending.kind === 'defaults') { title = '确认保存默认设置'; copy = '只保存项目默认引用，不改当前任务的明确分配或历史快照。'; detail = ['general', 'male', 'female'].map(slot => `${slotNames[slot]}：${defaultVoice(state.data, slot)?.name ?? '未设置'} → ${defaultVoice(state.data, slot, pending.defaults)?.name ?? '未设置'}`).join('；'); action = '确认保存默认'; }
      if (pending.kind === 'delete') { title = '确认从项目库隐藏'; copy = '已有任务保留，后续默认不再使用。记录、引用及试听文件都不会物理删除。'; detail = `当前角色引用：${pending.refs.roles.join('、') || '无'}；默认引用：${pending.refs.defaults.map(slot => slotNames[slot]).join('、') || '无'}；历史引用：${pending.refs.history}。`; action = '确认软删除'; }
      if (pending.kind === 'switch-edit') { title = '当前声音有未保存修改'; copy = '保存后切换，或明确放弃本次编辑。添加表单草稿保持不变。'; action = '保存并切换'; }
      if (pending.kind === 'category') { title = '分类变化影响默认显示'; copy = `${pending.affected.map(slot => slotNames[slot]).join('、')}将显示“未设置”；旧引用仍保留，不替换其他声音。`; detail = '当前任务明确分配不换声音，历史快照不变。'; action = '确认保存修改'; }
      if (pending.kind === 'restore-name') { title = '撤销遇到活动名称冲突'; copy = '请为恢复的旧声音指定另一名称；不会覆盖新声音。'; action = '改名并恢复'; get('restore-name').value = pending.suggested; }
      get('confirm-title').textContent = title; get('confirm-copy').textContent = copy; get('confirm-detail').textContent = detail; get('confirm-save').textContent = action;
    }
    get('confirm-save').disabled = state.busy; if (!dialog.open) dialog.showModal();
  };
  render(store.getState()); return store.subscribe(render);
}
