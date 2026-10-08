# UI test evidence

Branch `phase/ui-living-companion`, worktree `C:\Users\cheta\Development\uri-ui-phase`, baseline `037229c`. Evidence integrity per root `CLAUDE.md`: only `COMPLETED_WITH_RESULT` outcomes below support a positive claim; everything else is labelled.

Commits in this phase (newest last):

| Commit | Content |
|---|---|
| `a0615b6` | first implementation (orb, controller, shell, views, 47 tests) |
| `d0a3751` | polish, docs, screenshots, evidence tooling; Codex round 1 reviewed this |
| `4544f33` | Codex round-1 repairs, six orb variants, cursor gust, click response; 69 living tests |
| (next) | this evidence file + perf logs + Codex round 2 record |

## 1. Static analysis

`flutter analyze` at `4544f33`: 2 issues, both pre-existing in the baseline and outside this phase (`lib/screens/settings/providers_screen.dart:730` deprecated `value`; `test/chat_supervised_handoff_test.dart:5` unnecessary import). 0 errors, 0 warnings in `lib/living/**`, `lib/theme/glass_theme.dart`, `lib/main_living.dart`, `test/living/**`.

## 2. Automated tests

| Run | Command | Result | Status |
|---|---|---|---|
| Baseline before any change | `flutter test` (uri_ui) | `+205 ~2: All tests passed!` | COMPLETED_WITH_RESULT |
| Living suite at `4544f33` | `flutter test test/living` | `+69: All tests passed!` | COMPLETED_WITH_RESULT |
| Full suite at `4544f33` | `flutter test` | `+274 ~2: All tests passed!` (205 baseline + 69 living; the 2 skips are pre-existing live-runtime tests) | COMPLETED_WITH_RESULT |

Living tests by file (69):

| File | Count | What it proves (acceptance criterion) |
|---|---|---|
| `presentation_controller_test.dart` | 6 | A3: parser grammar incl. non-hijack cases; cooldown; Back; sealed vocabulary |
| `energy_orb_test.dart` | 30 | A1: every state renders with effects on and off; **pixel-difference test**: every pair of the nine states differs in >1% of pixels, with and without effects; every variant renders every state; tween keeps the element; poke; theme tokens |
| `companion_sources_test.dart` | 6 | A12/section-3 contract: `SupervisedCompanionSource` mapping with a fake runtime that throws on begin/decide/cancel (observe-only proven); `AppStateCompanionSource` unavailable/approval-with-proposal/success-with-result |
| `work_simulator_test.dart` | 3 | A4: lifecycle, structured approval only, cancel |
| `intelligence_snapshot_test.dart` | 2 | A7: idle snapshot claims nothing; working does not imply a decision; route never inferred |
| `onboarding_test.dart` | 2 | A6: all eight steps, honesty badges, real preference writes under `uri.living.prefs.*`, skip/back |
| `living_shell_test.dart` | 20 | A2 (orb element identity across all forms), A3 (typed command, Back), A4 (office workflow + every region), A5 (a Simulated badge inside each of the 8 dashboard tiles), A7, A8 (default wiring offline), A9 (no `BackdropFilter`, no shader under reduced effects; dashboard never blurs), A11 (only `uri.living.*` keys written), click/double-click/gust/keyboard, 440x680 and 1920x1080 layouts, Hybrid themes |

## 3. Real-build evidence (Windows release, Impeller)

`flutter build windows -t lib/main_living.dart` (release) at `4544f33`: built; the log shows `Using the Impeller rendering backend (OpenGLESSDF)` on launch, so the runtime shader path is the one exercised. 24 screenshots captured by `docs/ui_phase/tools/capture_screenshots.ps1` (PrintWindow of the client area; no other windows): `docs/ui_phase/screenshots/01..13_*.png` (forms, states, onboarding, reduced effects, narrow) and `orb_*.png` (six variants, five states), plus `orb_variants_sheet.png`.

Visual self-review (Claude, from the screenshots): the three forms read as one space; the orb is recognizable at 72 px (rail), 128 px (dashboard) and 180-320 px (companion); every mock region shows the Simulated badge; no overflow at 440x680 or 884x661; the shader core renders (plasma visible in `orb_nebula_idle.png`), the gradient fallback renders in `12_companion_reduced_fx.png`.

## 4. Performance (profile build, `flutter run --profile`, `URI_LIVING_PERF=1`, 5-second windows)

Sampler: `lib/living/perf_logger.dart`; script: `docs/ui_phase/tools/perf_sample.sh`; logs: `docs/ui_phase/perf/*.log`. Machine: this development PC (Windows 11, Impeller OpenGLES backend); numbers are specific to it.

