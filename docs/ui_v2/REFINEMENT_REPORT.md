# Companion spacing refinement — unverified local candidate

**NOT READY — BLOCKERS.** These source edits are newer than the last tested/captured snapshot `15a322d17aa54a4aec8316c6fc6628f70bf617ff`. They are isolated work for later qualification, not an accepted build.

## Changes

- Widen compact detached chat and reclaim waveform space when voice is off. Use the same geometry for rendering and desktop interaction-region calculation.
- Refine Conversation header, message spacing, neutral bubble fill and composer proportions. Remove the floating composer's enclosing glass panel; retain the shared submit/service path.
- Align the Solar center and floating-control orbit with the approved reference. Keep existing renderers, voice signal, click recognizer and motion pause logic.
- Reserve more small-dashboard header space, aligned with the central Companion, to make supporting copy visible.
- Author two widget checks for latest-reply visibility at 360 × 560 and dashboard header visibility at 390 × 844. Neither ran in this session.

## Available evidence and blockers

The [HTML study](companion-refinement.html) shows the approved reference beside an interactive spacing proposal. It uses a recorded frame of the existing Solar renderer and simulated controls/messages/voice. It is not a current Flutter export or a real 3D model. Browser visual inspection is **NOT VERIFIED**: the browser could not connect to this session's local documentation server.

Flutter test and analysis commands fail before loading the application with `Empty value for option resolved_executable_name` and `Unrecognized flags: resolved_executable_name`. Direct Dart VM attempts also fail to canonicalize paths (OS error 5). The Dart analysis connector cannot register the workspace because it requires approval and this session disallows approvals. See [test launch log](refinement_before.txt) and [analysis launch log](refinement_analysis_attempt.txt). These are tool failures, not completed analysis or test results.

The fresh lifecycle run failed during initialization, before review or gates ([attempt record](refinement_lifecycle_attempt.json)). The canonical GitHub refresh failed because `github.com` could not be resolved. The cached accepted base remains `1b5423bc15fd7e5da9161c862cf839925da9f2eb`; no newer acceptance is asserted.

Previous `evidence/final`, `regression_final.jsonl` and `analyze_final.txt` belong to `15a322d1`: 567 tests passed, five skipped. The prior Companion comparison was 0.634 and dashboard 0.879 under the recorded regional SSIM method. SSIM is an image metric, not a literal percentage of design accuracy. The owner's 80% Companion target remains unmet/unestablished; there is no new screenshot score.

No native transparency, hit testing across applications, microphone/wake phrase, live chat, DPI/multi-monitor behavior or measured performance is newly verified. Previous independent review was WAITING_FOR_MODEL; it cannot accept this newer source.

## Resume qualification

1. In this worktree only, restore a session where the installed Flutter SDK can resolve its own executable and source paths.
2. From `uri_ui`, run `C:\Users\cheta\flutter\bin\flutter.bat test --no-pub test/living/ui_v2_test.dart`, then the full Flutter suite and analysis.
3. Build/capture `lib/main_v2_preview.dart` using fixture data. Compare at 828 × 1280, 360 × 560 and matching dashboard sizes. Repair observed differences before asserting the target is reached.
4. Run the fresh exact-commit lifecycle configuration `docs/ui_v2/lifecycle_refinement.json` when canonical/network and reviewer access are available. No merge, push or deployment is authorized.

The [machine state](REFINEMENT_STATE.json) records source hashes and evidence boundaries. Exact candidate SHA is the containing Git commit. Existing binaries remain the previous build until rebuilt.
