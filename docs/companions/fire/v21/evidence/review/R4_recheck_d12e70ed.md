# Independent recheck R4: Ember V2.1 final, R3 repairs 0484afdc..d12e70ed

Reviewer: Claude (independent; did not write this work and did not see earlier conversation about it).
Worktree: `C:\uri-wt\ember-review-d12e70ed`, HEAD verified as `d12e70edf979f59fc3e7dc795b4c1fb4b1b5d3b4`, `git status` clean before and after the review.
I treated `R3_repairs.md` as a set of claims to check, not as facts.

## 0. Acceptance criteria (set before the review)

- **A1, R3-01 repaired.**
  - Initializing is never shown while either Brain snapshot (`brain_status` or `brain_health`) shows a failure, stop or stopping state.
  - A normal startup whose snapshots differ in age does not flash depleted.
  - The logic matches what `runtime_v1.py`, `brain_health.py`, `worker_bridge.py` and `ws_brain_host.py` actually emit, and the refresh cadence in `oi_conversation.dart` and `working_system_app.dart`.
  - Tests cover snapshots that disagree.
- **A2, R3-02 repaired.** `WAITING_FOR_GPU` is not Initializing. The mapping agrees with `brain_health`, or the deviation is recorded.
- **A3, every other R3 finding** is repaired, correctly disclosed, or explicitly open. Each claim in `R3_repairs.md` holds.
- **A4, no new defects:**
  - tests pass at d12e70ed;
  - the edited documents contain no unsupported claims;
  - the numbers match the raw data.
- **A5, evidence.** Each file under `evidence/final/` that a claim cites exists and supports that claim.
- **A6, protected paths.** No protected or frozen path changed in `1b5423bc..d12e70ed`.

## 1. Primary evidence I produced

- **`git diff 0484afdc d12e70ed`:** read in full for code, tests, driver and documents. Changed: 35 files, all under `docs/companions/fire/v21/**`, `scripts/fire_companion/size_crop_v21.py`, `uri_ui/lib/living/integration/oi_sources.dart` and `uri_ui/test/living/companion_initializing_test.dart`.
- **Full suite at d12e70ed:** I ran `flutter test` in the review worktree. Result: **`+599 ~5: All tests passed!`, rc=0.** This is the same count as the committed `evidence/final/full_flutter_test.log`.
- **`flutter test test/living/companion_initializing_test.dart -r expanded`:** all 8 tests pass by name, including the 4 new tests in the group "brainStartingDetail decides from both snapshots (review R3-01)".
- **Fidelity "lowest" values:** recomputed with my own script from `r1_raw` and `r2_raw` (`reviewer*.json`) and `r*_key/key.json`, using the per-reviewer `min(v21_worst, v21_mid)` character %. Every number matches; see section 4.
- **T4 on the shipped depleted atlas:** recomputed per frame by calling `transparency_check.gates()` read-only. The worst value is 14 px at frame 8, which matches the JSON. The failure, however, covers most of the clip; see R4-N4.
- **Protected paths:** `git diff --name-only 1b5423bc d12e70ed` against `uri_core/`, `uri_supervisor/`, `uri_supervisor_bridge/`, `uri_harness_adapters/`, `model_lab/integration/`, `uri_operational_intelligence/`, `scripts/run_uri_*`, `scripts/launch_uri*` and `.gitignore`, plus the remaining `ws_frozen_check.py` PROTECTED entries (`c1_bootstrap.py`, `paired_runtime*`, `supervised_runtime.dart`, `settings_shell.dart`, `supervised_execution_screen.dart`) and `ws_brain_host.py`. **No hits.** `1b5423bc` is an ancestor of d12e70ed.

## 2. Producer facts that the R3-01 and R3-02 analysis relies on

- **Both Brain commands read the same readiness.**
  - `worker_bridge.py:446-453` (`_brain_status`) and `:489-519` (`_brain_health`) both call `self._status()`, which is `RuntimeManager.status()`.
  - So `brainStatus['state']` and `brainHealth['readiness']` differ only in **age**, never in derivation.
