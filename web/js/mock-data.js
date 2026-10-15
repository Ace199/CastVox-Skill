import { clone } from './validation.js';
import { neutralSettings, signature } from './voice-model.js';

export const mockSamples = [
  { path: 'assets/mock-preview-a.wav', duration_seconds: 6 },
  { path: 'assets/mock-preview-b.wav', duration_seconds: 7 }
];
export function mockPreview(voice, index = 0) {
  return { ...mockSamples[index % mockSamples.length], sample_id: `MOCK_SAMPLE_${voice.id}_${index}`, source_job_id: 'MOCK_AUDIO_JOB', source_chunk_id: `MOCK_CHUNK_${index}`, effective_settings: clone(voice.settings), signature: signature(voice), available: true, mock: true };
}
export function bootstrapData(providers) {
  const provider = providers.find(item => item.models.length), model = provider?.default_model ?? provider?.models[0]?.id;
  const voices = {};
  if (provider && model) [['项目旁白', 'male'], ['对白音色', 'female'], ['环境叙述', 'other']].forEach(([name, category], index) => {
    const id = `pv_${String(index + 1).padStart(3, '0')}`, source = { provider: provider.id, region: provider.region ?? 'configured', model, voice_id: `MOCK_VOICE_${index + 1}` };
    voices[id] = { id, name, category, deleted: false, source, settings: neutralSettings(source, providers), preview: null };
    if (index === 1) voices[id].preview = mockPreview(voices[id]);
    if (index === 2) voices[id].preview = { ...mockPreview(voices[id], 1), available: false };
  });
  return { schema_version: '1.6-ui-mock', revision: 0,
    project: { id: 'MOCK_PROJECT_A', name: '声音故事 · 演示项目', location: 'Mock 项目 · 未连接真实项目目录' },
    question: { question_id: 'MOCK_QUESTION_A', job_id: 'MOCK_JOB_A' },
    voices, defaults: { general: null, male: null, female: null },
    roles: [{ id: 'MOCK_ROLE_A', name: '主角 A', required: true, gender_requirement: 'male', description: '示例角色：年轻的探索者，行动果断，表达直接。', voice_recommendation: '清晰、有活力的男声；保持自然表达。', assignment: null },
      { id: 'MOCK_ROLE_B', name: '主角 B', required: true, gender_requirement: 'female', description: '示例角色：沉着细心的伙伴，善于观察与解释。', voice_recommendation: '温和、清晰的女声，语气沉稳。', assignment: null },
      { id: 'MOCK_ROLE_N', name: '旁白', required: true, gender_requirement: null, description: '示例角色：故事之外的讲述者，不指定外貌或性别。', voice_recommendation: '自然、中性的叙述声音，重视清晰度与节奏。', assignment: null }],
    historical_references: { pv_001: 1 } };
}
