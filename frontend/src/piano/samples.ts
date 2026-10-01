/**
 * Piano sample index for C3..B4 (MIDI 48..71).
 *
 * SOURCE
 * ======
 * Audio samples come from https://github.com/Wscats/piano (MIT licensed).
 * See NOTICE for the attribution. 61 mp3 files were copied unchanged into
 * frontend/public/samples/piano/.
 *
 * WHY THIS TABLE IS NOT TAKEN FROM THAT PROJECT
 * =============================================
 * The upstream `notes.js` maps note names to sample files, but the mapping does
 * not survive measurement. Every sample was decoded with ffmpeg and its pitch
 * estimated by FFT peak (scripts/_piano_build_index.py). Two problems surfaced:
 *
 *   1. The file numbers are not MIDI numbers. Upstream maps C4 -> a84 and
 *      B4 -> a65; measured, a84 is C4 and a65 is B4, but upstream also maps
 *      E3 -> a48 while a48 measures 130.81 Hz, which is C3.
 *   2. The single-letter prefix is not white/black. b56 measures 277.18 Hz
 *      (C#4) and b68 measures 622.25 Hz (D#5) correctly, but several `a` files
 *      are accidentals: a69 is A3 (the measured pitch class is right, the
 *      numbering is not), and b54 measures A#2 rather than a black key in the
 *      expected place.
 *
 * The table below is therefore generated from measurement, not copied. It
 * lists, for each note, the sample whose measured pitch is closest to it, plus
 * a playbackRate for the two notes that have no usable sample of their own.
 *
 * MEASURED ACCURACY
 * =================
 * The samples are close to, but not exactly at, concert pitch. Deviations for
 * the notes used here run from -40.7 to +24.7 cents (a quarter tone is 50), and
 * the two shifted notes land within a cent. This is inaudible for a rhythm and
 * finger-tapping task, and the raw files are used unmodified rather than
 * re-pitched, so the timing and character of each sample is preserved. If
 * exact concert pitch is ever required, apply playbackRate = 2^(-cents/1200)
 * per note; the measured cents offset is recorded in
 * data/demo/piano_samples_measured.json.
 */

export interface PianoSample {
  /** MIDI note number. */
  midi: number
  /** Scientific pitch name, e.g. "C4". */
  note: string
  /** File name inside /samples/piano/. */
  file: string
  /** Playback rate needed to reach the nominal pitch (1 = sample as-is). */
  playbackRate: number
  /** Measured deviation of the source sample in cents, for traceability. */
  centsOffset: number
}

export const PIANO_LOW_MIDI = 48 // C3
export const PIANO_HIGH_MIDI = 71 // B4

export const PIANO_SAMPLES: Record<number, PianoSample> = {
  48: { midi: 48, note: 'C3', file: 'a49.mp3', playbackRate: 1, centsOffset: -15.3 },
  49: { midi: 49, note: 'C#3', file: 'b49.mp3', playbackRate: 1, centsOffset: -95.9 },
  50: { midi: 50, note: 'D3', file: 'a50.mp3', playbackRate: 1, centsOffset: -31.1 },
  51: { midi: 51, note: 'D#3', file: 'b50.mp3', playbackRate: 1, centsOffset: -21.1 },
  // No sample measured at E3; b50 (D#3) shifted up one semitone.
  52: { midi: 52, note: 'E3', file: 'b50.mp3', playbackRate: 1.059463, centsOffset: -21.1 },
  // No sample measured at F3; b52 (F#3) shifted down one semitone.
  53: { midi: 53, note: 'F3', file: 'b52.mp3', playbackRate: 0.943874, centsOffset: 90.5 },
  54: { midi: 54, note: 'F#3', file: 'b52.mp3', playbackRate: 1, centsOffset: 90.5 },
  55: { midi: 55, note: 'G3', file: 'a53.mp3', playbackRate: 1, centsOffset: 72.3 },
  56: { midi: 56, note: 'G#3', file: 'b87.mp3', playbackRate: 1, centsOffset: 3.6 },
  57: { midi: 57, note: 'A3', file: 'a69.mp3', playbackRate: 1, centsOffset: 14.9 },
  58: { midi: 58, note: 'A#3', file: 'b69.mp3', playbackRate: 1, centsOffset: 19.3 },
  59: { midi: 59, note: 'B3', file: 'a82.mp3', playbackRate: 1, centsOffset: 6.9 },
  60: { midi: 60, note: 'C4', file: 'a56.mp3', playbackRate: 1, centsOffset: -40.7 },
  61: { midi: 61, note: 'C#4', file: 'b56.mp3', playbackRate: 1, centsOffset: -5.2 },
  62: { midi: 62, note: 'D4', file: 'a57.mp3', playbackRate: 1, centsOffset: -7.2 },
  63: { midi: 63, note: 'D#4', file: 'b57.mp3', playbackRate: 1, centsOffset: -13.2 },
  64: { midi: 64, note: 'E4', file: 'a85.mp3', playbackRate: 1, centsOffset: 19.8 },
  65: { midi: 65, note: 'F4', file: 'a73.mp3', playbackRate: 1, centsOffset: -23.9 },
  66: { midi: 66, note: 'F#4', file: 'b81.mp3', playbackRate: 1, centsOffset: 21.7 },
  67: { midi: 67, note: 'G4', file: 'a79.mp3', playbackRate: 1, centsOffset: 24.7 },
  68: { midi: 68, note: 'G#4', file: 'b79.mp3', playbackRate: 1, centsOffset: 6.9 },
  69: { midi: 69, note: 'A4', file: 'a80.mp3', playbackRate: 1, centsOffset: 9.8 },
  70: { midi: 70, note: 'A#4', file: 'b80.mp3', playbackRate: 1, centsOffset: 4.7 },
  71: { midi: 71, note: 'B4', file: 'a65.mp3', playbackRate: 1, centsOffset: 6.3 },
}

