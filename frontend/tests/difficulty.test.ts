/**
 * Rule-engine tests for the piano adaptive difficulty.
 *
 * Run with:  npm run test:rules      (Node >= 22.6, no extra dependencies)
 *
 * The objective for this engine is "a round changes only a small number of
 * parameters", because otherwise a later change in performance cannot be
 * attributed to anything. That property is the reason this file exists: it was
 * previously only convention, and one real round changed four fields at once.
 *
 * The module under test imports types only, so Node's type stripping can run it
 * directly without a bundler.
 */

import assert from 'node:assert/strict'
import test from 'node:test'

import {
  adaptDifficulty,
  baselineFromCalibration,
  DIFFICULTY_ENGINE_VERSION,
  initialDifficulty,
  RULES,
  type CalibrationBaseline,
} from '../src/piano/difficulty.ts'
import type { DifficultyConfig } from '../src/piano/session.ts'
import type { PianoMetrics } from '../src/piano/metrics.ts'

/** A metric set with everything at "acceptable", overridable per test. */
function metrics(overrides: Partial<PianoMetrics> = {}): PianoMetrics {
  return {
    total_cues: 30,
    correct_count: 28,
    missed_count: 0,
    wrong_key_count: 2,
    accuracy: 0.93,
    miss_rate: 0,
    mean_response_latency_ms: 520,
    median_response_latency_ms: 515,
    response_latency_cv: 0.12,
    mean_timing_error_ms: 5,
    median_timing_error_ms: 4,
    timing_error_std_ms: 40,
    timing_error_cv: 0.3,
    timing_error_cv_note: null,
    mean_absolute_timing_error_ms: 60,
    early_press_rate: 0.2,
    late_press_rate: 0.2,
    left_mean_latency: 530,
    right_mean_latency: 510,
    left_right_latency_difference: 20,
    left_accuracy: 0.92,
    right_accuracy: 0.94,
    weak_finger_error_rate: 0.1,
    sequence_completion_rate: 0.9,
    session_completion_rate: 1,
    error_streak_max: 1,
    ...overrides,
  } as PianoMetrics
}

const BASE: DifficultyConfig = {
  bpm: 60,
  judgement_window_ms: 300,
  sequence_length: 4,
  note_density: 1,
  hand_mode: 'SINGLE',
  weak_side_ratio: 0.5,
  finger_complexity: 1,
  session_duration_sec: 60,
}

function baseline(overrides: Partial<CalibrationBaseline> = {}): CalibrationBaseline {
  return {
    baseline_accuracy: 0.9,
    baseline_response_latency: 500,
    baseline_response_latency_cv: 0.15,
    baseline_timing_mae: 70,
    baseline_left_accuracy: 0.9,
    baseline_right_accuracy: 0.9,
    baseline_left_latency: 500,
    baseline_right_latency: 500,
    ...overrides,
  }
}

// --------------------------------------------------------------- the budget
test('no round changes more than maxChangesPerRound parameters', () => {
  const cases: Array<[string, PianoMetrics]> = [
    ['strong performance', metrics()],
    ['failing performance', metrics({ accuracy: 0.4, miss_rate: 0.35, error_streak_max: 6 })],
    ['failing and asymmetric', metrics({
      accuracy: 0.4,
      miss_rate: 0.35,
      error_streak_max: 6,
      left_mean_latency: 900,
      right_mean_latency: 600,
      left_accuracy: 0.3,
      right_accuracy: 0.6,
    })],
    ['slow but accurate', metrics({ mean_response_latency_ms: 900 })],
    ['exactly at the maintain boundary', metrics({ accuracy: 0.7, miss_rate: 0.06 })],
  ]

  for (const [label, m] of cases) {
    const result = adaptDifficulty(m, BASE, baseline())
    assert.ok(
      result.changes.length <= RULES.maxChangesPerRound,
      `${label}: changed ${result.changes.length} parameters (${result.changes
        .map((c) => c.field)
        .join(', ')})`,
    )
  }
})

test('a downgrade no longer changes four fields at once', () => {
  // This is the exact shape that produced bpm -5, window +25, sequence -1 and
  // weak_side_ratio +0.15 in a single round.
  const m = metrics({
    accuracy: 0.4,
    miss_rate: 0.35,
    error_streak_max: 6,
    left_mean_latency: 900,
    right_mean_latency: 600,
    left_accuracy: 0.3,
    right_accuracy: 0.6,
  })
  const result = adaptDifficulty(m, BASE, baseline())

  assert.equal(result.decision, 'DOWNGRADE')
  assert.equal(result.changes.length, RULES.maxChangesPerRound)
  // Safety first: the window widens before the tempo drops.
  assert.deepEqual(
    result.changes.map((c) => c.field),
    ['judgement_window_ms', 'bpm'],
  )
  assert.equal(result.after.judgement_window_ms, 325)
  assert.equal(result.after.bpm, 55)
  // Untouched within the budget.
  assert.equal(result.after.sequence_length, BASE.sequence_length)
  assert.equal(result.after.weak_side_ratio, BASE.weak_side_ratio)
  assert.ok(result.reasons.some((r) => r.includes('已达上限')))
})

