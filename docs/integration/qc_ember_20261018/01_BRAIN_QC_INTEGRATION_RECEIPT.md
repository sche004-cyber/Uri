# Brain Quick Controls - controlled canonical integration receipt (stage 1 of 2)

Owner authorization: "URI - Controlled Canonical Integration, Brain Quick Controls + Ember V2.1", 2026-10-18,
APPROVED subject to gates; order Brain Quick Controls, then Ember V2.1. This receipt covers stage 1 only.
Reviewer verdicts below are independent read-only subagents (Codex quota-blocked until 2026-10-22); they are not owner
approval.

## 1. Provenance

| Item | Value |
|---|---|
| Canonical before | `integration/git-sync-20261008` = `cd4a7963` on `uri-repo` (verified with `git ls-remote` immediately before integration) |
| Milestone branch | `milestone/brain-quick-controls-20261018`, tip `4e827178` (code `5bcf1f24`), reviews R1-R4 in `docs/operational_intelligence/brain_quick_controls/review/` |
| Integration branch | `integration-candidate/qc-ember-20261018`, worktree `D:\uri-dev\uri-integ-20261018` |
| Integration repairs | `01e06d70` (IC1-01, IC1-02, IC1-04), `6427b681` (IC1-R2 R2-01, R2-02) |
| Integrated code | `6427b681`; this receipt is the following docs-only commit |
| Integration method | fast-forward of canonical (cd4a7963 is an ancestor); no rewrite |

## 2. Integration review (IC-1 files)

