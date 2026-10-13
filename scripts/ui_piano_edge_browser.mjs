// Actual Chromium interactions against scripts/ui_piano_test_server.py only.
import { chromium } from 'file:///C:/Users/All_in/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules/playwright/index.mjs'
import assert from 'node:assert/strict'
import { writeFile } from 'node:fs/promises'
const base='http://127.0.0.1:5175',api='http://127.0.0.1:8013/api',out='artifacts/screenshots'
const browser=await chromium.launch({headless:true,executablePath:'C:/Program Files/Google/Chrome/Application/chrome.exe'})
const context=await browser.newContext({viewport:{width:1440,height:900}})
const login=await context.request.post(api+'/auth/login',{data:{username:'browserqa',password:'browser-qa-only'}})
assert.equal(login.status(),200)
const token=(await login.json()).access_token,headers={Authorization:`Bearer ${token}`}
await context.addInitScript(t=>{if(location.origin==='http://127.0.0.1:5175') localStorage.setItem('pd-rehab-token',t)},token)
const checks=[],errors=[]
context.on('page',p=>p.on('pageerror',e=>errors.push(e.message)))
let page=await context.newPage()
async function total(id='browser-qa') {const response=await context.request.get(api+`/patients/${id}/piano/history`,{headers});return (await response.json()).total}
const initial=await total(),secondInitial=await total('browser-second')
const state=()=>page.evaluate(()=>{
  let c=document.querySelector('.piano-workspace')?.__vueParentComponent
  while(c&&c.type.__name!=='PianoTrainingPage') c=c.parent
  const r=c?.setupState.runner
  return {phase:c?.setupState.startState.phase,error:c?.setupState.startState.error,state:r?.state.value,cues:r?.cues.value,now:r?.nowMs.value,presses:r?.presses.value,pressed:[...(r?.pressedKeys.value??[])]}
})
async function open(path='/training/piano?patientId=browser-qa&selftest=1') {await page.goto(base+path);await page.locator('.practice-start').waitFor();await page.waitForTimeout(350)}
async function start(id) {
  await open();await page.locator(`[data-practice="${id}"]`).click()
  await page.clock.install()
  await page.getByRole('button',{name:'开始训练',exact:true}).click()
  await page.locator('.training-countdown__number').filter({hasText:'3'}).waitFor()
  await page.locator('.focus-shell').waitFor()
  await page.clock.pauseAt(new Date(Date.now()+100))
}
async function discard() {
  await page.clock.resume()
  await page.getByRole('button',{name:'返回康复训练',exact:true}).click()
  await page.getByRole('button',{name:'放弃并离开',exact:true}).click()
  await page.waitForURL(url=>url.pathname==='/training')
}
try {
  // Patientless selection preserves the selected recipe, and switching in
  // countdown verifies a new identity without creating a record for either.
  await open('/training/piano?selftest=1')
  await page.locator('[data-practice="HOLD_RELEASE"]').click()
  await page.getByRole('button',{name:'开始训练',exact:true}).click()
  const picker=page.getByRole('dialog',{name:'选择本次训练患者'})
  await picker.locator('.el-table__row').filter({hasText:'browser-qa'}).getByRole('button',{name:'选择',exact:true}).click()
  const gate=page.getByRole('dialog',{name:'准备训练'})
  await page.locator('.training-countdown__number').filter({hasText:'3'}).waitFor()
  assert.ok((await gate.innerText()).includes('长短音控制'))
  assert.ok((await gate.innerText()).includes('browser-qa'))
  await gate.getByRole('button',{name:'更换患者'}).click()
  await picker.locator('.el-table__row').filter({hasText:'browser-second'}).getByRole('button',{name:'选择',exact:true}).click()
  await page.locator('.training-countdown__number').filter({hasText:'3'}).waitFor()
  assert.ok((await gate.innerText()).includes('browser-second'))
  await gate.getByRole('button',{name:'取消启动'}).click()
  assert.equal(await total(),initial);assert.equal(await total('browser-second'),secondInitial)
  checks.push('patientless selection / countdown patient switch / cancel without writes')

  // A patient verification network failure must not launch; a subsequent click
  // after network recovery reaches the normal countdown.
  await open()
  await page.route('**/api/patients/browser-qa',route=>route.abort('failed'))
  await page.getByRole('button',{name:'开始训练',exact:true}).click()
  await page.waitForFunction(()=>{
    let c=document.querySelector('.piano-workspace')?.__vueParentComponent
    while(c&&c.type.__name!=='PianoTrainingPage') c=c.parent
    return !!c?.setupState.startState.error
  })
  assert.equal((await state()).state,'IDLE')
  assert.equal(await total(),initial)
  await page.unroute('**/api/patients/browser-qa')
  await page.getByRole('button',{name:'开始训练',exact:true}).click()
  await page.locator('.training-countdown__number').filter({hasText:'3'}).waitFor()
  await page.getByRole('button',{name:'取消启动'}).click()
  checks.push('verification network failure and retry without writes')

  // Historical result detail is read from the real saved record, including MAE
  // and the synthetic provenance warning.
  await page.goto(base+'/follow-up?patientId=browser-qa')
  await page.locator('.el-table__row').filter({hasText:'节奏变速'}).getByRole('button',{name:'查看结果',exact:true}).click()
  const detail=page.getByRole('dialog',{name:'钢琴训练结果'})
  await detail.waitFor()
  assert.ok((await detail.innerText()).includes('browser-qa'))
  assert.ok((await detail.innerText()).includes('不是真人测量值'))
  assert.ok(!(await detail.locator('.el-table__row').filter({hasText:'节拍绝对误差'}).first().innerText()).includes('暂无数据'))
  await page.screenshot({path:out+'/piano_history_after.png'})
  checks.push('history real detail / measured MAE / source warning / identity')

  await page.close()
  const mobile=await browser.newContext({viewport:{width:390,height:844},isMobile:true,hasTouch:true})
  await mobile.addInitScript(t=>{if(location.origin==='http://127.0.0.1:5175') localStorage.setItem('pd-rehab-token',t)},token)
  mobile.on('page',p=>p.on('pageerror',e=>errors.push(e.message)))
  page=await mobile.newPage()
  const cdp=await mobile.newCDPSession(page)
  async function points() {
    await page.locator('.touch-targets').scrollIntoViewIfNeeded()
    return page.locator('.touch-key').evaluateAll(elements=>elements.map((e,i)=>{const r=e.getBoundingClientRect();return {x:r.x+r.width/2,y:r.y+r.height/2,id:i+1}}))
  }
  const touch=(type,touchPoints)=>cdp.send('Input.dispatchTouchEvent',{type,touchPoints})
  await start('BIMANUAL_SYNC')
  let s=await state(),cue=s.cues[0]
  await page.clock.runFor(Math.max(0,Math.ceil(cue.targetMs-s.now)))
  await touch('touchStart',await points())
  assert.equal((await state()).pressed.length,2)
  await page.clock.runFor(80)
  await touch('touchEnd',[])
  s=await state()
  assert.equal(s.pressed.length,0)
  assert.equal(s.presses.length,2)
  assert.ok(s.presses.every(p=>Math.abs(p.relativeUpMs-p.relativeDownMs-80)<1))
  await page.clock.runFor(300)
  await page.screenshot({path:out+'/mobile_piano.png'})
  await page.setViewportSize({width:375,height:812})
  const next=(await state()).cues[1]
  await page.clock.runFor(Math.max(0,Math.ceil(next.targetMs-(await state()).now)))
  await touch('touchStart',await points())
  await touch('touchCancel',[])
  s=await state();assert.equal(s.pressed.length,0)
  assert.ok(s.presses.slice(-2).every(p=>p.relativeUpMs===null))
  assert.equal(await page.evaluate(()=>document.documentElement.scrollWidth>innerWidth),false)
  await page.screenshot({path:out+'/mobile_piano_375.png'})
  await discard();assert.equal(await total(),initial)
  checks.push('390 / 375 mobile two-finger simultaneous input, physical releases, cancellation, protected exit')
  await page.close();page=await mobile.newPage()
  const holdCdp=await mobile.newCDPSession(page)
  await start('HOLD_RELEASE')
  s=await state();cue=s.cues.find(c=>c.targetHoldMs===750)
  await page.clock.runFor(Math.max(0,Math.ceil(cue.targetMs-s.now)))
  await page.locator('.touch-targets').scrollIntoViewIfNeeded()
  const key=await page.locator('.touch-key').last().boundingBox()
  await holdCdp.send('Input.dispatchTouchEvent',{type:'touchStart',touchPoints:[{x:key.x+key.width/2,y:key.y+key.height/2,id:1}]})
  await page.clock.runFor(750)
  await holdCdp.send('Input.dispatchTouchEvent',{type:'touchEnd',touchPoints:[]})
  s=await state();const press=s.presses.at(-1)
  assert.equal(Math.round(press.relativeUpMs-press.relativeDownMs),750)
  await page.screenshot({path:out+'/mobile_hold_after.png'})
  await discard();assert.equal(await total(),initial)
  checks.push('mobile 750ms hold/release and discard without writes')
  await mobile.close()
  page=await context.newPage()
  await start('HOLD_RELEASE')
  s=await state();cue=s.cues[0]
  await page.clock.runFor(Math.max(0,Math.ceil(cue.targetMs-s.now)))
  await page.keyboard.down(cue.binding.code)
  await page.clock.runFor(250)
  await page.keyboard.up(cue.binding.code)
  await page.clock.runFor(400)
  await page.clock.resume()
  await page.getByRole('button',{name:'结束本轮',exact:true}).click()
  await page.getByRole('button',{name:'保存本轮结果',exact:true}).waitFor()
  // First create fails before reaching the server: no row and no success UI.
  await page.route('**/api/patients/browser-qa/piano/sessions',r=>r.abort('failed'),{times:1})
  await page.getByRole('button',{name:'保存本轮结果',exact:true}).click()
  await page.waitForTimeout(400)
  assert.equal(await total(),initial)
  assert.equal(await page.getByRole('button',{name:'返回练习，继续训练',exact:true}).count(),0)
  // Second save stores events then loses the upload response. Retrying reuses
  // the session and event indices. A lost complete response is recovered by GET.
  await page.route('**/api/piano/sessions/*/events/batch',async r=>{await r.fetch();await r.abort('failed')},{times:1})
  await page.getByRole('button',{name:'保存本轮结果',exact:true}).click()
  await page.waitForTimeout(500)
  assert.equal(await total(),initial+1)
  await page.route('**/api/piano/sessions/*/complete',async r=>{await r.fetch();await r.abort('failed')},{times:1})
  await page.getByRole('button',{name:'保存本轮结果',exact:true}).click()
  await page.getByRole('button',{name:'返回练习，继续训练',exact:true}).waitFor()
  assert.equal(await total(),initial+1)
  const history=await (await context.request.get(api+'/patients/browser-qa/piano/history',{headers})).json()
  const saved=await (await context.request.get(api+`/piano/sessions/${history.items[0].id}`,{headers})).json()
  assert.equal(saved.difficulty_before_json.completion_status,'INTERRUPTED')
  assert.equal(saved.input_source,'SYNTHETIC_SELFTEST')
  assert.equal(new Set(saved.events.map(e=>e.event_index)).size,saved.events.length)
  await page.screenshot({path:out+'/piano_retry_after.png'})
  checks.push('create failure / upload response loss / retry same session and events / complete response recovery / interrupted status')
  assert.deepEqual(errors,[])
  await writeFile('artifacts/ui_piano_edge_results.json',JSON.stringify({checks,errors,initialSessions:initial,finalSessions:await total()},null,2))
  console.log(JSON.stringify({checks,errors}))
} catch(error) {
  console.error(error)
  console.error((await page.locator('body').innerText()).slice(-5000))
  await page.screenshot({path:out+'/edge_failure.png'})
  process.exitCode=1
} finally {await browser.close()}
