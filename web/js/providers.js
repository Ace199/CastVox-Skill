import { t, translateMessage } from './i18n.js';
import { request } from './transport.js';
// Provider-specific labels, URLs, models and statuses come from a redacted local API.
export async function fetchProviders() {
  const body = await request('/api/providers');
  if (!Array.isArray(body.providers)) throw new Error(t("厂商元数据格式不正确"));
  return body.providers;
}

export async function openProviderConfig(provider) {
  const result = await request('/api/providers/open-config', { provider });
  if (!result.ok) throw new Error(translateMessage(result.message) || t("无法打开配置文件"));
  return result;
}

export async function openDefaultConfig() {
  const result = await request('/api/v16/defaults/open-config', {});
  if (!result.ok) throw new Error(translateMessage(result.message) || t("无法打开默认配置"));
  return result;
}
