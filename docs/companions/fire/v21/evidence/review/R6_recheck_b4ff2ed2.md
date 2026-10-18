# Independent final recheck R6: Ember V2.1 final at b4ff2ed2

I am an independent Claude reviewer and did not write this work. I treated `R5_repairs.md`, `FINAL_REPORT_V21_FINAL.md` and every other document as claims, and checked them against the raw files.

- **Worktree:** `C:\uri-wt\ember-review-final`, detached at `b4ff2ed2c9155b56245d47c81b055d03800e5106`. It was clean before I ran the tests.
- **Code:** the final code commit is `06370431`. `b4ff2ed2` changes only `FINAL_REPORT_V21_FINAL.md` and `boundary_check_final.txt`; I confirmed this with `git diff --stat 06370431 b4ff2ed2`.
- **Code delta since R5:** `5d05f4dc..06370431` touches two non-doc files, `oi_sources.dart` and `companion_initializing_test.dart`.

## 0. Acceptance criteria (set before the review)

- **C1. R5 findings.** Each of R5-N1..N6 is repaired as claimed in `R5_repairs.md`, checked against the files at `b4ff2ed2`.
- **C2. Logic.**
  - No path shows a real Brain failure as Initializing.
  - A normal startup through the canonical launcher is not regressed.
  - The unavailable detail names the newest known state.
  - The `checked_at` comparison is sound against the real producers and the UI refresh path.
- **C3. Report numbers.** The numeric claims in sections 2, 3, 6 and 7, and the "602 passed" claim, are reproducible from the raw evidence.
- **C4. Protected paths.** No protected path changed in `1b5423bc..b4ff2ed2`.
- **C5. Documents.** No placeholder and no false or unsupported claim remains in the docs touched since `28149905`. FP-21R is not presented as accepted, and no score was altered.
- **C6. Tests and analysis.** The full suite passes and `flutter analyze` shows no errors, in my own run at `b4ff2ed2`.

## 1. Primary evidence I produced

- **Full suite.** `flutter test -r compact` in the review worktree at `b4ff2ed2` gave `01:05 +602 ~5: All other tests passed!`, rc 0. That is 602 passed, 5 skipped and 0 failed, which matches the claim. The committed log `evidence/final/full_flutter_test.log` also ends `+602 ~5: All tests passed!` rc=0. Its header says it ran on `5d05f4dc` plus a working tree with the two changed files, in the checkout `uri-fire-companion-v21`. My own run is the result of record for the committed code.
- **Analysis.** `flutter analyze lib test` found 4 issues, all `info`, with 0 errors and 0 warnings. They are the same 4 infos as in R5.
- **Protected paths.**
  - `git merge-base --is-ancestor 1b5423bc b4ff2ed2` succeeds.
  - `git diff --name-only 1b5423bc b4ff2ed2`, filtered by the prefixes `uri_core/`, `uri_supervisor/`, `uri_supervisor_bridge/`, `uri_harness_adapters/`, `model_lab/integration/`, `uri_operational_intelligence/`, `scripts/run_uri_`, `scripts/launch_uri`, `scripts/ws_brain_host.py` and `.gitignore`, gives **no hits**.
  - The producer line `out["checked_at"] = round(time.time(), 3)` (`worker_bridge.py:518`) dates from `f566e032` (2026-10-09). It is pre-existing and was not changed here.
- **Producers read:**
  - `worker_bridge.py:446-519`: `_brain_status` returns `Readiness.to_dict()`, which includes `checked_at`. `_brain_health` stamps `checked_at` at its end.
  - `runtime_v1.py:161-174, 264-296`: `Readiness.checked_at = field(default_factory=time.time)` is set when the object is built, after `probe_server`.
  - `brain_health.py:39, 54-140`.
  - `scripts/ws_brain_host.py`: every `self.set(...)` state. On `FAILED` the host stops the server (`:288-292`).
  - `scripts/run_uri_integrated_worker.py:244-266`: the worker handles commands **serially** from a single stdin loop.
- **UI path read:** `oi_conversation.dart:133, 185, 217-270, 746-747` and `oi_sources.dart:1-183`.
- **Recomputation.** I used my own print-only scripts, kept in the scratchpad and not the repository:
  - the perf series from `*_gpu.json` and `*_perf.json`;
  - the FP-21R R2 decode from `r2_raw/*.json` and `r2_key/key.json`. The key's SHA-256 list matched all 132 pack files.
