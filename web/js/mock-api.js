// UI-only in-memory adapter; no Python/Core writes or provider requests.
import { clone, same, normalizeName, stableJson } from './validation.js';
import { bootstrapData, mockPreview } from './mock-data.js';
import { validateNewVoice, validateName, validateSettings, neutralSettings, defaultVoice, signature } from './voice-model.js';
import { fetchProviders } from './providers.js';
import { withMockCapabilities } from './capabilities.js';

export function createMockApi(log = { record() {} }, descriptors = []) {
  let providers = withMockCapabilities(descriptors), data = bootstrapData(providers), failNext = false, nextId = 4;
  const receipts = new Map();
  const pause = ms => new Promise(resolve => setTimeout(resolve, ms));
  const conflict = () => Object.assign(new Error('Mock revision 已变化，请重新读取后重试；草稿已保留。'), { code: 'revision_conflict' });
  const begin = async revision => { await pause(70); if (failNext) { failNext = false; throw new Error('模拟保存失败；未修改记录，可以重试。'); } if (revision !== data.revision) throw conflict(); };
  const active = id => { const voice = data.voices[id]; if (!voice || voice.deleted) throw new Error('声音已从项目库移除，请恢复或重新选择。'); return voice; };
  const changed = (name, id) => { data.revision++; log.record({ name, objectId: id, result: `Mock 保存成功 · revision ${data.revision}` }); return clone(data); };
  return {
    async load() { await pause(30); return clone(data); },
    getProviders: () => clone(providers),
    async loadProviders() { providers = withMockCapabilities(await fetchProviders()); return clone(providers); },
    configureMock({ failSave = false, conflict: revise = false, empty = false, management = false } = {}) {
      if (failSave) failNext = true;
      if (revise) data.revision++;
      if (empty) { data.voices = {}; data.defaults = { general: null, male: null, female: null }; data.revision++; }
      if (management) data.question = null;
      log.record({ name: 'mock.scenario', objectId: data.project.id, result: '只改变内存 Mock，无外部请求' });
    },
    async addVoice({ draft, expectedRevision }) {
      const name = normalizeName(draft.name), identity = validateNewVoice(draft, providers);
      await begin(expectedRevision); validateName(data, name);
      let id; do { id = `pv_${String(nextId++).padStart(3, '0')}`; } while (Object.hasOwn(data.voices, id));
      data.voices[id] = { id, name, ...identity, deleted: false, settings: neutralSettings(identity.source, providers), preview: null };
      return { data: changed('voice.mock.added', id), id };
    },
    async saveVoice({ id, draft, expectedSource, expectedRevision }) {
      await begin(expectedRevision); const voice = active(id);
      if (!same(expectedSource, voice.source)) throw conflict();
      const name = validateName(data, draft.name, id), settings = validateSettings(voice, draft, providers);
      data.voices[id] = { ...voice, name, category: draft.category, settings };
      return changed('voice.mock.updated', id);
    },
    async saveDefaults({ defaults, expectedRevision, confirmed }) {
      if (confirmed !== true) throw new Error('默认设置必须明确确认。');
      await begin(expectedRevision);
      for (const slot of ['general', 'male', 'female']) {
        const id = defaults[slot];
        if (id !== null && id !== data.defaults[slot] && !defaultVoice(data, slot, defaults)) throw new Error('默认候选已删除、缺失或分类不匹配。');
      }
      data.defaults = clone(defaults); return changed('defaults.mock.saved', data.project.id);
    },
    async deleteVoice({ id, expectedRevision }) {
      await begin(expectedRevision); const voice = active(id); data.voices[id] = { ...voice, deleted: true };
      return changed('voice.mock.deleted', id);
    },
    async restoreVoice({ id, name, expectedRevision }) {
      await begin(expectedRevision); const voice = data.voices[id]; if (!voice?.deleted) throw new Error('没有可撤销的删除。');
      const restoredName = validateName(data, name ?? voice.name, id);
      data.voices[id] = { ...voice, name: restoredName, deleted: false }; return changed('voice.mock.restored', id);
    },
    async updatePreview({ id, expectedSignature, expectedRevision }) {
      await begin(expectedRevision); const voice = active(id);
      if (expectedSignature !== signature(voice)) throw new Error('试听结果参数已过期，保留原样本。');
      await pause(300);
      if (data.voices[id].deleted || signature(data.voices[id]) !== expectedSignature) throw new Error('试听保存期间参数已改变；旧任务结果未覆盖当前样本。');
      data.voices[id] = { ...data.voices[id], preview: mockPreview(data.voices[id], data.revision + 1) };
      return changed('preview.mock.updated', id);
    },
    async setPreviewScenario({ id, scenario, expectedRevision }) {
      await begin(expectedRevision); const voice = active(id); let preview = mockPreview(voice);
      if (scenario === 'none') preview = null;
      if (scenario === 'unavailable') preview.available = false;
      if (scenario === 'stale') preview.signature = 'MOCK_OLD_PARAMETERS';
      data.voices[id] = { ...voice, preview }; return changed('preview.mock.scenario', id);
    },
    async submitAnswer(answer) {
      const key = stableJson(answer);
      if (receipts.has(key)) return clone(receipts.get(key));
      await begin(answer.expected_revision);
      if (!data.question || answer.question_id !== data.question.question_id || answer.job_id !== data.question.job_id || answer.project_id !== data.project.id) throw new Error('当前没有匹配的 Studio Question，未通知 Harness。');
      if (answer.mock !== true || answer.assignments.some(role => role.required && (!role.snapshot?.source?.voice_id || role.error))) throw new Error('必要角色声音未满足。');
      if (!same(answer.defaults, data.defaults)) throw conflict();
      if (receipts.has(key)) return clone(receipts.get(key));
      const receipt = { mock: true, status: 'accepted', can_generate: false, answer: clone(answer) };
      receipts.set(key, receipt); log.record({ name: 'answer.mock.submitted', objectId: answer.question_id, result: '仅 Mock 接收，未通知真实 Harness，未调用 TTS' });
      return clone(receipt);
    }
  };
}
