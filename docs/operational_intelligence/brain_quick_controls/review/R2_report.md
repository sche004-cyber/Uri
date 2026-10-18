# BRAIN-QC-20261018 independent review, round R2

Reviewed commit: c87a3387 (HEAD verified). Worktree D:/uri-dev/uri-brain-quick-controls, branch
milestone/brain-quick-controls-20261018. Repair range 177a5319..c87a3387. Final code aba3a5b6. Gates at 25701f51.

This was a read-only review: nothing was edited, committed, launched, or run on the GPU. `git status` was clean before
and after. Scratch files are in C:\Users\cheta\AppData\Local\Temp\claude\brainqc_review_r2\.

## Verdict: ACCEPT WITH FINDINGS (3 LOW, 2 INFO; nothing blocking)

All eight R1 findings were either repaired correctly or recorded honestly. The evidence re-derives exactly. The gates
are pinned to code identical to aba3a5b6, and the boundaries hold. The new findings are a narrow stuck-mask edge case,
the scope and wording of the context-shrink refusal, and gaps in the disclosures.

## Acceptance criteria

- **A1:** each R1 finding is repaired or honestly recorded, and the repairs add no new defect of significance.
- **A2:** qc-4 and qc-5 re-derive. No "ready" row appears while a switch is pending, and "starting" is shown.
- **A3:** gates ran on 25701f51, and 25701f51 is code-identical to aba3a5b6. 25701f51..c87a3387 changes docs only.
- **A4:** the boundaries are unchanged against f3d5eb29, no protected path is touched, and the UI V2 frozen files change additively only (C-4 disclosed).
- **A5:** QC-F1..F6 and the IC-1 disclosure are honest and complete.

Results:
- **A1:** MET, with R2-01 and R2-02 (LOW).
- **A2:** MET.
- **A3:** MET.
- **A4:** MET.
- **A5:** PARTIAL (R2-03 LOW, R2-04 INFO).

## R1 findings, one by one

**R1-01 (header "ready" during a switch): REPAIRED.**
- **Mechanism:** `oi_conversation.dart:281-292` re-reads `brain_status` on a health edge, while health is RECOVERING, or while `controls.switch.pending` is set. While a switch is pending, a READY status is masked as STARTING.
- **Why it cannot stick in normal operation:** the worker forces health to RECOVERING whenever a switch is pending (`worker_bridge.py:631-636`). The poll on which pending clears is therefore a health edge, and that edge re-reads the status unmasked.
- **Widget test:** it now models READY at the edge, then STOPPED, then LOADING, then READY before calibration, then READY.
- **Live, qc-4 and qc-5:** I tabulated every switch-timeline row myself. With pending=true, `header_brain` was only STOPPED ("not running"), LOADING or STARTING ("starting"); it was never READY. With pending=false there is exactly one row, READY with an active profile:
  - qc-4: 16 + 21 pending rows;
  - qc-5: 14 + 22 pending rows.

  For contrast, qc-3 shows 7 and 15 READY rows while pending, which confirms C-1.
- **Screenshot:** `qc-5/06-switching.png` shows the header and the right panel at "starting".
- **Residual:** see R2-01.

**R1-02 (shrink promise not kept): REPAIRED by refusal.**
- **Schema:** `confirm_shrink` is removed (`COMMANDS` at `worker_bridge.py:61`), and the old payload is now COMMAND_SCHEMA (tested).
- **Refusal:** the worker refuses when the largest session's last answer context plus 4,096 is more than the target context. It returns `refused` with the numbers, and the UI shows a notice with no "switch anyway" option.
- **Accounting:** context is tracked per session through `_turn_session`.
- **Check of the frozen `plan_change`:** it is called without `confirm_shrink`, so the default False applies, and the result is correct.
- **Residual:** see R2-02.

**R1-03 (pre-check vs start budget): REPAIRED.**
- **Change:** `ws_brain_host.py:479-482`, target_mib = `cfg_required_mib(derive_config(frozen, *key), DEVICE_MIB)`.
- **Live, qc-4 and qc-5:** `fit_before.required_mib` is 15626 for Standard and 13658 for Long, equal to the start `required_mib`.
- **Side effect, a mild improvement:** a missing frozen config now fails before the stop, not after it.

**R1-04 (gates not pinned): REPAIRED.** All five `.head` files contain 25701f51. The log mtimes (12:29-12:35) come
after the 25701f51 commit (12:29:10). There is a release build log, exit 0. `git diff aba3a5b6..25701f51 -- . ':!docs'`
and `git diff 25701f51..c87a3387 -- . ':!docs'` are both empty.

