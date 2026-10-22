# URI-CONTROLS-3 review R2 (tier-3 fresh subagent, read-only)

- **Commit reviewed:** `d1388d8c888500cb08898da85fd05e27ee25a838`. I checked it with `git rev-parse HEAD` in `D:/uri-dev/uri-controls-3`, branch milestone/uri-controls-3-20261021.
- **Range:** `68061d85..d1388d8c`. It contains merge 5f9e5cc6 (of e9ee7409), 0d77a015 (the R1 record) and d1388d8c (the repair).
- **Ancestry:** ec2fab54 is an ancestor of 68061d85 (checked with `git merge-base --is-ancestor`).
- **Reviewer:** I did not write this code. I modified no tracked file and made no commit.

## Verdict: REVISE (small, bounded repair)

The three-toggle design is implemented correctly and the R1 repairs are real:
- Thinking sends the turn depth.
- Vision goes through the qualified catalog, asks for confirmation, and glows only once the worker has verified the change.
- Off->On for URI Assist opens the consent view without granting anything. On->Off sends `assist_revoke`.
- R1-01 keyboard and screen-reader support works.

Two MEDIUM defects need fixing before acceptance, because they break owner criteria AC3 and AC1/AC7:
- **R2-01:** the URI Assist toggle can keep glowing after the worker has ended the grant (the 30-minute TTL expiry, or target lost).
- **R2-02:** a second Thinking/Depth control with Auto and Deep is still on the same conversation screen. Its values do not survive a restart.

Neither fix is large. No live run of the d1388d8c UI exists yet.

## Acceptance criteria

