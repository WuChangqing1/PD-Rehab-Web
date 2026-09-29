/**
 * Piano session metrics (spec V2 sections 18 and 19).
 *
 * Every metric is computed from stored raw events, so a session can be
 * recomputed later without replaying it. Formula notes that matter:
 *
 *   CV        = std / mean, with a guard when |mean| is near zero. This matters
 *               for timing_error_cv in particular: mean timing error can sit
 *               near zero because early and late presses cancel out, which would
 *               make the ratio explode. When that happens the metric is null and
 *               timing_error_std_ms is the honest alternative.
 *   weak_finger_error_rate
 *             counts errors on cues whose finger_hint is RING or LITTLE. This is
 *               a TASK MAPPING metric: the system knows which mapping key was
 *               requested, not which physical finger was used.
 *
 * Anything undefined is null, never 0, so "no data" and "zero" stay distinct.
 */

import { isWeakFinger, type Hand } from '@/piano/samples'
import type { PianoRawEvent } from '@/piano/session'

const EPS = 1e-9

export interface PianoMetrics {
  // --- counts ---
  total_cues: number
  correct_count: number
  wrong_count: number
  missed_count: number

  // --- P0 ---
  accuracy: number | null
  miss_rate: number | null
  mean_timing_error_ms: number | null
  median_timing_error_ms: number | null
  timing_error_cv: number | null
  mean_response_latency_ms: number | null
  median_response_latency_ms: number | null
  response_latency_cv: number | null
  left_mean_latency: number | null
  right_mean_latency: number | null
  left_right_latency_difference: number | null
  left_accuracy: number | null
  right_accuracy: number | null
  weak_finger_error_rate: number | null
  session_completion_rate: number | null

  // --- P1, computed because they are free from stored events ---
  mean_absolute_timing_error_ms: number | null
  timing_error_std_ms: number | null
  early_press_rate: number | null
  late_press_rate: number | null
  error_streak_max: number | null
  key_hold_duration_ms: number | null
  sequence_completion_rate: number | null

  // --- traceability ---
  timing_error_cv_note: string | null
}

function finite(value: number | null | undefined): number | null {
  if (value === null || value === undefined) return null
  return Number.isFinite(value) ? value : null
}

function mean(values: number[]): number | null {
  const usable = values.filter((v) => Number.isFinite(v))
  if (usable.length === 0) return null
  return finite(usable.reduce((a, b) => a + b, 0) / usable.length)
}

function median(values: number[]): number | null {
  const usable = values.filter((v) => Number.isFinite(v)).slice().sort((a, b) => a - b)
  if (usable.length === 0) return null
  const mid = Math.floor(usable.length / 2)
  return finite(usable.length % 2 ? usable[mid] : (usable[mid - 1] + usable[mid]) / 2)
}

function std(values: number[]): number | null {
  const usable = values.filter((v) => Number.isFinite(v))
  if (usable.length < 2) return null
  const m = usable.reduce((a, b) => a + b, 0) / usable.length
  const variance = usable.reduce((acc, v) => acc + (v - m) ** 2, 0) / usable.length
  return finite(Math.sqrt(variance))
}

function cv(values: number[]): number | null {
  const usable = values.filter((v) => Number.isFinite(v))
  if (usable.length < 2) return null
  const m = usable.reduce((a, b) => a + b, 0) / usable.length
  if (Math.abs(m) < EPS) return null
  const s = std(usable)
  if (s === null) return null
  return finite(s / m)
}

/**
 * CV of the signed timing error, or null when it cannot be interpreted.
 *
 * A mean timing error near zero is the expected result for a competent
 * performer, because early and late presses cancel out. Dividing by it gives an
 * enormous meaningless ratio: a real calibration round produced mean 1.4 ms with
 * sd 82 ms, i.e. CV = 58.7. The CV is therefore reported only when the mean is
 * large enough to be distinguished from zero (|mean| >= 0.25 * sd); otherwise
 * timing_error_std_ms is the honest measure and a note explains why.
 */
function timingErrorCv(values: number[]): { cv: number | null; note: string | null } {
  const usable = values.filter((v) => Number.isFinite(v))
  if (usable.length < 2) return { cv: null, note: null }
  const m = usable.reduce((a, b) => a + b, 0) / usable.length
  const s = std(usable)
  if (s === null || s < EPS) {
    return { cv: Math.abs(m) >= EPS ? 0 : null, note: null }
  }
  if (Math.abs(m) < 0.25 * s) {
    return {
      cv: null,
      note:
        '平均节拍误差接近 0（提前与滞后互相抵消），CV 无法解释；' +
        '请改看 timing_error_std_ms（节拍误差标准差）。',
    }
  }
  return { cv: finite(s / m), note: null }
}

function ratio(numerator: number, denominator: number): number | null {
  if (denominator <= 0) return null
  return finite(numerator / denominator)
}

/** Cue rows are the ones that represent a target the patient was asked to hit. */
function cueRows(events: PianoRawEvent[]): PianoRawEvent[] {
  return events.filter((e) => !e.is_wrong_key)
}

