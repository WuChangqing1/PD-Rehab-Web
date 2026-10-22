<script setup lang="ts">
/**
 * Model status page (/system/model-status).
 *
 * Everything here reflects measured state. A component that cannot run is shown
 * as unavailable along with the reason, so nobody has to guess whether a
 * displayed result is real.
 */
import { computed, onMounted, ref } from 'vue'
import { Refresh } from '@element-plus/icons-vue'

import { systemApi } from '@/api'
import { notifyError } from '@/api/client'
import type { GpuStatus, ModelsResponse, SystemInfo } from '@/types'
import { MODEL_STATE_LABELS, formatDateTime, modelStateTagType } from '@/utils/format'

const loading = ref(false)
const models = ref<ModelsResponse | null>(null)
const gpu = ref<GpuStatus | null>(null)
const info = ref<SystemInfo | null>(null)

const MODEL_LABELS: Record<string, string> = {
  micro_expression_model: '微表情 / AI 辅助识别模型',
  finger_tapping: 'Finger Tapping 分析',
  mediapipe_hand_landmarker: 'MediaPipe Hand Landmarker（手部关键点模型）',
  mediapipe_pose: 'MediaPipe Pose（姿态关键点模型）',
}

const modelRows = computed(() => Object.values(models.value?.models ?? {}))

async function load() {
  loading.value = true
  try {
    const [m, g, i] = await Promise.all([
      systemApi.models(),
      systemApi.gpu(),
      systemApi.info(),
    ])
    models.value = m
    gpu.value = g
    info.value = i
  } catch (error) {
    notifyError(error, '无法加载模型状态。')
  } finally {
    loading.value = false
  }
}

/** Render a nested extra value without dumping raw JSON at the user. */
function extraEntries(extra: Record<string, unknown>): Array<[string, string]> {
  const out: Array<[string, string]> = []
  for (const [key, value] of Object.entries(extra)) {
    if (value === null || value === undefined) continue
    if (Array.isArray(value)) {
      out.push([key, value.length ? value.join(', ') : '（空）'])
    } else if (typeof value === 'object') {
      out.push([key, JSON.stringify(value)])
    } else {
      out.push([key, String(value)])
    }
  }
  return out
}

onMounted(load)
</script>

