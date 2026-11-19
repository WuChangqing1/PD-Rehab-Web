import test from 'node:test'
import assert from 'node:assert/strict'
import {reportPreset, reportParams} from '../src/followup/reportDates.ts'

test('China day shortcuts include today across year and UTC boundary',()=>{
 const now=new Date('2025-12-31T17:00:00Z')
 assert.deepEqual(reportPreset('7',now),['2025-12-26','2026-01-01'])
 assert.deepEqual(reportPreset('month',now),['2026-01-01','2026-01-01'])
 assert.deepEqual(reportPreset('all',now),[])
})
test('patient is required and invalid ranges never request exports',()=>{
 assert.throws(()=>reportParams(null,['2026-01-01','2026-01-02']))
 assert.throws(()=>reportParams('p',['2026-02-30','2026-03-01']))
 assert.throws(()=>reportParams('p',['2026-01-02','2026-01-01']))
 assert.deepEqual(reportParams('p',[]),{})
 assert.deepEqual(reportParams('p',['2025-12-31','2026-01-01']),{start_date:'2025-12-31',end_date:'2026-01-01'})
})
