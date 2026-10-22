# URI-CONTROLS-3 review R5 (tier-3 fresh subagent, read-only, final-commit acceptance review)

- **Commit reviewed:** `1741e97efa3755c500a1bf17229db8ce1212760f` (`git rev-parse HEAD` in `D:/uri-dev/uri-controls-3`, branch `milestone/uri-controls-3-20261021`; gate `head.txt`: same SHA, dirty=0).
- **Docs-only check:** `git diff a87ee0a1 1741e97e --stat` = `docs/ui/uri_controls_3/URI_CONTROLS_3_REPORT.md` only (6+/3-). Code under review = `a87ee0a1`.
- **Ranges read:** `git diff b774bb85 a87ee0a1` (full: `assist_controller.dart` +7, `brain_quick_controls.dart` +9/-3, `oi_conversation.dart` +4, test +48/-10); `git diff 68061d85 1741e97e -- uri_ui/lib uri_operational_intelligence scripts` (stat + Python diffs in full; Dart feature files re-read at current lines; parts R2-R4 reviewed line by line were spot-checked).
- **Reviewer:** did not write this code; no tracked change, no commit. Experiments ran in a scratch export (`git archive 1741e97e uri_ui`) at `C:/Users/cheta/AppData/Local/Temp/claude/C--Users-cheta-Development-Uri--V1/174285df-d2c8-4145-8120-3fca9e34a8f0/scratchpad/r5/uri_ui`. After the gate's DONE, `.tmp_m26_render/rebuilt_dashboard.png` (modified by the gate) was restored; worktree clean (`git status --short` empty).

## Acceptance criteria for this review (defined first)

1. R4-01 resolved: a grant made in the consent view shows ON immediately, idle and during a turn; the newer of the two worker readings wins.
2. R4-02 / R4-03 resolved or safely carried.
3. R3-01 still holds (no worker -> OFF, no calls; at most one Assist re-read per health reading; no ping-pong); R2-01 still holds (a grant the worker ended shows OFF after the next health reading).
4. No other writer of `AssistController.status` / `OiConversation.brainHealth` bypasses the timestamps; clock edge cases do not create a MEDIUM/HIGH defect.
5. Whole feature meets AC1-AC9 (R1-01 included); Ember (`uri_ui/lib/living/companion/`) and Brain QC closure behaviour kept.
6. Gates for the exact commit COMPLETED_WITH_RESULT.

## Verdict: ACCEPT WITH FINDINGS

No MEDIUM or HIGH remains. R4-01 is fixed and tested, R3-01 and R2-01 still hold, gates on the exact commit are green. Two new LOW findings (R5-01 wall-clock ordering, R5-02 Vision lock lags the newer Assist reading) and one INFO (docs). Carried LOW: R3-03, R3-04; R3-05 INFO. Open verification item (not a code defect): **no live run of the three toggles** against the real worker and the Qwen3.6 Brain (GPU contended by the owner desktop).

## R4 resolution

| R4 | Status | Evidence |
|---|---|---|
| R4-01 MEDIUM: grant shows OFF until next health poll (unbounded during a turn) | **RESOLVED** | `brain_quick_controls.dart:433-436`: `mirrorNewer = a.statusAt > conv.brainHealthAt`; when both readings exist the newer wins. `statusAt` is stamped on every successful status-updating reply (`assist_controller.dart:125-126`, used by `refresh/grant/pause/resume/revoke` `:157,182,189,194,200`), on no-worker (`:112-113`) and on worker reset (`:141-142`). `brainHealthAt` stamped only on a successful health read (`oi_conversation.dart:301-302`). New test `R4-01: a grant made in the consent view shows at once, also while a turn runs` (grant during `conv.busy`, ON with "URI Assist is on", click revokes once, then OFF) passes. Ordering soundness: the worker channel is strictly FIFO (`integrated_runtime.dart` `_dispatch`: `_pending.removeAt(0)`), so reply arrival order equals worker processing order; stamping at arrival is a valid proxy, apart from R5-01. A same-chunk microtask reordering (health has an extra `.timeout` hop) can only make health look newer, which triggers one bounded re-read that converges. |
| R4-02 LOW: old worker's health trusted after restart | **RESOLVED (by mechanism)** | `AssistController` listens to `oi` (`living_app.dart:192-196`, `workerChanges: oi`); any `oi` notification after `runtime = fresh` runs `_checkWorker` -> `_resetForNewWorker` (OFF, `statusAt = now`) before the widget rebuilds, so the mirror (OFF, newer) beats the old health reading. `_call` also resets on a runtime change (`assist_controller.dart:118`). A rebuild between `runtime = fresh` and the first `oi` notification would need an Assist notification, which itself goes through `_call` and resets. Derived from code; not separately tested. |
| R4-03 LOW: vacuous bound test | **RESOLVED** | Fake returns `Map.of(health)` per read; test asserts exactly 1 then exactly 2 `assist_status` calls with `assist_status` failing (`brain_quick_controls_test.dart` R3-01/R4-03 test). Passes. |
| R4-04 INFO: docs | **MOSTLY RESOLVED** (see R5-03) | Report section 2 names `a87ee0a1`; section 6 points at `docs/ui/uri_controls_3/review/`. |

