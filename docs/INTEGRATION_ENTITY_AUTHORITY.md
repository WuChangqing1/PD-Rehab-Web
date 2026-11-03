# Cross-client authority and contract revision 1.1

Original v1 field names/paths are unchanged. Original contract JSON is preserved; additive runtime schema is cross_client_openapi_integration-v1.1.json.

| Entity | Authority | Direction / edits | Version / conflict |
| --- | --- | --- | --- |
| staff_users | Web | Names/IDs read-only to Flutter, password hashes never synced | Full paginated patient snapshot + bounded staff list; no staff editing API |
| patients | Web UUID | Read-only snapshot to Flutter; deleted/unassigned hidden | updated_at; refresh snapshot manually, not a durable change cursor |
| device_patient_links | Web | Current staff binds own device profile once; owner/Admin may revoke | Revoked binding cannot be silently rebound/reassigned |
| piano_sessions / guided_song_sessions / pose_sessions / assessment_sessions | Web | Flutter fetches namespaced read-only history | Original algorithm versions kept; never inserted into native Flutter tables |
| external_practice_records | Flutter originals | Immutable append-only Flutter→Web | source_app=origin, schema/task/metric versions, payload SHA256; same source id + different metadata/payload =409 |
| training_plan snapshots | Each origin owns its own | Flutter revisions use content-addressed source IDs | No cross-client mutable plan merge |
| mobile_face_jobs | Web | Client uploads/explicitly reviews; server owns transitions/results | Persisted indices; bounded8 active; 50MB max; 24h review expiry; interrupted inference fails/reconciles |
| expert_chat_turns | Web | Own question/answer saved, no automatic patient record retrieval | Curated sources + configured model; no medical diagnosis/dose changes |

## Patient policy
ADMIN can access active patients; DOCTOR needs explicit patient_access_grants.active or original patient creation audit/assessment ownership/guided-session ownership. Explicit inactive grant overrides all legacy ownership. Existing authenticated Web reads and WebSocket use the same policy, preventing path-switch bypass. Existing already-authorized clinical owners retain access. Soft-deleted patients remain restorable through the original authorized Web workflow; integration endpoints hide them. Admin grant/revoke API is documented in runtime schema; no extra admin UI introduced.

## Current synchronization boundary
This is manual resumable immutable upload plus read-only server snapshots, not continuous editable two-way replication. next_offset is a pagination offset, not an incrementally consistent change cursor or ETag. No background offline mutation merge, automatic tombstone push or unified KPI formula is claimed. Flutter local SQLite v4 and the sync sidecar are not modified in this Web release. Sign-in caches on shared devices still need a separate app hardening release.

## AI privacy / environment
Only the current question plus fixed reviewed snippets goes to the configured model. No patient DB lookup, arbitrary SQL, face video or training record is sent. The user authorized a Windows-local Spark endpoint; server reaches it through loopback-only SSH reverse forwarding. HTTP is accepted only with EXPERT_LLM_ALLOW_LOCAL_HTTP=true and loopback hostname. Browser/mobile clients still use HTTPS to the unified server. Model and tunnel availability depend on the Windows machine. End-to-end HTTPS local QA uses a self-signed test gateway only; production uses the normal public certificate.
