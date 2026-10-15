import test from 'node:test'
import assert from 'node:assert/strict'
import {createRequire} from 'node:module'
import {readFileSync} from 'node:fs'
import {GuidedSongMachine} from '../src/piano/guided-song/machine.ts'
import {TWO_TIGERS,SEVEN_KEYS,DIFFICULTY_BPM} from '../src/piano/guided-song/song.ts'
const require=createRequire(import.meta.url),vue=require('vue'),ts=require('typescript')
const code=ts.transpileModule(readFileSync(new URL('../src/piano/guided-song/useGuidedSong.ts',import.meta.url),'utf8'),{compilerOptions:{module:ts.ModuleKind.CommonJS,target:ts.ScriptTarget.ES2022}}).outputText
const flush=async()=>{for(let i=0;i<16;i++)await Promise.resolve()}
function fixture(overrides:Record<string,unknown>={}){
 let gateOptions:any;let time=1000;const calls:string[]=[];const session={id:'s1',patient_id:'p1',segment_1_bpm:60,segment_2_bpm:60,metrics:{},events:[]}
 const api={create:async()=>session,events:async()=>{calls.push('events');return session},second:async()=>{calls.push('second');return session},complete:async()=>{calls.push('complete');return session},cancel:async()=>{calls.push('cancel');return session},history:async()=>[],emotion:async()=>session,upload:async()=>session,...overrides}
 class Engine{unlock=async()=>{};load=async()=>{};has=()=>true;stopAll=()=>{};close=async()=>{};play=()=>null;getBuffer=()=>undefined;ensureContext=()=>({currentTime:0});audioTimeToPerformance=(t:number)=>t*1000}
 const modules:any={'@/api/client':{API_BASE:'/api',TOKEN_STORAGE_KEY:'token'},vue:{...vue,onBeforeUnmount:()=>{}},'vue-router':{useRoute:()=>({query:{selftest:'1'}}),onBeforeRouteLeave:()=>{}},'@/composables/useTrainingStartGate':{useTrainingStartGate:(options:any)=>{gateOptions=options;return{busy:vue.ref(false),state:vue.reactive({error:''}),requestStart:()=>{},cancelStart:()=>{},changePatient:()=>{}}}},'@/stores/taskMode':{useTaskModeStore:()=>({enter:()=>{},exit:()=>{}})},'@/stores/patientContext':{usePatientContextStore:()=>({currentPatient:{id:'p1'}})},'@/piano/engine':{PianoEngine:Engine},'./machine':{GuidedSongMachine},'./song':{TWO_TIGERS,SEVEN_KEYS,DIFFICULTY_BPM},'./audio':{renderPerformanceAudio:async()=>({blob:new Blob(['a'])})},'./api':{songApi:api},'@/emotion/useLiveEmotion':{useLiveEmotion:()=>({status:vue.ref('IDLE'),consent:vue.ref(false),start:async()=>{},stop:()=>{}})}}
 const windowMock={setInterval:()=>0,setTimeout:()=>0,addEventListener:()=>{},removeEventListener:()=>{}}
 const doc={fullscreenElement:null,documentElement:{},addEventListener:()=>{},removeEventListener:()=>{}}
 const exports:any={}
 new Function('require','exports','window','document','screen','performance','requestAnimationFrame','cancelAnimationFrame','crypto','URL','structuredClone',code)((key:string)=>modules[key],exports,windowMock,doc,{orientation:{unlock:()=>{}}},{now:()=>time},()=>0,()=>{},{randomUUID:()=> 'request'},URL,structuredClone)
 const song=exports.useGuidedSong()
 async function prepare(){await gateOptions.prepare({id:'p1'},new AbortController().signal)}
 function play(which:1|2=1){song.session.value=session;song.active.value=true;const m=song.machine.value;for(const state of ['PREPARING','COUNTDOWN','SEGMENT_1_DEMO','SEGMENT_1_PLAY'])if(m.state==='CONFIGURING'||m.state==='PREPARING'||m.state==='COUNTDOWN'||m.state==='SEGMENT_1_DEMO')m.transition(state,0);if(which===2){for(let i=0;i<14;i++)m.skip(0);m.transition('SEGMENT_2_DEMO',0);m.transition('SEGMENT_2_PLAY',0)}}
 return{song,calls,session,prepare,start:()=>gateOptions.start(),play,tick:()=>time+=100}
}
test('repeated physical pointer creates distinct press identifiers and retains each press',()=>{
 const f=fixture();f.play();for(const index of [0,1,0]){f.tick();f.song.down(index,'pointer-1');f.tick();f.song.up('pointer-1')}
 const downs=f.song.machine.value.events.filter((e:any)=>e.type==='DOWN')
 assert.equal(downs.length,3);assert.equal(new Set(downs.map((e:any)=>e.press_id)).size,3)
 assert.equal(f.song.machine.value.metrics().wrong_press_count,1)
})
test('cancelled countdown never creates a session',()=>{const f=fixture();f.song.begin();f.song.cancelStart();assert.equal(f.song.active.value,false);assert.deepEqual(f.calls,[])})
test('late create response is cancelled and cannot launch demo',async()=>{
 let resolve:any;const f=fixture({create:()=>new Promise(r=>resolve=r)});await f.prepare();f.start();await flush();f.song.cancelStart();resolve(f.session);await flush();assert.equal(f.song.active.value,false);assert.equal(f.song.state.value,'CANCELLED');assert.deepEqual(f.calls,['cancel'])
})
test('exit while saving first segment cannot create second-segment work',async()=>{
 let resolve:any;let first=true;const f=fixture({events:async()=>{if(first){first=false;await new Promise(r=>resolve=r)}return f.session}});f.play();for(let i=0;i<14;i++)f.song.skip();await flush();const end=f.song.end();await flush();resolve();await end;await flush();assert.equal(f.song.state.value,'CANCELLED');assert.ok(!f.calls.includes('second'));assert.ok(f.calls.includes('cancel'))
})
test('a failed cancellation retries both raw save and cancellation',async()=>{
 let fail=true;const f=fixture({cancel:async()=>{if(fail)throw new Error('offline');f.calls.push('cancel');return {...f.session,status:'CANCELLED'}}});f.play();await f.song.end();assert.ok(f.song.error.value);fail=false;await f.song.retry();assert.ok(f.calls.includes('cancel'));assert.equal(f.song.error.value,'')
})
test('pending cancellation cannot be overwritten by history navigation',async()=>{
 let fail=true,reads=0;const f=fixture({events:async()=>{if(fail)throw new Error('offline');return f.session},get:async()=>{reads++;return {...f.session,id:'prior',events:[]}}});f.play();f.song.down(0,'pointer-1');f.song.up('pointer-1');await f.song.end();const snapshot=JSON.stringify(f.song.machine.value.events),beforeReads=reads;await f.song.viewHistory({id:'prior'});assert.equal(reads,beforeReads);assert.equal(f.song.session.value.id,'s1');assert.equal(JSON.stringify(f.song.machine.value.events),snapshot);fail=false;await f.song.retry();assert.ok(f.calls.includes('cancel'));assert.equal(f.song.pendingCancellation.value,false)
})
test('ending while completion is already committed keeps the valid completed record',async()=>{
 const f=fixture({events:async()=>({...f.session,status:'COMPLETED'})});f.play();await f.song.end();assert.equal(f.song.pendingCancellation.value,false);assert.equal(f.song.saved.value,true);assert.equal(f.song.session.value.status,'COMPLETED');assert.ok(!f.calls.includes('cancel'))
})

test('preparation failure is visible and cannot start a session',async()=>{
 const f=fixture();f.song.gate.state.error='音源准备失败';await flush();assert.equal(f.song.state.value,'FAILED');assert.equal(f.song.active.value,false);assert.deepEqual(f.calls,[])
})
