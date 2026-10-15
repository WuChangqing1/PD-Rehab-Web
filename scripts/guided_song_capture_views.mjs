import {chromium} from 'file:///C:/Users/All_in/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules/playwright/index.mjs'
import assert from 'node:assert/strict'
const b=await chromium.launch({headless:true,executablePath:'C:/Program Files/Google/Chrome/Application/chrome.exe'}),c=await b.newContext({viewport:{width:1440,height:1000}})
const l=await c.request.post('http://127.0.0.1:8013/api/auth/login',{data:{username:'browserqa',password:'browser-qa-only'}}),t=(await l.json()).access_token
await c.addInitScript(t=>localStorage.setItem('pd-rehab-token',t),t)
const p=await c.newPage(),out='artifacts/guided-song',errors=[];p.on('pageerror',e=>errors.push(e.message))
await p.goto('http://127.0.0.1:5175/training/piano/guided-song?patientId=browser-qa&selftest=1');await p.locator('.song-history-row').filter({hasText:'已完成'}).first().click();await p.locator('.song-result audio').waitFor();await p.screenshot({path:out+'/pc-result.png',fullPage:true});await p.locator('summary').click();await p.locator('.song-result details').screenshot({path:out+'/pc-note-records.png'})
for(const [name,width,height] of [['pc',1440,1000],['tablet',820,1180],['mobile',390,844],['mobile-landscape',844,390]]){await p.setViewportSize({width,height});await p.reload();await p.getByRole('heading',{name:'曲目跟弹',exact:true}).waitFor();await p.screenshot({path:`${out}/${name}-config.png`,fullPage:true});assert.equal(await p.evaluate(()=>document.documentElement.scrollWidth>innerWidth),false)}
assert.deepEqual(errors,[]);await b.close();console.log('Refreshed layout and per-note detail screenshots; no overflow or page errors')
