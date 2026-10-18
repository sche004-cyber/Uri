# IC1 — Integration-safety review of BRAIN-QC-20261018 against runtime-profiles guarantees

Reviewer: independent subagent, read-only. Date 2026-10-18. I did not write this code.
Canonical `integration/git-sync-20261008` = `cd4a7963`. Candidate `milestone/brain-quick-controls-20261018` = `4e827178`
(final code `5bcf1f24`). `git merge-base --is-ancestor cd4a7963 4e827178` → true, so integration is a fast-forward.

## Verdict: ACCEPT WITH FINDINGS (0 HIGH, 1 MEDIUM, 5 LOW, 2 INFO)

The default/frozen path is functionally unchanged apart from the differences listed in section 2, and none of them alters
the lease, the start, calibration, stop or the report fields canonical relies on. All 744 canonical tests in tests/oi and
tests/ws pass at 4e827178 (none of them was modified). IC1-01 (MEDIUM) is a truthfulness defect that occurs only in the
Quick Controls path. It is a one-line fix. I recommend repairing it before the fast-forward, but it does not block
integration safety: the default path is not affected, and nothing unsafe happens. The owner decides.

## 0. Acceptance criteria (set before review)
- AC1: The default path (no `--profile`, no reconfigure request) is equivalent to cd4a7963: the same lease and expected
  VRAM, the same start, calibration and stop, and the same report fields. Every difference is listed.
- AC2: No route through the request channel can start an unqualified profile. The fit check runs before the stop. A
  refusal keeps the running Brain. The lease follows the profile. The stop file and graceful stop are unchanged. No
  foreign process is killed.
- AC3: A switch failure after the stop is reported truthfully (host report, worker controls, UI) and the user can
  recover from it. No state leaves the worker believing a profile is active or switching when it is not.
- AC4: Request-file races with the restart path, the `_restart_pending` gate, and turns refused during a switch are all
  sound.
- AC5: Compatible with `runtime_profile_selection.SELECTABLE`, `ProfileFollower`, brain_health readiness and the FCV-10
  presentation.
- AC6: The canonical tests pass at 4e827178 with no new failure, and the QC tests cover the risky branches.
- AC7: The IC-1 protected files beyond the three named ones are byte-identical to cd4a7963.

## 1. Results per criterion
| AC | Result | Evidence |
|---|---|---|
| AC1 | MET (differences in section 2) | read: full diff of the 4 files, plus `ws_brain_host.py` at 4e827178 lines 68-600 |
| AC2 | MET | read: `take_request` 156-168 (`QC.switch_target` at the host: refused before anything is stopped); `reconfigure` (fit check 487-494 before `stop_brain`; attached instance refused); `apply_pending_profile` (`lease.heartbeat(expected_vram_mib=...)`); `stop_brain` and `should_exit` unchanged; no new kill or signal; `reap_loaders` unchanged. With `--override-contention`, a CONTENDED switch proceeds (consistent with the owner-override semantics; INFO IC1-08) |
| AC3 | PARTLY: IC1-01, IC1-02, IC1-04 | ran: probes 1 and 2 (section 5) |
| AC4 | MET with IC1-01 and IC1-05 | read and ran |
| AC5 | MET with IC1-03 | read: catalog qualified set = SELECTABLE (test `test_catalog_agrees_with_the_integrated_selectable_set`); `derive_config(frozen, FROZEN_KEY)` returns the frozen object itself, so a switch back to Standard deletes the file (absent = frozen) |
| AC6 | MET | ran: 779 passed, 23 skipped, exit 0 at 4e827178 = 744 canonical + 35 QC. Baseline cd4a7963 (git-archive extract): 742 passed, 2 failed, 23 skipped = 744. Both failures come from the extract (no .git, no docs) and pass in the worktree. Risky-branch gaps: IC1-06 |
| AC7 | MET | ran: `git rev-parse` blobs. `runtime_profiles.py` 17b6b3e4, `runtime_v1.py` b2926d2c and `runtime_profile_selection.py` a0ac83c5 are identical at 7c7a7776 (where present), cd4a7963 and 4e827178. `ws_brain_host.py` was 2c5739d9 at 7c7a7776 = cd4a7963 and is b83072bf at 4e827178 (an intended change, see note) |

