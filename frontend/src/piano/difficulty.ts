/**
 * Adaptive difficulty rule engine (spec V2 sections 23 and 24).
 *
 * The rules below are transcribed from the specification. They are NOT invented
 * here, and the engine deliberately has a narrow input set:
 *
 *   Accuracy, Miss Rate, Response Latency, Response Latency CV,
 *   Timing MAE, Left/Right Difference, Weak Finger Error Rate
 *
 * Micro-expression tag proportions and any PD probability are explicitly NOT
 * inputs (spec V2 sections 5.3 and 20). First-version difficulty depends on the
 * personal calibration plus actual training performance only.
 *
 * Other constraints that are enforced in code rather than left to convention:
 *   - one round changes at most `RULES.maxChangesPerRound` parameters (2), so a
 *     later change in performance can be attributed (spec V2 section 23.1)
 *   - the weak-side share moves by at most 10-15% per round (section 24) and
 *     counts against the same budget
 *   - every threshold is a named constant in RULES, versioned by
 *     DIFFICULTY_ENGINE_VERSION, so a decision is reproducible and auditable
 */

import type { DifficultyConfig } from '@/piano/session'
import type { PianoMetrics } from '@/piano/metrics'
import type { Hand } from '@/piano/samples'

export const DIFFICULTY_ENGINE_VERSION = 'piano-difficulty-v1.1.0'

/**
 * Decision thresholds, transcribed from spec V2 section 23.
 * `timingMaeBaselineFactor` is the one value the specification leaves open
 * ("Timing MAE <= current threshold"); it is expressed as a multiple of the
 * patient's own calibration MAE and is recorded with the decision.
 */
export const RULES = {
  upgrade: {
    accuracyMin: 0.9,
    missRateMax: 0.05,
    latencyCvMax: 0.25,
    /** MAE must be no worse than this multiple of the calibration MAE. */
    timingMaeBaselineFactor: 1.0,
  },
  maintain: {
    accuracyMin: 0.7,
  },
  downgrade: {
    accuracyBelow: 0.7,
    missRateAbove: 0.2,
    /** Latency this much above the personal baseline counts as a regression. */
    latencyBaselineFactor: 1.3,
    errorStreakMax: 4,
  },
  /** Section 24: limit how far the weak-side share may move in one round. */
  weakSideStepMax: 0.15,
  weakSideMin: 0.3,
  weakSideMax: 0.8,
  /**
   * Section 23.1: a single round may change at most this many parameters.
   *
   * This is enforced as a hard budget over every field the engine may touch,
   * including `weak_side_ratio`. Without it a worsening round changed four
   * fields at once (bpm, window, sequence length and the hand share), and the
   * next round's result could not be attributed to any one of them.
   */
  maxChangesPerRound: 2,
  bpmStep: 5,
  bpmMin: 40,
  bpmMax: 160,
  judgementWindowStep: 25,
  judgementWindowMin: 120,
  judgementWindowMax: 600,
  sequenceLengthStep: 1,
  sequenceLengthMin: 2,
  sequenceLengthMax: 8,
} as const

export type DifficultyDecision = 'UPGRADE' | 'MAINTAIN' | 'DOWNGRADE'

export interface DifficultyChange {
  field: keyof DifficultyConfig
  from: number | string
  to: number | string
}

export interface DifficultyResult {
  decision: DifficultyDecision
  before: DifficultyConfig
  after: DifficultyConfig
  changes: DifficultyChange[]
  /** Human-readable reasons, stored with the session for auditability. */
  reasons: string[]
  /** Which thresholds were applied, so the decision can be reproduced. */
  applied_rules: Record<string, unknown>
  engine_version: string
  /** Hand that was served more often next round, if any. */
  weak_hand: Hand | null
}

export interface CalibrationBaseline {
  baseline_accuracy: number | null
  baseline_response_latency: number | null
  baseline_response_latency_cv: number | null
  baseline_timing_mae: number | null
  baseline_left_accuracy: number | null
  baseline_right_accuracy: number | null
  baseline_left_latency: number | null
  baseline_right_latency: number | null
}

/** Derive the eight calibration values from a completed calibration round. */
export function baselineFromCalibration(metrics: PianoMetrics): CalibrationBaseline {
  return {
    baseline_accuracy: metrics.accuracy,
    baseline_response_latency: metrics.mean_response_latency_ms,
    baseline_response_latency_cv: metrics.response_latency_cv,
    baseline_timing_mae: metrics.mean_absolute_timing_error_ms,
    baseline_left_accuracy: metrics.left_accuracy,
    baseline_right_accuracy: metrics.right_accuracy,
    baseline_left_latency: metrics.left_mean_latency,
    baseline_right_latency: metrics.right_mean_latency,
  }
}

/**
 * Choose the starting difficulty from the calibration result.
 *
 * Not from any disease probability (spec V2 section 20).
 */
