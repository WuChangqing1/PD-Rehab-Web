<script setup lang="ts">
/**
 * Facial video analysis.
 *
 * Reached from 评估中心 with a patient, or directly with `?patientId=`. If no
 * session exists yet the page creates one itself: the old flow refused to work
 * without a session id and told the operator to go and create one elsewhere,
 * which is a dead end dressed up as guidance.
 *
 * Sessions remain in the database -- they are how results are grouped -- but they
 * are not something the operator has to think about.
 */
import { computed, onMounted, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'

import MetricSummaryCards from '@/components/MetricSummaryCards.vue'
import PatientSelector from '@/components/PatientSelector.vue'
import SelectedPatientBar from '@/components/SelectedPatientBar.vue'
import VideoCapturePanel from '@/components/VideoCapturePanel.vue'
import { assessmentApi, systemApi } from '@/api'
import { notifyError, toApiError } from '@/api/client'
import { usePatientContextStore } from '@/stores/patientContext'
import type { MicroExpressionResult, Patient } from '@/types'
import { NO_DATA, formatDateTime, formatNumber } from '@/utils/format'

const route = useRoute()
const router = useRouter()
const store = usePatientContextStore()

const patient = ref<Patient | null>(null)
const sessionId = ref<string | null>(null)
const modelReady = ref(false)
const results = ref<MicroExpressionResult[]>([])
const loading = ref(false)
const uploading = ref(false)
const clip = ref<{ blob: Blob | null; name: string }>({ blob: null, name: '' })

const patientId = computed(() => patient.value?.id ?? null)
const hasClip = computed(() => clip.value.blob !== null)

const summary = computed(() => {
  const latest = results.value[0]
  if (!latest) return []
  return [
    { label: '主导标签', value: latest.dominant_tag ?? NO_DATA, emphasis: true },
    { label: '预测类别', value: latest.predicted_class ?? NO_DATA },
    { label: '分析时间', value: formatDateTime(latest.created_at) },
  ]
})

async function loadModelStatus() {
  try {
    const models = await systemApi.models()
    modelReady.value = models.models.micro_expression_model?.is_ready === true
  } catch {
    modelReady.value = false
  }
}

async function loadResults() {
  if (!sessionId.value) return
  try {
    results.value = await assessmentApi.listMicroExpression(sessionId.value)
  } catch {
    results.value = []
  }
}

/** Find an open session of the right kind, or create one. */
async function ensureSession(): Promise<string | null> {
  if (sessionId.value) return sessionId.value
  if (!patientId.value) return null

  const page = await assessmentApi.listSessions(patientId.value, 1, 20, 'IN_PROGRESS')
  const reusable = page.items.find(
    (s) => s.session_type === 'MICRO_EXPRESSION_ONLY' || s.session_type === 'COMPREHENSIVE',
  )
  if (reusable) {
    sessionId.value = reusable.id
    return reusable.id
  }

  const created = await assessmentApi.createSession(patientId.value, {
    session_type: 'MICRO_EXPRESSION_ONLY',
    medication_state: patient.value?.medication_state ?? 'UNKNOWN',
  })
  sessionId.value = created.id
  return created.id
}

async function usePatient(id: string) {
  patient.value = await store.resolve(id)
  router.replace({ query: { ...route.query, patientId: id } })
  sessionId.value = null
  results.value = []
  const fromQuery = route.query.sessionId
  if (typeof fromQuery === 'string' && fromQuery) {
    sessionId.value = fromQuery
    await loadResults()
  }
}

/** Refuse to analyse when the URL's patient and the session's patient disagree. */
async function assertSessionMatchesPatient(): Promise<boolean> {
  if (!sessionId.value || !patientId.value) return true
  try {
    const session = await assessmentApi.getSession(sessionId.value)
    if (session.patient_id !== patientId.value) {
      ElMessage.error('当前评估记录与所选患者不一致，请重新选择。')
      sessionId.value = null
      return false
    }
    return true
  } catch {
    ElMessage.error('无法读取该评估记录，请重新开始。')
    sessionId.value = null
    return false
  }
}

async function analyze() {
  if (!clip.value.blob) {
    ElMessage.warning('请先录制或选择一个视频文件。')
    return
  }
  if (!(await assertSessionMatchesPatient())) return

  uploading.value = true
  try {
    const id = await ensureSession()
    if (!id) return
    if (!(await assertSessionMatchesPatient())) return

    const file = new File([clip.value.blob], clip.value.name || 'recording.webm', {
      type: clip.value.blob.type,
    })
    const result = await assessmentApi.uploadMicroExpression(id, file, 'UNKNOWN')
    results.value = [result, ...results.value]
    ElMessage.success('分析完成')
  } catch (error) {
    const apiError = toApiError(error)
    if (apiError.code === 'MODEL_NOT_CONFIGURED') {
      // Operator-facing wording; the technical reason lives in 系统设置.
      ElMessage.warning('面部分析功能当前暂不可用，请联系系统管理员。')
    } else {
      notifyError(error, '分析失败。')
    }
  } finally {
    uploading.value = false
  }
}

onMounted(async () => {
  await loadModelStatus()
  const fromQuery = route.query.patientId
  if (typeof fromQuery === 'string' && fromQuery) await usePatient(fromQuery)
})
</script>

<template>
  <div v-loading="loading" class="pd-page">
    <div class="pd-page-header">
      <div>
        <h1 class="pd-page-title">面部分析</h1>
        <p class="pd-page-subtitle">上传面部视频，由模型输出表情标签分布或辅助识别概率。</p>
      </div>
    </div>

    <SelectedPatientBar v-if="patient" :patient="patient" @change="patient = null" />

    <PatientSelector
      v-if="!patient"
      title="选择患者"
      description="搜索姓名或患者编号，选择后即可开始面部分析。"
      @select="(p) => usePatient(p.id)"
    />

    <template v-else>
      <!-- The model's absence is stated plainly; the technical reason is not here. -->
      <el-alert
        v-if="!modelReady"
        type="info"
        show-icon
        :closable="false"
        title="面部分析功能当前暂不可用，请联系系统管理员"
        description="该功能需要模型支持，当前环境尚未配置。已有的其他评估与训练不受影响。"
        style="margin-bottom: 16px"
      />

      <div class="pd-grid pd-grid-2">
        <div class="pd-card">
          <div class="pd-card-header"><span class="pd-card-title">视频来源</span></div>
          <div class="pd-card-body">
            <VideoCapturePanel
              :disabled="!modelReady"
              :max-seconds="30"
              instruction="请让患者正对镜头，面部完整入镜，光线均匀。"
              @change="clip = $event"
            />

            <el-button
              type="primary"
              class="pd-big-action"
              style="width: 100%; margin-top: 12px"
              :loading="uploading"
              :disabled="!modelReady || !hasClip"
              @click="analyze"
            >
              开始分析
            </el-button>
          </div>
        </div>

        <div class="pd-card">
          <div class="pd-card-header"><span class="pd-card-title">分析结果</span></div>
          <div class="pd-card-body">
            <div v-if="!results.length" class="pd-empty">
              尚无分析结果。完成一次分析后，这里会显示标签分布与概率。
            </div>

            <template v-else>
              <MetricSummaryCards
                :cards="summary"
                advanced-label="查看详细数据"
                footnote="标签占比表示面部运动 / 表情表现维度，不代表疾病严重程度，也不用于调整训练难度。"
              >
                <dl class="pd-kv">
                  <dt>模型</dt><dd>{{ results[0].model_name ?? NO_DATA }}</dd>
                  <dt>模型版本</dt><dd>{{ results[0].model_version ?? NO_DATA }}</dd>
                  <dt>模型输出概率</dt><dd>{{ formatNumber(results[0].pd_probability, 3) }}</dd>
                  <dt>推理耗时</dt>
                  <dd>
                    {{
                      results[0].inference_time_ms != null
                        ? `${results[0].inference_time_ms} ms`
                        : NO_DATA
                    }}
                  </dd>
                </dl>
                <div v-if="results[0].tag_distribution?.length" class="pd-tag-list">
                  <el-tag
                    v-for="tag in results[0].tag_distribution"
                    :key="tag.name"
                    size="small"
                  >
                    {{ tag.name }} {{ (tag.score * 100).toFixed(1) }}%
                  </el-tag>
                </div>
              </MetricSummaryCards>
            </template>
          </div>
        </div>
      </div>
    </template>
  </div>
</template>
