// Public release verification. Authenticated UI browsing is read-only; the
// optional token is loaded from a temporary file and never written to results.
import {chromium} from 'file:///C:/Users/All_in/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules/playwright/index.mjs'
import {readFile,readdir,mkdir,writeFile} from 'node:fs/promises'
import {createHash} from 'node:crypto'
import assert from 'node:assert/strict'
const https='https://ccqspace.site/pd-rehab/',root='http://110.42.236.65:18085/'
const sha=bytes=>createHash('sha256').update(bytes).digest('hex')
const results={sourceRevision:'19dba0f5165b0c06104422437deb0a14654a5ce2',entries:[],assets:[],routes:[],browser:[]}
async function get(url,options={}) {const r=await fetch(url,{signal:AbortSignal.timeout(30000),...options});return {r,bytes:Buffer.from(await r.arrayBuffer())}}
for(const [base,dir] of [[https,'dist-under-path'],[root,'dist']]) {
  const expected=await readFile(`frontend/${dir}/index.html`)
  const {r,bytes}=await get(base+'?release=19dba0f')
  assert.equal(r.status,200);assert.equal(sha(bytes),sha(expected))
  results.entries.push({base,status:r.status,indexSha256:sha(bytes),cache:r.headers.get('cache-control')})
  const files=(await readdir(`frontend/${dir}/assets`)).filter(f=>/\.(js|css)$/.test(f))
  let cursor=0
  await Promise.all(Array.from({length:5},async()=>{
    while(cursor<files.length) {
      const file=files[cursor++]
      const {r,bytes}=await get(base+'assets/'+file)
      assert.equal(r.status,200,file)
      assert.equal(sha(bytes),sha(await readFile(`frontend/${dir}/assets/${file}`)),file)
      results.assets.push({url:base+'assets/'+file,status:r.status,sha256:sha(bytes)})
    }
  }))
}
for(const route of ['login','dashboard','patients','assessment','training','training/piano','training/movement','follow-up']) {
  const {r,bytes}=await get(https+route)
  assert.equal(r.status,200)
  assert.equal(sha(bytes),results.entries[0].indexSha256)
  results.routes.push({route,status:r.status})
}
const health=await get(https+'api/system/health')
assert.equal(health.r.status,200);assert.equal(JSON.parse(health.bytes).status,'ok')
results.health=JSON.parse(health.bytes)
const auth=await get(https+'api/auth/me')
assert.equal(auth.r.status,401);assert.ok(auth.r.headers.get('content-type').includes('application/json'))
results.unauthenticatedStatus=401
const sample=await get(https+'samples/piano/a48.mp3',{headers:{Range:'bytes=0-99'}})
assert.equal(sample.r.status,206);assert.equal(sample.bytes.length,100)
results.audioRangeStatus=206
const browser=await chromium.launch({headless:true,executablePath:'C:/Program Files/Google/Chrome/Application/chrome.exe'})
try {
  await mkdir('artifacts/screenshots/production',{recursive:true})
  const context=await browser.newContext({viewport:{width:1440,height:900}})
  const errors=[],failed=[]
  context.on('page',p=>{p.on('pageerror',e=>errors.push(e.message));p.on('requestfailed',r=>failed.push(r.url()))})
  let page=await context.newPage()
  await page.goto(https+'training/piano')
  await page.waitForURL('**/login**')
  await page.getByLabel('用户名').waitFor()
  assert.equal(await page.evaluate(()=>isSecureContext),true)
  await page.screenshot({path:'artifacts/screenshots/production/login.png'})
  results.browser.push('real HTTPS login redirect and secure context')
  const token=(await readFile('.ui-piano-auth.tmp','utf8')).trim()
  await context.addInitScript(t=>{if(location.origin==='https://ccqspace.site') localStorage.setItem('pd-rehab-token',t)},token)
  const writes=[]
  await context.route('**/pd-rehab/api/**',async route=>{
    if(route.request().method()!=='GET') {writes.push(route.request().url());await route.abort();return}
    await route.continue()
  })
  await page.close();page=await context.newPage()
  await page.goto(https+'training/piano')
  await page.locator('[data-practice]').first().waitFor()
  assert.equal(await page.locator('[data-practice]').count(),13)
  for(const id of ['TEMPO_RAMP','HOLD_RELEASE','BIMANUAL_OFFSET','REVERSE_SEQUENCE','GO_NO_GO']) {
    await page.locator(`[data-practice="${id}"]`).click()
    assert.equal(await page.locator(`[data-practice="${id}"]`).getAttribute('aria-pressed'),'true')
  }
  // No patient is automatically selected; browsing/auditioning produces no POST.
  await page.locator('.piano-key.white').first().click()
  await page.getByRole('button',{name:'开始训练',exact:true}).click()
  const picker=page.getByRole('dialog',{name:'选择本次训练患者'})
  await picker.waitFor()
  await picker.locator('.el-dialog__headerbtn').click()
  await picker.waitFor({state:'hidden'})
  await page.evaluate(()=>{document.getElementById('main-content')?.scrollTo(0,0)})
  await page.waitForTimeout(350)
  await page.screenshot({path:'artifacts/screenshots/production/piano-desktop.png'})
  await page.setViewportSize({width:390,height:844})
  assert.equal(await page.evaluate(()=>document.documentElement.scrollWidth>innerWidth),false)
  await page.screenshot({path:'artifacts/screenshots/production/piano-mobile.png'})
  assert.deepEqual(writes,[]);assert.deepEqual(errors,[]);assert.deepEqual(failed,[])
  results.browser.push('real authenticated API, 13 practices and all five selections, audition, patientless start/cancel, mobile no overflow; zero writes/errors/failed requests')
  results.browserWrites=0;results.pageErrors=errors;results.failedRequests=failed
} finally {await browser.close()}
await writeFile('artifacts/ui_piano_production_results.json',JSON.stringify(results,null,2))
console.log(JSON.stringify({entries:results.entries.length,assets:results.assets.length,routes:results.routes.length,health:'ok',audioRange:206,browser:results.browser}))
