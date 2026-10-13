// Read-only UI captures; uses the disposable browser QA API, no production DB.
import { chromium } from 'file:///C:/Users/All_in/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules/playwright/index.mjs'
import assert from 'node:assert/strict'
import { writeFile } from 'node:fs/promises'
const base='http://127.0.0.1:5175',out='artifacts/screenshots'
const browser=await chromium.launch({headless:true,executablePath:'C:/Program Files/Google/Chrome/Application/chrome.exe'})
try {
  const context=await browser.newContext({viewport:{width:2048,height:1092}})
  const response=await context.request.post('http://127.0.0.1:8013/api/auth/login',{data:{username:'browserqa',password:'browser-qa-only'}})
  const token=(await response.json()).access_token
  await context.addInitScript(t=>{if(location.origin==='http://127.0.0.1:5175') localStorage.setItem('pd-rehab-token',t)},token)
  const page=await context.newPage()
  async function capture(path,name,fullPage=false) {
    await page.goto(base+path);await page.locator('.pd-page').waitFor();await page.waitForTimeout(450)
    await page.screenshot({path:`${out}/${name}.png`,fullPage})
  }
  await capture('/dashboard','dashboard_after_2048')
  await page.setViewportSize({width:1440,height:900})
  await capture('/dashboard','dashboard_after')
  await capture('/training','training_after')
  await capture('/training/piano','piano_catalog_after',true)
  const alignment=[]
  for(const [width,height] of [[1440,900],[1366,768],[1024,768],[768,1024],[430,932],[390,844],[375,812]]) {
    await page.setViewportSize({width,height})
    await capture('/training/piano',`piano_catalog_${width}x${height}`)
    const layout=await page.evaluate(()=>({overflow:document.documentElement.scrollWidth>innerWidth,cards:[...document.querySelectorAll('[data-practice]')].map(e=>{
      const r=e.getBoundingClientRect()
      return {y:r.y,height:r.height,cover:e.querySelector('svg').getBoundingClientRect().height,title:e.querySelector('strong').getBoundingClientRect().top,footer:e.querySelector('.practice-footer').getBoundingClientRect().bottom}
    })}))
    assert.equal(layout.overflow,false)
    assert.equal(layout.cards.length,13)
    const rows=new Map()
    for(const card of layout.cards) rows.set(Math.round(card.y),[...(rows.get(Math.round(card.y))??[]),card])
    for(const row of rows.values()) for(const key of ['height','cover','title','footer']) assert.ok(Math.max(...row.map(c=>c[key]))-Math.min(...row.map(c=>c[key]))<=2,`${width} ${key}`)
    alignment.push({viewport:`${width}x${height}`,cards:13,overflow:false,coverTitleFooterAligned:true})
  }
  await page.setViewportSize({width:390,height:844})
  await capture('/dashboard','mobile_dashboard')
  await capture('/training','mobile_training')
  await page.setViewportSize({width:1440,height:900})
  await page.goto(base+'/training/piano?patientId=browser-qa&selftest=1')
  await page.locator('.practice-start').waitFor()
  await page.locator('[data-practice="TEMPO_RAMP"]').click()
  await page.getByRole('button',{name:'开始训练',exact:true}).click()
  await page.locator('.focus-shell').waitFor()
  await page.waitForTimeout(800)
  const runVisibility=await page.locator('.cue-instruction').evaluate(e=>{const r=e.getBoundingClientRect();return {top:r.top,bottom:r.bottom}})
  assert.ok(runVisibility.top>=76 && runVisibility.bottom<900,'running instruction stays in view when targets change')
  await page.screenshot({path:`${out}/piano_run_after.png`})
  await writeFile('artifacts/ui_piano_capture_results.json',JSON.stringify({alignment},null,2))
  // Closing the disposable page discards this unsaved local round; no session
  // creation request is made before an explicit Save.
} finally {await browser.close()}
console.log('Read-only screenshots captured')
