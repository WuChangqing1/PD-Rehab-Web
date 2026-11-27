import {test} from 'node:test'
import assert from 'node:assert/strict'
import {MEDICATION_CATALOG,MEDICATION_CATALOG_SOURCE,MEDICATION_CATALOG_VERSION,searchMedications} from '../src/patients/medicationCatalog.ts'

test('medication catalog has stable unique codes and non-empty names',()=>{
 assert.ok(MEDICATION_CATALOG_VERSION)
 assert.ok(MEDICATION_CATALOG_SOURCE)
 assert.equal(new Set(MEDICATION_CATALOG.map(item=>item.code)).size,MEDICATION_CATALOG.length)
 assert.equal(new Set(MEDICATION_CATALOG.map(item=>item.name)).size,MEDICATION_CATALOG.length)
 for(const item of MEDICATION_CATALOG){
  assert.match(item.code,/^[A-Z][A-Z0-9_]*$/)
  assert.ok(item.name.trim().length>0)
 }
})

test('catalog search matches generic names and aliases',()=>{
 assert.equal(searchMedications('').length,MEDICATION_CATALOG.length)
 assert.deepEqual(searchMedications('普拉克索').map(item=>item.name),['普拉克索'])
 assert.deepEqual(searchMedications('卡比多巴').map(item=>item.name),['左旋多巴/卡比多巴'])
 assert.deepEqual(searchMedications('多巴').map(item=>item.name),['左旋多巴/卡比多巴'])
 assert.deepEqual(searchMedications('  ').length,MEDICATION_CATALOG.length)
 assert.deepEqual(searchMedications('不存在的药名'),[])
})
