/**
 * The patient's own tapping rate, measured with no cue present.
 *
 * Evidence basis (docs/piano_training_plan.md P1): every source that sets a
 * metronome "at 110% / 120% of baseline" assumes a baseline tempo exists. Until
 * this measurement was added the system had none -- tempo was an absolute bpm
 * unrelated to the patient's own rhythm.
 *
 * This is a MEASUREMENT, not a task: nothing here is scored right or wrong, and
 * the segment it reads is deliberately uncued.
 *
 * NOTE ON SELF-CONTAINMENT
 * ========================
 * This module deliberately imports nothing, not even the numeric helpers in
 * `metrics.ts`. `npm run test:rules` runs the TS directly under Node, which does
 * not resolve the `@/` alias, so a module that pulls one in cannot be unit
 * tested. The three helpers below are a few lines each; keeping them local buys
 * a tested measurement.
 */

export interface SpontaneousTempo {
  tap_count: number
  /** Median interval between consecutive taps, ms. Robust to a missed tap. */
  interval_ms: number | null
  rate_hz: number | null
  /** Variability of the patient's own rhythm; null below two intervals. */
  interval_cv: number | null
}

function finite(value: number | null | undefined): number | null {
  if (value === null || value === undefined || !Number.isFinite(value)) return null
  return value
}

function median(values: number[]): number | null {
  if (!values.length) return null
  const sorted = [...values].sort((a, b) => a - b)
  const middle = Math.floor(sorted.length / 2)
  return sorted.length % 2 ? sorted[middle] : (sorted[middle - 1] + sorted[middle]) / 2
}

/**
 * @param relativeDownMs press times, in ms from session start
 * @param windowStartMs start of the uncued segment
 */
export function spontaneousTempo(
  relativeDownMs: number[],
  windowStartMs: number,
): SpontaneousTempo {
  const taps = relativeDownMs
    .filter((t) => Number.isFinite(t) && t >= windowStartMs)
    .sort((a, b) => a - b)

  if (taps.length < 2) {
    return { tap_count: taps.length, interval_ms: null, rate_hz: null, interval_cv: null }
  }

  const intervals: number[] = []
  for (let i = 1; i < taps.length; i++) {
    const gap = taps[i] - taps[i - 1]
    // Ignore accidental double-triggers; a real tap cannot repeat in under 80 ms.
    if (gap >= 80) intervals.push(gap)
  }
  if (intervals.length === 0) {
    return { tap_count: taps.length, interval_ms: null, rate_hz: null, interval_cv: null }
  }

  const medianInterval = median(intervals)
  if (medianInterval === null || medianInterval <= 0) {
    return { tap_count: taps.length, interval_ms: null, rate_hz: null, interval_cv: null }
  }

  let cv: number | null = null
  if (intervals.length >= 2) {
    const mean = intervals.reduce((a, b) => a + b, 0) / intervals.length
    if (Math.abs(mean) > 1e-9) {
      const variance =
        intervals.reduce((sum, v) => sum + (v - mean) ** 2, 0) / (intervals.length - 1)
      cv = finite(Math.sqrt(Math.max(0, variance)) / Math.abs(mean))
    }
  }

  return {
    tap_count: taps.length,
    interval_ms: finite(medianInterval),
    rate_hz: finite(1000 / medianInterval),
    interval_cv: cv,
  }
}
