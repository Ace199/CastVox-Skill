import { bootstrapData } from './mock/data.js';
import { eventLog } from './events.js';
import { catalogData } from './mock/catalog.js';
import { capabilities, editorSignature } from './editor.js';

// Promise contract shared by future callers; no Harness or provider SDK.
// An in-memory adapter only: no fetch, credentials or M1 writes.
export function createMockApi(log = eventLog) {
  const cache = new Map(), inflight = new Map(), receipts = new Map();
  let library = structuredClone(bootstrapData.voices), revision = 0, nextId = 1;
  let failPreview = false, failSave = false;
  const pause = () => new Promise(resolve => setTimeout(resolve, 100));
  return {
    async notifyHarness({ projectId, jobId, assignments }) {
      if (!projectId || !jobId || !assignments?.length || assignments.some(item => !item.voiceId)) throw new Error('角色尚未全部分配，未通知 Harness');
      const snapshot = structuredClone(assignments);
      await pause();
      const receipt = { mock: true, status: 'acknowledged', projectId, jobId, assignments: snapshot };
      log.record({ name: 'harness.mock.notified', objectId: jobId, result: `Mock Harness 已收到 ${assignments.length} 个角色配置；未发送真实消息` });
      return receipt;
    },
    configureMock(options) {
      if (options.failPreview) failPreview = true;
      if (options.failSave) failSave = true;
      if (options.conflict) revision++;
      log.record({ name: 'debug.mock.configured', objectId: 'MOCK_PROJECT_A', result: JSON.stringify(options) });
    },
    async getProjectLibrary() { return { voices: structuredClone(library), revision, projectId: bootstrapData.project.id }; },
    async saveProjectVoice({ name, draft, metadata, expectedRevision, confirmation, operationId }) {
      const request = JSON.stringify({ name, draft, metadata, expectedRevision, confirmation });
      if (receipts.has(operationId)) {
        const prior = receipts.get(operationId);
        if (prior.request !== request) throw new Error('重复操作 ID 的内容不一致');
        return structuredClone(prior.result);
      }
      await pause();
      if (receipts.has(operationId)) {
        const prior = receipts.get(operationId);
        if (prior.request !== request) throw new Error('重复操作 ID 的内容不一致');
        return structuredClone(prior.result);
      }
      if (failSave) { failSave = false; throw new Error('模拟保存失败，尚未写入 Mock 项目库'); }
      if (!operationId || !cache.has(editorSignature(draft)) || metadata.availability === 'unavailable') throw new Error('没有当前参数对应的成功模拟试听，不能保存');
      if (name !== name.trim() || !name || name.length > 120 || /[\x00-\x1f]/.test(name)) throw new Error('请输入无首尾空格的项目内唯一名称（1–120 字）');
      name = name.normalize('NFC');
      if (expectedRevision !== revision) { const error = new Error('项目库 revision 冲突，请重新读取后再次确认'); error.code = 'revision_conflict'; throw error; }
      const existing = library.find(voice => voice.name.normalize('NFC') === name);
      if (existing && (!confirmation || confirmation.voiceId !== existing.id || confirmation.oldRef !== (existing.originVoiceKey ?? `project:${existing.id}`))) throw new Error('同名音色需要明确确认旧引用后才能重绑定');
      const voice = { id: existing?.id ?? `MOCK_PROJECT_SAVED_${nextId++}`, name, gender: metadata.gender ?? 'unknown', provenance: metadata.provenance ?? null,
        source: 'mock', avatar: ['assets/portrait-narrator.svg', 'assets/portrait-reader.svg', 'assets/portrait-soft.svg'].includes(metadata.avatar) ? metadata.avatar : undefined, originVoiceKey: draft.resolvedVoiceKey ?? draft.voiceKey, parameters: { speed: draft.speed, volume: draft.volume, emotion: draft.emotion },
        studioSettings: { model: draft.model, latex: draft.latex, normalize: draft.normalize, text: draft.text } };
      library = existing ? library.map(item => item.id === existing.id ? voice : item) : [...library, voice]; revision++;
      const result = { voices: structuredClone(library), revision, voice: structuredClone(voice), projectId: bootstrapData.project.id };
      receipts.set(operationId, { request, result });
      log.record({ name: 'api.library.saved', objectId: voice.id, result: `Mock 保存成功 revision=${revision}，没有文件写入` });
      return structuredClone(result);
    },
    async createPreview({ draft, simulateError = false }) {
      log.record({ name: 'api.preview.request', objectId: draft.voiceKey, result: '本地 Mock 试听，不调用 MiniMax' });
      if (simulateError || failPreview || !draft.text.trim() || !capabilities[draft.model]?.emotions.includes(draft.emotion)) {
        failPreview = false;
        const error = new Error('模拟试听失败或参数不兼容');
        log.record({ name: 'api.preview.failure', objectId: draft.voiceKey, result: '失败', error }); throw error;
      }
      const key = editorSignature(draft);
      if (cache.has(key)) { log.record({ name: 'api.preview.cache-hit', objectId: draft.voiceKey, result: '命中当前完整参数缓存' }); return { ...structuredClone(cache.get(key)), cacheHit: true }; }
      if (inflight.has(key)) return inflight.get(key);
      const pending = (async () => {
        await pause();
        const result = { url: 'assets/mock-preview.wav', duration: 2, cacheKey: key, cacheHit: false };
        cache.set(key, result); log.record({ name: 'api.preview.success', objectId: draft.voiceKey, result: '返回本地 2 秒提示音；不模拟真实音色/参数效果' });
        return structuredClone(result);
      })();
      inflight.set(key, pending);
      try { return await pending; } finally { inflight.delete(key); }
    },
    async listCatalog({ simulateError = false, empty = false } = {}) {
      log.record({ name: 'api.catalog.request', objectId: 'MOCK_CATALOG', result: '加载 Mock 声音池' });
      try {
        if (simulateError) throw new Error('模拟声音池加载失败；未发送网络请求');
        const data = structuredClone(empty ? [] : catalogData);
        log.record({ name: 'api.catalog.success', objectId: 'MOCK_CATALOG', result: `返回 ${data.length} 个 Mock 候选` });
        return data;
      } catch (error) {
        log.record({ name: 'api.catalog.failure', objectId: 'MOCK_CATALOG', result: '失败', error }); throw error;
      }
    },
    async loadWorkspace({ projectId = 'MOCK_PROJECT_A', simulateError = false } = {}) {
      log.record({ name: 'api.workspace.request', objectId: projectId, result: 'Mock 请求' });
      try {
        if (simulateError) throw new Error('模拟加载失败；未发送网络请求');
        if (projectId !== bootstrapData.project.id) throw new Error('Mock 项目不存在');
        const data = structuredClone(bootstrapData);
        data.voices = structuredClone(library); data.libraryRevision = revision;
        log.record({ name: 'api.workspace.success', objectId: projectId, result: 'Mock 数据已返回' });
        return data;
      } catch (error) {
        log.record({ name: 'api.workspace.failure', objectId: projectId, result: '失败', error });
        throw error;
      }
    }
  };
}

export const api = createMockApi();
