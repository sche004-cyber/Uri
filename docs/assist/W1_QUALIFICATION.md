# W1 Web Intelligence — qualification (cloud, automatable criteria)

Branch `milestone/w1-web-intelligence-20261010` @ `db7c02c` (W1 `885483b` + interim-review repair). Gates run on the
stacked A0 tip `1844b48`, which contains it. Host: Linux cloud container, Python 3.13, no GPU, no Windows.

**Verdict: TESTED — automatable criteria met; NOT independently accepted (Codex audit not performed); NOT
integrated; NOT activated.**

## 1. Criteria (from `00_PLAN_AND_ACCEPTANCE_CRITERIA.md`)

| ID | Status | Evidence |
|---|---|---|
| W1-AC1 SSRF corpus refused | MET | `test_w1_netpolicy_safe_fetch.py` (40 address forms, 26 URL forms) + F6 LDH tests |
| W1-AC2 every redirect re-validated, max 5 | MET | redirect tests (private, literal loopback, `file:`, limit) |
| W1-AC3 pinned connection, rebinding refused | MET | pinning + rebinding tests; live direct run against pypi.org shows the pinned IP with correct Host/SNI/TLS (`evidence/w1_live_direct_pinned*.json`) |
| W1-AC4 timeouts, byte cap, type allow-list, no cookies/credentials | MET | tests; compressed bodies refused (raw byte cap) |
| W1-AC5 SourceRecord per attempt, UNTRUSTED fixed | MET | record test |
| W1-AC6 extraction + hidden content dropped | MET | extraction fixtures + 8 more hidden forms (F3) |
| W1-AC7 RSS/Atom/RDF, DOCTYPE/ENTITY refused | MET | feed tests; live Atom/RSS from pypi.org (20 items) |
| W1-AC8 providers, explicit UNAVAILABLE, no key leakage | MET in code; **search NOT VERIFIED live** (no keys; egress policy) | provider tests; key file for the worker (F2) |
| W1-AC9 duplicates / near-duplicates | MET | evaluation tests |
| W1-AC10 citation-backed, unsupported sentences dropped | MET **as a lexical check** (one supporting sentence, numbers, polarity); not a semantic proof | verifier + F3 tests |
| W1-AC11 conflicts with both citations | MET | conflict tests incl. near-duplicate pages |
| W1-AC12 prompt-injection resistance | MET for the paths tested (malicious page, feed, data-block escape, steering notes) | `test_malicious_page_cannot_redirect_the_pipeline` and F3 tests |
| W1-AC13 bounded background research, progress, cancel, fixed statuses | MET (Brain synthesis itself not cancellable: L-W1-3) | pipeline/bridge tests, F1 deferred start |
| W1-AC14 read-only Mastodon/Bluesky | MET with fake HTTP; **live NOT VERIFIED** (egress policy denied the hosts) | social tests; `evidence/w1_live_proxy_egress_denied.json` |
| W1-AC15 A2UI rendering, no URLs, no new action | MET | surface tests; Dart renderer test |
| W1-AC16 no frozen path, no new dependency, gates unchanged | MET (protected-path check); Phase 1 byte check **BLOCKED** (zip only on the PC) | `ws_frozen_check` protected part `[]`; gates below |

## 2. Gates

| Gate | Result | Evidence |
|---|---|---|
| `tests/web` | 158 passed | run 2026-10-10 |
| ws/oi/a2ui/web/assist (Linux) | 772 passed, 24 skipped; failing set **identical** to the pre-change baseline (199 IDs, all Windows-only `msvcrt`/PowerShell or their consequences) | `evidence/gates_repaired_1844b48_linux.txt`, `baseline_gates_linux_ffdf534.txt` |
| Frozen check | protected paths changed: none; Phase 1 zip check BLOCKED here | `ws_frozen_check.py` output |

Pre-existing intermittent test recorded: `test_host_requests_are_explicit_fresh_and_used_once`
(`evidence/flake_test_host_requests.txt`).

## 3. Not verified (and effect)

Live search through a provider (no keys) — blocks activation of search, not the code verdict. Live social APIs and
other public sites (container egress policy) — same. The worker hook running on Windows — PC step. Codex review —
blocks acceptance.

## 4. Carried limitations

- **L-W1-1** Lexical verification cannot prove paraphrase meaning; wording in the UI says so.
- **L-W1-2** Instruction-like text detection is pattern-based; unflagged steering is mitigated by data blocks and the
  verifier, not eliminated.
- **L-W1-3** Research synthesis uses a non-cancellable Brain call (≤ 700 tokens, ~6 s); a user turn can queue behind it.
- **L-W1-4** Total fetch deadline can overrun by up to the read timeout; no dual-stack fallback after the first address.
- **L-W1-5** Proxy egress mode trusts the proxy for resolution of allow-listed names.
- **SSRF-1 (pre-existing, frozen)**: `uri_core/tools/fetch_url.py` remains unsafe; owner decision.
