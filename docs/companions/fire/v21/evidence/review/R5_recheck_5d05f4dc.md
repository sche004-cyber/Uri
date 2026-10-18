# Independent recheck R5: Ember V2.1 final, R4 repairs d12e70ed..5d05f4dc

Reviewer: Claude, independent. I did not write this work. I treated `R4_repairs.md` as a set of claims to check.

Worktree: `C:\uri-wt\ember-review-5d05f4dc`. HEAD is `5d05f4dce5115add8f174ca53866c19b4480023e`, and `git status` was clean.

Scope: `git diff d12e70ed 5d05f4dc`. That is 43 files and one commit (`5d05f4dc`). Code changes are only in `uri_ui/lib/living/integration/oi_sources.dart` and `uri_ui/test/living/companion_initializing_test.dart`. Everything else is under `docs/`.

## 0. Acceptance criteria (set before the review)

- **C1. Each R4 finding** is repaired as claimed, or it is correctly marked open. Every "Repaired" row in `R4_repairs.md` must hold against the files.
- **C2. No logic regression:**
  - a real Brain failure is never shown as Initializing;
  - a normal startup through the canonical launcher (`ws_brain_host.py`) is not newly shown as unavailable;
  - the unavailable detail names the newest known state;
  - the recorded live pairs map the same way at `5d05f4dc` as at `d12e70ed`.
- **C3. Tests and analysis:**
  - the targeted test passes at `5d05f4dc`;
  - `flutter analyze` shows no errors;
  - the new tests cover the new branches in both snapshot-age directions.
- **C4. Live evidence:**
  - the files under `evidence/final/live/` agree with each other;
  - every document that cites them is consistent with the raw files.
- **C5. Protected paths:** no frozen or protected path changed in `1b5423bc..5d05f4dc`.

## 1. Primary evidence I produced

- **`flutter test test/living/companion_initializing_test.dart -r expanded` at `5d05f4dc`:** `+10: All tests passed!`. This includes the 2 new tests (R4-N1, R4-N2).
- **`flutter analyze lib test`:** 4 issues, all `info`, and 0 errors or warnings. These are the same 4 info items as before.
- **Protected paths:** I ran `git diff --name-only 1b5423bc 5d05f4dc` against the same prefixes as R4: `uri_core/`, `uri_supervisor*`, `uri_harness_adapters/`, `model_lab/integration/`, `uri_operational_intelligence/`, `scripts/run_uri_*`, `scripts/launch_uri*`, `scripts/ws_brain_host*`, `.gitignore`, `c1_bootstrap`, `paired_runtime*`, `supervised_runtime.dart`, `settings_shell.dart` and `supervised_execution_screen.dart`.
  - Result: **no hits**.
  - `1b5423bc` is an ancestor of `5d05f4dc`.
- **Producers read:**
  - `brain_health.py:54-140`: `readiness` is the runtime `Readiness.state`; `host.running` means the host process is alive.
  - `worker_bridge.py:446-519`: both commands call the same `_status()`. `readiness` can be `UNKNOWN` if `_status()` throws.
  - `runtime_v1.py:264-296`.
  - `ws_brain_host.py:160-300, 368-398`.
  - `oi_conversation.dart:217-238`: `refreshStatus` sets `brainStatus` first and then calls `refreshHealth`. When `refreshHealth` throws or times out, the previous `brainHealth` is kept.
- **Live run files:** I parsed all of `observations-first.json`, `runner-log-first.json`, `gpu-samples-first.json`, `first-brain_host.json` and the `*.json` flags. I viewed screenshots 05, 16 and 18. I read the driver code that produced them (`docs/companions/fire/v21/live/fire_v21_live_driver.dart:225-310`).

## 2. Status of each R4 finding

