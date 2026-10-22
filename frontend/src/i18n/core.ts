export type Locale = 'zh-CN' | 'en'
export const LANGUAGE_STORAGE_KEY = 'paqin-language'
export function normalizeLocale(value: unknown): Locale { return value === 'en' ? 'en' : 'zh-CN' }
export function readLocale(storage?: Pick<Storage, 'getItem'>): Locale {
  try { return normalizeLocale(storage?.getItem(LANGUAGE_STORAGE_KEY)) } catch { return 'zh-CN' }
}
export function persistLocale(storage: Pick<Storage, 'setItem'> | undefined, value: Locale): void {
  try { storage?.setItem(LANGUAGE_STORAGE_KEY, value) } catch { /* Private browsing can block storage. */ }
}
const escape = (value: string) => value.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')
/** Only known UI messages are translated. Captured data is carried through verbatim. */
export function createTranslator(messages: Record<string, string>) {
  const patterns = Object.entries(messages).filter(([key]) => /\{\d+\}/.test(key))
    .sort(([a], [b]) => b.replace(/\{\d+\}/g, '').length - a.replace(/\{\d+\}/g, '').length).map(([key, value]) => {
    const slots: string[] = []
    let cursor = 0, source = '^'
    for (const match of key.matchAll(/\{(\d+)\}/g)) {
      source += escape(key.slice(cursor, match.index)) + '([\\s\\S]+?)'
      slots.push(match[1]!); cursor = match.index! + match[0].length
    }
    source += escape(key.slice(cursor)) + '$'
    return { regex: new RegExp(source), slots, value }
  })
  return (input: unknown, locale: Locale): string => {
    if (input == null) return ''
    const original = String(input)
    if (locale === 'zh-CN') return original
    if (Object.hasOwn(messages, original)) return messages[original]!
    if (!/[\u3400-\u9fff]/.test(original)) return original
    for (const pattern of patterns) {
      const match = pattern.regex.exec(original)
      if (!match) continue
      const values: Record<string, string> = {}
      pattern.slots.forEach((slot, index) => { values[slot] = match[index + 1]! })
      return pattern.value.replace(/\{(\d+)\}/g, (placeholder, slot: string) => values[slot] ?? placeholder)
    }
    return original
  }
}
