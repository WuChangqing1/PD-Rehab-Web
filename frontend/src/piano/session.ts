/**
 * Piano session model: cue generation, event capture, and metrics.
 *
 * This is a pure TypeScript module with no DOM or audio dependency, so every
 * rule below is unit-testable and the numbers can be recomputed from stored raw
 * events.
 *
 * TWO QUANTITIES THAT MUST NEVER BE CONFUSED (spec V2 section 16)
 * ==============================================================
 *   response_latency_ms = first_valid_response_time - cue_onset_time
 *       How long after the stimulus appeared the patient responded at all.
 *   timing_error_ms     = actual_time_ms - target_time_ms
 *       How far from the intended beat the response landed.
 *       < 0 early, > 0 late.
 *
 * A patient can have a fast latency and a large timing error (responds quickly
 * but off the beat), or a slow latency and a small timing error. They are
 * therefore computed from different pairs of timestamps and never substituted
 * for one another.
 *
 * HAND AND FINGER
 * ===============
 * `hand` and `finger_hint` are TASK MAPPING values: the system knows which key
 * it asked for, not which physical finger was used. Everything derived from
 * them (`weak_finger_error_rate` in particular) must be labelled that way.
 */

// Relative, not the `@/` alias: Node resolves this module directly in the rule
// tests, and `@/piano/samples` is not a package it can find. `samples.ts` has no
// imports of its own, so this makes the whole cue/event model testable as-is.
import {
  BINDING_BY_CODE,
  BINDING_BY_MIDI,
  type FingerHint,
  type Hand,
  type KeyBinding,
} from './samples.ts'

export type PianoMode =
  | 'CALIBRATION'
  | 'SINGLE_KEY_RHYTHM'
  | 'ALTERNATING_HANDS'
  | 'MAPPED_SEQUENCE'
  | 'FOLLOW_THE_BEAT'
  | 'MEMORY_RHYTHM'

/**
 * Modes the doctor chooses from for a training round.
 *
 * Calibration is not in the list: it is the capability test that runs once
 * before training and is not selectable per round.
 */
export const TRAINING_MODES: PianoMode[] = [
  'SINGLE_KEY_RHYTHM',
  'ALTERNATING_HANDS',
  'MAPPED_SEQUENCE',
  'FOLLOW_THE_BEAT',
  'MEMORY_RHYTHM',
]

/**
 * Modes that are part of the standard three-round programme.
 *
 * Memory rhythm is deliberately excluded: it is an optional extra the doctor may
 * add, not something the patient has to complete. Mixing it into the automatic
 * progression would make an optional task mandatory by scheduling it.
 */
export const CORE_TRAINING_MODES: PianoMode[] = [
  'SINGLE_KEY_RHYTHM',
  'ALTERNATING_HANDS',
  'MAPPED_SEQUENCE',
  'FOLLOW_THE_BEAT',
]

export function isOptionalMode(mode: PianoMode): boolean {
  return mode === 'MEMORY_RHYTHM'
}

export const MODE_LABELS: Record<PianoMode, string> = {
  CALIBRATION: '基础能力测试',
  SINGLE_KEY_RHYTHM: '单键节奏',
  ALTERNATING_HANDS: '左右手交替',
  MAPPED_SEQUENCE: '按键序列',
  FOLLOW_THE_BEAT: '跟随节拍',
  MEMORY_RHYTHM: '记忆节奏（可选）',
}

export const MODE_DESCRIPTIONS: Record<PianoMode, string> = {
  CALIBRATION: '约 45 秒，用来测量患者自己的节奏，作为之后训练的起点。',
  SINGLE_KEY_RHYTHM: '按提示逐个按下高亮的琴键，建立基本的手部节奏。',
  ALTERNATING_HANDS: '左右手交替按键，训练双手协调。',
  MAPPED_SEQUENCE: '按顺序完成一组琴键，训练连续动作。',
  FOLLOW_THE_BEAT: '跟着节拍器的节拍按键。',
  MEMORY_RHYTHM: '系统先示范一小段，再由患者凭记忆弹出。可选，不计入必须完成的轮次。',
}

