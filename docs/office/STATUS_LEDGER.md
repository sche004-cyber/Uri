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
| Bundle hash (current) | `faf22fb35a711e8d97fa437085b3261a3128a8d77037b5cd1b9ec0956ad50a8b` (review R1 repair: function guard after every load, structural edits refused; two clean Linux builds agree, and the same procedure reproduces the superseded `0720ed8e…` from 3599db6) | `uri_ui/office_web/BUNDLE_SHA256`, Dart constant |
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
