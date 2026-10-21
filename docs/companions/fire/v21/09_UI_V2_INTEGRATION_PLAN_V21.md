# Ember V2.1 final - UI V2 integration plan (Phase 5, prepared, NOT executed)

Status: **PLAN + REHEARSAL ONLY.** UI V2 is not independently qualified, so nothing has been merged into UI V2 and
no UI V2 branch was changed.
- **UI V2 candidate:** `316e6475`, recorded BLOCKED in
  `uri-ui-v2-final-qualification-20261013/FINAL_REPORT.md`.
- **Why it is blocked:**
  - the strict frozen-integrity check fails on canonical and on both candidates, and needs an owner decision;
  - its formal lifecycle ran 0 rounds;
  - native interaction and visual comparison were not qualified.
- **Rehearsal:** a throw-away merge in an isolated, detached worktree (`C:\uri-wt\ember-uiv2-rehearsal`). It was
  used only to measure what the real integration will need. It is evidence, not a candidate.

## 1. Read-only inspection of UI V2 `316e6475`

| Item | Finding | Effect on Ember |
|---|---|---|
| `CompanionIdentity` / gallery | `CompanionDesign.installed` lists every `CompanionIdentity.values`; the gallery and selector are generic. | Ember appears in the UI V2 gallery once the enum value is merged; no gallery code change. |
| Rendering path | `LivingShell` draws `LivingCompanion` (unchanged contract): scale = `presenceScale(id) * look.size * presentationScale`, then `SoftDisc`. | The same path as today's host, on a frameless transparent window (`setBackgroundColor(Colors.transparent)`, 440x680). Ember's own alpha is all that reaches the desktop. |
| `presentationScale` | 1.85 only for Solar in companion mode with `visualV2`; 1 for every other identity. | Ember keeps 1.19 x size. No Ember-specific change needed in UI V2. |
| Size preference | `CompanionLook.sizeMin/sizeMax` = 0.8 / 1.25 (unchanged). | **F-SIZE-1** (section 3). |
| Persistence | `CompanionPreferences` stores the choice by key; UI V2 adds `interfaceTheme` and `classicVariant` keys only. | Ember's key (`ember`) persists as any identity. |
| State signal | `LivingShell` passes `signal.state` and labels it with `signal.state.label`. UI V2's own state switches (`legacy_companion_mode_view.dart`, `companion_presence.dart`) all have a default branch. | `CompanionState.initializing` compiles in UI V2 without editing a UI V2 file. |
| Hit regions | `CompanionWindowLayout.orb` is a rectangle; native click-through is decided per region. | No change from Ember; click-through around the disc is a UI V2 gate (C-gates). |

## 2. Merge surface

- **Ember's diff against canonical `1b5423bc`:** 23 non-asset files under `uri_ui`, plus 12 asset files, the art and the docs (review R3-11: 19 was the count at `28149905`).
- **Overlap with UI V2's own diff:** 4 files:
  - `companion_preferences.dart`, auto-merged;
  - `companion_settings_section.dart`, auto-merged;
  - `pubspec.yaml`, auto-merged;
  - `test/ws/ws_integration_test.dart`, the **only textual conflict**: both sides add tests.

`git merge-tree --write-tree 316e6475 <ember>` reproduces this.

Integration candidate content (when the gates in section 5 open):
- only the Ember V2.1 final commits;
- their assets and the shared `initializing` state.

It does not include:
- V1/V2 Ember history docs beyond the qualification record;
- reviewer packs (`evidence/fidelity/<round>/`);
- reference artwork, unless OD-2 licensing allows it.

## 3. Findings for integration

- **F-SIZE-1 (open, owner/UI V2 decision).** At size 1.25 the host scales Ember 1.49x, and the disc fades and cuts
  the feet and the flame tip.
  - Share of Ember's alpha cut at 1.25 (`evidence/final/size_crop.json`, `size_crop.jpg`):
    - idle and most clips: visible 85.7 %, 6.5 % cut;
    - joyful: 2.8 % cut;
    - depleted: 2.9 % cut.
  - At sizes 0.8 and 1.0 the cut is at most 0.3 %.
  - Ember cannot fix this alone: the scale is the host's.
  - Options:
    - (a) cap the effective scale for painted "model" companions in `LivingCompanion` (a UI V2 shared file);
    - (b) let the disc grow with the size for model companions;
    - (c) accept the crop at 1.25.
  - **Recommendation:** (a), as a one-line host rule decided inside UI V2's process.
