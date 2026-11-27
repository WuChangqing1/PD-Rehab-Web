/**
 * Optional post-training self-report, stored on this device only.
 *
 * Training records have no free-text column and no update endpoint, and their
 * JSON columns feed scoring and the AI review, so this deliberately stays out
 * of the backend and out of every training calculation. A skipped
 * questionnaire writes nothing at all.
 */
import type { TrainingReference } from './reviewOffers'

export type TrainingEffort = 'EASY' | 'MODERATE' | 'FATIGUE'
export type TrainingDiscomfort = 'NONE' | 'PRESENT'

export const DISCOMFORT_NOTE_LIMIT = 50
export const TRAINING_FEEDBACK_KEY = 'pd-rehab.training-feedback.v1'

export interface TrainingFeedbackAnswers {
  effort: TrainingEffort | null
  discomfort: TrainingDiscomfort | null
  discomfortNote: string
}

interface StoredFeedback {
  v: 1
  effort?: TrainingEffort
  discomfort?: TrainingDiscomfort
  discomfort_note?: string
  recorded_at: string
}

interface StoredRoot {
  v: 1
  items: Record<string, StoredFeedback>
}

const EFFORT_VALUES: readonly TrainingEffort[] = ['EASY', 'MODERATE', 'FATIGUE']
const DISCOMFORT_VALUES: readonly TrainingDiscomfort[] = ['NONE', 'PRESENT']

function storage(): Storage | undefined {
  try {
    return typeof localStorage === 'undefined' ? undefined : localStorage
  } catch {
    return undefined
  }
}

export function emptyTrainingFeedback(): TrainingFeedbackAnswers {
  return { effort: null, discomfort: null, discomfortNote: '' }
}

export function trainingFeedbackKey(ref: TrainingReference): string {
  return `${ref.kind}:${ref.id}`
}

function normalizeNote(value: unknown): string {
  return typeof value === 'string' ? value.trim().slice(0, DISCOMFORT_NOTE_LIMIT) : ''
}

export function normalizeTrainingFeedback(
  input: TrainingFeedbackAnswers | null | undefined,
): TrainingFeedbackAnswers {
  if (!input) return emptyTrainingFeedback()
  const effort = EFFORT_VALUES.includes(input.effort as TrainingEffort) ? (input.effort as TrainingEffort) : null
  const discomfort = DISCOMFORT_VALUES.includes(input.discomfort as TrainingDiscomfort)
    ? (input.discomfort as TrainingDiscomfort)
    : null
  return {
    effort,
    discomfort,
    discomfortNote: discomfort === 'PRESENT' ? normalizeNote(input.discomfortNote) : '',
  }
}

/** True only when the user actually picked a structured answer. */
export function hasTrainingFeedback(input: TrainingFeedbackAnswers | null | undefined): boolean {
  const answers = normalizeTrainingFeedback(input)
  return Boolean(answers.effort || answers.discomfort)
}

export function trainingFeedbackStorageKey(ownerId:string):string {return `${TRAINING_FEEDBACK_KEY}:${encodeURIComponent(ownerId)}`}

function readRoot(store: Storage, ownerId:string): StoredRoot {
  try {
    const parsed = JSON.parse(store.getItem(trainingFeedbackStorageKey(ownerId)) ?? 'null') as Partial<StoredRoot> | null
    if (parsed && parsed.v === 1 && parsed.items && typeof parsed.items === 'object') {
      return { v: 1, items: parsed.items as Record<string, StoredFeedback> }
    }
  } catch {
    // Corrupted or foreign value: start from an empty map instead of throwing.
  }
  return { v: 1, items: {} }
}

/**
 * Persists one questionnaire. Returns false when nothing was answered or the
 * browser refused storage; callers must never treat that as a failure of the
 * training flow.
 */
export function saveTrainingFeedback(
  ref: TrainingReference,
  input: TrainingFeedbackAnswers,
  now: Date = new Date(),
  ownerId: string = '',
): boolean {
  if (!ownerId.trim()) return false
  const answers = normalizeTrainingFeedback(input)
  if (!answers.effort && !answers.discomfort) return false
  const store = storage()
  if (!store) return false
  try {
    const root = readRoot(store,ownerId)
    const record: StoredFeedback = { v: 1, recorded_at: now.toISOString() }
    if (answers.effort) record.effort = answers.effort
    if (answers.discomfort) record.discomfort = answers.discomfort
    if (answers.discomfort === 'PRESENT' && answers.discomfortNote) {
      record.discomfort_note = answers.discomfortNote
    }
    root.items[trainingFeedbackKey(ref)] = record
    store.setItem(trainingFeedbackStorageKey(ownerId), JSON.stringify(root))
    return true
  } catch {
    return false
  }
}

export function loadTrainingFeedback(ref: TrainingReference,ownerId:string=''): TrainingFeedbackAnswers | null {
  if (!ownerId.trim()) return null
  const store = storage()
  if (!store) return null
  try {
    const root = readRoot(store,ownerId)
    const record = root.items[trainingFeedbackKey(ref)]
    if (!record || record.v !== 1) return null
    const answers = normalizeTrainingFeedback({
      effort: record.effort ?? null,
      discomfort: record.discomfort ?? null,
      discomfortNote: record.discomfort_note ?? '',
    })
    return answers.effort || answers.discomfort ? answers : null
  } catch {
    return null
  }
}
