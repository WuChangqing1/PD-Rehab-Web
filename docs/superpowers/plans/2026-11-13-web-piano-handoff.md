# Web piano patient pacing and hand cues — 2026-11-13

## Before / after

| Item | Existing standard / old session | New patient-facing start |
|---|---|---|
| Basic BPM | 60; calibration may override to personal40–160 or fallback50/60/70 | 40 |
| Density / cue spacing | 1 / 1000ms | 1 / 1500ms |
| Cue lead | 700ms | 1200ms in snapshot `cue_lead_ms` |
| First target / actual cue onset | 700 / 0ms | 1200 / 0ms |
| Judgement window / scoring | 300ms | 300ms, formulas unchanged |
| Auto baseline / round adjustment | Automatically replaces selected configuration | Explicit doctor toggle, initially off; custom edits turn it off |
| Guided BEGINNER demonstration | 60BPM: quarter1000ms, half500ms | 40BPM: quarter1500ms, half750ms |
| Guided INTERMEDIATE / ADVANCED | 80 / 100BPM | 80 / 100BPM |

Standard button restores canonical settings (60BPM/300ms/implicit700ms lead); custom BPM/window/length/duration/lead remain available. All six basic modes and nine recipes use recorded lead. GO/NO_GO remains an immediate stimulus (onset=target, existing response-window semantics); withdrawn/memory cues are not revealed. HOLD and OFFSET retain their task timing meaning. The legacy ALTERNATING_HANDS generator serves weak-side-biased random hand cues, which can repeat a hand; its algorithm was preserved and the display follows actual bindings.

Left is blue #1D4ED8 on #EFF6FF; right is orange #C2410C on #FFF7ED. Actual targets carry hand text and physical key letters. Simultaneous targets show both hands; touch quick buttons emit each current hand's actual binding. Demonstrations retain their actual hand. Guided-song keys receive selected hand from page→stage→keyboard, including demo letters. NO_GO/withdrawn cues show no target hand. Added DOM selectors `data-hand`, `data-key-code`, and `data-testid=piano-cue-hands/piano-pacing` support verification.

## Recorded data and compatibility

No score formulas, event timestamp clock, synthetic-source exclusions, or raw metric recomputation were changed. New optional lead is accepted by backend schema and retained in `difficulty_before_json`, while actual cue onset/target are still raw event values. Same target hit now has response latency1200ms instead of700ms because the cue really appears500ms earlier. It must not be interpreted as clinical change. Follow-up configuration fingerprints include `cue_lead_ms ?? 700`; absent legacy lead and explicit700 remain compatible, while1200 is grouped separately. Parameter labels show actual lead in seconds.

New guided configurations store `pacing_version=guided-song-pacing-2`; raw score replay remains `guided-song-1`. Historical guided configs missing the pacing version retain their60BPM floor, and persisted60BPM sessions can append/finish/replay without deriving BPM from the updated table. New beginner40BPM sessions never accelerate to60 on poor performance. Guided follow-up already groups actual persisted segment1+2 BPM, so new40 and historical60 are separated. Demo scheduling reads persisted session BPM; performance replay/audio reads actual raw events.

When automatic adjustment is off, completion reports MAINTAIN with unchanged actual next-round settings and records proposed engine decision/changes within applied_rules for audit. No fake or forced scores are introduced.

## Verification

- Frontend npm test:358/358; Vue typecheck and Vite build pass.
- Full backend suite with pdPython:602 collected,600passed/2skipped, exit0. Existing warnings: Starlette testclient, duplicate playback operation ID, deliberate NumPy overflow test.
- Stronger targeted snapshot regression rerun passes:1200 lead accepted/persisted, raw onset0/target1200 stored, server recomputation returns latency1200 and timing error0.
- Guided tests cover new beginner40, persisted old60 append/replay/complete, and poor-performance floors for both.
- Real Vue keyboard mounted in local Vite/Chromium: generated LEFT/RIGHT/BOTH targets at1440×900,820×1180,390×844 and100%/200% root font; correct hand labels/fill/outline, no viewport overflow, correct left/right quick-button emitted codes. Evidence: `.validation/piano-pacing/check.mjs` and keyboard screenshots. This isolates the component and is not full authenticated patient-start acceptance or browser200%zoom.
- `git diff --check` passes. No staging/commit/deploy performed by this worker. No production/patient data used.

Coordinator still owns full page/browser acceptance, two-base final build/release, and patient-start/countdown/identity/no-autosave browsing checks. Port5188 Vite session80832 was used only for component QA.


## Follow-up serial-runner correction

Independent review found that custom60BPM with requested1200ms lead announced the second cue later than its recorded onset because the serial runner still waited for the previous judgement window. Added actual-runner red/green tests and a shared `pacedDifficulty` normalization before launch snapshot and defensively in the runner. For explicit new lead profiles, effective lead is bounded by actual next-target minus previous judgement/hold/response close minus1ms; density, ramp rates and offbeat recipe spacing are taken from generated timelines. The calculation converges before cue generation/snapshot. UI shows effective lead and explains clamping. Configurations with windows already overlapping the next target cannot have any positive safe lead; start returns a readable slower-tempo/shorter-window error. GO/NO_GO remain immediate target-time stimuli, with their response-window timing preserved, and hidden cues stay hidden.

Actual runner examples:60BPM/request1200→849ms;40BPM/request2000→1349ms;40BPM/request1200→1200ms unchanged. Density2 at60BPM→349ms. Default HOLD/RELEASE and OFFSET at40BPM require599ms lead because the previous hold/offbeat window occupies more of the interval. Snapshot records the effective value. Tests step the real runner to every recipe cue's nominal onset and assert that exact cue is current. Legacy absent-lead configurations retain original700ms behavior, including existing serial-overlap limitations at aggressive legacy settings; old records are not retrospectively changed.

Updated frontend result:373/373 tests, including20/20 real-runner tests, build passes. Earlier358 count preceded this correction. Full backend rerun after the correction:602 collected,600passed/2skipped, exit0.
