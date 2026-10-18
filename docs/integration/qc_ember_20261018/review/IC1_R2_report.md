# IC1-R2: focused re-review of the IC-1 repairs (Brain Quick Controls integration)

Reviewer: an independent subagent working read-only. I did not write this code. Date: 2026-10-18.
Worktree: D:/uri-dev/uri-integ-20261018, branch integration-candidate/qc-ember-20261018. HEAD = 01e06d70 (verified).
Scope: `git diff 4e827178 01e06d70`, which changes scripts/ws_brain_host.py, uri_operational_intelligence/worker_bridge.py and the new
tests/oi/test_brain_qc_integration.py.

## Verdict: ACCEPT WITH FINDINGS (0 HIGH, 0 MEDIUM, 1 LOW, 3 INFO)

IC1-01 is fixed correctly, and the fix hides no genuine pending switch. IC1-04 is fixed with acceptable blocking. IC1-02 is fixed for
the case it targeted, a stop during the GPU wait. A sibling branch is still open: a stop during a switch's lease wait (R2-01, LOW,
reproduced). Tests: 782 passed, 23 skipped, exit 0 at HEAD. All 3 new tests fail on 4e827178 sources. Beyond the IC1 section 2 list,
the only new default-path difference is a 3 s retry delay at host start, and it happens only when the selection file cannot be deleted.

## 0. Acceptance criteria (set before review)
- A1: Clearing `_switch` is correct. No genuine pending switch is hidden, and the UI state stays truthful in the edge cases: the gate
  times out while the host is still switching, a restart is refused or ignored, the host dies.
- A2: The STOPPED mapping covers every stop or exit during a switch's wait. It does not affect non-switch starts. It never relabels a
  genuine WAITING result.
- A3: The retry loop puts no material blocking on the run loop or the lease. PROFILE_NOT_SELECTABLE is not retried. The docstring is
  accurate.
- A4: The new tests fail on 4e827178 and pass at HEAD. The full suite gives 782 passed and 23 skipped.
- A5: The default path is unchanged relative to cd4a7963, apart from IC1 section 2 and any newly listed item.

## 1. Results
| # | Result | Evidence |
|---|---|---|
| A1 | MET | read and ran (sections 2.1 and 4) |
| A2 | PARTLY: R2-01 | read; ran probe 1 |
| A3 | MET (R2-02 INFO) | read; ran probe 2 |
| A4 | MET (R2-04 INFO) | ran |
| A5 | MET (one new error-only item) | read; ran `git diff --name-only` |

## 2. Analysis per question

### 2.1 IC1-01: `_switch` cleared in `_brain_restart` and whenever the gate opens
- `_switch` is set in one place only, `_brain_reconfigure`, and always with the same id as `_restart`. `_brain_restart` now sets
  `_switch = None` when it overwrites `_restart`, so the invariant "`_switch` is None or `_switch.id == _restart.id`" holds.
  Under that invariant, the unconditional clear in `_restart_pending` behaves exactly like the old id-match clear, and it guards
  against the stale case. It is correct.
- Worker-side refusals (ACTION_INVALID, BRAIN_CONTROL_UNAVAILABLE, BRAIN_HOST_NOT_RUNNING) raise before `_switch = None`. A
  `_host_request` that raises also leaves `_switch` and `_restart` untouched. A refused restart therefore keeps the switch. Good.
- The gate opens by timeout (600 s) while the host still waits for the GPU in a switch. The old code also cleared `_switch` here,
  because the ids matched, so nothing changes. The UI state stays truthful: `brain_health.assess` returns UNAVAILABLE with the host
  `detail` (GPU_CONTENDED and so on) and the host `explain`. `controls.switch.last.result = IN_PROGRESS` makes `_notice` return
  null, and `active` is not set without verified readiness.
- The host is dead: the gate opens and `can_switch` is false with BRAIN_HOST_NOT_RUNNING. Truthful.
- A restart (or start) request sent while the host is mid-switch: R2-03 (INFO). The worker now says "restart requested" instead of
  "switching". That is literally true, and the host explain and `controls.switch.last` still show the switch. The old code did the
  same at this point, but left the stale switch behind afterwards (IC1-01). The new behaviour is strictly better.
- A stop sent during a switch: the switch is cleared, and the host closes `profile_switch` as STOPPED (GPU-wait or load branch).
  `_notice` then shows "The switch was stopped; the Brain is not running." Exception: the lease-wait branch (R2-01).

