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
import { formatDateTime, SESSION_TYPE_LABELS } from '@/utils/format'

const route = useRoute()
const router = useRouter()
const store = usePatientContextStore()

const patient = ref<Patient | null>(null)
const openSessions = ref<AssessmentSession[]>([])
const busy = ref(false)
const deleting = ref<string|null>(null)
const openTotal = ref(0)
const pickerOpen = ref(false)
const pendingType = ref<AssessmentSessionType | null>(null)

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
  openSessions.value=[];openTotal.value=0
  patient.value = await store.resolve(id)
  if (patient.value) {
    // Keep the patient in the URL so the page survives a refresh and can be shared.
    router.replace({ query: { ...route.query, patientId: id } })
    await loadOpenSessions()
    pickerOpen.value = false
    if (pendingType.value) {
      const type = pendingType.value
      pendingType.value = null
      await start(type)
    }
  }
}

async function loadOpenSessions() {
  if (!patientId.value) return
  const id=patientId.value
  try {
    const page = await assessmentApi.listSessions(id, 1, 200, 'IN_PROGRESS')
    if(patientId.value!==id)return
    openSessions.value = page.items
    openTotal.value = page.total
  } catch (error) {
    notifyError(error, '无法读取未完成的评估。')
  }
}

async function start(type: AssessmentSessionType) {
  if (busy.value || deleting.value) return
  if (!patientId.value) { pendingType.value = type; pickerOpen.value = true; return }
  busy.value = true
  try {
    const valid = await store.resolve(patientId.value)
    if (!valid) { patient.value = null; ElMessage.error('无法读取该患者，请重新选择。'); return }
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
  if(type==='COMPREHENSIVE'){
    router.push({name:'assessment-comprehensive',params:{sessionId},query:{patientId:patientId.value??''}})
    return
  }
  const name =
    type === 'MICRO_EXPRESSION_ONLY' ? 'assessment-micro-expression' : 'assessment-finger-tapping'
  router.push({
    name,
    query: { patientId: patientId.value ?? '', sessionId },
  })
}

function continueSession(session: AssessmentSession) {
  goToModule(session.session_type, session.id)
}

async function abandon(session: AssessmentSession) {
  if(deleting.value||busy.value||!patientId.value)return
  const id=patientId.value
  try {
    await ElMessageBox.confirm(
      `删除 ${formatDateTime(session.started_at)} 的本次评估记录？本次已采集的结果和关联上传文件也会删除，操作无法撤销。其他评估不受影响。`,
      '删除本次评估记录',
      { confirmButtonText: '确认删除', cancelButtonText: '取消', type: 'warning' },
    )
  } catch {
    return
  }
  if(patientId.value!==id)return
  deleting.value=session.id
  try {
    await assessmentApi.deleteSession(session.id,id)
    ElMessage.success('已删除本次评估记录')
    await loadOpenSessions()
  } catch (error) {
    notifyError(error, '无法删除该评估，请稍后重试。')
  } finally {
    deleting.value=null
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
          开始评估时确认患者。
        </p>
      </div>
    </div>

    <SelectedPatientBar
      v-if="patient"
      :patient="patient"
      @change="patient = null; openSessions = []; openTotal = 0"
    />

    <el-dialog v-model="pickerOpen" title="选择本次评估患者" width="680px" class="training-picker" align-center destroy-on-close @update:model-value="!$event && (pendingType = null)">
      <PatientSelector
        title="选择患者"
        description="搜索姓名或患者编号，选择后即可开始评估。"
        @select="(p) => usePatient(p.id)"
      />
    </el-dialog>

    <template v-if="true">
      <!-- An unfinished session is surfaced, never silently reused or ignored. -->
      <el-alert
        v-if="openSessions.length"
        type="warning"
        show-icon
        :closable="false"
        style="margin-bottom: 16px"
        :title="`发现 ${openTotal} 项未完成的评估`"
      >
        <div v-for="session in openSessions" :key="session.id" class="open-session">
          <span>
            {{ formatDateTime(session.started_at) }} ·
            {{ SESSION_TYPE_LABELS[session.session_type] ?? '评估' }}
          </span>
          <span class="open-session-actions">
            <el-button size="small" type="primary" :disabled="!!deleting" @click="continueSession(session)">
              继续上次评估
            </el-button>
            <el-button size="small" type="danger" plain :loading="deleting===session.id" :disabled="!!deleting&&deleting!==session.id" @click="abandon(session)">删除本次评估记录</el-button>
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
              :disabled="busy || !!deleting"
              @click="start(option.key)"
            >
              <div class="option-cover"><el-icon class="option-icon"><component :is="option.icon" /></el-icon></div>
              <strong class="option-title">{{ option.title }}</strong>
              <span class="option-subtitle">{{ option.subtitle }}</span>
              <span class="option-description">{{ option.description }}</span>
              <span class="option-action">开始{{ option.title }} <span aria-hidden="true">→</span></span>
            </button>
          </div>
        </div>
      </div>
    </template>
  </div>
</template>

<style scoped>
.option-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(min(220px, 100%), 1fr));
  gap: 20px;
}

.option-card {
  display: flex;
  flex-direction: column;
  align-items: flex-start;
  gap: 8px;
  padding: 24px;
  text-align: left;
  background: var(--pd-surface);
  border: 1px solid var(--pd-border);
  border-radius: 14px;
  color: var(--pd-text);
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
  font-size: 14px;
  color: var(--pd-text-muted);
  margin-top: 4px;
}
.option-cover { display: flex; width: 100%; align-items: center; justify-content: space-between; background: var(--pd-primary-soft); border-radius: 12px; padding: 24px 20px; margin-bottom: 12px; }
.option-cover span { color: var(--pd-primary-dark); font-size: 11px; letter-spacing: 1px; }
.option-cover .option-icon { margin: 0; font-size: 34px; }
.option-title { min-height: 28px; }
.option-subtitle { min-height: 3em; }
.option-description { margin-bottom: 24px; }
.option-action { display: flex; justify-content: space-between; width: 100%; margin-top: auto; padding-top: 16px; border-top: 1px solid var(--pd-border); color: var(--pd-primary-dark); font-size: 14px; font-weight: 600; }

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