- **Health is normally the newer snapshot.**
  - `refreshStatus` (`oi_conversation.dart:217-227`) reads `brain_status`, then `brain_catalog`, then **always** `refreshHealth`. Its timer runs every 15 s (`working_system_app.dart:48,119`).
  - The monitor refreshes health alone every 5 s when not busy (`oi_conversation.dart:259-268`).
  - **Exceptions:**
    - a `brain_health` call that throws or times out (`probeTimeout` = 40 s) leaves the older `brainHealth` in place, next to a fresh `brainStatus`;
    - `brain.status` events (`oi_conversation.dart:746-747`) overwrite `brainStatus`. The only producer in `uri_operational_intelligence` emits `DEGRADED` (`orchestrator.py:236`).
- **Brain host state machine (`scripts/ws_brain_host.py`):**
  - `STARTING_HOST` -> `WAITING_FOR_LEASE` (`:179`, possibly unbounded while another URI GPU workload holds the lease) -> `wait_for_gpu`: `WAITING_FOR_GPU` (`GPU_UNMEASURED`, `GPU_CONTENDED`, `VRAM_RELEASE_TIMEOUT`, `GPU_QUIET_WINDOW`) or `RELEASE_WAIT` -> `STARTING` -> `LOADING` -> `FAILED` (`:287-292`) or `CALIBRATING` (`:321`) -> `READY` or `DEGRADED`.
  - `brain_health.py:121-129`:
    - `RECOVERING` for runtime `STARTING`/`LOADING` or host in `HOST_RECOVERING`;
    - `UNAVAILABLE` for `WAITING_FOR_GPU` and `WAITING_FOR_LEASE`.

## 3. Per-finding status

| R3 finding | Claimed | R4 status | Evidence |
|---|---|---|---|
| **R3-01 HIGH**: snapshots of different ages | Repaired | **REPAIRED** (residual LOW items R4-N1 and R4-N2) | See 3.1 |
| **R3-02 MEDIUM**: `WAITING_FOR_GPU` read as Initializing | Repaired | **REPAIRED** (doc-claim error R4-N3) | See 3.2 |
| **R3-03 MEDIUM**: cited evidence not committed | Repaired | **REPAIRED** (stale or unpinned evidence, R4-N5) | See 3.3 |
| **R3-04 MEDIUM**: R2 conclusions overreach | Repaired | **REPAIRED** | See 3.4 |
| **R3-05 MEDIUM**: launch shows depleted first; no live evidence | Owner decision; live run "see section 6" | **STILL OPEN** (disclosed). The cited section 6 is a placeholder (R4-N6) | See 3.5 |
| R3-06 LOW: driver drops first state after a reset | Repaired | **REPAIRED** | `lastState = ''` follows all three `states.clear()` calls (`fire_v21_live_driver.dart:314-315, 406-407, 452-453`) |
| R3-07 LOW: doc comment on the wrong declaration | Repaired | **REPAIRED** | The class doc now sits directly above `class OiCompanionSource` (`oi_sources.dart:51-63`). The new constants carry their own docs (`:9-24`). |
| R3-08 LOW: e43e97a7 failed the suite | "Disclosed in the final report" | **CLAIM FALSE; disclosure missing** (R4-N7) | `grep e43e97a7 FINAL_REPORT_V21_FINAL.md` finds nothing |
| R3-09 LOW: stale startup documents | Repaired | **PARTLY REPAIRED** (R4-N3, R4-N8) | `04` has a dated status note. `FINAL_QUALIFICATION_REPORT_V21.md:172` still says "proposed, not implemented" with no pointer. The deviations from 04 are not recorded. |
| R3-10 LOW: wording | Repaired | **PARTLY REPAIRED** (R4-N9) | C-2 in `08`, decoder one decimal plus caveat, and the R1 audit wording are fixed. The R2 audit wording (`R2_RESULTS.md:10-11`) is unchanged, and a new stale "decoder rounding" bullet was added. |
| R3-11 LOW: size-crop "cut" definition; file count | Repaired | **REPAIRED** | The docstring in `size_crop_v21.py:13-16` now defines "cut". I count 23 non-asset plus 12 asset files under `uri_ui` in `1b5423bc..d12e70ed`, which matches `09:28`. |
| R3-12 LOW: dark blob and hard rim on light desktops | Open, F-LIGHT-1 | **OPEN, disclosed** | `FINAL_REPORT` section 3 and section 11 item 2. Related T4 extent: R4-N4. |