| R4 finding | Claimed in `R4_repairs.md` | R5 status | Evidence |
|---|---|---|---|
| **R4-N1**: stale health plus a fresh `STOPPED` | Repaired | **REPAIRED** (narrow residual, see R5-N3) | `oi_sources.dart:57` returns null for a `STOPPED` runtime with no running host. The test at `companion_initializing_test.dart:134-138` passes. |
| **R4-N2**: the unavailable detail names the stale state | Repaired | **PARTLY** (R5-N2) | `brainUnavailableDetail` (`oi_sources.dart:29-36`) fixes the R4 case: a stale `LOADING` with a host in `FAILED` now shows "Brain FAILED". But it always prefers the health readiness, so in the R4-N1 scenario it names the older snapshot. |
| **R4-N3**: `WAITING_FOR_LEASE` history; deviations not recorded | Repaired | **REPAIRED** (wording now stale after N1, see R5-N4) | The `R3_repairs.md` R3-02 row is corrected. The `04` status note lists 4 deviations. |
| **R4-N4**: T4 extent understated | Repaired | **REPAIRED** | `FINAL_REPORT_V21_FINAL.md:89` now says "70 of 72 frames ... 7-14 px; the worst is 14 px at frame 8". This matches R4's per-frame recomputation. |
| **R4-N5**: evidence not pinned to a commit | Repaired: boundary check regenerated; log header added | **PARTLY. The claim is false for the boundary check** (R5-N1) | `evidence/final/boundary_check_final.txt:2` still reads "Range A: V2.1 28149905..HEAD 0484afdc", and the file is not in the `d12e70ed..5d05f4dc` diff. Its last commit is `d12e70ed`. `full_flutter_test.log:1-12` now starts with "commit-base: d12e70ed... + working tree", which lists `oi_sources.dart` and the test as modified, and ends `+601 ~5: All tests passed!` (599 + 2 new tests, consistent). The claim about the protected paths is still true at `5d05f4dc`: I verified it myself (section 1). |
| **R4-N6**: final report section 6 is a placeholder | Repaired: "Section 6 is filled from the committed live run" | **OPEN. The claim is false** (R5-N1) | `FINAL_REPORT_V21_FINAL.md:127-129` is still `## 6. Live Windows (Phase 6)` followed by `TBD-LIVE`. The section was not touched in this commit; the only hunk in `FINAL_REPORT` is the T4 row. It is worse than before: `09_UI_V2_INTEGRATION_PLAN_V21.md:66` and `R3_repairs.md` (R3-05 row) now say in the past tense that the run "recorded ... see section 6". |
| **R4-N7**: R3-08 (`e43e97a7`) not disclosed | Repaired: "Final report, section 7" | **OPEN. The claim is false** (R5-N1) | `FINAL_REPORT_V21_FINAL.md:131-133` is `## 7. Performance and regression` followed by `TBD-PERF`. Running `grep e43e97a7 FINAL_REPORT_V21_FINAL.md` finds nothing. `R3_repairs.md` (R3-08 row) now says the disclosure "was added after R4-N7". It was not. |
| **R4-N8**: earlier report stale | Repaired | **REPAIRED** | A forward note was added at `FINAL_QUALIFICATION_REPORT_V21.md:172-173`. The owner approval is still only asserted; I cannot check it from the repository (unchanged since R4). |
| **R4-N9**: R2 audit wording; stale bullet | Repaired | **PARTLY** (R5-N6) | The bullet is now in the past tense (`R2_RESULTS.md:83`), which is correct. The audit note names the folder `fp21r2`, but `r2_raw/access_audit.txt:1` shows `...\scratchpad\fp21r\r2`. The opening sentence "Each reviewer read only its own pack folder" is kept right next to the exception. |

## 3. Logic regression check (task 2)

### 3.1 New behaviour at `5d05f4dc`

- **`brainStartingDetail`.** The only change is the guard at `:57`: a runtime `STOPPED` with no running host now returns null.
  - With a running host, the decision is the same as at `d12e70ed`.
  - For any runtime other than `STOPPED`, nothing changes.
- **`brainUnavailableDetail`** picks the detail in this order:
  1. a running host in `brainHostNotStarting`;
  2. otherwise the health readiness, if it differs from the runtime state and is not `READY`;
  3. otherwise the runtime state.

### 3.2 Normal startup through the canonical launcher

- `launch_uri_working_system.ps1:239-240` always starts `scripts/ws_brain_host.py`. The host has `running: true` from its first heartbeat until it exits, through `STARTING_HOST`, `WAITING_FOR_LEASE`, `STARTING`, `LOADING`, `CALIBRATING` and `READY`/`DEGRADED`.
- The worker's own `RuntimeManager` never spawns, so it never reports `STARTING`. It reports `STOPPED` until llama-server listens, and `LOADING` while llama-server answers 503.
- So the new guard cannot fire during a normal launcher startup. **No regression on the canonical path.**