## R3-01 / R2-01 re-check

| Property | Status | Evidence |
|---|---|---|
| No worker -> OFF, unavailable, no calls | **HOLDS** | `connected` guard `brain_quick_controls.dart:427`; both readings null, `onPressed` null (`:467`). Test `R3-01: the worker goes away...` passes (asserts no new calls). |
| Bounded re-reads | **HOLDS** | Re-read only when health is newer and disagrees (`:438-441`), at most once per health Map (`_resyncedFor` Expando, `:482-490`). A failing `assist_status` does not stamp `statusAt`, so it cannot become "newer". Test asserts exactly one per reading. |
| No ping-pong | **HOLDS** | After a successful re-read the mirror is newer and no further re-read is possible for that reading (`!mirrorNewer`); the next re-read needs a new health reading (5 s monitor). |
| R2-01 (worker ended grant -> OFF after next health reading) | **HOLDS** | Health reading is newer -> OFF; one re-read brings the mirror to OFF. Test `R2-01: the worker ended the grant...` passes. |
| Other writers bypassing timestamps | **NONE** | `grep` of `lib` and `test`: `status =` assignments only at `assist_controller.dart:112,125,141` (all stamped); `brainHealth =` only at `oi_conversation.dart:301` (stamped). No `..status`, `brainHealth[...] =`, `.clear()` or test-side direct assignment. Assist events (`_onEvent`) do not touch `status`. |
| Equal timestamps | **LOW, see R5-01** | Tie -> health wins -> one re-read; converges unless the re-read reply also lands in the same clock tick. |
| `DateTime.now` going backwards | **LOW, see R5-01** | Reproduced in scratch, both directions. |

## Acceptance criteria (final commit 1741e97e, code = a87ee0a1)

