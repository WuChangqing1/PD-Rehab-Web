<script setup lang="ts">
/**
 * Virtual piano / rhythm training.
 *
 * Flow: Calibration (optional) -> four training modes -> Round 1 -> adapt ->
 * Round 2 -> adapt -> Round 3. Difficulty comes from the personal calibration
 * plus this session's performance only; no model output feeds it.
 *
 * Every number shown comes from stored raw events. Metrics are computed locally
 * for immediate feedback and recomputed by the server on completion; the server
 * value is authoritative and any divergence is recorded.
 */
import { computed, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { onBeforeRouteLeave, onBeforeRouteUpdate, useRoute, useRouter } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import { ArrowLeft, InfoFilled, VideoPlay } from '@element-plus/icons-vue'

import { pianoApi } from '@/api'
import { notifyError } from '@/api/client'
import MetricSummaryCards from '@/components/MetricSummaryCards.vue'
import SelectedPatientBar from '@/components/SelectedPatientBar.vue'
import TrainingStartGate from '@/components/TrainingStartGate.vue'
import TrainingArtwork from '@/components/TrainingArtwork.vue'
import PracticeCover from '@/components/PracticeCover.vue'
import { PRACTICES, PRACTICE_FAMILIES, type PracticeDefinition } from '@/piano/catalogue'
import { RECIPE_METRIC_ROWS } from '@/piano/metricDefinitions'
import { RECIPE_BY_ID } from '@/piano/recipes'
import { useTrainingStartGate } from '@/composables/useTrainingStartGate'
import OrientationHint from '@/components/OrientationHint.vue'
import PatientTaskLayout from '@/components/PatientTaskLayout.vue'
import PianoKeyboard from '@/piano/PianoKeyboard.vue'
import {
  adaptDifficulty,
  DIFFICULTY_ENGINE_VERSION,
  initialDifficulty,
  TEMPO_GOAL_CEILING,
  type CalibrationBaseline,
  type DifficultyResult,
} from '@/piano/difficulty'
import { usePianoRunner } from '@/piano/useRunner'
import { spontaneousTempo } from '@/piano/tempo'
import type { DifficultyConfig, PianoMode } from '@/piano/session'
import { DEFAULT_DIFFICULTY, MODE_LABELS } from '@/piano/session'
import type { TempoGoal } from '@/piano/difficulty'
import type { Hand } from '@/piano/samples'
import type { PianoInputSource } from '@/types'
import { NO_DATA, formatDateTime, formatNumber, formatPercent } from '@/utils/format'
import { inputSourceLabel } from '@/utils/source'
import { usePatientContextStore } from '@/stores/patientContext'
import { useTaskModeStore } from '@/stores/taskMode'
import {
  type TrainingRecipe,
} from '@/piano/recipes'
import type { Patient } from '@/types'

const route = useRoute()
const router = useRouter()
/**
 * The patient comes from the query, not the path.
 *
 * Function-first routing means `/training/piano?patientId=…`: the patient is
 * chosen inside the function. The old `/patients/:id/training/piano` shape still
 * redirects here, so params are read as a fallback for any stale link.
 */
const patientId = computed(() => {
  const fromQuery = route.query.patientId
  if (typeof fromQuery === 'string' && fromQuery) return fromQuery
  const fromParams = route.params.id
  return typeof fromParams === 'string' ? fromParams : ''
})

/**
 * The patient record, for the identity line in patient mode.
 *
 * This page never needed it before -- it works from the id alone -- but the
 * patient-facing header has to say whose session this is, and "unknown patient"
 * in front of the person doing the task is not acceptable.
 */
const patientStore = usePatientContextStore()
const patient = ref<Patient | null>(null)

const runner = usePianoRunner()

const selectedMode = ref<PianoMode>('SINGLE_KEY_RHYTHM')

/**
 * The training recipe, when the doctor picked one.
 *
 * A recipe and a mode are not alternatives: the recipe is a template that selects
 * a mode and adds a cue policy on top of it. Choosing a recipe therefore also
 * sets `selectedMode`, and choosing a plain mode clears the recipe. That is what
 * keeps the four new practices inside the one existing engine instead of
 * becoming a second set of pages.
 */
const selectedRecipe = ref<TrainingRecipe | null>(null)

function chooseRecipe(recipe: TrainingRecipe) {
  if (running.value || startBusy.value) return
  selectedRecipe.value = recipe
  selectedMode.value = recipe.baseMode
}

function chooseMode(mode: PianoMode) {
  if (running.value || startBusy.value) return
  selectedRecipe.value = null
  selectedMode.value = mode
}
const calibrationSeconds = ref(45)
const difficulty = ref<DifficultyConfig>({ ...DEFAULT_DIFFICULTY })
const roundNumber = ref(1)
const seed = ref(Math.floor(Math.random() * 1_000_000))
const weakHand = ref<Hand | null>(null)

const saving = ref(false)
const roundSaved = ref(false)
const sessionId = ref<string | null>(null)
const serverMetrics = ref<Record<string, number | null> | null>(null)
const adaptation = ref<DifficultyResult | null>(null)
const warnings = ref<string[]>([])
/** Baseline captured from Calibration, used by the rule engine as reference. */
const calibration = ref<CalibrationBaseline | null>(null)

/**
 * Length of the uncued tempo-measurement segment appended to calibration.
 *
 * Long enough for roughly 10-20 taps at a parkinsonian rate, short enough not to
 * tire the patient. See docs/piano_training_plan.md P1.
 */
const SPONTANEOUS_WINDOW_MS = 15000

/**
 * Rehabilitation goal for the tempo ceiling.
 *
 * The evidence gives 110% for stability and 120% for speed. The system does not
 * choose a goal for the clinician, so this is an explicit setting and it travels
 * with the session audit.
 */
const tempoGoal = ref<TempoGoal>('STABILITY')

const isCalibration = computed(() => selectedMode.value === 'CALIBRATION')

/**
 * Whether the chosen mode is the optional memory-rhythm extra.
 *
 * It is selectable, and the page says so, but the automatic three-round
 * progression never schedules it: an optional task that the system queues up is
 * not optional.
 */
const isMemoryMode = computed(() => selectedMode.value === 'MEMORY_RHYTHM')
const running = computed(
  () => runner.state.value === 'RUNNING' || runner.state.value === 'COUNTDOWN',
)

/**
 * Whether the screen belongs to the patient.
 *
 * Set when a round actually starts (not when the page opens) and cleared by
 * 返回. The doctor needs the workspace to choose a mode and a patient; the
 * patient needs the piano and the count.
 */
const taskMode = useTaskModeStore()
const started = ref(false)
// The component is the source of truth for whether a round is under way; this
// only widens it to cover the result the patient sees after the last round.
const patientScreen = computed(() => started.value)

/**
 * Props for whichever chrome is being used.
 *
 * Bound with `v-bind` onto `<component :is>`: in workspace mode the wrapper is a
 * plain `div` and the object is empty, so no patient props leak into the DOM.
 */
const wrapperProps = computed(() =>
  patientScreen.value
    ? {
        patient: patient.value,
        task: '钢琴节奏训练',
        instruction: isCalibration.value
        ? '基础能力测试'
        : /*
            The recipe name wins over the mode name.

            A recipe is a template over a mode, so BIMANUAL_SYNC runs on
            SINGLE_KEY_RHYTHM -- but the doctor chose 双手同时敲击 and the patient
            is doing two hands at once. Showing the underlying mode here told
            them 单键节奏, which describes neither what they picked nor what they
            are doing. Falls back to the mode label when no recipe is selected.
          */
          (selectedRecipe.value?.label ?? MODE_LABELS[selectedMode.value]),
        progress: `第 ${roundNumber.value} / ${TOTAL_ROUNDS} 轮`,
        backLabel: '返回康复训练',
        onExit: leaveTask,
      }
    : {},
)

function leaveTask() {
  router.push({ name: 'training', query: { patientId: patientId.value } })
}

/**
 * Provenance of the key events for this round.
 *
 * Normal use is HUMAN_KEYBOARD. Opening the page with `?selftest=1` declares
 * SYNTHETIC_SELFTEST, which is how the scripted end-to-end check drives a round
 * without a person at the keyboard; the flag is stored with the session so such
 * a row can never be read as a patient measurement.
 */
const inputSource = computed<PianoInputSource>(() =>
  route.query.selftest === '1' ? 'SYNTHETIC_SELFTEST' : 'HUMAN_KEYBOARD',
)
const isSyntheticInput = computed(() => inputSource.value !== 'HUMAN_KEYBOARD')
/** Source reported back by the server for the saved session, if any. */
const savedInputSource = ref<PianoInputSource | null>(null)
const savedSourceIsSynthetic = computed(
  () => savedInputSource.value !== null && savedInputSource.value !== 'HUMAN_KEYBOARD',
)

/**
 * Recipe reported back by the server for the saved session.
 *
 * Read from the SAVED session rather than from the picker, so the extra metric
 * rows describe the round whose numbers are on screen. A doctor who switches the
 * picker after finishing a round must not relabel the results already shown.
 */
const savedRecipeId = ref<string | null>(null)

// The canonical mode list lives in `TRAINING_MODES` for the patient-facing cards
// and in `MODE_LABELS` for display names; `PianoMode` already enumerates them, so
// no separate array of the raw enum values is needed here.

/** Total rounds in one session; the system advances them, the patient does not. */
const TOTAL_ROUNDS = 3

/** Doctor-only parameters; collapsed by default. */
const advancedOpen = ref<string[]>([])

/** When the current baseline was taken, for the "already tested" message. */
const calibrationTakenAt = ref<string | null>(null)

/**
 * Load the patient's existing baseline, if any.
 *
 * A missing baseline is a normal state -- it means the capability test still has
 * to be run -- so a 404 is not reported as an error.
 */
let baselinePatientId = ''
let baselineRequest = 0
let patientLoadVersion = 0
const pendingPractice = ref<{ mode: PianoMode; recipe: TrainingRecipe | null } | null>(null)
async function loadBaseline(id = patientId.value) {
  const request = ++baselineRequest
  calibration.value = null
  calibrationTakenAt.value = null
  baselinePatientId = ''
  if (!id) return
  try {
    const baseline = await pianoApi.baseline(id)
    if (request !== baselineRequest) return
    calibration.value = {
      baseline_accuracy: baseline.baseline_accuracy,
      baseline_response_latency: baseline.baseline_response_latency,
      baseline_response_latency_cv: baseline.baseline_response_latency_cv,
      baseline_timing_mae: baseline.baseline_timing_mae,
      baseline_left_accuracy: baseline.baseline_left_accuracy,
      baseline_right_accuracy: baseline.baseline_right_accuracy,
      baseline_left_latency: baseline.baseline_left_latency,
      baseline_right_latency: baseline.baseline_right_latency,
      baseline_spontaneous_bpm: baseline.baseline_spontaneous_bpm ?? null,
    }
    calibrationTakenAt.value = baseline.created_at
    // Start training from the stored baseline rather than defaults.
    difficulty.value = initialDifficulty(calibration.value, { tempoGoal: tempoGoal.value })
    // A patient who already has a baseline goes straight to training; the
    // capability test is only the default when it is still outstanding.
    baselinePatientId = id
  } catch (error) {
    if (request !== baselineRequest) return
    calibration.value = null
    calibrationTakenAt.value = null
    const status = (error as { response?: { status?: number } }).response?.status
    if (status !== 404) throw new Error('无法读取患者基础测试，请检查网络后重试。')
    baselinePatientId = id
  }
}

/**
 * The four training modes as the patient sees them.
 *
 * Plain Chinese with a one-line description each. The internal enum names are
 * implementation vocabulary and are deliberately not shown.
 */
const practiceFamily = ref('ALL')
const visiblePractices = computed(()=>PRACTICES.filter(p=>practiceFamily.value==='ALL'||p.family===practiceFamily.value))
const selectedPracticeId = computed(()=>selectedRecipe.value?.id==='SFT_CUE_SYNC'?'SINGLE_KEY_RHYTHM':selectedRecipe.value?.id??selectedMode.value)
function chooseVariant(value: string|number|boolean|undefined) {
  if(value==='BASE') chooseMode('SINGLE_KEY_RHYTHM'); else chooseRecipe(RECIPE_BY_ID.SFT_CUE_SYNC)
}
function choosePractice(practice:PracticeDefinition) {
  if(practice.recipe) chooseRecipe(practice.recipe)
  else chooseMode(practice.mode)
}
/** Metrics the specification places in P0, shown in the order it lists them. */
const METRIC_ROWS: Array<{ key: string; label: string; kind: 'ms' | 'ratio' | 'number' }> = [
  { key: 'accuracy', label: '准确率', kind: 'ratio' },
  { key: 'miss_rate', label: '漏击率', kind: 'ratio' },
  { key: 'mean_timing_error_ms', label: '平均节拍误差', kind: 'ms' },
  { key: 'median_timing_error_ms', label: '节拍误差中位数', kind: 'ms' },
  { key: 'timing_error_cv', label: '节拍误差变异系数', kind: 'number' },
  { key: 'mean_response_latency_ms', label: '平均反应延迟', kind: 'ms' },
  { key: 'response_latency_cv', label: '反应延迟变异系数', kind: 'number' },
  { key: 'left_mean_latency', label: '左手平均延迟', kind: 'ms' },
  { key: 'right_mean_latency', label: '右手平均延迟', kind: 'ms' },
  { key: 'left_right_latency_difference', label: '左右延迟差（左−右）', kind: 'ms' },
  { key: 'left_accuracy', label: '左手准确率', kind: 'ratio' },
  { key: 'right_accuracy', label: '右手准确率', kind: 'ratio' },
  { key: 'weak_finger_error_rate', label: '弱指错误率（任务映射）', kind: 'ratio' },
  { key: 'session_completion_rate', label: '本次完成率', kind: 'ratio' },
]

/**
 * Extra rows for the metrics only a recipe produces.
 *
 * Shown only for the recipe that produces them, and only when a value exists, so
 * a plain round's table is exactly what it was. A metric that does not apply is
 * left out rather than printed as "no data" -- "not measured here" and "measured
 * as nothing" are different statements and the table should not blur them.
 */

const metricRows = computed(() => {
  const recipe = savedRecipeId.value ?? selectedRecipe.value?.id
  if (!recipe) return METRIC_ROWS
  const extra = (RECIPE_METRIC_ROWS[recipe] ?? []).filter((row) => {
    const value = metricValue(row.key)
    return value !== undefined && value !== null
  })
  return [...METRIC_ROWS, ...extra]
})

function metricValue(key: string): number | null {
  const local = (runner.metrics.value as unknown as Record<string, number | null>)[key]
  const remote = serverMetrics.value?.[key]
  return remote !== undefined && remote !== null ? remote : (local ?? null)
}



function renderMetric(key: string, kind: 'ms' | 'ratio' | 'number'): string {
  const value = metricValue(key)
  if (value === null || value === undefined) return NO_DATA
  if (kind === 'ratio') return formatPercent(value)
  if (kind === 'ms') return `${value.toFixed(1)} ms`
  return formatNumber(value, 3)
}

/**
 * The four numbers a patient or doctor reads first.
 *
 * Everything else -- fourteen P0 metrics, cross-checks, algorithm caveats --
 * stays behind "查看全部训练指标". The weak-finger caveat is repeated in the
 * visible footnote because that number is a task mapping, not an anatomical
 * measurement, and that must not be discoverable only after expanding.
 */
const standardSummaryCards = computed(() => [
  {
    label: '准确率',
    value: renderMetric('accuracy', 'ratio'),
    note: '正确完成提示 / 应完成提示',
    emphasis: true,
  },
  {
    label: '平均反应延迟',
    value: renderMetric('mean_response_latency_ms', 'ms'),
    note: '提示出现到第一次有效击键',
    emphasis: true,
  },
  {
    label: '平均节拍误差',
    value: renderMetric('mean_timing_error_ms', 'ms'),
    note: '负数偏早、正数偏晚',
  },
  {
    label: '左右手延迟差',
    value: renderMetric('left_right_latency_difference', 'ms'),
    note: '左手 − 右手',
  },
])

const summaryCards=computed(()=>{
 const recipe=savedRecipeId.value??selectedRecipe.value?.id
 const extra=recipe?RECIPE_METRIC_ROWS[recipe]??[]:[]
 return [...extra.slice(0,2).map(row=>({label:row.label,value:renderMetric(row.key,row.kind),note:'本轮原始事件计算',emphasis:true})),...standardSummaryCards.value].slice(0,6)
})

const targetMidi = computed(() => runner.currentCue.value?.hasCue === false || runner.currentCue.value?.cueType === 'NO_GO' ? null : runner.currentCue.value?.binding.midi ?? null)
const cueInstruction=computed(()=>{ const cue=runner.currentCue.value; if(!cue) return ''; if(cue.isPrompt) return '观看示范 · 暂不按键'; if(cue.cueType==='NO_GO') return '等待 × · 不要按键'; if(cue.cueType==='GO') return '按下 ○'; if(cue.targetHoldMs) return runner.nowMs.value>=cue.targetMs+cue.targetHoldMs?'现在松开':`按住 ${cue.targetHoldMs} 毫秒后松开`; if(cue.pairRole) return cue.pairRole==='PRIMARY'?'左手先按':'右手跟上'; if(cue.accent) return '第 1 拍 · 强拍'; if(cue.tempoSegment!=null) return ['起始速度','稍快','较快','回到起始速度'][cue.tempoSegment]; return '' })

/**
 * The second key of a bimanual cue, or null.
 *
 * This has to reach the keyboard. The recipe asks the patient for one key per
 * hand, and without the second key being highlighted they are told to press two
 * things while being shown one -- the practice is not performable, however
 * correct the data layer is.
 */
const secondaryTargetMidi = computed(
  () => runner.currentCue.value?.secondaryBinding?.midi ?? null,
)
const upcomingMidi = computed(() => {
  const index = runner.activeCueIndex.value
  if (index === null) return null
  const next = runner.cues.value[index + 1]
  if (!next) return null
  return runner.nowMs.value >= next.cueOnsetMs ? next.binding.midi : null
})
const errorMidi = ref<number | null>(null)

/**
 * Audio state shown in the header.
 *
 * "loaded" and "unlocked" are separate: the samples decode on mount, but the
 * browser will not let sound out until the page has been interacted with, so the
 * two states need different wording. Any click or key press unlocks it -- the
 * start button is only there to begin recording.
 */
const audioTag = computed<{ kind: 'ready' | 'hint' | 'info'; text: string }>(() => {
  if (runner.audioError.value) return { kind: 'hint', text: '音源部分失败' }
  if (!runner.audioReady.value) return { kind: 'info', text: '音源加载中…' }
  if (!runner.unlocked.value) return { kind: 'hint', text: '音源已加载 · 点击页面任意处即可发声' }
  return { kind: 'ready', text: '音源已就绪' }
})

/** Keyboard handling is global so the patient does not have to focus a key. */
function onKeyDown(event: KeyboardEvent) {
  if (startBusy.value || (event.target instanceof Element && event.target.closest('input, textarea, select, [contenteditable="true"]'))) return
  if (event.repeat) return
  const binding = runner.press(event.code)
  if (!binding) return
  event.preventDefault()
  if (!running.value) return
  // Flash red when the press is for the wrong key at this moment.
  const expected = runner.currentCue.value?.binding.midi
  if (expected !== undefined && expected !== null && binding.midi !== expected && binding.midi !== runner.currentCue.value?.secondaryBinding?.midi && !runner.currentCue.value?.isPrompt) {
    errorMidi.value = binding.midi
    window.setTimeout(() => {
      if (errorMidi.value === binding.midi) errorMidi.value = null
    }, 220)
  }
}

function onKeyUp(event: KeyboardEvent) {
  if (runner.release(event.code)) event.preventDefault()
}

/** Removed on unmount; kept so the same handler instance is detached. */
let unlockListeners: (() => void) | null = null

onMounted(() => {
  window.addEventListener('keydown', onKeyDown)
  window.addEventListener('keyup', onKeyUp)
  window.addEventListener('blur', runner.releaseAll)

  // Load any existing baseline so the page knows whether the capability test is
  // still outstanding, and so later rounds start from it.
  void runner.warmUp()

  // Browsers only allow audio to start after a user gesture. Any interaction
  // anywhere on the page counts, so the patient can click a piano key to hear
  // it without having to press "start" first.
  const unlock = () => {
    void runner.unlock()
  }
  window.addEventListener('pointerdown', unlock, { capture: true })
  window.addEventListener('touchstart', unlock, { capture: true, passive: true })
  window.addEventListener('keydown', unlock, { capture: true })
  unlockListeners = unlock
})

/** Release keyboard listeners and workspace mode when leaving the page. */
onBeforeUnmount(() => {
  window.removeEventListener('keydown', onKeyDown)
  window.removeEventListener('keyup', onKeyUp)
  window.removeEventListener('blur', runner.releaseAll)
  if (unlockListeners) {
    window.removeEventListener('pointerdown', unlockListeners, { capture: true })
    window.removeEventListener('touchstart', unlockListeners, { capture: true })
    window.removeEventListener('keydown', unlockListeners, { capture: true })
  }
  // Restore the workspace chrome even if the doctor used the browser's back
  // button instead of 返回.
  taskMode.exit()
})

let sessionStartedAt=''
let sessionRequestId=''
let sessionSnapshot: {patientId:string; calibration:boolean;mode:PianoMode;recipeId:string|null;round:number;config:DifficultyConfig;seed:number;weakHand:Hand|null;source:PianoInputSource}|null=null
const interrupted=ref(false)
let eventsUploaded=false
let launchOptions: Parameters<typeof runner.start>[0] | null = null
let gestureUnlock: Promise<boolean> | null = null
const { state: startState, busy: startBusy, requestStart, selectPatient, cancelStart: cancelGate, changePatient: pickPatient } = useTrainingStartGate({
  async bind(next, signal) {
    patientLoadVersion++
    if (patient.value?.id !== next.id) {
      reset()
      roundNumber.value = 1
      weakHand.value = null
      adaptation.value = null
      warnings.value = []
      savedRecipeId.value = null
      savedInputSource.value = null
      pendingPractice.value = null
      difficulty.value = { ...DEFAULT_DIFFICULTY }
    }
    patient.value = next
    if (baselinePatientId !== next.id) await loadBaseline(next.id)
    if (signal.aborted) return
  },
  async prepare(next, signal) {
    if (!(await (gestureUnlock ?? runner.unlock())) || !await runner.prepare()) {
      throw new Error('声音尚未启用。请点击琴键试听，再重新开始训练。')
    }
    if (signal.aborted) return
    if (!calibration.value && !isCalibration.value) {
      pendingPractice.value = { mode: selectedMode.value, recipe: selectedRecipe.value }
      selectedMode.value = 'CALIBRATION'
      ElMessage.info('该患者尚无基础测试，先测量个人节奏，随后返回已选练习。')
    }
    prepareSession(next.id, signal)
  },
  start() {
    if (!launchOptions) return
    sessionRequestId=crypto.randomUUID()
    sessionStartedAt=new Date().toISOString()
    interrupted.value=false
    eventsUploaded=false
    runner.start(launchOptions)
    started.value = true
    taskMode.enter()
  },
})
function begin() {
  // Resume is initiated inside the click gesture; await its result after the
  // patient lookup instead of reading the ref before resume has settled.
  gestureUnlock = runner.unlock()
  requestStart()
}
function restorePractice() {
  if (pendingPractice.value && !started.value) {
    selectedMode.value = pendingPractice.value.mode
    selectedRecipe.value = pendingPractice.value.recipe
    pendingPractice.value = null
  }
}
function cancelStart() { cancelGate(); restorePractice() }
function changePatient() { restorePractice(); pickPatient() }
watch(() => startState.error, (error) => { if (error) restorePractice() })
async function prepareSession(id: string, signal: AbortSignal) {
  serverMetrics.value = null
  adaptation.value = null
  warnings.value = []
  seed.value = Math.floor(Math.random() * 1_000_000)

  const config: DifficultyConfig = isCalibration.value
    ? { ...difficulty.value, session_duration_sec: calibrationSeconds.value }
    : { ...difficulty.value }
  if (selectedRecipe.value?.id === 'TEMPO_RAMP') {
    const reference=calibration.value?.baseline_spontaneous_bpm
    config.tempo_ceiling_bpm=reference && reference>0
      ? Math.max(40,Math.min(160,reference*TEMPO_GOAL_CEILING[tempoGoal.value]/100)) : 160
  }

  sessionId.value = null
  sessionSnapshot = { patientId:id, calibration:isCalibration.value, mode:selectedMode.value,
    recipeId:selectedRecipe.value?.id??null, round:roundNumber.value, config:{...config}, seed:seed.value,
    weakHand:weakHand.value, source:inputSource.value }
  if(signal.aborted) return

  launchOptions = {
    mode: selectedMode.value,
    difficulty: config,
    seed: seed.value,
    weakHand: weakHand.value,
    countInMs: 0,
    /*
      The recipe reshapes the cue stream the shared generator produced. It is
      applied here, on the way into the runner, so every recipe keeps the same
      beat grid, approach time and judgement window as the mode it is built on --
      a template must not be able to drift from the engine underneath it.
    */
    recipe: isCalibration.value ? undefined : (selectedRecipe.value ?? undefined),
    // Calibration ends with an uncued segment that measures the patient's own
    // tempo. Everything else paces the patient and cannot reveal it.
    tailMs: isCalibration.value ? SPONTANEOUS_WINDOW_MS : 0,
  }
}

/**
 * The patient's own tempo, measured during the uncued tail of calibration.
 *
 * Read from the raw press list rather than from resolved events: the tail has no
 * cues, so it produces no cue rows by definition.
 */
const spontaneous = computed(() =>
  spontaneousTempo(
    runner.presses.value.map((press) => press.relativeDownMs),
    calibrationSeconds.value * 1000,
  ),
)

async function saveAndFinish() {
  if (!sessionSnapshot || !runner.events.value.length || saving.value || roundSaved.value) return
  saving.value = true
  try {
    const snapshot=sessionSnapshot
    if(!sessionId.value) {
      const created=snapshot.calibration
        ? await pianoApi.startCalibration(snapshot.patientId,{duration_sec:snapshot.config.session_duration_sec,difficulty:{...snapshot.config},input_source:snapshot.source,started_at:sessionStartedAt,client_request_id:sessionRequestId})
        : await pianoApi.startSession(snapshot.patientId,{mode:snapshot.mode,recipe_id:snapshot.recipeId,round_number:snapshot.round,difficulty:{...snapshot.config},seed:snapshot.seed,weak_hand:snapshot.weakHand,input_source:snapshot.source,started_at:sessionStartedAt,client_request_id:sessionRequestId})
      sessionId.value=created.id
    }
    // Raw events first: they are the primary record and the server recomputes
    // every metric from them.
    if(!eventsUploaded) await pianoApi.postEvents(sessionId.value, {
      events: runner.events.value as unknown[],
      planned_cues: runner.cues.value.filter(c=>!c.isPrompt).reduce((n,c)=>n+(c.secondaryBinding?2:1),0),
      client_metrics: runner.metrics.value as unknown as Record<string, unknown>,
      input_latency_note: runner.inputLatencyNote,
      raw_presses: runner.presses.value.map(p=>({key_code:p.code,midi:p.midi,key_down_time_ms:p.relativeDownMs,key_up_time_ms:p.relativeUpMs})),
      // Only calibration has the uncued segment; other modes send nothing and
      // the server stores nothing.
      spontaneous_tapping: isCalibration.value
        ? {
            window_ms: SPONTANEOUS_WINDOW_MS,
            tap_count: spontaneous.value.tap_count,
            interval_ms: spontaneous.value.interval_ms,
            rate_hz: spontaneous.value.rate_hz,
            interval_cv: spontaneous.value.interval_cv,
            note: '无提示自由敲击段测量值，不判对错、不计准确率。',
          }
        : null,
    })

    eventsUploaded=true

    // Decide the next round's difficulty from this session's metrics.
    const result = adaptDifficulty(
      runner.metrics.value,
      difficulty.value,
      calibration.value,
      { tempoGoal: tempoGoal.value },
    )
    adaptation.value = interrupted.value ? null : result.decision === 'MAINTAIN' && !result.changes.length ? null : result


    const completionPayload = {
      interrupted: interrupted.value,
      difficulty_after: (interrupted.value?difficulty.value:result.after) as unknown as Record<string, unknown>,
      adaptation: {
        decision: interrupted.value?'MAINTAIN':result.decision,
        changes: interrupted.value?[]:result.changes,
        reasons: interrupted.value?['本轮已中断，保持原难度。']:result.reasons,
        engine_version: result.engine_version,
        weak_hand: result.weak_hand,
        applied_rules: result.applied_rules,
      },
    }

    let completed: Awaited<ReturnType<typeof pianoApi.getSession>>
    try { completed=await pianoApi.completeSession(sessionId.value,completionPayload) }
    catch(error) {
      // A lost success response must be recoverable without another completed round.
      const existing=await pianoApi.getSession(sessionId.value)
      if(!existing.completed_at) throw error
      completed=existing
    }
    // The server's recomputed metrics are authoritative.
    const storedAudit=completed.difficulty_before_json as {server_metrics?:Record<string,number|null>}|null
    serverMetrics.value = {...completed as unknown as Record<string,number|null>,...storedAudit?.server_metrics}
    savedInputSource.value = completed.input_source
    savedRecipeId.value = (completed as { recipe_id?: string | null }).recipe_id ?? null
    if(!interrupted.value) {difficulty.value = result.after;weakHand.value = result.weak_hand}

    const audit = completed.difficulty_before_json as
      | { validation_warnings?: string[] }
      | null
    warnings.value = audit?.validation_warnings ?? []
    roundSaved.value = true

    ElMessage.success('本轮训练已保存')

    // The round advances itself. The patient never chooses one, so there is no
    // path from Round 1 to Round 3 that skips the difficulty adjustment.
    if (!interrupted.value && !isCalibration.value && roundNumber.value < TOTAL_ROUNDS) {
      const next = roundNumber.value + 1
      roundNumber.value = next
      ElMessage.info(`下一轮：第 ${next} / ${TOTAL_ROUNDS} 轮，难度已按本轮表现调整`)
    } else if (!interrupted.value && !isCalibration.value) {
      ElMessage.success('本次训练的三个轮次已全部完成')
    }

    // After the capability test the baseline exists, so move straight on to the
    // first training round rather than leaving the patient on the test screen.
    if (isCalibration.value) {
      await loadBaseline()
      roundNumber.value = 1
      selectedMode.value = pendingPractice.value?.mode ?? 'SINGLE_KEY_RHYTHM'
      selectedRecipe.value = pendingPractice.value?.recipe ?? null
      pendingPractice.value = null
    }
  } catch (error) {
    notifyError(error, '保存训练结果失败。')
  } finally {
    saving.value = false
  }
}

function stop() {
  interrupted.value=true
  runner.finish()
}

function reset() {
  runner.cancel()
  runner.events.value = []
  runner.presses.value = []
  runner.cues.value = []
  roundSaved.value = false
  sessionId.value = null
  serverMetrics.value = null
}
function nextRound() {
  reset()
  started.value = false
  taskMode.exit()
}

async function confirmDiscard() {
  if (!runner.events.value.length) {
    nextRound()
    return
  }
  try {
    await ElMessageBox.confirm(
      '本轮尚未保存，离开将丢失原始事件。确认放弃？',
      '提示',
      { confirmButtonText: '放弃', cancelButtonText: '取消', type: 'warning' },
    )
  } catch {
    return
  }
  nextRound()
}

onBeforeRouteLeave(async()=>{
  if(saving.value) { ElMessage.info('正在保存训练，请稍候。'); return false }
  if(!started.value || roundSaved.value) return true
  try { await ElMessageBox.confirm('本轮尚未保存，离开将放弃已采集的数据。','离开训练',{confirmButtonText:'放弃并离开',cancelButtonText:'继续训练',type:'warning'}); runner.cancel(); return true } catch { return false }
})
watch(patientId, async (id) => {
  if (patient.value?.id === id) return
  const version = ++patientLoadVersion
  cancelStart()
  reset()
  patient.value = null
  roundNumber.value = 1
  weakHand.value = null
  adaptation.value = null
  warnings.value = []
  savedRecipeId.value = null
  savedInputSource.value = null
  pendingPractice.value = null
  difficulty.value = { ...DEFAULT_DIFFICULTY }
  try {
    await loadBaseline('')
    const next = id ? await patientStore.resolve(id) : patientStore.currentPatient
    if (version !== patientLoadVersion || id !== patientId.value) return
    patient.value = next
    if (next) await loadBaseline(next.id)
  } catch (error) { notifyError(error, '无法加载基础测试，请重试。') }
}, { immediate: true })
onBeforeUnmount(() => { patientLoadVersion++; baselineRequest++ })
onBeforeRouteUpdate((to, from) => {
  if (started.value && to.query.patientId !== from.query.patientId) {
    ElMessage.warning('请先退出当前训练，再更换患者。')
    return false
  }
})
</script>

<template>
  <!-- Browse and audition first; bind a patient only at the actual start. -->
  <TrainingStartGate :state="startState" :exercise="isCalibration ? '基础能力测试' : (selectedRecipe?.label ?? MODE_LABELS[selectedMode])" @select="selectPatient" @cancel="cancelStart" @change="changePatient" />

  <!--
    One template, two chromes. In patient mode the page is wrapped in
    PatientTaskLayout (which carries the identity, the task, the progress and a
    permanent 返回); otherwise it is an ordinary workspace page. Duplicating the
    keyboard and status markup for the two cases would mean two places to keep
    the round display correct.
  -->
  <component
    :is="patientScreen ? PatientTaskLayout : 'div'"
    v-bind="wrapperProps"
    :class="{ 'pd-page': !patientScreen }"
  >
    <router-link
      v-if="!patientScreen"
      class="pd-back"
      :to="{ name: 'training', query: { patientId } }"
    >
      <el-icon><ArrowLeft /></el-icon>返回康复训练
    </router-link>

    <div v-if="!patientScreen" class="pd-page-header piano-page-header">
      <div>
        <h1 class="pd-page-title">钢琴节奏训练</h1>
        <p class="pd-page-subtitle">
          跟随节拍，练习手指控制与双手协调。支持电脑键盘、鼠标和触屏。
        </p>
      </div>
      <div class="piano-audio-status">
        <el-tag :type="audioTag.kind === 'ready' ? 'success' : audioTag.kind === 'hint' ? 'warning' : 'info'" size="small">{{ audioTag.text }}</el-tag>
      </div>
    </div>

    <SelectedPatientBar v-if="patient && !started" :patient="patient" @change="changePatient" />
    <el-alert v-if="startState.error" type="error" show-icon :closable="false" :title="startState.error" class="pd-start-error" />
    <el-alert
      v-if="runner.audioError.value"
      type="error"
      show-icon
      :closable="false"
      :title="runner.audioError.value"
      style="margin-bottom: 16px"
    />

    <el-alert
      v-if="isSyntheticInput"
      type="warning"
      show-icon
      :closable="false"
      title="自检模式：本轮按键由脚本合成，不是真人测量值"
      description="本页由开发用参数打开，保存后会标记为非真人来源。该记录只能用于验证流程，不会进入患者的趋势与报告。"
      style="margin-bottom: 16px"
    />

    <el-alert
      v-else-if="savedSourceIsSynthetic"
      type="warning"
      show-icon
      :closable="false"
      :title="`该会话的按键来源为「${inputSourceLabel(savedInputSource, 'piano')}」`"
      description="下面的指标不是真人测量值，仅用于流程验证，不会进入患者的趋势与报告。"
      style="margin-bottom: 16px"
    />

    <div class="pd-grid pd-grid-2 piano-workspace" :class="{ 'is-running': patientScreen }">
      <!-- ------------------------------- configuration ------------------------------- -->
      <div v-if="!patientScreen" class="pd-card piano-configuration" :class="{ 'is-preparing': startBusy }">
        <div class="pd-card-header">
          <span class="pd-card-title">
            {{ isCalibration ? '基础能力测试' : '练习目录' }}
          </span>
        </div>
        <div class="pd-card-body">
          <!--
            Baseline test first. A patient does not need to know what
            "Calibration" means, only that the tempo has to be set to suit them
            before the first round.
          -->
          <template v-if="isCalibration">
            <el-alert
              v-if="!calibration"
              type="info"
              show-icon
              :closable="false"
              style="margin-bottom: 12px"
              title="首次训练前需要先做一次基础能力测试"
              description="约 45 秒，用来测量患者自己的节奏，之后的训练速度会按这个节奏设定。测试不评分、不计对错。"
            />
            <el-alert
              v-else
              type="success"
              show-icon
              :closable="false"
              style="margin-bottom: 12px"
              title="已完成基础能力测试"
              :description="`上次测试：${formatDateTime(calibrationTakenAt)}。可以重新测一次以更新基线。`"
            />
            <el-form label-width="150px" :disabled="running || startBusy">
              <el-form-item label="测试时长">
                <el-slider v-model="calibrationSeconds" :min="30" :max="60" :step="5" show-input />
              </el-form-item>
            </el-form>
          </template>

          <!--
            Training recipes (docs/05), grouped so the doctor sees four practices
            in three families rather than a wall of similar cards. Each card
            states the concrete behaviour, because four cards that differ only by
            title would be worse than one.
          -->
          <template v-else>
            <div class="practice-filters" role="group" aria-label="按训练目标筛选">
              <button type="button" :aria-pressed="practiceFamily === 'ALL'" @click="practiceFamily='ALL'">全部练习 · {{ PRACTICES.length }}</button>
              <button v-for="family in PRACTICE_FAMILIES" :key="family.id" type="button" :aria-pressed="practiceFamily===family.id" @click="practiceFamily=family.id">{{ family.label }}</button>
            </div>
            <div class="practice-grid">
              <button v-for="(practice,index) in visiblePractices" :key="practice.id" type="button"
                class="practice-card" :data-practice="practice.id" :aria-pressed="selectedPracticeId===practice.id"
                :class="{'is-selected':selectedPracticeId===practice.id}" :disabled="running||startBusy" @click="choosePractice(practice)">
                <PracticeCover :family="practice.family" :index="index" />
                <strong>{{ practice.label }}</strong>
                <span class="practice-description">{{ practice.description }}</span>
                <span class="practice-footer"><span>{{ PRACTICE_FAMILIES.find(f=>f.id===practice.family)?.label }}</span><span>{{ selectedPracticeId===practice.id?'✓ 已选择':'选择练习' }}</span></span>
              </button>
            </div>
            <el-radio-group v-if="selectedPracticeId==='SINGLE_KEY_RHYTHM'" :model-value="selectedRecipe?.id??'BASE'" class="practice-variants" aria-label="单键提示方式" @change="chooseVariant">
              <el-radio-button value="BASE">单键节奏</el-radio-button><el-radio-button value="SFT_CUE_SYNC">听提示按键（SFT）</el-radio-button>
            </el-radio-group>
            <p v-if="isMemoryMode" class="round-note">
              记忆节奏是可选训练，不计入必须完成的三轮。系统会先示范一小段，再请患者凭记忆弹出。
            </p>

            <!--
              The round is chosen by the system, not by the patient: it advances
              after each saved round. Showing it read-only keeps the patient
              oriented without letting them skip ahead.
            -->
            <p class="round-note">
              第 <strong>{{ roundNumber }}</strong> / {{ TOTAL_ROUNDS }} 轮 ·
              难度由系统根据上一轮表现自动调整
            </p>

            <!--
              Doctor-only parameters. Collapsed by default: a patient must not be
              able to change the judgement window mid-course, and the values are
              derived from the baseline test plus the rule engine.
            -->
            <el-collapse v-model="advancedOpen" class="advanced">
              <el-collapse-item title="高级设置（医生）" name="advanced">
                <el-alert
                  type="warning"
                  show-icon
                  :closable="false"
                  style="margin-bottom: 12px"
                  title="手工修改会覆盖系统推算的难度"
                  description="修改后的参数会随本轮会话一起记录在审计字段中。"
                />
                <el-form label-width="130px" :disabled="running || startBusy">
                  <el-form-item label="BPM">
                    <el-input-number v-model="difficulty.bpm" :min="40" :max="160" :step="5" />
                  </el-form-item>
                  <el-form-item label="判定窗口">
                    <el-input-number
                      v-model="difficulty.judgement_window_ms"
                      :min="120"
                      :max="600"
                      :step="25"
                    />
                    <span class="pd-muted" style="margin-left: 8px; font-size: 12px">ms</span>
                  </el-form-item>
                  <el-form-item label="序列长度">
                    <el-input-number
                      v-model="difficulty.sequence_length"
                      :min="2"
                      :max="8"
                      :step="1"
                    />
                  </el-form-item>
                  <el-form-item label="本轮时长">
                    <el-input-number
                      v-model="difficulty.session_duration_sec"
                      :min="20"
                      :max="300"
                      :step="10"
                    />
                    <span class="pd-muted" style="margin-left: 8px; font-size: 12px">秒</span>
                  </el-form-item>
                </el-form>
              </el-collapse-item>
            </el-collapse>
          </template>

          <p class="pd-muted" style="font-size: 13px; margin: 12px 0 0">
            难度只根据患者本人的基础测试结果和本次表现调整，不使用面部表现标签，
            也不使用任何疾病概率。
            <span class="pd-mono">{{ DIFFICULTY_ENGINE_VERSION }}</span>
          </p>
        </div>
      </div>

      <!-- ------------------------------- live status ------------------------------- -->
      <div class="pd-card piano-preview">
        <div class="pd-card-header">
          <span class="pd-card-title">{{ started ? '本次状态' : '当前练习' }}</span>
          <span class="pd-muted" style="font-size: 12px">
            事件 {{ runner.events.value.length }} 条
          </span>
        </div>
        <div class="pd-card-body">
          <div v-if="runner.state.value === 'COUNTDOWN'" class="countdown">
            <div class="countdown-number">
              {{ Math.ceil(runner.countdownMs.value / 1000) }}
            </div>
            <div class="pd-muted">准备开始</div>
          </div>

    <div v-else-if="running" class="live">
            <div v-if="cueInstruction" class="cue-instruction" role="status">{{ cueInstruction }}</div>
            <div class="live-row">
              <span class="pd-secondary">目标音符</span>
              <strong class="live-note">
                {{ runner.currentCue.value?.hasCue===false || runner.currentCue.value?.cueType==='NO_GO'?'—':runner.currentCue.value?.binding.note ?? '—' }}
                <span class="pd-muted" style="font-size: 12px">
                  （{{ runner.currentCue.value?.binding.label ?? '' }} 键）
                </span>
              </strong>
            </div>
            <div class="live-row">
              <span class="pd-secondary">已用时间</span>
              <span>{{ (runner.elapsedMs.value / 1000).toFixed(1) }} s</span>
            </div>
            <el-progress :percentage="Math.round(runner.progress.value * 100)" />
            <el-button class="pd-big-action" @click="stop">结束本轮</el-button>
          </div>

          <div v-else-if="runner.state.value === 'FINISHED'" class="result-summary">
            <div class="live-row">
              <span class="pd-secondary">准确率</span>
              <strong>{{ renderMetric('accuracy', 'ratio') }}</strong>
            </div>
            <div class="live-row">
              <span class="pd-secondary">平均反应延迟</span>
              <strong>{{ renderMetric('mean_response_latency_ms', 'ms') }}</strong>
            </div>
            <div class="live-row">
              <span class="pd-secondary">平均节拍误差</span>
              <strong>{{ renderMetric('mean_timing_error_ms', 'ms') }}</strong>
            </div>
            <div class="live-row">
              <span class="pd-secondary">左右延迟差</span>
              <strong>{{ renderMetric('left_right_latency_difference', 'ms') }}</strong>
            </div>
            <p v-if="interrupted" class="pd-muted">本轮已中断，保存时保留实际采集数据。</p>
            <div class="actions"><el-button v-if="!roundSaved" type="primary" class="pd-big-action" :loading="saving" @click="saveAndFinish">保存本轮结果</el-button><el-button v-if="roundSaved" type="primary" class="pd-big-action" @click="nextRound">返回练习，继续训练</el-button><el-button v-else class="pd-big-action" :disabled="saving" @click="confirmDiscard">放弃并重来</el-button></div>
          </div>

          <div v-else class="practice-preview">
            <TrainingArtwork kind="piano" compact />
            <span class="pd-eyebrow">已选练习</span>
            <h2>{{ selectedRecipe?.label ?? MODE_LABELS[selectedMode] }}</h2>
            <p>{{ selectedRecipe?.summary ?? PRACTICES.find((practice) => practice.mode === selectedMode)?.description ?? '先测量个人敲击节奏，为后续训练设置合适的速度。' }}</p>
            <div class="practice-preview__facts"><span>{{ isCalibration ? '基础测试' : isMemoryMode ? '可选练习' : '三轮练习' }}</span><span>3 秒准备倒计时</span></div>
            <p class="practice-preview__hint">{{ patient ? (calibration ? '已读取该患者的基础测试，训练难度按个人能力调整。' : '该患者首次训练将先完成基础测试，已选练习会保留。') : '可以先试听。开始时选择患者，训练结果会保存到对应档案。' }}</p>
            <el-button type="primary" class="pd-big-action practice-start" :icon="VideoPlay" :loading="startBusy" @click="begin">{{ isCalibration ? '开始基础测试' : '开始训练' }}</el-button>
            <el-button v-if="!isCalibration" text @click="chooseMode('CALIBRATION')">查看基础能力测试</el-button>
            <el-button v-else text @click="chooseMode('SINGLE_KEY_RHYTHM')">返回训练练习</el-button>
          </div>
        </div>
      </div>
    </div>

    <!-- ------------------------------- keyboard ------------------------------- -->
    <div class="pd-card">
      <div class="pd-card-header">
        <span class="pd-card-title">钢琴键盘（左手下排 / 右手上排）</span>
      </div>
      <div class="pd-card-body">
        <OrientationHint message="横屏使用可以获得更大的琴键区域。" />

    <PianoKeyboard
          :pressed="runner.pressedKeys.value"
          :target-midi="targetMidi"
          :secondary-target-midi="secondaryTargetMidi"
          :upcoming-midi="upcomingMidi"
          :error-midi="errorMidi"
          @press="runner.press($event)"
          @release="runner.release($event)"
          @cancel="runner.cancelPress($event)"
        />
        <p class="pd-muted" style="font-size: 12px; margin: 12px 0 0">
          键盘与鼠标/触屏均可。<b>现在就可以点键试听</b>（不开始训练也能发声，按键不会入库）；
          开始训练后才会记录事件。蓝色描边高亮是当前应弹的音符。
        </p>
      </div>
    </div>

    <!-- ------------------------------- metrics ------------------------------- -->
    <div v-if="started || runner.state.value === 'FINISHED'" class="pd-card">
      <div class="pd-card-header">
        <span class="pd-card-title">训练指标</span>
        <el-tooltip
          content="保存后由服务端从原始事件重新计算，与前端本地计算比对；不一致会记录为告警"
          placement="top"
        >
          <el-icon class="pd-muted"><InfoFilled /></el-icon>
        </el-tooltip>
      </div>
      <div class="pd-card-body">
        <MetricSummaryCards
          :cards="summaryCards"
          advanced-label="查看全部训练指标"
          footnote="本页所有「手」与「手指」均为任务映射，不是生理手指测量。数值来自本次按键事件，不是量表评分。"
        >
          <el-table :data="metricRows" size="small">
            <el-table-column label="指标" min-width="220">
              <template #default="{ row }">{{ row.label }}</template>
            </el-table-column>
            <el-table-column label="数值" width="160" align="right">
              <template #default="{ row }">{{ renderMetric(row.key, row.kind) }}</template>
            </el-table-column>
          </el-table>

          <el-alert
            v-if="runner.metrics.value.timing_error_cv_note"
            type="info"
            show-icon
            :closable="false"
            :title="runner.metrics.value.timing_error_cv_note"
            style="margin-top: 12px"
          />

          <el-alert
            type="info"
            show-icon
            :closable="false"
            title="关于弱指与手别"
            style="margin-top: 12px"
          >
            本页面所有的「手」与「手指」均为<strong>任务映射</strong>：系统知道要求按哪个映射键，
            但普通键盘无法确认患者实际使用了哪根生理手指。弱指错误率同样基于任务映射，
            不代表真实生理手指表现。
          </el-alert>

          <el-alert
            type="info"
            show-icon
            :closable="false"
            :title="runner.inputLatencyNote"
            style="margin-top: 12px"
          />
        </MetricSummaryCards>

        <el-alert
          v-if="warnings.length"
          type="warning"
          show-icon
          :closable="false"
          title="数据校验告警"
          style="margin-top: 12px"
        >
          <ul style="margin: 0; padding-left: 18px">
            <li v-for="warning in warnings" :key="warning">{{ warning }}</li>
          </ul>
        </el-alert>
      </div>
    </div>

    <!-- ------------------------------- adaptation ------------------------------- -->
    <div v-if="adaptation" class="pd-card">
      <div class="pd-card-header"><span class="pd-card-title">下一轮难度调整</span></div>
      <div class="pd-card-body">
        <p>
          <el-tag
            :type="adaptation.decision === 'UPGRADE' ? 'success' : adaptation.decision === 'DOWNGRADE' ? 'warning' : 'info'"
          >
            {{ {UPGRADE:'适当增加难度',DOWNGRADE:'适当降低难度',MAINTAIN:'保持当前难度'}[adaptation.decision] }}
          </el-tag>
        </p>
        <ul class="pd-list">
          <li v-for="reason in adaptation.reasons" :key="reason">{{ reason }}</li>
        </ul>
        <el-table v-if="adaptation.changes.length" :data="adaptation.changes" size="small">
          <el-table-column prop="field" label="参数" />
          <el-table-column prop="from" label="原值" width="110" />
          <el-table-column prop="to" label="新值" width="110" />
        </el-table>
      </div>
    </div>
  </component>
</template>

<style scoped>
/* Mode cards: plain names and one line of explanation each, instead of a
   dropdown of internal enum values. */
/*
  `auto-fit` rather than `auto-fill`: a group holding one recipe should let that
  card use the row. With `auto-fill` the empty track is reserved and a lone card
  sits at half width with dead space beside it, which reads as a broken grid.
*/
.mode-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(min(180px, 100%), 1fr));
  gap: 10px;
}

