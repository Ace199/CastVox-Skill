import { containDialogFocus } from './dialog-focus.js';
import { defaultSaveBlocker } from '../editor.js';
import { selectionGender } from '../voice-presentation.js';

export function defaultIsDirty(state) {
  return JSON.stringify(state.projectDefault.draft) !== JSON.stringify(state.projectDefault.saved);
}

export function mountRequirements(section, context, store, log) {
  section.innerHTML = `<div class="requirements-heading"><span class="eyebrow">02 / 当前需求</span><h2 id="requirements-title">为角色找到声音</h2></div>
    <div class="requirements"><button type="button" class="default-voice" id="default-target" aria-pressed="false">★ 默认声音<small>项目持久默认</small><small id="default-label">尚未设置</small></button><div id="roles" class="role-strip" role="region" aria-label="角色列表，横向滚动" tabindex="0"></div></div>
    <p id="requirements-status" class="muted" role="status">选择一个角色，再点击上方项目音色卡片。</p><button type="button" id="complete-settings" aria-describedby="complete-hint">完成设置 <span aria-hidden="true">→</span></button><small id="complete-hint">提交本次角色配置 · 通知 Harness（Mock）</small>
    <dialog id="default-confirmation" aria-labelledby="default-confirm-title"><h2 id="default-confirm-title">确认保存项目默认声音</h2><label id="quick-default-field">选择项目声音<select id="quick-default-voice" aria-label="默认声音候选"></select></label><p id="default-diff"></p><p>使用所选项目声音的已保存参数；不会应用设置面板的未保存草稿。</p><p>这是项目持久默认的 Mock 保存，不会写入真实文件；刷新后重置。当前任务已分配角色保持原配置。</p><p id="quick-default-error" role="status"></p><div class="dialog-actions"><button id="default-cancel" type="button" autofocus>返回编辑</button><button id="default-confirm" type="button">确认保存（Mock）</button></div></dialog>`;
  context.innerHTML = `<p id="target-context" class="muted"></p><div id="default-actions" hidden><p id="default-draft-status"></p><button id="default-save" type="button">预览保存项目默认</button><button id="default-discard" type="button">放弃默认草稿</button><p class="muted">仅 Mock 保存，刷新重置，不写真实项目文件。</p></div>`;
  const roles = section.querySelector('#roles');
  const dialog = section.querySelector('dialog');
  containDialogFocus(dialog);
  const recordAction = (type, name, objectId) => {
    try { store.dispatch({ type }); log.record({ name, objectId, result: type === 'CONFIRM_DEFAULT_SAVE' ? '项目默认已保存到 Mock 内存；未修改任务绑定' : '已更新 Mock 默认草稿状态' }); }
    catch (error) { log.record({ name, objectId, result: '失败', error }); section.querySelector('#requirements-status').textContent = error.message; }
  };
  const selectRole = (id, focus = false) => {
    store.dispatch({ type: 'SELECT_ROLE', roleId: id });
    log.record({ name: 'requirements.role.select', objectId: id, result: '已选中当前任务角色，保留其独立绑定与参数' });
    const button = [...roles.querySelectorAll('button')].find(item => item.dataset.roleId === id);
    button?.scrollIntoView({ block: 'nearest', inline: 'nearest' });
    if (focus) button?.focus({ preventScroll: true });
  };
  section.querySelector('#default-target').onclick = () => recordAction('QUICK_DEFAULT_OPEN', 'requirements.default.quick.open', store.getState().data.project.id);
  section.querySelector('#quick-default-voice').onchange = event => {
    store.dispatch({ type: 'QUICK_DEFAULT_VOICE', voiceId: event.target.value });
    log.record({ name: 'requirements.default.quick.choose', objectId: event.target.value, result: '仅更新弹窗候选，等待确认' });
  };
  context.querySelector('#default-save').onclick = () => recordAction('REQUEST_DEFAULT_SAVE', 'requirements.default.preview', store.getState().data.project.id);
  context.querySelector('#default-discard').onclick = () => recordAction('DISCARD_DEFAULT_DRAFT', 'requirements.default.discard', store.getState().data.project.id);
  const cancelDefault = () => recordAction(store.getState().projectDefault.quick ? 'QUICK_DEFAULT_CANCEL' : 'CANCEL_DEFAULT_SAVE', 'requirements.default.cancel', store.getState().data.project.id);
  section.querySelector('#default-cancel').onclick = cancelDefault;
  section.querySelector('#default-confirm').onclick = () => {
    section.querySelector('#quick-default-error').textContent = '';
    try { const type = store.getState().projectDefault.quick ? 'QUICK_DEFAULT_CONFIRM' : 'CONFIRM_DEFAULT_SAVE'; store.dispatch({ type }); log.record({ name: 'requirements.default.saved', objectId: store.getState().data.project.id, result: '项目默认已保存到 Mock 内存，未修改任务角色或编辑器' }); }
    catch (error) { section.querySelector('#quick-default-error').textContent = error.message; log.record({ name: 'requirements.default.failed', objectId: store.getState().data.project.id, result: '保存被拒绝', error }); }
  };
  dialog.addEventListener('cancel', event => { event.preventDefault(); cancelDefault(); });
  const voiceName = (state, id) => state.data?.voices.find(item => item.id === id)?.name ?? state.catalog.voices.find(item => item.id === id)?.name ?? Object.values(state.task.selections).find(item => item.voiceId === id)?.voiceName ?? state.projectDefault.saved?.voiceName ?? '尚未设置';
  const params = selection => `语速 ${selection.parameters.speed} · 音量 ${selection.parameters.volume} · 情绪 ${selection.parameters.emotion}`;
  const render = (state, action) => {
    if (!action || action === 'LOAD_SUCCESS') {
      roles.replaceChildren();
      const list = state.task.jobId ? state.data?.roles ?? [] : [];
      list.forEach((role, index) => {
        const button = document.createElement('button'); button.type = 'button'; button.className = 'role-card'; button.dataset.roleId = role.id; button.title = role.name;
        const name = document.createElement('span'); name.className = 'role-name'; name.textContent = `${index + 1} ${role.name}`;
        const binding = document.createElement('small'); binding.className = 'role-binding';
        const avatar = document.createElement('img'); avatar.className = 'role-avatar'; avatar.src = state.task.avatars[role.id]; avatar.alt = ''; avatar.width = 36; avatar.height = 36;
        button.append(avatar, name, binding); button.onclick = () => selectRole(role.id);
        button.addEventListener('keydown', event => {
          const next = { ArrowRight: Math.min(index + 1, list.length - 1), ArrowLeft: Math.max(index - 1, 0), Home: 0, End: list.length - 1 }[event.key];
          if (next === undefined) return;
          event.preventDefault(); selectRole(list[next].id, true);
          if (event.key === 'Home') roles.scrollLeft = 0;
          if (event.key === 'End') roles.scrollLeft = roles.scrollWidth;
        });
        roles.append(button);
      });
      if (!list.length) { const empty = document.createElement('p'); empty.className = 'role-empty'; empty.textContent = '当前无任务角色，仍可管理项目默认声音。'; roles.append(empty); }
    }
    for (const button of roles.querySelectorAll('button')) {
      const selection = state.task.selections[button.dataset.roleId];
      const role = state.data.roles.find(item => item.id === button.dataset.roleId);
      const active = state.ui.target?.kind === 'role' && state.ui.target.roleId === role.id;
      button.dataset.gender = selection.voiceId ? selectionGender(state, selection) : 'other';
      button.setAttribute('aria-pressed', String(active)); button.classList.toggle('target-selected', active);
      button.classList.toggle('is-assigned', !!selection.voiceId);
      const status = selection.voiceId ? `✓ 已分配 · ${selection.voiceName ?? voiceName(state, selection.voiceId)}` : '○ 未分配';
      button.querySelector('.role-binding').textContent = status;
      button.setAttribute('aria-label', `角色 ${role.name}，${status}`);
      button.title = `${role.name} / ${status} / ${params(selection)}`;
    }
    const isDefault = state.ui.target?.kind === 'default';
    const dirty = defaultIsDirty(state);
    const defaultButton = section.querySelector('#default-target');
    defaultButton.setAttribute('aria-pressed', String(isDefault)); defaultButton.classList.toggle('target-selected', isDefault);
    section.querySelector('#default-label').textContent = `${voiceName(state, state.projectDefault.saved?.voiceId)}${dirty ? ' · 有未保存修改' : state.projectDefault.saved ? ' · Mock 已保存' : ''}`;
    defaultButton.title = `项目持久默认：${section.querySelector('#default-label').textContent}；修改需确认保存`;
    const selection = state.ui.target?.kind === 'role' ? state.task.selections[state.ui.target.roleId] : state.projectDefault.draft;
    const role = state.data?.roles?.find(item => item.id === state.ui.target?.roleId);
    context.querySelector('#target-context').textContent = !state.ui.target ? '选择需求角色，或选择项目默认声音。' : `${isDefault ? '项目默认草稿（独立保存）' : `当前任务角色：${role.name}`} · ${selection?.voiceName ?? voiceName(state, selection?.voiceId)}${selection ? ` / ${params(selection)}` : ''}`;
    context.querySelector('#default-actions').hidden = !isDefault;
    context.querySelector('#default-draft-status').textContent = dirty ? `待保存：${voiceName(state, state.projectDefault.draft?.voiceId)}` : '没有未保存修改';
    context.querySelector('#default-save').disabled = !dirty || !state.projectDefault.draft?.voiceId || !!defaultSaveBlocker(state);
    context.querySelector('#default-save').title = defaultSaveBlocker(state);
    context.querySelector('#default-discard').disabled = !dirty;
    section.querySelector('#requirements-status').textContent = !state.ui.target ? '选择一个角色，再点击上方项目音色卡片。' : isDefault ? '当前修改项目默认草稿，需要明确确认保存。' : `${role.name}：${selection.voiceId ? `已分配 ${selection.voiceName ?? voiceName(state, selection.voiceId)}` : '等待分配'} · 仅影响当前任务`;
    const quick = state.projectDefault.quick;
    section.querySelector('#quick-default-field').hidden = !quick;
    if (quick) {
      const select = section.querySelector('#quick-default-voice');
      const ids = JSON.stringify(state.data.voices.map(voice => [voice.id, voice.name, voice.availability]));
      if (select.dataset.options !== ids) {
        select.dataset.options = ids; select.replaceChildren(...state.data.voices.map(voice => { const option = document.createElement('option'); option.value = voice.id; option.textContent = voice.name; option.disabled = voice.availability === 'unavailable'; return option; }));
      }
      select.value = quick.voiceId ?? '';
      const voice = state.data.voices.find(item => item.id === quick.voiceId);
      section.querySelector('#default-confirm').disabled = !voice || voice.availability === 'unavailable';
      section.querySelector('#default-diff').textContent = `${voiceName(state, state.projectDefault.saved?.voiceId)} → ${voice?.name ?? '项目库暂无可选声音'} / 仅修改项目默认`;
      if (!dialog.open) { section.querySelector('#quick-default-error').textContent = ''; dialog.showModal(); }
    } else if (state.projectDefault.confirmation && !dialog.open) {
      section.querySelector('#default-confirm').disabled = false;
      section.querySelector('#default-diff').textContent = `${voiceName(state, state.projectDefault.saved?.voiceId)} → ${voiceName(state, state.projectDefault.confirmation.proposal.voiceId)} / ${params(state.projectDefault.confirmation.proposal)}`;
      dialog.showModal();
    } else if (!state.projectDefault.confirmation && dialog.open) dialog.close();
  };
  render(store.getState());
  return store.subscribe(render);
}