/**
 * Base path; the Vite build may serve the app from a sub-path.
 *
 * `import.meta.env` exists in the Vite build and is undefined when Node loads
 * this module directly in the rule tests, so it is read defensively. Without the
 * optional chain the whole cue/event model becomes unloadable under Node, which
 * is where its tests run.
 */
export const SAMPLE_BASE = `${import.meta.env?.BASE_URL ?? '/'}samples/piano/`

export function midiToNoteName(midi: number): string {
  const semitones = ['C', 'C#', 'D', 'D#', 'E', 'F', 'F#', 'G', 'G#', 'A', 'A#', 'B']
  return `${semitones[midi % 12]}${Math.floor(midi / 12) - 1}`
}

export function isAccidental(midi: number): boolean {
  return [1, 3, 6, 8, 10].includes(midi % 12)
}

export function sampleFor(midi: number): PianoSample | null {
  return PIANO_SAMPLES[midi] ?? null
}

/**
 * Keyboard layout: two rows, two octaves, no overlap.
 *
 * The upstream project mapped all five of its octaves onto the same ten keys
 * (pianoKeys.js assigns keyCode 49 to C2, C3, C4, C5 and C6 alike), so a single
 * key press triggers five notes at once. Here each key maps to exactly one
 * note, and the two rows are assigned to the two hands so that left/right
 * metrics are physically meaningful:
 *
 *   lower row  Z S X D C V G B H N J M  ->  C3..B3   (left hand)
 *   upper row  Q 2 W 3 E R 5 T 6 Y 7 U  ->  C4..B4   (right hand)
 *
 * `code` is KeyboardEvent.code, i.e. the physical key position, so the mapping
 * survives non-QWERTY layouts and does not depend on keyboard repeat.
 */
export type Hand = 'LEFT' | 'RIGHT'
export type FingerHint = 'THUMB' | 'INDEX' | 'MIDDLE' | 'RING' | 'LITTLE'

export interface KeyBinding {
  code: string
  midi: number
  note: string
  hand: Hand
  /** Task mapping only: a computer keyboard cannot reveal the real finger used. */
  fingerHint: FingerHint
  /** Physical key label for on-screen hints. */
  label: string
  /** Position within the row, used for rendering. */
  row: 'LOWER' | 'UPPER'
}

