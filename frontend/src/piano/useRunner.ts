/**
 * Composable that runs one piano round.
 *
 * Responsibilities, kept out of the components so the timing logic is in one
 * place and testable:
 *   - build the cue stream and drive the visual/audio timeline
 *   - capture every key press with its timestamp, on the performance clock
 *   - resolve cues into raw events (wrong presses, correct presses, misses)
 *   - report live progress
 *
 * Timing is taken from `performance.now()` at the moment the browser delivers
 * the event. That value already includes OS and browser input latency, so the
 * recorded latencies are upper bounds on reaction time; the caveat is stored
 * with the session rather than compensated for.
 */

import { computed, onBeforeUnmount, ref, shallowRef } from 'vue'

import { getPianoEngine, INPUT_LATENCY_NOTE } from '@/piano/engine'
import { computeMetrics, type PianoMetrics } from '@/piano/metrics'
import {
  generateCues,
  resolveCue,
  strayEvent,
  type Cue,
  type DifficultyConfig,
  type PianoMode,
  type PianoRawEvent,
  type PressInput,
} from '@/piano/session'
import { BINDING_BY_CODE, type Hand, type KeyBinding } from '@/piano/samples'

export type RunnerState = 'IDLE' | 'COUNTDOWN' | 'RUNNING' | 'FINISHED'

export interface RunnerOptions {
  mode: PianoMode
  difficulty: DifficultyConfig
  seed: number
  weakHand: Hand | null
  /** Milliseconds of count-in before the first cue. */
  countInMs?: number
  /**
   * Extra time after the last cue with no cue at all.
   *
   * Used by calibration to measure the patient's own tempo: presses during the
   * tail are still recorded, they simply have nothing to be right or wrong
   * about. Without this the runner finished as soon as the last cue resolved.
   */
  tailMs?: number
}