- **Raw files parsed:** the live `observations-*.json`, `runner-log-*.json`, `gpu-samples-first.json`, `runner_task_output.txt`, `transparency_gates.json`, `haze_probe.json`, `size_crop.json` and the rehearsal logs.
- **Machine lease history**, read-only: `%LOCALAPPDATA%\URI\gpu\history.jsonl`, 191 lines.

## 2. Status of each R5 finding

| R5 finding | Claimed in `R5_repairs.md` | R6 status | Evidence |
|---|---|---|---|
| **R5-N1 MEDIUM**: false "Repaired" claims; documents cited placeholders | Repaired | **REPAIRED** (small residual, R6-6) | `grep TBD` finds nothing in `FINAL_REPORT_V21_FINAL.md`. Sections 6, 7 and 8 are filled (`:127-262`). `e43e97a7` is disclosed (`:239-241`, commits table `:298`). `boundary_check_final.txt:1` reads "generated at commit 06370431", is committed in `b4ff2ed2`, and shows `(none)` for `1b5423bc..06370431`, which my own check confirms. `R4_repairs.md` has a correction note that keeps the history. The `09` wording is changed (`09:65-66`). **But** `R3_repairs.md` was **not** modified after `5d05f4dc` (`git log` shows its last commit is `5d05f4dc`), although `R5_repairs.md:11` says its wording "is corrected". Its rows R3-05 and R3-08 are now true only because the report sections they cite exist. |
| **R5-N2 LOW**: the detail and the guard assumed opposite snapshot ages | Repaired in code | **REPAIRED** | `brainHealthIsNewer` (`oi_sources.dart:46-50`) compares the stamps. `brainUnavailableDetail` (`:30-40`) returns the runtime state unless health is newer, and never lets `UNKNOWN` win. Both stamps come from `time.time()` in the same worker process, and commands are handled serially (`run_uri_integrated_worker.py:244-266`), so a newer stamp really means a later reading. Tests: `companion_initializing_test.dart:140-167`. |
| **R5-N3 LOW**: the no-host path regressed; residual | Repaired | **REPAIRED** (test gap, R6-7) | With health stamped newer, `STOPPED` plus health `LOADING` and no host gives "Brain loading" (`:67-81`; test `:162`). With health older, only the runtime state counts (`:67`; tests `:156-160`), which closes the stale `host.running` residual. The host guard (`:73`) now applies only when a stamp is missing. |
| **R5-N4 LOW**: documents not updated | Repaired | **REPAIRED** | The final report mapping row (`:102`) describes the stamped, older and unstamped cases. "11 tests" (`:106`) matches the file: 11 `test(` calls, at lines 57, 63, 118, 127, 134, 140, 153, 169, 177, 183 and 192. `04` deviation 2 is updated. |
| **R5-N5 LOW**: limits of the live evidence | Repaired | **REPAIRED**, with numeric inconsistencies (R6-1) | The section 6 "Limits" block (`:157-176`) covers provenance (`runner_task_output.txt` = `d12e70ed`), the pre-repair code, the host-only path not being demonstrated, the DEGRADED recovery and the mislabel. The numbers around it disagree with each other and with the raw data (R6-1). |
| **R5-N6 LOW**: R2 audit wording | Repaired | **REPAIRED** (partly unverifiable) | `R2_RESULTS.md` now explains the parent-folder reduction. That matches `scripts/fire_companion/audit_reviewer_access.py`, which applies `PureWindowsPath(p).parent` to every path. The transcripts are not in the repository or the scratch `fp21r/r2_raw`, so the Glob argument itself could not be checked. The key is not in the scratch area: `fp21r/` holds only `r1`, `r1_raw`, `r2` and `r2_raw`. |

## 3. Logic check (task 2)

### 3.1 Can a failure show as Initializing? No path found.