### 3.3 The recorded live pairs, re-mapped at `5d05f4dc`

| Observation (`observations-first.json`) | Recorded | Host at that time | `d12e70ed` result | `5d05f4dc` result |
|---|---|---|---|---|
| "1 start" 10:07:14, "3 companion mode before brain" 10:07:30 | `brain_status` `STOPPED`, orb `unavailable` | Not recorded. The runner log shows the launcher and host started only at 10:11:23-28, so there was no host. | unavailable, "Brain STOPPED" | Same. The new guard returns null; the detail is "Brain STOPPED", since the readiness is also `STOPPED`. |
| "3c brain initializing" 10:11:41 | `brain_status` `LOADING`; host `running: true`, `STARTING`; detail "Brain loading" | Recorded | initializing, "Brain loading" | Same. The runtime is not `STOPPED`, so the guard does not apply. |
| "brain ready" 10:13:18 | `READY` | n/a | idle | Same (outer guard `state != 'READY'`). |
| "9 brain stopped" 10:14:57 | `STOPPED`, orb `unavailable`; screenshot `first-16` shows "Brain STOPPED" | Host stopped at 10:14:45, process gone, so `running: false` | unavailable, "Brain STOPPED" | Same. |

**Conclusion:**
- every recorded pair maps identically at `5d05f4dc`;
- the live run cannot show any difference, because the only changed branch, `STOPPED` with no host but health that says starting or ready, never occurred in it.

The live run was made at `d12e70ed`, not `5d05f4dc`, so it is not a live run of the repaired code.

## 4. New findings

### MEDIUM

**R5-N1 (MEDIUM, evidence integrity): three "Repaired" claims in `R4_repairs.md` are false, and two documents now cite content that does not exist.**
- **The false claims:**
  - **R4-N5:** "`boundary_check_final.txt` is regenerated at the final HEAD". The file still states `HEAD 0484afdc` (`boundary_check_final.txt:2`) and is unchanged in `d12e70ed..5d05f4dc`.
  - **R4-N6:** "Section 6 is filled from the committed live run". Section 6 is `TBD-LIVE` (`FINAL_REPORT_V21_FINAL.md:129`).
  - **R4-N7:** "Repaired. Final report, section 7". Section 7 is `TBD-PERF` (`:133`), and `e43e97a7` appears nowhere in the report.
- **Citations of missing content, now in the past tense:**
  - `R3_repairs.md` R3-05 row: "The live first-time run at `d12e70ed` recorded timed state sequences ...; see the final report, section 6".
  - `R3_repairs.md` R3-08 row: "Disclosed in the final report, section 7 ... added after R4-N7".
  - `09_UI_V2_INTEGRATION_PLAN_V21.md:66`: "recorded how long each look lasted ... (`FINAL_REPORT_V21_FINAL.md`, section 6)".
- **Why MEDIUM:**
  - this is the third round in a row that cites evidence that does not exist (R3-03, R4-N6, R4-N7);
  - this time the repair record itself asserts completion;
  - under the project's Evidence Integrity Rules, a claim with no `COMPLETED_WITH_RESULT` behind it cannot stand.
  - The code is not affected.
- **Repair (not made by me):**
  - fill section 6 from the raw files (see R5-N5 for what they support) and section 7 with the `e43e97a7` disclosure, or change the three rows in `R4_repairs.md` to OPEN;
  - regenerate `boundary_check_final.txt` at the final SHA, or withdraw that claim;
  - make `R3_repairs.md` and `09` say "will record" until section 6 exists.

### LOW

**R5-N2 (LOW): `brainUnavailableDetail` assumes health is newer, while `brainStartingDetail`'s new guard assumes it may be older.**
- **Where:** `oi_sources.dart:33-34`. The function always prefers the health readiness when it differs.
- **The contradiction:** the R4-N1 comment at `:53-56` states that the health report can be older than a `STOPPED` read, because a failed `refreshHealth` keeps the last one (`oi_conversation.dart:229-238`).
- **Scenario:**
  - fresh runtime `STOPPED` (or `FAILED`);
  - `brain_health` throws or times out;
  - the stale health still says `readiness: LOADING` or `STARTING`;
  - the companion is correctly unavailable, but the detail reads **"Brain LOADING"** for a Brain that is stopped or failed.