Note on IC-1: the runtime-profiles IC-1 criterion was a scope criterion for that integration ("byte-identical to
7c7a7776"). BRAIN-QC intentionally ends that byte identity for `scripts/ws_brain_host.py` and modifies
`brain_health.py` and `run_uri_integrated_worker.py` (A1 files from 4d782ef1 and fa0a70e6). This is the change under
review, not a violation, but the integration receipt must record that the 7c7a7776 byte identity no longer holds for
ws_brain_host.py after this fast-forward.

## 2. Default-path behaviour differences (no `--profile`, no reconfigure request), exhaustive
Host (`scripts/ws_brain_host.py`):
1. It imports `brain_quick_controls` and `runtime_profile_selection` at module load. A defect in either module would
   now break host start (it was not a dependency at cd4a7963).
2. `main()` calls `R.load_config()` itself and passes the result as `frozen_cfg`. `Host.__init__` (cfg=None) still
   calls `R.load_config()` again, so the config is read twice and `self.cfg` and `self._frozen_cfg` are equal but
   distinct objects. No functional effect: `cfg_required_mib` gives the same RUNTIME_V1_DEVICE_MIB, and the lease and
   argv are unchanged.
3. `run()` calls `sync_selection()` before `acquire_lease`. On the frozen config it **deletes
   `<report-dir>/brain_profile.json`** (= `control/oi/brain_profile.json` under the launcher,
   launch_uri_working_system.ps1:232/240). At cd4a7963 no product code touched this file ("No product code writes the
   file; the launcher/harness does", runtime_profile_selection.py docstring, now outdated, see IC1-07). Effect: a stale
   selection left by a harness no longer makes the worker report FOREIGN_INSTANCE against a frozen host. That is safer,
   but a launcher that writes a selection and starts the host without `--profile` gets its selection removed. If the
   unlink raises OSError, the report gains `selection_error` (a new field, error case only).
4. `wait_or_request()` (used in WAITING_FOR_LEASE, WAITING_FOR_GPU, RELEASE_WAIT and GPU_QUIET_WINDOW) now also
   consumes a `reconfigure` request, not only `stop`. With no reconfigure request this changes nothing.
5. `start_brain()` is now a wrapper: `_start_brain()` with `_finish_switch()` in `finally`. Without an IN_PROGRESS
   `profile_switch` this is a no-op (no extra write).
6. `take_request()` accepts the new action `reconfigure` (ACTIONS grew), and the `only` argument accepts a tuple.
   restart/stop/start are handled identically.
7. Report: on the default path, no new field appears (`profile_switch` only after a reconfigure, `selection_error` only
   on error or for a research profile). `profile`, `lease`, `gpu`, `calibration`, `server`, `requests` and
   `last_request` are unchanged.
8. Unchanged: lease acquire with `expected_vram_mib = RUNTIME_V1_DEVICE_MIB`, `wait_for_gpu` verdict handling,
   load-thread stop, `calibrate`, `stop_brain`, the stop file, `release_lease` and the exit `finally`.

`brain_health.py`:
9. `ACTIONS` gains `reconfigure`. The new `RESTART_ACTIONS` holds the old three. `write_host_request(dir, action,
   profile=None)` raises `ValueError("PROFILE_REQUIRED_FOR_RECONFIGURE_ONLY")` for a profile on restart/stop/start; the
   request bytes for restart/stop/start are unchanged.

`run_uri_integrated_worker.py`:
10. The `host_request` lambda gains `profile=None` and forwards it. For a call with one argument the result is
    identical.

`worker_bridge.py`:
11. `brain_health` always carries a new `controls` object (`QC.controls`, with exceptions caught). The existing keys,
    state, reasons and explain are unchanged unless a switch is pending.
12. `_restart_pending` also treats a `REFUSED_*` result as done. That result is unreachable for restart/stop/start.
13. `_brain_restart` validates against `RESTART_ACTIONS` (the same three as before).
14. Every `oi_turn` records `turn_id → session` (bounded to 64), and every `answer.done` records the context size
    (bounded LRU of 64). This is new memory and CPU work, but small.
15. New command `brain_reconfigure` in COMMANDS. It is not in OPEN_WHILE_BUSY, so it is refused while a turn runs.

UI (not a requested file, but on the default path): `oi_conversation.refreshHealth` now issues an extra `brain_status`
call on every health-state change and on every poll while health is RECOVERING. This also happens on a plain restart.
A `brain_status` IntegratedRuntimeException now sets `lastError`, where only a brain_health failure did before.

## 3. Findings

**IC1-01 MEDIUM — worker_bridge.py `_brain_restart` (around 4e827178:718-732) together with `_restart_pending`
(225-242): Restart Brain during a pending switch leaves a stale `_switch`.**
Scenario (reproduced, probe 1): the user picks Long context, and then, while the switch is pending, presses Restart
Brain. `_brain_restart` is not gated on `_restart_pending` (pre-existing by design) and overwrites `_restart` with the
restart id. When the host marks the restart DONE, `_restart_pending` clears `_restart`, but it clears `_switch` only
when its id matches. The id is the reconfigure id, so `_switch` survives indefinitely. From then on, every ordinary
restart reports `reasons[0] = PROFILE_SWITCH`, the explain text "Switching the Brain to Long context…",
`controls.switch.pending = True` with a stale target, and the UI masks `brainStatus` as STARTING/switching. The worker
believes a profile switch is in flight when none is (AC3). This repeats until the next reconfigure. There is no safety
impact: the host is never asked for a profile and turns are gated correctly.
Fix: in `_brain_restart`, set `self._switch = None` when writing a new request, or clear `_switch` in
`_restart_pending` whenever `_restart` is cleared, whatever the id. Add a unit test: reconfigure, then restart, then
DONE for the restart → `_switch is None`, and a later restart reports RESTART_REQUESTED.

**IC1-02 LOW — ws_brain_host.py `_finish_switch` (303-309) with `wait_for_gpu` (277-279) and the run loop (551-555): a
stop during a switch's GPU wait records `profile_switch.result = "WAITING_FOR_GPU"`.**
Reproduced (probe 2). The switch stops the old Brain, the target waits CONTENDED, and the user sends Stop.
`_start_brain` returns False while the state is still WAITING_FOR_GPU, `_finish_switch` writes that state, and only
afterwards does the run loop set STOPPED. The UI's `_notice` (brain_quick_controls.dart, about line 284) then says "The
new setting is waiting for GPU memory. Choose the previous setting to go back." while the host is STOPPED (the
dart has a STOPPED message that is never reached in this case). The host `state` itself is truthful. Fix: in
`_finish_switch`, map `self.stop_requested` or `should_exit()` to `STOPPED`, or close the record after the stop
handling in `run()`.

**IC1-03 LOW (inherited) — oi_sources.dart `_derive` (about line 55) reads `brainHealth['readiness']` first, which the
switch mask does not cover.**
The R1-01/R2-01 fix masks `brainStatus` (the header and panel), but the companion signal prefers
`brainHealth.readiness`, the worker's raw readiness. That stays READY while the old server still answers (before and
during STOPPING) and again during the new server's CALIBRATING. In those windows the companion reads idle (ready)
while the chips say switching and `oi_turn` is refused with BRAIN_RESTARTING. A plain restart at cd4a7963 already had
this behaviour (calibration window), so it is inherited, but a switch makes it more visible. I did not verify it live.
Fix: in `_derive`, treat `brainHealth.state == RECOVERING` (or `controls.switch.pending`) as not ready before the
READY shortcut.