export function computeMetrics(
  events: PianoRawEvent[],
  options: { plannedCues?: number } = {},
): PianoMetrics {
  const cues = cueRows(events)
  const totalCues = cues.length
  const correct = cues.filter((e) => e.is_correct)
  const missed = cues.filter((e) => e.is_missed)
  const wrong = events.filter((e) => e.is_wrong_key)

  const latencies = correct
    .map((e) => e.response_latency_ms)
    .filter((v): v is number => v !== null)
  const timingErrors = correct
    .map((e) => e.timing_error_ms)
    .filter((v): v is number => v !== null)
  const timingAbs = timingErrors.map((v) => Math.abs(v))
  const holds = events
    .map((e) => e.hold_duration_ms)
    .filter((v): v is number => v !== null)

  const byHand = (hand: Hand) => correct.filter((e) => e.hand === hand)
  const cuesByHand = (hand: Hand) => cues.filter((e) => e.hand === hand)

  const leftLatencies = byHand('LEFT')
    .map((e) => e.response_latency_ms)
    .filter((v): v is number => v !== null)
  const rightLatencies = byHand('RIGHT')
    .map((e) => e.response_latency_ms)
    .filter((v): v is number => v !== null)
  const leftMean = mean(leftLatencies)
  const rightMean = mean(rightLatencies)

  const weakCues = cues.filter((e) => isWeakFinger(e.finger_hint))
  const weakErrors = weakCues.filter((e) => !e.is_correct)

  // Early / late use the judgement window as the reference for "on time"; the
  // threshold is derived from the data rather than invented here.
  const absErrors = timingAbs
  const typicalError = absErrors.length ? median(absErrors) ?? 0 : 0
  const earlyThreshold = typicalError
  const early = timingErrors.filter((v) => v < -earlyThreshold).length
  const late = timingErrors.filter((v) => v > earlyThreshold).length

  // Longest run of consecutive non-correct cues.
  let streak = 0
  let maxStreak = 0
  for (const row of cues) {
    if (row.is_correct) {
      streak = 0
    } else {
      streak += 1
      maxStreak = Math.max(maxStreak, streak)
    }
  }

  // Sequence completion: fraction of started note groups fully correct.
  const groups = new Map<string, { total: number; correct: number }>()
  for (const row of cues) {
    if (row.sequence_position == null || row.sequence_length == null) continue
    const key = `${row.cue_index ?? 'x'}-${row.sequence_length}`
    const group = groups.get(key) ?? { total: 0, correct: 0 }
    group.total += 1
    if (row.is_correct) group.correct += 1
    groups.set(key, group)
  }
  const sequenceCompletion =
    groups.size === 0
      ? null
      : ratio(
          [...groups.values()].filter((g) => g.total > 0 && g.correct === g.total).length,
          groups.size,
        )

  const planned = options.plannedCues && options.plannedCues > 0 ? options.plannedCues : totalCues

  const timingResult = timingErrorCv(timingErrors)
  const timingCv = timingResult.cv

  return {
    total_cues: totalCues,
    correct_count: correct.length,
    wrong_count: wrong.length,
    missed_count: missed.length,

    accuracy: ratio(correct.length, totalCues),
    miss_rate: ratio(missed.length, totalCues),
    mean_timing_error_ms: mean(timingErrors),
    median_timing_error_ms: median(timingErrors),
    timing_error_cv: timingCv,
    mean_response_latency_ms: mean(latencies),
    median_response_latency_ms: median(latencies),
    response_latency_cv: cv(latencies),
    left_mean_latency: leftMean,
    right_mean_latency: rightMean,
    left_right_latency_difference:
      leftMean === null || rightMean === null ? null : finite(leftMean - rightMean),
    left_accuracy: ratio(byHand('LEFT').length, cuesByHand('LEFT').length),
    right_accuracy: ratio(byHand('RIGHT').length, cuesByHand('RIGHT').length),
    weak_finger_error_rate: ratio(weakErrors.length, weakCues.length),
    session_completion_rate: ratio(totalCues, planned),

    mean_absolute_timing_error_ms: mean(timingAbs),
    timing_error_std_ms: std(timingErrors),
    early_press_rate: ratio(early, timingErrors.length),
    late_press_rate: ratio(late, timingErrors.length),
    error_streak_max: totalCues ? maxStreak : null,
    key_hold_duration_ms: mean(holds),
    sequence_completion_rate: sequenceCompletion,

    timing_error_cv_note: timingResult.note,
  }
}

/** Left/right summary used by the UI, mirroring the finger tapping comparison. */
export interface HandComparison {  metric: string
  left: number | null
  right: number | null
  absolute_difference: number | null
}

export function compareHands(metrics: PianoMetrics): HandComparison[] {
  const pairs: Array<[string, number | null, number | null]> = [
    ['mean_response_latency_ms', metrics.left_mean_latency, metrics.right_mean_latency],
    ['accuracy', metrics.left_accuracy, metrics.right_accuracy],
  ]
  return pairs.map(([metric, left, right]) => ({
    metric,
    left,
    right,
    absolute_difference:
      left === null || right === null ? null : finite(left - right),
  }))
}
