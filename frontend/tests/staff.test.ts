import test from 'node:test'
import assert from 'node:assert/strict'
const staff = await import('../src/staff/controller.ts').catch(()=>({} as any))
const policy = await import('../src/staff/permissions.ts').catch(()=>({} as any))
test('nurse can collect and edit basic patient data but cannot write professional fields or administer accounts',()=>{
 assert.equal(typeof policy.permissionsFor,'function')
 assert.deepEqual(policy.permissionsFor('NURSE'),{staff:true,admin:false,clinical:false})
 assert.deepEqual(policy.permissionsFor('PATIENT'),{staff:false,admin:false,clinical:false})
 assert.equal(policy.permissionsFor('DOCTOR').clinical,true)
 assert.equal(policy.permissionsFor('DOCTOR').admin,false)
 assert.equal(policy.permissionsFor('ADMIN').admin,true)
})
test('public staff registration emits only approved application fields, never authenticates and prevents double submit',async()=>{
 assert.equal(typeof staff.StaffRegistrationController,'function')
 let resolve:any;const calls:any[]=[]
 const c=new staff.StaffRegistrationController(async(payload:any)=>{calls.push(payload);return new Promise(r=>resolve=r)})
 Object.assign(c.form,{username:' doctor ',password:'long-password',display_name:' 医护 ',phone:'13800138000',requested_role:'ADMIN'})
 await c.submit();assert.equal(calls.length,0)
 c.form.requested_role='NURSE';const first=c.submit();await c.submit();assert.equal(calls.length,1)
 assert.deepEqual(calls[0],{username:'doctor',password:'long-password',display_name:'医护',phone:'13800138000',requested_role:'NURSE'})
 resolve({id:'application',status:'PENDING',message:'pending',access_token:'must-not-store'});await first
 assert.deepEqual(c.result,{id:'application',status:'PENDING'});assert.equal(c.form.password,'')
})
test('registration disposal ignores late success; rejection retains editable fields and a retry path',async()=>{
 assert.equal(typeof staff.StaffRegistrationController,'function')
 let resolve:any;const c=new staff.StaffRegistrationController(()=>new Promise(r=>resolve=r))
 Object.assign(c.form,{username:'doctor',password:'long-password',display_name:'name',phone:'13800138000'})
 const pending=c.submit();c.dispose();resolve({id:'late',status:'PENDING'});await pending;assert.equal(c.result,null)
 const d=new staff.StaffRegistrationController(async()=>{throw Error('duplicate')});Object.assign(d.form,{username:'doctor',password:'long-password',display_name:'name',phone:'13800138000'});await d.submit();assert.equal(d.error,'duplicate');assert.equal(d.submitting,false);assert.equal(d.form.username,'doctor')
})
test('public registration request uses subpath and no bearer or staff session effects',async()=>{
 assert.equal(typeof staff.createStaffRegistrationApi,'function')
 let request:any;const api=staff.createStaffRegistrationApi('/pd-rehab/',async(url:any,init:any)=>{request={url,init};return new Response(JSON.stringify({id:'1',status:'PENDING'}),{status:201})})
 await api({username:'u',password:'password',display_name:'Name',phone:'123',requested_role:'DOCTOR'})
 assert.equal(request.url,'/pd-rehab/api/auth/register');assert.equal(request.init.credentials,'omit');assert.equal(new Headers(request.init.headers).has('Authorization'),false)
})
test('management controller preserves failed review for retry and reloads current status after success',async()=>{
 assert.equal(typeof staff.StaffManagementController,'function')
 let fails=true;const reviewed:any[]=[]
 const api={applications:async(status:string)=>({items:[{id:'1',status}],total:1}),staff:async()=>({items:[{id:'doctor',role:'DOCTOR'}],total:1}),review:async(id:string,payload:any)=>{if(fails)throw Error('conflict');reviewed.push({id,payload})},update:async()=>{}}
 const c=new staff.StaffManagementController(api);await c.load();assert.equal(c.applications[0].status,'PENDING');assert.equal(c.staff[0].role,'DOCTOR')
 await c.review('1','APPROVE','NURSE','');assert.equal(c.error,'conflict');assert.equal(c.busy,false)
 fails=false;await c.review('1','APPROVE','NURSE','');assert.deepEqual(reviewed,[{id:'1',payload:{decision:'APPROVE',role:'NURSE'}}]);assert.equal(c.error,'')
 c.status='REJECTED';await c.load();assert.equal(c.applications[0].status,'REJECTED')
})
test('only administrators delete completed assessment; staff retain own unfinished cleanup',()=>{
 assert.equal(typeof policy.canDeleteAssessment,'function')
 assert.equal(policy.canDeleteAssessment('DOCTOR','d',{status:'COMPLETED',created_by:'d'}),false)
 assert.equal(policy.canDeleteAssessment('ADMIN','a',{status:'COMPLETED',created_by:'d'}),true)
 assert.equal(policy.canDeleteAssessment('NURSE','n',{status:'IN_PROGRESS',created_by:'n'}),true)
 assert.equal(policy.canDeleteAssessment('NURSE','n',{status:'IN_PROGRESS',created_by:'other'}),false)
})
test('nurse patient payload omits professional notes while preserving basic intake; doctor keeps them',()=>{
 assert.equal(typeof policy.patientPayloadFor,'function')
 assert.deepEqual(policy.patientPayloadFor('NURSE',{name:'姓名',medical_history:'history',doctor_notes:'clinical'}),{name:'姓名',medical_history:'history'})
 assert.deepEqual(policy.patientPayloadFor('DOCTOR',{doctor_notes:'clinical'}),{doctor_notes:'clinical'})
})
import {readFileSync} from 'node:fs'
import {createRequire} from 'node:module'
const require=createRequire(import.meta.url),vue=require('vue'),ts=require('typescript')
function shellEntries(role:string){
 const source=readFileSync(new URL('../src/layouts/MainLayout.vue',import.meta.url),'utf8').match(/<script setup lang="ts">([\s\S]*?)<\/script>/)![1]
 const output:any={};const modules:any={vue:{...vue,onMounted:()=>{},onBeforeUnmount:()=>{}},'vue-router':{useRoute:()=>({path:'/dashboard'}),useRouter:()=>({})},'@/stores/auth':{useAuthStore:()=>({permissions:policy.permissionsFor(role)})},'@/stores/taskMode':{useTaskModeStore:()=>({})}}
 const code=ts.transpileModule(source+'\nexports.entries=entries',{compilerOptions:{module:ts.ModuleKind.CommonJS,target:ts.ScriptTarget.ES2022}}).outputText
 new Function('require','exports',code)((id:string)=>modules[id]??{},output);return output.entries.value.map((e:any)=>e.to)
}
test('actual shell offers staff management only to administrator and keeps shared clinical entries',()=>{
 assert.deepEqual(shellEntries('NURSE'),['/dashboard','/patients','/assessment','/training','/follow-up'])
 assert.deepEqual(shellEntries('DOCTOR'),['/dashboard','/patients','/assessment','/training','/follow-up'])
 assert.deepEqual(shellEntries('ADMIN'),['/dashboard','/patients','/assessment','/training','/follow-up','/staff'])
})
function routerFixture(role:string,authenticated=true){
 const guards:any[]=[],output:any={},routes:any[]=[]
 const router={beforeEach:(fn:any)=>guards.push(fn),beforeResolve:()=>{},afterEach:()=>{},onError:()=>{}}
 const auth={initialised:true,isAuthenticated:authenticated,user:{id:'staff'},permissions:policy.permissionsFor(role)}
 const modules:any={'vue-router':{createRouter:(config:any)=>{routes.push(...config.routes);return router},createWebHistory:()=>({})},'@/stores/auth':{useAuthStore:()=>auth},'@/navigation/assessmentLifecycle':{onAssessmentExpired:()=>{},setAssessmentOwner:()=>false,retryAssessmentCleanup:async()=>{}},'@/i18n':{}}
 const source=readFileSync(new URL('../src/router/index.ts',import.meta.url),'utf8').replaceAll('import.meta.env.BASE_URL',"'/'")
 const code=ts.transpileModule(source,{compilerOptions:{module:ts.ModuleKind.CommonJS,target:ts.ScriptTarget.ES2022}}).outputText
 new Function('require','exports',code)((id:string)=>modules[id]??{},output)
 return {guard:guards.at(-1),routes}
}
test('actual router permits public staff registration and refuses direct staff admin entry for nurse/doctor',async()=>{
 for(const role of ['NURSE','DOCTOR']){
  const f=routerFixture(role);assert.deepEqual(await f.guard({meta:{admin:true},fullPath:'/staff'}, {name:'dashboard'}),{name:'dashboard'})
 }
 const admin=routerFixture('ADMIN');assert.equal(await admin.guard({meta:{admin:true},fullPath:'/staff'},{name:'dashboard'}),true)
 const publicRoute=admin.routes.find((r:any)=>r.path==='/register/staff');assert.equal(publicRoute.meta.public,true)
 const signedOut=routerFixture('',false);assert.equal(await signedOut.guard(publicRoute,{name:'login'}),true)
})
test('recording cleanup controls keep own unfinished work and exclude other staff or completed records',()=>{
 assert.equal(typeof policy.canManageRecording,'function')
 assert.equal(policy.canManageRecording('NURSE','n',{status:'FAILED',operator_id:'n'},'delete'),true)
 assert.equal(policy.canManageRecording('NURSE','n',{status:'FAILED',operator_id:'other'},'delete'),false)
 assert.equal(policy.canManageRecording('DOCTOR','d',{status:'PARTIAL_SUCCESS',operator_id:'d'},'delete'),false)
 assert.equal(policy.canManageRecording('DOCTOR','d',{status:'PARTIAL_SUCCESS',operator_id:'d'},'retry'),true)
 assert.equal(policy.canManageRecording('ADMIN','a',{status:'SUCCESS',operator_id:'other'},'delete'),true)
 assert.equal(policy.canDeleteAssessment('PATIENT','p',{status:'IN_PROGRESS',created_by:'p'}),false)
})
test('registration rejects invalid username, password length or phone before making a public request',async()=>{
 let requests=0;const c=new staff.StaffRegistrationController(async()=>{requests++;return {id:'1',status:'PENDING'}})
 Object.assign(c.form,{username:'bad name',password:'long-password',display_name:'Name',phone:'13800138000'});await c.submit();assert.equal(requests,0)
 c.form.username='valid';c.form.password='short';await c.submit();assert.equal(requests,0)
 c.form.password='x'.repeat(65);await c.submit();assert.equal(requests,0)
 c.form.password='long-password';c.form.phone='no phone';await c.submit();assert.equal(requests,0)
})
test('registration network failure presents a translated actionable message',async()=>{
 const api=staff.createStaffRegistrationApi('/',async()=>{throw TypeError('fetch failed')})
 await assert.rejects(api({username:'valid',password:'password',display_name:'Name',phone:'123456',requested_role:'DOCTOR'}),{message:'无法连接到服务器，请检查网络后重试。'})
})
test('failed session restoration with a retained token does not redirect login back into a role guard loop',async()=>{
 const f=routerFixture('',true);assert.equal(await f.guard({name:'login',meta:{public:true}},{name:'dashboard'}),true)
})
test('registration enforces password UTF8 byte limit and rejects control characters in names',async()=>{
 let requests=0;const c=new staff.StaffRegistrationController(async()=>{requests++;return{id:'1',status:'PENDING'}})
 Object.assign(c.form,{username:'valid',password:'密'.repeat(25),display_name:'Name',phone:'123456'});await c.submit();assert.equal(requests,0)
 c.form.password='long-password';c.form.display_name='Name\nOther';await c.submit();assert.equal(requests,0)
})

test('successful account mutation stays successful when an admin-list reload is forbidden after self-demotion',async()=>{
 let role='ADMIN';const c=new staff.StaffManagementController({applications:async()=>{if(role!=='ADMIN')throw Error('403');return{items:[],total:0}},staff:async()=>({items:[],total:0}),review:async()=>{},update:async()=>{role='NURSE'}});
 await c.load();assert.equal(await c.update('self',{role:'NURSE'}),true);assert.equal(role,'NURSE');assert.equal(c.error,'403');
});