test('an upgrade changes one difficulty lever, plus at most the hand share', () => {
  // The difficulty levers are bpm / window / sequence / finger complexity; only
  // one of them may move per round so the effect stays attributable. The
  // weak-side share is personalisation rather than difficulty (V2 section 24),
  // it is separately bounded to 15 points, and it spends the same budget.
  const result = adaptDifficulty(metrics(), BASE, baseline())
  assert.equal(result.decision, 'UPGRADE')

  const difficultyLevers = result.changes.filter((c) => c.field !== 'weak_side_ratio')
  assert.equal(difficultyLevers.length, 1, `difficulty levers moved: ${difficultyLevers.map((c) => c.field)}`)
  assert.equal(difficultyLevers[0].field, 'bpm')
  assert.equal(result.after.bpm, 65)

  for (const change of result.changes) {
    assert.ok(
      (['bpm', 'judgement_window_ms', 'sequence_length', 'finger_complexity', 'weak_side_ratio'] as string[]).includes(
        String(change.field),
      ),
    )
  }
})

test('an upgrade spends only the difficulty slot when the hands are symmetric', () => {
  const symmetric = metrics({
    left_mean_latency: 520,
    right_mean_latency: 520,
    left_accuracy: 0.93,
    right_accuracy: 0.93,
  })
  const result = adaptDifficulty(symmetric, BASE, baseline())
  assert.equal(result.decision, 'UPGRADE')
  assert.deepEqual(result.changes.map((c) => c.field), ['bpm'])
})

test('the budget does not waste a slot on a field that cannot move', () => {
  // Window is already at its maximum, so the downgrade must spend its budget on
  // the two fields that can still move instead of proposing a no-op.
  const atCeiling: DifficultyConfig = { ...BASE, judgement_window_ms: RULES.judgementWindowMax }
  const m = metrics({ accuracy: 0.4, miss_rate: 0.35, error_streak_max: 6 })
  const result = adaptDifficulty(m, atCeiling, baseline())

  assert.equal(result.decision, 'DOWNGRADE')
  assert.deepEqual(
    result.changes.map((c) => c.field),
    ['bpm', 'sequence_length'],
  )
  for (const change of result.changes) {
    assert.notEqual(change.from, change.to)
  }
})

test('every change is a real change and matches the returned config', () => {
  const m = metrics({ accuracy: 0.4, miss_rate: 0.35, error_streak_max: 6 })
  const result = adaptDifficulty(m, BASE, baseline())
  for (const change of result.changes) {
    assert.notEqual(change.from, change.to, `${String(change.field)} was recorded unchanged`)
    assert.equal(
      result.after[change.field as keyof DifficultyConfig],
      change.to,
      `${String(change.field)} on the config disagrees with the recorded change`,
    )
  }
})

// ------------------------------------------------- left / right personalisation
test('the weak-side share moves by at most 15 percentage points', () => {
  const m = metrics({
    // Right hand worse on both measures.
    right_mean_latency: 900,
    right_accuracy: 0.8,
    left_mean_latency: 500,
    left_accuracy: 0.95,
  })
  const result = adaptDifficulty(m, BASE, baseline())

  const share = result.changes.find((c) => c.field === 'weak_side_ratio')
  assert.ok(share, 'expected the weaker hand to be served more often')
  const delta = Math.abs(Number(share!.to) - Number(share!.from))
  assert.ok(delta <= 0.15 + 1e-9, `weak-side share moved by ${delta}`)
  assert.ok(delta >= 0.1, `weak-side share should move by 10-15%, moved ${delta}`)
})

test('a weak hand is only inferred when latency and accuracy agree', () => {
  // Slower on the right but also more accurate: not a weak side, just cautious.
  const m = metrics({
    right_mean_latency: 900,
    right_accuracy: 0.99,
    left_mean_latency: 500,
    left_accuracy: 0.8,
  })
  const result = adaptDifficulty(m, BASE, baseline())
  assert.equal(result.weak_hand, null)
  assert.equal(result.changes.filter((c) => c.field === 'weak_side_ratio').length, 0)
})

test('the weak-side share stays inside its configured bounds', () => {
  let config: DifficultyConfig = { ...BASE, weak_side_ratio: RULES.weakSideMax }
  const m = metrics({ left_mean_latency: 900, left_accuracy: 0.5, right_mean_latency: 400, right_accuracy: 0.99 })
  for (let round = 0; round < 5; round++) {
    const result = adaptDifficulty(m, config, baseline())
    config = result.after
    assert.ok(config.weak_side_ratio <= RULES.weakSideMax)
    assert.ok(config.weak_side_ratio >= RULES.weakSideMin)
  }
})

