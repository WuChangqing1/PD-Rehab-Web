/**
 * Tests for the piano training recipes.
 *
 * Run with:  npm run test:rules
 *
 * The requirement these protect is that a recipe must be a real practice with its
 * own interaction and its own data, not a renamed card. `docs/05` asks for four
 * recipes and warns specifically against the failure mode where four cards differ
 * only by title, so the tests below check the behaviour of each cue policy rather
 * than the existence of a label.
 *
 * The sharpest of them is the CFT latency rule. When the cue is withdrawn there is
 * no cue onset, so `response_latency_ms` must be null; filling it in from the
 * target time would report a reaction to something the patient never saw. That is
 * an easy mistake to make and an invisible one in the UI, which is why it is
 * pinned here rather than trusted.
 */

import assert from 'node:assert/strict'
import test from 'node:test'

import {
  DEFAULT_DIFFICULTY,
  generateCues,
  resolveCue,
  type DifficultyConfig,
  type PressInput,
} from '../src/piano/session.ts'
import {
  RECIPES,
  RECIPE_BY_ID,
  RECIPE_GROUPS,
  applyRecipe,
  answerableCues,
  cueIsVisible,
  isRecipeId,
  recipeEventFields,
  recipesInGroup,
  splitCuedAndFree,
  type RecipeId,
} from '../src/piano/recipes.ts'
import { BINDING_BY_MIDI, KEY_BINDINGS } from '../src/piano/samples.ts'

const DIFFICULTY: DifficultyConfig = {
  ...DEFAULT_DIFFICULTY,
  bpm: 60,
  session_duration_sec: 30,
  note_density: 1,
  judgement_window_ms: 300,
}

/** A press that lands exactly on a cue's target. */
function pressOn(midi: number, atMs: number, code?: string): PressInput {
  const binding = Object.values(BINDING_BY_MIDI).find((b) => b.midi === midi)
  return {
    code: code ?? binding?.code ?? `POINTER:${midi}`,
    midi,
    downTimeMs: atMs,
    upTimeMs: atMs + 80,
    relativeDownMs: atMs,
    relativeUpMs: atMs + 80,
  }
}

function cuesFor(id: RecipeId, overrides: Partial<DifficultyConfig> = {}) {
  const recipe = RECIPE_BY_ID[id]
  const difficulty = { ...DIFFICULTY, ...overrides }
  const base = generateCues(recipe.baseMode, difficulty, { seed: 7 })
  return { recipe, difficulty, cues: applyRecipe(recipe, base, difficulty, { seed: 7 }) }
}

// ------------------------------------------------------------- registry shape

test('every recipe reuses an existing mode rather than defining a new engine', () => {
  const modes = new Set(['SINGLE_KEY_RHYTHM', 'ALTERNATING_HANDS', 'MAPPED_SEQUENCE', 'FOLLOW_THE_BEAT', 'MEMORY_RHYTHM'])
  for (const recipe of RECIPES) {
    assert.ok(modes.has(recipe.baseMode), `${recipe.id} uses an unknown base mode`)
    assert.ok(recipe.algorithmVersion.length > 0)
  }
})

test('every recipe is grouped and the groups are all populated', () => {
  for (const { group } of RECIPE_GROUPS) {
    assert.ok(recipesInGroup(group).length > 0, `group ${group} is empty`)
  }
  const grouped = RECIPE_GROUPS.flatMap((g) => recipesInGroup(g.group))
  assert.equal(grouped.length, RECIPES.length)
})

test('each recipe states a concrete behaviour and a real output', () => {
  for (const recipe of RECIPES) {
    assert.ok(recipe.summary.length >= 10, `${recipe.id} has no usable summary`)
    assert.ok(recipe.produces.length > 0, `${recipe.id} does not say what it measures`)
  }
  // Four distinct summaries: the cards must not read as four copies.
  assert.equal(new Set(RECIPES.map((r) => r.summary)).size, RECIPES.length)
  assert.equal(new Set(RECIPES.map((r) => r.label)).size, RECIPES.length)
})

test('isRecipeId accepts the registry and rejects anything else', () => {
  assert.ok(isRecipeId('SFT_CUE_SYNC'))
  assert.ok(!isRecipeId('NOT_A_RECIPE'))
  assert.ok(!isRecipeId(''))
})

