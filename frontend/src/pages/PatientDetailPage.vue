<script setup lang="ts">
/**
 * Patient record.
 *
 * This page is about *who the patient is*, not about doing things to them. It
 * used to carry a second copy of the whole navigation -- 开始综合评估 / 开始训练
 * buttons and four jump tabs -- so the same function could be entered from the
 * sidebar, the patient list and here, and none of them was canonical.
 *
 * Only two things remain: the record itself, and a summary of recent activity
 * that links to the one place each activity lives.
 */
import { computed, ref, watch, onBeforeUnmount } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ArrowLeft, Edit, ArrowUp, ArrowDown } from '@element-plus/icons-vue'

import { assessmentApi, patientApi, pianoApi, poseApi } from '@/api'
import OptionalValue from '@/components/OptionalValue.vue'
import { notifyError } from '@/api/client'
import { usePatientContextStore } from '@/stores/patientContext'
import { exerciseName } from '@/pose/exercises'
import { practiceLabel } from '@/piano/catalogue'
import type { AssessmentSession, Patient, PianoSession, PoseSession } from '@/types'
import {
  AFFECTED_SIDE_LABELS,
  DOMINANT_HAND_LABELS,
  MEDICATION_LABELS,
  SEX_LABELS,
  formatDate,
  formatDateTime,
  SESSION_STATUS_LABELS,
  medicationTagType,
  displayPatientName,
  displayHospitalNumber,
} from '@/utils/format'

const route = useRoute()
const router = useRouter()
const store = usePatientContextStore()

const patientId = computed(() => String(route.params.id))
const loading = ref(false)
const patient = ref<Patient | null>(null)
const sessions = ref<AssessmentSession[]>([])
const piano = ref<PianoSession[]>([])
const pose = ref<PoseSession[]>([])

const basicOpen=ref(true),medicalOpen=ref(true)
let loadRequest=0
const latestAssessment = computed(() => sessions.value[0] ?? null)
const latestPiano = computed(() => piano.value[0] ?? null)
const latestPose = computed(() => pose.value[0] ?? null)

async function load() {
  const id=patientId.value,request=++loadRequest
  loading.value = true;patient.value=null;sessions.value=[];piano.value=[];pose.value=[]
  try {
    const loaded=await patientApi.get(id)
    if(request!==loadRequest||id!==patientId.value)return
    patient.value=loaded
    const [assessmentPage, pianoPage, posePage] = await Promise.all([
      assessmentApi.listSessions(id, 1, 5),
      pianoApi.history(id, 5),
      poseApi.history(id, 5),
    ])
    if(request!==loadRequest||id!==patientId.value)return
    sessions.value = assessmentPage.items
    piano.value = pianoPage.items
    pose.value = posePage.items
  } catch (error) {
    if(request===loadRequest)notifyError(error, '无法加载患者资料。')
  } finally {
    if(request===loadRequest)loading.value = false
  }
}

function edit() {
  router.push({ name: 'patient-edit', params: { id: patientId.value } })
}

/** Historical entries always show saved results without restarting collection. */
function openAssessment(session: AssessmentSession) {
  router.push({ name:'assessment-results', params:{sessionId:session.id}, query:{patientId:patientId.value} })
}

watch(patientId,async () => {
  await load()
  if (patient.value) await store.select(patient.value.id)
},{immediate:true})
onBeforeUnmount(()=>loadRequest++)
const basicFields=computed(()=>patient.value?[
 ['患者编号',displayHospitalNumber(patient.value.hospital_number)],['姓名',displayPatientName(patient.value.name)],['性别',SEX_LABELS[patient.value.sex]??patient.value.sex],
 ['出生日期',patient.value.birthday?formatDate(patient.value.birthday):null],['年龄',patient.value.age],['联系电话',patient.value.phone],['联系地址',patient.value.address],['紧急联系人',patient.value.emergency_contact],['紧急联系电话',patient.value.emergency_phone]
 ]:[])
