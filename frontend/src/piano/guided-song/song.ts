export const SEVEN_KEYS = [60, 62, 64, 65, 67, 69, 71] as const
export const DIFFICULTY_BPM = { BEGINNER: 60, INTERMEDIATE: 80, ADVANCED: 100 } as const
export type SongDifficulty = keyof typeof DIFFICULTY_BPM
export interface SongNote { note_index: number; segment_index: 1 | 2; midi: number; beats: number }
const pitches = [[60,62,64,60,60,62,64,60,64,65,67,64,65,67], [67,69,67,65,64,60,67,69,67,65,64,60,60,67,60,60,67,60]]
const beats = [[1,1,1,1,1,1,1,1,1,1,2,1,1,2], [.5,.5,.5,.5,1,1,.5,.5,.5,.5,1,1,1,1,2,1,1,2]]
const segments = pitches.map((notes, i) => ({
  segment_index: (i + 1) as 1 | 2,
  notes: notes.map((midi, j): SongNote => ({ midi, beats: beats[i]![j]!, note_index: (i ? 14 : 0) + j, segment_index: (i + 1) as 1 | 2 })),
}))
export const TWO_TIGERS = {
  song_id: 'two_tigers', song_version: '1', version: 1, title: '两只老虎', scale: SEVEN_KEYS,
  supported_difficulties: Object.keys(DIFFICULTY_BPM) as SongDifficulty[], segments, notes: segments.flatMap(s => s.notes),
}
export function noteDurationMs(note: SongNote, bpm: number): number {
  if (!Number.isFinite(bpm) || bpm <= 0 || bpm > 120) throw new Error('速度应在 0 至 120 BPM 之间')
  return note.beats * 60000 / bpm
}
// Shared by the visible key labels and physical keyboard input.
export const KEYBOARD_LETTERS = ['A','S','D','F','G','H','J'] as const