**IC1-04 LOW — ws_brain_host.py `sync_selection` (414-438): a failed write is not retried and Restart does not repair it.**
`os.replace` or `unlink` on Windows can fail with PermissionError while the worker's `ProfileFollower` has the file
open, because it reads it on every readiness check. The error is recorded only as `selection_error` (not surfaced: R4-04),
the switch then proceeds, and the worker verifies against the old config, so it reports FOREIGN_INSTANCE (fails
closed). A later Restart Brain does not call `sync_selection`; only a new reconfigure or a host relaunch rewrites the
file. The docstring's "Written before every start" is inaccurate: the file is written at `run()` start and in
`apply_pending_profile`, not in the restart path. The `os.replace` pattern without retry already exists elsewhere, so
the likelihood is low, but the consequence here persists until the user acts. Fix: retry the replace or unlink a few
times; refuse the switch (before `stop_brain` is not possible, so set FAILED with `SELECTION_WRITE_FAILED`) when it
still fails; call `sync_selection()` before every `start_brain`.

**IC1-05 LOW (inherited) — request max age versus host phases that do not take a reconfigure.**
During the initial load (`_start_brain` takes only `stop`) and during `calibrate` (up to 120 s), a reconfigure is not
taken. If load plus calibration exceed REQUEST_MAX_AGE_S = 120 s, the request is marked IGNORED_INVALID_OR_STALE. The
worker gate opens and `_switch` is cleared, and the UI shows no notice (`last.id` ≠ `profileRequestId`), so the click
silently does nothing. The same applies to restart at cd4a7963. Fix (optional): map an IGNORED result of the UI's own
request id to a notice.

