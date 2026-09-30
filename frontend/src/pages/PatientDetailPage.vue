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
import { computed, onMounted, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { Edit, Lock } from '@element-plus/icons-vue'

import SelectedPatientBar from '@/components/SelectedPatientBar.vue'
import { assessmentApi, patientApi, pianoApi, poseApi } from '@/api'
import { notifyError } from '@/api/client'
import { usePatientContextStore } from '@/stores/patientContext'
import type { AssessmentSession, Patient, PianoSession, PoseSession } from '@/types'
import {
  AFFECTED_SIDE_LABELS,
  DOMINANT_HAND_LABELS,
  MEDICATION_LABELS,
  SEX_LABELS,
  formatDate,
  formatDateTime,
  medicationTagType,
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

const latestAssessment = computed(() => sessions.value[0] ?? null)
const latestPiano = computed(() => piano.value[0] ?? null)
const latestPose = computed(() => pose.value[0] ?? null)

async function load() {
  loading.value = true
  try {
    patient.value = await patientApi.get(patientId.value)
    const [assessmentPage, pianoPage, posePage] = await Promise.all([
      assessmentApi.listSessions(patientId.value, 1, 5),
      pianoApi.history(patientId.value, 5),
      poseApi.history(patientId.value, 5),
    ])
    sessions.value = assessmentPage.items
    piano.value = pianoPage.items
    pose.value = posePage.items
  } catch (error) {
    notifyError(error, '无法加载患者资料。')
  } finally {
    loading.value = false
  }
}

function edit() {
  router.push({ name: 'patient-edit', params: { id: patientId.value } })
}

/** The single way into an assessment: its own module, with the real session id. */
function openAssessment(session: AssessmentSession) {
  const name =
    session.session_type === 'MICRO_EXPRESSION_ONLY'
      ? 'assessment-micro-expression'
      : 'assessment-finger-tapping'
  router.push({ name, query: { patientId: patientId.value, sessionId: session.id } })
}

onMounted(async () => {
  await load()
  if (patient.value) await store.select(patient.value.id)
})
</script>

<template>
  <div v-loading="loading" class="pd-page">
    <div class="pd-page-header">
      <div>
        <h1 class="pd-page-title">
          {{ patient?.name ?? '患者资料' }}
          <el-tag v-if="patient" size="small" type="info" style="margin-left: 8px">
            {{ patient.hospital_number }}
          </el-tag>
        </h1>
        <p v-if="patient" class="pd-page-subtitle">
          {{ SEX_LABELS[patient.sex] ?? patient.sex }} ·
          {{ patient.age ?? '年龄暂无数据' }} ·
          主要受累侧 {{ AFFECTED_SIDE_LABELS[patient.affected_side] ?? patient.affected_side }} ·
          用药状态 {{ MEDICATION_LABELS[patient.medication_state] ?? patient.medication_state }}
        </p>
      </div>
      <el-button :icon="Edit" @click="edit">编辑资料</el-button>
    </div>

    <el-alert
      type="info"
      show-icon
      :closable="false"
      style="margin-bottom: 16px"
      title="要开始评估或训练，请从左侧对应模块进入"
      description="评估中心、康复训练会先请你选择患者。本页只显示资料与既往记录摘要。"
    />

    <SelectedPatientBar v-if="patient" :patient="patient" @change="load" />

    <!-- ------------------------------------------------ record -->
    <div class="pd-card">
      <div class="pd-card-header"><span class="pd-card-title">基本资料</span></div>
      <div class="pd-card-body">
        <dl v-if="patient" class="pd-kv">
          <dt>患者编号</dt><dd>{{ patient.hospital_number }}</dd>
          <dt>姓名</dt><dd>{{ patient.name }}</dd>
          <dt>性别</dt><dd>{{ SEX_LABELS[patient.sex] ?? patient.sex }}</dd>
          <dt>出生日期</dt><dd>{{ formatDate(patient.birthday) }}</dd>
          <dt>年龄</dt><dd>{{ patient.age ?? '暂无数据' }}</dd>
          <dt>联系电话</dt><dd>{{ patient.phone || '暂无数据' }}</dd>
          <dt>联系地址</dt><dd>{{ patient.address || '暂无数据' }}</dd>
          <dt>紧急联系人</dt><dd>{{ patient.emergency_contact || '暂无数据' }}</dd>
          <dt>紧急联系电话</dt><dd>{{ patient.emergency_phone || '暂无数据' }}</dd>
        </dl>
      </div>
    </div>

    <div class="pd-card">
      <div class="pd-card-header"><span class="pd-card-title">医疗资料</span></div>
      <div class="pd-card-body">
        <dl v-if="patient" class="pd-kv">
          <dt>惯用手</dt><dd>{{ DOMINANT_HAND_LABELS[patient.dominant_hand] ?? patient.dominant_hand }}</dd>
          <dt>主要受累侧</dt><dd>{{ AFFECTED_SIDE_LABELS[patient.affected_side] ?? patient.affected_side }}</dd>
          <dt>临床诊断日期</dt><dd>{{ formatDate(patient.diagnosis_date) }}</dd>
          <dt>病程</dt>
          <dd>{{ patient.disease_duration_years != null ? `${patient.disease_duration_years} 年` : '暂无数据' }}</dd>
          <dt>当前分期</dt><dd>{{ patient.current_stage || '暂无数据' }}</dd>
          <dt>用药状态</dt>
          <dd>
            <el-tag :type="medicationTagType(patient.medication_state)" size="small">
              {{ MEDICATION_LABELS[patient.medication_state] ?? patient.medication_state }}
            </el-tag>
          </dd>
          <dt>当前用药</dt><dd>{{ patient.current_medications || '暂无数据' }}</dd>
          <dt>末次用药时间</dt><dd>{{ formatDateTime(patient.last_medication_time) }}</dd>
          <dt>既往病史</dt><dd>{{ patient.medical_history || '暂无数据' }}</dd>
          <dt>合并症</dt><dd>{{ patient.comorbidities || '暂无数据' }}</dd>
          <dt>过敏史</dt><dd>{{ patient.allergies || '暂无数据' }}</dd>
          <dt>手术史</dt><dd>{{ patient.surgery_history || '暂无数据' }}</dd>
          <dt>康复史</dt><dd>{{ patient.rehab_history || '暂无数据' }}</dd>
          <dt>医生备注</dt><dd>{{ patient.doctor_notes || '暂无数据' }}</dd>
        </dl>
      </div>
    </div>

    <!-- --------------------------------------- recent activity summary -->
    <div class="pd-card">
      <div class="pd-card-header">
        <span class="pd-card-title">最近活动</span>
        <el-button link type="primary" @click="router.push({ name: 'follow-up', query: { patientId } })">
          查看全部记录
        </el-button>
      </div>
      <div class="pd-card-body">
        <el-table :data="[
          { label: '最近一次评估', at: latestAssessment?.started_at ?? null, note: latestAssessment ? (latestAssessment.status === 'COMPLETED' ? '已完成' : '进行中') : '' },
          { label: '最近一次钢琴训练', at: latestPiano?.started_at ?? null, note: latestPiano?.mode ?? '' },
          { label: '最近一次动作训练', at: latestPose?.started_at ?? null, note: latestPose?.exercise_type ?? '' },
        ]" size="small">
          <el-table-column label="项目" min-width="160">
            <template #default="{ row }">{{ row.label }}</template>
          </el-table-column>
          <el-table-column label="时间" width="180">
            <template #default="{ row }">{{ formatDateTime(row.at) }}</template>
          </el-table-column>
          <el-table-column label="说明">
            <template #default="{ row }">
              <span class="pd-muted">{{ row.note || '暂无记录' }}</span>
            </template>
          </el-table-column>
        </el-table>

        <div v-if="sessions.length" style="margin-top: 16px">
          <h4 style="margin: 0 0 8px; font-size: 14px">近期评估</h4>
          <el-table :data="sessions" size="small" empty-text="暂无评估记录">
            <el-table-column label="开始时间" width="180">
              <template #default="{ row }">{{ formatDateTime(row.started_at) }}</template>
            </el-table-column>
            <el-table-column label="状态" width="110">
              <template #default="{ row }">
                {{ row.status === 'COMPLETED' ? '已完成' : '进行中' }}
              </template>
            </el-table-column>
            <el-table-column label="操作" width="120" align="right">
              <template #default="{ row }">
                <!-- One action, carrying the real session id: the old pair of
                     buttons passed only the patient and landed on a dead end. -->
                <el-button link type="primary" @click="openAssessment(row)">
                  查看本次评估
                </el-button>
              </template>
            </el-table-column>
          </el-table>
        </div>
      </div>
    </div>

    <p class="pd-muted" style="font-size: 12px; display: flex; align-items: center; gap: 6px">
      <el-icon><Lock /></el-icon>
      删除患者请在「患者档案」列表操作，本页不提供删除入口。
    </p>
  </div>
</template>