// ------------------------------------------------------------------- SFT

test('SFT keeps a cue visible for every target', () => {
  const { cues } = cuesFor('SFT_CUE_SYNC')
  assert.ok(cues.length > 4)
  for (const cue of cues) {
    assert.equal(cueIsVisible(cue), true)
    assert.equal(cue.recipeId, 'SFT_CUE_SYNC')
  }
})

test('SFT records a latency for a press on the beat', () => {
  const { cues, difficulty } = cuesFor('SFT_CUE_SYNC')
  const cue = cues[0]
  const rows = resolveCue(cue, [pressOn(cue.binding.midi, cue.targetMs)], difficulty.judgement_window_ms)
  const answered = rows.find((r) => r.is_correct)
  assert.ok(answered)
  assert.equal(answered?.timing_error_ms, 0)
  // Latency is measured from the cue appearing, which is APPROACH_MS earlier.
  assert.ok((answered?.response_latency_ms ?? 0) > 0)
})

// ------------------------------------------------------------------- CFT

test('CFT removes the cue after the warm-up beats', () => {
  const { cues, recipe } = cuesFor('CFT_RHYTHM_HOLD')
  const { cued, free } = splitCuedAndFree(cues)

  assert.ok(cued.length > 0, 'CFT must start with cues to follow')
  assert.ok(free.length > 0, 'CFT must withdraw the cue at some point')

  // The warm-up is a duration, not a count: at 60 bpm, 8 beats is 8 seconds.
  const beatMs = 60000 / DIFFICULTY.bpm
  const expected = (recipe.promptBeats ?? 8) * beatMs
  const span = cued[cued.length - 1].targetMs - cues[0].targetMs
  assert.ok(
    Math.abs(span - expected) < beatMs,
    `warm-up spanned ${Math.round(span)}ms, expected about ${Math.round(expected)}ms`,
  )
})

test('CFT leaves response latency null once the cue is gone', () => {
  // The rule from docs/05. There is no cue onset, so there is nothing to be
  // latent from; timing error survives because the beat is still defined.
  const { cues, difficulty } = cuesFor('CFT_RHYTHM_HOLD')
  const { free } = splitCuedAndFree(cues)
  assert.ok(free.length > 0)

  for (const cue of free.slice(0, 5)) {
    const rows = resolveCue(cue, [pressOn(cue.binding.midi, cue.targetMs)], difficulty.judgement_window_ms)
    const answered = rows.find((r) => r.is_correct)
    assert.ok(answered, 'the press should still count as correct')
    assert.equal(answered?.response_latency_ms, null, 'latency must not be invented')
    assert.equal(answered?.cue_onset_time_ms, null, 'a removed cue has no onset')
    assert.equal(answered?.timing_error_ms, 0, 'timing error is still meaningful')
    assert.equal(answered?.target_time_ms, cue.targetMs, 'the beat is still the target')
  }
})

test('CFT still reports latency during the cued warm-up', () => {
  const { cues, difficulty } = cuesFor('CFT_RHYTHM_HOLD')
  const { cued } = splitCuedAndFree(cues)
  const cue = cued[0]
  const rows = resolveCue(cue, [pressOn(cue.binding.midi, cue.targetMs)], difficulty.judgement_window_ms)
  const answered = rows.find((r) => r.is_correct)
  assert.notEqual(answered?.response_latency_ms, null)
})

test('CFT counts a missed free beat as a miss, not as perfect timing', () => {
  const { cues, difficulty } = cuesFor('CFT_RHYTHM_HOLD')
  const { free } = splitCuedAndFree(cues)
  const rows = resolveCue(free[0], [], difficulty.judgement_window_ms)
  assert.equal(rows.length, 1)
  assert.equal(rows[0].is_missed, true)
  assert.equal(rows[0].timing_error_ms, null)
  assert.equal(rows[0].response_latency_ms, null)
})

// -------------------------------------------------------------- BIMANUAL

test('BIMANUAL asks for one key in each hand on every cue', () => {
  const { cues } = cuesFor('BIMANUAL_SYNC')
  assert.ok(cues.length > 0)
  for (const cue of cues) {
    assert.ok(cue.secondaryBinding, 'a bimanual cue must name a second key')
    assert.notEqual(cue.binding.hand, cue.secondaryBinding?.hand, 'the pair must span both hands')
    assert.notEqual(cue.binding.midi, cue.secondaryBinding?.midi)
  }
})

