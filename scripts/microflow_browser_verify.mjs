import {chromium} from 'file:///C:/Users/All_in/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules/playwright/index.mjs'
import {mkdir,writeFile} from 'node:fs/promises'
import assert from 'node:assert/strict'
const out='artifacts/microflow';await mkdir(out,{recursive:true})
const browser=await chromium.launch({headless:true,executablePath:'C:/Program Files/Google/Chrome/Application/chrome.exe'})
const ctx=await browser.newContext({viewport:{width:1440,height:1000}})
const api='http://127.0.0.1:8013/api'
const auth=await ctx.request.post(api+'/auth/login',{data:{username:'browserqa',password:'browser-qa-only'}})
assert.equal(auth.status(),200)
const token=(await auth.json()).access_token
await ctx.addInitScript(t=>{localStorage.setItem('pd-rehab-token',t);window.__cameraCalls=0;if(navigator.mediaDevices)navigator.mediaDevices.getUserMedia=async()=>{window.__cameraCalls++;throw new Error('QA camera disabled')}},token)
const status=await(await ctx.request.get(api+'/system/models',{headers:{Authorization:`Bearer ${token}`}})).json()
const model=status.models.micro_expression_model
assert.equal(model.extra.adapter,'microflow_da');assert.equal(model.extra.source_present,true)
assert.equal(model.extra.known_source_issue,'TEMPORAL_BRANCH_DISCONNECTED')
assert.equal(model.is_ready,false);assert.equal(model.state,'MODEL_NOT_CONFIGURED')
assert.deepEqual(model.extra.labels,['negative','positive','surprise'])
const page=await ctx.newPage(),errors=[],writes=[]
page.on('pageerror',e=>errors.push(e.message));page.on('request',r=>{if(r.method()!=='GET'&&r.url().includes('/api/'))writes.push(r.url())})
for(const [name,width,height] of [['pc',1440,1000],['tablet',820,1180],['mobile',390,844]]){
 await page.setViewportSize({width,height})
 await page.goto('http://127.0.0.1:5175/assessment/micro-expression?patientId=browser-qa')
 await page.getByText('MicroFlow-DA 已接入，等待训练权重',{exact:true}).waitFor()
 await page.getByText('准备好后开始检查',{exact:true}).waitFor()
 assert.equal(await page.getByRole('button',{name:'开始检查',exact:true}).isDisabled(),true)
 assert.equal(await page.getByRole('button',{name:'开始分析',exact:true}).isDisabled(),true)
 assert.equal(await page.getByLabel('起始帧',{exact:true}).isDisabled(),true)
 assert.equal(await page.getByLabel('峰值帧',{exact:true}).isDisabled(),true)
 assert.equal(await page.evaluate(()=>document.documentElement.scrollWidth>innerWidth),false)
 assert.equal(await page.evaluate(()=>window.__cameraCalls),0)
 await page.screenshot({path:`${out}/${name}-pending.png`,fullPage:true})
}
assert.deepEqual(writes,[]);assert.deepEqual(errors,[])
await writeFile(out+'/browser-verification.json',JSON.stringify({model,viewports:3,cameraCalls:0,clinicalWrites:writes,errors,scope:'Actual missing-weight adapter with disposable QA DB'},null,2))
await browser.close();console.log(JSON.stringify({adapter:model.extra.adapter,ready:model.is_ready,missing:model.extra.missing,sourceIssue:model.extra.known_source_issue,viewports:3,errors,writes}))
