<script setup lang="ts">
/**
 * One video capture panel for every module that needs a recording.
 *
 * Micro-expression, finger tapping and pose all ask the same question -- "give
 * me a clip" -- and each had grown its own answer, including one button that did
 * nothing. This panel is the single implementation: camera when the browser
 * allows it, file upload always, preview and retake in both cases.
 *
 * A control that cannot work is not rendered as a dead button. When the camera
 * is unavailable the panel says why and makes file upload the primary path.
 */
import { computed, onBeforeUnmount, ref, watch } from 'vue'
import { Upload, VideoCamera, VideoPlay } from '@element-plus/icons-vue'

import { useCameraCapability } from '@/utils/capability'
import { DEFAULT_RECORDING_NAME, pickRecordingFormat, recordingFilename } from '@/utils/recording'

const props = withDefaults(
  defineProps<{
    /** Shown above the preview; explains what to record. */
    instruction?: string
    /** Stop automatically at this length, protecting a forgotten camera. */
    maxSeconds?: number
    /** Extra line under the preview, e.g. framing advice. */
    hint?: string
    disabled?: boolean
  }>(),
  {
    instruction: '',
    maxSeconds: 120,
    hint: '',
    disabled: false,
  },
)

const emit = defineEmits<{
  (e: 'change', payload: { blob: Blob | null; name: string }): void
}>()

const { cameraAvailable, reason: cameraReason } = useCameraCapability()

const cameraOn = ref(false)
const recording = ref(false)
const cameraError = ref<string | null>(null)
const blob = ref<Blob | null>(null)
const objectUrl = ref<string | null>(null)
const seconds = ref(0)
const filename = ref(DEFAULT_RECORDING_NAME)
const videoEl = ref<HTMLVideoElement | null>(null)

let stream: MediaStream | null = null
let recorder: MediaRecorder | null = null
let timer = 0

const hasClip = computed(() => blob.value !== null)

function publish(next: Blob | null, name: string) {
  blob.value = next
  filename.value = name
  if (objectUrl.value) URL.revokeObjectURL(objectUrl.value)
  objectUrl.value = next ? URL.createObjectURL(next) : null
  emit('change', { blob: next, name })
}

async function openCamera() {
  cameraError.value = null
  if (!cameraAvailable.value) {
    cameraError.value = cameraReason.value ?? '当前环境无法使用摄像头。'
    return
  }
  try {
    stream = await navigator.mediaDevices.getUserMedia({
      video: { width: { ideal: 1280 }, height: { ideal: 720 } },
      audio: false,
    })
    cameraOn.value = true
    if (videoEl.value) {
      videoEl.value.srcObject = stream
      await videoEl.value.play()
    }
  } catch (error) {
    cameraError.value =
      error instanceof Error ? error.message : '无法打开摄像头，请检查浏览器权限。'
  }
}

function closeCamera() {
  stream?.getTracks().forEach((track) => track.stop())
  stream = null
  cameraOn.value = false
  recording.value = false
  window.clearInterval(timer)
}

function startRecording() {
  if (!stream) return
  const chunks: Blob[] = []
  const format = pickRecordingFormat()
  const options = format.mimeType ? { mimeType: format.mimeType } : undefined
  recorder = new MediaRecorder(stream, options)
  const actualType = recorder.mimeType || format.mimeType || 'video/webm'

  recorder.ondataavailable = (event) => {
    if (event.data.size > 0) chunks.push(event.data)
  }
  recorder.onstop = () => {
    // The filename must name the container the recorder actually produced.
    publish(new Blob(chunks, { type: actualType }), recordingFilename(actualType))
  }

  recorder.start()
  recording.value = true
  seconds.value = 0
  timer = window.setInterval(() => {
    seconds.value += 0.1
    if (seconds.value >= props.maxSeconds) stopRecording()
  }, 100)
}

function stopRecording() {
  recorder?.stop()
  recorder = null
  recording.value = false
  window.clearInterval(timer)
}

function onFilePicked(event: Event) {
  const input = event.target as HTMLInputElement
  const file = input.files?.[0]
  if (!file) return
  closeCamera()
  publish(file, file.name)
}

function retake() {
  publish(null, DEFAULT_RECORDING_NAME)
  seconds.value = 0
}

watch(
  () => props.disabled,
  (disabled) => {
    if (disabled) closeCamera()
  },
)

onBeforeUnmount(() => {
  closeCamera()
  if (objectUrl.value) URL.revokeObjectURL(objectUrl.value)
})

defineExpose({ clear: retake })
</script>

<template>
  <div class="capture">
    <p v-if="instruction" class="pd-secondary" style="margin-top: 0">{{ instruction }}</p>

    <el-alert
      v-if="!cameraAvailable"
      type="info"
      show-icon
      :closable="false"
      :title="cameraReason ?? '当前环境无法使用摄像头'"
      description="可以直接选择一段已录好的视频文件，分析结果完全相同。"
      style="margin-bottom: 12px"
    />

    <el-alert
      v-if="cameraError"
      type="error"
      show-icon
      :closable="false"
      :title="cameraError"
      style="margin-bottom: 12px"
    />

    <div class="preview">
      <video v-show="cameraOn" ref="videoEl" class="preview-video" muted playsinline />
      <video v-if="!cameraOn && objectUrl" :src="objectUrl" class="preview-video" controls />
      <div v-if="!cameraOn && !objectUrl" class="preview-empty">
        打开摄像头录制，或直接选择一段已有的视频文件
      </div>
    </div>

    <div class="capture-actions">
      <template v-if="!cameraOn">
        <el-button
          v-if="cameraAvailable"
          :icon="VideoCamera"
          :disabled="disabled"
          @click="openCamera"
        >
          打开摄像头
        </el-button>
        <label class="file-label">
          <input type="file" accept="video/*" :disabled="disabled" @change="onFilePicked" />
          <el-button
            :icon="Upload"
            :type="cameraAvailable ? 'default' : 'primary'"
            :disabled="disabled"
          >
            {{ cameraAvailable ? '选择视频文件' : '选择视频文件（推荐）' }}
          </el-button>
        </label>
      </template>

      <template v-else>
        <el-button
          v-if="!recording"
          type="primary"
          :icon="VideoPlay"
          :disabled="disabled"
          @click="startRecording"
        >
          开始录制
        </el-button>
        <el-button v-else type="danger" @click="stopRecording">
          停止录制（{{ seconds.toFixed(1) }} s）
        </el-button>
        <el-button @click="closeCamera">关闭摄像头</el-button>
      </template>

      <el-button v-if="hasClip" :disabled="disabled || recording" @click="retake">
        重新采集
      </el-button>
    </div>

    <p v-if="hint" class="pd-muted" style="font-size: 12px; margin: 8px 0 0">{{ hint }}</p>
  </div>
</template>

<style scoped>
.preview {
  position: relative;
  width: 100%;
  aspect-ratio: 16 / 9;
  background: #10151a;
  border-radius: 8px;
  overflow: hidden;
  margin-bottom: 12px;
}

.preview-video {
  width: 100%;
  height: 100%;
  object-fit: contain;
  display: block;
}

.preview-empty {
  position: absolute;
  inset: 0;
  display: flex;
  align-items: center;
  justify-content: center;
  color: #8b97a3;
  font-size: 14px;
  padding: 0 24px;
  text-align: center;
}

.capture-actions {
  display: flex;
  flex-wrap: wrap;
  gap: 10px;
}

.file-label input {
  display: none;
}
</style>
