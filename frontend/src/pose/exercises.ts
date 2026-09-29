/**
 * Presentation metadata for the five movement exercises.
 *
 * The backend owns everything that is measured or targeted (metrics, target
 * repetitions, hold time, contraindications) and this file only supplies what
 * belongs to the interface: the English name, the body-area tag and the muscle
 * chips shown on the card, in the same style as the reference fitness site.
 *
 * Nothing here is a measurement and nothing may be used as one.
 */

export interface ExercisePresentation {
  /** Body area shown as the coloured corner tag. */
  area: string
  /** Colour token for the area tag. */
  areaColor: string
  nameEn: string
  /** Muscle / joint chips under the name, matching the reference card style. */
  chips: string[]
}

export const EXERCISE_PRESENTATION: Record<string, ExercisePresentation> = {
  MOUNTAIN_ARMS_UP: {
    area: '肩部',
    areaColor: '#2f7cc0',
    nameEn: 'mountain arms up',
    chips: ['三角肌', '斜方肌', '躯干稳定'],
  },
  ARMS_LATERAL_RAISE: {
    area: '肩部',
    areaColor: '#2f7cc0',
    nameEn: 'lateral raise',
    chips: ['三角肌中束', '冈上肌'],
  },
  SIDE_BEND_STRETCH: {
    area: '腰腹',
    areaColor: '#c07a2f',
    nameEn: 'side bend stretch',
    chips: ['腹斜肌', '腰方肌', '竖脊肌'],
  },
  SEATED_TRUNK_ROTATION: {
    area: '腰腹',
    areaColor: '#c07a2f',
    nameEn: 'seated trunk rotation',
    chips: ['腹斜肌', '胸椎旋转'],
  },
  SEATED_ALTERNATING_ARM_RAISE: {
    area: '肩部',
    areaColor: '#2f7cc0',
    nameEn: 'alternating arm raise',
    chips: ['三角肌前束', '肱二头肌', '躯干稳定'],
  },
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
