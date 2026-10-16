// Frontend-only test server. It mocks redacted metadata and never imports Python/Core.
const { chromium } = require('playwright');
const { expect } = require('playwright/test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const http = require('node:http');
const root = path.resolve(__dirname, '..'), output = path.join(root, 'qa', 'bilingual');
const descriptors = ['minimax', 'volcengine'].map(id => ({ id, name: id === 'minimax' ? 'MiniMax' : '火山引擎', region: 'configured', source: 'mock_fixture',
  ...JSON.parse(fs.readFileSync(path.join(__dirname, 'fixtures', 'providers', id, 'config.json'))),
  support: id === 'minimax' ? 'Mock 配置 · 不进行真实生成' : '仅保存配置，暂不可由本 Skill 生成',
  url: id === 'minimax' ? 'https://www.minimax.cn/audio' : 'https://docs.volcengine.com/docs/DoubaoVoice/Tasksubmission?lang=zh',
  identifier_label: id === 'minimax' ? 'MiniMax Voice ID' : '音色标识（speaker）', help: 'Mock 脱敏元数据；仅用于前端交互验证。', message: '模型来自隔离配置 fixture',
  identifier_pattern: id === 'minimax' ? '^[A-Za-z0-9][A-Za-z0-9_-]{0,255}$' : null }));
const evidence = { status: 'RUNNING', scope: 'frontend_only_no_core_tests', checks: [], errors: [], externalRequests: [], businessRequests: [], failedResponses: [] };
let browser, server, base;
async function check(name, run) { try { await run(); evidence.checks.push({ name, status: 'PASS' }); } catch (error) { evidence.checks.push({ name, status: 'FAIL', error: error.message }); throw error; } }
async function context(options = {}) {
  const ctx = await browser.newContext({ viewport: { width: 1440, height: 900 }, locale: 'zh-CN', ...options });
  await ctx.route('**/*', route => { const request = route.request(), url = new URL(request.url()); if (url.origin !== base) { evidence.externalRequests.push(url.href); return route.abort(); } if (request.method() !== 'GET' || ['fetch', 'xhr', 'websocket'].includes(request.resourceType()) && url.pathname !== '/api/providers') { evidence.businessRequests.push(url.href); return route.abort(); } return route.continue(); });
  await ctx.addInitScript(() => { const AudioClass = window.Audio; window.__testAudio = []; window.Audio = function(url) { const audio = new AudioClass(url); window.__testAudio.push(audio); return audio; }; });
  return ctx;
}
function track(page) { page.on('pageerror', error => evidence.errors.push(error.message)); page.on('console', item => { if (item.type() === 'error') evidence.errors.push(item.text()); }); page.on('response', response => { if (response.status() >= 400) evidence.failedResponses.push(response.url()); }); page.setDefaultTimeout(7000); }
(async () => {
  fs.mkdirSync(output, { recursive: true });
  server = http.createServer((request, response) => {
    const url = new URL(request.url, 'http://localhost');
    if (url.pathname === '/api/providers') { response.writeHead(200, { 'Content-Type': 'application/json', 'Cache-Control': 'no-store' }); response.end(JSON.stringify({ providers: descriptors })); return; }
    const file = path.resolve(root, '.' + decodeURIComponent(url.pathname === '/' ? '/index.html' : url.pathname));
    if (!file.startsWith(root + path.sep) || !fs.existsSync(file) || !fs.statSync(file).isFile()) { response.writeHead(404); response.end(); return; }
    const body = fs.readFileSync(file), type = { '.html': 'text/html', '.js': 'text/javascript', '.css': 'text/css', '.svg': 'image/svg+xml', '.wav': 'audio/wav' }[path.extname(file)] ?? 'application/octet-stream'; response.writeHead(200, { 'Content-Type': type, 'Content-Length': body.length, 'Cache-Control': 'no-store' }); response.end(body);
  });
  await new Promise(resolve => server.listen(0, '127.0.0.1', resolve)); base = `http://127.0.0.1:${server.address().port}`;
  browser = await chromium.launch({ headless: true, channel: 'msedge', args: ['--disable-background-networking'] }); evidence.browser = browser.version();
  async function open({locale, host, manual} = {}) {
    const ctx = await context({ locale: locale ?? 'en-US' });
    if (manual) await ctx.addInitScript(value => localStorage.setItem('castvox.ui-language', value), manual);
    if (host) await ctx.route('**/js/session.js', route => route.fulfill({contentType: 'text/javascript', body: `export const session = Object.freeze(${JSON.stringify({ mode: 'mock', ui_language: host })});`}));
    const page = await ctx.newPage(); track(page);
    await page.goto(base);
    await expect(page.locator('#default-general')).toBeVisible();
    const state = () => page.evaluate(async () => (await import('/js/app.js?v=config-editor-1')).store.getState());
    await expect.poll(async () => (await state()).busy).toBe(false);
    return {ctx,page,state};
  }
  const {ctx,page,state} = await open({locale:'zh-CN',host:'en'});
  await expect(page.locator('html')).toHaveAttribute('lang','en');
  await expect(page.locator('#ui-language')).toHaveAttribute('title','Using launch language');
  await expect(page.locator('#tab-add')).toHaveText('Add project voice');
  await expect(page.locator('select#ui-language')).toHaveCount(0);
  await expect(page.locator('#ui-language button[data-language="en"]')).toHaveAttribute('aria-pressed','true');
  const chineseButton = page.locator('#ui-language button[data-language="zh-CN"]'), englishButton = page.locator('#ui-language button[data-language="en"]');
  const offset = button => button.evaluate(node=>new DOMMatrixReadOnly(getComputedStyle(node).transform).m41);
  await expect.poll(()=>offset(englishButton)).toBe(3);
  await chineseButton.hover(); await expect.poll(()=>offset(chineseButton)).toBe(1.5);
  await page.locator('header').screenshot({path:path.join(output,'language-hover.png')});
  await page.mouse.down(); await expect.poll(()=>offset(chineseButton)).toBe(3);
  await page.locator('header').screenshot({path:path.join(output,'language-pressed.png')});
  await page.mouse.up(); await expect(page.locator('html')).toHaveAttribute('lang','zh-CN');
  await englishButton.focus(); await page.keyboard.press('Enter');
  await expect(page.locator('html')).toHaveAttribute('lang','en');
  await expect(englishButton).toBeFocused();

  await page.locator('#voice-name').fill('保存修改 <script> {0}');
  await page.locator('#voice-id').fill('Voice_ID_UNCHANGED');
  await page.locator('#default-general').click();
  await page.locator('.project-voice-card[data-voice-id="pv_001"] .voice-body').click();
  const before = await state();
  await page.locator('#ui-language button[data-language="zh-CN"]').click();
  await expect(page.locator('#tab-add')).toHaveText('添加项目声音');
  assert.deepEqual(await state(),before);
  await expect(page.locator('#voice-name')).toHaveValue('保存修改 <script> {0}');
  await expect(page.locator('#voice-id')).toHaveValue('Voice_ID_UNCHANGED');
  await page.locator('#ui-language button[data-language="en"]').click();
  await expect(page.locator('#complete-settings')).toBeEnabled();
  await page.locator('#complete-settings').click();
  await expect(page.locator('#confirm-title')).toHaveText('Confirm defaults and finish');
  await expect(page.locator('#ui-language button').first()).toBeDisabled();
  await page.screenshot({path:path.join(output,'english-confirmation.png'),fullPage:true});
  await page.keyboard.press('Escape');
  assert.equal((await state()).defaultsDraft.general,'pv_001');
  await page.locator('#ui-language button[data-language="zh-CN"]').click();
  await page.screenshot({path:path.join(output,'chinese.png'),fullPage:true});
  await page.locator('#ui-language button[data-language="en"]').click();
  // Repeated remounts must not duplicate writes or retain stale subscribers.
  await page.evaluate(async()=>{const {api}=await import('/js/app.js?v=config-editor-1');window.calls={save:0,submit:0};for(const [method,key] of [['saveDefaults','save'],['submitAnswer','submit']]){const original=api[method];api[method]=async(...args)=>{window.calls[key]++;return original(...args);};}});
  await page.locator('#complete-settings').click();
  await page.locator('#confirm-save').click();
  await expect.poll(async () => (await state()).receipt?.answer?.defaults?.general).toBe('pv_001');
  assert.deepEqual(await page.evaluate(()=>window.calls),{save:1,submit:1});
  for (const [width,height] of [[1440,900],[1024,768],[390,844]]) {
    await page.setViewportSize({width,height});
    await page.screenshot({path:path.join(output,`english-${width}.png`),fullPage:true});
    if (await page.evaluate(()=>document.documentElement.scrollWidth>innerWidth)) console.log(await page.locator('body *').evaluateAll(nodes=>nodes.filter(n=>{const b=n.getBoundingClientRect();return b.width&&b.right>innerWidth+1;}).map(n=>({tag:n.tagName,id:n.id,class:n.className,right:n.getBoundingClientRect().right,width:n.getBoundingClientRect().width})).slice(0,25)));
    assert.equal(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth),true,`horizontal overflow at ${width}`);
    await page.screenshot({path:path.join(output,`english-${width}.png`),fullPage:true});
  }
  await ctx.close();
  for(const scenario of [
    {locale:'en-US',expected:'zh-CN',source:'使用中文默认语言'},
    {locale:'zh-CN',expected:'zh-CN',source:'使用中文默认语言'},
    {locale:'fr-FR',expected:'zh-CN',source:'使用中文默认语言'},
    {locale:'en-US',host:'en',manual:'zh-CN',expected:'zh-CN',source:'手动选择语言'}
  ]) {
    const current=await open(scenario);
    await expect(current.page.locator('html')).toHaveAttribute('lang',scenario.expected);
    await expect(current.page.locator('#ui-language')).toHaveAttribute('title',scenario.source);
    await current.ctx.close();
  }
  assert.deepEqual(evidence.errors,[]); assert.deepEqual(evidence.externalRequests,[]); assert.deepEqual(evidence.businessRequests,[]);
  console.log('PASS bilingual: host/manual/Chinese fallback priority, drafts and user text preserved, translated dialogs, one save+submit, desktop/mobile no overflow.');
})().catch(error=>{console.error(error);process.exitCode=1;}).finally(async()=>{await browser?.close();await new Promise(resolve=>server?server.close(resolve):resolve());});
