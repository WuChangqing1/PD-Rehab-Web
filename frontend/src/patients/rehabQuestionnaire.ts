/**
 * Structured rehab-history questionnaire.
 *
 * There is no dedicated backend column, so the answers travel inside the
 * existing `rehab_history` long-text field as a versioned JSON envelope. The
 * legacy free text is kept byte-for-byte in front of the envelope and is never
 * rewritten or cleaned up. Unanswered questions stay null: "未记录" is NOT "否".
 */
export type RehabContact = 'YES' | 'NO' | 'UNKNOWN'
export type RehabType = 'HOME' | 'HOSPITAL' | 'OTHER'
export type RehabFrequency = 'DAILY' | 'WEEKLY' | 'OCCASIONAL' | 'UNKNOWN'

export interface RehabAnswers {
  contact: RehabContact | null
  types: RehabType[]
  frequency: RehabFrequency | null
}

export const REHAB_ENVELOPE_HINT = '[结构化问卷记录，请使用新版网页查看]'
export const REHAB_MARKER_START = '[[PD_REHAB_V1]]'
export const REHAB_MARKER_END = '[[/PD_REHAB_V1]]'

export const REHAB_CONTACT_LABELS: Record<RehabContact, string> = {
  YES: '是',
  NO: '否',
  UNKNOWN: '不清楚',
}

export const REHAB_TYPE_ORDER: RehabType[] = ['HOME', 'HOSPITAL', 'OTHER']

export const REHAB_TYPE_LABELS: Record<RehabType, string> = {
  HOME: '居家锻炼',
  HOSPITAL: '医院康复训练',
  OTHER: '其他训练',
}

export const REHAB_FREQUENCY_LABELS: Record<RehabFrequency, string> = {
  DAILY: '每天',
  WEEKLY: '每周几次',
  OCCASIONAL: '偶尔',
  UNKNOWN: '记不清',
}

export function emptyRehabAnswers(): RehabAnswers {
  return { contact: null, types: [], frequency: null }
}

export function hasRehabAnswers(answers: RehabAnswers): boolean {
  return answers.contact !== null || answers.types.length > 0 || answers.frequency !== null
}

function isContact(value: unknown): value is RehabContact {
  return value === 'YES' || value === 'NO' || value === 'UNKNOWN'
}

function isFrequency(value: unknown): value is RehabFrequency {
  return value === 'DAILY' || value === 'WEEKLY' || value === 'OCCASIONAL' || value === 'UNKNOWN'
}

/** Drop unknown codes, deduplicate and keep a stable display order. */
export function normalizeRehabAnswers(input: Partial<RehabAnswers> | null | undefined): RehabAnswers {
  const source = input ?? {}
  const types = Array.isArray(source.types) ? source.types : []
  return {
    contact: isContact(source.contact) ? source.contact : null,
    types: REHAB_TYPE_ORDER.filter((type) => types.includes(type)),
    frequency: isFrequency(source.frequency) ? source.frequency : null,
  }
}

/**
 * Split the stored value into the untouched free text and the structured
 * answers. Anything malformed is treated as plain text so nothing is lost.
 */
export function parseRehabHistory(raw: unknown): { text: string; answers: RehabAnswers } {
  const value = String(raw ?? '')
  const end = value.lastIndexOf(REHAB_MARKER_END)
  const start = end >= 0 ? value.lastIndexOf(REHAB_MARKER_START, end) : -1
  if (start < 0 || end < start) return { text: value, answers: emptyRehabAnswers() }

  const hintIndex = value.lastIndexOf(REHAB_ENVELOPE_HINT, start)
  if (hintIndex < 0 || value.slice(hintIndex + REHAB_ENVELOPE_HINT.length, start).trim() !== '') {
    // No recognisable envelope prefix: keep the whole value as free text.
    return { text: value, answers: emptyRehabAnswers() }
  }

  let parsed: unknown
  try {
    parsed = JSON.parse(value.slice(start + REHAB_MARKER_START.length, end))
  } catch {
    return { text: value, answers: emptyRehabAnswers() }
  }
  if (typeof parsed !== 'object' || parsed === null || Array.isArray(parsed)) {
    return { text: value, answers: emptyRehabAnswers() }
  }

  let text = value.slice(0, hintIndex)
  // compose() inserts exactly two newlines as the separator; remove only those.
  if (text.endsWith('\n\n')) text = text.slice(0, -2)

  const record = parsed as Record<string, unknown>
  return {
    text,
    answers: normalizeRehabAnswers({
      contact: record.contact as RehabContact | null,
      types: record.types as RehabType[] | undefined,
      frequency: record.frequency as RehabFrequency | null,
    }),
  }
}

/** Rebuild the stored value; returns the free text unchanged when unanswered. */
export function composeRehabHistory(text: unknown, answers: RehabAnswers): string {
  const freeText = String(text ?? '')
    .replaceAll(REHAB_MARKER_START, '')
    .replaceAll(REHAB_MARKER_END, '')
  const normalized = normalizeRehabAnswers(answers)
  if (!hasRehabAnswers(normalized)) return freeText

  const payload: Record<string, unknown> = { v: 1 }
  if (normalized.contact) payload.contact = normalized.contact
  if (normalized.types.length) payload.types = normalized.types
  if (normalized.frequency) payload.frequency = normalized.frequency
  const separator = freeText.trim() ? '\n\n' : ''
  return `${freeText}${separator}${REHAB_ENVELOPE_HINT}\n${REHAB_MARKER_START}${JSON.stringify(payload)}${REHAB_MARKER_END}`
}

/** Human-readable one-line summary for the detail page; null when unanswered. */
export function rehabSummary(answers: RehabAnswers): string | null {
  const parts: string[] = []
  if (answers.contact) parts.push(`接触过康复：${REHAB_CONTACT_LABELS[answers.contact]}`)
  if (answers.types.length) parts.push(`训练类型：${answers.types.map((type) => REHAB_TYPE_LABELS[type]).join('、')}`)
  if (answers.frequency) parts.push(`频次：${REHAB_FREQUENCY_LABELS[answers.frequency]}`)
  return parts.length ? parts.join('；') : null
}
