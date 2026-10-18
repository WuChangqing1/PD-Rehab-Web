/** Form snapshots preserve unchanged fields; only deliberate edits reach PATCH. */
export type PatientForm=Record<string,unknown>
export function createPatientForm():PatientForm {
 return {hospital_number:'',name:'',sex:'UNKNOWN',birthday:null,phone:'',address:'',emergency_contact:'',emergency_phone:'',
 dominant_hand:'UNKNOWN',affected_side:'UNKNOWN',diagnosis_date:null,disease_duration_years:null,current_stage:'',
 current_medications:'',last_medication_time:null,medication_state:'UNKNOWN',medical_history:'',comorbidities:'',allergies:'',surgery_history:'',rehab_history:'',doctor_notes:''}
}
export function loadPatientForm(patient:Record<string,unknown>):PatientForm {
 const form=createPatientForm()
 for(const key of Object.keys(form))if(patient[key]!==undefined)form[key]=patient[key]
 const time=form.last_medication_time
 if(typeof time==='string'&&time){
  const date=new Date(/(?:Z|[+-]\d{2}:?\d{2})$/i.test(time)?time:time+'Z')
  if(Number.isFinite(date.getTime()))form.last_medication_time=new Date(date.getTime()+480*60_000).toISOString().slice(0,19)
 }
 return form
}
function normalize(key:string,value:unknown):unknown {
 if(value==null||(typeof value==='string'&&!value.trim()))return null
 if(key==='last_medication_time'&&typeof value==='string'){
  const date=new Date(/(?:Z|[+-]\d{2}:?\d{2})$/i.test(value)?value:value+'+08:00')
  return Number.isFinite(date.getTime())?date.toISOString():value
 }
 return value
}
export function buildPatientPatch(form:PatientForm,snapshot?:PatientForm):PatientForm {
 const payload:PatientForm={}
 for(const key of Object.keys(createPatientForm())){
  if(key === 'hospital_number')continue
  const value=normalize(key,form[key])
  if(!snapshot||value!==normalize(key,snapshot[key]))payload[key]=value
 }
 return payload
}
