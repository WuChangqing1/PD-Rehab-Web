<script setup lang="ts">
/**
 * Finger Tapping: left and right hands analysed separately.
 *
 * Every number on this page comes from a stored analysis result. A metric that
 * was not produced renders as 暂无数据 and is never replaced by 0. Left/right
 * difference is left - right; a missing side stays empty.
 */
import { computed, onMounted, ref } from 'vue'
import { useRoute } from 'vue-router'
import { ElMessage } from 'element-plus'
import { InfoFilled, UploadFilled } from '@element-plus/icons-vue'
import type { UploadFile, UploadRawFile } from 'element-plus'

import ApertureChart from '@/components/ApertureChart.vue'
import { assessmentApi } from '@/api'
import { notifyError, toApiError } from '@/api/client'
import type { FingerTappingResult, FingerTappingSessionSummary, FingerTappingTimeseries } from '@/types'
import { NO_DATA, formatDateTime, formatNumber } from '@/utils/format'

const route = useRoute()
const sessionId = computed(() =>
  typeof route.query.sessionId === 'string' ? route.query.sessionId : null,
)

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

const hasAnyResult = computed(
  () => Boolean(summary.value?.left) || Boolean(summary.value?.right),
)

function onFileChange(hand: 'LEFT' | 'RIGHT', file: UploadFile) {
  files.value[hand] = (file.raw as UploadRawFile | undefined) ?? null
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
  if (!sessionId.value) {
    ElMessage.warning('请先在综合评估页创建一条评估会话。')
    return
  }
  const file = files.value[hand]
  if (!file) {
    ElMessage.warning(`请先选择${hand === 'LEFT' ? '左' : '右'}手视频文件。`)
    return
  }

  uploading.value = hand
  try {
    summary.value = await assessmentApi.uploadFingerTapping(
      sessionId.value,
      file,
      hand,
      'UNKNOWN',
    )
    files.value[hand] = null
    await loadSeries(hand)
    ElMessage.success('分析完成')
  } catch (error) {
    const apiError = toApiError(error)
    // Quality rejections carry the measured quality report; show why.
    const detail = apiError.detail as Record<string, unknown> | null
    const quality = detail?.quality as Record<string, unknown> | undefined
    if (quality) {
      const ratio = quality.valid_frame_ratio
      const cycles = quality.cycle_count
      ElMessage.warning(
        `${apiError.message}` +
          (ratio !== undefined && ratio !== null ? `（有效帧比例 ${Number(ratio).toFixed(2)}）` : '') +
          (cycles !== undefined && cycles !== null ? `（有效周期 ${cycles} 个）` : ''),
      )
    } else {
      notifyError(error, '上传或分析失败。')
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

onMounted(load)
</script>

<template>
  <div v-loading="loading" class="pd-page">
    <div class="pd-page-header">
      <div>
        <h1 class="pd-page-title">Finger Tapping 运动量化</h1>
        <p class="pd-page-subtitle">
          左右手分别录制、分别保存、分别分析。建议录制 10～20 秒，录制前 3 秒倒计时。
        </p>
      </div>
    </div>

    <el-alert type="info" show-icon :closable="false" style="margin-bottom: 16px">
      <template #title>录制提示</template>
      <ul class="tips">
        <li>请将完整手掌放在摄像头前</li>
        <li>使用拇指和食指，连续进行张开—闭合动作</li>
        <li>尽量快速且规律，避免手掌离开画面</li>
      </ul>
    </el-alert>

    <el-alert
      type="warning"
      show-icon
      :closable="false"
      title="严重度分类不可用"
      description="外部算法仓库不包含预训练严重度模型，也不提供推理入口，因此 severity_score / severity_label 恒为空。系统不会伪造该分数。"
      style="margin-bottom: 16px"
    />

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
          <el-upload
            drag
            :auto-upload="false"
            :limit="1"
            accept=".mp4,.mov,.avi"
            :on-change="(f: UploadFile) => onFileChange(hand, f)"
          >
            <el-icon class="el-icon--upload"><UploadFilled /></el-icon>
            <div class="el-upload__text">拖入视频或<em>点击选择</em></div>
          </el-upload>
          <el-button
            type="primary"
            class="pd-big-action"
            style="width: 100%; margin-top: 12px"
            :loading="uploading === hand"
            @click="upload(hand)"
          >
            上传并分析{{ hand === 'LEFT' ? '左手' : '右手' }}
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
        <span class="pd-card-title">运动学指标（真实结果）</span>
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
