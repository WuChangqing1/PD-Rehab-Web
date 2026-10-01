/**
 * Tests for the ballet rhythm engine's pure parts.
 *
 * Run with:  npm run test:rules
 *
 * The properties that matter and that a listening test would not pin down: the
 * count wraps, the accent lands on beat 1, and the cue sequence maps beats to
 * instructions exactly. A cue that drifts one beat out of step tells the patient
 * to raise their arms while the music says hold.
 */

import assert from 'node:assert/strict'
import test from 'node:test'

import {
  accompanimentMidi,
  beatInBar,
  clampTempo,
  cuePositionAt,
  isAccent,
  midiToFrequency,
  repetitionBeats,
  secondsPerBeat,
  TEMPO_CHOICES,
  type CueLike,
} from '../src/ballet/rhythm.ts'

const PORT_DE_BRAS: CueLike[] = [
  { text: '双臂缓慢抬起', beats: 4 },
  { text: '向外打开', beats: 4 },
  { text: '缓慢回落', beats: 4 },
]

test('seconds per beat follows the tempo', () => {
  assert.equal(secondsPerBeat(60), 1)
  assert.equal(secondsPerBeat(120), 0.5)
  assert.equal(secondsPerBeat(50), 1.2)
})

test('tempo is clamped into a usable range', () => {
  assert.equal(clampTempo(0), 40)
  assert.equal(clampTempo(-10), 40)
  assert.equal(clampTempo(999), 120)
  assert.equal(clampTempo(Number.NaN), 60)
  assert.equal(clampTempo(60.4), 60)
})

test('every offered tempo is inside the clamp range', () => {
  for (const bpm of TEMPO_CHOICES) {
    assert.equal(clampTempo(bpm), bpm)
  }
})

test('the bar accent lands on beat 1 and only beat 1', () => {
  assert.equal(isAccent(0), true)
  assert.equal(isAccent(1), false)
  assert.equal(isAccent(2), false)
  assert.equal(isAccent(3), false)
  assert.equal(isAccent(4), true)
})

test('beatInBar wraps for negative and large indices', () => {
  assert.equal(beatInBar(0), 0)
  assert.equal(beatInBar(5), 1)
  assert.equal(beatInBar(-1), 3)
  assert.equal(beatInBar(8), 0)
})

test('one repetition is the sum of the cue steps plus the hold', () => {
  assert.equal(repetitionBeats(PORT_DE_BRAS, 4), 16)
  assert.equal(repetitionBeats(PORT_DE_BRAS, 0), 12)
  assert.equal(repetitionBeats([], 4), 4)
})

test('each beat maps to the cue step that is actually being performed', () => {
  // Beats 0-3 are the first step, 4-7 the second, 8-11 the third, 12-15 hold.
  assert.deepEqual(
    [0, 3, 4, 7, 8, 11, 12, 15].map((b) => cuePositionAt(PORT_DE_BRAS, 4, b).text),
    [
      '双臂缓慢抬起',
      '双臂缓慢抬起',
      '向外打开',
      '向外打开',
      '缓慢回落',
      '缓慢回落',
      '保持',
      '保持',
    ],
  )
})

test('the step beat counts up inside a step and restarts at the next one', () => {
  assert.equal(cuePositionAt(PORT_DE_BRAS, 4, 0).stepBeat, 1)
  assert.equal(cuePositionAt(PORT_DE_BRAS, 4, 3).stepBeat, 4)
  assert.equal(cuePositionAt(PORT_DE_BRAS, 4, 4).stepBeat, 1)
})

test('the hold is reported as a hold, not as a cue step', () => {
  const held = cuePositionAt(PORT_DE_BRAS, 4, 13)
  assert.equal(held.holding, true)
  assert.equal(held.index, -1)
  assert.equal(held.stepBeats, 4)
})

test('the cue position wraps, so a longer session keeps counting', () => {
  assert.equal(cuePositionAt(PORT_DE_BRAS, 4, 0).text, cuePositionAt(PORT_DE_BRAS, 4, 16).text)
  assert.equal(cuePositionAt(PORT_DE_BRAS, 4, 20).text, '向外打开')
})

test('a cue sequence with no beats does not divide by zero', () => {
  const empty = cuePositionAt([], 0, 3)
  assert.equal(empty.text, '')
  assert.equal(empty.holding, false)
})

test('the accompaniment walks a chord per bar and repeats', () => {
  const firstBar = [0, 1, 2, 3].map((b) => accompanimentMidi(b))
  const fifthBar = [16, 17, 18, 19].map((b) => accompanimentMidi(b))
  // Four bars of progression, so bar 5 is bar 1 again: the loop is seamless.
  assert.deepEqual(firstBar, fifthBar)
})

test('the accompaniment stays inside the bass-to-mid range', () => {
  for (let beat = 0; beat < 64; beat += 1) {
    const midi = accompanimentMidi(beat)
    assert.ok(midi >= 36 && midi <= 72, `midi ${midi} out of range at beat ${beat}`)
  }
})

test('midi to frequency matches the concert pitch reference', () => {
  assert.equal(Math.round(midiToFrequency(69)), 440)
  assert.equal(Math.round(midiToFrequency(60)), 262)
  assert.equal(Math.round(midiToFrequency(81)), 880)
})
