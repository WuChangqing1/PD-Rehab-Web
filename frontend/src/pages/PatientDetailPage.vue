<script setup lang="ts">
/**
 * Patient detail with the six tabs required by spec V2 section 55:
 * 基本资料 / 最近评估 / 康复训练 / 功能评估 / 长期趋势 / 报告.
 */
import { computed, onMounted, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { Edit, Plus, TrendCharts } from '@element-plus/icons-vue'

import MedicalDisclaimer from '@/components/MedicalDisclaimer.vue'
import { assessmentApi, patientApi } from '@/api'
import { notifyError } from '@/api/client'
import type { AssessmentSession, Patient } from '@/types'
import {
  AFFECTED_SIDE_LABELS,
  DOMINANT_HAND_LABELS,
  MEDICATION_LABELS,
  SESSION_STATUS_LABELS,
  SESSION_TYPE_LABELS,
  SEX_LABELS,
  formatDate,
  formatDateTime,
  medicationTagType,
  sessionStatusTagType,
} from '@/utils/format'

const route = useRoute()
const router = useRouter()

const patientId = computed(() => String(route.params.id))
const loading = ref(false)
const patient = ref<Patient | null>(null)
const sessions = ref<AssessmentSession[]>([])
const activeTab = ref('profile')

async function load() {
  loading.value = true
  try {
    patient.value = await patientApi.get(patientId.value)
    const page = await assessmentApi.listSessions(patientId.value, 1, 20)
    sessions.value = page.items
  } catch (error) {
    notifyError(error, '无法加载患者详情。')
  } finally {
    loading.value = false
  }
}

function go(name: string) {
  router.push({
    name,
    params: { id: patientId.value },
    query: patient.value ? { patientName: patient.value.name } : undefined,
  })
}

onMounted(load)
</script>

<template>
  <div v-loading="loading" class="pd-page">
    <div class="pd-page-header">
      <div>
        <h1 class="pd-page-title">
          {{ patient?.name ?? '患者详情' }}
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
      <div class="header-actions">
        <el-button type="primary" :icon="Plus" @click="go('assessment')">开始综合评估</el-button>
        <el-button @click="go('training')">开始训练</el-button>
        <el-button :icon="Edit" @click="go('patient-edit')">编辑</el-button>
      </div>
    </div>

    <el-tabs v-model="activeTab" class="pd-card tabs-card">
      <el-tab-pane label="基本资料" name="profile">
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
      </el-tab-pane>

      <el-tab-pane label="最近评估" name="assessment">
        <div class="pd-card-body">
          <div class="tab-toolbar">
            <el-button type="primary" size="small" :icon="Plus" @click="go('assessment')">
              新建综合评估
            </el-button>
          </div>
          <el-table :data="sessions" size="small" empty-text="暂无评估记录">
            <el-table-column label="评估类型">
              <template #default="{ row }">
                {{ SESSION_TYPE_LABELS[row.session_type] ?? row.session_type }}
              </template>
            </el-table-column>
            <el-table-column label="用药状态" width="120">
              <template #default="{ row }">
                {{ MEDICATION_LABELS[row.medication_state] ?? row.medication_state }}
              </template>
            </el-table-column>
            <el-table-column label="状态" width="100">
              <template #default="{ row }">
                <el-tag :type="sessionStatusTagType(row.status)" size="small">
                  {{ SESSION_STATUS_LABELS[row.status] ?? row.status }}
                </el-tag>
              </template>
            </el-table-column>
            <el-table-column label="开始时间" width="170">
              <template #default="{ row }">{{ formatDateTime(row.started_at) }}</template>
            </el-table-column>
            <el-table-column label="完成时间" width="170">
              <template #default="{ row }">{{ formatDateTime(row.completed_at) }}</template>
            </el-table-column>
            <el-table-column label="操作" width="200">
              <template #default>
                <el-button link type="primary" @click="go('assessment-micro-expression')">微表情</el-button>
                <el-button link type="primary" @click="go('assessment-finger-tapping')">Finger Tapping</el-button>
              </template>
            </el-table-column>
          </el-table>
        </div>
      </el-tab-pane>

      <el-tab-pane label="康复训练" name="training">
        <div class="pd-card-body">
          <el-empty description="训练记录将在 Phase 5 / Phase 6 接入">
            <el-button type="primary" @click="go('training')">进入训练入口</el-button>
          </el-empty>
        </div>
      </el-tab-pane>

      <el-tab-pane label="功能评估" name="functional">
        <div class="pd-card-body">
          <el-empty description="功能测试数据将在 Phase 7 接入">
            <el-button type="primary" @click="go('functional-assessment')">进入功能评估</el-button>
          </el-empty>
        </div>
      </el-tab-pane>

      <el-tab-pane label="长期趋势" name="trends">
        <div class="pd-card-body">
          <el-empty description="趋势图将在 Phase 8 接入（需要足够的历史数据点）">
            <el-button type="primary" :icon="TrendCharts" @click="go('trends')">打开趋势页</el-button>
          </el-empty>
        </div>
      </el-tab-pane>

      <el-tab-pane label="报告" name="report">
        <div class="pd-card-body">
          <el-empty description="综合报告将在 Phase 8 接入">
            <el-button type="primary" @click="go('report')">打开报告页</el-button>
          </el-empty>
        </div>
      </el-tab-pane>
    </el-tabs>

    <MedicalDisclaimer />
  </div>
</template>

<style scoped>
.header-actions {
  display: flex;
  gap: 8px;
  flex-wrap: wrap;
}

.tabs-card {
  padding: 0 18px 18px;
}

.tab-toolbar {
  display: flex;
  justify-content: flex-end;
  margin-bottom: 12px;
}
</style>