// ----------------------------------------------------------------- inputs
test('the engine does not read micro-expression tags or a PD probability', () => {
  // Guard against a future edit wiring model output into difficulty: the
  // sensitive metrics object is frozen, and any extra property is ignored.
  const extended = {
    ...metrics(),
    micro_expression_tag_ratio: { bradykinesia: 0.9 },
    pd_probability: 0.97,
    severity_score: 42,
  } as unknown as PianoMetrics

  const withModel = adaptDifficulty(extended, BASE, baseline())
  const withoutModel = adaptDifficulty(metrics(), BASE, baseline())
  assert.deepEqual(withModel.after, withoutModel.after)
  assert.equal(withModel.decision, withoutModel.decision)
})

test('a missing calibration degrades to behaviour-only rules, never to a guess', () => {
  const result = adaptDifficulty(metrics(), BASE, null)
  const computed = result.applied_rules.computed as Record<string, unknown>
  // Without a personal baseline the MAE and latency comparisons are undefined
  // and must not silently count as passing or failing.
  assert.equal(computed.timing_mae_threshold_ms, null)
  assert.equal(computed.latency_threshold_ms, null)
  assert.equal((computed.upgrade_conditions as Record<string, unknown>).timing_mae_ok, null)
  // Accuracy, miss rate and latency CV alone are enough to upgrade.
  assert.equal(result.decision, 'UPGRADE')
})

// --------------------------------------------------------------- calibration
test('initial difficulty comes from the calibration, not from a disease label', () => {
  const strong = initialDifficulty(baseline({ baseline_accuracy: 0.95, baseline_response_latency: 400 }))
  const weak = initialDifficulty(baseline({ baseline_accuracy: 0.5, baseline_response_latency: 900 }))
  const mid = initialDifficulty(baseline({ baseline_accuracy: 0.8, baseline_response_latency: 700 }))

  assert.ok(strong.bpm > mid.bpm && mid.bpm > weak.bpm)
  assert.ok(strong.judgement_window_ms < mid.judgement_window_ms)
  assert.ok(mid.judgement_window_ms < weak.judgement_window_ms)

  // An asymmetric calibration biases the hand mix toward the worse hand.
  const asymmetric = initialDifficulty(
    baseline({ baseline_left_accuracy: 0.6, baseline_right_accuracy: 0.95 }),
  )
  assert.ok(asymmetric.weak_side_ratio > 0.5)
  const mirrored = initialDifficulty(
    baseline({ baseline_left_accuracy: 0.95, baseline_right_accuracy: 0.6 }),
  )
  assert.ok(mirrored.weak_side_ratio < 0.5)
})

test('baselineFromCalibration copies a metric into each of the eight values', () => {
  const m = metrics()
  const b = baselineFromCalibration(m)
  assert.equal(b.baseline_accuracy, m.accuracy)
  assert.equal(b.baseline_response_latency, m.mean_response_latency_ms)
  assert.equal(b.baseline_response_latency_cv, m.response_latency_cv)
  assert.equal(b.baseline_timing_mae, m.mean_absolute_timing_error_ms)
  assert.equal(b.baseline_left_accuracy, m.left_accuracy)
  assert.equal(b.baseline_right_accuracy, m.right_accuracy)
  assert.equal(b.baseline_left_latency, m.left_mean_latency)
  assert.equal(b.baseline_right_latency, m.right_mean_latency)
  assert.equal(Object.keys(b).length, 8)
})

// ------------------------------------------------------------------ versions
test('the decision carries the engine version and the thresholds it applied', () => {
  const result = adaptDifficulty(metrics(), BASE, baseline())
  assert.equal(result.engine_version, DIFFICULTY_ENGINE_VERSION)
  assert.match(result.engine_version, /^piano-difficulty-v\d+\.\d+\.\d+$/)
  assert.equal(result.applied_rules.maxChangesPerRound, RULES.maxChangesPerRound)
  assert.equal(result.applied_rules.weakSideStepMax, RULES.weakSideStepMax)
  // The computed inputs are recorded so a decision can be reproduced.
  const computed = result.applied_rules.computed as Record<string, unknown>
  assert.equal(computed.accuracy, 0.93)
  assert.equal(computed.timing_mae_threshold_ms, 70)
  assert.equal(computed.latency_threshold_ms, 650)
})

test('the engine never mutates the configuration it was given', () => {
  const before: DifficultyConfig = { ...BASE }
  const snapshot = { ...before }
  adaptDifficulty(metrics({ accuracy: 0.3, miss_rate: 0.4 }), before, baseline())
  assert.deepEqual(before, snapshot)
})
