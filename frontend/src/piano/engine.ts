/**
 * Piano audio engine.
 *
 * WHY WEB AUDIO AND NOT <audio> ELEMENTS
 * =====================================
 * The reference implementation calls `audio.currentTime = 0; audio.play()` on
 * one HTMLAudioElement per key. That has no sample-accurate start: the actual
 * sounding moment depends on decoder state and is typically tens of
 * milliseconds late and variable. This project measures Response Latency and
 * Timing Error, so the audio path must not be the largest source of error.
 *
 * Here every note is decoded once into an AudioBuffer, and playback uses
 * `AudioBufferSourceNode.start(when)` against the AudioContext clock, which is
 * sample accurate. A note can therefore be scheduled in advance for exact
 * playback at a target time.
 *
 * TIMING MODEL
 * ============
 * Two clocks are involved and they are reconciled once, explicitly:
 *   - performance.now(): a monotonic millisecond clock, used for all recorded
 *     event timestamps.
 *   - AudioContext.currentTime: seconds since the context was created.
 * `audioTimeToPerformance()` is the only place that converts between them, and
 * the offset is captured on first use and kept.
 *
 * MEASUREMENT CAVEAT (recorded on purpose)
 * ========================================
 * The user's key press is timestamped with the DOM event's timeStamp / 
 * performance.now(). That is the moment the *browser* processed the event, which
 * already includes some operating system and browser input latency (typically
 * on the order of a few to ~20 ms). The system therefore does not claim to
 * measure the physical finger movement time; `input_latency_note` is stored with
 * each session so the number is interpreted correctly.
 */

import { SAMPLE_BASE, sampleFor, type PianoSample } from '@/piano/samples'

export interface EngineStatus {
  ready: boolean
  loaded: number
  total: number
  failed: string[]
  contextState: string
  sampleRate: number
}

export interface ScheduledNote {
  midi: number
  /** Time on the AudioContext clock at which the sample starts. */
  audioTime: number
  /** Corresponding performance.now() value, for display and logging. */
  performanceTime: number
  gain: GainNode
  source: AudioBufferSourceNode
}

const ATTACK_SEC = 0.004
const RELEASE_SEC = 0.25
const MIN_GAIN = 1e-4

export class PianoEngine {
  private context: AudioContext | null = null
  private master: GainNode | null = null
  private buffers = new Map<number, AudioBuffer>()
  private failed: string[] = []
  private loading: Promise<void> | null = null
  private clockOffsetMs: number | null = null

  private totalSamples = 0
  private loadedSamples = 0

  /** Volume for the master output, 0..1. */
  volume = 0.6

  status(): EngineStatus {
    return {
      ready: this.buffers.size > 0 && this.context !== null,
      loaded: this.loadedSamples,
      total: this.totalSamples,
      failed: [...this.failed],
      contextState: this.context?.state ?? 'closed',
      sampleRate: this.context?.sampleRate ?? 0,
    }
  }

  ensureContext(): AudioContext {
    if (this.context) return this.context
    const Ctor: typeof AudioContext =
      window.AudioContext ??
      (window as unknown as { webkitAudioContext: typeof AudioContext }).webkitAudioContext
    if (!Ctor) {
      throw new Error('当前浏览器不支持 Web Audio API，无法进行钢琴训练。')
    }
    this.context = new Ctor()
    this.master = this.context.createGain()
    this.master.gain.value = this.volume
    this.master.connect(this.context.destination)
    return this.context
  }

  /**
   * Browsers require a user gesture before audio may start. Call this from a
   * click handler before anything else.
   */
  async unlock(): Promise<void> {
    const context = this.ensureContext()
    if (context.state === 'suspended') {
      await context.resume()
    }
  }

  /** Decode every sample once. Safe to call repeatedly; decoding happens once. */
  async load(): Promise<void> {
    if (this.loading) return this.loading
    const context = this.ensureContext()

    const entries = Object.values(
      Object.fromEntries(
        Array.from({ length: 24 }, (_, i) => {
          const midi = 48 + i
          const sample = sampleFor(midi)
          return sample ? [midi, sample] : null
        }).filter((x): x is [number, PianoSample] => x !== null),
      ),
    )

    // Unique files only: two notes share a source file.
    const files = [...new Set(entries.map((sample) => sample.file))]
    this.totalSamples = files.length
    this.loadedSamples = 0
    this.failed = []

    this.loading = (async () => {
      await Promise.all(
        files.map(async (file) => {
          try {
            const response = await fetch(`${SAMPLE_BASE}${file}`)
            if (!response.ok) {
              throw new Error(`HTTP ${response.status}`)
            }
            const bytes = await response.arrayBuffer()
            const buffer = await context.decodeAudioData(bytes)
            // Map every note that uses this file.
            for (const sample of entries) {
              if (sample.file === file) this.buffers.set(sample.midi, buffer)
            }
            this.loadedSamples += 1
          } catch (error) {
            this.failed.push(`${file}: ${error instanceof Error ? error.message : String(error)}`)
          }
        }),
      )
    })()

    return this.loading
  }

