// Frontend-only test server. It mocks redacted metadata and never imports Python/Core.
const { chromium } = require('playwright');
const { expect } = require('playwright/test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const http = require('node:http');
const root = path.resolve(__dirname, '..'), output = path.join(root, 'qa', 'v16');
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
  const ctx = await browser.newContext({ viewport: { width: 1440, height: 900 }, ...options });
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
  browser = await chromium.launch({ headless: true, executablePath: process.env.STUDIO_CHROMIUM || undefined, args: ['--disable-background-networking'] }); evidence.browser = browser.version();
  const ctx = await context(), page = await ctx.newPage(); track(page);
  const state = () => page.evaluate(async () => (await import('/js/app.js?v=config-editor-1')).store.getState());
  const ready = async () => expect.poll(async () => (await state()).busy).toBe(false);
  const action = name => page.getByRole('button', { name, exact: true });
  const tab = name => page.getByRole('tab', { name, exact: true });
  const card = id => page.locator(`.project-voice-card[data-voice-id="${id}"]`);
  const field = name => page.getByLabel(name, { exact: true }).filter({ visible: true });
  const fresh = async () => { await page.goto(base); await expect(page.getByRole('heading', { name: '声音故事 · 演示项目' })).toBeVisible(); await ready(); };
  const fill = async (name, id, category = 'other') => { await field('项目声音名称').fill(name); await page.locator('#voice-id').fill(id); await field('声音分类').selectOption(category); };
  const open = async id => { await card(id).locator('.voice-settings').click(); await expect(tab('声音设置')).toHaveAttribute('aria-selected', 'true'); };
  const saveDefaults = async () => { await action('保存默认设置').click(); await expect(page.getByRole('dialog')).toContainText('确认保存默认设置'); await action('确认保存默认').click(); await ready(); };
  await fresh();
  await check('Loaded project defaults show outlines immediately without selecting a role or voice', async () => {
    await page.evaluate(async () => {
      const { store, api, controller } = await import('/js/app.js?v=config-editor-1');
      const loaded = await api.load();
      loaded.defaults = { general: 'pv_001', male: 'pv_001', female: 'pv_002' };
      const originalLoad = api.load;
      api.load = async () => structuredClone(loaded);
      store.update({ data: null });
      try { await controller.load(); } finally { api.load = originalLoad; }
    });
    await expect(card('pv_001').locator('.default-voice-outline')).toHaveCount(2);
    await expect(card('pv_001').locator('.default-voice-outline[data-slot=general]')).toHaveCount(1);
    await expect(card('pv_001').locator('.default-voice-outline[data-slot=male]')).toHaveCount(1);
    await expect(card('pv_002').locator('.default-voice-outline[data-slot=female]')).toHaveCount(1);
    await expect(card('pv_003').locator('.default-voice-outline')).toHaveCount(0);
    const loadedState = await state();
    assert.equal(loadedState.activeRoleId, null); assert.equal(loadedState.selectedVoiceId, null);
    await expect(action('保存默认设置')).toBeDisabled();
    await page.screenshot({path:path.join(output,'loaded-default-outlines.png'),fullPage:true});
    await fresh();
  });
  await check('Visual refresh uses supplied portraits with smaller offset color frames and geometric header', async () => {
    const paths=await page.locator('.voice-avatar').evaluateAll(nodes=>nodes.map(img=>img.getAttribute('src')));
    assert.ok(paths[0].startsWith('assets/man/'));assert.ok(paths[1].startsWith('assets/woman/'));assert.ok(paths[2].startsWith('assets/unknow/'));
    await expect.poll(()=>page.locator('.voice-avatar').evaluateAll(nodes=>nodes.every(img=>img.complete&&img.naturalWidth>0))).toBe(true);
    const frame=await page.locator('.voice-avatar-frame').first().evaluate(el=>{const box=getComputedStyle(el,'::before'),img=el.querySelector('img'),style=getComputedStyle(img);return{frameWidth:parseFloat(box.width),imageWidth:img.width,frameHeight:parseFloat(box.height),imageHeight:img.height,left:parseFloat(style.left),frameLeft:parseFloat(box.left),background:style.backgroundColor};});
    assert.ok(frame.imageWidth>frame.frameWidth&&frame.imageHeight>frame.frameHeight&&frame.left<frame.frameLeft);assert.equal(frame.background,'rgba(0, 0, 0, 0)');
    const headerImages=await page.locator('header img').evaluateAll(nodes=>nodes.map(img=>img.getAttribute('src')));assert.equal(headerImages.length,2);assert.ok(headerImages.every(src=>/geometry\.png$/.test(src)));
    const panels=await page.locator('#workspace>.panel').evaluateAll(nodes=>nodes.map(el=>el.getBoundingClientRect().width));const share=panels[0]/(panels[0]+panels[1]);assert.ok(share>=.55&&share<=.62);
    await card('pv_001').locator('.voice-body').focus();await expect(card('pv_001').locator('.voice-body')).toBeFocused();assert.notEqual(await card('pv_001').locator('.voice-body').evaluate(el=>getComputedStyle(el).outlineStyle),'none');
    await fresh();
  });
  await check('Open configuration targets selected provider, preserves drafts and reports errors', async () => {
    const requests=[]; let fail=false;
    await page.route('**/api/providers/open-config',async route=>{const request=route.request();requests.push(request.postDataJSON());assert.equal(request.method(),'POST');assert.equal(request.headers()['x-studio-action'],'open-config');await route.fulfill({json:fail?{ok:false,message:'无法打开本地编辑器'}:{ok:true,created:false,message:'已请求在编辑器中打开配置'}});});
    await fill('配置操作保留草稿','VOICE_KEEP','male');await action('打开配置文件').click();await expect(page.locator('#provider-config-status')).toContainText('已请求');await expect(page.locator('#voice-id')).toHaveValue('VOICE_KEEP');assert.deepEqual(requests,[{provider:'minimax'}]);
    await field('声音厂商').selectOption('volcengine');await ready();fail=true;await action('打开配置文件').click();await expect(page.locator('#provider-config-status')).toContainText('无法打开');assert.deepEqual(requests[1],{provider:'volcengine'});
    await page.evaluate(async()=>{const {store}=await import('/js/app.js?v=config-editor-1');store.update({providers:store.getState().providers.map(p=>({...p,config_edit:{available:false,reason:'尚未接入'}}))});});await expect(action('打开配置文件')).toBeDisabled();
    await page.unroute('**/api/providers/open-config');await fresh();
  });
  await check('Avatar category colors brighten on assignment, not selection, and return pale after reassignment', async () => {
    const color = node => node.evaluate(el => getComputedStyle(el.parentElement, '::before').backgroundColor);
    const ids = ['pv_001','pv_002','pv_003'], pale = ['rgb(216, 240, 237)','rgb(249, 224, 232)','rgb(255, 240, 201)'], bright = ['rgb(54, 189, 181)','rgb(238, 112, 151)','rgb(244, 189, 57)'];
    for(let i=0;i<3;i++)assert.equal(await color(card(ids[i]).locator('.voice-avatar')),pale[i]);
    const role = action('角色 主角 A');await role.click();await expect(role.locator('.unknown-avatar')).toHaveAccessibleName('尚未分配声音');assert.ok(await role.locator('.unknown-avatar').evaluate(el=>getComputedStyle(el).backgroundImage.includes('unknow.png')));
    for(let i=0;i<3;i++){await card(ids[i]).locator('.voice-body').click();assert.equal(await color(card(ids[i]).locator('.voice-avatar')),bright[i]);assert.equal(await color(role.locator('.role-avatar')),bright[i]);if(i>0)assert.equal(await color(card(ids[i-1]).locator('.voice-avatar')),pale[i-1]);}
    await action('角色 主角 B').click();assert.equal(await color(role.locator('.role-avatar')),bright[2]);
    await page.screenshot({path:path.join(output,'avatar-colors.png'),fullPage:true});await fresh();
  });
  await check('Role details open on double click/F2, dismiss outside/Escape, and assigned avatar matches voice', async () => {
    const role=action('角色 主角 A'), detail=page.locator('#role-detail');
    await expect(role.locator('.unknown-avatar')).toHaveAccessibleName('尚未分配声音');assert.ok(await role.locator('.unknown-avatar').evaluate(el=>getComputedStyle(el).backgroundImage.includes('unknow.png'))); await role.click(); await expect(detail).not.toBeVisible();
    await role.dblclick(); await expect(detail).toBeVisible(); await expect(detail).toContainText('角色形象'); await expect(detail).toContainText('推荐声音');
    await detail.click(); await expect(detail).toBeVisible(); await page.screenshot({path:path.join(output,'role-detail.png'),fullPage:true});
    const artworkBox = await detail.boundingBox(); assert.ok(Math.abs(artworkBox.width / artworkBox.height - 2) < .01);
    await detail.getByRole('button', {name:'关闭角色信息'}).click(); await expect(detail).not.toBeVisible(); await expect(role).toBeFocused();
    await role.press('F2'); await expect(detail).toBeVisible();
    await page.locator('#project-name').click(); await expect(detail).not.toBeVisible();
    await role.focus(); await role.press('F2'); await expect(detail).toBeVisible(); await page.keyboard.press('Escape'); await expect(detail).not.toBeVisible();
    await card('pv_002').locator('.voice-body').click(); await expect(role.locator('img.role-avatar')).toHaveAttribute('src',await card('pv_002').locator('.voice-avatar').getAttribute('src'));
    await page.setViewportSize({width:320,height:640}); await role.dblclick(); await expect(detail).toBeVisible(); const box=await detail.boundingBox(); assert.ok(box.x>=0&&box.x+box.width<=320&&box.y>=0&&box.y+box.height<=640);
    assert.ok(Math.abs(box.width / box.height - 2) < .01);
    await detail.locator('.role-detail-content').evaluate(el => { el.scrollTop = el.scrollHeight; }); await expect(detail).toBeVisible();
    await page.screenshot({path:path.join(output,'role-detail-narrow.png'),fullPage:true});
    await page.keyboard.press('Escape'); await page.setViewportSize({width:1440,height:900}); await fresh();
  });
  await check('V1.6 three tabs and fixed three-row project library render', async () => { await expect(page.getByRole('tab')).toHaveCount(3); await expect(tab('添加项目声音')).toHaveAttribute('aria-selected','true'); await expect(page.locator('.library-row')).toHaveCount(3); await expect(page.locator('.project-voice-card')).toHaveCount(3); await expect(action('完成设置')).toBeDisabled(); });
  await check('Defaults use one row of three cards without avatars', async () => {
    await expect(page.locator('.default-card')).toHaveCount(3); await expect(page.locator('.default-card img')).toHaveCount(0); const boxes = await page.locator('.default-card').evaluateAll(nodes => nodes.map(node => ({ y: node.getBoundingClientRect().y, color: getComputedStyle(node).backgroundColor }))); assert.equal(new Set(boxes.map(box => box.y)).size,1); assert.equal(boxes[1].y,boxes[2].y); assert.equal(new Set(boxes.map(box => box.color)).size,3); await expect(page.locator('#default-general-name')).toHaveText('未设置');
  });
  await check('Default cards stay pale on selection, brighten with a candidate and clear/cancel correctly', async () => {
    for(const [slot,id,pale,bright] of [['general','pv_003','rgb(255, 240, 201)','rgb(248, 217, 72)'],['male','pv_001','rgb(216, 240, 237)','rgb(78, 205, 196)'],['female','pv_002','rgb(249, 224, 232)','rgb(243, 129, 164)']]){
      const target=page.locator('#default-'+slot), tile=page.locator('.default-card[data-slot='+slot+']');const color=()=>tile.evaluate(el=>getComputedStyle(el).backgroundColor);
      assert.equal(await color(),pale);await target.click();assert.equal(await color(),pale);await card(id).locator('.voice-body').click();assert.equal(await color(),bright);await expect(page.locator('#default-'+slot+'-state')).toHaveText('待保存');await action('取消更改').click();assert.equal(await color(),pale);
      await card(id).locator('.voice-body').click();await saveDefaults();assert.equal(await color(),bright);await page.locator('#clear-default-'+slot).click();assert.equal(await color(),pale);await action('取消更改').click();assert.equal(await color(),bright);
    }
    await fresh();
  });
  await check('Add drafts persist per provider and across tabs; new same-name voice cannot overwrite', async () => {
    await fill('未保存 A','MINIMAX_ONLY','male'); await tab('More Tools').click(); await expect(page.getByRole('tabpanel', {name:'More Tools'})).toContainText('暂未提供功能'); await tab('添加项目声音').click(); await expect(page.locator('#voice-id')).toHaveValue('MINIMAX_ONLY');
    await field('声音厂商').selectOption('volcengine'); await ready(); await expect(page.locator('#voice-id')).toHaveValue(''); await fill('未保存 B','VOLC_ONLY'); await field('声音厂商').selectOption('minimax'); await ready(); await expect(page.locator('#voice-id')).toHaveValue('MINIMAX_ONLY');
    await fill('项目旁白','NEW_SOURCE','male'); await action('添加到项目库').click(); await expect(page.getByRole('alert')).toContainText('同名'); await expect(page.getByRole('alertdialog')).toContainText('同名'); await action('返回修改').click(); assert.equal(Object.keys((await state()).data.voices).length,3); await action('清空此厂商草稿').click();
  });
  await check('Settings use a separate draft and fixed source; cancel does not mutate saved voice', async () => {
    const before=(await state()).data.voices.pv_002; await open('pv_002'); await field('声音名称').fill('未保存新名'); await field('语速数值').fill('1.2'); await expect(page.locator('#settings-preview-state')).toContainText('调整前试听'); assert.deepEqual((await state()).data.voices.pv_002,before); await action('取消').click(); await expect(field('声音名称')).toHaveValue('对白音色'); await expect(field('语速数值')).toHaveValue('1');
    await expect(page.locator('#setting-provider')).toHaveText('minimax'); await expect(page.locator('#setting-voice-id')).toHaveText('MOCK_VOICE_2'); await expect(page.locator('#panel-settings input[readonly]')).toHaveCount(0);
  });
  await check('Descriptor slider/numeric/reset sync; save marks stale only for effective parameter changes', async () => {
    await expect(field('语速滑块')).toHaveAttribute('step','0.1'); await field('语速滑块').fill('1.3'); await expect(field('语速数值')).toHaveValue('1.3'); await action('恢复语速默认值').click(); await expect(field('语速数值')).toHaveValue('1'); await field('声调数值').fill('2'); await expect(field('声调滑块')).toHaveValue('2'); await action('保存修改').click(); await ready(); await expect(card('pv_002').locator('.card-preview-status')).toHaveText('调整前试听');
    await action('恢复声调默认值').click(); await action('保存修改').click(); await ready(); await expect(card('pv_002').locator('.card-preview-status')).toHaveText('示例试听'); await field('声音名称').fill('对白新名'); await action('保存修改').click(); await ready(); await expect(card('pv_002').locator('.card-preview-status')).toHaveText('示例试听');
  });
  await check('Switching edited object prompts; save/discard/cancel preserve the intended object', async () => {
    await field('声音名称').fill('待处理'); await card('pv_001').locator('.voice-settings').click(); await expect(page.getByRole('dialog')).toContainText('未保存修改'); await page.locator('#cancel-confirm').click(); await expect(field('声音名称')).toHaveValue('待处理');
    await card('pv_001').locator('.voice-settings').click(); await action('放弃并切换').click(); await expect(field('声音名称')).toHaveValue('项目旁白');
    await field('声音名称').fill('旁白新名'); await card('pv_002').locator('.voice-settings').click(); await action('保存并切换').click(); await ready(); await expect(field('声音名称')).toHaveValue('对白新名'); assert.equal((await state()).data.voices.pv_001.name,'旁白新名');
  });
  await check('Defaults select via cards and project library; classification filters candidates and requires explicit save', async () => {
    await action('选择默认男声').click(); await expect(card('pv_002').locator('.voice-body')).toBeDisabled(); await card('pv_001').locator('.voice-body').click(); assert.equal((await state()).data.defaults.male,null); await action('选择默认女声').click(); await card('pv_002').locator('.voice-body').click(); await saveDefaults(); assert.equal((await state()).data.defaults.female,'pv_002'); assert.equal((await state()).roles[1].assignment,null);
  });
  await check('Changing category warns before invalidating a gender default, preserves raw reference', async () => {
    await open('pv_002'); await field('声音分类').filter({visible:true}).selectOption('other'); await action('保存修改').click(); await expect(page.getByRole('dialog')).toContainText('默认女声将显示'); await action('确认保存修改').click(); await ready(); await expect(page.locator('#default-female-name')).toHaveText('未设置'); assert.equal((await state()).data.defaults.female,'pv_002');
    await field('声音分类').filter({visible:true}).selectOption('female'); await action('保存修改').click(); await ready(); await expect(page.locator('#default-female-name')).toHaveText('对白新名');
  });
  await check('Role selection differs from assignment; controls do not bind roles and optional defaults can be empty', async () => {
    await action('清空默认男声').click(); await action('清空默认女声').click(); await saveDefaults(); await action('角色 主角 A').click(); await expect(action('角色 主角 A')).not.toHaveClass(/is-assigned/); const before=(await state()).roles; await card('pv_002').locator('.voice-preview').click(); await expect.poll(async()=>(await state()).player.status).toBe('playing'); assert.deepEqual((await state()).roles,before); await card('pv_002').locator('.voice-preview').click(); await card('pv_001').locator('.voice-settings').click(); assert.deepEqual((await state()).roles,before);
    for(const [role,id] of [['主角 A','pv_001'],['主角 B','pv_002'],['旁白','pv_003']]) { await action(`角色 ${role}`).click(); await card(id).locator('.voice-body').click(); }
    await expect(action('角色 主角 A')).toHaveClass(/is-assigned/); await expect(action('角色 主角 A')).toContainText('✓ 已分配'); await expect(action('完成设置')).toBeEnabled(); assert.deepEqual((await state()).data.defaults,{general:null,male:null,female:null});
  });
  await check('Preview states: none and unavailable disable play; a valid local Mock sample pauses/resumes', async () => {
    await expect(card('pv_001').locator('.voice-preview')).toBeDisabled(); await expect(card('pv_003').locator('.voice-preview')).toBeDisabled(); await expect(card('pv_003').locator('.card-preview-status')).toContainText('文件不可用'); const play=card('pv_002').locator('.voice-preview'); await play.click(); await expect.poll(async()=>(await state()).player.status).toBe('playing'); await play.click(); await expect.poll(async()=>(await state()).player.status).toBe('paused'); await play.click(); await expect.poll(async()=>(await state()).player.status).toBe('playing');
  });
  await check('Only one actual Audio instance plays at once', async () => {
    await page.evaluate(async()=>{const {controller}=await import('/js/app.js?v=config-editor-1');await controller.setPreviewScenario('pv_001','valid');}); await card('pv_001').locator('.voice-preview').click(); await expect.poll(async()=>(await state()).player.voiceId).toBe('pv_001'); assert.equal(await page.evaluate(()=>window.__testAudio.filter(audio=>!audio.paused&&!audio.ended).length),1); await card('pv_002').locator('.voice-preview').click(); await expect.poll(async()=>(await state()).player.voiceId).toBe('pv_002'); assert.equal(await page.evaluate(()=>window.__testAudio.filter(audio=>!audio.paused&&!audio.ended).length),1);
  });
  await check('Stale saved preview remains playable; successful update switches only after local Mock save', async () => {
    await open('pv_002'); await field('语速数值').fill('1.2'); await action('保存修改').click(); await ready(); await expect(card('pv_002').locator('.voice-preview')).toBeEnabled(); const before=(await state()).data.voices.pv_002.preview.sample_id; await action('更新试听').click(); await expect(page.locator('#preview-update-status')).toContainText('旧样本仍可播放'); assert.equal((await state()).data.voices.pv_002.preview.sample_id,before); await expect.poll(async()=>(await state()).previewSaving.pv_002).toBe(false); assert.notEqual((await state()).data.voices.pv_002.preview.sample_id,before); await expect(card('pv_002').locator('.card-preview-status')).toHaveText('示例试听');
  });
  await check('Saving failure and revision conflict retain settings draft for recovery', async () => {
    await field('声音名称').fill('错误恢复名'); await action('打开 Debug').click(); await action('下一次写入失败').click(); await action('保存修改').click(); await expect(page.getByRole('alert')).toContainText('失败'); await action('模拟 revision 冲突').click(); await action('保存修改').click(); await expect(page.getByRole('alert')).toContainText('revision'); await expect(field('声音名称')).toHaveValue('错误恢复名'); await action('重新读取项目').click(); await ready(); await action('保存修改').click(); await ready(); assert.equal((await state()).data.voices.pv_002.name,'错误恢复名'); await action('关闭 Debug').last().click();
  });
  await check('Complete submits Mock question/answer with frozen assignments and no default writes', async () => {
    const before=structuredClone((await state()).data.defaults); await action('完成设置').click(); await ready(); await expect(page.getByRole('heading',{name:'配置已模拟提交'})).toBeVisible(); const s=await state();assert.equal(s.receipt.answer.question_id,'MOCK_QUESTION_A');assert.equal(s.receipt.answer.assignments.length,3);assert.deepEqual(s.data.defaults,before);assert.equal(s.receipt.can_generate,false);
  });
  await fresh();
  await check('Hover requires a continuous one second, exit resets and moving onto × keeps it visible without reflow', async () => {
    await page.clock.install();await page.clock.pauseAt(new Date());await page.mouse.move(1,1);const target=card('pv_001'),remove=target.locator('.voice-delete');await target.hover();const before=await target.boundingBox();await page.clock.fastForward(999);await expect(remove).toBeHidden();await page.clock.fastForward(1);await expect(remove).toBeVisible();assert.deepEqual(await target.boundingBox(),before);await remove.hover();await expect(remove).toBeVisible();await page.screenshot({path:path.join(output,'hover-delete.png'),fullPage:true});await page.mouse.move(1,1);await expect(remove).toBeHidden();await target.hover();await page.clock.fastForward(500);await page.mouse.move(1,1);await target.hover();await page.clock.fastForward(999);await expect(remove).toBeHidden();await page.clock.fastForward(1);await expect(remove).toBeVisible();await page.clock.resume();await page.mouse.move(1,1);
  });
  await check('Keyboard deletion is reachable immediately; referenced voice asks for confirmation without assigning a role', async () => {
    await card('pv_001').locator('.voice-body').focus();await expect(card('pv_001').locator('.voice-delete')).toBeVisible();await page.keyboard.press('Delete');await expect(page.getByRole('dialog')).toContainText('已有任务保留');assert.equal((await state()).roles[0].assignment,null);await page.screenshot({path:path.join(output,'delete-confirm.png'),fullPage:true});await page.locator('#cancel-confirm').click();
  });
  await check('Soft delete preserves referenced assignment and preview; undo restores stable identity', async () => {
    await action('角色 主角 B').click();await card('pv_002').locator('.voice-body').click();const original=structuredClone((await state()).data.voices.pv_002);await open('pv_002');await action('从项目库删除此声音').click();await action('确认软删除').click();await ready();await expect(card('pv_002')).toHaveCount(0);await expect(action('角色 主角 B')).toContainText('已从项目库移除');assert.deepEqual((await state()).data.voices.pv_002.preview,original.preview);await action('撤销删除').click();await ready();await expect(card('pv_002')).toHaveCount(1);assert.equal((await state()).data.voices.pv_002.id,original.id);
  });
  await check('Undo name conflict requires explicit rename and never overwrites new same-name voice', async () => {
    await open('pv_003');await action('从项目库删除此声音').click();await ready();await tab('添加项目声音').click();await fill('环境叙述','NEW_OTHER');await action('添加到项目库').click();await ready();await action('撤销删除').click();await expect(page.getByRole('dialog')).toContainText('名称冲突');await field('恢复后的名称').fill('恢复的环境声');await action('改名并恢复').click();await ready();assert.equal((await state()).data.voices.pv_003.name,'恢复的环境声');assert.equal(Object.values((await state()).data.voices).filter(v=>!v.deleted&&v.name==='环境叙述').length,1);
  });
  await check('Unknown model capabilities disable settings and explain instead of assuming ranges', async () => {
    const raw=structuredClone(descriptors).map(provider=>({...provider,source:'local_readonly'}));await page.route('**/api/providers',route=>route.fulfill({json:{providers:raw}}));await fresh();await open('pv_001');await expect(field('语速数值')).toBeDisabled();await expect(field('声调数值')).toBeDisabled();await expect(page.locator('#speed-capability')).toContainText('尚未验证');await page.screenshot({path:path.join(output,'unverified-controls.png'),fullPage:true});await page.unroute('**/api/providers');
  });
  await check('Corrupt local media is handled as unavailable without TTS or uncaught errors', async () => {
    await fresh();await page.route('**/assets/mock-preview-a.wav',route=>route.fulfill({status:200,contentType:'audio/wav',body:'MOCK_CORRUPT_AUDIO'}));await card('pv_002').locator('.voice-preview').click();await expect.poll(async()=>(await state()).player.status).toBe('error');await expect(card('pv_002').locator('.card-preview-status')).toContainText('文件不可用');await page.unroute('**/assets/mock-preview-a.wav');
  });
  await check('Touch deletes through settings without hover and without triggering assignment', async () => {
    const mobile=await context({viewport:{width:390,height:844},hasTouch:true,isMobile:true});const touch=await mobile.newPage();track(touch);await touch.goto(base);await expect(touch.getByRole('heading',{name:'声音故事 · 演示项目'})).toBeVisible();await touch.locator('[data-voice-id=pv_002] .voice-settings').tap();await touch.getByRole('button',{name:'从项目库删除此声音',exact:true}).tap();await expect(touch.locator('[data-voice-id=pv_002]')).toHaveCount(0);const s=await touch.evaluate(async()=>(await import('/js/app.js?v=config-editor-1')).store.getState());assert.equal(s.roles[0].assignment,null);await mobile.close();
  });
  await fresh();for(const [name,id] of [['主角 A','pv_001'],['主角 B','pv_002'],['旁白','pv_001']]){await action(`角色 ${name}`).click();await card(id).locator('.voice-body').click();}await open('pv_002');await field('语速数值').fill('1.2');await action('保存修改').click();await ready();await page.evaluate(()=>document.activeElement.blur());
  for(const [width,height] of [[1920,1080],[1440,900],[1280,720],[390,844],[320,640]]) await check(`Layout ${width}×${height}: independent scroll and no horizontal page overflow`,async()=>{
    await page.setViewportSize({width,height});
    if(width>=951){await page.evaluate(()=>scrollTo(0,0));await page.locator('.settings-content').evaluate(node=>node.scrollTop=0);await expect(action('保存修改')).toBeInViewport({ratio:1});const saveBox=await action('保存修改').boundingBox();assert.equal(await page.evaluate(({x,y})=>document.elementFromPoint(x,y)?.closest('button')?.id,{x:saveBox.x+saveBox.width/2,y:saveBox.y+saveBox.height/2}),'save-settings');}
    await page.mouse.move(1,1);await page.evaluate(()=>scrollTo(0,0));await page.locator('.project-panel').evaluate(node=>node.scrollTop=0);assert.equal(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth),true);const boxes=await page.locator('.default-card').evaluateAll(nodes=>nodes.map(node=>node.getBoundingClientRect().y));assert.equal(new Set(boxes).size,1);if(width>=1440&&height>=900){await expect(action('角色 主角 A')).toBeInViewport({ratio:1});await expect(action('完成设置')).toBeInViewport({ratio:1});const box=await action('角色 主角 A').boundingBox();assert.equal(await page.evaluate(({x,y})=>!!document.elementFromPoint(x,y)?.closest('.role-card'),{x:box.x+box.width/2,y:box.y+box.height/2}),true);}await page.screenshot({path:path.join(output,`studio-${width}x${height}.png`),fullPage:true});
  });
  await check('Compact add form: paired fields, full-width ID, visible desktop submit and no narrow overflow',async()=>{
    await page.getByRole('tab',{name:'添加项目声音',exact:true}).click();
    for(const [width,height] of [[1920,1080],[1440,900],[1280,720],[390,844],[320,640]]){
      await page.setViewportSize({width,height});await page.evaluate(()=>scrollTo(0,0));await page.locator('.add-content').evaluate(node=>node.scrollTop=0);
      const boxes=await page.locator('#panel-add .identity-grid>div').evaluateAll(nodes=>Object.fromEntries(nodes.map(node=>[node.className,{x:node.getBoundingClientRect().x,y:node.getBoundingClientRect().y,width:node.getBoundingClientRect().width}])));
      assert.equal(boxes['provider-field'].y,boxes['model-field'].y);assert.equal(boxes['name-field'].y,boxes['category-field'].y);assert.ok(boxes['id-field'].y>boxes['name-field'].y);assert.ok(boxes['id-field'].width>boxes['name-field'].width*1.9);
      assert.equal(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth),true);
      if(width>=951){await expect(action('添加到项目库')).toBeInViewport({ratio:1});const box=await action('添加到项目库').boundingBox();assert.equal(await page.evaluate(({x,y})=>document.elementFromPoint(x,y)?.closest('button')?.id,{x:box.x+box.width/2,y:box.y+box.height/2}),'save-alias');}
      await page.screenshot({path:path.join(output,`add-${width}x${height}.png`),fullPage:true});
    }
  });
  await check('Desktop single canvas: compact header, both panels fit with no vertical scrolling in add/settings',async()=>{
    await fresh();
    for(const [width,height] of [[1920,1080],[1440,900],[1280,720]]){
      await page.setViewportSize({width,height});
      for(const mode of ['add','settings']){
        if(mode==='add')await tab('添加项目声音').click();else await open('pv_002');
        await page.evaluate(()=>scrollTo(0,0));
        assert.ok((await page.locator('header').boundingBox()).height<=56);
        assert.equal(await page.evaluate(()=>document.documentElement.scrollHeight<=innerHeight),true);
        for(const selector of ['.project-panel',mode==='add'?'.add-content':'.settings-content'])assert.equal(await page.locator(selector).evaluate(el=>el.scrollHeight<=el.clientHeight+1),true,selector+' must fit '+width+'x'+height);
        await expect(action('完成设置')).toBeInViewport({ratio:1});await expect(action(mode==='add'?'添加到项目库':'保存修改')).toBeInViewport({ratio:1});
        await page.screenshot({path:path.join(output,'canvas-'+mode+'-'+width+'x'+height+'.png'),fullPage:true});
      }
    }
  });
  await check('Dense grouped library has one shared scroller with fixed labels; role scrolling is separate',async()=>{
    await page.setViewportSize({width:1440,height:900});await page.evaluate(async()=>{const {store}=await import('/js/app.js?v=config-editor-1');const s=store.getState();for(const category of ['male','female','other'])for(let i=0;i<25;i++){const id=`dense_${category}_${i}`;s.data.voices[id]={...structuredClone(s.data.voices.pv_001),id,name:'长名称测试'.repeat(12)+i,category};}store.update({data:s.data});});const before=await page.locator('.row-label').first().boundingBox();await page.locator('.library-scroll').evaluate(node=>node.scrollLeft=500);const xs=await page.locator('.library-row').evaluateAll(nodes=>nodes.map(node=>Math.round(node.getBoundingClientRect().left)));assert.equal(new Set(xs).size,1);assert.equal((await page.locator('.row-label').first().boundingBox()).x,before.x);assert.equal(await page.locator('.voice-name').last().evaluate(node=>node.scrollWidth>node.clientWidth),true);const libScroll=await page.locator('.library-scroll').evaluate(node=>node.scrollLeft);await page.locator('#role-strip').evaluate(node=>node.scrollLeft=200);assert.equal(await page.locator('.library-scroll').evaluate(node=>node.scrollLeft),libScroll);
  });
  await check('No question: management remains possible without claiming Harness resume',async()=>{await page.evaluate(async()=>{const {api,controller}=await import('/js/app.js?v=config-editor-1');api.configureMock({management:true});await controller.load();});await expect(action('完成设置')).toBeDisabled();await expect(page.locator('#complete-reason')).toContainText('Question');});
  await check('No console errors, missing resources, provider requests or HTTP business writes',async()=>{assert.deepEqual(evidence.errors,[]);assert.deepEqual(evidence.failedResponses,[]);assert.deepEqual(evidence.externalRequests,[]);assert.deepEqual(evidence.businessRequests,[]);});
  evidence.status='PASS';
})().catch(error=>{evidence.status='FAIL';evidence.failure=error.message;process.exitCode=1;}).finally(async()=>{if(browser)await browser.close();if(server)await new Promise(resolve=>server.close(resolve));fs.writeFileSync(path.join(output,'browser-results.json'),JSON.stringify(evidence,null,2));console.log(JSON.stringify({status:evidence.status,passed:evidence.checks.filter(c=>c.status==='PASS').length,failed:evidence.checks.filter(c=>c.status==='FAIL').length,failure:evidence.failure}));});