export function initialDifficulty(baseline: CalibrationBaseline): DifficultyConfig {
  const config: DifficultyConfig = { ...DEFAULT_BASE }
  const accuracy = baseline.baseline_accuracy
  const latency = baseline.baseline_response_latency

  if (accuracy !== null && accuracy >= 0.9 && (latency === null || latency <= 500)) {
    config.bpm = 70
    config.judgement_window_ms = 250
    config.sequence_length = 4
  } else if (accuracy !== null && accuracy < 0.6) {
    config.bpm = 50
    config.judgement_window_ms = 400
    config.sequence_length = 2
  } else {
    config.bpm = 60
    config.judgement_window_ms = 300
    config.sequence_length = 3
  }

  // Start biased toward whichever hand calibrated worse.
  const left = baseline.baseline_left_accuracy
  const right = baseline.baseline_right_accuracy
  if (left !== null && right !== null && Math.abs(left - right) > 0.1) {
    config.weak_side_ratio = left < right ? 0.6 : 0.4
  }
  return config
}

const DEFAULT_BASE: DifficultyConfig = {
  bpm: 60,
  judgement_window_ms: 300,
  sequence_length: 4,
  note_density: 1.0,
  hand_mode: 'SINGLE',
  weak_side_ratio: 0.5,
  finger_complexity: 1,
  session_duration_sec: 60,
}

function clamp(value: number, min: number, max: number): number {
  return Math.max(min, Math.min(max, value))
}

/**
 * Decide the next round's difficulty.
 *
 * The weak hand is inferred from the metrics: the hand with the longer mean
 * latency and no better accuracy is served more next round, bounded by
 * weakSideStepMax (section 24).
 */
