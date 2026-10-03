<script setup lang="ts">
/**
 * Assessment centre.
 *
 * The workflow the old page imposed was backwards: create a session, then choose
 * a module, then remember which session you were in. Here the doctor picks the
 * patient and then says what they want to do, and the session -- a database
 * concept -- is created for them.
 *
 * The three choices carry plain names. "MICRO_EXPRESSION_ONLY" is an
 * implementation detail and never appears.
 */
import { computed, onMounted, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import { DataAnalysis, Monitor, VideoCamera } from '@element-plus/icons-vue'

import PatientSelector from '@/components/PatientSelector.vue'
import SelectedPatientBar from '@/components/SelectedPatientBar.vue'
import { assessmentApi } from '@/api'
import { notifyError } from '@/api/client'
import { usePatientContextStore } from '@/stores/patientContext'
import type { AssessmentSession, AssessmentSessionType, Patient } from '@/types'
import { formatDateTime } from '@/utils/format'

const route = useRoute()
const router = useRouter()
const store = usePatientContextStore()

const patient = ref<Patient | null>(null)
const openSessions = ref<AssessmentSession[]>([])
const busy = ref(false)

const patientId = computed(() => patient.value?.id ?? null)

/** What the doctor can start. Each one maps to a session type behind the scenes. */
const OPTIONS: Array<{
  key: 'COMPREHENSIVE' | 'MICRO_EXPRESSION_ONLY' | 'FINGER_TAPPING_ONLY'
  title: string
  subtitle: string
  description: string
  icon: typeof Monitor
}> = [
  {
    key: 'COMPREHENSIVE',
    title: '综合评估',
    subtitle: '面部表现 + 左右手手指敲击',
    description: '按步骤依次完成，最后统一汇总。适合周期性复评。',
    icon: Monitor,
  },
  {
    key: 'MICRO_EXPRESSION_ONLY',
    title: '面部表现分析',
    subtitle: '面部视频分析',
    description: '只做面部视频这一项。',
    icon: VideoCamera,
  },
  {
    key: 'FINGER_TAPPING_ONLY',
    title: '手指敲击评估',
    subtitle: '手指动作速度、幅度与稳定性',
    description: '只做左右手手指敲击。',
    icon: DataAnalysis,
  },
]

async function usePatient(id: string) {
  patient.value = await store.resolve(id)
  if (patient.value) {
    // Keep the patient in the URL so the page survives a refresh and can be shared.
    router.replace({ query: { ...route.query, patientId: id } })
    await loadOpenSessions()
  }
}

async function loadOpenSessions() {
  if (!patientId.value) return
  try {
    const page = await assessmentApi.listSessions(patientId.value, 1, 20, 'IN_PROGRESS')
    openSessions.value = page.items
  } catch (error) {
    notifyError(error, '无法读取未完成的评估。')
  }
}

async function start(type: AssessmentSessionType) {
  if (!patientId.value) return
  busy.value = true
  try {
    const session = await assessmentApi.createSession(patientId.value, {
      session_type: type,
      medication_state: patient.value?.medication_state ?? 'UNKNOWN',
    })
    ElMessage.success('已开始新的评估')
    goToModule(type, session.id)
  } catch (error) {
    notifyError(error, '无法开始评估。')
  } finally {
    busy.value = false
  }
}

function goToModule(type: string, sessionId: string) {
  const name =
    type === 'MICRO_EXPRESSION_ONLY' ? 'assessment-micro-expression' : 'assessment-finger-tapping'
  // A comprehensive assessment starts at the first step it can actually run.
  router.push({
    name,
    query: { patientId: patientId.value ?? '', sessionId },
  })
}

function continueSession(session: AssessmentSession) {
  goToModule(session.session_type, session.id)
}

async function abandon(session: AssessmentSession) {
  try {
    await ElMessageBox.confirm(
      `放弃 ${formatDateTime(session.started_at)} 开始的未完成评估？已采集的结果会保留在记录里。`,
      '放弃评估',
      { confirmButtonText: '放弃并开始新的', cancelButtonText: '取消', type: 'warning' },
    )
  } catch {
    return
  }
  try {
    await assessmentApi.updateSession(session.id, { status: 'ABORTED' })
    ElMessage.success('已放弃该评估')
    await loadOpenSessions()
  } catch (error) {
    notifyError(error, '无法放弃该评估。')
  }
}

onMounted(async () => {
  const fromQuery = route.query.patientId
  if (typeof fromQuery === 'string' && fromQuery) {
    await usePatient(fromQuery)
  }
})
</script>

<template>
  <div class="pd-page">
    <div class="pd-page-header">
      <div>
        <h1 class="pd-page-title">评估中心</h1>
        <p class="pd-page-subtitle">
          先选择患者，再选择要做哪一项评估。系统会自动记录本次评估。
        </p>
      </div>
    </div>

    <SelectedPatientBar
      v-if="patient"
      :patient="patient"
      @change="patient = null"
    />

    <template v-if="!patient">
      <PatientSelector
        title="选择患者"
        description="搜索姓名或患者编号，选择后即可开始评估。"
        @select="(p) => usePatient(p.id)"
      />
    </template>

    <template v-else>
      <!-- An unfinished session is surfaced, never silently reused or ignored. -->
      <el-alert
        v-if="openSessions.length"
        type="warning"
        show-icon
        :closable="false"
        style="margin-bottom: 16px"
        :title="`发现 ${openSessions.length} 项未完成的评估`"
      >
        <div v-for="session in openSessions" :key="session.id" class="open-session">
          <span>
            {{ formatDateTime(session.started_at) }} ·
            {{ session.session_type === 'COMPREHENSIVE' ? '综合评估' : '单项评估' }}
          </span>
          <span class="open-session-actions">
            <el-button size="small" type="primary" @click="continueSession(session)">
              继续上次评估
            </el-button>
            <el-button size="small" @click="abandon(session)">放弃并开始新的</el-button>
          </span>
        </div>
      </el-alert>

      <div class="pd-card">
        <div class="pd-card-header"><span class="pd-card-title">选择评估方式</span></div>
        <div class="pd-card-body">
          <div class="option-grid">
            <button
              v-for="option in OPTIONS"
              :key="option.key"
              type="button"
              class="option-card"
              :disabled="busy"
              @click="start(option.key)"
            >
              <el-icon class="option-icon"><component :is="option.icon" /></el-icon>
              <strong class="option-title">{{ option.title }}</strong>
              <span class="option-subtitle">{{ option.subtitle }}</span>
              <span class="option-description">{{ option.description }}</span>
            </button>
          </div>
          <p class="pd-muted" style="font-size: 12px; margin: 12px 0 0">
            功能测试（如 9-HPT 钉板测试）不在综合评估内，它有自己的模块。
          </p>
        </div>
      </div>
    </template>
  </div>
</template>

<style scoped>
.option-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(min(220px, 100%), 1fr));
  gap: 12px;
}

.option-card {
  display: flex;
  flex-direction: column;
  align-items: flex-start;
  gap: 4px;
  padding: 18px 16px;
  text-align: left;
  background: var(--pd-surface);
  border: 1px solid var(--pd-border);
  border-radius: 10px;
  cursor: pointer;
  transition: border-color 0.15s, box-shadow 0.15s;
}

.option-card:hover:not(:disabled) {
  border-color: var(--pd-primary);
  box-shadow: 0 4px 14px rgb(27 111 184 / 12%);
}

.option-card:disabled {
  opacity: 0.6;
  cursor: not-allowed;
}

.option-icon {
  font-size: 26px;
  color: var(--pd-primary);
  margin-bottom: 6px;
}

.option-title {
  font-size: 17px;
}

.option-subtitle {
  font-size: 13px;
  color: var(--pd-text-secondary);
}

.option-description {
  font-size: 12px;
  color: var(--pd-text-muted);
  margin-top: 4px;
}

.open-session {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  flex-wrap: wrap;
  margin-top: 8px;
}

.open-session-actions {
  display: flex;
  gap: 8px;
}
</style>
