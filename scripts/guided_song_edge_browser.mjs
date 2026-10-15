import {chromium} from 'file:///C:/Users/All_in/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules/playwright/index.mjs'
import {writeFile} from 'node:fs/promises';import assert from 'node:assert/strict'
const browser=await chromium.launch({headless:true,executablePath:'C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe'})
const ctx=await browser.newContext({viewport:{width:1440,height:900}}),api='http://127.0.0.1:8013/api'
const login=await ctx.request.post(api+'/auth/login',{data:{username:'browserqa',password:'browser-qa-only'}}),token=(await login.json()).access_token,headers={Authorization:`Bearer ${token}`}
await ctx.addInitScript(t=>localStorage.setItem('pd-rehab-token',t),token)
const page=await ctx.newPage(),errors=[];page.on('pageerror',e=>errors.push(e.message))
await page.goto('http://127.0.0.1:5175/training/piano/guided-song?patientId=browser-second&selftest=1')
await page.getByRole('button',{name:/中级/}).click();await page.getByRole('button',{name:'开始训练',exact:true}).click()
await page.locator('[data-state="SEGMENT_1_PLAY"]').waitFor({timeout:30000})
await page.keyboard.press('a');assert.equal(await page.locator('.seven-key.is-target').getAttribute('data-key'),'1')
await ctx.setOffline(true)
for(let i=0;i<13;i++)await page.getByRole('button',{name:'跳过当前音符',exact:true}).click()
await page.getByText('暂时无法保存第一段，请点击重试。',{exact:true}).waitFor()
await page.screenshot({path:'artifacts/guided-song/edge-network-failure.png'})
await ctx.setOffline(false);await page.getByRole('button',{name:'重试保存并继续'}).click()
await page.locator('[data-state="SEGMENT_2_PLAY"]').waitFor({timeout:30000})
const keys=['a','s','d','f','g','h','j']
for(let i=0;i<18;i++){const index=Number(await page.locator('.seven-key.is-target').getAttribute('data-key'));await page.keyboard.press(keys[index])}
await page.locator('.song-result audio').waitFor({timeout:30000})
const normal=(await(await ctx.request.get(api+'/patients/browser-second/guided-song/history',{headers})).json()).items[0]
assert.equal(normal.status,'COMPLETED');assert.equal(normal.metrics.skip_count,13);assert.equal(normal.metrics.completed_notes,19);assert.equal(normal.segment_2_bpm,60)
await page.screenshot({path:'artifacts/guided-song/edge-recovered-result.png',fullPage:true})
// Reload and read protected audio from the server, without any in-memory render.
await page.reload();await page.locator('.song-history-row').first().click();await page.locator('.song-result audio').waitFor()
assert.ok(await page.locator('audio').evaluate(e=>e.src.startsWith('blob:')))
await page.goto('http://127.0.0.1:5175/training/piano/guided-song?patientId=browser-second&selftest=1')
await page.locator('.song-consent input').first().check();await page.locator('.song-notice input').check()
await page.getByRole('button',{name:'开始训练',exact:true}).click()
await page.locator('[data-state="SEGMENT_1_PLAY"]').waitFor({timeout:30000})
for(let i=0;i<14;i++)await page.getByRole('button',{name:'跳过当前音符',exact:true}).click()
await page.locator('[data-state="SEGMENT_2_DEMO"]').waitFor()
assert.ok(await page.locator('.song-tempo').innerText().then(t=>t.includes('80 BPM')))
await page.screenshot({path:'artifacts/guided-song/edge-simulation-80bpm.png'})
const cancelled=page.waitForResponse(r=>r.url().endsWith('/cancel')&&r.request().method()==='POST');await page.getByRole('button',{name:'结束训练',exact:true}).click();await cancelled;await page.locator('.song-page').waitFor()
const sim=(await(await ctx.request.get(api+'/patients/browser-second/guided-song/history',{headers})).json()).items[0]
assert.equal(sim.status,'CANCELLED');assert.equal(sim.emotion_source,'SIMULATED');assert.equal(sim.input_source,'SYNTHETIC_SELFTEST')
assert.equal(sim.difficulty_adjustment.trigger_source,'SIMULATED');assert.equal(sim.segment_2_bpm,80)
assert.deepEqual(errors,[])
await writeFile('artifacts/guided-song/edge-results.json',JSON.stringify({browser:'Installed Microsoft Edge',networkRecovery:normal,simulation:sim,errors},null,2))
await browser.close();console.log(JSON.stringify({networkRecovery:'passed',historyAudio:'passed',simulation:'60 -> 80 only at boundary, explicit selftest',errors}))
