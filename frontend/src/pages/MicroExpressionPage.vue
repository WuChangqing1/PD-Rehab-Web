<script setup lang="ts">
/**
 * Micro-expression / AI video analysis.
 *
 * This page is built to be honest about state:
 *   - Model status comes from /api/system/models. While the model is not
 *     configured the upload control is disabled and the reason is shown.
 *   - No tag distribution, probability or placeholder chart is ever rendered
 *     from local data. If the backend returns no result, we show that.
 *   - Camera recording is offered only when the browser actually allows it.
 */
import { computed, onMounted, ref } from 'vue'
import { useRoute } from 'vue-router'
import { ElMessage } from 'element-plus'
import { UploadFilled, VideoCamera } from '@element-plus/icons-vue'
import type { UploadFile, UploadRawFile } from 'element-plus'

import MedicalDisclaimer from '@/components/MedicalDisclaimer.vue'
import { assessmentApi, systemApi } from '@/api'
import { notifyError, toApiError } from '@/api/client'
import type { MicroExpressionResult, ModelStatus } from '@/types'
import { useCameraCapability } from '@/utils/capability'
import { NO_DATA, formatDateTime, formatNumber } from '@/utils/format'

const route = useRoute()
const sessionId = computed(() =>
  typeof route.query.sessionId === 'string' ? route.query.sessionId : null,
)

const { cameraAvailable, reason: cameraReason } = useCameraCapability()

const modelStatus = ref<ModelStatus | null>(null)
const results = ref<MicroExpressionResult[]>([])
const loading = ref(false)
const uploading = ref(false)
const selectedFile = ref<File | null>(null)

const modelReady = computed(() => modelStatus.value?.is_ready === true)

async function load() {
  loading.value = true
  try {
    const models = await systemApi.models()
    modelStatus.value = models.models.micro_expression_model ?? null
    if (sessionId.value) {
      results.value = await assessmentApi.listMicroExpression(sessionId.value)
    }
  } catch (error) {
    notifyError(error, '无法加载模型状态。')
  } finally {
    loading.value = false
  }
}

function onFileChange(file: UploadFile) {
  selectedFile.value = (file.raw as UploadRawFile | undefined) ?? null
}

async function upload() {
  if (!sessionId.value) {
    ElMessage.warning('请先在综合评估页创建一条评估会话。')
    return
  }
  if (!selectedFile.value) {
    ElMessage.warning('请先选择视频文件。')
    return
  }

  uploading.value = true
  try {
    const result = await assessmentApi.uploadMicroExpression(
      sessionId.value,
      selectedFile.value,
      'UNKNOWN',
    )
    results.value = [result, ...results.value]
    ElMessage.success('分析完成')
    selectedFile.value = null
  } catch (error) {
    const apiError = toApiError(error)
    if (apiError.code === 'MODEL_NOT_CONFIGURED') {
      ElMessage.warning(apiError.message)
    } else {
      notifyError(error, '分析失败。')
    }
  } finally {
    uploading.value = false
  }
}

onMounted(load)
</script>

