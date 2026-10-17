# Follow-up Calendar and Training Analysis Implementation Plan

> **For agentic workers:** Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox syntax for tracking.

**Goal:** Add a patient activity calendar, comparable per-practice trend charts and objective reports, an independent labelled demonstration dataset, a photographic ballet cover, and concise product copy.

**Architecture:** A read-only, authenticated bounded-date feed returns existing assessment, piano, pose and owner-scoped guided-song records. Calendar days and trends use pure frontend transformations; trends separate provenance, exercise, settings and algorithm versions. A guarded idempotent script writes only a reserved independent demonstration patient and derives examples through existing metric functions where applicable.

**Tech Stack:** Existing Vue 3, TypeScript, ECharts, FastAPI and SQLAlchemy; built-in image generation.

**Spec:** User request in this conversation, including explicit approval to add labelled sample records for an independent demonstration patient.

## Global Constraints

- Preserve existing untracked files and real records. Work in the named project checkout/main, consistent with the user's prior requested workflow.
- Do not fabricate clinical measurements, model output, pressure metrics or recovery conclusions. Example records retain SEED_DEMO/SYNTHETIC_SELFTEST provenance and are plotted only in a separate labelled example view.
- Calendar includes incomplete records but attendance counts only completed training; date grouping respects timezone and does not truncate at 50 rows.
- Guided-song ownership checks remain in force. Do not include raw audio or events in aggregate feed.
- Keep necessary instructions, consent, destructive confirmations, provenance labels and unavailable/error states; remove redundant promotional or generation-process copy.
- No database clearing or schema migration; no new paid service.

## Review Focus

1. UTC/local midnight and month boundaries: test date range offsets and calendar indexing.
2. Missing/non-finite values, incomplete rounds and non-human input: test exclusion, explicit sample scope and null handling.
3. Incompatible practice/configuration/version: test grouping prevents false continuous trends.
4. Patient switching/network races: stale loads must not expose previous patient data or mark empty dates incorrectly.
5. Demo seeding: idempotency and reserved patient guard; never overwrite any real patient or falsify face outputs.

### Task 1: Date-range feed and calendar

Files: create backend/app/api/followup.py, backend/app/services/followup_service.py, backend/app/schemas/followup.py; modify API router, frontend API/types; create frontend/src/followup/calendar.ts and frontend/src/components/ActivityCalendar.vue.

- [x] Write backend tests for authentication, patient isolation, timezone boundaries, >50 rows, incomplete status, guided ownership and bounded dates. Observe failure.
- [x] Implement GET /patients/{id}/follow-up?start_date=&end_date=&offset_minutes= with existing schemas and owner-scoped guided summaries.
- [x] Write calendar date/count tests, observe failure, implement local calendar helpers and keyboard-accessible day buttons.
- [x] Verify focused tests and commit.

### Task 2: Comparable trends and reports

Files: rewrite frontend/src/pages/FollowUpPage.vue; add frontend/src/followup/analysis.ts; extend trends.ts with explicit source scope; preserve default human-only API.

- [x] Write tests for practice/config/version grouping, sample separation, missing values and objective comparison summaries. Observe failure.
- [x] Implement date range feed loading, calendar/day list with read-only result actions, all-practice metric definitions, pose-specific metrics, guided-song charts and scoped report summaries.
- [x] Verify focused tests; preserve existing result dialog and raw events. Commit.

### Task 3: Independent example dataset and cover/copy

Files: add scripts/seed_followup_showcase.py and tests; add unique cover asset and generation metadata; modify TrainingArtwork and product descriptions.

- [x] Write tests proving idempotent reserved-only seeding and all training categories covered, observe failure, implement labelled examples with stored raw inputs and existing metric computation.
- [x] Generate and inspect a photographic ballet-preparation cover distinct from the five training demonstrations; save project asset and integrate it.
- [x] Remove unnecessary descriptive copy site-wide while retaining operating instructions and data provenance.
- [x] Verify tests and commit.

### Task 4: Verify and deliver

- [x] Run npm run test, npm run build, subpath build and backend pytest.
- [x] Browser-check calendar date navigation/day details and per-practice charts on desktop, tablet and mobile using isolated demonstration data; save screenshots.
- [x] One fresh-context review of full changes; fix important findings.
- [x] Deliver source, tests, screenshots, asset provenance and commits. Follow existing push/deploy authorization for this project; production data actions limited to the explicitly approved isolated example patient, no real medical reads.

## Execution ledger

- Baseline main: 7c4f59269c4c8cf984c91190406be0a2de8499f8. Tracked files clean; six pre-existing untracked paths preserved.
- User clarified that independent labelled example data is desired. No request for fabricated real patient measurements.
- Ruling: Continue in current checkout/main rather than introduce a worktree — user named the actual project path and previously specified main; tracked baseline is clean.

- Task 1 complete: 5b1886e; 4 backend API tests, 3 calendar helper tests and Vue type check passed.
- Task 2: analysis source scope, practice/config grouping, same-version objective summaries and patient-switch protection implemented; 264 frontend tests and build passed before adding 3 additional controller tests, which also passed.
- Task 3: isolated dataset generates 184 parent/result records per one staff owner, including 112 piano sessions (14 variants), 40 ballet sessions, 8 assessment sessions, 16 tapping results and 8 guided sessions; focused seeding and API tests pass.

- Final verification: 270 frontend tests, both base builds, 461 backend passed / 1 skipped; seed/API final focused 8 passed. Independent follow-up review verified all five fixes and timezone regression with no remaining P1/P2 findings.
- Responsive browser QA: 14 piano variants and 5 ballet exercises, guided and tapping charts, scope isolation, calendar navigation and readonly detail views; screenshots retained. New dancing cover replaces the seated variant by explicit user request.
- Commits: 492c9a7 (trends/reports), 71fb520 (showcase/cover/copy). Deployment and cleanup are in progress; final task checkbox below remains pending until production verification.
- [ ] Complete production verification, reserved-demo seeding, push/main alignment and deployment staging cleanup.
