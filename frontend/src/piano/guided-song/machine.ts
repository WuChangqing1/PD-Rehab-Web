import { SEVEN_KEYS, TWO_TIGERS } from './song.ts'
export type SongState = 'CONFIGURING' | 'PREPARING' | 'COUNTDOWN' | 'SEGMENT_1_DEMO' | 'SEGMENT_1_PLAY' | 'SEGMENT_1_RESULT' | 'SEGMENT_2_DEMO' | 'SEGMENT_2_PLAY' | 'MERGING_AUDIO' | 'PLAYBACK' | 'COMPLETED' | 'CANCELLED' | 'FAILED'
export interface RawSongEvent {
  seq: number; type: 'CUE' | 'DOWN' | 'UP' | 'SKIP' | 'PAUSE' | 'RESUME'
  segment_index: 1 | 2; note_index: number; time_ms: number; midi?: number; press_id?: string
}
export type SongEvent = RawSongEvent
export interface NoteRecord {
  note_index: number; segment_index: 1 | 2; expected_midi: number; cue_onset_time_ms: number
  first_attempt_time_ms: number | null; correct_press_time_ms: number | null; response_latency_ms: number | null
  attempt_count: number; wrong_attempt_count: number; is_first_attempt_correct: boolean; was_skipped: boolean
  key_down_time_ms: number | null; key_up_time_ms: number | null; hold_duration_ms: number | null
}
const nextStates: Record<SongState, SongState[]> = {
  CONFIGURING:['PREPARING'], PREPARING:['COUNTDOWN'], COUNTDOWN:['SEGMENT_1_DEMO'],
  SEGMENT_1_DEMO:['SEGMENT_1_PLAY'], SEGMENT_1_PLAY:['SEGMENT_1_RESULT'], SEGMENT_1_RESULT:['SEGMENT_2_DEMO'],
  SEGMENT_2_DEMO:['SEGMENT_2_PLAY'], SEGMENT_2_PLAY:['MERGING_AUDIO'], MERGING_AUDIO:['PLAYBACK'],
  PLAYBACK:['COMPLETED'], COMPLETED:[], CANCELLED:[], FAILED:[],
}
export class GuidedSongMachine {
  state: SongState = 'CONFIGURING'
  paused = false
  events: RawSongEvent[] = []
  noteRecords: NoteRecord[] = []
  private index = 0
  private segment: 1 | 2 = 1
  private held = new Map<string, RawSongEvent>()
  private lastTime = 0
  private usedPressIds = new Set<string>()
  get isPlaying() { return this.state === 'SEGMENT_1_PLAY' || this.state === 'SEGMENT_2_PLAY' }
  get currentNote() { return this.isPlaying && this.index < (this.segment === 1 ? 14 : 32) ? TWO_TIGERS.notes[this.index]! : null }
  get heldCount() { return this.held.size }
  private checkTime(time: number) {
    if (!Number.isFinite(time) || time < this.lastTime || time < 0) throw new Error('事件时间必须单调递增')
    this.lastTime = time
  }
  private record(type: RawSongEvent['type'], time_ms: number, detail: Partial<RawSongEvent> = {}) {
    this.checkTime(time_ms)
    const event: RawSongEvent = { seq: this.events.length, type, segment_index: this.segment, note_index: Math.min(this.index, this.segment === 1 ? 13 : 31), time_ms, ...detail }
    this.events.push(event)
    return event
  }
  transition(next: SongState, timeMs: number) {
    if (!nextStates[this.state].includes(next)) throw new Error(`非法训练状态转换: ${this.state} → ${next}`)
    if (this.isPlaying && (this.currentNote || this.held.size)) throw new Error('段落尚未完成或仍有按键未释放')
    this.checkTime(timeMs)
    this.state = next
    if (next === 'SEGMENT_1_PLAY' || next === 'SEGMENT_2_PLAY') {
      this.segment = next === 'SEGMENT_1_PLAY' ? 1 : 2
      this.index = this.segment === 1 ? 0 : 14
      this.cue(timeMs)
    }
  }
  private cue(time: number) {
    const note = this.currentNote
    if (!note) return
    this.record('CUE', time)
    this.noteRecords.push({ note_index: note.note_index, segment_index: note.segment_index, expected_midi: note.midi,
      cue_onset_time_ms: time, first_attempt_time_ms:null,correct_press_time_ms:null,response_latency_ms:null,
      attempt_count:0,wrong_attempt_count:0,is_first_attempt_correct:false,was_skipped:false,
      key_down_time_ms:null,key_up_time_ms:null,hold_duration_ms:null })
  }
  down(midi: number, pressId: string, timeMs: number): { accepted: boolean; correct: boolean } {
    const note = this.currentNote
    if (!note || this.paused || this.usedPressIds.has(pressId) || [...this.held.values()].some(e=>e.midi===midi) || !pressId || !(SEVEN_KEYS as readonly number[]).includes(midi)) return { accepted:false,correct:false }
    const event = this.record('DOWN', timeMs, {midi,press_id:pressId})
    this.held.set(pressId,event); this.usedPressIds.add(pressId)
    const record = this.noteRecords[this.index]!
    record.attempt_count++
    record.first_attempt_time_ms ??= timeMs
    const correct = midi === note.midi
    if (correct) {
      record.is_first_attempt_correct = record.attempt_count === 1
      record.correct_press_time_ms = record.key_down_time_ms = timeMs
      record.response_latency_ms = timeMs - record.cue_onset_time_ms
      this.index++; this.cue(timeMs)
    } else record.wrong_attempt_count++
    return {accepted:true,correct}
  }
  up(pressId: string, timeMs: number) {
    const down = this.held.get(pressId)
    if (!down) return false
    this.record('UP',timeMs,{note_index:down.note_index,segment_index:down.segment_index,midi:down.midi,press_id:pressId})
    this.held.delete(pressId)
    const note = this.noteRecords[down.note_index]!
    if (note.correct_press_time_ms === down.time_ms && note.expected_midi === down.midi) {
      note.key_up_time_ms = timeMs; note.hold_duration_ms = timeMs - down.time_ms
    }
    this.finishSegment(timeMs)
    return true
  }
  private finishSegment(time: number) {
    if (this.isPlaying && !this.currentNote && !this.held.size) this.transition(this.segment === 1 ? 'SEGMENT_1_RESULT' : 'MERGING_AUDIO',time)
  }
  skip(timeMs: number) {
    if (!this.currentNote || this.paused) return false
    this.record('SKIP',timeMs); this.noteRecords[this.index]!.was_skipped = true
    this.index++; this.cue(timeMs); this.finishSegment(timeMs)
    return true
  }
  pause(timeMs: number) {
    if (!this.isPlaying || this.paused) return
    // Record release before PAUSE so audio cannot hang while the app is hidden.
    for (const id of [...this.held.keys()]) this.up(id,timeMs)
    if (!this.isPlaying) return
    this.record('PAUSE',timeMs); this.paused = true
  }
  resume(timeMs: number) { if (this.isPlaying && this.paused) { this.record('RESUME',timeMs); this.paused = false } }
  cancel(timeMs: number) { this.terminate('CANCELLED',timeMs) }
  fail(timeMs: number) { this.terminate('FAILED',timeMs) }
  private terminate(state: 'CANCELLED' | 'FAILED', timeMs: number) {
    if (['COMPLETED','CANCELLED','FAILED'].includes(this.state)) return
    this.checkTime(timeMs)
    for (const id of [...this.held.keys()]) this.up(id,timeMs)
    this.state = state; this.paused = false
  }
  metrics(segment?: 1 | 2) {
    const records = this.noteRecords.filter(n => !segment || n.segment_index === segment)
    const attempted = records.filter(n => n.attempt_count > 0)
    const correct = records.filter(n => n.correct_press_time_ms !== null).length
    const attempts = records.reduce((sum,n)=>sum+n.attempt_count,0)
    const total = segment === 1 ? 14 : segment === 2 ? 18 : 32
    return { first_attempt_accuracy: attempted.length ? attempted.filter(n=>n.is_first_attempt_correct).length/attempted.length : 0,
      total_attempt_accuracy:attempts ? correct/attempts : 0, completion_rate:correct/total,
      wrong_press_count:records.reduce((sum,n)=>sum+n.wrong_attempt_count,0), skip_count:records.filter(n=>n.was_skipped).length,
      completed_notes:correct,total_notes:total }
  }
}
