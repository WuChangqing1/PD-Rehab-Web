/**
 * Which raw metrics to surface for a given exercise, and in what order.
 *
 * WHY THIS EXISTS
 * ===============
 * The result cards used to be a hardcoded four-item list starting with
 * "抬起角度 · 左 x · 右 y" built from `left_shoulder_max_angle_deg`. That is right
 * for Port de Bras and wrong for Tendu and Demi-Plié: a reader looking at a knee
 * exercise was shown shoulder angles, and the number they actually wanted (how
 * far the knee bent) was buried in the collapsed raw-metrics table.
 *
 * The backend already knows which joint drives each exercise -- it declares
 * `drive_series` per definition, and the analyzer records the matching raw
 * metrics. So the interface derives the cards from that instead of guessing:
 *
 *   DRIVE_SHOULDER    -> shoulder angles      (Port de Bras, First Position)
 *   DRIVE_HIP         -> hip abduction        (Tendu)
 *   DRIVE_KNEE        -> knee angles          (Demi-Plié)
 *   DRIVE_TRUNK_TILT  -> trunk tilt angle     (Weight Shift)
 *
 * NOTHING HERE IS A MEASUREMENT. It maps metric keys the backend already emits
 * onto labels and ordering. No formula is defined, and no display score is
 * produced -- the score fields stay empty on purpose (see the card footnote).
 *
 * The module is intentionally free of Vue and of `@/` imports so the rule tests
 * can exercise it directly under `node --test`.
 */

/** Raw metric keys, as emitted by `backend/app/ml/pose/metrics.py`. */
export const METRIC = {
  shoulderLeft: 'left_shoulder_max_angle_deg',
  shoulderRight: 'right_shoulder_max_angle_deg',
  kneeLeft: 'left_knee_max_angle_deg',
  kneeRight: 'right_knee_max_angle_deg',
  hipLeft: 'left_hip_abduction_deg',
  hipRight: 'right_hip_abduction_deg',
  trunk: 'trunk_angle_deg',
  leftRightDiff: 'left_right_angle_difference_deg',
  speed: 'movement_speed_deg_per_sec',
  hold: 'hold_time_sec',
  repetitions: 'repetition_count',
  interval: 'repetition_interval_ms',
  angleStd: 'angle_std_deg',
  validFrames: 'valid_pose_frame_ratio',
} as const

/**
 * The `drive_series` values the backend actually puts on the wire.
 *
 * These are the STRING VALUES of the Python constants in
 * `backend/app/ml/pose/exercises.py`, not their names:
 *
 *   DRIVE_SHOULDER   = "shoulder_abduction"
 *   DRIVE_HIP        = "hip_abduction"
 *   DRIVE_KNEE       = "knee_extension"
 *   DRIVE_TRUNK_TILT = "trunk_tilt"
 *
 * Using the constant names here would silently match nothing and fall back to
 * the shoulder profile -- which is exactly the bug this module exists to fix, so
 * there is a test asserting the wire values against the live catalogue.
 */
export const DRIVE = {
  SHOULDER: 'shoulder_abduction',
  HIP: 'hip_abduction',
  KNEE: 'knee_extension',
  TRUNK_TILT: 'trunk_tilt',
} as const

export type DriveSeries = (typeof DRIVE)[keyof typeof DRIVE]

export interface ResultCardSpec {
  label: string
  /** Metric keys whose values are shown side by side. */
  metrics: string[]
  /** How to join them: `pair` prefixes 左/右, `single` prints one value. */
  shape: 'pair' | 'single'
  note: string
  emphasis?: boolean
}

/**
 * The card set for a drive joint.
 *
 * The first card is always the movement itself: how many repetitions were
 * completed. The second is the range the exercise is actually about. Speed and
 * left/right difference follow, because they are comparable across exercises.
 */