/* ------------------------------------------------------------ recipes */

.recipe-group + .recipe-group {
  margin-top: 16px;
}

.recipe-group-head {
  display: flex;
  align-items: baseline;
  gap: 10px;
  flex-wrap: wrap;
  margin-bottom: 8px;
}

.recipe-group-head .pd-muted {
  font-size: var(--pd-font-size-secondary);
}

/*
  Recipe cards carry more text than the plain mode cards -- a concrete behaviour
  and what gets recorded -- so they get a two-line floor for the title and a
  reserved line for the output. Within a row, every card's bottom edge and the
  "记录：" line land on the same place regardless of text length.
*/
.recipe-card {
  min-height: 132px;
}

.recipe-card strong {
  min-height: 2.6em;
}

.recipe-produces {
  margin-top: auto;
  padding-top: 8px;
  font-size: 12px;
  color: var(--pd-text-muted);
}

.plain-modes {
  margin-top: 16px;
}

.mode-card {
  display: flex;
  flex-direction: column;
  gap: 4px;
  padding: 14px 12px;
  text-align: left;
  background: var(--pd-surface);
  border: 1px solid var(--pd-border);
  border-radius: 10px;
  cursor: pointer;
  transition: border-color 0.15s, box-shadow 0.15s;
  min-height: 48px;
}

