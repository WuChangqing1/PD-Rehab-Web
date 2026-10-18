import test from 'node:test'
import assert from 'node:assert/strict'
import {readFileSync} from 'node:fs'
import {displayHospitalNumber} from '../src/utils/format.ts'
test('displayed patient identifiers retain their distinguishing prefixes',()=>{
 assert.equal(displayHospitalNumber('DEMO-0001'),'DEMO-0001')
 assert.notEqual(displayHospitalNumber('DEMO-0001'),displayHospitalNumber('0001'))
 assert.equal(displayHospitalNumber('P000042'),'P000042')
})
test('ordinary patient creation has no editable identifier and edits show it read-only',()=>{
 const source=readFileSync(new URL('../src/pages/PatientFormPage.vue',import.meta.url),'utf8')
 assert.ok(!source.includes('v-model="form.hospital_number'))
 assert.match(source,/readonly/)
 assert.match(readFileSync(new URL('../src/patients/editState.ts',import.meta.url),'utf8'),/key === 'hospital_number'/)
})
