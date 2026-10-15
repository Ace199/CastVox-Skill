import { previewStatus } from './voice-model.js';

export function createPreviewPlayer(store, log, makeAudio = url => new Audio(url)) {
  let audio = null, currentId = null, sampleId = null, operation = 0;
  const retire = () => { operation++; if (audio) { audio.onended = null; audio.onerror = null; audio.pause(); } audio = null; currentId = null; sampleId = null; };
  const stop = () => { retire(); store.update({ player: { voiceId: null, status: 'idle', sampleId: null, error: '' } }); };
  const error = (id, sample, token) => {
    if (token !== operation) return;
    audio?.pause(); store.update({ player: { voiceId: id, sampleId: sample, status: 'error', error: '试听文件不可用' }, message: '试听文件不可用；没有调用 TTS。' });
    log.record({ name: 'preview.unavailable', objectId: id, result: '保留试听记录，不生成替代音频', error: '本地文件不可播放' });
  };
  const unsubscribe = store.subscribe(state => {
    if (!currentId) return;
    const voice = state.data?.voices[currentId];
    if (!voice || voice.deleted || voice.preview?.sample_id !== sampleId || voice.preview.available === false) stop();
  });
  return {
    async toggle(id) {
      const state = store.getState(), voice = state.data?.voices[id];
      if (!voice || voice.deleted || !previewStatus(voice, state.player).playable) return;
      if (currentId === id && sampleId === voice.preview.sample_id && state.player.status === 'playing') {
        audio.pause(); store.update({ player: { ...state.player, status: 'paused' } }); return;
      }
      const url = new URL(voice.preview.url ?? voice.preview.path, location.href);
      const safe = url.origin === location.origin && /^\/(assets\/|api\/previews\/)/.test(url.pathname) && !url.search && !url.hash;
      if (!safe) { store.update({ player: { voiceId: id, sampleId: voice.preview.sample_id, status: 'error', error: '未提供合法本地试听地址' } }); return; }
      if (currentId !== id || sampleId !== voice.preview.sample_id || !audio) {
        retire(); currentId = id; sampleId = voice.preview.sample_id; audio = makeAudio(url.href);
      }
      const token = ++operation, sample = sampleId;
      audio.onended = () => { if (token === operation) store.update({ player: { voiceId: id, sampleId: sample, status: 'ended', error: '' } }); };
      audio.onerror = () => error(id, sample, token);
      store.update({ player: { voiceId: id, sampleId: sample, status: 'loading', error: '' } });
      try { await audio.play(); if (token === operation) { store.update({ player: { voiceId: id, sampleId: sample, status: 'playing', error: '' } }); log.record({ name: 'preview.play', objectId: id, result: voice.preview.mock ? '播放明确标注的本地 Mock 测试音，非真实 MiniMax 音频' : '播放已有本地文件，无合成请求' }); } }
      catch { error(id, sample, token); }
    },
    stop,
    dispose() { retire(); unsubscribe(); }
  };
}
