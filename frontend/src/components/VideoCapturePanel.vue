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
import { computed, nextTick, onBeforeUnmount, ref, watch } from 'vue'
import { Upload, VideoCamera, VideoPlay } from '@element-plus/icons-vue'

import { readyCamera } from '@/utils/cameraReady'
import { useCameraCapability } from '@/utils/capability'
import {newCaptureLifetime,beginCapture,invalidateCapture,disposeCapture,isCurrentCapture} from '@/utils/captureLifetime'
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
    showFilePreview?: boolean
    guided?: boolean
  }>(),
  {
    instruction: '',
    maxSeconds: 120,
    hint: '',
    disabled: false,
    showFilePreview: true,
  },
)

const emit = defineEmits<{
  (e: 'change', payload: { blob: Blob | null; name: string }): void
  (e: 'recording-change', active:boolean):void
}>()

const { cameraAvailable, reason: cameraReason } = useCameraCapability()

const cameraOn = ref(false)
const recording = ref(false)
const opening = ref(false)
const stopping = ref(false)
const cameraError = ref<string | null>(null)
const blob = ref<Blob | null>(null)
const objectUrl = ref<string | null>(null)
const seconds = ref(0)
const filename = ref(DEFAULT_RECORDING_NAME)
const videoEl = ref<HTMLVideoElement | null>(null)
const fileInput = ref<HTMLInputElement | null>(null)

const lifetime=newCaptureLifetime()
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

/**
 * Which camera to ask for.
 *
 * `user` is the screen-side camera, which is what a face or hand task needs when
 * someone holds the phone. For a standing ballet exercise the phone is usually
 * propped up across the room and the rear camera is the better lens, so the
 * panel offers a switch rather than guessing from the task.
 *
 * `ideal` rather than `exact`: a device with one camera must still open it
 * instead of failing with OverconstrainedError.
 */
const facing = ref<'user' | 'environment'>('user')
const canSwitchCamera = ref(false)

/**
 * Turn a getUserMedia failure into something a person can act on.
 *
 * The DOMException names are accurate and useless at the bedside:
 * "NotAllowedError" does not tell anyone what to do next. The name is kept in
 * the console for whoever is debugging.
 */
function describeCameraError(error: unknown): string {
  const name = error instanceof DOMException ? error.name : ''
  if (name) console.warn('[camera] getUserMedia failed:', name, error)

  if (name === 'NotAllowedError' || name === 'SecurityError') {
    return '无法使用摄像头：请允许浏览器访问摄像头，或改为上传已有视频。'
  }
  if (name === 'NotFoundError' || name === 'OverconstrainedError') {
    return '没有找到可用的摄像头，请改为上传已有视频。'
  }
  if (name === 'NotReadableError') {
    return '摄像头被其他程序占用，请关闭后重试，或改为上传已有视频。'
  }
  return '摄像头暂时无法使用，请改为上传已有视频。'
}

async function openCamera(device: 'user' | 'environment' = facing.value) {
  if(opening.value || props.disabled)return
  const ticket=beginCapture(lifetime)
  opening.value = true
  cameraError.value = null
  if (!cameraAvailable.value) {
    opening.value = false
    cameraError.value = cameraReason.value ?? '当前浏览器无法使用摄像头，请使用视频上传。'
    return
  }
  try {
    const cameraStream = await navigator.mediaDevices.getUserMedia({
      video: {
        facingMode: { ideal: device },
        width: { ideal: 1280 },
        height: { ideal: 720 },
      },
      audio: false,
    })
    if(!isCurrentCapture(lifetime,ticket)){cameraStream.getTracks().forEach(track=>track.stop());return}
    stream=cameraStream
    facing.value = device
    cameraOn.value = true
    await readyCamera(async()=>{
      await nextTick()
      if(!isCurrentCapture(lifetime,ticket))return
      if(!videoEl.value)throw Error('Preview missing')
      videoEl.value.srcObject = cameraStream
      videoEl.value.setAttribute('playsinline','true')
      await videoEl.value.play()
    },()=>{if(isCurrentCapture(lifetime,ticket))opening.value=false},async()=>{
      await detectCameraCount()
    })
  } catch (error) {
    if(isCurrentCapture(lifetime,ticket)){closeCamera();cameraError.value = describeCameraError(error)}
  }
}

