import { session } from './session.js';
export async function request(path, body, binary = false) {
  const headers = {};
  if (session.mode === 'persistent') headers.Authorization = `Bearer ${session.token}`;
  if (body !== undefined) {
    headers['Content-Type'] = 'application/json';
    headers['X-CSRF-Token'] = session.csrf;
    headers['X-Studio-Action'] = 'open-config';
  }
  const response = await fetch(path, { method: body === undefined ? 'GET' : 'POST', headers,
    cache: 'no-store', credentials: 'same-origin', ...(body === undefined ? {} : { body: JSON.stringify(body) }) });
  if (!response.ok) {
    const result = await response.json().catch(() => ({}));
    const messages = { revision_conflict: '项目已被其他页面或任务修改；请重新读取，检查保留的草稿后再次保存。',
      answer_immutable: '回答已提交，请重新读取查看结果。', forbidden: '会话失效或请求被拒绝，请刷新页面。',
      name_conflict: '项目内已有同名声音，请更换名称。', question_expired: '任务问题已过期，请在 Agent 中重新发起。',
      voice_unavailable: '声音已删除或不可用，请重新选择。', migration_required: '旧项目需要先显式迁移，请保留备份后操作。' };
    throw Object.assign(new Error(messages[result.error] ?? `操作未完成（${result.error ?? response.status}），请检查配置。`), { code: result.error });
  }
  return binary ? response.blob() : response.json();
}
