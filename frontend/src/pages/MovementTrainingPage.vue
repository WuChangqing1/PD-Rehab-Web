<script setup lang="ts">
/**
 * Movement / Pose training.
 *
 * Card layout follows the fitness module already deployed on the same host; the
 * figures are our own inline SVG because that site's photographs currently 404
 * and a broken image is worse than an honest diagram.
 *
 * Flow: pick an exercise -> open a session -> record with the camera or upload a
 * clip -> the backend runs MediaPipe Pose and returns raw metrics. The analysis
 * runs on the server, not in the browser, so what the patient sees afterwards is
 * the same number the database holds.
 *
 * No display score is shown anywhere: the formulas are undefined, so the API
 * returns null for all four and the page says so instead of inventing one.
 */
import { computed, onBeforeUnmount, onMounted, ref } from 'vue'
import { useRoute } from 'vue-router'
import { ElMessage } from 'element-plus'
import { Refresh, Upload, VideoCamera, VideoPlay } from '@element-plus/icons-vue'

import MedicalDisclaimer from '@/components/MedicalDisclaimer.vue'
import { patientApi, poseApi } from '@/api'
import { notifyError } from '@/api/client'
import PoseFigure from '@/pose/PoseFigure.vue'
import { presentationFor } from '@/pose/exercises'
import { PIANO_INPUT_SOURCE_LABELS, type PianoInputSource } from '@/types'
import type {
  Patient,
  PoseAnalysisResponse,
  PoseExerciseDefinition,
  PoseSession,
  PoseThresholds,
} from '@/types'
import { NO_DATA, formatDateTime, formatNumber } from '@/utils/format'

const route = useRoute()
const patientId = computed(() => String(route.params.id))

const patient = ref<Patient | null>(null)
const exercises = ref<PoseExerciseDefinition[]>([])
const thresholds = ref<PoseThresholds | null>(null)
const history = ref<PoseSession[]>([])
const loading = ref(false)

const selectedKey = ref<string | null>(null)
const sessionId = ref<string | null>(null)
const analyzing = ref(false)
const result = ref<PoseAnalysisResponse | null>(null)
const rejection = ref<{
  gate_failures: string[]
  quality: Record<string, unknown>
  warnings: string[]
} | null>(null)

const cameraOn = ref(false)
const recording = ref(false)
const cameraError = ref<string | null>(null)
const recordedBlob = ref<Blob | null>(null)
const recordedUrl = ref<string | null>(null)
const recordedSeconds = ref(0)

let stream: MediaStream | null = null
let recorder: MediaRecorder | null = null
let timer: number | null = null
const videoEl = ref<HTMLVideoElement | null>(null)

const selected = computed(
  () => exercises.value.find((e) => e.key === selectedKey.value) ?? null,
)

const METRIC_LABELS: Record<string, string> = {
  left_shoulder_max_angle_deg: '左肩最大角度',
  right_shoulder_max_angle_deg: '右肩最大角度',
  left_right_angle_difference_deg: '左右角度差',
  trunk_angle_deg: '躯干侧屈角',
  hold_time_sec: '保持时间',
  repetition_count: '完成次数',
  repetition_interval_ms: '动作周期',
  movement_speed_deg_per_sec: '动作速度',
  angle_std_deg: '角度标准差（稳定性）',
  valid_pose_frame_ratio: '有效帧比例',
}

const METRIC_UNITS: Record<string, string> = {
  left_shoulder_max_angle_deg: '°',
  right_shoulder_max_angle_deg: '°',
  left_right_angle_difference_deg: '°',
  trunk_angle_deg: '°',
  hold_time_sec: 's',
  repetition_count: '次',
  repetition_interval_ms: 'ms',
  movement_speed_deg_per_sec: '°/s',
  angle_std_deg: '°',
  valid_pose_frame_ratio: '',
}