| AC | Result | Evidence |
|---|---|---|
| AC1: exactly three quick controls; Context, Draft and Thinking Auto menu removed | **MET for the quick-control row; see R2-02** | `brain_quick_controls.dart:221-233` (Thinking), the Vision block, and `:312-315` (Assist added last). Context, Draft and the menu are removed in the d1388d8c diff. Test "the row holds exactly Thinking, Vision and URI Assist" passes. However, `oi_widgets.dart:573-592` (OiBrainBar `oi-depth`) still offers Depth auto / fast / thinking / deep in the same pane (live screenshot ui-2/20 shows "Depth: auto" above the chat and "Reasoning: Depth auto" in the side panel). With no catalog, Vision is hidden and only two controls show; this is documented. |
| AC2: real functionality | **MET** | Thinking calls `conv.setDepth`, and `oi_conversation.dart:597` sends `'depth': depth.name` (the test checks that `oi_turn` has depth `fast`). Vision still goes through `_confirmAndSwitch` to `reconfigureBrain`. Assist: `:451-460`. When granted it calls `a.revoke()` (`assist_revoke`). When off it calls `openAssist()` and then `a.refresh()`, and does not grant (test: no `assist_grant` is sent). |
| AC3: glow only from worker-verified state; loading and unavailable shown with reasons | **NOT MET (R2-01)** | Vision is correct (`controls.active`). For Assist, `brain_quick_controls.dart:414` uses the cached `AssistController.status` whenever `a.loaded` is true and ignores the fresher `controls.assist.granted` that arrives with each 5 s health poll. The worker revokes on its own: `uri_assist/access.py:47` sets DEFAULT_TTL_S = 30 min, `:179-181` expires the grant, `:174-177` handles target_lost. When that happens the toggle keeps glowing ON while the worker reports OFF and the Vision lock lifts. Loading and unavailable states with reasons exist (`:417-425`, `:444`), but see R2-04 and R2-06. |
| AC4: permissions, GPU and VRAM | **MET** | The consent model is unchanged: the UI never calls `grant` from the toggle. `lockVision` and the worker's `ASSIST_NEEDS_VISION` refusal (`worker_bridge.py:722-725`) are unchanged. The catalog and fit refusals are unchanged; only the Context and Draft entry points were removed. |
| AC5: context preserved | **MET (by reading and tests)** | Vision switches keep the conversation (existing tests). The Assist toggle changes only the presentation mode or the Assist session; `OiConversation` is a shared service. Test "Thinking, Vision and URI Assist switch independently" passes. |
| AC6: R1-01 accessibility | **MET with LOW findings (R2-03, R2-05)** | `qc_toggle.dart:142-160` has a single Semantics node (button, toggled, enabled, focusable, label, value, hint and onTap) with `excludeSemantics: true`, so the Focus, Tooltip and Text semantics underneath are dropped and nothing is announced twice. FocusableActionDetector maps ActivateIntent (`:124`, `:159`), and the focus ring is a foregroundDecoration (`:187`). On Windows, Enter and Space reach ActivateIntent: `WidgetsApp._defaultShortcuts` (flutter `app.dart:1265-1267`) maps enter, numpadEnter and space to ActivateIntent, and Windows does not use the web map that sends Enter to ButtonActivateIntent. The composer's `CallbackShortcuts` for Enter wraps only the TextField (`living_composer.dart:297-300`), so it does not capture Enter on a toggle. Disabled controls get `canRequestFocus=false` through `FocusableActionDetector(enabled:)`, so Tab skips them. Tooltip and GestureDetector interplay: taps work (tests). The Tooltip is not shown on keyboard focus, so keyboard-only users see no reason for a disabled toggle (screen readers get it as the hint). |
| AC7: consistent after restart | **PARTLY MET (R2-02)** | `living_app.dart:211-214` stores and `:227-228` restores `uri.living.thinking`. The restart test passes. However, only `fast` and `normal` are restored, while the OiBrainBar can set and store `auto` or `deep`, so a Deep choice (shown as Thinking ON) comes back as OFF after a restart. Vision comes from the host. Assist starts OFF after a worker restart (`assist_controller.dart:130-145`, `_resetForNewWorker`; `living_app.dart:192-196` passes `workerChanges: oi`). |
| AC8: no unrelated changes or new dependencies; R1-02..06 truthful | **MET with LOW docs findings (R2-08)** | `pubspec` is unchanged in the range, and there is no change under `uri_ui/lib/living/companion/`. R1-02: ui-2 `observations.json` has exactly 26 rows with result PASS (plus one REFUSED_DOES_NOT_FIT row), so 26/26 is correct. R1-03: `brain_quick_controls.dart:385-389`. R1-04: `ws_brain_host.py:469-479`, with 2 new pytests. R1-05: wording fixed in 3 places. R1-06: `:595-596`, tested. R1-07 (INFO) is still not handled in SUCCESSOR.md. |
| AC9: meaningful tests | **MET with gaps (R2-05)** | The new tests cover the three-control order, Space/Enter/Tab, semantics with a real `SemanticsAction.tap`, the Assist off/on/paused/unavailable states, independence of the three toggles, depth persistence across an app restart, and the R1-04 host record. Missing tests: R1-03, Assist expiry or staleness, and focus after loading. The Tab-skip assertion is weak. |

## Findings

### R2-01 MEDIUM: the URI Assist toggle can glow after the worker ended the grant (AC3)
- **Where:** `uri_ui/lib/living/integration/brain_quick_controls.dart:414`
  ```dart
  final granted = a != null && a.loaded ? (a.active || a.paused) : worker?['granted'] == true;
  ```
- **Failure scenario:**
  1. The user grants Assist; `grant` updates `status` and sets `loaded=true`.
  2. Thirty minutes later the worker expires the grant (`access.py:179-181`), or the window closes (`target_lost`).
  3. `brain_health.controls.assist.granted` becomes false within 5 s, so the Vision lock lifts (`vision_locked` comes from the worker).
  4. `AssistController` is refreshed only by Assist commands; it has no poll and no state event. The toggle keeps glowing "URI Assist is on: URI may look only at what you allowed" until some Assist command runs.
- **Result:** Two surfaces on the same row disagree. The glow is no longer worker-verified, which AC3 forbids. Clicking it is harmless (it sends a revoke).
- **Fix:** Treat `controls.assist.granted` (fresh from the worker on every health poll) as the authority for on/off whenever it is present. Use the controller only for Paused and busy. Alternatively, call `a.refresh()` when the two disagree. Add a test with `assistStatus` ACTIVE and `controls.assist.granted=false` after a `refreshHealth`.