.mode-card:hover:not(:disabled) {
  border-color: var(--pd-primary);
  box-shadow: 0 4px 14px rgb(27 111 184 / 12%);
}

.mode-card.is-selected {
  border-color: var(--pd-primary);
  box-shadow: 0 0 0 2px rgb(27 111 184 / 18%);
  background: #f4f8fc;
}

.mode-card:disabled {
  opacity: 0.6;
  cursor: not-allowed;
}

.mode-card strong {
  font-size: 15px;
}

.mode-card span {
  font-size: 12px;
  color: var(--pd-text-secondary);
  line-height: 1.5;
}

.round-note {
  margin: 14px 0 0;
  font-size: 14px;
  color: var(--pd-text-secondary);
}

.advanced {
  margin-top: 12px;
}

.actions {
  display: flex;
  flex-wrap: wrap;
  gap: 12px;
  margin-top: 8px;
}

.countdown {
  text-align: center;
  padding: 20px 0;
}

.countdown-number {
  font-size: 56px;
  font-weight: 700;
  line-height: 1;
  color: var(--pd-primary);
}

.live-row {
  display: flex;
  justify-content: space-between;
  align-items: baseline;
  margin-bottom: 10px;
}

.live-note {
  font-size: 20px;
}

.pd-list {
  margin: 8px 0 12px;
  padding-left: 20px;
  color: var(--pd-text-secondary);
}