export function usePianoRunner() {
  const engine = getPianoEngine()

  const state = ref<RunnerState>('IDLE')
  const cues = shallowRef<Cue[]>([])
  const events = ref<PianoRawEvent[]>([])
  const presses = ref<PressInput[]>([])
  const nowMs = ref(0)
  const countdownMs = ref(0)
  const activeCueIndex = ref<number | null>(null)
  const pressedKeys = ref<Set<number>>(new Set())
  const audioReady = ref(false)
  const audioError = ref<string | null>(null)
  /** True once the AudioContext has actually been resumed by a user gesture. */
  const unlocked = ref(false)
  const elapsedMs = ref(0)

  let options: RunnerOptions | null = null
  let startPerf = 0
  let rafHandle: number | null = null
  let resolvedUpTo = -1
  const downTimes = new Map<string, number>()
  /** Cue indices whose note has already been scheduled, so it sounds once. */
  const sounded = new Set<number>()

  const metrics = computed<PianoMetrics>(() =>
    computeMetrics(events.value, { plannedCues: cues.value.length }),
  )

  const progress = computed(() => {
    if (!cues.value.length) return 0
    const resolved = resolvedUpTo + 1
    return Math.min(1, resolved / cues.value.length)
  })

  /** The cue the patient should currently be responding to. */
  const currentCue = computed<Cue | null>(() => {
    const index = activeCueIndex.value
    return index === null ? null : (cues.value[index] ?? null)
  })

  /** Cues whose judgement window has not closed yet, for rendering. */
  const visibleCues = computed(() => {
    const window = options?.difficulty.judgement_window_ms ?? 300
    return cues.value.filter((cue) => {
      const end = cue.targetMs + window / 2
      const start = cue.cueOnsetMs
      return nowMs.value >= start - 100 && nowMs.value <= end
    })
  })

  async function prepare(): Promise<boolean> {
    try {
      await engine.unlock()
      await engine.load()
      const status = engine.status()
      audioReady.value = status.ready
      audioError.value = status.failed.length
        ? `部分音源加载失败：${status.failed.slice(0, 3).join('; ')}`
        : null
      return status.ready
    } catch (error) {
      audioError.value = error instanceof Error ? error.message : String(error)
      audioReady.value = false
      return false
    }
  }

  /**
   * Decode the samples without asking for a user gesture.
   *
   * `decodeAudioData` works while the context is still suspended, so the samples
   * can be ready before the patient touches anything. Only *starting* audio
   * needs a gesture, which `unlock()` handles.
   */
  async function warmUp(): Promise<void> {
    try {
      await engine.load()
      const status = engine.status()
      audioReady.value = status.ready
      audioError.value = status.failed.length
        ? `部分音源加载失败：${status.failed.slice(0, 3).join('; ')}`
        : null
    } catch (error) {
      audioError.value = error instanceof Error ? error.message : String(error)
    }
  }

  /** Resume the audio context. Must be called from a real user gesture. */
  async function unlock(): Promise<boolean> {
    try {
      await engine.unlock()
      unlocked.value = engine.status().contextState === 'running'
      return unlocked.value
    } catch {
      unlocked.value = false
      return false
    }
  }

  function start(opts: RunnerOptions) {
    options = opts
    cues.value = generateCues(opts.mode, opts.difficulty, {
      seed: opts.seed,
      weakHand: opts.weakHand,
    })
    events.value = []
    presses.value = []
    resolvedUpTo = -1
    downTimes.clear()
    sounded.clear()
    activeCueIndex.value = null
    pressedKeys.value = new Set()

    const totalMs = opts.difficulty.session_duration_sec * 1000
    const countIn = opts.countInMs ?? 0
    const tailMs = Math.max(0, opts.tailMs ?? 0)

    state.value = countIn > 0 ? 'COUNTDOWN' : 'RUNNING'
    countdownMs.value = countIn
    // Session time zero is the moment the first cue can appear.
    startPerf = performance.now() + countIn
    elapsedMs.value = 0

    // Count-in clicks on the beat.
    if (countIn > 0) {
      const beat = 60000 / Math.max(20, opts.difficulty.bpm)
      for (let t = countIn; t > 0; t -= beat) {
        engine.click(performance.now() + (countIn - t), t <= beat)
      }
    }

    const tick = () => {
      const elapsed = performance.now() - startPerf
      elapsedMs.value = elapsed
      countdownMs.value = Math.max(0, -elapsed)
      if (elapsed >= 0) {
        nowMs.value = elapsed
        if (state.value === 'COUNTDOWN') state.value = 'RUNNING'
      }
      advance()
      // With a tail, the round keeps running after the last cue so the uncued
      // presses are captured; otherwise it ends as soon as the cues are resolved.
      const allCuesResolved = resolvedUpTo >= cues.value.length - 1
      const done = tailMs > 0 ? elapsed > totalMs + tailMs + 1500 : true
      if (elapsed > totalMs + tailMs + 1500 || (allCuesResolved && done)) {
        finish()
        return
      }
      rafHandle = requestAnimationFrame(tick)
    }
    rafHandle = requestAnimationFrame(tick)
  }

  /** Play the cue note at its target and reveal it at its onset. */
  function advance() {
    const window = options?.difficulty.judgement_window_ms ?? 300
    for (let i = resolvedUpTo + 1; i < cues.value.length; i++) {
      const cue = cues.value[i]
      if (nowMs.value < cue.cueOnsetMs) break

      // Sound the note once, at the exact target time on the audio clock.
      if (!sounded.has(i)) {
        sounded.add(i)
        engine.play(cue.binding.midi, startPerf + cue.targetMs)
        activeCueIndex.value = i
      }

      // Resolve once the window has closed.
      if (nowMs.value > cue.targetMs + window / 2) {
        const rows = resolveCue(cue, presses.value, window, events.value.length)
        events.value = [...events.value, ...rows]
        resolvedUpTo = i
        if (activeCueIndex.value === i) activeCueIndex.value = null
      } else {
        break
      }
    }
  }

  function finish() {
    if (rafHandle !== null) {
      cancelAnimationFrame(rafHandle)
      rafHandle = null
    }
    // Resolve anything still pending so no cue is lost.
    const window = options?.difficulty.judgement_window_ms ?? 300
    for (let i = resolvedUpTo + 1; i < cues.value.length; i++) {
      const cue = cues.value[i]
      if (nowMs.value < cue.cueOnsetMs) break
      const rows = resolveCue(cue, presses.value, window, events.value.length)
      events.value = [...events.value, ...rows]
      resolvedUpTo = i
    }
    activeCueIndex.value = null
    state.value = 'FINISHED'
  }

  function cancel() {
    if (rafHandle !== null) {
      cancelAnimationFrame(rafHandle)
      rafHandle = null
    }
    state.value = 'IDLE'
  }

  /**
   * Register a key press. `code` is the physical key, so the mapping does not
   * depend on the keyboard layout.
   */
  function press(code: string): KeyBinding | null {
    const binding = BINDING_BY_CODE[code]
    if (!binding) return null
    if (downTimes.has(code)) return binding // ignore auto-repeat

    const perf = performance.now()
    const relative = perf - startPerf
    downTimes.set(code, perf)

    // Sound immediately on press so the patient hears their own key.
    engine.play(binding.midi, perf)

    pressedKeys.value = new Set([...pressedKeys.value, binding.midi])

    if (state.value === 'RUNNING') {
      presses.value = [
        ...presses.value,
        {
          code,
          midi: binding.midi,
          downTimeMs: perf,
          upTimeMs: null,
          relativeDownMs: relative,
          relativeUpMs: null,
        },
      ]
      // A press outside every open window is recorded as a stray event so the
      // raw timeline stays complete.
      const insideAnyWindow = cues.value.some((cue) => {
        const window = options?.difficulty.judgement_window_ms ?? 300
        return (
          relative >= cue.targetMs - window / 2 &&
          relative <= cue.targetMs + window / 2
        )
      })
      if (!insideAnyWindow) {
        events.value = [...events.value, strayEvent(presses.value[presses.value.length - 1], events.value.length)]
      }
    }
    return binding
  }

  function release(code: string): KeyBinding | null {
    const binding = BINDING_BY_CODE[code]
    if (!binding) return null
    const down = downTimes.get(code)
    downTimes.delete(code)
    pressedKeys.value = new Set([...pressedKeys.value].filter((m) => m !== binding.midi))
    if (down === undefined) return binding

    const up = performance.now()
    // Attach the release to the matching press so hold duration is recorded.
    const index = presses.value.findIndex((p) => p.code === code && p.upTimeMs === null)
    if (index >= 0) {
      const next = [...presses.value]
      next[index] = { ...next[index], upTimeMs: up, relativeUpMs: up - startPerf }
      presses.value = next
    }
    return binding
  }

  onBeforeUnmount(() => {
    if (rafHandle !== null) cancelAnimationFrame(rafHandle)
  })

  return {
    state,
    cues,
    events,
    presses,
    metrics,
    progress,
    nowMs,
    elapsedMs,
    countdownMs,
    currentCue,
    activeCueIndex,
    visibleCues,
    pressedKeys,
    audioReady,
    audioError,
    unlocked,
    inputLatencyNote: INPUT_LATENCY_NOTE,
    prepare,
    warmUp,
    unlock,
    start,
    finish,
    cancel,
    press,
    release,
  }
}
