# Platform release implementation plan

Goal: implement the six authorized requirements on current Web and App sources without schema, algorithm or unrelated UI changes.

Spec: ../../platform-release-20261119/request.md (user-provided execution specification).

Architecture: explicitly reviewed document manifest and bounded lexical chunk retrieval; authenticated document viewer; current SQLAlchemy patient access scope for reports and exports; server-rendered PDF; verified APK metadata; official Shorebird only. Existing provider remains unchanged. No production action before final approval.

Baseline: Web 4794609, App cf12656, production Web 4794609 active. Original root dirty and left intact. Work branches codex/platform-release-20261119 in separate clones under _deploy.

## Task 1: Document hosting and evidence retrieval
- [ ] Review documents and create explicit publishable manifest with permissions, hashes, versions and inventory exclusions.
- [ ] Add failing tests for allowlists, traversal, XSS/link handling, permission-filtered retrieval and stable citations.
- [ ] Implement document service, viewer and knowledge integration with existing provider; incremental hash-based chunk cache; removal handling.
- [ ] Run document/expert/API tests and frontend tests/build; commit only owned files.

## Task 2: Persistence and authorized structured export
- [ ] Audit every model/data object, existing file retention and export, including volatile states.
- [ ] Write failing tests for patient authorization, safe field allowlists, deleted media and integrity.
- [ ] Implement JSON/CSV export with scope, audit, hashes and no credential material. Expose entry within existing patient/report page in integration with Task 3.
- [ ] Verify and document audit, gaps and backup manifest; commit only owned files.

## Task 3: Follow-up PDF report and date UI
- [ ] Test inclusive UTC+8 dates, cross-year/month, single-day/all-history, patient auth, empty/large results.
- [ ] Reuse native and App records, version-separated metrics and plans; generate Chinese A4 PDF server-side without public temporary files.
- [ ] Add date dialog and authenticated download to existing FollowUpPage; integrate JSON/CSV actions from Task 2.
- [ ] Verify PDF pages, relevant tests and frontend build; commit only owned files.

## Task 4: APK and official hot update
- [ ] Audit package, signing certificate/config, SDK, current installed APKs, Shorebird and connected devices; consult official current docs.
- [ ] Add tested, fail-closed approved artifact metadata and login download UI (no fallback to debug APK).
- [ ] Implement official Dart updater and release signing guard; no new signing identity; preserve data/capture/sync.
- [ ] Analyze/test/build where supported; create genuine Shorebird Release and staging patches only with credentials, compatible SDK, original signing and test device. Report unavailable prerequisites rather than invent IDs.

## Task 5: Integrated delivery and release gate
- [ ] Run baseline and modified full suites, classify old/new failures; isolated Alembic upgrade/downgrade rehearsal if no schema change.
- [ ] Browser responsive CN/EN, docs, export, PDF and login regression; isolated prerelease only without production restarts/migrations.
- [ ] Produce all seven requested guides with actual counts/results and rollback; branch push/PR only after secret review.
- [ ] Present concrete production delta, evidence and rollback for final approval; do not deploy or push main before that approval.

## Review focus
Revoked patient access; untrusted Markdown links/images; misleading mixed metrics; end-date/timezone truncation; debug signing or an ordinary APK incorrectly advertised as Shorebird-enabled.

## Shared interfaces
Task 1 adds /api/documents and /docs/:documentId, filtered by caller role. Task 2 exports a patient payload reused by Task 3; the agents must agree exact service signatures before using them. Task 4 owns artifact router and LoginPage only. Root owns router/deps registration and shared configuration changes unless delegated explicitly.
