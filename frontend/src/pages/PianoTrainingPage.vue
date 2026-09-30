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
import { useRoute, useRouter } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import { ArrowLeft, InfoFilled, VideoPlay } from '@element-plus/icons-vue'

import { pianoApi } from '@/api'
import { notifyError } from '@/api/client'
import PatientSelector from '@/components/PatientSelector.vue'
import PianoKeyboard from '@/piano/PianoKeyboard.vue'
import {
  adaptDifficulty,
  baselineFromCalibration,
  DIFFICULTY_ENGINE_VERSION,
  initialDifficulty,
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
const hasPatient = computed(() => patientId.value.length > 0)

const runner = usePianoRunner()

const selectedMode = ref<PianoMode>('CALIBRATION')
const calibrationSeconds = ref(45)
const difficulty = ref<DifficultyConfig>({ ...DEFAULT_DIFFICULTY })
const roundNumber = ref(1)
const seed = ref(Math.floor(Math.random() * 1_000_000))
const weakHand = ref<Hand | null>(null)

const saving = ref(false)
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
const running = computed(
  () => runner.state.value === 'RUNNING' || runner.state.value === 'COUNTDOWN',
)

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
async function loadBaseline() {
  if (!patientId.value) return
  try {
    const baseline = await pianoApi.baseline(patientId.value)
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
    if (selectedMode.value === 'CALIBRATION') {
      selectedMode.value = 'SINGLE_KEY_RHYTHM'
    }
  } catch {
    calibration.value = null
    calibrationTakenAt.value = null
    // No baseline yet: the capability test is the right first step.
    selectedMode.value = 'CALIBRATION'
  }
}

/**
 * The four training modes as the patient sees them.
 *
 * Plain Chinese with a one-line description each. The internal enum names are
 * implementation vocabulary and are deliberately not shown.
 */
const TRAINING_MODES: Array<{ key: PianoMode; title: string; description: string }> = [
  {
    key: 'SINGLE_KEY_RHYTHM',
    title: '单键节奏',
    description: '跟着节拍反复敲击同一个键，先把节奏稳住。',
  },
  {
    key: 'ALTERNATING_HANDS',
    title: '左右手交替',
    description: '左右手轮流敲击，练习双手配合。',
  },
  {
    key: 'MAPPED_SEQUENCE',
    title: '按键序列',
    description: '按顺序敲击几个不同的键，练习手指分工。',
  },
  {
    key: 'FOLLOW_THE_BEAT',
    title: '跟随节拍',
    description: '音符落到线上时按下，练习节拍同步。',
  },
]

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

const targetMidi = computed(() => runner.currentCue.value?.binding.midi ?? null)
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
  if (event.repeat) return
  const binding = runner.press(event.code)
  if (!binding) return
  event.preventDefault()
  if (!running.value) return
  // Flash red when the press is for the wrong key at this moment.
  const expected = runner.currentCue.value?.binding.midi
  if (expected !== undefined && expected !== null && binding.midi !== expected) {
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

  // Load any existing baseline so the page knows whether the capability test is
  // still outstanding, and so later rounds start from it.
  void loadBaseline()

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

/**
 * Preload the samples only once there is a patient to train.
 *
 * The page opens on the patient picker, and that picker needs the network more
 * than the piano does. Decoding ahead of a choice meant the audio competed with
 * the patient list for connections.
 */
watch(hasPatient, (chosen) => {
  if (chosen) void runner.warmUp()
}, { immediate: true })
onBeforeUnmount(() => {
  window.removeEventListener('keydown', onKeyDown)
  window.removeEventListener('keyup', onKeyUp)
  if (unlockListeners) {
    window.removeEventListener('pointerdown', unlockListeners, { capture: true })
    window.removeEventListener('touchstart', unlockListeners, { capture: true })
    window.removeEventListener('keydown', unlockListeners, { capture: true })
  }
})

async function begin() {
  const ready = await runner.prepare()
  if (!ready) {
    ElMessage.error(
      runner.audioError.value ?? '音频未能加载，无法开始训练。请检查网络后重试。',
    )
    return
  }

  serverMetrics.value = null
  adaptation.value = null
  warnings.value = []
  seed.value = Math.floor(Math.random() * 1_000_000)

  const config: DifficultyConfig = isCalibration.value
    ? { ...difficulty.value, session_duration_sec: calibrationSeconds.value }
    : { ...difficulty.value }

  try {
    const session = isCalibration.value
      ? await pianoApi.startCalibration(patientId.value, {
          duration_sec: calibrationSeconds.value,
          difficulty: { ...config },
          input_source: inputSource.value,
        })
      : await pianoApi.startSession(patientId.value, {
          mode: selectedMode.value,
          round_number: roundNumber.value,
          difficulty: { ...config },
          seed: seed.value,
          weak_hand: weakHand.value,
          input_source: inputSource.value,
        })
    sessionId.value = session.id
    savedInputSource.value = null
  } catch (error) {
    notifyError(error, '无法创建训练会话。')
    return
  }

  runner.start({
    mode: selectedMode.value,
    difficulty: config,
    seed: seed.value,
    weakHand: weakHand.value,
    countInMs: isCalibration.value ? 3000 : 2000,
    // Calibration ends with an uncued segment that measures the patient's own
    // tempo. Everything else paces the patient and cannot reveal it.
    tailMs: isCalibration.value ? SPONTANEOUS_WINDOW_MS : 0,
  })
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
  if (!sessionId.value) return
  saving.value = true
  try {
    // Raw events first: they are the primary record and the server recomputes
    // every metric from them.
    await pianoApi.postEvents(sessionId.value, {
      events: runner.events.value as unknown[],
      planned_cues: runner.cues.value.length,
      client_metrics: runner.metrics.value as unknown as Record<string, unknown>,
      input_latency_note: runner.inputLatencyNote,
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

    // Decide the next round's difficulty from this session's metrics.
    const result = adaptDifficulty(
      runner.metrics.value,
      difficulty.value,
      calibration.value,
      { tempoGoal: tempoGoal.value },
    )
    adaptation.value = result.decision === 'MAINTAIN' && !result.changes.length ? null : result

    if (isCalibration.value) {
      // Calibration defines the personal baseline that later rounds start from.
      calibration.value = {
        ...baselineFromCalibration(runner.metrics.value),
        // The uncued segment is the only source of the patient's own tempo.
        baseline_spontaneous_bpm: spontaneous.value.rate_hz
          ? spontaneous.value.rate_hz * 60
          : null,
        baseline_spontaneous_interval_cv: spontaneous.value.interval_cv,
      }
      difficulty.value = initialDifficulty(calibration.value, { tempoGoal: tempoGoal.value })
      ElMessage.success(
        spontaneous.value.rate_hz
          ? `Calibration 完成；个人基线节奏 ${(spontaneous.value.rate_hz * 60).toFixed(0)} bpm，` +
            `下一轮按该节奏的 100% 起算`
          : 'Calibration 完成，已建立个人基线并推算初始难度',
      )
    }

    const completed = await pianoApi.completeSession(sessionId.value, {
      difficulty_after: result.after as unknown as Record<string, unknown>,
      adaptation: {
        decision: result.decision,
        changes: result.changes,
        reasons: result.reasons,
        engine_version: result.engine_version,
        weak_hand: result.weak_hand,
        applied_rules: result.applied_rules,
      },
    })

    // The server's recomputed metrics are authoritative.
    serverMetrics.value = completed as unknown as Record<string, number | null>
    savedInputSource.value = completed.input_source
    difficulty.value = result.after
    weakHand.value = result.weak_hand

    const audit = completed.difficulty_before_json as
      | { validation_warnings?: string[] }
      | null
    warnings.value = audit?.validation_warnings ?? []

    ElMessage.success('本轮已保存（服务端已从原始事件重算指标）')

    // The round advances itself. The patient never chooses one, so there is no
    // path from Round 1 to Round 3 that skips the difficulty adjustment.
    if (!isCalibration.value && roundNumber.value < TOTAL_ROUNDS) {
      const next = roundNumber.value + 1
      roundNumber.value = next
      ElMessage.info(`下一轮：第 ${next} / ${TOTAL_ROUNDS} 轮，难度已按本轮表现调整`)
    } else if (!isCalibration.value) {
      ElMessage.success('本次训练的三个轮次已全部完成')
    }

    // After the capability test the baseline exists, so move straight on to the
    // first training round rather than leaving the patient on the test screen.
    if (isCalibration.value) {
      await loadBaseline()
      roundNumber.value = 1
    }
  } catch (error) {
    notifyError(error, '保存训练结果失败。')
  } finally {
    saving.value = false
  }
}

function stop() {
  runner.finish()
}

function reset() {
  runner.cancel()
  sessionId.value = null
  serverMetrics.value = null
}

async function confirmDiscard() {
  if (!runner.events.value.length) {
    reset()
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
  reset()
}
</script>

<template>
  <!--
    Function-first: with no patient in the query the page asks for one instead of
    calling the API with an empty id. Entered from 康复训练 it always has one.
  -->
  <PatientSelector
    v-if="!hasPatient"
    title="选择患者"
    description="搜索姓名或患者编号，选择后即可开始钢琴节奏训练。"
    @select="(p) => router.replace({ query: { patientId: p.id } })"
  />

  <div v-else class="pd-page">
    <router-link class="pd-back" :to="{ name: 'training', query: { patientId } }">
      <el-icon><ArrowLeft /></el-icon>返回康复训练
    </router-link>

    <div class="pd-page-header">
      <div>
        <h1 class="pd-page-title">虚拟钢琴 / 节奏训练</h1>
        <p class="pd-page-subtitle">
          第一版不依赖 MIDI：电脑键盘、鼠标与触屏均可。每个按键事件都会完整保存，
          并严格区分反应延迟与节拍误差。
        </p>
      </div>
      <el-tag v-if="audioTag.kind === 'ready'" type="success" size="small">{{ audioTag.text }}</el-tag>
      <el-tag v-else-if="audioTag.kind === 'hint'" type="warning" size="small">{{ audioTag.text }}</el-tag>
      <el-tag v-else type="info" size="small">{{ audioTag.text }}</el-tag>
    </div>

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
      description="本页以 ?selftest=1 打开，保存时会写入 input_source=SYNTHETIC_SELFTEST。该记录的指标只能用于验证流程，不得作为患者数据、科研数据或趋势输入。"
      style="margin-bottom: 16px"
    />

    <el-alert
      v-else-if="savedSourceIsSynthetic"
      type="warning"
      show-icon
      :closable="false"
      :title="`该会话的按键来源为「${inputSourceLabel(savedInputSource, 'piano')}」`"
      description="下面的指标不是真人测量值，仅用于演示与流程验证。"
      style="margin-bottom: 16px"
    />

    <div class="pd-grid pd-grid-2">
      <!-- ------------------------------- configuration ------------------------------- -->
      <div class="pd-card">
        <div class="pd-card-header">
          <span class="pd-card-title">
            {{ isCalibration ? '基础能力测试' : '训练设置' }}
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
            <el-form label-width="150px" :disabled="running">
              <el-form-item label="测试时长">
                <el-slider v-model="calibrationSeconds" :min="30" :max="60" :step="5" show-input />
              </el-form-item>
            </el-form>
          </template>

          <!--
            Training modes as cards, in plain Chinese. The internal names
            (SINGLE_KEY_RHYTHM, FOLLOW_THE_BEAT…) are not shown to the patient.
          -->
          <template v-else>
            <div class="mode-grid">
              <button
                v-for="mode in TRAINING_MODES"
                :key="mode.key"
                type="button"
                class="mode-card"
                :class="{ 'is-selected': selectedMode === mode.key }"
                :disabled="running"
                @click="selectedMode = mode.key"
              >
                <strong>{{ mode.title }}</strong>
                <span>{{ mode.description }}</span>
              </button>
            </div>

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
                <el-form label-width="130px" :disabled="running">
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

          <div class="actions">
            <el-button
              v-if="!running && runner.state.value !== 'FINISHED'"
              type="primary"
              class="pd-big-action"
              :icon="VideoPlay"
              @click="begin"
            >
              {{ isCalibration ? '开始基础测试' : `开始 ${MODE_LABELS[selectedMode]}` }}
            </el-button>

            <el-button
              v-else-if="running"
              type="danger"
              class="pd-big-action"
              @click="stop"
            >
              结束本轮
            </el-button>

            <template v-else>
              <el-button
                type="primary"
                class="pd-big-action"
                :loading="saving"
                @click="saveAndFinish"
              >
                保存本轮结果
              </el-button>
              <el-button class="pd-big-action" @click="confirmDiscard">重新开始</el-button>
            </template>
          </div>

          <p class="pd-muted" style="font-size: 13px; margin: 12px 0 0">
            难度只根据患者本人的基础测试结果和本次表现调整，不使用面部分析标签，
            也不使用任何疾病概率。算法版本：
            <span class="pd-mono">{{ DIFFICULTY_ENGINE_VERSION }}</span>
          </p>
        </div>
      </div>

      <!-- ------------------------------- live status ------------------------------- -->
      <div class="pd-card">
        <div class="pd-card-header">
          <span class="pd-card-title">本次状态</span>
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
            <div class="live-row">
              <span class="pd-secondary">目标音符</span>
              <strong class="live-note">
                {{ runner.currentCue.value?.binding.note ?? '—' }}
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
          </div>

          <div v-else class="pd-empty">
            尚未开始。点击左侧按钮开始
            {{ isCalibration ? '基础能力测试' : '训练' }}。
          </div>
        </div>
      </div>
    </div>

    <!-- ------------------------------- keyboard ------------------------------- -->
    <div class="pd-card">
      <div class="pd-card-header">
        <span class="pd-card-title">虚拟钢琴（C3 – B4，左手下排 / 右手上排）</span>
      </div>
      <div class="pd-card-body">
        <PianoKeyboard
          :pressed="runner.pressedKeys.value"
          :target-midi="targetMidi"
          :upcoming-midi="upcomingMidi"
          :error-midi="errorMidi"
          @press="runner.press($event)"
          @release="runner.release($event)"
        />
        <p class="pd-muted" style="font-size: 12px; margin: 12px 0 0">
          键盘与鼠标/触屏均可。<b>现在就可以点键试听</b>（不开始训练也能发声，按键不会入库）；
          开始训练后才会记录事件。蓝色描边高亮是当前应弹的音符。
        </p>
      </div>
    </div>

    <!-- ------------------------------- metrics ------------------------------- -->
    <div class="pd-card">
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
        <el-table :data="METRIC_ROWS" size="small">
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
            {{ adaptation.decision }}
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

  </div>
</template>

<style scoped>
/* Mode cards: plain names and one line of explanation each, instead of a
   dropdown of internal enum values. */
.mode-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(180px, 1fr));
  gap: 10px;
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
</style>