export function adaptDifficulty(
  metrics: PianoMetrics,
  before: DifficultyConfig,
  baseline: CalibrationBaseline | null,
): DifficultyResult {
  const after: DifficultyConfig = { ...before }
  const changes: DifficultyChange[] = []
  const reasons: string[] = []

  const accuracy = metrics.accuracy
  const missRate = metrics.miss_rate
  const latencyCv = metrics.response_latency_cv
  const timingMae = metrics.mean_absolute_timing_error_ms
  const latency = metrics.mean_response_latency_ms
  const streak = metrics.error_streak_max

  const maeThreshold =
    baseline?.baseline_timing_mae != null
      ? baseline.baseline_timing_mae * RULES.upgrade.timingMaeBaselineFactor
      : null
  const latencyThreshold =
    baseline?.baseline_response_latency != null
      ? baseline.baseline_response_latency * RULES.downgrade.latencyBaselineFactor
      : null

  const upgradeConditions = {
    accuracy_ok: accuracy !== null && accuracy >= RULES.upgrade.accuracyMin,
    miss_rate_ok: missRate !== null && missRate <= RULES.upgrade.missRateMax,
    latency_cv_ok: latencyCv !== null && latencyCv <= RULES.upgrade.latencyCvMax,
    timing_mae_ok:
      timingMae === null || maeThreshold === null ? null : timingMae <= maeThreshold,
  }
  const upgradeWanted =
    upgradeConditions.accuracy_ok &&
    upgradeConditions.miss_rate_ok &&
    upgradeConditions.latency_cv_ok &&
    upgradeConditions.timing_mae_ok !== false

  const downgradeReasons: string[] = []
  if (accuracy !== null && accuracy < RULES.downgrade.accuracyBelow) {
    downgradeReasons.push(`准确率 ${(accuracy * 100).toFixed(0)}% 低于 ${RULES.downgrade.accuracyBelow * 100}%`)
  }
  if (missRate !== null && missRate > RULES.downgrade.missRateAbove) {
    downgradeReasons.push(`漏击率 ${(missRate * 100).toFixed(0)}% 高于 ${RULES.downgrade.missRateAbove * 100}%`)
  }
  if (latency !== null && latencyThreshold !== null && latency > latencyThreshold) {
    downgradeReasons.push(
      `平均反应延迟 ${latency.toFixed(0)} ms 明显高于个人基线 ${baseline?.baseline_response_latency?.toFixed(0)} ms`,
    )
  }
  if (streak !== null && streak >= RULES.downgrade.errorStreakMax) {
    downgradeReasons.push(`连续错误达到 ${streak} 次`)
  }

  let decision: DifficultyDecision = 'MAINTAIN'

  /**
   * Apply one parameter change if the per-round budget still allows it.
   *
   * Callers propose changes already ordered by priority, so the budget is spent
   * on the most important change first. A proposal that would not move the value
   * is dropped without consuming budget, so a clamped field never blocks a
   * change that is still possible.
   */
  function propose(
    field: keyof DifficultyConfig,
    from: number | string,
    to: number | string,
    apply: (value: never) => void,
  ): boolean {
    if (from === to) return false
    if (changes.length >= RULES.maxChangesPerRound) return false
    changes.push({ field, from, to })
    apply(to as never)
    return true
  }

  if (downgradeReasons.length > 0) {
    decision = 'DOWNGRADE'
    reasons.push(...downgradeReasons)
    // Safety first: widen the window, then slow the beat, then shorten the
    // sequence. The budget stops this at two fields.
    propose(
      'judgement_window_ms',
      before.judgement_window_ms,
      clamp(
        before.judgement_window_ms + RULES.judgementWindowStep,
        RULES.judgementWindowMin,
        RULES.judgementWindowMax,
      ),
      (v: number) => {
        after.judgement_window_ms = v
      },
    )
    propose(
      'bpm',
      before.bpm,
      clamp(before.bpm - RULES.bpmStep, RULES.bpmMin, RULES.bpmMax),
      (v: number) => {
        after.bpm = v
      },
    )
    propose(
      'sequence_length',
      before.sequence_length,
      clamp(
        before.sequence_length - RULES.sequenceLengthStep,
        RULES.sequenceLengthMin,
        RULES.sequenceLengthMax,
      ),
      (v: number) => {
        after.sequence_length = v
      },
    )
  } else if (upgradeWanted) {
    decision = 'UPGRADE'
    reasons.push('准确率、漏击率与响应延迟变异均达到升级条件')
    // One primary change per round so the effect stays attributable: raise the
    // tempo, and only if that is already capped move on to the next lever.
    const raisedBpm = propose(
      'bpm',
      before.bpm,
      clamp(before.bpm + RULES.bpmStep, RULES.bpmMin, RULES.bpmMax),
      (v: number) => {
        after.bpm = v
      },
    )
    const narrowedWindow =
      raisedBpm ||
      propose(
        'judgement_window_ms',
        before.judgement_window_ms,
        clamp(
          before.judgement_window_ms - RULES.judgementWindowStep,
          RULES.judgementWindowMin,
          RULES.judgementWindowMax,
        ),
        (v: number) => {
          after.judgement_window_ms = v
        },
      )
    const longerSequence =
      raisedBpm ||
      narrowedWindow ||
      propose(
        'sequence_length',
        before.sequence_length,
        clamp(
          before.sequence_length + RULES.sequenceLengthStep,
          RULES.sequenceLengthMin,
          RULES.sequenceLengthMax,
        ),
        (v: number) => {
          after.sequence_length = v
        },
      )
    if (!raisedBpm && !narrowedWindow && !longerSequence) {
      propose(
        'finger_complexity',
        before.finger_complexity,
        Math.min(3, before.finger_complexity + 1),
        (v: number) => {
          after.finger_complexity = v
        },
      )
    }
  } else {
    reasons.push('表现处于维持区间，本轮不改变难度')
  }

  // ---- left / right personalisation (spec V2 section 24) ----
  let weakHand: Hand | null = null
  const leftLatency = metrics.left_mean_latency
  const rightLatency = metrics.right_mean_latency
  const leftAccuracy = metrics.left_accuracy
  const rightAccuracy = metrics.right_accuracy

  if (leftLatency !== null && rightLatency !== null && leftAccuracy !== null && rightAccuracy !== null) {
    if (leftLatency > rightLatency && leftAccuracy <= rightAccuracy) {
      weakHand = 'LEFT'
    } else if (rightLatency > leftLatency && rightAccuracy <= leftAccuracy) {
      weakHand = 'RIGHT'
    }
  }

  if (weakHand === 'LEFT') {
    const next = clamp(
      before.weak_side_ratio + RULES.weakSideStepMax,
      RULES.weakSideMin,
      RULES.weakSideMax,
    )
    if (propose('weak_side_ratio', before.weak_side_ratio, next, (v: number) => {
      after.weak_side_ratio = v
    })) {
      reasons.push(
        `左手平均延迟更高且准确率不优于右手，下一轮左手任务比例 ${(before.weak_side_ratio * 100).toFixed(0)}% → ${(next * 100).toFixed(0)}%`,
      )
    } else if (changes.length >= RULES.maxChangesPerRound) {
      reasons.push('本轮参数调整已达上限，左右手比例保持不变')
    }
  } else if (weakHand === 'RIGHT') {
    const next = clamp(
      before.weak_side_ratio - RULES.weakSideStepMax,
      RULES.weakSideMin,
      RULES.weakSideMax,
    )
    if (propose('weak_side_ratio', before.weak_side_ratio, next, (v: number) => {
      after.weak_side_ratio = v
    })) {
      reasons.push(
        `右手平均延迟更高且准确率不优于左手，下一轮右手任务比例 ${((1 - before.weak_side_ratio) * 100).toFixed(0)}% → ${((1 - next) * 100).toFixed(0)}%`,
      )
    } else if (changes.length >= RULES.maxChangesPerRound) {
      reasons.push('本轮参数调整已达上限，左右手比例保持不变')
    }
  }

  return {
    decision,
    before,
    after,
    changes,
    reasons,
    applied_rules: {
      ...RULES,
      computed: {
        accuracy,
        miss_rate: missRate,
        response_latency_cv: latencyCv,
        mean_response_latency_ms: latency,
        timing_mae_ms: timingMae,
        timing_mae_threshold_ms: maeThreshold,
        latency_threshold_ms: latencyThreshold,
        error_streak_max: streak,
        upgrade_conditions: upgradeConditions,
      },
    },
    engine_version: DIFFICULTY_ENGINE_VERSION,
    weak_hand: weakHand,
  }
}
