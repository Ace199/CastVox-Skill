// Fictional catalogue only; neither IDs nor attributes are real MiniMax claims.
export const catalogData = [
  { id: 'MOCK_OFFICIAL_A', name: '晴朗叙述', source: 'official', gender: 'male', tags: ['青年', '清晰'], availability: 'available', provenance: '本地虚构元数据', portrait: 'narrator' },
  { id: 'MOCK_OFFICIAL_B', name: '轻柔讲述', source: 'official', gender: 'female', tags: ['温柔', '清晰'], availability: 'available', provenance: '本地虚构元数据', portrait: 'reader' },
  { id: 'MOCK_USER_A', name: '故事伙伴', source: 'user', gender: 'female', tags: ['青年', '活泼'], availability: 'available', provenance: '本地虚构元数据', portrait: 'soft' },
  { id: 'MOCK_USER_B', name: '沉稳旁白', source: 'user', gender: 'male', tags: ['沉稳'], availability: 'unavailable', unavailableReason: '模拟：音色暂不可用', provenance: '本地虚构元数据', portrait: 'narrator' },
  { id: 'MOCK_USER_UNKNOWN', name: '甜美女声（属性未确认）', source: 'user', gender: 'unknown', tags: [], availability: 'unknown', provenance: null, portrait: 'soft' },
  { id: 'MOCK_OFFICIAL_C', name: '档案声音', source: 'official', gender: 'unknown', tags: ['沉稳'], availability: 'available', provenance: '本地虚构元数据', portrait: 'reader' }
];
