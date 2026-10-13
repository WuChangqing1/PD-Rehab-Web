/**
 * Piano training recipes: named practice templates over the existing modes.
 *
 * WHAT A RECIPE IS, AND IS NOT
 * ============================
 * A recipe is a TEMPLATE. It selects one of the five existing modes, says how the
 * cues should behave, and names the measurement the practice is for. It is not a
 * second training engine: every recipe runs through the same `generateCues`,
 * `resolveCue`, `PianoKeyboard`, runner and API as the original modes. Adding a
 * card here must never add a page (`docs/05`, `docs/02`).
 *
 * The four recipes below are the ones `docs/05` specifies for the first version.
 * Two of them are the base mode with a different cue policy (SFT, ACCENT) and two
 * genuinely change how a cue resolves (CFT removes the cue, BIMANUAL expects two
 * keys at once) -- so they produce different event data, not just different
 * headings.
 *
 * The distinction matters for the interface requirement that recipe cards must
 * not be four near-identical buttons: each card states the concrete behaviour the
 * patient will meet, and `cuePolicy` is what makes that statement true.
 */

import { mulberry32, type Cue, type DifficultyConfig, type PianoMode } from './session.ts'
import { extendedCues } from './extendedRecipes.ts'
import { BINDING_BY_MIDI, type Hand, type KeyBinding } from './samples.ts'

export type RecipeId =
  | 'SFT_CUE_SYNC'
  | 'CFT_RHYTHM_HOLD'
  | 'BIMANUAL_SYNC'
  | 'ACCENT_GROUPING'
  | 'TEMPO_RAMP' | 'HOLD_RELEASE' | 'BIMANUAL_OFFSET' | 'REVERSE_SEQUENCE' | 'GO_NO_GO'

/** How cues are presented during the round. */
export type CuePolicy =
  /** A cue appears for every target, as in the original modes. */
  | 'FULL_CUE'
  /** Cues run for a warm-up stretch, then stop while the beat continues. */
  | 'DEMONSTRATE_THEN_REMOVE'
  /** One cue asks for two keys, one per hand. */
  | 'DUAL_CUE'
  /** Cues are grouped into bars and the first beat of each bar is accented. */
  | 'ACCENT_GROUP'
  | 'EXTENDED'

/** Coarse grouping used by the interface, not a difficulty rating. */
export type RecipeGroup = 'BASIC' | 'BIMANUAL' | 'ADVANCED'

export interface TrainingRecipe {
  id: RecipeId
  label: string
  group: RecipeGroup
  /** The existing mode this recipe is built on. */
  baseMode: PianoMode
  cuePolicy: CuePolicy
  /** One concrete sentence: what the patient actually does. */
  summary: string
  /** What the round yields. Shown to staff, never as a score. */
  produces: string
  /** Beats of cueing before the cue is removed. CFT only. */
  promptBeats?: number
  /** Beats per bar for accent grouping. */
  beatsPerBar?: number
  /** Version string stored with the session. */
  algorithmVersion: string
}

export const RECIPE_ALGORITHM_VERSION = 'piano-recipe-v1.0.0'

