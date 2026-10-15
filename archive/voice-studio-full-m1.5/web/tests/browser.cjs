// Requires existing Playwright + Chromium; never downloads browsers or dependencies.
const { chromium } = require('playwright');
const { expect } = require('playwright/test');
const assert = require('node:assert/strict');
const { spawn } = require('node:child_process');
const fs = require('node:fs');
const path = require('node:path');
const net = require('node:net');
const { pathToFileURL } = require('node:url');
const root = path.resolve(__dirname, '..');
const output = path.join(root, 'qa', 'role-context');
const evidence = { status: 'RUNNING', checks: [], errors: [], externalRequests: [], businessRequests: [], failedResponses: [] };
let browser, server;
async function check(name, run) {
  try { await run(); evidence.checks.push({ name, status: 'PASS' }); }
  catch (error) { evidence.checks.push({ name, status: 'FAIL', error: error.message }); throw error; }
}
async function availablePort() {
  const probe = net.createServer(); await new Promise(resolve => probe.listen(0, '127.0.0.1', resolve));
  const port = probe.address().port; await new Promise(resolve => probe.close(resolve)); return port;
}
(async () => {
  fs.mkdirSync(output, { recursive: true });
  const port = await availablePort(); const base = `http://127.0.0.1:${port}`;
  server = spawn(process.env.PYTHON || 'python', ['-m', 'http.server', String(port), '--bind', '127.0.0.1', '--directory', root], { windowsHide: true, stdio: ['ignore', 'ignore', 'pipe'] });
  let serverError = ''; server.on('error', error => { serverError = error.message; });
  server.stderr.on('data', () => {});
  await expect.poll(async () => { if (serverError) throw new Error(serverError); try { return (await fetch(base)).status; } catch { return 0; } }, { timeout: 10000 }).toBe(200);
  const options = { headless: true, args: ['--disable-background-networking'] };
  if (process.env.STUDIO_CHROMIUM) options.executablePath = process.env.STUDIO_CHROMIUM;
  browser = await chromium.launch(options); evidence.browser = browser.version();
  const context = await browser.newContext({ viewport: { width: 1440, height: 1000 } });
  await context.route('**/*', route => {
    const request = route.request();
    if (new URL(request.url()).origin !== base) { evidence.externalRequests.push(request.url()); return route.abort(); }
    if (['fetch', 'xhr', 'websocket', 'eventsource'].includes(request.resourceType()) || request.method() !== 'GET') evidence.businessRequests.push(request.url());
    return route.continue();
  });
  const page = await context.newPage();
  page.setDefaultTimeout(7000);
  page.on('pageerror', error => evidence.errors.push(error.message));
  page.on('console', message => { if (message.type() === 'error') evidence.errors.push(message.text()); });
  page.on('response', response => { if (response.status() >= 400) evidence.failedResponses.push(response.url()); });
  const openPool = async () => { if (await page.locator('#pool-toggle').getAttribute('aria-expanded') === 'false') await page.locator('#pool-toggle').click(); };
  const response = await page.goto(base);
  await check('HTTP page and ES modules bootstrap successfully', async () => {
    assert.equal(response.status(), 200);
    await expect(page.getByRole('heading', { name: '声音故事 · 演示项目' })).toBeVisible();
    await expect(page.locator('#load-status')).toContainText('Mock 数据已加载');
    await expect(page.getByRole('tab', { name: '基础设置' })).toHaveAttribute('aria-selected', 'true');
    await expect(page.getByRole('tabpanel')).toContainText('请选择角色');
    await expect(page.locator('#pool-status')).toContainText('6 / 6');
  });
  await check('Debug opens and displays test event fields', async () => {
    await page.getByRole('button', { name: '打开 Debug' }).click();
    await expect(page.locator('#debug-panel')).toBeVisible();
    await page.getByRole('button', { name: '记录测试事件' }).click();
    const row = page.getByRole('row').filter({ hasText: 'debug.test' });
    await expect(row).toContainText('MOCK_PROJECT_A'); await expect(row).toContainText('测试事件成功');
  });
  await check('Mock success and failure are visible without unhandled errors', async () => {
    await page.getByRole('button', { name: '测试 Mock 返回' }).click();
    await expect(page.locator('#debug-status')).toHaveText('返回 3 个 Mock 声音');
    await page.getByRole('button', { name: '测试 Mock 错误' }).click();
    await expect(page.getByRole('row').filter({ hasText: 'api.workspace.failure' })).toContainText('模拟加载失败');
  });
  await check('Debug clears, closes, reopens and shows current state', async () => {
    await page.getByRole('button', { name: '清空日志' }).click();
    await expect(page.locator('#event-rows tr')).toHaveCount(0);
    await page.locator('#debug-close').click(); await expect(page.locator('#debug-panel')).toBeHidden();
    await page.getByRole('button', { name: '打开 Debug' }).click();
    await expect(page.locator('#state-view')).toContainText('MOCK_PROJECT_A');
  });
  await check('Tabs support keyboard and generation remains a placeholder', async () => {
    const tab = page.getByRole('tab', { name: '探索更多' }); await tab.focus(); await tab.press('ArrowRight');
    await expect(page.getByRole('tabpanel')).toContainText('本阶段仅保留占位');
    await page.getByRole('tab', { name: '音色生成', exact: true }).press('Home');
    await expect(page.getByRole('tab', { name: '基础设置' })).toBeFocused();
  });
  await page.getByRole('tab', { name: '探索更多' }).click();
  await page.locator('#debug-close').click();
  await page.screenshot({ path: path.join(output, 'desktop.png'), fullPage: true });
  await check('Desktop and narrow viewports do not overflow', async () => {
    for (const width of [1440, 390, 320]) {
      await page.setViewportSize({ width, height: 1000 });
      assert.ok(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth), `overflow at ${width}`);
    }
  });
  await page.screenshot({ path: path.join(output, 'mobile.png'), fullPage: true });
  await page.setViewportSize({ width: 1440, height: 1000 });
  await check('Long card visual order, always visible settings and hover geometry', async () => {
    const card = page.locator('.project-voice-card').first();
    const boxes = async () => Promise.all(['.voice-avatar', '.voice-preview', '.voice-name', '.voice-settings'].map(selector => card.locator(selector).boundingBox()));
    const before = await boxes();
    for (let n = 0; n < before.length - 1; n++) assert.ok(before[n].x + before[n].width <= before[n + 1].x + 1, 'left-to-right order');
    assert.equal((await card.boundingBox()).width, 240); assert.equal((await card.boundingBox()).height, 56);
    await expect(card.locator('.voice-settings')).toBeVisible();
    await card.hover(); assert.deepEqual(await boxes(), before);
  });
  await check('Card selection and settings emit separate events and correct detail ID', async () => {
    await page.evaluate(async () => (await import('/js/events.js')).eventLog.clear());
    await page.getByRole('button', { name: '选择项目声音：叙述男声', exact: true }).click();
    await expect(page.getByRole('tab', { name: '探索更多' })).toHaveAttribute('aria-selected', 'true');
    await expect(page.locator('#library-feedback')).toContainText('已选择：叙述男声');
    await page.getByRole('button', { name: '设置 温柔女声', exact: true }).click();
    await expect(page.getByRole('tab', { name: '基础设置' })).toHaveAttribute('aria-selected', 'true');
    await expect(page.getByRole('tabpanel')).toContainText('请选择角色');
    await page.getByRole('tab',{name:'探索更多'}).click();
    await expect(page.getByRole('tabpanel')).toContainText('当前音色：温柔女声');
    await expect(page.getByRole('tabpanel')).toContainText('MOCK_VOICE_B');
    const events = await page.evaluate(async () => (await import('/js/events.js')).eventLog.getEntries().filter(event => event.name.startsWith('library.')));
    assert.deepEqual(events.map(event => [event.name, event.objectId]), [['library.card.select', 'MOCK_VOICE_A'], ['library.settings.open', 'MOCK_VOICE_B']]);
    await page.getByRole('button', { name: '打开 Debug' }).click();
    await expect(page.getByRole('row').filter({ hasText: 'library.settings.open' })).toContainText('MOCK_VOICE_B');
    await page.locator('#debug-close').click();
  });
  await check('Local Mock preview plays and stops without selecting or opening settings', async () => {
    await page.evaluate(async () => (await import('/js/events.js')).eventLog.clear());
    const label = '叙述男声（本地 Mock 提示音）';
    await page.getByRole('button', { name: `试听 ${label}`, exact: true }).click();
    await expect(page.locator('#library-feedback')).toContainText('正在播放本地 Mock 提示音');
    await page.getByRole('button', { name: `停止 ${label}`, exact: true }).click();
    await expect(page.getByRole('button', { name: `试听 ${label}`, exact: true })).toBeVisible();
    const events = await page.evaluate(async () => (await import('/js/events.js')).eventLog.getEntries().filter(event => event.name.startsWith('library.')));
    assert.deepEqual(events.map(event => event.name), ['library.preview.loading', 'library.preview.playing', 'library.preview.stopped']);
    assert.ok(events.every(event => event.objectId === 'MOCK_VOICE_A'));
    await expect(page.getByRole('tabpanel')).toContainText('当前音色：温柔女声');
  });
  await check('Keyboard can select, preview and open settings independently', async () => {
    const body = page.getByRole('button', { name: '选择项目声音：叙述男声', exact: true });
    await body.focus(); await body.press('Enter'); await body.press('Tab');
    await expect(page.getByRole('button', { name: '试听 叙述男声（本地 Mock 提示音）', exact: true })).toBeFocused();
    await page.keyboard.press('Tab');
    await expect(page.getByRole('button', { name: '设置 叙述男声', exact: true })).toBeFocused();
    await page.keyboard.press('Enter'); await expect(page.locator('#role-required')).toBeVisible();await page.getByRole('tab',{name:'探索更多'}).click(); await expect(page.getByRole('tabpanel')).toContainText('MOCK_VOICE_A');
    await page.setViewportSize({ width: 320, height: 640 });
    const settings = page.getByRole('button', { name: '设置 温柔女声', exact: true });
    await settings.focus();
    const scroll = await page.locator('.library-scroll').boundingBox();
    const visibleSettings = await settings.boundingBox();
    assert.ok(visibleSettings.x >= scroll.x && visibleSettings.x + visibleSettings.width <= scroll.x + scroll.width, 'narrow focus reveals settings');
    await settings.press('Enter');await expect(page.locator('#role-required')).toBeVisible();await page.getByRole('tab',{name:'探索更多'}).click(); await expect(page.getByRole('tabpanel')).toContainText('MOCK_VOICE_B');
    await page.setViewportSize({ width: 1440, height: 1000 });
  });
  await check('Agent roles display unassigned and preassigned states with independent bindings', async () => {
    const role = id => page.locator(`[data-role-id="${id}"]`);
    await expect(role('MOCK_ROLE_A')).toContainText('未分配');
    await expect(role('MOCK_ROLE_B')).toContainText('✓ 已分配 · 温柔女声');
    await role('MOCK_ROLE_A').click();
    await expect(role('MOCK_ROLE_A')).toHaveAttribute('aria-pressed', 'true');
    await page.getByRole('button', { name: '选择项目声音：叙述男声', exact: true }).click();
    await expect(role('MOCK_ROLE_A')).toContainText('叙述男声');
    await expect(role('MOCK_ROLE_B')).toContainText('温柔女声');
    await expect(role('MOCK_ROLE_N')).toContainText('未分配');
    await role('MOCK_ROLE_N').click();
    await page.getByRole('button', { name: '选择项目声音：叙述男声', exact: true }).click();
    await role('MOCK_ROLE_A').click();
    await page.getByRole('button', { name: '选择项目声音：未分类声音', exact: true }).click();
    await expect(role('MOCK_ROLE_A')).toContainText('未分类声音');
    await expect(role('MOCK_ROLE_N')).toContainText('叙述男声');
    await expect(page.locator('#target-context')).toContainText('语速 1.1');
    await role('MOCK_ROLE_B').click();
    await expect(page.locator('#target-context')).toContainText('语速 0.9 · 音量 0.8');
    await role('MOCK_ROLE_A').click();
    await expect(page.locator('#target-context')).toContainText('未分类声音 / 语速 1.1');
    await expect(page.locator('#default-label')).toHaveText('尚未设置');
    await page.getByRole('button', { name: '打开 Debug' }).click();
    await expect(page.getByRole('row').filter({ hasText: 'requirements.role.assigned' }).first()).toContainText('MOCK_ROLE_A');
    await page.locator('#debug-close').click();
    await page.screenshot({ path: path.join(output, 'assigned-desktop.png'), fullPage: true });
  });
  await check('Default quick dialog confirms, cancels and preserves roles and editor context', async () => {
    const before = await page.evaluate(async () => { const s=(await import('/js/store.js')).store.getState();return { task:s.task, editor:s.editor, target:s.ui.target }; });
    await page.locator('#default-target').click();
    await expect(page.locator('#default-confirmation')).toBeVisible();
    await page.getByLabel('默认声音候选').selectOption('MOCK_VOICE_B');
    await expect(page.locator('#default-diff')).toContainText('尚未设置 → 温柔女声');
    await page.locator('#default-cancel').click(); await expect(page.locator('#default-label')).toHaveText('尚未设置');
    await page.locator('#default-target').click(); await page.keyboard.press('Escape'); await expect(page.locator('#default-confirmation')).toBeHidden();
    await page.locator('#default-target').click(); await page.getByLabel('默认声音候选').selectOption('MOCK_VOICE_B');
    await page.screenshot({ path:path.join(output,'default-confirmation.png'),fullPage:true });
    await page.locator('#default-confirm').click(); await expect(page.locator('#default-label')).toHaveText('温柔女声 · Mock 已保存');
    const after = await page.evaluate(async () => { const s=(await import('/js/store.js')).store.getState();return { task:s.task, editor:s.editor, target:s.ui.target, input:s.data.project.defaultVoice }; });
    assert.deepEqual(after.task,before.task); assert.deepEqual(after.editor,before.editor); assert.deepEqual(after.target,before.target); assert.equal(after.input,null);
    await page.reload(); await expect(page.locator('#default-label')).toHaveText('尚未设置');
  });
  await check('No-job management mode can use the quick Mock default without opening the editor', async () => {
    await page.evaluate(async () => { const {store}=await import('/js/store.js');const data=store.getState().data;data.job=null;store.dispatch({type:'LOAD_SUCCESS',data}); });
    await expect(page.locator('#roles')).toContainText('当前无任务角色'); await expect(page.locator('#complete-settings')).toBeHidden();
    await page.locator('#default-target').click(); await page.getByLabel('默认声音候选').selectOption('MOCK_VOICE_A'); await page.locator('#default-confirm').click();
    await expect(page.locator('#default-label')).toHaveText('叙述男声 · Mock 已保存');
    assert.equal(await page.evaluate(async ()=>(await import('/js/store.js')).store.getState().editor.activeKey),null);
    await page.reload(); await expect(page.locator('#pool-status')).toContainText('6 / 6');
  });
  await check('Pool cards retain visible portrait, name and metadata inside fixed-height cards', async () => {
    const metrics = await page.locator('.pool-voice-card').evaluateAll(cards => cards.map(card => {
      const box = card.getBoundingClientRect(); const name = card.querySelector('.pool-name').getBoundingClientRect(); const status = card.querySelector('.pool-availability').getBoundingClientRect();
      return { height: box.height, nameInside: name.y >= box.y && name.bottom <= box.bottom, labelsInside: status.bottom <= box.bottom };
    }));
    assert.equal(metrics.length, 6); assert.ok(metrics.every(metric => metric.height === 192 && metric.nameInside && metric.labelsInside));
    const first = await page.locator('.pool-voice-card').first().boundingBox();
    const list = await page.locator('#pool').boundingBox();
    assert.ok(first.y >= list.y && first.y + first.height <= list.y + list.height + 1, 'desktop first card fully visible');
  });
  await check('Pool filters combine instantly and empty results remain informative', async () => {
    await page.getByLabel('来源', { exact: true }).selectOption('official');
    await expect(page.locator('.pool-voice-card')).toHaveCount(3);
    await page.getByLabel('声音特征', { exact: true }).selectOption('female');
    await expect(page.locator('.pool-voice-card')).toHaveCount(1);
    await page.getByLabel('关键词', { exact: true }).fill('轻柔');
    await expect(page.locator('#pool-status')).toContainText('1 / 6');
    await page.getByLabel('关键词', { exact: true }).fill('无匹配内容');
    await expect(page.locator('.pool-voice-card')).toHaveCount(0);
    await expect(page.locator('#pool')).toContainText('没有匹配的声音');
    await page.getByLabel('关键词', { exact: true }).fill('');
    await page.getByLabel('来源', { exact: true }).selectOption('all');
    await page.getByLabel('声音特征', { exact: true }).selectOption('all');
    await expect(page.locator('.pool-voice-card')).toHaveCount(6);
  });
  await check('Pool selection opens Basic with correct details and does not bind the active role', async () => {
    await page.locator('[data-role-id="MOCK_ROLE_A"]').click();
    const before = await page.evaluate(async () => { const state = (await import('/js/store.js')).store.getState(); return { task: state.task, data: state.data, projectDefault: state.projectDefault }; });
    await page.getByRole('tab', { name: '基础设置' }).click();
    const card = page.locator('[data-pool-id="MOCK_OFFICIAL_B"] .pool-body-button'); await card.focus(); await card.press('Enter');
    await expect(card).toHaveAttribute('aria-pressed', 'true'); await expect(card).toBeFocused();
    await expect(page.getByRole('tab', { name: '基础设置' })).toHaveAttribute('aria-selected', 'true');
    await expect(page.getByRole('tabpanel')).toContainText('当前音色：轻柔讲述');
    await expect(page.getByRole('tabpanel')).toContainText('MOCK_OFFICIAL_B');
    const after = await page.evaluate(async () => { const state = (await import('/js/store.js')).store.getState(); return { task: state.task, data: state.data, projectDefault: state.projectDefault }; });
    assert.deepEqual(after, before);
    await page.getByLabel('关键词', { exact: true }).fill('晴朗');
    await page.getByRole('tab',{name:'探索更多'}).click();
    await expect(page.getByRole('tabpanel')).toContainText('当前候选不在筛选结果中');
    await page.getByLabel('关键词', { exact: true }).fill('');
    await page.screenshot({ path: path.join(output, 'pool-selected.png'), fullPage: true });
  });
  await check('Unknown metadata is not inferred from name; unavailable candidates remain inspectable', async () => {
    await page.getByLabel('来源', { exact: true }).selectOption('user');
    await page.getByLabel('声音特征', { exact: true }).selectOption('female');
    await expect(page.locator('[data-pool-id="MOCK_USER_UNKNOWN"]')).toHaveCount(0);
    await page.getByLabel('声音特征', { exact: true }).selectOption('unknown');
    await expect(page.locator('.pool-voice-card')).toHaveCount(1);
    await openPool(); await page.locator('[data-pool-id="MOCK_USER_UNKNOWN"]').dblclick();
    await page.getByRole('tab',{name:'探索更多'}).click();
    await expect(page.getByRole('tabpanel')).toContainText('性别：unknown');
    await expect(page.getByRole('tabpanel')).toContainText('声音特征：unknown');
    await page.getByLabel('声音特征', { exact: true }).selectOption('沉稳');
    await openPool(); await page.locator('[data-pool-id="MOCK_USER_B"]').dblclick();
    await page.getByRole('tab',{name:'探索更多'}).click();
    await expect(page.getByRole('tabpanel')).toContainText('不可用：模拟：音色暂不可用');
    await expect(page.locator('[data-pool-id="MOCK_USER_B"]')).toContainText('不可用');
    await page.getByLabel('来源', { exact: true }).selectOption('all');
    await page.getByLabel('声音特征', { exact: true }).selectOption('all');
  });
  await check('Debug can demonstrate catalogue failure, manual retry, empty data and recovery', async () => {
    await page.getByRole('button', { name: '打开 Debug' }).click();
    await page.getByRole('button', { name: '声音池：模拟失败', exact: true }).click();
    await expect(page.locator('#pool-status')).toContainText('模拟声音池加载失败');
    await expect(page.getByRole('tabpanel')).toContainText('请选择声音');
    await page.getByRole('button', { name: '重新加载 Mock 声音池', exact: true }).click();
    await expect(page.locator('.pool-voice-card')).toHaveCount(6);
    await page.getByRole('button', { name: '声音池：空列表', exact: true }).click();
    await expect(page.locator('#pool')).toContainText('声音池暂无音色');
    await page.getByRole('button', { name: '声音池：恢复数据', exact: true }).click();
    await expect(page.locator('.pool-voice-card')).toHaveCount(6);
    await expect(page.getByRole('row').filter({ hasText: 'api.catalog.failure' }).last()).toContainText('MOCK_CATALOG');
    await page.locator('#debug-close').click();
    await page.reload(); await expect(page.locator('#pool-status')).toContainText('6 / 6');
  });
  await check('Basic and Explore share all common fields without exposing voice choice or pitch in Basic', async () => {
    await page.locator('[data-role-id="MOCK_ROLE_A"]').click();
    await page.getByRole('button', { name: '设置 叙述男声', exact: true }).click();
    await expect(page.getByLabel('音色选择', { exact: true })).toBeHidden();
    await expect(page.getByLabel('模型选择', { exact: true })).toBeHidden();
    await expect(page.getByLabel('试听文本', { exact: true })).toHaveValue(/清晨的第一束阳光/);
    await page.getByLabel('语速', { exact: true }).fill('1.5');
    await page.getByLabel('音量', { exact: true }).fill('2.1');
    await page.getByLabel('LaTeX 公式朗读', { exact: true }).check();
    await page.getByLabel('中英文文本规范化', { exact: true }).uncheck();
    await page.getByLabel('试听文本', { exact: true }).fill('这是一条由用户编辑的完整试听句子，用于确认切换页面后文本和参数仍然保留。');
    await page.getByRole('tab', { name: '探索更多' }).click();
    await expect(page.getByLabel('模型选择', { exact: true })).toBeVisible();
    await expect(page.getByLabel('音色选择', { exact: true })).toBeVisible();
    await expect(page.getByLabel('语速', { exact: true })).toHaveValue('1.5');
    await expect(page.getByLabel('LaTeX 公式朗读', { exact: true })).toBeChecked();
    await page.getByRole('tab', { name: '音色生成', exact: true }).click();
    await expect(page.getByRole('tabpanel')).toContainText('本阶段仅保留占位');
    await page.getByRole('tab', { name: '基础设置' }).click();
    await expect(page.getByLabel('音量', { exact: true })).toHaveValue('2.1');
    await expect(page.getByLabel('中英文文本规范化', { exact: true })).not.toBeChecked();
    assert.equal(await page.locator('input[name="pitch"],#editor-pitch').count(), 0);
  });
  await check('Mock capability changes retain unsupported emotion and explain disabled options', async () => {
    await page.getByLabel('情绪', { exact: true }).selectOption('sad');
    await page.getByRole('tab', { name: '探索更多' }).click();
    await page.getByRole('tab',{name:'探索更多'}).click(); await page.getByLabel('模型选择', { exact: true }).selectOption('MOCK_STUDIO_LIGHT');
    await expect(page.getByLabel('情绪', { exact: true })).toHaveValue('sad');
    await expect(page.locator('#editor-emotion option[value="sad"]')).toHaveJSProperty('disabled', true);
    await expect(page.locator('#emotion-compatibility')).toContainText('原情绪已保留');
    await expect(page.locator('#editor-preview')).toBeDisabled();
    await page.getByLabel('情绪', { exact: true }).selectOption('happy');
    await expect(page.locator('#editor-preview')).toBeEnabled();
    await page.screenshot({ path: path.join(output, 'explore-settings.png'), fullPage: true });
  });
  await check('Preview result becomes stale after edits and survives tab switching; errors retain text', async () => {
    await page.locator('#editor-preview').click();
    await expect(page.locator('#editor-preview-status')).toContainText('当前参数模拟试听');
    await expect(page.locator('#editor-audio')).toBeVisible();
    await page.getByLabel('语速', { exact: true }).fill('1.6');
    await expect(page.locator('#editor-preview-status')).toContainText('旧参数试听');
    await page.getByRole('tab', { name: '基础设置' }).click();
    await expect(page.locator('#editor-preview-status')).toContainText('旧参数试听');
    await page.screenshot({ path: path.join(output, 'basic-settings.png'), fullPage: true });
    await page.evaluate(async () => { const { api } = await import('/js/api.js'); api.createPreview = async () => { throw new Error('模拟试听失败测试'); }; });
    await page.locator('#editor-preview').click();
    await expect(page.locator('#editor-preview-status')).toContainText('模拟试听失败测试');
    await expect(page.getByLabel('试听文本', { exact: true })).toHaveValue(/用户编辑/);
    await page.reload(); await expect(page.locator('#pool-status')).toContainText('6 / 6');
  });
  await check('Role, project and candidate editors keep independent drafts without changing saved input', async () => {
    const original = await page.evaluate(async () => { const state = (await import('/js/store.js')).store.getState(); return { data: state.data, task: state.task, projectDefault: state.projectDefault }; });
    await page.locator('[data-role-id="MOCK_ROLE_B"]').click();
    await expect(page.getByRole('tab', { name: '基础设置' })).toHaveAttribute('aria-selected', 'true');
    await expect(page.getByLabel('语速', { exact: true })).toHaveValue('0.9');
    await page.getByLabel('语速', { exact: true }).fill('1.2');
    await page.locator('[data-role-id="MOCK_ROLE_A"]').click();
    await expect(page.getByLabel('语速', { exact: true })).toHaveValue('1.1');
    await page.getByLabel('语速', { exact: true }).fill('1.4');
    await page.locator('[data-role-id="MOCK_ROLE_B"]').click();
    await expect(page.getByLabel('语速', { exact: true })).toHaveValue('1.2');
    await page.getByRole('button', { name: '设置 温柔女声', exact: true }).click();
    await expect(page.getByLabel('语速', { exact: true })).toHaveValue('1.2');
    await page.getByLabel('语速', { exact: true }).fill('1.7');
    await openPool(); await page.locator('[data-pool-id="MOCK_OFFICIAL_B"]').dblclick();
    await expect(page.getByLabel('语速', { exact: true })).toHaveValue('1.7');
    await page.getByLabel('语速', { exact: true }).fill('1.8');
    await page.getByRole('tab',{name:'探索更多'}).click(); await page.getByLabel('音色选择', { exact: true }).selectOption('pool:MOCK_OFFICIAL_A');
    await expect(page.getByRole('tabpanel')).toContainText('当前音色：晴朗叙述');
    await page.locator('[data-role-id="MOCK_ROLE_B"]').click();
    await expect(page.getByLabel('语速', { exact: true })).toHaveValue('1.2');
    await openPool(); await page.locator('[data-pool-id="MOCK_OFFICIAL_B"]').dblclick();
    await expect(page.getByLabel('语速', { exact: true })).toHaveValue('1.8');
    const after = await page.evaluate(async () => { const state = (await import('/js/store.js')).store.getState(); return { data: state.data, task: state.task, projectDefault: state.projectDefault }; });
    assert.deepEqual(after, original);
    await page.reload(); await expect(page.locator('#pool-status')).toContainText('6 / 6');
  });
  await check('Current Mock audition unlocks role apply; cache hit and stale configurations are explicit', async () => {
    await page.locator('[data-role-id="MOCK_ROLE_A"]').click();
    await openPool(); await page.locator('[data-pool-id="MOCK_OFFICIAL_A"]').dblclick();
    await expect(page.locator('#flow-role')).toBeDisabled();
    await page.getByRole('button', { name: '打开 Debug' }).click();
    await page.getByRole('button', { name: '下一次试听失败', exact: true }).click();
    await page.locator('#debug-close').click();
    await page.locator('#editor-preview').click();
    await expect(page.locator('#editor-preview-status')).toContainText('模拟试听失败');
    await expect(page.locator('#flow-role')).toBeDisabled();
    await page.locator('#editor-preview').click();
    await expect(page.locator('#editor-preview-status')).toContainText('当前参数模拟试听');
    await page.locator('#editor-preview').click();
    await expect(page.locator('#editor-preview-status')).toContainText('缓存命中');
    await page.getByLabel('音色名称',{exact:true}).fill('晴朗叙述');
    await page.locator('#flow-role').click();
    await expect(page.locator('[data-role-id="MOCK_ROLE_A"]')).toContainText('晴朗叙述');
    await expect(page.locator('[data-role-id="MOCK_ROLE_N"]')).toContainText('未分配');
    await page.getByLabel('语速', { exact: true }).fill('1.3');
    await expect(page.locator('#editor-preview-status')).toContainText('过期配置结果');
    await expect(page.locator('#flow-role')).toBeDisabled();
    await page.locator('#editor-preview').click();
    await expect(page.locator('#flow-role')).toBeEnabled();
    await page.getByLabel('音色名称',{exact:true}).fill('晴朗叙述');
    await page.locator('#flow-role').click();
    await expect(page.locator('#target-context')).toContainText('语速 1.3');
  });
  await check('Library failure and duplicate clicks preserve drafts and create one project voice', async () => {
    await page.getByLabel('音色名称', { exact: true }).fill('新项目旁白');
    await page.getByRole('button', { name: '打开 Debug' }).click();
    await page.getByRole('button', { name: '下一次保存失败', exact: true }).click(); await page.locator('#debug-close').click();
    await page.locator('#flow-save').click();
    await expect(page.locator('#flow-message')).toContainText('模拟保存失败');
    await expect(page.getByLabel('音色名称', { exact: true })).toHaveValue('新项目旁白');
    await page.locator('#flow-retry').click();
    await expect(page.locator('#flow-message')).toContainText('Mock 保存成功');
    await expect(page.getByRole('button', { name: '设置 新项目旁白', exact: true })).toHaveCount(1);
    await expect(page.locator('[data-role-id="MOCK_ROLE_A"]')).toContainText('新项目旁白');
    await page.locator('#flow-save').click();
    await expect(page.locator('#flow-message')).toContainText('重复点击没有再次写入');
    await expect(page.getByRole('button', { name: '设置 新项目旁白', exact: true })).toHaveCount(1);
    await page.screenshot({ path: path.join(output, 'applied-and-saved.png'), fullPage: true });
  });
  await check('Same-name rebind confirms old/new references; revision conflict refreshes then reconfirms', async () => {
    await page.getByLabel('音色名称', { exact: true }).fill('温柔女声');
    await page.getByRole('button', { name: '打开 Debug' }).click();
    await page.getByRole('button', { name: '模拟项目库 revision 冲突', exact: true }).click(); await page.locator('#debug-close').click();
    await page.locator('#flow-save').click();
    await expect(page.locator('#rebind-dialog')).toContainText('project:MOCK_VOICE_B → pool:MOCK_OFFICIAL_A');
    await page.locator('#rebind-confirm').click();
    await expect(page.locator('#flow-message')).toContainText('revision 冲突');
    await expect(page.locator('#rebind-dialog')).toBeHidden();
    await page.locator('#flow-refresh').click();
    await page.locator('#flow-save').click();
    await expect(page.locator('#rebind-dialog')).toContainText('expected revision 2');
    await page.screenshot({ path: path.join(output, 'rebind-confirmation.png'), fullPage: true });
    await page.locator('#rebind-confirm').click();
    await expect(page.locator('#flow-message')).toContainText('Mock 保存成功');
    await expect(page.locator('[data-role-id="MOCK_ROLE_B"]')).toContainText('温柔女声');
    const state = await page.evaluate(async () => (await import('/js/store.js')).store.getState());
    assert.equal(state.task.selections.MOCK_ROLE_B.voiceRef, 'project:MOCK_VOICE_B');
    assert.equal(state.task.selections.MOCK_ROLE_A.voiceRef, 'pool:MOCK_OFFICIAL_A');
  });
  await check('Completion summary distinguishes missing roles and complete Mock settings', async () => {
    await page.locator('#complete-settings').click();
    await expect(page.locator('#summary-state')).toContainText('仍有 1 个角色未分配');
    await expect(page.locator('#harness-status')).toContainText('未通知 Harness');
    await page.locator('#summary-close').click();
    await page.locator('[data-role-id="MOCK_ROLE_N"]').click();
    await page.getByRole('button', { name: '选择项目声音：叙述男声', exact: true }).click();
    await page.locator('#complete-settings').click();
    await expect(page.locator('#summary-state')).toContainText('全部角色已分配');
    await expect(page.locator('#harness-status')).toContainText('本次配置已通知 Harness（Mock）');
    await expect(page.locator('#summary-rows')).toContainText('主角 A');
    await expect(page.locator('#summary-rows')).toContainText('旁白');
    await page.screenshot({ path: path.join(output, 'assignment-summary.png'), fullPage: true });
    await page.locator('#summary-close').click();
    await page.reload(); await expect(page.locator('#pool-status')).toContainText('6 / 6');
  });
  await check('Quick default remains independent while management saves with no role binding', async () => {
    await page.locator('[data-role-id="MOCK_ROLE_A"]').click();
    await page.locator('#default-target').click();
    await expect(page.locator('#default-confirmation')).toBeVisible();
    await page.getByLabel('默认声音候选').selectOption('MOCK_VOICE_C');
    await page.locator('#default-confirm').click();
    await expect(page.locator('#default-label')).toContainText('未分类声音 · Mock 已保存');
    await expect(page.locator('[data-role-id="MOCK_ROLE_A"]')).toContainText('未分配');
    await page.evaluate(async () => { const { store } = await import('/js/store.js'); const data = store.getState().data; data.job = null; store.dispatch({ type: 'LOAD_SUCCESS', data }); });
    await openPool(); await page.locator('[data-pool-id="MOCK_OFFICIAL_A"]').dblclick();
    await page.getByRole('tab',{name:'探索更多'}).click();
    await page.locator('#editor-preview').click(); await expect(page.locator('#flow-save')).toBeEnabled();
    await expect(page.locator('#flow-role')).toBeDisabled();
    await page.getByLabel('音色名称', { exact: true }).fill('管理专用声音');
    await page.locator('#flow-save').click(); await expect(page.locator('#flow-message')).toContainText('Mock 保存成功');
    await expect(page.locator('#roles button')).toHaveCount(0);
    await page.reload(); await expect(page.locator('#pool-status')).toContainText('6 / 6');
  });
  await check('01 and 02 share one outer panel; pool stays separate', async () => {
    await expect(page.locator('.workspace-left > .panel')).toHaveCount(2);
    await expect(page.locator('.assignment-workspace > .project-section')).toHaveCount(1);
    await expect(page.locator('.assignment-workspace > .requirements-section')).toHaveCount(1);
    assert.equal(await page.locator('.pool-panel').evaluate(node => node.closest('.assignment-workspace')), null);
  });
  await check('Desktop columns and narrow stacking have distinct boundaries', async () => {
    for (const width of [1920, 1440, 1280, 1024, 851, 850, 768, 390, 320]) {
      await page.setViewportSize({ width, height: 900 });
      const left = await page.locator('.workspace-left').boundingBox();
      const right = await page.locator('.settings').boundingBox();
      if (width > 850) {
        assert.ok(right.x >= left.x + left.width + 16, `column gap at ${width}`);
        assert.ok(Math.abs(left.y - right.y) < 1, `aligned top at ${width}`);
        assert.ok(Math.abs(left.height - right.height) < 1, `aligned bottom at ${width}`);
        const panel = await page.locator('.assignment-workspace').boundingBox();
        const roles = await page.locator('.requirements').boundingBox();
        assert.ok(roles.y + roles.height <= panel.y + panel.height - 5, `requirements visible at ${width}`);
      } else assert.ok(right.y >= left.y + left.height, `stacked at ${width}`);
      assert.ok(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth), `overflow at ${width}`);
    }
  });
  await check('Large data and long names stay in bounded scroll regions', async () => {
    await page.setViewportSize({ width: 1440, height: 900 });
    const before = await page.locator('main').boundingBox();
    await page.evaluate(async () => {
      const { store } = await import('/js/store.js');
      const data = store.getState().data;
      data.voices = Array.from({ length: 120 }, (_, n) => ({ id: `MOCK_VOICE_${n}`, name: n === 0 ? '长名称LongName'.repeat(30) : `演示声音 ${n}`, gender: ['male', 'female', 'unknown'][n % 3], provenance: '本地压力测试数据' }));
      data.roles = Array.from({ length: 80 }, (_, n) => ({ id: `MOCK_ROLE_${n}`, name: n === 0 ? '长角色名称'.repeat(30) : `角色 ${n}`, voiceId: null }));
      store.dispatch({ type: 'LOAD_SUCCESS', data });
      const catalog = store.getState().catalog.voices;
      store.dispatch({ type: 'CATALOG_LOAD_SUCCESS', voices: Array.from({ length: 120 }, (_, n) => ({ ...catalog[n % catalog.length], id: `MOCK_POOL_${n}`, name: `声音池候选 ${n}` })) });
    });
    for (const viewport of [{ width: 1440, height: 900 }, { width: 1024, height: 600 }, { width: 851, height: 900 }, { width: 850, height: 900 }, { width: 390, height: 844 }, { width: 320, height: 640 }]) {
      await page.setViewportSize(viewport);
      const metrics = await page.evaluate(() => {
        const measure = selector => { const node = document.querySelector(selector); return { width: node.clientWidth, scrollWidth: node.scrollWidth, height: node.clientHeight, scrollHeight: node.scrollHeight }; };
        return { overflow: document.documentElement.scrollWidth > innerWidth, library: measure('.library-scroll'), roles: measure('.role-strip'), pool: measure('#pool'), assignment: measure('.assignment-workspace') };
      });
      assert.equal(metrics.overflow, false, `stress overflow ${viewport.width}`);
      assert.ok(metrics.library.scrollWidth > metrics.library.width, 'library scrolls horizontally');
      assert.ok(metrics.roles.scrollWidth > metrics.roles.width, 'roles scroll horizontally');
      assert.ok(metrics.pool.scrollHeight > metrics.pool.height && metrics.pool.height > 0, 'pool has bounded vertical scroll');
      assert.ok(metrics.assignment.height <= 700, 'upper panel bounded');
    }
    await page.setViewportSize({ width: 1440, height: 900 });
    const after = await page.locator('main').boundingBox();
    assert.equal(after.width, before.width); assert.equal(after.height, before.height);
    const geometry = await page.evaluate(() => {
      const cards = [...document.querySelectorAll('.project-voice-card')];
      const firstRows = ['male', 'female'].map(category => document.querySelector(`[data-category="${category}"] .project-voice-card`));
      const before = firstRows.map(node => node.getBoundingClientRect().x);
      const labels = [...document.querySelectorAll('.row-label')].map(node => node.getBoundingClientRect().x);
      const number = document.querySelector('.library-number').getBoundingClientRect().x;
      document.querySelector('.library-scroll').scrollLeft = 180;
      return {
        sizes: cards.map(node => ({ w: node.getBoundingClientRect().width, h: node.getBoundingClientRect().height })),
        deltas: firstRows.map((node, n) => before[n] - node.getBoundingClientRect().x),
        fixedLabels: [...document.querySelectorAll('.row-label')].every((node, n) => node.getBoundingClientRect().x === labels[n]),
        fixedNumber: document.querySelector('.library-number').getBoundingClientRect().x === number,
        gap: firstRows.map(node => node.nextElementSibling.getBoundingClientRect().x - node.getBoundingClientRect().right),
        truncated: document.querySelector('.voice-name').scrollWidth > document.querySelector('.voice-name').clientWidth
      };
    });
    assert.ok(geometry.sizes.every(size => size.w === 240 && size.h === 56));
    assert.deepEqual(geometry.deltas, [180, 180]); assert.deepEqual(geometry.gap, [12, 12]);
    assert.ok(geometry.fixedLabels && geometry.fixedNumber && geometry.truncated);
    await page.evaluate(() => { document.querySelector('.library-scroll').scrollLeft = 0; });
    await page.screenshot({ path: path.join(output, 'dense-desktop.png'), fullPage: true });
  });
  await check('Many roles support End/Home selection and independent scroll positioning', async () => {
    const libraryBefore = await page.locator('.library-scroll').evaluate(node => node.scrollLeft);
    const fixedBefore = await page.locator('#default-target').boundingBox();
    const first = page.locator('#roles button').first(); await first.focus(); await first.press('End');
    const last = page.locator('#roles button').last();
    await expect(last).toBeFocused(); await expect(last).toHaveAttribute('aria-pressed', 'true');
    assert.ok(await page.locator('#roles').evaluate(node => node.scrollLeft > 0));
    assert.equal(await page.locator('.library-scroll').evaluate(node => node.scrollLeft), libraryBefore);
    assert.equal((await page.locator('#default-target').boundingBox()).x, fixedBefore.x);
    const visibleRole = await last.boundingBox(); const strip = await page.locator('#roles').boundingBox();
    assert.ok(visibleRole.x >= strip.x - 1 && visibleRole.x + visibleRole.width <= strip.x + strip.width + 1, JSON.stringify({ visibleRole, strip }));
    await last.press('Home'); await expect(first).toBeFocused();
    assert.equal(await page.locator('#roles').evaluate(node => node.scrollLeft), 0);
  });
  await check('Scroll containers move independently; UI changes retain list positions', async () => {
    const defaultBefore = await page.locator('.default-voice').boundingBox();
    const scrolls = await page.evaluate(() => {
      const library = document.querySelector('.library-scroll');
      const roles = document.querySelector('#roles'); const pool = document.querySelector('#pool');
      library.scrollLeft = 200; roles.scrollLeft = 150; pool.scrollTop = 100;
      return { library: library.scrollLeft, roles: roles.scrollLeft, pool: pool.scrollTop };
    });
    assert.ok(scrolls.library > 0 && scrolls.roles > 0 && scrolls.pool > 0);
    const defaultAfter = await page.locator('.default-voice').boundingBox(); assert.equal(defaultAfter.x, defaultBefore.x);
    await page.getByRole('tab', { name: '基础设置' }).click();
    await page.getByRole('button', { name: '打开 Debug' }).click();
    const retained = await page.evaluate(() => ({ library: document.querySelector('.library-scroll').scrollLeft, roles: document.querySelector('#roles').scrollLeft, pool: document.querySelector('#pool').scrollTop }));
    assert.deepEqual(retained, scrolls);
    await page.locator('#debug-close').click();
  });
  await check('Long detail content scrolls below fixed Tabs without growing panel', async () => {
    const before = await page.locator('.settings').boundingBox();
    await page.locator('#settings-content').evaluate(node => {
      for (let n = 0; n < 80; n++) { const p = document.createElement('p'); p.textContent = `布局压力段落 ${n}`; node.append(p); }
      node.scrollTop = 200;
    });
    const metrics = await page.locator('#settings-content').evaluate(node => ({ top: node.scrollTop, height: node.clientHeight, full: node.scrollHeight }));
    assert.ok(metrics.top > 0 && metrics.full > metrics.height);
    assert.equal((await page.locator('.settings').boundingBox()).height, before.height);
    await expect(page.getByRole('tab', { name: '基础设置' })).toBeVisible();
    await page.reload();
    await expect(page.locator('#load-status')).toContainText('Mock 数据已加载');
    await page.setViewportSize({ width: 390, height: 844 });
    await page.screenshot({ path: path.join(output, 'narrow.png'), fullPage: true });
  });
  await check('Specified desktop and narrow dimensions preserve boundaries and avoid horizontal page overflow', async () => {
    await page.reload(); await expect(page.locator('#pool-status')).toContainText('6 / 6');
    await page.locator('[data-role-id="MOCK_ROLE_A"]').click();
    await openPool(); await page.locator('[data-pool-id="MOCK_OFFICIAL_B"]').dblclick();
    evidence.viewports = [];
    for (const [width, height] of [[1920,1080],[1440,900],[1280,720],[390,844],[320,640]]) {
      await page.setViewportSize({ width, height });
      const metrics = await page.evaluate(() => {
        const left = document.querySelector('.assignment-workspace').getBoundingClientRect();
        const right = document.querySelector('.settings').getBoundingClientRect();
        return { scrollWidth: document.documentElement.scrollWidth, scrollHeight: document.documentElement.scrollHeight,
          viewportWidth: innerWidth, viewportHeight: innerHeight, columns: left.right < right.left,
          contained: [...document.querySelectorAll('.panel')].every(node => { const r=node.getBoundingClientRect(); return r.left>=0 && r.right<=innerWidth; }) };
      });
      assert.ok(metrics.scrollWidth <= width && metrics.contained, JSON.stringify(metrics));
      assert.equal(metrics.columns, width > 850);
      const screenshot = `viewport-${width}x${height}.png`;
      await page.screenshot({ path: path.join(output, screenshot), fullPage: true });
      evidence.viewports.push({ width, height, ...metrics, screenshot });
    }
    await page.setViewportSize({ width:1440, height:900 });
  });
  await check('Basic accessible names, labels, image alternatives and linked Tabs are present', async () => {
    await expect(page.getByRole('main', { name:'声音工作台' })).toHaveCount(1);
    assert.ok(await page.locator('img').evaluateAll(images => images.every(image => image.hasAttribute('alt'))));
    assert.deepEqual(await page.locator('button,input,select,textarea').evaluateAll(nodes => nodes.filter(node => {
      if (!node.getClientRects().length) return false;
      return !(node.getAttribute('aria-label') || node.getAttribute('aria-labelledby') || node.labels?.length || (node.tagName==='BUTTON' && node.textContent.trim()));
    }).map(node => node.id || node.outerHTML)), []);
    const tab = page.getByRole('tab', { name:'基础设置' });
    await expect(tab).toHaveAttribute('aria-controls','settings-content');
    await expect(page.getByRole('tabpanel')).toHaveAttribute('aria-labelledby','tab-basic');
    await expect(page.locator('#editor-preview-status')).toHaveAttribute('role','status');
  });
  await check('Skip link, visible keyboard focus and modal focus containment work', async () => {
    await page.reload(); await expect(page.locator('#load-status')).toContainText('Mock 数据已加载');
    await page.keyboard.press('Tab'); await expect(page.getByRole('link', { name:'跳到声音工作台' })).toBeFocused();
    await page.keyboard.press('Enter'); await expect(page.locator('#workspace')).toBeInViewport();
    await page.locator('#default-target').focus();
    const focus = await page.locator('#default-target').evaluate(node => ({ width:getComputedStyle(node).outlineWidth, style:getComputedStyle(node).outlineStyle }));
    assert.equal(focus.width,'3px'); assert.notEqual(focus.style,'none');
    await page.keyboard.press('Enter');
    await expect(page.locator('#default-cancel')).toBeFocused();
    for (let n=0;n<4;n++) { await page.keyboard.press('Tab'); assert.ok(await page.locator('#default-confirmation').evaluate(node => node.contains(document.activeElement))); }
    await page.keyboard.press('Escape'); await expect(page.locator('#default-confirmation')).toBeHidden();
    await expect(page.locator('#default-target')).toBeFocused();
  });
  await check('Loading and disabled states announce pending work and recover after a real Mock result', async () => {
    await page.reload(); await expect(page.locator('#pool-status')).toContainText('6 / 6');
    await openPool(); await page.locator('[data-pool-id="MOCK_OFFICIAL_A"]').dblclick();
    await page.getByRole('tab',{name:'探索更多'}).click();
    await expect(page.locator('#flow-role')).toBeDisabled(); await expect(page.locator('#flow-save')).toBeDisabled();
    const busy = await page.locator('#editor-preview').evaluate(button => {
      button.click(); return { busy:button.getAttribute('aria-busy'), disabled:button.disabled, text:button.textContent, border:getComputedStyle(button).borderTopStyle };
    });
    assert.equal(busy.busy,'true'); assert.equal(busy.disabled,true); assert.ok(busy.text.includes('正在生成')); assert.equal(busy.border,'dashed');
    await expect(page.locator('#editor-preview-status')).toContainText('当前参数模拟试听');
    await expect(page.locator('#editor-preview')).toHaveAttribute('aria-busy','false');
    await expect(page.locator('#flow-save')).toBeEnabled(); await expect(page.locator('#flow-role')).toBeDisabled();
    await page.getByLabel('音色名称').fill('视觉验收声音');
    const saving = await page.locator('#flow-save').evaluate(button => { button.click(); return { busy:button.getAttribute('aria-busy'), disabled:button.disabled }; });
    assert.equal(saving.busy,'true'); assert.equal(saving.disabled,true);
    await expect(page.locator('#flow-message')).toContainText('Mock 保存成功');
    await expect(page.locator('#flow-save')).toHaveAttribute('aria-busy','false');
  });
  await check('Solid palette, readable text contrast and reduced motion meet basic visual rules', async () => {
    const visual = await page.evaluate(() => {
      const css=getComputedStyle(document.documentElement), value=name=>css.getPropertyValue(name).trim();
      const lum=color=>{const rgb=color.match(/[0-9a-f]{2}/gi).map(x=>parseInt(x,16)/255).map(x=>x<=.04045?x/12.92:((x+.055)/1.055)**2.4);return rgb[0]*.2126+rgb[1]*.7152+rgb[2]*.0722;};
      const pairs=[['--ink','--paper'],['--ink','--blue'],['--ink','--yellow'],['--on-red','--red'],['--muted','--surface'],['--danger','--surface'],['--success','--paper'],['--disabled-ink','--disabled-bg']];
      return { contrast:pairs.map(([a,b])=>({pair:[a,b],ratio:(Math.max(lum(value(a)),lum(value(b)))+.05)/(Math.min(lum(value(a)),lum(value(b)))+.05)})),
        gradients:[...document.querySelectorAll('body *')].filter(node=>getComputedStyle(node).backgroundImage.includes('gradient')).length,
        prohibited:/\b(?:WEFT|PPL)\b/i.test(document.body.innerText) };
    });
    assert.equal(visual.gradients,0); assert.equal(visual.prohibited,false);
    assert.ok(visual.contrast.every(pair=>pair.ratio>=4.5), JSON.stringify(visual.contrast));
    evidence.basicContrast=visual.contrast;
    await page.emulateMedia({ reducedMotion:'reduce' });
    assert.equal(await page.locator('#editor-preview').evaluate(node=>getComputedStyle(node).transitionDuration),'0s');
    await page.emulateMedia({ reducedMotion:'no-preference' });
  });
  await check('Empty results and catalogue failure keep recovery controls accessible', async () => {
    await page.getByLabel('关键词', { exact:true }).fill('没有这样的声音');
    await expect(page.locator('#pool')).toContainText('没有匹配的声音');
    await page.screenshot({ path:path.join(output,'empty-results.png'), fullPage:true });
    await page.getByLabel('关键词', { exact:true }).fill('');
    await page.getByRole('button', { name:'打开 Debug' }).click();
    await page.getByRole('button', { name:'声音池：模拟失败' }).click();
    await expect(page.locator('#pool-status')).toContainText('模拟声音池加载失败');
    await page.locator('#debug-close').click();
    await page.getByRole('button', { name:'重新加载 Mock 声音池' }).focus();
    await page.screenshot({ path:path.join(output,'catalogue-error.png'), fullPage:true });
    await page.keyboard.press('Enter'); await expect(page.locator('#pool-status')).toContainText('6 / 6');
  });
  await check('Voice category colors are consistent across library and pool, including unknown names', async () => {
    await page.reload(); await expect(page.locator('#pool-status')).toContainText('6 / 6');
    const pairs=[['[data-voice-id="MOCK_VOICE_A"] .voice-avatar','rgb(78, 205, 196)'],['[data-voice-id="MOCK_VOICE_B"] .voice-avatar','rgb(243, 129, 164)'],['[data-voice-id="MOCK_VOICE_C"] .voice-avatar','rgb(242, 181, 68)'],['[data-pool-id="MOCK_OFFICIAL_A"] .pool-portrait','rgb(78, 205, 196)'],['[data-pool-id="MOCK_OFFICIAL_B"] .pool-portrait','rgb(243, 129, 164)'],['[data-pool-id="MOCK_USER_UNKNOWN"] .pool-portrait','rgb(242, 181, 68)']];
    for (const [selector,color] of pairs) await expect(page.locator(selector)).toHaveCSS('background-color',color);
    await expect(page.locator('[data-pool-id="MOCK_USER_UNKNOWN"]')).toContainText('性别 unknown');
    await expect(page.locator('[data-pool-id="MOCK_USER_B"] .pool-portrait')).toHaveCSS('background-color','rgb(78, 205, 196)');
    await expect(page.locator('[data-pool-id="MOCK_USER_B"] .pool-portrait')).toHaveCSS('filter','none');
  });
  await check('Completion is the dominant CTA and generated decorative assets load locally', async () => {
    const cta=await page.locator('#complete-settings').boundingBox();
    assert.ok(cta.height>=56 && cta.width>500);
    const hint=await page.locator('#complete-hint').boundingBox(), frame=await page.locator('.assignment-workspace').boundingBox();
    assert.ok(hint.y+hint.height<=frame.y+frame.height-8,'completion description stays inside its panel');
    assert.equal(await page.locator('#complete-settings').evaluate(node=>getComputedStyle(node).fontSize),'22px');
    assert.ok(await page.locator('.header-decoration').evaluate(node=>node.complete && node.naturalWidth>0));
    await page.getByRole('tab',{name:'音色生成',exact:true}).click();
    await expect(page.locator('.placeholder-decoration')).toBeVisible();
    assert.ok(await page.locator('.placeholder-decoration').evaluate(node=>node.complete && node.naturalWidth>0));
    await page.screenshot({path:path.join(output,'decoration-placeholder.png'),fullPage:true});
    await page.getByRole('tab',{name:'基础设置'}).click();
  });
  await check('Pool collapse preserves filter and list nodes without losing candidate state', async () => {
    await page.getByLabel('关键词',{exact:true}).fill('轻柔');
    await page.locator('[data-pool-id="MOCK_OFFICIAL_B"]').dblclick();
    await page.locator('#pool-toggle').click();
    await expect(page.locator('#pool-toggle')).toHaveAttribute('aria-expanded','false');
    await expect(page.locator('#pool-body')).toBeHidden();
    await page.locator('#pool-toggle').click();
    await expect(page.getByLabel('关键词',{exact:true})).toHaveValue('轻柔');
    await expect(page.locator('.pool-voice-card')).toHaveCount(1);
    await expect(page.locator('[data-pool-id="MOCK_OFFICIAL_B"] .pool-body-button')).toHaveAttribute('aria-pressed','true');
    await page.getByLabel('关键词',{exact:true}).fill('');
  });
  await check('Narrow project settings collapse pool and reveal a tall fully readable Basic card', async () => {
    await page.locator('[data-role-id="MOCK_ROLE_A"]').click();
    await page.setViewportSize({width:390,height:844});
    await page.getByRole('button',{name:'设置 叙述男声',exact:true}).click();
    await expect(page.locator('#pool-body')).toBeHidden();
    await expect(page.getByRole('tab',{name:'基础设置'})).toHaveAttribute('aria-selected','true');
    await expect(page.locator('#settings-content')).toBeFocused();
    const geometry=await page.locator('.settings').boundingBox();
    assert.ok(geometry.y>=0 && geometry.y<60 && geometry.height>=1050,JSON.stringify(geometry));
    assert.equal(await page.locator('#settings-content').evaluate(node=>getComputedStyle(node).overflowY),'visible');
    assert.ok(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth));
    await page.screenshot({path:path.join(output,'narrow-settings-collapsed.png'),fullPage:true});
    await page.locator('#default-target').click();
    await expect(page.locator('#default-confirmation')).toBeVisible();
    await page.screenshot({path:path.join(output,'narrow-default-quick.png'),fullPage:true});
    await page.keyboard.press('Escape');
    await page.setViewportSize({width:1440,height:900});
    await page.reload();await expect(page.locator('#pool-status')).toContainText('6 / 6');
    await page.locator('[data-role-id="MOCK_ROLE_A"]').click();
    await page.locator('[data-pool-id="MOCK_OFFICIAL_B"]').dblclick();
    await page.screenshot({path:path.join(output,'final-desktop.png'),fullPage:true});
    await page.setViewportSize({width:390,height:844});
    await page.screenshot({path:path.join(output,'final-narrow.png'),fullPage:true});
    await page.setViewportSize({width:1440,height:900});
  });
  await check('Pool single click only selects; double click opens Basic without binding a role', async () => {
    await page.reload();await expect(page.locator('#pool-status')).toContainText('6 / 6');
    await page.getByRole('button',{name:'设置 叙述男声',exact:true}).click();await openPool();
    await page.getByRole('tab',{name:'探索更多'}).click();
    const before=await page.evaluate(async()=>{const s=(await import('/js/store.js')).store.getState();return {editor:s.editor,task:s.task,projectDefault:s.projectDefault,ui:s.ui};});
    const body=page.locator('[data-pool-id="MOCK_OFFICIAL_B"] .pool-body-button');await body.click();
    await expect(body).toHaveAttribute('aria-pressed','true');
    await expect(page.getByRole('tab',{name:'探索更多'})).toHaveAttribute('aria-selected','true');
    const after=await page.evaluate(async()=>{const s=(await import('/js/store.js')).store.getState();return {editor:s.editor,task:s.task,projectDefault:s.projectDefault,ui:s.ui};});
    assert.deepEqual(after,before);
    await body.dblclick();await expect(page.getByRole('tab',{name:'基础设置'})).toHaveAttribute('aria-selected','true');
    await expect(page.locator('#role-required')).toBeVisible();await page.getByRole('tab',{name:'探索更多'}).click();
    await expect(page.locator('#settings-metadata')).toContainText('轻柔讲述');
    assert.deepEqual(await page.evaluate(async()=>(await import('/js/store.js')).store.getState().task),before.task);
  });
  await check('Available pool voices play and stop Mock audio independently, unavailable and unknown lack play buttons', async () => {
    await page.reload();await expect(page.locator('#pool-status')).toContainText('6 / 6');
    await expect(page.locator('.pool-play')).toHaveCount(4);
    await expect(page.locator('[data-pool-id="MOCK_USER_B"] .pool-play')).toHaveCount(0);
    await expect(page.locator('[data-pool-id="MOCK_USER_UNKNOWN"] .pool-play')).toHaveCount(0);
    await expect(page.locator('button button')).toHaveCount(0);
    const before=await page.evaluate(async()=>{const s=(await import('/js/store.js')).store.getState();return {editor:s.editor,task:s.task,projectDefault:s.projectDefault,selected:s.catalog.selectedId};});
    await page.getByRole('button',{name:'试听声音池：晴朗叙述（本地 Mock 提示音）',exact:true}).click();
    await expect(page.locator('#pool-status')).toContainText('正在播放本地 Mock');
    await page.getByRole('button',{name:'停止声音池：晴朗叙述（本地 Mock 提示音）',exact:true}).click();
    await expect(page.locator('#pool-status')).toContainText('播放已停止');
    const after=await page.evaluate(async()=>{const s=(await import('/js/store.js')).store.getState();return {editor:s.editor,task:s.task,projectDefault:s.projectDefault,selected:s.catalog.selectedId};});
    assert.deepEqual(after,before);await expect(page.locator('#flow-role')).toBeDisabled();
    const body=page.locator('[data-pool-id="MOCK_OFFICIAL_B"] .pool-body-button');await body.focus();await body.press('Space');
    await expect(body).toHaveAttribute('aria-pressed','true');await expect(page.locator('#role-required')).toBeVisible();
    await body.press('Enter');await expect(page.locator('#role-required')).toBeVisible();await page.getByRole('tab',{name:'探索更多'}).click();await expect(page.locator('#settings-metadata')).toContainText('轻柔讲述');
    await page.screenshot({path:path.join(output,'final-desktop.png'),fullPage:true});
    await page.setViewportSize({width:390,height:844});
    await page.screenshot({path:path.join(output,'final-narrow.png'),fullPage:true});
    await page.setViewportSize({width:1440,height:900});
  });
  await check('Project binding markers change from gray squares to role numbers, including multiple bindings', async () => {
    await page.reload();await expect(page.locator('#pool-status')).toContainText('6 / 6');
    const badge=id=>page.locator(`[data-voice-id="${id}"] .voice-role-markers`);
    await expect(badge('MOCK_VOICE_A')).toHaveClass(/is-unbound/);await expect(badge('MOCK_VOICE_A')).toHaveCSS('background-color','rgb(185, 186, 184)');
    await expect(badge('MOCK_VOICE_B')).toHaveText('2');
    await page.locator('[data-role-id="MOCK_ROLE_A"]').click();
    await expect(page.locator('[data-role-id="MOCK_ROLE_A"]')).toHaveCSS('background-color','rgb(105, 73, 14)');
    await expect(page.locator('[data-role-id="MOCK_ROLE_B"]')).toHaveCSS('background-color','rgb(243, 129, 164)');
    await page.screenshot({path:path.join(output,'unassigned-gray-markers.png'),fullPage:true});
    await page.locator('[data-role-id="MOCK_ROLE_A"]').click();await page.getByRole('button',{name:'选择项目声音：叙述男声',exact:true}).click();
    await expect(badge('MOCK_VOICE_A')).toHaveText('1');await expect(badge('MOCK_VOICE_A')).not.toHaveClass(/is-unbound/);
    await page.locator('[data-role-id="MOCK_ROLE_N"]').click();await page.getByRole('button',{name:'选择项目声音：叙述男声',exact:true}).click();
    await expect(badge('MOCK_VOICE_A').locator('span')).toHaveText(['1','3']);
    await page.getByRole('button',{name:'选择项目声音：未分类声音',exact:true}).click();await expect(badge('MOCK_VOICE_A')).toHaveText('1');
    await page.screenshot({path:path.join(output,'role-binding-markers.png'),fullPage:true});
  });
  await check('Assigned role cards stay bright after selection changes; unassigned roles remain dark', async () => {
    await page.locator('[data-role-id="MOCK_ROLE_A"]').click();
    await expect(page.locator('[data-role-id="MOCK_ROLE_A"]')).toHaveCSS('background-color','rgb(78, 205, 196)');
    await expect(page.locator('[data-role-id="MOCK_ROLE_B"]')).toHaveCSS('background-color','rgb(243, 129, 164)');
    const before=await page.evaluate(async()=>(await import('/js/store.js')).store.getState().task);
    await page.locator('[data-role-id="MOCK_ROLE_B"]').click();
    await expect(page.locator('[data-role-id="MOCK_ROLE_A"]')).toHaveCSS('background-color','rgb(78, 205, 196)');
    await expect(page.locator('[data-role-id="MOCK_ROLE_B"]')).toHaveCSS('background-color','rgb(243, 129, 164)');
    assert.deepEqual(await page.evaluate(async()=>(await import('/js/store.js')).store.getState().task),before);
    await page.locator('[data-role-id="MOCK_ROLE_N"]').click();await expect(page.locator('[data-role-id="MOCK_ROLE_N"]')).toHaveCSS('background-color','rgb(242, 181, 68)');
    await page.screenshot({path:path.join(output,'final-desktop.png'),fullPage:true});
    await page.setViewportSize({width:390,height:844});await page.screenshot({path:path.join(output,'final-narrow.png'),fullPage:true});await page.setViewportSize({width:1440,height:900});
  });
  await check('Shared voice name applies to role only; role action sits left of project save on desktop and narrow', async () => {
    await page.reload();await expect(page.locator('#pool-status')).toContainText('6 / 6');
    await page.locator('[data-role-id="MOCK_ROLE_A"]').click();
    await page.locator('[data-pool-id="MOCK_OFFICIAL_B"]').dblclick();await page.locator('#editor-preview').click();await expect(page.locator('#flow-role')).toBeEnabled();
    await page.getByLabel('音色名称',{exact:true}).fill('');await page.locator('#flow-role').click();await expect(page.locator('#flow-message')).toContainText('请输入音色名称');await expect(page.locator('#flow-recovery')).toBeHidden();
    await page.getByLabel('音色名称',{exact:true}).fill('主角专属轻柔声');
    const count=await page.locator('.project-voice-card').count();
    await page.locator('#flow-role').click();await expect(page.locator('[data-role-id="MOCK_ROLE_A"]')).toContainText('主角专属轻柔声');
    assert.equal(await page.locator('.project-voice-card').count(),count);
    for(const width of [1440,390,320]) {
      await page.setViewportSize({width,height:900});
      const role=await page.locator('#flow-role').boundingBox(),save=await page.locator('#flow-save').boundingBox(),name=await page.locator('#flow-name').boundingBox();
      assert.ok(role.x+role.width<=save.x && Math.abs(role.y-save.y)<1 && name.y+name.height<=role.y,JSON.stringify({width,role,save,name}));
    }
    await page.setViewportSize({width:390,height:844});await page.screenshot({path:path.join(output,'shared-name-actions-narrow.png'),fullPage:true});
    await page.setViewportSize({width:1440,height:900});await page.screenshot({path:path.join(output,'shared-name-actions-desktop.png'),fullPage:true});await page.locator('#flow-actions').screenshot({path:path.join(output,'shared-name-actions-detail.png')});
  });
  await check('Basic requires a role and carries the selected role identity, fields and stable icon', async () => {
    await page.reload();await expect(page.locator('#pool-status')).toContainText('6 / 6');
    await expect(page.locator('#role-required')).toContainText('请选择角色');await expect(page.locator('#editor-fields')).toBeHidden();await expect(page.locator('#assignment-actions')).toBeHidden();
    await page.getByRole('button',{name:'设置 叙述男声',exact:true}).click();await expect(page.locator('#role-required')).toBeVisible();
    await page.screenshot({path:path.join(output,'choose-role.png'),fullPage:true});
    await page.locator('[data-role-id="MOCK_ROLE_B"]').click();
    await expect(page.locator('#role-required')).toBeHidden();await expect(page.locator('.role-editor-context')).toContainText('主角 B');
    await expect(page.getByLabel('语速',{exact:true})).toHaveValue('0.9');await expect(page.getByLabel('音量',{exact:true})).toHaveValue('0.8');await expect(page.getByLabel('音色名称',{exact:true})).toHaveValue('温柔女声');
    const icon=await page.locator('[data-role-id="MOCK_ROLE_B"] .role-avatar').getAttribute('src');await expect(page.locator('.editor-role-avatar')).toHaveAttribute('src',icon);
    await page.getByLabel('语速',{exact:true}).fill('1.3');await page.getByLabel('音色名称',{exact:true}).fill('B 的专属声');await page.getByLabel('试听文本',{exact:true}).fill('这是主角 B 专属的完整试听句，切换角色和候选后应保留。');
    await page.locator('[data-role-id="MOCK_ROLE_A"]').click();await expect(page.getByLabel('语速',{exact:true})).toHaveValue('1.1');await expect(page.getByLabel('音色名称',{exact:true})).toHaveValue('主角 A');
    await page.locator('[data-role-id="MOCK_ROLE_B"]').click();await expect(page.getByLabel('语速',{exact:true})).toHaveValue('1.3');await expect(page.getByLabel('音色名称',{exact:true})).toHaveValue('B 的专属声');await expect(page.locator('.editor-role-avatar')).toHaveAttribute('src',icon);
    await page.getByRole('tab',{name:'探索更多'}).click();await page.getByRole('tab',{name:'基础设置'}).click();await expect(page.locator('.editor-role-avatar')).toHaveAttribute('src',icon);
  });
  await check('Same candidate inherits each role separately and Mock library save keeps the role icon', async () => {
    const icon=await page.locator('[data-role-id="MOCK_ROLE_B"] .role-avatar').getAttribute('src');
    await openPool();await page.locator('[data-pool-id="MOCK_OFFICIAL_A"]').dblclick();await expect(page.getByLabel('语速',{exact:true})).toHaveValue('1.3');await expect(page.getByLabel('音量',{exact:true})).toHaveValue('0.8');await expect(page.getByLabel('试听文本',{exact:true})).toHaveValue(/主角 B 专属/);
    await page.locator('[data-role-id="MOCK_ROLE_A"]').click();await page.locator('[data-pool-id="MOCK_OFFICIAL_A"]').dblclick();await expect(page.getByLabel('语速',{exact:true})).toHaveValue('1.1');await expect(page.getByLabel('音色名称',{exact:true})).toHaveValue('主角 A');
    await page.locator('[data-role-id="MOCK_ROLE_B"]').click();await page.locator('[data-pool-id="MOCK_OFFICIAL_A"]').dblclick();await expect(page.getByLabel('语速',{exact:true})).toHaveValue('1.3');await expect(page.locator('.editor-role-avatar')).toHaveAttribute('src',icon);
    await page.locator('#editor-preview').click();await expect(page.locator('#flow-save')).toBeEnabled();await page.getByLabel('音色名称',{exact:true}).fill('B 带图标的项目声');await page.locator('#flow-save').click();await expect(page.locator('#flow-message')).toContainText('Mock 保存成功');
    const saved=page.locator('.project-voice-card').filter({hasText:'B 带图标的项目声'});await expect(saved.locator('.voice-avatar')).toHaveAttribute('src',icon);
    await page.locator('[data-role-id="MOCK_ROLE_A"]').click();await page.locator('[data-role-id="MOCK_ROLE_B"]').click();await expect(page.getByLabel('音色名称',{exact:true})).toHaveValue('B 带图标的项目声');await expect(page.getByLabel('语速',{exact:true})).toHaveValue('1.3');await expect(page.locator('.editor-role-avatar')).toHaveAttribute('src',icon);
    await page.screenshot({path:path.join(output,'role-context-desktop.png'),fullPage:true});await page.setViewportSize({width:390,height:844});await page.screenshot({path:path.join(output,'role-context-narrow.png'),fullPage:true});await page.setViewportSize({width:1440,height:900});
  });
  await check('Nondevelopment entry hides Debug controls', async () => {
    await page.goto(`${base}/?dev=0`);
    await expect(page.locator('#load-status')).toContainText('Mock 数据已加载');
    await expect(page.locator('#debug-toggle')).toBeHidden(); await expect(page.locator('#debug-panel')).toBeHidden();
  });
  await check('Reload resets in-memory state', async () => {
    await page.goto(base); await page.getByRole('tab', { name: '基础设置' }).click();
    await page.reload(); await expect(page.getByRole('tab', { name: '基础设置' })).toHaveAttribute('aria-selected', 'true');
    await expect(page.locator('#debug-panel')).toBeHidden();
  });
  await check('Opening HTML directly displays HTTP startup guidance instead of blank content', async () => {
    // file:// module failure is expected; isolate from HTTP application's error evidence.
    const fileContext = await browser.newContext();
    try {
      const filePage = await fileContext.newPage();
      await filePage.goto(pathToFileURL(path.join(root, 'index.html')).href);
      await expect(filePage.getByRole('heading', { name: '工作台尚未加载' })).toBeVisible();
      await expect(filePage.locator('#workspace')).toContainText('python -m http.server');
      await expect(filePage.getByRole('link', { name: 'http://127.0.0.1:8765/' })).toBeVisible();
    } finally { await fileContext.close(); }
  });
  await check('Zero console errors, failed HTTP assets, external or business requests', async () => {
    assert.deepEqual(evidence.errors, []); assert.deepEqual(evidence.failedResponses, []);
    assert.deepEqual(evidence.externalRequests, []); assert.deepEqual(evidence.businessRequests, []);
  });
  evidence.status = 'PASS';
})().catch(error => { evidence.status = 'FAIL'; evidence.failure = error.message; process.exitCode = 1; })
  .finally(async () => {
    if (browser) await browser.close();
    if (server) server.kill();
    evidence.completedAt = new Date().toISOString();
    fs.writeFileSync(path.join(output, 'browser-results.json'), JSON.stringify(evidence, null, 2));
    console.log(JSON.stringify(evidence, null, 2));
  });
