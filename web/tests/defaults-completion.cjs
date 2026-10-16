// Frontend-only test server. It mocks redacted metadata and never imports Python/Core.
const { chromium } = require('playwright');
const { expect } = require('playwright/test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const http = require('node:http');
const root = path.resolve(__dirname, '..'), output = path.join(root, 'qa', 'defaults-completion');
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
  const ctx = await context(), page = await ctx.newPage(); track(page);
  const state = () => page.evaluate(async () => (await import('/js/app.js?v=config-editor-1')).store.getState());
  const ready = async () => expect.poll(async () => (await state()).busy).toBe(false);
  const action = name => page.getByRole('button', { name, exact: true });
  const tab = name => page.getByRole('tab', { name, exact: true });
  const card = id => page.locator(`.project-voice-card[data-voice-id="${id}"]`);
  const field = name => page.getByLabel(name, { exact: true }).filter({ visible: true });
  await page.goto(base); await ready();
  await expect(page.locator('#default-general')).toBeVisible();
  await expect(page.locator('#save-defaults')).toHaveCount(0);
  await expect(page.locator('#cancel-defaults')).toHaveCount(0);
  await page.locator('#default-general').click();
  await card('pv_001').locator('.voice-body').click();
  await expect(page.locator('#complete-settings')).toBeEnabled();
  await page.locator('#complete-settings').click();
  await expect(page.locator('#confirm-title')).toHaveText('确认默认设置并完成');
  assert.equal((await state()).data.defaults.general, null);
  await page.keyboard.press('Escape');
  await expect(page.getByRole('dialog', { name: '确认默认设置并完成' })).not.toBeVisible();
  assert.equal((await state()).defaultsDraft.general, 'pv_001');
  await page.locator('#complete-settings').click();
  await page.screenshot({path: path.join(output, 'confirmation.png'), fullPage: true});
  await page.getByRole('button', { name: '确认并完成', exact: true }).click();
  await expect.poll(async () => (await state()).receipt?.answer?.defaults?.general).toBe('pv_001');
  assert.equal((await state()).data.defaults.general, 'pv_001');
  assert.deepEqual(evidence.errors, []);
  console.log('PASS: buttons removed, draft enables completion, confirmation, Escape preserves draft, confirm saves and submits.');
})().catch(error => { console.error(error); process.exitCode = 1; }).finally(async () => { await browser?.close(); await new Promise(resolve => server ? server.close(resolve) : resolve()); });