export const RECIPES: TrainingRecipe[] = [
  {
    id: 'SFT_CUE_SYNC',
    label: '听提示按键',
    group: 'BASIC',
    baseMode: 'SINGLE_KEY_RHYTHM',
    cuePolicy: 'FULL_CUE',
    summary: '看到高亮的琴键就按下，每个提示都有声音和画面。',
    produces: '反应延迟、命中率、节拍误差',
    algorithmVersion: RECIPE_ALGORITHM_VERSION,
  },
  {
    id: 'CFT_RHYTHM_HOLD',
    label: '保持节奏',
    group: 'ADVANCED',
    baseMode: 'FOLLOW_THE_BEAT',
    cuePolicy: 'DEMONSTRATE_THEN_REMOVE',
    summary: '先跟着提示打 8 拍，之后提示消失，继续按同样的节拍自己打下去。',
    produces: '无提示阶段的节拍误差与间隔稳定性',
    promptBeats: 8,
    algorithmVersion: RECIPE_ALGORITHM_VERSION,
  },
  {
    id: 'BIMANUAL_SYNC',
    label: '双手同时敲击',
    group: 'BIMANUAL',
    baseMode: 'SINGLE_KEY_RHYTHM',
    cuePolicy: 'DUAL_CUE',
    summary: '提示出现时，左右手各按一个键，尽量同时按下。',
    produces: '双手同步误差、命中率、左右不平衡',
    algorithmVersion: RECIPE_ALGORITHM_VERSION,
  },
  {
    id: 'ACCENT_GROUPING',
    label: '强拍识别',
    group: 'ADVANCED',
    baseMode: 'FOLLOW_THE_BEAT',
    cuePolicy: 'ACCENT_GROUP',
    summary: '每组第 1 拍提示更明显，请按准每个节拍，留意强拍位置。',
    produces: '组内早晚误差、强拍命中率、漏按率',
    beatsPerBar: 4,
    algorithmVersion: RECIPE_ALGORITHM_VERSION,
  },
  { id: 'TEMPO_RAMP', label: '节奏变速', group: 'ADVANCED', baseMode: 'SINGLE_KEY_RHYTHM', cuePolicy: 'EXTENDED', summary: '跟随逐段变化的节拍，最后回到起始速度。', produces: '分段准确率、节拍绝对误差', algorithmVersion: 'piano-recipe-v2.0.0' },
  { id: 'HOLD_RELEASE', label: '长短音控制', group: 'BASIC', baseMode: 'SINGLE_KEY_RHYTHM', cuePolicy: 'EXTENDED', summary: '按下高亮键，按提示保持 250 或 750 毫秒后松开。', produces: '持续时间误差、释放完成率', algorithmVersion: 'piano-recipe-v2.0.0' },
  { id: 'BIMANUAL_OFFSET', label: '双手错位节奏', group: 'BIMANUAL', baseMode: 'SINGLE_KEY_RHYTHM', cuePolicy: 'EXTENDED', summary: '左手先按，右手晚半拍；每组之间留一拍休息。', produces: '双手相位误差、左右漏击率', algorithmVersion: 'piano-recipe-v2.0.0' },
  { id: 'REVERSE_SEQUENCE', label: '反向序列', group: 'ADVANCED', baseMode: 'MEMORY_RHYTHM', cuePolicy: 'EXTENDED', summary: '先观看并聆听示范，再用相反顺序弹出。', produces: '逆序位置准确率、序列完成率', algorithmVersion: 'piano-recipe-v2.0.0' },
  { id: 'GO_NO_GO', label: '选择性反应', group: 'ADVANCED', baseMode: 'SINGLE_KEY_RHYTHM', cuePolicy: 'EXTENDED', summary: '看到“按下 ○”时按键，看到“等待 ×”时不要按。', produces: '误按次数、漏按次数、反应延迟', algorithmVersion: 'piano-recipe-v2.0.0' },
]

export const RECIPE_BY_ID: Record<RecipeId, TrainingRecipe> = Object.fromEntries(
  RECIPES.map((r) => [r.id, r]),
) as Record<RecipeId, TrainingRecipe>

export function isRecipeId(value: string): value is RecipeId {
  return value in RECIPE_BY_ID
}

export function recipeFor(id: RecipeId): TrainingRecipe {
  return RECIPE_BY_ID[id]
}

/** Grouped for the picker, so the doctor sees four cards rather than a flat list. */
export const RECIPE_GROUPS: Array<{ group: RecipeGroup; title: string; description: string }> = [
  { group: 'BASIC', title: '基础节奏', description: '单个提示、单个按键，建立稳定的手部节奏。' },
  { group: 'BIMANUAL', title: '双手协调', description: '两只手一起参与，观察双手配合。' },
  { group: 'ADVANCED', title: '进阶练习', description: '撤除提示或加入强弱变化，更接近日常动作。' },
]

export function recipesInGroup(group: RecipeGroup): TrainingRecipe[] {
  return RECIPES.filter((r) => r.group === group)
}

// ---------------------------------------------------------------- cue shaping

/**
 * Keys available to a hand, respecting the finger-complexity limit.
 *
 * Mirrors `keysForComplexity` in session.ts, which is not exported. Duplicating a
 * four-line filter is preferable to widening that module's surface for one
 * caller, and the tests assert both hands are always non-empty.
 */
function poolFor(hand: Hand): KeyBinding[] {
  const all = Object.values(BINDING_BY_MIDI).filter((b) => b.hand === hand)
  const simple = all.filter((b) => b.fingerHint === 'INDEX')
  return simple.length ? simple : all
}

export interface ApplyRecipeOptions {
  seed?: number
  /** Which hand the cues are drawn from for a single-hand recipe. */
  hand?: Hand
}

/**
 * Reshape a base cue stream into the recipe's cue stream.
 *
 * Operates on the cues `generateCues` already produced rather than re-deriving
 * times, so the beat grid, approach time and judgement windows stay identical to
 * the original modes and a recipe cannot drift from them.
 */
export function applyRecipe(
  recipe: TrainingRecipe,
  cues: Cue[],
  difficulty: DifficultyConfig,
  options: ApplyRecipeOptions = {},
): Cue[] {
  if (recipe.cuePolicy === 'EXTENDED') return extendedCues(recipe.id, cues, difficulty, options.seed)
  switch (recipe.cuePolicy) {
    case 'FULL_CUE':
      return cues.map((c) => ({ ...c, recipeId: recipe.id }))

    case 'DEMONSTRATE_THEN_REMOVE':
      return applyCueRemoval(recipe, cues, difficulty)

    case 'DUAL_CUE':
      return applyDualCue(recipe, cues, options)

    case 'ACCENT_GROUP':
      return applyAccentGrouping(recipe, cues)

    default:
      return cues
  }
}

