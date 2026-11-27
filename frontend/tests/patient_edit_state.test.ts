import test from 'node:test'
import assert from 'node:assert/strict'
import {createPatientForm,loadPatientForm,buildPatientPatch,applyBirthday,applyAgeYears,type PatientForm} from '../src/patients/editState.ts'
test('loading includes medication time, and an untouched form produces no patch',()=>{
 const form=loadPatientForm({name:'档案',sex:'OTHER',last_medication_time:'2026-10-17T01:30:00'})
 assert.equal(form.last_medication_time,'2026-10-17T09:30:00');assert.equal(form.sex,'OTHER')
 assert.deepEqual(buildPatientPatch(form,{...form}),{})
})
test('only changed fields are sent, clearing is null and zero is retained',()=>{
 const before=loadPatientForm({name:'档案',phone:'123',doctor_notes:'保留',disease_duration_years:1})
 assert.deepEqual(buildPatientPatch({...before,phone:'',disease_duration_years:0},before),{phone:null,disease_duration_years:0})
})
test('onset side starts unrecorded and is never copied from the affected side',()=>{
 assert.equal(createPatientForm().onset_side,'UNKNOWN')
 const form=loadPatientForm({affected_side:'LEFT'})
 assert.equal(form.onset_side,'UNKNOWN')
 assert.deepEqual(buildPatientPatch({...form,onset_side:'LEFT'},form),{onset_side:'LEFT'})
})
test('medication use status starts unrecorded and is independent of the on/off period',()=>{
 assert.equal(createPatientForm().medication_use_status,'UNKNOWN')
 const form=loadPatientForm({medication_state:'OFF'})
 assert.equal(form.medication_use_status,'UNKNOWN')
 assert.deepEqual(buildPatientPatch({...form,medication_use_status:'USING'},form),{medication_use_status:'USING'})
})
test('legacy medication text is never rewritten or lost',()=>{
 const legacy='左旋多巴/卡比多巴；某医院自备药'
 const loaded=loadPatientForm({current_medications:legacy})
 assert.equal(loaded.current_medications,legacy)
 assert.deepEqual(buildPatientPatch(loaded,loaded),{})
 const added=buildPatientPatch({...loaded,current_medications:legacy+'；普拉克索'},loaded)
 assert.deepEqual(added,{current_medications:legacy+'；普拉克索'})
})
test('age fallback and birthday stay mutually exclusive',()=>{
 const empty=createPatientForm();assert.equal(empty.age_years,null)
 const loaded=loadPatientForm({age_years:65,birthday:null});assert.equal(loaded.age_years,65)
 const patch=buildPatientPatch({...loaded,age_years:66},loaded);assert.deepEqual(patch,{age_years:66})
 const withAge:PatientForm={...createPatientForm(),age_years:65};applyBirthday(withAge,'1958-06-12')
 assert.equal(withAge.birthday,'1958-06-12');assert.equal(withAge.age_years,null)
 const withBirthday:PatientForm={...createPatientForm(),birthday:'1958-06-12'};applyAgeYears(withBirthday,70)
 assert.equal(withBirthday.age_years,70);assert.equal(withBirthday.birthday,null)
 applyAgeYears(withBirthday,undefined)
 assert.equal(withBirthday.age_years,null);assert.equal(withBirthday.birthday,null)
})
test('new form declares medication time and a changed time round trips through UTC',()=>{
 assert.equal(createPatientForm().last_medication_time,null)
 const before=createPatientForm();assert.equal(buildPatientPatch({...before,last_medication_time:'2026-10-17T09:30:00'},before).last_medication_time,'2026-10-17T01:30:00.000Z')
})
