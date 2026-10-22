# URI-CONTROLS-3 review R3 (tier-3 fresh subagent, read-only re-review)

- **Commit reviewed:** `abdfaa26d8ed91319648f5a4b16ec25b71fb0b06`. I checked it with `git rev-parse HEAD` in `D:/uri-dev/uri-controls-3`, branch milestone/uri-controls-3-20261021.
- **Worktree state:** clean at the start and at the end. `.tmp_m26_render/rebuilt_dashboard.png` was modified by the parallel gate's flutter test run; I restored it after the gate wrote DONE.
- **Ranges:** `git diff d1388d8c abdfaa26` (commits 708500fd and abdfaa26), read in full. I also re-checked `git diff 68061d85 abdfaa26 -- uri_ui/lib uri_operational_intelligence scripts`.
- **Reviewer:** I did not write this code. I made no tracked change and no commit. My scratch experiments ran in a copy of `uri_ui` in my scratchpad, not in the worktree.

## Verdict: REVISE (one small, bounded repair)

Most R2 findings are repaired correctly:
- R2-02: the second Depth picker is gone, and store and restore are symmetric.
- R2-03: focus is kept while a toggle shows loading.
- R2-04: unrelated Assist work no longer shows a spinner.
- R2-07: analyzer is back to 5 baseline infos.
- R2-05: tests were added.

However, the R2-01 repair introduced a **MEDIUM regression (R3-01)**, which I reproduced by running it. The cause is that the URI Assist toggle now trusts `brain_health.controls.assist.granted` even when that health snapshot is stale:
- If the worker exits (or is restarting, or its restart failed) while Assist holds a grant, the toggle **glows ON** ("URI Assist · unavailable").
- `_resyncAssist` then calls `brain_health` **once per frame, without end**, while that state lasts.
- The same per-frame loop (2 RPCs per frame) happens whenever `assist_status` keeps failing while health says granted.
- At d1388d8c the same scenario showed OFF with 0 extra calls.

This breaks AC3 (glow only from worker-verified state) and AC7 (Assist off after a worker restart, and stays responsive), and it fails the specific check requested for this review: that the resync cannot loop or spam the worker.

## Acceptance criteria

| AC | Result | Evidence |
|---|---|---|
| AC1: exactly three toggles; no other Thinking/Depth control | **MET** | `brain_quick_controls.dart:217-233` (Thinking), `:275-291` (Vision), `:313-315` (Assist last). The `oi-depth` dropdown was removed (`oi_widgets.dart:573-574`). A grep of `uri_ui/lib` finds no other `setDepth` caller and no Depth picker. What remains is read-only diagnostics: `oi_health_widgets.dart:248` "Thinking: depth fast" and `workspace_mode_view.dart:1473` "Reasoning: Depth fast" (see R3-05). Test R2-02 (`brain_quick_controls_test.dart:611-618`) passes. |
| AC2: real functionality | **MET** | Thinking: `:232` calls `conv.setDepth`, and `oi_conversation.dart:597` sends `depth`. Vision: `_confirmAndSwitch` calls `reconfigureBrain` (unchanged). Assist: when on, `:458-461` revokes and then calls `refreshHealth`. When off, `:464-467` calls `openAssist` and `refresh`, and never sends `assist_grant`. |
| AC3: glow only from worker-verified state; loading and unavailable shown with reasons | **NOT MET (R3-01)** | `:417-419` makes the health value the authority with no freshness check. The health map is kept when a read fails (`oi_conversation.dart:291-319`) and is not cleared on `worker.exited` (`:884-890`). Result: a stale `granted:true` glows while `unavailable` is shown. Reproduced (see "What I ran"). Vision glow is still correct (`controls.active`). |
| AC4: consent, GPU and VRAM | **MET (LOW R3-03)** | The toggle never grants. `vision_locked` and `ASSIST_NEEDS_VISION` are unchanged (`worker_bridge.py:722-725`, `brain_quick_controls.py:200-201`). When the Assist state cannot be read, the lock fails open; this is the same as before but now explicit (R3-03). |
| AC5: session and task context preserved | **MET (by reading and tests)** | Assist and Thinking changes do not touch the conversation. Vision keeps the conversation (existing tests). No new code path resets messages. |
| AC6: accessibility | **MET with LOW residual (R3-04)** | `qc_toggle.dart:130-152`: single Semantics node (button, toggled, label, value, hint, onTap), with `focusable` kept while loading. `FocusableActionDetector(enabled: onPressed != null \|\| loading)` at `:150`. Activation is guarded by `_enabled` (`:115-119`). The R2-03 test passes. Residual: focus can still drop when loading ends in a disabled state. |
| AC7: consistent after restart | **PARTLY MET (R3-01)** | Thinking is stored only for fast/normal (`living_app.dart:211-215`) and restored only for those (`:227-228`), so the two sides are symmetric. Assist: the mirror is reset to OFF (`assist_controller.dart:133-148`), but the toggle now prefers stale health. It glows ON during `restarting`, and indefinitely after `WORKER_RESTART_FAILED`, and runs the per-frame resync loop meanwhile. |
| AC8: no unrelated changes or new dependencies | **MET with LOW docs finding (R3-06)** | `pubspec.yaml`, `pubspec.lock` and `lib/living/companion/` are unchanged across 68061d85..abdfaa26. The d1388d8c..abdfaa26 diff touches only the controls, `living_app`, the worker's `_assist`, tests and docs. The 708500fd QcStyle reformat is formatting only. |
| AC9: meaningful tests | **MET with gap** | New tests: R2-01 staleness, R2-06 unreadable state, R2-03 focus while loading, R1-03 notice, R2-02 no picker, and a stronger Tab-skip test. Missing: any test where health is stale or unreadable while the worker has exited or is restarting, or where `assist_status` fails (this would have caught R3-01). |

