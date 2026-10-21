<script setup lang="ts">
import {computed,onBeforeUnmount,onMounted,reactive,ref,watch} from 'vue'
import {onBeforeRouteLeave,onBeforeRouteUpdate,useRoute,useRouter} from 'vue-router'
import {ElMessage,ElMessageBox} from 'element-plus'
import type {FormInstance,FormRules} from 'element-plus'
import {ArrowLeft,Check} from '@element-plus/icons-vue'
import {patientApi} from '@/api'
import {notifyError} from '@/api/client'
import type {Patient} from '@/types'
import {MEDICATION_LABELS} from '@/utils/format'
import {createPatientForm,loadPatientForm,buildPatientPatch,type PatientForm} from '@/patients/editState'
const route=useRoute(),router=useRouter()
const patientId=computed(()=>typeof route.params.id==='string'?route.params.id:null)
const isEdit=computed(()=>!!patientId.value)
const formRef=ref<FormInstance>(),loading=ref(false),saving=ref(false),loadError=ref<string|null>(null)
const form=reactive<PatientForm>(createPatientForm()),snapshot=ref<PatientForm>(createPatientForm())
const loadedVersion=ref<string|null>(null),initialSex=ref('UNKNOWN')
const dirty=computed(()=>Object.keys(buildPatientPatch(form,snapshot.value)).length>0)
let loadRequest=0
const rules:FormRules={name:[{required:true,whitespace:true,message:'请输入姓名',trigger:'blur'}]}
async function loadPatient(){
 const id=patientId.value,request=++loadRequest
 loading.value=false;loadError.value=null;loadedVersion.value=null
 Object.assign(form,createPatientForm());snapshot.value={...form}
 if(!id)return
 loading.value=true
 try{
  const patient=await patientApi.get(id)
  if(request!==loadRequest||id!==patientId.value)return
  Object.assign(form,loadPatientForm(patient as unknown as Record<string,unknown>))
  snapshot.value={...form};loadedVersion.value=patient.updated_at;initialSex.value=patient.sex
 }catch(error){if(request===loadRequest)loadError.value=notifyError(error,'无法加载患者信息。').message}
 finally{if(request===loadRequest)loading.value=false}
}
async function submit(){
 if(saving.value||loading.value||loadError.value)return
 saving.value=true
 try{
  const valid=await formRef.value?.validate().catch(()=>false);if(!valid)return
  const payload=buildPatientPatch(form,isEdit.value?snapshot.value:undefined)
  if(isEdit.value&&!Object.keys(payload).length){ElMessage.info('没有需要保存的修改');return}
  if(isEdit.value){
   try{await ElMessageBox.confirm('确认要保存本次档案的修改内容？','确认保存',{confirmButtonText:'确认保存',cancelButtonText:'取消',type:'warning'})}catch{return}
   const updated=await patientApi.update(patientId.value!,{...payload,...(loadedVersion.value?{expected_updated_at:loadedVersion.value}:{})} as Partial<Patient>&{expected_updated_at?:string})
   loadedVersion.value=updated.updated_at;snapshot.value={...form};ElMessage.success('已保存编辑')
   await router.push({name:'patient-detail',params:{id:updated.id}})
  }else{
   const created=await patientApi.create(payload as Partial<Patient>)
   snapshot.value={...form};ElMessage.success('已创建患者')
   await router.push({name:'patient-detail',params:{id:created.id}})
  }
 }catch(error){notifyError(error,'保存失败，编辑内容已保留。')}
 finally{saving.value=false}
}
async function confirmLeave(){
 if(!dirty.value)return true
 if(saving.value)return false
 try{await ElMessageBox.confirm('有未保存的修改，确认离开并放弃这些修改？','未保存的修改',{confirmButtonText:'放弃修改并离开',cancelButtonText:'继续编辑',type:'warning'});return true}catch{return false}
}
function cancelEditing(){if(!saving.value)router.push(isEdit.value&&!loadError.value?{name:'patient-detail',params:{id:patientId.value}}:{name:'patients'})}
function beforeUnload(event:BeforeUnloadEvent){if(dirty.value){event.preventDefault();event.returnValue=''}}
onBeforeRouteLeave(confirmLeave);onBeforeRouteUpdate(confirmLeave)
watch(patientId,()=>void loadPatient())
onMounted(()=>{void loadPatient();window.addEventListener('beforeunload',beforeUnload)})
onBeforeUnmount(()=>{loadRequest++;window.removeEventListener('beforeunload',beforeUnload)})
</script>