- **Runtime states.** Only `STARTING`, `LOADING` and `STOPPED` can enter `brainStartingDetail` (`:63`). Any other runtime state, including `FAILED`, `FOREIGN_INSTANCE`, `IDENTITY_MISMATCH`, `DEGRADED` and `UNKNOWN`, returns null and stays unavailable.
- **Health newer:**
  - A running host in `FAILED`, `STOPPED`, `STOPPING`, `RELEASE_WAIT` or `WAITING_FOR_GPU` returns null (`:70`).
  - Otherwise Initializing needs a newer readiness of `READY`, `STARTING` or `LOADING`, or `STOPPED` with a running host in a starting state.
  - A newer readiness of `FAILED`, `UNKNOWN`, `ARTIFACT_*` or anything else returns null.
- **Health older:** only a runtime of `STARTING` or `LOADING` gives Initializing (`:67`).
  - The runtime is then the newest snapshot, and it says the server is loading (503).
  - An older host `FAILED` is ignored (test `:158`). That is consistent with "newest wins": the host stops the server when it fails (`ws_brain_host.py:288-292`), so a later `LOADING` read means a server really is loading.
  - Health is older only when a health call fails or exceeds `probeTimeout`, which is 40 s (`oi_conversation.dart:98`). `refreshStatus` always calls `brain_health` right after `brain_status` (`:217-226`).
- **`brain.status` events** merge into `brainStatus` without a stamp, so the old `checked_at` is kept (`oi_conversation.dart:746-747`). The only production emitter sends `DEGRADED` (`orchestrator.py:236`), which can never enter the starting path. No failure leaks through.
- **Unknown host states.** Host states outside both sets (`READY`, `DEGRADED`) with a newer readiness of `READY` keep the calm look only until the next status poll (at most 15 s). After that the outer `READY` guard applies. This is the existing, disclosed behaviour that the mapping follows the runtime state.

### 3.2 Normal startup through the canonical launcher: no regression

- **Before the first host report:** runtime `STOPPED`, newer health with no host, readiness `STOPPED`. The result is unavailable, which is F-START-GAP, unchanged.
- **Host running in `STARTING_HOST`, `WAITING_FOR_LEASE`, `STARTING`, `LOADING` or `CALIBRATING`** with health newer: Initializing.
- **Runtime `LOADING`:** Initializing whichever snapshot is newer.

I re-mapped the four recorded live pairs from `observations-first.json` (states at 10:07:14, 10:07:30, 10:11:41 and 10:14:57) under the `06370431` code. They map identically:

| Recorded pair | Health newer | Health older |
|---|---|---|
| `STOPPED`, no host | unavailable | unavailable |
| `LOADING`, host `STARTING` | Initializing | Initializing |
| `STOPPED`, host gone | unavailable | unavailable |

R5 section 3.3, which the report cites, covered only `5d05f4dc`. This re-mapping covers the final code.

## 4. Report numbers against the raw evidence (task 3)

