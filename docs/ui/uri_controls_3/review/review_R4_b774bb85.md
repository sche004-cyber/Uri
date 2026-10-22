# URI-CONTROLS-3 review R4 (tier-3 fresh subagent, read-only, final-commit acceptance review)

- **Commit reviewed:** `b774bb852d9a1ef96dbe5ece8cbbc2798a6defa8` (`git rev-parse HEAD` in `D:/uri-dev/uri-controls-3`, branch `milestone/uri-controls-3-20261021`; gate `head.txt` also records it with dirty=0).
- **Ranges:** `git diff abdfaa26 b774bb85` (the R3 repair, read in full). Also `git diff 68061d85 b774bb85 -- uri_ui/lib uri_operational_intelligence scripts`, re-checked against AC1-AC9. For the parts R2 and R3 already reviewed line by line, I spot-checked the current line numbers.
- **Reviewer:** I did not write this code. I made no tracked change and no commit. All experiments ran in a copy of `uri_ui` in my scratchpad (`C:/Users/cheta/AppData/Local/Temp/claude/C--Users-cheta-Development-Uri--V1/174285df-d2c8-4145-8120-3fca9e34a8f0/scratchpad/uri_ui`). Its `brain_quick_controls.dart` is byte-identical to b774bb85 (checked with `cmp`).

## Verdict: REVISE (one bounded MEDIUM regression, R4-01)

The R3-01 repair does what R3 asked:
- No stale glow while the worker is gone.
- No call loop.
- At most one Assist re-read per health reading.
- R2-01 still holds.

However, the repair also removed the `refreshHealth()` call from the resync and keeps the worker's health reading as the only authority. That makes a new false state:

- **What happens:** after the user grants URI Assist in the consent view, the toggle shows **OFF**, with the tooltip "URI Assist is off: URI sees nothing on your screen".
- **Why:** the worker has granted and the mirror says ACTIVE, but the toggle waits for the next health poll.
- **How long:** up to 5 s when idle. While a turn is running there is no poll at all (`monitorTick` does not re-read health when `busy`), so the OFF state lasts until the turn ends.
- **Effect of a click:** clicking the toggle in that state opens the consent view again instead of stopping Assist.

This is a privacy-indicator false negative, so AC3 is not met. I reproduced it at b774bb85. At abdfaa26 the same test shows ON (reproduced). At d1388d8c the mirror came first, so it should not happen there either (by reading; not run).

## Acceptance criteria (final commit b774bb85)

