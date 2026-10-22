# UI-CONTROLS-TYPO-20261018 - acceptance criteria (written before implementation)

Milestone: URI UI - Interactive Controls & Typography Refinement. Branch `milestone/ui-controls-typography-20261018`,
cut from canonical `feaabe3f` (Brain Quick Controls integrated). Written 2026-10-18 17:05 IST, before any code change.
Only `COMPLETED_WITH_RESULT` evidence may mark a criterion MET.

## A. Push-to-enable controls

| ID | Criterion | Evidence required |
|----|-----------|-------------------|
| A1 | Thinking, Vision and every other applicable on/off Brain control is a toggle button: one click enables, a second click disables. | widget tests (tap -> state), live UI run |
| A2 | Context (mutually exclusive sizes) is a selection (segmented), not independent toggles. | widget test, screenshot |
| A3 | Enabled controls show a visible, theme-coloured glow; disabled controls are subdued. | widget test on decoration, screenshots in >= 2 themes |
| A4 | Hover, pressed, loading, enabled, disabled and error states are visually distinct. | widget tests per state (decoration / semantics), screenshots |
| A5 | Glow is static (no looping animation), one shadow per enabled control; no shader, no repaint loop. | code review + widget test that no ticker runs when idle |
| A6 | Controls reflect verified runtime state: Vision/Context glow/selection only from `controls.active` (worker-verified). A toggle press never changes the shown state before the worker confirms. | widget tests (press -> confirm -> still old state until health says active) |
| A7 | Reload controls: a confirmation states what changes (including the coupled change: Vision off => 64K, Vision on => 32K, 64K + vision unavailable with reason); a switching indicator is shown; the glow appears only after activation. | widget tests, live run |
| A8 | Conversation and task state preserved across a switch. | existing worker tests + live run (conversation still present after switch) |
| A9 | A failed switch start restores the previous, known-good profile automatically (host side), recorded truthfully in `profile_switch` and shown in the UI; if the restore also fails the result is a truthful FAILED. Never stops another holder; lease-respecting; default (no-switch) path unchanged. | pytest: fallback success, fallback failing, stop during switch, restart during switch, no fallback when not applicable |
| A10 | Thinking semantics decided and justified (per message, no reload). | report section + widget test |
| A11 | Draft (parallel branch) / vision lock / mismatch can drop into the same components later. | report: merge points; generic widget API |

## B. Typography

| ID | Criterion | Evidence |
|----|-----------|----------|
| B1 | One UI font family for the whole application (no serif/brand exceptions), monospace only for code. | grep before/after counts |
| B2 | The theme's TextTheme carries the family explicitly on every role (no silent engine fallback). | unit test on `buildUriTheme` |
| B3 | One type scale (named tokens); off-scale sizes removed; distinct fontSize literals reduced. | grep before/after counts |
| B4 | Applied to Dashboard, Workspace, Companion, Assist, chat + input, settings + quick controls, dialogs, notifications/tooltips/status, onboarding/diagnostics. | screenshots of each surface |
| B5 | No new font dependency (no package, no bundled font file). | pubspec diff |

## C. Visual quality

| ID | Criterion | Evidence |
|----|-----------|----------|
| C1 | Brain switch confirmation dialog: clear hierarchy, readable width, consistent spacing, standard typography, distinct primary/secondary actions; theme kept. | before (REFERENCE) / after screenshot |

## D. Non-regression and gates

| ID | Criterion | Evidence |
|----|-----------|----------|
| D1 | `pytest tests/oi tests/ws` pass on the final commit. | log with HEAD |
| D2 | Full `flutter test` pass; `flutter analyze` 0 errors. | logs with HEAD |
| D3 | Windows release build succeeds. | log with HEAD |
| D4 | `scripts/ws_frozen_check.py` passes (no protected path changed). | log with HEAD |
| D5 | UI V2 journeys regression passes on the final code (live, real Brain). | harness summary |
| D6 | Live Windows run: toggles glow only after activation, switching indicator, conversation kept, one live round trip. | harness summary + screenshots |
| D7 | No meaningful GPU/CPU/memory regression (static glow, no new animation, no new font). | code review + frame stats if available |

## Out of scope / owner gates

* No integration into canonical, no push, no tag.
* Frozen paths (ws_frozen_check PROTECTED, Runtime v1 frozen config, runtime_profiles.py / runtime_profile_selection.py /
  runtime_v1.py) are not modified.
