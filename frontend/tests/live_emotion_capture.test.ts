import test from 'node:test'
import assert from 'node:assert/strict'
import {createRequire} from 'node:module'
import {readFileSync} from 'node:fs'
import {validDistribution,EMOTION_LABELS} from '../src/emotion/types.ts'
const require=createRequire(import.meta.url),vue=require('vue'),ts=require('typescript')
const code=ts.transpileModule(readFileSync(new URL('../src/emotion/useLiveEmotion.ts',import.meta.url),'utf8'),{compilerOptions:{module:ts.ModuleKind.CommonJS,target:ts.ScriptTarget.ES2022}}).outputText
function fixture(getUserMedia:()=>Promise<any>){
 let transport:any,requests=0,tracksStopped=0,recorderStopped=0
 class Client{onMessage:any;onFailure:any;connect=()=>{requests++};close=()=>{};sendChunk=()=>false;constructor(){transport=this}}
 class Recorder{static isTypeSupported=()=>true;state='inactive';ondataavailable:any;start(){this.state='recording'}stop(){this.state='inactive';recorderStopped++}}
 const stream={getTracks:()=>[{stop:()=>tracksStopped++}]}
 const modules:any={vue:{...vue,onBeforeUnmount:()=>{}},'@/api/client':{API_BASE:'/api',TOKEN_STORAGE_KEY:'token'},'./streamClient':{EmotionStreamClient:Client},'./types':{validDistribution,EMOTION_LABELS}}
 const exports:any={}
 const globals={isSecureContext:true,MediaRecorder:Recorder}
 new Function('require','exports','globalThis','navigator','document','window','localStorage','MediaRecorder','URL',code)((name:string)=>modules[name],exports,globals,{mediaDevices:{getUserMedia}}, {addEventListener:()=>{},removeEventListener:()=>{}},{location:{origin:'https://test.local',protocol:'https:'}},{getItem:()=> 'token'},Recorder,URL)
 return{live:exports.useLiveEmotion(),transport:()=>transport,requests:()=>requests,stopped:()=>tracksStopped,stream,recorderStopped:()=>recorderStopped}
}
const ready={status:'READY',capture_required:true,protocol:'continuous-mediarecorder-v1',requirements:{fps:30,width:640,height:480}}
test('no consent and no model never request a camera or invent a result',async()=>{
 let camera=0;const f=fixture(async()=>{camera++;return f.stream});await f.live.start('s','p');assert.equal(f.requests(),0);f.live.consent.value=true;await f.live.start('s','p');await f.transport().onMessage({status:'MODEL_NOT_CONFIGURED'});assert.equal(camera,0);assert.equal(f.live.summary.value,null);assert.equal(f.live.status.value,'MODEL_NOT_CONFIGURED')
})
test('late camera permission after stop releases every track',async()=>{
 let resolve:any;const f=fixture(()=>new Promise(r=>resolve=r));f.live.consent.value=true;await f.live.start('s','p');const pending=f.transport().onMessage(ready);f.live.stop();resolve(f.stream);await pending;assert.equal(f.stopped(),1);assert.equal(f.live.status.value,'STOPPED')
})
test('camera denial degrades without generating probabilities',async()=>{
 const f=fixture(async()=>{throw new Error('NotAllowedError')});f.live.consent.value=true;await f.live.start('s','p');await f.transport().onMessage(ready);assert.equal(f.live.status.value,'UNAVAILABLE');assert.equal(f.live.summary.value,null)
})
test('offline-only video model stops the connection without requesting a camera',async()=>{
 let camera=0;const f=fixture(async()=>{camera++;return f.stream});f.live.consent.value=true;await f.live.start('s','p')
 await f.transport().onMessage({status:'UNAVAILABLE',capture_required:false,labels:['negative','positive','surprise']})
 assert.equal(camera,0);assert.equal(f.live.status.value,'UNAVAILABLE');assert.equal(f.live.summary.value,null)
})
test('backpressure and network loss stop capture instead of queuing video',async()=>{
 const f=fixture(async()=>f.stream);f.live.consent.value=true;await f.live.start('s','p');await f.transport().onMessage(ready);assert.equal(f.live.status.value,'STREAMING');f.transport().onFailure();assert.equal(f.stopped(),1);assert.equal(f.recorderStopped(),1);assert.equal(f.live.status.value,'UNAVAILABLE')
})
test('model quality and latency statistics come only from valid labeled results',async()=>{
 const f=fixture(async()=>f.stream);f.live.consent.value=true;await f.live.start('s','p');await f.transport().onMessage({type:'result',source:'MODEL',labels:[...EMOTION_LABELS],probabilities:null,quality:'LOW',inference_latency_ms:30});assert.equal(f.live.statistics.value.results,1);assert.equal(f.live.statistics.value.low_quality,1);assert.equal(f.live.statistics.value.last_latency_ms,30);assert.equal(f.live.summary.value.probabilities,null)
})
