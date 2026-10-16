import { t } from './i18n.js';
// UI adapter contract. Real ranges are accepted only from verified descriptors.
export function controlCapability(source, providers, key) {
  const provider = providers.find(item => item.id === source.provider);
  const model = provider?.models.find(item => item.id === source.model);
  const cap = model?.capabilities?.[key] ?? provider?.capabilities?.[source.model]?.[key];
  const valid = cap?.supported === true && cap?.verified === true &&
    ['min', 'max', 'neutral'].every(field => Number.isFinite(cap[field])) &&
    cap.min <= cap.neutral && cap.neutral <= cap.max && (cap.step === 'any' || Number.isFinite(cap.step) && cap.step > 0);
  return valid ? { ...cap, enabled: true } : {
    enabled: false, reason: cap?.reason ?? t("模型能力尚未验证，暂不可编辑；现有值将保留。")
  };
}

export function withMockCapabilities(providers) {
  // Isolated UI fixtures only; never infer support for a real account/model.
  return structuredClone(providers).map(provider => ({ ...provider, models: provider.models.map((model, index) => ({
    ...model,
    capabilities: model.capabilities ?? provider.capabilities?.[model.id] ?? (provider.source === 'mock_fixture' ? (index === 0 && provider.id === 'minimax' ? {
      speed: { supported: true, verified: true, min: 0.5, max: 2, step: 0.1, neutral: 1, unit: t("倍（Mock）"), verification: 'mock_only' },
      pitch: { supported: true, verified: true, min: -6, max: 6, step: 1, neutral: 0, unit: t("示例刻度（Mock）"), verification: 'mock_only' }
    } : { speed: { supported: false, reason: t("此 Mock 模型未验证语速能力。") }, pitch: { supported: false, reason: t("此 Mock 模型未验证声调能力。") } }) : undefined)
  })) }));
}
