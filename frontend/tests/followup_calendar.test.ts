import test from 'node:test'
import assert from 'node:assert/strict'
import { dayKey, monthCells, buildActivities, summarizeDays } from '../src/followup/calendar.ts'
import {formatDateTime} from '../src/utils/format.ts'

test('result timestamps use the same Beijing date and time as the calendar',()=>{
 assert.equal(formatDateTime('2026-09-30T16:50:00'),'2026-10-01 00:50')
 assert.equal(formatDateTime('2026-10-01T00:50:00+08:00'),'2026-10-01 00:50')
 assert.equal(formatDateTime('invalid'),'暂无数据')
})

test('stored UTC timestamps group into Beijing days including month boundaries',()=>{
  assert.equal(dayKey('2026-09-30T16:00:00'), '2026-10-01')
  assert.equal(dayKey('2026-09-30T15:59:59Z'), '2026-09-30')
  assert.equal(dayKey('invalid'), null)
})
test('calendar includes correct padding, leap days and valid month navigation',()=>{
  const dates=monthCells('2024-02')
  assert.equal(dates[0],null);assert.equal(dates[2],null);assert.equal(dates[3],'2024-02-01')
  assert.equal(dates.filter(Boolean).length,29)
  assert.equal(monthCells('invalid').length,0)
})
test('calendar includes every module and distinguishes completion from unfinished activity',()=>{
 const data:any={assessments:[{id:'a1',started_at:'2026-10-01T01:00:00',status:'IN_PROGRESS',session_type:'COMPREHENSIVE'}],
 piano:[{id:'p1',started_at:'2026-10-01T02:00:00',completed_at:'2026-10-01T02:01:00',mode:'SINGLE_KEY_RHYTHM',input_source:'HUMAN_KEYBOARD'},
 {id:'p2',started_at:'2026-10-01T03:00:00',completed_at:'2026-10-01T03:01:00',mode:'SINGLE_KEY_RHYTHM',difficulty_before_json:{completion_status:'INTERRUPTED'}}],
 pose:[{id:'m1',started_at:'2026-10-01T04:00:00',exercise_type:'BALLET_TENDU'}],guided:[{id:'g1',started_at:'2026-10-01T05:00:00',status:'COMPLETED',source:'SEED_DEMO'}]}
 const rows=buildActivities(data),day=summarizeDays(rows)['2026-10-01']
 assert.equal(rows.length,5);assert.equal(day.assessments,1);assert.equal(day.completedTraining,2);assert.equal(day.unfinished,3)
 assert.deepEqual(rows.map(r=>r.kind).sort(),['assessment','guided','piano','piano','pose'])
 assert.equal(rows.find(r=>r.id==='g1')?.source,'SEED_DEMO')
})
