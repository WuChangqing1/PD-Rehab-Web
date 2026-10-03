<script setup lang="ts">
/**
 * Follow-up and reports: one place for looking back at a patient's data.
 *
 * History, trends and the report were three separate pages reached from three
 * different places, each showing a development notice. They are the same task --
 * "show me what has happened" -- so they are one entry with three views.
 *
 * Two rules shape everything here:
 *
 * 1. **Only measurements are plotted.** Training tables also hold scripted
 *    self-tests and seeded demo rows. Those are dropped from every series and
 *    the count is shown, so a demo row can never read as patient progress.
 *
 * 2. **There is no composite score.** The system has no validated formula for
 *    one, so the report lists each module's objective metrics side by side and
 *    says plainly that it is not a severity assessment.
 */
import { computed, onMounted, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'

import PatientSelector from '@/components/PatientSelector.vue'
import SelectedPatientBar from '@/components/SelectedPatientBar.vue'
import TrendChart from '@/components/TrendChart.vue'
import { assessmentApi, pianoApi, poseApi } from '@/api'
import { notifyError } from '@/api/client'
import {
  buildTrendSeries,
  latestPoint,
  previousPoint,
  type TrendRowInput,
  type TrendUnit,
} from '@/followup/trends'
import { usePatientContextStore } from '@/stores/patientContext'
import { exerciseName } from '@/pose/exercises'
import { MODE_LABELS, type PianoMode } from '@/piano/session'
import type {
  AssessmentSession,
  FingerTappingResult,
  Patient,
  PianoSession,
  PoseSession,
} from '@/types'
import {
  NO_DATA,
  SESSION_TYPE_LABELS,
  formatDateTime,
  formatNumber,
  formatPercent,
} from '@/utils/format'
// The provenance filtering stays in the data layer (`followup/trends.ts`); this
// page just does not explain it to the reader any more.
import { isHumanSource } from '@/utils/source'

const route = useRoute()
const router = useRouter()
const store = usePatientContextStore()

const patient = ref<Patient | null>(null)
const tab = ref<'timeline' | 'trends' | 'report'>('timeline')
const sessions = ref<AssessmentSession[]>([])
const piano = ref<PianoSession[]>([])
const pose = ref<PoseSession[]>([])
const tapping = ref<FingerTappingResult[]>([])
const loading = ref(false)

const patientId = computed(() => patient.value?.id ?? null)

/** Which exercise the movement trend is about; the metrics differ per exercise. */
const poseExercise = ref<string>('')


async function load() {
  if (!patientId.value) return
  loading.value = true
  try {
    const id = patientId.value
    sessions.value = (await assessmentApi.listSessions(id, 1, 50)).items
    piano.value = (await pianoApi.history(id, 50)).items
    pose.value = (await poseApi.history(id, 50)).items
    tapping.value = await assessmentApi.listFingerTappingResults(id)
    const firstExercise = pose.value.find((s) => s.exercise_type)?.exercise_type ?? ''
    if (!poseExercise.value) poseExercise.value = firstExercise
  } catch (error) {
    notifyError(error, '无法加载随访数据。')
  } finally {
    loading.value = false
  }
}

async function usePatient(id: string) {
  patient.value = await store.resolve(id)
  if (patient.value) {
    router.replace({ query: { ...route.query, patientId: id } })
    await load()
  }
}

// ------------------------------------------------------------------- series
/**
 * Piano rows reduced to trend input.
 *
 * Only rounds that produced metrics are plottable; a calibration run or an
 * abandoned round stores nulls and the builder counts them as skipped.
 */
function pianoRows(key: keyof PianoSession): TrendRowInput[] {
  return piano.value.map((row) => ({
    at: row.completed_at ?? row.started_at,
    value: typeof row[key] === 'number' ? (row[key] as number) : null,
    source: row.input_source,
    version: row.metrics_version,
  }))
}

function poseRows(key: keyof PoseSession): TrendRowInput[] {
  return pose.value
    .filter((row) => row.exercise_type === poseExercise.value)
    .map((row) => ({
      at: row.completed_at ?? row.started_at,
      value: typeof row[key] === 'number' ? (row[key] as number) : null,
      // Camera recordings are always a real measurement; the enum is shared with
      // the piano module and seeded pose rows still carry SEED_DEMO.
      source: row.input_source,
      version: row.algorithm_version,
    }))
}

/**
 * Finger tapping rows reduced to trend input.
 *
 * `input_source` is carried through rather than assumed. Rows written before the
 * provenance column exist as UNLABELLED, and at least one of those came from the
 * test fixture `finger_tapping_sample.mp4`; treating them as measurements would
 * put a fixture on a patient's chart. The hand filter keeps left and right from
 * being averaged into one line.
 */
function tappingRows(hand: 'LEFT' | 'RIGHT', key: keyof FingerTappingResult): TrendRowInput[] {
  return tapping.value
    .filter((row) => row.hand === hand)
    .map((row) => ({
      at: row.created_at,
      value: typeof row[key] === 'number' ? (row[key] as number) : null,
      source: row.input_source,
      version: row.analyzer_version,
    }))
}

interface ChartSpec {
  key: string
  label: string
  unit: TrendUnit
  rows: TrendRowInput[]
}

const pianoCharts = computed<ChartSpec[]>(() => [
  { key: 'accuracy', label: '准确率', unit: 'ratio', rows: pianoRows('accuracy') },
  {
    key: 'mean_response_latency_ms',
    label: '平均反应延迟',
    unit: 'ms',
    rows: pianoRows('mean_response_latency_ms'),
  },
  {
    key: 'mean_timing_error_ms',
    label: '平均节拍误差',
    unit: 'ms',
    rows: pianoRows('mean_timing_error_ms'),
  },
  { key: 'miss_rate', label: '漏击率', unit: 'ratio', rows: pianoRows('miss_rate') },
])

const poseCharts = computed<ChartSpec[]>(() => [
  {
    key: 'repetition_count',
    label: '完成次数',
    unit: 'count',
    rows: poseRows('repetition_count'),
  },
  { key: 'hold_time_sec', label: '保持时间', unit: 'sec', rows: poseRows('hold_time_sec') },
  {
    key: 'movement_speed',
    label: '动作速度',
    unit: 'number',
    rows: poseRows('movement_speed'),
  },
  {
    key: 'valid_pose_frame_ratio',
    label: '有效帧比例',
    unit: 'ratio',
    rows: poseRows('valid_pose_frame_ratio'),
  },
])

const tappingCharts = computed<ChartSpec[]>(() => [
  {
    key: 'tapping_frequency_left',
    label: '左手敲击频率',
    unit: 'number',
    rows: tappingRows('LEFT', 'tapping_frequency'),
  },
  {
    key: 'tapping_frequency_right',
    label: '右手敲击频率',
    unit: 'number',
    rows: tappingRows('RIGHT', 'tapping_frequency'),
  },
  {
    key: 'cycle_cv_left',
    label: '左手周期变异系数',
    unit: 'number',
    rows: tappingRows('LEFT', 'cycle_cv'),
  },
  {
    key: 'cycle_cv_right',
    label: '右手周期变异系数',
    unit: 'number',
    rows: tappingRows('RIGHT', 'cycle_cv'),
  },
])

const series = computed(() =>
  [...pianoCharts.value, ...poseCharts.value, ...tappingCharts.value].map((spec) => ({
    spec,
    built: buildTrendSeries(spec.rows),
  })),
)

/**
 * Provenance summary across every series.
 *
 * The excluded count is taken from the stored records, not by summing the
 * per-series counters: one record feeds four series, so summing them reported
 * "74 excluded records" when the real number of records is far smaller. A count
 * that overstates itself is still a wrong number on screen.
 *
 * The missing-value counters are per (record × metric) pair by nature -- a round
 * can store an accuracy and no timing error -- so they are labelled as pairs.
 */
const provenance = computed(() => {
  const all = series.value
  return {
    excludedByModule: nonHumanTotals.value,
    excludedRecords:
      nonHumanTotals.value.piano + nonHumanTotals.value.pose + nonHumanTotals.value.tapping,
    missingValuePairs: all.reduce((sum, s) => sum + s.built.skippedMissingValue, 0),
    missingTimestampPairs: all.reduce((sum, s) => sum + s.built.skippedNoTimestamp, 0),
    mixedVersions: all.filter((s) => s.built.mixedVersions).map((s) => s.spec.label),
    plottable: all.filter((s) => s.built.points.length > 0).length,
  }
})

const nonHumanTotals = computed(() => ({
  piano: piano.value.filter((row) => !isHumanSource(row.input_source)).length,
  pose: pose.value.filter((row) => !isHumanSource(row.input_source)).length,
  tapping: tapping.value.filter((row) => !isHumanSource(row.input_source)).length,
}))

const poseExercises = computed(() => {
  const keys: string[] = []
  for (const row of pose.value) {
    if (row.exercise_type && !keys.includes(row.exercise_type)) keys.push(row.exercise_type)
  }
  return keys.map((key) => ({ key, label: exerciseName(key) }))
})

/** Piano mode in plain language; a mode stored by a future version shows itself. */
function pianoModeLabel(mode: string): string {
  return MODE_LABELS[mode as PianoMode] ?? mode
}

function displayValue(value: number | null | undefined, unit: TrendUnit): string {  if (value === null || value === undefined) return NO_DATA
  if (unit === 'ratio') return formatPercent(value)
  if (unit === 'ms') return `${value.toFixed(1)} ms`
  if (unit === 'count') return `${value.toFixed(0)} 次`
  if (unit === 'sec') return `${value.toFixed(2)} s`
  if (unit === 'deg') return `${value.toFixed(1)}°`
  return formatNumber(value, 3)
}

/** The latest and previous plottable value for one series, for the report. */
function summaryFor(spec: ChartSpec) {
  const built = buildTrendSeries(spec.rows)
  return {
    spec,
    built,
    latest: latestPoint(built),
    previous: previousPoint(built),
  }
}

const pianoReport = computed(() => pianoCharts.value.map(summaryFor))
const poseReport = computed(() => poseCharts.value.map(summaryFor))
const tappingReport = computed(() => tappingCharts.value.map(summaryFor))

onMounted(async () => {
  const fromQuery = route.query.patientId
  const fromTab = route.query.tab
  if (fromTab === 'trends' || fromTab === 'report') tab.value = fromTab
  if (typeof fromQuery === 'string' && fromQuery) await usePatient(fromQuery)
})
</script>

<template>
  <div v-loading="loading" class="pd-page">
    <div class="pd-page-header">
      <div>
        <h1 class="pd-page-title">随访与报告</h1>
        <p class="pd-page-subtitle">
          查看患者既往的评估与训练记录。先选择患者。
        </p>
      </div>
    </div>

    <SelectedPatientBar v-if="patient" :patient="patient" @change="patient = null" />

    <PatientSelector
      v-if="!patient"
      title="选择患者"
      description="搜索姓名或患者编号，选择后查看其随访数据。"
      @select="(p) => usePatient(p.id)"
    />

    <template v-else>
      <el-tabs v-model="tab" class="pd-card tabs-card">
        <!-- ------------------------------------------------------- timeline -->
        <el-tab-pane label="时间轴" name="timeline">
          <div class="pd-card-body">
            <p class="pd-secondary" style="margin-top: 0">
              按时间顺序查看已保存的评估与训练记录。
            </p>

            <h4>评估记录</h4>
            <el-table :data="sessions" size="small" empty-text="暂无评估记录">
              <el-table-column label="开始时间" width="180">
                <template #default="{ row }">{{ formatDateTime(row.started_at) }}</template>
              </el-table-column>
              <el-table-column label="类型" width="140">
                <template #default="{ row }">{{ SESSION_TYPE_LABELS[row.session_type] ?? row.session_type }}</template>
              </el-table-column>
              <el-table-column label="状态" width="110">
                <template #default="{ row }">
                  {{ row.status === 'COMPLETED' ? '已完成' : '进行中' }}
                </template>
              </el-table-column>
            </el-table>

            <h4>手指敲击</h4>
            <el-table :data="tapping" size="small" empty-text="暂无手指敲击结果">
              <el-table-column label="时间" width="180">
                <template #default="{ row }">{{ formatDateTime(row.created_at) }}</template>
              </el-table-column>
              <el-table-column label="手" width="70">
                <template #default="{ row }">{{ row.hand === 'LEFT' ? '左手' : '右手' }}</template>
              </el-table-column>
              <el-table-column label="敲击频率" width="110">
                <template #default="{ row }">{{ displayValue(row.tapping_frequency, 'number') }}</template>
              </el-table-column>
              <el-table-column label="周期变异系数" width="130">
                <template #default="{ row }">{{ displayValue(row.cycle_cv, 'number') }}</template>
              </el-table-column>
            </el-table>

            <h4>钢琴训练</h4>
            <el-table :data="piano" size="small" empty-text="暂无钢琴训练记录">
              <el-table-column label="开始时间" width="180">
                <template #default="{ row }">{{ formatDateTime(row.started_at) }}</template>
              </el-table-column>
              <el-table-column label="模式" width="150">
                <template #default="{ row }">{{ pianoModeLabel(row.mode) }}</template>
              </el-table-column>
              <el-table-column label="准确率" width="100">
                <template #default="{ row }">{{ displayValue(row.accuracy, 'ratio') }}</template>
              </el-table-column>
            </el-table>

            <h4>动作训练</h4>
            <el-table :data="pose" size="small" empty-text="暂无动作训练记录">
              <el-table-column label="开始时间" width="180">
                <template #default="{ row }">{{ formatDateTime(row.started_at) }}</template>
              </el-table-column>
              <el-table-column label="动作" width="160">
                <template #default="{ row }">
                  {{ exerciseName(row.exercise_type) }}
                </template>
              </el-table-column>
              <el-table-column label="完成次数" width="100">
                <template #default="{ row }">{{ row.repetition_count ?? NO_DATA }}</template>
              </el-table-column>
            </el-table>
          </div>
        </el-tab-pane>

        <!-- --------------------------------------------------------- trends -->
        <el-tab-pane label="趋势分析" name="trends">
          <div class="pd-card-body">
            <!--
              The data cleaning is real and still runs: non-measurement rows,
              rows with no value for this metric and rows with no timestamp are
              dropped before anything is drawn. What is gone is the explanation
              of it. A doctor reading a chart needs the chart, not a note about
              which rows the software discarded to produce it.
            -->
            <div v-if="provenance.plottable === 0" class="pd-empty">
              <div>暂无可绘制的趋势。</div>
              <div style="font-size: 12px; margin-top: 6px">
                完成一次测量并保存后即可看到曲线。只有一个数据点时会显示为点，
                积累两次以上才会连成线。
              </div>
            </div>

            <template v-else>
              <h4>钢琴训练</h4>
              <div class="chart-grid">
                <div v-for="item in series.filter((s) => pianoCharts.includes(s.spec))" :key="item.spec.key" class="pd-card chart-card">
                  <div class="pd-card-header">
                    <span class="pd-card-title">{{ item.spec.label }}</span>
                    <el-tag v-if="item.built.points.length" size="small" type="info">
                      {{ item.built.points.length }} 个点
                    </el-tag>
                  </div>
                  <div class="pd-card-body">
                    <TrendChart
                      :points="item.built.points"
                      :label="item.spec.label"
                      :unit="item.spec.unit"
                    />
                  </div>
                </div>
              </div>

              <template v-if="poseExercises.length">
                <h4>动作训练</h4>
                <el-radio-group v-model="poseExercise" size="small" style="margin-bottom: 12px">
                  <el-radio-button
                    v-for="exercise in poseExercises"
                    :key="exercise.key"
                    :value="exercise.key"
                  >
                    {{ exercise.label }}
                  </el-radio-button>
                </el-radio-group>
                <div class="chart-grid">
                  <div v-for="item in series.filter((s) => poseCharts.includes(s.spec))" :key="item.spec.key" class="pd-card chart-card">
                    <div class="pd-card-header">
                      <span class="pd-card-title">{{ item.spec.label }}</span>
                      <el-tag v-if="item.built.points.length" size="small" type="info">
                        {{ item.built.points.length }} 个点
                      </el-tag>
                    </div>
                    <div class="pd-card-body">
                      <TrendChart
                        :points="item.built.points"
                        :label="item.spec.label"
                        :unit="item.spec.unit"
                      />
                    </div>
                  </div>
                </div>
              </template>

              <h4>手指敲击</h4>
              <div class="chart-grid">
                <div v-for="item in series.filter((s) => tappingCharts.includes(s.spec))" :key="item.spec.key" class="pd-card chart-card">
                  <div class="pd-card-header">
                    <span class="pd-card-title">{{ item.spec.label }}</span>
                    <el-tag v-if="item.built.points.length" size="small" type="info">
                      {{ item.built.points.length }} 个点
                    </el-tag>
                  </div>
                  <div class="pd-card-body">
                    <TrendChart
                      :points="item.built.points"
                      :label="item.spec.label"
                      :unit="item.spec.unit"
                    />
                  </div>
                </div>
              </div>
            </template>
          </div>
        </el-tab-pane>

        <!-- --------------------------------------------------------- report -->
        <el-tab-pane label="综合报告" name="report">
          <div class="pd-card-body">
            <p class="pd-secondary" style="margin-top: 0">
              各模块的客观指标并列，附测量时间与上一次的对照值。
              系统不输出综合评分、严重程度分级或病情变化百分比：这些需要经过验证的公式，
              目前没有，因此留空而不是估算。
            </p>

            <h4>钢琴训练</h4>
            <el-table :data="pianoReport" size="small" empty-text="暂无钢琴训练记录">
              <el-table-column label="指标" min-width="170">
                <template #default="{ row }">{{ row.spec.label }}</template>
              </el-table-column>
              <el-table-column label="最近一次" width="150" align="right">
                <template #default="{ row }">
                  {{ displayValue(row.latest?.value, row.spec.unit) }}
                </template>
              </el-table-column>
              <el-table-column label="测量时间" width="180">
                <template #default="{ row }">
                  {{ row.latest ? formatDateTime(row.latest.at) : NO_DATA }}
                </template>
              </el-table-column>
              <el-table-column label="上一次" width="130" align="right">
                <template #default="{ row }">
                  {{ displayValue(row.previous?.value, row.spec.unit) }}
                </template>
              </el-table-column>
              <el-table-column label="可用于趋势的点数" width="150" align="right">
                <template #default="{ row }">{{ row.built.points.length }}</template>
              </el-table-column>
            </el-table>

            <h4>芭蕾动作训练（{{ poseExercise ? exerciseName(poseExercise) : '未选择动作' }}）</h4>
            <el-table :data="poseReport" size="small" empty-text="暂无动作训练记录">
              <el-table-column label="指标" min-width="170">
                <template #default="{ row }">{{ row.spec.label }}</template>
              </el-table-column>
              <el-table-column label="最近一次" width="150" align="right">
                <template #default="{ row }">
                  {{ displayValue(row.latest?.value, row.spec.unit) }}
                </template>
              </el-table-column>
              <el-table-column label="测量时间" width="180">
                <template #default="{ row }">
                  {{ row.latest ? formatDateTime(row.latest.at) : NO_DATA }}
                </template>
              </el-table-column>
              <el-table-column label="上一次" width="130" align="right">
                <template #default="{ row }">
                  {{ displayValue(row.previous?.value, row.spec.unit) }}
                </template>
              </el-table-column>
              <el-table-column label="可用于趋势的点数" width="150" align="right">
                <template #default="{ row }">{{ row.built.points.length }}</template>
              </el-table-column>
            </el-table>

            <h4>手指敲击</h4>
            <el-table :data="tappingReport" size="small" empty-text="暂无手指敲击结果">
              <el-table-column label="指标" min-width="170">
                <template #default="{ row }">{{ row.spec.label }}</template>
              </el-table-column>
              <el-table-column label="最近一次" width="150" align="right">
                <template #default="{ row }">
                  {{ displayValue(row.latest?.value, row.spec.unit) }}
                </template>
              </el-table-column>
              <el-table-column label="测量时间" width="180">
                <template #default="{ row }">
                  {{ row.latest ? formatDateTime(row.latest.at) : NO_DATA }}
                </template>
              </el-table-column>
              <el-table-column label="上一次" width="130" align="right">
                <template #default="{ row }">
                  {{ displayValue(row.previous?.value, row.spec.unit) }}
                </template>
              </el-table-column>
              <el-table-column label="可用于趋势的点数" width="150" align="right">
                <template #default="{ row }">{{ row.built.points.length }}</template>
              </el-table-column>
            </el-table>

            <p class="pd-muted" style="font-size: 12px; margin-top: 16px">
              缺失的数值显示为「{{ NO_DATA }}」，不会被当成 0。
            </p>
          </div>
        </el-tab-pane>
      </el-tabs>
    </template>
  </div>
</template>

<style scoped>
.tabs-card {
  padding: 0 18px 18px;
}

h4 {
  margin: 18px 0 8px;
  font-size: 14px;
}

.chart-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(min(360px, 100%), 1fr));
  gap: 16px;
}

.chart-card {
  display: flex;
  flex-direction: column;
}
</style>
