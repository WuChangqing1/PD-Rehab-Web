import { ref } from 'vue'
import { createTranslator, normalizeLocale, persistLocale, readLocale, type Locale } from './core'
import general from './en-general.json'
import piano from './en-piano.json'
import patients from './en-patients.json'
import extra from './en-extra.json'
import errors from './en-errors.json'
import dynamic from './en-dynamic.json'
import models from './en-models.json'

function storage(): Storage | undefined { try { return typeof localStorage === 'undefined' ? undefined : localStorage } catch { return undefined } }
export const locale = ref<Locale>(readLocale(storage()))
const translate = createTranslator({ ...general, ...piano, ...patients, ...extra, ...errors, ...dynamic, ...models,
  '、': ', ', '语言': 'Language', '切换为英文': 'Switch to English', '切换为中文': 'Switch to Chinese',
})
export function t(value: unknown): string { return translate(value, locale.value) }
export function setLocale(value: unknown): void {
  locale.value = normalizeLocale(value)
  persistLocale(storage(), locale.value)
  if (typeof document !== 'undefined') document.documentElement.lang = locale.value === 'en' ? 'en' : 'zh-CN'
}
export function pageTitle(title: unknown): string { return title ? `${t(title)} · ${t('帕琴律动')}` : t('帕琴律动') }
