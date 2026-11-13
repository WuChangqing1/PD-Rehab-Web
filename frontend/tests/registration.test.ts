import test from 'node:test'
import assert from 'node:assert/strict'
import { createRegistrationApi } from '../src/registration/publicApi.ts'
import { RegistrationController } from '../src/registration/controller.ts'
import { readFileSync } from 'node:fs'
import { createRequire } from 'node:module'

test('public API uses deployment base, omits staff credentials and revokes only temporary mobile session', async () => {
  const calls: {url:string, init:RequestInit}[] = []
  const api = createRegistrationApi('/pd-rehab/', async (url, init) => {
    calls.push({url:String(url),init:init!})
    return new Response(JSON.stringify(String(url).endsWith('/sms/login') ? {user:{username:'p_fixture'},access_token:'private-access',refresh_token:'private-refresh',recovery_code:'one-time'} : {}))
  })
  const result = await api.verify('challenge','123456')
  assert.deepEqual(result,{username:'p_fixture',recoveryCode:'one-time'})
  await api.cleanup()
  assert.deepEqual(calls.map(c=>c.url), ['/pd-rehab/api/mobile/auth/sms/login','/pd-rehab/api/mobile/auth/logout'])
  assert.deepEqual(JSON.parse(calls[0]!.init.body as string), {challenge_id:'challenge',code:'123456',sync_consent_version:'account-sync-v1'})
  assert.deepEqual(JSON.parse(calls[1]!.init.body as string), {refresh_token:'private-refresh'})
  for (const c of calls) { assert.equal(c.init.credentials,'omit'); assert.equal(new Headers(c.init.headers).has('Authorization'),false) }
})
test('401 preserves error contract without a staff logout; Retry-After is retained', async () => {
  const api = createRegistrationApi('/', async()=>new Response(JSON.stringify({error:{code:'INVALID_LOGIN_PROOF',message:'验证码错误或已失效。'}}),{status:401,headers:{'Retry-After':'60'}}))
  await assert.rejects(api.verify('challenge','123456'), (error:any)=>error.message==='验证码错误或已失效。' && error.retryAfter===60)
})
function fixture() {
  let now=1000, sends=0, verifies=0
  let resolveSend:(value:any)=>void = ()=>{}
  const api={providers:async()=>({sms_enabled:true}),challenge:async()=>{sends++;return new Promise<any>(resolve=>{resolveSend=resolve})},verify:async()=>{verifies++;return {username:'existing'}},cleanup:async()=>true}
  const controller = new RegistrationController(api,()=>now)
  controller.enabled=true;controller.loading=false;controller.setPhone('13800138000');controller.consent=true
  return {controller,api,get sends(){return sends},get verifies(){return verifies},resolveSend:(v:any)=>resolveSend(v),advance:(ms:number)=>{now+=ms}}
}
test('send locks synchronously; phone edit invalidates late challenge but retains server cooldown',async()=>{
  const f=fixture(), first=f.controller.send();await f.controller.send();assert.equal(f.sends,1)
  f.controller.setPhone('13900139000');f.resolveSend({challenge_id:'old',retry_after:60,expires_in:300});await first
  assert.equal(f.controller.challengeId,'');assert.equal(f.controller.retrySeconds,60)
  f.advance(60001);assert.equal(f.controller.retrySeconds,0)
})
test('consent, six digit proof and wall-clock expiry gate verification',async()=>{
  const f=fixture();const send=f.controller.send();f.resolveSend({challenge_id:'valid',retry_after:60,expires_in:300});await send
  f.controller.code='123456';f.controller.consent=false;await f.controller.submit();assert.equal(f.verifies,0)
  f.controller.consent=true;f.advance(300001);await f.controller.submit();assert.equal(f.verifies,0);assert.match(f.controller.error,/失效/)
})
test('unmount suppresses late updates; existing account has no invented recovery code',async()=>{
  const f=fixture();const send=f.controller.send();f.controller.dispose();f.resolveSend({challenge_id:'late',retry_after:60,expires_in:300});await send
  assert.equal(f.controller.challengeId,'')
  const g=fixture();const sent=g.controller.send();g.resolveSend({challenge_id:'valid',retry_after:60,expires_in:300});await sent;g.controller.code='123456';await g.controller.submit()
  assert.deepEqual(g.controller.result,{username:'existing'});assert.equal(g.controller.code,'');assert.equal(g.controller.phone,'')
})
test('provider request and SMS challenge use actual public contract and actionable unavailable error',async()=>{
  const calls:any[]=[]
  const api=createRegistrationApi('/',async(url,init)=>{
    calls.push({url,init})
    if(String(url).endsWith('/providers'))return new Response(JSON.stringify({sms_enabled:true,wechat_enabled:false}))
    return new Response(JSON.stringify({error:{code:'LOGIN_PROVIDER_UNAVAILABLE',message:'此登录方式暂不可用，请使用账号密码登录。'}}),{status:503,headers:{'Retry-After':'60'}})
  })
  assert.equal((await api.providers()).sms_enabled,true)
  await assert.rejects(api.challenge('+8613800138000'),(error:any)=>error.message==='短信注册暂不可用，请稍后重试或联系技术支持。'&&error.retryAfter===60)
  assert.equal(calls[0].url,'/api/mobile/auth/providers');assert.equal(calls[0].init.method,'GET')
  assert.equal(calls[1].url,'/api/mobile/auth/sms/challenge');assert.deepEqual(JSON.parse(calls[1].init.body),{phone:'+8613800138000'})
})
test('failed requests reserve cooldown and first account stays new after recovery code is cleared',async()=>{
  const f=fixture();f.api.challenge=async()=>{throw Error('offline')};await f.controller.send();assert.equal(f.controller.retrySeconds,60)
  f.advance(60001);f.api.challenge=async()=>({challenge_id:'valid',retry_after:60,expires_in:300});await f.controller.send()
  f.api.verify=async()=>({username:'new',recoveryCode:'only-once'} as any);f.controller.code='123456';await f.controller.submit()
  assert.equal(f.controller.newAccount,true);f.controller.clearRecovery();assert.deepEqual(f.controller.result,{username:'new'});assert.equal(f.controller.newAccount,true)
})
test('verification locks duplicate submit and disposes safely while API cleanup finishes',async()=>{
  const f=fixture();f.api.challenge=async()=>({challenge_id:'valid',retry_after:60,expires_in:300});await f.controller.send();f.controller.code='123456'
  let count=0,finish:(value:any)=>void=()=>{}
  f.api.verify=async()=>{count++;return new Promise(resolve=>finish=resolve)}
  const first=f.controller.submit();await f.controller.submit();assert.equal(count,1)
  f.controller.dispose();finish({username:'new',recoveryCode:'secret'});await first;assert.equal(f.controller.result,null);assert.equal(f.controller.code,'')
})
test('temporary session cleanup failure retains only in-memory token for retry and does not resubmit proof',async()=>{
  let failures=1,logins=0,logouts=0
  const api=createRegistrationApi('/',async(url)=>{
    if(String(url).endsWith('/sms/login')){logins++;return new Response(JSON.stringify({user:{username:'new'},refresh_token:'temporary',recovery_code:'secret'}))}
    logouts++;return new Response('{}',{status:failures-->0?503:200})
  })
  assert.deepEqual(await api.verify('challenge','123456'),{username:'new',recoveryCode:'secret'})
  assert.equal(await api.cleanup(),false)
  assert.equal(await api.cleanup(),true);assert.equal(logins,1);assert.equal(logouts,2)
})
test('registration page compiles with one native submit path and isolated public client',()=>{
  const require=createRequire(import.meta.url),compiler=require('@vue/compiler-sfc')
  const source=readFileSync(new URL('../src/pages/PhoneRegistrationPage.vue',import.meta.url),'utf8')
  const {descriptor}=compiler.parse(source)
  const script=compiler.compileScript(descriptor,{id:'registration-test'})
  const template=compiler.compileTemplate({source:descriptor.template.content,filename:'PhoneRegistrationPage.vue',id:'registration-test',compilerOptions:{bindingMetadata:script.bindings}})
  assert.deepEqual(template.errors,[]);assert.match(source,/@submit.prevent="submit"/);assert.doesNotMatch(source,/@keyup.enter|useAuthStore|localStorage|console\./)
  assert.match(source,/isComposing/);assert.match(source,/onBeforeUnmount/)
})
test('resending invalidates previous proof even when replacement SMS delivery fails',async()=>{
  const f=fixture();f.api.challenge=async()=>({challenge_id:'old',retry_after:60,expires_in:300});await f.controller.send();f.controller.code='123456';f.advance(60001)
  f.api.challenge=async()=>{throw Error('delivery failed')};await f.controller.send()
  assert.equal(f.controller.challengeId,'');assert.equal(f.controller.code,'');assert.equal(f.controller.canSubmit,false)
})
test('first account recovery is visible immediately while one asynchronous session cleanup is pending',async()=>{
  let finishCleanup:(value:boolean)=>void=()=>{},cleanups=0
  const f=fixture();f.api.challenge=async()=>({challenge_id:'valid',retry_after:60,expires_in:300})
  f.api.verify=async()=>({username:'first',recoveryCode:'save-now'} as any)
  f.api.cleanup=async()=>{cleanups++;return new Promise<boolean>(resolve=>{finishCleanup=resolve})}
  await f.controller.send();f.controller.code='123456'
  await f.controller.submit()
  assert.deepEqual(f.controller.result,{username:'first',recoveryCode:'save-now'})
  assert.equal(f.controller.submitting,false);assert.equal(f.controller.cleanupPending,true);assert.equal(cleanups,1)
  assert.equal(f.controller.cleanupRunning,true)
  finishCleanup(true);await Promise.resolve();await Promise.resolve()
  assert.equal(f.controller.cleanupPending,false)
})
test('mobile logout is keepalive and deduplicated in flight without delaying proof response',async()=>{
  let release:()=>void=()=>{},logoutCount=0
  const api=createRegistrationApi('/',async(url,init)=>{
    if(String(url).endsWith('/sms/login')){assert.notEqual(init?.keepalive,true);return new Response(JSON.stringify({user:{username:'first'},refresh_token:'temporary',recovery_code:'save-now'}))}
    logoutCount++;assert.equal(init?.keepalive,true)
    await new Promise<void>(resolve=>{release=resolve});return new Response('{}')
  })
  assert.deepEqual(await api.verify('challenge','123456'),{username:'first',recoveryCode:'save-now'})
  const first=api.cleanup(),duplicate=api.cleanup();assert.equal(logoutCount,1)
  release();assert.equal(await first,true);assert.equal(await duplicate,true)
})
