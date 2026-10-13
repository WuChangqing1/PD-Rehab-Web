import test from 'node:test'
import assert from 'node:assert/strict'
import { applyRecipe, RECIPE_BY_ID } from '../src/piano/recipes.ts'
import { generateCues, resolveCue, DEFAULT_DIFFICULTY, type PressInput } from '../src/piano/session.ts'
import { extendedMetrics } from '../src/piano/extendedMetrics.ts'
import { computeMetrics } from '../src/piano/metrics.ts'

const config = { ...DEFAULT_DIFFICULTY, session_duration_sec: 20, finger_complexity: 3 }
function cues(id: keyof typeof RECIPE_BY_ID) {
  const recipe = RECIPE_BY_ID[id]
  return applyRecipe(recipe, generateCues(recipe.baseMode, config, { seed: 7 }), config, { seed: 7 })
}
function press(midi: number, down: number, up = down + 80): PressInput {
  return { midi, code: 'KeyJ', downTimeMs: down, upTimeMs: up, relativeDownMs: down, relativeUpMs: up }
}
test('tempo ramp changes actual intervals and returns to baseline without exceeding 110%', () => {
  const stream = cues('TEMPO_RAMP')
  assert.deepEqual([...new Set(stream.map(c => c.tempoSegment))], [0,1,2,3])
  const intervals = [0,1,2,3].map(segment => {
    const group = stream.filter(c => c.tempoSegment === segment)
    return group[1].targetMs - group[0].targetMs
  })
  assert.ok(intervals[1] < intervals[0] && intervals[2] < intervals[1])
  assert.ok(intervals[2] >= 1000/1.1 - 1e-8)
  assert.ok(Math.abs(intervals[3]-intervals[0])<1e-8)
})
test('hold task supplies genuinely different release targets and records timestamp duration', () => {
  const stream = cues('HOLD_RELEASE')
  assert.deepEqual([...new Set(stream.map(c => c.targetHoldMs))], [250, 750])
  const c = stream[0]
  const rows = resolveCue(c, [press(c.binding.midi,c.targetMs,c.targetMs+300)], 300)
  assert.equal(rows[0].target_hold_ms, 250)
  assert.equal(rows[0].hold_duration_ms, 300)
})
test('offset pairs have separate targets 500ms apart and preserve pair metadata', () => {
  const stream = cues('BIMANUAL_OFFSET')
  assert.equal(stream[1].targetMs-stream[0].targetMs,500)
  assert.equal(stream[0].pairId,stream[1].pairId)
  assert.notEqual(stream[0].binding.hand,stream[1].binding.hand)
  assert.equal(resolveCue(stream[1],[],300)[0].target_offset_ms,500)
})
test('reverse sequence demonstrates forward then asks the exact reverse, never scoring prompts', () => {
  const stream = cues('REVERSE_SEQUENCE')
  const group = stream.filter(c => c.memoryGroup === 0)
  assert.deepEqual(group.filter(c=>!c.isPrompt).map(c=>c.binding.midi),group.filter(c=>c.isPrompt).map(c=>c.binding.midi).reverse())
  assert.ok(new Set(group.map(c=>c.binding.midi)).size>1)
  const row=resolveCue(group[0],[],300)[0]
  assert.equal(row.is_prompt,true)
  assert.equal(row.is_missed,false)
})
test('no-go correct silence is a successful inhibition, any pressed key a commission', () => {
  const c=cues('GO_NO_GO').find(c=>c.cueType==='NO_GO')!
  const quiet=resolveCue(c,[],300)[0]
  assert.equal(quiet.is_correct,true)
  assert.equal(quiet.is_missed,false)
  assert.equal(quiet.cue_type,'NO_GO')
  const wrong=resolveCue(c,[press(c.binding.midi+1,c.targetMs)],300)[0]
  assert.equal(wrong.is_correct,false)
  assert.equal(wrong.is_missed,false)
  assert.equal(wrong.actual_time_ms,c.targetMs)
})
test('selective reaction accepts a response after the visible GO signal without requiring beat anticipation',()=>{
  const c=cues('GO_NO_GO').find(c=>c.cueType==='GO')!
  const row=resolveCue(c,[press(c.binding.midi,c.cueOnsetMs+300)],300)[0]
  assert.equal(row.is_correct,true)
  assert.equal(row.response_latency_ms,300)
  assert.equal(row.timing_error_ms,null)
})
test('simultaneous pair does not treat the second expected key as a wrong key and preserves a lone right response', () => {
  const c=cues('BIMANUAL_SYNC')[0]
  const both=resolveCue(c,[press(c.binding.midi,c.targetMs),press(c.secondaryBinding!.midi,c.targetMs+10)],300)
  assert.equal(both.filter(r=>r.is_wrong_key).length,0)
  assert.equal(both.filter(r=>r.is_correct).length,2)
  const right=resolveCue(c,[press(c.secondaryBinding!.midi,c.targetMs)],300)
  assert.equal(right.length,2)
  assert.equal(right[0].is_missed,true)
  assert.equal(right[1].is_correct,true)
  assert.equal(right[1].inter_hand_onset_diff_ms,null)
})

test('low-complexity memory has a valid binding at every prompt and response position',()=>{
  const stream=generateCues('MEMORY_RHYTHM',DEFAULT_DIFFICULTY,{seed:7})
  assert.ok(stream.length>0)
  assert.ok(stream.every(c=>c.binding?.midi!=null))
})

test('extended hold and inhibition metrics use observed timestamps, excluding prompt cues',()=>{
  const hold=cues('HOLD_RELEASE')[0]
  const released=resolveCue(hold,[press(hold.binding.midi,hold.targetMs,hold.targetMs+300)],300)[0]
  const missing=resolveCue({...hold,eventIndex:1,targetHoldMs:750},[],300)[0]
  const no=cues('GO_NO_GO').find(c=>c.cueType==='NO_GO')!
  const go=cues('GO_NO_GO').find(c=>c.cueType==='GO')!
  const rows=[released,missing,...resolveCue(no,[press(no.binding.midi,no.targetMs+100)],300),...resolveCue(go,[press(go.binding.midi,go.targetMs+250)],300)]
  const metrics=extendedMetrics(rows)
  assert.equal(metrics.hold_duration_mae_ms,50)
  assert.equal(metrics.hold_release_completion_rate,.5)
  assert.equal(metrics.go_commission_count,1)
  assert.equal(metrics.go_omission_count,0)
  assert.equal(metrics.go_response_latency_ms,250)
})

test('demonstration notes cannot improve accuracy or inflate completion',()=>{
  const stream=cues('REVERSE_SEQUENCE')
  const rows=stream.flatMap(c=>resolveCue(c,[],300))
  const metrics=computeMetrics(rows,{plannedCues:stream.filter(c=>!c.isPrompt).length})
  assert.equal(metrics.accuracy,0)
  assert.equal(metrics.miss_rate,1)
  assert.equal(metrics.session_completion_rate,1)
})

test('dense tempo ramp still reaches all four stages within the configured duration and ceiling',()=>{
  const recipe=RECIPE_BY_ID.TEMPO_RAMP
  const dense={...config,note_density:1.5,tempo_ceiling_bpm:63}
  const stream=applyRecipe(recipe,generateCues(recipe.baseMode,dense,{seed:7}),dense,{seed:7})
  assert.deepEqual([...new Set(stream.map(c=>c.tempoSegment))],[0,1,2,3])
  assert.ok(stream.every(c=>c.targetMs+150<20000))
  for(let i=1;i<stream.length;i++) assert.ok(stream[i].targetMs-stream[i-1].targetMs>=60000/63-1e-8)
})