/** Cue definition, produced before the round starts. */
export interface Cue {
  eventIndex: number
  /** Time the cue becomes visible, ms from session start. */
  cueOnsetMs: number
  /** Time the patient should press, ms from session start. */
  targetMs: number
  binding: KeyBinding
  /** For sequence modes, which note of the group this is (1-based). */
  sequencePosition?: number
  sequenceLength?: number
  /**
   * Memory mode only: this cue is demonstrated for the patient, not asked of
   * them. The key is highlighted and sounded; nothing is expected to be pressed.
   */
  isPrompt?: boolean
  /** Memory mode only: which demonstration-and-reply group this belongs to. */
  memoryGroup?: number
}

/**
 * A recorded key press or a resolved cue, stored per spec V2 section 44.
 *
 * Missed cues are recorded with the press fields null, so `is_missed` is
 * derivable and the raw timeline stays complete.
 */
export interface PianoRawEvent {
  event_index: number
  cue_onset_time_ms: number | null
  target_time_ms: number | null
  actual_time_ms: number | null
  response_latency_ms: number | null
  timing_error_ms: number | null
  key_code: string | null
  note: string | null
  hand: Hand | null
  finger_hint: FingerHint | null

  key_down_time_ms: number | null
  key_up_time_ms: number | null
  hold_duration_ms: number | null

  is_correct: boolean
  is_missed: boolean

  /** True when the press was not for the expected key. */
  is_wrong_key?: boolean
  /** Cue this event belongs to, so wrong presses can be traced back. */
  cue_index?: number | null
  /** Position within a mapped-sequence group, when applicable (1-based). */
  sequence_position?: number | null
  sequence_length?: number | null
  /**
   * Memory mode: this row records a demonstrated note, not a patient response.
   *
   * It must be excluded from accuracy, miss rate and every latency statistic.
   * Counting a note the patient was never allowed to answer as a miss would
   * report a failure that did not happen.
   */
  is_prompt?: boolean
  memory_group?: number | null
}

/** Difficulty parameters actually used for a round (spec V2 section 23). */
export interface DifficultyConfig {
  bpm: number
  judgement_window_ms: number
  sequence_length: number
  note_density: number
  hand_mode: 'SINGLE' | 'ALTERNATING' | 'BOTH'
  weak_side_ratio: number
  finger_complexity: number
  session_duration_sec: number
}

export const DEFAULT_DIFFICULTY: DifficultyConfig = {
  bpm: 60,
  judgement_window_ms: 300,
  sequence_length: 4,
  note_density: 1.0,
  hand_mode: 'SINGLE',
  weak_side_ratio: 0.5,
  finger_complexity: 1,
  session_duration_sec: 60,
}

/** Time between the cue appearing and the moment it should be pressed. */
export const APPROACH_MS = 700

/**
 * Deterministic pseudo-random generator.
 *
 * Sequence generation must be reproducible from the stored configuration, so a
 * session can be replayed exactly. Math.random would break that.
 */
export function mulberry32(seed: number): () => number {
  let a = seed >>> 0
  return () => {
    a = (a + 0x6d2b79f5) >>> 0
    let t = a
    t = Math.imul(t ^ (t >>> 15), t | 1)
    t ^= t + Math.imul(t ^ (t >>> 7), t | 61)
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296
  }
}

const LEFT_KEYS = Object.values(BINDING_BY_MIDI).filter((b) => b.hand === 'LEFT')
const RIGHT_KEYS = Object.values(BINDING_BY_MIDI).filter((b) => b.hand === 'RIGHT')

/** Keys with a low finger_complexity: index/middle finger mappings only. */
function keysForComplexity(complexity: number, hand: Hand | 'ANY'): KeyBinding[] {
  const pool = hand === 'ANY' ? [...LEFT_KEYS, ...RIGHT_KEYS] : hand === 'LEFT' ? LEFT_KEYS : RIGHT_KEYS
  if (complexity <= 1) return pool.filter((b) => b.fingerHint === 'INDEX')
  if (complexity === 2) return pool.filter((b) => b.fingerHint === 'INDEX' || b.fingerHint === 'MIDDLE')
  return pool
}

/**
 * Build the cue stream for a round.
 *
 * Times are relative to session start. `note_density` scales the inter-onset
 * interval, and `weak_side_ratio` biases alternating modes toward the weaker
 * hand, which is the training-personalisation lever from spec V2 section 24.
 */