const GATE_LABELS: Record<string, string> = {
  NO_POSE_DETECTED: '未检出人体',
  LOW_VALID_FRAME_RATIO: '有效帧比例过低',
  VIDEO_TOO_SHORT: '视频过短',
  LOW_LANDMARK_VISIBILITY: '关键点可见度过低',
  NO_MOVEMENT_DETECTED: '未检测到动作幅度',
  INSUFFICIENT_REPETITIONS: '未完成一个完整动作',
}

function metricRows(): Array<{ key: string; label: string; value: string }> {
  const metrics = result.value?.session.raw_metrics_json
  if (!metrics) return []
  return Object.keys(METRIC_LABELS).map((key) => {
    const raw = metrics[key]
    const value =
      raw === null || raw === undefined || typeof raw === 'object'
        ? NO_DATA
        : `${formatNumber(Number(raw), key === 'repetition_count' ? 0 : 2)}${METRIC_UNITS[key]}`
    return { key, label: METRIC_LABELS[key], value }
  })
}

function sourceLabel(source: PianoInputSource): string | null {
  return source === 'HUMAN_KEYBOARD' ? null : (PIANO_INPUT_SOURCE_LABELS[source] ?? source)
}

/**
 * Recording formats, best first.
 *
 * A browser records with MediaRecorder: Chrome and Firefox produce webm, Safari
 * produces mp4. The backend accepts both, but the uploaded filename must carry
 * the extension of the container that is actually inside it -- naming a webm
 * "recording.mp4" would pass the extension check while lying about the format.
 */
const RECORDING_FORMATS: Array<{ mimeType: string; extension: string }> = [
  { mimeType: 'video/mp4;codecs=h264', extension: 'mp4' },
  { mimeType: 'video/mp4', extension: 'mp4' },
  { mimeType: 'video/webm;codecs=vp9', extension: 'webm' },
  { mimeType: 'video/webm;codecs=vp8', extension: 'webm' },
  { mimeType: 'video/webm', extension: 'webm' },
]

const recordedName = ref('recording.webm')

function pickRecordingFormat(): { mimeType: string; extension: string } {
  if (typeof MediaRecorder === 'undefined') {
    return { mimeType: '', extension: 'webm' }
  }
  for (const format of RECORDING_FORMATS) {
    if (MediaRecorder.isTypeSupported(format.mimeType)) return format
  }
  // No declared support: let the browser choose and keep the webm default.
  return { mimeType: '', extension: 'webm' }
}

async function load() {
  loading.value = true
  try {
    patient.value = await patientApi.get(patientId.value)
    exercises.value = await poseApi.exercises()
    thresholds.value = await poseApi.thresholds()
    const page = await poseApi.history(patientId.value, 10)
    history.value = page.items
  } catch (error) {
    notifyError(error, '无法加载动作训练信息。')
  } finally {
    loading.value = false
  }
}

function selectExercise(key: string) {
  selectedKey.value = key
  sessionId.value = null
  result.value = null
  rejection.value = null
  clearRecording()
}

async function ensureSession(): Promise<string | null> {
  if (sessionId.value) return sessionId.value
  if (!selectedKey.value) return null
  try {
    const session = await poseApi.startSession(patientId.value, {
      exercise_type: selectedKey.value,
    })
    sessionId.value = session.id
    return session.id
  } catch (error) {
    notifyError(error, '无法创建动作训练会话。')
    return null
  }
}

// ------------------------------------------------------------------- camera
async function startCamera() {
  cameraError.value = null
  try {
    stream = await navigator.mediaDevices.getUserMedia({
      video: { width: { ideal: 1280 }, height: { ideal: 720 } },
      audio: false,
    })
    cameraOn.value = true
    if (videoEl.value) {
      videoEl.value.srcObject = stream
      await videoEl.value.play()
    }
  } catch (error) {
    cameraError.value =
      error instanceof Error ? error.message : '无法打开摄像头，请检查浏览器权限。'
  }
}

function stopCamera() {
  stream?.getTracks().forEach((track) => track.stop())
  stream = null
  cameraOn.value = false
  recording.value = false
  if (timer !== null) {
    window.clearInterval(timer)
    timer = null
  }
}