### 2.2 IC1-02: `stop_during_wait` and the STOPPED mapping
- Correct for a stop request taken in `wait_for_gpu`, which sets the flag. Correct for `should_exit()` (stop file or deadline),
  which ends the `wait_for_gpu` loop with a WAITING_* state, and `_finish_switch` checks `should_exit()`. A stop during the load
  already set STOPPED (`STOPPED_DURING_LOAD`).
- Non-switch starts: `_finish_switch` does nothing unless `profile_switch.result == IN_PROGRESS`. Resetting the flag in
  `start_brain` has no effect on them.
- Genuine WAITING results: `wait_for_gpu` returns only on a fit, a stop or an exit. A reconfigure taken during the wait keeps the
  record IN_PROGRESS (`apply_pending_profile`). So no path closes a record with a genuine WAITING_* while the host keeps waiting, and
  the mapping cannot mislabel one. A stale `True` flag (left over from an earlier start) is only read in a branch that is itself
  reached only on a stop or an exit, so it can only yield STOPPED, which is correct there.
- Gap (R2-01): `reconfigure` on a stopped Brain calls `acquire_lease()`. A stop consumed in its `wait_or_request` returns False
  without setting `stop_during_wait`, so `_finish_switch` records `WAITING_FOR_LEASE`. Reproduced (probe 1): `state =
  WAITING_FOR_LEASE`, `profile_switch.result = WAITING_FOR_LEASE`, `stop_requested = True`. The run loop then sets STOPPED, and the UI
  says "The new setting is waiting for GPU memory…" while the host is STOPPED. This is the same symptom as IC1-02, in a narrower
  branch: the Brain was stopped, a switch was started, the lease was held by another URI workload, and then a Stop arrived.

### 2.3 IC1-04: retry loop
- Up to 5 attempts, with sleeps 0.2, 0.4, 0.6, 0.8 and 1.0 s, for a worst-case total of 3.0 s (probe 2). The last 1.0 s sleep
  comes after the fifth failed attempt and serves no purpose (R2-02).
- Callers: `run()` before `acquire_lease`, and `apply_pending_profile`, which runs in `reconfigure` and inside the
  lease/GPU waits. The report heartbeat runs on its own thread (`_heartbeat`), so the liveness evidence keeps flowing. The GPU lease
  is an OS byte lock with no timer-based staleness (gpu_lease.py), and `lease.heartbeat(expected_vram_mib=...)` runs right after the
  sync. A 3 s block therefore cannot endanger the lease. The only cost is that a stop or request is handled up to 3 s later, and only
  when the write fails. Acceptable.
