> Latest source adds button and page-placement refinements. See [current pass](BUTTON_LAYOUT_REPORT.md). Flutter tests, fresh captures and independent acceptance remain **NOT VERIFIED** for this source.

> Current source has newer **unverified spacing refinements**. The captures and 567-pass suite below belong to `15a322d17aa54a4aec8316c6fc6628f70bf617ff`. See [refinement status](REFINEMENT_REPORT.md); do not treat earlier evidence as testing the new source.

# URI UI V2 — isolated review handoff

**NOT READY — BLOCKERS.** The owner-approved reference is implemented as an isolated candidate, not independently accepted or integrated. Companion screenshot similarity is 0.634 against the 0.80 checkpoint; dashboard is 0.879. Native desktop/device/live runtime/performance qualification remains unverified. Reviewer availability/status is recorded by the external lifecycle receipt, never inferred from unit tests.

Worktree: `C:/Users/cheta/Development/uri-ui-v2`
Branch: `ui/companion-v2-visual-qualification`
Accepted base: `1b5423bc15fd7e5da9161c862cf839925da9f2eb`
Exact local snapshot: run `git rev-parse HEAD` in this worktree; the external lifecycle report pins that SHA. No canonical push, merge or deployment is authorized.

## Review evidence

- [Companion comparison](companion-review.html): actual Solar, floating Chat/Dashboard/Voice, waveform and detached shared conversation. Smaller native layouts also included.
- [Dashboard comparison](dashboard-review.html): all three approved palettes, six linked destinations and faded artwork.
- [Visual differences and gate boundaries](VISUAL_QUALIFICATION.md), [current functionality](CURRENT_UI_EVIDENCE.md), [discovery](DISCOVERY_REPORT.md), [coverage](FUNCTIONAL_COVERAGE_MATRIX.md), [inventory](SCREEN_AND_FUNCTION_INVENTORY.md), [machine ledger](FUNCTIONALITY_LEDGER.json).
- `evidence/final/`: actual engine exports for all eleven Gallery designs, login/themes, dashboard/responsive layouts and Companion states; fixture-only data. `result.json` and `capture_log.txt` record capture and 96-DPI native-region facts.
- `WORKING_STATE.json`, `regression_final.jsonl`, `analyze_final.txt`, real/preview build logs and `frozen_candidate_delta.json` record available checks. Five suite skips and three baseline analysis infos are explicit.

## Launch later

Use this worktree only. Do not launch or replace an owner server. The debug executable currently contains the offline preview; rebuilding another entry replaces that local binary only.

```powershell
Set-Location C:\Users\cheta\Development\uri-ui-v2\uri_ui
& C:\Users\cheta\flutter\bin\flutter.bat run -d windows --no-pub -t lib/main_v2_preview.dart
```

The offline entry starts on Dashboard, uses simulated service data and isolated in-memory preferences, opens no microphone and offers no unavailable Voice action. It is for visual inspection, not authentication/execution proof. Use Settings → Companions for the live isolated renderer viewer; Apply/Cancel control preference changes. Click the Companion to reveal controls; Chat toggles detached chat; double click opens Dashboard. Escape closes chat first and then floating controls. Motion stops near the pointer, on chat/focus/voice, reduced motion and hidden windows.

For a separately prepared test service/account, the real bootstrap/auth entry is `lib/main_v2.dart`. It preserves authentication; no owner login or active server was used here. `lib/main_v2_integrated.dart` is an optional test-worker entry requiring URI_V2_CLIENT_MANIFEST under this worktree/work/ui_v2; no worker was spawned and no runtime qualification is claimed. Wake phrase detection is unsupported by the inspected baseline.

Read-only HTML comparisons: `python docs/ui_v2/tools/serve_options.py` from the worktree, then `http://127.0.0.1:8137/companion-review.html`. An existing preview server may already occupy that port; reuse it. This serves documentation only and starts no URI backend.

External lifecycle evidence: `C:/Users/cheta/Development/uri-ui-v2-lifecycle-20261013/REPORT.html` and receipt/state files. The fresh reviewer must be available and exact-commit evidence valid before any claim of independent acceptance. No integration step belongs to this task.