const PROFILES: Record<DriveSeries, ResultCardSpec[]> = {
  [DRIVE.SHOULDER]: [
    {
      label: '抬臂角度',
      metrics: [METRIC.shoulderLeft, METRIC.shoulderRight],
      shape: 'pair',
      note: '两侧各自达到的最大肩关节角度',
      emphasis: true,
    },
    {
      label: '动作速度',
      metrics: [METRIC.speed],
      shape: 'single',
      note: '角度变化速率，数值越大动作越快',
    },
    {
      label: '左右差异',
      metrics: [METRIC.leftRightDiff],
      shape: 'single',
      note: '数值越小说明两侧越接近',
    },
  ],
  [DRIVE.HIP]: [
    {
      label: '腿部外展角度',
      metrics: [METRIC.hipLeft, METRIC.hipRight],
      shape: 'pair',
      note: '两侧各自达到的最大髋关节外展角度',
      emphasis: true,
    },
    {
      label: '动作速度',
      metrics: [METRIC.speed],
      shape: 'single',
      note: '角度变化速率，数值越大动作越快',
    },
    {
      label: '左右差异',
      metrics: [METRIC.leftRightDiff],
      shape: 'single',
      note: '数值越小说明两侧越接近',
    },
  ],
  [DRIVE.KNEE]: [
    {
      label: '屈膝角度',
      metrics: [METRIC.kneeLeft, METRIC.kneeRight],
      shape: 'pair',
      note: '两侧各自达到的最大膝关节屈曲角度',
      emphasis: true,
    },
    {
      label: '动作速度',
      metrics: [METRIC.speed],
      shape: 'single',
      note: '角度变化速率，数值越大动作越快',
    },
    {
      label: '左右差异',
      metrics: [METRIC.leftRightDiff],
      shape: 'single',
      note: '数值越小说明两侧越接近',
    },
  ],
  [DRIVE.TRUNK_TILT]: [
    {
      label: '躯干倾角',
      metrics: [METRIC.trunk],
      shape: 'single',
      note: '躯干相对竖直方向的最大偏移角度',
      emphasis: true,
    },
    {
      label: '动作速度',
      metrics: [METRIC.speed],
      shape: 'single',
      note: '角度变化速率，数值越大动作越快',
    },
    {
      label: '左右差异',
      metrics: [METRIC.leftRightDiff],
      shape: 'single',
      note: '数值越小说明两侧越接近',
    },
  ],
}

/**
 * Repetition count is universal, so it is built separately rather than repeated
 * in all four profiles. It always comes first.
 */
const REPETITION_CARD: ResultCardSpec = {
  label: '完成次数',
  metrics: [METRIC.repetitions],
  shape: 'single',
  note: '本次录制中完整完成的动作个数',
  emphasis: true,
}

/** What the cards look like when the drive joint is unknown. */
const FALLBACK_DRIVE: DriveSeries = DRIVE.SHOULDER

export function normaliseDriveSeries(value: string | null | undefined): DriveSeries {
  if (value && value in PROFILES) return value as DriveSeries
  return FALLBACK_DRIVE
}

/**
 * Ordered card specification for an exercise.
 *
 * `driveSeries` comes from the exercise definition the backend serves; when it
 * is missing (an older response, or a retired exercise whose definition is gone)
 * the shoulder profile is used, which is what the previous hardcoded list did.
 */
export function resultCardsFor(driveSeries: string | null | undefined): ResultCardSpec[] {
  return [REPETITION_CARD, ...PROFILES[normaliseDriveSeries(driveSeries)]]
}

/**
 * How many cards a metric appears on.
 *
 * Used by the tests to assert no metric is presented under two different labels,
 * which is how the old list managed to show a shoulder angle on a leg exercise
 * without anyone noticing.
 */
export function metricCardCount(cards: ResultCardSpec[], metric: string): number {
  return cards.filter((card) => card.metrics.includes(metric)).length
}

/** Every metric key any profile can surface. */
export function surfacedMetrics(): string[] {
  const all = new Set<string>([REPETITION_CARD.metrics[0]])
  for (const cards of Object.values(PROFILES)) {
    for (const card of cards) for (const metric of card.metrics) all.add(metric)
  }
  return [...all]
}