### R2-02 MEDIUM: a second Thinking/Depth control with Auto and Deep remains on the same screen, and its values do not persist (AC1 intent, AC7)
- **Where:**
  - `uri_ui/lib/living/integration/oi_widgets.dart:573-592`: OiBrainBar `oi-depth` DropdownButton (Depth: auto / fast / thinking / deep). It is shown unconditionally by `OiConversationPane` (`:109`), which is used in Workspace (`workspace_mode_view.dart:451`) and Companion (`companion_mode_view.dart:511`).
  - Live evidence `docs/ui/controls_typography_20261018/evidence/live/ui-2/20-workspace-conversation.png` shows "Depth: auto" above the chat and "Reasoning: Depth auto" in the right panel.
- **Failure scenario:** The owner asked for the Thinking Auto menu to be removed, yet Auto (and Deep) can still be chosen from the dropdown a few hundred pixels above the toggle.
  - Choosing Auto there makes the toggle show "Thinking · Auto" with the OFF look.
  - `onDepthChanged` stores `auto` or `deep`, but `living_app.dart:228` restores only `fast` or `normal`. After a restart, Deep (shown as ON) silently comes back as OFF, and Auto comes back as Off.
- **Fix:** This is the owner's choice:
  - (a) Reduce the dropdown to Off/On (fast/normal), or remove it now that the quick control exists, and keep diagnostics read-only.
  - (b) Keep it as an expert control. Then restore every stored `OiDepth` name and say in the docs that two controls exist.

  Either way, make store and restore symmetric.

### R2-03 LOW: keyboard focus is lost when a toggle enters its loading state (AC6)
- **Where:** `qc_toggle.dart:127`. `_enabled` is false while `visual == loading`, so `FocusableActionDetector(enabled: false)` sets `canRequestFocus=false`, and Flutter unfocuses a focused node whose `canRequestFocus` turns false.
- **Scenario 1:** A keyboard user presses Space on URI Assist while it is on. `revoke` sets busy, which shows the loading look, and focus jumps to the scope's previously focused child (typically the composer field). The next Space types into the composer.
- **Scenario 2:** Vision: confirm the switch. The dialog's focus restore targets a node that cannot take focus, so the keyboard position is lost.
- **Fix:** Keep the node focusable while loading (`FocusableActionDetector(enabled: widget.onPressed != null)`) and only ignore activation in `_activate`. Alternatively, restore focus when loading ends. Add a test.

### R2-04 LOW: the Assist toggle shows "changing" for unrelated Assist work (AC3)
- **Where:** `brain_quick_controls.dart:444` (`a.busy`). `AssistController.busy` is set by every `_call`, which includes `ask`, `check`, `listTargets`, `loadProviders`, `research` and `cancelResearch` (`assist_controller.dart:113-130`).
- **Scenario:** While the Assist view asks a question or a web research starts, the toggle briefly turns into a disabled spinner labelled "changing", though Assist itself is not changing. The window is short, because polling uses `rt.call` directly.
- **Fix:** Set a separate flag only for status, grant, revoke, pause and resume.

### R2-05 LOW: test gaps (AC9)
- "a disabled toggle is skipped by Tab" (`brain_quick_controls_test.dart`, R1-01 group) checks only that no dialog opened. It would also pass if Vision were focused, because a disabled Vision ignores Enter anyway. Assert `FocusManager.instance.primaryFocus` or the focus ring on `qc-assist`/`qc-thinking`, and assert `conv.depth` after the Enter.
- The R1-03 notice ("URI is still going back to …", `brain_quick_controls.dart:385-389`) has no widget test. The other fallback notices do.
- There is no test for R2-01 staleness or R2-03 focus. Keyboard tests run on the default test platform; the shortcut map is the same as on Windows (verified in the SDK source), so this is acceptable, but `debugDefaultTargetPlatformOverride = TargetPlatform.windows` would make the claim explicit.