| Round | Commit | Verdict | Result |
|---|---|---|---|
| IC1 | `4e827178` | ACCEPT WITH FINDINGS (1 MEDIUM, 5 LOW, 2 INFO) | Default path unchanged vs `cd4a7963`; profile safety holds; 744 canonical tests pass. IC1-01 (stale switch after Restart, MEDIUM), IC1-02, IC1-04 repaired in `01e06d70`; IC1-03 (companion idle during a switch) assigned to the Ember stage (it owns `oi_sources.dart`); IC1-05..09 recorded below |
| IC1-R2 | `01e06d70` | ACCEPT WITH FINDINGS (1 LOW, 3 INFO) | Repairs confirmed; new tests fail on `4e827178`. R2-01 (stop during the lease wait recorded WAITING_FOR_LEASE) and R2-02 repaired in `6427b681` with tests |
| Pre-push | `5f77acb8` | ACCEPT WITH FINDINGS (4 LOW, 4 INFO) | R2-01/R2-02 fixes confirmed (tests fail on `01e06d70`); receipt citation fixes (F-1..F-4) applied in this revision; INTEG-F1 re-run with the original driver (`integ-qc-5`); F-7 (pre-existing: a stop during a restart's lease wait exits the host) recorded. Report `review/FINAL_QC_report.md` |

Recorded: `scripts/ws_brain_host.py` is no longer byte-identical to `7c7a7776` (runtime-profiles IC-1 ends here by
owner-authorized integration); `runtime_profiles.py`, `runtime_profile_selection.py`, `runtime_v1.py` are unchanged.
The canonical `runtime_profile_selection.py` docstring ("no product code writes the selection file") is now outdated:
the host syncs it (IC1-07); the file is protected, so this is recorded here instead of edited.

## 3. Automated gates

| Gate | Commit | Result |
|---|---|---|
| pytest `tests/oi tests/ws` | `6427b681` | 784 passed, 23 skipped (`evidence/gates/pytest_oi_ws_final.log`) |
| `ws_frozen_check` | `6427b681` | `unapproved_protected_changes: []` |
| `tests/phase2a/test_frozen_core.py` | `4e827178` | 3 of 8 fail - identical set fails on canonical `cd4a7963` (`evidence/gates/test_frozen_core_canonical_cd4a7963.log`; pre-existing governance gap, QC-F4) |
| flutter analyze / full flutter test / release build | `4e827178` | 0 errors (4 info) / 779 passed / rc 0. `git diff 4e827178 6427b681 -- uri_ui` is empty (`dart_unchanged_since_4e827178.txt`) |
| Secret scan of `cd4a7963..5f77acb8` additions | - | no matches (main session regex scan; independently repeated by the pre-push review) |

## 4. Windows live verification

Real Windows app through production `main()` in a Debug build driven by `integration_test` (synthesized taps and
typing, not physical input), real integrated worker, paired Core and Runtime v1 Brain, own GPU lease, no override. The
Release build was built (section 3) but not run live.

| Run | Code | Result |
|---|---|---|
| `integ-qc-2` | `4e827178` | PASS 22/22 |
| `integ-uiv2-2` | `4e827178` | UI V2 journeys 68/68 PASS |
| `integ-vision-1` | `4e827178` (host unchanged on this path) | Standard: image answered "Red" in 2.1 s; Long: server refuses image input ("image input is not supported"), as designed |
| `integ-qc-3` | `01e06d70` | FAIL 1 check: `QC-switch-to-standard` - the Standard confirm dialog was shown (`09-confirm-standard.png`); after the Switch tap the host received no second request (all host samples show only the Long switch) and the worker showed no pending switch; timed out after ~7 min. Whether a notice appeared was not recorded by that driver. Cause unknown (finding INTEG-F1) |
| `integ-qc-4` | `6427b681` | PASS 22/22 with an instrumented driver (`qc_driver_integration_instrumented.dart`, sha `ebeb62dd`: records request id, notice and dialog state after the tap, and pumps ~5 s more frames) - the tap produced a request id and closed the dialog |
| `integ-qc-5` | `5f77acb8` (code = `6427b681`, final) | PASS 22/22 with the original, unmodified QC driver (sha `c2f23a11`, same as `integ-qc-2/3`) |

Final runs vs qualified baseline qc-5 (the qualification run on the pre-R2 QC code):

| Metric | qc-5 (qualified) | integ-qc-4 | integ-qc-5 |
|---|---|---|---|
| Decode tok/s Standard start / Long / Standard after switch | 121.2 / 98.2 / 148.3 | 122.8 / 98.8 / 150.0 | 122.2 / 98.4 / 151.4 |
| Switch to Long / back, UI s (host s) | 31.4 / 40.1 (30.8 / 38.2) | 32.1 / 38.8 (31.0 / 36.9) | 33.7 / 39.1 (32.4 / 36.8) |
| Fit before switch to Long / back | FITS +1,678.5 / AT_RISK -299.3 MiB (qc-1..qc-4 range -294.5..-336.6) | FITS +1,669.9 / AT_RISK -316.4 MiB | FITS +1,635.6 / AT_RISK -350.6 MiB |
| llama-server dedicated / non-local MiB, Standard | 15,008 / 1,731 | 15,008 / 1,731 | see summary |
| llama-server dedicated / non-local MiB, Long | 13,896 / 562 | 13,896 / 562 | see summary |
| Conversation continuity ("4817"), same worker pids, turn refused during switch | yes | yes | yes |
| Lease FREE after, Brain config digest unchanged | yes | yes | yes |

No sustained performance regression; the Standard AT_RISK start with ~1.7 GB non-local is the known, qualified
behaviour of the frozen Runtime v1 next to a UI window (unchanged by this milestone).

## 5. Accepted findings (not blocking)

| ID | Finding | Status |
|---|---|---|
| QC-F1 | Choice not persisted; a new Brain host starts on Standard | follow-up (owner-allowed) |
| QC-F2 | No live >32K conversation evidence (shrink refusal unit-tested) | follow-up |
| QC-F3 | Residency alert timing (pre-existing) | recorded |
| QC-F4 | `test_frozen_core` / `phase2close_chain` guards not updated (pre-existing failures identical on canonical) | governance follow-up |
| QC-F5 | No automatic fallback after a failed switch start; failure is reported truthfully (IC1-02/R2-01 fixed) | follow-up (owner-allowed) |
| QC-F6 | Health chip may briefly show previous tok/s (pre-existing) | recorded |
| QC-F7 | Shrink refusal is worker-wide (conversation-specific restriction) | follow-up (owner-allowed) |
| QC-F8 | From a P3 host, Standard takes two switches (research launch only) | recorded |
| QC-F9/F10 | `selection_error` / host-side refusals not surfaced in UI (research launch only; worker fails closed) | recorded; another session's closure branch works on QC-F9 |
| IC1-03 | Companion showed idle during a switch | fixed in the Ember stage |
| IC1-05, IC1-08, IC1-09 | stale reconfigure after >120 s load; override skips switch fit refusal; failed Long switch + long conversation leaves Restart/relaunch | recorded |
| INTEG-F1 | One live run (`integ-qc-3`, code `01e06d70`) where the Standard confirm dialog's Switch tap produced no request; cause unknown (a synthesized-tap or frame race in the test harness is possible but not shown). Rate: 1 failure in 10 live QC runs (qc-1..qc-6, integ-qc-2..5); not reproduced with the original driver (`integ-qc-5`) or the instrumented one (`integ-qc-4`). Physical-input behaviour not tested | OPEN, cause unknown |

## 6. Rollback

Rollback of stage 1 = reset `integration/git-sync-20261008` to `cd4a7963` (force-with-lease from the integrated SHA),
or revert the range `cd4a7963..<integrated>` as one revert commit. The frozen Brain default path is unchanged, so the
Runtime v1 rollback runbook is unaffected. Verified before push: `cd4a7963` exists on `uri-repo` and is an ancestor.

## 7. Licensing

Brain Quick Controls contains no Ember material or third-party assets; OD-2 does not apply to this stage.
