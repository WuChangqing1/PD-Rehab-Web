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

import MedicalDisclaimer from '@/components/MedicalDisclaimer.vue'
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
        <h1 class="pd-page-title">模型状态</h1>
        <p class="pd-page-subtitle">
          组件真实可用性。未配置的组件显示为「未配置」，系统不会用模拟结果替代。
        </p>
      </div>
      <el-button :icon="Refresh" @click="load">刷新</el-button>
    </div>

    <el-alert
      v-if="models?.mock_mode"
      type="warning"
      show-icon
      :closable="false"
      title="DEMO DATA：当前处于 Mock 模式"
      description="DEMO_MOCK_MODE=true。演示数据不得与真实模型输出混淆。"
      style="margin-bottom: 16px"
    />

    <div class="pd-grid pd-grid-4">
      <div class="pd-stat">
        <div class="pd-stat-label">模型总数</div>
        <div class="pd-stat-value">{{ models?.summary.total ?? '—' }}</div>
      </div>
      <div class="pd-stat">
        <div class="pd-stat-label">就绪</div>
        <div class="pd-stat-value">{{ models?.summary.ready ?? '—' }}</div>
      </div>
      <div class="pd-stat">
        <div class="pd-stat-label">不可用 / 未配置</div>
        <div class="pd-stat-value is-muted">{{ models?.summary.not_ready ?? '—' }}</div>
      </div>
      <div class="pd-stat">
        <div class="pd-stat-label">推理设备</div>
        <div class="pd-stat-value is-muted">{{ gpu?.device ?? '—' }}</div>
      </div>
    </div>

    <div class="pd-card">
      <div class="pd-card-header"><span class="pd-card-title">组件状态</span></div>
      <div class="pd-card-body">
        <div v-for="row in modelRows" :key="row.name" class="model-row">
          <div class="model-head">
            <strong>{{ MODEL_LABELS[row.name] ?? row.name }}</strong>
            <el-tag :type="modelStateTagType(row.state)" size="small">
              {{ MODEL_STATE_LABELS[row.state] ?? row.state }}
            </el-tag>
          </div>
          <dl class="pd-kv">
            <dt>版本</dt><dd class="pd-mono">{{ row.version || '—' }}</dd>
            <dt>设备</dt><dd>{{ row.device ?? '—' }}</dd>
            <dt>加载时间</dt><dd>{{ formatDateTime(row.loaded_at) }}</dd>
            <dt>说明</dt><dd>{{ row.detail ?? '—' }}</dd>
          </dl>
          <el-collapse v-if="extraEntries(row.extra).length" class="model-extra">
            <el-collapse-item title="附加信息" :name="row.name">
              <dl class="pd-kv">
                <template v-for="[key, value] in extraEntries(row.extra)" :key="key">
                  <dt>{{ key }}</dt>
                  <dd class="pd-mono">{{ value }}</dd>
                </template>
              </dl>
            </el-collapse-item>
          </el-collapse>
        </div>
      </div>
    </div>

    <div class="pd-grid pd-grid-2">
      <div class="pd-card">
        <div class="pd-card-header"><span class="pd-card-title">推理设备</span></div>
        <div class="pd-card-body">
          <dl v-if="gpu" class="pd-kv">
            <dt>请求使用 GPU</dt><dd>{{ gpu.use_gpu_requested ? '是' : '否' }}</dd>
            <dt>PyTorch 已安装</dt><dd>{{ gpu.torch_installed ? '是' : '否' }}</dd>
            <dt>PyTorch 版本</dt><dd class="pd-mono">{{ gpu.torch_version ?? '—' }}</dd>
            <dt>CUDA 运行时</dt><dd class="pd-mono">{{ gpu.cuda_version ?? '—' }}</dd>
            <dt>CUDA 可用</dt><dd>{{ gpu.cuda_available ? '是' : '否' }}</dd>
            <dt>设备名称</dt><dd>{{ gpu.device_name ?? '—' }}</dd>
            <dt>计算能力</dt><dd class="pd-mono">{{ gpu.compute_capability ?? '—' }}</dd>
            <dt>推理并发上限</dt><dd>{{ gpu.gpu_inference_concurrency }}</dd>
          </dl>
          <el-alert
            v-if="gpu?.driver_note"
            type="info"
            show-icon
            :closable="false"
            :title="gpu.driver_note"
            style="margin-top: 12px"
          />
        </div>
      </div>

      <div class="pd-card">
        <div class="pd-card-header"><span class="pd-card-title">运行环境</span></div>
        <div class="pd-card-body">
          <dl v-if="info" class="pd-kv">
            <dt>应用</dt><dd>{{ info.app }}</dd>
            <dt>环境</dt><dd>{{ info.env }}</dd>
            <dt>Python</dt><dd class="pd-mono">{{ info.python_version }}</dd>
            <dt>平台</dt><dd class="pd-mono">{{ info.platform }}</dd>
            <dt>数据库</dt><dd class="pd-mono">{{ info.database_url_scheme }}</dd>
            <dt>Mock 模式</dt><dd>{{ info.mock_mode ? '开启' : '关闭' }}</dd>
          </dl>
          <h3 style="margin-top: 16px">数据量</h3>
          <dl v-if="info" class="pd-kv">
            <dt>患者</dt><dd>{{ info.counts.patients }}</dd>
            <dt>评估会话</dt><dd>{{ info.counts.assessment_sessions }}</dd>
            <dt>微表情结果</dt><dd>{{ info.counts.micro_expression_results }}</dd>
            <dt>Finger Tapping 结果</dt><dd>{{ info.counts.finger_tapping_results }}</dd>
            <dt>钢琴训练</dt><dd>{{ info.counts.piano_sessions }}</dd>
            <dt>动作训练</dt><dd>{{ info.counts.pose_sessions }}</dd>
          </dl>
        </div>
      </div>
    </div>

    <div class="pd-card">
      <div class="pd-card-header">
        <span class="pd-card-title">已定义的动作训练项目</span>
      </div>
      <div class="pd-card-body">
        <el-table :data="models?.exercises ?? []" size="small">
          <el-table-column prop="name_zh" label="动作" width="150" />
          <el-table-column prop="description" label="说明" min-width="240" />
          <el-table-column label="展示分公式" width="130">
            <template #default="{ row }">
              <el-tag :type="row.scores_available ? 'success' : 'info'" size="small">
                {{ row.scores_available ? '已定义' : '未定义' }}
              </el-tag>
            </template>
          </el-table-column>
          <el-table-column label="目标次数" width="100">
            <template #default="{ row }">{{ row.target_repetitions ?? '—' }}</template>
          </el-table-column>
          <el-table-column label="禁忌" min-width="180">
            <template #default="{ row }">
              {{ row.contraindications.length ? row.contraindications.join('、') : '—' }}
            </template>
          </el-table-column>
        </el-table>
        <p class="pd-muted" style="font-size: 12px; margin: 12px 0 0">
          展示分公式未定义前，completion / ROM / symmetry / stability 一律不入库、不展示。
        </p>
      </div>
    </div>

    <MedicalDisclaimer />
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
