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
