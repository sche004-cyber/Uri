# Capability ledger update — Web Intelligence, URI Assist, REA (2026-10-10)

Ladder (from `docs/integration/final_20261010/CAPABILITY_LEDGER.md`): RESEARCHED → PLANNED → IMPLEMENTED → TESTED →
INDEPENDENTLY ACCEPTED → INTEGRATED (canonical) → STAGED → ACTIVATED. A level is claimed only with
COMPLETED_WITH_RESULT evidence.

| Capability | Highest level | Evidence | Not yet |
|---|---|---|---|
| W1 SafeFetcher (SSRF-safe pinned retrieval) | TESTED (+ live direct pinned run) | `W1_QUALIFICATION.md`; `evidence/w1_live_direct_pinned_after_repair.json` | Codex; integration |
| W1 search providers (Tavily/Brave/SearXNG) | TESTED (fake HTTP) | provider tests | live search (no keys); Codex |
| W1 extraction, feeds | TESTED (+ live feed) | tests; live RSS 20 items | Codex |
| W1 read-only Mastodon / Bluesky | TESTED (fake HTTP) | social tests | live (egress policy); Codex |
| W1 evaluation, conflicts, lexical citation check | TESTED | tests incl. F3 regressions | Codex; semantic verification not claimed |
| W1 research job + worker commands + A2UI result | TESTED | bridge/surface tests; Dart renderer test | worker live on Windows; Codex |
| A0 Assist UI (fourth form, scope line, Dashboard tile) | TESTED (Flutter widget tests) | `assist_mode_test.dart` | live on Windows; owner review of prototype; Codex |
| A0 access control (scope, 5 permissions, revoke, generations) | TESTED | access/bridge tests | Codex |
| A0 redaction (two layers) | TESTED (incl. real Chromium, 2 hostile fixtures) | tests | Codex; live pages |
| A0 browser snapshot script (MV3) | TESTED in Chromium | tests | channel to URI: PLANNED |
| A0 Windows UIA adapter | PLANNED (contract only) | `perception.py` docstring | implementation (PC) |
| A0 screen capture adapter | PLANNED | — | owner decision |
| A0 on-demand vision via resident Brain | IMPLEMENTED + TESTED (gating, building, cancellable send with fakes); disabled by default | vision tests | application-path qualification on the PC |
| A1 Teach URI / Smart Fill | PLANNED (design) + RESEARCHED (PBE spike 7/8 from one example) | `A1_DESIGN.md`; `research/rea_discovery/` | entry gate |
| REA (Reverse Engineer Anything) | RESEARCHED (paper only, earlier session); **not installed, not used** | `research/rea_discovery/REA_DISCOVERY_REPORT.md` §1 | owner decision whether to evaluate |
| SSRF-1 in frozen `fetch_url` | open defect (pre-existing) | `01_EXISTING_SYSTEM_AUDIT.md` | owner decision |
