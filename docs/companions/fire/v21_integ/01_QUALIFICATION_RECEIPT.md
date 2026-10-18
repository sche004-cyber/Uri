# EMBER-V21-INTEG-20261018 - Qualification receipt

**Status: QUALIFIED CANDIDATE - NOT INTEGRATED.** Independent review pending re-review at the exact receipt commit
(see section 6). Not frozen, not tagged, not pushed, not deployed. Owner decisions listed in section 7 stay open.

| Item | Value |
|---|---|
| Branch / worktree | `milestone/ember-v21-integ-20261018`, `D:\uri-dev\uri-ember-v21-integ` (local only; OD-2) |
| Base | canonical `348677b79610d6e261885531bb2e2a95b5253315` |
| Ember source | preserved V2.1 `d6a8313109ad58d4dd6d51431afba33491b1ac32`, handoff `4a70d9e7` |
| Merge | `ce972cc2` (parents `348677b7`, `d6a83131`) |
| Code candidate (tested live) | `6bdaf86e0e1bba05ab503cc69735b273c363cb24` (tree `f61d9581`) |
| Final candidate | `67d61d3a` = `6bdaf86e` + two comment-only edits (R2-02: `companion_orb.dart` doc comment, `pubspec.yaml` comment); gates re-run at `67d61d3a` (section 2); later commits docs only |
| Runtime for live runs | `D:\uri-dev\uri-ember-rt`, materialized from `0533d2a4` (`evidence/runtime_materialization_receipt.json`). `0533d2a4..6bdaf86e` changes no runtime-copied file; `live_session.py` re-verifies every copied file byte-identical in runtime and candidate before each run. |
| Acceptance criteria | `00_ACCEPTANCE_CRITERIA.md`, written before qualification; D-1 owner ruling recorded there (criteria unchanged) |

## 1. Commits

| Commit | Content |
|---|---|
| `ce972cc2` | Merge of `d6a83131`; 3 conflicts resolved (oi_sources.dart, voice_input_settings.dart, ws_integration_test.dart); excluded material removed from the tree |
| `0533d2a4` | Design count 11 -> 12 (UI V2 pin named in the handoff); `CompositeCompanionSource.owned` so the integrated Oi source and Ember's success-hold timer are disposed; Initializing tests aligned with the merge resolution |
| `6bdaf86e` | Review R1 repairs (R1-01, R1-04, R1-06 owned-dispose test, R1-07 header comment, R1-08, R1-09, R1-10) |
| `d98873fa` | Receipt, live evidence, harness (docs) |
| `67d61d3a` | R2-02: Ember comments no longer say Blender / `companion_art/fire` (comment-only) |
| receipt update | R2 corrections to this receipt and new evidence logs (docs only) |

## 2. Automated gates (all COMPLETED_WITH_RESULT)

| Gate | Result | Evidence |
|---|---|---|
| `flutter analyze lib test tool` at `6bdaf86e` and `67d61d3a` | 0 errors, 5 info (rc 1 from info only) | `evidence/analyze_6bdaf86e.log`, `evidence/analyze_67d61d3a.log` |
| Full Flutter suite at `6bdaf86e` and `67d61d3a` | **827 passed, 5 skipped, 0 failed**, rc 0 (both) | `evidence/full_flutter_test_6bdaf86e.log`, `evidence/full_flutter_test_67d61d3a.log` |
| Full suite after the merge (before repair) | Tree: merge `ce972cc2` plus the uncommitted 11 -> 12 pin edit later committed in `0533d2a4` (the log has no commit header; R2-07). 4 failures: 2 Initializing tests (merge semantics), 2 `uiv2_postint` UIV2-F3 (pending Ember timer). The same `uiv2_postint` file passes on clean `348677b7` (21/21), so the timer leak was Ember-caused; repaired in `0533d2a4` | `evidence/full_flutter_test.log`, `evidence/baseline_348677b7_uiv2_postint.log` |
| T0-T5 atlas gates | Same as closure: all clips pass T0-T3/T5; T4 FAILS only for `depleted` (fringe 14 px) - carried owner decision, unchanged | `evidence/tgates/` |
| `scripts/ws_frozen_check.py` | `unapproved_protected_changes: []`, identical output to clean `348677b7` | `evidence/ws_frozen_check.txt` |
| Boundary diff vs `348677b7` (logged at `ce972cc2`; re-checked clean at `d98873fa` by review R2) | no change under `uri_operational_intelligence/`, `scripts/run_uri_*`, launch scripts, `.gitignore`, `scripts/ws_frozen_check.py`, `uri_ui/windows/` | `evidence/boundary_check.txt` |
| Excluded material | 0 tree files under `docs/companions/fire/{reference,v2,evidence}`, `v21/evidence/fidelity`, `companion_art/fire`; V1 history docs and `before_after.jpg` removed (R1-01/R1-10); no blob of the reference folder in the tree | `git ls-tree` checks |
| Windows release build (production `lib/main.dart`) | rc 0 at `0533d2a4` and at `67d61d3a` | `evidence/build_windows_release_main.log` (0533d2a4), `evidence/build_windows_release_main_67d61d3a.log` |

