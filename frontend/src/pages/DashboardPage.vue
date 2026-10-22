<script setup lang="ts">
/**
 * Dashboard: patient and activity counts, recent items, and the true model
 * readiness state.
 *
 * Model status is shown exactly as the backend reports it. A component that is
 * not configured is labelled 未配置 rather than hidden or shown as ready.
 */
import { onMounted, ref } from 'vue'
import { ElTag } from 'element-plus'
import { Refresh, User, Monitor, DataAnalysis } from '@element-plus/icons-vue'

import { systemApi } from '@/api'
import { notifyError } from '@/api/client'
import type { DashboardResponse, ModelSummaryItem } from '@/types'
import {
  MEDICATION_LABELS,
  MODEL_STATE_LABELS,
  SESSION_TYPE_LABELS,
  displayPatientName,
  formatDateTime,
  modelStateTagType,
} from '@/utils/format'

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
  if (loading.value) return
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

onMounted(load)
</script>

<template>
  <div v-loading="loading" class="pd-page">
    <div class="pd-page-header">
      <h1 class="pd-page-title">{{ $t("工作台") }}</h1>
      <el-button :icon="Refresh" :loading="loading" @click="load">{{ $t("刷新") }}</el-button>
    </div>

    <div class="dashboard-stats">
      <div class="pd-stat">
        <div class="pd-stat-label">{{ $t("患者总数") }}</div>
        <el-icon class="stat-icon"><User /></el-icon>
        <div class="pd-stat-value">{{ $t(data?.counts.total_patients ?? '—') }}</div>
      </div>
      <div class="pd-stat">
        <div class="pd-stat-label">{{ $t("今日评估次数") }}</div>
        <el-icon class="stat-icon"><Monitor /></el-icon>
        <div class="pd-stat-value">{{ $t(data?.counts.today_assessments ?? '—') }}</div>
      </div>
      <div class="pd-stat">
        <div class="pd-stat-label">{{ $t("今日训练次数") }}</div>
        <el-icon class="stat-icon"><DataAnalysis /></el-icon>
        <div class="pd-stat-value">{{ $t(data?.counts.today_trainings ?? '—') }}</div>
      </div>
    </div>

    <section class="pd-card dashboard-records" aria-labelledby="recent-patients-title">
      <div class="pd-card-header">
        <h2 id="recent-patients-title" class="pd-card-title">{{ $t("最近患者") }}</h2>
        <router-link to="/patients">{{ $t("全部患者") }}</router-link>
      </div>
      <div class="pd-card-body">
        <div v-if="!data?.recent_patients.length" class="pd-empty">{{ $t("暂无患者记录") }}</div>
        <el-table v-else :data="data.recent_patients" size="small">
          <el-table-column :label="$t('姓名')" min-width="100">
            <template #default="{ row }">{{ displayPatientName(row.name) }}</template>
          </el-table-column>
          <el-table-column :label="$t('档案')" width="100" align="right">
            <template #default="{ row }">
              <router-link class="dashboard-detail-link" :to="{ name: 'patient-detail', params: { id: row.id } }" :aria-label="$t(`查看${displayPatientName(row.name)}的档案`)">{{ $t("查看档案") }}</router-link>
            </template>
          </el-table-column>
        </el-table>
      </div>
    </section>

    <section class="pd-card dashboard-records" aria-labelledby="recent-assessments-title">
      <div class="pd-card-header"><h2 id="recent-assessments-title" class="pd-card-title">{{ $t("最近评估") }}</h2></div>
      <div class="pd-card-body">
        <div v-if="!data?.recent_assessments.length" class="pd-empty">{{ $t("暂无评估记录") }}</div>
        <div v-else class="pd-table-scroll">
          <el-table :data="data.recent_assessments" size="small">
            <el-table-column :label="$t('患者')" min-width="150">
              <template #default="{ row }"><router-link class="dashboard-detail-link" :to="{ name: 'patient-detail', params: { id: row.patient_id } }">{{ displayPatientName(row.patient_name) }}</router-link></template>
            </el-table-column>
            <el-table-column :label="$t('评估类型')" min-width="150">
              <template #default="{ row }">{{ $t(SESSION_TYPE_LABELS[row.session_type] ?? row.session_type) }}</template>
            </el-table-column>
            <el-table-column :label="$t('药物状态')" min-width="150">
              <template #default="{ row }">{{ $t(MEDICATION_LABELS[row.medication_state] ?? row.medication_state) }}</template>
            </el-table-column>
            <el-table-column :label="$t('创建时间')" min-width="150">
              <template #default="{ row }">{{ $t(formatDateTime(row.created_at)) }}</template>
            </el-table-column>
          </el-table>
        </div>
      </div>
    </section>

    <section class="dashboard-models" aria-labelledby="analysis-status-title">
      <div class="dashboard-models-heading">
        <h2 id="analysis-status-title">{{ $t("分析组件状态") }}</h2>
        <span v-if="data">{{ $t(`${$t(data.model_status.ready)} / ${$t(data.model_status.total)} 就绪`) }}</span>
      </div>
      <p v-if="!models.length" class="pd-muted">{{ $t("暂无组件状态") }}</p>
      <ul v-else class="dashboard-model-list">
        <li v-for="model in models" :key="model.name">
          <span>{{ $t(MODEL_LABELS[model.name] ?? model.name) }}</span>
          <el-tag :type="modelStateTagType(model.state)" size="small">{{ $t(MODEL_STATE_LABELS[model.state] ?? model.state) }}</el-tag>
        </li>
      </ul>
    </section>
  </div>
</template>

<style scoped>
.dashboard-stats { display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: 16px; margin-bottom: 24px; }
.stat-icon { position: absolute; right: 20px; top: 20px; width: 36px; height: 36px; background: var(--pd-primary-soft); border-radius: 10px; color: var(--pd-primary); padding: 9px; }
.dashboard-records .pd-card-title { margin: 0; }
.dashboard-records .pd-card-header > a { font-size: 14px; }
.dashboard-detail-link { display: inline-flex; align-items: center; min-height: 36px; white-space: nowrap; font-size: 14px; }
.dashboard-models { margin-top: 24px; border-top: 1px solid var(--pd-border); padding-top: 20px; }
.dashboard-models-heading { display: flex; align-items: baseline; justify-content: space-between; gap: 12px; }
.dashboard-models-heading h2 { font-size: 15px; margin: 0; }
.dashboard-models-heading > span { color: var(--pd-text-secondary); font-size: 13px; }
.dashboard-model-list { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 10px 24px; padding: 0; margin: 16px 0 0; list-style: none; }
.dashboard-model-list li { display: flex; align-items: center; justify-content: space-between; gap: 12px; font-size: 13px; }
.dashboard-model-list .el-tag { flex-shrink: 0; }
@media (max-width: 767px) {
  .dashboard-stats { gap: 10px; }
  .pd-stat { padding: 16px 12px; }
  .pd-stat-label { font-size: 12px; }
  .pd-stat-value { font-size: 28px; }
  .stat-icon { display: none; }
  .dashboard-records .pd-card-body { padding: 8px; }
  .dashboard-detail-link { min-height: 44px; font-size: 13px; }
  .dashboard-model-list { grid-template-columns: minmax(0, 1fr); gap: 12px; }
}
</style>
