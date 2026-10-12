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
import { Refresh, ArrowRight, User, Monitor, DataAnalysis, TrendCharts } from '@element-plus/icons-vue'
import TrainingArtwork from '@/components/TrainingArtwork.vue'

import { systemApi } from '@/api'
import { notifyError } from '@/api/client'
import type { DashboardResponse, ModelSummaryItem } from '@/types'
import {
  AFFECTED_SIDE_LABELS,
  MEDICATION_LABELS,
  MODEL_STATE_LABELS,
  SESSION_TYPE_LABELS,
  displayHospitalNumber,
  displayPatientName,
  formatDateTime,
  modelStateTagType,
} from '@/utils/format'

const router = useRouter()
const loading = ref(false)
const data = ref<DashboardResponse | null>(null)
const models = ref<ModelSummaryItem[]>([])

/**
 * What each engine is called in front of a doctor.
 *
 * The module names on the left are the servers's internal model keys. A doctor
 * reading the overview needs to know which capability is available, not which
 * library implements it, so the labels name the capability.
 */
const MODEL_LABELS: Record<string, string> = {
  micro_expression_model: '面部表现分析',
  finger_tapping: '手指敲击评估',
  mediapipe_hand_landmarker: '手指敲击（录像分析）',
  mediapipe_pose: '芭蕾动作训练（录像分析）',
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
        <span class="pd-eyebrow">CARE WORKSPACE</span>
        <h1 class="pd-page-title">工作台</h1>
        <p class="pd-page-subtitle">从一次评估开始，陪伴每一步康复。</p>
      </div>
      <el-button :icon="Refresh" @click="load">刷新</el-button>
    </div>

    <!--
      Mock mode is an operator condition, not something a clinician acts on, and
      it is reported where it can be investigated (/system/model-status, which
      has no navigation entry). Printing it on the overview told a doctor about
      a configuration flag while giving them nothing to do about it.
    -->

    <div class="dashboard-welcome"><div><span class="pd-pill">康复工作空间</span><h2>让训练融入日常</h2><p>浏览钢琴与芭蕾练习，为患者安排适合的康复训练。</p><router-link to="/training">探索康复训练<el-icon><ArrowRight /></el-icon></router-link></div><TrainingArtwork kind="piano" /></div>

    <div class="pd-grid pd-grid-4 dashboard-stats">
      <div class="pd-stat">
        <div class="pd-stat-label">患者总数</div>
        <el-icon class="stat-icon"><User /></el-icon>
        <div class="pd-stat-value">{{ data?.counts.total_patients ?? '—' }}</div>
      </div>
      <div class="pd-stat">
        <div class="pd-stat-label">今日评估次数</div>
        <el-icon class="stat-icon"><Monitor /></el-icon>
        <div class="pd-stat-value">{{ data?.counts.today_assessments ?? '—' }}</div>
      </div>
      <div class="pd-stat">
        <div class="pd-stat-label">今日训练次数</div>
        <el-icon class="stat-icon"><DataAnalysis /></el-icon>
        <div class="pd-stat-value">{{ data?.counts.today_trainings ?? '—' }}</div>
      </div>
      <div class="pd-stat">
        <div class="pd-stat-label">可用功能</div>
        <el-icon class="stat-icon"><TrendCharts /></el-icon>
        <div class="pd-stat-value">
          {{ data ? `${data.model_status.ready} / ${data.model_status.total}` : '—' }}
        </div>
      </div>
    </div>

    <nav class="dashboard-shortcuts" aria-label="快捷操作"><router-link to="/patients"><el-icon><User /></el-icon><span>患者档案<small>管理资料与既往记录</small></span><el-icon><ArrowRight /></el-icon></router-link><router-link to="/assessment"><el-icon><Monitor /></el-icon><span>开始评估<small>面部表现与手指敲击</small></span><el-icon><ArrowRight /></el-icon></router-link><router-link to="/follow-up"><el-icon><TrendCharts /></el-icon><span>随访与报告<small>回顾记录与客观趋势</small></span><el-icon><ArrowRight /></el-icon></router-link></nav>
    <div class="pd-grid pd-grid-2 dashboard-details">
      <div class="pd-card">
        <div class="pd-card-header">
          <span class="pd-card-title">功能可用性</span>
        </div>
        <div class="pd-card-body">
          <div v-if="!models.length" class="pd-empty">暂无模型信息</div>
          <div v-else class="pd-table-scroll">
            <el-table :data="models" size="small" :show-header="false">
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
      </div>

      <div class="pd-card">
        <div class="pd-card-header">
          <span class="pd-card-title">最近患者</span>
          <router-link to="/patients">全部患者</router-link>
        </div>
        <div class="pd-card-body">
          <div v-if="!data?.recent_patients.length" class="pd-empty">暂无患者记录</div>
          <el-table v-else :data="data.recent_patients" size="small" @row-click="(row: any) => openPatient(row.id)">
            <el-table-column label="姓名" prop="name">
              <template #default="{ row }">{{ displayPatientName(row.name) }}</template>
            </el-table-column>
            <el-table-column label="编号" width="110">
              <template #default="{ row }">{{ displayHospitalNumber(row.hospital_number) }}</template>
            </el-table-column>
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
              {{ displayPatientName(row.patient_name) || '—' }}
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

  </div>
</template>

<style scoped>
:deep(.el-table__row) {
  cursor: pointer;
}
.dashboard-welcome { display: grid; grid-template-columns: 1.2fr 1fr; align-items: center; background: #eaf1fa; border: 1px solid #dce7f5; border-radius: 18px; overflow: hidden; margin-bottom: 24px; }
.dashboard-welcome > div:first-child { padding: 28px 32px; }
.dashboard-welcome h2 { margin: 12px 0 8px; font-size: 26px; }
.dashboard-welcome p { font-size: 14px; color: var(--pd-text-secondary); margin: 0 0 16px; }
.dashboard-welcome a { display: inline-flex; align-items: center; gap: 12px; font-size: 14px; font-weight: 600; }
.dashboard-welcome :deep(.training-art) { height: 100%; background: transparent; }
.dashboard-welcome :deep(.training-art__label) { display: none; }
.stat-icon { position: absolute; right: 20px; top: 20px; width: 36px; height: 36px; background: var(--pd-primary-soft); border-radius: 10px; color: var(--pd-primary); padding: 9px; }
.dashboard-shortcuts { display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: 16px; margin: 24px 0; }
.dashboard-shortcuts a { display: flex; align-items: center; gap: 12px; background: white; border: 1px solid var(--pd-border); border-radius: 12px; padding: 18px; color: var(--pd-text); font-size: 14px; }
.dashboard-shortcuts a > .el-icon:first-child { font-size: 22px; color: var(--pd-primary); }
.dashboard-shortcuts a > .el-icon:last-child { margin-left: auto; color: var(--pd-text-secondary); }
.dashboard-shortcuts small { display: block; color: var(--pd-text-secondary); margin-top: 3px; font-size: 12px; }
.dashboard-details { margin-bottom: 24px; }
@media (max-width: 767px) { .dashboard-welcome { grid-template-columns: 1fr; } .dashboard-welcome > div:first-child { padding: 24px; } .dashboard-welcome :deep(.training-art) { display: none; } .dashboard-shortcuts { grid-template-columns: 1fr; gap: 10px; } .dashboard-stats { grid-template-columns: repeat(2, minmax(0, 1fr)) !important; } .pd-stat { padding: 20px 16px; } .stat-icon { right: 12px; top: 12px; width: 28px; height: 28px; padding: 7px; } }
</style>
