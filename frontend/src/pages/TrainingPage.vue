<script setup lang="ts">
/**
 * Training entry point.
 *
 * Phase 5 delivered the virtual piano, so this page is no longer a placeholder:
 * it is the only route that links to it. Until this existed the piano page could
 * be reached solely by typing its URL, which is exactly how it was missed.
 *
 * The Pose module belongs to Phase 6 and is shown as unavailable rather than as
 * a card that leads nowhere.
 */
import { computed, onMounted, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { Refresh } from '@element-plus/icons-vue'

import MedicalDisclaimer from '@/components/MedicalDisclaimer.vue'
import { patientApi, pianoApi, poseApi } from '@/api'
import { notifyError } from '@/api/client'
import { DIFFICULTY_ENGINE_VERSION } from '@/piano/difficulty'
import { presentationFor } from '@/pose/exercises'
import { MODE_LABELS } from '@/piano/session'
import type {
  Patient,
  PianoCalibrationBaseline,
  PianoSession,
  PoseSession,
  PoseThresholds,
} from '@/types'
import { PIANO_INPUT_SOURCE_LABELS } from '@/types'
import { NO_DATA, formatDateTime, formatNumber, formatPercent } from '@/utils/format'

const route = useRoute()
const router = useRouter()

const patientId = computed(() => String(route.params.id))
const patient = ref<Patient | null>(null)
const baseline = ref<PianoCalibrationBaseline | null>(null)
const sessions = ref<PianoSession[]>([])
const poseSessions = ref<PoseSession[]>([])
const poseThresholds = ref<PoseThresholds | null>(null)
const loading = ref(false)

/** The eight values of spec V2 section 20, in the order it lists them. */
const BASELINE_ROWS: Array<{ key: keyof PianoCalibrationBaseline; label: string; kind: 'ms' | 'ratio' | 'number' }> = [
  { key: 'baseline_accuracy', label: '基线准确率', kind: 'ratio' },
  { key: 'baseline_response_latency', label: '基线平均反应延迟', kind: 'ms' },
  { key: 'baseline_response_latency_cv', label: '基线反应延迟变异', kind: 'number' },
  { key: 'baseline_timing_mae', label: '基线节拍误差 MAE', kind: 'ms' },
  { key: 'baseline_left_accuracy', label: '基线左手准确率', kind: 'ratio' },
  { key: 'baseline_right_accuracy', label: '基线右手准确率', kind: 'ratio' },
  { key: 'baseline_left_latency', label: '基线左手延迟', kind: 'ms' },
  { key: 'baseline_right_latency', label: '基线右手延迟', kind: 'ms' },
]

function renderValue(value: unknown, kind: 'ms' | 'ratio' | 'number'): string {
  if (value === null || value === undefined) return NO_DATA
  const numeric = Number(value)
  if (!Number.isFinite(numeric)) return NO_DATA
  if (kind === 'ratio') return formatPercent(numeric)
  if (kind === 'ms') return `${numeric.toFixed(1)} ms`
  return formatNumber(numeric, 3)
}

/** Calibration rows that came from a scripted or seeded session, if any. */
const baselineProvenance = computed(() => {
  const meta = (baseline.value?.snapshot as { quality_metadata?: { input_source?: string } } | null)
    ?.quality_metadata
  const source = meta?.input_source
  if (!source || source === 'HUMAN_KEYBOARD') return null
  return source
})

const baselineNote = computed(() => {
  const note = (baseline.value?.snapshot as { note?: string } | null)?.note
  return typeof note === 'string' ? note : null
})

function sourceLabel(session: PianoSession): string | null {
  if (session.input_source === 'HUMAN_KEYBOARD') return null
  return PIANO_INPUT_SOURCE_LABELS[session.input_source] ?? session.input_source
}

async function load() {
  loading.value = true
  try {
    patient.value = await patientApi.get(patientId.value)
    const page = await pianoApi.history(patientId.value, 10)
    sessions.value = page.items
    try {
      baseline.value = await pianoApi.baseline(patientId.value)
    } catch {
      // 404 simply means no calibration yet; that is a state, not an error.
      baseline.value = null
    }

    const posePage = await poseApi.history(patientId.value, 10)
    poseSessions.value = posePage.items
    poseThresholds.value = await poseApi.thresholds()
  } catch (error) {
    notifyError(error, '无法加载训练信息。')
  } finally {
    loading.value = false
  }
}

function openPiano() {
  router.push({ name: 'training-piano', params: { id: patientId.value } })
}

function openMovement() {
  router.push({ name: 'training-movement', params: { id: patientId.value } })
}

onMounted(load)
</script>

<template>
  <div v-loading="loading" class="pd-page">
    <div class="pd-page-header">
      <div>
        <h1 class="pd-page-title">康复训练</h1>
        <p class="pd-page-subtitle">
          患者：{{ patient?.name ?? '—' }}。精细运动训练（虚拟钢琴 / 节奏）与动作训练（Pose /
          简单瑜伽）。每次训练都保存原始事件、录制文件与客观指标，而不只是游戏总分。
        </p>
      </div>
      <el-button :icon="Refresh" @click="load">刷新</el-button>
    </div>

    <div class="pd-grid pd-grid-2">
      <!-- ------------------------------ piano ------------------------------ -->
      <div class="pd-card">
        <div class="pd-card-header">
          <span class="pd-card-title">虚拟钢琴 / 节奏训练</span>
          <el-tag type="success" size="small">可用</el-tag>
        </div>
        <div class="pd-card-body">
          <p class="pd-secondary" style="margin-top: 0">
            精细运动与节拍同步训练。Calibration（30–60 秒，左右手各半）建立个人基线，
            之后是四种训练模式与最多三轮自适应难度。
          </p>
          <ul class="pd-list">
            <li>单键节奏 / 左右手交替 / 映射序列 / 跟随节拍</li>
            <li>每个按键事件（含按错、漏击、按下与抬起时刻）全部入库</li>
            <li>指标由服务端从原始事件重算，前端只做即时反馈</li>
            <li>
              规则引擎版本
              <span class="pd-mono">{{ DIFFICULTY_ENGINE_VERSION }}</span>：难度只依赖个人
              Calibration 与本次表现，不使用微表情标签占比或疾病概率
            </li>
          </ul>
          <el-button type="primary" class="pd-big-action" @click="openPiano">
            进入钢琴训练
          </el-button>
        </div>
      </div>

      <!-- --------------------------- calibration --------------------------- -->
      <div class="pd-card">
        <div class="pd-card-header">
          <span class="pd-card-title">当前钢琴 Calibration 基线</span>
          <el-tag v-if="baseline" size="small" type="info">
            {{ formatDateTime(baseline.created_at) }}
          </el-tag>
        </div>
        <div class="pd-card-body">
          <div v-if="!baseline" class="pd-empty">
            该患者尚未建立钢琴基线。进入钢琴训练并完成一次 Calibration 后，这里会显示八项基线值。
          </div>
          <template v-else>
            <el-alert
              v-if="baselineProvenance"
              type="warning"
              show-icon
              :closable="false"
              :title="`该基线来源为「${PIANO_INPUT_SOURCE_LABELS[baselineProvenance as keyof typeof PIANO_INPUT_SOURCE_LABELS] ?? baselineProvenance}」`"
              description="不是真人测量值，仅供流程演示，不得作为临床或科研基线使用。"
              style="margin-bottom: 12px"
            />
            <el-table :data="BASELINE_ROWS" size="small">
              <el-table-column label="指标">
                <template #default="{ row }">{{ row.label }}</template>
              </el-table-column>
              <el-table-column label="数值" width="140" align="right">
                <template #default="{ row }">
                  {{ renderValue(baseline?.[row.key as keyof PianoCalibrationBaseline], row.kind) }}
                </template>
              </el-table-column>
            </el-table>
            <p v-if="baselineNote" class="pd-muted" style="font-size: 12px; margin-bottom: 0">
              {{ baselineNote }}
            </p>
            <p class="pd-muted" style="font-size: 12px; margin-bottom: 0">
              算法版本：<span class="pd-mono">{{ baseline.algorithm_version ?? NO_DATA }}</span>
            </p>
          </template>
        </div>
      </div>
    </div>

    <!-- ------------------------------ pose ------------------------------ -->
    <div class="pd-grid pd-grid-2">
      <div class="pd-card">
        <div class="pd-card-header">
          <span class="pd-card-title">动作训练（Pose / 简单瑜伽）</span>
          <el-tag type="success" size="small">可用</el-tag>
        </div>
        <div class="pd-card-body">
          <p class="pd-secondary" style="margin-top: 0">
            五个简单动作，用摄像头录制或上传视频，由服务端 MediaPipe Pose 逐帧提取 33 个关键点，
            计算关节活动度、保持时间、动作次数与稳定性等原始指标。
          </p>
          <ul class="pd-list">
            <li>山式双臂上举 / 双臂侧平举 / 左右侧屈伸展 / 坐姿躯干旋转 / 坐姿交替抬臂</li>
            <li>每个动作都有禁忌提示；出现疼痛、头晕请立即停止</li>
            <li>未通过质量控制门限的录制会返回实测报告，<b>不当作有效测量值</b></li>
            <li>
              <b>展示分（完成度 / ROM / 对称性 / 稳定性）公式未定义，因此恒为空</b>，
              页面不会显示任何编造的分数
            </li>
          </ul>
          <el-button type="primary" class="pd-big-action" @click="openMovement">
            进入动作训练
          </el-button>
        </div>
      </div>

      <div class="pd-card">
        <div class="pd-card-header">
          <span class="pd-card-title">动作分析的质量门限</span>
        </div>
        <div class="pd-card-body">
          <div v-if="!poseThresholds" class="pd-empty">尚未获取门限配置。</div>
          <template v-else>
            <el-table :data="[
              { label: '最短时长', value: `${poseThresholds.min_duration_sec} 秒` },
              { label: '有效帧比例', value: `≥ ${(poseThresholds.min_valid_frame_ratio * 100).toFixed(0)}%` },
              { label: '关键点可见度', value: `≥ ${poseThresholds.min_landmark_visibility}` },
              { label: '动作幅度', value: `≥ ${poseThresholds.min_movement_range_deg}°` },
              { label: '完整动作次数', value: '至少 1 次' },
            ]" size="small">
              <el-table-column label="门限">
                <template #default="{ row }">{{ row.label }}</template>
              </el-table-column>
              <el-table-column label="要求" width="140" align="right">
                <template #default="{ row }">{{ row.value }}</template>
              </el-table-column>
            </el-table>
            <p class="pd-muted" style="font-size: 12px; margin-bottom: 0">
              算法版本 <span class="pd-mono">{{ poseThresholds.algorithm_version }}</span>；
              全部阈值由本次录制自身的活动范围导出，不引入外部临床常数。
            </p>
          </template>
        </div>
      </div>
    </div>

    <!-- ---------------------------- pose history ---------------------------- -->
    <div class="pd-card">
      <div class="pd-card-header">
        <span class="pd-card-title">最近动作训练记录</span>
      </div>
      <div class="pd-card-body">
        <el-table :data="poseSessions" size="small" empty-text="暂无动作训练记录">
          <el-table-column label="动作" min-width="150">
            <template #default="{ row }">
              {{ presentationFor(row.exercise_type).area }} ·
              {{ row.exercise_type.replace(/_/g, ' ').toLowerCase() }}
            </template>
          </el-table-column>
          <el-table-column label="完成次数" width="100" align="right">
            <template #default="{ row }">{{ row.repetition_count ?? NO_DATA }}</template>
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
                  : formatPercent(row.valid_pose_frame_ratio)
              }}
            </template>
          </el-table-column>
          <el-table-column label="状态" width="110">
            <template #default="{ row }">
              <el-tag v-if="row.completed_at" type="success" size="small">已通过</el-tag>
              <el-tag v-else type="info" size="small">未通过 / 未分析</el-tag>
            </template>
          </el-table-column>
          <el-table-column label="开始时间" width="170">
            <template #default="{ row }">{{ formatDateTime(row.started_at) }}</template>
          </el-table-column>
          <el-table-column label="来源" width="150">
            <template #default="{ row }">
              <el-tag v-if="sourceLabel(row)" type="warning" size="small">
                {{ sourceLabel(row) }}
              </el-tag>
              <span v-else class="pd-muted">真人录制</span>
            </template>
          </el-table-column>
        </el-table>
      </div>
    </div>

    <!-- ---------------------------- piano history ---------------------------- -->
    <div class="pd-card">
      <div class="pd-card-header">
        <span class="pd-card-title">最近钢琴训练记录</span>
      </div>
      <div class="pd-card-body">
        <el-table :data="sessions" size="small" empty-text="暂无钢琴训练记录">
          <el-table-column label="模式" min-width="150">
            <template #default="{ row }">
              {{ MODE_LABELS[row.mode as keyof typeof MODE_LABELS] ?? row.mode }}
            </template>
          </el-table-column>
          <el-table-column label="轮次" width="70">
            <template #default="{ row }">
              {{ row.mode === 'CALIBRATION' ? '—' : row.round_number }}
            </template>
          </el-table-column>
          <el-table-column label="难度" width="150">
            <template #default="{ row }">
              {{ row.bpm }} bpm / {{ row.judgement_window_ms }} ms
            </template>
          </el-table-column>
          <el-table-column label="准确率" width="90" align="right">
            <template #default="{ row }">{{ renderValue(row.accuracy, 'ratio') }}</template>
          </el-table-column>
          <el-table-column label="平均反应延迟" width="130" align="right">
            <template #default="{ row }">
              {{ renderValue(row.mean_response_latency_ms, 'ms') }}
            </template>
          </el-table-column>
          <el-table-column label="开始时间" width="170">
            <template #default="{ row }">{{ formatDateTime(row.started_at) }}</template>
          </el-table-column>
          <el-table-column label="来源" width="150">
            <template #default="{ row }">
              <el-tag v-if="sourceLabel(row)" type="warning" size="small">
                {{ sourceLabel(row) }}
              </el-tag>
              <span v-else class="pd-muted">真人键盘</span>
            </template>
          </el-table-column>
        </el-table>
        <p class="pd-muted" style="font-size: 12px; margin-bottom: 0">
          「来源」一栏标明该次按键是否来自真人：演示种子数据与脚本自检记录都如实标注，
          不会被当作患者测量值，也不进入长期趋势。
        </p>
      </div>
    </div>

    <MedicalDisclaimer />
  </div>
</template>

<style scoped>
.pd-list {
  margin: 0 0 16px;
  padding-left: 18px;
  color: var(--el-text-color-regular);
  font-size: 13px;
  line-height: 1.9;
}
</style>
