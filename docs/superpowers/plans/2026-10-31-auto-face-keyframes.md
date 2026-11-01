# Reviewed Automatic Face Keyframes Implementation Plan
> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement task-by-task.
**Goal:** Replace default raw-frame entry with reviewed candidate triplets.
**Architecture:** Bounded versioned spotter runs in existing isolated CausalNet worker; authenticated temporary endpoint returns candidates. Explicit review gate remains until independent evaluation. Existing classification unchanged.
**Tech Stack:** Python/OpenCV/NumPy/MediaPipe, FastAPI, Vue3/TypeScript, pytest/Node tests.
**Spec:** ../specs/2026-10-31-auto-face-keyframes.md

## Global Constraints
- Private video/features/weights/upstream checkouts stay ignored/local.
- No automatic production activation, GitHub push, accuracy claims or classifier changes.
- No persistent records during selection; bounded uploads, frames and memory.

## Review Focus
- Static/blink/camera movement must not become confident expression candidates.
- Apex is displacement peak, not inter-frame speed peak.
- Clip/patient/recording changes and stale asynchronous responses invalidate confirmation.
- Client provenance must be bounded/validated, not trusted model evidence.
- Ambiguous/incomplete clips allow manual recovery without creating records.

### Task 1: Offline spotting
Files: new spotting.py, tests/test_face_spotting.py, docs/auto-face-keyframes.md; ignored probes.
Interface: select_intervals(times, signal, quality) -> candidates/reasons; spot_video(path, aligner) -> structured response.
- [x] Pin/read DMA and SoftNet sources/weights and isolated environment.
- [x] Write RED tests for analytic pulse/plateau, static, incomplete, ambiguity, global motion and frame bounds.
- [x] GREEN bounded per-face displacement extraction + multi-scale interval generation, explicit adapted baseline.
- [x] Real video and negative fixtures; real SoftNet comparison or exact blocker.

### Task 2: API/runtime
Files: causalnet.py, worker.py, assessment_sessions.py, schema/service; tests/test_face_spotting_api.py.
Interface: runtime.spot(video); POST /micro-expression/keyframes no writes; reviewed source metadata on classify.
- [x] RED auth, cleanup/no-write, worker protocol and provenance validation tests.
- [x] GREEN serialized worker operation and temporary upload route, bounded typed metadata.
- [x] Targeted tests and real runtime check.

### Task 3: Reviewed UI
Files: emotion/selection.ts, FaceKeyframeSelection.vue, MicroExpressionPage.vue, VideoCapturePanel.vue, i18n/API; tests/face_selection.test.ts.
Interface: candidates -> reviewed triple bound to clip/revision.
- [x] RED tests for stale replies, changed triplet/candidate, recording and confirmation.
- [x] GREEN automatic find/retry, thumbnails/confirmation and collapsed manual controls in both modes.
- [x] Verify translations, buttons and preserved legacy manual route.

### Task 4: Verify/review/handoff
- [x] Full pytest/npm test, root/subpath build.
- [x] Local real selection/classification/save/readback and failure/zero-write checks.
- [x] Desktop/mobile browser screenshots; fresh whole-change review and blocker fixes.
- [x] Deliver result evidence and missing-data boundary, retain local branch unpushed.

Ruling: user approved execution; proceed inline without another approval. Only one supplied human clip; keep review gate and do not invent a multi-person accuracy dataset.