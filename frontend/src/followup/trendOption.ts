/**
 * Chart options for one metric over time.
 *
 * Kept out of the component so it can be tested directly: the rule that matters
 * here is that points from different algorithm versions never end up joined into
 * one line, and "the chart looked fine" is not evidence that the rule held.
 *
 * No `@/` imports: the rule tests run this through `node --experimental-strip-types`.
 */

import type { TrendPoint, TrendUnit } from './trends'

export interface TrendSeriesOption {
  name: string
  data: Array<[string, number]>
}

export interface TrendOption {
  /** One entry per algorithm version, in first-seen order. */
  series: TrendSeriesOption[]
  /** Whether more than one version is present, i.e. a legend is needed. */
  multiVersion: boolean
}

/** Label for the group of points that carry no version. */
export const UNVERSIONED_LABEL = '未标注算法版本'

/**
 * Group points into one series per algorithm version.
 *
 * Unversioned points get their own group rather than being folded into the first
 * version seen, which would attribute them to an algorithm that did not
 * necessarily produce them.
 */
export function buildTrendOption(points: readonly TrendPoint[]): TrendOption {
  const groups = new Map<string, TrendSeriesOption>()

  for (const point of points) {
    const key = point.version ?? ''
    const existing = groups.get(key)
    if (existing) {
      existing.data.push([point.at, point.value])
    } else {
      groups.set(key, {
        name: point.version ?? UNVERSIONED_LABEL,
        data: [[point.at, point.value]],
      })
    }
  }

  const series = [...groups.values()]
  return { series, multiVersion: series.length > 1 }
}

/** Format one value the way the axis and tooltip show it. */
export function formatTrendValue(value: number, unit: TrendUnit): string {
  if (!Number.isFinite(value)) return '暂无数据'
  if (unit === 'ratio') return `${(value * 100).toFixed(1)}%`
  if (unit === 'ms') return `${value.toFixed(1)} ms`
  if (unit === 'count') return `${value.toFixed(0)} 次`
  if (unit === 'sec') return `${value.toFixed(2)} s`
  if (unit === 'deg') return `${value.toFixed(1)}°`
  return value.toFixed(3)
}
