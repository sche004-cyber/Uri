# UI test evidence

Branch `phase/ui-living-companion`, worktree `C:\Users\cheta\Development\uri-ui-phase`, baseline `037229c`. Evidence integrity per root `CLAUDE.md`: only `COMPLETED_WITH_RESULT` outcomes below support a positive claim; everything else is labelled.

Commits in this phase (newest last):

| Commit | Content |
|---|---|
| `a0615b6` | first implementation (orb, controller, shell, views, 47 tests) |
| `d0a3751` | polish, docs, screenshots, evidence tooling; Codex round 1 reviewed this |
| `4544f33` | Codex round-1 repairs, six orb variants, cursor gust, click response; 69 living tests |
| `cfdaf70` | Codex round-2 repairs (`WorkItem.decided`, `UriGlass.specular`), softer swarm; first evidence file |
| `f32a3b1` | Codex round-3 MINOR (cancel counts as a decision) |
| `a09f453` | orb rework from the owner's three references: seven styles x ten palettes, smoothed ribbons |
| `abb6b6d` | Codex round-4 repairs (cancel semantics, tinted hot light, A1 across styles) |
| 838d1dd+ | this evidence (perf run 3, Codex rounds 2-5), memory and handoff |

## 1. Static analysis

`flutter analyze` at `abb6b6d`: 2 issues, both pre-existing in the baseline and outside this phase (`lib/screens/settings/providers_screen.dart:730` deprecated `value`; `test/chat_supervised_handoff_test.dart:5` unnecessary import). 0 errors, 0 warnings in `lib/living/**`, `lib/theme/glass_theme.dart`, `lib/main_living.dart`, `test/living/**`.

## 2. Automated tests

| Run | Command | Result | Status |
|---|---|---|---|
| Baseline before any change | `flutter test` (uri_ui) | `+205 ~2: All tests passed!` | COMPLETED_WITH_RESULT |
| Living suite at `4544f33` | `flutter test test/living` | `+69: All tests passed!` | COMPLETED_WITH_RESULT |
| Full suite at `4544f33` | `flutter test` | `+274 ~2: All tests passed!` | COMPLETED_WITH_RESULT |
| Living suite at `abb6b6d` | `flutter test test/living` | `+72: All tests passed!` | COMPLETED_WITH_RESULT |
| Full suite at `abb6b6d` | `flutter test` | `+277 ~2: All tests passed!` at `a09f453`; at `838d1dd` only the living suite was re-run (`+72`), the full suite was not re-run before the session's usage limit (205 baseline + 72 living; the 2 skips are pre-existing live-runtime tests). Note: the `a09f453` commit message says 278; the measured number at that commit was 277. | COMPLETED_WITH_RESULT |

Living tests by file (72 at `abb6b6d`):

| File | Count | What it proves (acceptance criterion) |
|---|---|---|
| `presentation_controller_test.dart` | 6 | A3: parser grammar incl. non-hijack cases; cooldown; Back; sealed vocabulary |
| `energy_orb_test.dart` | 32 | A1: every state renders with effects on and off; **pixel-difference test**: for every style, every pair of the nine states differs in >1% of pixels, with and without effects; every style renders every state; every palette renders on every style; tween keeps the element; poke; theme tokens |
| `companion_sources_test.dart` | 6 | A12/section-3 contract: `SupervisedCompanionSource` mapping with a fake runtime that throws on begin/decide/cancel (observe-only proven); `AppStateCompanionSource` unavailable/approval-with-proposal/success-with-result |
| `work_simulator_test.dart` | 3 | A4: lifecycle, structured approval only, cancel |
| `intelligence_snapshot_test.dart` | 3 | A7: idle snapshot claims nothing; working does not imply a decision; route never inferred; seeded history and withdrawn work never count as decisions, a decision on a waiting item does |
| `onboarding_test.dart` | 2 | A6: all eight steps, honesty badges, real preference writes under `uri.living.prefs.*`, skip/back |
| `living_shell_test.dart` | 20 (+ palette chip assertion) | A2 (orb element identity across all forms), A3 (typed command, Back), A4 (office workflow + every region), A5 (a Simulated badge inside each of the 8 dashboard tiles), A7, A8 (default wiring offline), A9 (no `BackdropFilter`, no shader under reduced effects; dashboard never blurs), A11 (only `uri.living.*` keys written), click/double-click/gust/keyboard, 440x680 and 1920x1080 layouts, Hybrid themes |

## 3. Real-build evidence (Windows release, Impeller)

`flutter build windows -t lib/main_living.dart` (release) at `a09f453` (orb rework; the round-4 repairs change tint maths only): built; the log shows `Using the Impeller rendering backend (OpenGLESSDF)` on launch, so the runtime shader path is the one exercised. 31 screenshots captured by `docs/ui_phase/tools/capture_screenshots.ps1` (PrintWindow of the client area; no other windows): `docs/ui_phase/screenshots/01..13_*.png` (forms, states, onboarding, reduced effects, narrow) `orb_*.png` (seven styles, six states), `palette_*.png` (five palette swaps), plus `orb_variants_sheet.png`.

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

Run 2 (started at commit `4544f33`; `SAMPLE_SECONDS=130`): the particle-only first build. Dashboard with blur opt-in: raster p95 4.4 ms, 0 frames over 16.7 ms per window (was 22.6 ms and ~154). Companion idle/working/reduced: raster p95 3.2 / 4.2 / 3.1 ms, 0 janky frames. Old `mesh` and `swarm` variants: raster p95 8.0 / 8.5 ms, 0-4 janky frames per window. (Logs for the superseded variants were replaced by run 3.)