### R2-06 LOW: a catalog error marks Assist "not available in this URI worker"
- **Where:**
  - `brain_quick_controls.dart:423`: `controls.isNotEmpty && worker == null` leads to "unavailable".
  - `worker_bridge.py:679-681`: the PROFILE_UNDESCRIBED error dict has no `assist` key.
  - `_assist()` returns None if `assist_state` raises (`:687-695`).
- **Scenario:** A describe error, or a transient exception in `assist_state`, disables the Assist toggle with a false reason, even though Assist commands work and the controller may hold a real state.
- **Fix:** Treat `assist: null` as "unknown" when the controller has loaded a status. Alternatively, have the worker always emit `assist` when Assist commands are registered.

### R2-07 LOW: analyzer infos rose from 4 to 10
- **Where:** The parallel gate `gates_d1388d8c/analyze.log` (rc=1, infos only, as at 22b53b78). The new infos include:
  - `qc_toggle.dart:41` (curly_braces_in_flow_control_structures)
  - deprecated `containsSemantics` (x3) and `pipelineOwner` in `brain_quick_controls_test.dart:537-555`
  - `ember_transparency_test.dart:15`, from the Ember base
- **Fix:** Use `isSemantics` and `tester.binding.rootPipelineOwner`/SemanticsBinding, and add braces.

### R2-08 LOW: evidence and docs lag the new design (AC8)
- **No live run:** there is no live run of the d1388d8c three-toggle UI. A driver `docs/ui/uri_controls_3/live_harness/controls3_driver.dart` is untracked in the worktree, so it is in progress. Runtime behaviour of the new Assist toggle against a real worker is therefore unverified.
- **Report still describes the old design:** `UI_CONTROLS_TYPO_REPORT.md:16-35`, `:108-116` describe the Thinking Auto menu (`qc-thinking-menu`), the Context selection and Draft as the design. The only note about URI-CONTROLS-3 is the R1-02 correction (`:104`). There is no supersession note and no committed URI-CONTROLS-3 report or acceptance criteria.
- **Old drivers:** `qc_driver.dart`, `qc_driver_integration_instrumented.dart` (R1-07) and the controls_typography `ui_driver.dart` now target controls that no longer exist (`qc-context-*`, `qc-thinking-menu`). SUCCESSOR.md is not updated.
- **Fix:** Add a supersession header and a URI-CONTROLS-3 record, update SUCCESSOR.md, and commit the live run evidence.

### R2-09 INFO (owner decision): profiles no longer reachable from the UI
- **Standard, draft off (P3) cannot be selected any more.** It was reachable only via the removed Draft chip; the test now asserts Vision never targets `standard-nodraft`.
  - If the host runs P3 (as every ui-1/ui-2 live run did, `--profile 32768,gpu,0`), Vision Off goes to Long, and Vision On returns to Standard with MTP (about 1.2 GB more VRAM).
  - P3 is then reachable only through host/CLI configuration.
- **Context is no longer an independent choice.** 64K is reachable only as "Vision off" (Long). 32K without vision, and any future context size, have no UI.
- The tooltip and confirmation state the coupling, so this is truthful. It is still a capability reduction for the owner to accept.

### R2-10 INFO (owner decision): behaviour defaults
- Thinking now defaults to Off (fast) instead of Auto (`oi_conversation.dart:204`). Every user without a stored choice gets direct answers until they opt in.
- Auto is no longer offered by the quick control.
- Paused Assist shows as ON (glow plus "Paused"), and its click revokes rather than resumes.
- When the worker has exited, the Thinking tooltip says "can be changed once URI has restarted", which is acceptable.

### R2-11 INFO
- **No SemanticsAction.focus handler:** with `excludeSemantics: true` the Focus widget's semantics are dropped, so the toggle node has no focus handler. A screen reader moving its cursor does not move input focus; invoking uses `onTap` and works. The `focused` flag follows the keyboard highlight, not focus as such.
- **Redundant ternary from e9ee7409:** `companion_mode_view.dart:478` reads `referenceSize ? UriType.titleLarge : UriType.titleLarge`. The non-reference title was 16 and is now 17; harmless but redundant.
- **Test side-effect on a tracked file:** `.tmp_m26_render/rebuilt_dashboard.png` (tracked) shows as modified in the worktree after test runs, from the gate run or my focused runs. It is pre-existing hygiene, not part of the commit, and I left it untouched.

