import test from 'node:test'
import assert from 'node:assert/strict'
import {readFileSync} from 'node:fs'
import {createRequire} from 'node:module'
const require=createRequire(import.meta.url),vue=require('vue'),ts=require('typescript')
function pageFixture(file:string, options:any={}){
 const routes:any[]=[],writes:string[]=[]
 const patient={id:'p1',medication_state:'ON'}
 const api={listSessions:async()=>({items:[],total:0}),createSession:async(_id:string,payload:any)=>{writes.push('create');return{id:'s1',...payload}},
  deleteSession:async()=>{writes.push('delete')},getSession:async()=>({id:'s1',patient_id:'p1',session_type:'COMPREHENSIVE',status:'IN_PROGRESS',finger_tapping_results:[],micro_expression_results:[],functional_assessments:[]}),
  readiness:async()=>({can_complete:false,items:[{key:'micro_expression',state:'SKIPPED_MODEL_UNAVAILABLE'},{key:'finger_tapping_left',state:'PENDING'},{key:'finger_tapping_right',state:'PENDING'}]}),
  completeSession:async()=>{writes.push('complete')},...options.api}
 const router={push:async(value:any)=>{routes.push(value)},replace:async()=>{}}
 const modules:any={vue:{...vue,onMounted:()=>{},onBeforeUnmount:()=>{},watch:()=>{}},'vue-router':{useRoute:()=>({params:{id:'p1',sessionId:'s1'},query:options.query??{}}),useRouter:()=>router},
  '@/api':{assessmentApi:api,patientApi:{get:async()=>patient}},'@/api/client':{notifyError:()=>{}},'@/stores/patientContext':{usePatientContextStore:()=>({resolve:async()=>patient})},
  'element-plus':{ElMessage:{success:()=>{},error:()=>{}},ElMessageBox:{confirm:options.confirm??(async()=>{})}},'@element-plus/icons-vue':{Monitor:{},VideoCamera:{},DataAnalysis:{}},
  '@/utils/format':{formatDateTime:()=>''}}
 const source=readFileSync(new URL(`../src/pages/${file}`,import.meta.url),'utf8').match(/<script setup lang="ts">([\s\S]*?)<\/script>/)![1]
 const exports:any={};const script=source+'\nexports.handlers={openAssessment:typeof openAssessment==="function"?openAssessment:null,start:typeof start==="function"?start:null,usePatient:typeof usePatient==="function"?usePatient:null,abandon:typeof abandon==="function"?abandon:null,load:typeof load==="function"?load:null,finish:typeof finish==="function"?finish:null,openStep:typeof openStep==="function"?openStep:null,session:typeof session!=="undefined"?session:null,error:typeof error!=="undefined"?error:null,openSessions:typeof openSessions!=="undefined"?openSessions:null,openTotal:typeof openTotal!=="undefined"?openTotal:null}'
 const code=ts.transpileModule(script,{compilerOptions:{module:ts.ModuleKind.CommonJS,target:ts.ScriptTarget.ES2022}}).outputText
 new Function('require','exports',code)((name:string)=>modules[name]??{},exports)
 return{...exports.handlers,routes,writes}
}
test('patient history opens stored assessment results without creating a session',()=>{
 const f=pageFixture('PatientDetailPage.vue')
 f.openAssessment({id:'saved-session',session_type:'COMPREHENSIVE',status:'COMPLETED'})
 assert.equal(f.routes[0].name,'assessment-results')
 assert.equal(f.routes[0].params.sessionId,'saved-session')
 assert.deepEqual(f.writes,[])
})

test('cancelling deletion leaves the selected assessment intact',async()=>{
 const f=pageFixture('AssessmentHubPage.vue',{confirm:async()=>{throw 'cancel'}})
 await f.usePatient('p1');await f.abandon({id:'s1'})
 assert.deepEqual(f.writes,[]);assert.deepEqual(f.routes,[])
})
test('confirmed deletion calls delete and refreshes the unfinished count without creating another assessment',async()=>{
 let count=2
 const f=pageFixture('AssessmentHubPage.vue',{api:{listSessions:async()=>({items:count===2?[{id:'s1'},{id:'s2'}]:[{id:'s2'}],total:count}),deleteSession:async(id:string,patientId:string)=>{assert.equal(id,'s1');assert.equal(patientId,'p1');count--}}})
 await f.usePatient('p1');await f.abandon({id:'s1'})
 assert.equal(f.openTotal.value,1);assert.equal(f.openSessions.value[0].id,'s2');assert.deepEqual(f.writes,[]);assert.deepEqual(f.routes,[])
})
test('failed deletion retains the unfinished row and count',async()=>{
 const f=pageFixture('AssessmentHubPage.vue',{api:{listSessions:async()=>({items:[{id:'s1'}],total:1}),deleteSession:async()=>{throw Error('offline')}}})
 await f.usePatient('p1');await f.abandon({id:'s1'})
 assert.equal(f.openTotal.value,1);assert.equal(f.openSessions.value[0].id,'s1')
})
test('results page loads saved data without creating, completing or analyzing a record',async()=>{
 const f=pageFixture('AssessmentResultsPage.vue');await f.load()
 assert.equal(f.session.value.id,'s1');assert.deepEqual(f.writes,[])
})
test('results page refuses a session for a different patient',async()=>{
 const f=pageFixture('AssessmentResultsPage.vue',{query:{patientId:'p2'}});await f.load()
 assert.equal(f.session.value,null);assert.match(f.error.value,/不一致/);assert.deepEqual(f.writes,[])
})
test('comprehensive workflow keeps one session and gates completion on stored readiness',async()=>{
 const f=pageFixture('AssessmentComprehensivePage.vue');await f.load();await f.finish()
 assert.deepEqual(f.writes,[])
 f.openStep('finger_tapping_right')
 assert.equal(f.routes[0].query.sessionId,'s1');assert.equal(f.routes[0].query.hand,'RIGHT')
})
test('comprehensive completion saves the existing session and opens its stored results',async()=>{
 const f=pageFixture('AssessmentComprehensivePage.vue',{api:{readiness:async()=>({can_complete:true,items:[]})}})
 await f.load();await f.finish()
 assert.deepEqual(f.writes,['complete']);assert.equal(f.routes[0].name,'assessment-results');assert.equal(f.routes[0].params.sessionId,'s1')
})
test('starting comprehensive assessment opens its workflow and preserves the created session',async()=>{
 const f=pageFixture('AssessmentHubPage.vue');await f.usePatient('p1');await f.start('COMPREHENSIVE')
 assert.equal(f.routes[0].name,'assessment-comprehensive')
 assert.equal(f.routes[0].params.sessionId,'s1');assert.deepEqual(f.writes,['create'])
})


test('facial entry keeps the comprehensive patient and session without saving or completing',async()=>{
 const f=pageFixture('AssessmentComprehensivePage.vue');await f.load()
 f.openStep('micro_expression')
 assert.equal(f.routes[0].name,'assessment-micro-expression')
 assert.deepEqual(f.routes[0].query,{patientId:'p1',sessionId:'s1'})
 assert.deepEqual(f.writes,[])
 await f.finish();assert.deepEqual(f.writes,[])
})
