import { createAssignmentFlow, roleTarget } from '../assignment-flow.js';
import { hasCurrentPreview } from '../editor.js';
import { containDialogFocus } from './dialog-focus.js';

export function mountAssignmentActions(root, store, api, log, complete) {
  const flow = createAssignmentFlow(store, api, log);
  root.innerHTML = `<div id="flow-actions"><p id="flow-gate" class="muted"></p><label>音色名称<input id="flow-name" aria-label="音色名称" aria-describedby="flow-name-hint" maxlength="120" autocomplete="off" required placeholder="为这份音色配置命名"></label><small id="flow-name-hint">两种操作共用此名称；角色池名称仅用于当前任务，项目库名称须项目内唯一。</small><div class="flow-buttons"><button type="button" id="flow-role">加入角色池</button><button type="button" id="flow-save">加入项目库</button></div><button type="button" id="flow-default" hidden>保存为项目默认（确认）</button><p id="flow-target" class="muted"></p><p id="flow-message" role="status"></p><div id="flow-recovery" hidden><button type="button" id="flow-refresh">重新读取项目库</button><button type="button" id="flow-retry">重试保存</button></div></div>
    <dialog id="rebind-dialog" aria-labelledby="rebind-title"><h2 id="rebind-title">确认同名重绑定</h2><p id="rebind-diff"></p><p>仅修改 Mock 项目库。确认绑定旧引用与当前 revision；冲突后必须重新读取和确认。</p><button type="button" id="rebind-cancel" autofocus>取消重绑定</button><button type="button" id="rebind-confirm">确认重绑定</button></dialog>
    <dialog id="summary-dialog" aria-labelledby="summary-title"><h2 id="summary-title">角色分配摘要</h2><p id="summary-state"></p><p id="harness-status" role="status"></p><ul id="summary-rows"></ul><p>仅通知内存 Mock Harness；未提交真实 Answer、恢复 Agent 或发起生成。</p><button type="button" id="summary-close" autofocus>关闭摘要</button></dialog>`;
  const rebind = root.querySelector('#rebind-dialog'), summary = root.querySelector('#summary-dialog');
  containDialogFocus(rebind); containDialogFocus(summary);
  const protect = action => { try { action(); } catch (error) { store.dispatch({ type: 'FLOW_STATUS', patch: { status: 'validation', error: error.message } }); log.record({ name: 'flow.action.failed', objectId: store.getState().editor.activeKey, result: '拒绝', error }); } };
  root.querySelector('#flow-name').oninput = event => store.dispatch({ type: 'FLOW_NAME', value: event.target.value });
  root.querySelector('#flow-role').onclick = () => protect(() => flow.applyRole());
  root.querySelector('#flow-default').onclick = () => protect(() => flow.prepareDefault());
  root.querySelector('#flow-save').onclick = () => { void flow.save(); };
  root.querySelector('#rebind-confirm').onclick = () => { void flow.save(true); };
  root.querySelector('#flow-retry').onclick = () => { void flow.save(); };
  root.querySelector('#flow-refresh').onclick = () => { void flow.refresh(); };
  const cancel = () => store.dispatch({ type: 'FLOW_STATUS', patch: { confirmation: null } });
  root.querySelector('#rebind-cancel').onclick = cancel;
  rebind.addEventListener('cancel', event => { event.preventDefault(); cancel(); });
  let submitting = false;
  complete.onclick = async () => {
    if (submitting) return;
    store.dispatch({ type: 'FLOW_SUMMARY' });
    const state = store.getState(), rows = state.flow.summary;
    const message = root.querySelector('#harness-status');
    log.record({ name: 'flow.complete.click', objectId: state.task.jobId, result: '检查本次角色配置，准备 Mock Harness 通知' });
    log.record({ name: 'flow.summary.open', objectId: state.task.jobId, result: '显示角色分配摘要' });
    if (!state.task.jobId || !rows.length || rows.some(row => !row.voiceId)) { message.textContent = '仍有未分配角色，未通知 Harness。'; return; }
    submitting = true; complete.disabled = true; complete.setAttribute('aria-busy', 'true'); message.textContent = '正在通知 Harness（Mock）…';
    try {
      const result = await api.notifyHarness({ projectId: state.data.project.id, jobId: state.task.jobId, assignments: state.data.roles.map(role => ({ roleId: role.id, ...state.task.selections[role.id] })) });
      message.textContent = store.getState().task.jobId === result.jobId ? '本次配置已通知 Harness（Mock），未发送真实请求。' : '原任务 Mock 通知已完成；当前任务未被提交。';
    } catch (error) { message.textContent = error.message; log.record({ name: 'harness.mock.failed', objectId: state.task.jobId, result: '通知失败，可重试', error }); }
    finally { submitting = false; complete.disabled = false; complete.setAttribute('aria-busy', 'false'); }
  };
  const close = () => store.dispatch({ type: 'FLOW_STATUS', patch: { summary: null } });
  root.querySelector('#summary-close').onclick = close;
  summary.addEventListener('cancel', event => { event.preventDefault(); close(); });
  const render = state => {
    const draft = state.editor.drafts[state.editor.activeKey], ready = hasCurrentPreview(state, draft), target = roleTarget(state), isDefault = state.ui.target?.kind === 'default', busy = state.flow.status === 'saving';
    root.querySelector('#flow-gate').textContent = ready ? '当前参数模拟试听已就绪，可以显式应用或保存。' : '请先获取当前参数对应的模拟试听；旧配置结果不能用于应用。';
    root.querySelector('#flow-role').hidden = isDefault; root.querySelector('#flow-save').hidden = isDefault; root.querySelector('#flow-name').parentElement.hidden = isDefault;
    root.querySelector('#flow-default').hidden = !isDefault;
    root.querySelector('#flow-role').disabled = !ready || !target || busy;
    root.querySelector('#flow-save').disabled = !ready || busy;
    root.querySelector('#flow-save').setAttribute('aria-busy', String(busy));
    root.querySelector('#flow-save').textContent = busy ? '正在保存 Mock…' : '加入项目库';
    root.querySelector('#flow-default').disabled = !ready || busy;
    root.querySelector('#flow-name').disabled = busy;
    if (root.querySelector('#flow-name').value !== state.flow.name) root.querySelector('#flow-name').value = state.flow.name;
    root.querySelector('#flow-target').textContent = isDefault ? '当前为项目默认目标，必须独立确认，不绑定普通角色。' : target ? `应用目标：${state.data.roles.find(role => role.id === target.roleId).name}（仅当前任务）。保存项目库成功后同时应用到此角色。` : '没有有效角色目标；可单独加入项目库，不绑定任何角色。';
    root.querySelector('#flow-message').textContent = state.flow.error || (busy ? '正在 Mock 保存…' : state.flow.message);
    root.querySelector('#flow-recovery').hidden = !state.flow.error || state.flow.status !== 'error'; root.querySelector('#flow-refresh').disabled = busy; root.querySelector('#flow-retry').disabled = busy || !ready;
    complete.hidden = !state.task.jobId;
    if (state.flow.confirmation && !rebind.open) { const c = state.flow.confirmation; root.querySelector('#rebind-diff').textContent = `${c.oldName}：${c.oldRef} → ${c.newRef} / 参数 ${JSON.stringify(c.oldParameters)} → ${JSON.stringify(c.newParameters)} / 模型 ${c.model} / expected revision ${c.expected.revision}`; rebind.showModal(); }
    else if (!state.flow.confirmation && rebind.open) rebind.close();
    if (state.flow.summary) {
      const rows = state.flow.summary, missing = rows.filter(row => !row.voiceId).length;
      root.querySelector('#summary-state').textContent = missing ? `仍有 ${missing} 个角色未分配，设置尚未完成。` : '全部角色已分配 · Mock 设置完成';
      root.querySelector('#summary-rows').replaceChildren(...rows.map(row => {
        const li = document.createElement('li');
        li.textContent = `${row.name} → ${row.voiceName ?? state.data.voices.find(voice => voice.id === row.voiceId)?.name ?? (row.voiceId ? row.voiceId : '未分配')} / ${row.voiceRef ?? row.voiceId ?? '无引用'} / 语速 ${row.parameters.speed} · 音量 ${row.parameters.volume} · 情绪 ${row.parameters.emotion}`; return li;
      }));
      if (!summary.open) summary.showModal();
    } else if (summary.open) summary.close();
  };
  render(store.getState()); return store.subscribe(render);
}
