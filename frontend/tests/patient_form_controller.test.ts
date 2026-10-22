import test from 'node:test'
import assert from 'node:assert/strict'
import {readFileSync} from 'node:fs'
import {createRequire} from 'node:module'
import * as state from '../src/patients/editState.ts'
const require=createRequire(import.meta.url),vue=require('vue'),ts=require('typescript')
function fixture(options:any={}){
 const patches:any[]=[],confirmations:string[]=[],moves:any[]=[]
 const patient={...state.createPatientForm(),id:'qa',name:'验收',sex:'OTHER',hospital_number:'P000001',last_medication_time:'2026-10-17T01:30:00',updated_at:'2026-10-17T00:00:00'}
 const modules:any={vue:{...vue,onMounted:()=>{},onBeforeUnmount:()=>{},watch:()=>{}},'vue-router':{useRoute:()=>({params:{id:'qa'}}),useRouter:()=>({push:async(v:any)=>moves.push(v),back:()=>{}}),onBeforeRouteLeave:()=>{},onBeforeRouteUpdate:()=>{}},
 'element-plus':{ElMessage:{success:()=>{},info:()=>{}},ElMessageBox:{confirm:async(message:string)=>{confirmations.push(message);if(options.confirm)return options.confirm()}}},
 '@/api':{patientApi:{get:async()=>{if(options.loadFail)throw Error('offline');return patient},update:async(_id:string,payload:any)=>{patches.push(payload);if(options.fail)throw Error('offline');return patient}}},
 '@/api/client':{notifyError:()=>({message:'离线'})},'@/patients/editState':state,'@/utils/format':{MEDICATION_LABELS:{}}}
 const path=process.env.PATIENT_FORM_BASELINE??new URL('../src/pages/PatientFormPage.vue',import.meta.url)
 const script=readFileSync(path,'utf8').match(/<script setup lang="ts">([\s\S]*?)<\/script>/)![1]
 const output:any={};const compiled=ts.transpileModule(script+'\nexports.page={form,formRef,submit,loadPatient,saving,loadError,confirmLeave:typeof confirmLeave==="undefined"?null:confirmLeave}',{compilerOptions:{module:ts.ModuleKind.CommonJS,target:ts.ScriptTarget.ES2022}}).outputText
 new Function('require','exports',compiled)((id:string)=>modules[id]??(id==='@/i18n'?{t:(value:unknown)=>value}:{}),output)
 output.page.formRef.value={validate:async()=>true}
 return {...output.page,patches,confirmations,moves}
}
test('unchanged edit does not confirm or send PATCH',async()=>{
 const page=fixture();await page.loadPatient();await page.submit()
 assert.equal(page.patches.length,0);assert.equal(page.confirmations.length,0)
})
test('cancelled save confirmation preserves edits without PATCH',async()=>{
 const page=fixture({confirm:async()=>{throw 'cancel'}});await page.loadPatient();page.form.phone='456';await page.submit()
 assert.equal(page.patches.length,0);assert.equal(page.form.phone,'456');assert.equal(page.saving.value,false)
})
test('confirmed save sends only changed fields plus version and ignores double clicks',async()=>{
 let resolve:any;const page=fixture({confirm:()=>new Promise(done=>resolve=done)})
 await page.loadPatient();page.form.phone='456';const first=page.submit();await Promise.resolve();await Promise.resolve()
 await page.submit();resolve();await first
 assert.equal(page.patches.length,1);assert.deepEqual(Object.keys(page.patches[0]).sort(),['expected_updated_at','phone'])
 assert.equal(page.moves.length,1)
})
test('failed save and cancelled navigation retain current edit content',async()=>{
 const page=fixture({fail:true});await page.loadPatient();page.form.phone='456';await page.submit()
 assert.equal(page.form.phone,'456');assert.equal(page.moves.length,0);assert.equal(page.saving.value,false)
})
test('a failed edit load cannot submit empty replacement data',async()=>{
 const page=fixture({loadFail:true});await page.loadPatient();await page.submit();assert.equal(page.patches.length,0)
})
