# Final focused review: Ember V2.1 controlled integration, stage 2

Reviewer: Claude (read-only subagent), 2026-10-18. Worktree `D:/uri-dev/uri-integ-ember`.
- HEAD is `74e7f7ba` and the tree is clean (`git status --porcelain` is empty).
- `bb61e976..74e7f7ba` changes only `docs/integration/qc_ember_20261018/**` (196 files).
- Nothing in the repository was edited, committed or pushed. No app was launched and the GPU was not used.
- I ran `git fetch uri-repo` read-only. It updated only the local remote-tracking refs.
- I ran one CPU-only `flutter test` of a single file, on a copy of the code in a scratch folder.

## Verdict for the stage-2 qualification record: ACCEPT WITH FINDINGS

- The code repair is correct, the merge is clean, the gates reconcile and the push status is true.
- The findings are all LOW or INFO. They concern wording and evidence in the receipt, not the code. None of them changes the qualification status or the OD-2 block.

## Acceptance criteria (set before review)
- **AC1:** F-1 and F-2 are fixed as specified, and the test fails at `b07bd496`'s logic.
- **AC2:** `bb61e976` is a clean merge of the true canonical tip. The closure keeps the `switch.pending` semantics, and the new `mismatch` and `vision_locked` fields do not affect `oi_sources`.
- **AC3:** Every number and claim in the receipt matches the stored evidence. Inferences are labelled as inferences.
- **AC4:** The push status and the licensing section are accurate.

## 1. Repair of F-1 and F-2 (`git diff b07bd496 8f883bbf`): MET
- **F-1:** `switching` is now derived only from `brainControls['switch']['pending']`. The `brainStatus['switching']` term is gone. This is correct.
- **F-2:** inside the switching branch the code now calls `brainNotReadyPresentation(hs=='FAILED' ? 'FAILED' : 'STOPPED', {...health, readiness: null, state: null})`.
  - The host map is kept.
  - For FAILED, no host-state case matches, so the call falls through to readiness `FAILED`. The result is error, "Brain failed to start". This is correct.
  - For WAITING_FOR_GPU or WAITING_FOR_LEASE, the host-state case wins and gives unavailable, "Waiting for GPU". This is correct.
  - Nulling `state` removes the RECOVERING-to-STARTING rewrite.
- **Residue (INFO, already F-4):** the detail still comes from `say(explain)`. During a switch that is the worker's switch text, so a failed switch shows "Brain failed to start" together with the "Switching the Brain to X" detail. The headline and state are correct.
- **Is the test meaningful? Yes (ran).**
  - I copied `uri_ui` to scratch and replaced `oi_sources.dart` with the `b07bd496` version. `companion_initializing_test.dart` then fails at line 327: "Expected CompanionState.error, Actual working".
  - With the HEAD version of `oi_sources.dart` the result is "+14 All tests passed!".
  - Logs are in `neg_run.log` and `pos_run.log` in this folder.
  - The fixture now emits `state: RECOVERING`. The F-1 stale-mask path still has no test of its own; this was optional.

## 2. Merge `bb61e976`: MET
- `git ls-remote uri-repo refs/heads/integration/git-sync-20261008` returns `ec2fab5493578a4f...`, which equals the second parent of `bb61e976`.
- `git merge-tree --write-tree 8f883bbf ec2fab54` returns `801c7bca...` with rc 0, and that equals `bb61e976^{tree}`. `feaabe3f` is an ancestor of `ec2fab54` (fast-forward).
- The merge base is `feaabe3f`. The two sides changed no file in common (`comm -12` is empty).
- **Closure compatibility (read):**
  - In `worker_bridge.py`, the `pending` derivation is unchanged. The new `switch_pending()` mirrors it.
  - The Assist refusals (`ASSIST_*`) are raised before a switch is recorded, so they never set `pending`.
  - `QC.controls` adds `mismatch` (forced to None while `pending` is set), `assist` and `vision_locked`. The worker does not change `readiness` or `state` based on them.
  - `oi_sources.dart` references none of these fields. The only Dart change in `oi_conversation.dart` is two refusal strings.
  - So the companion's switching logic is unaffected.

## 3. Receipt `02_EMBER_STAGE2_INTEGRATION_RECEIPT.md` versus the evidence

**Verified:**
- **Gates:** every gate log has `HEAD=bb61e976` on its first line, except tgates, which is at `b07bd496`. The assets are unchanged between `b07bd496` and `bb61e976` (empty diff).
  - pytest: 793 passed, 23 skipped. This reconciles: 784 − 2 removed parametrize cases + 11 new tests = 793.
  - flutter test: 855 passed, 5 skipped. This reconciles: 846 + 9 new closure tests = 855.
  - flutter analyze: 5 issues, all info, rc 1.
  - Release build: rc 0.
  - Frozen check: the full output is stored (76 lines, `ok: true`, both lists empty), so F-3 is repaired.