test('BIMANUAL measures the gap between the two hands', () => {
  const { cues, difficulty } = cuesFor('BIMANUAL_SYNC')
  const cue = cues[0]
  const second = cue.secondaryBinding
  assert.ok(second)

  const rows = resolveCue(
    cue,
    [pressOn(cue.binding.midi, cue.targetMs), pressOn(second.midi, cue.targetMs + 45)],
    difficulty.judgement_window_ms,
  )
  const correct = rows.filter((r) => r.is_correct)
  assert.equal(correct.length, 2, 'both hands must produce a row')
  assert.equal(correct[0].inter_hand_onset_diff_ms, 45)
  assert.equal(correct[1].inter_hand_onset_diff_ms, 45, 'the gap is on both rows')
  assert.equal(correct[0].pair_role, 'PRIMARY')
  assert.equal(correct[1].pair_role, 'SECONDARY')
})

test('BIMANUAL reports a missing hand as a miss, never as perfect synchrony', () => {
  const { cues, difficulty } = cuesFor('BIMANUAL_SYNC')
  const cue = cues[0]
  const rows = resolveCue(cue, [pressOn(cue.binding.midi, cue.targetMs)], difficulty.judgement_window_ms)

  const primary = rows.find((r) => r.pair_role === 'PRIMARY')
  const secondary = rows.find((r) => r.pair_role === 'SECONDARY')
  assert.ok(primary && secondary)
  assert.equal(secondary.is_missed, true)
  assert.equal(secondary.inter_hand_onset_diff_ms, null)
  // The hand that arrived has no partner, so it has no synchrony value either.
  assert.equal(primary.inter_hand_onset_diff_ms, null)
})

test('BIMANUAL accepts a tap inside the judgement window as simultaneous', () => {
  const { cues, difficulty } = cuesFor('BIMANUAL_SYNC')
  const cue = cues[0]
  const second = cue.secondaryBinding
  assert.ok(second)
  const rows = resolveCue(
    cue,
    [pressOn(cue.binding.midi, cue.targetMs), pressOn(second.midi, cue.targetMs - 40)],
    difficulty.judgement_window_ms,
  )
  const correct = rows.filter((r) => r.is_correct)
  assert.equal(correct.length, 2)
  assert.equal(correct[0].inter_hand_onset_diff_ms, 40)
})

test('BIMANUAL keeps the single-key metrics meaningful', () => {
  // Primary rows still carry latency and timing error, so an existing report does
  // not become empty just because the recipe is new.
  const { cues, difficulty } = cuesFor('BIMANUAL_SYNC')
  const cue = cues[0]
  const second = cue.secondaryBinding
  assert.ok(second)
  const rows = resolveCue(
    cue,
    [pressOn(cue.binding.midi, cue.targetMs + 20), pressOn(second.midi, cue.targetMs + 60)],
    difficulty.judgement_window_ms,
  )
  const primary = rows.find((r) => r.pair_role === 'PRIMARY')
  assert.equal(primary?.timing_error_ms, 20)
  assert.notEqual(primary?.response_latency_ms, null)
})

// ------------------------------------------------------------------ ACCENT

test('ACCENT groups beats into bars and accents the first of each', () => {
  const { cues } = cuesFor('ACCENT_GROUPING')
  assert.ok(cues.length >= 8)

  cues.forEach((cue, i) => {
    const expectedBeat = (i % 4) + 1
    assert.equal(cue.beatInBar, expectedBeat, `cue ${i} has the wrong beat in bar`)
    assert.equal(cue.accent, expectedBeat === 1, `cue ${i} accent flag is wrong`)
  })
})

test('ACCENT produces one accent per bar', () => {
  const { cues } = cuesFor('ACCENT_GROUPING')
  const accents = cues.filter((c) => c.accent)
  assert.equal(accents.length, Math.ceil(cues.length / 4))
})

