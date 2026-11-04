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

Once a plan has a versioned snapshot, the highest nonnegative integer
payload.snapshot_revision is preferred. Unversioned snapshots stay in history
and cannot replace it. An unversioned-only plan uses receipt order. The Android
client must persist the counter and increment it for each changed snapshot;
late lower revisions remain in history. Same-revision ties use receipt order
and indicate a client protocol error if the snapshot content differs.
Deletion/pausing is not inferred from missing rows. Dates only show progress
explicitly present in the snapshot.

The Web record panel refreshes while visible approximately every 15 seconds.
An open snapshot detail or version history stays stable, and the manual refresh
button remains available. This is a read refresh; Android uploads still require
a client version with a durable queue and automatic retry.
