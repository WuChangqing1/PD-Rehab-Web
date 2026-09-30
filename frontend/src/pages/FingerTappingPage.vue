<script setup lang="ts">
/**
 * Finger tapping assessment: left and right hands analysed separately.
 *
 * Function first: the page is reached from 评估中心 with a patient, or directly
 * with `?patientId=`. It creates or reuses its own session, so the operator never
 * has to go somewhere else to make one first.
 *
 * Every number on this page comes from a stored analysis result. A metric that
 * was not produced renders as 暂无数据 and is never replaced by 0. Left/right
 * difference is left - right; a missing side stays empty.
 */
import { computed, onMounted, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { ArrowLeft, InfoFilled } from '@element-plus/icons-vue'

import ApertureChart from '@/components/ApertureChart.vue'
import PatientSelector from '@/components/PatientSelector.vue'
import SelectedPatientBar from '@/components/SelectedPatientBar.vue'
import VideoCapturePanel from '@/components/VideoCapturePanel.vue'
import { assessmentApi } from '@/api'
import { notifyError, toApiError } from '@/api/client'
import { usePatientContextStore } from '@/stores/patientContext'
import type {
  FingerTappingResult,
  FingerTappingSessionSummary,
  FingerTappingTimeseries,
  Patient,
} from '@/types'
import { plainErrorMessage } from '@/utils/errors'
import { NO_DATA, formatDateTime, formatNumber } from '@/utils/format'

const route = useRoute()
const router = useRouter()
const store = usePatientContextStore()

const patient = ref<Patient | null>(null)
const sessionId = ref<string | null>(null)

/** The patient comes from the query; params remain as a fallback for old links. */
const patientId = computed(() => {
  const fromQuery = route.query.patientId
  if (typeof fromQuery === 'string' && fromQuery) return fromQuery
  const fromParams = route.params.id
  return typeof fromParams === 'string' ? fromParams : ''
})
const hasPatient = computed(() => patientId.value.length > 0)

interface MetricRow {
  key: keyof FingerTappingResult
  label: string
  digits: number
  unit?: string
  hint?: string
}

const PRIMARY_ROWS: MetricRow[] = [
  { key: 'tapping_frequency', label: '敲击频率', digits: 2, unit: ' Hz', hint: '有效敲击周期数 / 有效分析时长；(峰值数−1) / 首尾峰值时间跨度' },
  { key: 'avg_amplitude', label: '平均动作幅度', digits: 3, hint: '掌宽归一化后，每个周期的峰值与前一谷值之差，取均值（无量纲）' },
  { key: 'avg_speed', label: '平均动作速度', digits: 3, hint: '归一化距离一阶变化率，逐周期取绝对值均值，单位 1/秒' },
  { key: 'avg_cycle_duration', label: '平均周期时长', digits: 3, unit: ' s' },
  { key: 'amplitude_cv', label: '幅度变异系数', digits: 3, hint: '标准差 / 均值' },
  { key: 'speed_cv', label: '速度变异系数', digits: 3 },
  { key: 'cycle_cv', label: '周期变异系数', digits: 3 },
  { key: 'amplitude_slope', label: '幅度趋势斜率', digits: 4, hint: '对周期序号做线性回归；单位是「每周期变化量」，不是每秒' },
  { key: 'speed_slope', label: '速度趋势斜率', digits: 4 },
  { key: 'cycle_slope', label: '周期趋势斜率', digits: 4 },
  { key: 'interruptions', label: '中断次数', digits: 0, hint: '周期时长 > 1.5 × 周期中位数 的次数' },
]

const QUALITY_ROWS: MetricRow[] = [
  { key: 'valid_frame_ratio', label: '有效帧比例', digits: 3, hint: '检测到目标手的帧数 / 总帧数；低于 0.5 会被拒绝' },
  {
    key: 'avg_landmark_confidence',
    label: '平均手别置信度',
    digits: 3,
    hint:
      'MediaPipe 手别分类分数。Tasks API 的 visibility 与 presence 恒为 null，' +
      '因此该字段表示手别判定置信度，而非逐关键点可见度',
  },
]

const COMPARISON_LABELS: Record<string, string> = {
  avg_amplitude: '平均动作幅度',
  avg_speed: '平均动作速度',
  tapping_frequency: '敲击频率',
  cycle_cv: '周期变异系数',
}

const loading = ref(false)
const uploading = ref<'LEFT' | 'RIGHT' | null>(null)
const summary = ref<FingerTappingSessionSummary | null>(null)
const timeseries = ref<Record<'LEFT' | 'RIGHT', FingerTappingTimeseries | null>>({
  LEFT: null,
  RIGHT: null,
})

const files = ref<Record<'LEFT' | 'RIGHT', File | null>>({ LEFT: null, RIGHT: null })
/** Captured or uploaded clip per hand, from the shared capture panel. */
const clips = ref<Record<'LEFT' | 'RIGHT', Blob | null>>({ LEFT: null, RIGHT: null })

const hasAnyResult = computed(
  () => Boolean(summary.value?.left) || Boolean(summary.value?.right),
)

function onClipChange(hand: 'LEFT' | 'RIGHT', payload: { blob: Blob | null; name: string }) {
  clips.value[hand] = payload.blob
}

/** Find an open session of the right kind, or create one. */
async function ensureSession(): Promise<string | null> {
  if (sessionId.value) return sessionId.value
  if (!patientId.value) return null

  const page = await assessmentApi.listSessions(patientId.value, 1, 20, 'IN_PROGRESS')
  const reusable = page.items.find(
    (s) => s.session_type === 'FINGER_TAPPING_ONLY' || s.session_type === 'COMPREHENSIVE',
  )
  if (reusable) {
    sessionId.value = reusable.id
    return reusable.id
  }
  const created = await assessmentApi.createSession(patientId.value, {
    session_type: 'FINGER_TAPPING_ONLY',
    medication_state: patient.value?.medication_state ?? 'UNKNOWN',
  })
  sessionId.value = created.id
  return created.id
}

/** The URL's patient and the session's patient must agree before we record. */
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

async function usePatient(id: string) {
  patient.value = await store.resolve(id)
  router.replace({ query: { ...route.query, patientId: id } })
  sessionId.value = null
  summary.value = null
  const fromQuery = route.query.sessionId
  if (typeof fromQuery === 'string' && fromQuery) {
    sessionId.value = fromQuery
    await load()
  }
}

async function loadSeries(hand: 'LEFT' | 'RIGHT') {
  if (!sessionId.value) return
  const present = hand === 'LEFT' ? summary.value?.left : summary.value?.right
  if (!present) {
    timeseries.value[hand] = null
    return
  }
  try {
    timeseries.value[hand] = await assessmentApi.getFingerTappingTimeseries(
      sessionId.value,
      hand,
    )
  } catch {
    // A missing series must not break the page; the chart shows "no data".
    timeseries.value[hand] = null
  }
}

async function load() {
  if (!sessionId.value) return
  loading.value = true
  try {
    summary.value = await assessmentApi.getFingerTapping(sessionId.value)
    await Promise.all([loadSeries('LEFT'), loadSeries('RIGHT')])
  } catch (error) {
    notifyError(error, '无法加载 Finger Tapping 结果。')
  } finally {
    loading.value = false
  }
}

async function upload(hand: 'LEFT' | 'RIGHT') {
  const blob = clips.value[hand] ?? files.value[hand]
  if (!blob) {
    ElMessage.warning(`请先录制或选择${hand === 'LEFT' ? '左' : '右'}手视频。`)
    return
  }
  if (!(await assertSessionMatchesPatient())) return

  uploading.value = hand
  try {
    const id = await ensureSession()
    if (!id) return
    if (!(await assertSessionMatchesPatient())) return

    const file =
      blob instanceof File
        ? blob
        : new File([blob], `${hand.toLowerCase()}-tapping.webm`, { type: blob.type })
    summary.value = await assessmentApi.uploadFingerTapping(id, file, hand, 'UNKNOWN')
    clips.value[hand] = null
    files.value[hand] = null
    await loadSeries(hand)
    ElMessage.success('分析完成')
  } catch (error) {
    const apiError = toApiError(error)
    // The wording is for the operator; the code stays in the console.
    const plain = plainErrorMessage(error, '上传或分析失败。')
    const detail = apiError.detail as Record<string, unknown> | null
    const quality = detail?.quality as Record<string, unknown> | undefined
    if (quality) {
      const ratio = quality.valid_frame_ratio
      const cycles = quality.cycle_count
      ElMessage.warning(
        `${plain}` +
          (ratio !== undefined && ratio !== null ? `（有效帧比例 ${Number(ratio).toFixed(2)}）` : '') +
          (cycles !== undefined && cycles !== null ? `（有效周期 ${cycles} 个）` : ''),
      )
    } else {
      console.warn('[finger-tapping] analysis failed', apiError.code, apiError.detail)
      ElMessage.warning(plain)
    }
  } finally {
    uploading.value = null
  }
}

function metricOf(hand: 'left' | 'right', key: keyof FingerTappingResult): string {
  const row = summary.value?.[hand]
  if (!row) return NO_DATA
  const value = row[key]
  if (value === null || value === undefined) return NO_DATA
  const spec = [...PRIMARY_ROWS, ...QUALITY_ROWS].find((r) => r.key === key)
  return `${Number(value).toFixed(spec?.digits ?? 3)}${spec?.unit ?? ''}`
}

onMounted(async () => {
  const fromQuery = route.query.patientId
  if (typeof fromQuery === 'string' && fromQuery) await usePatient(fromQuery)
})
</script>

<template>
  <!-- Function first: without a patient in the query, ask for one. -->
  <PatientSelector
    v-if="!hasPatient"
    title="选择患者"
    description="搜索姓名或患者编号，选择后即可开始手指敲击评估。"
    @select="(p) => usePatient(p.id)"
  />

  <div v-else v-loading="loading" class="pd-page">
    <router-link class="pd-back" :to="{ name: 'assessment', query: { patientId } }">
      <el-icon><ArrowLeft /></el-icon>返回评估中心
    </router-link>

    <div class="pd-page-header">
      <div>
        <h1 class="pd-page-title">手指敲击评估（Finger Tapping）</h1>
        <p class="pd-page-subtitle">
          左右手分别录制、分别保存、分别分析。建议录制 10～20 秒。
        </p>
      </div>
    </div>

    <SelectedPatientBar v-if="patient" :patient="patient" @change="patient = null" />

    <el-alert type="info" show-icon :closable="false" style="margin-bottom: 16px">
      <template #title>录制提示</template>
      <ul class="tips">
        <li>请将完整手掌放在摄像头前</li>
        <li>使用拇指和食指，连续进行张开—闭合动作</li>
        <li>尽量快速且规律，避免手掌离开画面</li>
      </ul>
    </el-alert>

    <div class="pd-grid pd-grid-2">
      <div v-for="hand in (['LEFT', 'RIGHT'] as const)" :key="hand" class="pd-card">
        <div class="pd-card-header">
          <span class="pd-card-title">{{ hand === 'LEFT' ? '左手' : '右手' }}</span>
          <el-tag v-if="summary?.[hand === 'LEFT' ? 'left' : 'right']" type="success" size="small">
            已有结果
          </el-tag>
          <el-tag v-else type="info" size="small">暂无结果</el-tag>
        </div>
        <div class="pd-card-body">
          <VideoCapturePanel
            :max-seconds="20"
            :instruction="`录制${hand === 'LEFT' ? '左' : '右'}手：手掌完整入镜，拇指与食指连续开合 10–20 秒。`"
            @change="(payload) => onClipChange(hand, payload)"
          />
          <el-button
            type="primary"
            class="pd-big-action"
            style="width: 100%; margin-top: 12px"
            :loading="uploading === hand"
            @click="upload(hand)"
          >
            分析{{ hand === 'LEFT' ? '左手' : '右手' }}
          </el-button>

          <p
            v-if="summary?.[hand === 'LEFT' ? 'left' : 'right']"
            class="pd-muted"
            style="font-size: 12px; margin: 10px 0 0"
          >
            分析时间：{{
              formatDateTime(
                (hand === 'LEFT' ? summary?.left : summary?.right)?.created_at ?? null,
              )
            }}
          </p>
        </div>
      </div>
    </div>

    <div class="pd-card">
      <div class="pd-card-header">
        <span class="pd-card-title">运动学指标</span>
        <el-tooltip content="没有结果时显示「暂无数据」，不会显示 0 或占位值" placement="top">
          <el-icon class="pd-muted"><InfoFilled /></el-icon>
        </el-tooltip>
      </div>
      <div class="pd-card-body">
        <el-table :data="PRIMARY_ROWS" size="small">
          <el-table-column label="指标" min-width="190">
            <template #default="{ row }">
              {{ row.label }}
              <el-tooltip v-if="row.hint" :content="row.hint" placement="top">
                <el-icon class="pd-muted" style="margin-left: 4px"><InfoFilled /></el-icon>
              </el-tooltip>
            </template>
          </el-table-column>
          <el-table-column label="左手" width="150" align="right">
            <template #default="{ row }">{{ metricOf('left', row.key) }}</template>
          </el-table-column>
          <el-table-column label="右手" width="150" align="right">
            <template #default="{ row }">{{ metricOf('right', row.key) }}</template>
          </el-table-column>
        </el-table>
      </div>
    </div>

    <div v-if="hasAnyResult" class="pd-grid pd-grid-2">
      <div v-for="hand in (['LEFT', 'RIGHT'] as const)" :key="`chart-${hand}`" class="pd-card">
        <div class="pd-card-header">
          <span class="pd-card-title">
            {{ hand === 'LEFT' ? '左手' : '右手' }} 拇指-食指距离时间序列
          </span>
        </div>
        <div class="pd-card-body">
          <ApertureChart
            v-if="timeseries[hand]"
            :frames="timeseries[hand]!.series.frame_index"
            :values="timeseries[hand]!.series.aperture_filtered"
            :peak-frames="timeseries[hand]!.peak_frames"
          />
          <div v-else class="pd-empty">该结果未保存时间序列数据。</div>
          <p class="pd-muted" style="font-size: 12px; margin: 10px 0 0">
            曲线为掌宽归一化后的拇指-食指距离（已做 9 Hz 低通滤波），红点为检测到的敲击峰值。
            峰值之间的间隔决定周期与全部变异指标。
          </p>
        </div>
      </div>
    </div>

    <div class="pd-card">
      <div class="pd-card-header">
        <span class="pd-card-title">左右手差异（左手 − 右手）</span>
      </div>
      <div class="pd-card-body">
        <el-table :data="summary?.comparisons ?? []" size="small" empty-text="暂无结果">
          <el-table-column label="指标">
            <template #default="{ row }">{{ COMPARISON_LABELS[row.metric] ?? row.metric }}</template>
          </el-table-column>
          <el-table-column label="左手" width="130" align="right">
            <template #default="{ row }">{{ formatNumber(row.left, 3) }}</template>
          </el-table-column>
          <el-table-column label="右手" width="130" align="right">
            <template #default="{ row }">{{ formatNumber(row.right, 3) }}</template>
          </el-table-column>
          <el-table-column label="绝对差异" width="130" align="right">
            <template #default="{ row }">{{ formatNumber(row.absolute_difference, 3) }}</template>
          </el-table-column>
          <el-table-column label="不对称比" width="130" align="right">
            <template #default="{ row }">{{ formatNumber(row.asymmetry_ratio, 3) }}</template>
          </el-table-column>
        </el-table>
        <p class="pd-muted" style="font-size: 12px; margin: 12px 0 0">
          左右差异仅作为运动表现差异展示，<strong>不得</strong>用于判断疾病侧别。
        </p>
      </div>
    </div>

    <div class="pd-card">
      <div class="pd-card-header"><span class="pd-card-title">质量控制</span></div>
      <div class="pd-card-body">
        <el-table :data="QUALITY_ROWS" size="small">
          <el-table-column label="指标" min-width="190">
            <template #default="{ row }">
              {{ row.label }}
              <el-tooltip v-if="row.hint" :content="row.hint" placement="top">
                <el-icon class="pd-muted" style="margin-left: 4px"><InfoFilled /></el-icon>
              </el-tooltip>
            </template>
          </el-table-column>
          <el-table-column label="左手" width="150" align="right">
            <template #default="{ row }">{{ metricOf('left', row.key) }}</template>
          </el-table-column>
          <el-table-column label="右手" width="150" align="right">
            <template #default="{ row }">{{ metricOf('right', row.key) }}</template>
          </el-table-column>
        </el-table>
        <p class="pd-muted" style="font-size: 12px; margin: 12px 0 0">
          质量不足时系统会拒绝出结果并给出原因（未检测到手 / 有效帧比例过低 / 周期数不足等），
          不会硬算出不可靠的指标。
        </p>
      </div>
    </div>

  </div>
</template>

<style scoped>
.tips {
  margin: 4px 0 0;
  padding-left: 18px;
}
</style>