| AC | Result | Evidence |
|---|---|---|
| AC1: exactly three toggles in the order Thinking, Vision, URI Assist; no Context, Draft, Auto or second Depth picker | **MET** | `brain_quick_controls.dart:219` `qc-thinking`, `:276` `qc-vision`, `:454` `qc-assist` (added last, `:314-315`). `grep "oi-depth\|setDepth(\|qc-context\|qc-draft\|DropdownButton<OiDepth"` in `uri_ui/lib` finds only `:232` (Thinking). The R2-02 negative test passes. |
| AC2: each toggle does real work | **MET** | Thinking `:232` -> `conv.setDepth` -> `'depth': depth.name` in `oi_turn` (`oi_conversation.dart:601`). Vision `:289` `_confirmAndSwitch` -> `:513` `conv.reconfigureBrain` (`oi_conversation.dart:845`). Assist on: `openAssist` + `refresh` (`:474-477`), never grants; off: `revoke` + `refreshHealth` (`:469-472`). |
| AC3: glow only from runtime state; loading/unavailable with reason | **MET (LOW R5-01)** | Assist: newer of two worker readings (`:427-436`); unavailable reasons `:414-422`. Vision glows only from `active['vision_on']` (`:285`). Loading look on pending switch (`:280`). R4-01 test passes. |
| AC4: consent and GPU/VRAM rules unchanged | **MET (LOW R3-03 carried, LOW R5-02)** | Toggle never grants. Worker interlock `worker_bridge.py:726` (`ASSIST_NEEDS_VISION`) and the UI message `oi_conversation.dart:52`. Python diff vs 68061d85 only adds the fallback explain text (`worker_bridge.py:644-654`), `entry_by_profile_id` (`brain_quick_controls.py:79-84`) and the R2-06 unreadable state (`worker_bridge.py:696`); host fit refusal/restore in `scripts/ws_brain_host.py` (reviewed R1-R4). Focused pytest 58 passed. |
| AC5: session and context kept | **MET (tests and reading)** | No new path clears `messages`; Vision-switch tests keep the conversation; Assist/Thinking do not touch it. |
| AC6: accessibility (R1-01) | **MET (LOW R3-04 carried)** | `qc_toggle.dart:130-146` Semantics (button, toggled, enabled, focusable while loading, label, value, hint, onTap, excludeSemantics); `:147` `FocusableActionDetector` with `ActivateIntent` (`:112`, Enter/Space); focus ring `:177`. `ui_controls_typography_test.dart` passes. |
| AC7: consistent after restart | **MET** | Thinking stored/restored `living_app.dart:211-215, 228-229` (`uri.living.thinking`, `:45`); default `OiDepth.fast` (`oi_conversation.dart:207`). Assist OFF after restart via `_resetForNewWorker` and the `connected` guard (R4-02 above). Vision follows host health. |
| AC8: no unrelated change, no new dependency; frozen-check clean | **MET** | `git diff 68061d85 1741e97e -- uri_ui/pubspec.yaml uri_ui/pubspec.lock` empty. Gate `frozen_check.json`: `ok: true`, `unapproved_drift: []`, `unapproved_protected_changes: []`. The wide `uri_ui/lib` stat is the merged UI Controls & Typography candidate (R1-reviewed). Ember: `git diff 68061d85 1741e97e --stat -- uri_ui/lib/living/companion` is empty. Brain QC closure kept: mismatch (`qc-mismatch` `:335`), Assist keeps vision (`vision_locked` `:247` + worker interlock), notice (`qc-notice` `:343`); "P3 via Draft" is superseded by owner-directed D-2 (disclosed). |
| AC9: tests and gates; live run | **MET except live run** | Gate `gates_1741e97e` (DONE present, read): pytest `tests/oi tests/ws` 807 passed, 23 skipped, rc=0; flutter test `+882 ~5 All tests passed!` rc=0 (881 at b774bb85 + the new R4-01 test); analyze 5 infos, the same 5 baseline files (`office_o2_live_check.dart:86`, `providers_screen.dart:730`, `chat_supervised_handoff_test.dart:5`, `assist_mode_test.dart:277`, `ember_transparency_test.dart:15`), rc=1 for infos only; release build `uri_ui.exe` rc=0. **Live run not done** (GPU contended): open verification item, not a code defect. |

## New findings

### R5-01 LOW: the two readings are ordered by wall-clock `DateTime.now()`, so a clock tie or a backwards step can show a stale Assist state

- **Where:** `assist_controller.dart:113,126,142` and `oi_conversation.dart:302` stamp `DateTime.now().microsecondsSinceEpoch`; compared at `brain_quick_controls.dart:433`.
- **Why:** wall-clock time is neither strictly increasing nor fine-grained on Windows. Measured on this host: `DateTime.now()` advances in steps of 0.5-1.9 ms (and can be 15.6 ms when no process raises the timer resolution); NTP steps, manual changes or resume-from-sleep time sync can move it backwards.
- **Scenario A (tie or step back after a health reading; false OFF):** a monitor health read is in flight when the user grants. Its reply (`granted:false`) and the grant reply land in the same clock tick, or the clock has stepped back. Health wins, one re-read is spent, and if that reply is stamped no later than the health reading (same tick, or still before the backwards jump), the toggle shows **OFF / "URI sees nothing on your screen"** while Assist is ACTIVE. The Expando blocks further re-reads until the next health reading, which never comes while a turn runs. This is the R4-01 symptom, but only under a timing coincidence or a clock change. **Reproduced** (scratch `r5_clock_scratch_test.dart`, `conv.brainHealthAt += 1 h` to stand for a backwards step): `assist.state=ACTIVE visual=QcVisual.off statusReads=2`, unchanged after 5 `monitorTick()` during the turn.
- **Scenario B (step back after an Assist reading; false ON):** the worker ends the grant; health says `granted:false` but has an older stamp than the mirror, so the mirror's ACTIVE is shown with no re-read, for as long as the size of the clock step. **Reproduced** (`assist.statusAt += 1 h`): 3 health readings with `granted:false` -> `visual=QcVisual.on`, mirror ACTIVE, 0 re-reads. This is the safe direction for privacy (it claims more access than exists), but it breaks R2-01 for that period.
- **Severity rationale:** LOW. It needs a sub-tick coincidence or a wall-clock step. A is bounded by the next health reading, B by the size of the step. The worker stays the enforcing authority, so no access happens without a grant.
- **Fix (trivial):** replace both stamps with one process-wide strictly increasing counter, for example `int _readingSeq = 0; int nextReading() => ++_readingSeq;` in a shared file, or a shared `Stopwatch` for a monotonic clock. Ties and backward jumps are then impossible. Add a test where the two readings arrive back to back.