/**
 * CFT: cue for the first N beats, then silence while the beat continues.
 *
 * `hasCue` is what changes, not the target. The patient is still asked to press
 * on the beat -- there is simply nothing on screen to follow. Keeping the target
 * is what allows `timing_error_ms` to stay meaningful in the un-cued phase while
 * `response_latency_ms` becomes null, because there is no cue onset to measure
 * from (`docs/05`).
 */
function applyCueRemoval(recipe: TrainingRecipe, cues: Cue[], difficulty: DifficultyConfig): Cue[] {
  const promptBeats = recipe.promptBeats ?? 8
  const beatMs = 60000 / Math.max(20, difficulty.bpm)
  // Beats are measured from the first target, so the warm-up is a real duration
  // rather than a count of whatever density the difficulty happened to produce.
  const firstTarget = cues.length ? cues[0].targetMs : 0
  const cutOffMs = firstTarget + promptBeats * beatMs

  return cues.map((cue) => ({
    ...cue,
    recipeId: recipe.id,
    hasCue: cue.targetMs <= cutOffMs,
  }))
}

/**
 * BIMANUAL: every cue asks for one key in each hand at the same moment.
 *
 * The second binding is drawn from a seeded generator so a stored configuration
 * replays exactly. Left is the primary binding so the existing single-key
 * metrics keep a defined meaning, and the right one rides along as `secondary`.
 */
function applyDualCue(recipe: TrainingRecipe, cues: Cue[], options: ApplyRecipeOptions): Cue[] {
  const random = mulberry32(options.seed ?? 20260929)
  const left = poolFor('LEFT')
  const right = poolFor('RIGHT')

  return cues.map((cue) => {
    // The base mode may have drawn from either hand; both sides are replaced so
    // the pair is genuinely one per hand.
    const primary = cue.binding.hand === 'LEFT' ? cue.binding : left[Math.floor(random() * left.length)]
    const secondary = right[Math.floor(random() * right.length)]
    return {
      ...cue,
      recipeId: recipe.id,
      binding: primary,
      secondaryBinding: secondary,
    }
  })
}

/**
 * ACCENT: number the beats in each bar and mark the first as accented.
 *
 * `beatInBar` counts from the first target so bar 1 starts where the patient
 * starts. The accent is a playing instruction; it is not a difficulty setting and
 * does not change any timing.
 */
function applyAccentGrouping(recipe: TrainingRecipe, cues: Cue[]): Cue[] {
  const beatsPerBar = recipe.beatsPerBar ?? 4
  return cues.map((cue, i) => {
    const beatInBar = (i % beatsPerBar) + 1
    return {
      ...cue,
      recipeId: recipe.id,
      beatInBar,
      accent: beatInBar === 1,
    }
  })
}

// ------------------------------------------------------------------- readouts

/**
 * Whether a cue presents something on screen to react to.
 *
 * A cue with `hasCue === false` is one the patient must produce from their own
 * sense of the beat. Absent means true, so every pre-existing mode is unaffected.
 */
export function cueIsVisible(cue: Cue): boolean {
  return cue.hasCue !== false
}

/** Cues the patient is expected to answer, in the order they should be answered. */
export function answerableCues(cues: Cue[]): Cue[] {
  return cues.filter((c) => !c.isPrompt)
}

/**
 * Split a CFT round into its cued and un-cued halves.
 *
 * Reported separately because averaging them together would hide the thing the
 * practice is for: staying on the beat once the support is gone.
 */
export function splitCuedAndFree(cues: Cue[]): { cued: Cue[]; free: Cue[] } {
  const cued: Cue[] = []
  const free: Cue[] = []
  for (const cue of answerableCues(cues)) {
    if (cueIsVisible(cue)) cued.push(cue)
    else free.push(cue)
  }
  return { cued, free }
}

/** Bar boundaries for the accent recipe, for the beat indicator. */
export function barPosition(cue: Cue, beatsPerBar = 4): { index: number; of: number } {
  return { index: cue.beatInBar ?? 1, of: beatsPerBar }
}

/** What a recipe is expected to record, for the doctor-facing summary. */
export function recipeEventFields(recipe: TrainingRecipe): string[] {
  const base = [
    'cue_onset_time_ms',
    'target_time_ms',
    'actual_time_ms',
    'timing_error_ms',
    'key_code',
    'hand',
    'is_correct',
    'is_missed',
  ]
  switch (recipe.cuePolicy) {
    case 'FULL_CUE':
      return [...base, 'response_latency_ms']
    case 'DEMONSTRATE_THEN_REMOVE':
      // Latency exists only where a cue existed.
      return [...base, 'response_latency_ms（仅提示阶段）']
    case 'DUAL_CUE':
      return [...base, 'response_latency_ms', 'inter_hand_onset_diff_ms']
    case 'ACCENT_GROUP':
      return [...base, 'response_latency_ms', 'beat_in_bar', 'is_accent']
    default:
      return base
  }
}
