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


test('new report labels have registered English translations and translated template controls',async()=>{
 const {readFileSync}=await import('node:fs')
 const {createTranslator}=await import('../src/i18n/core.ts')
 const dict=JSON.parse(readFileSync(new URL('../src/i18n/en-reports.json',import.meta.url),'utf8'))
 for(const key of ['导出 PDF 报告','全选日期（全部历史）','导出患者报告与数据','所选范围：','预计导出内容'])assert.ok(dict[key],key)
 const translate=createTranslator(dict)
 for(const key of Object.keys(dict)){assert.equal(translate(key,'zh-CN'),key);assert.ok(!/[\u3400-\u9fff]/.test(translate(key,'en')),key)}
 const index=readFileSync(new URL('../src/i18n/index.ts',import.meta.url),'utf8')
 assert.match(index,/import reports from '.\/en-reports.json'/)
 assert.match(index,/\.\.\.reports/)
 const source=readFileSync(new URL('../src/pages/FollowUpPage.vue',import.meta.url),'utf8')
 assert.ok(source.includes("$t('导出 PDF 报告')"))
 assert.ok(source.includes("$t('全选日期（全部历史）')"))
 assert.ok(!source.includes('>导出 PDF 报告 / 数据<'))
})


test('export calendars use separately labelled single-month popups for phone screens',async()=>{
 const {readFileSync}=await import('node:fs')
 const source=readFileSync(new URL('../src/pages/FollowUpPage.vue',import.meta.url),'utf8')
 const dialog=source.slice(source.indexOf('<el-dialog'),source.indexOf('</el-dialog>'))
 assert.ok(!dialog.includes('type="daterange"'))
 assert.equal((dialog.match(/type="date"/g)||[]).length,2)
 for(const id of ['report-start-date','report-end-date']){
  assert.ok(dialog.includes(`for="${id}"`));assert.ok(dialog.includes(`id="${id}"`))
 }
 assert.ok(dialog.includes('v-model="exportDates[0]"'))
 assert.ok(dialog.includes('v-model="exportDates[1]"'))
})
