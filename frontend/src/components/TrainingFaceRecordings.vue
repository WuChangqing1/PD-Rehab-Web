<script setup lang="ts">
import {onUnmounted, ref, watch} from 'vue'
import {ElMessageBox} from 'element-plus'
import {API_BASE, http, notifyError} from '@/api/client'

const props = defineProps<{recordId: string}>()
type Candidate = {id: string; onset_frame: number; apex_frame: number; offset_frame: number}
type Segment = {id: string; status: string; start_seconds: number; file_id: string; candidates?: Candidate[]}
type VideoFile = {file_id: string; sequence: number; duration_ms: number}
type Recording = {recording_id: string; status: string; summary: string; expires_at: string; upload_complete: boolean; media_deleted: boolean; video_files?: VideoFile[]; results: Array<Record<string, unknown>>}
const statusLabels: Record<string, string> = {
  UPLOADING: '上传中', PROCESSING: '定位片段中', REVIEW_REQUIRED: '待复核', PENDING: '等待分析',
  RUNNING: '分析中', SUCCESS: '已完成', PARTIAL_SUCCESS: '部分完成', NO_VALID_SEGMENTS: '无有效片段',
  REJECTED: '已拒绝', FAILED: '处理失败', CANCELLED: '已取消', DELETED: '已删除', NEW: '待处理',
}
const recordings = ref<Recording[]>([]), segments = ref<Segment[]>([])
const busy = ref(false), error = ref(''), selected = ref('')
const previews = ref<string[]>([]), previewKey = ref('')
let epoch = 0
let playerEpoch = 0
let renewal: ReturnType<typeof setInterval> | undefined
const playing = ref<{recording: string; file: string; url: string} | null>(null)
const playerError = ref('')
const downloading = ref(false)

function playbackPath(row: Recording, file: VideoFile) {
  return `/integration/v1/face/recordings/${row.recording_id}/files/${file.file_id}/playback`
}

async function downloadVideo(row: Recording, file: VideoFile) {
  if (downloading.value) return
  const version = epoch
  const path = playbackPath(row, file)
  downloading.value = true
  playerError.value = ''
  try {
    await http.post(path)
    if (version !== epoch) return
    const link = document.createElement('a')
    link.href = API_BASE + path + '?download=true'
    link.download = ''
    document.body.appendChild(link)
    try { link.click() } finally { link.remove() }
  } catch {
    if (version === epoch) playerError.value = '无法下载录像，请刷新后重试。'
  } finally {
    downloading.value = false
  }
}

function closePlayer() {
  playerEpoch++
  clearInterval(renewal)
  renewal = undefined
  playing.value = null
  playerError.value = ''
}

async function openPlayer(row: Recording, file: VideoFile) {
  closePlayer()
  const version = playerEpoch
  const path = playbackPath(row, file)
  try {
    await http.post(path)
    if (version !== playerEpoch) return
    playing.value = {recording: row.recording_id, file: file.file_id, url: API_BASE + path}
    renewal = setInterval(async () => {
      try { await http.post(path) }
      catch {
        if (version !== playerEpoch) return
        closePlayer()
        playerError.value = '播放授权已失效，请重新打开录像。'
      }
    }, 90_000)
  } catch {
    if (version === playerEpoch) playerError.value = '无法打开录像，请刷新后重试。'
  }
}
function clearPreview() { previews.value.forEach(URL.revokeObjectURL); previews.value = []; previewKey.value = '' }
function reset() { epoch++; closePlayer(); clearPreview(); recordings.value = []; segments.value = []; selected.value = ''; error.value = ''; busy.value = false }
async function load() {
  const version = ++epoch, id = props.recordId
  closePlayer(); clearPreview(); selected.value = ''; segments.value = []; busy.value = true; error.value = ''
  try {
    const {data} = await http.get<{items: Recording[]}>('/integration/v1/face/recordings', {params: {external_record_id: id}})
    if (version !== epoch) return
    recordings.value = data.items
  } catch (e) { if (version === epoch) error.value = '面部录像读取失败，请刷新重试。' }
  finally { if (version === epoch) busy.value = false }
}
async function show(row: Recording) {
  const version = ++epoch; clearPreview(); segments.value = []; selected.value = row.recording_id; busy.value = true
  try {
    let offset: number | null = 0
    const items: Segment[] = []
    while (offset !== null) {
      const {data}: {data: {items: Segment[]; next_offset: number | null}} = await http.get(`/integration/v1/face/recordings/${row.recording_id}/segments`, {params: {offset}})
      if (version !== epoch) return
      items.push(...data.items); offset = data.next_offset
    }
    segments.value = items
  } catch (e) { if (version === epoch) notifyError(e) }
  finally { if (version === epoch) busy.value = false }
}
async function preview(segment: Segment, candidate: Candidate) {
  const version = ++epoch; clearPreview(); busy.value = true
  const urls: string[] = []
  try {
    for (const which of ['onset', 'apex', 'offset']) {
      const {data} = await http.get<Blob>(`/integration/v1/face/recordings/${selected.value}/segments/${segment.id}/frames/${which}`, {
        params: {candidate_id: candidate.id}, responseType: 'blob',
      })
      urls.push(URL.createObjectURL(data))
    }
    if (version !== epoch) { urls.forEach(URL.revokeObjectURL); return }
    previews.value = urls; previewKey.value = `${segment.id}/${candidate.id}`
  } catch (e) { urls.forEach(URL.revokeObjectURL); if (version === epoch) notifyError(e) }
  finally { if (version === epoch) busy.value = false }
}
async function review(segment: Segment, candidate?: Candidate) {
  const version = epoch, recordingId = selected.value
  busy.value = true
  try {
    await http.post(`/integration/v1/face/recordings/${recordingId}/segments/${segment.id}/review`, {
      candidate_id: candidate?.id, review_confirmed: !!candidate, reject: !candidate,
    })
    if (version !== epoch) return
    clearPreview(); segment.status = candidate ? 'PENDING' : 'REJECTED'
  } catch (e) { if (version === epoch) notifyError(e) }
  finally { if (version === epoch) busy.value = false }
}
async function changeRecording(row: Recording, action: 'delete' | 'retry') {
  const version = epoch
  if (action === 'delete') {
    try {
      await ElMessageBox.confirm('将删除该录像及其分析结果，原训练成绩会保留。', '删除录像', {type: 'warning'})
    } catch { return }
    if (version !== epoch) return
  }
  const path = `/integration/v1/face/recordings/${row.recording_id}`
  busy.value = true
  try {
    if (action === 'delete') await http.delete(path)
    else await http.post(path + '/retry')
    if (version === epoch) await load()
  } catch (e) { if (version === epoch) notifyError(e) }
  finally { if (version === epoch) busy.value = false }
}
watch(() => props.recordId, () => { reset(); void load() }, {immediate: true})
onUnmounted(reset)
</script>

