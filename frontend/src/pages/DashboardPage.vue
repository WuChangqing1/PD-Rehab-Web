<script setup lang="ts">
/**
 * Dashboard: patient and activity counts, recent items, and the true model
 * readiness state.
 *
 * Model status is shown exactly as the backend reports it. A component that is
 * not configured is labelled 未配置 rather than hidden or shown as ready.
 */
import { onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import { ElTag } from 'element-plus'
import { Refresh } from '@element-plus/icons-vue'

import MedicalDisclaimer from '@/components/MedicalDisclaimer.vue'
import { systemApi } from '@/api'
import { notifyError } from '@/api/client'
import type { DashboardResponse, ModelSummaryItem } from '@/types'
import {
  AFFECTED_SIDE_LABELS,
  MEDICATION_LABELS,
  MODEL_STATE_LABELS,
  SESSION_TYPE_LABELS,
  formatDateTime,
  modelStateTagType,
} from '@/utils/format'

const router = useRouter()
const loading = ref(false)
const data = ref<DashboardResponse | null>(null)
const models = ref<ModelSummaryItem[]>([])

const MODEL_LABELS: Record<string, string> = {
  micro_expression_model: '微表情 / AI 模型',
  finger_tapping: 'Finger Tapping',
  mediapipe_hand_landmarker: 'MediaPipe Hand Landmarker',
  mediapipe_pose: 'MediaPipe Pose',
}

async function load() {
  loading.value = true
  try {
    data.value = await systemApi.dashboard()
    models.value = data.value.model_status.models
  } catch (error) {
    notifyError(error, '无法加载工作台数据。')
  } finally {
    loading.value = false
  }
}

function openPatient(id: string) {
  router.push({ name: 'patient-detail', params: { id } })
}

onMounted(load)
</script>

<template>
  <div v-loading="loading" class="pd-page">
    <div class="pd-page-header">
      <div>
        <h1 class="pd-page-title">工作台</h1>
        <p class="pd-page-subtitle">
          当前系统状态、近期活动与模型可用性。所有数值均来自真实数据，未配置的功能显示为不可用。
        </p>
      </div>
      <el-button :icon="Refresh" @click="load">刷新</el-button>
    </div>

    <el-alert
      v-if="data?.mock_mode"
      type="warning"
      show-icon
      :closable="false"
      title="DEMO DATA：当前处于 Mock 模式"
      description="DEMO_MOCK_MODE=true，页面数据可能包含演示用模拟结果，请勿与真实模型输出混淆。"
      style="margin-bottom: 16px"
    />

    <div class="pd-grid pd-grid-4">
      <div class="pd-stat">
        <div class="pd-stat-label">患者总数</div>
        <div class="pd-stat-value">{{ data?.counts.total_patients ?? '—' }}</div>
      </div>
      <div class="pd-stat">
        <div class="pd-stat-label">今日评估次数</div>
        <div class="pd-stat-value">{{ data?.counts.today_assessments ?? '—' }}</div>
      </div>
      <div class="pd-stat">
        <div class="pd-stat-label">今日训练次数</div>
        <div class="pd-stat-value">{{ data?.counts.today_trainings ?? '—' }}</div>
      </div>
      <div class="pd-stat">
        <div class="pd-stat-label">可用模型</div>
        <div class="pd-stat-value">
          {{ data ? `${data.model_status.ready} / ${data.model_status.total}` : '—' }}
        </div>
      </div>
    </div>

    <div class="pd-grid pd-grid-2" style="margin-top: 16px">
      <div class="pd-card">
        <div class="pd-card-header">
          <span class="pd-card-title">系统模型状态</span>
          <router-link to="/system/model-status">查看详情</router-link>
        </div>
        <div class="pd-card-body">
          <div v-if="!models.length" class="pd-empty">暂无模型信息</div>
          <el-table v-else :data="models" size="small" :show-header="false">
            <el-table-column prop="name" label="模型">
              <template #default="{ row }">
                {{ MODEL_LABELS[row.name] ?? row.name }}
              </template>
            </el-table-column>
            <el-table-column width="150" align="right">
              <template #default="{ row }">
                <el-tag :type="modelStateTagType(row.state)" size="small">
                  {{ MODEL_STATE_LABELS[row.state] ?? row.state }}
                </el-tag>
              </template>
            </el-table-column>
          </el-table>
        </div>
      </div>

      <div class="pd-card">
        <div class="pd-card-header">
          <span class="pd-card-title">最近患者</span>
          <router-link to="/patients">全部患者</router-link>
        </div>
        <div class="pd-card-body">
          <div v-if="!data?.recent_patients.length" class="pd-empty">暂无患者记录</div>
          <el-table v-else :data="data.recent_patients" size="small" @row-click="(row: any) => openPatient(row.id)">
            <el-table-column prop="name" label="姓名" />
            <el-table-column prop="hospital_number" label="编号" width="110" />
            <el-table-column label="年龄" width="70">
              <template #default="{ row }">{{ row.age ?? '—' }}</template>
            </el-table-column>
            <el-table-column label="受累侧" width="90">
              <template #default="{ row }">
                {{ AFFECTED_SIDE_LABELS[row.affected_side] ?? row.affected_side }}
              </template>
            </el-table-column>
            <el-table-column label="药物状态" width="110">
              <template #default="{ row }">
                {{ MEDICATION_LABELS[row.medication_state] ?? row.medication_state }}
              </template>
            </el-table-column>
          </el-table>
        </div>
      </div>
    </div>

    <div class="pd-card">
      <div class="pd-card-header">
        <span class="pd-card-title">最近评估</span>
      </div>
      <div class="pd-card-body">
        <div v-if="!data?.recent_assessments.length" class="pd-empty">暂无评估记录</div>
        <el-table v-else :data="data.recent_assessments" size="small">
          <el-table-column label="患者">
            <template #default="{ row }">
              {{ row.patient_name ?? '—' }}
            </template>
          </el-table-column>
          <el-table-column label="评估类型">
            <template #default="{ row }">
              {{ SESSION_TYPE_LABELS[row.session_type] ?? row.session_type }}
            </template>
          </el-table-column>
          <el-table-column label="药物状态" width="120">
            <template #default="{ row }">
              {{ MEDICATION_LABELS[row.medication_state] ?? row.medication_state }}
            </template>
          </el-table-column>
          <el-table-column label="创建时间" width="170">
            <template #default="{ row }">{{ formatDateTime(row.created_at) }}</template>
          </el-table-column>
        </el-table>
      </div>
    </div>

    <MedicalDisclaimer />
  </div>
</template>

<style scoped>
:deep(.el-table__row) {
  cursor: pointer;
}
</style>
