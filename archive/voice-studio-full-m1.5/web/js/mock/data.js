// UI-only fixtures. This is not an extension of the M1 Python schema.
export const bootstrapData = {
  project: { id: 'MOCK_PROJECT_A', name: '声音故事 · 演示项目', defaultVoice: null },
  job: { id: 'MOCK_JOB_A', questionId: 'MOCK_QUESTION_A' },
  agent: { previewText: '清晨的第一束阳光穿过窗边的树叶，主角终于翻开那封等待已久的来信，并决定带着伙伴一起寻找故事背后的答案。', previewSource: 'Mock Agent 从已确认稿件提取的完整句' },
  voices: [
    { id: 'MOCK_VOICE_A', name: '叙述男声', gender: 'male', source: 'mock', provenance: '本地虚构数据' },
    { id: 'MOCK_VOICE_B', name: '温柔女声', gender: 'female', source: 'mock', provenance: '本地虚构数据' },
    { id: 'MOCK_VOICE_C', name: '未分类声音', gender: 'unknown', source: 'mock', provenance: '本地虚构数据' }
  ],
  roles: [
    { id: 'MOCK_ROLE_A', name: '主角 A', voiceId: null, parameters: { speed: 1.1, volume: 1, emotion: 'auto' } },
    { id: 'MOCK_ROLE_B', name: '主角 B', voiceId: 'MOCK_VOICE_B', parameters: { speed: 0.9, volume: 0.8, emotion: 'auto' } },
    { id: 'MOCK_ROLE_N', name: '旁白', voiceId: null, parameters: { speed: 1, volume: 1, emotion: 'auto' } }
  ]
};
