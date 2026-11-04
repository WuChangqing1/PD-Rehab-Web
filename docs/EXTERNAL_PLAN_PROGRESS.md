# Software plan progress in Web

The existing POST /api/integration/v1/records and raw record reads are unchanged.
GET /api/integration/v1/plans takes patient_id, on_date (YYYY-MM-DD), offset,
limit, and optional snapshot_id to inspect one plan's version history. It
groups by patient, device, local profile and record.plan_id before pagination.
Without a known grouping identity, snapshots are kept separate. Old snapshots
are immutable. No database migration is required.

daily_progress is optional. A date with no matching valid entry is unknown,
not zero. For minutes, completed_units is milliseconds and target is minutes.
Plan start is separate from training time and server receipt time.

If every snapshot has a nonnegative integer payload.snapshot_revision, order
by it (the client must increment it for each changed snapshot). Otherwise
display the latest received snapshot, explicitly labelled as such; arrival
order is not a claim of source order. This does not add revision emission to
the Android client. Deletion/pausing semantics are not inferred from missing
rows. Historical dates only show progress explicitly present in the snapshot.
