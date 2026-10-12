# URI-OFFICE-M1 status ledger

This ledger feeds the integration receipt. The lifecycle receipt (`receipt.json` / `RECEIPT.md`) replaces it once the
independent review has run. Every entry states its evidence.

## 2026-10-11, candidate after commit 6b5db718 (owner direction "next steps", items 1–5)

| Item | State | Evidence |
|---|---|---|
| 1. Linux test count | **NOT VERIFIED (no runner); non-blocking.** Linux is not a target platform. No cloud session or CI workflow was used. | owner direction 2026-10-11 |
| 2. Hyphenation chunks removed | Done. The bundle went from 11,321,368 bytes in 80 files to 6,737,775 bytes in 3 files (`index.html`, `assets/index-qNa08Mb9.js`, `assets/index-swO04emn.css`). | `uri_ui/office_web/vite.config.js` plugin, which fails the build if the table changes shape |
| 2. Built during staging, not committed | Done. `uri_ui/assets/office/` is untracked; staging runs `python -m uri_office.page_build build`. | `uri_office/page_build.py` |
| 2. Reproducible | Done. Two clean builds (`npm ci --ignore-scripts` + `vite build`) gave the same bundle SHA-256: **`d35a39745f9db43619ff04cc3a9f35bb39127f4894c287efaf53d6fd424f6b90`**, recorded in `uri_ui/office_web/BUNDLE_SHA256`. Staging refuses any other bundle (exit 2). | `tests/office/test_page.py` |
| 2. Network block still first | Done. `no-network.js` sits at byte offset **615** of `assets/index-qNa08Mb9.js`; the first Univer plugin code is at 4,414,176. | bundle scan |
| 3a. Workers | Done. Univer starts none: the only `new Worker` is in `UniverRPCMainThreadPlugin`, added only when a `workerURL` is given (none is). `worker-src 'none'`, and `Worker`/`SharedWorker` are blocked in the page. | bundle scan; probe `worker` attempt blocked |
| 3b. CSP tightened and tested | Done. Images, CSS `url()`, the bundle's own Tailwind `url(https://example.com/…)` class, prefetch, iframe, fonts and form posts are blocked by the policy alone; fetch, XHR, WebSocket, EventSource and sendBeacon are blocked by both layers. | `docs/office/evidence/page_network_block_edge.json`; test above |
| 3b. `window.open` | Page patch returns null. Headless Edge blocks pop-ups anyway, so a CSP-only result proves nothing; the host must refuse new windows. | evidence file note |
| 3b. Navigation | **Not blocked by page layers** (canary hit `/nav`), by design. Only the host can cancel it. | evidence file |
| Defect found by the probe, fixed | The page sent formula recalculation results (`{onlyLocal, fromFormula}` writes) to the host as user edits, which would have replaced formulas with values. Now ignored; the probe asserts that only `ready` is sent after a load with marks. | `src/main.js`; probe `only_ready_sent` |
| 3c. Host-side block | **BLOCKED: owner decision OFF-O6.** `webview_flutter_windows` 1.2.0 has no request filter, navigation cancel or dev-tools switch. Recommendation: vendor the package and patch it. | plan §13 |
| 3d. Real WebView2 run | **NOT VERIFIED.** Depends on 3c and the Flutter panel. | — |
| 4. Independent review | **Not started.** It runs after 3c and 3d so its scope covers every network-block layer. | — |
| 5. Integration | None. Canonical stays at `ce1a90c`. OFF-O1..O6 are open. | `git ls-remote uri-repo` |

## Test counts at this candidate

| Platform | Python `tests/office` | Page unit tests (`node --test`) |
|---|---|---|
| Windows 11, Python 3.13, Node 24.19 | 134 collected, 134 passed, 0 skipped | 4/4 (also run inside pytest) |
| Linux | NOT VERIFIED (no runner) | NOT VERIFIED |

## 2026-10-11, OFF-O6 (a) approved: vendored host, panel and real-runtime tests

