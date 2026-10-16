import { t, msg, escapeHtml, translateMessage } from './i18n.js';
import { controlCapability } from './capabilities.js';

export function mountAddParameters(root, store) {
  const fields = [['speed', t("语速")], ['pitch', t("声调")]];
  root.innerHTML = `<div class="parameter-grid">${fields.map(([key, label]) => `
    <div class="parameter-block"><fieldset id="add-${key}-control" class="parameter-control"><legend>${label}</legend>
      <input id="add-${key}-range" type="range" aria-label="${escapeHtml(t("添加{0}滑块", label))}">
      <div class="parameter-value"><input id="add-${key}" type="number" aria-label="${escapeHtml(t("添加{0}数值", label))}" aria-describedby="add-${key}-capability">
      <button id="add-reset-${key}" type="button" class="quiet" aria-label="${escapeHtml(t("恢复添加{0}默认值", label))}">${escapeHtml(t("恢复默认"))}</button></div>
    </fieldset><p id="add-${key}-capability" class="small muted parameter-help"></p></div>`).join('')}</div>`;
  const get = id => root.querySelector(`#${id}`);
  for (const [key] of fields) {
    for (const suffix of ['', '-range']) get(`add-${key}${suffix}`).oninput = event => store.edit(key, event.target.value);
    get(`add-reset-${key}`).onclick = () => store.edit(key, null);
  }
  const render = state => {
    const source = { provider: state.draft.provider, model: state.draft.model };
    for (const [key] of fields) {
      const cap = controlCapability(source, state.providers, key), input = get(`add-${key}`), range = get(`add-${key}-range`);
      get(`add-${key}-control`).disabled = state.busy || !cap.enabled;
      const value = state.draft[key] ?? (cap.enabled ? cap.neutral : '');
      if (input.value !== String(value)) input.value = value;
      range.hidden = !cap.enabled;
      if (cap.enabled) {
        for (const node of [input, range]) for (const attribute of ['min', 'max', 'step']) node.setAttribute(attribute, cap[attribute]);
        range.step = cap.range_step ?? cap.step;
        range.value = value === '' ? cap.neutral : value;
      } else {
        for (const attribute of ['min', 'max', 'step']) input.removeAttribute(attribute);
      }
      get(`add-${key}-capability`).textContent = cap.enabled
        ? `${cap.min}–${cap.max}${cap.unit ? ` ${translateMessage(cap.unit)}` : ''}${cap.step === 'any' ? '' : msg` · 步长 ${cap.step}`}${cap.live_verified === false ? t(" · 文档范围，真实效果未验收") : ''}`
        : translateMessage(cap.reason);
    }
  };
  render(store.getState());
  return store.subscribe(render);
}
