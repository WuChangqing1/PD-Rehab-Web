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
import { computed, onMounted, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { ArrowLeft, Refresh } from '@element-plus/icons-vue'

import MetricSummaryCards from '@/components/MetricSummaryCards.vue'
import PatientSelector from '@/components/PatientSelector.vue'
import OrientationHint from '@/components/OrientationHint.vue'
import PatientTaskLayout from '@/components/PatientTaskLayout.vue'
import PoseHistoryTable from '@/components/PoseHistoryTable.vue'
import VideoCapturePanel from '@/components/VideoCapturePanel.vue'
import BalletRhythmPanel from '@/ballet/BalletRhythmPanel.vue'
import ExerciseDemoPanel from '@/ballet/ExerciseDemoPanel.vue'
import { resolveDemo } from '@/ballet/demoAssets'
import { patientApi, poseApi } from '@/api'
import { notifyError } from '@/api/client'
import PoseFigure from '@/pose/PoseFigure.vue'
import { exerciseName, presentationFor } from '@/pose/exercises'
import { resultCardsFor } from '@/pose/resultProfile'
import { useTaskModeStore } from '@/stores/taskMode'
import type {
  Patient,
  PoseAnalysisResponse,
  PoseExerciseDefinition,
  PoseSession,
  PoseThresholds,
} from '@/types'
import { NO_DATA, displayPatientName, formatNumber } from '@/utils/format'
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
const hasPatient = computed(() => patientId.value.length > 0)

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

function startTask() {
  if (!selected.value) return
  sessionId.value = null
  result.value = null
  rejection.value = null
  started.value = true
  taskMode.enter()
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

async function load() {
  /*
    Guard the empty id.

    Without a patient in the query this used to call `patientApi.get('')`, which
    requests `/api/patients/`. FastAPI answers that with a 307 to `/api/patients`
    -- built from the path it sees *after* nginx strips the `/pd-rehab` prefix, so
    the Location header points at the site root. At the root that path belongs to
    a different project's nginx block, which answers 502. One missing guard here
    produced a cross-application error in the browser console.

    The exercise catalogue and thresholds do not depend on the patient, so they
    still load; the history does.
  */
  loading.value = true
  try {
    patient.value = patientId.value ? await patientApi.get(patientId.value) : null
    exercises.value = await poseApi.exercises()
    thresholds.value = await poseApi.thresholds()
    if (patientId.value) {
      const page = await poseApi.history(patientId.value, 10)
      history.value = page.items
    } else {
      history.value = []
    }
  } catch (error) {
    notifyError(error, '无法加载动作训练信息。')
  } finally {
    loading.value = false
  }
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

function selectExercise(key: string) {  selectedKey.value = key
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
      exercise_type: selectedKey.value as never,
      execution_mode: executionMode.value,
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
// The capture panel releases its own camera and object URL on unmount.
</script>

<template>
  <!-- Function-first: with no patient in the query, ask for one. -->
  <PatientSelector
    v-if="!hasPatient"
    title="选择患者"
    description="搜索姓名或患者编号，选择后即可开始芭蕾动作训练。"
    @select="(p) => router.replace({ query: { patientId: p.id } })"
  />

  <!--
    Patient mode. The doctor chose the patient, the training mode and the
    exercise; the patient now sees the count, the instruction and the camera,
    and one permanent way out.
  -->
  <PatientTaskLayout
    v-else-if="started && selected && patient"
    :patient="patient"
    task="芭蕾动作训练"
    :instruction="selected.name_zh"
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
            playsinline
            preload="metadata"
          />
          <div v-else class="task-demo-figure">
            <PoseFigure :exercise="selected.key" />
          </div>
          <p class="pd-muted task-demo-note">
            {{ demoResolution.kind === 'VIDEO'
              ? '示范视频循环播放中，没有声音；节拍与伴奏由本页的节拍器提供。'
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
  </PatientTaskLayout>

  <div v-else v-loading="loading" class="pd-page">
    <router-link class="pd-back" :to="{ name: 'training', query: { patientId } }">
      <el-icon><ArrowLeft /></el-icon>返回康复训练
    </router-link>

    <div class="pd-page-header">
      <div>
        <h1 class="pd-page-title">芭蕾动作训练</h1>
        <p class="pd-page-subtitle">
          患者：{{ displayPatientName(patient?.name) || '—' }}。五个芭蕾动作，带节拍与口令提示，
          用摄像头录制或上传视频后由系统分析。
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

    <!-- ------------------------------------------- execution mode -->
    <div class="pd-card" style="margin-bottom: 16px">
      <div class="pd-card-header">
        <span class="pd-card-title">训练方式</span>
        <span class="pd-muted" style="font-size: 12px">由医生选择</span>
      </div>
      <div class="pd-card-body">
        <el-radio-group v-model="executionMode" size="large">
          <el-radio-button value="SEATED">坐姿</el-radio-button>
          <el-radio-button value="STANDING_SUPPORTED">站姿（扶椅）</el-radio-button>
        </el-radio-group>
        <p class="pd-muted" style="font-size: 12px; margin: 10px 0 0">
          不同动作支持的完成方式不同，选定后只显示对应的动作。
          坐姿与站姿测出的角度描述的是不同的任务，因此会分别记录。
        </p>
      </div>
    </div>

    <!-- ------------------------------------------- exercise cards -->
    <div class="pd-card">
      <div class="pd-card-header">
        <span class="pd-card-title">选择动作</span>
        <span class="pd-muted" style="font-size: 12px">
          当前方式可用 {{ availableExercises.length }} 个动作
        </span>
      </div>
      <div class="pd-card-body">
        <!--
          Equal-height action cards.
          `.pd-action-card__footer` uses `margin-top: auto`, so the CTA sits on
          the same line in every card of a row no matter how long the description
          runs. The whole card selects on click (a large touch target), and the
          explicit 查看动作 button is the keyboard-reachable control and the
          visible affordance.
        -->
        <div class="pd-card-grid">
          <article
            v-for="exercise in availableExercises"
            :key="exercise.key"
            class="pd-action-card exercise-card"
            :class="{ 'is-selected': exercise.key === selectedKey }"
            @click="selectExercise(exercise.key)"
          >
            <!--
              Media slot. Today this holds the reviewed static diagram; when an
              action has an APPROVED, movement-reviewed clip it becomes the
              poster frame and the loop video opens in the detail workspace. An
              action with no approved media keeps the diagram rather than being
              given someone else's video.
            -->
            <div class="pd-action-card__media exercise-media">
              <span
                class="area-tag"
                :style="{ background: presentationFor(exercise.key).areaColor }"
              >
                {{ presentationFor(exercise.key).area }}
              </span>
              <PoseFigure :exercise="exercise.key" />
            </div>

            <div class="pd-action-card__body">
              <h3 class="pd-action-card__title">{{ exercise.name_zh }}</h3>
              <p class="pd-action-card__subtitle">{{ exercise.name_en }}</p>

              <p class="pd-action-card__desc">{{ exercise.description }}</p>

              <div class="pd-action-card__meta">
                <span v-for="chip in exercise.focus" :key="chip" class="chip">
                  {{ chip }}
                </span>
              </div>

              <p class="exercise-target">
                <template v-if="exercise.target_repetitions">
                  目标 {{ exercise.target_repetitions }} 次
                </template>
                <template v-if="exercise.hold_time_sec">
                  · 保持 {{ exercise.hold_time_sec }} 秒
                </template>
                · {{ exercise.default_bpm }} BPM
              </p>

              <div class="pd-action-card__footer">
                <el-button
                  type="primary"
                  :plain="exercise.key !== selectedKey"
                  @click.stop="selectExercise(exercise.key)"
                >
                  {{ exercise.key === selectedKey ? '已选择' : '查看动作' }}
                </el-button>
              </div>
            </div>
          </article>
        </div>

        <p v-if="!availableExercises.length" class="pd-empty">
          这种训练方式下暂无可选动作，请切换到另一种方式。
        </p>
      </div>
    </div>

    <!--
      Demonstration workspace for the selected exercise.

      This is the DEMONSTRATION only. The patient's own camera view appears later,
      inside the patient task screen, and the two are labelled differently on
      purpose so nobody mistakes one for the other.
    -->
    <div class="pd-card" style="margin-top: 16px">
      <div class="pd-card-header">
        <span class="pd-card-title">动作示范</span>
        <span class="pd-muted" style="font-size: 12px">
          {{ executionMode === 'SEATED' ? '坐姿' : '站姿（扶椅）' }}
        </span>
      </div>
      <div class="pd-card-body">
        <ExerciseDemoPanel
          :exercise-key="selectedKey"
          :execution-mode="executionMode"
          :exercise-name="selected?.name_zh ?? ''"
          :description="selected?.description"
          show-review-detail
        />
      </div>
    </div>

    <!-- ------------------------------------------- start -->
    <div class="pd-card" style="margin-top: 16px">
      <div class="pd-card-body start-row">
        <div>
          <strong>{{ selected ? `开始：${selected.name_zh}` : '请先选择一个动作' }}</strong>
          <p class="pd-secondary" style="margin: 4px 0 0">
            {{
              selected
                ? `开始后进入患者操作界面：${selected.name_en}，${executionMode === 'SEATED' ? '坐姿' : '站姿（扶椅）'}，` +
                  `${selected.default_bpm} BPM，共 ${selected.target_repetitions ?? 3} 遍。`
                : '选择动作后即可开始。'
            }}
          </p>
        </div>
        <el-button type="primary" size="large" :disabled="!selected" @click="startTask">
          开始训练
        </el-button>
      </div>
    </div>

    <!-- ------------------------------------------- recording -->
    <!--
      The recording entry is always mounted. It used to sit behind
      `v-if="selected"`, so a patient landing on the page saw no way to record
      until they had clicked an exercise card, and the controls appeared to pop
      into existence. Exercise-specific copy still waits for a selection; the
      controls are always visible and disabled until one exists.
    -->
    <div class="pd-grid pd-grid-2">
      <div class="pd-card">
        <div class="pd-card-header">
          <span class="pd-card-title">
            录制{{ selected ? `：${selected.name_zh}` : '' }}
          </span>
          <el-tag v-if="!selected" type="info" size="small">请先选择动作</el-tag>
        </div>
        <div class="pd-card-body">
          <div v-if="!selected" class="pd-empty" style="margin-bottom: 12px">
            请先在上方选择一个动作。选择后即可用摄像头录制或上传已有视频，
            录制与分析结果都会记录到该动作上。
          </div>

          <template v-else>
            <p class="pd-secondary" style="margin-top: 0">{{ selected.description }}</p>
            <p v-if="selected.contraindications.length" class="pd-muted" style="font-size: 12px">
              禁忌：{{ selected.contraindications.join('、') }}
            </p>

            <el-alert
              type="info"
              show-icon
              :closable="false"
              style="margin-bottom: 12px"
              title="拍摄建议"
            >
              <template #default>
                <span style="font-size: 12px; line-height: 1.8">
                  手机横放或摄像头正对，<b>让整个人进入画面</b>——侧屈与旋转这类动作需要看到髋部，
                  只拍到上半身会被判为"关键点可见度过低"。距离 2–3 米，做
                  {{ selected.target_repetitions ?? 3 }} 次完整动作，中间不要停顿太久；
                  光线要均匀，避免逆光。
                </span>
              </template>
            </el-alert>
          </template>

          <VideoCapturePanel
            ref="captureRef"
            :disabled="!selected"
            :max-seconds="MAX_RECORDING_SECONDS"
            :instruction="`目标：${selected?.target_repetitions ?? 3} 次完整动作，每次保持约 5 秒。`"
            hint="手机横放或摄像头正对，让整个人进入画面——侧屈与旋转这类动作需要看到髋部，只拍到上半身会被判为「关键点可见度过低」。距离 2–3 米，光线均匀，避免逆光。"
            @change="onClipChange"
          />

          <div class="record-actions">
            <el-button
              type="primary"
              :loading="analyzing"
              :disabled="!recordedBlob || !selected"
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
            <MetricSummaryCards
              :cards="summaryCards"
              advanced-label="查看全部原始指标"
              footnote="以上为本次录制的原始测量值；展示分（完成度 / ROM / 对称性 / 稳定性）因公式未定义而保持为空。"
            >
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
            </MetricSummaryCards>
          </template>
        </div>
      </div>
    </div>

    <!-- ------------------------------------------- history -->
    <div class="pd-card">
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
</style>