## 3. Live Windows qualification

Real production `main()` through `integration_test` on Windows, real integrated worker, paired Core (port 18300) and
Runtime v1 Brain (Qwen3.6-35B-A3B MoE, frozen config, hash unchanged before/after), own GPU lease without override,
preferences and APPDATA redirected to fixtures. Window checks by `harness/win_probe.py` with Win32 APIs, screen
capture and OS input (`SetCursorPos` + `mouse_event`). Not a human usability study; no physical keyboard/mouse
qualification claimed.

| Run | Purpose | Result |
|---|---|---|
| `l1-first` (10:05-10:11 IST) | First-time user, Brain lifecycle and conversation | J0-J5 PASS. Window checks of this run **INVALID** (probe attempt 1, see 3.2) |
| `l2-returning` | Returning user + window checks with fixed occlusion handling | restore, Initializing, borderless, transparency, click-through-outside, 1.25x PASS; Ember click and drag FAIL - harness artifacts (3.2 items 3 and 4) |
| `l3-input`, `l4-input` | Input root cause | l3: Flutter received 0 pointer events; l4 with device events propagated: click reveals controls, drag moves window |
| `l5-returning` | Repeat | all PASS except Ember click - second harness artifact (3.2) |
| `l6-returning` (10:21-10:23 IST) | Final window run on `6bdaf86e` | **all checks PASS, 0 failures** |

### 3.1 Results by criterion

