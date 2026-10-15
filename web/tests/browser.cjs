// Uses an existing Playwright and Chromium installation; never downloads dependencies.
const { chromium } = require('playwright');
const { expect } = require('playwright/test');
const assert = require('node:assert/strict');
const { spawn } = require('node:child_process');
const fs = require('node:fs');
const path = require('node:path');
const net = require('node:net');
const root = path.resolve(__dirname, '..'), output = path.join(root, 'qa', 'simplified');
const evidence = { status: 'RUNNING', checks: [], errors: [], externalRequests: [], businessRequests: [], failedResponses: [] };
let browser, server;
async function check(name, run) { try { await run(); evidence.checks.push({ name, status: 'PASS' }); } catch (error) { evidence.checks.push({ name, status: 'FAIL', error: error.message }); throw error; } }
(async () => {
  fs.mkdirSync(output, { recursive: true });
  const probe = net.createServer(); await new Promise(r => probe.listen(0, '127.0.0.1', r)); const port = probe.address().port; await new Promise(r => probe.close(r)); const base = `http://127.0.0.1:${port}`;
  server = spawn('python', [path.join(root, '..', 'studio_server.py'), '--port', String(port), '--config-dir', path.join(root, 'tests', 'fixtures', 'providers')], { windowsHide: true, stdio: 'ignore' });
  await expect.poll(async () => { try { return (await fetch(base)).status; } catch { return 0; } }).toBe(200);
  browser = await chromium.launch({ headless: true, ...(process.env.STUDIO_CHROMIUM ? { executablePath: process.env.STUDIO_CHROMIUM } : {}), args: ['--disable-background-networking'] });
  evidence.browser = browser.version(); const context = await browser.newContext({ viewport: { width: 1440, height: 900 } });
  await context.route('**/*', route => { const r = route.request(); if (new URL(r.url()).origin !== base) { evidence.externalRequests.push(r.url()); return route.abort(); } if ((['fetch', 'xhr', 'websocket', 'eventsource'].includes(r.resourceType()) && new URL(r.url()).pathname !== '/api/providers') || r.method() !== 'GET') { evidence.businessRequests.push(r.url()); return route.abort(); } return route.continue(); });
  const page = await context.newPage(); page.setDefaultTimeout(7000);
  page.on('pageerror', e => evidence.errors.push(e.message)); page.on('console', m => { if (m.type() === 'error') evidence.errors.push(m.text()); }); page.on('response', r => { if (r.status() >= 400) evidence.failedResponses.push(r.url()); });
  const state = () => page.evaluate(async () => (await import('/js/app.js')).store.getState());
  const ready = async () => expect.poll(async () => (await state()).busy).toBe(false);
  const action = name => page.getByRole('button', { name, exact: true });
  await page.goto(base); await expect(page.getByRole('heading', { name: '声音故事 · 演示项目' })).toBeVisible(); await ready();
  const tab = name => page.getByRole('tab', {name,exact:true});
  const field = name => page.getByLabel(name, {exact:true});
  const save = () => page.locator('#save-alias').click();
  const edit = name => action(`设置 ${name}`).click();
  const enter = async (name,id,category='other') => { await field('项目音色名称').fill(name); await page.locator('#voice-id').fill(id); await page.locator('#voice-category').selectOption(category); };
  await check('HTTP ES modules and two-tab layout load without obsolete workflows', async () => {
    await expect(tab('添加项目声音')).toHaveAttribute('aria-selected','true'); await expect(page.getByRole('tab')).toHaveCount(2); await expect(page.locator('.library-row')).toHaveCount(3);
    await expect(page.locator('audio,video,#pool,#speed,#volume,#emotion')).toHaveCount(0); await expect(page.locator('#complete-settings')).toBeDisabled();
    await expect(page.locator('#voice-model')).toHaveValue('MOCK_MINIMAX_HD'); await expect(page.locator('#provider-link')).toHaveAttribute('href','https://www.minimax.cn/audio');
  });
  await check('No matching local preview: play disabled, reason provided, no audio request', async () => {
    for(const b of await page.locator('.voice-preview').all()) { await expect(b).toBeDisabled(); await expect(b).toHaveAttribute('title',/没有匹配/); }
    await expect(page.getByText(/暂无匹配音色的合法本地试听文件/)).toBeVisible();
  });
  await check('Tab switches preserve all five draft fields and support keyboard navigation', async () => {
    await enter('未保存草稿','DRAFT_ID','female'); const before=(await state()).draft; await tab('More Tools').click(); await expect(page.getByRole('tabpanel',{name:'More Tools',exact:true})).toContainText('暂未提供功能'); await page.screenshot({path:path.join(output,'more-tools.png'),fullPage:true}); await tab('More Tools').focus(); await page.keyboard.press('Home'); await expect(tab('添加项目声音')).toBeFocused(); assert.deepEqual((await state()).draft,before); await action('清空输入').click();
  });
  await check('Required category and exact Voice ID validation prevent invalid saves', async () => {
    await field('项目音色名称').fill('新声音'); await page.locator('#voice-id').fill('NEW_ID'); await save(); await expect(page.getByRole('alert')).toContainText('分类');
    await page.locator('#voice-category').selectOption('male'); await page.locator('#voice-id').fill('invalid/id'); await save(); await expect(page.getByRole('alert')).toContainText('Voice ID');
  });
  await check('Add manually classified sound and display in corresponding shared row', async () => {
    await enter('新增旁白','USER_VOICE_A','other'); await save(); await ready(); await expect(page.locator('.library-row[data-category=other]').getByRole('button',{name:'选择项目声音：新增旁白',exact:true})).toBeVisible(); const s=await state();assert.equal(s.data.named_voices['新增旁白'].metadata.source,'user_selected');assert.equal(s.data.default_voice,null);
  });
  await check('Explicit default confirmation cancel and save are independent from aliases', async () => {
    await action('设为项目默认').click(); await expect(page.getByRole('dialog')).toBeVisible(); await page.keyboard.press('Escape'); assert.equal((await state()).data.default_voice,null);
    await action('设为项目默认').click(); await action('确认保存（Mock）').click(); await ready(); assert.equal((await state()).data.default_voice.ref.voice_id,'USER_VOICE_A');
  });
  await check('Edit existing name/category/ID; rebind confirmation shows old and new identity', async () => {
    await edit('新增旁白'); await enter('改名旁白','USER_VOICE_B','female'); await save(); await expect(page.getByRole('dialog')).toContainText('确认项目别名重绑定'); await expect(page.getByRole('dialog')).toContainText('USER_VOICE_A'); await action('确认保存（Mock）').focus();await page.keyboard.press('Tab');await expect(action('返回编辑')).toBeFocused();
    await page.screenshot({path:path.join(output,'confirm-rebind.png'),fullPage:true}); await action('返回编辑').click(); assert.equal((await state()).data.named_voices['新增旁白'].ref.voice_id,'USER_VOICE_A');
    await save();await action('确认保存（Mock）').click();await ready();const s=await state();assert.equal(Object.hasOwn(s.data.named_voices,'新增旁白'),false);assert.equal(s.data.named_voices['改名旁白'].metadata.gender,'female');assert.equal(s.data.default_voice.ref.voice_id,'USER_VOICE_A');
  });
  await check('Rename cannot overwrite another project alias', async () => {
    await field('项目音色名称').fill('对白音色');await save();await expect(page.getByRole('alert')).toContainText('已存在');await action('清空输入').click();
  });
  await check('Provider switch reloads metadata, clears ID and does not change default provider', async () => {
    await enter('火山声音','MINIMAX_ONLY_ID','other');await page.locator('#provider').selectOption('volcengine');await ready();await expect(page.locator('#voice-id')).toHaveValue('');await expect(page.locator('#voice-model')).toHaveValue('MOCK_VOLC_TTS');await expect(page.getByLabel('音色标识（speaker）',{exact:true})).toBeVisible();await expect(page.locator('#provider-support')).toContainText('待接入');await expect(page.locator('#provider-link')).toHaveAttribute('href',/docs.volcengine.com/);assert.equal((await state()).data.default_voice.ref.provider,'minimax');assert.equal((await state()).providerDrafts.minimax.voiceId,'MINIMAX_ONLY_ID');
  });
  await check('Mixed-provider voices save only to Mock, each with its fixed model', async () => {
    await page.locator('#voice-id').fill('speaker_A');await save();await ready();const s=await state();assert.equal(s.data.named_voices['火山声音'].ref.provider,'volcengine');assert.equal(s.data.named_voices['火山声音'].model,'MOCK_VOLC_TTS');assert.equal(s.data.named_voices['项目旁白'].model,'MOCK_MINIMAX_HD');assert.equal(s.data.studio_schema_version,'1.5-mock');await expect(page.locator('.library-row[data-category=other]').getByRole('button',{name:'选择项目声音：火山声音',exact:true})).toBeVisible();await page.screenshot({path:path.join(output,'provider-volcengine-mock.png'),fullPage:true});
  });
  await check('Provider switch back never reuses foreign speaker identifier', async () => {
    await page.locator('#provider').selectOption('minimax');await ready();await expect(page.locator('#voice-id')).toHaveValue('');await expect(page.locator('#voice-model')).toHaveValue('MOCK_MINIMAX_HD');await action('恢复本厂商未保存草稿').click();await expect(page.locator('#voice-id')).toHaveValue('MINIMAX_ONLY_ID');await action('清空输入').click();
  });
  await check('Lightweight current roles keep assignment, avatar, classification and independent scrolling', async () => {
    const a=action('角色 主角 A'),b=action('角色 主角 B');await a.click();await expect(a).not.toHaveClass(/is-assigned/);const avatar=await a.locator('img').getAttribute('src');await action('选择项目声音：项目旁白').click();await expect(a).toHaveClass(/is-assigned/);await expect(a).toHaveAttribute('data-gender','male');
    await b.click();await action('选择项目声音：对白音色').click();await expect(b).toHaveAttribute('data-gender','female');await expect(a).toHaveClass(/is-assigned/);await a.click();await expect(a.locator('img')).toHaveAttribute('src',avatar);await expect(page.locator('#editor-role-context img')).toHaveAttribute('src',avatar);
    const before=(await state()).roles;await edit('火山声音');assert.deepEqual((await state()).roles,before);
    await a.focus();await page.keyboard.press('End');await expect(action('角色 旁白')).toBeFocused();await action('选择项目声音：火山声音').click();await expect(action('角色 旁白')).toHaveAttribute('data-gender','other');
    await page.locator('#role-strip').evaluate(e=>e.scrollLeft=100);assert.equal(await page.locator('.library-scroll').evaluate(e=>e.scrollLeft),0);
  });
  await check('Fixed default entry opens direct modal without replacing role editor', async () => {
    const before=await state();await page.locator('#default-target').click();await expect(page.locator('#quick-default-choice')).toBeVisible();await action('返回编辑').click();assert.deepEqual((await state()).draft,before.draft);assert.deepEqual((await state()).roles,before.roles);
  });
  await check('Debug failure, duplicate save and revision conflict preserve input and retry safely', async () => {
    await action('新增音色').click();await page.locator('#provider').selectOption('minimax');await ready();await enter('重试声音','RETRY_ID','male');await action('打开 Debug').click();await action('记录测试事件').click();await expect(page.getByRole('row').filter({hasText:'debug.test'})).toContainText('MOCK_PROJECT_A');
    await action('下一次写入失败').click();await save();await expect(page.getByRole('alert')).toContainText('失败');await action('模拟 revision 冲突').click();await save();await expect(page.getByRole('alert')).toContainText('revision');await expect(page.locator('#voice-id')).toHaveValue('RETRY_ID');await action('重新读取配置').click();await ready();await page.locator('#save-alias').evaluate(b=>{b.click();b.click();});await ready();assert.equal((await state()).data.named_voices['重试声音'].ref.voice_id,'RETRY_ID');await action('关闭 Debug').last().click();
  });
  await check('Complete submits current Question/Answer, assignments and model snapshots; default unchanged', async () => {
    const before=(await state()).data.default_voice;await action('完成设置').click();await ready();await expect(page.getByRole('heading',{name:'配置回答已接收（Mock）'})).toBeVisible();const s=await state();assert.equal(s.receipt.answer.job_id,'MOCK_JOB_A');assert.equal(s.receipt.answer.question_id,'MOCK_QUESTION_A');assert.ok(s.receipt.answer.answer_id);assert.equal(s.receipt.answer.task_assignments[2].binding.voice.ref.provider,'volcengine');assert.deepEqual(s.data.default_voice,before);assert.equal(s.receipt.mock,true);await page.screenshot({path:path.join(output,'answer-receipt.png'),fullPage:true});
  });
  const catalog=await (await page.request.get(`${base}/api/providers`)).json();
  await check('Config default changes do not mutate stored model/default or frozen answer', async () => {
    const before=await state(),updated=structuredClone(catalog);updated.providers[0].default_model='MOCK_MINIMAX_FAST';await page.route('**/api/providers',r=>r.fulfill({json:updated}));await action('重新读取模型').click();await ready();const after=await state();assert.deepEqual(after.data.named_voices,before.data.named_voices);assert.deepEqual(after.data.default_voice,before.data.default_voice);await page.unroute('**/api/providers');
  });
  await check('Missing models show repairable state, never invalid-API-Key claim or fallback list', async () => {
    const empty=structuredClone(catalog);for(const p of empty.providers){p.models=[];p.default_model=null;p.model_status='not_configured';p.message='尚未配置模型；这不表示 API Key 无效';}await page.route('**/api/providers',r=>r.fulfill({json:empty}));await page.reload();await ready();await expect(page.locator('#model-help')).toContainText('尚未配置模型');await expect(page.locator('#voice-model')).toHaveValue('');await expect(page.locator('#voice-model option')).toHaveCount(1);await page.screenshot({path:path.join(output,'models-not-configured.png'),fullPage:true});await page.unroute('**/api/providers');
  });
  await check('Management mode cannot claim task continuation', async () => {
    await page.reload();await ready();await page.evaluate(async()=>{const {api,controller}=await import('/js/app.js');api.configureMock({management:true,empty:true});await controller.load();});await expect(action('完成设置')).toBeDisabled();await expect(page.locator('#complete-reason')).toContainText('管理模式');
  });
  await page.reload();await ready();await action('角色 主角 A').click();await action('选择项目声音：项目旁白').click();await action('角色 主角 B').click();await action('选择项目声音：对白音色').click();await action('角色 旁白').click();await action('选择项目声音：项目旁白').click();await page.locator('#default-target').click();await action('确认保存（Mock）').click();await ready();await action('清空输入').click();await page.evaluate(()=>document.activeElement.blur());await page.evaluate(()=>scrollTo(0,0));
  for(const [width,height] of [[1920,1080],[1440,900],[1280,720],[390,844],[320,640]]) await check(`Layout ${width}×${height}: bounded columns and no page overflow`,async()=>{
    await page.setViewportSize({width,height});await expect(page.getByRole('heading',{name:'声音故事 · 演示项目'})).toBeVisible();assert.equal(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth),true);await page.mouse.move(0,0);await page.screenshot({path:path.join(output,`studio-${width}x${height}.png`),fullPage:true});
  });
  await check('Dense male/female/other rows share one scroller and fixed labels; long names truncate',async()=>{
    await page.setViewportSize({width:1280,height:720});await page.evaluate(async()=>{const {store}=await import('/js/app.js');const s=store.getState();for(const gender of ['male','female','other'])for(let i=0;i<20;i++)s.data.named_voices[gender+'长名称'.repeat(15)+i]={...structuredClone(s.data.named_voices['项目旁白']),metadata:{gender,source:'mock_fixture'}};store.update({data:s.data});});
    assert.equal(await page.locator('.library-scroll').count(),1);const before=await page.locator('.row-label').first().boundingBox();await page.locator('.library-scroll').evaluate(e=>e.scrollLeft=500);const positions=await page.locator('.library-row').evaluateAll(rows=>rows.map(r=>Math.round(r.getBoundingClientRect().left)));assert.equal(new Set(positions).size,1);assert.equal((await page.locator('.row-label').first().boundingBox()).x,before.x);assert.equal(await page.locator('.voice-name').last().evaluate(e=>e.scrollWidth>e.clientWidth),true);assert.equal(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth),true);
  });
  await check('Raw credential/config fixtures are not served; API only exposes allowlisted metadata',async()=>{
    const response=await page.request.get(`${base}/tests/fixtures/providers/minimax/config.json`);assert.equal(response.status(),404);const metadata=await(await page.request.get(`${base}/api/providers`)).json();assert.equal(JSON.stringify(metadata).includes('api_key'),false);
  });
  await check('Dev debug can be disabled',async()=>{await page.goto(`${base}/?dev=0`);await ready();await expect(action('打开 Debug')).toBeHidden();});
  await check('No console errors, missing assets, external requests or business writes',async()=>{assert.deepEqual(evidence.errors,[]);assert.deepEqual(evidence.failedResponses,[]);assert.deepEqual(evidence.businessRequests,[]);assert.deepEqual(evidence.externalRequests,[]);});
  evidence.status = 'PASS';
})().catch(error => { evidence.status = 'FAIL'; evidence.failure = error.message; process.exitCode = 1; }).finally(async () => {
  if (browser) await browser.close(); if (server) server.kill(); fs.writeFileSync(path.join(output, 'browser-results.json'), JSON.stringify(evidence, null, 2)); console.log(JSON.stringify({ status: evidence.status, passed: evidence.checks.filter(c => c.status === 'PASS').length, failed: evidence.checks.filter(c => c.status === 'FAIL').length, failure: evidence.failure }));
});