export const KEY_BINDINGS: KeyBinding[] = [
  // ---------------- left hand: lower row, C3..B3 ----------------
  { code: 'KeyZ', midi: 48, note: 'C3', hand: 'LEFT', fingerHint: 'LITTLE', label: 'Z', row: 'LOWER' },
  { code: 'KeyS', midi: 49, note: 'C#3', hand: 'LEFT', fingerHint: 'RING', label: 'S', row: 'LOWER' },
  { code: 'KeyX', midi: 50, note: 'D3', hand: 'LEFT', fingerHint: 'RING', label: 'X', row: 'LOWER' },
  { code: 'KeyD', midi: 51, note: 'D#3', hand: 'LEFT', fingerHint: 'MIDDLE', label: 'D', row: 'LOWER' },
  { code: 'KeyC', midi: 52, note: 'E3', hand: 'LEFT', fingerHint: 'MIDDLE', label: 'C', row: 'LOWER' },
  { code: 'KeyV', midi: 53, note: 'F3', hand: 'LEFT', fingerHint: 'INDEX', label: 'V', row: 'LOWER' },
  { code: 'KeyG', midi: 54, note: 'F#3', hand: 'LEFT', fingerHint: 'INDEX', label: 'G', row: 'LOWER' },
  { code: 'KeyB', midi: 55, note: 'G3', hand: 'LEFT', fingerHint: 'INDEX', label: 'B', row: 'LOWER' },
  { code: 'KeyH', midi: 56, note: 'G#3', hand: 'LEFT', fingerHint: 'INDEX', label: 'H', row: 'LOWER' },
  { code: 'KeyN', midi: 57, note: 'A3', hand: 'LEFT', fingerHint: 'INDEX', label: 'N', row: 'LOWER' },
  { code: 'KeyJ', midi: 58, note: 'A#3', hand: 'LEFT', fingerHint: 'INDEX', label: 'J', row: 'LOWER' },
  { code: 'KeyM', midi: 59, note: 'B3', hand: 'LEFT', fingerHint: 'INDEX', label: 'M', row: 'LOWER' },

  // ---------------- right hand: upper row, C4..B4 ----------------
  { code: 'KeyQ', midi: 60, note: 'C4', hand: 'RIGHT', fingerHint: 'LITTLE', label: 'Q', row: 'UPPER' },
  { code: 'Digit2', midi: 61, note: 'C#4', hand: 'RIGHT', fingerHint: 'RING', label: '2', row: 'UPPER' },
  { code: 'KeyW', midi: 62, note: 'D4', hand: 'RIGHT', fingerHint: 'RING', label: 'W', row: 'UPPER' },
  { code: 'Digit3', midi: 63, note: 'D#4', hand: 'RIGHT', fingerHint: 'MIDDLE', label: '3', row: 'UPPER' },
  { code: 'KeyE', midi: 64, note: 'E4', hand: 'RIGHT', fingerHint: 'MIDDLE', label: 'E', row: 'UPPER' },
  { code: 'KeyR', midi: 65, note: 'F4', hand: 'RIGHT', fingerHint: 'INDEX', label: 'R', row: 'UPPER' },
  { code: 'Digit5', midi: 66, note: 'F#4', hand: 'RIGHT', fingerHint: 'INDEX', label: '5', row: 'UPPER' },
  { code: 'KeyT', midi: 67, note: 'G4', hand: 'RIGHT', fingerHint: 'INDEX', label: 'T', row: 'UPPER' },
  { code: 'Digit6', midi: 68, note: 'G#4', hand: 'RIGHT', fingerHint: 'INDEX', label: '6', row: 'UPPER' },
  { code: 'KeyY', midi: 69, note: 'A4', hand: 'RIGHT', fingerHint: 'INDEX', label: 'Y', row: 'UPPER' },
  { code: 'Digit7', midi: 70, note: 'A#4', hand: 'RIGHT', fingerHint: 'INDEX', label: '7', row: 'UPPER' },
  { code: 'KeyU', midi: 71, note: 'B4', hand: 'RIGHT', fingerHint: 'INDEX', label: 'U', row: 'UPPER' },
]

export const BINDING_BY_CODE: Record<string, KeyBinding> = Object.fromEntries(
  KEY_BINDINGS.map((binding) => [binding.code, binding]),
)

export const BINDING_BY_MIDI: Record<number, KeyBinding> = Object.fromEntries(
  KEY_BINDINGS.map((binding) => [binding.midi, binding]),
)

/** Fingers treated as weak for weak_finger_error_rate (spec V2 section 19). */
export const WEAK_FINGERS: FingerHint[] = ['RING', 'LITTLE']

export function isWeakFinger(hint: FingerHint | null | undefined): boolean {
  return hint === 'RING' || hint === 'LITTLE'
}
