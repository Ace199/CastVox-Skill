import { catalogAttributes } from './catalog.js';

export function voiceGender(voice) {
  const value = voice ? catalogAttributes(voice).gender : 'unknown';
  return ['male', 'female'].includes(value) ? value : 'other';
}

export function selectionGender(state, selection) {
  if (['male', 'female', 'other'].includes(selection?.voiceGender)) return selection.voiceGender;
  const key = selection?.voiceRef ?? selection?.voiceKey ?? (selection?.voiceId ? `project:${selection.voiceId}` : null);
  const voice = key?.startsWith('pool:') ? state.catalog.voices.find(item => `pool:${item.id}` === key)
    : state.data?.voices.find(item => (item.originVoiceKey ?? `project:${item.id}`) === key);
  return voiceGender(voice);
}

export function boundRoleNumbers(state, voice) {
  const key = voice.originVoiceKey ?? `project:${voice.id}`;
  return (state.task.jobId ? state.data?.roles ?? [] : []).flatMap((role, index) => {
    const selection = state.task.selections[role.id];
    const reference = selection?.voiceRef ?? selection?.voiceKey ?? (selection?.voiceId ? `project:${selection.voiceId}` : null);
    return reference === key ? [index + 1] : [];
  });
}
