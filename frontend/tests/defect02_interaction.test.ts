import test from 'node:test'
import assert from 'node:assert/strict'
import {existsSync,readFileSync} from 'node:fs'
import {createRequire} from 'node:module'
const require=createRequire(import.meta.url),ts=require('typescript'),vue=require('vue')
import {displayRecordNote} from '../src/utils/format.ts'
import {monthCells,completedActivities,type Activity} from '../src/followup/calendar.ts'

const confirmationURL=new URL('../src/training/confirmCalibration.ts',import.meta.url)
const readinessURL=new URL('../src/navigation/imageReadiness.ts',import.meta.url)
const deferred=()=>{let resolve!:()=>void;const promise=new Promise<void>(yes=>resolve=yes);return{promise,resolve}}

test('calendar excludes every unfinished, cancelled or interrupted activity',()=>{
 const rows=[{id:'done',completed:true},{id:'active-piano',completed:false},{id:'interrupted',completed:false},{id:'active-pose',completed:false},{id:'cancelled-guided',completed:false}] as Activity[]
 assert.deepEqual(completedActivities(rows).map(r=>r.id),['done'])
 assert.equal(rows.length,5,'history source remains unchanged')
})

test('every valid month reserves six weeks without inventing dates',()=>{
 for(const month of ['2021-02','2024-02','2026-08','2026-10']){
  const cells=monthCells(month)
  assert.equal(cells.length,42)
  assert.equal(new Set(cells.filter(Boolean)).size,cells.filter(Boolean).length)
 }
 assert.equal(monthCells('2024-02').filter(Boolean).length,29)
})

test('baseline confirmation waits for explicit approval and cancellation never approves',async()=>{
 assert.ok(existsSync(confirmationURL),'baseline test needs a cancellable confirmation before countdown')
 const {confirmCalibration}=await import(confirmationURL.href)
 const ask=deferred();let finished=false
 const signal=new AbortController()
 const result=confirmCalibration(signal.signal,()=>ask.promise,()=>{}).then((v:boolean)=>{finished=true;return v})
 await Promise.resolve();assert.equal(finished,false)
 ask.resolve();assert.equal(await result,true)
 assert.equal(await confirmCalibration(signal.signal,()=>Promise.reject(new Error('cancel')),()=>{}),false)
})

test('leaving during baseline confirmation closes it and ignores late approval',async()=>{
 assert.ok(existsSync(confirmationURL))
 const {confirmCalibration}=await import(confirmationURL.href)
 const ask=deferred(),operation=new AbortController();let closes=0
 const result=confirmCalibration(operation.signal,()=>ask.promise,()=>closes++)
 operation.abort();assert.equal(await result,false);assert.equal(closes,1)
 ask.resolve();await Promise.resolve()
 assert.equal(await confirmCalibration(operation.signal,()=>{throw new Error('must not ask')},()=>{}),false)
})

test('page images wait for every unique image; successful loads are reusable',async()=>{
 assert.ok(existsSync(readinessURL),'critical route assets need a bounded readiness gate')
 const {createImagePreloader}=await import(readinessURL.href)
 const first=deferred(),second=deferred(),calls:string[]=[]
 const load=createImagePreloader((url:string)=>{calls.push(url);return url==='one'?first.promise:second.promise},1000)
 let ready=false;const result=load(['one','two','one']).then(()=>ready=true)
 first.resolve();await Promise.resolve();assert.equal(ready,false)
 second.resolve();await result;assert.deepEqual(calls,['one','two'])
 await load(['two','one']);assert.equal(calls.length,2)
})

test('page image failure can retry; abort and timeout cannot leave loading pending',async()=>{
 assert.ok(existsSync(readinessURL))
 const {createImagePreloader}=await import(readinessURL.href)
 let attempts=0
 const retry=createImagePreloader(async()=>{if(++attempts===1)throw new Error('network')},100)
 await assert.rejects(retry(['failed']),/network/);await retry(['failed']);assert.equal(attempts,2)
 const pending=createImagePreloader(()=>new Promise(()=>{}),10)
 await assert.rejects(pending(['timeout']),/超时/)
 const controller=new AbortController(),aborted=createImagePreloader(()=>new Promise(()=>{}),1000)(['abort'],controller.signal)
 controller.abort();await assert.rejects(aborted,{name:'AbortError'})
})


test('recent patients are unique, latest first, and limited to five',()=>{
 const source=readFileSync(new URL('../src/stores/patientContext.ts',import.meta.url),'utf8')
 const output:any={}
 const compiled=ts.transpileModule(source,{compilerOptions:{module:ts.ModuleKind.CommonJS,target:ts.ScriptTarget.ES2022}}).outputText
 new Function('require','exports',compiled)((id:string)=>id==='vue'?vue:id==='pinia'?{defineStore:(_name:string,setup:any)=>setup}:{patientApi:{}},output)
 const store=output.usePatientContextStore()
 for(let i=0;i<7;i++)store.accept({id:String(i)})
 store.accept({id:'4'})
 assert.deepEqual(store.recentIds.value,['4','6','5','3','2'])
 assert.equal(store.currentPatientId.value,'4')
 store.accept({id:'deleted',is_deleted:true})
 assert.equal(store.currentPatientId.value,'4')
})

test('guided catalogue selection stays on page; only its configuration action navigates',()=>{
 const source=readFileSync(new URL('../src/pages/PianoTrainingPage.vue',import.meta.url),'utf8').match(/<script setup lang="ts">([\s\S]*?)<\/script>/)![1]
 const tree=ts.createSourceFile('page.ts',source,ts.ScriptTarget.Latest,true)
 const names=new Set(['choosePractice','chooseMode','chooseRecipe','begin'])
 const functions=tree.statements.filter((n:any)=>ts.isFunctionDeclaration(n)&&names.has(n.name?.text)).map((n:any)=>n.getText(tree)).join('\n')
 assert.equal(functions.includes('function choosePractice'),true)
 const output:any={},moves:any[]=[],starts:any[]=[],selected={value:null as any}
 const compiled=ts.transpileModule(functions+'\nexports.actions={choosePractice,begin}',{compilerOptions:{module:ts.ModuleKind.CommonJS,target:ts.ScriptTarget.ES2022}}).outputText
 new Function('exports','selectedRoutePractice','selectedRecipe','selectedMode','running','startBusy','router','route','runner','requestStart','gestureUnlock',compiled)(output,selected,{value:null},{value:'SINGLE_KEY_RHYTHM'},{value:false},{value:false},{push:(v:any)=>moves.push(v)},{query:{patientId:'qa'}},{unlock:()=>starts.push('unlock')},()=>starts.push('start'),null)
 output.actions.choosePractice({id:'GUIDED',route:'/training/guided-song'})
 assert.equal(moves.length,0);assert.equal(starts.length,0)
 output.actions.begin()
 assert.deepEqual(moves,[{path:'/training/guided-song',query:{patientId:'qa'}}]);assert.equal(starts.length,0)
 output.actions.choosePractice({id:'single',mode:'SINGLE_KEY_RHYTHM'})
 assert.equal(selected.value,null);output.actions.begin();assert.deepEqual(starts,['unlock','start'])
})

 test('saved record notes use the current source terminology without altering the record',()=>{
 const record={notes:'仿真记录；仿真原始数据'}
 assert.equal(displayRecordNote(record.notes),'参考记录；参考原始数据')
 assert.equal(record.notes,'仿真记录；仿真原始数据')
 assert.equal(displayRecordNote(null),null)
 assert.equal(displayRecordNote('常规随访'),'常规随访')
 })
