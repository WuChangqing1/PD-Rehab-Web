/**
 * Where a training record's data came from.
 *
 * The same `input_source` enum is used by the piano and the pose modules, but the
 * human case means different things: a piano round is played on a computer
 * keyboard, a movement exercise is recorded on a camera. A single shared label
 * map rendered "真人键盘输入" in the pose history table, so this module keeps one
 * map per context and every caller passes the context it is displaying.
 *
 * Only `HUMAN_KEYBOARD` is a measurement. The other two exist so a scripted
 * self-test or a seeded demo row can never be read as a patient result.
 */

import type { PianoInputSource } from '@/types'

export type InputSourceContext = 'piano' | 'pose'

const LABELS: Record<InputSourceContext, Record<PianoInputSource, string>> = {
  piano: {
    HUMAN_KEYBOARD: '真人键盘输入',
    SYNTHETIC_SELFTEST: '脚本自检输入（非真人）',
    SEED_DEMO: '演示种子数据（非真人）',
  },
  pose: {
    HUMAN_KEYBOARD: '真人录制',
    SYNTHETIC_SELFTEST: '脚本自检录制（非真人）',
    SEED_DEMO: '演示种子数据（非真人）',
  },
}

/** True when the row is a real patient measurement. */
export function isHumanSource(source: PianoInputSource | null | undefined): boolean {
  return source === 'HUMAN_KEYBOARD'
}

/**
 * The label to show for any source, including the human one.
 *
 * Falls back to the raw value so an enum member added later shows up as itself
 * rather than as an empty cell.
 */
export function inputSourceLabel(
  source: PianoInputSource | null | undefined,
  context: InputSourceContext,
): string {
  if (!source) return '未知来源'
  return LABELS[context][source] ?? source
}

/**
 * The label to show only when the row is NOT a real measurement.
 *
 * Returns null for human input, which is the common case, so a table can render
 * a tag for exceptions and plain text otherwise.
 */
export function nonHumanSourceLabel(
  source: PianoInputSource | null | undefined,
  context: InputSourceContext,
): string | null {
  if (!source || isHumanSource(source)) return null
  return inputSourceLabel(source, context)
}
