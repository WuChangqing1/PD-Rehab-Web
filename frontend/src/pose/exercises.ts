/**
 * Presentation metadata for the ballet exercises.
 *
 * The backend owns everything that is measured or targeted (metrics, target
 * repetitions, hold time, cue phrase, tempo, supported execution modes) and this
 * file only supplies what belongs to the interface: the body area tag, the
 * colour and the short chips shown on the card.
 *
 * Nothing here is a measurement and nothing may be used as one.
 *
 * RETIRED EXERCISES
 * =================
 * The module shipped five yoga poses first and recordings made then are still in
 * the database. They are not renamed on the server, so this map keeps a readable
 * label for them; without it an old session would render its raw key. The label
 * says "早期动作" rather than pretending the row is ballet, because it is not.
 */

export interface ExercisePresentation {
  /** Body area shown as the coloured corner tag. */
  area: string
  /** Colour token for the area tag. */
  areaColor: string
  nameEn: string
  /** Short chips under the name. Read by doctors, not by patients. */
  chips: string[]
}

export const EXERCISE_PRESENTATION: Record<string, ExercisePresentation> = {
  BALLET_PORT_DE_BRAS: {
    area: '手臂',
    areaColor: '#2f7cc0',
    nameEn: 'Port de Bras',
    chips: ['肩肘控制', '左右对称', '躯干稳定'],
  },
  BALLET_FIRST_POSITION: {
    area: '姿态',
    areaColor: '#5c6bc0',
    nameEn: 'First Position Hold',
    chips: ['躯干直立', '对称', '保持'],
  },
  BALLET_TENDU: {
    area: '腿部',
    areaColor: '#2f9e6f',
    nameEn: 'Tendu',
    chips: ['髋膝踝', '重心转移', '左右差异'],
  },
  BALLET_DEMI_PLIE: {
    area: '腿部',
    areaColor: '#2f9e6f',
    nameEn: 'Demi-Plié',
    chips: ['膝髋屈曲', '对称', '缓慢'],
  },
  BALLET_WEIGHT_SHIFT: {
    area: '平衡',
    areaColor: '#c07a2f',
    nameEn: 'Weight Shift',
    chips: ['重心转移', '协调', '节奏'],
  },

  // ---- retired yoga keys, kept so historical sessions still render ----
  MOUNTAIN_ARMS_UP: {
    area: '早期动作',
    areaColor: '#6b7885',
    nameEn: 'arms up (retired)',
    chips: [],
  },
  ARMS_LATERAL_RAISE: {
    area: '早期动作',
    areaColor: '#6b7885',
    nameEn: 'lateral raise (retired)',
    chips: [],
  },
  SIDE_BEND_STRETCH: {
    area: '早期动作',
    areaColor: '#6b7885',
    nameEn: 'side bend (retired)',
    chips: [],
  },
  SEATED_TRUNK_ROTATION: {
    area: '早期动作',
    areaColor: '#6b7885',
    nameEn: 'trunk rotation (retired)',
    chips: [],
  },
  SEATED_ALTERNATING_ARM_RAISE: {
    area: '早期动作',
    areaColor: '#6b7885',
    nameEn: 'alternating arm raise (retired)',
    chips: [],
  },
}

/** Chinese names for retired keys; the backend owns the current ones. */
export const RETIRED_EXERCISE_NAMES: Record<string, string> = {
  MOUNTAIN_ARMS_UP: '双臂上举（早期动作）',
  ARMS_LATERAL_RAISE: '侧平举（早期动作）',
  SIDE_BEND_STRETCH: '侧屈伸展（早期动作）',
  SEATED_TRUNK_ROTATION: '坐姿躯干旋转（早期动作）',
  SEATED_ALTERNATING_ARM_RAISE: '交替抬臂（早期动作）',
}

/** True when the key is one of the retired yoga exercises. */
export function isRetiredExercise(key: string): boolean {
  return key in RETIRED_EXERCISE_NAMES
}

/**
 * Name to show for any stored exercise key.
 *
 * `serverName` is the backend's own `name_zh` when the exercise is still in the
 * catalogue; retired keys are not in it, so they fall back to the label above
 * rather than to a raw enum value.
 */
export function exerciseName(key: string, serverName?: string | null): string {
  if (serverName) return serverName
  return RETIRED_EXERCISE_NAMES[key] ?? '历史训练记录'
}

export function presentationFor(key: string): ExercisePresentation {
  return (
    EXERCISE_PRESENTATION[key] ?? {
      area: '动作',
      areaColor: '#6b7885',
      nameEn: key.toLowerCase().replace(/_/g, ' '),
      chips: [],
    }
  )
}
