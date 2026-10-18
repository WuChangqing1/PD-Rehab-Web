import test from 'node:test'
import assert from 'node:assert/strict'
import {createPatientForm,loadPatientForm,buildPatientPatch} from '../src/patients/editState.ts'
test('loading includes medication time, and an untouched form produces no patch',()=>{
 const form=loadPatientForm({name:'档案',sex:'OTHER',last_medication_time:'2026-10-17T01:30:00'})
 assert.equal(form.last_medication_time,'2026-10-17T09:30:00');assert.equal(form.sex,'OTHER')
 assert.deepEqual(buildPatientPatch(form,{...form}),{})
})
test('only changed fields are sent, clearing is null and zero is retained',()=>{
 const before=loadPatientForm({name:'档案',phone:'123',doctor_notes:'保留',disease_duration_years:1})
 assert.deepEqual(buildPatientPatch({...before,phone:'',disease_duration_years:0},before),{phone:null,disease_duration_years:0})
})
test('new form declares medication time and a changed time round trips through UTC',()=>{
 assert.equal(createPatientForm().last_medication_time,null)
 const before=createPatientForm();assert.equal(buildPatientPatch({...before,last_medication_time:'2026-10-17T09:30:00'},before).last_medication_time,'2026-10-17T01:30:00.000Z')
})