.piano-workspace { grid-template-columns: minmax(0, 1.25fr) minmax(0, 1fr); align-items: start; }
.piano-workspace.is-running { grid-template-columns: minmax(0, 1fr); }
.piano-workspace > .pd-card { margin-top: 0; }
.piano-page-header { display: grid; grid-template-columns: minmax(0, 1fr) auto; }
.piano-audio-status { min-height: 24px; }
@media (max-width: 767px) { .piano-page-header { grid-template-columns: minmax(0, 1fr); } }
.piano-preview { position: sticky; top: 24px; }
.practice-preview > .pd-eyebrow { display: block; margin-top: 24px; }
.practice-preview h2 { margin: 8px 0; font-size: 24px; }
.practice-preview p { color: var(--pd-text-secondary); font-size: 14px; }
.practice-preview__facts { display: flex; gap: 8px; flex-wrap: wrap; margin: 20px 0; }
.practice-preview__facts span { padding: 5px 10px; background: var(--pd-primary-soft); color: var(--pd-primary-dark); border-radius: 6px; font-size: 12px; }
.practice-preview__hint { padding-top: 20px; border-top: 1px solid var(--pd-border); }
.practice-start { width: 100%; margin-bottom: 12px; }
.mode-card { padding: 16px; border-radius: 12px; color: var(--pd-text); }
.mode-card.is-selected { background: var(--pd-primary-soft); box-shadow: inset 3px 0 var(--pd-primary); }
.mode-card span { font-size: 13px; }
.recipe-card strong { min-height: 0; }
.recipe-card { min-height: 140px; }
.recipe-group-head strong { font-size: 14px; }
.recipe-group-head .pd-muted { font-size: 12px; }
.recipe-produces { color: var(--pd-primary-dark) !important; }
.is-preparing { pointer-events: none; }
.actions { margin-top: 20px; }
.actions > .el-button { flex: 1; }
@media (max-width: 767px) { .piano-preview { position: static; } .piano-workspace { display: flex; flex-direction: column; } .piano-workspace > .pd-card { width: 100%; } .piano-preview { order: -1; } .practice-preview :deep(.training-art) { display: none; } }
.practice-filters { display:flex;flex-wrap:wrap;gap:8px;margin-bottom:16px; }
.practice-filters button { background:var(--pd-surface);border:1px solid var(--pd-border);padding:9px 12px;border-radius:9px;font:inherit;color:var(--pd-text-secondary);cursor:pointer;min-height:44px; }
.practice-filters button[aria-pressed="true"] { background:var(--pd-primary-soft);color:var(--pd-primary-dark);border-color:var(--pd-primary); }
.practice-grid { display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:12px; }
.practice-card { display:flex;flex-direction:column;gap:10px;text-align:left;border:1px solid var(--pd-border);background:var(--pd-surface);padding:12px;border-radius:14px;min-width:0;font:inherit;cursor:pointer;transition:border-color .18s,box-shadow .18s; }
.practice-card strong { color:var(--pd-text);font-size:15px;line-height:24px; }
.practice-card:hover { border-color:#9ab3d8;box-shadow:0 4px 14px #1d365b09; }
.practice-card.is-selected { border:2px solid var(--pd-primary);padding:11px;background:#f8faff; }
.practice-description { display:-webkit-box;-webkit-line-clamp:2;-webkit-box-orient:vertical;overflow:hidden;color:var(--pd-text-secondary);font-size:12px;line-height:20px;height:40px; }
.practice-footer { display:flex;justify-content:space-between;gap:6px;font-size:11px;color:var(--pd-primary-dark);margin-top:auto;line-height:20px; }
.practice-variants { margin-top:16px; }
.cue-instruction { font-size:22px;font-weight:600;line-height:1.5;padding:16px;background:var(--pd-primary-soft);border-radius:12px;margin-bottom:16px;color:var(--pd-primary-dark); }
@media (min-width:768px) and (max-width:1199px) { .practice-grid { grid-template-columns:repeat(2,minmax(0,1fr)); } }
@media (max-width:767px) { .practice-grid { grid-template-columns:minmax(0,1fr); } .practice-card { display:grid;grid-template-columns:76px minmax(0,1fr);gap:6px 12px; } .practice-card :deep(.practice-cover) { grid-row:1/4;height:100%;min-height:82px; } .practice-footer { grid-column:2; } .practice-description { height:40px; } }
</style>