function startRecording() {
  if (!stream) return
  recordedBlob.value = null
  recordedSeconds.value = 0
  const chunks: Blob[] = []
  const format = pickRecordingFormat()
  recordedName.value = `recording.${format.extension}`

  const options = format.mimeType ? { mimeType: format.mimeType } : undefined
  recorder = new MediaRecorder(stream, options)
  const actualType = recorder.mimeType || format.mimeType || 'video/webm'
  recorder.ondataavailable = (event) => {
    if (event.data.size > 0) chunks.push(event.data)
  }
  recorder.onstop = () => {
    // Trust the recorder's own type over the requested one.
    const blob = new Blob(chunks, { type: actualType })
    recordedBlob.value = blob
    if (recordedUrl.value) URL.revokeObjectURL(recordedUrl.value)
    recordedUrl.value = URL.createObjectURL(blob)
  }
  recorder.start()
  recording.value = true
  timer = window.setInterval(() => {
    recordedSeconds.value += 0.1
    // Keep the demo honest about length: the gates reject anything under 2 s.
    if (recordedSeconds.value >= 60) stopRecording()
  }, 100)
}

function stopRecording() {
  recorder?.stop()
  recorder = null
  recording.value = false
  if (timer !== null) {
    window.clearInterval(timer)
    timer = null
  }
}

function onFilePicked(event: Event) {
  const input = event.target as HTMLInputElement
  const file = input.files?.[0]
  if (!file) return
  recordedBlob.value = file
  recordedName.value = file.name
  if (recordedUrl.value) URL.revokeObjectURL(recordedUrl.value)
  recordedUrl.value = URL.createObjectURL(file)
}

function clearRecording() {
  recordedBlob.value = null
  if (recordedUrl.value) URL.revokeObjectURL(recordedUrl.value)
  recordedUrl.value = null
  recordedSeconds.value = 0
  recordedName.value = 'recording.webm'
  result.value = null
  rejection.value = null
}

// ------------------------------------------------------------------ analyse
async function analyze() {
  const blob = recordedBlob.value
  if (!blob) {
    ElMessage.warning('请先录制或选择一个视频文件。')
    return
  }
  const id = await ensureSession()
  if (!id) return

  analyzing.value = true
  result.value = null
  rejection.value = null
  try {
    // A picked file keeps its own name; a recording uses the extension that
    // matches the container the browser actually produced.
    const filename = blob instanceof File ? blob.name : recordedName.value
    const response = await poseApi.analyze(id, blob, filename)
    result.value = response
    ElMessage.success('分析完成，指标已保存')
    await load()
  } catch (error) {
    // A quality refusal is 422 with the measured report; show the reason rather
    // than a generic failure, and never dress it up as a result.
    const detail = (error as { response?: { status?: number; data?: { error?: { detail?: unknown } } } })
      ?.response
    const payload = detail?.data?.error?.detail as
      | { gate_failures?: string[]; quality?: Record<string, unknown>; warnings?: string[] }
      | undefined
    if (detail?.status === 422 && payload?.gate_failures) {
      rejection.value = {
        gate_failures: payload.gate_failures,
        quality: payload.quality ?? {},
        warnings: payload.warnings ?? [],
      }
      ElMessage.warning('本次录制未通过质量控制')
    } else {
      notifyError(error, '动作分析失败。')
    }
  } finally {
    analyzing.value = false
  }
}

function reset() {
  sessionId.value = null
  clearRecording()
  result.value = null
  rejection.value = null
}

onMounted(load)
onBeforeUnmount(() => {
  stopCamera()
  if (recordedUrl.value) URL.revokeObjectURL(recordedUrl.value)
})
</script>