<template>
  <section class="training-face">
    <header><h3>训练面部录像</h3><el-button :loading="busy" @click="load">刷新</el-button></header>
    <p v-if="error" role="alert">{{error}}</p>
    <p v-else-if="!busy && !recordings.length">本条训练暂无面部录像。</p>
    <p v-if="playerError" role="alert">{{playerError}}</p>
    <article v-for="row in recordings" :key="row.recording_id" class="pd-card recording">
      <p>{{statusLabels[row.status] || row.status}} · {{row.summary}}</p>
      <p v-if="row.media_deleted">录像素材已清理。</p>
      <p v-else>素材有效期至 {{new Date(row.expires_at).toLocaleString()}}。片段输出不代表病情或真实情绪。</p>
      <el-button :disabled="busy" @click="show(row)">查看片段与复核</el-button>
      <el-button v-if="!row.media_deleted && row.upload_complete && ['FAILED','PARTIAL_SUCCESS'].includes(row.status)" :disabled="busy" @click="changeRecording(row, 'retry')">重试分析</el-button>
      <el-button :disabled="busy" text type="danger" @click="changeRecording(row, 'delete')">删除录像</el-button>
      <div v-if="row.video_files?.length" class="video-controls">
        <div v-for="file in row.video_files" :key="file.file_id" class="video-file">
          <el-button :type="playing?.file === file.file_id ? 'primary' : 'default'" @click="openPlayer(row, file)">
            {{ row.video_files.length === 1 ? '播放完整录像' : `播放原视频 ${file.sequence + 1}` }}
          </el-button>
          <el-button :disabled="downloading || busy" @click="downloadVideo(row, file)">
            {{ row.video_files.length === 1 ? '下载视频' : `下载原视频 ${file.sequence + 1}` }}
          </el-button>
        </div>
        <template v-if="playing?.recording === row.recording_id">
          <el-button text @click="closePlayer">关闭播放器</el-button>
          <video :key="playing.file" :src="playing.url" controls controlslist="nodownload"
            playsinline preload="metadata" aria-label="训练面部录像"
            @error="playerError = '视频暂时无法播放，可能已失效或浏览器不支持此编码。'"></video>
        </template>
      </div>
      <template v-if="selected === row.recording_id">
        <article v-for="segment in segments" :key="segment.id" class="segment">
          <h4>原视频 {{segment.start_seconds.toFixed(1)}} 秒起 · {{statusLabels[segment.status] || segment.status}}</h4>
          <template v-if="segment.status === 'REVIEW_REQUIRED'">
            <div v-for="candidate in segment.candidates" :key="candidate.id" class="candidate">
              <el-button :disabled="busy" @click="preview(segment, candidate)">预览开始、峰值、结束</el-button>
              <div v-if="previewKey === `${segment.id}/${candidate.id}`" class="frames">
                <figure v-for="(image, index) in previews" :key="image">
                  <img :src="image" :alt="['开始','变化最明显','结束'][index]"><figcaption>{{['开始','变化最明显','结束'][index]}}</figcaption>
                </figure>
              </div>
              <el-button type="primary" :disabled="busy || previewKey !== `${segment.id}/${candidate.id}`" @click="review(segment, candidate)">确认此片段并分析</el-button>
            </div>
            <el-button :disabled="busy" @click="review(segment)">拒绝本段候选</el-button>
          </template>
        </article>
        <details v-if="row.results.length"><summary>查看已完成的模型输出</summary><pre>{{JSON.stringify(row.results, null, 2)}}</pre></details>
      </template>
    </article>
  </section>
</template>

<style scoped>
.training-face{margin:20px 0;min-width:0}.training-face header{display:flex;justify-content:space-between;align-items:center;gap:12px}
.recording,.segment{padding:16px;margin-top:12px;border:1px solid var(--el-border-color);border-radius:12px}.recording p{overflow-wrap:anywhere}
.candidate{margin:12px 0;display:flex;flex-wrap:wrap;gap:12px}.frames{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:8px;flex-basis:100%}.frames figure{margin:0}.frames img{width:100%;object-fit:contain;border-radius:8px}.frames figcaption{font-size:12px;text-align:center}.training-face pre{white-space:pre-wrap;overflow-wrap:anywhere}
.video-controls,.video-file{display:flex;flex-wrap:wrap;gap:8px}.video-controls{margin-top:12px}.video-controls .el-button{margin:0}.video-controls video{width:100%;max-height:440px;background:#101418;border-radius:8px}
</style>
