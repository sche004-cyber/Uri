# Button and page placement pass

**NOT READY — BLOCKERS.** Isolated source implementation and HTML study. No fresh compiled Flutter preview, screenshot comparison or independent acceptance. Parent: `d51517cb1de741970e94ed17a14cb5381419939e`.

## Changes

- Elevated/Filled/Outlined/Text/Icon button themes use consistent minimum targets, padding and label proportions, with height growth for longer/scaled text. Existing palettes and Companion identity remain intact.
- Companion A2UI circles use 13-pixel native labels and 16-pixel reference-size labels, proportional existing icons, and existing orbital geometry. The detached chat header accommodates its close target.
- Gallery Cancel/Apply move to a safe footer. Centered inspection controls have a 640-pixel maximum width; long animation choices use an expanded field. Preview state and callbacks remain isolated.
- Workspace context is inline from 960 pixels; narrower layouts use a dismissible context dialog while retaining conversation width and draft. Header titles can wrap. Composer send targets are 44 pixels; idle input no longer inherits a second enclosing border.
- Living onboarding separates Skip from wrapping Back/Next. Approval and scheduler actions wrap beneath summaries. Assist Research moves beneath its field on narrow/enlarged-text layouts.
- Bootstrap's bounded form width matches login. Login inherits consistent button sizing and has a stable submit key; authentication callbacks are unchanged.
- Providers, connections, memory, intelligence, diagnostics and draft toolbars inherit shared styles. Protected files and runtime handlers were not rewritten. Office/experimental candidates remain deferred without integration/design evidence.

## Review

[Page proportions study](page-proportions.html): twelve source-based page studies, three neutral themes, 390-pixel canvas and 200% text toggles. Its controls/messages are simulated; they cannot call a backend, grant approval, start voice or save preferences. Solar is a recorded frame of the real renderer. The linked older captures are explicitly historical.

[Page placement decisions](BUTTON_PLACEMENT_PLAN.md) records each surface family's disposition. Pages without an approved screenshot are proposals, not newly approved designs. The approved Companion reference study remains linked separately.

## Evidence

Five new widget cases were authored: three theme/large-text target checks, narrow context draft retention, and Gallery footer placement. The targeted command failed before tests loaded with `resolved_executable_name`; analysis failed at the same launcher. See [test launch](button_layout_test_attempt.txt) and [analysis launch](button_layout_analysis_attempt.txt). No new pass count exists.

JavaScript syntax, local assets, source hashes, whitespace and coarse Dart lexical delimiters were checked. Delimiter balance is not Dart parsing, type analysis or compilation. Source-colour calculations give white primary-label contrast of 5.961 (Ivory Foundry), 5.642 (Snow Archive) and 9.130 (Ash & Limestone). Rendered disabled/focus/other states remain unverified. See [static checks](button_layout_static_checks.json).

No fresh browser/Flutter capture, native transparency/hit testing, live voice/chat, multi-monitor/DPI, performance measurement or 80% reference claim is made. Historical 567-pass evidence/captures belong to `15a322d1`, before both refinement passes. Fresh lifecycle initialization also failed because GitHub DNS is unavailable; see [attempt](button_layout_lifecycle_attempt.json). No review or gates started. Independent acceptance: none. Integration/deployment: none.

## Resume

Worktree: `C:/Users/cheta/Development/uri-ui-v2`; branch: `ui/companion-v2-visual-qualification`. Run targeted tests, full tests/analysis, rebuild `lib/main_v2_preview.dart`, then capture affected routes at 360/390, 1024 and 1440+ widths, including 200% text. Use `docs/ui_v2/lifecycle_buttons.json` for fresh exact-commit qualification when network/reviewer access is available. Existing binaries are older. No merge, push, active-server replacement or deployment is authorized.
