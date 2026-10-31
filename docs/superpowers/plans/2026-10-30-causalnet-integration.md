# CausalNet Local Integration Implementation Plan

**Goal:** Run an actual video through selected trained CausalNet weights and the existing assessment result/storage/viewing flow, locally.

**Architecture:** Keep MicroFlow support intact. Add a CausalNet runtime with a persistent, isolated Python worker so optional model dependencies do not change the Web interpreter. Use the author's published TV-L1/strain/normalization protocol; implement and version a face alignment adapter explicitly. Manual onset/apex/offset selection, no invented spotting or PD probabilities.

**Tech Stack:** Existing Vue/TypeScript, FastAPI/SQLAlchemy; CPU PyTorch worker, OpenCV contrib TV-L1, MediaPipe face detection.

## Constraints

- User delegates implementation choices. On 2026-10-31 the user supplied a phone video and explicitly authorized commit, push and deployment after successful verification.
- Preserve unrelated untracked files and existing algorithms. No migrations or real patient data changes.
- Weights/source/video remain outside Git; strict loading with safe tensor loading and hashes.
- s12.pth is an engineering candidate, not a clinically validated winner. Labels negative/positive/surprise only; PD probability null.
- 25/30 FPS is accepted as real input, never relabeled/interpolated to pretend it was captured at 100/200 FPS.
- No false training-contract or clinical-validity flags. Identify author-derived flow protocol and adapted face cropping separately.

## Tasks

- [x] Tests first: ordered triple keyframes, missing/invalid resources, no writes on failed inference; preserve MicroFlow two-frame behavior.
- [x] Implement bounded sequential video decoding, single-face alignment and author-protocol four inputs; verify numerical behavior and real source feature tensor compatibility.
- [x] Implement persistent worker with checkpoint/source hashes, strict state load, finite outputs and temporal-response diagnostics; runtime configuration remains explicit.
- [x] Extend adapter/API to offset_frame and reuse existing result schema. Make failed analysis transactional for new adapter.
- [x] Extend UI to three keyframes with preview/frame selection; clear stale selection on video/patient change and preserve Chinese/English.
- [x] Configure local ignored model resources and isolated API/browser test environment; run real weights through video, storage and result viewing.
- [x] Run targeted/full regression, frontend test/build, review and PC/mobile browser checks. Record limitations and reproduction steps.

## Review focus

Malformed media or invalid frame triples must not create results/media; missing worker dependencies must not make startup hang; worker errors must not leak into another patient's request; concurrent inference must be serialized; negative/positive are emotion labels, not PD diagnosis; arbitrary camera input is not the training distribution.

## Verification ledger (2026-10-31)

- Real phone video: local inference, API save/read and browser use passed; no private video transferred to server or Git.
- Final backend regression: 495 passed, 1 skipped; targeted final cases 41 passed, 1 skipped.
- Frontend: 307 passed, root/subpath builds passed. PC 1440/mobile 390 checked; responsive viewport is not a physical-device test.
- Reviewer findings fixed: multipart metadata, transactional persistence, camera DOM lifetime, stale patient history.
- Server cold model startup and explicit synthetic public-image motion-video inference passed in separate CPU venv, no clinical DB writes.
- Deployment and push authorized; release activation and final checks are the remaining release steps.
