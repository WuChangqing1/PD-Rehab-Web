/**
 * Tests for the per-exercise result card profile.
 *
 * Run with:  npm run test:rules
 *
 * The bug these lock down: the result cards were a hardcoded list whose second
 * card always read `left_shoulder_max_angle_deg`. On Tendu and Demi-Plié -- leg
 * exercises -- that showed a reader shoulder angles and buried the number they
 * wanted in the collapsed table. The fix derives the cards from the drive joint
 * the backend declares per exercise.
 *
 * The critical test here is the wire-value one. The backend's Python constants
 * are NAMED DRIVE_SHOULDER / DRIVE_HIP / ... but their VALUES are
 * "shoulder_abduction" / "hip_abduction" / ... . An earlier draft of this module
 * compared against the names, matched nothing, and silently fell back to the
 * shoulder profile for every exercise -- reproducing the original bug exactly.
 * So the names and values are checked against the backend source rather than
 * trusted.
 */

import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { fileURLToPath } from 'node:url'
import { dirname, join } from 'node:path'
import test from 'node:test'

import {
  DRIVE,
  METRIC,
  metricCardCount,
  normaliseDriveSeries,
  resultCardsFor,
  surfacedMetrics,
} from '../src/pose/resultProfile.ts'

const HERE = dirname(fileURLToPath(import.meta.url))
const BACKEND_EXERCISES = join(HERE, '..', '..', 'backend', 'app', 'ml', 'pose', 'exercises.py')

// --------------------------------------------------------- the wire contract

test('drive values match the backend constants they come from', () => {
  const src = readFileSync(BACKEND_EXERCISES, 'utf8')

  // Parse `DRIVE_X = "value"` out of the Python source.
  const declared: Record<string, string> = {}
  for (const m of src.matchAll(/^(DRIVE_\w+)\s*=\s*"([^"]+)"/gm)) {
    declared[m[1]] = m[2]
  }

  assert.ok(Object.keys(declared).length >= 4, 'expected the DRIVE_ constants to be found')

  assert.equal(DRIVE.SHOULDER, declared.DRIVE_SHOULDER)
  assert.equal(DRIVE.HIP, declared.DRIVE_HIP)
  assert.equal(DRIVE.KNEE, declared.DRIVE_KNEE)
  assert.equal(DRIVE.TRUNK_TILT, declared.DRIVE_TRUNK_TILT)
})

test('the drive values are not accidentally the constant names', () => {
  // Guards the exact mistake described in the module header.
  for (const value of Object.values(DRIVE)) {
    assert.ok(!value.startsWith('DRIVE_'), `${value} looks like a constant name, not a wire value`)
  }
})

test('every drive value the catalogue uses is handled', () => {
  const src = readFileSync(BACKEND_EXERCISES, 'utf8')
  const used = [...src.matchAll(/drive_series=(DRIVE_\w+)/g)].map((m) => m[1])
  assert.ok(used.length >= 5, 'expected drive_series on every exercise')

  const declared: Record<string, string> = {}
  for (const m of src.matchAll(/^(DRIVE_\w+)\s*=\s*"([^"]+)"/gm)) declared[m[1]] = m[2]

  const known = new Set<string>(Object.values(DRIVE))
  for (const constant of used) {
    const wire = declared[constant]
    assert.ok(known.has(wire), `no profile for ${constant} = "${wire}"`)
  }
})

// ------------------------------------------------------------ card contents

test('a leg exercise no longer shows shoulder angles', () => {
  const cards = resultCardsFor(DRIVE.HIP)
  const shoulder = surfacedMetrics().filter((m) => m.includes('shoulder'))
  for (const metric of shoulder) {
    assert.equal(metricCardCount(cards, metric), 0, `hip exercise shows ${metric}`)
  }
  assert.equal(cards[1].label, '腿部外展角度')
  assert.deepEqual(cards[1].metrics, [METRIC.hipLeft, METRIC.hipRight])
})

