// Real Chromium -> Vite -> real FastAPI -> isolated in-memory SQLite.
// Scripted input always declares SYNTHETIC_SELFTEST; no clinical DB is opened.
import { chromium } from 'file:///C:/Users/All_in/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules/playwright/index.mjs'
import {mkdir,writeFile} from 'node:fs/promises'
import assert from 'node:assert/strict'
const base='http://127.0.0.1:5175', api='http://127.0.0.1:8013/api'
const out='artifacts/screenshots'
await mkdir(out,{recursive:true})
const browser=await chromium.launch({headless:true,executablePath:'C:/Program Files/Google/Chrome/Application/chrome.exe'})
const context=await browser.newContext({viewport:{width:1440,height:900}})
const errors=[],posts=[],results=[]
context.on('page',page=>page.on('pageerror',error=>errors.push(error.message)))
context.on('request',request=>{if(request.method()==='POST') posts.push({url:request.url(),body:request.postDataJSON()})})
context.on('response',async response=>{if(response.url().includes('/api/')&&response.status()>=400) console.error(response.status(),response.url(),await response.text())})
let page=await context.newPage()
page.on('console',msg=>{if(msg.type()==='error') console.error(msg.text())})
process.on('uncaughtException',async error=>{console.error(error);try {console.error((await page.locator('body').innerText()).slice(-5000));await page.screenshot({path:out+'/failure.png'})}catch{}await browser.close();process.exit(1)})
async function open(path) {await page.goto(base+path);await page.locator('.pd-page').waitFor()}
const runner=()=>page.evaluate(()=>{
  const element=document.querySelector('.piano-workspace')
  let component=element?.__vueParentComponent
  while(component&&component.type.__name!=='PianoTrainingPage') component=component.parent
  const r=component?.setupState.runner
  return r?{state:r.state.value,now:r.nowMs.value,elapsed:r.elapsedMs.value,cues:r.cues.value,events:r.events.value,pressed:[...r.pressedKeys.value],unlocked:r.unlocked.value}:null
})
await page.goto(base+'/login')
await page.getByLabel('用户名').fill('browserqa')
await page.getByLabel('密码',{exact:true}).fill('browser-qa-only')
await page.getByRole('button',{name:'登录',exact:true}).click()
await page.waitForURL('**/dashboard')
const token=await page.evaluate(()=>localStorage.getItem('pd-rehab-token'))
const headers={Authorization:`Bearer ${token}`}
async function list() {const r=await context.request.get(api+'/patients/browser-qa/piano/history',{headers});assert.equal(r.status(),200);return r.json()}
await page.screenshot({path:out+'/dashboard_after.png'})
await open('/training')
await page.screenshot({path:out+'/training_after.png'})
await open('/training/piano?selftest=1')
assert.equal(await page.locator('[data-practice]').count(),13)
await page.screenshot({path:out+'/piano_catalog_after.png',fullPage:true})
for(const [width,height] of [[1440,900],[1366,768],[1024,768],[768,1024],[430,932],[390,844],[375,812]]) {
  await page.setViewportSize({width,height})
  const layout=await page.evaluate(()=>{
    const cards=[...document.querySelectorAll('[data-practice]')].map(e=>{const r=e.getBoundingClientRect();return {x:r.x,y:r.y,height:r.height,cover:e.querySelector('svg').getBoundingClientRect().height,footer:e.querySelector('.practice-footer').getBoundingClientRect().bottom}})
    return {overflow:document.documentElement.scrollWidth>innerWidth,cards}
  })
  assert.equal(layout.overflow,false,`overflow at ${width}`)
  const rows=new Map()
  for(const c of layout.cards) rows.set(Math.round(c.y),[...(rows.get(Math.round(c.y))??[]),c])
  for(const row of rows.values()) for(const key of ['height','cover','footer']) assert.ok(Math.max(...row.map(c=>c[key]))-Math.min(...row.map(c=>c[key]))<=2,`${key} alignment ${width}`)
  await page.screenshot({path:`${out}/piano_catalog_${width}x${height}.png`})
  results.push({viewport:`${width}x${height}`,overflow:false,alignment:true})
}
await page.setViewportSize({width:1440,height:900})
// No patient: browse all categories, audition, choose, and only Start asks.
await page.locator('[data-practice="TEMPO_RAMP"]').click()
await page.locator('.piano-key.white').first().click()
await page.getByRole('button',{name:'开始训练',exact:true}).click()
await page.getByRole('dialog',{name:'选择本次训练患者'}).waitFor()
assert.equal((await list()).total,0)
await page.getByRole('dialog',{name:'选择本次训练患者'}).locator('.el-dialog__headerbtn').click()
// Cancellation at every countdown value: zero POSTs / zero stored sessions.
await open('/training/piano?patientId=browser-qa&selftest=1')
for(const remaining of [3,2,1]) {
  console.log('Cancel at',remaining)
  await page.getByRole('button',{name:'开始训练',exact:true}).click()
  await page.locator('.training-countdown__number').filter({hasText:String(remaining)}).waitFor()
  await page.getByRole('button',{name:'取消启动'}).click()
  assert.equal((await list()).total,0)
  await page.getByRole('dialog',{name:'准备训练'}).waitFor({state:'hidden'})
  await page.waitForTimeout(300)
}
// Five complete protocols. Clock drives deterministic input through actual DOM.
for(const id of ['TEMPO_RAMP','HOLD_RELEASE','BIMANUAL_OFFSET','REVERSE_SEQUENCE','GO_NO_GO']) {
  console.log('Playing',id)
  await open('/training/piano?patientId=browser-qa&selftest=1')
  await page.locator(`[data-practice="${id}"]`).click()
  await page.getByText('高级设置（医生）',{exact:true}).click()
  const duration=page.locator('.el-form-item').filter({has:page.getByText('本轮时长',{exact:true})}).locator('input')
  await duration.fill('20');await duration.press('Tab')
  await page.clock.install()
  await page.getByRole('button',{name:'开始训练',exact:true}).click()
  await page.locator('.training-countdown__number').filter({hasText:'3'}).waitFor()
  await page.locator('.focus-shell').waitFor({timeout:10000})
  assert.equal((await list()).total,results.filter(r=>r.recipe).length)
  const initial=await runner();assert.equal(initial.state,'RUNNING');assert.equal(initial.unlocked,true)
  await page.clock.pauseAt(new Date(Date.now()+100))
  const stream=(await runner()).cues
  for(const cue of stream) {
    const state=await runner()
    const wait=Math.max(0,Math.ceil(cue.targetMs-state.now))
    if(wait) await page.clock.runFor(wait)
    if(cue.isPrompt||cue.cueType==='NO_GO') continue
    await page.keyboard.down(cue.binding.code)
    await page.clock.runFor(cue.targetHoldMs??60)
    await page.keyboard.up(cue.binding.code)
  }
  await page.clock.runFor(2000)
  const finished=await runner();assert.equal(finished.state,'FINISHED')
  assert.equal(finished.pressed.length,0)
  if(id==='HOLD_RELEASE') assert.ok(finished.events.some(e=>e.hold_duration_ms>=740))
  if(id==='GO_NO_GO') assert.ok(finished.events.filter(e=>e.cue_type==='NO_GO').every(e=>e.is_correct&&!e.is_missed))
  if(id==='REVERSE_SEQUENCE') assert.ok(finished.events.some(e=>e.is_prompt))
  await page.screenshot({path:`${out}/piano_${id.toLowerCase()}_result.png`})
  await page.clock.resume()
  const completed=page.waitForResponse(r=>r.url().endsWith('/complete'))
  await page.getByRole('button',{name:'保存本轮结果'}).click()
  console.log('Save clicked',posts.map(p=>p.url))
  const response=await completed
  assert.equal(response.status(),200,await response.text())
  const stored=await response.json()
  assert.equal(stored.recipe_id,id)
  assert.equal(stored.input_source,'SYNTHETIC_SELFTEST')
  const detailResponse=await context.request.get(api+`/piano/sessions/${stored.id}`,{headers})
  assert.equal(detailResponse.status(),200)
  const detail=await detailResponse.json()
  assert.ok(detail.events.length>0)
  assert.ok(detail.difficulty_before_json.raw_presses.length>0)
  results.push({recipe:id,id:stored.id,events:detail.events.length,metrics:detail.difficulty_before_json.server_metrics})
  // New page resets the test clock and task lifecycle before the next exercise.
  await page.close()
  const replacement=await context.newPage()
  // Reassign the active page while retaining auth and isolated DB.
  page=replacement
}
assert.equal((await list()).total,5)
assert.deepEqual(errors,[])
await writeFile('artifacts/ui_piano_browser_results.json',JSON.stringify({results,errors,posts:posts.map(p=>({url:p.url,recipe:p.body?.recipe_id}))},null,2))
await browser.close()
console.log(JSON.stringify({checks:results.length,errors:errors.length,storedRecipes:5}))