export function generateCues(
  mode: PianoMode,
  difficulty: DifficultyConfig,
  options: { seed?: number; weakHand?: Hand | null; cueCount?: number } = {},
): Cue[] {
  const seed = options.seed ?? 20260929
  const random = mulberry32(seed)
  const beatMs = 60000 / Math.max(20, difficulty.bpm)
  const intervalMs = Math.max(150, beatMs / Math.max(0.25, difficulty.note_density))
  const weakHand = options.weakHand ?? 'LEFT'
  const strongHand: Hand = weakHand === 'LEFT' ? 'RIGHT' : 'LEFT'

  const totalMs = difficulty.session_duration_sec * 1000
  const maxCues = options.cueCount ?? Math.max(4, Math.floor(totalMs / intervalMs))

  const cues: Cue[] = []
  let index = 0

  const push = (
    binding: KeyBinding,
    targetMs: number,
    sequence?: { position: number; length: number },
    extra?: { isPrompt?: boolean; memoryGroup?: number },
  ) => {
    cues.push({
      eventIndex: index++,
      cueOnsetMs: Math.max(0, targetMs - APPROACH_MS),
      targetMs,
      binding,
      sequencePosition: sequence?.position,
      sequenceLength: sequence?.length,
      isPrompt: extra?.isPrompt,
      memoryGroup: extra?.memoryGroup,
    })
  }

  switch (mode) {
    case 'CALIBRATION':
    case 'SINGLE_KEY_RHYTHM': {
      // One hand at a time, simplest mapping. Calibration uses both hands in
      // equal halves so left/right baselines can be derived from it.
      const pool = keysForComplexity(difficulty.finger_complexity, 'ANY')
      const half = mode === 'CALIBRATION' ? Math.floor(maxCues / 2) : maxCues
      for (let i = 0; i < maxCues; i++) {
        const hand: Hand =
          mode === 'CALIBRATION' ? (i < half ? 'LEFT' : 'RIGHT') : difficulty.hand_mode === 'BOTH' ? (i % 2 ? 'RIGHT' : 'LEFT') : 'RIGHT'
        const handPool = pool.filter((b) => b.hand === hand)
        const binding = handPool[Math.floor(random() * handPool.length)] ?? pool[0]
        push(binding, APPROACH_MS + i * intervalMs)
      }
      break
    }

    case 'ALTERNATING_HANDS': {
      for (let i = 0; i < maxCues; i++) {
        // weak_side_ratio is the probability of serving the weaker hand.
        const useWeak = random() < difficulty.weak_side_ratio
        const hand: Hand = useWeak ? weakHand : strongHand
        const pool = keysForComplexity(difficulty.finger_complexity, hand)
        const binding = pool[Math.floor(random() * pool.length)] ?? (hand === 'LEFT' ? LEFT_KEYS[0] : RIGHT_KEYS[0])
        push(binding, APPROACH_MS + i * intervalMs)
      }
      break
    }

    case 'MAPPED_SEQUENCE': {
      // Groups of ascending notes, each note still its own timed cue.
      const length = Math.max(2, Math.min(8, difficulty.sequence_length))
      const pool = keysForComplexity(difficulty.finger_complexity, 'ANY')
      let cursor = APPROACH_MS
      let served = 0
      while (served < maxCues) {
        const hand: Hand = cursor / intervalMs % 2 < 1 ? weakHand : strongHand
        const handPool = pool.filter((b) => b.hand === hand)
        const candidates = (handPool.length ? handPool : pool).slice().sort((a, b) => a.midi - b.midi)
        const start = Math.floor(random() * Math.max(1, candidates.length - length))
        const group = candidates.slice(start, start + length)
        for (let i = 0; i < group.length && served < maxCues; i++) {
          push(group[i], cursor, { position: i + 1, length: group.length })
          cursor += intervalMs
          served++
        }
      }
      break
    }

    case 'FOLLOW_THE_BEAT': {
      // Steady beat on a grid; notes descend to the judgement line at targetMs.
      const pool = keysForComplexity(difficulty.finger_complexity, 'ANY')
      for (let i = 0; i < maxCues; i++) {
        const hand: Hand =
          difficulty.hand_mode === 'ALTERNATING' ? (random() < difficulty.weak_side_ratio ? weakHand : strongHand) : 'ANY' as Hand
        const handPool = hand === ('ANY' as Hand) ? pool : pool.filter((b) => b.hand === hand)
        const binding = handPool[Math.floor(random() * handPool.length)] ?? pool[0]
        // Snap targets to the beat grid so the rhythm is unambiguous.
        push(binding, Math.ceil((APPROACH_MS + i * intervalMs) / beatMs) * beatMs)
      }
      break
    }

    case 'MEMORY_RHYTHM': {
      /*
        Demonstrate a short group, then ask for it back.

        The demonstration notes are cues of their own (`isPrompt`), so the
        patient watches and hears the sequence in time before reproducing it.
        Showing all four notes at once would make it a reading task rather than a
        memory one. Prompt cues are excluded from every accuracy denominator.

        This trains working rhythm under an external beat. It is not a cognitive
        assessment and produces no cognitive score.
      */
      const length = Math.max(3, Math.min(8, difficulty.sequence_length + 1))
      const pool = keysForComplexity(difficulty.finger_complexity, 'ANY')
      const candidates = pool.slice().sort((a, b) => a.midi - b.midi)
      const gapBeats = 2
      let cursor = APPROACH_MS
      let group = 0
      let served = 0

      while (served + length * 2 <= maxCues) {
        const span = Math.max(1, candidates.length - length)
        const start = Math.floor(random() * span)
        const notes = candidates.slice(start, start + length)
        // A deterministic rotation: the same configuration always yields the
        // same group, so a stored session can be replayed exactly.
        const offset = length ? Math.floor(random() * length) : 0
        const sequence = notes.map((_, i) => notes[(i + offset) % length])

        for (let i = 0; i < length; i++) {
          push(sequence[i], cursor, { position: i + 1, length }, { isPrompt: true, memoryGroup: group })
          cursor += intervalMs
        }
        cursor += beatMs * gapBeats
        for (let i = 0; i < length; i++) {
          push(sequence[i], cursor, { position: i + 1, length }, { memoryGroup: group })
          cursor += intervalMs
        }
        served += length * 2
        group += 1
      }
      break
    }
  }

  return cues
}