**IC1-06 LOW — test coverage of risky branches.**
Covered: refusal before stop (fit, attached instance, unqualified, from a hand-written request), lease
expected-VRAM update, selection write and removal, research profile, waiting-start switch, a switch on a stopped Brain,
worker gating and refusals, R4-01. Not covered by any unit test: a start FAILED after the stop
(`profile_switch.result = FAILED`, with the worker/UI on the new config, and recovery by choosing Standard); a stop
during a switch (IC1-02); restart during a switch (IC1-01); `acquire_lease` failing inside `reconfigure`; a
`run()`-level test that a reconfigure ends with `requests[id] = DONE` (only `reconfigure()` is called directly; DONE
comes from `finish_request` in the run loop, which I verified by reading only). Fix: add these 5 tests.

**IC1-07 LOW (doc) — runtime_profile_selection.py docstring (canonical, unchanged): "No product code writes the file;
the launcher/harness does (reviewer finding R1-07)".** After BRAIN-QC the Brain host writes and deletes it. The file is
protected by IC-1 and so left untouched; record the change in the integration receipt or in a follow-up doc change.

**IC1-08 INFO — `--override-contention`.** With the owner override, `reconfigure` skips the CONTENDED/UNKNOWN refusal
and stops the Brain even when the target does not fit. This is consistent with what the override means at start, but
it is undocumented for switches.

**IC1-09 INFO — failed switch recovery and the context guard.** After a FAILED switch to Long, the worker follows the
selection (now Long). Choosing Standard is refused with CONTEXT_SMALLER_THAN_CONVERSATION when any session exceeds
28,672 tokens, even though no Brain runs. The user's options are then Restart Brain (Long again) or relaunching URI
(the host returns to frozen). This is consistent with QC-F5 (no automatic fallback) and the UI text, but worth knowing.