<template>
  <div v-loading="loading" class="pd-page">
    <div class="pd-page-header">
      <div>
        <h1 class="pd-page-title">动作训练（Pose）</h1>
        <p class="pd-page-subtitle">
          患者：{{ patient?.name ?? '—' }}。五个简单动作，使用摄像头录制或上传视频，
          由服务端 MediaPipe Pose 逐帧提取 33 个关键点后计算原始指标。
        </p>
      </div>
      <el-button :icon="Refresh" @click="load">刷新</el-button>
    </div>

    <el-alert
      type="warning"
      show-icon
      :closable="false"
      title="请在医生或工作人员指导下完成。如出现疼痛、头晕或明显不适，请立即停止。"
      style="margin-bottom: 16px"
    />

    <el-alert
      type="info"
      show-icon
      :closable="false"
      title="本模块只输出原始指标，不输出 0–100 展示分"
      description="规格里的完成度 / ROM / 对称性 / 稳定性分数只有示意值，没有公式。公式定义并版本化之前，这些字段恒为空，页面也不会显示任何编造的分数。"
      style="margin-bottom: 16px"
    />

    <!-- ------------------------------------------- exercise cards -->
    <div class="pd-card">
      <div class="pd-card-header">
        <span class="pd-card-title">选择动作</span>
        <span class="pd-muted" style="font-size: 12px">
          共 {{ exercises.length }} 个动作
        </span>
      </div>
      <div class="pd-card-body">
        <div class="exercise-grid">
          <button
            v-for="exercise in exercises"
            :key="exercise.key"
            class="exercise-card"
            :class="{ 'is-selected': exercise.key === selectedKey }"
            type="button"
            @click="selectExercise(exercise.key)"
          >
            <span
              class="area-tag"
              :style="{ background: presentationFor(exercise.key).areaColor }"
            >
              {{ presentationFor(exercise.key).area }}
            </span>
            <span class="figure-box">
              <PoseFigure :exercise="exercise.key" />
            </span>
            <span class="exercise-name">{{ exercise.name_zh }}</span>
            <span class="exercise-name-en">{{ presentationFor(exercise.key).nameEn }}</span>
            <span class="chip-row">
              <span v-for="chip in presentationFor(exercise.key).chips" :key="chip" class="chip">
                {{ chip }}
              </span>
            </span>
            <span class="exercise-target">
              <template v-if="exercise.target_repetitions">
                目标 {{ exercise.target_repetitions }} 次
              </template>
              <template v-if="exercise.hold_time_sec">
                · 保持 {{ exercise.hold_time_sec }} 秒
              </template>
            </span>
          </button>
        </div>
      </div>
    </div>

    <!-- ------------------------------------------- recording -->
    <div v-if="selected" class="pd-grid pd-grid-2">
      <div class="pd-card">
        <div class="pd-card-header">
          <span class="pd-card-title">录制：{{ selected.name_zh }}</span>
        </div>
        <div class="pd-card-body">
          <p class="pd-secondary" style="margin-top: 0">{{ selected.description }}</p>
          <p v-if="selected.contraindications.length" class="pd-muted" style="font-size: 12px">
            禁忌：{{ selected.contraindications.join('、') }}
          </p>

          <el-alert
            v-if="cameraError"
            type="error"
            show-icon
            :closable="false"
            :title="cameraError"
            style="margin-bottom: 12px"
          />

          <div class="preview">
            <video v-show="cameraOn" ref="videoEl" class="preview-video" muted playsinline />
            <video v-if="!cameraOn && recordedUrl" :src="recordedUrl" class="preview-video" controls />
            <div v-if="!cameraOn && !recordedUrl" class="preview-empty">
              打开摄像头录制，或直接上传一段已有的视频文件
            </div>
          </div>

          <div class="record-actions">
            <el-button v-if="!cameraOn" :icon="VideoCamera" @click="startCamera">
              打开摄像头
            </el-button>
            <template v-else>
              <el-button
                v-if="!recording"
                type="primary"
                :icon="VideoPlay"
                @click="startRecording"
              >
                开始录制
              </el-button>
              <el-button v-else type="danger" @click="stopRecording">
                停止录制（{{ recordedSeconds.toFixed(1) }} s）
              </el-button>
              <el-button @click="stopCamera">关闭摄像头</el-button>
            </template>

            <el-upload
              :auto-upload="false"
              :show-file-list="false"
              accept="video/*"
              :on-change="onFilePicked as never"
            >
              <el-button :icon="Upload">选择视频文件</el-button>
            </el-upload>
          </div>

          <div class="record-actions">
            <el-button
              type="primary"
              :loading="analyzing"
              :disabled="!recordedBlob"
              @click="analyze"
            >
              上传并分析
            </el-button>
            <el-button :disabled="analyzing" @click="reset">重来</el-button>
          </div>

          <p class="pd-muted" style="font-size: 12px; margin: 8px 0 0">
            质量门限（来自服务端）：
            时长 ≥ {{ thresholds?.min_duration_sec ?? 2 }} 秒、
            有效帧比例 ≥ {{ thresholds?.min_valid_frame_ratio ?? 0.5 }}、
            关键点可见度 ≥ {{ thresholds?.min_landmark_visibility ?? 0.5 }}、
            动作幅度 ≥ {{ thresholds?.min_movement_range_deg ?? 10 }}°，
            且至少完成 1 次动作。分析在服务端进行，通常需要十几秒到一分钟。
          </p>
        </div>
      </div>

      <div class="pd-card">
        <div class="pd-card-header">
          <span class="pd-card-title">分析结果</span>
          <el-tag v-if="result" type="success" size="small">已通过质量门限</el-tag>
          <el-tag v-else-if="rejection" type="warning" size="small">未通过</el-tag>
        </div>
        <div class="pd-card-body">
          <div v-if="!result && !rejection" class="pd-empty">
            还没有结果。录制或上传视频后点击「上传并分析」。
          </div>

          <template v-else-if="rejection">
            <el-alert
              type="warning"
              show-icon
              :closable="false"
              title="本次录制未通过质量控制，不作为有效测量值"
              style="margin-bottom: 12px"
            />
            <ul class="gate-list">
              <li v-for="gate in rejection.gate_failures" :key="gate">
                {{ GATE_LABELS[gate] ?? gate }}（<span class="pd-mono">{{ gate }}</span>）
              </li>
            </ul>
            <p class="pd-secondary" style="font-size: 13px">
              实测：有效帧
              {{ (rejection.quality as Record<string, number>).valid_frame_count ?? '—' }} /
              {{ (rejection.quality as Record<string, number>).frame_count ?? '—' }}，
              时长 {{ formatNumber(Number((rejection.quality as Record<string, number>).duration_sec ?? 0), 1) }} 秒。
              请让患者完整入镜、动作幅度更大一些后重录。
            </p>
          </template>

          <template v-else>
            <el-table :data="metricRows()" size="small">
              <el-table-column label="原始指标" min-width="200">
                <template #default="{ row }">{{ row.label }}</template>
              </el-table-column>
              <el-table-column label="数值" width="140" align="right">
                <template #default="{ row }">{{ row.value }}</template>
              </el-table-column>
            </el-table>

            <p class="pd-muted" style="font-size: 12px; margin-top: 10px">
              展示分（完成度 / ROM / 对称性 / 稳定性）：<b>公式未定义，因此为空</b>。
              算法版本 <span class="pd-mono">{{ result?.session.algorithm_version ?? NO_DATA }}</span>。
            </p>

            <el-alert
              v-for="warning in result?.warnings ?? []"
              :key="warning"
              type="info"
              show-icon
              :closable="false"
              :title="warning"
              style="margin-top: 8px"
            />
          </template>
        </div>
      </div>
    </div>

    <!-- ------------------------------------------- history -->
    <div class="pd-card">
      <div class="pd-card-header"><span class="pd-card-title">最近动作训练记录</span></div>
      <div class="pd-card-body">
        <el-table :data="history" size="small" empty-text="暂无动作训练记录">
          <el-table-column label="动作" min-width="160">
            <template #default="{ row }">
              {{ exercises.find((e) => e.key === row.exercise_type)?.name_zh ?? row.exercise_type }}
            </template>
          </el-table-column>
          <el-table-column label="完成次数" width="100" align="right">
            <template #default="{ row }">
              {{ row.repetition_count ?? NO_DATA }}
            </template>
          </el-table-column>
          <el-table-column label="保持时间" width="110" align="right">
            <template #default="{ row }">
              {{ row.hold_time_sec === null ? NO_DATA : `${formatNumber(row.hold_time_sec, 2)} s` }}
            </template>
          </el-table-column>
          <el-table-column label="有效帧比例" width="120" align="right">
            <template #default="{ row }">
              {{
                row.valid_pose_frame_ratio === null
                  ? NO_DATA
                  : `${(row.valid_pose_frame_ratio * 100).toFixed(0)}%`
              }}
            </template>
          </el-table-column>
          <el-table-column label="开始时间" width="170">
            <template #default="{ row }">{{ formatDateTime(row.started_at) }}</template>
          </el-table-column>
          <el-table-column label="状态" width="110">
            <template #default="{ row }">
              <el-tag v-if="row.completed_at" type="success" size="small">已通过</el-tag>
              <el-tag v-else type="info" size="small">未通过 / 未分析</el-tag>
            </template>
          </el-table-column>
          <el-table-column label="来源" width="150">
            <template #default="{ row }">
              <el-tag v-if="sourceLabel(row.input_source)" type="warning" size="small">
                {{ sourceLabel(row.input_source) }}
              </el-tag>
              <span v-else class="pd-muted">真人录制</span>
            </template>
          </el-table-column>
        </el-table>
      </div>
    </div>

    <MedicalDisclaimer />
  </div>