### 3.1 R3-01 in detail (`oi_sources.dart:14-49`, `:137-146`)

The new `brainStartingDetail(runtimeState, health)` works as follows:
- it returns null unless the runtime is `STOPPED`, `STARTING` or `LOADING`;
- it returns null if a **running** host is in `FAILED`, `STOPPED`, `STOPPING`, `RELEASE_WAIT` or `WAITING_FOR_GPU`;
- otherwise it accepts when the health readiness (or the runtime state, if health has none) is `READY`, `STARTING` or `LOADING`, or is `STOPPED` with a host in `STARTING_HOST`, `STARTING`, `LOADING`, `CALIBRATING` or `WAITING_FOR_LEASE`.

Checked against the producers:

- **R3 case 1** (stale `LOADING`; the host then fails, `ws_brain_host.py:287-292`):
  - if the host is still alive with `FAILED`, the function returns null;
  - if the host has exited, `running` is false, the readiness becomes `STOPPED` (the server was stopped) and no starting host exists, so it returns null.
  - Either way the companion is unavailable. **Fixed.**
- **R3 case 2** (stale `STOPPED`; the host reaches `CALIBRATING` or `READY`, and readiness is `READY`):
  - the function returns "Brain loading", so the companion stays calm, not depleted;
  - the next `refreshStatus` gives `READY` and then idle.
  - `DEGRADED` after calibration also stays "Brain loading" until the runtime reads `READY`, which is acceptable.
  - **Fixed.**
- **Normal first launch:**
  - `STARTING_HOST`, `STARTING`, `LOADING`, `CALIBRATING` and `READY` show Initializing then idle.
  - `GPU_QUIET_WINDOW` (only after this host saw contention) and `RELEASE_WAIT` (restart path) show depleted. That is consistent with `brain_health` and the R3-02 ruling.
  - The UI-before-host gap remains (R3-05).
