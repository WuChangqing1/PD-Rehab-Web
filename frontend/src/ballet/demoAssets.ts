/**
 * Which demonstration an exercise may show, and whether it is allowed on screen.
 *
 * THE RULE THIS ENFORCES
 * ======================
 * A demonstration clip may only reach a patient once BOTH its licence has been
 * verified and a human has watched it and approved the movement. The registry in
 * `demoAssets.json` records that, and this module is the only thing the interface
 * asks. Today every entry resolves to `DIAGRAM` because nothing has passed both
 * gates -- and that is the correct, intended state rather than a gap to paper
 * over.
 *
 * WHY NOT JUST SHOW THE VIDEO WE HAVE
 * ===================================
 * The one clip that downloaded (SRC-PLIE-01) was watched frame by frame and
 * rejected: no chair, turned-out feet, a deeper bend than the exercise allows.
 * Playing it for a patient with Parkinson's would demonstrate the opposite of the
 * instructions on the same screen. docs/04 is explicit that a mismatched clip
 * must not be substituted, so a rejected asset resolves to the diagram and the
 * registry keeps the reason on record.
 *
 * Pure module: no Vue, no `@/` imports, so `npm test` exercises it directly.
 */

/*
  The import attribute is required: Node's ESM loader refuses a JSON import
  without `type: json`, and the rule tests run these modules directly under
  `node --test`. Vite understands the same syntax, so one form works in both the
  test runner and the build.
*/
import registry from './demoAssets.json' with { type: 'json' }

/** Registry states, in the order docs/07 defines them. */
export type AssetStatus =
  | 'NOT_SELECTED'
  | 'SOURCE_FOUND'
  | 'LICENSE_VERIFIED'
  | 'DOWNLOADED'
  | 'CLIP_REVIEWED'
  | 'MOVEMENT_APPROVED'
  | 'TRANSCODED'
  | 'QA_PASSED'
  | 'PUBLISHED'

export interface DemoAssetEntry {
  exercise_key: string
  execution_mode: string
  status: AssetStatus
  source_id: string | null
  license_verified: boolean
  movement_reviewed: boolean
  poster_path: string | null
  video_path: string | null
  duration_sec: number | null
  demonstration_version: string | null
  /**
   * Short Chinese sentence, safe to render next to the diagram.
   *
   * Separated from `notes` because `notes` is the developer audit text. Returning
   * `notes` here was the first version of this module, and it put a sentence
   * beginning "REJECTED for patient use" in front of a clinician.
   */
  ui_note?: string
  /** Developer audit text. Never rendered. */
  notes: string
}

/** What the interface should render for an exercise and mode. */
export type DemoResolution =
  | { kind: 'VIDEO'; video: string; poster: string | null; version: string | null; attribution: Attribution | null }
  | { kind: 'DIAGRAM'; reason: DemoFallbackReason; note: string }

export type DemoFallbackReason =
  /** Nothing has been selected for this exercise and mode yet. */
  | 'NOT_SELECTED'
  /** A candidate exists but has not cleared both gates. */
  | 'AWAITING_REVIEW'
  /** A candidate was watched and rejected; the reason is on record. */
  | 'REJECTED'
  /** Cleared the gates but the files are not in the bundle. */
  | 'FILES_MISSING'

export interface Attribution {
  author: string
  license: string
  sourcePage: string
}

const ENTRIES = registry.entries as DemoAssetEntry[]

/** Reviews are keyed by source id so the interface can show why something failed. */
const REVIEWS = (registry.review_log ?? []) as Array<{
  source_id: string
  author?: string
  license?: string
  source_page?: string
  verdict?: string
  /** Chinese reasons, shown to staff in the disclosure panel. */
  reasons_zh?: string[]
  /** The developer's original English notes, kept for the audit trail only. */
  reasons_en_developer_note?: string[]
}>

/**
 * Both gates.
 *
 * Split out so the tests can assert the two conditions independently rather than
 * only through the resolution result.
 */