</template>

<style scoped>
.exercise-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(200px, 1fr));
  gap: 12px;
}

.exercise-card {
  position: relative;
  display: flex;
  flex-direction: column;
  align-items: flex-start;
  gap: 4px;
  padding: 14px 12px 12px;
  text-align: left;
  background: var(--pd-surface);
  border: 1px solid var(--pd-border);
  border-radius: 10px;
  cursor: pointer;
  transition: border-color 0.15s, box-shadow 0.15s, transform 0.15s;
}

.exercise-card:hover {
  border-color: var(--pd-primary);
  box-shadow: 0 4px 14px rgb(27 111 184 / 12%);
}

.exercise-card.is-selected {
  border-color: var(--pd-primary);
  box-shadow: 0 0 0 2px rgb(27 111 184 / 18%);
}

.area-tag {
  position: absolute;
  top: 10px;
  left: 10px;
  padding: 1px 8px;
  border-radius: 10px;
  color: #fff;
  font-size: 11px;
}

.figure-box {
  width: 100%;
  height: 110px;
  display: flex;
  align-items: center;
  justify-content: center;
  background: #f7f9fb;
  border-radius: 8px;
  margin-bottom: 6px;
}

.exercise-name {
  font-size: 15px;
  font-weight: 600;
  color: var(--pd-text);
}