<template>
  <div v-loading="loading" class="pd-page">
    <el-button link class="pd-back" :icon="ArrowLeft" :disabled="saving" @click="cancelEditing">{{isEdit?'取消编辑':'返回患者档案'}}</el-button>
    <div class="pd-page-header">
      <div>
        <h1 class="pd-page-title">{{ isEdit ? '编辑患者档案' : '新增患者' }}</h1>

      </div>
    </div>

    <el-alert v-if="loadError" type="error" :closable="false" show-icon :title="loadError" style="margin-bottom: 16px" />

    <!--
      `label-position` flips to top on a phone: a 130px label column plus an
      input does not fit in 375px, and squeezing both makes the input too narrow
      to type in.
    -->
    <el-form
      ref="formRef"
      :model="form"
      :rules="rules"
      class="pd-patient-form"
      label-position="top"
      :disabled="loading || saving || !!loadError"
    >
      <div class="pd-card">
        <div class="pd-card-header"><span class="pd-card-title">基本信息</span></div>
        <div class="pd-card-body pd-grid pd-grid-2">
          <el-form-item label="患者编号" prop="hospital_number">
            <el-input v-if="isEdit" :model-value="form.hospital_number as string" readonly class="patient-number-readonly" aria-label="患者编号（只读）"/><span v-else class="pd-muted">创建后由系统自动分配</span>
          </el-form-item>
          <el-form-item label="姓名" prop="name">
            <el-input v-model="form.name as string" placeholder="患者姓名" />
          </el-form-item>
          <el-form-item label="性别">
            <el-select v-model="form.sex as string" style="width: 100%">
              <el-option label="男" value="MALE" />
              <el-option label="女" value="FEMALE" />
              <el-option v-if="isEdit && initialSex==='OTHER'" label="其他（历史值）" value="OTHER" />
              <el-option label="未知" value="UNKNOWN" />
            </el-select>
          </el-form-item>
          <el-form-item label="出生日期">
            <el-date-picker
              v-model="form.birthday as string"
              type="date"
              value-format="YYYY-MM-DD"
              placeholder="选择日期"
              style="width: 100%"
            />
          </el-form-item>
          <el-form-item label="联系电话">
            <el-input v-model="form.phone as string" />
          </el-form-item>
          <el-form-item label="联系地址">
            <el-input v-model="form.address as string" />
          </el-form-item>
          <el-form-item label="紧急联系人">
            <el-input v-model="form.emergency_contact as string" />
          </el-form-item>
          <el-form-item label="紧急联系电话">
            <el-input v-model="form.emergency_phone as string" />
          </el-form-item>
        </div>
      </div>

      <div class="pd-card">
        <div class="pd-card-header"><span class="pd-card-title">帕金森相关信息</span></div>
        <div class="pd-card-body pd-grid pd-grid-2">
          <el-form-item label="惯用手">
            <el-select v-model="form.dominant_hand as string" style="width: 100%">
              <el-option label="左手" value="LEFT" />
              <el-option label="右手" value="RIGHT" />
              <el-option label="双手" value="AMBIDEXTROUS" />
              <el-option label="未知" value="UNKNOWN" />
            </el-select>
          </el-form-item>
          <el-form-item label="主要受累侧">
            <el-select v-model="form.affected_side as string" style="width: 100%">
              <el-option label="左侧" value="LEFT" />
              <el-option label="右侧" value="RIGHT" />
              <el-option label="双侧" value="BILATERAL" />
              <el-option label="未知" value="UNKNOWN" />
            </el-select>
          </el-form-item>
          <el-form-item label="临床诊断日期">
            <el-date-picker
              v-model="form.diagnosis_date as string"
              type="date"
              value-format="YYYY-MM-DD"
              style="width: 100%"
            />
          </el-form-item>
          <el-form-item label="病程（年）">
            <el-input-number v-model="form.disease_duration_years as number" :min="0" :max="100" :precision="1" style="width: 100%" />
          </el-form-item>
          <el-form-item label="当前分期">
            <el-input v-model="form.current_stage as string" placeholder="如 H-Y 2 期（医生填写）" />
          </el-form-item>
          <el-form-item label="用药状态">
            <el-select v-model="form.medication_state as string" style="width: 100%">
              <el-option v-for="(label,value) in MEDICATION_LABELS" :key="value" :label="label" :value="value"/>
            </el-select>
          </el-form-item>
          <el-form-item label="当前用药" class="wide-field">
            <el-input v-model="form.current_medications as string" type="textarea" :rows="2" />
          </el-form-item>
          <el-form-item label="末次用药时间">
            <el-date-picker
              v-model="form.last_medication_time as string"
              type="datetime"
              value-format="YYYY-MM-DDTHH:mm:ss"
              style="width: 100%"
            />
          </el-form-item>
        </div>
      </div>

      <div class="pd-card">
        <div class="pd-card-header"><span class="pd-card-title">其他医疗信息</span></div>
        <div class="pd-card-body pd-grid pd-grid-2">
          <el-form-item label="既往病史">
            <el-input v-model="form.medical_history as string" type="textarea" :rows="2" />
          </el-form-item>
          <el-form-item label="合并症">
            <el-input v-model="form.comorbidities as string" type="textarea" :rows="2" />
          </el-form-item>
          <el-form-item label="过敏史">
            <el-input v-model="form.allergies as string" type="textarea" :rows="2" />
          </el-form-item>
          <el-form-item label="手术史">
            <el-input v-model="form.surgery_history as string" type="textarea" :rows="2" />
          </el-form-item>
          <el-form-item label="康复史">
            <el-input v-model="form.rehab_history as string" type="textarea" :rows="2" />
          </el-form-item>
          <el-form-item label="医生备注">
            <el-input v-model="form.doctor_notes as string" type="textarea" :rows="2" />
          </el-form-item>
        </div>
      </div>

      <div class="form-actions">
        <el-button :icon="ArrowLeft" :disabled="saving" @click="cancelEditing">{{isEdit?'取消编辑':'取消'}}</el-button>
        <el-button type="primary" :icon="Check" :loading="saving" :disabled="loading || !!loadError" @click="submit">
          {{ isEdit ? '保存编辑' : '创建患者' }}
        </el-button>
      </div>
    </el-form>

  </div>
</template>

<style scoped>
.pd-patient-form :deep(.el-input-number) { height:var(--pd-control-height); }
.pd-patient-form :deep(.el-form-item) { margin-bottom:0; align-self:start; min-width:0; }
.pd-patient-form :deep(.el-form-item__label) { line-height:24px; padding:0; margin-bottom:8px; }
.pd-patient-form :deep(.el-form-item__content) { min-width:0; min-height:var(--pd-control-height); }
.pd-patient-form :deep(.pd-grid) { row-gap:28px; align-items:start; }
.wide-field { grid-column:1/-1; }
.form-actions :deep(.el-button) { margin-left:0; min-width:128px; height:44px; }
@media(max-width:767px) { .form-actions { position:sticky; bottom:0; padding:12px 0; background:var(--pd-bg); } .form-actions :deep(.el-button) { flex:1; min-width:0; } }

.form-actions {
  display: flex;
  justify-content: flex-end;
  gap: 12px;
  margin-top: 20px;
}
</style>