## R2 resolution

| R2 | Status | Evidence |
|---|---|---|
| R2-01 MEDIUM: Assist glows after the worker ended the grant | **RESOLVED for the reported case, but the fix REGRESSES (R3-01)** | `:417-423`. The worker value wins and a disagreement triggers one resync. Test `brain_quick_controls_test.dart:666-687` passes. The repair has no freshness or availability guard and no backoff, which is R3-01. |
| R2-02 MEDIUM: second Depth control | **RESOLVED** | The dropdown was removed (`oi_widgets.dart:573`). Store is filtered (`living_app.dart:212`) and restore is filtered (`:228`). No caller in lib sets auto or deep. `uiv2_postint_test.dart:148` still calls `setDepth(deep)` through the API only, to check voice/typed parity, and passes. `ws_ui_live_test.dart:106` sets auto (live test, API only). The old live drivers that referenced `oi-depth` or `qc-thinking-menu` are documentation; SUCCESSOR.md marks them obsolete. |
| R2-03 LOW: focus lost while loading | **RESOLVED (LOW residual R3-04)** | `qc_toggle.dart:134-135,150,177`. Test `:573-589`. Only Vision has a loading look now. |
| R2-04 LOW: "changing" for unrelated Assist work | **RESOLVED by removal** | `:452-453`. Assist never shows loading. A revoke in flight shows no feedback, and a second press sends a second idempotent `assist_revoke`. INFO only. |
| R2-05 LOW: test gaps | **PARTLY** | R1-03, R2-01, R2-03 and the Tab-skip assertion were added (`:526-531`). There is still no Windows platform override, and no stale-health or worker-exit case (see AC9). |
| R2-06 LOW: a catalog error marks Assist unavailable | **PARTLY** | When `assist_state` raises, the worker now sends `{granted: None, error: ASSIST_STATE_UNREADABLE}` (`worker_bridge.py:692-696`). The UI falls back to the Assist mirror (test `:689-700`). `vision_locked` is `bool(None)`, i.e. False, exactly as before (pytest `test_assist_state_failure_never_breaks_controls`). However, the `PROFILE_UNDESCRIBED` dict (`worker_bridge.py:679-681`) still has no `assist` key, so `brain_quick_controls.dart:429-430` still shows "not available in this URI worker" in that case. |
| R2-07 LOW: analyzer infos | **RESOLVED** | Gate `gates_abdfaa26/analyze.log` shows 5 infos, all in files outside this feature, rc=1 (infos only, same as the baseline). My `flutter analyze` on the 5 changed Dart files: "No issues found!". |
| R2-08 LOW: evidence and docs lag | **PARTLY (R3-06)** | There is a supersession header (`UI_CONTROLS_TYPO_REPORT.md:3-6`), a SUCCESSOR.md note, and a committed driver `controls3_driver.dart`. However, the header points to `docs/ui/uri_controls_3/URI_CONTROLS_3_REPORT.md`, which **does not exist**. There is no URI-CONTROLS-3 acceptance-criteria record and still no live run. |
| R2-09 / R2-10 INFO (owner decisions) | **OPEN for the owner** | P3 is unreachable from the UI, context is coupled to Vision, Thinking defaults to Off (`oi_conversation.dart:204`), and Paused shows as ON and is revoked on click. Unchanged. |
| R2-11 INFO | **unchanged** | The redundant ternary is still at `companion_mode_view.dart:478`, plus a second one at `a2ui_view.dart:233`. Both are harmless. |