- **`e-first`** (8f883bbf, frozen): every number and check in the receipt matches.
  - Calibration 154.7 tok/s.
  - J1-initializing-seen and J1-idle passed, and so did the W-* checks.
  - The conversation went thinking, speaking, success.
  - J3 shows unavailable, J4 shows Initializing during the restart, and recovery answered "15".
  - The J5 persistence check passed. The run has `failures: []`.
- **`p3-ember-switch`** (bb61e976, P3 `--profile 32768,gpu,0`):
  - All W-* checks pass: transparent 90.83 % and blended 7.14 %; on Long, 89.82 % and 5.44 %.
  - Both switches show only `initializing` while pending. The timeline records every change of state, headline or detail, so the state stayed constant through the host's STOPPING, LOADING and CALIBRATING.
  - The companion went idle 0.5 s after the host was READY with `pending` false. "4817" was recalled after each switch.
  - Values check: Ember window 178.5 MiB; fit margin +431.5 / +250 (AT_RISK); non-local 2097.3 MiB; calibration 63.3 tok/s; Chrome 438.3 MB.
  - The 173-179 MiB range matches the qualification receipt (172.7 / 179.0).
- **`R-initializing-seen`:** the receipt's explanation is supported.
  - `qc_session.py` starts the Brain first. `--ui-first` only stops the UI runner from waiting.
  - The host was READY at about 12:28:47-48. The app's first observation was at 12:28:49.7, and the first companion sample at 12:29:20.96, after 31 s to connect.
  - So Initializing could not be observed in this run.
- **`c-uiv2` and `p3-uiv2`:** 68/68 checks PASS, with `failures: []`.
- **`c-qc`:**
  - The host stayed in WAITING_FOR_GPU (GPU_CONTENDED) for about 11 minutes and never started.
  - It needed 15,626 MiB with 14,444 MiB free (margin −1,181.6). Chrome used 675.6 MB, dwm 571 MB and uri_ui 212.7 MB.
  - The lease was FREE afterwards.

### Findings

| ID | Sev | Location | Issue | Fix |
|---|---|---|---|---|
| R-1 | LOW | Receipt §4, `e-returning-switch` row | **"fact prompt triggered the remember_fact approval card" is not supported, and is arguably contradicted.** The stored evidence shows the turn `status: refused`, with states `[thinking, idle]`. The companion timeline goes thinking to idle with no `awaitingApproval`, but `_derive` would show awaitingApproval for any `pendingApproval` or `pendingConfirmation`. In `c-uiv2`, "remember" prompts produced Core INTENT_CLARIFICATION/CONFIRMATION messages, not an approval card. The "in-process host" cause fits the evidence (`host: null` in every timeline row, `reconfigure request` result `null`, and the V2.1 `live_session.py` imports `Host` in-process). However, the harness copy that actually ran (it pointed at `uri-integ-ember`) and its driver (sha `bcdce2a1`) are not archived. The INVALID verdict itself is sound. | Restate as: "fact turn refused (status `refused`; cause not recorded); the switch request returned null and the worker never saw a host report, consistent with the in-process host of the V2.1 harness (copy not archived)". Note that R-initializing-seen PASSED in this run. |
| R-2 | LOW | Receipt §4, performance paragraph | **"demotion caused by foreign GPU use" is an inference stated as a fact.** The host's fit verdict still said the Brain fits (+431 MiB). The frozen runs on the light desktop also showed 1730 MiB non-local. The qualified P3 baseline is median 103.8 tok/s with at most 498 MiB non-local (`RUNTIME_PROFILES_LIVE_RESULTS.md` §4), so 63 tok/s is about 40 % below it, and the receipt does not cite that. The strongest evidence against an Ember cause is not cited either: in both P3 runs the calibration ran **before any uri_ui process existed** (no uri_ui among the consumers; `p3-uiv2` gave 63.5 tok/s with no Ember). | Say "probably caused by the desktop's GPU use (dwm 678 MB vs about 400 MB, Chrome 438 MB); not isolated". Cite the P3 baseline and the fact that calibration ran before the UI started. |
| R-3 | LOW | Receipt §4, `c-uiv2` row | **"UI V2 journeys PASS" omits `flutter_errors: 2`.** Both are RenderFlex overflows (75 px and 7 px) at `oi_health_widgets.dart:94`. This is pre-existing and not Ember: the file is untouched since `cd4a7963`, and the same class of error appears in UI V2 completion runs l11 and l13. `p3-uiv2` had 0. | Add "(68/68; 2 pre-existing RenderFlex overflows in oi_health_widgets, not Ember)". |
| R-4 | LOW | Receipt §6 | The licensing section names only the 12 shipped assets as derivative content in the tree. Per the OD-2 report §5, the tree also holds derived imagery: the `v21` demo GIFs, haze and size-crop images, live screenshots, `rig.json` with the signature-erase coordinates, and `v21_integ/live`. `74e7f7ba` adds 134 more PNGs under `ember_stage2/evidence/live`, including Ember window captures. Option B ("shipped files only") is correct, but the push-exposure statement is incomplete for options A and C. | Add one line: "the candidate tree (incl. this receipt's evidence) also contains derived Ember imagery". |
| R-5 | INFO | Receipt §4 | **Code labels.** For `c-qc`, `c-uiv2`, `e-first` and `e-returning`, the UI was built from `8f883bbf`, but the runtime (Python worker) was materialized from `b07bd496` (`session.receipt.candidate_head` / `verified.materialized_from`). The Python code is identical between the two (only Dart changed), so this is harmless but unstated. Startup Initializing was verified live only at `8f883bbf`, in `e-first` and `e-returning`. The merge does not touch that path. | Optionally add "(runtime materialized from b07bd496; Python identical)" and "startup Initializing verified at 8f883bbf; path unchanged by bb61e976". |
| R-6 | INFO | Receipt §4, `c-qc` row | "production host refused" is imprecise: the host **waited** (WAITING_FOR_GPU) and exited when the run ended. "Chrome ~660 MB" does not match the stored host report, which shows 675.6 MB. | Reword as "waited (GPU_CONTENDED, 15.6 GB needed, 14.4 GB free; Chrome 676 MB, dwm 571 MB, uri_ui 213 MB)". |
| R-7 | INFO | Evidence | The QC live driver (`c2f23a11`) and the e-run Ember driver (`bcdce2a1`) are not archived. Only the p3 driver (`7a0087a5`) and the UI V2 driver (`884902e2`) are in the tree. | Archive them, or note it in the receipt. |

