# Training face recordings, protocol 1.2

Web release candidate dated 2026-11-04, based on `cb75a00dbb75d41aa180e452ead64179e96baab4`. Validated in isolated staging; not deployed to production. See [validation and release gates](TRAINING_FACE_VIDEO_VALIDATION.md).

## Scope

`/api/integration/v1/face/recordings` accepts resumable 4 MiB chunks associated with one existing immutable Flutter training record and its device/profile/patient binding. Whole-file hashes must match before processing. Original Flutter metrics are never rewritten.

The dispatcher handles one bounded short segment per pass, with overlap and source file/time information. Candidates require explicit preview and confirmation in **Follow-up → Mobile records → Details → Training face recordings** before a real CausalNet job is submitted. No automatic approval or aggregate mood/clinical score is provided.

## Prerequisites

- Back up the database and media before applying the migration through your established release procedure.
- Use the existing Python environment and model configuration.
- Install system `ffmpeg` and `ffprobe` with H.264 encoding support.
- Run `python -m alembic upgrade head` from `backend`; expected revision `l8a0b2c4d6e8`.
- Set `TRAINING_VIDEO_ENABLED=true` and `MICRO_EXPRESSION_ENTRY=causalnet` in the server environment.
- Build and deploy the updated frontend. Keep the existing authenticated HTTPS reverse proxy.
- Run the backend as the existing **single instance/dispatcher**. This patch does not implement distributed leases.

`capabilities` reports `face_recordings_ready` only when the feature is enabled, both media tools are present, and the configured CausalNet model is ready. No new LLM provider configuration is needed; videos are not sent to the chat provider.

## Lifecycle

Uploads expire after 24 hours; review expires after 7 days. The dispatcher removes terminal source and derived clips after 24 hours. Training results are stored on the recording parent and do not create a general assessment. `DELETE` cancels children, deletes owned results/media and leaves the original Flutter training record intact. Late inference rechecks cancellation and binding before publication.

Failed analysis can be retried at most twice within retention, using the already received source video, through `POST /{id}/retry`. Frames and all task operations require object authorization. Tokens, private paths and raw media are not returned as public URLs.

## Validation

The isolated staging endpoint returned real model output after explicit review of a publicly sourced synthetic clip. Physical front-camera capture and reading the result in the new Android build remain joint acceptance gates. See the validation report for test counts and limitations.

See `training_face_openapi-v1.2.json` for request definitions. Keep the original v1 short-clip endpoints intact.
