# Backend staff accounts and canonical names validation

Backend work is isolated in `_deploy/staff-accounts-20261118-web`, baseline `1c15a63`.
No commits, pushes, migrations against production, SMS sends or deployment were performed by the backend implementer.

## Contracts

- Public `POST /api/auth/register` accepts username/password/display_name/phone/requested_role DOCTOR or NURSE; returns 201 pending application only. Password is bcrypt hashed and never serialized. No StaffUser exists until approval. Names are normalized/validated; extra fields such as role/is_active/patient_id are rejected.
- Username: ASCII letters/digits/underscore, 3–32, normalized lowercase; collision checks use case-insensitive comparison across users and pending staff applications, including patient registration. Password: 8–64 characters, at most 72 UTF-8 bytes. Registration limit: six attempts per IP per ten minutes per worker, complementing deployment edge limits.
- ADMIN-only `/api/auth/staff-applications`, review, staff list and staff PATCH implement the approved contract. Application detail uses explicit fields: id, username, display_name, phone, requested_role, status, reason, reviewed_by, reviewed_at, created_at, user_id. StaffUser retains its existing public schema (no phone field); phone remains in the application.
- SQLite writes use BEGIN IMMEDIATE for cross-process serialization. Approval is atomic and repeated same-decision approval returns the same account; opposite decisions conflict. Management rechecks the acting administrator inside the write transaction. Concurrent demotion cannot remove the last active administrator.
- `PATCH /api/mobile/auth/profile {display_name,expected_name}` compares the canonical patient name, returns 409 on stale name and updates linked patient.name/user.display_name in one transaction. Additional fields are forbidden. Stable IDs, username, hospital number and login identities are untouched.
- GET mobile identity always derives display_name from patient.name, fixing legacy mismatches in responses without writing during GET. Bootstrap also uses canonical name, independent of pagination. Web patient rename updates linked display_name within its transaction and preserves existing expected_updated_at conflict handling.

## Authorization matrix

- Current database role and active flag are checked on every bearer request; unsupported roles fail closed. Mobile session revocation and own-patient scope remain enforced.
- Existing active DOCTOR and approved NURSE share the current single institution workspace. Existing explicit inactive PatientAccessGrant rows remain denied; this is not a multitenancy implementation.
- Nurses may read shared patients, maintain intake/history/medication fields, collect assessments and execute training. Changed doctor_notes are forbidden; an unchanged doctor_notes from a full form is stripped before writing to avoid overwriting concurrent professional changes. Basic fields such as diagnosis_date and medical_history remain allowed.
- Nurses cannot sync TRAINING_PLAN/TRAINING_PLAN_EVENT snapshots on behalf of patients. DOCTOR/ADMIN may. PATIENT own native plan sync is deliberately preserved. Baseline has no Web plan-write endpoint, bulk-export endpoint or raw-metric edit endpoint; none was invented.
- Patient delete/restore is ADMIN only. Completed assessment deletion remains prohibited by the existing service for all users, preserving historical records.
- Nurse assessment delete/discard requires ownership of an unfinished session. Legacy piano/pose pending cleanup requires a matching START audit record for nurses; unknown ownership fails closed. Guided training mutations retain existing owner checks.
- Shared staff may read guided history/detail/audio and face recording/job status/candidate/media views. Recording/job mutations retain operator-or-ADMIN checks. Face recordings with SUCCESS/PARTIAL_SUCCESS/NO_VALID_SEGMENTS require ADMIN for both DELETE and cancel erasure routes.
- Playback capability cookies re-evaluate active database role, patient scope and live device binding for GET/HEAD/download requests. Patient capabilities additionally revalidate mobile session. WebSocket live emotion accepts active recognized staff roles only and rechecks database role/active state during chunks.

## Migration

New head `p2e4f6a8b0c2`, parent `o1d3e5f7a9b1`, adds only `staff_applications`. No existing business table columns or rows are modified.

`test_staff_migration.py` upgrades a fresh database and a populated prior-head SQLite database, compares every pre-existing table row, and checks integrity/foreign keys. Existing chain roundtrip and external-login migration tests were updated for the added table/head. Downgrade refuses to erase nonempty staff applications. An empty staff application table may be removed before an older migration refuses to erase live external identity bindings; older business rows remain unchanged.

## Validation evidence

Interpreter: `D:/App/Business/Coding/Python/Miniconda/envs/pd/python.exe`.

Initial TDD failure evidence: `validation/staff-red.txt` (missing registration/profile and nurse shared access); first green: `validation/staff-green.txt`. Follow-up boundary red/green logs cover canonical bootstrap, cleanup ownership and control characters. Core tests: six passed. Security tests cover role changes/deactivation, pending namespace collisions, no secret serialization, rejection, rate limiting, own patient plan sync, explicit denies, playback GET/HEAD revocation, shared reads/foreign mutation denial, completed erasure, legacy cleanup and concurrent account invariants.

Focused regression: 38 passed in `validation/staff-focused-final.txt`. Pre-review full suite: **616 passed, 2 skipped, 3 warnings in 182.12 seconds**, exit 0, `validation/staff-full-final.txt`. Skips are existing optional fixture/source checks. Warnings are existing TestClient deprecation, playback GET/HEAD duplicate OpenAPI operation identifier, and NumPy overflow in its explicit nonfinite guard test. `git diff --check -- backend` passed. Logs contain synthetic fixtures and test JWTs only; the markdown handoff is intended for inclusion, raw console logs need not be committed.

The backend does not claim physical camera/model/SMS/device acceptance. SQLite account concurrency is tested; equivalent non-SQLite cross-table username concurrency has not been exercised and this deployment remains SQLite.


## Independent review fixes

Two reproduced authorization issues were fixed after the first full green run:

- Piano idempotent retry previously returned another staff member's round and emitted a fresh caller START audit, which could satisfy an ownership check. New piano rounds now persist their first server START audit atomically with round creation. Existing retries require that original owner; nurse cleanup and can_clear use the first START owner exclusively. Legacy later duplicate START events do not grant ownership. No difficulty JSON, metric algorithm, fingerprint or table schema was changed. Own retries preserve the same round ID.
- Legacy in-process jobs previously exposed all outcomes in list/detail. Jobs now carry server-assigned patient_id from the assessment session; list/detail enforce the same current patient scope, retaining shared authorized staff reads. Legacy unscoped jobs are ADMIN-only. Patientless/denied job outcomes never appear in staff listings.

Review regression evidence: `staff-review-red.txt` confirms both failures, `staff-review-green.txt` records 13 focused passes including existing concurrent retry tests, and `staff-review-extra.txt` records three explicit regressions including calibration and late duplicate START events. The final full suite after these fixes passed: **619 passed, 2 skipped, 3 warnings in 167.30 seconds**, exit 0; see `staff-full-final.txt`. `git diff --check` passed after the final changes.
