/// <reference lib="dom" />
import type { RawSongEvent } from './machine.ts'
import { sampleFor } from '../samples.ts'
export const AUDIO_SOURCE = 'SYNTHESIZED_FROM_KEY_EVENTS' as const
export const RENDER_VERSION = '1'
const TRANSITION_MS = 150
const RELEASE_MS = 250
// A mono float render + PCM WAV stays below ~85 MB at this limit.
export const MAX_RENDER_DURATION_MS = 300000
export interface PerformanceTone { midi: number; start_ms: number; duration_ms: number }
export function buildPerformanceTimeline(events: readonly RawSongEvent[]) {
  const notes: PerformanceTone[] = []
  let offset = 0
  for (const segment of [1,2] as const) {
    const segmentEvents = events.filter(e=>e.segment_index === segment)
    const cue = segmentEvents.find(e=>e.type === 'CUE')
    if (!cue) continue
    const held = new Map<string, RawSongEvent>()
    let end = cue.time_ms
    for (const event of segmentEvents) {
      end = Math.max(end,event.time_ms)
      if (event.type === 'DOWN' && event.press_id && event.midi !== undefined) {
        if (held.has(event.press_id)) throw new Error('重复按下事件')
        held.set(event.press_id,event)
      }
      if (event.type === 'UP' && event.press_id) {
        const down = held.get(event.press_id)
        if (!down || event.midi !== down.midi || event.time_ms < down.time_ms) throw new Error('按键释放事件不匹配')
        notes.push({midi:down.midi!,start_ms:offset+down.time_ms-cue.time_ms,duration_ms:event.time_ms-down.time_ms})
        held.delete(event.press_id)
      }
    }
    if (held.size) throw new Error('请释放所有琴键后重新生成音频')
    offset += end-cue.time_ms+TRANSITION_MS
  }
  const duration_ms = Math.max(1,offset ? offset-TRANSITION_MS+RELEASE_MS : RELEASE_MS)
  if (!Number.isFinite(duration_ms) || duration_ms > MAX_RENDER_DURATION_MS) throw new Error('演奏音频超过五分钟内存限制，原始训练记录仍可保存')
  return {notes:notes.sort((a,b)=>a.start_ms-b.start_ms),duration_ms}
}
export async function renderPerformanceAudio(events: readonly RawSongEvent[], getBuffer: (midi: number)=>AudioBuffer | undefined) {
  const timeline = buildPerformanceTimeline(events)
  const sampleRate = 44100
  const context = new OfflineAudioContext(1,Math.ceil(timeline.duration_ms*sampleRate/1000),sampleRate)
  for (const tone of timeline.notes) {
    const buffer = getBuffer(tone.midi)
    if (!buffer) throw new Error('钢琴音源尚未准备完成，请重新加载后重试')
    const source = context.createBufferSource(); source.buffer = buffer
    source.playbackRate.value = sampleFor(tone.midi)?.playbackRate ?? 1
    const gain = context.createGain()
    const start = tone.start_ms/1000
    const release = start+tone.duration_ms/1000
    gain.gain.setValueAtTime(0,start)
    gain.gain.linearRampToValueAtTime(0.35,start+Math.min(.004,tone.duration_ms/1000))
    gain.gain.setValueAtTime(0.35,release)
    gain.gain.linearRampToValueAtTime(0,release+RELEASE_MS/1000)
    source.connect(gain); gain.connect(context.destination)
    source.start(start); source.stop(release+RELEASE_MS/1000)
  }
  const rendered = await context.startRendering()
  const pcm = rendered.getChannelData(0)
  const bytes = new ArrayBuffer(44+pcm.length*2); const view = new DataView(bytes)
  const word = (offset:number,value:string)=>{for(let i=0;i<value.length;i++)view.setUint8(offset+i,value.charCodeAt(i))}
  word(0,'RIFF');view.setUint32(4,36+pcm.length*2,true);word(8,'WAVE');word(12,'fmt ')
  view.setUint32(16,16,true);view.setUint16(20,1,true);view.setUint16(22,1,true)
  view.setUint32(24,sampleRate,true);view.setUint32(28,sampleRate*2,true);view.setUint16(32,2,true);view.setUint16(34,16,true)
  word(36,'data');view.setUint32(40,pcm.length*2,true)
  let peak=1
  for(const value of pcm) peak=Math.max(peak,Math.abs(value))
  for(let i=0;i<pcm.length;i++) {const value=pcm[i]!/peak;view.setInt16(44+i*2,Math.round(value*(value<0?32768:32767)),true)}
  return {blob:new Blob([bytes],{type:'audio/wav'}),duration_ms:Math.ceil(rendered.duration*1000),audio_source:AUDIO_SOURCE,render_version:RENDER_VERSION,audio_format:'wav' as const}
}
