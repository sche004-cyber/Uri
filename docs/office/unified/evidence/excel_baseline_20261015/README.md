# Excel baseline re-check, 2026-10-15 (code at `5b958da0`, planning tip `dd5d31f5`)

This is automated evidence only. It is not a live qualification and it did not use the Brain.

| Run | Command | Result |
|---|---|---|
| 1 | `python -m pytest tests/office tests/a2ui -q` in this worktree | **1 failed**, 482 passed, 5 skipped (`pytest_office_a2ui_run1_no_bundle.log`). The failure is `test_page_blocks_every_network_attempt_in_edge`: `BundleRefused: no built bundle at uri_ui\assets\office`. This worktree never built the Univer page bundle. The bundle is a build output and is not committed. |
| 2 | The same command, after copying the built bundle from `uri-office-m2\uri_ui\assets\office`. Its `bundle_hash` equals the recorded `uri_ui/office_web/BUNDLE_SHA256` (`b379fff2…c02c`). | **483 passed, 5 skipped, 0 failed** (`pytest_office_a2ui_run2.log`). The copied bundle was removed afterwards and is not committed. |
| 3 | `flutter test test/office test/living/presentation_controller_test.dart test/living/living_shell_test.dart` | **58 passed**, exit 0 (`flutter_office_living.log`). |

Skip reasons:
- 2 tests need `npm ci` (a staging build against the real Univer engine);
- 3 tests are POSIX-only.

What this shows:
- The Office service, grants, drafts, approvals, M2 and A2UI code at `5b958da0` pass their automated suites on this PC today.
- The Flutter Office panel, M2, companion, presentation controller and living shell tests pass.

What this does not show:
- Any live behaviour.
- The Brain path.
- WebView2 rendering.
- Model speed with the panel open (AC11, still NOT VERIFIED).

O2 must re-run all of these suites unchanged as its Excel regression gate.

Finding for O2: the page-bundle test depends on a build output that a fresh worktree does not have. O2's setup step must
either stage a hash-verified bundle or record the skip explicitly. It must never pass silently.