/** Whether a second camera exists, so the switch is not offered pointlessly. */
async function detectCameraCount() {
  try {
    const devices = await navigator.mediaDevices.enumerateDevices()
    canSwitchCamera.value = devices.filter((d) => d.kind === 'videoinput').length > 1
  } catch {
    canSwitchCamera.value = false
  }
}

/** Swap between the front and rear camera without leaving the panel. */
async function switchCamera() {
  closeCamera()
  await openCamera(facing.value === 'user' ? 'environment' : 'user')
}

function closeCamera() {
  invalidateCapture(lifetime)
  opening.value=false
  stopping.value=false
  if(recorder){
    invalidateCapture(lifetime)
    if(recorder?.state==='recording')recorder.stop()
    recorder=null
  }
  stream?.getTracks().forEach((track) => track.stop())
  stream = null
  cameraOn.value = false
  recording.value = false
  emit('recording-change',false)
  window.clearInterval(timer)
}

function startRecording() {
  if (!stream||lifetime.disposed||recording.value||stopping.value||props.disabled) return
  if(typeof MediaRecorder==='undefined'){cameraError.value='当前浏览器不支持录制，请选择视频文件。';return}
  cameraError.value=null
  try {
  const ticket=beginCapture(lifetime)
  const chunks: Blob[] = []
  const format = pickRecordingFormat()
  const options = format.mimeType ? { mimeType: format.mimeType } : undefined
  recorder = new MediaRecorder(stream, options)
  const actualType = recorder.mimeType || format.mimeType || 'video/webm'

  recorder.ondataavailable = (event) => {
    if (isCurrentCapture(lifetime,ticket)&&event.data.size > 0) chunks.push(event.data)
  }
  recorder.onstop = () => {
    if(!isCurrentCapture(lifetime,ticket))return
    const recorded=new Blob(chunks, { type: actualType })
    closeCamera()
    if(recorded.size)publish(recorded, recordingFilename(actualType))
    else cameraError.value='未录到视频，请重新录制。'
  }

  recorder.onerror = () => {
    if(!isCurrentCapture(lifetime,ticket))return
    closeCamera()
    cameraError.value='录制失败，请重新录制或选择视频文件。'
  }
  recorder.start()
  recording.value = true
  emit('recording-change',true)
  seconds.value = 0
  timer = window.setInterval(() => {
    seconds.value += 0.1
    if (seconds.value >= props.maxSeconds) stopRecording()
  }, 100)
  } catch {
    closeCamera()
    cameraError.value='录制失败，请重新录制或选择视频文件。'
  }
}

function stopRecording() {
  if(recorder?.state!=='recording')return
  stopping.value=true
  recorder.stop()
  recording.value = false
  window.clearInterval(timer)
}

function onFilePicked(event: Event) {
  const input = event.target as HTMLInputElement
  const file = input.files?.[0]
  if (!file) return
  invalidateCapture(lifetime)
  closeCamera()
  publish(file, file.name)
}

function retake() {
  closeCamera()
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
  disposeCapture(lifetime)
  closeCamera()
  if (objectUrl.value) URL.revokeObjectURL(objectUrl.value)
})

defineExpose({ clear: retake })
</script>