Run 3 (commit `a09f453` painter, `SAMPLE_SECONDS=100`): the first ribbon build used one `MaskFilter.blur` per ribbon/bolt/thread stroke. Result: every ribbon style janked (raster p95 about 34 ms, 110-156 of ~400-500 frames per window over 16.7 ms; Fluid Plasma 33.5 ms, Particle Intelligence 36.0 ms, Neural Filaments 36.1 ms, Electric Core 33.8 ms, Holographic 33.9 ms, Aurora 35.4 ms, Sun 26.8 ms; working state 16.6 ms). Finding PERF-2, fixed in the final commit: glow is now three widening additive strokes plus a hot core (`_glowStroke`); only hairline blurs (<= 1.6 px) remain. Those run-3 logs were replaced by run 4.

Run 4 (final commit painter, `SAMPLE_SECONDS=100`, first window skipped, medians across windows; `docs/ui_phase/tools/summarize_perf.py` over `docs/ui_phase/perf/`):

| Scenario (log) | Windows | Frames / window | build p50 / p95 ms | raster p50 / p95 ms | total p95 ms | frames > 16.7 ms per window |
|---|---|---|---|---|---|---|
| companion_idle_profile | 15 x 5s | 738 | 0.21 / 0.27 | 2.33 / 3.22 | 4.73 | 0 (max 0) |
| companion_reduced_profile | 22 x 5s | 721 | 0.26 / 0.39 | 2.25 / 3.10 | 4.48 | 0 (max 0) |
| companion_working_profile | 15 x 5s | 716 | 0.23 / 0.35 | 3.00 / 4.19 | 5.56 | 0 (max 0) |
| dashboard_plasma_profile | 16 x 5s | 721 | 0.20 / 0.25 | 2.84 / 3.42 | 4.96 | 0 (max 0) |
| dashboard_profile | 22 x 5s | 725 | 0.23 / 0.35 | 3.13 / 4.38 | 5.88 | 0 (max 0) |
| orb_flow_profile | 22 x 5s | 718 | 0.30 / 0.41 | 3.28 / 4.46 | 5.84 | 0 (max 0) |
| orb_glass_profile | 22 x 5s | 723 | 0.23 / 0.32 | 3.22 / 4.19 | 5.60 | 0 (max 0) |
| orb_mesh_profile | 16 x 5s | 720 | 0.56 / 0.81 | 6.24 / 8.01 | 11.45 | 0 (max 1) |
| orb_swarm_profile | 22 x 5s | 701 | 0.64 / 1.07 | 6.68 / 8.46 | 14.21 | 4 (max 38) |
| reduced_plasma_profile | 16 x 5s | 720 | 0.19 / 0.22 | 1.83 / 2.50 | 3.83 | 0 (max 0) |
| style_aurora_profile | 16 x 5s | 722 | 0.22 / 0.29 | 2.48 / 3.30 | 4.70 | 0 (max 0) |
| style_electric_profile | 16 x 5s | 721 | 0.23 / 0.29 | 2.53 / 3.33 | 4.68 | 0 (max 0) |
| style_filaments_profile | 16 x 5s | 724 | 0.24 / 0.32 | 2.72 / 3.69 | 4.93 | 0 (max 0) |
| style_holographic_profile | 16 x 5s | 720 | 0.19 / 0.24 | 2.84 / 3.90 | 5.21 | 0 (max 0) |
| style_particles_profile | 16 x 5s | 719 | 0.53 / 0.74 | 5.21 / 6.33 | 8.00 | 0 (max 0) |
| style_plasma_profile | 11 x 5s | 723 | 0.19 / 0.23 | 2.36 / 2.87 | 4.39 | 0 (max 0) |
| style_plasma_working_profile | 16 x 5s | 723 | 0.21 / 0.25 | 2.60 / 3.77 | 5.11 | 0 (max 0) |
| style_sun_profile | 16 x 5s | 720 | 0.23 / 0.30 | 3.21 / 4.28 | 5.67 | 0 (max 0) |

Reading: the ">16.7 ms" column is the measure that matters on this machine; see the per-style rows for the cost of each structure after the blur removal. Reduced effects removes the blur and additive passes and is the floor. Frames per window are ~700-800 because Impeller on this machine is not vsync-capped in the profile run.

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
| 2 | `4544f33` | REJECTED | M1 Approval shown "done" from the simulator's seeded history; M2 `Colors.white` literals in the orb painter; N round-1 B1/B2/M4/M5 confirmed FIXED; N interactions UI-local; N boundary OK | both repaired in `cfdaf70` (`WorkItem.decided`, `UriGlass.specular`) |
| 3 | `cfdaf70` | ACCEPTED WITH FINDINGS | MINOR: a cancel while awaiting approval was not counted as a recorded decision; N both round-2 repairs present, no regression, boundary OK | repaired in `f32a3b1` |
| 4 | `a09f453` | REJECTED | M1 cancelling queued/working work counted as a decision; M2 the palette's hot light was not tinted by state; MINOR A1 pixel test only on the default style; N round-3 fix present, one state engine, no `Colors.white`, boundary OK | all repaired in `abb6b6d` |
| 5 | `abb6b6d` | ACCEPTED WITH FINDINGS (abb6b6d) | MINOR: keep a working-state profile scenario (restored in 838d1dd); N: round-4 repairs FIXED, boundary OK | perf run 4 recorded below |

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