| AC | Result | Evidence |
|---|---|---|
| AC1: exactly three toggles in the order Thinking, Vision, URI Assist; no Context, Draft, Auto or second Depth control | **MET** | `brain_quick_controls.dart:219` (`qc-thinking`), `:276` (`qc-vision`), `:448` (`qc-assist`), with Assist placed last (`:315`). Grep for `oi-depth` or `setDepth(` in `uri_ui/lib` finds only `:232`. The R2-02 negative test passes. |
| AC2: each toggle does real work | **MET** | Thinking: `:232` calls `conv.setDepth`, which goes into the `oi_turn` depth (`oi_conversation.dart:597`). Vision: `:289` `_confirmAndSwitch`, then `:507` `reconfigureBrain`. Assist: `:463` revokes and then calls `refreshHealth`. Off: `:469` `openAssist` and `refresh`. The toggle never sends `assist_grant`. |
| AC3: glow only from runtime state; loading and unavailable shown with a reason | **NOT MET (R4-01)** | `:428-430`: `granted = workerGranted ?? mirrorGranted`, where the worker value is the last health reading and always wins. After a grant, the mirror (the worker's own `assist_grant` reply) says ACTIVE but the toggle shows OFF until the next health reading. Unavailable is correct (`:414-422`). Vision glow is correct (unchanged). |
| AC4: consent and GPU/VRAM rules unchanged | **MET (R3-03 LOW carried)** | The toggle never grants. The worker interlock reads live state (`worker_bridge.py:723-727` `ASSIST_NEEDS_VISION`). During R4-01 the UI Vision lock (`brain_quick_controls.dart:247`, from health) can be open, but the worker still refuses. Host fit refusal and the restore after a failed switch are in `ws_brain_host.py`; pytest passes (58 passed). |
| AC5: session and context kept | **MET (by reading and tests)** | No new path resets messages. The Vision-switch tests keep the conversation. Assist and Thinking do not touch it. |
| AC6: accessibility (R1-01) | **MET (R3-04 LOW carried)** | `qc_toggle.dart:130-147`: Semantics toggled, `focusable` while loading, `FocusableActionDetector`. The focused tests pass. |
| AC7: consistent after restart | **MET for the R3-01 cases (LOW R4-02)** | `connected` guard at `:427`. `restartWorker` sets `restarting` and then, on failure, `workerExited` (`oi_conversation.dart:402, 451-456`). The AssistController runtime getter returns null when `workerExited` (`living_app.dart:193`). Thinking is stored and restored (`living_app.dart:214, 228-229`). Residual: a stale health reading from the old worker is not cleared after a successful restart (R4-02). |
| AC8: no unrelated change, no new dependency; frozen-check clean | **MET** | No change to `pubspec.yaml` or `pubspec.lock` across 68061d85..b774bb85. Gate `frozen_check.json` reports `ok: true`. The abdfaa26..b774bb85 code diff touches only `brain_quick_controls.dart` and its test. |
| AC9: tests and gates; live run | **PARTLY** | Focused flutter tests pass: 92. Focused pytest passes: 58. The parallel gate (read, DONE present) reports pytest `tests/oi tests/ws` 807 passed and 23 skipped (rc=0), flutter test +881 ~5 with all tests passing (rc=0), analyze 5 infos (the same count as the baseline, none in the feature lib files; rc=1 for infos only), and a release build with rc=0. Test gaps: no test of a grant made in the consent view, which would have caught R4-01. The R3-01 "next poll" test is vacuous (R4-03). **Live run not done** (GPU contended by the owner desktop): this is an open verification item, not a code defect. |

## R3 resolution

| R3 | Status | Evidence |
|---|---|---|
| R3-01 MEDIUM: stale health glows, per-frame loop | **RESOLVED, but the repair causes R4-01** | (a) **Worker exited, restarting or restart failed:** `connected=false`, so `workerGranted` and `mirrorGranted` are null, the toggle is OFF, `unavailable` is set, there is no resync and `onPressed` is null (`:427-435, 459`). The worktree test passes. By reading, `restarting` and `WORKER_RESTART_FAILED` (`workerExited=true`) take the same branch. (b) **Failing reads:** `brainHealth` is assigned only on a successful read (`oi_conversation.dart:298`). In production every reply is a fresh `jsonDecode` map (`integrated_runtime.dart:140`), so a resync happens once per successful reading. When health reads keep failing, the old map persists and the Expando blocks any further resync. Scratch R4-B: with `assist_status` refusing and fresh health maps, 5 polls of 50 frames each gave exactly **5** `assist_status` calls. (c) **Expando:** when `brainHealth` is `const {}`, `controls` is empty and `worker` is null, so `_resyncAssist` is never reached. A const Map would in any case be a legal Expando key (it is not a number, string, bool, null or record). Expando entries are weak, so there is no leak; the static Expando is shared deliberately. (d) **R2-01:** the worktree R2-01 test passes: the worker ends the grant, the toggle goes OFF, and the mirror is re-read and becomes OFF. |
| R3-02 LOW: static latch | **RESOLVED** | Replaced by the per-reading Expando. No latch can hang now. |
| R3-03 LOW: fail-open Vision lock when Assist is unreadable | **OPEN (carried, disclosed in the report)** | unchanged |
| R3-04 LOW: focus drop | **OPEN (carried)** | unchanged |
| R3-05 INFO | **OPEN (carried)** | unchanged |
| R3-06 LOW: dangling report | **RESOLVED (docs nit remains)** | `docs/ui/uri_controls_3/URI_CONTROLS_3_REPORT.md` now exists and contains AC1-AC9 and D-1..D-5. Remaining nit: its section 6 row for the R2/R3 reviews points only at `D:\uri-dev\lifecycle\...`, although committed copies exist in `docs/ui/uri_controls_3/review/`. Section 2 also says "next commit" instead of `b774bb85`, and there is no gates row for b774bb85 yet. |

## New findings

### R4-01 MEDIUM: after a grant, URI Assist shows OFF ("URI sees nothing on your screen") until the next health poll; with no limit while a turn runs (AC3; regression from the R3-01 repair)

**Where:** `uri_ui/lib/living/integration/brain_quick_controls.dart:427-435` and `:476-485`.
```dart
final workerGranted = connected && worker?['granted'] is bool ? worker!['granted'] as bool : null;
final mirrorGranted = connected && a != null && a.loaded ? (a.active || a.paused) : null;
final granted = workerGranted ?? mirrorGranted ?? false;
...
WidgetsBinding.instance.addPostFrameCallback((_) => a.refresh());   // abdfaa26 also re-read health here
```

**Failure scenario:**
1. Assist is OFF, so the last `brain_health` says `granted:false`.
2. The user grants a window in the Assist view (`assist_mode_view.dart:187/222`, which calls `a.grant`). The worker accepts, and the mirror becomes ACTIVE from the grant reply.
3. Nothing re-reads health after the grant: no caller of `refreshHealth` exists in the assist code.
4. The toggle shows the stale worker value: OFF, with the tooltip "URI Assist is off: URI sees nothing on your screen…".
5. The resync re-reads only `assist_status`, which says ACTIVE again, so the values still disagree. The Expando then blocks any further resync for this reading.
6. The state lasts until the next `monitorTick`. That is 5 s when idle. While `busy` (a turn running), `monitorTick` does not call `refreshHealth` (`oi_conversation.dart:343-352`), so the state lasts until the turn ends plus up to 5 s.
7. Clicking the toggle in that state calls `openAssist` instead of `revoke`, so the user cannot stop Assist from the toggle.
8. The UI Vision-off lock (from health `vision_locked`) is also open. The worker still refuses `ASSIST_NEEDS_VISION`, so this is not a safety breach, only a confusing refusal.

**Reproduced:** scratch widget tests with a `QcRuntime` subclass that returns a fresh health map per read, `assistLinked=true`, and `assist_status` changed to ACTIVE plus `assist.refresh()` to stand for the grant reply.

| Commit and scenario | Result |
|---|---|
| b774bb85, idle, 50 frames without a health poll | `visual=QcVisual.off`, tooltip "URI Assist is off: URI sees nothing on your screen…", while `assist.state=ACTIVE`. After `conv.refreshHealth()` the toggle is `on`. |
| b774bb85, turn running (`conv.send`, `busy=true`), 10 `monitorTick()` calls | still `QcVisual.off`, while `assist.state=ACTIVE`. |
| abdfaa26 `brain_quick_controls.dart` swapped into the same copy, same idle test | `QcVisual.on` with the tooltip "URI Assist is on…". |

**Why simply putting back `refreshHealth()` in the resync is not enough:** each read produces a new map, so every resync would be allowed again. When `assist_status` keeps failing, this would rebuild an endless loop paced by RPC latency (the R3-01 class of bug).

**Fix (small, bounded):**
- Show the **more recent** of the two readings instead of always the health value. Record a timestamp, or a monotonic counter, when `AssistController.status` is set from a successful reply. Record the same when `OiConversation.brainHealth` is assigned. Show whichever is newer.
- On disagreement, keep the one-`assist_status`-re-read-per-health-reading rule. The R2-01 case still resolves, because the newer health reading wins and the mirror is re-read and agrees.
- Alternatively, or in addition: after a successful `grant`, `pause`, `resume` or `revoke`, call `conv.refreshHealth()` once from the Assist path. For example, `LivingServices` could wire `AssistController` to `oi.refreshHealth` on status change, or the Assist view could call it. One call per user action is bounded.
- Add tests:
  - a grant made in the consent view shows ON without waiting for a poll, both idle and while `busy`
  - with `assist_status` failing, the calls stay bounded per reading when health maps are fresh (my scratch R4-B is a template)

### R4-02 LOW: after a successful worker restart, the old worker's health reading is still trusted until the new one arrives
- **Where:** `restartWorker` sets `restarting=false` and `workerExited=false` (`oi_conversation.dart:461-464`) and only afterwards awaits `refreshStatus()`. `refreshStatus` first runs `brain_status` and `brain_catalog`, then `brain_health` (40 s timeout).
- **Why it matters:** `brainHealth` (including `controls.assist.granted:true` from the old worker) is not cleared on exit or restart, so `connected` is true again while the reading belongs to the old worker.
- **Scenario:** a rebuild in that window shows Assist ON for a fresh worker, which by design starts with Assist OFF. One resync is spent on the old reading. If the new worker's first `brain_health` fails, the old reading stays until the next successful poll (5 s ticks).
- **Likelihood:** low, because `restartWorker` does not notify in that window. Derived from code; not reproduced.
- **Fix:** clear `brainHealth` (or at least `controls.assist`) on `worker.exited` and when a new runtime is installed. R3 proposed the same. The R4-01 recency rule also covers this case.

### R4-03 LOW: the R3-01 "next poll" test does not exercise a second reading
- **Where:** `brain_quick_controls_test.dart` (R3-01 failing-status test). With `assistLinked=false`, `QcRuntime.call('brain_health')` returns the **same** `health` object every time (`:106`).
- **Consequence:** `conv.refreshHealth()` hands the Expando the identical key. The "one more chance" path is never taken, and `lessThanOrEqualTo(2)` passes whether or not the per-reading rule works.
- **Status:** production is unaffected, because `jsonDecode` gives a fresh map each time (my R4-B shows 1 call per fresh reading).
- **Fix:** return `{...health}` from the fake, and assert exactly 1 extra call per poll.

### R4-04 INFO (docs): report evidence index and gates table
- **Evidence index:** section 6 lists the R2/R3 reviews only under `D:\uri-dev\lifecycle\...`, but copies are committed at `docs/ui/uri_controls_3/review/review_R2_d1388d8c.md` and `review_R3_abdfaa26.md`. This is the known nit.
- **Commit reference:** section 2 says "next commit" for `b774bb85`.
- **Gates table:** section 5 has no row for `b774bb85`.

## What I ran (COMPLETED_WITH_RESULT)
- **Repository state:** `git rev-parse HEAD` returned b774bb85…. I also ran `git log`, `git diff abdfaa26 b774bb85` (full), `git diff --stat 68061d85 b774bb85` (plus the full diff for `uri_operational_intelligence` and `scripts`), `git diff 68061d85 b774bb85 -- pubspec.*` (empty), and greps.
- **Focused pytest in the worktree:** `pytest -q -p no:cacheprovider tests/oi/test_brain_quick_controls.py tests/oi/test_ui_controls_switch_fallback.py` gave **58 passed**.
- **Focused flutter tests in the scratch copy:** byte-identical controls file; I used the copy so I did not run flutter in the worktree while the gate's flutter test was running. `flutter test --no-pub test/living/brain_quick_controls_test.dart test/living/ui_controls_typography_test.dart test/living/uiv2_postint_test.dart test/living/assist_mode_test.dart` gave **+92, All tests passed**.
- **Scratch reproductions** (`test/living/r4_scratch_test.dart` and `r4_busy_scratch_test.dart`, in the scratch copy only):
  - R4-A idle: OFF while ACTIVE at b774bb85; ON at abdfaa26.
  - R4-A busy: OFF across 10 monitor ticks.
  - R4-B: 5 calls over 5 fresh readings.

## What I only read
- **Parallel gate `gates_b774bb85/`:**
  - head b774bb85, dirty=0
  - `frozen_check.json` ok=true
  - pytest `tests/oi tests/ws`: 807 passed, 23 skipped, rc=0
  - DONE, then: flutter test +881 ~5 All tests passed (rc=0); analyze 5 infos (`office_o2_live_check.dart:86`, `providers_screen.dart:730`, `chat_supervised_handoff_test.dart:5`, `assist_mode_test.dart:277`, `ember_transparency_test.dart:15`; rc=1, infos only); release build `uri_ui.exe` rc=0. After DONE, I restored `.tmp_m26_render/rebuilt_dashboard.png`, which the gate had modified, so the worktree is clean.
- **Source:**
  - `brain_quick_controls.dart` (`_assistToggle`, `_resyncAssist`)
  - `qc_toggle.dart`
  - `oi_conversation.dart` (refreshStatus, refreshHealth, monitorTick, restartWorker, worker.exited)
  - `assist_controller.dart`, `assist_mode_view.dart` (grant call sites), `integrated_runtime.dart`, `living_app.dart`
  - `worker_bridge.py` (`_assist`, `ASSIST_NEEDS_VISION`), `brain_quick_controls.py`, `ws_brain_host.py` (restore after a failed switch)
- **Docs:** the URI-CONTROLS-3 report, and the R2 and R3 reviews.

## Not verified
- **No live run** of the three toggles against the real worker and the Qwen3.6 Brain. The GPU is contended by the owner desktop. This is an open verification item for AC3, AC5, AC7 and AC9, not a code defect. R4-01 would show live on any real grant, but D-5 (perception adapters are placeholders) may make a real grant impossible on this build.
- **R4-02** is derived from code, not reproduced.
- **Real Narrator/UIA behaviour** is not checked.

## Required to accept
- Fix R4-01 with the recency rule, or one `refreshHealth` per Assist user action, and keep the per-reading bound. Add its tests.
- Fix the R4-03 fake so the bound is actually tested.
- R4-02 and R4-04 may be carried or fixed alongside.
- The live run is still required before integration, per the owner's conditions.