<template>
  <div class="capture">
    <p v-if="instruction" class="pd-secondary" style="margin-top: 0">{{ $t(instruction) }}</p>

    <el-alert
      v-if="!cameraAvailable"
      type="info"
      show-icon
      :closable="false"
      :title="$t(cameraReason ?? '当前环境无法使用摄像头')"
      :description="$t('可以直接选择一段已录好的视频文件，分析结果完全相同。')"
      style="margin-bottom: 12px"
    />

    <el-alert
      v-if="cameraError"
      type="error"
      show-icon
      :closable="false"
      :title="$t(cameraError)"
      style="margin-bottom: 12px"
    />

    <div v-show="cameraOn || !objectUrl || showFilePreview" class="preview">
      <video v-show="cameraOn" ref="videoEl" class="preview-video" muted playsinline />
      <video v-if="!cameraOn && objectUrl && showFilePreview" :src="objectUrl" class="preview-video" controls />
      <div v-if="!cameraOn && !objectUrl" class="preview-empty">
        {{ $t("打开摄像头录制，或直接选择一段已有的视频文件") }}
      </div>
    </div>

    <p v-if="guided" role="status" class="capture-status">{{ $t(opening ? '正在打开摄像头，请允许浏览器访问。' : stopping ? '正在保存录制视频…' : recording ? '正在录制：先保持自然表情，再做一次表情，最后恢复自然。' : cameraOn ? '摄像头已打开，点击开始录制；建议录制 8–15 秒。' : hasClip ? '录制已完成，请确认下方片段后开始分析。' : '打开摄像头后，点击开始录制。也可选择已有视频。') }}</p>
    <div class="capture-actions" :class="{'guided-actions':guided}">
      <el-button v-if="opening" @click="closeCamera">{{ $t('取消打开') }}</el-button>
      <template v-if="!cameraOn">
        <el-button
          v-if="cameraAvailable && !opening"
          :type="guided ? 'primary' : 'default'"
          :icon="VideoCamera"
          :disabled="disabled"
          @click="openCamera()"
        >
          {{ $t("打开摄像头") }}
        </el-button>
        <label class="file-label">
          <input ref="fileInput" type="file" accept="video/*" :disabled="disabled" @change="onFilePicked" />
          <el-button
            :icon="Upload"
            :type="cameraAvailable ? 'default' : 'primary'"
            :disabled="disabled"
            @click="fileInput?.click()"
          >
            {{ $t(cameraAvailable ? '选择视频文件' : '选择视频文件（推荐）') }}
          </el-button>
        </label>
      </template>

      <template v-else>
        <el-button
          v-if="!recording"
          :loading="opening || stopping"
          type="primary"
          :icon="VideoPlay"
          :disabled="disabled || opening || stopping"
          @click="startRecording"
        >
          {{ $t(guided ? "开始录制检查" : "开始录制") }}
        </el-button>
        <el-button v-else type="danger" @click="stopRecording">{{ $t(guided ? "结束录制并继续" : "停止录制") }}（{{ seconds.toFixed(1) }} s）</el-button>
        <!--
          Only offered when a second camera actually exists: a switch that does
          nothing is worse than no switch.
        -->
        <el-button v-if="canSwitchCamera && !recording && !stopping && !opening" @click="switchCamera">
          {{ $t("切换前后摄像头") }}
        </el-button>
        <el-button :disabled="recording || stopping" @click="closeCamera">{{ $t("关闭摄像头") }}</el-button>
      </template>

      <el-button v-if="hasClip" :disabled="disabled || recording || stopping" @click="retake">
        {{ $t("重新采集") }}
      </el-button>
    </div>

    <p v-if="hint" class="pd-muted capture-hint">{{ $t(hint) }}</p>
  </div>
</template>

<style scoped>
.capture-status{line-height:1.6;color:var(--pd-text-primary,#26384a)}
.guided-actions > .el-button:first-of-type{min-height:48px;flex:1 0 100%;margin-left:0}

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

.capture-hint {
  font-size: 13px;
  margin: 8px 0 0;
}

/*
  Patient-facing capture controls.

  Stacked and full width on a phone: "停止录制" next to "关闭摄像头" at half width
  each is two adjacent controls a shaky hand can confuse, and the gap between
  destructive and benign actions is part of the design, not decoration.
*/
@media (max-width: 767px) {
  .capture-actions {
    flex-direction: column;
    gap: 12px;
  }

  .capture-actions .el-button,
  .capture-actions .file-label,
  .capture-actions .file-label .el-button {
    width: 100%;
    min-height: var(--pd-touch-large);
    margin-left: 0;
  }

  .preview {
    /* Portrait phone: a 16:9 box wastes most of the screen. */
    aspect-ratio: 3 / 4;
  }
}

.file-label input {
  display: none;
}
</style>
