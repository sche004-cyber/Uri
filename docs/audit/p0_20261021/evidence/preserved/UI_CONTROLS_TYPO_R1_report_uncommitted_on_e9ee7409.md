# UI-CONTROLS-TYPO-20261018 - Independent review R1 (read-only)

**Verdict: ACCEPT WITH FINDINGS.** No HIGH findings. Fix R1-01 (MEDIUM) and correct R1-02 (the live count) before integration.

## Acceptance criteria used by this review
- AC1. The host restore holds the lease, stops only its own server, makes one attempt, gives way to a newer request, a stop or an exit, restores only a qualified profile that was running, keeps the selection file and the lease VRAM in step, and writes truthful records. The path with no switch is unchanged. Tests cover success, a failed restore, and a stop during the restore.
- AC2. Every glow and current-state display comes from the worker-verified `controls.active`. Loading and error states are truthful. Draft, the vision lock and the mismatch line survived the merge. Thinking is a push toggle and Auto (the default) is reachable from the caret menu.
- AC3. The dialog wording matches what the host actually does.
- AC4. One font family and one size scale. The exceptions really are frozen or protected. The guard test means something. Protected files are untouched.
- AC5. The gates and live evidence are at 22b53b78 and the counts match the raw records.
- AC6. The findings and limitations are disclosed honestly.

## Repo state (RAN)
- HEAD is e9ee7409 on milestone/ui-controls-typography-20261018.
- `git diff 22b53b78 e9ee7409 -- . ':!docs'` is empty. ec2fab54 is an ancestor.
- One untracked file is present: REFERENCE_confirm_dialog_before.png.

## Tests run by me
- pytest on test_brain_quick_controls.py, test_brain_qc_integration.py and test_ui_controls_switch_fallback.py: **61 passed**, exit 0.
- `flutter test --no-pub` on brain_quick_controls_test.dart, ui_controls_typography_test.dart and four_theme_persistence_test.dart: **47 passed**, exit 0.
- `scripts/ws_frozen_check.py` at HEAD: `unapproved_protected_changes: []`.
- Not run: the full suites, analyze, the build, or anything live. For those I checked the logs only (see below).

## Findings

### R1-01 MEDIUM: the new toggles and segments cannot be reached by keyboard or screen reader
- **Where:** `uri_ui/lib/living/integration/qc_toggle.dart:111-140` (QcToggle) and `:269-289` (QcSegment).
- **Problem:** Activation is a bare `GestureDetector` inside `Semantics(button: true, excludeSemantics: true)`. There is no Focus, InkWell, FocusableActionDetector or Shortcuts.
  - At ec2fab54 these controls were `PopupMenuButton`s, which can be focused and activated from the keyboard (brain_quick_controls.dart:477 at ec2fab54).
- **Failure scenario:**
  - Keyboard: Tab skips Vision, Context and Draft. Enter or Space cannot switch them.
  - Screen reader (Narrator): announces a "button" with no tap action, because `excludeSemantics` drops the GestureDetector's semantic tap.
  - Only the Thinking caret (still a PopupMenuButton) stays keyboard-operable.
  - Net effect: Brain controls that used to be keyboard-operable no longer are. This is a regression against "enhancement, not redesign". It is not disclosed in the report.
- **Fix:**
  - Use `InkWell` / `FocusableActionDetector` with ActivateIntent, plus a visible focus ring as another distinguishable state.
  - Or pass `onTap` to the outer `Semantics`.
  - Add a widget test that tabs to `qc-vision`, presses Enter, and expects the confirmation dialog.
- **Basis:** read only (not run). High confidence.

### R1-02 LOW (evidence integrity): "ui-2 30/30 PASS" is not what the raw records show
- **Where:** `UI_CONTROLS_TYPO_REPORT.md:104` and `:157`. Compare `evidence/live/ui-2/observations.json`.
- **What the record shows:**
  - It holds **26** `check` entries, all PASS, with `final.failures = []`. ui-finished.json reports `failures: []`.
  - No summary file in ui-2 contains a 30.
  - The driver (`ui_driver.dart`, sha 0392ac3f..., matching native-execution.json) defines more check ids than were recorded. Some are conditional, for example the Draft checks were skipped.
- **Impact:** The run is still a pass. The stated count, however, is not backed by the evidence.
- **Fix:** State 26/26 and list the conditional checks that did not run.
- uiv2-1 is correct: 68 PASS, with the same duplicate `J2-ctrl-dashboard` id as the canonical qcc-uiv2 and uiv2-main runs.

### R1-03 LOW (truthfulness, partly disclosed in F-2): after the 600 s gate, a restore still running is shown as failed
- **Where:**
  - `worker_bridge.py:240` (`RESTART_GATE_S = 600`)
  - `brain_quick_controls.dart` `_notice` FAILED branch (~lines 475-495)
  - `errorLook`