/** A raw press captured from the keyboard or the on-screen keys. */
export interface PressInput {
  /** KeyboardEvent.code, or `POINTER:<midi>` for mouse/touch. */
  code: string
  midi: number
  /** performance.now() at the moment the browser delivered the event. */
  downTimeMs: number
  upTimeMs: number | null
  /** Session-relative time in ms, computed by the recorder. */
  relativeDownMs: number
  relativeUpMs: number | null
}

/**
 * Resolve a cue against the presses seen during its window.
 *
 * Returns the event rows this cue produced:
 *   - one row per wrong press (is_correct false, is_wrong_key true)
 *   - one row for the first correct press (is_correct true), carrying both
 *     response_latency_ms and timing_error_ms
 *   - one row with null press fields when nothing correct arrived (is_missed)
 *
 * `event_index` is assigned from `startIndex` so the whole session forms one
 * non-decreasing sequence. It used to restart at 0 for every cue, which meant
 * every stored row had index 0 and the raw timeline had no defined order.
 */
export function resolveCue(
  cue: Cue,
  presses: PressInput[],
  judgementWindowMs: number,
  startIndex = 0,
): PianoRawEvent[] {
  const rows: PianoRawEvent[] = []
  const halfWindow = judgementWindowMs / 2
  const windowStart = cue.targetMs - halfWindow
  const windowEnd = cue.targetMs + halfWindow

  const inWindow = presses.filter(
    (press) => press.relativeDownMs >= windowStart && press.relativeDownMs <= windowEnd,
  )
  const correct = inWindow
    .filter((press) => press.midi === cue.binding.midi)
    .sort((a, b) => a.relativeDownMs - b.relativeDownMs)

  const base = {
    cue_onset_time_ms: Math.round(cue.cueOnsetMs),
    target_time_ms: Math.round(cue.targetMs),
    note: cue.binding.note,
    cue_index: cue.eventIndex,
    sequence_position: cue.sequencePosition ?? null,
    sequence_length: cue.sequenceLength ?? null,
    is_prompt: cue.isPrompt === true,
    memory_group: cue.memoryGroup ?? null,
  }

  /*
    A demonstrated note resolves to exactly one row and ignores presses.

    Any key the patient happens to hit while watching is not an answer to this
    cue -- they were not asked for one -- so it is deliberately not recorded
    against it. Recording it as a wrong key would manufacture errors.
  */
  if (cue.isPrompt) {
    rows.push({
      ...base,
      event_index: startIndex,
      actual_time_ms: null,
      response_latency_ms: null,
      timing_error_ms: null,
      key_code: cue.binding.code,
      hand: cue.binding.hand,
      finger_hint: cue.binding.fingerHint,
      key_down_time_ms: null,
      key_up_time_ms: null,
      hold_duration_ms: null,
      is_correct: true,
      is_missed: false,
      is_wrong_key: false,
    })
    return rows
  }

  // Wrong-key presses are recorded so the error is traceable, not just counted.
  for (const press of inWindow) {
    if (press.midi === cue.binding.midi) continue
    const binding = BINDING_BY_CODE[press.code] ?? BINDING_BY_MIDI[press.midi] ?? null
    rows.push({
      ...base,
      event_index: startIndex + rows.length,
      actual_time_ms: Math.round(press.relativeDownMs),
      // Latency is only defined against the first response to this cue.
      response_latency_ms: null,
      timing_error_ms: Math.round(press.relativeDownMs - cue.targetMs),
      key_code: binding?.code ?? press.code,
      hand: binding?.hand ?? cue.binding.hand,
      finger_hint: binding?.fingerHint ?? null,
      key_down_time_ms: Math.round(press.relativeDownMs),
      key_up_time_ms: press.relativeUpMs === null ? null : Math.round(press.relativeUpMs),
      hold_duration_ms:
        press.relativeUpMs === null ? null : Math.round(press.relativeUpMs - press.relativeDownMs),
      is_correct: false,
      is_missed: false,
      is_wrong_key: true,
    })
  }

  if (correct.length === 0) {
    rows.push({
      ...base,
      event_index: startIndex + rows.length,
      actual_time_ms: null,
      response_latency_ms: null,
      timing_error_ms: null,
      key_code: cue.binding.code,
      hand: cue.binding.hand,
      finger_hint: cue.binding.fingerHint,
      key_down_time_ms: null,
      key_up_time_ms: null,
      hold_duration_ms: null,
      is_correct: false,
      is_missed: true,
      is_wrong_key: false,
    })
    return rows
  }

  const first = correct[0]
  rows.push({
    ...base,
    event_index: startIndex + rows.length,
    actual_time_ms: Math.round(first.relativeDownMs),
    // The two quantities, from two different pairs of timestamps.
    response_latency_ms: Math.round(first.relativeDownMs - cue.cueOnsetMs),
    timing_error_ms: Math.round(first.relativeDownMs - cue.targetMs),
    key_code: first.code,
    hand: cue.binding.hand,
    finger_hint: cue.binding.fingerHint,
    key_down_time_ms: Math.round(first.relativeDownMs),
    key_up_time_ms: first.relativeUpMs === null ? null : Math.round(first.relativeUpMs),
    hold_duration_ms:
      first.relativeUpMs === null ? null : Math.round(first.relativeUpMs - first.relativeDownMs),
    is_correct: true,
    is_missed: false,
    is_wrong_key: false,
  })
  return rows
}

/** A press that landed outside any judgement window. */
export function strayEvent(press: PressInput, eventIndex: number): PianoRawEvent {
  const binding = BINDING_BY_CODE[press.code] ?? BINDING_BY_MIDI[press.midi] ?? null
  return {
    event_index: eventIndex,
    cue_onset_time_ms: null,
    target_time_ms: null,
    actual_time_ms: Math.round(press.relativeDownMs),
    response_latency_ms: null,
    timing_error_ms: null,
    key_code: binding?.code ?? press.code,
    note: binding?.note ?? null,
    hand: binding?.hand ?? null,
    finger_hint: binding?.fingerHint ?? null,
    key_down_time_ms: Math.round(press.relativeDownMs),
    key_up_time_ms: press.relativeUpMs === null ? null : Math.round(press.relativeUpMs),
    hold_duration_ms:
      press.relativeUpMs === null ? null : Math.round(press.relativeUpMs - press.relativeDownMs),
    is_correct: false,
    is_missed: false,
    is_wrong_key: true,
    cue_index: null,
  }
}