<template>
  <div v-loading="loading" class="pd-page">
    <div class="pd-page-header">
      <div>
        <h1 class="pd-page-title">{{ $t("模型状态") }}</h1>
        <p class="pd-page-subtitle">
          {{ $t("组件真实可用性。未配置的组件显示为「未配置」，系统不会用模拟结果替代。") }}
        </p>
      </div>
      <el-button :icon="Refresh" @click="load">{{ $t("刷新") }}</el-button>
    </div>

    <el-alert
      v-if="models?.mock_mode"
      type="warning"
      show-icon
      :closable="false"
      :title="$t('DEMO DATA：当前处于 Mock 模式')"
      :description="$t('DEMO_MOCK_MODE=true。演示数据不得与真实模型输出混淆。')"
      style="margin-bottom: 16px"
    />

    <div class="pd-grid pd-grid-4">
      <div class="pd-stat">
        <div class="pd-stat-label">{{ $t("模型总数") }}</div>
        <div class="pd-stat-value">{{ $t(models?.summary.total ?? '—') }}</div>
      </div>
      <div class="pd-stat">
        <div class="pd-stat-label">{{ $t("就绪") }}</div>
        <div class="pd-stat-value">{{ $t(models?.summary.ready ?? '—') }}</div>
      </div>
      <div class="pd-stat">
        <div class="pd-stat-label">{{ $t("不可用 / 未配置") }}</div>
        <div class="pd-stat-value is-muted">{{ $t(models?.summary.not_ready ?? '—') }}</div>
      </div>
      <div class="pd-stat">
        <div class="pd-stat-label">{{ $t("推理设备") }}</div>
        <div class="pd-stat-value is-muted">{{ $t(gpu?.device ?? '—') }}</div>
      </div>
    </div>

    <div class="pd-card">
      <div class="pd-card-header"><span class="pd-card-title">{{ $t("组件状态") }}</span></div>
      <div class="pd-card-body">
        <div v-for="row in modelRows" :key="row.name" class="model-row">
          <div class="model-head">
            <strong>{{ $t(MODEL_LABELS[row.name] ?? row.name) }}</strong>
            <el-tag :type="modelStateTagType(row.state)" size="small">
              {{ $t(MODEL_STATE_LABELS[row.state] ?? row.state) }}
            </el-tag>
          </div>
          <dl class="pd-kv">
            <dt>{{ $t("版本") }}</dt><dd class="pd-mono">{{ $t(row.version || '—') }}</dd>
            <dt>{{ $t("设备") }}</dt><dd>{{ $t(row.device ?? '—') }}</dd>
            <dt>{{ $t("加载时间") }}</dt><dd>{{ $t(formatDateTime(row.loaded_at)) }}</dd>
            <dt>{{ $t("说明") }}</dt><dd>{{ $t(row.detail ?? '—') }}</dd>
          </dl>
          <el-collapse v-if="extraEntries(row.extra).length" class="model-extra">
            <el-collapse-item :title="$t('附加信息')" :name="row.name">
              <dl class="pd-kv">
                <template v-for="[key, value] in extraEntries(row.extra)" :key="key">
                  <dt>{{ $t(key) }}</dt>
                  <dd class="pd-mono">{{ $t(value) }}</dd>
                </template>
              </dl>
            </el-collapse-item>
          </el-collapse>
        </div>
      </div>
    </div>

    <div class="pd-grid pd-grid-2">
      <div class="pd-card">
        <div class="pd-card-header"><span class="pd-card-title">{{ $t("推理设备") }}</span></div>
        <div class="pd-card-body">
          <dl v-if="gpu" class="pd-kv">
            <dt>{{ $t("请求使用 GPU") }}</dt><dd>{{ $t(gpu.use_gpu_requested ? '是' : '否') }}</dd>
            <dt>{{ $t("PyTorch 已安装") }}</dt><dd>{{ $t(gpu.torch_installed ? '是' : '否') }}</dd>
            <dt>{{ $t("PyTorch 版本") }}</dt><dd class="pd-mono">{{ $t(gpu.torch_version ?? '—') }}</dd>
            <dt>{{ $t("CUDA 运行时") }}</dt><dd class="pd-mono">{{ $t(gpu.cuda_version ?? '—') }}</dd>
            <dt>{{ $t("CUDA 可用") }}</dt><dd>{{ $t(gpu.cuda_available ? '是' : '否') }}</dd>
            <dt>{{ $t("设备名称") }}</dt><dd>{{ $t(gpu.device_name ?? '—') }}</dd>
            <dt>{{ $t("计算能力") }}</dt><dd class="pd-mono">{{ $t(gpu.compute_capability ?? '—') }}</dd>
            <dt>{{ $t("推理并发上限") }}</dt><dd>{{ $t(gpu.gpu_inference_concurrency) }}</dd>
          </dl>
          <el-alert
            v-if="gpu?.driver_note"
            type="info"
            show-icon
            :closable="false"
            :title="$t(gpu.driver_note)"
            style="margin-top: 12px"
          />
        </div>
      </div>

      <div class="pd-card">
        <div class="pd-card-header"><span class="pd-card-title">{{ $t("运行环境") }}</span></div>
        <div class="pd-card-body">
          <dl v-if="info" class="pd-kv">
            <dt>{{ $t("应用") }}</dt><dd>{{ $t(info.app) }}</dd>
            <dt>{{ $t("环境") }}</dt><dd>{{ $t(info.env) }}</dd>
            <dt>Python</dt><dd class="pd-mono">{{ $t(info.python_version) }}</dd>
            <dt>{{ $t("平台") }}</dt><dd class="pd-mono">{{ $t(info.platform) }}</dd>
            <dt>{{ $t("数据库") }}</dt><dd class="pd-mono">{{ $t(info.database_url_scheme) }}</dd>
            <dt>{{ $t("Mock 模式") }}</dt><dd>{{ $t(info.mock_mode ? '开启' : '关闭') }}</dd>
          </dl>
          <h3 style="margin-top: 16px">{{ $t("数据量") }}</h3>
          <dl v-if="info" class="pd-kv">
            <dt>{{ $t("患者") }}</dt><dd>{{ $t(info.counts.patients) }}</dd>
            <dt>{{ $t("评估会话") }}</dt><dd>{{ $t(info.counts.assessment_sessions) }}</dd>
            <dt>{{ $t("微表情结果") }}</dt><dd>{{ $t(info.counts.micro_expression_results) }}</dd>
            <dt>{{ $t("Finger Tapping 结果") }}</dt><dd>{{ $t(info.counts.finger_tapping_results) }}</dd>
            <dt>{{ $t("钢琴训练") }}</dt><dd>{{ $t(info.counts.piano_sessions) }}</dd>
            <dt>{{ $t("动作训练") }}</dt><dd>{{ $t(info.counts.pose_sessions) }}</dd>
          </dl>
        </div>
      </div>
    </div>

    <div class="pd-card">
      <div class="pd-card-header">
        <span class="pd-card-title">{{ $t("已定义的动作训练项目") }}</span>
      </div>
      <div class="pd-card-body">
        <el-table :data="models?.exercises ?? []" size="small">
          <el-table-column prop="name_zh" :label="$t('动作')" width="150" :formatter="(row: { name_zh: unknown }) => $t(row.name_zh)" />
          <el-table-column prop="description" :label="$t('说明')" min-width="240" :formatter="(row: { description: unknown }) => $t(row.description)" />
          <el-table-column :label="$t('展示分公式')" width="130">
            <template #default="{ row }">
              <el-tag :type="row.scores_available ? 'success' : 'info'" size="small">
                {{ $t(row.scores_available ? '已定义' : '未定义') }}
              </el-tag>
            </template>
          </el-table-column>
          <el-table-column :label="$t('目标次数')" width="100">
            <template #default="{ row }">{{ $t(row.target_repetitions ?? '—') }}</template>
          </el-table-column>
          <el-table-column :label="$t('禁忌')" min-width="180">
            <template #default="{ row }">
              {{ $t(row.contraindications.length ? row.contraindications.map((item: unknown) => $t(item)).join($t('、')) : '—') }}
            </template>
          </el-table-column>
        </el-table>

      </div>
    </div>

  </div>
</template>

<style scoped>
.model-row + .model-row {
  margin-top: 18px;
  padding-top: 18px;
  border-top: 1px solid var(--pd-border);
}

.model-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  margin-bottom: 10px;
}

.model-extra {
  margin-top: 8px;
}
</style>
