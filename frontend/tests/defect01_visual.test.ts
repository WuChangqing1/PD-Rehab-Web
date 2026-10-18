import test from 'node:test'
import assert from 'node:assert/strict'
import {readFileSync} from 'node:fs'
import {displayOptionalValue,MEDICATION_LABELS} from '../src/utils/format.ts'
const source=(path:string)=>readFileSync(new URL('../src/'+path,import.meta.url),'utf8')
test('ordinary missing values use a dash while zero and false remain values',()=>{
 for(const value of [null,undefined,'','  ','UNKNOWN'])assert.equal(displayOptionalValue(value),'—')
 assert.equal(displayOptionalValue(0),'0');assert.equal(displayOptionalValue(false),'false')
 assert.equal(MEDICATION_LABELS.UNKNOWN,'未知')
})
test('medication labels consistently use readable half-width parentheses',()=>{
 assert.equal(MEDICATION_LABELS.ON,'开期 (ON)');assert.equal(MEDICATION_LABELS.OFF,'关期 (OFF)')
})
test('desktop collapse control belongs to sidebar and conveys its state',()=>{
 const layout=source('layouts/MainLayout.vue'),aside=layout.match(/<el-aside[\s\S]*?<\/el-aside>/)![0]
 assert.match(aside,/pd-sidebar-toggle/);assert.match(aside,/:aria-expanded="!collapsed"/)
 assert.match(aside,/:icon="collapsed \? Expand : Fold"/)
 for(const header of layout.matchAll(/<el-header[\s\S]*?<\/el-header>/g))assert.ok(!header[0].includes('collapsed = !collapsed'))
})
