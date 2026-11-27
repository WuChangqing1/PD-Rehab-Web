import {test,afterEach,beforeEach} from 'node:test'
import assert from 'node:assert/strict'
import {
 TRAINING_FEEDBACK_KEY,DISCOMFORT_NOTE_LIMIT,
 emptyTrainingFeedback,hasTrainingFeedback,loadTrainingFeedback as load,saveTrainingFeedback as save,trainingFeedbackKey,
} from '../src/training/trainingFeedback.ts'

const saveTrainingFeedback=(ref:Parameters<typeof save>[0],input:Parameters<typeof save>[1],now=new Date(),owner='test-account')=>save(ref,input,now,owner)
const loadTrainingFeedback=(ref:Parameters<typeof load>[0],owner='test-account')=>load(ref,owner)
const scoped=TRAINING_FEEDBACK_KEY+':test-account'

class MemoryStorage{
 data=new Map<string,string>()
 get length(){return this.data.size}
 clear(){this.data.clear()}
 getItem(key:string){return this.data.get(key)??null}
 key(index:number){return [...this.data.keys()][index]??null}
 removeItem(key:string){this.data.delete(key)}
 setItem(key:string,value:string){this.data.set(key,String(value))}
}

let store:MemoryStorage
function useStorage(value:unknown){Object.defineProperty(globalThis,'localStorage',{value,configurable:true,writable:true})}
beforeEach(()=>{store=new MemoryStorage();useStorage(store)})
afterEach(()=>{Reflect.deleteProperty(globalThis,'localStorage')})

const piano={kind:'piano' as const,id:'session-1'}
const pose={kind:'pose' as const,id:'session-1'}

test('round-trips a completed questionnaire under one session key',()=>{
 const at=new Date('2026-11-27T01:30:00.000Z')
 const saved=saveTrainingFeedback(piano,{effort:'MODERATE',discomfort:'PRESENT',discomfortNote:' 右肩酸 '},at)
 assert.equal(saved,true)
 assert.deepEqual(loadTrainingFeedback(piano),{effort:'MODERATE',discomfort:'PRESENT',discomfortNote:'右肩酸'})
 const root=JSON.parse(store.getItem(scoped) as string)
 assert.equal(root.items[trainingFeedbackKey(piano)].recorded_at,at.toISOString())
})

test('a skipped questionnaire writes nothing and reports no record',()=>{
 assert.equal(saveTrainingFeedback(piano,emptyTrainingFeedback()),false)
 assert.equal(store.getItem(scoped),null)
 assert.equal(loadTrainingFeedback(piano),null)
})

test('effort alone counts as an answer',()=>{
 assert.equal(hasTrainingFeedback({effort:'EASY',discomfort:null,discomfortNote:''}),true)
 assert.equal(saveTrainingFeedback(piano,{effort:'EASY',discomfort:null,discomfortNote:''}),true)
 assert.deepEqual(loadTrainingFeedback(piano),{effort:'EASY',discomfort:null,discomfortNote:''})
})

test('a note is kept only for reported discomfort and is capped',()=>{
 const long='疼'.repeat(DISCOMFORT_NOTE_LIMIT+20)
 saveTrainingFeedback(piano,{effort:null,discomfort:'PRESENT',discomfortNote:long})
 assert.equal(loadTrainingFeedback(piano)?.discomfortNote.length,DISCOMFORT_NOTE_LIMIT)
 saveTrainingFeedback(piano,{effort:null,discomfort:'NONE',discomfortNote:'右肩酸'})
 assert.deepEqual(loadTrainingFeedback(piano),{effort:null,discomfort:'NONE',discomfortNote:''})
 const root=JSON.parse(store.getItem(scoped) as string)
 assert.equal('discomfort_note' in root.items[trainingFeedbackKey(piano)],false)
})

test('sessions and kinds stay isolated',()=>{
 saveTrainingFeedback(piano,{effort:'FATIGUE',discomfort:null,discomfortNote:''})
 saveTrainingFeedback(pose,{effort:'EASY',discomfort:'NONE',discomfortNote:''})
 assert.equal(loadTrainingFeedback(piano)?.effort,'FATIGUE')
 assert.equal(loadTrainingFeedback(pose)?.effort,'EASY')
 assert.equal(loadTrainingFeedback({kind:'piano',id:'session-2'}),null)
})

test('corrupted storage is replaced instead of breaking the flow',()=>{
 store.setItem(scoped,'not-json')
 assert.equal(loadTrainingFeedback(piano),null)
 assert.equal(saveTrainingFeedback(piano,{effort:'EASY',discomfort:null,discomfortNote:''}),true)
 assert.equal(loadTrainingFeedback(piano)?.effort,'EASY')
})

test('unknown stored values are ignored',()=>{
 store.setItem(scoped,JSON.stringify({v:1,items:{'piano:session-1':{v:1,effort:'EXTREME',discomfort:'MAYBE',recorded_at:'2026-11-27T00:00:00.000Z'}}}))
 assert.equal(loadTrainingFeedback(piano),null)
})

test('unavailable or throwing storage degrades silently',()=>{
 useStorage({getItem(){throw new Error('blocked')},setItem(){throw new Error('blocked')}})
 assert.equal(loadTrainingFeedback(piano),null)
 assert.equal(saveTrainingFeedback(piano,{effort:'EASY',discomfort:null,discomfortNote:''}),false)
 Reflect.deleteProperty(globalThis,'localStorage')
 assert.equal(loadTrainingFeedback(piano),null)
 assert.equal(saveTrainingFeedback(piano,{effort:'EASY',discomfort:null,discomfortNote:''}),false)
})


test('feedback is isolated by account and anonymous saves are rejected',()=>{
 const answers={effort:'EASY' as const,discomfort:null,discomfortNote:''}
 assert.equal(saveTrainingFeedback(piano,answers,new Date(),'account-a'),true)
 assert.equal(loadTrainingFeedback(piano,'account-b'),null)
 assert.equal(saveTrainingFeedback(piano,answers,new Date(),''),false)
 assert.equal(loadTrainingFeedback(piano,''),null)
 assert.equal(loadTrainingFeedback(piano,'account-a')?.effort,'EASY')
})