**R1-05: DISCLOSED as C-4 / QC-9 MET_WITH_NOTE.** I checked the UI V2 regression: uiv2-main-3 on 29db21f9 gives 68 PASS out of
68, with exit 0 and a clean status before the run. 29db21f9..aba3a5b6 touches only the P3 resolution (5 lines) and one
refusal text.

**R1-06: REPAIRED.** The dialog text is qualified, and the gap is listed as QC-F5.

**R1-07: REPAIRED.** QC-F4 now names `test_frozen_core.py` ALLOWED_NEW and `phase2close_chain.py` WS_EXACT.

**R1-08:**
- **.1, REPAIRED:** the notice expires through a getter-based timestamp. There is no Timer, so no timer can leak in tests, and the test restores `profileNoticeFor` in a tearDown. The notice disappears on the next rebuild, and the health polls trigger rebuilds.
- **.2, REPAIRED:** there are outcome lines for WAITING_*, RELEASE_WAIT, STOPPED and a catch-all. READY and DEGRADED are handled before the catch-all, and ALREADY_ACTIVE shows nothing.
- **.3, DOCUMENTED:** `started_stopped_brain` is recorded and the dialog warns about it. Both are tested.
- **.4, REPAIRED:** a compact "Brain settings" button opens the same controls in a dialog. I re-ran the UIV2-F3 no-overflow tests; they pass.

**Coordinator P3 rule: CORRECT.**
- **Catalog:** `standard-nodraft` has `switchable: False`. `switch_target` raises PROFILE_NOT_OFFERED after the qualified check, so P1 still gets PROFILE_NOT_QUALIFIED.
- **View:** `switchable = qualified AND switchable`.
- **Dart:** `_firstQualified` uses `switchable`.
- **P1:** it still cannot be chosen (`qualified` is false, so `switchable` is false, and it is shown as blocked with its reason).
- **Tests:** the unit test asserts that the only switchable targets are {standard, long}. The widget test asserts that no choice targets standard-nodraft or long-vision.

## New findings

### R2-01 LOW: the masked "starting" status can stick if the status read fails on the poll where the switch ends

- **Where:** `uri_ui/lib/living/integration/oi_conversation.dart:285-292`.
- **Scenario:**
  1. The last pending poll stores `{state: STARTING, switching: true}`.
  2. On the next poll, health goes from RECOVERING to READY (`changed` is true), but `brain_status` throws a TimeoutException (probeTimeout) or an IntegratedRuntimeException.
  3. `brainStatus` keeps the masked value.
  4. Every later poll has `changed` false, `switching` false and health READY, so it never re-reads the status.

  The header, the right panel and `brainReady` (the "not ready" empty-state text) then say "starting" until the next health-state edge, possibly indefinitely. Before R2 the same failure left a stale real status. Now it leaves a synthetic one that the runtime never reported.
- **Fix:** add `|| brainStatus['switching'] == true` to the re-read condition, and add a test with a throwing status read on the final edge.

### R2-02 LOW: the CONTEXT_SMALLER_THAN_CONVERSATION refusal covers the whole worker and its lifetime, but the UI says "this conversation"

- **Where:**
  - `worker_bridge.py:191-192`, `289-292` and `663-665`;
  - the notice text in `oi_conversation.dart` `reconfigureBrain`.
- **Scenario:** one conversation on Long context reaches about 28.7K tokens of answer context. Then:
  - Long to Standard is refused for every conversation;
  - Vision On is refused too, because from Long it resolves to Standard.

  This lasts until that same session's later answers shrink below the limit, or the worker restarts. `_context_tokens` is never cleared: there is no session close, and `history` is never cleared either. A user who starts a new, short conversation still gets "Not switched: this conversation (about N tokens...) ... Keep the larger context for this conversation", which is wrong for the conversation they are in. This is safe (it is conservative) but it misleads.
- **Smaller points:**
  - (a) Updating an existing dict key does not move it to the end, so the >64-session eviction drops the earliest-created session, not the least recently used one. It could evict a live long session and under-count.
  - (b) The 4,096 reserve covers the answer but not the next user message (MAX_TEXT is 20,000 chars). The check is a heuristic, not a guarantee.
- **Fix:**
  - word the notice for the worker ("a conversation in this session of URI uses about N tokens");
  - list the lifetime scope as a QC-F item, or reset the entry when a session's history is empty;
  - in `_context_tokens`, pop before re-inserting;
  - state that the reserve is a heuristic.

### R2-03 LOW: the IC-1 integration risk names only ws_brain_host.py

