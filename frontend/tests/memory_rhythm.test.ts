/**
 * Tests for the optional memory-rhythm piano mode.
 *
 * Run with:  npm run test:rules
 *
 * The rule that matters most here is a negative one: a demonstrated note is not
 * a question. If a prompt cue were counted as a target, the mode would report a
 * miss for every note the patient was told to watch, and the resulting accuracy
 * would describe the mode rather than the patient.
 */

import assert from 'node:assert/strict'
import test from 'node:test'

import {
  CORE_TRAINING_MODES,
  generateCues,
  isOptionalMode,
  MODE_LABELS,
  resolveCue,
  TRAINING_MODES,
  type DifficultyConfig,
  type PressInput,
  type PianoMode,
} from '../src/piano/session.ts'

const base: DifficultyConfig = {
  bpm: 60,
  judgement_window_ms: 300,
  sequence_length: 4,
  note_density: 1.0,
  hand_mode: 'SINGLE',
  weak_side_ratio: 0.5,
  finger_complexity: 1,
  session_duration_sec: 60,
}

const memoryCues = (overrides: Partial<DifficultyConfig> = {}) =>
  generateCues('MEMORY_RHYTHM', { ...base, ...overrides }, { seed: 7, cueCount: 24 })

test('memory rhythm is offered as a mode the doctor can choose', () => {
  assert.ok(TRAINING_MODES.includes('MEMORY_RHYTHM'))
  assert.ok(MODE_LABELS.MEMORY_RHYTHM.length > 0)
})

test('memory rhythm is optional and not part of the core programme', () => {
  assert.equal(isOptionalMode('MEMORY_RHYTHM'), true)
  assert.equal(isOptionalMode('SINGLE_KEY_RHYTHM'), false)
  assert.ok(!CORE_TRAINING_MODES.includes('MEMORY_RHYTHM'))
  // The four core modes are still all there.
  assert.deepEqual(CORE_TRAINING_MODES, [
    'SINGLE_KEY_RHYTHM',
    'ALTERNATING_HANDS',
    'MAPPED_SEQUENCE',
    'FOLLOW_THE_BEAT',
  ])
})

test('every mode still generates cues', () => {
  const modes: PianoMode[] = [
    'CALIBRATION',
    'SINGLE_KEY_RHYTHM',
    'ALTERNATING_HANDS',
    'MAPPED_SEQUENCE',
    'FOLLOW_THE_BEAT',
    'MEMORY_RHYTHM',
  ]
  for (const mode of modes) {
    const cues = generateCues(mode, base, { seed: 3, cueCount: 24 })
    assert.ok(cues.length > 0, `${mode} produced no cues`)
  }
})

test('memory cues alternate a demonstrated group and a reply group', () => {
  const cues = memoryCues()
  assert.ok(cues.length > 0)
  // Starts with a demonstration: the patient watches first.
  assert.equal(cues[0].isPrompt, true)

  const group0 = cues.filter((c) => c.memoryGroup === 0)
  const prompts = group0.filter((c) => c.isPrompt)
  const replies = group0.filter((c) => !c.isPrompt)
  assert.equal(prompts.length, replies.length)
  assert.equal(prompts.length, base.sequence_length + 1)
})

test('the reply asks for exactly the notes that were demonstrated', () => {
  const cues = memoryCues()
  const group0 = cues.filter((c) => c.memoryGroup === 0)
  const prompts = group0.filter((c) => c.isPrompt).map((c) => c.binding.midi)
  const replies = group0.filter((c) => !c.isPrompt).map((c) => c.binding.midi)
  assert.deepEqual(replies, prompts)
})

test('demonstration notes are played before their reply, not at the same time', () => {
  const cues = memoryCues()
  const group0 = cues.filter((c) => c.memoryGroup === 0)
  const lastPrompt = Math.max(...group0.filter((c) => c.isPrompt).map((c) => c.targetMs))
  const firstReply = Math.min(...group0.filter((c) => !c.isPrompt).map((c) => c.targetMs))
  assert.ok(firstReply > lastPrompt, 'the reply must come after the demonstration')
  // The gap is a real pause, not a single beat: the patient needs a moment.
  assert.ok(firstReply - lastPrompt >= 1800)
})

test('the sequence is reproducible from the configuration alone', () => {
  const a = memoryCues().map((c) => `${c.binding.midi}:${c.targetMs}:${c.isPrompt}`)
  const b = memoryCues().map((c) => `${c.binding.midi}:${c.targetMs}:${c.isPrompt}`)
  assert.deepEqual(a, b)
})

test('a demonstrated note resolves to one row and counts no press against it', () => {
  const cues = memoryCues()
  const prompt = cues.find((c) => c.isPrompt)!
  // The patient happened to press something during the demonstration.
  const stray: PressInput[] = [
    {
      code: 'KeyA',
      midi: prompt.binding.midi,
      downTimeMs: 0,
      upTimeMs: null,
      relativeDownMs: prompt.targetMs,
      relativeUpMs: null,
    },
  ]
  const rows = resolveCue(prompt, stray, base.judgement_window_ms)
  assert.equal(rows.length, 1)
  assert.equal(rows[0].is_prompt, true)
  assert.equal(rows[0].is_correct, true)
  assert.equal(rows[0].is_missed, false)
  // A prompt is not an answer, so it carries no latency or timing error.
  assert.equal(rows[0].response_latency_ms, null)
  assert.equal(rows[0].timing_error_ms, null)
})

test('a prompt resolves the same way with no presses at all', () => {
  const prompt = memoryCues().find((c) => c.isPrompt)!
  const rows = resolveCue(prompt, [], base.judgement_window_ms)
  assert.equal(rows.length, 1)
  assert.equal(rows[0].is_missed, false)
  assert.equal(rows[0].is_prompt, true)
})

test('a reply cue is resolved as an ordinary target', () => {
  const reply = memoryCues().find((c) => !c.isPrompt)!
  const rows = resolveCue(reply, [], base.judgement_window_ms)
  assert.equal(rows.length, 1)
  assert.equal(rows[0].is_missed, true, 'an unanswered reply is a real miss')
  assert.equal(rows[0].is_prompt, false)
  assert.equal(rows[0].memory_group, reply.memoryGroup)
})

test('the reply carries the memory group so it can be scored as one sequence', () => {
  const cues = memoryCues()
  const replies = cues.filter((c) => !c.isPrompt)
  assert.ok(replies.length > 0)
  assert.ok(replies.every((c) => typeof c.memoryGroup === 'number'))
  assert.ok(replies.every((c) => c.sequencePosition !== undefined && c.sequenceLength !== undefined))
})

test('sequence length is raised above the base so the group is worth remembering', () => {
  const short = generateCues(
    'MEMORY_RHYTHM',
    { ...base, sequence_length: 3 },
    { seed: 1, cueCount: 24 },
  ).find((c) => c.isPrompt && c.sequenceLength)
  assert.ok((short?.sequenceLength ?? 0) >= 4)
})

test('a short round still produces a complete pair rather than a truncated group', () => {
  // 6 cues cannot hold a demonstration and a reply of 5, so nothing is emitted.
  const cues = generateCues('MEMORY_RHYTHM', base, { seed: 1, cueCount: 6 })
  const group0 = cues.filter((c) => c.memoryGroup === 0)
  if (group0.length) {
    const prompts = group0.filter((c) => c.isPrompt).length
    const replies = group0.filter((c) => !c.isPrompt).length
    assert.equal(prompts, replies, 'a half-emitted group would be unanswerable')
  }
})
