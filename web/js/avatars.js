// Presentation-only mapping from user-declared category and stable voice identity.
// Never infer a category from a name or provider voice ID.
const portraits = {
  male: ['man/001-man.svg', 'man/002-man.svg', 'man/003-man.svg', 'man/004-man.svg'],
  female: ['women/010-woman.svg', 'women/011-woman.svg', 'women/015-woman.svg', 'women/017-woman.svg'],
  other: ['unknow/robot_head.svg', 'unknow/robot.svg']
};
const initialPortraits = { pv_001: 'man/002-man.svg', pv_002: 'women/010-woman.svg', pv_003: 'unknow/robot_head.svg' };
export function voicePortrait(id, category = 'other') {
  const choices = portraits[category] ?? portraits.other;
  if (choices.includes(initialPortraits[id])) return initialPortraits[id];
  return choices[[...id].reduce((sum, char) => sum + char.charCodeAt(0), 0) % choices.length];
}