.exercise-name-en {
  font-size: 12px;
  color: var(--pd-text-secondary);
}

.chip-row {
  display: flex;
  flex-wrap: wrap;
  gap: 4px;
  margin-top: 2px;
}

.chip {
  padding: 1px 7px;
  border-radius: 8px;
  background: #eef2f6;
  color: var(--pd-text-secondary);
  font-size: 11px;
}

.exercise-target {
  margin-top: 4px;
  font-size: 12px;
  color: var(--pd-text-secondary);
}

.preview {
  position: relative;
  width: 100%;
  aspect-ratio: 16 / 9;
  background: #10151a;
  border-radius: 8px;
  overflow: hidden;
  margin-bottom: 12px;
}

.preview-video {
  width: 100%;
  height: 100%;
  object-fit: contain;
  display: block;
}

.preview-empty {
  position: absolute;
  inset: 0;
  display: flex;
  align-items: center;
  justify-content: center;
  color: #8b97a3;
  font-size: 13px;
  padding: 0 24px;
  text-align: center;
}

.record-actions {
  display: flex;
  flex-wrap: wrap;
  gap: 10px;
  margin-bottom: 10px;
}

.gate-list {
  margin: 0 0 10px;
  padding-left: 18px;
  font-size: 13px;
  color: var(--el-color-warning);
  line-height: 1.9;
}
</style>
