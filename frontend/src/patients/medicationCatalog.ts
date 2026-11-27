/**
 * Frontend medication catalog for quick pick.
 *
 * The names below are the ones already used by the repository demo data
 * (scripts/seed_demo.py). They are a DRAFT for clinician review, not a formal
 * hospital formulary: no dosage, frequency or treatment plan is encoded here.
 * Keep codes stable; rename only the display name and bump the version.
 */
export interface MedicationCatalogItem {
  /** Stable identifier for future structured storage/statistics. */
  code: string
  /** Generic name shown to staff and stored in current_medications. */
  name: string
  /** Extra search terms; never displayed as a separate option. */
  aliases?: string[]
}

export const MEDICATION_CATALOG_VERSION = '2026-11-27.draft.1'
export const MEDICATION_CATALOG_SOURCE = '沿用仓库演示数据，待医护审核'

export const MEDICATION_CATALOG: MedicationCatalogItem[] = [
  { code: 'LEVODOPA_CARBIDOPA', name: '左旋多巴/卡比多巴', aliases: ['左旋多巴', '卡比多巴'] },
  { code: 'PRAMIPEXOLE', name: '普拉克索' },
  { code: 'ENTACAPONE', name: '恩他卡朋' },
  { code: 'AMANTADINE', name: '金刚烷胺' },
  { code: 'SELEGILINE', name: '司来吉兰' },
]

function normalize(value: string): string {
  return value.trim().toLowerCase().replace(/\s+/g, '')
}

/** Case/space-insensitive search over generic name and aliases. */
export function searchMedications(query: string): MedicationCatalogItem[] {
  const needle = normalize(query)
  if (!needle) return MEDICATION_CATALOG
  return MEDICATION_CATALOG.filter((item) =>
    [item.name, ...(item.aliases ?? [])].some((term) => normalize(term).includes(needle)),
  )
}