## 4. Answers to the six questions
1. Default path: section 2. No change to lease, expected VRAM, start, calibration, stop, or the report fields used by
   the UI or tests. The material differences are the deletion of `brain_profile.json` at host start (#3) and the extra
   module imports (#1).
2. Profile safety: MET. P1 is refused at the worker and again at the host (`switch_target` → REFUSED_PROFILE_NOT_QUALIFIED;
   P3 → PROFILE_NOT_OFFERED). The fit check against the target's measured request runs before `stop_brain`, with owners
   excluded. A refusal keeps the Brain and closes the request with REFUSED_*. The lease heartbeat follows the profile.
   The stop file and graceful stop are unchanged, and nothing foreign is killed. An attached instance is never switched.
3. Failure after stop: the host reports it truthfully (`profile_switch.result` = FAILED/DEGRADED/WAITING…, state) and
   the UI has plain-words mapping for each. It is recoverable by choosing another setting or Restart Brain (subject to
   IC1-09). Defects: IC1-01 (the worker believes a switch is in flight when it is not), IC1-02 (STOPPED reported as
   waiting), IC1-04 (selection write failure). `controls.active` is set only when the readiness is serving and the host
   profile matches, so I found no path that shows a profile as *active* when it is not.
4. Concurrency: the host is single-threaded for requests. A reconfigure during a load waits for the main loop, and one
   taken during a GPU wait swaps the target before any start. The worker refuses a reconfigure while a turn runs
   (TURN_IN_PROGRESS) and while any Brain request is pending (BRAIN_RESTARTING), and `oi_turn` is refused while the gate
   is closed. The gate opens on DONE, IGNORED, REFUSED_*, a dead host, or 600 s. Gap: restart after reconfigure (IC1-01).
   A latest-request-wins overwrite can drop an unread reconfigure; this is the same pre-existing semantics as restart.
5. Compatibility: catalog qualified = SELECTABLE; offered = {frozen, P2} ⊂ SELECTABLE. The host writes only SELECTABLE
   (R9-01), and `ProfileFollower` picks the file up by content. brain_health readiness semantics are unchanged apart from
   the forced RECOVERING/PROFILE_SWITCH while a switch is pending. FCV-10 `brainNotReadyPresentation` sees RECOVERING plus
   the host phase (STOPPING / RELEASE_WAIT / STARTING / LOADING / CALIBRATING / WAITING_FOR_GPU), which is sensible,
   except for the readiness=READY windows (IC1-03). In WAITING_FOR_GPU during a switch, the detail line uses the
   worker's "Switching… about half a minute" explanation under a "Waiting for GPU" headline. That is slightly optimistic
   but not false.
6. Tests: ran, 779 passed, 23 skipped, exit 0 = 744 canonical (unmodified) + 35 QC. The baseline extract has 744 tests
   (742 pass, plus 2 extract-environment failures). There is no new failure. Coverage gaps: IC1-06.

## 5. Ran vs read
Ran:
- `git rev-parse`, `merge-base --is-ancestor`, `log`, `diff --stat` and `diff` on cd4a7963..4e827178; blob hashes of the
  IC-1 files at 7c7a7776, cd4a7963 and 4e827178.
- `D:/uri-dev/uri-ember-rt2/.venv/Scripts/python.exe -m pytest -q -p no:cacheprovider tests/oi tests/ws` in
  D:/uri-dev/uri-brain-quick-controls → 779 passed, 23 skipped, exit 0 (log: integ_ic1/pytest_4e827178.txt).
  `tests/oi/test_brain_quick_controls.py` alone → 35 passed.
- Baseline: `git archive cd4a7963` (without docs, uri_ui, rnd) extracted to integ_ic1/base_cd4a7963; same pytest
  command → 742 passed, 2 failed (test_second_process_cannot_write_or_recover and
  test_capture_tool_runs_the_advisory_from_the_repository_root: the extract has no .git and no docs; both pass in the
  worktree), 23 skipped (log: integ_ic1/pytest_base_cd4a7963_archive.txt).
- Scratch probes (integ_ic1/probe/test_ic1_probe.py, outside the repo, importing the worktree's tests read-only): probe
  1 confirms IC1-01, probe 2 confirms IC1-02. 2 passed.
- `git status --short` of the worktree before and after: clean.

Read: the diffs of the 4 Python files; `ws_brain_host.py` in full at 4e827178; `brain_quick_controls.py`; the worker's
`handle`, `_restart_pending`, `_brain_restart`, `_brain_reconfigure` and `_controls`; `gpu_lease.assess_fit` and
`heartbeat`; `runtime_profiles.derive_config`, `describe` and `plan_change`; `runtime_profile_selection` (canonical);
`run_uri_integrated_worker.py` (ProfileFollower wiring, oi_state); the launcher's report-dir; RUNTIME_PROFILES_INTEGRATION_PLAN.md
(IC-1, A1-A3) and the RUNTIME-PROFILES-INTEG.json IC-1 line; the Dart diffs (oi_conversation, living_composer) and the
relevant parts of brain_quick_controls.dart and oi_sources.dart; the R4 report.

Not verified: no live run (no Brain or GPU, by brief); Flutter tests not run; the Windows sharing-violation race
(IC1-04) is reasoned, not reproduced; the IC1-03 companion behaviour during a live switch is reasoned from code only.
None of these changes the verdict.