## Ember and Brain QC closure after the merge
- `git diff 68061d85 d1388d8c -- uri_ui/lib/living/companion/` is empty, and there is no pubspec change. In `companion_mode_view.dart` and `living_shell.dart` only typography tokens changed.
- The Brain QC closure behaviour is kept, by reading and tests:
  - Assist vision lock (`lockVision`, `ASSIST_NEEDS_VISION`)
  - host/worker mismatch
  - P3 restore test (`test_restore_to_standard_draft_off_after_the_closure`)
  - the closure tests in `brain_quick_controls_test.dart`
- Ember, companion and Assist widget tests pass (below).

## What I ran (COMPLETED_WITH_RESULT)
- `git rev-parse HEAD` gave d1388d8c…; `git log`, `git show d1388d8c`, `git diff --stat 68061d85 d1388d8c`, `git merge-base --is-ancestor ec2fab54 68061d85` (true).
- `flutter test --no-pub test/living/brain_quick_controls_test.dart test/living/ui_controls_typography_test.dart test/living/uiv2_postint_test.dart`: **+67, All tests passed, exit 0**.
- `flutter test --no-pub test/living/ember_companion_test.dart test/living/ember_transparency_test.dart test/living/companion_orb_test.dart test/living/assist_mode_test.dart test/living/assist_r41_poll_test.dart test/living/assist_r9_test.dart`: **+89, All tests passed**.
  - An earlier attempt that passed the directory `test/living/assist` failed only because that directory does not exist (a loading error, not a test failure).
- `pytest -q tests/oi/test_ui_controls_switch_fallback.py`: **14 passed**.
- `flutter analyze --no-pub` on the 6 changed Dart files: 5 infos, 0 warnings, 0 errors.
- A python check of ui-2 `observations.json`: 46 rows, 27 with `result`, of which 26 are PASS and 1 is REFUSED_DOES_NOT_FIT. This confirms 26/26.

## What I only read
- **Parallel gate logs** in `gates_d1388d8c/`, which I did not run myself:
  - head d1388d8c, dirty=0
  - frozen_check ok, rc=0
  - pytest tests/oi and tests/ws: 807 passed, 23 skipped, rc=0
  - analyze: 10 infos, rc=1, the same class as the earlier gate's 4 infos
  - flutter test: +874 ~5, All tests passed, rc=0
  - windows release build: rc=0
  - These are another process's logs; I read them but did not reproduce them.
- **Source I read:**
  - `qc_toggle.dart`, `brain_quick_controls.dart`, `assist_controller.dart`, `living_app.dart`, `living_composer.dart`, `oi_conversation.dart`, `oi_widgets.dart` (OiBrainBar)
  - `worker_bridge.py` (`_assist`, `assist_state_of`), `uri_assist/access.py`, `scripts/ws_brain_host.py` (R1-04, restore), `run_uri_integrated_worker.py:251`
  - the Flutter SDK `app.dart` shortcut maps
  - the R1 report, and UI_CONTROLS_TYPO_REPORT.md
  - one ui-2 screenshot

## Not verified
- **Live d1388d8c run** against the real worker and the Qwen3.6 Brain: no evidence exists. This matters for AC3 and AC5 runtime proof, but not for the defects above, which come from reading the code.
- **Real Narrator/UIA behaviour on Windows:** only the semantics tree in flutter_test was checked.
- **Empirical repro of R2-01 and R2-03:** both are derived from code paths (the TTL in `access.py`, the precedence at `brain_quick_controls.dart:414`; Flutter's `FocusNode.canRequestFocus` unfocus behaviour). I did not add scratch tests, to avoid contaminating the parallel full-suite gate. The conclusion is high-confidence, but there is no executed repro.

## Required to accept
Fix R2-01. Resolve R2-02 one of two ways: (a) make the Depth dropdown and the store/restore consistent, or (b) record an explicit owner decision to keep it. Then commit a live run of the three toggles (R2-08). The LOW findings may be fixed or carried.
