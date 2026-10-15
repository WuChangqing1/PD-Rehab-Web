import { onBeforeUnmount, ref, shallowRef } from 'vue'
import { API_BASE, TOKEN_STORAGE_KEY } from '@/api/client'
import { EmotionStreamClient } from './streamClient'
import type { EmotionResult, LiveEmotionStatus } from './types'
import { validDistribution, EMOTION_LABELS } from './types'

export function useLiveEmotion() {
  const status = ref<LiveEmotionStatus>('IDLE')
  const consent = ref(false)
  const statistics = ref({results:0,low_quality:0,last_latency_ms:null as number|null})
  const summary = shallowRef<EmotionResult|null>(null)
  let stream:MediaStream|null = null
  let recorder:MediaRecorder|null = null
  let client:EmotionStreamClient|null = null
  let generation = 0
  function release() {
    if (recorder && recorder.state !== 'inactive') recorder.stop()
    recorder = null
    stream?.getTracks().forEach(track => track.stop())
    stream = null
    client?.close()
    client = null
  }
  function stop() { generation++; release(); status.value = 'STOPPED' }
  function unavailable() { generation++; release(); status.value = 'UNAVAILABLE' }
  async function start(sessionId:string,patientId:string,simulationDemo=false) {
    stop()
    summary.value = null
    statistics.value={results:0,low_quality:0,last_latency_ms:null}
    if (!consent.value) { status.value = 'CONSENT_REQUIRED'; return }
    const run = generation
    status.value = 'CONNECTING'
    client = new EmotionStreamClient()
    client.onFailure = unavailable
    client.onMessage = async data => {
      if (run !== generation) return
      if (data.type === 'result' && data.source === 'MODEL' && JSON.stringify(data.labels) === JSON.stringify(EMOTION_LABELS)) {
        if (data.probabilities === null || validDistribution(data.probabilities)) {
          summary.value = data as unknown as EmotionResult
          statistics.value={results:statistics.value.results+1,low_quality:statistics.value.low_quality+(data.quality==='GOOD'?0:1),last_latency_ms:typeof data.inference_latency_ms==='number'?data.inference_latency_ms:null}
        }
        return
      }
      if (data.type === 'result' && data.source === 'SIMULATED' && simulationDemo && validDistribution(data.probabilities)) {
        summary.value = data as unknown as EmotionResult
        status.value = 'SIMULATED'
        release()
        return
      }
      if (data.status === 'MODEL_NOT_CONFIGURED') {
        status.value = 'MODEL_NOT_CONFIGURED'
        release()
        return
      }
      // Only a verified temporal adapter with explicit requirements can return
      // READY; the default unconfigured adapter never requests acquisition.
      if (data.status !== 'READY' || data.capture_required !== true || data.protocol !== 'continuous-mediarecorder-v1') return
      try {
        if (!globalThis.isSecureContext || !navigator.mediaDevices || !globalThis.MediaRecorder) throw new Error('CAMERA_UNAVAILABLE')
        const acquired = await navigator.mediaDevices.getUserMedia({video:{facingMode:'user',frameRate:{ideal:Number((data.requirements as Record<string,unknown>)?.fps)||30},width:{ideal:Number((data.requirements as Record<string,unknown>)?.width)||640},height:{ideal:Number((data.requirements as Record<string,unknown>)?.height)||480}},audio:false})
        if (run !== generation || !consent.value) { acquired.getTracks().forEach(t => t.stop()); return }
        stream = acquired
        const mimeType = ['video/webm;codecs=vp8','video/webm','video/mp4'].find(t => MediaRecorder.isTypeSupported(t))
        if (!mimeType) throw new Error('ENCODING_UNAVAILABLE')
        recorder = new MediaRecorder(stream,{mimeType,videoBitsPerSecond:500000})
        let last = Date.now()
        recorder.ondataavailable = event => {
          if (run !== generation || !event.data.size) return
          const now = Date.now()
          // A dropped container fragment invalidates continuity: stop instead
          // of buffering indefinitely or passing corrupted temporal input.
          if (!client?.sendChunk(event.data,last,now-last)) unavailable()
          last = now
        }
        recorder.onerror = unavailable
        stream.getTracks().forEach(t => { t.onended = unavailable })
        recorder.start(1000)
        status.value = 'STREAMING'
      } catch { if (run === generation) unavailable() }
    }
    const url = new URL(`${API_BASE}/live-emotion/stream`,window.location.origin)
    url.protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:'
    try { client.connect(url.toString(),localStorage.getItem(TOKEN_STORAGE_KEY) || '',sessionId,patientId,simulationDemo) }
    catch { unavailable() }
  }
  const visibility = () => { if (document.hidden) stop() }
  if (typeof document !== 'undefined') document.addEventListener('visibilitychange',visibility)
  onBeforeUnmount(() => { stop(); document.removeEventListener('visibilitychange',visibility) })
  return { status, consent, summary, statistics, start, stop }
}
