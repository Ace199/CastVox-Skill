// Local browser checks only. Requires an existing Playwright installation.
const { chromium } = require('playwright');
const { expect } = require('playwright/test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const { pathToFileURL } = require('node:url');
const root = path.resolve(__dirname, '..');
const evidence = { status: 'RUNNING', checks: [], page_errors: [], external_requests: [], screenshots: [] };
let browser;
async function check(name, action) {
  try { await action(); evidence.checks.push({ name, status: 'PASS' }); }
  catch (error) { evidence.checks.push({ name, status: 'FAIL', error: error.message }); throw error; }
}
(async () => {
  const options = { headless: true, args: ['--disable-background-networking'] };
  if (process.env.WIREFRAME_CHROMIUM) options.executablePath = process.env.WIREFRAME_CHROMIUM;
  browser = await chromium.launch(options);
  evidence.browser = browser.version();
  const context = await browser.newContext({ viewport: { width: 1440, height: 1080 } });
  await context.route(/^https?:\/\//, route => { evidence.external_requests.push(route.request().url()); return route.abort(); });
  const page = await context.newPage();
  page.on('pageerror', error => evidence.page_errors.push(error.message));
  const open = number => page.goto(pathToFileURL(path.join(root, `Voice_Studio_Wireframe_0${number}.html`)).href);
  const apply = () => page.locator('#apply').click();
  const chooseModel = async () => { await page.getByRole('button', { name: '选择模型 / 调整参数' }).click(); await page.getByLabel('模型（必选）').selectOption('FAKE_MODEL'); };
  const screenshot = async name => { await page.screenshot({ path: path.join(__dirname, name), fullPage: true }); evidence.screenshots.push(name); };
  await open(1);
  await check('01 initial state: no voice, no model, default checked, alias unchecked', async () => {
    await expect(page.locator('#selected-name')).toHaveText('尚未选择');
    await expect(page.locator('#save-default')).toBeChecked();
    await expect(page.locator('#save-alias')).not.toBeChecked();
    await expect(page.locator('#alias')).toBeDisabled();
    await expect(page.locator('#model')).toHaveValue('');
  });
  await screenshot('01-desktop.png');
  await check('01 missing voice blocks submission', async () => { await apply(); await expect(page.locator('#feedback')).toHaveText('请选择一个声音。'); await expect(page.locator('#result')).toBeHidden(); });
  await check('01 missing model blocks submission', async () => { await page.getByRole('radio', { name: '示例女声 A', exact: true }).check(); await apply(); await expect(page.locator('#feedback')).toContainText('请选择模型'); await expect(page.locator('#model')).toBeFocused(); });
  await chooseModel();
  await check('01 direct default without alias', async () => { await apply(); await expect(page.locator('#result-list')).toContainText('直接引用 Voice ID，不创建命名音色'); await expect(page.locator('#result-list')).toContainText('项目音色库：不添加、不修改'); });
  await check('01 save only leaves task awaiting answer', async () => { await page.locator('#save-only').click(); await expect(page.locator('#result-list')).toContainText('不应用、不开始生成；任务仍等待回答'); });
  await check('01 task only makes no persistence request', async () => { await page.locator('#save-default').uncheck(); await expect(page.locator('#save-only')).toBeDisabled(); await apply(); await expect(page.locator('#result-list')).toContainText('项目默认：不修改'); });
  await check('01 alias requires name; alias-only does not change default', async () => { await page.locator('#save-alias').check(); await apply(); await expect(page.locator('#feedback')).toContainText('请填写项目音色名称'); await page.getByLabel('项目音色名称').fill('女声音1'); await apply(); await expect(page.locator('#result-list')).toContainText('新增“女声音1”'); await expect(page.locator('#result-list')).toContainText('项目默认：不修改'); });
  await check('01 user text renders as text, not markup', async () => { await page.getByLabel('项目音色名称').fill('<b>女声音</b>'); await apply(); await expect(page.locator('#result-list b')).toHaveCount(0); await expect(page.locator('#result-list')).toContainText('<b>女声音</b>'); });
  await check('01 empty project library has actionable empty state', async () => { await page.getByRole('tab', { name: 'Voices / 选声音', exact: true }).click(); await page.getByLabel('声音来源').selectOption('project'); await expect(page.locator('#voice-list')).toContainText('项目音色库暂无匹配项'); });
  await check('tabs support keyboard navigation', async () => { await page.locator('#voices-tab').focus(); await page.keyboard.press('ArrowRight'); await expect(page.locator('#settings-tab')).toBeFocused(); await expect(page.locator('#settings-panel')).toBeVisible(); });
  await open(2);
  await check('02 prefilter and missing alias shown; persistence not selected', async () => { await expect(page.locator('#notice-title')).toContainText('没有“男声音1”'); await expect(page.getByRole('radio')).toHaveCount(2); await expect(page.getByRole('radio', { name: '示例声音 D', exact: true })).toHaveCount(0); await expect(page.locator('#save-default')).not.toBeChecked(); await expect(page.locator('#save-alias')).not.toBeChecked(); await expect(page.locator('#alias')).toHaveValue('男声音1'); });
  await screenshot('02-desktop.png');
  await check('02 explicit task-only replacement is limited to p002', async () => { await page.getByRole('radio', { name: '示例男声 B', exact: true }).check(); await apply(); await expect(page.locator('#result-list')).toContainText('仅第二段 p002'); await expect(page.locator('#result-list')).toContainText('以后请求该别名仍需补全'); await expect(page.locator('#result-list')).toContainText('项目默认：不修改'); });
  await check('02 alias repair and default remain independent', async () => { await page.locator('#save-alias').check(); await apply(); await expect(page.locator('#result-list')).toContainText('新增“男声音1”'); await expect(page.locator('#result-list')).toContainText('项目默认：不修改'); await page.locator('#save-default').check(); await apply(); await expect(page.locator('#result-list')).toContainText('引用项目别名“男声音1”'); });
  await check('02 removing filter permits explicit final override', async () => { await page.getByRole('button', { name: '取消男声筛选' }).click(); await expect(page.getByRole('radio')).toHaveCount(4); await page.getByRole('radio', { name: '示例女声 A', exact: true }).check(); await expect(page.locator('#result')).toBeHidden(); await apply(); await expect(page.locator('#result-list')).toContainText('记录为约束覆盖'); });
  await check('conflict demo retains edits and prevents success preview', async () => { await page.getByText('评审工具：检查异常路径', { exact: false }).click(); await page.getByRole('button', { name: '演示配置已被修改' }).click(); await apply(); await expect(page.locator('#feedback')).toContainText('尚未提交'); await expect(page.locator('#result')).toBeHidden(); await expect(page.locator('#selected-name')).toHaveText('示例女声 A'); });
  await open(2);
  await check('timeout demo shows persistent answer + manual resume, no message sending', async () => { await page.getByRole('radio', { name: '示例男声 B', exact: true }).check(); await page.getByText('评审工具：检查异常路径', { exact: false }).click(); await page.getByRole('button', { name: '演示等待已超时' }).click(); await apply(); await expect(page.locator('#resume-note')).toContainText('用户向原 Agent 发送'); await expect(page.locator('#resume-note')).toContainText('不自动向聊天发送消息'); });
  await check('refresh resets prototype rather than persisting answers', async () => { await page.reload(); await expect(page.locator('#selected-name')).toHaveText('尚未选择'); await expect(page.locator('#result')).toBeHidden(); });
  for (const width of [1440, 390, 320]) {
    for (const scene of [1, 2]) {
      await page.setViewportSize({ width, height: width > 800 ? 1080 : 844 });
      await open(scene);
      await check(`0${scene} layout at ${width}px has no horizontal overflow`, async () => { assert.equal(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth), true); });
      if (width === 390) await screenshot(`0${scene}-mobile.png`);
    }
  }
  await check('no page JavaScript errors or external HTTP requests', async () => { assert.deepEqual(evidence.page_errors, []); assert.deepEqual(evidence.external_requests, []); });
  evidence.status = 'PASS';
})().catch(error => { evidence.status = 'FAIL'; evidence.error = error.message; process.exitCode = 1; }).finally(async () => {
  if (browser) await browser.close();
  evidence.completed_at = new Date().toISOString();
  fs.writeFileSync(path.join(__dirname, 'Wireframe_QA_Results.json'), JSON.stringify(evidence, null, 2) + '\n');
  console.log(JSON.stringify({ status: evidence.status, pass: evidence.checks.filter(x => x.status === 'PASS').length, fail: evidence.checks.filter(x => x.status === 'FAIL').length, error: evidence.error }));
});
