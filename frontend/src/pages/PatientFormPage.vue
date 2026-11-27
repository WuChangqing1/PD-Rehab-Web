<script setup lang="ts">
import { useAuthStore } from "@/stores/auth"
const auth = useAuthStore()
import { patientPayloadFor } from '@/staff/permissions'
import { t } from '@/i18n'
import {hasChoice,toggleChoice} from '@/patients/historyChoices'

import {computed,onBeforeUnmount,onMounted,reactive,ref,watch} from 'vue'
import {onBeforeRouteLeave,onBeforeRouteUpdate,useRoute,useRouter} from 'vue-router'
import {ElMessage,ElMessageBox} from 'element-plus'
import type {FormInstance,FormRules} from 'element-plus'
import {ArrowLeft,Check} from '@element-plus/icons-vue'
import {patientApi} from '@/api'
import {notifyError} from '@/api/client'
import type {Patient} from '@/types'
import {MEDICATION_LABELS} from '@/utils/format'
import {createPatientForm,loadPatientForm,buildPatientPatch,applyBirthday,applyAgeYears,type PatientForm} from '@/patients/editState'
import {MEDICATION_CATALOG_SOURCE,MEDICATION_CATALOG_VERSION,searchMedications} from '@/patients/medicationCatalog'
import {composeRehabHistory,emptyRehabAnswers,parseRehabHistory,type RehabAnswers,type RehabContact,type RehabFrequency,type RehabType} from '@/patients/rehabQuestionnaire'
const route=useRoute(),router=useRouter()
const patientId=computed(()=>typeof route.params.id==='string'?route.params.id:null)
const isEdit=computed(()=>!!patientId.value)
const formRef=ref<FormInstance>(),loading=ref(false),saving=ref(false),loadError=ref<string|null>(null)
const form=reactive<PatientForm>(createPatientForm()),snapshot=ref<PatientForm>(createPatientForm())
const loadedVersion=ref<string|null>(null),initialSex=ref('UNKNOWN')
const medicationChoices=computed({get:()=>String(form.current_medications??'').split('；').filter(Boolean),set:(values:string[])=>{form.current_medications=values.join('；')}})
const medicationQuery=ref('')
// Keep selected names in the option list so legacy or hand-typed drugs still
// render as tags even when they are not in the catalog.
const medicationOptions=computed(()=>[...new Set([...searchMedications(medicationQuery.value).map(item=>item.name),...medicationChoices.value])])
function filterMedicationOptions(query:string){medicationQuery.value=query}
const historyOptions=['高血压','糖尿病','血脂异常','骨质疏松']
const rehabText=ref(''),rehabState=reactive<RehabAnswers>(emptyRehabAnswers())
function resetRehab(raw:unknown){const parsed=parseRehabHistory(raw);rehabText.value=parsed.text;Object.assign(rehabState,parsed.answers)}
function syncRehab(){form.rehab_history=composeRehabHistory(rehabText.value,rehabState)}
function onRehabTextInput(value:unknown){rehabText.value=String(value??'');syncRehab()}
const rehabContact=computed({get:()=>rehabState.contact??'',set:(value:string)=>{rehabState.contact=(value||null) as RehabContact|null;syncRehab()}})
const rehabTypes=computed({get:()=>rehabState.types as string[],set:(values:string[])=>{rehabState.types=values as RehabType[];syncRehab()}})
const rehabFrequency=computed({get:()=>rehabState.frequency??'',set:(value:string)=>{rehabState.frequency=(value||null) as RehabFrequency|null;syncRehab()}})
const historyOpen=computed(()=>['medical_history','comorbidities','allergies','surgery_history','rehab_history'].some(key=>!!form[key]))
function choose(key:string,choice:string,value:unknown){form[key]=toggleChoice(form[key],choice,Boolean(value))}
function onBirthdayChange(value:string|null){applyBirthday(form,value)}
function onAgeChange(value:number|null|undefined){applyAgeYears(form,value)}
const dirty=computed(()=>Object.keys(buildPatientPatch(form,snapshot.value)).length>0)
let loadRequest=0
const rules=computed<FormRules>(()=>({name:[{required:true,whitespace:true,message:t('请输入姓名'),trigger:'blur'}]}))
async function loadPatient(){
 const id=patientId.value,request=++loadRequest
 loading.value=false;loadError.value=null;loadedVersion.value=null
 Object.assign(form,createPatientForm());resetRehab(form.rehab_history);snapshot.value={...form}
 if(!id)return
 loading.value=true
 try{
  const patient=await patientApi.get(id)
  if(request!==loadRequest||id!==patientId.value)return
  Object.assign(form,loadPatientForm(patient as unknown as Record<string,unknown>));resetRehab(form.rehab_history)
  snapshot.value={...form};loadedVersion.value=patient.updated_at;initialSex.value=patient.sex
 }catch(error){if(request===loadRequest)loadError.value=notifyError(error,'无法加载患者信息。').message}
 finally{if(request===loadRequest)loading.value=false}
}
async function submit(){
 if(saving.value||loading.value||loadError.value)return
 saving.value=true
 try{
  const valid=await formRef.value?.validate().catch(()=>false);if(!valid)return
  const payload=patientPayloadFor(auth.user?.role,buildPatientPatch(form,isEdit.value?snapshot.value:undefined))
  if(isEdit.value&&!Object.keys(payload).length){ElMessage.info(t('没有需要保存的修改'));return}
  if(isEdit.value){
   try{await ElMessageBox.confirm(t('确认要保存本次档案的修改内容？'),t('确认保存'),{confirmButtonText:t('确认保存'),cancelButtonText:t('取消'),type:'warning'})}catch{return}
   const updated=await patientApi.update(patientId.value!,{...payload,...(loadedVersion.value?{expected_updated_at:loadedVersion.value}:{})} as Partial<Patient>&{expected_updated_at?:string})
   loadedVersion.value=updated.updated_at;snapshot.value={...form};ElMessage.success(t('已保存编辑'))
   await router.push({name:'patient-detail',params:{id:updated.id}})
  }else{
   const created=await patientApi.create(payload as Partial<Patient>)
   snapshot.value={...form};ElMessage.success(t('已创建患者'))
   await router.push({name:'patient-detail',params:{id:created.id}})
  }
 }catch(error){notifyError(error,'保存失败，编辑内容已保留。')}
 finally{saving.value=false}
}
async function confirmLeave(){
 if(!dirty.value)return true
 if(saving.value)return false
 try{await ElMessageBox.confirm(t('有未保存的修改，确认离开并放弃这些修改？'),t('未保存的修改'),{confirmButtonText:t('放弃修改并离开'),cancelButtonText:t('继续编辑'),type:'warning'});return true}catch{return false}
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
    <el-button link class="pd-back" :icon="ArrowLeft" :disabled="saving" @click="cancelEditing">{{ $t(isEdit?'取消编辑':'返回患者档案') }}</el-button>
    <div class="pd-page-header">
      <div>
        <h1 class="pd-page-title">{{ $t(isEdit ? '编辑患者档案' : '新增患者') }}</h1>

      </div>
    </div>

    <el-alert v-if="loadError" type="error" :closable="false" show-icon :title="$t(loadError)" style="margin-bottom: 16px" />

    <!--
      `label-position` flips to top on a phone: a 130px label column plus an
      input does not fit in 375px, and squeezing both makes the input too narrow
      to type in.
    -->
    <el-form :validate-on-rule-change="false"
      ref="formRef"
      :model="form"
      :rules="rules"
      class="pd-patient-form"
      label-position="top"
      :disabled="loading || saving || !!loadError"
    >
      <div class="pd-card">
        <div class="pd-card-header"><span class="pd-card-title">{{ $t("基本信息") }}</span></div>
        <div class="pd-card-body pd-grid pd-grid-2">
          <el-form-item :label="$t('患者编号')" prop="hospital_number">
            <el-input v-if="isEdit" :model-value="form.hospital_number as string" readonly class="patient-number-readonly" :aria-label="$t('患者编号（只读）')"/><span v-else class="pd-muted">{{ $t("创建后由系统自动分配") }}</span>
          </el-form-item>
          <el-form-item :label="$t('姓名')" prop="name">
            <el-input v-model="form.name as string" :placeholder="$t('患者姓名')" />
          </el-form-item>
          <el-form-item :label="$t('性别')">
            <el-select v-model="form.sex as string" style="width: 100%">
              <el-option :label="$t('男')" value="MALE" />
              <el-option :label="$t('女')" value="FEMALE" />
              <el-option v-if="isEdit && initialSex==='OTHER'" :label="$t('其他（历史值）')" value="OTHER" />
              <el-option :label="$t('未知')" value="UNKNOWN" />
            </el-select>
          </el-form-item>
          <el-form-item :label="$t('出生日期')">
            <el-date-picker
              :model-value="form.birthday as string"
              @update:model-value="onBirthdayChange"
              type="date"
              :editable="true"
              :disabled="form.age_years!=null"
              value-format="YYYY-MM-DD"
              :placeholder="$t(form.age_years!=null?'已按年龄记录，清空年龄后可填写日期':'可直接输入 YYYY-MM-DD')"
              style="width: 100%"
            />
          </el-form-item>
          <el-form-item :label="$t('年龄（岁）')">
            <el-input-number
              :model-value="(form.age_years as number | null) ?? undefined"
              @update:model-value="onAgeChange"
              :min="0"
              :max="120"
              :precision="0"
              :controls="false"
              :disabled="!!form.birthday"
              :placeholder="$t('仅当不知道出生日期时填写')"
              style="width: 100%"
            />
            <div class="pd-muted" style="font-size:12px;line-height:1.4">{{ $t(form.birthday?'已有出生日期，年龄自动计算':'仅当不知道出生日期时填写，按录入当天记录') }}</div>
          </el-form-item>
          <el-form-item :label="$t('联系电话')">
            <el-input v-model="form.phone as string" />
          </el-form-item>
          <details class="wide-field form-details"><summary>{{ $t('补充联系方式') }}</summary><div class="pd-grid pd-grid-2">
          <el-form-item :label="$t('联系地址')">
            <el-input v-model="form.address as string" />
          </el-form-item>
          <el-form-item :label="$t('紧急联系人')">
            <el-input v-model="form.emergency_contact as string" />
          </el-form-item>
          <el-form-item :label="$t('紧急联系电话')">
            <el-input v-model="form.emergency_phone as string" />
          </el-form-item>
          </div></details>
        </div>
      </div>

      <div class="pd-card">
        <div class="pd-card-header"><span class="pd-card-title">{{ $t("帕金森相关信息") }}</span></div>
        <div class="pd-card-body pd-grid pd-grid-2">
          <el-form-item :label="$t('惯用手')">
            <el-select v-model="form.dominant_hand as string" style="width: 100%">
              <el-option :label="$t('左手')" value="LEFT" />
              <el-option :label="$t('右手')" value="RIGHT" />
              <el-option :label="$t('双手')" value="AMBIDEXTROUS" />
              <el-option :label="$t('未知')" value="UNKNOWN" />
            </el-select>
          </el-form-item>
          <el-form-item :label="$t('主要受累侧')">
            <el-select v-model="form.affected_side as string" style="width: 100%">
              <el-option :label="$t('左侧')" value="LEFT" />
              <el-option :label="$t('右侧')" value="RIGHT" />
              <el-option :label="$t('双侧')" value="BILATERAL" />
              <el-option :label="$t('未知')" value="UNKNOWN" />
            </el-select>
          </el-form-item>
          <el-form-item :label="$t('起病侧')">
            <el-select v-model="form.onset_side as string" style="width: 100%">
              <el-option :label="$t('左侧')" value="LEFT" />
              <el-option :label="$t('右侧')" value="RIGHT" />
              <el-option :label="$t('不明确/未记录')" value="UNKNOWN" />
            </el-select>
          </el-form-item>
          <el-form-item :label="$t('帕金森病首诊日期')">
            <el-date-picker
              v-model="form.diagnosis_date as string"
              type="date"
              :editable="true"
              value-format="YYYY-MM-DD"
              style="width: 100%"
            />
          </el-form-item>
          <el-form-item :label="$t('病程（年）')">
            <el-input-number v-model="form.disease_duration_years as number" :min="0" :max="100" :precision="1" style="width: 100%" />
          </el-form-item>
          <el-form-item :label="$t('当前分期')">
            <el-input v-model="form.current_stage as string" :placeholder="$t('如 H-Y 2 期（医护填写）')" />
          </el-form-item>
        </div>
      </div>

      <div class="pd-card"><div class="pd-card-header"><span class="pd-card-title">{{ $t('用药信息') }}</span></div><div class="pd-card-body pd-grid pd-grid-2">
          <el-form-item :label="$t('开关期状态')">
            <el-select v-model="form.medication_state as string" style="width: 100%">
              <el-option v-for="(label,value) in MEDICATION_LABELS" :key="value" :label="$t(label)" :value="value"/>
            </el-select>
          </el-form-item>
          <el-form-item :label="$t('用药情况')">
            <el-select v-model="form.medication_use_status as string" style="width: 100%">
              <el-option :label="$t('正在用药')" value="USING" />
              <el-option :label="$t('未用药')" value="NOT_USING" />
              <el-option :label="$t('不明确/未记录')" value="UNKNOWN" />
            </el-select>
          </el-form-item>
          <el-form-item :label="$t('帕金森相关用药')" class="wide-field">
            <el-select v-model="medicationChoices" multiple filterable allow-create default-first-option :reserve-keyword="false" :filter-method="filterMedicationOptions" :placeholder="$t('搜索常用药，或直接输入其他药物后回车')" style="width:100%"><el-option v-for="name in medicationOptions" :key="name" :label="name" :value="name" /></el-select>
            <div class="pd-muted" style="font-size:12px;line-height:1.4">{{ $t('常用药列表') }} · {{ MEDICATION_CATALOG_VERSION }} · {{ $t(MEDICATION_CATALOG_SOURCE) }}</div>
          </el-form-item>
          <el-form-item :label="$t('末次用药时间')">
            <el-date-picker
              v-model="form.last_medication_time as string"
              type="datetime"
              value-format="YYYY-MM-DDTHH:mm:ss"
              style="width: 100%"
            />
          </el-form-item>
      </div></div>

      <details class="pd-card form-details" :open="isEdit && historyOpen">
        <summary class="pd-card-header"><span class="pd-card-title">{{ $t('补充病史与康复经历') }}</span></summary>
        <div class="pd-card-body pd-grid pd-grid-2">
          <el-form-item :label="$t('既往病史')">
            <el-input v-model="form.medical_history as string" type="textarea" :rows="2" />
          </el-form-item>
          <el-form-item :label="$t('合并症')">
            <el-checkbox-group :model-value="historyOptions.filter(x=>hasChoice(form.comorbidities,x))" @update:model-value="(values:unknown[])=>historyOptions.forEach(x=>choose('comorbidities',x,values.includes(x)))"><el-checkbox v-for="choice in historyOptions" :key="choice" :value="choice">{{ $t(choice) }}</el-checkbox></el-checkbox-group>
            <el-input v-model="form.comorbidities as string" type="textarea" :rows="2" />
          </el-form-item>
          <el-form-item :label="$t('过敏史')">
            <el-input v-model="form.allergies as string" type="textarea" :rows="2" />
          </el-form-item>
          <el-form-item :label="$t('手术史')">
            <el-input v-model="form.surgery_history as string" type="textarea" :rows="2" />
          </el-form-item>
          <el-form-item :label="$t('康复史')">
            <el-input :model-value="rehabText" @update:model-value="onRehabTextInput" type="textarea" :rows="2" :placeholder="$t('可填写其他康复经历')" />
          </el-form-item>
          <el-form-item :label="$t('是否接触过康复')" class="wide-field">
            <el-radio-group v-model="rehabContact">
              <el-radio value="YES">{{ $t('是') }}</el-radio>
              <el-radio value="NO">{{ $t('否') }}</el-radio>
              <el-radio value="UNKNOWN">{{ $t('不清楚') }}</el-radio>
              <el-radio value="">{{ $t('未记录') }}</el-radio>
            </el-radio-group>
          </el-form-item>
          <el-form-item :label="$t('做过的康复训练类型')" class="wide-field">
            <el-checkbox-group v-model="rehabTypes">
              <el-checkbox value="HOME">{{ $t('居家锻炼') }}</el-checkbox>
              <el-checkbox value="HOSPITAL">{{ $t('医院康复训练') }}</el-checkbox>
              <el-checkbox value="OTHER">{{ $t('其他训练') }}</el-checkbox>
            </el-checkbox-group>
          </el-form-item>
          <el-form-item :label="$t('可记得的频次或时期')" class="wide-field">
            <el-radio-group v-model="rehabFrequency">
              <el-radio value="DAILY">{{ $t('每天') }}</el-radio>
              <el-radio value="WEEKLY">{{ $t('每周几次') }}</el-radio>
              <el-radio value="OCCASIONAL">{{ $t('偶尔') }}</el-radio>
              <el-radio value="UNKNOWN">{{ $t('记不清') }}</el-radio>
              <el-radio value="">{{ $t('未记录') }}</el-radio>
            </el-radio-group>
          </el-form-item>

        </div>
      </details>

      <div class="pd-card"><div class="pd-card-body">          <el-form-item :label="$t('备注')">
            <el-input v-model="form.doctor_notes as string" type="textarea" :rows="2" />
          </el-form-item></div></div>

      <div class="form-actions">
        <el-button :icon="ArrowLeft" :disabled="saving" @click="cancelEditing">{{ $t(isEdit?'取消编辑':'取消') }}</el-button>
        <el-button type="primary" :icon="Check" :loading="saving" :disabled="loading || !!loadError" @click="submit">
          {{ $t(isEdit ? '保存编辑' : '创建患者') }}
        </el-button>
      </div>
    </el-form>

  </div>
</template>

<style scoped>
.form-details summary { cursor:pointer; min-height:44px; padding-block:12px; font-weight:600; }
.form-details[open]>summary { margin-bottom:12px; }
.form-details .el-checkbox-group { width:100%; margin-bottom:8px; }

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
