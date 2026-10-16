import { request } from './transport.js';
import { session } from './session.js';
import { fetchProviders } from './providers.js';
import { validateNewVoice, validateSettings } from './voice-model.js';

export function createPersistentApi(descriptors) {
  let providers = descriptors, lastData = null;
  const load = async () => {
    const result = await request('/api/v16/state');
    const question = session.question_id ? await request(`/api/v16/questions/${session.question_id}`) : null;
    const voices = Object.fromEntries(Object.entries(result.preset.voices).map(([id, voice]) => {
      const sample = result.previews[id];
      return [id, { ...voice, id, preview: sample.preview ? { ...sample.preview,
        available: ['current', 'before_adjustment'].includes(sample.status), backend_status: sample.status,
        url: `/api/v16/preview/${id}` } : null }];
    }));
    const roles = (question?.roles ?? []).map(id => {
      const meta = question.role_metadata?.[id] ?? {};
      let binding = question.assignments?.[id];
      if (!binding && question.answer?.resolved?.[id]) {
        const resolved = question.answer.resolved[id], voice = voices[resolved.project_voice_id];
        binding = { project_voice_id: resolved.project_voice_id, snapshot: { project_voice_id: resolved.project_voice_id,
          name: voice?.name ?? resolved.project_voice_id, category: voice?.category ?? 'other', source: resolved.source, settings: resolved.effective_settings } };
      }
      return { id, name: meta.display_name ?? id, required: true, gender_requirement: meta.gender_requirement,
        description: meta.appearance_summary, voice_recommendation: meta.recommended_voice_description,
        recommended_project_voice_id: meta.recommended_project_voice_id,
        ...(binding ? { assignment: { project_voice_id: binding.project_voice_id, snapshot: binding.snapshot } } : {}) };
    });
    lastData = { ...result.preset, voices, roles, question, mode: 'persistent',
      project: result.project, historical_references: {} };
    return structuredClone(lastData);
  };
  const edit = async (id, patch, revision) => { await request('/api/v16/voices/edit', { project_voice_id: id, patch, revision }); return load(); };
  return {
    mode: 'persistent', load, getProviders: () => structuredClone(providers),
    async loadProviders() { providers = await fetchProviders(); return providers; },
    async addVoice({ draft, expectedRevision }) {
      const identity = validateNewVoice(draft, providers);
      const result = await request('/api/v16/voices/add', { ...identity, name: draft.name.normalize('NFC').trim(), revision: expectedRevision });
      return { data: await load(), id: result.project_voice_id };
    },
    saveVoice({ id, draft, expectedRevision }) {
      // Capability checks are repeated by Core; only verified UI controls are submitted.
      const settings = validateSettings(lastData.voices[id], draft, providers);
      return edit(id, { name: draft.name.normalize('NFC').trim(), category: draft.category, settings }, expectedRevision);
    },
    async saveDefaults({ defaults, expectedRevision, confirmed }) {
      if (!confirmed) throw new Error('请确认保存默认设置。');
      const changes = Object.fromEntries(Object.entries(defaults).filter(([slot, id]) => lastData?.defaults[slot] !== id));
      await request('/api/v16/defaults', { defaults: changes, revision: expectedRevision }); return load();
    },
    deleteVoice: ({ id, expectedRevision }) => edit(id, { deleted: true }, expectedRevision),
    restoreVoice: ({ id, name, expectedRevision }) => edit(id, { deleted: false, name }, expectedRevision),
    async assignRole(role_id, project_voice_id, revision) {
      await request('/api/v16/assignments', { question_id: session.question_id, role_id, project_voice_id, revision });
      return load();
    },
    async submitAnswer(answer) {
      const result = await request('/api/v16/answers', { question_id: answer.question_id,
        assignments: Object.fromEntries(answer.assignments.filter(r => !r.error).map(r => [r.role_id, r.via?.startsWith('default_') ? { default_slot: r.via.slice(8) } : r.project_voice_id])), revision: answer.expected_revision });
      return { ...result, summary: answer.assignments };
    },
    complete: () => request('/api/v16/complete', {}),
    previewBlob: id => request(`/api/v16/preview/${id}`, undefined, true)
  };
}
