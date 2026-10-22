import { t } from './index'
/** Translate presentation labels only. Numeric data, units and series identities are untouched. */
export function localizeChartOption<T>(option: T): T {
  function visit(value: unknown, key = ''): unknown {
    if (key === 'data' || key === 'id') return value
    if (typeof value === 'string') return t(value)
    if (Array.isArray(value)) return value.map(item => visit(item))
    if (typeof value === 'function' && /formatter/i.test(key)) return (...args: unknown[]) => {
      const result = value(...args)
      return typeof result === 'string' ? t(result) : result
    }
    if (value && typeof value === 'object' && Object.getPrototypeOf(value) === Object.prototype) {
      return Object.fromEntries(Object.entries(value).map(([name, item]) => [name, visit(item, name)]))
    }
    return value
  }
  return visit(option) as T
}
