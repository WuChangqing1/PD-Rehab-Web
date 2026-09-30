/**
 * Turning stored sessions into a plottable series.
 *
 * Three rules decide what may be drawn, and all three exist because the
 * alternative would put a number on screen that does not mean what it looks
 * like it means.
 *
 * 1. **Only real measurements.** A scripted self-test and a seeded demo row are
 *    stored in the same tables as a patient's own session. Plotting them in one
 *    line would show a trend that no patient ever produced, so they are dropped
 *    and counted, and the page reports how many were dropped.
 *
 * 2. **A point needs a time.** Rows without a timestamp cannot be placed on a
 *    time axis. They are dropped and counted rather than sorted to one end.
 *
 * 3. **Versions are not silently mixed.** Two points produced by different
 *    algorithm versions are not necessarily the same measurement, so the series
 *    carries the set of versions it spans and flags when there is more than one.
 *    The page can then say so instead of drawing a line across the change.
 *
 * What this module deliberately does NOT do is decide whether a change is an
 * improvement. That judgement needs a clinical direction per metric, and the
 * system has no validated one; it reports the numbers and leaves the reading to
 * the clinician.
 *
 * This file must stay free of `@/` imports: the rule tests run it through
 * `node --experimental-strip-types`, which cannot resolve the alias.
 */

/** How a metric's numbers should be formatted. */
export type TrendUnit = 'ratio' | 'ms' | 'number' | 'count' | 'sec' | 'deg'

/** One stored session, reduced to what a series needs. */
export interface TrendRowInput {
  /** ISO timestamp of the session, or null when the row has none. */
  at: string | null
  /** Raw metric value; null when this session has no value for this metric. */
  value: number | null
  /** Provenance flag from the stored row. */
  source: string | null
  /** Algorithm / engine version that produced the value, when stored. */
  version: string | null
}

export interface TrendPoint {
  /** ISO timestamp. */
  at: string
  value: number
  version: string | null
}

export interface TrendSeries {
  /** Plottable points, oldest first. */
  points: TrendPoint[]
  /** Rows dropped because they are not a real patient measurement. */
  excludedNonHuman: number
  /** Rows dropped because they carry no value for this metric. */
  skippedMissingValue: number
  /** Rows dropped because they carry no timestamp. */
  skippedNoTimestamp: number
  /** Distinct versions across the plotted points, in first-seen order. */
  versions: string[]
  /** True when the plotted points do not all come from one version. */
  mixedVersions: boolean
}

/** The only provenance flag that represents a measurement. */
export const HUMAN_SOURCE = 'HUMAN_KEYBOARD'

/** A row is plottable only when it came from a person. */
export function isMeasuredRow(source: string | null | undefined): boolean {
  return source === HUMAN_SOURCE
}

/**
 * Build the series for one metric.
 *
 * @param rows one entry per stored session, in any order
 */
export function buildTrendSeries(rows: readonly TrendRowInput[]): TrendSeries {
  const points: TrendPoint[] = []
  let excludedNonHuman = 0
  let skippedMissingValue = 0
  let skippedNoTimestamp = 0

  for (const row of rows) {
    if (!isMeasuredRow(row.source)) {
      excludedNonHuman += 1
      continue
    }
    if (row.value === null || row.value === undefined || !Number.isFinite(row.value)) {
      skippedMissingValue += 1
      continue
    }
    if (!row.at) {
      skippedNoTimestamp += 1
      continue
    }
    points.push({ at: row.at, value: row.value, version: row.version ?? null })
  }

  // Oldest first: a trend reads left to right in time.
  points.sort((a, b) => (a.at < b.at ? -1 : a.at > b.at ? 1 : 0))

  const versions: string[] = []
  for (const point of points) {
    if (point.version && !versions.includes(point.version)) versions.push(point.version)
  }

  return {
    points,
    excludedNonHuman,
    skippedMissingValue,
    skippedNoTimestamp,
    versions,
    mixedVersions: versions.length > 1,
  }
}

/** The most recent point, or null when nothing is plottable. */
export function latestPoint(series: TrendSeries): TrendPoint | null {
  return series.points.length ? series.points[series.points.length - 1] : null
}

/** The point before the most recent one, or null when there is only one. */
export function previousPoint(series: TrendSeries): TrendPoint | null {
  return series.points.length > 1 ? series.points[series.points.length - 2] : null
}

/**
 * Whether anything at all is being shown.
 *
 * The page uses this to choose between "no data yet" and "data exists but none
 * of it is a measurement", which are different messages.
 */
export function hasPlottablePoints(series: TrendSeries): boolean {
  return series.points.length > 0
}