<template>
  <div v-loading="loading" class="pd-page">
    <div class="pd-page-header">
      <div>
        <h1 class="pd-page-title">微表情 / AI 视频分析</h1>
        <p class="pd-page-subtitle">
          上传面部视频，由老师团队的模型输出表情标签分布或辅助识别概率。结果按真实模型输出原样记录。
        </p>
      </div>
      <el-tag :type="modelReady ? 'success' : 'info'" size="large">
        {{ modelReady ? '模型就绪' : '模型未配置' }}
      </el-tag>
    </div>

    <el-alert
      v-if="modelStatus && !modelReady"
      type="warning"
      show-icon
      :closable="false"
      title="微表情模型当前不可用（MODEL_NOT_CONFIGURED）"
      style="margin-bottom: 16px"
    >
      <p style="margin: 0 0 6px">{{ modelStatus.detail }}</p>
      <p style="margin: 0">
        系统不会伪造模型输出：不会生成随机标签、不会写入截图中的百分比、也不会用替代模型冒充。
        配置方式见 <code>docs/model_integration.md</code>。
      </p>
    </el-alert>

    <div class="pd-grid pd-grid-2">
      <div class="pd-card">
        <div class="pd-card-header"><span class="pd-card-title">视频来源</span></div>
        <div class="pd-card-body">
          <el-alert
            v-if="!cameraAvailable"
            type="info"
            show-icon
            :closable="false"
            :title="cameraReason ?? '当前环境不支持浏览器摄像头'"
            style="margin-bottom: 12px"
          />

          <el-upload
            drag
            :auto-upload="false"
            :limit="1"
            accept=".mp4,.mov,.avi"
            :on-change="onFileChange"
            :disabled="!modelReady"
          >
            <el-icon class="el-icon--upload"><UploadFilled /></el-icon>
            <div class="el-upload__text">将视频拖到此处，或<em>点击选择文件</em></div>
            <template #tip>
              <div class="el-upload__tip">
                支持 mp4 / mov / avi。文件以 UUID 命名存储，不使用患者姓名。
              </div>
            </template>
          </el-upload>

          <div class="record-row">
            <el-button
              :icon="VideoCamera"
              class="pd-big-action"
              :disabled="!cameraAvailable || !modelReady"
            >
              浏览器摄像头录制
            </el-button>
            <span class="pd-muted" style="font-size: 12px">
              {{
                cameraAvailable
                  ? '录制功能将在 Phase 3 接入，当前请使用文件上传。'
                  : '不可用：需要 HTTPS 或 localhost 安全上下文。'
              }}
            </span>
          </div>

          <el-button
            type="primary"
            class="pd-big-action"
            style="width: 100%; margin-top: 12px"
            :loading="uploading"
            :disabled="!modelReady || !selectedFile"
            @click="upload"
          >
            开始分析
          </el-button>

          <p v-if="!sessionId" class="pd-muted" style="font-size: 12px; margin-bottom: 0">
            未指定评估会话，请从「综合评估」页进入本页面。
          </p>
        </div>
      </div>

      <div class="pd-card">
        <div class="pd-card-header"><span class="pd-card-title">分析结果</span></div>
        <div class="pd-card-body">
          <div v-if="!results.length" class="pd-empty">
            暂无分析结果。<br />
            <span style="font-size: 12px">
              模型未配置或尚未上传视频时，本区域保持为空 —— 不会显示占位图表。
            </span>
          </div>

          <div v-for="item in results" :key="item.id" class="result-block">
            <div class="result-head">
              <strong>模型：</strong>{{ item.model_name ?? NO_DATA }}
              <span class="pd-muted">/ 版本 {{ item.model_version ?? NO_DATA }}</span>
            </div>
            <dl class="pd-kv">
              <dt>主导标签</dt><dd>{{ item.dominant_tag ?? NO_DATA }}</dd>
              <dt>预测类别</dt><dd>{{ item.predicted_class ?? NO_DATA }}</dd>
              <dt>模型输出概率</dt><dd>{{ formatNumber(item.pd_probability, 3) }}</dd>
              <dt>推理耗时</dt>
              <dd>{{ item.inference_time_ms != null ? `${item.inference_time_ms} ms` : NO_DATA }}</dd>
              <dt>分析时间</dt><dd>{{ formatDateTime(item.created_at) }}</dd>
            </dl>

            <div v-if="item.tag_distribution?.length" class="pd-tag-list">
              <el-tag v-for="tag in item.tag_distribution" :key="tag.name" size="small">
                {{ tag.name }} {{ (tag.score * 100).toFixed(1) }}%
              </el-tag>
            </div>

            <p class="pd-muted" style="font-size: 12px; margin: 10px 0 0">
              标签占比表示面部运动 / 表情表现维度，不代表疾病严重程度，也不用于调整训练难度。
            </p>
          </div>
        </div>
      </div>
    </div>

    <MedicalDisclaimer />
  </div>
</template>

<style scoped>
.record-row {
  display: flex;
  align-items: center;
  gap: 12px;
  margin-top: 16px;
  flex-wrap: wrap;
}

.result-block + .result-block {
  margin-top: 18px;
  padding-top: 18px;
  border-top: 1px solid var(--pd-border);
}

.result-head {
  margin-bottom: 10px;
}
</style>