- **Where:** BRAIN_QC_REPORT.md, the last bullet of "Open findings (updated)".
- **What is missing:** RUNTIME_PROFILES_INTEGRATION_PLAN.md:91-92 widens IC-1 to include the files of fa0a70e6 and 4d782ef1. These include `uri_operational_intelligence/brain_health.py` and `scripts/run_uri_integrated_worker.py`, and BRAIN-QC also changes both (+11/-3 and +1/-1 against f3d5eb29).
- **A second gap:** the runtime-profiles candidate branch has moved past this base. `milestone/runtime-profiles-integ-20261017` is now at c3fc8bbc, 12 commits after f3d5eb29, and it changes `runtime_profile_selection.py` and its tests (owner D3). BRAIN-QC does not touch those files, so a merge should not conflict. But BRAIN-QC was never gated on that tip.
- **Fix:** name all three files in the IC-1 note, and record that integration needs a rebase or merge onto the current runtime-profiles tip, with the gates re-run.

### R2-04 INFO: small inaccuracies in the record

- **Where:** BRAIN_QC_QUALIFICATION.json.
- **Items:**
  - QC-5 gives AT_RISK as "-294..-335 MiB", but qc-4 is -336.6 MiB. The report's "-0.29 to -0.34 GB" is fine after rounding.
  - QC-6 cites only qc-1/2/3, although qc-4 and qc-5 also hold (4817 recalled, worker pids constant).
  - `not_qualified` still lists "context shrink confirmation live", but there is now a refusal path.
- **Fix:** correct the wording.

### R2-05 INFO: when the host runs P3, Standard is not reachable in one step

- **What happens:** P3 runs only when a harness or CLI started it. Its 32K and Vision On are both "current", so the menus offer only Long (64K). Getting back to Standard needs two switches.
- **Assessment:** this is acceptable under the "never offer P3" rule. Note it if P3 hosts matter.

## Evidence I re-derived

I ran `harness/summarize.py` on scratch copies of qc-4 and qc-5. Both gave a summary.json identical to the committed one
(dict equality), with COMPLETED_WITH_RESULT / PASS and no failed checks.

| Run | Checks | Switch to Long / back (s) | Stop (s) | Decode tok/s Standard / Long / Standard after switch |
|---|---|---|---|---|
| qc-4 | 22/22 | 30.9 / 37.3 | 3.55 / 3.53 | 121.45 / 97.40 / 151.27 |
| qc-5 | 22/22 | 30.8 / 38.2 | 3.55 / 3.58 | 121.18 / 98.24 / 148.34 |

All of these match the report.

| Run | Fit Long | Fit back to Standard | Recall | Message during the switch | After the run |
|---|---|---|---|---|---|
| qc-4 | FITS +1642.2 MiB | AT_RISK -336.6 MiB | "4817" after both switches | refused, BRAIN_RESTARTING | lease FREE, config digest unchanged, host exit 0, native exit 0 |
| qc-5 | FITS +1678.5 MiB | AT_RISK -299.3 MiB | "4817" after both switches | refused, BRAIN_RESTARTING | lease FREE, config digest unchanged, host exit 0, native exit 0 |

- `started_stopped_brain` is false in both runs.
- The runtime was verified in both runs (360 files, none mismatched).
- source_head is 78db55f6 for qc-4 and 578f7c40 for qc-5. 578f7c40 is code-identical to aba3a5b6.

## Boundaries

- **Unchanged against f3d5eb29:** runtime_profiles.py, runtime_profile_selection.py, runtime_v1.py and model_lab/ (empty diff).
- **Protected paths:** none of the 10 changed non-doc files starts with a ws_frozen_check PROTECTED prefix. frozen_check.json is ok at 25701f51.
- **UI V2 frozen files:** against 7893aaed, oi_conversation.dart is +96/0 and living_composer.dart is +37/0. The behaviour change is disclosed as C-4.
- **ws_brain_host.py:** its blob at f3d5eb29 equals the one at 7c7a7776 (2c5739d9), so BRAIN-QC is its first change.

## What I ran and what I only read

Ran (all COMPLETED_WITH_RESULT):

- `python -m pytest tests/oi tests/ws -q -p no:cacheprovider` (ember-rt venv) on c87a3387: 762 passed, 23 skipped, exit 0. This equals the gate log.
- `flutter test --no-pub test/living/brain_quick_controls_test.dart`: 17/17 passed.
- `flutter test --no-pub` on living_shell_test, uiv2_postint_test (including the UIV2-F3 shrink test with testing tools on) and ws_integration_test: 66 passed.
- `summarize.py` on qc-4 and qc-5: identical to the committed summaries.
- Timeline tabulation for qc-3, qc-4 and qc-5, and the uiv2-main-3 count (68 PASS).
- git diffs, numstats and blob checks.
- Viewed screenshot qc-5/06-switching.png.

Read only, not run:

- the full flutter suite (778), flutter analyze, the release build and ws_frozen_check. I relied on the pinned logs.
- live behaviour beyond the evidence: no GPU or Brain was used. R2-01 is inferred from the code and not reproduced. It does not affect the verdict, because it needs a failed status read at the exact transition poll.
