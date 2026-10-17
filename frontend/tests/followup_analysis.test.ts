import test from 'node:test'
import assert from 'node:assert/strict'
import {buildTrendSeries} from '../src/followup/trends.ts'
import {pianoPracticeKey,pianoConfigKey,metricValue,objectiveSummary,usablePiano,pianoMetricSpecs,poseMetricSpecs} from '../src/followup/analysis.ts'

test('default trends remain human-only and explicit demo view never includes human records',()=>{
 const rows=[{at:'2026-10-01T00:00:00Z',value:1,source:'HUMAN_KEYBOARD',version:'1'}, {at:'2026-10-02T00:00:00Z',value:2,source:'SEED_DEMO',version:'1'}]
 assert.deepEqual(buildTrendSeries(rows).points.map(p=>p.value),[1])
 assert.deepEqual(buildTrendSeries(rows,{source:'SEED_DEMO'}).points.map(p=>p.value),[2])
})
test('practice and actual difficulty configurations cannot be averaged together',()=>{
 const base:any={mode:'SINGLE_KEY_RHYTHM',recipe_id:null,bpm:60,judgement_window_ms:250,sequence_length:4,hand_mode:'SINGLE'}
 assert.notEqual(pianoPracticeKey(base),pianoPracticeKey({...base,recipe_id:'HOLD_RELEASE'}))
 assert.notEqual(pianoConfigKey(base),pianoConfigKey({...base,bpm:80}))
 assert.notEqual(pianoConfigKey(base),pianoConfigKey({...base,judgement_window_ms:300}))
 for(const key of ['tempo_ceiling_bpm','weak_hand','recipe_algorithm_version'])
  assert.notEqual(pianoConfigKey({...base,difficulty_before_json:{[key]:70}}),pianoConfigKey({...base,difficulty_before_json:{[key]:120}}))
 assert.equal(usablePiano({...base,completed_at:'2026-10-01',difficulty_before_json:{completion_status:'INTERRUPTED'}}),false)
})
test('recipe metrics use authoritative stored values and never synthesize missing values',()=>{
 const row:any={timing_mae_ms:15,difficulty_before_json:{server_metrics:{hold_duration_mae_ms:37}}}
 assert.equal(metricValue(row,'hold_duration_mae_ms'),37)
 assert.equal(metricValue(row,'timing_mae_ms'),15)
 assert.equal(metricValue(row,'missing'),null)
 assert.ok(pianoMetricSpecs('HOLD_RELEASE').some(s=>s.key==='hold_duration_mae_ms'))
 assert.ok(poseMetricSpecs('BALLET_TENDU').some(s=>s.key.includes('hip')))
})
test('objective report compares the latest compatible version and states insufficient evidence',()=>{
 const built=buildTrendSeries([{at:'2026-10-01',value:1,source:'HUMAN_KEYBOARD',version:'v1'}, {at:'2026-10-02',value:2,source:'HUMAN_KEYBOARD',version:'v2'}])
 const summary=objectiveSummary(built)
 assert.equal(summary.previous,null);assert.equal(summary.delta,null);assert.equal(summary.count,1)
 const two=objectiveSummary(buildTrendSeries([{at:'2026-10-01',value:5,source:'HUMAN_KEYBOARD',version:'v1'}, {at:'2026-10-02',value:3,source:'HUMAN_KEYBOARD',version:'v1'}]))
 assert.equal(two.delta,-2);assert.equal(two.median,4);assert.equal(two.minimum,3);assert.equal(two.maximum,5)
})
test('invalid timestamps do not become trend points',()=>{
 assert.equal(buildTrendSeries([{at:'not-a-date',value:4,source:'HUMAN_KEYBOARD',version:null}]).points.length,0)
})
