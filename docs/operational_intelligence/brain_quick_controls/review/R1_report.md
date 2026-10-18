# BRAIN-QC-20261018 independent review, round R1

Reviewed commit: 177a5319 (HEAD verified), range f3d5eb29..177a5319, final code commit aa7a1cf6. Worktree
D:/uri-dev/uri-brain-quick-controls, branch milestone/brain-quick-controls-20261018. Read-only review: nothing edited,
committed, launched, and no GPU used. Scratch files are under C:\Users\cheta\AppData\Local\Temp\claude\brainqc_review_r1\.

## Verdict: REVISE (narrow)

The core design holds up. The host is the authority on what it loads, P1 cannot be selected, the fit is refused
before anything is stopped, the chips never show a profile as active before the runtime confirms it, and the
evidence numbers re-derive exactly. Two MEDIUM defects need repair before acceptance:

- R1-01: the header "ready" fix in aa7a1cf6 is disproved by the candidate's own qc-3 evidence on that commit.
- R1-02: after a confirmed context shrink, the dialog promises something the code does not do.

The rest are LOW findings, mostly documentation and evidence accuracy.

## Acceptance criteria used for this review

- A1: No path reaches an unqualified profile (P1 64K+vision) through the worker or the host.
- A2: The host never stops a running Brain for a switch it already knows will not fit, and it never stops an attached instance.
- A3: Every switch record is closed (no IN_PROGRESS left behind on a live host), and the worker's turn gate opens on every terminal result.
- A4: The UI and worker never show a profile, or the Brain, as ready or active before the runtime confirms it.
- A5: The report's numbers re-derive from the raw evidence.
- A6: Gates ran on the claimed commits, and later commits are docs-only.
- A7: Frozen and boundary rules hold.
- A8: The open items are honest and complete.

A1, A2, A3 and A5 are MET. A4 is NOT MET (R1-01, header). A6 is PARTIAL (R1-04). A7 is MET with a note (R1-05). A8 is PARTIAL (R1-06, R1-07).

## Findings

### R1-01 MEDIUM: the header still says "ready" while a switch runs, on the final code

- **Where:** `uri_ui/lib/living/integration/oi_conversation.dart` refreshHealth (`changed` block, about lines 278-286). The fix commit is aa7a1cf6.
- **Evidence:** in `evidence/live/qc-3/observations.json`, both `switch-timeline` rows on source_head aa7a1cf6 show `header_brain: "READY"`:
  - while the worker reports `RUNTIME_STOPPED` / `HOST_STOPPING` / `HOST_STARTING`: about 10 s on the switch to Long and about 17 s on the switch to Standard;
  - again during `HOST_CALIBRATING`.

  Screenshot `qc-3/06-switching.png` shows "Brain: qwen... · ready" in the header and "Model ... · ready" in the right panel, next to "Brain: Starting / Switching ...".
- **Cause:** brain_status is re-read only on a health state edge. At READY -> RECOVERING the old server is still up, so the read returns READY. The health state then stays RECOVERING for the whole switch, so no further refresh happens. The widget test (brain_quick_controls_test.dart:194) passes only because it fakes status already STOPPED at the edge, which is not what happens live.
- **Impact:** the aa7a1cf6 commit message ("no stale ready while switching") is a positive claim that the candidate's own final evidence contradicts. The report and qualification do not disclose this. The chips and the RECOVERING card are truthful; the header and the right panel are not.
- **Fix:** while health is RECOVERING, or `controls.switch.pending` is true, refresh brain_status on every health poll, or derive the header from health during a switch. Add a test where status is READY at the edge and STOPPED on a later poll. Record the correction in the report.

### R1-02 MEDIUM: after a confirmed shrink, the Brain is not kept within the new context

- **Where:** `brain_quick_controls.dart:355-373` (shrink dialog) and `worker_bridge.py` `_brain_reconfigure`. Related: `answer.py:202` sends the last 12 history messages with no token budget, and `worker_bridge.py:424-429` bounds history by message count only (MAX_HISTORY 24).
- **What the dialog says:** "URI keeps the whole conversation, but the Brain will not see all of it at once."
- **What the code does:** nothing trims the history to the new n_ctx. Scenario: a conversation reaches more than 32K tokens on Long context, and the user confirms the switch to Standard. The next turn sends the same 12 messages, which are larger than the 32K window. llama-server then rejects or fails the request. This is inferred from code; it was not run live (no GPU). Each failed turn is still appended to history (user text, no answer), so the session keeps failing until the long messages age out.
- **Coverage:** QC-8 is marked MET_UNIT_ONLY. The unit test checks only the confirmation gate, not the turn after the shrink.
- **Fix:** before the switch, or per turn, trim the history sent to the Brain to fit `ctx` minus the answer budget, and add a test for it. Otherwise, change the dialog to say what actually happens and refuse the shrink instead.
- A related LOW point: `_context_tokens` is one value per worker, not per session. The shrink check therefore uses the last answer in any session.

