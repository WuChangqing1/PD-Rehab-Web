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
import { computed, onBeforeUnmount, onMounted, ref } from 'vue'
import { useRoute } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import { InfoFilled, VideoPlay } from '@element-plus/icons-vue'

import MedicalDisclaimer from '@/components/MedicalDisclaimer.vue'
import { pianoApi } from '@/api'
import { notifyError } from '@/api/client'
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
import type { DifficultyConfig, PianoMode } from '@/piano/session'
import { DEFAULT_DIFFICULTY, MODE_LABELS } from '@/piano/session'
import type { Hand } from '@/piano/samples'
import { PIANO_INPUT_SOURCE_LABELS, type PianoInputSource } from '@/types'
import { NO_DATA, formatNumber, formatPercent } from '@/utils/format'

const route = useRoute()
const patientId = computed(() => String(route.params.id))

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

const MODES: PianoMode[] = [
  'CALIBRATION',
  'SINGLE_KEY_RHYTHM',
  'ALTERNATING_HANDS',
  'MAPPED_SEQUENCE',
  'FOLLOW_THE_BEAT',
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

/** Keyboard handling is global so the patient does not have to focus a key. */
function onKeyDown(event: KeyboardEvent) {
  if (!running.value) return
  if (event.repeat) return
  const binding = runner.press(event.code)
  if (!binding) return
  event.preventDefault()
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
  if (!running.value) return
  if (runner.release(event.code)) event.preventDefault()
}

onMounted(() => {
  window.addEventListener('keydown', onKeyDown)
  window.addEventListener('keyup', onKeyUp)
})
onBeforeUnmount(() => {
  window.removeEventListener('keydown', onKeyDown)
  window.removeEventListener('keyup', onKeyUp)
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
  })
}

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
    })

    // Decide the next round's difficulty from this session's metrics.
    const result = adaptDifficulty(
      runner.metrics.value,
      difficulty.value,
      calibration.value,
    )
    adaptation.value = result.decision === 'MAINTAIN' && !result.changes.length ? null : result

    if (isCalibration.value) {
      // Calibration defines the personal baseline that later rounds start from.
      calibration.value = baselineFromCalibration(runner.metrics.value)
      difficulty.value = initialDifficulty(calibration.value)
      ElMessage.success('Calibration 完成，已建立个人基线并推算初始难度')
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

    // Advance to the next round automatically after a training round.
    if (!isCalibration.value && roundNumber.value < 3) {
      roundNumber.value += 1
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
  <div class="pd-page">
    <div class="pd-page-header">
      <div>
        <h1 class="pd-page-title">虚拟钢琴 / 节奏训练</h1>
        <p class="pd-page-subtitle">
          第一版不依赖 MIDI：电脑键盘、鼠标与触屏均可。每个按键事件都会完整保存，
          并严格区分反应延迟与节拍误差。
        </p>
      </div>
      <el-tag v-if="runner.audioReady.value" type="success" size="small">音源已就绪</el-tag>
      <el-tag v-else type="info" size="small">音源未加载</el-tag>
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
      :title="`该会话的按键来源为「${PIANO_INPUT_SOURCE_LABELS[savedInputSource as PianoInputSource]}」`"
      description="下面的指标不是真人测量值，仅用于演示与流程验证。"
      style="margin-bottom: 16px"
    />

    <div class="pd-grid pd-grid-2">
      <!-- ------------------------------- configuration ------------------------------- -->
      <div class="pd-card">
        <div class="pd-card-header"><span class="pd-card-title">训练设置</span></div>
        <div class="pd-card-body">
          <el-form label-width="110px" :disabled="running">
            <el-form-item label="训练模式">
              <el-select v-model="selectedMode" style="width: 100%">
                <el-option
                  v-for="mode in MODES"
                  :key="mode"
                  :label="MODE_LABELS[mode]"
                  :value="mode"
                />
              </el-select>
            </el-form-item>

            <el-form-item v-if="isCalibration" label="Calibration 时长">
              <el-slider v-model="calibrationSeconds" :min="30" :max="60" :step="5" show-input />
            </el-form-item>

            <template v-else>
              <el-form-item label="轮次">
                <el-radio-group v-model="roundNumber">
                  <el-radio-button :value="1">Round 1</el-radio-button>
                  <el-radio-button :value="2">Round 2</el-radio-button>
                  <el-radio-button :value="3">Round 3</el-radio-button>
                </el-radio-group>
              </el-form-item>

              <el-form-item label="BPM">
                <el-input-number v-model="difficulty.bpm" :min="40" :max="160" :step="5" />
                <span class="pd-muted" style="margin-left: 8px; font-size: 12px">
                  由个人基线决定起点，训练中按规则调整
                </span>
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

              <el-form-item label="时长">
                <el-input-number
                  v-model="difficulty.session_duration_sec"
                  :min="20"
                  :max="300"
                  :step="10"
                />
                <span class="pd-muted" style="margin-left: 8px; font-size: 12px">秒</span>
              </el-form-item>
            </template>
          </el-form>

          <div class="actions">
            <el-button
              v-if="!running && runner.state.value !== 'FINISHED'"
              type="primary"
              class="pd-big-action"
              :icon="VideoPlay"
              @click="begin"
            >
              {{ isCalibration ? '开始 Calibration' : `开始 ${MODE_LABELS[selectedMode]}` }}
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

          <p class="pd-muted" style="font-size: 12px; margin: 12px 0 0">
            规则引擎版本 {{ DIFFICULTY_ENGINE_VERSION }}；难度只依赖个人 Calibration
            与本次表现，不使用微表情标签占比或疾病概率。
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
            {{ isCalibration ? 'Calibration' : '训练' }}。
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
          :disabled="!running"
          @press="runner.press($event)"
          @release="runner.release($event)"
        />
        <p class="pd-muted" style="font-size: 12px; margin: 12px 0 0">
          键盘与鼠标/触屏均可。每个按键只对应一个音符；下排（Z S X D C V G B H N J M）为左手
          C3–B3，上排（Q 2 W 3 E R 5 T 6 Y 7 U）为右手 C4–B4。蓝色高亮是当前应弹的音符。
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

    <MedicalDisclaimer />
  </div>
</template>

<style scoped>
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