test('a knee exercise shows knee angles', () => {
  const cards = resultCardsFor(DRIVE.KNEE)
  assert.equal(cards[1].label, '屈膝角度')
  assert.deepEqual(cards[1].metrics, [METRIC.kneeLeft, METRIC.kneeRight])
})

test('an arm exercise still shows shoulder angles', () => {
  const cards = resultCardsFor(DRIVE.SHOULDER)
  assert.equal(cards[1].label, '抬臂角度')
  assert.deepEqual(cards[1].metrics, [METRIC.shoulderLeft, METRIC.shoulderRight])
})

test('a trunk exercise shows the trunk angle', () => {
  const cards = resultCardsFor(DRIVE.TRUNK_TILT)
  assert.equal(cards[1].label, '躯干倾角')
  assert.deepEqual(cards[1].metrics, [METRIC.trunk])
})

test('repetition count is always the first card', () => {
  for (const drive of Object.values(DRIVE)) {
    const cards = resultCardsFor(drive)
    assert.equal(cards[0].label, '完成次数')
    assert.deepEqual(cards[0].metrics, [METRIC.repetitions])
  }
})

test('no metric is presented under two different labels', () => {
  for (const drive of Object.values(DRIVE)) {
    const cards = resultCardsFor(drive)
    const seen = new Set()
    for (const card of cards) {
      for (const metric of card.metrics) {
        assert.ok(!seen.has(metric), `${metric} appears on two cards for ${drive}`)
        seen.add(metric)
      }
    }
  }
})

test('a pair card names exactly two metrics and a single card exactly one', () => {
  for (const drive of Object.values(DRIVE)) {
    for (const card of resultCardsFor(drive)) {
      const expected = card.shape === 'pair' ? 2 : 1
      assert.equal(card.metrics.length, expected, `${card.label} has the wrong metric count`)
    }
  }
})

test('every card carries a note explaining what the number is', () => {
  for (const drive of Object.values(DRIVE)) {
    for (const card of resultCardsFor(drive)) {
      assert.ok(card.note.length > 0, `${card.label} has no note`)
    }
  }
})

// ------------------------------------------------------------- unknown input

test('an unknown or missing drive falls back to the shoulder profile', () => {
  // What an older API response, or a retired exercise, would produce.
  const fallback = resultCardsFor(null).map((c) => c.label)
  assert.deepEqual(fallback, resultCardsFor(DRIVE.SHOULDER).map((c) => c.label))
  assert.deepEqual(resultCardsFor(undefined).map((c) => c.label), fallback)
  assert.deepEqual(resultCardsFor('not_a_real_drive').map((c) => c.label), fallback)
  // The previous hardcoded list was the shoulder one, so behaviour is unchanged
  // for the exercises it was actually right about.
  assert.equal(fallback[1], '抬臂角度')
})

test('normaliseDriveSeries accepts only known values', () => {
  assert.equal(normaliseDriveSeries(DRIVE.KNEE), DRIVE.KNEE)
  assert.equal(normaliseDriveSeries('DRIVE_KNEE'), DRIVE.SHOULDER)
  assert.equal(normaliseDriveSeries(''), DRIVE.SHOULDER)
  assert.equal(normaliseDriveSeries(null), DRIVE.SHOULDER)
})

// ------------------------------------------------------- metric key sanity

test('the metric keys are the ones the backend emits', () => {
  const src = readFileSync(BACKEND_EXERCISES, 'utf8')
  // The declared raw metric lists, common plus leg.
  const declaredMetrics = new Set([...src.matchAll(/"([a-z_]+_(?:deg|sec|ms|ratio|count))"/g)].map((m) => m[1]))
  for (const metric of surfacedMetrics()) {
    assert.ok(
      declaredMetrics.has(metric),
      `${metric} is surfaced by a card but is not a backend raw metric`,
    )
  }
})
