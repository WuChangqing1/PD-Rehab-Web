/**
 * Tests for the trend chart's option builder.
 *
 * Run with:  npm run test:rules
 *
 * The property under test is the one a screenshot cannot prove: points from two
 * algorithm versions are never merged into a single line, and a lone measurement
 * is never drawn as a line.
 */

import assert from 'node:assert/strict'
import test from 'node:test'

import {
  buildTrendOption,
  formatTrendValue,
  UNVERSIONED_LABEL,
} from '../src/followup/trendOption.ts'
import type { TrendPoint } from '../src/followup/trends.ts'

const point = (at: string, value: number, version: string | null = 'v1'): TrendPoint => ({
  at,
  value,
  version,
})

test('one version produces one series', () => {
  const option = buildTrendOption([
    point('2026-01-01T10:00:00Z', 1),
    point('2026-02-01T10:00:00Z', 2),
  ])

  assert.equal(option.series.length, 1)
  assert.equal(option.multiVersion, false)
  assert.equal(option.series[0].name, 'v1')
  assert.deepEqual(option.series[0].data, [
    ['2026-01-01T10:00:00Z', 1],
    ['2026-02-01T10:00:00Z', 2],
  ])
})

test('two versions are never joined into one line', () => {
  const option = buildTrendOption([
    point('2026-01-01T10:00:00Z', 1, 'metrics-v1'),
    point('2026-02-01T10:00:00Z', 2, 'metrics-v2'),
    point('2026-03-01T10:00:00Z', 3, 'metrics-v1'),
  ])

  assert.equal(option.series.length, 2)
  assert.equal(option.multiVersion, true)
  const byName = Object.fromEntries(option.series.map((s) => [s.name, s.data]))
  assert.deepEqual(byName['metrics-v1'], [
    ['2026-01-01T10:00:00Z', 1],
    ['2026-03-01T10:00:00Z', 3],
  ])
  assert.deepEqual(byName['metrics-v2'], [['2026-02-01T10:00:00Z', 2]])
})

test('an unversioned point gets its own labelled series, not the first version', () => {
  const option = buildTrendOption([
    point('2026-01-01T10:00:00Z', 1, null),
    point('2026-02-01T10:00:00Z', 2, 'metrics-v1'),
  ])

  assert.equal(option.series.length, 2)
  assert.equal(option.multiVersion, true)
  const names = option.series.map((s) => s.name)
  assert.ok(names.includes(UNVERSIONED_LABEL))
  assert.ok(names.includes('metrics-v1'))
})

test('a single point stays a single-element series', () => {
  const option = buildTrendOption([point('2026-01-01T10:00:00Z', 1.5)])

  assert.equal(option.series.length, 1)
  assert.equal(option.series[0].data.length, 1)
  assert.equal(option.multiVersion, false)
})

test('no points produce no series rather than an empty one', () => {
  const option = buildTrendOption([])
  assert.deepEqual(option.series, [])
  assert.equal(option.multiVersion, false)
})

test('series keep first-seen version order', () => {
  const option = buildTrendOption([
    point('2026-01-01T10:00:00Z', 1, 'b'),
    point('2026-02-01T10:00:00Z', 2, 'a'),
    point('2026-03-01T10:00:00Z', 3, 'b'),
  ])

  assert.deepEqual(
    option.series.map((s) => s.name),
    ['b', 'a'],
  )
})

test('values are formatted per unit', () => {
  assert.equal(formatTrendValue(0.7325, 'ratio'), '73.3%')
  assert.equal(formatTrendValue(412.34, 'ms'), '412.3 ms')
  assert.equal(formatTrendValue(5.6, 'count'), '6 次')
  assert.equal(formatTrendValue(3.456, 'sec'), '3.46 s')
  assert.equal(formatTrendValue(88.24, 'deg'), '88.2°')
  assert.equal(formatTrendValue(1.2345, 'number'), '1.234')
})

test('a non-finite value is labelled, not rendered as a number', () => {
  assert.equal(formatTrendValue(Number.NaN, 'ratio'), '暂无数据')
  assert.equal(formatTrendValue(Number.POSITIVE_INFINITY, 'ms'), '暂无数据')
})
