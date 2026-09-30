/**
 * Tests for the follow-up trend builder.
 *
 * Run with:  npm run test:rules      (Node >= 22.6, no extra dependencies)
 *
 * These tests exist because the failure mode is silent and dishonest: a seeded
 * demo row or a scripted self-test sitting in the same table as a patient's own
 * session would be plotted as if the patient had produced it, and nothing on
 * screen would look wrong.
 */

import assert from 'node:assert/strict'
import test from 'node:test'

import {
  buildTrendSeries,
  hasPlottablePoints,
  HUMAN_SOURCE,
  isMeasuredRow,
  latestPoint,
  previousPoint,
  type TrendRowInput,
} from '../src/followup/trends.ts'

const human = (at: string, value: number | null, version = 'v1'): TrendRowInput => ({
  at,
  value,
  source: HUMAN_SOURCE,
  version,
})

test('only human rows become points', () => {
  const series = buildTrendSeries([
    human('2026-01-01T10:00:00Z', 1.5),
    { at: '2026-01-02T10:00:00Z', value: 9.9, source: 'SEED_DEMO', version: 'v1' },
    { at: '2026-01-03T10:00:00Z', value: 8.8, source: 'SYNTHETIC_SELFTEST', version: 'v1' },
    human('2026-01-04T10:00:00Z', 1.7),
  ])

  assert.equal(series.points.length, 2)
  assert.deepEqual(
    series.points.map((p) => p.value),
    [1.5, 1.7],
  )
  assert.equal(series.excludedNonHuman, 2)
})

test('an unknown source is not treated as human', () => {
  assert.equal(isMeasuredRow('HUMAN_KEYBOARD'), true)
  assert.equal(isMeasuredRow('SEED_DEMO'), false)
  assert.equal(isMeasuredRow(null), false)
  assert.equal(isMeasuredRow(undefined), false)
  // A source added later must not be assumed to be a measurement.
  assert.equal(isMeasuredRow('SOMETHING_NEW'), false)
})

test('rows with no value for this metric are skipped, not plotted as zero', () => {
  const series = buildTrendSeries([
    human('2026-01-01T10:00:00Z', 1.5),
    human('2026-01-02T10:00:00Z', null),
  ])

  assert.equal(series.points.length, 1)
  assert.equal(series.skippedMissingValue, 1)
  assert.equal(series.points[0].value, 1.5)
})

test('non-finite values are skipped', () => {
  const series = buildTrendSeries([
    human('2026-01-01T10:00:00Z', Number.NaN),
    human('2026-01-02T10:00:00Z', Number.POSITIVE_INFINITY),
  ])

  assert.equal(series.points.length, 0)
  assert.equal(series.skippedMissingValue, 2)
})

test('rows without a timestamp are dropped and counted', () => {
  const series = buildTrendSeries([
    human('2026-01-01T10:00:00Z', 1.5),
    { at: null, value: 2.5, source: HUMAN_SOURCE, version: 'v1' },
  ])

  assert.equal(series.points.length, 1)
  assert.equal(series.skippedNoTimestamp, 1)
})

test('points come out oldest first regardless of input order', () => {
  const series = buildTrendSeries([
    human('2026-03-01T10:00:00Z', 3),
    human('2026-01-01T10:00:00Z', 1),
    human('2026-02-01T10:00:00Z', 2),
  ])

  assert.deepEqual(
    series.points.map((p) => p.value),
    [1, 2, 3],
  )
})

test('a single version is reported without the mixed flag', () => {
  const series = buildTrendSeries([
    human('2026-01-01T10:00:00Z', 1, 'piano-metrics-v1'),
    human('2026-02-01T10:00:00Z', 2, 'piano-metrics-v1'),
  ])

  assert.deepEqual(series.versions, ['piano-metrics-v1'])
  assert.equal(series.mixedVersions, false)
})

test('points from two versions are flagged as mixed', () => {
  const series = buildTrendSeries([
    human('2026-01-01T10:00:00Z', 1, 'piano-metrics-v1'),
    human('2026-02-01T10:00:00Z', 2, 'piano-metrics-v2'),
  ])

  assert.deepEqual(series.versions, ['piano-metrics-v1', 'piano-metrics-v2'])
  assert.equal(series.mixedVersions, true)
})

test('an unversioned point neither hides nor invents a version', () => {
  // `version: null`, not `undefined`: the `human` helper defaults the parameter,
  // so passing undefined would quietly supply 'v1' and test nothing.
  const unversioned: TrendRowInput = {
    at: '2026-01-01T10:00:00Z',
    value: 1,
    source: HUMAN_SOURCE,
    version: null,
  }

  const onlyUnversioned = buildTrendSeries([unversioned])
  assert.deepEqual(onlyUnversioned.versions, [])
  assert.equal(onlyUnversioned.mixedVersions, false)
  assert.equal(onlyUnversioned.points[0].version, null)

  // One versioned plus one unversioned is not "one version": the caller cannot
  // claim all points came from the same algorithm.
  const mixed = buildTrendSeries([unversioned, human('2026-02-01T10:00:00Z', 2, 'piano-metrics-v1')])
  assert.deepEqual(mixed.versions, ['piano-metrics-v1'])
  assert.equal(mixed.mixedVersions, false)
  assert.equal(mixed.points[0].version, null)
  assert.equal(mixed.points[1].version, 'piano-metrics-v1')
})

test('the version list keeps first-seen order and does not repeat', () => {
  const series = buildTrendSeries([
    human('2026-01-01T10:00:00Z', 1, 'b'),
    human('2026-02-01T10:00:00Z', 2, 'a'),
    human('2026-03-01T10:00:00Z', 3, 'b'),
  ])

  assert.deepEqual(series.versions, ['b', 'a'])
})

test('latest and previous read the ends of the series', () => {
  const series = buildTrendSeries([
    human('2026-01-01T10:00:00Z', 1),
    human('2026-02-01T10:00:00Z', 2),
  ])

  assert.equal(latestPoint(series)?.value, 2)
  assert.equal(previousPoint(series)?.value, 1)
})

test('a single point has no previous, and nothing has no latest', () => {
  const one = buildTrendSeries([human('2026-01-01T10:00:00Z', 1)])
  assert.equal(latestPoint(one)?.value, 1)
  assert.equal(previousPoint(one), null)

  const none = buildTrendSeries([])
  assert.equal(latestPoint(none), null)
  assert.equal(previousPoint(none), null)
  assert.equal(hasPlottablePoints(none), false)
})

test('an empty input produces an empty but well-formed series', () => {
  const series = buildTrendSeries([])
  assert.deepEqual(series.points, [])
  assert.equal(series.excludedNonHuman, 0)
  assert.equal(series.skippedMissingValue, 0)
  assert.equal(series.skippedNoTimestamp, 0)
  assert.equal(series.mixedVersions, false)
})

test('every excluded row is accounted for', () => {
  const rows: TrendRowInput[] = [
    human('2026-01-01T10:00:00Z', 1),
    { at: '2026-01-02T10:00:00Z', value: 2, source: 'SEED_DEMO', version: 'v1' },
    human('2026-01-03T10:00:00Z', null),
    { at: null, value: 4, source: HUMAN_SOURCE, version: 'v1' },
  ]
  const series = buildTrendSeries(rows)

  const accounted =
    series.points.length +
    series.excludedNonHuman +
    series.skippedMissingValue +
    series.skippedNoTimestamp
  assert.equal(accounted, rows.length)
})