- **Runtime `FAILED`, `ARTIFACT_MISSING`, `IDENTITY_MISMATCH`, `FOREIGN_INSTANCE`, `DEGRADED` or unknown:** the first guard returns null. Readiness `UNKNOWN` (health's status exception) returns null too.
- **Tests:** the new group drives `brainStartingDetail` with disagreeing snapshots in both directions of the R3 cases. All pass.
  - Gap: the "health older than status" direction is not tested (R4-N1).

### 3.2 R3-02 in detail

- `WAITING_FOR_GPU` is now in `brainHostNotStarting` (`oi_sources.dart:24`) and absent from `brainHostStarting` (`:19`).
- The runtime starting set is now only `STARTING` and `LOADING` (`:13`), which matches `runtime_v1.py:42-45` (Runtime v1 never reports `STARTING_HOST` or `CALIBRATING`).
- The integration test asserts host `WAITING_FOR_GPU` -> unavailable (`companion_initializing_test.dart:96-97`); the unit test asserts it with readiness `LOADING` (`:123`).
- **Agreement with `brain_health`:** now consistent for `WAITING_FOR_GPU`.
- **`WAITING_FOR_LEASE`:**
  - It stays Initializing ("Waiting for the GPU"), while `brain_health.py:125-128` reports it as UNAVAILABLE with the recovery option `wait`.
  - It is in the original owner-reviewed proposal (`04_STARTUP_PROPOSAL_V21.md`, Proposal item 2), so it is not scope drift.
  - The lease wait can be unbounded (another URI GPU workload; the final report itself records the lease being held by another session's chain), so this remains an owner preference to confirm. It is not a failure misreport: the wait needs no user action.

### 3.3 R3-03: evidence now committed

| Cited claim | File | Supports it? |
|---|---|---|
| Haze H1 0 px, H2 0, H3 11.4 % (was 44.7 %) | `final/haze/haze_probe.json` | **Yes.** `gates_shipped` all true; `shipped.worst` = footprint 11.44, outside-circle 0 px, corner 0.0; `h0_current` = 44.67 % / 4115 px; pool [0.10, 0.60] matches `expressions.json:141`. `haze_candidates.jpg` exists. |
| T0-T3 and T5 PASS all clips; T4 fails for depleted, 14 px | `final/transparency/transparency_gates.json` | **Yes.** `all_pass: false`; depleted `matte_fringe_px_max: 14`, `T4_matte: false`; the other 8 clips pass. The limit is max(5, 0.02 x 215) = 5. The failure is **disclosed, not hidden**. Its extent is understated; see R4-N4. |
| Contrast sheets, T4 diagnosis image | `final/transparency/contrast_*.jpg` (9 files), `t4_depleted_contact_shadow_x6.png` | Present. Visual content not judged by me. |
| F-SIZE-1: 85.7 % visible, 6.5 % cut; joyful 2.8 %; depleted 2.9 %; at most 0.3 % at sizes 0.8-1.0 | `final/size_crop.json` | **Yes**, exactly. "Cut" understates loss at the frame edge, which the docstring now discloses. |
| Rehearsal: analyze 0 errors / 4 info; 630 passed, 5 skipped, 1 failed (`ui_v2_test` design count) | `final/rehearsal/analyze.log`, `rehearsal/full_flutter_test.log` | **Yes.** `+630 ~5 -1`; the failing test is `ui_v2_test.dart` "every accepted design is represented once"; 4 `info` lines, 0 errors. The "32/32 after the edit" (`09`) has no committed log. |
| Full suite at the repaired commit | `final/full_flutter_test.log` | **Yes, by my independent run** (599 passed, 5 skipped at d12e70ed). The log itself names no SHA and ran in another worktree (R4-N5). |
| Frozen Core and Runtime untouched | `final/boundary_check_final.txt` | Its content says "HEAD 0484afdc", which predates this commit (R4-N5). My own check at d12e70ed confirms the claim. |

### 3.4 R3-04

- `R2_RESULTS.md` "Reading" now covers each point R3 raised:
  - it states that the control shares Ember's alpha, with a pixel difference of 0.8-5.1/255;
  - it limits the finding to still frames ("motion was last judged in Q2");
  - it scopes the 90 % finding to "this cut-out", not to any artwork;
  - it calls option (b) weak evidence.
- `FINAL_REPORT_V21_FINAL.md:47-66` follows the same wording.
- The R1 variance point is covered by "Panel variance ... about 5 points".
- **Repaired.**

### 3.5 R3-05

- **Unchanged and still open.** F-START-GAP is an owner decision.
- `09:66` and `R3_repairs.md` now point to "`FINAL_REPORT_V21_FINAL.md`, section 6" for timed live state sequences. **Section 6 reads `TBD-LIVE`** (`FINAL_REPORT_V21_FINAL.md:127-129`).
- No live run of the repaired mapping exists in the repository, so there is still no live evidence of `initializing`.
- The live driver still refreshes in a tight loop (`fire_v21_live_driver.dart:454-456`), not at the app's 15 s / 5 s cadence. Any future live run should record the real cadence.

## 4. Fidelity numbers recomputed (task 2)

Per-reviewer character % = min(`v21_worst`, `v21_mid`) for that surround, from `r*_raw/reviewer*.json` decoded with `r*_key/key.json`.

| Round | State / surround | Per reviewer | Mean | Lowest | Document |
|---|---|---|---|---|---|
| R2 | idle dark | 90.0 / 89.17 / 87.5 | 88.89 | **87.5** | 87.5 matches |
| R2 | joyful dark | 90.0 / 89.17 / 88.33 | 89.17 | **88.33** | 88.3 matches |
| R2 | fierce dark | 90.83 x 3 | 90.83 | **90.83** | 90.8 matches |
| R2 | depleted dark | 85.83 / 83.33 / 80.83 | 83.33 | **80.83** | 80.8 matches |
| R2 | light (idle, joyful, fierce, depleted) | - | 76.94 / 78.33 / 78.89 / 73.89 | 76.67 / 77.50 / 76.67 / 70.83 | `r2_decoded.md` matches |
| R1 | all 8 rows | - | 90.28 / 70.56 / 91.67 / 76.11 / 91.94 / 75.00 / 85.28 / 66.94 | 89.17 / 66.67 / 90.83 / 74.17 / 90.83 / 73.33 / 81.67 / 65.00 | `r1_decoded.md` matches |

- The "lowest" values in `R2_RESULTS.md` (87.5 / 88.3 / 90.8 / 80.8) and both decoded tables are correct. No gate result changes.
- The "AC-F3 still NOT MET on dark: idle 88.9, joyful 89.2, depleted 83.3" line is correct.

## 5. New findings

No new HIGH or MEDIUM findings.

### LOW

**R4-N1 (LOW): stale health plus fresh runtime `STOPPED` can still read as Initializing.**
- **Where:** `oi_sources.dart:37-48`. The code accepts `readiness == 'READY'` with runtime `STOPPED`, on the assumption that health is "usually newer".
- **Scenario:**
  - `refreshStatus` reads a fresh `STOPPED` (for example, a Brain server that died with no host running);
  - its `brain_health` call then throws `IntegratedRuntimeException` or times out (`oi_conversation.dart:229-238`), so the previous `brainHealth` with `readiness: READY` stays in place;
  - `brainStartingDetail('STOPPED', {readiness: READY, host: {running: false}})` returns "Brain loading".
- **Effect:** a stopped Brain shows as Initializing until a later health read succeeds.
- **How likely:** the window needs a failed health call. A dead worker is caught first by `workerExited`. So the exposure is small, and in practice the health snapshot is never older outside this path, because `worker_bridge` derives both snapshots from the same `_status()`.
- **Why it still matters:** it contradicts the absolute claim "A failure in either snapshot is never shown as Initializing" (`oi_sources.dart:34-35`, `FINAL_REPORT:102`). No test covers health older than status.
- **Repair:**
  - accept `READY` (and the other health-only acceptances) only when `brainHealth['checked_at']` is newer than the `brainStatus` read (store a timestamp in `refreshStatus`), or clear `brainHealth` when `refreshHealth` fails;
  - add a test with health older than status.

**R4-N2 (LOW): the unavailable detail can name the stale state.**
- **Where:** `oi_sources.dart:145`.
- When R3 case 1 now falls through to unavailable, the detail is built from the stale runtime state, so the companion shows depleted with "Brain LOADING" while the host reports `FAILED`.
- This is not a misreport as Initializing, but the code comment at `:139-141` says the detail "keeps naming the real state".
- **Repair:** when the host is in `brainHostNotStarting` or the health readiness differs, use the newer state (for example "Brain FAILED" or the host state) in the detail.

**R4-N3 (LOW): `R3_repairs.md` misstates the `WAITING_FOR_LEASE` history, and the real deviations from 04 are unrecorded.**
- **The claim:** `R3_repairs.md`, R3-02 row, calls `WAITING_FOR_LEASE` "a deliberate extension of the startup proposal, recorded in `04_STARTUP_PROPOSAL_V21.md`".
- **The facts:**
  - `WAITING_FOR_LEASE` is in the **original** proposal (`04`, Proposal item 2);
  - the 04 status note records no extension.
- **The actual extensions beyond the proposal are not recorded in 04:**
  - host `CALIBRATING` accepted;
  - health readiness `READY` accepted while the runtime reads `STOPPED`/`LOADING`;
  - runtime `STOPPED` accepted with a starting host.
- **Repair:** correct the repairs row, and list these deviations in the 04 status note (R3-09 asked for this).

**R4-N4 (LOW): the T4 depleted failure is disclosed, but its extent is understated.**
- **Where:** `FINAL_REPORT_V21_FINAL.md:89` says "14 px over the 5 px limit, at frame 8".
- **My per-frame recomputation:**
  - **70 of 72 depleted frames exceed the 5 px limit** (7-14 px);
  - only frames 50 (5 px) and 52 (4 px) pass;
  - frame 8 is just the worst.
  - The pixels form one row (cell y = 273, x around 170-193, alpha 0.22-0.43), which is consistent with the stated contact-shadow diagnosis.
- **Repair:** reword as "14 px worst (frame 8); 70 of 72 frames above the limit". The phrase "14 px over the 5 px limit" also reads as 19 px; say "14 px against a 5 px limit".

**R4-N5 (LOW): two final evidence files are not pinned to the commit they support.**
- **`boundary_check_final.txt`:** it states "Range A: V2.1 28149905..HEAD 0484afdc", so it predates d12e70ed, yet `FINAL_REPORT:107` cites it for the final state.
- **`full_flutter_test.log`:** it records no SHA and ran in `C:/Users/cheta/Development/uri-fire-companion-v21`.
- **Substance:** both claims are true at d12e70ed. I verified them myself (no protected-path hits; 599 passed and 5 skipped in a clean worktree at d12e70ed). Only provenance is missing.
- **Repair:** regenerate the boundary check at the final SHA, and prefix logs with `git rev-parse HEAD` and `git status --porcelain`.

**R4-N6 (LOW, evidence integrity): documents cite a section that is still a placeholder.**
- **Where:**
  - `09_UI_V2_INTEGRATION_PLAN_V21.md:66` ("The final live run records how long each look lasts ... section 6");
  - `FINAL_REPORT_V21_FINAL.md:113`;
  - `R3_repairs.md` (R3-05 row).
- **The problem:** all three point to section 6, which is `TBD-LIVE`. Sections 7 and 8 are `TBD-PERF` and `TBD-REVIEW`.
- This is the same class of problem as R3-03: citing evidence that does not exist. The final report is visibly unfinished, so this is LOW, but the wording "records" presents the run as done.
- **Repair:** use future tense ("will record") until the run is committed, or fill section 6 with the committed run.

**R4-N7 (LOW): R3-08 is claimed as disclosed in the final report, but it is not.**
- `FINAL_REPORT_V21_FINAL.md` never mentions `e43e97a7` or the failing intermediate suite.
- **Repair:** add one line to the report, for example in section 7 or in a commits table, or correct the repairs row.

**R4-N8 (LOW): the earlier qualification report is still stale, with no pointer.**
- `FINAL_QUALIFICATION_REPORT_V21.md:172` still says the shared state is `CompanionState.starting` and "proposed, not implemented".
- Keeping history is right, but a one-line forward note ("superseded: implemented as `initializing`, see `FINAL_REPORT_V21_FINAL.md` section 4") avoids misleading a reader.
- **Owner approval:** the report records it only as an assertion ("owner-approved direction"; 04 cites the owner task). I cannot check the owner's words from the repository.

**R4-N9 (LOW): R3-10 is only partly repaired in `R2_RESULTS.md`.**
- **Audit wording unchanged** (`R2_RESULTS.md:10-11`):
  - it still says "Each reviewer read only its own pack folder ... in its own folder";
  - `r2_raw/access_audit.txt` lists reviewer 1's paths as including the parent `...\fp21r\r2`;
  - `R3_repairs.md` claims "The access-audit wording now matches the audit files". That is true for R1 (`R1_RESULTS.md:7`) but not for R2.
  - Blinding is not affected (no key in scratch).
- **New "Decoder rounding" bullet is stale on arrival** (`R2_RESULTS.md:81-84`):
  - it says "`r2_decoded.md` prints the 'lowest' values rounded to whole numbers";
  - in the same commit, `r2_decoded.md` was regenerated with one decimal.
- **Repair:**
  - state that reviewer 1's audit includes the parent round folder;
  - reword the bullet in the past tense ("printed ... before C-2").

### Observations (no finding; for the owner)

- **Unchanged since before this pass:** the outer guard `state != 'READY'` (`oi_sources.dart:138`) means a stale `READY` runtime snapshot shows **idle** for up to 15 s after the newer health report already shows `STOPPING`, `RELEASE_WAIT` or `STOPPED`, for example during a requested restart. This does not violate the "never Initializing" rule. Deciding from the health readiness when it is newer would fix both this and R4-N1.
- **A host-driven restart shows depleted for its whole stop and release phase** (`STOPPING`, `RELEASE_WAIT`), then Initializing. Whether a requested restart should also "look calm" is an owner preference.
- **`WAITING_FOR_LEASE`** can show a calm "Waiting for the GPU" indefinitely, while `brain_health` says UNAVAILABLE (see 3.2). This is per the original proposal; the owner should confirm.

## 6. What I could not verify, and whether it matters

- **Live behaviour.** I ran no live run, and none exists for the repaired mapping (R3-05, R4-N6). The R3-01 conclusions rest on code and producer analysis plus unit tests. This does not change the verdict, because the repair is a pure function and tested.
- **"32/32 after the edit"** for `ui_v2_test.dart` in the rehearsal: no log is committed. The rehearsal also merged `7baefb17`, not d12e70ed. The R3 repair touches only `oi_sources.dart` and its test, which are outside the 4-file overlap, but the rehearsal was not re-run. This has a minor effect, on integration preparation only.
- **T4 diagnosis.** "Panel y 484-486, near-black at alpha 0.2-0.4 in the source cut": I verified the atlas pixels (cell y 273, alpha 0.22-0.43), not the source-panel mapping. No effect, since the failure is disclosed as a failure.
- **Contrast-sheet images:** not visually judged.
- **Reviewer transcripts and the Codex sandbox probe:** not in the repository (hashes only). They do not affect the recomputed numbers.
- **Owner approval wording** of the Initializing direction: not checkable from the repository (R4-N8).
- **Side effects of this review:**
  - `flutter test` wrote build caches (`.dart_tool`, `build`) inside the review worktree, as permitted; `git status` stays clean.
  - Helper scripts and logs are only in the session scratchpad (`r4_lowest.py`, `r4_t4.py`, `r4_full_test.log`, this report).

## 7. Self-review against the criteria

- **A1:** met.
  - Both R3 cases were traced through the code and the producers.
  - The tests ran and passed.
  - The residual edge case, health older than status, is real but narrow, so I filed it as LOW (R4-N1). I did not ignore it: the owner rule is absolute, which is why it is listed.
- **A2:** met. The `WAITING_FOR_LEASE` divergence from `brain_health` is noted as owner preference, not as a defect, because the original proposal names it.
- **A3:**
  - each repairs-table claim was checked;
  - three claims are wrong or partly wrong (R3-08 in R4-N7; the R3-02 note in R4-N3; R3-10 for R2 in R4-N9);
  - R3-05 is still open.
- **A4:**
  - the full suite passes at d12e70ed (my run);
  - the numbers match the raw data;
  - the document defects found are all LOW.
- **A5:**
  - all cited `evidence/final` files exist and support their numbers;
  - the provenance gaps and the T4 extent are recorded.
- **A6:** pass.

**Verdict rationale:**
- The HIGH (R3-01) and the MEDIUM mapping finding (R3-02) are genuinely repaired.
- R3-03 and R3-04 are repaired.
- R3-05 stays open but is disclosed as an owner decision plus a pending live phase.
- All new findings are LOW: documentation accuracy, and one narrow stale-snapshot edge.
- None of these blocks acceptance of the repair commit, but they should be fixed before the final report is closed.

VERDICT: ACCEPT WITH FINDINGS