- **F-START-GAP (open, launcher, pre-existing order).** `launch_uri_working_system.ps1` starts the UI, waits for its
  window, and only then starts the Brain host.
  - Until the host writes its first report, the runtime reads `STOPPED` with no host, which is truthfully
    `unavailable` (depleted).
  - The mapping is designed to show `initializing` once a running host reports `STARTING_HOST`, `STARTING`, `LOADING`, `CALIBRATING` or `WAITING_FOR_LEASE`. The live run did not demonstrate the host-only path: Initializing first appeared once the runtime read `LOADING`, about 12-13 s after our host process started (R5-N5, R6-1).
  - The final live run at `d12e70ed` recorded how long each look lasted, as timed state sequences (`FINAL_REPORT_V21_FINAL.md`, section 6).
  - Closing it fully needs the launcher to announce the host before the UI starts. That is a shared launcher
    change, and is not made here.

## 4. Gates before a real integration candidate is cut

1. UI V2 independently qualified at an exact SHA, including its frozen-integrity owner decision.
2. Owner approval of the FP-21R fidelity criteria, or another owner fidelity decision.
3. OD-2 licensing of the reference art and the derived atlases.
4. Owner decision on F-SIZE-1.
5. An exact-final-commit, driver-counted independent acceptance of Ember. Today the Codex sandbox refuses every
   command and the Claude CLI is logged out: BLOCKED.

Then:
- cut `integration/ember-v21-ui-v2-<date>` from the accepted UI V2 SHA, in its own worktree;
- merge the Ember final commit and resolve `ws_integration_test.dart` by keeping both sides' tests;
- update UI V2's pinned design count in `ui_v2_test.dart` (11 -> 12), inside UI V2's process;
- run the combined suite, the transparency test and the UI V2 suite;
- run the Stage 2 live list (C1-C10 and the owner's journeys 1-15) on the real Windows app, Core and Brain under
  the GPU lease;
- get independent acceptance of the exact integration SHA;
- obtain the owner integration approval. Production cutover is a separate approval.

## 5. Rehearsal record (evidence only; never a candidate)

- **Worktree.** `C:\uri-wt\ember-uiv2-rehearsal`, detached at UI V2 `316e6475`.
  - No branch was created and nothing was pushed.
  - No UI V2 branch or worktree was touched.
- **Merge.** The Ember final commit `7baefb17` was merged, giving rehearsal commit `73aa3bd2`.
  - There was one conflict, in `test/ws/ws_integration_test.dart`.
  - It was resolved by keeping UI V2's formatted approval test plus Ember's new tests, and dropping Ember's duplicate
    of that approval test.
- **`flutter pub get`:** OK. No new dependency; `pubspec.yaml` auto-merged the Ember asset folder.
- **`flutter analyze lib test tool`:** 0 errors, 4 info notices (`evidence/final/rehearsal/analyze.log`).
- **Full suite:** 630 passed, 5 skipped, 1 failed (`evidence/final/rehearsal/full_flutter_test.log`).
  - The failure is `ui_v2_test.dart` "every accepted design is represented once". It pins
    `CompanionDesign.installed.length` to 11, and Ember makes it 12.
  - This is an expected integration edit to a UI V2 test, to be made inside UI V2's process.
  - The rehearsal-only commit `67bce88b` changes 11 to 12; `ui_v2_test.dart` then passes 32/32.
- **Initializing in UI V2.** Every UI V2 state switch has a default branch, so `CompanionState.initializing` compiles
  and renders with no UI V2 file change. The companion label reads "URI Companion: Initializing".
- **Cosmetic (for the integration).** `CompanionDesign.rendererReference` reports Ember's placeholder
  `shaders/companion_ember.unused`.
  - It is not displayed anywhere in `lib/` today.
  - If the gallery ever shows it, it should name Ember's atlas instead.
- **Not done in the rehearsal:**
  - a native UI V2 window run;
  - live Core and Brain;
  - drag, click-through and DPI checks.

  These are Stage 2 live gates, and they wait for an accepted UI V2.
