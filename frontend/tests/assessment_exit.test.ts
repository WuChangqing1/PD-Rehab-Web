import test from 'node:test'
import assert from 'node:assert/strict'
import {assessmentSessionId,shouldDiscard,createExitCleanup} from '../src/utils/assessmentExit.ts'
const face={name:'assessment-micro-expression',query:{sessionId:'s1'}}
test('leaving discards assessment; comprehensive steps and results preserve the same session',()=>{
 assert.equal(shouldDiscard(face,{name:'dashboard'}),'s1')
 for(const name of ['assessment-comprehensive','assessment-results'])
  assert.equal(shouldDiscard(face,{name,params:{sessionId:'s1'}}),null)
 assert.equal(shouldDiscard(face,{...face,query:{sessionId:'s2'}}),'s1')
 assert.equal(assessmentSessionId({name:'patient-detail',query:{sessionId:'s1'}}),null)
})
test('failed exit remains pending; successful retry clears the queue',async()=>{
 let pending:string[]=[],fail=true
 const c=createExitCleanup({read:()=>pending,write:v=>{pending=v},discard:async()=>{if(fail)throw Error('offline');return {deleted:true}}})
 await assert.rejects(c.leave('s1'));assert.deepEqual(pending,['s1'])
 fail=false;await c.retry();assert.deepEqual(pending,[])
})
test('unload remembers the exact session without duplicate requests',()=>{
 let pending:string[]=[]
 const c=createExitCleanup({read:()=>pending,write:v=>{pending=v},discard:async()=>({deleted:true})})
 c.remember('s1');c.remember('s1');assert.deepEqual(pending,['s1'])
})

test('a superseded navigation does not discard until the route actually leaves',async()=>{
 let calls=0,pending:string[]=[]
 const c=createExitCleanup({read:()=>pending,write:v=>{pending=v},discard:async()=>{calls++;return {deleted:true}}})
 shouldDiscard(face,{name:'dashboard'})
 assert.equal(calls,0);assert.equal(await c.canEnter('s1'),true)
 await c.leave('s1');assert.equal(await c.canEnter('s1'),false)
})
test('returning to a session waits for cleanup and cannot enter a deleted record',async()=>{
 let finish!:(v:{deleted:boolean})=>void
 const c=createExitCleanup({read:()=>[],write:()=>{},discard:()=>new Promise(resolve=>{finish=resolve})})
 const exiting=c.leave('s1');const entering=c.canEnter('s1')
 finish({deleted:true});await exiting;assert.equal(await entering,false)
})

test('logout still clears local credentials when both cleanup and logout requests fail',async()=>{
 const {createRequire}=await import('node:module'),require=createRequire(import.meta.url)
 const {readFileSync}=await import('node:fs'),ts=require('typescript'),vue=require('vue')
 const source=readFileSync(new URL('../src/stores/auth.ts',import.meta.url),'utf8')
 const compiled=ts.transpileModule(source,{compilerOptions:{module:ts.ModuleKind.CommonJS,target:ts.ScriptTarget.ES2022}}).outputText
 let stored:string|null='test-token'
 const modules:any={'vue':vue,'pinia':{defineStore:(_name:string,setup:()=>unknown)=>setup},
  '@/api':{authApi:{logout:async()=>{throw Error('offline')}}},
  '@/api/client':{TOKEN_STORAGE_KEY:'test-key'},
  '@/navigation/assessmentLifecycle':{discardActiveAssessment:async()=>{throw Error('offline')}}}
 const exports:any={}
 new Function('require','exports','localStorage',compiled)((name:string)=>modules[name],exports,{
  getItem:()=>stored,setItem:(_key:string,value:string)=>{stored=value},removeItem:()=>{stored=null}})
 const store=exports.useAuthStore()
 await store.logout()
 assert.equal(store.token.value,null);assert.equal(store.user.value,null);assert.equal(stored,null)
})