export function isPublishable(entry: DemoAssetEntry): boolean {
  if (!entry.license_verified || !entry.movement_reviewed) return false
  if (!entry.video_path) return false
  return entry.status === 'QA_PASSED' || entry.status === 'PUBLISHED' || entry.status === 'TRANSCODED'
}

export function findEntry(
  exerciseKey: string,
  executionMode: string,
  entries: DemoAssetEntry[] = ENTRIES,
): DemoAssetEntry | null {
  return (
    entries.find((e) => e.exercise_key === exerciseKey && e.execution_mode === executionMode) ?? null
  )
}

function attributionFor(sourceId: string | null): Attribution | null {
  if (!sourceId) return null
  const review = REVIEWS.find((r) => r.source_id === sourceId)
  if (!review?.author || !review.license || !review.source_page) return null
  return { author: review.author, license: review.license, sourcePage: review.source_page }
}

/**
 * Resolve what to show.
 *
 * Returns a VIDEO only when the entry is publishable; otherwise a DIAGRAM with
 * the reason, so the interface can say why rather than simply showing nothing.
 */
export function resolveDemo(
  exerciseKey: string,
  executionMode: string,
  entries: DemoAssetEntry[] = ENTRIES,
): DemoResolution {
  const entry = findEntry(exerciseKey, executionMode, entries)

  if (!entry) {
    return { kind: 'DIAGRAM', reason: 'NOT_SELECTED', note: '暂无示范视频。当前显示的是已核对的静态动作示意。' }
  }

  if (isPublishable(entry)) {
    return {
      kind: 'VIDEO',
      video: entry.video_path as string,
      poster: entry.poster_path,
      version: entry.demonstration_version,
      attribution: attributionFor(entry.source_id),
    }
  }

  const review = entry.source_id ? REVIEWS.find((r) => r.source_id === entry.source_id) : undefined
  const rejected = review?.verdict?.startsWith('REJECTED') ?? false

  // Both gates met but the files never made it into the bundle: never claim a
  // video is playing when it is not.
  if (entry.license_verified && entry.movement_reviewed && !entry.video_path) {
    return { kind: 'DIAGRAM', reason: 'FILES_MISSING', note: '示范视频尚未加入发布包，当前显示静态动作示意。' }
  }

  // The rendered sentence is `ui_note`, never `notes`. Rendered text has to be
  // written for the person reading it; `notes` is the audit trail.
  return {
    kind: 'DIAGRAM',
    reason: rejected ? 'REJECTED' : entry.status === 'NOT_SELECTED' ? 'NOT_SELECTED' : 'AWAITING_REVIEW',
    note: entry.ui_note ?? entry.notes,
  }
}

/** Short, non-technical label for the state, shown next to the diagram. */
export const FALLBACK_LABELS: Record<DemoFallbackReason, string> = {
  NOT_SELECTED: '暂无视频示范',
  AWAITING_REVIEW: '视频示范待审核',
  REJECTED: '暂无视频示范',
  FILES_MISSING: '视频示范未发布',
}

/**
 * Why a candidate was rejected, for the staff-facing detail panel.
 *
 * Kept for doctors rather than patients: it answers "is a video coming, and if
 * not, why" without putting a licence discussion in front of somebody doing
 * demi-pliés.
 */
export function reviewNotes(exerciseKey: string, executionMode: string): string[] {
  const entry = findEntry(exerciseKey, executionMode)
  if (!entry?.source_id) return []
  const review = REVIEWS.find((r) => r.source_id === entry.source_id)
  return review?.reasons_zh ?? []
}

/** Every entry, for the audit table in the report and for tests. */
export function allEntries(): DemoAssetEntry[] {
  return ENTRIES
}

/**
 * Guard against a registry that would let something unsafe through.
 *
 * Returns the entries that claim to be publishable. The tests assert this is
 * empty today, so a future edit that flips a flag without the review behind it
 * fails the build rather than reaching a patient.
 */
export function publishableEntries(entries: DemoAssetEntry[] = ENTRIES): DemoAssetEntry[] {
  return entries.filter(isPublishable)
}
