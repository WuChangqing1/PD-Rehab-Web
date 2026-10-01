/**
 * Display formatting helpers.
 *
 * Central rule: a missing value renders as an explicit placeholder, never as a
 * plausible-looking number. "暂无数据" is always preferable to a fabricated 0.
 */

export const NO_DATA = '暂无数据'
export const NOT_AVAILABLE = '不可用'

/**
 * The patient name as it should be shown to a doctor or a patient.
 *
 * Demonstration records carry a "（虚拟）" suffix in the database, which is a
 * provenance marker and belongs there. On screen it reads as a label attached to
 * a person, which is not what a clinician should see next to a name during a
 * consultation -- and it is not information the person in the chair needs.
 *
 * The suffix is stripped for display only. Stored names, exports and the
 * database keep it, so data provenance is unchanged.
 */
export function displayPatientName(name: string | null | undefined): string {
  if (!name) return ''
  return name.replace(/[（(]\s*虚拟\s*[)）]/g, '').trim()
}

/**
 * The patient number as it should be shown.
 *
 * Demonstration records are numbered `DEMO-0001`. The prefix marks provenance in
 * the database, not something a patient or a doctor should read off a screen, so
 * it is dropped for display only.
 *
 * Search is unaffected: the server matches on the stored value with a substring
 * comparison, so typing the visible `0001` still finds `DEMO-0001`, and typing
 * the full stored value works too.
 */
export function displayHospitalNumber(number: string | null | undefined): string {
  if (!number) return ''
  return number.replace(/^\s*(DEMO|TEST|SAMPLE)[-_ ]*/i, '').trim() || number
}

export function formatNumber(
  value: number | null | undefined,
  digits = 2,
  unit = '',
): string {
  if (value === null || value === undefined || Number.isNaN(value)) {
    return NO_DATA
  }
  return `${value.toFixed(digits)}${unit}`
}

export function formatInteger(value: number | null | undefined, unit = ''): string {
  if (value === null || value === undefined || Number.isNaN(value)) {
    return NO_DATA
  }
  return `${Math.round(value)}${unit}`
}

export function formatRatio(value: number | null | undefined, digits = 2): string {
  if (value === null || value === undefined || Number.isNaN(value)) {
    return NO_DATA
  }
  return value.toFixed(digits)
}

export function formatPercent(value: number | null | undefined, digits = 1): string {
  if (value === null || value === undefined || Number.isNaN(value)) {
    return NO_DATA
  }
  return `${(value * 100).toFixed(digits)}%`
}

export function formatDateTime(value: string | null | undefined): string {
  if (!value) return NO_DATA
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return NO_DATA
  const pad = (n: number) => String(n).padStart(2, '0')
  return (
    `${date.getFullYear()}-${pad(date.getMonth() + 1)}-${pad(date.getDate())} ` +
    `${pad(date.getHours())}:${pad(date.getMinutes())}`
  )
}

export function formatDate(value: string | null | undefined): string {
  if (!value) return NO_DATA
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return NO_DATA
  const pad = (n: number) => String(n).padStart(2, '0')
  return `${date.getFullYear()}-${pad(date.getMonth() + 1)}-${pad(date.getDate())}`
}

// ------------------------------------------------------------------ label maps
export const SEX_LABELS: Record<string, string> = {
  MALE: '男',
  FEMALE: '女',
  OTHER: '其他',
  UNKNOWN: '未知',
}

export const MEDICATION_LABELS: Record<string, string> = {
  ON: '开期（ON）',
  OFF: '关期（OFF）',
  UNKNOWN: '未知',
}

export const AFFECTED_SIDE_LABELS: Record<string, string> = {
  LEFT: '左侧',
  RIGHT: '右侧',
  BILATERAL: '双侧',
  UNKNOWN: '未知',
}

export const DOMINANT_HAND_LABELS: Record<string, string> = {
  LEFT: '左手',
  RIGHT: '右手',
  AMBIDEXTROUS: '双手',
  UNKNOWN: '未知',
}

export const HAND_LABELS: Record<string, string> = {
  LEFT: '左手',
  RIGHT: '右手',
}

export const SESSION_TYPE_LABELS: Record<string, string> = {
  COMPREHENSIVE: '综合评估',
  MICRO_EXPRESSION_ONLY: '面部表现分析',
  FINGER_TAPPING_ONLY: '手指敲击评估',
  FUNCTIONAL_TEST: '功能测试',
}

export const SESSION_STATUS_LABELS: Record<string, string> = {
  PENDING: '待开始',
  IN_PROGRESS: '进行中',
  COMPLETED: '已完成',
  ABORTED: '已中止',
}

export const MODEL_STATE_LABELS: Record<string, string> = {
  MODEL_NOT_CONFIGURED: '未配置',
  LOADING: '加载中',
  READY: '就绪',
  UNAVAILABLE: '不可用',
  LOAD_FAILED: '加载失败',
}

export const FUNCTIONAL_TEST_LABELS: Record<string, string> = {
  NINE_HOLE_PEG: '九孔插棒测试（9-HPT）',
  BOX_AND_BLOCK: '盒块测试（BBT）',
  HAND_COORDINATION: '手指协同运动测试',
  MDS_UPDRS: 'MDS-UPDRS',
  PDQ39: 'PDQ-39',
}

export function modelStateTagType(state: string): 'success' | 'warning' | 'danger' | 'info' {
  switch (state) {
    case 'READY':
      return 'success'
    case 'LOADING':
      return 'warning'
    case 'LOAD_FAILED':
      return 'danger'
    case 'MODEL_NOT_CONFIGURED':
      return 'info'
    default:
      return 'warning'
  }
}

export function sessionStatusTagType(status: string): 'success' | 'warning' | 'danger' | 'info' {
  switch (status) {
    case 'COMPLETED':
      return 'success'
    case 'IN_PROGRESS':
      return 'warning'
    case 'ABORTED':
      return 'danger'
    default:
      return 'info'
  }
}

export function medicationTagType(state: string): 'success' | 'info' | 'warning' {
  switch (state) {
    case 'ON':
      return 'success'
    case 'OFF':
      return 'warning'
    default:
      return 'info'
  }
}
