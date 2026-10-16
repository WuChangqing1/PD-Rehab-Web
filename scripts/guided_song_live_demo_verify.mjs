// Published production UI; every API call is routed to disposable local QA.
import {chromium} from 'file:///C:/Users/All_in/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules/playwright/index.mjs'
import {mkdir,writeFile} from 'node:fs/promises'
import assert from 'node:assert/strict'
const out='artifacts/guided-song-key-hints-production';await mkdir(out,{recursive:true})
const browser=await chromium.launch({headless:true,executablePath:'C:/Program Files/Google/Chrome/Application/chrome.exe'})
const ctx=await browser.newContext({viewport:{width:1440,height:1000},hasTouch:true})
const login=await ctx.request.post('http://127.0.0.1:8013/api/auth/login',{data:{username:'browserqa',password:'browser-qa-only'}})
assert.equal(login.status(),200)
await ctx.addInitScript(t=>localStorage.setItem('pd-rehab-token',t),(await login.json()).access_token)
let localRequests=0
await ctx.route('**/pd-rehab/api/**',async route=>{
 const u=new URL(route.request().url());localRequests++
 const response=await route.fetch({url:'http://127.0.0.1:8013'+u.pathname.replace(/^\/pd-rehab/,'')+u.search})
 await route.fulfill({response})
})
const page=await ctx.newPage(),errors=[];page.on('pageerror',e=>errors.push(e.message))
await page.goto('https://ccqspace.site/pd-rehab/training/piano/guided-song?patientId=browser-qa&selftest=1')
await page.getByRole('button',{name:'开始训练',exact:true}).click()
await page.locator('.song-immersive[data-state="SEGMENT_1_DEMO"]').waitFor()
await page.locator('.seven-key.is-target').waitFor()
await page.waitForTimeout(1800)
for(const [name,width,height] of [['pc',1440,1000],['tablet',820,1180],['mobile',390,844],['mobile-landscape',844,390]]){
 await page.setViewportSize({width,height})
 assert.deepEqual(await page.locator('.key-letter').allTextContents(),['A','S','D','F','G','H','J'])
 await page.keyboard.down('a');assert.equal(await page.locator('.seven-key.is-pressed').getAttribute('data-key'),'0');await page.keyboard.up('a')
 await page.locator('.seven-key').nth(2).tap();await page.waitForTimeout(250)
 assert.equal((await page.locator('.song-count').innerText()).trim(),'0 / 32')
 assert.equal(await page.evaluate(()=>document.documentElement.scrollWidth>innerWidth),false)
 await page.screenshot({path:`${out}/live-demo-${name}.png`})
}
await page.getByRole('button',{name:'结束训练',exact:true}).click();await page.locator('.song-page').waitFor()
assert.deepEqual(errors,[])
const result={ui:'Published HTTPS production assets',api:'Disposable localhost QA, all production API calls intercepted',productionTrainingWrites:0,localRequests,letters:['A','S','D','F','G','H','J'],rehearsalKeyboardAndTouch:true,scoredProgressAfterRehearsal:0,viewports:4,errors}
await writeFile(out+'/live-demo-verification.json',JSON.stringify(result,null,2))
await browser.close();console.log(JSON.stringify(result))
