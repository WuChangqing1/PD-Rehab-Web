# Cross-client unified backend release plan

Goal: harden and deploy the supplied Web integration with the existing Flutter contract, preserve existing algorithms/data and all unrelated server projects, then merge into the original main repository and push GitHub.

Architecture: keep Web authentication and patient UUIDs, immutable Flutter snapshots, isolated CausalNet worker, DB-backed mobile job dispatcher. No automatic metric merging or patient-data export to external LLMs.

Spec: supplied Web_Agent_维护部署_真实目录修正版.md and PD_双端集成交付说明_20261103.md. Current user explicitly authorizes PD production release and final original-repo merge.

## Constraints
- Implementation only in integrated Web source until final controlled merge; Flutter stays read-only unless a blocking interoperability fix requires authorization.
- Do not alter other services, shared Nginx routes, model weights, original algorithms, production identities or existing records.
- Back up PD DB/models/uploads/config; test migrations on a copy and retain rollback capability.
- Keep API v1 field names; add optional response fields only, document version extension.
- No keys, patient media, databases or private weights in Git.

## Review focus
- Cross-user patient/device/job access and revocation.
- Duplicate or conflicting metadata, concurrent review, restart while queued/running.
- Nested inference lock deadlock and real-video bounds.
- Stale frontend responses after patient change.
- Shared server memory and non-PD service continuity.

## Tasks
- [ ] Baseline real dependency tests/builds; inspect deployment and Flutter protocol.
- [ ] Add failing authorization, idempotency, job-lifecycle/bounds and safe-QA tests.
- [ ] Enforce patient grants/creator policy, binding ownership/revocation and filtered snapshots.
- [ ] Implement bounded DB-backed job dispatch, atomic claiming, persisted frame review, expiry/restart recovery; remove nested inference locking.
- [ ] Add source-backed platform knowledge answers, explicit provider status and no clinical-data LLM export; keep unconfigured provider truthful.
- [ ] Fix frontend types/stale detail; test root/subpath and PC/mobile.
- [ ] Rehearse SQLite migration/restore on copy; cross-client actual Dart/API flow if SDK available; report unavailable MySQL/device/provider checks.
- [ ] Review changes, merge scoped files into original repository, commit/push main.
- [ ] Deploy isolated localhost staging first, then PD-only production backup/migration/service restart/static update; verify other service PIDs/config hashes.
- [ ] Deliver maintenance report with exact results, screenshots, rollback and commit.