| Claim (`FINAL_REPORT_V21_FINAL.md`) | Raw evidence | Result |
|---|---|---|
| §7 perf table: GPU, VRAM, frames/s, p50/p99 for all six runs (`:202-204`) | My recomputation from `*_gpu.json` and `*_perf.json`. For example, Ember r1 is 0.28 (0.60), 147.2 (183.5), 45.2, 1.667 / 3.153. Solar r1/r2 have a GPU maximum of 8.92/8.99. | **Match** (all rows; `summary_table.md` agrees) |
| §7: 12 of 12 lease checks passed; lease held by our process | `lease_checks.txt`: 12 lines, `held` with `lease_pid=10468`, `ours=True`, `brain_resident=0`. History lines 187-188: pid 10468 acquired at `…0234.769` and released at `…0632.742`. | **Match** |
| §7: the lease was held for 6.6 min | 398.0 s = 6.63 min | **Match** |
| §7: waited 617 s ("machine lease history") | The history has no queue event. 617.1 s = acquire time minus `census_queued.json` `t=1792059617.64`. The lease was held in the meantime by FCV pid 8544 (lines 185-186). | **Match**, but the start of the wait comes from the census file, not the lease history |
| §7: initializing frames p50 1.6-1.7, p99 2.8-3.0; steady-state p99 3.1/2.9 | 1.646/1.598 and 2.75/2.957; 3.063/2.883 | **Match** |
| §7: transitions p99 8.7/5.8 ms; worst 53/34 ms | Reproduced only by a ceiling-rank p99 over the first 10 frames of **every** segment, **including the run's first segment**. The 53.0 and 34.0 ms frames are frame 0 of the run (app start, first `idle`), not a state change. | **Imprecise** (R6-2) |
| §7: Brain throughput pairs 112.2/142.9, 138.6/141.1, 132.4/135.8; means 135.5 / 139.9; draft 48/78 | `predicted_per_second` from the coexistence turns | **Match** |
| §7: Brain VRAM 14,982-15,009 MB while ready | `gpu-samples-first.json`, pid 17140, READY samples | **Match** |
| §6 row 1: "shell in 15.9 s" (`:144`) | `seconds_to_shell: 14.839` (first run); 6.076 (returning run). 15.9 does not appear in any live file. | **Unsupported** (R6-1) |
| §6 row 12: Initializing "18 s after our host started" (`:152`) | Host start: launcher event 10:11:28.67, `override.at` 10:11:29.03. First Initializing: 10:11:41.04. That is 12-13 s. From the launcher call (10:11:23.9) it is 17.1 s. The report's own Limits say 13 s (`:163-165`), and `09:65` says about 11 s. | **Wrong / inconsistent** (R6-1) |
| §6 row 12: after 97 s of Initializing | 10:11:41.04 to 10:13:18.67 = 97.6 s | **Match** |
| §6: recovered reply 7.6 s against about 2 s; DEGRADED at the end | `application_seconds` 7.592 against 1.889 | **Match** |
| §6 row 3: returning run blinks 5 in 25 s; rc=0 | `blink_starts_s` has 5 entries; the log ends "All tests passed!"; `runner-log-returning` rc 0 | **Match** |
| §6: foreign Brain at 10:17:27 | `census_queued.json`: llama-server pid 14176, `create_time` 1792059447.22 = 10:17:27 UTC | **Match** |
| §3: T4 depleted 14 px maximum; the other clips pass; `all_pass` false | `transparency_gates.json`: depleted `matte_fringe_px_max` 14, `T4_matte` false; all others true | **Match** (the per-frame "70 of 72" was verified by R4/R5 and not rechecked here) |
| §3: H1 0 px, H2 0, H3 11.4 % (was 44.7 %) | `haze_probe.json` shipped: `outside_circle_px` 0, `corner_max` 0.0, `footprint_pct` 11.44. `h0_current` is 44.67. | **Match** |
| §3: shipped pool [0.10, 0.60], `panel_feather` 20 | `companion_art/fire_v2/expressions.json` | **Match** |
| §2: character, presentation and visual tables; "identical"; joyful light 78.1 vs 78.3; V2 79.4-83.6; R = 1.000-1.007 | My decode of R2 | **Match** |
| §2: "all six reviewers ... scored the two identically" (`:43-44`) | R2 reviewer 3, joyful on the light surround, scored the painting and Ember differently: C4 6 against 6.5, P2 4.5 against 5. The report's own `:38` shows 78.1 vs 78.3. | **Overstated** (R6-5) |
| §5: rehearsal 630 passed / 5 skipped / 1 failed; analyze 0 errors | `rehearsal/full_flutter_test.log` "+630 ~5 -1", the failure in `ui_v2_test.dart`; analyze shows 4 infos | **Match** |
| §7: 602 passed, 5 skipped, 0 failed | Committed log, and my own run at `b4ff2ed2` | **Match** (COMPLETED_WITH_RESULT) |

## 5. New findings

No HIGH or MEDIUM findings. All new findings are LOW and concern the documents, except R6-7, which is about test coverage.

**R6-1 (LOW, evidence integrity): two section 6 numbers are unsupported, and the start-gap timing is stated three different ways.**
- `FINAL_REPORT_V21_FINAL.md:144` says "shell in 15.9 s". The raw `observations-first.json` "1 start" record has `seconds_to_shell: 14.839`.
- `FINAL_REPORT_V21_FINAL.md:152` says Initializing came "18 s after our host started". The raw data gives 12-13 s after the host started (`runner-log-first.json` launcher event 10:11:28.67; `override.at` 1792059089.027 = 10:11:29.03; first Initializing 10:11:41.04).
- The same report says 13 s (`:163-165`: 10:11:28 to 10:11:41), and `09_UI_V2_INTEGRATION_PLAN_V21.md:65` says "about 11 s".
- Impact: nothing in the verdict depends on these numbers, but the report must not state numbers the evidence does not give.
- Repair: use 14.8 s and roughly 12-13 s, or define the reference point (launcher call: 17 s), and use one figure across the report and `09`.

