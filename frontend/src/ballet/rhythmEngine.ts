/**
 * The rhythm clock: schedules the click and the accompaniment, and reports beats.
 *
 * SEPARATE FROM ./rhythm.ts ON PURPOSE
 * ===================================
 * Everything in this file needs Web Audio and a browser. Keeping it out of
 * ./rhythm.ts lets the pure counting logic there be tested under Node, where
 * there is no AudioContext -- the same split the piano tempo module uses. The
 * test project has no DOM lib, so a DOM reference in the tested module would not
 * even type-check.
 *
 * COUNTING IS NOT setInterval
 * ===========================
 * Counting beats with setInterval drifts, and drift is the one thing a metronome
 * cannot have. Every beat's time is computed from the AudioContext clock and
 * scheduled ahead; a slow UI timer only tops up the schedule. The visual count in
 * BalletRhythmPanel reads the same beats, so what is heard and what is seen
 * cannot diverge.
 *
 * NO COPYRIGHTED MUSIC
 * ====================
 * Every note is synthesised from oscillators. There is no audio file, no sample
 * library and nothing to license.
 */

import {
  accompanimentMidi,
  clampTempo,
  isAccent,
  midiToFrequency,
  secondsPerBeat,
} from './rhythm'


export interface RhythmBeat {
  /** Monotonic beat counter since start. */
  index: number
  /** AudioContext time the beat sounds at. */
  time: number
}

export interface RhythmStatus {
  running: boolean
  /** Beat currently sounding, or null before the first beat. */
  beat: number | null
  bpm: number
}

export interface RhythmOptions {
  bpm: number
  beatsPerBar?: number
  /** Play the synthesised accompaniment under the click. */
  accompany?: boolean
  /** Called on every scheduled beat, from the audio scheduler. */
  onBeat?: (beat: RhythmBeat) => void
}

/** How far ahead beats are scheduled. Long enough to survive a busy frame. */
const SCHEDULE_AHEAD_SEC = 0.25
const SCHEDULER_INTERVAL_MS = 60
/** Click length. Short, so it reads as a metronome rather than a tone. */
const CLICK_SEC = 0.035
const NOTE_SEC = 0.9

export class RhythmEngine {
  private context: AudioContext | null = null
  private master: GainNode | null = null
  private workers: OscillatorNode[] = []
  private timer: number | null = null
  private nextBeatTime = 0
  private beatIndex = 0
  private options: Required<Pick<RhythmOptions, 'bpm' | 'beatsPerBar' | 'accompany'>> &
    Pick<RhythmOptions, 'onBeat'> = { bpm: 60, beatsPerBar: 4, accompany: true }

  get running(): boolean {
    return this.timer !== null
  }

  private ensureContext(): AudioContext {
    if (!this.context) {
      const Ctor: typeof AudioContext =
        window.AudioContext ??
        (window as unknown as { webkitAudioContext: typeof AudioContext }).webkitAudioContext
      this.context = new Ctor()
      this.master = this.context.createGain()
      this.master.gain.value = 0.9
      this.master.connect(this.context.destination)
    }
    return this.context
  }

  /** Must be called from a real user gesture. */
  async unlock(): Promise<boolean> {
    const context = this.ensureContext()
    if (context.state === 'suspended') await context.resume()
    return context.state === 'running'
  }

  start(options: RhythmOptions): void {
    if (this.running) this.stop()
    const context = this.ensureContext()
    this.options = {
      bpm: clampTempo(options.bpm),
      beatsPerBar: options.beatsPerBar ?? 4,
      accompany: options.accompany ?? true,
      onBeat: options.onBeat,
    }
    // Start slightly in the future so the first beat is scheduled, not late.
    this.nextBeatTime = context.currentTime + 0.12
    this.beatIndex = 0
    this.timer = window.setInterval(() => this.schedule(), SCHEDULER_INTERVAL_MS)
    this.schedule()
  }

  /** Change tempo without losing the count. */
  setTempo(bpm: number): void {
    this.options.bpm = clampTempo(bpm)
  }

  stop(): void {
    if (this.timer !== null) {
      window.clearInterval(this.timer)
      this.timer = null
    }
    for (const worker of this.workers) {
      try {
        worker.stop()
      } catch {
        // Already stopped; nothing to do.
      }
    }
    this.workers = []
  }

  dispose(): void {
    this.stop()
    void this.context?.close()
    this.context = null
    this.master = null
  }

  private schedule(): void {
    const context = this.context
    if (!context) return
    const horizon = context.currentTime + SCHEDULE_AHEAD_SEC
    while (this.nextBeatTime < horizon) {
      const index = this.beatIndex
      const accent = isAccent(index, this.options.beatsPerBar)
      this.click(this.nextBeatTime, accent)
      if (this.options.accompany) {
        this.note(this.nextBeatTime, accompanimentMidi(index, this.options.beatsPerBar), accent)
      }
      this.options.onBeat?.({ index, time: this.nextBeatTime })
      this.beatIndex += 1
      this.nextBeatTime += secondsPerBeat(this.options.bpm)
    }
  }

  /** A short filtered blip: the count the patient follows. */
  private click(time: number, accent: boolean): void {
    const context = this.ensureContext()
    const osc = context.createOscillator()
    const gain = context.createGain()
    osc.type = 'square'
    osc.frequency.value = accent ? 1600 : 1100
    gain.gain.setValueAtTime(0.0001, time)
    gain.gain.exponentialRampToValueAtTime(accent ? 0.22 : 0.12, time + 0.002)
    gain.gain.exponentialRampToValueAtTime(0.0001, time + CLICK_SEC)
    osc.connect(gain).connect(this.master as GainNode)
    osc.start(time)
    osc.stop(time + CLICK_SEC + 0.01)
    this.workers.push(osc)
    // Keep the list bounded; a long session would otherwise grow it forever.
    if (this.workers.length > 64) this.workers.splice(0, 32)
  }

  /**
   * A struck-string approximation: a triangle fundamental with a fast decay.
   *
   * Plain on purpose. The point is a pitch and a pulse the patient can follow,
   * not a convincing instrument.
   */
  private note(time: number, midi: number, accent: boolean): void {
    const context = this.ensureContext()
    const freq = midiToFrequency(midi)

    const osc = context.createOscillator()
    osc.type = 'triangle'
    osc.frequency.value = freq

    const gain = context.createGain()
    const peak = accent ? 0.16 : 0.09
    gain.gain.setValueAtTime(0.0001, time)
    gain.gain.exponentialRampToValueAtTime(peak, time + 0.012)
    gain.gain.exponentialRampToValueAtTime(0.0001, time + NOTE_SEC)

    // A quiet octave above gives the note some body without a second voice.
    const shimmer = context.createOscillator()
    shimmer.type = 'sine'
    shimmer.frequency.value = freq * 2
    const shimmerGain = context.createGain()
    shimmerGain.gain.setValueAtTime(0.0001, time)
    shimmerGain.gain.exponentialRampToValueAtTime(peak * 0.25, time + 0.012)
    shimmerGain.gain.exponentialRampToValueAtTime(0.0001, time + NOTE_SEC * 0.6)

    osc.connect(gain).connect(this.master as GainNode)
    shimmer.connect(shimmerGain).connect(this.master as GainNode)
    osc.start(time)
    shimmer.start(time)
    osc.stop(time + NOTE_SEC + 0.02)
    shimmer.stop(time + NOTE_SEC + 0.02)
    this.workers.push(osc, shimmer)
    if (this.workers.length > 64) this.workers.splice(0, 32)
  }
}