| Item | State | Evidence |
|---|---|---|
| Vendored package | Done. Baseline `9765e780`; patch listed in `uri_ui/packages/webview_flutter_windows/PATCHES.md` | archive SHA-256 equals pub.dev's |
| Build toolchain / runtime | Present (VS Community 2026 18.10 C++, WebView2 154.0.4258.62). Nothing installed. Build-local NuGet fetch pinned and verified. | `.nupkg` hashes equal nuget.org catalog |
| Release builds | App and security probe build with `/W4 /WX` | `flutter build windows --release` |
| Real-WebView2 security tests | **COMPLETED_WITH_RESULT**; final run: 0 escapes in 48 attempts + 9 navigations | `evidence/webview2_security_probe_run4_final.json` |
| Defects found by the probe, fixed | WebSocket bypassed the request filter (P2 proxy); WebRTC/STUN UDP escaped (constructors removed in every frame) | runs 1 and 2 kept as history |
| Bundle hash (current) | `b379fff2350c3b86fb51d4d85b4525d5ac03b6d9fda0fbdaa103182ca567c02c` (review R3 repair R3-03: multi-line or partly styled grid text is sent as its plain text, never as a clear; two clean Linux builds agree). Earlier: `34372d19…` (review R2 repair R2-01: shared-formula fill/insert-function cells are sent as formulas, never as clears; two clean Linux builds agree, and the same procedure reproduces the superseded `faf22fb3…` from 2b917cf). Earlier: `faf22fb3…` (review R1 repair: function guard after every load, structural edits refused), `0720ed8e…` (3599db6) | `uri_ui/office_web/BUNDLE_SHA256`, Dart constant |
| Real-WebView2 probe on the current bundle | **NOT VERIFIED.** The runs above used the superseded bundle `0720ed8e…`; the probe (now also checking that no network formula function is registered after a workbook loads) must be re-run on Windows | `tests/office/test_page.py::test_page_blocks_every_network_attempt_in_edge`, `uri_ui/lib/office_security_probe.dart` |
| Tests (Windows) | `tests/office` 136 passed; `tests/ws tests/oi tests/a2ui` 597 passed / 22 skipped (baseline); scheduler 71/71; `flutter test` 519 passed / 5 skipped (not Office); `flutter analyze` 2 pre-existing infos; `ws_frozen_check` ok | this session |
| Live panel with a real workbook and the Brain | **NOT VERIFIED.** Needs the launcher to start the Office service and an owner at the PC; not simulated. | — |
| Independent review | Pending: separate `claude_cli` reviewer in a Linux cloud session at the exact commit | — |

## 2026-10-11, independent review R1 (at 3599db6): corrections and repairs

The reviewer's findings disproved these earlier claims. The claims are kept above as history and corrected here.