**R6-2 (LOW): the state-transition hitch statistic counts the app's first frame as a state change.**
- Where: `FINAL_REPORT_V21_FINAL.md:209-213`. The p99 of 8.7/5.8 ms and worst frames of 53/34 ms are reproducible only if the first segment of the run is included.
- The 53.0 and 34.0 ms frames are frame 0 of the run (`ember_perf.json` `frames[0]`, state `idle`). That is the cold start, not a state transition.
- Excluding the start segment, the worst frame in the first 10 after a real change is 8.7 ms (r1, entering `speaking`) and 4.6 ms (r2). The p99 is 3.9 and 2.6 ms.
- The direction is pessimistic, so it is not an overclaim. But "a state change costs a one-off decode hitch" of 53/34 ms describes the cold start as a state change.

**R6-3 (LOW): section 8 says all R3 MEDIUM findings were repaired, but R3-05 is still open.**
- Where: `FINAL_REPORT_V21_FINAL.md:257`: "The HIGH ... and all MEDIUMs repaired".
- R3-05 (MEDIUM, `R3_review_0484afdc.md:124`) is F-START-GAP. `R3_repairs.md:13` keeps it as an owner decision, and the report itself lists F-START-GAP as open (`:109-113`, `:288`).
- Repair: "all MEDIUMs repaired or disclosed; R3-05 remains open (F-START-GAP)".

**R6-4 (LOW): forward references in the commit that is supposed to contain them.**
- `FINAL_REPORT_V21_FINAL.md:307`, the commits table, says the "next (docs only)" commit contains "Boundary check at `06370431`, this table, and the R6 record". That "next" commit is `b4ff2ed2` itself, and it contains no R6 record.
- `:260` points to "`R6_*` in `evidence/review/`", which does not exist at `b4ff2ed2`.
- Because R5-N1 was about citing content that did not yet exist, these rows must be made true, by committing this review and an `R6_*` record, or reworded before acceptance is recorded.

**R6-5 (LOW): "all six reviewers ... scored the two identically" is slightly overstated.**
- Where: `FINAL_REPORT_V21_FINAL.md:43-44` and `R2_RESULTS.md:44`.
- In R2, reviewer 3 scored the transparent painting and Ember differently on joyful, light surround (C4 6 vs 6.5, P2 4.5 vs 5). The report's own table at `:38` shows 78.1 vs 78.3.
- The conclusion (indistinguishable, weak evidence) is unaffected. The wording should say "identically, apart from one 0.5-point difference on two items".

**R6-6 (LOW): `R5_repairs.md` says the `R3_repairs.md` wording was corrected, but the file was not changed.**
- Where: `R5_repairs.md:11` says "The `R3_repairs.md` and `09` wording is corrected".
- `R3_repairs.md` is unchanged since `5d05f4dc`. Its R3-05 and R3-08 rows (`:13`, `:16`) are now true only because the final report sections were filled.
- The R3-05 row's "recorded timed state sequences" is only partly borne out: section 6 gives start and end times, and the restart window was not captured.
- This is a small repeat of the "claimed but not done" class. It does not affect the code or the verdict.

**R6-7 (LOW, test coverage): the production stamped path is not tested end to end.**
- Where: the fake worker in `companion_initializing_test.dart:17-42`. It answers `brain_status` and `brain_health` **without** `checked_at`, so the conversation-level tests (`:63-110`) exercise only the unstamped branch.
- In production, the worker always stamps both. So the branch real users hit is tested only at function level (`:140-167`).
- Not exercised by any test:
  - `_derive` reading `brainStatus['checked_at']` (`oi_sources.dart:176-178`);
  - the `brain.status` event merge that keeps a stale stamp (`oi_conversation.dart:746-747`).
- My code reading found no defect here (section 3). Recommended: stamp in the fake and add one stamped conversation-level case.

**R6-8 (LOW, wording): perf note on "untracked" output.**
- Where: `FINAL_REPORT_V21_FINAL.md:214-216`: "The orphan output was moved into `series/v2_ember_r2/` and is untracked old evidence".
- Every file in `series/v2_ember_r2/` is tracked (`git ls-files`).
- The sentence is ambiguous at best. It should say what was moved from where, and that it is now committed.

### Observations (no finding)

