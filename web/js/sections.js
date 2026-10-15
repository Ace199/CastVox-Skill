import { activeVoices, previewStatus, resolveRole, defaultVoice, slots, slotNames } from './voice-model.js';
import { voicePortrait } from './avatars.js';
const element = (tag, className, value) => { const node = document.createElement(tag); node.className = className; if (value !== undefined) node.textContent = value; return node; };
const button = (className, label, value) => { const node = element('button', className, value); node.type = 'button'; node.setAttribute('aria-label', label); return node; };
const portrait = (file, className = 'voice-avatar') => { const frame = element('span', `avatar-frame ${className}-frame`), img = element('img', className); img.src = `assets/${file}`; img.alt = ''; img.width = 44; img.height = 44; frame.append(img); return frame; };
export function mountSections(root, store, controller, log, player) {
  const list = root.querySelector('#voice-list'), strip = root.querySelector('#role-strip');
  let librarySignature = '', roleSignature = ''; const timers = new Map();
  const detail = element('aside', 'role-detail'); detail.id = 'role-detail'; detail.setAttribute('popover', 'auto'); detail.setAttribute('aria-labelledby', 'role-detail-title'); root.append(detail);
  const showDetail = (id, anchor) => {
    const role = store.getState().roles.find(item => item.id === id); if (!role) return;
    const title = element('h3', '', role.name); title.id = 'role-detail-title';
    const content = element('div', 'role-detail-content');
    content.tabIndex = 0;
    content.setAttribute('aria-label', '角色信息');
    const columns = element('div', 'role-detail-columns');
    const appearance = element('section', 'role-detail-section');
    appearance.append(element('strong', '', '角色形象'), element('p', '', role.description || '暂无角色形象信息'));
    const recommendation = element('section', 'role-detail-section');
    recommendation.append(element('strong', '', '推荐声音'), element('p', '', role.voice_recommendation || '暂无推荐声音信息'));
    columns.append(appearance, recommendation);
    content.append(title, columns);
    const close = button('role-detail-close', '关闭角色信息', '×');
    close.onclick = () => { detail.hidePopover(); anchor.focus({ preventScroll: true }); };
    detail.replaceChildren(content, close);
    detail.showPopover();
    const box = anchor.getBoundingClientRect(), height = detail.offsetHeight, width = detail.offsetWidth;
    // The supplied artwork's tip sits at 13% / 85.6% of its canvas.
    const flipped = box.left + 32 > innerWidth - width * .87 - 12;
    detail.classList.toggle('tip-right', flipped);
    const tipX = width * (flipped ? .87 : .13);
    detail.style.left = `${Math.max(8, Math.min(box.left + box.width / 2 - tipX, innerWidth - width - 8))}px`;
    detail.style.top = `${Math.max(8, box.top - height * .856)}px`;
    log.record({ name: 'task.role.details', objectId: id, result: '查看角色形象与推荐声音' });
  };
  const dismissDetail = event => { if (!(event.target instanceof Node && detail.contains(event.target)) && detail.matches(':popover-open')) detail.hidePopover(); };
  window.addEventListener('resize', dismissDetail);
  document.addEventListener('scroll', dismissDetail, true);
  const clearTimers = () => { for (const timer of timers.values()) clearTimeout(timer); timers.clear(); };
  const render = state => {
    const signature = JSON.stringify(state.data?.voices);
    if (signature !== librarySignature) {
      librarySignature = signature; clearTimers(); const offset = list.querySelector('.library-scroll')?.scrollLeft ?? 0;
      const focused = document.activeElement?.closest('.project-voice-card')?.dataset.voiceId, focusClass = document.activeElement?.className;
      list.replaceChildren(); list.className = 'project-library';
      const labels = element('div', 'library-labels'), scroll = element('div', 'library-scroll'); scroll.tabIndex = 0; scroll.setAttribute('role', 'region'); scroll.setAttribute('aria-label', '项目声音三行共用水平滚动');
      const voices = activeVoices(state.data);
      for (const [category, label] of [['male', '男声'], ['female', '女声'], ['other', '其他']]) {
        labels.append(element('strong', 'row-label', label)); const row = element('div', 'library-row'); row.dataset.category = category;
        for (const voice of voices.filter(item => item.category === category)) {
          const card = element('article', 'project-voice-card'); card.dataset.voiceId = voice.id;
          const body = button('voice-body', `分配声音：${voice.name}`), marker = element('span', 'voice-role-markers'), avatar = portrait(voicePortrait(voice.id, voice.category));
          const name = element('span', 'voice-name', voice.name), labelBox = element('span', 'voice-label'); labelBox.append(name, element('small', 'card-preview-status')); body.append(marker, avatar, labelBox); body.title = `${voice.name} / ${voice.source.provider} / ${voice.source.model} / ${voice.source.voice_id}`;
          body.onclick = () => { const before = store.getState(); store.assign(voice.id); log.record({ name: before.activeDefaultSlot ? 'defaults.draft.selected' : 'task.voice.assign', objectId: voice.id, result: before.activeDefaultSlot ? '仅更新默认草稿，需显式确认保存；角色未改变' : before.activeRoleId ? '仅分配当前角色，默认不变' : '未选角色，没有分配' }); };
          const play = button('voice-preview', `播放 ${voice.name}`, '▶'); play.onclick = event => { event.stopPropagation(); void player.toggle(voice.id); };
          const settings = button('voice-settings', `设置 ${voice.name}`, '⚙'); settings.onclick = event => { event.stopPropagation(); controller.openSettings(voice.id); if (matchMedia('(max-width:950px)').matches) root.querySelector('.editor-panel').scrollIntoView({ block: 'start' }); };
          const remove = button('voice-delete', `删除 ${voice.name}`, '×'); remove.title = '仅从项目库隐藏；键盘也可按 Delete'; remove.onclick = event => { event.stopPropagation(); controller.requestDelete(voice.id); };
          card.append(body, play, settings, remove);
          card.addEventListener('pointerenter', event => { if (event.pointerType === 'touch') return; const old = timers.get(voice.id); if (old) clearTimeout(old); timers.set(voice.id, setTimeout(() => { card.classList.add('delete-visible'); timers.delete(voice.id); }, 2000)); });
          card.addEventListener('pointerleave', () => { clearTimeout(timers.get(voice.id)); timers.delete(voice.id); card.classList.remove('delete-visible'); });
          card.addEventListener('keydown', event => { if (event.key === 'Delete') { event.preventDefault(); event.stopPropagation(); controller.requestDelete(voice.id); } });
          row.append(card);
        }
        if (!row.children.length) row.append(element('span', 'library-empty', `暂无${label}项目声音`)); scroll.append(row);
      }
      list.append(labels, scroll); scroll.scrollLeft = offset;
      if (focused && focusClass) [...list.querySelectorAll('.project-voice-card')].find(card => card.dataset.voiceId === focused)?.querySelector(`.${focusClass.split(' ')[0]}`)?.focus({ preventScroll: true });
    }
    for (const card of list.querySelectorAll('.project-voice-card')) {
      const voice = state.data.voices[card.dataset.voiceId], numbers = state.roles.flatMap((role, index) => role.assignment?.project_voice_id === voice.id ? [index + 1] : []);
      const defaultSlots = slots.filter(slot => defaultVoice(state.data, slot, state.defaultsDraft)?.id === voice.id);
      if (card.dataset.defaultSlots !== defaultSlots.join(' ')) {
        card.dataset.defaultSlots = defaultSlots.join(' ');
        card.querySelectorAll('.default-voice-outline').forEach(node => node.remove());
        defaultSlots.forEach((slot, index) => {
          const outline = element('span', 'default-voice-outline');
          outline.dataset.slot = slot;
          outline.style.setProperty('--outline-layer', index);
          outline.setAttribute('aria-hidden', 'true');
          card.append(outline);
        });
      }
      card.querySelector('.voice-body').setAttribute('aria-label', `分配声音：${voice.name}${defaultSlots.length ? `（${defaultSlots.map(slot => slotNames[slot]).join('、')}）` : ''}`);
      card.dataset.gender = voice.category;
      card.classList.toggle('has-assignment', state.roles.some(role => {
        const resolved = resolveRole(state, role);
        return !resolved.error && resolved.project_voice_id === voice.id;
      }));
      const marker = card.querySelector('.voice-role-markers'); marker.textContent = numbers.join('·'); marker.classList.toggle('is-unbound', !numbers.length); marker.setAttribute('aria-label', numbers.length ? `明确分配角色 ${numbers.join('、')}` : '未明确分配');
      card.classList.toggle('is-selected', state.selectedVoiceId === voice.id); card.querySelector('.voice-body').setAttribute('aria-pressed', String(state.selectedVoiceId === voice.id));
      const status = previewStatus(voice, state.player), play = card.querySelector('.voice-preview');
      const playing = state.player.voiceId === voice.id && state.player.status === 'playing'; play.disabled = state.busy || !status.playable; play.textContent = playing ? 'Ⅱ' : '▶'; play.setAttribute('aria-label', `${playing ? '暂停' : '播放'} ${voice.name}`); play.setAttribute('aria-pressed', String(playing)); play.title = status.text;
      const text = status.kind === 'stale' ? '调整前试听' : status.kind === 'unavailable' ? '文件不可用' : status.kind === 'none' ? '无试听' : voice.preview.mock ? '示例试听' : '可试听';
      card.querySelector('.card-preview-status').textContent = text;
      for (const node of card.querySelectorAll('.voice-body,.voice-settings,.voice-delete')) node.disabled = state.busy;
      const ineligible = state.activeDefaultSlot && state.activeDefaultSlot !== 'general' && voice.category !== state.activeDefaultSlot;
      card.querySelector('.voice-body').disabled = state.busy || !!ineligible;
      card.classList.toggle('default-ineligible', !!ineligible);
    }
    const roles = state.data?.question ? state.roles : [], nextRoles = JSON.stringify(roles.map(role => [role.id, role.name, role.avatar]));
    if (nextRoles !== roleSignature) {
      roleSignature = nextRoles; const offset = strip.scrollLeft; strip.replaceChildren();
      roles.forEach((role, index) => { const item = button('role-card', `角色 ${role.name}`); item.dataset.roleId = role.id; item.append(element('span', 'role-avatar unknown-avatar'), element('span', 'role-name', `${index + 1} ${role.name}`), element('small', 'role-binding'));
        item.onclick = () => { store.selectRole(role.id); item.scrollIntoView({ block: 'nearest', inline: 'nearest' }); };
        item.ondblclick = () => showDetail(role.id, item);
        item.setAttribute('aria-keyshortcuts', 'F2'); item.setAttribute('aria-description', '双击或按 F2 查看角色形象与推荐声音');
        item.addEventListener('keydown', event => { if (event.key === 'F2') { event.preventDefault(); showDetail(role.id, item); } });
        item.onkeydown = event => { const next = { ArrowRight: Math.min(index + 1, roles.length - 1), ArrowLeft: Math.max(0, index - 1), Home: 0, End: roles.length - 1 }[event.key]; if (next === undefined) return; event.preventDefault(); const target = strip.querySelectorAll('button')[next]; target.click(); target.focus({ preventScroll: true }); }; strip.append(item);
      });
      if (!roles.length) strip.append(element('p', 'small', '当前没有任务角色；可以管理项目声音与默认。')); strip.scrollLeft = offset;
    }
    for (const item of strip.querySelectorAll('button')) {
      const role = roles.find(role => role.id === item.dataset.roleId), resolved = resolveRole(state, role), voice = state.data.voices[role.assignment?.project_voice_id];
      const name = voice?.name ?? role.assignment?.snapshot.name ?? resolved.snapshot?.name;
      item.dataset.gender = resolved.snapshot?.category ?? role.gender_requirement ?? 'other';
      item.classList.toggle('has-assignment', !resolved.error && !!resolved.snapshot);
      const assignedId = !resolved.error && resolved.project_voice_id ? resolved.project_voice_id : '';
      const avatarKey = assignedId ? voicePortrait(assignedId, resolved.snapshot?.category) : '';
      if (item.dataset.avatarKey !== avatarKey || !item.querySelector('.role-avatar')) {
        const avatar = avatarKey ? portrait(avatarKey, 'role-avatar') : element('span', 'role-avatar unknown-avatar');
        if (!avatarKey) avatar.setAttribute('aria-label', '尚未分配声音');
        item.querySelector('.role-avatar-frame,.unknown-avatar')?.replaceWith(avatar); item.dataset.avatarKey = avatarKey;
      }
      item.classList.toggle('is-assigned', !!role.assignment); item.classList.toggle('is-resolved', !resolved.error); item.classList.toggle('target-selected', state.activeRoleId === role.id); item.setAttribute('aria-pressed', String(state.activeRoleId === role.id)); item.disabled = state.busy;
      const status = role.assignment ? `✓ 已分配 · ${name}${voice?.deleted ? '（已从项目库移除）' : ''}` : !resolved.error ? `默认 · ${name}` : role.required === false ? '可选 · 未分配' : '未分配';
      item.querySelector('.role-binding').textContent = status; item.title = `${role.name} / ${status}${role.gender_requirement ? ` / Agent 明确要求：${role.gender_requirement}` : ''}`;
    }
    const current = roles.find(role => role.id === state.activeRoleId); root.querySelector('#role-context').textContent = current ? `当前选择：${current.name}` : '请选择角色，再选择声音';
  };
  render(store.getState()); const unsubscribe = store.subscribe(render);
  return () => { clearTimers(); unsubscribe(); window.removeEventListener('resize', dismissDetail); document.removeEventListener('scroll', dismissDetail, true); detail.remove(); };
}