### R5-02 LOW: after a grant, the Vision lock still follows only the (older) health reading, so "Vision off" is offered while URI Assist shows ON

- **Where:** `brain_quick_controls.dart:247` (`locked = controls['vision_locked'] == true`, from health only) versus the Assist toggle, which now shows the newer mirror (`:433-436`). The Assist tooltip says "Vision stays on while URI Assist is on."
- **Scenario:** idle, Vision on; the user grants in the consent view. Assist shows ON at once (R4-01 fix), but until the next health poll (up to 5 s) the Vision toggle offers "Click to turn it off". If the user confirms, the worker refuses with `ASSIST_NEEDS_VISION` ("Not switched: a URI Assist session is open...", `oi_conversation.dart:52`). This is a confusing refusal, not a safety breach. During a turn Vision is disabled anyway (`canSwitch` requires `!conv.busy`, `:203`). **Reproduced** (scratch `r5_lock_scratch_test.dart`): `assist=QcVisual.on visionOffOffered=true`; after `refreshHealth()` `visionOffOffered=false`.
- **Fix:** compute the Assist `granted` once (the same newer-of-two rule) and lock Vision when `locked || granted`. Add a test.

### R5-03 INFO (docs): report gates table and open-items list
- **Gates table:** section 5 has no row for `a87ee0a1` / `1741e97e`. The gate has now completed: 807 passed / 23 skipped; flutter 882 passed / 5 skipped; 5 baseline infos; build rc 0; frozen ok.
- **Open-items list:** section 4 lists R3-02 among the open LOW items with the text "static resync guard is now per health reading". R4 marked R3-02 RESOLVED, so the list contradicts the R4 review. Reword or move it.

## What I ran (COMPLETED_WITH_RESULT)
- **Repository checks:** `git rev-parse HEAD`, `git log`, `git diff a87ee0a1 1741e97e --stat`, `git diff b774bb85 a87ee0a1` (full), `git diff 68061d85 1741e97e --stat` and the full Python diff, the pubspec diff (empty), the Ember dir diff (empty), and greps for status/brainHealth writers.
- **Focused flutter tests**, in the scratch export of `1741e97e` (pubspec.lock identical to the earlier scratch copy): `brain_quick_controls_test`, `ui_controls_typography_test`, `uiv2_postint_test`, `assist_mode_test`, `assist_r41_poll_test` and `assist_r9_test` gave **+102 All tests passed**, rc 0.
- **Focused pytest** (worktree): `tests/oi/test_brain_quick_controls.py tests/oi/test_ui_controls_switch_fallback.py` gave **58 passed**.
- **Clock granularity probe** (`dart run clk.dart`): steps of 503-1941 µs.
- **Scratch reproductions** (scratch copy only): R5-A, R5-B and R5-C as quoted above. All three ran to completion and printed the values shown.

## What I only read
- **Gate `gates_1741e97e/`** (after DONE): `head.txt`, `frozen_check.json`, `pytest_oi_ws.log`, `analyze.log`, `flutter_test.log`, `build.log`.
- **Source:** `brain_quick_controls.dart` (toggles, `_assistToggle`, `_resyncAssist`, Vision lock), `qc_toggle.dart`, `assist_controller.dart`, `oi_conversation.dart` (refreshHealth, monitorTick, restartWorker, setDepth, reconfigureBrain), `integrated_runtime.dart` (FIFO dispatch), `living_app.dart`, `worker_bridge.py`, `brain_quick_controls.py`.
- **Docs:** `URI_CONTROLS_3_REPORT.md` and the R4 review. R2, R3 and the typography R1 were read through R4's resolution tables, not re-read in full.

## Not verified
- **No live run** of the three toggles against the real worker and the Qwen3.6 Brain. The GPU is contended by the owner desktop. This is an open verification item for AC3, AC5, AC7 and AC9, not a code defect. D-5 (refusing perception adapters) may make a real grant impossible on this build.
- **Narrator/UIA behaviour** with a real screen reader is not checked.
- **R4-02 resolution** is derived from code (listener ordering), not tested directly.
- **R5-01 Scenario A** with a real same-tick coincidence was not reproduced on real IPC timing. It was simulated by shifting the stamp.

## Required / recommended
- **Nothing blocks integration** on code grounds.
- **Before integration:** the owner's live run of the three toggles is still outstanding.
- **Recommended, cheap, can go alongside or as a follow-up:** fix R5-01 (monotonic counter) and R5-02 (Vision lock from the same Assist rule), and update the report for R5-03.