## New findings

### R3-01 MEDIUM: a stale health snapshot makes URI Assist glow ON while the worker is gone, and `_resyncAssist` loops every frame (AC3, AC7; regression from the R2-01 repair)

**Where:** `uri_ui/lib/living/integration/brain_quick_controls.dart:417-423` and `:471-485`.
```dart
final workerGranted = worker?['granted'] is bool ? worker!['granted'] as bool : null;
final mirrorGranted = a != null && a.loaded ? (a.active || a.paused) : null;
final granted = workerGranted ?? mirrorGranted ?? false;
...
if (a != null && workerGranted != null && mirrorGranted != null && workerGranted != mirrorGranted && !a.busy) {
  _resyncAssist(conv, a);
}
```

**Failure scenario:**
1. Assist holds a grant, so the last `brain_health` reported `controls.assist.granted == true`.
2. The worker process exits. `integrated_runtime.dart:153` sets `_closed`, and the UI receives `worker.exited`.
3. `OiConversation` sets `workerExited` but keeps `brainHealth` (`oi_conversation.dart:884-890`).
4. AssistController's runtime getter now returns null (`living_app.dart:193`), so `_checkWorker` resets the mirror to OFF and `loaded` stays true.
5. The two values now disagree: `workerGranted=true` (stale) and `mirrorGranted=false`.
6. The toggle glows ON with the status "unavailable".
7. `_resyncAssist` runs `a.refresh()`, which returns at once with WORKER_NOT_CONNECTED and notifies. It then runs `conv.refreshHealth()`, which gets an immediate `WORKER_CLOSED` error (`integrated_runtime.dart:165`). That sets `conv.lastError='WORKER_CLOSED'` (overwriting WORKER_EXITED or WORKER_RESTART_FAILED) and notifies. `_resyncing` is cleared.
8. The next frame rebuilds and the cycle starts again: an endless run of frames with no backoff.

**When it ends:**
- After a successful restart, it ends once the fresh worker's health is read.
- After WORKER_RESTART_FAILED it never ends: continuous rendering on a GPU-contended machine, and a permanent ON glow.

**A second trigger, while the worker is alive:**
- Condition: `assist_status` keeps refusing while health says granted.
- What happens: `_call` leaves `status` unchanged on error (`assist_controller.dart:124-126`), so the two values never agree.
- Result: 2 RPCs per frame, without end.

**Reproduced:** scratch widget test in a copy of the abdfaa26 `uri_ui` (`QcRuntime` subclass, no tracked file):

| Scenario and commit | Look after 50 frames of 16 ms | Calls made in those 50 frames |
|---|---|---|
| Worker exited, abdfaa26 | `visual=QcVisual.on status=unavailable` | 50 (`brain_health`, one per frame) |
| `assist_status` refusing, abdfaa26 | `visual=QcVisual.on` | 100 |
| Worker exited, d1388d8c (same test) | `visual=QcVisual.off` | 0 |

