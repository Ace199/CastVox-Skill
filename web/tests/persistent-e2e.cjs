// Real browser + Python HTTP server + separate Fake-only Harness processes.
const { chromium } = require('playwright');
const { expect } = require('playwright/test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const { spawn, spawnSync } = require('node:child_process');
const { once } = require('node:events');
const root = path.resolve(__dirname, '../..');
const scratch = path.join(root, '.test-tmp', `persistent-${Date.now()}`);
const project = path.join(scratch, 'project'), config = path.join(scratch, 'providers');
fs.mkdirSync(project, { recursive: true }); fs.mkdirSync(config);
fs.mkdirSync(path.join(config, 'minimax'));
fs.writeFileSync(path.join(config, 'minimax/config.json'), JSON.stringify({ api_key: 'YOUR_API_KEY_HERE', region: 'cn',
  base_url: 'https://api.minimax.cn', models: ['speech-2.8-hd', 'speech-2.6-turbo', 'unknown-model'], default_model: 'speech-2.8-hd' }));
const output = path.join(root, 'web/qa/persistent'); fs.mkdirSync(output, { recursive: true });
const env = { ...process.env, PYTHONPATH: [path.join(root, 'tests/support'), root].join(path.delimiter), MAKESOUND_TEST_NO_NETWORK: '1', PYTHONIOENCODING: 'utf-8' };
const evidence = { status: 'RUNNING', checks: [], browserErrors: [], externalRequests: [], paid_api_calls: 0 };
const python = process.env.STUDIO_PYTHON || 'python';
function cli(args) {
  const run = spawnSync(python, ['-m', 'makesound.offline_harness', ...args, '--project', project], { cwd: root, env, encoding: 'utf8', windowsHide: true, timeout: 30000 });
  assert.equal(run.status, 0, run.stderr + run.stdout);
  return JSON.parse(run.stdout.trim());
}
async function check(name, action) { await action(); evidence.checks.push({ name, status: 'PASS' }); console.log(`PASS ${name}`); }
let server, browser, base;
async function start(qid) {
  server = spawn(python, ['studio_v16_server.py', '--project', project, '--fake', ...(qid ? ['--question', qid] : []), '--config-dir', config], { cwd: root, env, windowsHide: true, stdio: ['ignore', 'pipe', 'pipe'] });
  let buffer = '';
  base = await new Promise((resolve, reject) => {
    const timer = setTimeout(() => reject(new Error('Server startup timeout')), 15000);
    server.once('exit', code => { clearTimeout(timer); reject(new Error(`Server exited ${code}`)); });
    server.stdout.on('data', data => { buffer += data.toString(); if (buffer.includes('\n')) { clearTimeout(timer); resolve(JSON.parse(buffer.split('\n')[0]).url); } });
  });
}
async function stop() { if (server && server.exitCode === null) { const ended = once(server, 'exit'); server.kill(); await ended; } }
async function instrument(page) {
  page.on('pageerror', error => evidence.browserErrors.push(error.message));
  await page.route('**/*', route => {
    const url = new URL(route.request().url());
    if (!['127.0.0.1', 'localhost'].includes(url.hostname)) { evidence.externalRequests.push(url.origin); return route.abort(); }
    return route.continue();
  });
}
const card = (page, name) => page.locator('.project-voice-card').filter({ has: page.locator('.voice-name', { hasText: name }) });
async function add(page, name, category) {
  await page.getByRole('tab', { name: '添加项目声音', exact: true }).click();
  await page.getByLabel('声音厂商', { exact: true }).selectOption('fake');
  await expect(page.getByLabel('项目声音名称', { exact: true })).toBeEnabled();
  await page.getByLabel('项目声音名称', { exact: true }).fill(name);
  await page.locator('#voice-id').fill(`FAKE_${category}`);
  await page.getByRole('tabpanel', { name: '添加项目声音' }).getByLabel('声音分类', { exact: true }).selectOption(category);
  await page.getByRole('button', { name: '添加到项目库', exact: true }).click();
  await expect(card(page, name)).toHaveCount(1);
}
(async () => {
  const manifest = path.join(scratch, 'manifest.json');
  fs.writeFileSync(manifest, JSON.stringify({ roles: ['narrator', 'guest'], role_metadata: {
    narrator: { display_name: '讲解者', appearance_summary: '任务提供的讲解形象', recommended_voice_description: '清晰平静' },
    guest: { display_name: '来宾' } }, segments: [
      { paragraph_id: 'p1', sentence_id: 's1', role_id: 'narrator', text: '第一句原文。', pause_ms: 300 },
      { paragraph_id: 'p1', sentence_id: 's2', role_id: 'guest', text: '第二句原文。' } ] }));
  const prepared = cli(['prepare', '--manifest', manifest]), qid = prepared.question_id;
  try {
    await start(qid);
    browser = await chromium.launch({ headless: true, executablePath: process.env.STUDIO_CHROMIUM || 'C:/Program Files/Google/Chrome/Application/chrome.exe' });
    const context = await browser.newContext({ viewport: { width: 1440, height: 900 } });
    const page = await context.newPage(); await instrument(page); await page.goto(base);
    await check('real empty project, missing roles and no synthesis', async () => {
      await expect(page.getByRole('heading', { name: 'project', exact: true })).toBeVisible();
      await expect(page.locator('.project-voice-card')).toHaveCount(0);
      await expect(page.locator('#complete-settings')).toBeDisabled();
      assert.equal(cli(['continue', '--question', qid, '--confirmed', '--authorize-fake']).status, 'waiting_for_answer');
      assert.equal(fs.existsSync(path.join(project, '.makesound/jobs')), false);
    });
    await check('real add/defaults/role metadata and assignment persistence', async () => {
      await add(page, '男声测试', 'male'); await add(page, '女声测试', 'female');
      await page.getByRole('button', { name: '选择默认声音', exact: true }).click();
      await card(page, '男声测试').locator('.voice-body').click();
      await page.getByRole('button', { name: '保存默认设置', exact: true }).click();
      await page.getByRole('button', { name: '确认保存默认', exact: true }).click();
      await expect(page.locator('#save-defaults')).toBeDisabled();
      for (const [role, voice] of [['讲解者', '男声测试'], ['来宾', '女声测试']]) {
        await page.getByRole('button', { name: `角色 ${role}`, exact: true }).click();
        await card(page, voice).locator('.voice-body').click();
        await expect(page.locator('#operation-status')).toHaveText('角色分配已保存');
      }
      await page.getByRole('button', { name: '角色 讲解者', exact: true }).press('F2');
      await expect(page.locator('#role-detail')).toContainText('任务提供的讲解形象');
      await page.keyboard.press('Escape');
      await page.reload();
      await expect(page.getByRole('button', { name: '角色 来宾', exact: true })).toContainText('女声测试');
      await expect(page.locator('#default-general-name')).toHaveText('男声测试');
      await expect(card(page, '女声测试').locator('img')).toHaveAttribute('src', /assets\/woman\//);
    });
    await check('two pages reject stale revision and preserve draft until review', async () => {
      const other = await context.newPage(); await instrument(other); await other.goto(base);
      await card(page, '男声测试').locator('.voice-settings').click();
      await page.getByLabel('声音名称', { exact: true }).fill('男声新名称');
      await page.getByRole('button', { name: '保存修改', exact: true }).click();
      await expect(card(page, '男声新名称')).toHaveCount(1);
      await card(other, '男声测试').locator('.voice-settings').click();
      await other.getByLabel('声音名称', { exact: true }).fill('冲突草稿');
      await other.getByRole('button', { name: '保存修改', exact: true }).click();
      await expect(other.locator('#operation-error')).toContainText('请重新读取');
      await expect(other.getByLabel('声音名称', { exact: true })).toHaveValue('冲突草稿');
      await other.getByRole('button', { name: '重新读取项目', exact: true }).click();
      await expect(other.locator('#operation-error')).toBeEmpty();
      await expect(other.getByLabel('声音名称', { exact: true })).toHaveValue('冲突草稿');
      await other.close();
    });
    await check('soft delete/undo keeps task, immutable submitted answer and zero generation', async () => {
      await card(page, '女声测试').locator('.voice-settings').click();
      await page.getByRole('button', { name: '从项目库删除此声音', exact: true }).click();
      await page.getByRole('button', { name: '确认软删除', exact: true }).click();
      await expect(card(page, '女声测试')).toHaveCount(0);
      await expect(page.getByRole('button', { name: '角色 来宾', exact: true })).toContainText('已从项目库移除');
      await page.getByRole('button', { name: '撤销删除', exact: true }).click();
      await expect(card(page, '女声测试')).toHaveCount(1);
      await page.getByRole('button', { name: /完成设置/ }).click();
      await expect(page.locator('#answer-receipt')).toContainText('等待 Agent 领取');
      assert.equal(cli(['status', '--question', qid]).claimed, false);
      assert.equal(fs.existsSync(path.join(project, '.makesound/jobs')), false);
      await page.reload(); await expect(page.locator('#complete-settings')).toBeDisabled();
    });
    await check('server restart + separate Harness claim -> WAV/SRT + cache reuse', async () => {
      await stop(); await start(qid); await page.goto(base);
      await expect(page.locator('.project-voice-card')).toHaveCount(2);
      const result = cli(['continue', '--question', qid, '--confirmed', '--authorize-fake']);
      assert.equal(result.status, 'success'); assert.equal(result.fake_calls_this_run, 2);
      assert.equal(cli(['status', '--question', qid]).claimed, true);
      const exported = result.result.exports[0];
      assert.equal(exported.duration_seconds, 12.3);
      assert.ok(fs.readFileSync(path.join(project, exported.audio)).subarray(0, 4).equals(Buffer.from('RIFF')));
      assert.match(fs.readFileSync(path.join(project, exported.subtitle), 'utf8'), /00:00:06,300 --> 00:00:12,300/);
      assert.equal(cli(['continue', '--question', qid, '--confirmed', '--authorize-fake']).fake_calls_this_run, 0);
      evidence.output = { format: 'PCM WAV', duration_seconds: 12.3, subtitle: 'sentence SRT', repeat_fake_calls: 0 };
    });
    await check('authenticated preview Blob playback, pause and parameter stale state', async () => {
      await page.getByRole('button', { name: '重新读取项目', exact: true }).click();
      await expect(card(page, '男声新名称').locator('.voice-preview')).toBeEnabled();
      const audioResponse = page.waitForResponse(r => r.url().includes('/api/v16/preview/') && r.status() === 200);
      await card(page, '男声新名称').locator('.voice-preview').click(); await audioResponse;
      await expect(card(page, '男声新名称').locator('.voice-preview')).toHaveText('Ⅱ');
      await card(page, '男声新名称').locator('.voice-preview').click();
      await expect(card(page, '男声新名称').locator('.voice-preview')).toHaveText('▶');
      await card(page, '男声新名称').locator('.voice-settings').click();
      await page.getByRole('spinbutton', { name: '语速数值', exact: true }).fill('1.2');
      await page.getByRole('button', { name: '保存修改', exact: true }).click();
      await expect(card(page, '男声新名称')).toContainText('调整前试听');
      await page.getByRole('spinbutton', { name: '语速数值', exact: true }).fill('1');
      await page.getByRole('button', { name: '保存修改', exact: true }).click();
      await expect(card(page, '男声新名称')).toContainText('可试听');
      assert.equal(await page.evaluate(() => localStorage.length), 0);
      assert.equal(await page.evaluate(() => sessionStorage.length), 0);
      assert.equal(new URL(page.url()).search, '');
    });
    await check('desktop and narrow page keep layout and load renamed portraits', async () => {
      for (const [width, height] of [[1440, 900], [390, 844]]) {
        await page.setViewportSize({ width, height });
        assert.ok(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth));
        assert.ok(await page.locator('.project-voice-card img').evaluateAll(imgs => imgs.every(i => i.complete && i.naturalWidth > 0)));
        await page.screenshot({ path: path.join(output, `persistent-${width}.png`), fullPage: true });
      }
      assert.deepEqual(evidence.browserErrors, []); assert.deepEqual(evidence.externalRequests, []);
    });
    await check('management mode completes without a Question, synthesis or false resume', async () => {
      await stop(); await start(null); await page.goto(base);
      await expect(page.locator('.role-card')).toHaveCount(0);
      await expect(page.locator('#complete-settings')).toBeEnabled();
      await page.getByRole('button', { name: /完成设置/ }).click();
      await expect(page.locator('#answer-receipt')).toContainText('项目管理已完成');
      await expect(page.locator('#operation-status')).toHaveText('项目管理已完成；未启动合成');
      await expect(page.locator('#open-provider-config')).toBeEnabled();
      await expect(page.locator('#provider-support')).toHaveText('测试配置');
      await page.getByRole('button', { name: '重新读取项目', exact: true }).click();
      await expect(page.locator('.project-voice-card')).toHaveCount(2);
      assert.deepEqual(evidence.browserErrors, []); assert.deepEqual(evidence.externalRequests, []);
    });
    await check('MiniMax add controls synchronize, reset and persist parameters without synthesis', async () => {
      await page.setViewportSize({ width: 1440, height: 900 });
      await page.getByRole('tab', { name: '添加项目声音', exact: true }).click();
      await expect(page.getByRole('spinbutton', { name: '添加语速数值', exact: true })).toHaveValue('1');
      await expect(page.getByRole('spinbutton', { name: '添加声调数值', exact: true })).toHaveValue('0');
      await expect(page.locator('#add-speed-capability')).toContainText('真实效果未验收');
      await page.getByRole('slider', { name: '添加语速滑块', exact: true }).press('Home');
      await expect(page.locator('#add-speed')).toHaveValue('0.5');
      await page.getByRole('slider', { name: '添加语速滑块', exact: true }).press('End');
      await expect(page.locator('#add-speed')).toHaveValue('2');
      await page.getByRole('button', { name: '恢复添加语速默认值', exact: true }).click();
      await expect(page.locator('#add-speed')).toHaveValue('1');
      await page.locator('#add-speed').fill('1.234'); await page.locator('#add-pitch').fill('-3');
      await page.locator('#voice-model').selectOption('unknown-model');
      await expect(page.locator('#add-speed')).toBeDisabled(); await expect(page.locator('#add-pitch')).toBeDisabled();
      await page.locator('#voice-model').selectOption('speech-2.8-hd');
      await expect(page.locator('#add-speed')).toHaveValue('1'); await expect(page.locator('#add-pitch')).toHaveValue('0');
      await page.locator('#add-speed').fill('1.234'); await page.locator('#add-pitch').fill('-3');
      await page.locator('#provider').selectOption('volcengine'); await expect(page.locator('#provider')).toBeEnabled();
      await expect(page.locator('#add-speed')).toBeDisabled();
      await page.locator('#provider').selectOption('minimax'); await expect(page.locator('#provider')).toBeEnabled();
      await expect(page.locator('#add-speed')).toHaveValue('1.234'); await expect(page.locator('#add-pitch')).toHaveValue('-3');
      await page.locator('#voice-name').fill('添加参数声音'); await page.locator('#voice-id').fill('Chinese (Mandarin)_Reliable_Executive');
      await page.locator('#voice-category').selectOption('');
      await page.getByRole('button', { name: '添加到项目库', exact: true }).click();
      await expect(page.locator('#add-feedback')).toBeEmpty();
      await expect(page.locator('label[for="voice-category"]')).toHaveClass(/field-invalid/);
      await expect(page.getByRole('alertdialog')).toBeVisible();
      await expect(page.locator('#add-error-message')).toContainText('声音分类');
      await page.screenshot({path:path.join(output, 'add-error-dialog.png'),fullPage:true});
      await page.setViewportSize({width:390,height:844});
      await expect(page.getByRole('button',{name:'返回修改',exact:true})).toBeInViewport();
      await page.screenshot({path:path.join(output,'add-error-dialog-mobile.png'),fullPage:true});
      await page.keyboard.press('Escape');
      await expect(page.getByRole('alertdialog')).not.toBeVisible();
      await expect(page.locator('#voice-id')).toHaveValue('Chinese (Mandarin)_Reliable_Executive');
      await page.getByRole('button', {name:'添加到项目库',exact:true}).click();
      await expect(page.getByRole('alertdialog')).toBeVisible();
      await page.setViewportSize({width:1440,height:900});
      await page.getByRole('button', {name:'返回修改',exact:true}).click();
      await expect(page.getByRole('alertdialog')).not.toBeVisible();
      await expect(page.locator('#voice-id')).toHaveValue('Chinese (Mandarin)_Reliable_Executive');
      await page.locator('#voice-category').selectOption('male');
      await page.getByRole('button', { name: '添加到项目库', exact: true }).click();
      await expect(page.locator('#add-feedback')).toHaveText('已添加项目声音');
      await expect(card(page, '添加参数声音')).toHaveCount(1);
      const preset = JSON.parse(fs.readFileSync(path.join(project, '.makesound/preset.v1.6.json'), 'utf8'));
      assert.deepEqual(Object.values(preset.voices).find(v => v.name === '添加参数声音').settings, { speed: 1.234, pitch: -3 });
      await page.reload(); await card(page, '添加参数声音').locator('.voice-settings').click();
      await expect(page.getByRole('spinbutton', { name: '语速数值', exact: true })).toHaveValue('1.234');
      await expect(page.getByRole('spinbutton', { name: '声调数值', exact: true })).toHaveValue('-3');
      assert.equal(cli(['continue', '--question', qid, '--confirmed', '--authorize-fake']).fake_calls_this_run, 0);
    });
    await check('add parameters fit desktop and narrow layouts with the save action visible', async () => {
      await page.getByRole('tab', { name: '添加项目声音', exact: true }).click();
      for (const [width, height] of [[1440, 900], [1280, 720], [390, 844], [320, 640]]) {
        await page.setViewportSize({ width, height });
        assert.ok(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth));
        if (width > 950) {
          const metrics = await page.locator('.add-content').evaluate(el => ({ client: el.clientHeight, scroll: el.scrollHeight }));
          assert.ok(metrics.scroll <= metrics.client + 1, 'Add form must fit desktop height');
          (evidence.addLayout ??= []).push({ width, height, ...metrics });
          await expect(page.locator('#add-speed')).toBeInViewport({ ratio: 1 });
          await expect(page.locator('#add-pitch')).toBeInViewport({ ratio: 1 });
          await expect(page.locator('#save-alias')).toBeInViewport({ ratio: 1 });
        }
        await page.screenshot({ path: path.join(output, `add-parameters-${width}.png`), fullPage: true, animations: 'disabled' });
      }
      assert.deepEqual(evidence.browserErrors, []); assert.deepEqual(evidence.externalRequests, []);
    });
    evidence.status = 'PASS';
  } finally {
    if (browser) await browser.close(); await stop();
    fs.writeFileSync(path.join(root, 'docs/V1.8_Integration_Browser_Results.json'), JSON.stringify(evidence, null, 2));
  }
})().catch(error => { console.error(error.message); process.exitCode = 1; });
