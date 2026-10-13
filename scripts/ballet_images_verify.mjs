import { chromium } from 'file:///C:/Users/All_in/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules/playwright/index.mjs';
import {mkdir,writeFile} from 'node:fs/promises';
import assert from 'node:assert/strict';
const base=process.argv[2]||'http://127.0.0.1:5175';
const browser=await chromium.launch({headless:true,executablePath:'C:/Program Files/Google/Chrome/Application/chrome.exe'});
const ctx=await browser.newContext({viewport:{width:1440,height:1000}});
const login=await ctx.request.post('http://127.0.0.1:8013/api/auth/login',{data:{username:'browserqa',password:'browser-qa-only'}});
const token=(await login.json()).access_token;
await ctx.addInitScript(t=>localStorage.setItem('pd-rehab-token',t),token);
// When validating production rendering, use the isolated QA API for reads only.
if(base.startsWith('https')) await ctx.route('**/pd-rehab/api/**',async route=>{const req=route.request();assert.equal(req.method(),'GET');const path=new URL(req.url()).pathname.replace('/pd-rehab','');const r=await ctx.request.get('http://127.0.0.1:8013'+path,{headers:{Authorization:`Bearer ${token}`}});await route.fulfill({response:r});});
const page=await ctx.newPage(),errors=[];page.on('pageerror',e=>errors.push(e.message));
await mkdir('artifacts/ballet-images',{recursive:true});const results=[];
for(const [name,width,height] of [['pc',1440,1000],['tablet',820,1180],['mobile',390,844]]){
 await page.setViewportSize({width,height});await page.goto(base+'/training/movement');await page.locator('.exercise-choice').first().waitFor();
 for(const mode of ['坐姿','站姿扶椅']){
  await page.locator('.el-radio-button__inner').filter({hasText:mode==='坐姿'?'坐姿':'站姿（扶椅）'}).click();await page.waitForTimeout(150);
  const count=await page.locator('.exercise-choice').count();assert.equal(count,mode==='坐姿'?4:5);
  for(let i=0;i<count;i++){await page.locator('.exercise-choice').nth(i).click();await page.locator('.demo-diagram img').evaluate(img=>img.decode());assert.ok(await page.locator('.demo-diagram img').getAttribute('src'));}
  results.push({name,mode,images:count});
 }
 assert.equal(await page.evaluate(()=>document.documentElement.scrollWidth>innerWidth),false);
 await page.locator('.movement-detail').scrollIntoViewIfNeeded();await page.screenshot({path:`artifacts/ballet-images/${base.startsWith('https')?'live':'local'}-${name}.png`,fullPage:true});
}
await page.setViewportSize({width:1440,height:1000});await page.goto(base+'/training/movement?patientId=browser-qa&selftest=1');await page.getByRole('button',{name:'开始训练',exact:true}).click();await page.locator('.task-demo-figure img').waitFor();await page.locator('.task-demo-figure img').evaluate(img=>img.decode());
await page.screenshot({path:`artifacts/ballet-images/${base.startsWith('https')?'live':'local'}-training.png`,fullPage:true});assert.deepEqual(errors,[]);
await writeFile('artifacts/ballet-images/'+(base.startsWith('https')?'live':'local')+'-results.json',JSON.stringify({base,results,trainingImage:true,errors,api:'isolated QA API, no production data'},null,2));
await browser.close();console.log(JSON.stringify(results));