const medicalFields=computed(()=>patient.value?[
 ['惯用手',patient.value.dominant_hand==='UNKNOWN'?null:DOMINANT_HAND_LABELS[patient.value.dominant_hand]],['主要受累侧',patient.value.affected_side==='UNKNOWN'?null:AFFECTED_SIDE_LABELS[patient.value.affected_side]],
 ['临床诊断日期',patient.value.diagnosis_date?formatDate(patient.value.diagnosis_date):null],['病程',patient.value.disease_duration_years!=null?`${patient.value.disease_duration_years} 年`:null],['当前分期',patient.value.current_stage],
 ['用药状态',MEDICATION_LABELS[patient.value.medication_state]],['当前用药',patient.value.current_medications],['末次用药时间',patient.value.last_medication_time?formatDateTime(patient.value.last_medication_time):null],
 ['既往病史',patient.value.medical_history],['合并症',patient.value.comorbidities],['过敏史',patient.value.allergies],['手术史',patient.value.surgery_history],['康复史',patient.value.rehab_history],['医生备注',patient.value.doctor_notes]
 ]:[])
const activities=computed(()=>[
 {label:'最近一次评估',at:latestAssessment.value?.started_at??null,note:latestAssessment.value?SESSION_STATUS_LABELS[latestAssessment.value.status]:null},
 {label:'最近一次钢琴训练',at:latestPiano.value?.started_at??null,note:latestPiano.value?practiceLabel(latestPiano.value.mode,latestPiano.value.recipe_id):null},
 {label:'最近一次芭蕾动作训练',at:latestPose.value?.started_at??null,note:latestPose.value?exerciseName(latestPose.value.exercise_type):null},
])
</script>

