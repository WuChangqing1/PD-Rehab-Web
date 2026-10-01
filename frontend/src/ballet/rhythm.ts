/**
 * Rhythm for the ballet module: a metronome, a count, and a simple accompaniment.
 *
 * WHY THIS EXISTS
 * ===============
 * The training method this module follows is built on external rhythm, explicit
 * counts and slow, decomposed movement. A patient with Parkinson's who is asked
 * to "raise both arms" without a beat has no external time reference, which is
 * the thing the cue is supposed to supply. So the count is not decoration; it is
 * the task.
 *
 * NO COPYRIGHTED MUSIC
 * ====================
 * Every note here is synthesised with the Web Audio API from oscillators. There
 * is no audio file, no sample library and nothing to license. The timbre is a
 * deliberately plain struck-string approximation -- a plausible piano-ish note,
 * not a piano.
 *
 * THE CLOCK IS NOT `setInterval`
 * ==============================
 * Counting beats with `setInterval` drifts, and drift is the one thing a
 * metronome cannot have. Every beat's time is computed from the AudioContext
 * clock and scheduled ahead of time; a slow UI timer only tops up the schedule.
 * The visual count reads the same clock, so what the patient hears and what the
 * patient sees cannot diverge.
 *
 * This file must stay free of `@/` runtime imports so the pure helpers can be
 * tested through `node --experimental-strip-types`.
 */

// --------------------------------------------------------------------------
// pure helpers (testable without an AudioContext)
// --------------------------------------------------------------------------

/** Tempos the doctor may choose. The patient never picks one. */
export const TEMPO_CHOICES = [50, 60, 70, 80] as const

export const MIN_TEMPO = 40
export const MAX_TEMPO = 120

/** Seconds per beat at a given tempo. */
export function secondsPerBeat(bpm: number): number {
  const safe = clampTempo(bpm)
  return 60 / safe
}

export function clampTempo(bpm: number): number {
  if (!Number.isFinite(bpm)) return 60
  return Math.min(MAX_TEMPO, Math.max(MIN_TEMPO, Math.round(bpm)))
}

/**
 * Which beat of the bar a beat index falls on.
 *
 * A 4/4 bar with the accent on beat 1 is what makes a count followable; without
 * an accent every beat sounds the same and the patient cannot tell where the
 * phrase restarts.
 */
export function beatInBar(beatIndex: number, beatsPerBar = 4): number {
  const bar = Math.max(1, Math.round(beatsPerBar))
  return ((beatIndex % bar) + bar) % bar
}

export function isAccent(beatIndex: number, beatsPerBar = 4): boolean {
  return beatInBar(beatIndex, beatsPerBar) === 0
}

/**
 * The cue step that is active at a given beat within one repetition.
 *
 * Cues are a *sequence of counted steps* -- "双臂缓慢抬起" for 4 beats, then
 * "向外打开" for 4 -- so the beat determines which line the patient is on. The
 * hold is the tail: it is the last `holdBeats` beats of the phrase.
 */
export interface CueLike {
  text: string
  beats: number
}

export interface CuePosition {
  /** Index into the cue list, or -1 while holding. */
  index: number
  text: string
  /** Beat within this step, 1-based. */
  stepBeat: number
  stepBeats: number
  /** True while the patient is holding the end position. */
  holding: boolean
}

export function cuePositionAt(
  cues: readonly CueLike[],
  holdBeats: number,
  beatInRepetition: number,
): CuePosition {
  const total = cues.reduce((sum, c) => sum + c.beats, 0) + Math.max(0, holdBeats)
  if (total <= 0) {
    return { index: -1, text: '', stepBeat: 1, stepBeats: 1, holding: false }
  }
  // Wrap, so the function is total for any beat rather than only in range.
  const beat = ((beatInRepetition % total) + total) % total

  let cursor = 0
  for (let i = 0; i < cues.length; i += 1) {
    const step = cues[i]
    if (beat < cursor + step.beats) {
      return {
        index: i,
        text: step.text,
        stepBeat: beat - cursor + 1,
        stepBeats: step.beats,
        holding: false,
      }
    }
    cursor += step.beats
  }

  return {
    index: -1,
    text: '保持',
    stepBeat: beat - cursor + 1,
    stepBeats: Math.max(1, Math.round(holdBeats)),
    holding: true,
  }
}

/** Beats in one complete repetition. */
export function repetitionBeats(cues: readonly CueLike[], holdBeats: number): number {
  return cues.reduce((sum, c) => sum + c.beats, 0) + Math.max(0, holdBeats)
}

/**
 * The accompanying note for a beat.
 *
 * A slow four-bar progression in C, arpeggiated one note per beat, so the
 * harmony tells the patient where they are in the phrase as well as the click
 * does. Deliberately simple and loopable.
 */
const PROGRESSION = [
  [48, 55, 64, 67], // C
  [45, 52, 60, 64], // Am
  [41, 48, 57, 60], // F
  [43, 50, 59, 62], // G
]

export function accompanimentMidi(beatIndex: number, beatsPerBar = 4): number {
  const bar = Math.max(1, Math.round(beatsPerBar))
  const barIndex = Math.floor(beatIndex / bar)
  const chord = PROGRESSION[((barIndex % PROGRESSION.length) + PROGRESSION.length) % PROGRESSION.length]
  const note = beatInBar(beatIndex, bar)
  return chord[note % chord.length]
}

/** Equal temperament, A4 = 440 Hz, MIDI 69. */
export function midiToFrequency(midi: number): number {
  return 440 * Math.pow(2, (midi - 69) / 12)
}
