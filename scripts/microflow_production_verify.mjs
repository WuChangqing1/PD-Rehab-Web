import {chromium,request} from 'file:///C:/Users/All_in/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules/playwright/index.mjs'
import {spawnSync} from 'node:child_process'
import {readFile,writeFile,mkdir} from 'node:fs/promises'
import assert from 'node:assert/strict'
const out='artifacts/microflow-production';await mkdir(out,{recursive:true})
const base='https://ccqspace.site/pd-rehab/',api=await request.newContext({timeout:20000})
const checks=[]
for(const [url,folder] of [[base,'frontend/dist-under-path/'],['http://110.42.236.65:18085/','frontend/dist/']]){
 const entry=await api.get(url);assert.equal(entry.status(),200)
 assert.deepEqual(await entry.body(),await readFile(folder+'index.html'))
 const health=await api.get(new URL('api/system/health',url).href);assert.equal((await health.json()).status,'ok')
 const status=await(await api.get(new URL('api/system/models',url).href)).json()
 const m=status.models.micro_expression_model
 assert.equal(m.state,'MODEL_NOT_CONFIGURED');assert.equal(m.is_ready,false)
 assert.equal(m.extra.adapter,'microflow_da');assert.equal(m.extra.source_present,true)
 assert.deepEqual(m.extra.labels,['negative','positive','surprise'])
 assert.equal(m.extra.source_sha256,'797b82bb842e505ad464fdb8bba12ac4aa9261a13e46d859cc3891a4866bafa6')
 assert.equal(m.extra.known_source_issue,'TEMPORAL_BRANCH_DISCONNECTED')
 assert.ok(m.extra.missing.includes('checkpoint'));assert.equal(status.mock_mode,false)
 checks.push({url,indexMatches:true,health:'ok',model:m})
}
// Token remains in memory. No password/user/clinical record is changed.
const code="from sqlalchemy import select; from app.db.session import SessionLocal; from app.db.models import StaffUser; from app.core.security import create_access_token; db=SessionLocal(); user=db.scalar(select(StaffUser).where(StaffUser.is_active.is_(True),StaffUser.role=='ADMIN')); assert user; print(create_access_token(user.id,role=user.role,expires_minutes=5,extra={'purpose':'deployment_read_only_verification'})); db.close()"
const sh=s=>"'"+s.replaceAll("'","'\\''")+"'"
const auth=spawnSync('ssh',['-o','BatchMode=yes','fengz','cd /opt/pd-rehab/app/PD-Rehab-Web/backend && /opt/pd-rehab/venv/bin/python -c '+sh(code)],{encoding:'utf8',windowsHide:true})
assert.equal(auth.status,0,'Could not obtain short-lived verification session')
const token=auth.stdout.trim().split(/\r?\n/).at(-1);assert.equal(token.split('.').length,3)
const browser=await chromium.launch({headless:true,executablePath:'C:/Program Files/Google/Chrome/Application/chrome.exe'})
const context=await browser.newContext();await context.addInitScript(t=>localStorage.setItem('pd-rehab-token',t),token)
const writes=[],errors=[]
await context.route('**/api/**',async route=>{
 const r=route.request(),u=new URL(r.url())
 if(r.method()!=='GET'){writes.push(r.url());return route.abort()}
 // Suppress patient lists in screenshots; all model/health/UI checks are live.
 if(u.pathname.endsWith('/patients'))return route.fulfill({json:{items:[],total:0,page:1,page_size:20}})
 await route.continue()
})
const page=await context.newPage();page.on('pageerror',e=>errors.push(e.message))
for(const [name,width,height] of [['pc',1440,1000],['tablet',820,1180],['mobile',390,844]]){
 await page.setViewportSize({width,height});await page.goto(new URL('assessment/micro-expression',base).href)
 await page.getByText('MicroFlow-DA 已接入，等待训练权重',{exact:true}).waitFor()
 assert.equal(await page.evaluate(()=>document.documentElement.scrollWidth>innerWidth),false)
 await page.screenshot({path:`${out}/${name}-pending.png`,fullPage:true})
}
assert.deepEqual(errors,[]);assert.deepEqual(writes,[])
const result={checks,viewports:3,errors,writes,productionModelActivated:false,clinicalRecordsCreated:0,patientListsSuppressed:true}
await writeFile(out+'/verification.json',JSON.stringify(result,null,2))
await browser.close();await api.dispose();console.log(JSON.stringify({checks:checks.length,viewports:3,modelActivated:false,errors,writes}))