### R1-03 LOW: the fit pre-check and the start budget use different requirements for the same profile

- **Where:** `scripts/ws_brain_host.py` `reconfigure()` uses `RP.required_mib(key)` (frozen 15,620). `apply_pending_profile()` and `wait_for_gpu` use `RP.cfg_required_mib(cfg, G.RUNTIME_V1_DEVICE_MIB)` (frozen 15,626).
- **Evidence:** qc-3 switch 2 shows `fit_before.required_mib` 15620 but `required_mib` 15626. The pre-check is 6 MiB less conservative than the start.
- **Fix:** use `RP.cfg_required_mib(RP.derive_config(frozen, *key), G.RUNTIME_V1_DEVICE_MIB)` in the pre-check.

### R1-04 LOW: some gate evidence is older than the claimed exact commit

- **Where:** `evidence/gates/`:
  - `uibuild-release.log` (mtime 10:01) predates 1f3b3386 (10:04) and aa7a1cf6 (11:39), and has no HEAD file.
  - `ui_v2_frozen_files_diff_vs_7893aaed.patch` (committed in 157e35ea) shows oi_conversation blob 089cff05 without the refreshHealth hunk. The final blob is b13bc0d8.
  - `diff_stat_vs_f3d5eb29.txt` says oi_conversation +65; the final is +73.
- **Contrast:** pytest and flutter test are pinned to aa7a1cf6 by their .head files. The analyze log (11:47) has no head.
- **Effect:** the report's "Gates (exact commit) ... Windows release build OK" is not supported for aa7a1cf6. I independently confirmed the conclusion of the frozen-files gate (`git diff --numstat 7893aaed..177a5319` gives oi_conversation 73/0 and living_composer 9/0).
- **Fix:** rebuild the release on aa7a1cf6 or later with a head file, and regenerate the patch and the diff stat.

### R1-05 LOW (note): an additive line count does not mean the frozen UI V2 behaviour is unchanged

- **What changed:** the refreshHealth insertion adds a `brain_status` call inside an existing frozen method on every health-state change, on every screen, not only for Quick Controls. It adds no deletions, but it does change frozen-file behaviour.
- **Regression cover:** UI V2 68/68 was re-run on the final code (uiv2-main-2, source_head 7e3a99f3: 68 PASS re-counted from observations-main.json).
- **Fix:** state this in QC-9 rather than "only additive".

### R1-06 LOW: the report leaves out the plan's "no automatic fallback after a failed start"

- **The gap:** BRAIN_QC_PLAN.md section 2 discloses it; the report's open findings do not.
- **Scenario:** a target passes the pre-check, the running Brain is stopped, and then the start fails or waits (CONTENDED or a load crash). URI is then left with no Brain on the new profile. The confirmation dialog's "If it does not fit, URI keeps the current Brain" covers only the pre-check. Recovery from the UI works: Standard stays selectable while the host is alive.
- **Fix:** add this to the open findings, and qualify the sentence in the dialog.

### R1-07 LOW: QC-F4 is incomplete

- **The gap:** `scripts/phase2close_chain.py` `WS_EXACT` (the phase1 scope check) also lacks `uri_operational_intelligence/brain_quick_controls.py`. It also lacks runtime_profiles.py, which was already missing at the base.
- **Fix:** name both guards in QC-F4.

### R1-08 LOW: small UI and host behaviour points

1. `profileNotice` (a refusal message such as "wait until URI has finished answering") stays under the composer until the next switch request, even after it no longer applies.
2. `_notice` shows nothing when the host result is a non-final state, such as `WAITING_FOR_GPU` or `STOPPED` (a stop during the switch). The user gets no outcome line.
3. `reconfigure()` on a host whose Brain the user stopped (mgr None, lease released) acquires the lease and starts the Brain. A Vision or Context choice therefore starts a stopped Brain. This may be intended; it should be documented.
4. The hide rule (height < 640 or width < 420) hides Vision and Context at the UI V2-supported 800x600 window (`uiv2-main/main-j11-workspace-800x600.png`). There is no other route to these controls. The plan sanctions this, but the user-facing limitation should be listed.

## Checked and correct (no finding)