- **AC-P1** ("VRAM no worse than V2", `00_PLAN_AND_ACCEPTANCE_V21.md:14`) is declared met on the median: 147.2 against 147.4 MB. The peak is 8.1 MB higher (183.5 against 175.4). The report discloses this, and the owner may want to rule on whether peak counts.
- **Build provenance.** The perf exe paths (`_v21final_perf\v21_ember\uri_ui.exe`) do not encode a SHA. That they were built from `0484afdc` and V2 from `b73bd26c` is asserted only.
- **FP-21R** is still marked "PROPOSED, NOT APPROVED" (`08_FIDELITY_PROTOCOL_V21R.md:6`). The report calls AC-F1R "(proposed)", "not meaningful", and lists it as an owner option. The 90 % threshold is unchanged, and the R2 scores I decoded match the raw files. I found no score manipulation.
- **Returning run:** the "initializing" reading came from a foreign Brain on the shared port. This is disclosed, and is pre-existing attach behaviour.

## 6. What I could not verify, and whether it matters

- **The live run's code SHA:** the only record is `runner_task_output.txt` ("d12e70ed", no timestamp). The flutter log and the runner log carry no SHA. This does not matter for the verdict, because the final mapping maps every recorded pair identically (section 3.2).
- **Perf build SHAs** (`0484afdc`, `b73bd26c`): asserted only. Minor; the perf app does not use the Brain mapping.
- **The start of the 3.5-minute live lease wait:** no queue event is recorded. It is plausible from the runner log (UI ready 10:07:46, lease FREE at 10:11:23; FCV chain released at 10:11:19 per the history). Not material.
- **The cause of the ~11-13 s depleted window after the host started:** the report labels it "likely" and "not proven", which is correct.
- **The R2 reviewer Glob argument (R5-N6):** the transcripts are not available. The audit output is consistent with the script's parent-folder reduction.
- **T4 per-frame counts (70 of 72, 7-14 px):** not recomputed by me (verified by R4 and R5). The 14 px maximum matches.
- **Screenshots:** I viewed none. The visual claims (no grey patches, contrast sheets) rest on the gate JSONs I parsed and on earlier reviews.
- **Live desktop transparency for the other companions** (Solar, Sakura, Lunar, Moonlit): there is no evidence in this pass. Floating-window journeys 4-7 are PENDING on UI V2, and the report says so.
- **Owner authorizations** (Initializing direction, `-OverrideGpu`): asserted, and not checkable from the repository.
- **Side effects of this review:** `flutter test` and `flutter analyze` wrote build caches inside the review worktree. My scripts and this file are in the scratchpad. Nothing was edited or committed.

## 7. Self-review against the criteria

| Criterion | Result |
|---|---|
| C1 | All six R5 findings are repaired. One residual claim inaccuracy (R6-6). |
| C2 | No failure-as-Initializing path. No regression of the canonical startup. "Newest state" holds. The stamps are sound: same process clock, serial worker, stamped after the readiness probe. |
| C3 | Most numbers reproduce exactly. Two section 6 numbers are wrong (R6-1). The transition statistic is mis-described (R6-2). One overstatement (R6-5). |
| C4 | Pass. |
| C5 | No `TBD`. FP-21R is not presented as accepted. No score manipulation. Forward references (R6-4), one overstated repair (R6-3) and one wording issue (R6-8). |
| C6 | Pass: 602/5/0, rc 0; analyze 0 errors. |

**Corrections to my first draft:**
- I first planned to rate R6-1 MEDIUM, given the history of evidence-integrity findings. I lowered it to LOW: the errors are small, the report's own Limits section gives the correct 13 s, and nothing in a gate or verdict depends on them.
- I first read the 53/34 ms worst frames as plausible transition decodes. Recomputing per segment showed they are frame 0 of the run (R6-2).

**Verdict rationale:**
- The R5 MEDIUM is repaired: the sections are filled from raw files, the boundary check is regenerated, and the history is kept.
- The code repair for R5-N2/N3 is sound against the real producers and the refresh path.
- The protected paths are untouched, and the suite and analysis pass in my own run.
- The remaining items are LOW documentation inaccuracies and one test-coverage gap. They should be corrected, but they do not change any acceptance outcome or owner decision.
- R6-4 must be resolved when this review is recorded.

VERDICT: ACCEPT WITH FINDINGS