**Fix (small):**
- Accept `controls.assist` only while it can be current: not `workerExited`, not `restarting`, and `a.available`. Otherwise use the mirror, or simply OFF.
- Preferably, clear `brainHealth['controls']['assist']` when the worker exits or is replaced.
- Resync at most once per health snapshot, for example by remembering `identical(conv.brainHealth, _lastResyncedHealth)`, or by using a cooldown. Never resync while `unavailable != null`.
- Add tests:
  - worker exited with a stale `granted:true` gives OFF and 0 extra calls over N frames
  - `assist_status` failing gives a bounded number of calls

### R3-02 LOW: the static `_resyncing` latch has no timeout, and the callback holds the controller
- **Hang:** if `a.refresh()` or `refreshHealth()` hangs, `_resyncing` stays true. `rt.call` has a 2-minute timeout and `refreshHealth` a 40 s one, so the latch is bounded by those, but `a.refresh()` has no timeout of its own beyond the runtime's 2 minutes. Until then, no resync happens anywhere.
- **Static state across instances:** the flag is shared by every BrainQuickControls (full composer plus the compact dialog). That is acceptable, and even desirable for dedupe.
- **Tests:** the static state survives across tests in one isolate. A test that ends with a resync's await pending would silently disable resync in later tests of the same file.
- **Disposal:** the widget being disposed is safe, because the callback never touches `context` or `State`. If the AssistController itself is disposed mid-call, `_call`'s `finally notifyListeners()` asserts in debug. Its lifetime is the app's, so this is only a concern at shutdown.
- **Fix:** keep the latch in `AssistController`, or key it per controller, and fold it into the R3-01 one-resync-per-snapshot rule.

### R3-03 LOW: an unknown Assist state fails open for the Vision lock (UI and worker)
- **Where:** `worker_bridge.py:692-696` returns `granted: None`. `brain_quick_controls.py:201` then computes `vision_locked = bool(None) = False`. The `ASSIST_NEEDS_VISION` check (`worker_bridge.py:724`) is skipped.
- **Meanwhile in the UI:** the fallback shows Assist ON from the mirror (test `:689-700`) while the Vision-off choice is enabled.
- **Scenario:** a transient `assist_state` exception while a grant is ACTIVE. The user can switch to Long (vision off) under a live Assist grant, which is exactly what closure D2/D6 forbids.
- **Severity:** the same as before R2-06 (None was also fail-open), so this is not a regression. It is a safety gap that the repair made visible without closing.
- **Fix:** treat `granted is None` as locked (fail closed) in `controls()` and in `_brain_reconfigure`, or in the UI lock the Vision-off choice when the mirror says granted.

### R3-04 LOW: focus can still drop when loading ends in a disabled state (AC6 residual)
- **Where:** `qc_toggle.dart:150`. The node is focusable while loading or while `onPressed != null`.
- **Scenario:** when a Vision switch ends with an error look, or in "starting" or "not running" with `can_switch=false` (for example host not running or a restart pending), `onPressed` is null and the visual is not loading. `canRequestFocus` turns false and focus jumps to the scope's previous focus, typically the composer.
- **Status:** derived from code; not reproduced.
- **Fix:** keep the node focusable whenever it was focused (`enabled: true`, guarding activation only), or move focus deliberately.

### R3-05 INFO: diagnostics still use the depth vocabulary
`oi_health_widgets.dart:248` ("Thinking: depth fast") and `workspace_mode_view.dart:1473` ("Reasoning: Depth normal") are read-only, so they do not violate AC1. They use different words from the On/Off toggle, and the owner may want them aligned.

### R3-06 LOW: dangling record reference, and the live evidence is still missing (AC8, R2-08)
- **Dangling reference:** the supersession header (`UI_CONTROLS_TYPO_REPORT.md:6`) names `docs/ui/uri_controls_3/URI_CONTROLS_3_REPORT.md`, which is not in the tree; `docs/ui/uri_controls_3/` contains only `live_harness/`. There is no URI-CONTROLS-3 acceptance-criteria file.
- **Contradictory guidance:** SUCCESSOR.md lines 9-10 still say "the current live driver is …ui_driver.dart" above the new note that says otherwise.
- **Automated consent in the driver:** `controls3_driver.dart:350-368` makes the consent-view grant by calling `assist.grant(...)` directly. That is acceptable for automation, but the report must state it as automated consent, not a human choice.

