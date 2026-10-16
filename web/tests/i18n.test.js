import test from 'node:test';
import assert from 'node:assert/strict';
import { normalizeLocale, resolveLocale, setLocale, getLocale, t, msg, escapeHtml } from '../js/i18n.js';

test('locale priority is manual, host, Chinese fallback; browser language is ignored', () => {
  assert.equal(normalizeLocale('en_US'), 'en'); assert.equal(normalizeLocale('zh-Hant-TW'), 'zh-CN'); assert.equal(normalizeLocale('fr-FR'), null);
  assert.deepEqual(resolveLocale({ manual: 'en', host: 'zh-CN', browser: ['zh-CN'] }), { language: 'en', source: 'manual' });
  assert.deepEqual(resolveLocale({ manual: 'auto', host: 'en-GB', browser: ['zh-CN'] }), { language: 'en', source: 'harness' });
  assert.deepEqual(resolveLocale({ host: 'fr', browser: ['fr-FR', 'en-US'] }), { language: 'zh-CN', source: 'fallback' });
  assert.deepEqual(resolveLocale({ browser: ['fr-FR'] }), { language: 'zh-CN', source: 'fallback' });
});

test('known messages translate, interpolated user data is never translated or evaluated', () => {
  setLocale('en'); assert.equal(getLocale(), 'en'); assert.equal(t('保存修改'), 'Save changes');
  const name = '保存修改 <script> {1} $&';
  assert.equal(msg`播放 ${name}`, `Play ${name}`);
  assert.equal(t(name), name);
  assert.equal(escapeHtml('<"&\'>'), '&lt;&quot;&amp;&#39;&gt;');
  setLocale('zh-CN'); assert.equal(t('保存修改'), '保存修改');
  assert.equal(msg`播放 ${name}`, `播放 ${name}`);
});

import { translateMessage } from '../js/i18n.js';
import { validateVoice } from '../js/validation.js';
import { readPreference, savePreference } from '../js/locale-control.js';
import english from '../js/locales/en.js';
import extraEnglish from '../js/locales/en-extra.js';

test('existing validation messages retranslate system terms but not user interpolation', () => {
  setLocale('zh-CN'); let message;
  try { validateVoice({ ref: { kind: 'provider_voice', provider: 'minimax', region: 'cn', voice_id: 'valid_voice' }, voice_settings: { speed: 100 } }); } catch (error) { message = error.message; }
  const userMessage = msg`播放 ${'语速'}`;
  setLocale('en');
  assert.equal(translateMessage(message), 'Speech rate is out of range');
  assert.equal(translateMessage(userMessage), 'Play 语速');
  setLocale('zh-CN');
});

test('catalogs keep all numbered parameters and contain usable translations', () => {
  const params = value => [...value.matchAll(/\{\d+\}/g)].map(match => match[0]).sort();
  for (const [key, value] of Object.entries({...english, ...extraEnglish})) {
    assert.ok(value.trim(), key); assert.deepEqual(params(value), params(key), key);
  }
});

test('blocked preference storage never prevents switching and malformed tags are ignored', () => {
  const blocked = { getItem() { throw new Error('blocked'); }, setItem() { throw new Error('blocked'); } };
  assert.equal(readPreference(blocked), 'auto'); assert.doesNotThrow(() => savePreference(blocked,'en'));
  assert.equal(normalizeLocale('en-<script>'), null);
  assert.equal(readPreference({ getItem: () => 'zh_Hans' }), 'zh-CN');
});