| AC | Result | Evidence |
|---|---|---|
| AC-10 borderless | **PASS**: client rect = window rect (440 x 680), DWM extended frame = window rect (0 px shadow frame), no non-client area. Note: style bits keep `WS_CAPTION` (window_manager frameless keeps the style and removes the frame in `WM_NCCALCSIZE`); judged by the rendered result | `live/l6-returning/probe-transparent-1.0.done.json` |
| AC-11 per-pixel transparency | **PASS** at 1.0: 90.8 % transparent, 7.1 % blended, 2.0 % opaque, window-edge alpha max 0, show-through inside the silhouette box 5.7 %. The window also has a complex hit/visible region (`COMPLEXREGION`, orb + controls): pixels outside it are clipped by the region; the blended pixels inside it are true per-pixel alpha. Review R2 cross-checked the magenta/green alpha against black/white captures (identical at 1.0x and 1.25x). Window checks ran with reduced motion on (a still frame, needed for the two-capture alpha recovery); animated clips were seen in l1 screenshots, not alpha-measured. Dark and light backdrops: no box, matte or fringe from the window | `live/l6-returning/win-transparent-1_0-{black,white,magenta,green,alpha}.png` |
| AC-12 click-through | **PASS**: OS click at a transparent point reached the window behind; OS click on Ember reached URI (`WindowFromPoint` = companion, backdrop click count unchanged, companion controls shown) | `live/l6-returning/probe-click-through.done.json`, observations |
| AC-13 drag / 1.25x | **PASS**: OS drag moved the window (+57 px, clamped to work area). 1.25x: l6 transparency PASS (87.6 % transparent / 7.1 % blended / 5.4 % opaque); in l6 the 1.25x capture was taken after the Ember click, so it includes the companion controls (bbox [21,91,418,353]) and is not an Ember-only size measurement (R2-01). Ember-only silhouette at 1.25x from l2/l5 (same code `6bdaf86e`, controls closed): bbox 142-319 x 155-354, inside the window, 87.8 % / 9.3 %. F-SIZE-1 disc crop inside the renderer unchanged (owner decision) | `live/l6-returning/probe-drag.done.json`, `live/l6-returning/probe-transparent-1.25.done.json`, `live/l5-returning/probe-transparent-1.25.done.json` |
| AC-14 Brain journeys (l1) | **PASS**: Ember in gallery (12 designs); "Brain not running" (unavailable) -> Initializing "Loading model" -> idle at READY (load 56.7 s, calibration 155.7 tok/s); turn "Say hello in three words." ok, thinking -> speaking -> success -> idle; Brain stopped -> unavailable "Brain not running", no Initializing while stopping; restart -> Initializing -> idle; turn "7 plus 8" -> "15" ok; choice `ember` persisted; returning runs restore Ember | `live/l1-first/observations-first.json`, `companion-timeline-first.json`, `brain-phases.json` |
| Settings persistence | **PASS** (l1 J5, l2/l5/l6 R-ember-restored) | observations |
| Performance | Brain calibration 155.7 tok/s with the Ember window open (the host's fit check rated the start AT_RISK, margin -210.4 MiB, no override; calibration 155.7 tok/s against a 60 tok/s threshold, state READY; the post-load residency sample is still AT_RISK with 1730 MiB non-local); UI window dedicated VRAM median 172.7 MiB (l1) / 179.0 MiB (l6), Debug runner; adapter peak 15.77 GB of 16.0 GB. Not comparable 1:1 with closure (147 MB, Release build on UI V1 host); no equivalence claimed. Ember-vs-Solar series not re-run (Ember code unchanged since closure) | `live/*/resource-samples.json`, `brain-ready.json` |

### 3.2 Correction history (kept, not overwritten)

1. **Probe attempt 1 (l1) INVALID.** The companion window was below the owner's Claude desktop window. Captures showed
   that app; the "Ember" click (270,351) and the drag (270,351)->(150,411) landed on the Claude desktop sidebar near
   the "cheta" group header. The probe was stopped. Evidence kept in
   `live/l1-first/probe_attempt1_INVALID_occluded/`. Fix: raise the companion without activation before captures,
   refuse captures when any sample point belongs to a foreign window, verify `WindowFromPoint` before any input.
2. **Borderless by style bits was the wrong test** (l1/l2 marked FAIL on `WS_CAPTION`). Corrected to the rendered
   result (client = window rect, no DWM frame).
3. **l2 drag FAIL: harness artifact.** `LiveTestWidgetsFlutterBinding` drops device pointer events by default; l3
   proved 0 events reached Flutter. With `shouldPropagateDevicePointerEvents = true` (l4) click and drag work.
   (Corrected after review R2-06: the l2 Ember-click failure itself had the same cause as l5 - the backdrop count went
   0, 1, 2, so the click landed on the raised backdrop.)
4. **l5 Ember click FAIL: harness artifact.** The preceding click on the backdrop activated it and Windows raised it
   above the companion. The probe now re-raises the companion and re-checks before the second click (l6 PASS).

## 4. Merge semantics (D-1, EI-1)

- Brain-state authority is canonical FCV-10 (`brainNotReadyPresentation`); Ember changes only the look: Initializing
  replaces FCV-10's `working` startup state when `brainStartingDetail` accepts both snapshots and the running host is
  not in `brainHostNotStarting`.
- **D-1 (owner APPROVED 2026-10-18):** `WAITING_FOR_LEASE` keeps "Waiting for GPU" (unavailable).
- **EI-1 (recorded limitation, pre-existing canonical behaviour):** FCV-10 prefers `brain_health` readiness without
  comparing snapshot ages, so a newer host FAILED with readiness LOADING shows "Loading model" (working), and an older
  health report next to a fresh STOPPED shows its phase. Ember V2.1's stricter R3-01/R5 rules are not applied there.
  Live runs did not hit it. Candidate for a separate canonical FCV follow-up.

## 5. Changes to UI V2-owned files (AC-4)

| File | Change | Basis |
|---|---|---|
| `test/living/ui_v2_test.dart` | design count 11 -> 12 | handoff section 5 |
| `lib/living/living_app.dart` | integrated composite owns the Oi source | regression repair (R1-06 records the deviation) |
| `lib/living/companion/companion_sources.dart` | `owned` parameter | same |
| `lib/living/screens/settings/companion_gallery.dart` | Ember caption "painted animated clips" | R1-09 |
| `lib/living/integration/oi_sources.dart` | conflict resolution + R1-04 | merge |
No frozen or protected path changed (section 2).

## 6. Independent review

| Round | Reviewer | Commit | Verdict |
|---|---|---|---|
| R1 | independent read-only subagent (Codex quota-blocked until 2026-10-22, established 2026-10-17, not retried) | `0533d2a4` | ACCEPT WITH FINDINGS (0 HIGH, 2 MEDIUM, 8 LOW); repaired in `6bdaf86e` except R1-02 (owner ruling, now approved), recorded items R1-03 and R1-05, the unowned test sources of R1-06 (recorded in section 7) and the Blender comments of R1-07 (fixed in `67d61d3a`) |
| R2 | independent read-only subagent | `d98873fa` | ACCEPT WITH FINDINGS (0 HIGH, 1 MEDIUM receipt citation, 6 LOW); R2-01/02/05/06 corrected here and in `67d61d3a`; R2-07 corrected except the harness items recorded in HARN-2; R2-03/R2-04 recorded as HARN-2. Report `review/R2_report.md` |
| R3 | independent read-only subagent (focused on R2 repairs) | `4053bf69` | ACCEPT WITH FINDINGS (0 HIGH, 0 MEDIUM, 3 LOW wording); all three corrected in the following docs commit. Report `review/R3_report.md` |

Subagent acceptance is not owner approval and not driver-counted lifecycle acceptance.

## 7. Open items

| ID | Item | Class |
|---|---|---|
| Fidelity AC-F1/AC-F3, F-LIGHT-1, T4 depleted, F-SIZE-1, F-START-GAP, OD-2, AC-P1 | carried from closure, unchanged | owner decisions |
| EI-1 | FCV-10 snapshot-age handling | recorded limitation (canonical) |
| R1-05 | Initializing ranks just above idle (handoff priority), so voice/activity states hide the FCV-10 startup headline | recorded, per handoff section 6 |
| PERF-1 | Live VRAM measured on Debug runner only | limitation |
| HARN-2 | Harness gates (`harness/win_probe.py`) not tightened after the runs, kept identical to what ran: the Ember-click gate does not itself require a Flutter-side reaction (R2-03; l6 records controls visible), the transparency gate has loose thresholds and no frame-stability check (R2-04; l6 window checks ran on still frames and R2 cross-checked them). Per-run probe hash and the l1 driver version are not recorded, and `run_live_ui.py` records `git status --untracked-files=no` only (R2-07, R3-03) | limitation; tighten before reuse |
| R2-02 tests | `test/ws/fcv_context_rail_test.dart:68`, `test/ws/ws_hardening_test.dart:480` build an unowned `OiCompanionSource`; no leak today (no ok turn finishes there) | recorded, not changed (UI V2 tests) |
| HARN-1 | Probe attempt 1 sent one click and one drag to the owner's Claude desktop sidebar (section 3.2) | disclosed; owner may check the sidebar "cheta" group |
| Integration | Not requested; requires owner authorization and OD-2 resolution before any push | boundary |