- **A second case:** a health readiness of `UNKNOWN` (the `_status()` exception path, `worker_bridge.py:490-493`) replaces a specific runtime state such as `FAILED` with "Brain UNKNOWN".
- **Tests:** the only test is for health newer than status (`companion_initializing_test.dart:140-146`).
- **Effect:** the companion is never shown as Initializing for a failure, so the main owner rule still holds. It breaks only "name the newest known state", and only in a failed-health window.
- **Repair:**
  - prefer health only when it is known to be newer, for example by comparing `brainHealth['checked_at']` (`worker_bridge.py:518`) with `brainStatus['checked_at']`;
  - do not let `UNKNOWN` replace a known state;
  - add the opposite-direction test.

**R5-N3 (LOW): the R4-N1 guard changes earlier behaviour off the canonical path, and a narrow residual remains.**
- **The changed test:** two expectations in the R3-01 test "a stale STOPPED does not flash depleted" were rewritten instead of being kept. `brainStartingDetail('STOPPED', h('LOADING'))` and `h('READY')` without a host were `'Brain loading'` at `d12e70ed`, and are now `isNull` (test `:128-129` versus `:134-137`).
- **Off-path effect:** a Brain started without `ws_brain_host` (for example `uri_operational_intelligence/host.py:28` calling `ensure_ready` directly) again shows depleted for up to one 15 s status poll while it comes up. That is the R3 case-2 flash.
- **Why it is only LOW:** the canonical launcher always uses the host, so the impact is limited to development paths. This is the right trade under "a failure is never Initializing", but the 04 deviation note and the final report do not say it (R5-N4).
- **Residual:** stale health that still records `host.running: true` with `STARTING` stays accepted after the host has died, for as long as `refreshHealth` keeps failing. This is narrow and is the same class as R4-N1.

**R5-N4 (LOW): the documents were not updated for the code change in this commit.**
- `FINAL_REPORT_V21_FINAL.md:102`, section 4 mapping row:
  - it still says "the polled runtime state is `STARTING`, `LOADING` or `STOPPED`", with no "`STOPPED` only with a running host";
  - it still says "stays `unavailable` with 'Brain <state>'", which is no longer the detail rule.
- `FINAL_REPORT_V21_FINAL.md:105` says "8 tests". The file now has 10 (my run: `+10`).
- `04_STARTUP_PROPOSAL_V21.md`, deviation 2 says a newer `READY` keeps the calm look "while the runtime still reads `STARTING`, `LOADING` or `STOPPED`". For `STOPPED`, that is now true only with a running host.

**R5-N5 (LOW): live evidence limits that section 6 must state when it is written.**
- **Provenance:**
  - the run is named `d12e70ed`, but `flutter-test-first.log` and `runner-log-first.json` record no SHA;
  - the log ran in `C:/Users/cheta/Development/uri-fire-companion-v21`;
  - `d12e70ed` is asserted only by the folder name.
- **Pre-repair code:** the run predates `5d05f4dc`. The repaired functions were not live-run, though section 3.3 shows that the recorded pairs would not change.
- **Mislabel:**
  - the observation "10 recovered to idle" records `orb_state: success`;
  - `first-18-recovered-idle.png` shows "Done / Done", not idle;
  - the label and filename overstate the state.
- **Restart startup not recorded:** `states_through_recovery` starts at `thinking@555s`. Between 10:15:12 (host restarted) and the reply, no companion states were recorded, so there is no live record of how a restart looks.
- **The host-state path to Initializing is not demonstrated:**
  - the host started at 10:11:29 (`override.at` 1792059089.027);
  - the first Initializing sample came about 11 s later, when the runtime already read `LOADING`;
  - `state_sequence_while_loading` is `unavailable@20s`, `initializing@235s`, and the driver polls about every 2 s.
