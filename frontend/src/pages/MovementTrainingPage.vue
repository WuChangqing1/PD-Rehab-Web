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
import { computed, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { onBeforeRouteUpdate, useRoute, useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { ArrowLeft, Refresh } from '@element-plus/icons-vue'

import MetricSummaryCards from '@/components/MetricSummaryCards.vue'
import SelectedPatientBar from '@/components/SelectedPatientBar.vue'
import TrainingStartGate from '@/components/TrainingStartGate.vue'
import { useTrainingStartGate } from '@/composables/useTrainingStartGate'
import { usePatientContextStore } from '@/stores/patientContext'
import { RhythmEngine } from '@/ballet/rhythmEngine'
import OrientationHint from '@/components/OrientationHint.vue'
import PatientTaskLayout from '@/components/PatientTaskLayout.vue'
import PoseHistoryTable from '@/components/PoseHistoryTable.vue'
import VideoCapturePanel from '@/components/VideoCapturePanel.vue'
import BalletRhythmPanel from '@/ballet/BalletRhythmPanel.vue'
import ExerciseDemoPanel from '@/ballet/ExerciseDemoPanel.vue'
import { resolveDemo } from '@/ballet/demoAssets'
import { poseApi } from '@/api'
import { notifyError } from '@/api/client'
import PoseFigure from '@/pose/PoseFigure.vue'
import { exerciseName, presentationFor } from '@/pose/exercises'
import { resultCardsFor } from '@/pose/resultProfile'
import { useTaskModeStore } from '@/stores/taskMode'
import type {
  Patient,
  PianoInputSource,
  PoseAnalysisResponse,
  PoseExerciseDefinition,
  PoseSession,
  PoseThresholds,
} from '@/types'
import { NO_DATA, formatNumber } from '@/utils/format'
import { DEFAULT_RECORDING_NAME } from '@/utils/recording'

/**
 * Recording length cap, in seconds.
 *
 * This only stops a forgotten camera. The quality gates measure duration from
 * the decoded video on the server, so this number never decides whether a
 * recording is accepted. 120 s leaves room for six slow repetitions of the
 * trunk exercises, which is the longest the protocol asks for.
 */
const MAX_RECORDING_SECONDS = 120

const route = useRoute()
const router = useRouter()

/**
 * Provenance of the recording being analysed.
 *
 * Normal use is HUMAN_KEYBOARD. Opening the page with `?selftest=1` declares
 * SYNTHETIC_SELFTEST, so the recording-and-upload path can be exercised without
 * the resulting session claiming to be a patient measurement.
 *
 * Without this the upload pages could only ever produce rows marked as real, which
 * is how test clips ended up in the database as patient data and had to be removed
 * by hand.
 */
const inputSource = computed<PianoInputSource>(() =>
  route.query.selftest === '1' ? 'SYNTHETIC_SELFTEST' : 'HUMAN_KEYBOARD',
)
const isSyntheticInput = computed(() => inputSource.value !== 'HUMAN_KEYBOARD')

/**
 * Names that change when the exercise is performed seated.
 *
 * `spec_decisions.md` D04 records the decision: `BALLET_TENDU` supports both
 * standing and seated, but the seated variant is not a standard ballet tendu --
 * it is a knee extension performed while seated, with the foot reaching the floor
 * rather than the leg being worked through a turned-out tendu. The decision was to
 * show the seated form as 「坐姿伸腿改编版」 and not to head it with the standing
 * name.
 *
 * That decision was written down and never implemented: the exercise carries one
 * `name_zh` and one `name_en` for both modes, and the card shows 「伸腿点地 /
 * Tendu」 with the mode chosen separately. So a seated patient was told they were
 * doing a Tendu. This is the same class of problem as 半蹲, which was renamed for
 * exactly this reason -- a label that describes a movement the patient is not
 * doing.
 *
 * The override lives here rather than in the exercise definition because the
 * distinction is a presentation one and the backend definition stays canonical
 * for metrics, cues and history. A seated variant that grows its own metrics
 * should get its own definition instead.
 */
const SEATED_OVERRIDES: Record<string, { name_zh: string; name_en: string }> = {
  BALLET_TENDU: { name_zh: '坐姿伸腿改编版', name_en: 'Seated Knee Extension' },
}

function modeAwareName(key: string, fallback: string): string {
  if (executionMode.value !== 'SEATED') return fallback
  return SEATED_OVERRIDES[key]?.name_zh ?? fallback
}

function modeAwareEnglishName(key: string, fallback: string): string {
  if (executionMode.value !== 'SEATED') return fallback
  return SEATED_OVERRIDES[key]?.name_en ?? fallback
}
/**
 * The patient comes from the query, not the path: function-first routing means
 * `/training/movement?patientId=…`. Params remain as a fallback for the old
 * patient-centric links, which now redirect here.
 */
const patientId = computed(() => {
  const fromQuery = route.query.patientId
  if (typeof fromQuery === 'string' && fromQuery) return fromQuery
  const fromParams = route.params.id
  return typeof fromParams === 'string' ? fromParams : ''
})
const patientStore = usePatientContextStore()
const balletAudio = new RhythmEngine()
let audioUnlock: Promise<boolean> | null = null

/**
 * Framing advice shown to whoever holds the camera.
 *
 * Leg exercises need the whole body; a shoulder-only shot cannot measure a
 * tendu. The wording comes from the exercise, not from a generic hint.
 */
const standPrompt = computed(() => {
  if (!selected.value) return ''
  const needsLegs = ['BALLET_TENDU', 'BALLET_DEMI_PLIE'].includes(selected.value.key)
  return needsLegs
    ? '请让患者全身进入画面（需要看到髋、膝、踝），扶好椅子，光线均匀。'
    : '请让患者上半身与髋部进入画面，正对或侧对镜头，光线均匀。'
})

const patient = ref<Patient | null>(null)
let patientLoadVersion = 0
let historyRequest = 0
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

/**
 * How the patient performs the exercise. Chosen by the doctor, because the
 * patient should not have to judge which version of a movement they are safe to
 * perform, and because the same angles measured seated and standing are not the
 * same task.
 */
const executionMode = ref<'SEATED' | 'STANDING_SUPPORTED'>('SEATED')

/** Only the exercises that support the chosen mode. */
const availableExercises = computed(() =>
  exercises.value.filter((e) => e.supported_modes.includes(executionMode.value)),
)

const selected = computed(
  () => availableExercises.value.find((e) => e.key === selectedKey.value) ?? null,
)

/** Patient mode: the doctor starts the task, the patient then sees only it. */
const started = ref(false)
const taskMode = useTaskModeStore()

const { state: startState, busy: startBusy, requestStart, selectPatient, cancelStart, changePatient } = useTrainingStartGate({
  async bind(next, signal) {
    patientLoadVersion++
    if (patient.value?.id !== next.id) {
      reset()
      history.value = []
    }
    patient.value = next
    await loadHistory(next.id, signal)
  },
  async prepare(next, signal) {
    if (!selected.value) throw new Error('请先选择一个动作。')
    if (!await audioUnlock) throw new Error('节拍声音尚未启用，请重新点击开始训练。')
    if (signal.aborted) return
    const session = await poseApi.startSession(next.id, {
      exercise_type: selected.value.key as never,
      execution_mode: executionMode.value,
      input_source: inputSource.value,
    })
    if (signal.aborted) return
    sessionId.value = session.id
    result.value = null
    rejection.value = null
  },
  start() {
    started.value = true
    taskMode.enter()
  },
})
function startTask() {
  if (!selected.value || startBusy.value) return
  audioUnlock = balletAudio.unlock().catch(() => false)
  requestStart()
}

function leaveTask() {
  started.value = false
  taskMode.exit()
  router.push({ name: 'training', query: { patientId: patientId.value } })
}

const recordedBlob = ref<Blob | null>(null)
const recordedName = ref(DEFAULT_RECORDING_NAME)
/** Handle on the shared capture panel so "重来" can clear its preview too. */
const captureRef = ref<{ clear: () => void } | null>(null)

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

/** One raw metric, formatted for display, or the shared "no data" token. */
function metricText(key: string): string {
  const raw = result.value?.session.raw_metrics_json?.[key]
  if (raw === null || raw === undefined || typeof raw === 'object') return NO_DATA
  return `${formatNumber(Number(raw), key === 'repetition_count' ? 0 : 2)}${METRIC_UNITS[key] ?? ''}`
}

function metricRows(): Array<{ key: string; label: string; value: string }> {
  if (!result.value?.session.raw_metrics_json) return []
  return Object.keys(METRIC_LABELS).map((key) => ({
    key,
    label: METRIC_LABELS[key],
    value: metricText(key),
  }))
}

/**
 * The few numbers that answer "did the movement happen, and how did it go".
 *
 * The card set is derived from the exercise's drive joint rather than hardcoded,
 * so a knee exercise shows knee angles and not shoulder angles. See
 * `pose/resultProfile.ts` for why. All raw metrics remain behind the disclosure,
 * together with the note that the display scores are empty because their formulas
 * are undefined.
 */
const summaryCards = computed(() => {
  const spec = resultCardsFor(selected.value?.drive_series)
  return spec.map((card) => ({
    label: card.label,
    value:
      card.shape === 'pair'
        ? `左 ${metricText(card.metrics[0])} · 右 ${metricText(card.metrics[1])}`
        : metricText(card.metrics[0]),
    note: card.note,
    emphasis: card.emphasis,
  }))
})

async function loadHistory(id: string, signal?: AbortSignal) {
  const request = ++historyRequest
  const page = await poseApi.history(id, 10)
  if (request === historyRequest && patient.value?.id === id && !signal?.aborted) history.value = page.items
}

async function load() {
  loading.value = true
  try {
    const [catalogue, limits] = await Promise.all([poseApi.exercises(), poseApi.thresholds()])
    exercises.value = catalogue
    thresholds.value = limits
    if (!selected.value) selectedKey.value = availableExercises.value[0]?.key ?? null
  } catch (error) {
    notifyError(error, '无法加载动作，请检查网络后刷新重试。')
  } finally { loading.value = false }
}

/**
 * What the patient's demonstration region may show.
 *
 * Resolved through the same review gate as the staff workspace, so a clip that
 * has not been watched and approved cannot reach the patient screen either. The
 * patient screen is the one place where showing the wrong video would actually
 * teach the wrong movement.
 */
const demoResolution = computed(() =>
  selected.value
    ? resolveDemo(selected.value.key, executionMode.value)
    : ({ kind: 'DIAGRAM', reason: 'NOT_SELECTED', note: '请先选择一个动作。' } as const),
)

/**
 * Absolute URL for a bundled demonstration asset.
 *
 * Built from BASE_URL so the same build works at the site root and under
 * `/pd-rehab/`. A hardcoded `/assets/...` would 404 on the deployed sub-path,
 * which is the failure mode docs/04 warns about.
 */
function demoAssetUrl(path: string): string {
  const base = import.meta.env?.BASE_URL ?? '/'
  return `${base.replace(/\/$/, '')}/${path.replace(/^\//, '')}`
}

function selectExercise(key: string) {
  if (startBusy.value || started.value) return
  selectedKey.value = key
  sessionId.value = null
  result.value = null
  rejection.value = null
  clearRecording()
}

async function ensureSession(): Promise<string | null> {
  if (!started.value || !patient.value || patient.value.is_deleted) return null
  if (sessionId.value) return sessionId.value
  if (!selectedKey.value) return null
  try {
    const session = await poseApi.startSession(patient.value.id, {
      exercise_type: selectedKey.value as never,
      execution_mode: executionMode.value,
      // Declared, not assumed. The API client defaults this to HUMAN_KEYBOARD, so
      // a clip uploaded merely to exercise the analysis path used to be recorded
      // as a patient measurement with no way to say otherwise.
      input_source: inputSource.value,
    })
    sessionId.value = session.id
    return session.id
  } catch (error) {
    notifyError(error, '无法创建训练记录。')
    return null
  }
}

// ------------------------------------------------------------------- capture
/**
 * The shared capture panel owns the camera and the file picker.
 *
 * This page used to hand-roll both, and its `el-upload` handler expected a DOM
 * event while Element Plus passes an `UploadFile` -- so choosing a file threw
 * and the analysis button could never enable. One implementation, one contract.
 */
function onClipChange(payload: { blob: Blob | null; name: string }) {
  recordedBlob.value = payload.blob
  recordedName.value = payload.name
}

function clearRecording() {
  recordedBlob.value = null
  recordedName.value = DEFAULT_RECORDING_NAME
  captureRef.value?.clear()
  result.value = null
  rejection.value = null
}

// ------------------------------------------------------------------ analyse
async function analyze() {
  if (analyzing.value || !started.value) return
  const blob = recordedBlob.value
  if (!blob) {
    ElMessage.warning('请先录制或选择一个视频文件。')
    return
  }
  analyzing.value = true
  const id = await ensureSession()
  if (!id) { analyzing.value = false; return }
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

watch(executionMode, () => {
  if (!selected.value) selectedKey.value = availableExercises.value[0]?.key ?? null
  reset()
})
watch(patientId, async (id) => {
  if (patient.value?.id === id) return
  const version = ++patientLoadVersion
  historyRequest++
  cancelStart()
  reset()
  history.value = []
  patient.value = null
  const next = id ? await patientStore.resolve(id) : patientStore.currentPatient
  if (version !== patientLoadVersion || id !== patientId.value) return
  patient.value = next
  if (next) {
    try { await loadHistory(next.id) }
    catch (error) { notifyError(error, '无法读取历史记录，请刷新重试。') }
  }
}, { immediate: true })
onBeforeRouteUpdate((to, from) => {
  if (started.value && to.query.patientId !== from.query.patientId) {
    ElMessage.warning('请先退出当前训练，再更换患者。')
    return false
  }
})
onBeforeUnmount(() => { patientLoadVersion++; historyRequest++; taskMode.exit(); balletAudio.dispose() })
onMounted(load)
// The capture panel releases its own camera and object URL on unmount.
</script>

<template>
  <!-- Function-first: with no patient in the query, ask for one. -->
  <TrainingStartGate :state="startState" :exercise="selected ? modeAwareName(selected.key, selected.name_zh) : '芭蕾动作训练'" @select="selectPatient" @cancel="cancelStart" @change="changePatient" />

  <!--
    Patient mode. The doctor chose the patient, the training mode and the
    exercise; the patient now sees the count, the instruction and the camera,
    and one permanent way out.
  -->
  <PatientTaskLayout
    v-if="started && selected && patient"
    :patient="patient"
    task="芭蕾动作训练"
    :instruction="modeAwareName(selected.key, selected.name_zh)"
    :progress="`目标 ${selected.target_repetitions ?? 3} 次`"
    back-label="返回康复训练"
    @exit="leaveTask"
  >
    <OrientationHint message="把手机放稳，横屏可以获得更大的画面区域。" />

    <!--
      The beat and the cue stay at the top and full width: the patient follows
      them continuously, so they must not be pushed into a column beside the
      video. The accompaniment comes from this one engine and the demonstration
      clip, when there is one, is muted, so there is never a second tempo.
    -->
    <div class="pd-card task-rhythm">
      <div class="pd-card-body">
        <BalletRhythmPanel
          :cues="selected.cues"
          :hold-beats="selected.hold_beats"
          :bpm="selected.default_bpm"
          :repetitions="selected.target_repetitions ?? 3"
          :audio-engine="balletAudio"
          auto-start
        />
      </div>
    </div>

    <!--
      TWO REGIONS, LABELLED DIFFERENTLY.

      The demonstration and the patient's own camera feed sit side by side and
      are never allowed to look like the same thing: one is headed 动作示范 and
      shows the reviewed movement, the other is headed 录制动作 and shows the
      patient. A patient who mistakes a recording of someone else for a live view
      of themselves will try to copy a body that is not theirs, so the headings
      are part of the safety design rather than decoration.

      With no approved clip the demonstration region is the movement diagram,
      labelled as a diagram. It is still worth showing -- it is the movement the
      patient was asked to do -- and it is not dressed up as footage.
    -->
    <div class="task-media-grid">
      <div class="pd-card demo-region">
        <div class="pd-card-header">
          <span class="pd-card-title">动作示范</span>
          <!--
            The tag says which of the two the patient is looking at. It said 示意
            unconditionally, and the note under it claimed a video was looping
            while the box held a diagram: the region never rendered a <video> at
            all. Saying the wrong one is worse than saying nothing, because the
            patient is told to copy footage that is not there.
          -->
          <el-tag v-if="demoResolution.kind === 'VIDEO'" type="success" effect="plain" size="small">
            视频
          </el-tag>
          <el-tag v-else type="info" effect="plain" size="small">示意</el-tag>
        </div>
        <div class="pd-card-body">
          <video
            v-if="demoResolution.kind === 'VIDEO'"
            class="task-demo-video"
            :src="demoAssetUrl(demoResolution.video)"
            :poster="demoResolution.poster ? demoAssetUrl(demoResolution.poster) : undefined"
            muted
            loop
            controls
            playsinline
            preload="metadata"
          />
          <div v-else class="task-demo-figure">
            <PoseFigure :exercise="selected.key" />
          </div>
          <p class="pd-muted task-demo-note">
            {{ demoResolution.kind === 'VIDEO'
              ? '可播放动作示范，视频无声；节拍与伴奏由本页节拍器提供。'
              : demoResolution.note }}
          </p>
        </div>
      </div>

      <div class="pd-card camera-region">
        <div class="pd-card-header">
          <span class="pd-card-title">录制动作</span>
          <span class="pd-muted task-camera-note">您的动作</span>
        </div>
        <div class="pd-card-body">
          <p class="pd-secondary task-camera-desc">{{ selected.description }}</p>

          <VideoCapturePanel
            ref="captureRef"
            :max-seconds="MAX_RECORDING_SECONDS"
            :instruction="standPrompt"
            @change="onClipChange"
          />

          <el-button
            v-if="!result && !rejection"
            type="primary"
            size="large"
            class="pd-big-action"
            style="width: 100%; margin-top: 16px"
            :loading="analyzing"
            :disabled="!recordedBlob"
            @click="analyze"
          >
            完成并分析
          </el-button>

          <div v-else class="task-done">
            <p class="task-done-title">本次训练已完成</p>
            <el-button size="large" style="width: 100%" @click="leaveTask">
              返回康复训练
            </el-button>
          </div>
        </div>
      </div>
    </div>
    <div v-if="result" class="pd-card movement-results"><div class="pd-card-header"><span class="pd-card-title">本次训练结果</span></div><div class="pd-card-body"><MetricSummaryCards :cards="summaryCards" advanced-label="查看全部原始指标"><el-table :data="metricRows()" size="small"><el-table-column prop="label" label="指标" /><el-table-column prop="value" label="数值" /></el-table></MetricSummaryCards><p class="pd-secondary">展示分公式未定义，当前为空；这里只展示实际测得的原始指标。</p></div></div>
    <el-alert v-if="rejection" type="warning" :closable="false" title="本次录制未通过质量控制，请完整入镜后重录。"><ul><li v-for="gate in rejection.gate_failures" :key="gate">{{ GATE_LABELS[gate] ?? gate }}</li></ul><el-button @click="reset">重新录制</el-button></el-alert>
  </PatientTaskLayout>

  <div v-else v-loading="loading" class="pd-page">
    <router-link class="pd-back" :to="{ name: 'training', query: { patientId } }">
      <el-icon><ArrowLeft /></el-icon>返回康复训练
    </router-link>

    <div class="pd-page-header">
      <div>
        <h1 class="pd-page-title">芭蕾动作训练</h1>
        <p class="pd-page-subtitle">
          舒展、保持、跟随节拍。先查看示范，再选择适合的训练方式。
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

    <!--
      Shown only when the page was opened with `?selftest=1`. The point is that
      whoever is exercising the upload path can see, on the screen, that the row
      they are about to create is marked as not-a-person -- so a test recording is
      never mistaken for a patient's.
    -->
    <el-alert
      v-if="isSyntheticInput"
      type="warning"
      show-icon
      :closable="false"
      title="自检模式：本次录制的分析结果会标记为非真人来源"
      description="本页由开发用参数打开。保存后的记录只能用于验证分析流程，不会作为患者的测量值进入趋势与报告。"
      style="margin-bottom: 16px"
    />

    <SelectedPatientBar v-if="patient" :patient="patient" @change="changePatient" />
    <el-alert v-if="startState.error" type="error" show-icon :closable="false" :title="startState.error" class="pd-start-error" />
    <!-- ------------------------------------------- execution mode -->
    <div class="pd-card movement-mode" style="margin-bottom: 16px">
      <div class="pd-card-header">
        <span class="pd-card-title">训练方式</span>
        <span class="pd-muted" style="font-size: 12px">由医生选择</span>
      </div>
      <div class="pd-card-body">
        <el-radio-group v-model="executionMode" size="large" :disabled="startBusy">
          <el-radio-button value="SEATED">坐姿</el-radio-button>
          <el-radio-button value="STANDING_SUPPORTED">站姿（扶椅）</el-radio-button>
        </el-radio-group>
        <p class="pd-muted" style="font-size: 12px; margin: 10px 0 0">
          不同动作支持的完成方式不同，选定后只显示对应的动作。
          坐姿与站姿测出的角度描述的是不同的任务，因此会分别记录。
        </p>
      </div>
    </div>

    <div class="movement-workspace">
      <section class="pd-card movement-library">
        <div class="pd-card-header"><span class="pd-card-title"><span class="pd-section-index">01</span>选择动作</span><span class="pd-secondary">{{ availableExercises.length }} 个动作</span></div>
        <div class="pd-card-body exercise-list">
          <button v-for="(exercise, index) in availableExercises" :key="exercise.key" type="button" class="exercise-choice" :class="{ 'is-selected': exercise.key === selectedKey }" :aria-pressed="exercise.key === selectedKey" :disabled="startBusy" @click="selectExercise(exercise.key)">
            <span class="exercise-choice__figure"><PoseFigure :exercise="exercise.key" /></span>
            <span class="exercise-choice__text"><span class="exercise-choice__number">0{{ index + 1 }} · {{ presentationFor(exercise.key).area }}</span><strong>{{ modeAwareName(exercise.key, exercise.name_zh) }}</strong><span>{{ modeAwareEnglishName(exercise.key, exercise.name_en) }}</span></span>
            <span class="exercise-choice__status">{{ exercise.key === selectedKey ? '✓' : '›' }}</span>
          </button>
          <div v-if="!availableExercises.length" class="pd-empty">暂时没有可选动作，请切换方式或刷新重试。</div>
        </div>
      </section>
      <section class="pd-card movement-detail">
        <div class="pd-card-header"><span class="pd-card-title"><span class="pd-section-index">02</span>动作示范</span><span class="pd-pill is-teal">{{ executionMode === 'SEATED' ? '坐姿' : '站姿扶椅' }}</span></div>
        <div class="pd-card-body">
          <div v-if="selected" class="movement-heading"><h2>{{ modeAwareName(selected.key, selected.name_zh) }}</h2><p class="pd-secondary">{{ selected.description }}</p></div>
          <div class="movement-start"><p>开始时核实患者，3 秒倒计时后进入训练。</p><el-button type="primary" class="pd-big-action" :disabled="!selected" :loading="startBusy" @click="startTask">开始训练</el-button></div>
          <ExerciseDemoPanel :exercise-key="selectedKey" :execution-mode="executionMode" :exercise-name="selected ? modeAwareName(selected.key, selected.name_zh) : ''" :description="selected?.description" />
          <div v-if="selected" class="movement-detail__info">
            <div class="pd-tag-list"><span v-for="focus in selected.focus" :key="focus" class="pd-pill is-teal">{{ focus }}</span></div>
            <p class="pd-secondary">{{ selected.default_bpm }} BPM · 目标 {{ selected.target_repetitions ?? 3 }} 次<span v-if="selected.hold_time_sec"> · 保持 {{ selected.hold_time_sec }} 秒</span></p>
            <p v-if="selected.contraindications.length" class="movement-caution">注意：{{ selected.contraindications.join('、') }}</p>
            <el-collapse v-if="selected.cues.length" class="movement-steps"><el-collapse-item title="动作步骤与节拍" name="steps"><ol><li v-for="(cue, index) in selected.cues" :key="index">{{ cue.text }}<span class="pd-secondary"> · {{ cue.beats }} 拍</span></li></ol></el-collapse-item></el-collapse>
          </div>
        </div>
      </section>
    </div>

    <!-- ------------------------------------------- history -->
    <div v-if="patient" class="pd-card movement-history">
      <div class="pd-card-header"><span class="pd-card-title">最近动作训练记录</span></div>
      <div class="pd-card-body">
        <PoseHistoryTable
          :sessions="history"
          :name-for="(key) => exerciseName(key, exercises.find((e) => e.key === key)?.name_zh)"
        />
      </div>
    </div>

  </div>
</template>

<style scoped>
/*
  The card shell, the body layout and the footer alignment come from
  `.pd-action-card` in main.css. Only the parts specific to a ballet action are
  defined here: the media box that holds the diagram (or, once approved, the
  poster frame) and the area tag pinned over it.
*/

.exercise-card {
  position: relative;
  cursor: pointer;
  transition: border-color 0.15s, box-shadow 0.15s;
}

.exercise-card:hover {
  border-color: var(--pd-primary);
  box-shadow: 0 4px 14px rgb(48 109 216 / 12%);
}

.exercise-card.is-selected {
  border-color: var(--pd-primary);
  box-shadow: 0 0 0 2px rgb(48 109 216 / 18%);
}

/*
  A fixed 16:9 media box.

  The diagram is drawn inside it rather than setting the card height, so a tall
  figure and a wide one produce cards of the same height -- which is what keeps
  the rows level.
*/
.exercise-media {
  position: relative;
  display: flex;
  align-items: center;
  justify-content: center;
  overflow: hidden;
}

.exercise-media :deep(svg) {
  height: 100%;
  width: auto;
  max-width: 100%;
}

.area-tag {
  position: absolute;
  top: 10px;
  left: 10px;
  z-index: 1;
  padding: 2px 9px;
  border-radius: 10px;
  color: #fff;
  font-size: 12px;
}

.chip {
  padding: 3px 9px;
  border-radius: 8px;
  background: #eef2f6;
  color: var(--pd-text-secondary);
  font-size: 11px;
}

.exercise-target {
  margin: 10px 0 0;
  font-size: var(--pd-font-size-secondary);
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

/* ------------------------------------------------- patient task: two regions */

.task-rhythm {
  margin-bottom: 16px;
}

/*
  Demonstration and camera side by side on a wide screen.

  The demonstration gets the narrower column because the patient watches it in
  glances while the camera is what is actually being recorded, and on a phone
  the order is demonstration first, then camera, which is the order the task is
  performed in.
*/
.task-media-grid {
  display: grid;
  grid-template-columns: minmax(0, 2fr) minmax(0, 3fr);
  gap: var(--pd-gap);
  align-items: start;
}

.task-demo-figure,
.task-demo-video {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 100%;
  aspect-ratio: 16 / 9;
  background: #f2f6fb;
  border-radius: var(--pd-radius-video);
  overflow: hidden;
}

/* The clip fills its box; the silhouette diagram is centred inside it. */
.task-demo-video {
  display: block;
  object-fit: cover;
  background: #10151a;
}

.task-demo-figure :deep(svg) {
  height: 92%;
  width: auto;
  max-width: 92%;
}

.task-demo-note {
  margin: 10px 0 0;
  font-size: var(--pd-font-size-secondary);
  line-height: 1.6;
}

/* Explicitly the patient's own view, in words, not only by position. */
.task-camera-note {
  font-size: var(--pd-font-size-secondary);
}

.task-camera-desc {
  margin: 0 0 12px;
}

@media (max-width: 767px) {
  .task-media-grid {
    /* Demonstration first, then the camera: the order the task is performed in.
       At 768px and above the two still fit side by side, so the split follows
       the shared mobile breakpoint rather than inventing one. */
    grid-template-columns: minmax(0, 1fr);
    gap: var(--pd-gap-sm);
  }

  /* On a phone the diagram is a reference, not the main event: keep it small
     enough that the camera and the record button stay in view. */
  .task-demo-figure {
    aspect-ratio: 21 / 9;
  }
}

.movement-workspace { display: grid; grid-template-columns: minmax(0, 0.85fr) minmax(0, 1.4fr); gap: 24px; align-items: start; }
.movement-mode .pd-card-header { display: none; }
.movement-mode .pd-card-body { display: flex; align-items: center; gap: 24px; flex-wrap: wrap; padding: 16px 20px; }
.movement-mode .pd-card-body p { flex: 1; min-width: 200px; margin: 0 !important; }
.movement-detail :deep(.demo-diagram) { aspect-ratio: 21 / 9; }
.movement-detail :deep(.demo-meta) { display: none; }
.movement-workspace > .pd-card { margin: 0; }
.movement-detail { position: sticky; top: 20px; }
.exercise-list { display: flex; flex-direction: column; gap: 10px; }
.exercise-choice { display: flex; align-items: center; width: 100%; gap: 14px; padding: 12px; background: white; border: 1px solid var(--pd-border); border-radius: 12px; text-align: left; cursor: pointer; color: var(--pd-text); }
.exercise-choice.is-selected { border-color: var(--pd-primary); background: var(--pd-primary-soft); box-shadow: inset 3px 0 var(--pd-primary); }
.exercise-choice__figure { display: flex; align-items: center; justify-content: center; width: 72px; height: 78px; flex: none; border-radius: 9px; background: #ecf5f2; overflow: hidden; }
.exercise-choice__figure :deep(svg) { width: 100%; height: 100%; }
.exercise-choice__text { display: flex; flex-direction: column; gap: 3px; min-width: 0; }
.exercise-choice__text strong { font-size: 15px; }
.exercise-choice__text > span { font-size: 12px; color: var(--pd-text-secondary); }
.exercise-choice__number { letter-spacing: 0.6px; }
.exercise-choice__status { margin-left: auto; font-size: 20px; color: var(--pd-primary); }
.movement-detail__info { margin-top: 20px; font-size: 14px; }
.movement-heading h2 { margin: 0 0 8px; font-size: 22px; letter-spacing: -0.5px; }
.movement-heading p { margin: 0 0 20px; font-size: 14px; line-height: 1.7; }
.movement-steps ol { padding-left: 22px; margin: 0; }
.movement-steps li { padding: 4px 0; }
.movement-start { display: flex; align-items: center; gap: 16px; justify-content: space-between; margin-bottom: 24px; }
.movement-start p { color: var(--pd-text-secondary); font-size: 13px; margin: 0; line-height: 1.7; }
.movement-start .el-button { flex-shrink: 0; }
@media (max-width: 767px) { .movement-start { flex-direction: column; align-items: stretch; gap: 12px; } .movement-start .el-button { width: 100%; } }
.movement-caution { padding: 10px 12px; background: #fdf6e8; color: #785213; border-radius: 8px; font-size: 13px; }
.movement-history, .movement-results { margin-top: 24px; }
@media (max-width: 767px) { .movement-workspace { grid-template-columns: minmax(0, 1fr); gap: 16px; } .movement-detail { position: static; } .exercise-choice__figure { width: 58px; height: 62px; } }
</style>