## Specific checks requested

| Check | Result |
|---|---|
| `_resyncAssist` cannot loop or spam the worker | **FAILS** (R3-01, reproduced). |
| Safe if the widget is disposed | **Yes.** No context or State is used; `OiConversation.refreshHealth` checks `_disposed`. See R3-02 for the controller-disposed edge case. |
| Static `_resyncing` acceptable | **Acceptable as a dedupe across instances only after the R3-01 fix.** See R3-02. |
| R2-03 focus-while-loading semantics | Correct. While loading, Semantics has enabled=false, focusable=true, focused follows the focus highlight, and there is no tap action. Residual R3-04. |
| R2-06 Python change safe for `vision_locked` | **Unchanged behaviour** (False, as with None). Fail-open, R3-03. |
| Removal of `oi-depth` breaks nothing | **Confirmed.** No reference to `oi-depth` in `uri_ui/lib`, `test` (except the new negative test) or `integration_test`. No lib caller of `OiDepth.deep` or `auto`. Voice and typed turns send `conv.depth` (parity test passes). Analyzer is clean for `oi_widgets.dart` (no unused import). |

## What I ran (COMPLETED_WITH_RESULT)
- `git rev-parse HEAD` returned abdfaa26…. I also ran `git log`, `git diff d1388d8c abdfaa26` (full), `git diff --stat 68061d85 abdfaa26`, and greps.
- `flutter test --no-pub test/living/brain_quick_controls_test.dart test/living/ui_controls_typography_test.dart test/living/uiv2_postint_test.dart`: **+72, All tests passed**.
- `pytest -q tests/oi/test_brain_quick_controls.py tests/oi/test_ui_controls_switch_fallback.py`: **58 passed**.
- `flutter analyze --no-pub` on `qc_toggle.dart`, `brain_quick_controls.dart`, `oi_widgets.dart`, `living_app.dart` and `brain_quick_controls_test.dart` (scratch copy): **No issues found**.
- Scratch reproduction of R3-01 in a copy of `uri_ui` in my scratchpad (not in the worktree):
  - abdfaa26: worker exited gave ON plus 50 `brain_health` calls in 50 frames; `assist_status` refusing gave ON plus 100 calls.
  - d1388d8c `brain_quick_controls.dart` swapped into the same copy: worker exited gave OFF and 0 calls.

## What I only read
- **Parallel gate logs** in `gates_abdfaa26/`, which I did not run myself:
  - head abdfaa26, dirty=0
  - frozen_check rc=0, no unapproved protected changes
  - pytest tests/oi and tests/ws: 807 passed, 23 skipped, rc=0
  - analyze: 5 infos (none in feature files), rc=1
  - flutter test: +879 ~5, All tests passed, rc=0
  - windows release build: rc=0
- **Source:**
  - `qc_toggle.dart`, `brain_quick_controls.dart`, `assist_controller.dart`
  - `oi_conversation.dart` (refreshHealth, restartWorker, worker.exited)
  - `integrated_runtime.dart` (call, `_closed`), `living_app.dart`, `living_composer.dart`
  - `worker_bridge.py` (`_assist`, `_brain_reconfigure`), `brain_quick_controls.py`, `uri_assist/access.py` (`snapshot` expires lazily, so health and status agree when both reads succeed)
  - the docs changes and `controls3_driver.dart` (header and Assist section)

## Not verified
- **No live run** of the three toggles against the real worker and the Qwen3.6 Brain. The GPU is contended (owner desktop dwm.exe about 1.8 GB). This is not counted against code acceptance, but it is still an open verification item for AC3, AC5 and AC7 runtime proof. R3-01 would show in a live run only if the worker exits or restarts while a grant is held.
- **Real Narrator/UIA behaviour on Windows:** only the flutter_test semantics tree was checked.
- **R3-04** is derived from code, not reproduced.

## Required to accept
Fix R3-01 (availability and freshness guard plus a bounded resync) and add its two tests. Fix the dangling report reference (R3-06), or commit the URI-CONTROLS-3 report it names. R3-02..R3-05 may be fixed or carried. The live run is still required before integration.