- **Failure scenario:**
  1. The first start fails late (READY_TIMEOUT, around 300 s).
  2. The restore then waits for GPU memory or loads slowly, so the total passes 600 s.
  3. The worker gate expires: `_switch` becomes None and `pending` becomes false.
  4. `switch.last` still has `fallback.result == IN_PROGRESS` and `restored == false`.
  5. `_notice` falls through to "...and going back to X failed too. Use Restart Brain." in the error tone, and Vision and Context show the error look.
  6. Meanwhile the host is still restoring. Turns are also allowed while no Brain is ready.
- **Disclosure gap:** F-2 discloses that the gate opens. It does not disclose the false "failed too" notice or the error look.
- **Fix:**
  - In `_notice`, treat `fb.result` IN_PROGRESS or WAITING_* as "still going back" (warning tone).
  - In the worker, keep the gate closed while the host's `profile_switch.fallback.result == IN_PROGRESS`.

### R1-04 LOW: a superseded restore leaves no record
- **Where:** `scripts/ws_brain_host.py:463-469` (`apply_pending_profile` builds a new dict because the old record's result is FAILED) together with `:565-576`.
- **Problem:**
  - A reconfigure taken inside the restore's GPU wait replaces `report["profile_switch"]`.
  - The old record, holding `fallback.result = "SUPERSEDED"`, is changed only in memory and never written.
  - The new record says `from = <restored profile>`, although that profile never ran.
  - The docstring and report claim "a newer reconfigure request supersedes the restore". That behaviour is real, but the SUPERSEDED record is never persisted, and no test covers this path. All 12 fallback tests cover the other paths.
- **Likelihood:** The worker refuses its own reconfigure while the gate is pending, so this needs another writer or a gate expiry.
- **Fix:**
  - Copy the superseded fallback into the new record (for example `superseded: {id, fallback}`), or keep the history.
  - Add a test.

### R1-05 LOW (doc accuracy): `reference_dashboard.dart` is not frozen or protected
- **Where:**
  - `typo_migrate.py` SKIP comment
  - `ui_controls_typography_test.dart` exempt comment
  - report §1.4
  - `UIdevelopment.md:36`
- **What I checked:**
  - `settings_shell.dart` is in ws_frozen_check PROTECTED. That is correct.
  - `reference_dashboard.dart` is **not** in PROTECTED, and I found no freeze record naming it.
- **Mislabelled quote:** The quoted "never hand-edit" is in `dashboard_manifest.dart` and refers to keeping the manifest in sync with the HTML/JSON pair. That same manifest says no literal should be re-typed in reference_dashboard.dart, and that file still has 17 numeric fontSizes (pre-existing).
- **Assessment:** Exempting it is defensible on scope grounds (a board-unit-scaled classic surface), but calling it "frozen" is inaccurate.
- **Fix:** Reword the exemption as an explicit scope exclusion, or migrate it to manifest tokens.

### R1-06 LOW (dialog wording): the "no fit after the stop" case is not mentioned
- **Where:** QcSwitchDialog, the shield fact (`running` branch).
- **Problem:**
  - The dialog says: refused before the switch if it does not fit, and back to the current setting if the new one fails to start.
  - Not said: if GPU memory is taken between the pre-check and the new start, the host waits (WAITING_FOR_GPU). It does not restore. The current Brain is already stopped.
- **What is accurate:** The rest of the wording matches the host. It promises a restore only when `active.qualified` is set and the host is not STOPPED, which matches `prev_cfg` (mgr running and `_restorable`). DEGRADED new profiles are kept, and the dialog does not claim otherwise.
- **Fix:** Add one clause: "if memory is taken meanwhile, URI waits and says so."

### R1-07 INFO: the ember integration driver no longer works with the toggles
- **Where:** `docs/integration/qc_ember_20261018/evidence/qc_driver_integration_instrumented.dart:187-228`.
- **Problem:** Like `qc_driver.dart` (F-5), it relies on the old chip text ("Vision: On", "(not running)") and on the context menu tap. F-5 and SUCCESSOR.md mention only qc_driver.dart.
- **Fix:** Add a line to SUCCESSOR.md and F-5.

### R1-08 INFO: the typography guard is literal-only
- **Where:** `ui_controls_typography_test.dart` (`fontSize:\s*\d`).
- **Gap:** Computed sizes such as `oi_markdown.dart:202` `(base.fontSize ?? bodyLarge) - 1` pass the guard and can drift off the scale.
- **Assessment:** The guard is otherwise meaningful. It checks 15 roles × 4 palettes for family and scale, and catches family literals and Georgia.

## Point-by-point (AC1-AC6)

### 1. Host restore (READ; tests RAN): MET apart from R1-04
- **Lease:** The restore runs only when `self.lease is not None`. The lease is never released between the failed start and the restore, and `lease.heartbeat(expected_vram_mib)` follows the restored config.
- **Only its own server:**
  - Before the switch, attached instances are refused (`REFUSED_ATTACHED_INSTANCE`).
  - The failed start's `mgr.stop()` is the host's own RuntimeManager.
  - No other process is stopped. `wait_for_gpu` only waits.
- **One attempt:** It is called once from `reconfigure()` and is not recursive.
- **Stop or exit:** `stop_requested` / `should_exit` are checked before the restore and after it (result STOPPED). This is tested by test_stop_during_the_restore and test_stop_during_the_switch_load.
- **Qualified previous profile only:** It must have been running (`mgr is not None`) and be a qualified catalog entry. Tests cover both no-restore cases (a Brain that was stopped, and research P1).
- **Selection file:** `sync_selection()` runs after `self.cfg = prev_cfg`. The frozen config removes the file, and long writes it back (tested).
- **Records:**
  - The switch result stays FAILED, with a fallback block `{to, label, result, after, t_start, t_done, seconds}`.
  - `restored` is true only for READY or DEGRADED.
- **Path with no switch:** `start_brain` / `_start_brain` / `run` are unchanged. Only `reconfigure()` gains two lines plus the new methods.
- **Worker:**
  - The gate stays closed until the host's DONE, which comes after `reconfigure()` returns, so after the restore.
  - The explanation is specific to the restore.

### 2. Glow truthfulness (READ; tests RAN): MET
- **Glow source:**
  - Vision and Draft glow, and the selected Context segment, come only from `controls.active`. That is `QC.controls` and `describe_key(ckey) if serving`, which the worker sets only after its own verification.
  - While a switch is pending they show loading with no glow. The error look appears only when no Brain is verified and the outcome is an error.
- **Merge:**
  - Draft is shown only when `draftChoices` finds a qualified pair at the active ctx/vision (Standard / Standard draft off).
  - `lockVision` disables vision-off choices while `vision_locked` is set.
  - The refusals ASSIST_NEEDS_VISION, ASSIST_ASK_IN_PROGRESS and BRAIN_RESTARTING are mapped (oi_conversation.dart:33-53).
  - The `qc-mismatch` line is kept and hidden while pending.
  - Keys qc-draft, qc-vision, qc-context and qc-mismatch are kept.
  - P1 is shown disabled with its reason. P2 is offered.
- **Thinking:** A click goes On to Off and back. Auto (the default) shows as subdued "Thinking · Auto" and can be chosen only from the caret menu. This matches the brief and the report's justification.
- **Live:** ui-2 "glow honest" checks passed for the restore, long and vision-on timelines. The final controls JSON shows `active = long` and `mismatch = null`.

### 3. Dialog (READ): accurate, apart from the omission in R1-06

### 4. Typography (READ + guard test RAN)
- Theme:
  - `UriType` family is Segoe UI and mono is Consolas, both Windows system fonts.
  - pubspec is unchanged and no font package was added.
  - The 15 TextTheme roles carry the family.
- `typo_migrate.py` snapping:
  - The map is explicit and consistent: half steps round up, others go to the nearest step, ties go up.
  - In ec2fab54, the only small sizes outside the exceptions were 9 and 9.5, both snapped to 10.
- Protected files are untouched (frozen check ok). Ember companion files are untouched. `oi_conversation.dart` is unchanged by this milestone.
- The exception claim needs correcting: see R1-05.

### 5. Evidence (READ)
- **Gates at 22b53b78**, from logs headed with HEAD 22b53b78 and an empty porcelain status:
  - pytest 805 passed, 23 skipped
  - flutter 799 passed (5 skipped)
  - analyze: 4 infos, all in files this milestone did not touch, and 0 errors
  - Windows release build OK
  - frozen check exit 0
- **Live runs:**
  - native-execution.json for both ui-2 and uiv2-1 shows source_head 22b53b78, tree 429e221d, clean status before and after.
  - The runtime Python was materialized from a4935c2b. `git diff a4935c2b 22b53b78 -- '*.py'` is empty.
  - The P3 start is recorded in `host_argv` (`--profile 32768,gpu,0`). `override` is false and the lease-free time is recorded.
  - The Brain config sha 112c0595... is the same before and after in both runs.
  - uiv2-1 is 68/68 PASS. ui-2 is 26/26 (see R1-02).
  - The canonical driver is unchanged: no diff under `uri_ui/integration_test`.
  - The `draft-close` hit-test warning in uiv2-1 also appears in the canonical runs, so it is pre-existing.
- **Harness:**
  - `inject_host.py` is harness-only: nothing outside docs references it or `INJECTED_START_FAILURE`.
  - It fails before the spawn, after `wait_for_gpu`.
- **Screenshots:** 01-11 and 20-26 exist in ui-2, plus the uiv2-1 set. I checked that they exist; I did not judge them visually.

### 6. Findings F-1..F-5 and D7
- These are honest and match the code. F-1 is a real product limitation and is correctly classed as an owner decision.
- D7 PARTIAL is honest: no frame-time or memory measurement was taken. The glow is one static BoxShadow and the 140 ms AnimatedContainer runs only on a change. The loading spinner animates only while a switch is pending.
- Undisclosed: R1-01, R1-02's count, R1-03's false notice, R1-04, R1-05's mislabel and R1-07.

## Not verified (none of these changes the verdict)
- Pixel-level visual quality and glow strength: screenshots were not reviewed visually.
- Light themes live.
- A physical keyboard or mouse. The R1-01 conclusion comes from reading the code, not from a run.
- Windows 10.
- A real llama-server crash during load (F-4).
