/**
 * Tests for the demonstration-asset gate.
 *
 * Run with:  npm run test:rules
 *
 * The rule being protected: a demonstration video may only reach a patient after
 * BOTH its licence is verified AND a human has watched it and approved the
 * movement. The temptation this guards against is real and specific -- a clip did
 * download, and the easy thing to do would be to wire it up and call the feature
 * finished. It was watched and rejected instead (no chair, turned-out feet, too
 * deep), so these tests assert that the registry still refuses to publish
 * anything, and that flipping a flag without the review behind it breaks the
 * build.
 */

import assert from 'node:assert/strict'
import test from 'node:test'

import {
  FALLBACK_LABELS,
  allEntries,
  findEntry,
  isPublishable,
  publishableEntries,
  resolveDemo,
  reviewNotes,
  type DemoAssetEntry,
} from '../src/ballet/demoAssets.ts'

// The catalogue, mirrored from backend/app/ml/pose/exercises.py.
const EXERCISES = [
  'BALLET_PORT_DE_BRAS',
  'BALLET_FIRST_POSITION',
  'BALLET_TENDU',
  'BALLET_DEMI_PLIE',
  'BALLET_WEIGHT_SHIFT',
]

// ------------------------------------------------------- the gate itself

test('nothing in the registry is publishable today', () => {
  // This is the honest state: no clip has passed both gates. If a future edit
  // makes this fail, the edit must come with a real review record.
  assert.deepEqual(publishableEntries(), [])
})

test('both gates are required, independently', () => {
  const base: DemoAssetEntry = {
    exercise_key: 'BALLET_TENDU',
    execution_mode: 'STANDING_SUPPORTED',
    status: 'QA_PASSED',
    source_id: 'SRC-X',
    license_verified: true,
    movement_reviewed: true,
    poster_path: 'p.webp',
    video_path: 'v.mp4',
    duration_sec: 6,
    demonstration_version: 'v1',
    notes: '',
  }

  assert.equal(isPublishable(base), true, 'both gates plus files should publish')

  // Each gate alone is not enough.
  assert.equal(isPublishable({ ...base, license_verified: false }), false)
  assert.equal(isPublishable({ ...base, movement_reviewed: false }), false)

  // Gates met but nothing to play.
  assert.equal(isPublishable({ ...base, video_path: null }), false)

  // A late status is not a substitute for the gates.
  assert.equal(
    isPublishable({ ...base, license_verified: false, movement_reviewed: false, status: 'PUBLISHED' }),
    false,
  )

  // Nor is an early status enough even with the gates claimed.
  assert.equal(isPublishable({ ...base, status: 'CLIP_REVIEWED' }), false)
  assert.equal(isPublishable({ ...base, status: 'DOWNLOADED' }), false)
})

test('a rejected clip never resolves to a video', () => {
  // The specific clip that downloaded and was watched.
  const resolved = resolveDemo('BALLET_DEMI_PLIE', 'STANDING_SUPPORTED')
  assert.equal(resolved.kind, 'DIAGRAM')
  assert.equal(resolved.kind === 'DIAGRAM' && resolved.reason, 'REJECTED')
})

test('the rejected clip keeps its reasons on record', () => {
  const reasons = reviewNotes('BALLET_DEMI_PLIE', 'STANDING_SUPPORTED')
  assert.ok(reasons.length >= 3, 'a rejection must say why, not just that it failed')
  const joined = reasons.join(' ')
  // The three safety mismatches that caused the rejection.
  assert.match(joined, /椅|chair/i, 'the missing chair must be recorded')
  assert.match(joined, /外旋|turnout|turn-out/i, 'the turnout must be recorded')
  assert.match(joined, /幅度|bend|深/, 'the bend depth must be recorded')
})

// ------------------------------------------------------- every combination

test('every exercise and mode resolves to something, never to nothing', () => {
  const modes = ['SEATED', 'STANDING_SUPPORTED']
  for (const key of EXERCISES) {
    for (const mode of modes) {
      // Demi-Plié has no seated variant, so it is absent by design.
      if (key === 'BALLET_DEMI_PLIE' && mode === 'SEATED') continue
      const resolved = resolveDemo(key, mode)
      assert.ok(resolved.kind === 'DIAGRAM' || resolved.kind === 'VIDEO')
      if (resolved.kind === 'DIAGRAM') {
        assert.ok(resolved.note.length > 0, `${key}/${mode} has no explanation`)
        assert.ok(FALLBACK_LABELS[resolved.reason], `${key}/${mode} has no label`)
      }
    }
  }
})

test('Demi-Plié is supported standing only', () => {
  // Mirrors the backend constraint. A seated variant must not be invented by the
  // registry just to make the grid look symmetric.
  assert.equal(findEntry('BALLET_DEMI_PLIE', 'SEATED'), null)
  assert.ok(findEntry('BALLET_DEMI_PLIE', 'STANDING_SUPPORTED'))
})

test('an unknown exercise resolves to a labelled fallback rather than throwing', () => {
  const resolved = resolveDemo('BALLET_DOES_NOT_EXIST', 'SEATED')
  assert.equal(resolved.kind, 'DIAGRAM')
  assert.equal(resolved.kind === 'DIAGRAM' && resolved.reason, 'NOT_SELECTED')
})

// --------------------------------------------------------- review integrity

test('a candidate that was never watched is not treated as reviewed', () => {
  const tendu = findEntry('BALLET_TENDU', 'STANDING_SUPPORTED')
  assert.ok(tendu)
  assert.equal(tendu?.license_verified, true, 'the licence was checkable from the source page')
  assert.equal(tendu?.movement_reviewed, false, 'the download was blocked, so it was never watched')

  const resolved = resolveDemo('BALLET_TENDU', 'STANDING_SUPPORTED')
  assert.equal(resolved.kind, 'DIAGRAM')
  assert.equal(resolved.kind === 'DIAGRAM' && resolved.reason, 'AWAITING_REVIEW')
})

test('every registry entry carries an explanatory note', () => {
  for (const entry of allEntries()) {
    assert.ok(
      entry.notes && entry.notes.length > 10,
      `${entry.exercise_key}/${entry.execution_mode} has no note`,
    )
  }
})

test('the registry covers the catalogue without inventing combinations', () => {
  const keys = new Set(allEntries().map((e) => e.exercise_key))
  for (const key of EXERCISES) {
    assert.ok(keys.has(key), `${key} is in the catalogue but not in the registry`)
  }
  for (const key of keys) {
    assert.ok(EXERCISES.includes(key), `${key} is in the registry but not in the catalogue`)
  }
})

test('no entry claims a file path without the reviews behind it', () => {
  // The specific inconsistency that would make a broken <video> appear.
  for (const entry of allEntries()) {
    if (entry.video_path) {
      assert.ok(
        entry.license_verified && entry.movement_reviewed,
        `${entry.exercise_key}/${entry.execution_mode} has a video path but no review`,
      )
    }
  }
})

import { illustrationPath } from '../src/ballet/illustrations.ts'
import { existsSync } from 'node:fs'
test('all nine supported exercise modes have a distinct bundled AI illustration', () => {
  const paths = new Set<string>()
  for (const entry of allEntries()) {
    const path = illustrationPath(entry.exercise_key, entry.execution_mode)
    assert.ok(path)
    assert.ok(existsSync(new URL('../public/' + path, import.meta.url)), path)
    paths.add(path)
  }
  assert.equal(paths.size, 9)
  assert.equal(illustrationPath('BALLET_DEMI_PLIE', 'SEATED'), null)
  assert.equal(illustrationPath('UNKNOWN', 'SEATED'), null)
})