- PROFILE_NOT_SELECTABLE returns at once (no retry). The docstring ("Synced when the host starts and before a switch start…
  retried briefly… otherwise recorded as `selection_error`") is now accurate.
- Residual from IC1-04, not addressed and acceptable at LOW: a persistent failure is still not repaired by Restart Brain, and the
  worker fails closed (FOREIGN_INSTANCE).

### 2.4 Tests
- At HEAD: `D:/uri-dev/uri-integ-rt/.venv/Scripts/python.exe -m pytest -q -p no:cacheprovider tests/oi tests/ws` in the worktree
  gives **782 passed, 23 skipped, exit 0** in 242 s (log: integ_ic1_r2/pytest_head_01e06d70.txt). This equals 779 at 4e827178 plus
  the 3 new tests.
- Against 4e827178: `git archive 4e827178` (without uri_ui, docs and rnd) extracted to integ_ic1_r2/base_4e827178, plus the new
  test file. All **3 failed** (log: integ_ic1_r2/pytest_new_tests_on_4e827178.txt):
  - restart test: `assert b._switch is None` fails (`{'id': 'req-1', 'to': 'long', ...}`). This is the IC1-01 behaviour.
  - stop test: `'WAITING_FOR_GPU' == 'STOPPED'` fails. This is the IC1-02 behaviour.
  - retry test: AttributeError, no `_sync_selection_once`. The failure is structural, but the test does assert the behaviour (3
    calls, error cleared).
- The helper modules the new tests import (test_brain_quick_controls.py, tests/ws) are unchanged between 4e827178 and 01e06d70.

### 2.5 Default path relative to cd4a7963
`git diff --name-only cd4a7963 01e06d70` is the 4e827178 list plus tests/oi/test_brain_qc_integration.py. cd4a7963 is an ancestor
of HEAD (fast-forward). The blobs of runtime_profiles.py and runtime_profile_selection.py are identical at cd4a7963 and 01e06d70.
New default-path items beyond IC1 section 2:
- **New item:** when `brain_profile.json` cannot be deleted at host start (OSError), the host now retries for up to 3.0 s before
  `acquire_lease`. This happens on the error path only. The successful case is unchanged.
- No effect: the `stop_during_wait` attribute is reset in `start_brain` and set on a stop during the GPU wait, but it is read only
  for an IN_PROGRESS switch. `_switch = None` in `_brain_restart` and `_restart_pending` is a no-op because `_switch` is always None
  without a reconfigure.

## 3. Findings

**R2-01 LOW: scripts/ws_brain_host.py `reconfigure` (the `acquire_lease()` branch) and `_finish_switch`. A stop during a switch's
lease wait records `profile_switch.result = WAITING_FOR_LEASE`.**
`acquire_lease` does not set `stop_during_wait`, so the IC1-02 mapping, which lists WAITING_FOR_LEASE explicitly, is never
triggered for that state except by `should_exit()`. Reproduced by probe 1. Fix: in `_finish_switch`, also accept
`self.stop_requested`. `take_request` sets it for every stop it consumes, inside any wait or load, and the run loop clears it only
after `reconfigure()` returns. So it is the existing, complete signal, and the new flag could simply be replaced by it. Another
option is to set `stop_during_wait = True` in `acquire_lease` on `r == "stop"`. Add a test that mirrors the GPU-wait test with
`mgr = None`, `lease = None` and `G.acquire` raising `GpuBusy`.

**R2-02 INFO: `sync_selection` (ws_brain_host.py ~424-431).** The fifth attempt is followed by a 1.0 s sleep that has no purpose
(worst case 3.0 s instead of 2.0 s). Optional: `if attempt < 4: time.sleep(...)`. There is no lease or heartbeat risk (2.3).

**R2-03 INFO: a restart requested during a switch's GPU wait.** The host's waits take only `stop` and `reconfigure`. A `restart`
stays in the request file until the start completes. Then it either runs (it restarts the new profile) or, if older than 120 s,
it is marked IGNORED_INVALID_OR_STALE. Meanwhile the worker shows RESTART_REQUESTED ("The Brain restart was requested; URI is
waiting for it."), and the host explain and `controls.switch.last.result = IN_PROGRESS` still describe the switch. This is
truthful but less specific than before. The health widgets offer no restart during a switch (`recovery_options = []`), so the user
reaches it only through a direct call. The host semantics are pre-existing. No action required.

**R2-04 INFO: tests.** (a) The retry test fails on 4e827178 through an AttributeError, not an assertion. That is acceptable.
(b) The restart test passes with the `_brain_restart` clear alone, so the `_restart_pending` clear is not exercised on its own. It
is redundant under the invariant in 2.1, so this is acceptable. (c) The worktree has an untracked
`uri_ui/integration_test/qc_native_test.dart` that is not part of 01e06d70. Decide whether it belongs to the integration or is a
leftover.

## 4. Ran vs read
Ran:
- `git rev-parse HEAD` (01e06d70), `git status --short` before and after (only the untracked dart file, unchanged), `git diff
  4e827178 01e06d70`, `git diff --name-only/--stat cd4a7963..{4e827178,01e06d70}`, `merge-base --is-ancestor cd4a7963 01e06d70`,
  blob hashes of runtime_profiles.py and runtime_profile_selection.py.
- The full pytest command at HEAD: 782 passed, 23 skipped, exit 0. Run with PYTHONDONTWRITEBYTECODE=1.
- The new test file against a scratch `git archive 4e827178` extract: 3 failed, as expected.
- Scratch probes (integ_ic1_r2/probe/test_ic1_r2_probe.py, outside the repo, importing the worktree's test helpers read-only):
  probe 1 confirms R2-01, probe 2 measures the retry worst case at 3.0 s. 2 passed.

Read: worker_bridge.py `handle`, `_restart_pending`, `_brain_health`, `_controls`, `_brain_reconfigure` and `_brain_restart`;
ws_brain_host.py from `take_request` to `main` (wait/lease/GPU/start/finish/reconfigure/run loop/heartbeat);
brain_health.assess; gpu_lease (lock model, `GpuBusy`); brain_quick_controls.dart `_notice` and the enablement logic;
oi_conversation.dart `refreshHealth` and `brainAction`; oi_health_widgets restart buttons; the prior IC1 report.

Not verified: no live host, Brain, GPU or Flutter run (excluded by the brief). R2-03 is reasoned from code, not reproduced.
None of this changes the verdict.
