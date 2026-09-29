<script setup lang="ts">
/**
 * Comprehensive assessment entry point.
 *
 * A session is the shared time anchor: micro-expression, finger tapping (left
 * and right) and optional functional tests all attach to one session, so results
 * from different moments can never be mistaken for the same assessment.
 */
import { computed, onMounted, reactive, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { Check, Plus, Refresh } from '@element-plus/icons-vue'

import MedicalDisclaimer from '@/components/MedicalDisclaimer.vue'
import { assessmentApi, patientApi } from '@/api'
import { notifyError } from '@/api/client'
import type { AssessmentSession, AssessmentSessionType, Patient } from '@/types'
import {
  MEDICATION_LABELS,
  SESSION_STATUS_LABELS,
  SESSION_TYPE_LABELS,
  formatDateTime,
  sessionStatusTagType,
} from '@/utils/format'

const route = useRoute()
const router = useRouter()

const patientId = computed(() => String(route.params.id))
const patient = ref<Patient | null>(null)
const sessions = ref<AssessmentSession[]>([])
const loading = ref(false)
const creating = ref(false)
const completing = ref<string | null>(null)

const form = reactive({
  session_type: 'COMPREHENSIVE' as AssessmentSessionType,
  medication_state: 'UNKNOWN' as 'ON' | 'OFF' | 'UNKNOWN',
  notes: '',
})

const activeSession = computed(() =>
  sessions.value.find((s) => s.status === 'IN_PROGRESS') ?? null,
)

async function load() {
  loading.value = true
  try {
    patient.value = await patientApi.get(patientId.value)
    const page = await assessmentApi.listSessions(patientId.value, 1, 50)
    sessions.value = page.items
    if (form.medication_state === 'UNKNOWN' && patient.value.medication_state !== 'UNKNOWN') {
      form.medication_state = patient.value.medication_state
    }
  } catch (error) {
    notifyError(error, '无法加载评估信息。')
  } finally {
    loading.value = false
  }
}

async function createSession() {
  creating.value = true
  try {
    await assessmentApi.createSession(patientId.value, {
      session_type: form.session_type,
      medication_state: form.medication_state,
      notes: form.notes || undefined,
    })
    ElMessage.success('已创建评估会话')
    form.notes = ''
    await load()
  } catch (error) {
    notifyError(error, '创建评估会话失败。')
  } finally {
    creating.value = false
  }
}

async function completeSession(session: AssessmentSession) {
  completing.value = session.id
  try {
    await assessmentApi.completeSession(session.id)
    ElMessage.success('已标记该次评估为完成')
    await load()
  } catch (error) {
    notifyError(error, '完成评估失败。')
  } finally {
    completing.value = null
  }
}

function goSub(name: string, sessionId?: string) {
  router.push({
    name,
    params: { id: patientId.value },
    query: sessionId ? { sessionId } : undefined,
  })
}

onMounted(load)
</script>

<template>
  <div v-loading="loading" class="pd-page">
    <div class="pd-page-header">
      <div>
        <h1 class="pd-page-title">综合评估</h1>
        <p class="pd-page-subtitle">
          患者：{{ patient?.name ?? '—' }}。一次综合评估包含微表情分析、左右手 Finger Tapping
          与可选功能测试，全部结果关联同一条评估会话。
        </p>
      </div>
      <el-button :icon="Refresh" @click="load">刷新</el-button>
    </div>

    <el-alert
      type="info"
      show-icon
      :closable="false"
      title="系统不会伪造分析结果"
      description="微表情模型未配置时接口返回 MODEL_NOT_CONFIGURED；Finger Tapping 为 Phase 4 已交付的真实 OpenCV + MediaPipe 流水线。任一模块不可用时页面只显示原因，不显示示例指标。"
      style="margin-bottom: 16px"
    />

    <div class="pd-grid pd-grid-2">
      <div class="pd-card">
        <div class="pd-card-header"><span class="pd-card-title">新建评估会话</span></div>
        <div class="pd-card-body">
          <el-form label-width="110px">
            <el-form-item label="评估类型">
              <el-select v-model="form.session_type" style="width: 100%">
                <el-option label="综合评估（推荐）" value="COMPREHENSIVE" />
                <el-option label="仅微表情分析" value="MICRO_EXPRESSION_ONLY" />
                <el-option label="仅 Finger Tapping" value="FINGER_TAPPING_ONLY" />
                <el-option label="功能测试" value="FUNCTIONAL_TEST" />
              </el-select>
            </el-form-item>
            <el-form-item label="用药状态">
              <el-select v-model="form.medication_state" style="width: 100%">
                <el-option label="开期（ON）" value="ON" />
                <el-option label="关期（OFF）" value="OFF" />
                <el-option label="未知" value="UNKNOWN" />
              </el-select>
            </el-form-item>
            <el-form-item label="备注">
              <el-input v-model="form.notes" type="textarea" :rows="2" />
            </el-form-item>
            <el-form-item>
              <el-button type="primary" :icon="Plus" :loading="creating" @click="createSession">
                创建评估会话
              </el-button>
            </el-form-item>
          </el-form>
          <p class="pd-muted" style="font-size: 12px; margin: 0">
            长期比较必须记录用药状态：开期与关期的运动表现不可直接对比。
          </p>
        </div>
      </div>

      <div class="pd-card">
        <div class="pd-card-header"><span class="pd-card-title">评估模块入口</span></div>
        <div class="pd-card-body">
          <div v-if="!activeSession" class="pd-empty">
            请先创建一条评估会话，再进行各项分析。
          </div>
          <div v-else class="module-actions">
            <p class="pd-secondary" style="margin-top: 0">
              当前进行中的会话：<span class="pd-mono">{{ activeSession.id.slice(0, 8) }}</span>
              （{{ SESSION_TYPE_LABELS[activeSession.session_type] }}，
              {{ MEDICATION_LABELS[activeSession.medication_state] }}）
            </p>
            <el-button
              class="pd-big-action"
              type="primary"
              @click="goSub('assessment-micro-expression', activeSession.id)"
            >
              微表情 / AI 视频分析
            </el-button>
            <el-button
              class="pd-big-action"
              @click="goSub('assessment-finger-tapping', activeSession.id)"
            >
              Finger Tapping 运动量化
            </el-button>
            <el-button
              class="pd-big-action"
              :loading="completing === activeSession.id"
              :icon="Check"
              @click="completeSession(activeSession)"
            >
              标记本次评估完成
            </el-button>
          </div>
        </div>
      </div>
    </div>

    <div class="pd-card">
      <div class="pd-card-header">
        <span class="pd-card-title">历史评估会话</span>
      </div>
      <div class="pd-card-body">
        <el-table :data="sessions" size="small" empty-text="暂无评估会话">
          <el-table-column label="类型">
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
          <el-table-column label="会话 ID" width="120">
            <template #default="{ row }">
              <span class="pd-mono">{{ row.id.slice(0, 8) }}</span>
            </template>
          </el-table-column>
        </el-table>
      </div>
    </div>

    <MedicalDisclaimer />
  </div>
</template>

<style scoped>
.module-actions {
  display: flex;
  flex-direction: column;
  gap: 12px;
  align-items: stretch;
}
</style>