## 4. Status and licensing: MET
- After `git fetch uri-repo`, `git branch -r --contains` is empty for `8a1438ec`, `0b853288`, `55405e7e`, `b07bd496`, `8f883bbf`, `bb61e976` and `74e7f7ba`.
- I checked every `uri-repo` ref (80 refs, all objects local) with `--is-ancestor 8a1438ec`, and none contains it. The one exception is `refs/pull/1/merge`, whose object is not local and which I could not check.
- `ls-remote origin` shows no Ember or candidate refs.
- **Ember is not pushed: verified.**
- All 15 OD-2 commits are ancestors of `bb61e976` and of neither `feaabe3f` nor `ec2fab54`.
- The HEAD tree has 0 files under `docs/companions/fire/reference/`.
- The receipt's licensing section matches the OD-2 investigation on these points:
  - the OD-2 text and the owner's answer;
  - that the art derives from the Fiverr illustration and the Gemini sheet;
  - that the signature and the Gemini mark were inpainted out;
  - the 15 commits starting at `8a1438ec`;
  - options A-D, including the handoff §12 waiver for B.
- The only gap is R-4.

## Ran vs read
- **Ran:**
  - HEAD and clean-tree check;
  - `git diff b07bd496 8f883bbf`;
  - the negative and positive flutter test of `companion_initializing_test.dart` (scratch copy, CPU only);
  - `ls-remote`, merge-tree versus tree, the merge-base overlap check and the fast-forward check;
  - the closure diff for worker, QC and Dart;
  - the test-count reconciliation from the diffs;
  - parsing of all gate logs and of every live JSON (observations, timelines, brain-ready, session, native-execution, ui-finished);
  - driver sha matching;
  - the fetch and the containment and ancestry checks;
  - the 15-commit ancestry check.
- **Read:** `oi_sources.dart` (`_derive`, `brainNotReadyPresentation`), the test, the receipt, the prior stage-2 report, the OD-2 investigation, `qc_session.py`, `go.sh`, `ember_live_driver.dart`, the V2.1 `live_session.py` and `RUNTIME_PROFILES_LIVE_RESULTS.md`.
- **Not verified:**
  - the owner's quoted authorisation and instructions (they are chat statements, not repository evidence);
  - `refs/pull/1/merge`;
  - the exact harness that ran `e-*` and `c-qc` (not archived; see R-1 and R-7);
  - the screenshot PNG contents (not viewed).
  - None of these changes the verdict.