Run 1 (commit `d0a3751`, before the blur change):

| Scenario | Frames / 5 s | build p50 / p95 | raster p50 / p95 | total p95 | frames > 16.7 ms |
|---|---|---|---|---|---|
| companion idle (nebula) | not captured (the first scenario's compile ate the sampling window; fixed by `SAMPLE_SECONDS` in run 2) | | | | |
| companion working | ~718 | 0.22 / 0.36 ms | 2.8 / 9.5 ms | 10.9 ms | 0-6 |
| companion reduced effects | ~715 | 0.26 / 0.45 ms | 2.4 / 5.1 ms | 6.5 ms | 0-4 |
| dashboard (8 blurred tiles) | ~580 | 0.23 / 0.39 ms | **5.4 / 22.6 ms** | **24.9 ms** | **~154 of 580** |

Finding PERF-1: the dashboard janked because every tile used a `BackdropFilter`; with the orb ticking at 60 fps each frame re-blurred eight backdrops. Fix in `4544f33`: `GlassPanel.blur` defaults to false and only the composer opts in.

Run 2 (commit `4544f33`): see the table below, filled from `docs/ui_phase/perf/` when the run completes.

PERF_RUN2_TABLE

## 5. Accessibility checks

* Contrast (computed, WCAG 2.x formula, `UI_DESIGN_REFERENCE.md` section 2): ink 16.9:1, inkSoft 8.9:1, inkFaint 5.2:1 on canvas; 4.5:1 on surfaceSunken; accent 10.8:1; canvas-on-accent button text 10.8:1; canvas-on-warning 10.5:1. All AA for normal text. (inkFaint was raised from `#5F6F80` = 3.8:1 after this check.)
* Semantics: the orb exposes `URI companion: <state>` as a live region; every pipeline stage exposes `<stage>: <state>`; badges expose `Status: <label>`; buttons have tooltips or text.
* Reduced motion: honoured from the OS `disableAnimations` flag at startup and from the Settings switch; the orb then renders a still frame and `pumpAndSettle` terminates (test-proven). Reduced effects: no shader, no blur, no blurred masks (test-proven).
* Keyboard: Esc / Ctrl+1 / Ctrl+2 / Ctrl+3 switch forms; Enter sends; the composer takes focus on an orb click (test-proven).
* Not done: screen-reader run on Windows (Narrator) and a colour-blindness simulation of the three state tints (amber/green/red are also distinguished by ring, bloom and streak shapes, by design, but this was not verified with a simulator).

## 6. Independent review (Codex, read-only sandbox, `gpt-6-sol`)

| Round | Commit | Verdict | Findings | Disposition |
|---|---|---|---|---|
| 1 | `d0a3751` | REJECTED | B1 shared Hybrid prefs written; B2 section-3 contract not enforced; M3 inferred pipeline facts; M4 missing Simulated badges; M5 weak tests for A1/A4-A9; M6 evidence file absent; N7 boundary and command path OK | all repaired in `4544f33` (see commit message) |
| 2 | `4544f33` | CODEX_ROUND2_VERDICT | CODEX_ROUND2_FINDINGS | CODEX_ROUND2_DISPOSITION |

Codex's model config: the account's configured `gpt-6.1-sol` is refused for ChatGPT accounts in this session; `gpt-6-sol` worked. Codex output is a claim, not verification; the items above were checked against the code before being recorded as repaired.

## 7. Isolation re-check at `4544f33`

```
git diff --stat 037229c -- . ':!uri_ui/lib/living' ':!docs/ui_phase' ':!uri_ui/test/living' \
  ':!uri_ui/shaders' ':!uri_ui/lib/main_living.dart' ':!uri_ui/lib/theme/glass_theme.dart' \
  ':!docs/design_library/approved/living_companion_2026-10-08.md'
```

-> `uri_ui/lib/theme/uri_theme.dart | 44 ++` and `uri_ui/pubspec.yaml | 5 +` only (both additive). `uri_core/`, `uri_supervisor*/`, `scripts/`, `model_lab/`, `tests/`: unchanged. Other worktrees' HEADs unchanged (`_V1` 62d564c, `uri-agent` e8e3b65, consolidation clone 037229c); shared refs unchanged (`integration/git-sync-20261008` f8de153 local, `uri-repo/...` f8de153, `master` e8e3b65).

## 8. Not verified / limits

* GPU-less or remote-desktop rendering of the shader (fallback is tested in widget tests only).
* The physical mouse gust feel: tested for exceptions and determinism, judged visually in a live run by Claude only.
* `SupervisedCompanionSource` against the real worker: fake runtime only (no worker in the preview; see `UI_INTEGRATION_PLAN.md` I3).
* Any user acceptance: none yet.
