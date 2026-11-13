import assert from 'node:assert/strict'
import test from 'node:test'
import { COMFORTABLE_DIFFICULTY, DEFAULT_DIFFICULTY, generateCues, resolveCue } from '../src/piano/session.ts'
import { applyRecipe, RECIPES } from '../src/piano/recipes.ts'
import { cueBindings } from '../src/piano/cuePresentation.ts'

test('comfortable start spaces cues at 1500 ms without changing standard scoring or mapping', () => {
 const cues=generateCues('ALTERNATING_HANDS',COMFORTABLE_DIFFICULTY,{seed:42,cueCount:4})
 assert.equal(COMFORTABLE_DIFFICULTY.bpm,40)
 assert.equal(DEFAULT_DIFFICULTY.bpm,60)
 assert.equal(cues[1]!.targetMs-cues[0]!.targetMs,1500)
 assert.equal(COMFORTABLE_DIFFICULTY.judgement_window_ms,DEFAULT_DIFFICULTY.judgement_window_ms)
 for(const cue of cues){
  assert.equal(cueBindings(cue)[0]!.hand,cue.binding.hand)
  const result=resolveCue(cue,[{code:cue.binding.code,midi:cue.binding.midi,downTimeMs:cue.targetMs,upTimeMs:cue.targetMs+100,relativeDownMs:cue.targetMs,relativeUpMs:cue.targetMs+100}],COMFORTABLE_DIFFICULTY.judgement_window_ms)
  assert.equal(result[0]!.is_correct,true)
  assert.equal(result[0]!.hand,cue.binding.hand)
  assert.equal(result[0]!.timing_error_ms,0)
 }
})
test('hand instructions follow both real bindings, demonstrations, and withdrawn cues',()=>{
 const stream=generateCues('ALTERNATING_HANDS',DEFAULT_DIFFICULTY,{seed:42,cueCount:20})
 const left=stream.find(c=>c.binding.hand==='LEFT'),right=stream.find(c=>c.binding.hand==='RIGHT')
 assert.notEqual(left!.binding.hand,right!.binding.hand)
 assert.deepEqual(cueBindings({...left!,secondaryBinding:right!.binding}).map(b=>b.code),[left!.binding.code,right!.binding.code])
 assert.deepEqual(cueBindings({...left!,isPrompt:true}),[left!.binding])
 assert.deepEqual(cueBindings({...left!,hasCue:false}),[])
 assert.deepEqual(cueBindings({...left!,cueType:'NO_GO',secondaryBinding:right!.binding}),[])
 assert.deepEqual(cueBindings(null),[])
})

test('comfortable cue lead is recorded and standard/legacy timing remains 700 ms',()=>{
 for(const mode of ['CALIBRATION','SINGLE_KEY_RHYTHM','ALTERNATING_HANDS','MAPPED_SEQUENCE','FOLLOW_THE_BEAT','MEMORY_RHYTHM'] as const){
  const comfortable=generateCues(mode,COMFORTABLE_DIFFICULTY,{seed:42,cueCount:20})
  const standard=generateCues(mode,DEFAULT_DIFFICULTY,{seed:42,cueCount:20})
  assert.equal(comfortable[0]!.targetMs-comfortable[0]!.cueOnsetMs,1200,mode)
  assert.equal(comfortable[1]!.targetMs-comfortable[1]!.cueOnsetMs,1200,mode)
  assert.equal(standard[0]!.targetMs-standard[0]!.cueOnsetMs,700,mode)
 }
})

test('all recipe timelines retain actual lead and never reveal removed/no-go hand cues',()=>{
 for(const recipe of RECIPES){
  const stream=applyRecipe(recipe,generateCues(recipe.baseMode,COMFORTABLE_DIFFICULTY,{seed:42}),COMFORTABLE_DIFFICULTY,{seed:42})
  assert.ok(stream.length,recipe.id)
  for(const cue of stream){
   if(cue.cueType) assert.equal(cue.cueOnsetMs,cue.targetMs)
   else assert.equal(Math.round(cue.targetMs-cue.cueOnsetMs),1200,recipe.id)
   if(cue.hasCue===false||cue.cueType==='NO_GO') assert.deepEqual(cueBindings(cue),[])
  }
 }
})