| Finding | Earlier claim | Correction / repair | Regression test |
|---|---|---|---|
| R1-01 | AC15: IMAGE, HYPERLINK, FILTERXML and ENCODEURL are removed from the page's formula engine | **False at 3599db6.** Univer registers its functions when the first workbook loads, after the start-up removal. Now registration of these names is filtered, they are removed again after every load, and the page refuses to show a workbook while one is present. The Edge probe now reports `blocked_functions_present` | `uri_ui/office_web/test/guard.test.mjs`, `guard.univer.test.mjs` (real Univer 1.0.3, needs `npm ci`), `tests/office/test_page.py` |
| R1-02 | Network formulas are refused | Only `NAME(` calls were refused. Names are now refused as bare tokens (`=MAP(A1,WEBSERVICE)`), and STOCKHISTORY, TRANSLATE, DETECTLANGUAGE, COPILOT, CUBE*, SQL.REQUEST, ENCODEURL, GOOGLEFINANCE, GOOGLETRANSLATE, AI(, PY( were added | `tests/office/test_review_r1_repairs.py` |
| R1-03 | AC4: array formula cells are refused | Only the anchor was refused. Every cell in the array range is now locked and refused | same |
| R1-04 | Cell refs are validated | `A1\n` passed. Refs now use a full match and are keyed canonically at every entry point | same |
| R1-05 | Approval saves what was shown | Edits made after the card was shown were dropped on approve. The approval is now bound to the draft version; a changed draft refuses with STALE_CHANGE and closes the card | same |
| R1-06 | AC3: the hash binds exactly what was shown | The card cut values at 60 characters and 30 lines. It now shows every line in full (text quoted) and the full destination path; a change set too large for one card is refused | same |
| R1-07 | — | Lock-order inversion could deadlock approve against propose. The order is now always workbook lock, then approvals lock | same |
| R1-08 | AC7: writes only inside allowed roots | A planted symlink at the fixed temp name was followed. The temp file is now created with mkstemp (O_EXCL, random name), synced, and keeps the replaced file's permission bits (on Windows only the read-only bit; the folder's ACL applies) | same |
| R1-09 | — | Google apply wrote cells before checking structural ops. All checks now run first, then one all-or-nothing `batchUpdate` | same |
| R1-10 | AC2: user edits share one draft | The panel dropped page edits while busy (paste, typing during a Brain turn). They are now queued and sent in order | `uri_ui/test/office/office_panel_test.dart` |
| R1-11 | — | Structural grid edits in the page were never reported. They are now refused in the page (commands and mutations) and the owner is told why | `guard.test.mjs`, `guard.univer.test.mjs` |

Not verified in this repair: the Windows-only Edge/WebView2 probes on the new bundle (see the row above).

## 2026-10-11, independent review R3 (at 4743860): corrections and repairs

The reviewer's findings disproved these earlier claims. The claims are kept above as history and corrected here.

| Finding | Earlier claim | Correction / repair | Regression test |
|---|---|---|---|
| R3-01 | R1-02: network formulas are refused | **False at 4743860.** Strings were stripped with a regex that ignored quoted sheet names, so `='q"'!A1&WEBSERVICE(..)&'q"'!A1` was accepted and saved. `check_formula` now tokenises left to right (single-quoted sheet names and double-quoted strings, each with doubled-quote escapes), scans only the code, and refuses unterminated quotes | `tests/office/test_review_r3_repairs.py` (incl. end-to-end on a sheet named `q"`) |
| R3-02 | R1-06: the card shows the full value | A value containing a URL made `propose_save` fail with an uncaught A2UI `URL_REFUSED`. Such a value is shown as a JSON string with `:` written as `\u003a` (decodes to the exact value); anything else a card cannot show is refused as `CHANGE_CANNOT_BE_SHOWN` | same |
| R3-03 | R2-01: grid edits are never sent as clears | Multi-line or partly styled text (`{p, v: null}`) was sent as a clear. Its plain text is now read from `p.body.dataStream`; rich text with no plain-text form (cell image, table) is reported as `RICH_TEXT_NOT_READ` | `convert.test.mjs`, `edits.univer.test.mjs` (real `SetRangeValuesCommand` with the editor's rich-text shape; the DOM editor itself is not run in node) |
| R3-04 | R1-03: array formula cells are refused | Data-table formulas (`t="dataTable"`) were not locked; saving the anchor dropped the table. Every cell in a data table's `ref` is now locked and refused at save time | `tests/office/test_review_r3_repairs.py` |

Not verified in this repair: the Windows-only Edge/WebView2 probes on the new bundle `b379fff2…`.

## 2026-10-11, review VERIFIED at 25fce881 (R9 ACCEPT WITH FINDINGS) -> Windows gate evidence

The cloud lifecycle run continued after round 2 and reached VERIFIED at `25fce881` (9 rounds, repairs P6-P12; open: R9-01, R9-02 LOW). Its gates were Linux only. On the owner's PC, at that code:

| Check | Result |
|---|---|
| Page bundle, two clean builds | `b379fff2350c3b86fb51d4d85b4525d5ac03b6d9fda0fbdaa103182ca567c02c`, equal to `BUNDLE_SHA256` |
| Real WebView2 probe (run 6) | 0 escapes in 48 attempts + 9 navigations, nothing downloaded, all lockdown settings off (`evidence/webview2_security_probe_run6_verified_25fce881.json`) |
| `tests/ws tests/oi tests/a2ui` | 597 passed, 22 skipped (baseline) |
| `flutter test` | 522 passed, 5 skipped |
| `tests/office` | **3 failed** on Windows: the node-test wrappers looked for TAP output (`# fail 0`), which node prints only when it chooses TAP; the node tests themselves passed |
| `flutter analyze` | 4 issues (2 new `use_null_aware_elements` infos from the repairs) |

Windows gate fix on top (this commit): node wrappers force `--test-reporter=tap`; the two lints fixed. After it: `tests/office` 246 passed / 3 POSIX-only skips; analyze back to the 2 pre-existing infos; Office widget tests 11/11.
A local manual repair of round 2 (`wip/office-manual-r2-repair`, 9f5f14ad) overlapped the run's own repairs and was NOT pushed; its extra low-severity hardening (R2-03 Dart-args ignored, R2-04 install_ok, R2-06 card characters, R2-08 page-folder links) is available as a follow-up if wanted.

## 2026-10-12, Windows-fix re-review did not run (baseline moved)

The cloud re-review of `f0f95feb` (`URI-OFFICE-M1-w`) did not start: the lifecycle driver refused because `origin/integration/git-sync-20261008` moved from `ce1a90c` to `cbdf3f2c` (DEV-LIFECYCLE-2), and the config expects `ce1a90c`. Nothing was reviewed, committed or pushed by that session. Status of `f0f95feb`: **NOT VERIFIED** by an independent review. The next review (below) pins the baseline to the commit `ce1a90c046d2e9566a86d8dccf25df0e2bc98c80` itself, the base this candidate was built on; rebasing onto `cbdf3f2c` stays a later step (after W1/A0, owner-gated).

## 2026-10-12, scripted live check on the PC (owner choice 2b; NOT the owner's own check)

First run (before the companion pane), Brain started with `--override-contention` on the owner's instruction ("Override start"; dwm.exe held 1.1 GB): Brain READY 159 tok/s; page loaded; workbook opened; URI proposed `Sales!C2 = "Checked by URI"` in 2.1 s; accepted; approval card shown; saved. Evidence `evidence/live_check_20261012/`.

## 2026-10-12, AC19: URI companion in the Office pane (owner request, added to M1)

Owner: "On the right side pane Uri companion should be available to deal with user request, if this is inside uri" -> "Add to M1 now".

- The Office region's right pane is now the URI companion: requests, URI replies, suggested-change cards (Accept/Reject, hash-bound as before), the approval card, undo/redo/save tools, the history switch, and the companion's own composer (with push-to-talk) at the bottom.
- Routing is UI-side only: `LivingServices.officeTarget` is set by the Office region while it shows a controller; `activeOfficeTarget()` returns it only in Workspace mode, Office focus, with a workbook open. The composer and `VoiceInteractionController` send to it then; otherwise nothing changes. The worker, its commands and its sandbox are unchanged.
- A request only asks URI to suggest changes. Accept, reject and save remain buttons; spoken words never approve.

| Check (PC, Windows) | Result |
|---|---|
| `flutter analyze` | 2 issues, both pre-existing infos (unchanged) |
| `flutter test` | 532 passed, 5 skipped (522 before + 10 new) |
| New tests | `uri_ui/test/office/office_companion_test.dart` (8), `uri_ui/test/living/live_voice_test.dart` (+3) |
| Scripted live check, run 1 | COMPLETED_WITH_RESULT, but the harness build's icon font was stale (1 KB, tree-shaken in the morning build with no icons), so icons were blank in screenshots; also found: an empty Brain message left no URI line in the pane. Fixed: the pane says "I suggested N change(s). Review below." (test added); harness rebuilt with `--no-tree-shake-icons` |
| Scripted live check, run 2 | COMPLETED_WITH_RESULT. Brain READY 161 tok/s with the owner-approved override (owner answered "Yes, override start" for this check); `gpu_lease advise --window` GO; the app's `OfficeRegion` inside `LivingScope`, Office focus; companion routed to the workbook only after it opened; URI proposed C2 in 1.5 s; accepted; approval card; saved. File check: only `xl/worksheets/sheet1.xml` changed, only `Sales!C2` (None -> "Checked by URI"). Brain and service stopped; GPU lease FREE. Evidence `evidence/live_check_20261012_companion/` |

Not verified: typing in the real composer and push-to-talk on the PC (the harness calls the same `activeOfficeTarget().instruct` the composer and voice use; both paths are covered by widget and unit tests only); the owner's own live check (OFF-O5).

## 2026-10-12, review URI-OFFICE-M1-c VERIFIED (R1 ACCEPT WITH FINDINGS) and owner-requested repairs

Receipt `docs/office/review-c/` (candidate `e6a4dcd5`, baseline `ce1a90c`, 1 round, no repairs, 7 LOW non-blocking findings). Owner: "Fix" (R1-01 and R1-06, as recommended; R1-02..R1-05 and R1-07 stay open as known LOW limitations).

| Finding | Repair | Regression test (fails before, passes after) |
|---|---|---|
| R1-01 companion conversation kept when another workbook opens | `OfficeController._apply` clears the conversation, URI's last reply and the previous workbook's approval cards when the workbook id changes | `office_companion_test.dart` "opening another workbook clears..." (checked failing on the unrepaired controller) |
| R1-06 shared files converted LF->CRLF | `analysis_options.yaml`, `living_scope.dart`, `presentation_controller.dart`, `workspace_mode_view.dart`, `main.dart`, `pubspec.yaml` restored to LF; their diffs vs `ce1a90c` are now 2/23/1/5/5/3 added lines instead of whole-file rewrites | `tests/office/test_review_c_repairs.py` |

PC gates after the repair: `tests/office` 247 passed / 3 skipped; `flutter test` 534 passed / 5 skipped; `flutter analyze` 2 pre-existing infos; `ws_frozen_check` ok.

## 2026-10-12, review URI-OFFICE-M1-c2 VERIFIED (R1 ACCEPT WITH FINDINGS) and owner-approved repairs

Receipt `docs/office/review-c2/` (candidate `0dbb7bda`, baseline `ce1a90c`, 1 round, no repairs, 4 LOW non-blocking findings; the M1-c R1-01 and R1-06 repairs are no longer findings). Owner: "Approved recommendations" (fix R1-01 and R1-02; R1-03 and R1-04 stay open, to be handled at the merge step).

| Finding | Repair | Tests |
|---|---|---|
| R1-01 before a workbook is open, the Office composer invites sheet requests and sends them to the hidden ordinary conversation | `LivingServices.officeInFocus()`: in Office focus the composer and push-to-talk belong to Office. With no workbook open the hint says "Open a workbook first", nothing is sent, typed text stays in the composer and spoken text is put there with notice `NO_WORKBOOK` | `office_companion_test.dart` (inside the living UI), `live_voice_test.dart` (NO_WORKBOOK) |
| R1-02 leaving Office focus closes the workbook and drops accepted but unsaved changes without warning | Leaving no longer closes the workbook: `LivingServices.officeKeep` remembers the workbook id and conversation; on return `OfficeController.resume()` reloads the view, draft and open approval cards from the service and says "Your unsaved changes to <name> are still here." If the service no longer has it (restart), the keep is cleared and the owner is told. Opening another workbook closes the replaced one in the service | `office_companion_test.dart` (leave and return keeps the accepted change and conversation; unknown workbook reported; replaced workbook closed) |

PC gates: `flutter test` 536 passed / 5 skipped; `flutter analyze` 2 pre-existing infos. Fail-before for these tests: they do not compile against the unrepaired code (the new `officeKeep` / `officeInFocus` API), so they cannot pass there; the behaviour checks are the assertions listed. Not verified on the PC with the real Brain and WebView2: leave-and-return (no GPU override was requested for it).