- **Host request validation:** `take_request` validates every reconfigure through `QC.switch_target`, whoever wrote it, and refuses with `REFUSED_*` before anything is stopped. `pending_profile` is set only from a validated request.
- **P1 is never selectable:** CATALOG marks long-vision `qualified: False`, `switch_target` raises PROFILE_NOT_QUALIFIED, and the UI renders it disabled (enabled = target != null). P1 is reachable only through the research `--profile` CLI, which is unchanged.
- **Attached instances:** they are refused (REFUSED_ATTACHED_INSTANCE) before the stop.
- **Fit pre-check:** CONTENDED or UNKNOWN is refused before `stop_brain` (when there is no override). AT_RISK proceeds; this is disclosed.
- **Reconfigure during a wait:** inside the lease or GPU wait, the target is applied with no server running, and the fit is re-checked with the new requirement. During a load, `only="stop"` leaves the reconfigure for the main loop.
- **Switch records:** `_finish_switch` runs in the `start_brain` finally block and on the lease-failure path. The refuse paths and ALREADY_ACTIVE close their own records. The only IN_PROGRESS left is on host exit.
- **Lease:** `expected_vram_mib` follows the profile. The samples show 15626 to 13658 to 15626.
- **sync_selection:** writes the derived profile, or removes the file for the frozen profile, at start and on every apply (tested).
- **Worker restart command:** `brain_restart` uses RESTART_ACTIONS, so it cannot write a reconfigure. `write_host_request` refuses a profile without reconfigure, and the reverse.
- **Worker gate:** it opens on DONE, IGNORED and `REFUSED_*`, or on gate expiry or a dead host.
- **Command schema:** it is exact (`profile_id` with optional `confirm_shrink`, which must be a bool).
- **Worker `active`:** set only in READY, BUSY or DEGRADED, with no switch pending and the host profile equal to the worker's verified cfg. The worker cfg follows the host's selection file through ProfileFollower.
- **Catalog:** every entry is in MEASURED_MIB. Standard is FROZEN_KEY, and derive_config returns the frozen cfg unchanged. P2 and P3 numbers and qualification match RUNTIME_PROFILES_LIVE_RESULTS.md section 2.
- **UI choice resolution:** traced for Standard, Long and the not-running case. There is no unqualified target, and the second dimension change is stated.
- **Evidence re-derivation:** `summarize.py`, run in scratch on copies of qc-1, qc-2 and qc-3, gives a summary.json identical to the committed one for all three.
- **Report numbers:** 20/20 x3; switches 29.9/35.1, 31.5/34.7 and 31.4/36.6 s; stop 3.5-3.6 s; tok/s 122.5/98.7/149.4 and 125.6/99.3/147.6; AT_RISK -294.5/-335.3/-332.3. All match.
- **qc-3 timelines:** `active` is null and the switching chip shows until READY on the new profile. A turn sent during the switch was refused with BRAIN_RESTARTING. Recall of 4817 held after both switches, and the worker pids were constant.
- **Leftover request:** a request from qc-2 was correctly ignored as stale in qc-3 (7f6ec386).
- **Screenshots 03, 06, 07, 08, 10:** they match the claims (disabled "64K with vision on" with its reason, "Switching to Long context...", the switched notices), apart from the header issue in R1-01.
- **Runtime used in the live runs:** session.json runtime_verified ok (360 files checked against candidate 0d599b6a). No `.py` file changed after 0d599b6a (`git diff --stat 0d599b6a..177a5319 -- '*.py' ':!docs'` is empty). Native runs used source_head aa7a1cf6 (qc-3) and 7e3a99f3 (uiv2-main-2), with a clean status before and after.
- **Docs-only after the code commit:** `git diff aa7a1cf6..177a5319 -- . ':!docs'` is empty.
- **Boundaries:**
  - runtime_profiles.py, runtime_profile_selection.py, runtime_v1.py and model_lab/ are unchanged against f3d5eb29.
  - No ws_frozen_check PROTECTED path is touched.
  - ws_brain_host.py at f3d5eb29 is identical to 7c7a7776. BRAIN-QC is its first change, so the IC-1 supersession is correctly disclosed.

## What I ran and what I only read

Ran (all COMPLETED_WITH_RESULT):

- `pytest tests/oi tests/ws -q -p no:cacheprovider` (runtime venv): 759 passed, 23 skipped, exit 0. This matches the gate log.
- `flutter test --no-pub test/living/brain_quick_controls_test.dart`: 15/15 passed.
- `summarize.py` on scratch copies of qc-1, qc-2 and qc-3: identical to the committed summaries.
- The git diff, numstat and blob checks above.
- Inspection of the samples, observations and timelines.
- `git status` afterwards: the tree is clean.

Read only, not run:

- the full flutter suite (776), flutter analyze, the release build and ws_frozen_check. I relied on the logs for these and checked their timing (see R1-04).
- the R1-02 failure, which I could not reproduce (no GPU or Brain allowed). Its llama-server behaviour is inferred from the code and not verified. This does not change the finding, because no trimming code exists either way.
