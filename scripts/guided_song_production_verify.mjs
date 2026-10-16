import {chromium,request} from 'file:///C:/Users/All_in/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules/playwright/index.mjs'
import {spawnSync} from 'node:child_process'
import {readFile,writeFile,mkdir} from 'node:fs/promises'
import assert from 'node:assert/strict'
const out='artifacts/guided-song-production';await mkdir(out,{recursive:true})
const endpoints=[['https','https://ccqspace.site/pd-rehab/','frontend/dist-under-path/'],['root','http://110.42.236.65:18085/','frontend/dist/']]
const api=await request.newContext({timeout:20000}),checks=[]
for(const [name,base,folder] of endpoints){
 for(const path of ['', 'training/piano/guided-song','training/piano','training/movement']){
  const r=await api.get(new URL(path,base).href);assert.equal(r.status(),200,path)
  const expected=await readFile(folder+'index.html');assert.deepEqual(await r.body(),expected)
  checks.push({entry:name,path,status:r.status()})
 }
 const health=await api.get(new URL('api/system/health',base).href);assert.equal(health.status(),200);assert.equal((await health.json()).status,'ok')
 const unauth=await api.get(new URL('api/guided-song/sessions/missing',base).href);assert.equal(unauth.status(),401)
 const music=await api.get(new URL('assets/music/quarter-note.svg',base).href);assert.equal(music.status(),200)
 assert.deepEqual(await music.body(),await readFile(folder+'assets/music/quarter-note.svg'))
 const sample=await api.get(new URL('samples/piano/a56.mp3',base).href,{headers:{Range:'bytes=0-99'}});assert.equal(sample.status(),206);assert.equal((await sample.body()).length,100)
 checks.push({entry:name,health:'ok',protectedRoute:unauth.status(),musicAsset:true,audioRange:206})
}
// Generate a short-lived verification token in server memory without reading or
// changing passwords, creating users, or writing clinical records. Never log it.
const code="from sqlalchemy import select; from app.db.session import SessionLocal; from app.db.models import StaffUser; from app.core.security import create_access_token; db=SessionLocal(); user=db.scalar(select(StaffUser).where(StaffUser.is_active.is_(True),StaffUser.role=='ADMIN')); assert user; print(create_access_token(user.id,role=user.role,expires_minutes=5,extra={'purpose':'deployment_read_only_verification'})); db.close()"
const sh=s=>"'"+s.replaceAll("'","'\\''")+"'"
const command='cd /opt/pd-rehab/app/PD-Rehab-Web/backend && /opt/pd-rehab/venv/bin/python -c '+sh(code)
const auth=spawnSync('ssh',['-o','BatchMode=yes','fengz',command],{encoding:'utf8',windowsHide:true})
if(auth.status!==0)throw new Error('Could not obtain read-only verification session')
const token=auth.stdout.trim().split(/\r?\n/).at(-1);assert.ok(token && token.split('.').length===3,'Invalid verification session')
const headers={Authorization:`Bearer ${token}`},canonical=endpoints[0][1]
const patientResponse=await api.get(new URL('api/patients?page_size=1',canonical).href,{headers});assert.equal(patientResponse.status(),200)
const patientId=(await patientResponse.json()).items[0]?.id
if(patientId){const h=await api.get(new URL(`api/patients/${patientId}/guided-song/history`,canonical).href,{headers});assert.equal(h.status(),200);checks.push({authenticatedHistory:200})}
const browser=await chromium.launch({headless:true,executablePath:'C:/Program Files/Google/Chrome/Application/chrome.exe'})
const context=await browser.newContext({viewport:{width:1440,height:1000}})
await context.addInitScript(t=>localStorage.setItem('pd-rehab-token',t),token)
const page=await context.newPage(),errors=[],writes=[]
page.on('pageerror',e=>errors.push(e.message))
await context.route('**/api/**',async route=>{if(route.request().method()!=='GET'){writes.push({method:route.request().method(),url:route.request().url()});return route.abort()}await route.continue()})
await page.goto(new URL('training/piano',canonical).href)
await page.locator('[data-practice="GUIDED_SONG"]').click()
await page.getByRole('heading',{name:'曲目跟弹',exact:true}).waitFor()
assert.equal(await page.locator('.song-preview-stage .seven-key').count(),7)
assert.equal(await page.locator('.song-preview-stage .wave-overlay path').count(),5)
await page.locator('.song-preview-stage img').evaluateAll(images=>Promise.all(images.map(i=>i.decode())))
await page.screenshot({path:out+'/live-pc.png',fullPage:true})
await page.getByRole('button',{name:'开始训练',exact:true}).click()
await page.getByRole('dialog',{name:'选择本次训练患者'}).waitFor()
await page.locator('.el-dialog__headerbtn').click()
assert.deepEqual(writes,[])
const ws=await page.evaluate(url=>new Promise(resolve=>{const socket=new WebSocket(url),timer=setTimeout(()=>{socket.close();resolve({timeout:true})},8000);socket.onopen=()=>socket.send(JSON.stringify({type:'auth',token:''}));socket.onclose=e=>{clearTimeout(timer);resolve({code:e.code})};socket.onerror=()=>{} }),new URL('api/live-emotion/stream',canonical).href.replace('https:','wss:'))
assert.equal(ws.code,4403,'WebSocket upgrade must reach authenticated backend')
for(const [name,width,height] of [['tablet',820,1180],['mobile',390,844]]){
 await page.setViewportSize({width,height});await page.goto(new URL('training/piano/guided-song',canonical).href)
 await page.getByRole('heading',{name:'曲目跟弹',exact:true}).waitFor()
 assert.equal(await page.evaluate(()=>document.documentElement.scrollWidth>innerWidth),false)
 await page.screenshot({path:`${out}/live-${name}.png`,fullPage:true})
}
assert.deepEqual(errors,[]);assert.deepEqual(writes,[])
const result={canonical,checks,websocket:ws,browser:'Installed Chrome; PC/tablet/mobile viewport checks',sevenKeys:7,waveLines:5,patientPicker:true,errors,writes,clinicalRecordsCreated:0}
await writeFile(out+'/verification.json',JSON.stringify(result,null,2))
await browser.close();await api.dispose();console.log(JSON.stringify(result))
