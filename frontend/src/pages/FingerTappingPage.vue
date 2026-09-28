<script setup lang="ts">
/**
 * Finger Tapping: left and right hands analysed separately.
 *
 * The analysis pipeline is not implemented yet (Phase 4), so uploads fail with
 * NOT_IMPLEMENTED and the page says so. No metric is ever shown unless it came
 * from a real analysis result.
 *
 * Left/right difference is left - right; a missing side renders as 暂无数据 and
 * is never replaced by 0.
 */
import { computed, onMounted, ref } from 'vue'
import { useRoute } from 'vue-router'
import { ElMessage } from 'element-plus'
import { InfoFilled, UploadFilled } from '@element-plus/icons-vue'
import type { UploadFile, UploadRawFile } from 'element-plus'

import MedicalDisclaimer from '@/components/MedicalDisclaimer.vue'
import { assessmentApi } from '@/api'
import { notifyError, toApiError } from '@/api/client'
import type { FingerTappingResult, FingerTappingSessionSummary } from '@/types'
import { NO_DATA, formatNumber } from '@/utils/format'

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
  { key: 'tapping_frequency', label: '敲击频率', digits: 2, unit: ' Hz', hint: '有效敲击周期数 / 有效分析时长' },
  { key: 'avg_amplitude', label: '平均动作幅度', digits: 3, hint: '掌宽归一化后的拇指-食指距离差（无量纲）' },
  { key: 'avg_speed', label: '平均动作速度', digits: 3, hint: '归一化距离一阶变化率，单位 1/秒' },
  { key: 'avg_cycle_duration', label: '平均周期时长', digits: 3, unit: ' s' },
  { key: 'amplitude_cv', label: '幅度变异系数', digits: 3, hint: '标准差 / 均值' },
  { key: 'speed_cv', label: '速度变异系数', digits: 3 },
  { key: 'cycle_cv', label: '周期变异系数', digits: 3 },
  { key: 'amplitude_slope', label: '幅度趋势斜率', digits: 4, hint: '对周期序号回归，单位：每周期变化量' },
  { key: 'speed_slope', label: '速度趋势斜率', digits: 4 },
  { key: 'cycle_slope', label: '周期趋势斜率', digits: 4 },
  { key: 'interruptions', label: '中断次数', digits: 0, hint: '周期时长 > 1.5 × 周期中位数 的次数' },
]

const QUALITY_ROWS: MetricRow[] = [
  { key: 'valid_frame_ratio', label: '有效帧比例', digits: 3 },
  { key: 'avg_landmark_confidence', label: '平均关键点置信度', digits: 3, hint: '当前 MediaPipe Tasks API 无法提供，字段保持为空' },
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
const files = ref<Record<'LEFT' | 'RIGHT', File | null>>({ LEFT: null, RIGHT: null })

function onFileChange(hand: 'LEFT' | 'RIGHT', file: UploadFile) {
  files.value[hand] = (file.raw as UploadRawFile | undefined) ?? null
}

async function load() {
  if (!sessionId.value) return
  loading.value = true
  try {
    summary.value = await assessmentApi.getFingerTapping(sessionId.value)
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
    summary.value = await assessmentApi.uploadFingerTapping(sessionId.value, file, hand, 'UNKNOWN')
    ElMessage.success('上传成功')
    files.value[hand] = null
  } catch (error) {
    const apiError = toApiError(error)
    if (apiError.code === 'NOT_IMPLEMENTED') {
      ElMessage.warning(apiError.message)
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
  const digits = spec?.digits ?? 3
  const unit = spec?.unit ?? ''
  return `${Number(value).toFixed(digits)}${unit}`
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
      title="分析流水线尚未实现（Phase 4）"
      description="视频可以正常上传并保存，但 OpenCV + MediaPipe 关键点提取与特征计算将在 Phase 4 完成。当前不会产生任何运动学指标，系统也不会用示例数字填充下方表格。"
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
          <el-table-column label="指标" min-width="180">
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
          <el-table-column label="指标" min-width="180">
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
          严重度分类（severity_score / severity_label）恒为空：外部算法仓库不包含预训练严重度模型，
          也不提供推理入口。系统不会伪造该分数。
        </p>
      </div>
    </div>

    <MedicalDisclaimer />
  </div>
</template>

<style scoped>
.tips {
  margin: 4px 0 0;
  padding-left: 18px;
}
</style>