test('ACCENT carries the grouping into the recorded rows', () => {
  const { cues, difficulty } = cuesFor('ACCENT_GROUPING')
  const accented = cues.find((c) => c.accent)
  const plain = cues.find((c) => !c.accent)
  assert.ok(accented && plain)

  const accentRow = resolveCue(accented, [pressOn(accented.binding.midi, accented.targetMs)], difficulty.judgement_window_ms).find((r) => r.is_correct)
  const plainRow = resolveCue(plain, [pressOn(plain.binding.midi, plain.targetMs)], difficulty.judgement_window_ms).find((r) => r.is_correct)

  assert.equal(accentRow?.is_accent, true)
  assert.equal(accentRow?.beat_in_bar, 1)
  assert.equal(plainRow?.is_accent, false)
  assert.ok((plainRow?.beat_in_bar ?? 0) > 1)
})

// ------------------------------------------------------- shared invariants

test('every recipe stamps its id on the rows it produces', () => {
  for (const recipe of RECIPES) {
    const { cues, difficulty } = cuesFor(recipe.id)
    const cue = cues[0]
    const rows = resolveCue(cue, [pressOn(cue.binding.midi, cue.targetMs)], difficulty.judgement_window_ms)
    for (const row of rows) {
      assert.equal(row.recipe_id, recipe.id, `${recipe.id} produced a row without its id`)
    }
  }
})

test('legacy presentation recipes preserve the original target times', () => {
  // Times come from the shared engine; a recipe only reshapes presentation, so
  // two recipes over the same base mode must agree on when the beats fall.
  for (const recipe of RECIPES.filter(r=>r.cuePolicy!=='EXTENDED')) {
    const difficulty = DIFFICULTY
    const base = generateCues(recipe.baseMode, difficulty, { seed: 7 })
    const shaped = applyRecipe(recipe, base, difficulty, { seed: 7 })
    assert.equal(shaped.length, base.length, `${recipe.id} changed the number of cues`)
    shaped.forEach((cue, i) => {
      assert.equal(cue.targetMs, base[i].targetMs, `${recipe.id} moved a target`)
      assert.equal(cue.cueOnsetMs, base[i].cueOnsetMs, `${recipe.id} moved an onset`)
    })
  }
})

test('recipes are deterministic for a stored seed', () => {
  for (const recipe of RECIPES) {
    const a = cuesFor(recipe.id).cues
    const b = cuesFor(recipe.id).cues
    assert.deepEqual(
      a.map((c) => [c.targetMs, c.binding.midi, c.secondaryBinding?.midi ?? null]),
      b.map((c) => [c.targetMs, c.binding.midi, c.secondaryBinding?.midi ?? null]),
      `${recipe.id} is not reproducible`,
    )
  }
})

test('a bimanual cue always has a usable right-hand key', () => {
  const { cues } = cuesFor('BIMANUAL_SYNC')
  const rightMidis = new Set(KEY_BINDINGS.filter((b) => b.hand === 'RIGHT').map((b) => b.midi))
  for (const cue of cues) {
    assert.ok(rightMidis.has(cue.secondaryBinding?.midi ?? -1))
  }
})

test('the declared event fields match the policy', () => {
  assert.ok(recipeEventFields(RECIPE_BY_ID.SFT_CUE_SYNC).includes('response_latency_ms'))
  assert.ok(
    recipeEventFields(RECIPE_BY_ID.CFT_RHYTHM_HOLD).some((f) => f.includes('仅提示阶段')),
    'CFT must say its latency only exists during the cued phase',
  )
  assert.ok(recipeEventFields(RECIPE_BY_ID.BIMANUAL_SYNC).includes('inter_hand_onset_diff_ms'))
  assert.ok(recipeEventFields(RECIPE_BY_ID.ACCENT_GROUPING).includes('beat_in_bar'))
})

test('an empty base stream survives every recipe', () => {
  for (const recipe of RECIPES) {
    assert.deepEqual(applyRecipe(recipe, [], DIFFICULTY, { seed: 1 }), [])
  }
})

test('answerableCues excludes demonstrated prompts', () => {
  const cues = [
    { eventIndex: 0, cueOnsetMs: 0, targetMs: 100, binding: KEY_BINDINGS[0], isPrompt: true },
    { eventIndex: 1, cueOnsetMs: 200, targetMs: 900, binding: KEY_BINDINGS[0] },
  ]
  assert.equal(answerableCues(cues).length, 1)
})