<template>
  <div v-loading="loading" class="pd-page">
    <router-link class="pd-back" :to="{ name: 'patients' }">
      <el-icon><ArrowLeft /></el-icon>返回患者档案
    </router-link>

    <div class="pd-page-header">
      <div>
        <h1 class="pd-page-title">
          {{ displayPatientName(patient?.name) || '患者资料' }}
          <el-tag v-if="patient" size="small" type="info" style="margin-left: 8px">
            {{ displayHospitalNumber(patient.hospital_number) }}
          </el-tag>
        </h1>
        <p v-if="patient" class="pd-page-subtitle">
          {{ SEX_LABELS[patient.sex] ?? patient.sex }} ·
          <OptionalValue :value="patient.age"/> ·
          主要受累侧 <OptionalValue :value="patient.affected_side==='UNKNOWN'?null:AFFECTED_SIDE_LABELS[patient.affected_side]"/> ·
          用药状态 {{ MEDICATION_LABELS[patient.medication_state] ?? patient.medication_state }}
        </p>
      </div>
      <el-button v-if="patient && !patient.is_deleted" :icon="Edit" @click="edit">编辑资料</el-button>
    </div>

    <section class="pd-card patient-section">
      <div class="pd-card-header"><h2 class="pd-card-title">基本信息</h2><el-button link type="primary" :icon="basicOpen?ArrowUp:ArrowDown" :aria-expanded="basicOpen" aria-controls="patient-basic" :aria-label="basicOpen?'收起基本信息':'展开基本信息'" @click="basicOpen=!basicOpen">{{basicOpen?'收起':'展开'}}</el-button></div>
      <div v-show="basicOpen" id="patient-basic" class="pd-card-body"><dl class="record-values"><div v-for="[label,value] in basicFields" :key="String(label)"><dt>{{label}}</dt><dd><OptionalValue :value="value"/></dd></div></dl></div>
    </section>
    <section class="pd-card patient-section">
      <div class="pd-card-header"><h2 class="pd-card-title">医疗资料</h2><el-button link type="primary" :icon="medicalOpen?ArrowUp:ArrowDown" :aria-expanded="medicalOpen" aria-controls="patient-medical" :aria-label="medicalOpen?'收起医疗资料':'展开医疗资料'" @click="medicalOpen=!medicalOpen">{{medicalOpen?'收起':'展开'}}</el-button></div>
      <div v-show="medicalOpen" id="patient-medical" class="pd-card-body"><dl class="record-values"><div v-for="[label,value] in medicalFields" :key="String(label)"><dt>{{label}}</dt><dd><el-tag v-if="label==='用药状态' && patient" :type="medicationTagType(patient.medication_state)">{{value}}</el-tag><OptionalValue v-else :value="value"/></dd></div></dl></div>
    </section>
    <section class="pd-card patient-section">
      <div class="pd-card-header"><h2 class="pd-card-title">最近活动</h2><el-button link type="primary" @click="router.push({name:'follow-up',query:{patientId}})">查看全部记录</el-button></div>
      <div class="pd-card-body">
        <div class="desktop-only pd-table-scroll"><el-table :data="activities" style="width:100%"><el-table-column prop="label" label="项目" min-width="180"/><el-table-column label="时间" min-width="170"><template #default="{row}"><OptionalValue :value="row.at?formatDateTime(row.at):null"/></template></el-table-column><el-table-column label="说明" min-width="140"><template #default="{row}"><OptionalValue :value="row.note"/></template></el-table-column></el-table></div>
        <div class="mobile-only"><article v-for="activity in activities" :key="activity.label" class="record-item"><strong>{{activity.label}}</strong><p><OptionalValue :value="activity.at?formatDateTime(activity.at):null"/></p><OptionalValue :value="activity.note"/></article></div>
      </div>
    </section>
    <section class="pd-card patient-section">
      <div class="pd-card-header"><h2 class="pd-card-title">近期评估</h2></div>
      <div class="pd-card-body">
        <div class="desktop-only pd-table-scroll"><el-table :data="sessions" style="width:100%" empty-text="暂无评估记录"><el-table-column label="开始时间" min-width="180"><template #default="{row}"><OptionalValue :value="row.started_at?formatDateTime(row.started_at):null"/></template></el-table-column><el-table-column label="状态" min-width="110"><template #default="{row}">{{SESSION_STATUS_LABELS[row.status]}}</template></el-table-column><el-table-column label="操作" min-width="150" align="right"><template #default="{row}"><el-button link type="primary" @click="openAssessment(row)">查看本次评估</el-button></template></el-table-column></el-table></div>
        <div class="mobile-only"><div v-if="!sessions.length" class="pd-empty">暂无评估记录</div><article v-for="session in sessions" :key="session.id" class="record-item"><strong><OptionalValue :value="session.started_at?formatDateTime(session.started_at):null"/></strong><p>{{SESSION_STATUS_LABELS[session.status]}}</p><el-button link type="primary" @click="openAssessment(session)">查看本次评估</el-button></article></div>
      </div>
    </section>
  </div>
</template>

<style scoped>
.patient-section { width:100%; min-width:0; }
.patient-section .pd-card-header { min-height:64px; }
.patient-section h2 { margin:0; }
.record-values { display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:12px 28px;margin:0; }
.record-values>div { display:grid;grid-template-columns:130px minmax(0,1fr);gap:12px;align-items:start;min-width:0; }
.record-values dt { color:var(--pd-text-secondary);font-size:14px; }
.record-values dd { margin:0;font-size:14px;overflow-wrap:anywhere;white-space:pre-wrap; }
.record-item { padding:14px 0;border-bottom:1px solid var(--pd-border);font-size:14px; }
.record-item:last-child { border-bottom:0; }
.record-item p { margin:6px 0;color:var(--pd-text-secondary); }
@media(max-width:900px) { .record-values { grid-template-columns:1fr; } }
@media(max-width:767px) { .record-values>div { grid-template-columns:105px minmax(0,1fr); } .patient-section .pd-card-header { min-height:60px; } }
</style>
