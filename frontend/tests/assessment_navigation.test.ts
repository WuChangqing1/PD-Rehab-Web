import test from 'node:test'
import assert from 'node:assert/strict'
import {readFileSync} from 'node:fs'
import {createRequire} from 'node:module'
const require=createRequire(import.meta.url),vue=require('vue'),ts=require('typescript')
function pageFixture(file:string, options:any={}){
 const routes:any[]=[],writes:string[]=[],unmount:Array<()=>void>=[]
 const patient={id:'p1',medication_state:'ON'}
 const api={listSessions:async()=>({items:[],total:0}),createSession:async(_id:string,payload:any)=>{writes.push('create');return{id:'s1',...payload}},
  deleteSession:async()=>{writes.push('delete')},getSession:async()=>({id:'s1',patient_id:'p1',session_type:'COMPREHENSIVE',status:'IN_PROGRESS',finger_tapping_results:[],micro_expression_results:[],functional_assessments:[]}),
  readiness:async()=>({can_complete:false,items:[{key:'micro_expression',state:'SKIPPED_MODEL_UNAVAILABLE'},{key:'finger_tapping_left',state:'PENDING'},{key:'finger_tapping_right',state:'PENDING'}]}),
  completeSession:async()=>{writes.push('complete')},...options.api}
 const router={push:async(value:any)=>{routes.push(value)},replace:async()=>{}}
 const modules:any={vue:{...vue,onMounted:()=>{},onBeforeUnmount:(fn:()=>void)=>unmount.push(fn),watch:()=>{}},'vue-router':{useRoute:()=>({params:{id:'p1',sessionId:'s1'},query:options.query??{}}),useRouter:()=>router},
  '@/navigation/assessmentLifecycle':{retryAssessmentCleanup:async()=>{},captureAssessmentCleanup:()=>async(id:string)=>{writes.push('discard:'+id)}},'@/stores/taskMode':{useTaskModeStore:()=>({enter:()=>{},exit:()=>{}})},'@/api':{assessmentApi:api,patientApi:{get:async()=>patient}},'@/api/client':{notifyError:()=>{}},'@/stores/patientContext':{usePatientContextStore:()=>({resolve:async()=>patient})},
  'element-plus':{ElMessage:{success:()=>{},error:()=>{}},ElMessageBox:{confirm:options.confirm??(async()=>{})}},'@element-plus/icons-vue':{Monitor:{},VideoCamera:{},DataAnalysis:{}},
  '@/utils/format':{formatDateTime:()=>''}}
 const source=readFileSync(new URL(`../src/pages/${file}`,import.meta.url),'utf8').match(/<script setup lang="ts">([\s\S]*?)<\/script>/)![1]
 const exports:any={};const script=source+'\nexports.handlers={selectedHand:typeof selectedHand!=="undefined"?selectedHand:null,clips:typeof clips!=="undefined"?clips:null,selectHand:typeof selectHand==="function"?selectHand:null,onClipChange:typeof onClipChange==="function"?onClipChange:null,captureRecording:typeof captureRecording==="function"?captureRecording:null,upload:typeof upload==="function"?upload:null,ensureSession:typeof ensureSession==="function"?ensureSession:null,showHistory:typeof showHistory==="function"?showHistory:null,loadHistory:typeof loadHistory==="function"?loadHistory:null,historyOpen:typeof historyOpen!=="undefined"?historyOpen:null,pickerOpen:typeof pickerOpen!=="undefined"?pickerOpen:null,historyRows:typeof historyRows!=="undefined"?historyRows:null,viewResult:typeof viewResult==="function"?viewResult:null,openAssessment:typeof openAssessment==="function"?openAssessment:null,start:typeof start==="function"?start:null,usePatient:typeof usePatient==="function"?usePatient:null,abandon:typeof abandon==="function"?abandon:null,load:typeof load==="function"?load:null,finish:typeof finish==="function"?finish:null,openStep:typeof openStep==="function"?openStep:null,session:typeof session!=="undefined"?session:null,error:typeof error!=="undefined"?error:null,openSessions:typeof openSessions!=="undefined"?openSessions:null,openTotal:typeof openTotal!=="undefined"?openTotal:null}'
 const code=ts.transpileModule(script,{compilerOptions:{module:ts.ModuleKind.CommonJS,target:ts.ScriptTarget.ES2022}}).outputText
 new Function('require','exports',code)((name:string)=>modules[name]??(name==='@/i18n'?{t:(value:unknown)=>value}:{}),exports)
 return{...exports.handlers,routes,writes,unmount}
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
 f.openStep('finger_tapping')
 assert.equal(f.routes[0].query.sessionId,'s1');assert.equal(f.routes[0].query.hand,undefined)
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

test('assessment history opens records immediately without selecting a patient or creating an assessment',async()=>{
 let requested=false
 const row={id:'history1',patient_id:'actual-patient',patient_name:'Saved patient',status:'COMPLETED'}
 const f=pageFixture('AssessmentHubPage.vue',{api:{listHistory:async(_page:number,_size:number,id?:string)=>{requested=true;assert.equal(id,undefined);return {items:[row],total:1}}}})
 f.showHistory();await f.loadHistory()
 assert.equal(f.historyOpen.value,true);assert.equal(f.pickerOpen.value,false)
 assert.equal(requested,true);assert.deepEqual(f.historyRows.value,[row]);assert.deepEqual(f.writes,[])
 f.viewResult(row);assert.equal(f.routes[0].query.patientId,'actual-patient')
})

for(const file of ['MicroExpressionPage.vue','FingerTappingPage.vue']){
 test(file+' discards a newly created session if the user already left',async()=>{
  let finish!:(row:any)=>void
  const f=pageFixture(file,{api:{createSession:()=>new Promise(resolve=>{finish=resolve})}})
  await f.usePatient('p1')
  const pending=f.ensureSession()
  for(const fn of f.unmount)fn()
  finish({id:'late-session',session_type:'MICRO_EXPRESSION_ONLY'})
  assert.equal(await pending,null)
  assert.deepEqual(f.writes,['discard:late-session'])
  assert.deepEqual(f.routes,[])
 })
}

test('cancelling a hand change preserves the selected hand and its pending video',async()=>{
 const f=pageFixture('FingerTappingPage.vue',{confirm:async()=>{throw Error('cancel')}})
 const video=new Blob(['left video'])
 f.onClipChange('LEFT',{blob:video,name:'left.webm'})
 await f.selectHand('RIGHT')
 assert.equal(f.selectedHand.value,'LEFT');assert.equal(f.clips.value.LEFT,video)
})
test('confirmed hand change clears an unanalysed clip instead of relabelling it',async()=>{
 const f=pageFixture('FingerTappingPage.vue')
 f.onClipChange('LEFT',{blob:new Blob(['left video']),name:'left.webm'})
 await f.selectHand('RIGHT')
 assert.equal(f.selectedHand.value,'RIGHT');assert.equal(f.clips.value.LEFT,null);assert.equal(f.clips.value.RIGHT,null)
})
test('hand switching is locked while recording',async()=>{
 const f=pageFixture('FingerTappingPage.vue')
 f.captureRecording('LEFT',true);await f.selectHand('RIGHT')
 assert.equal(f.selectedHand.value,'LEFT')
})
test('a right-hand video is submitted with RIGHT in the existing session',async()=>{
 let submitted:any[]=[]
 const f=pageFixture('FingerTappingPage.vue',{api:{uploadFingerTapping:async(...args:any[])=>{submitted=args;return {right:{id:'r1'},left:null}}}})
 await f.usePatient('p1');await f.selectHand('RIGHT')
 const video=new Blob(['right video'],{type:'video/webm'})
 f.onClipChange('RIGHT',{blob:video,name:'right.webm'})
 await f.upload('RIGHT')
 assert.equal(submitted[0],'s1');assert.equal(submitted[2],'RIGHT')
 assert.equal(f.clips.value.LEFT,null)
})