- **Consequence:**
  - `09:65`'s "shows `initializing` as soon as the host reports `STARTING_HOST`" is not demonstrated by the run;
  - roughly 11 s of depletion after the host started is recorded and not explained.
  - Possible causes, such as a host report not yet visible to the worker, or slow calls, cannot be told apart from the files.
  - This affects the "normal startup looks calm" rule and should be stated or investigated, not claimed.
- **Brain health at the end:** the final host report (`first-brain_host.json`, host pid 1404, the restarted host) ends with:
  - `CALIBRATING` -> `DEGRADED`, `DECODE_THROUGHPUT_LOW` (10:17:10), with `verdict_now: CONTENDED`;
  - two `uri_ui.exe` GPU consumers and `--override-contention`;
  - the "after recovery" turn took 7.6 s, against about 2 s earlier.
  - The companion showed success and idle, because the mapping uses the runtime state, and that is `READY`.
  - This is pre-existing behaviour, not a defect of this commit, but section 6 and section 7 must not describe the recovery as healthy.

**R5-N6 (LOW): the R2 audit note is still imprecise.**
- `R2_RESULTS.md:10` names the parent folder `fp21r2`; the audit file shows `fp21r\r2`.
- The note keeps "Each reviewer read only its own pack folder" and then states the exception.
- "That folder holds only the three reviewer packs" cannot be checked from the repository.
- Blinding is not affected.

### Observations (no finding)

- **Unchanged, and still for the owner, as recorded in `R4_repairs.md`:**
  - a stale `READY` shows idle after a stop;
  - a requested restart looks depleted during `STOPPING` and `RELEASE_WAIT`;
  - `WAITING_FOR_LEASE` stays calm indefinitely.
- **GPU override:** the live run started the Brain with `-OverrideGpu`. The runner log records it as "owner-authorized start next to other GPU processes". I cannot verify the owner authorization from the repository.
- **`evidence/final/perf/`:** `lease_run_stdout.txt` and `live/.../runner_first_final_stdout.txt` are empty files. `census_queued.json` (10:20 UTC) shows a second `uri_ui.exe` (pid 21044) still holding GPU memory after the run ended. These files were outside my scope and were not judged.

## 5. What I could not verify, and whether it matters

- **Full suite at `5d05f4dc`:** I ran only the permitted targeted test and the analysis.
  - The committed `full_flutter_test.log` (`+601 ~5`, rc 0) ran on `d12e70ed` plus a working tree that matches the files in this commit.
  - I cannot prove that its contents were byte-identical to `5d05f4dc`.
  - This is a minor effect: the code delta is two files, and their test passes in my run.
- **The cause of the ~11 s depleted window after the host started:** not determinable from the files (R5-N5). It does not change the verdict on the repair; it matters for the open F-START-GAP question.
- **Screenshots:** I viewed only 05, 16 and 18.
- **Owner approvals** (Initializing direction, GPU override): asserted in the documents, and not checkable.
- **Side effects of this review:** `flutter test` and `flutter analyze` wrote build caches inside the review worktree. Nothing else was changed apart from this report file.

## 6. Self-review against the criteria

- **C1:**
  - every R4 row was checked against the files;
  - three "Repaired" claims are false (R5-N1);
  - two are partial (N2, N9; N5 is partly true for the log only).
- **C2:**
  - the "never Initializing on failure" rule holds; I found no new path to Initializing for a failure;
  - the canonical startup is unaffected (section 3.2);
  - the recorded live pairs map identically (section 3.3);
  - "newest state" naming is only partly achieved (R5-N2).
- **C3:**
  - the targeted test passes and the analysis shows 0 errors;
  - the opposite-direction test for the detail is missing (R5-N2).
- **C4:**
  - the raw files agree with each other;
  - the documents that cite them do not (R5-N1, R5-N5).
- **C5:** pass.

**Verdict rationale:**
- The code repair is sound, introduces no failure-as-Initializing path, and does not regress the canonical startup.
- The repair record claims three repairs that were not made, and two documents now cite in the past tense report sections that are still placeholders. That repeats the evidence-integrity defect class for the third consecutive round, and it must be corrected before acceptance.
- The required revision is documentation only:
  - fill or retract section 6 and section 7;
  - regenerate the boundary check;
  - correct `R4_repairs.md`, `R3_repairs.md` and `09`.
- The LOW code item R5-N2 is recommended.

VERDICT: REVISE
