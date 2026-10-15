// Provider-specific labels, URLs, models and statuses come from a redacted local API.
export async function fetchProviders() {
  const response = await fetch('/api/providers', { cache: 'no-store', credentials: 'same-origin' });
  if (!response.ok) throw new Error('无法读取厂商模型配置，请通过 studio_server.py 启动页面');
  const body = await response.json();
  if (!Array.isArray(body.providers)) throw new Error('厂商元数据格式不正确');
  return body.providers;
}

export async function openProviderConfig(provider) {
  const response = await fetch('/api/providers/open-config', {
    method: 'POST', credentials: 'same-origin',
    headers: { 'Content-Type': 'application/json', 'X-Studio-Action': 'open-config' },
    body: JSON.stringify({ provider })
  });
  if (!response.ok) throw new Error('无法打开配置，请确认本地服务已更新并重启');
  const result = await response.json();
  if (!result.ok) throw new Error(result.message || '无法打开配置文件');
  return result;
}
