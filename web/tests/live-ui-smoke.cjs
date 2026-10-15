// Actual local Python service smoke check. All business interactions remain Mock.
const { chromium } = require('playwright');
const { expect } = require('playwright/test');
const fs = require('node:fs');
const path = require('node:path');
const assert = require('node:assert/strict');
const url = process.env.STUDIO_URL || 'http://127.0.0.1:8766/';
assert.ok(['127.0.0.1', 'localhost'].includes(new URL(url).hostname));
const output=path.resolve(__dirname,'../qa/visual-refresh');fs.mkdirSync(output,{recursive:true});
(async()=>{
  const browser=await chromium.launch({headless:true,executablePath:process.env.STUDIO_CHROMIUM});
  const errors=[];const requests=[];
  try {
    const page=await browser.newPage({viewport:{width:1440,height:900}});
    page.on('pageerror',e=>errors.push(e.message));page.on('console',m=>{if(m.type()==='error')errors.push(m.text());});
    await page.route('**/*',route=>{const req=route.request();if(new URL(req.url()).origin!==new URL(url).origin||req.method()!=='GET'){requests.push(req.url());return route.abort();}return route.continue();});
    await page.goto(url);await expect(page.locator('.project-voice-card')).toHaveCount(3);
    for(const [role,id] of [['主角 A','pv_001'],['主角 B','pv_002'],['旁白','pv_003']]){
      await page.getByRole('button',{name:`角色 ${role}`,exact:true}).click();
      await page.locator(`[data-voice-id="${id}"] .voice-body`).click();
    }
    await expect(page.locator('#complete-settings')).toBeEnabled();
    for(const [width,height] of [[1920,1080],[1440,900],[1280,720],[390,844],[320,640]]){
      await page.setViewportSize({width,height});await page.getByRole('tab',{name:'添加项目声音',exact:true}).click();
      await page.evaluate(()=>scrollTo(0,0));
      assert.equal(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth),true);
      await page.screenshot({path:path.join(output,`live-add-${width}x${height}.png`),fullPage:true,animations:'disabled'});
      await page.locator('[data-voice-id="pv_002"] .voice-settings').click();
      await expect(page.locator('#save-settings')).toBeVisible();
      if(width>950)await expect(page.locator('#save-settings')).toBeInViewport({ratio:1});
      await page.screenshot({path:path.join(output,`live-settings-${width}x${height}.png`),fullPage:true,animations:'disabled'});
    }
    assert.deepEqual(errors,[]);assert.deepEqual(requests,[]);
    fs.writeFileSync(path.join(output,'live-results.json'),JSON.stringify({status:'PASS',url,viewports:5,errors,unexpectedRequests:requests},null,2));
    console.log('Live service: PASS; 5 viewports; no browser errors or external/business requests.');
  } finally {await browser.close();}
})().catch(e=>{console.error(e.message);process.exitCode=1;});