  /** True when the given note has a decoded buffer. */
  has(midi: number): boolean {
    return this.buffers.has(midi)
  }

  /** performance.now() equivalent of an AudioContext timestamp. */
  audioTimeToPerformance(audioTime: number): number {
    const context = this.context
    if (!context) return performance.now()
    const nowAudio = context.currentTime
    const nowPerf = performance.now()
    return nowPerf + (audioTime - nowAudio) * 1000
  }

  /** AudioContext timestamp corresponding to a performance.now() value. */
  performanceToAudioTime(perfTime: number): number {
    const context = this.context
    if (!context) return 0
    const nowAudio = context.currentTime
    const nowPerf = performance.now()
    if (this.clockOffsetMs === null) {
      this.clockOffsetMs = nowPerf - nowAudio * 1000
    }
    return (perfTime - this.clockOffsetMs) / 1000
  }

  /**
   * Play a note immediately.
   *
   * @param midi note to play
   * @param whenPerf performance.now() time at which the sound should start.
   *                 Defaults to now. Values in the past are clamped, since the
   *                 audio clock cannot schedule backwards.
   */
  play(midi: number, whenPerf?: number, velocity = 1): ScheduledNote | null {
    const context = this.ensureContext()
    const buffer = this.buffers.get(midi)
    if (!buffer || !this.master) return null

    const sample = sampleFor(midi)
    const targetPerf = whenPerf ?? performance.now()
    const requestedAudio = this.performanceToAudioTime(targetPerf)
    // Give the graph a small lead so start() is never in the past.
    const earliest = context.currentTime + 0.002
    const audioTime = Math.max(requestedAudio, earliest)

    const source = context.createBufferSource()
    source.buffer = buffer
    if (sample && sample.playbackRate !== 1) {
      source.playbackRate.value = sample.playbackRate
    }

    const gain = context.createGain()
    const level = Math.max(MIN_GAIN, Math.min(1, velocity))
    gain.gain.setValueAtTime(MIN_GAIN, audioTime)
    gain.gain.linearRampToValueAtTime(level, audioTime + ATTACK_SEC)
    gain.gain.setTargetAtTime(MIN_GAIN, audioTime + ATTACK_SEC, RELEASE_SEC)

    source.connect(gain)
    gain.connect(this.master)
    source.start(audioTime)
    // Stop after the sample would have finished anyway; frees the node.
    source.stop(audioTime + buffer.duration / (sample?.playbackRate ?? 1) + 0.05)

    return {
      midi,
      audioTime,
      performanceTime: this.audioTimeToPerformance(audioTime),
      gain,
      source,
    }
  }

  /** Short metronome-style click, used for the count-in and beat mode. */
  click(whenPerf?: number, accent = false): void {
    const context = this.ensureContext()
    if (!this.master) return
    const targetPerf = whenPerf ?? performance.now()
    const earliest = context.currentTime + 0.002
    const audioTime = Math.max(this.performanceToAudioTime(targetPerf), earliest)

    const osc = context.createOscillator()
    const gain = context.createGain()
    osc.frequency.value = accent ? 1600 : 1100
    const level = accent ? 0.5 : 0.3
    gain.gain.setValueAtTime(MIN_GAIN, audioTime)
    gain.gain.linearRampToValueAtTime(level, audioTime + 0.001)
    gain.gain.exponentialRampToValueAtTime(MIN_GAIN, audioTime + 0.06)
    osc.connect(gain)
    gain.connect(this.master)
    osc.start(audioTime)
    osc.stop(audioTime + 0.08)
  }

  setVolume(value: number): void {
    this.volume = Math.max(0, Math.min(1, value))
    if (this.master) this.master.gain.value = this.volume
  }

  async close(): Promise<void> {
    if (this.context) {
      await this.context.close()
    }
    this.context = null
    this.master = null
    this.buffers.clear()
    this.loading = null
    this.clockOffsetMs = null
  }
}

/** One engine per page; the AudioContext is expensive to create. */
let shared: PianoEngine | null = null

export function getPianoEngine(): PianoEngine {
  if (!shared) shared = new PianoEngine()
  return shared
}

/** Stored with each session so latency numbers are read correctly. */
export const INPUT_LATENCY_NOTE =
  '事件时间戳取自 DOM 事件（event.timeStamp / performance.now()），' +
  '已包含操作系统与浏览器输入延迟（通常数毫秒至约 20 毫秒），' +
  '不是手指物理运动时间；系统不对该延迟做补偿。'
