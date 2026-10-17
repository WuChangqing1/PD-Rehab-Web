import test from 'node:test'
import assert from 'node:assert/strict'
import {readFileSync} from 'node:fs'
import {createRequire} from 'node:module'
import * as calendar from '../src/followup/calendar.ts'
import * as analysis from '../src/followup/analysis.ts'
import * as trends from '../src/followup/trends.ts'
const require=createRequire(import.meta.url),vue=require('vue'),ts=require('typescript')
function fixture(read:any,getSession:any=()=>{}){
 const modules:any={vue:{...vue,onMounted:()=>{},watch:()=>{}},'vue-router':{useRoute:()=>({query:{}}),useRouter:()=>({replace:()=>{},push:()=>{}})},
 '@/api':{followupApi:{read},pianoApi:{getSession}},'@/api/client':{notifyError:()=>{}},
 '@/stores/patientContext':{usePatientContextStore:()=>({resolve:async(id:string)=>({id,hospital_number:id==='demo'?'DEMO-FOLLOWUP-20261017':id}),select:()=>{}})},
 '@/followup/calendar':calendar,'@/followup/analysis':analysis,'@/followup/trends':trends}
 const source=readFileSync(new URL('../src/pages/FollowUpPage.vue',import.meta.url),'utf8').match(/<script setup lang="ts">([\s\S]*?)<\/script>/)![1]
 const out:any={},code=ts.transpileModule(source+'\nexports.page={usePatient,clearPatient,feed,calendarFeed,calendarError,patient,scope,openActivity,detailBusy,detailOpen,guidedConfigs}',{compilerOptions:{module:ts.ModuleKind.CommonJS,target:ts.ScriptTarget.ES2022}}).outputText
 new Function('require','exports',code)((name:string)=>modules[name]??{},out)
 return out.page
}
const data=(id:string)=>({patient_id:id,piano:[],pose:[],guided:[],tapping:[],assessments:[]})
test('late responses for a previous patient never replace current follow-up or calendar data',async()=>{
 const pending:Array<{id:string;resolve:Function}>=[]
 const page=fixture((id:string)=>new Promise(resolve=>pending.push({id,resolve})))
 const first=page.usePatient('first');await Promise.resolve();await Promise.resolve()
 const second=page.usePatient('second');await Promise.resolve();await Promise.resolve()
 for(const request of pending.filter(r=>r.id==='second'))request.resolve(data('second'))
 await second
 for(const request of pending.filter(r=>r.id==='first'))request.resolve(data('first'))
 await first
 assert.equal(page.patient.value.id,'second');assert.equal(page.feed.value.patient_id,'second');assert.equal(page.calendarFeed.value.patient_id,'second')
})
test('switching patients during result loading clears the loading state and ignores old details',async()=>{
 let resolve:any;const page=fixture(async(id:string)=>data(id),()=>new Promise(done=>resolve=done))
 await page.usePatient('first');const pending=page.openActivity({kind:'piano',id:'old'})
 assert.equal(page.detailBusy.value,true);await page.usePatient('second')
 assert.equal(page.detailBusy.value,false);resolve({patient_id:'first'});await pending
 assert.equal(page.detailBusy.value,false);assert.equal(page.detailOpen.value,false)
})
test('guided trends distinguish both segment speeds',async()=>{
 const page=fixture(async(id:string)=>({...data(id),guided:[60,80].map(bpm=>({source:'HUMAN_KEYBOARD',status:'COMPLETED',song_id:'two_tigers',selected_hand:'LEFT',difficulty:'INTERMEDIATE',bpm:60,segment_1_bpm:bpm,segment_2_bpm:60}))}))
 await page.usePatient('first');assert.equal(page.guidedConfigs.value.length,2)
})
test('calendar failures are explicit rather than appearing as a day with no training',async()=>{
 const page=fixture(async()=>{throw Error('offline')});await page.usePatient('first')
 assert.equal(page.calendarFeed.value,null);assert.match(page.calendarError.value,/无法读取/)
})
test('only the independent showcase defaults to a labelled sample view',async()=>{
 const page=fixture(async(id:string)=>data(id));await page.usePatient('demo')
 assert.equal(page.scope.value,'SEED_DEMO');await page.usePatient('person')
 assert.equal(page.scope.value,'HUMAN_KEYBOARD')
})
