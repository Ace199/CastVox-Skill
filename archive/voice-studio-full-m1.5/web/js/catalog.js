export const featureOptions = [
  ['all', '全部特征'], ['male', '男声'], ['female', '女声'], ['unknown', '性别 unknown'],
  ['青年', '青年'], ['清晰', '清晰'], ['温柔', '温柔'], ['活泼', '活泼'], ['沉稳', '沉稳']
];
export const sourceLabel = source => ({ official: '官方音色（Mock）', user: '用户音色（Mock）' }[source] ?? '来源 unknown');
export function catalogAttributes(voice) {
  return {
    gender: voice.provenance && ['male', 'female'].includes(voice.gender) ? voice.gender : 'unknown',
    tags: voice.provenance && Array.isArray(voice.tags) ? voice.tags : []
  };
}
export function filterCatalog(voices, filters) {
  const query = filters.query.trim().toLowerCase();
  return voices.filter(voice => {
    const attributes = catalogAttributes(voice);
    const featureMatches = filters.feature === 'all' || (['male', 'female', 'unknown'].includes(filters.feature) ? attributes.gender === filters.feature : attributes.tags.includes(filters.feature));
    return (filters.source === 'all' || voice.source === filters.source) && featureMatches && (!query || [voice.name, voice.id, ...attributes.tags].join(' ').toLowerCase().includes(query));
  });
}
