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
| W1-AC4 timeouts, byte cap, type allow-list, no cookies/credentials | MET after the R4 repair | tests; compressed bodies refused (raw byte cap); `test_w1_r4_review_regressions.py` (real socket). **Correction (review R4 of `1615512`):** the earlier MET was false — the total deadline was checked only between body chunks, so a server dripping header bytes or chunk framing under the read timeout held a fetch for 67 s against a 2 s budget. A watchdog now shuts the hop's sockets down at the deadline (connect gets at most the remaining budget). |
| W1-AC5 SourceRecord per attempt, UNTRUSTED fixed | MET | record test |
| W1-AC6 extraction + hidden content dropped | MET | extraction fixtures + 8 more hidden forms (F3) |
| W1-AC7 RSS/Atom/RDF, DOCTYPE/ENTITY refused | MET | feed tests; live Atom/RSS from pypi.org (20 items) |
| W1-AC8 providers, explicit UNAVAILABLE, no key leakage | MET in code; **search NOT VERIFIED live** (no keys; egress policy) | provider tests; key file for the worker (F2) |
| W1-AC9 duplicates / near-duplicates | MET | evaluation tests |
| W1-AC10 citation-backed, unsupported sentences dropped | **MET by construction for quantities (owner decision D7, 2026-10-11):** every answer sentence that states a quantity (digits, number words, fractions, ordinals, percentages, currencies, dates, weekdays) is shown as the cited source sentence word for word (quoted, one citation) or dropped (`NO_SOURCE_SENTENCE_TO_QUOTE`), so a value the sources do not state cannot be shown. Sentences without quantities keep the lexical check (one supporting sentence, polarity). Reason: four repairs of the lexical number check (R1-01 class) were each bypassed by a fresh reviewer (Indian grouping, swapped dates, signs, number words, currencies); the lifecycle stopped at RETRY_LIMIT and the owner chose verbatim quoting (`test_w1_d7_verbatim_numbers.py`). History of the lexical check, kept for audit: MET **as a lexical check** after the R6 repair (one supporting sentence, numbers with their magnitude/unit, compound numerals as one ordered value, polarity); not a semantic proof; number-to-referent binding NOT checked (L-W1-6) | verifier + F3 tests; `test_w1_r4_review_regressions.py`, `test_w1_r6_review_regressions.py`. **Correction (review R6 of `08a4569`):** the earlier MET was false for compound numerals — every numeral was reduced to an unordered set of digit groups, so a claim with a swapped ISO/slash/dash date (`2026-11-10` vs `2026-10-11`, `11/10/2026` vs `10/11/2026`), a reversed range (`10-20`, `from 100 to 200`), ratio (`3:1`), time (`10:30`) or fraction (`1/2`), or another month name (`10 November` vs `10 October 2026`) was kept. Earlier repairs (R1, R4, R5) patched only the reviewer's surface forms; the set model was the cause. A chain of numerals joined by `-`, `/`, `:`, an en/em dash, ` - ` or ` to ` is now one token in written order (dates canonicalised; D/M order kept as written), month-name dates are one value, and the class (every separator × swap) is tested. **Correction (review R4 of `1615512`):** numbers were compared without attached magnitudes (`$5bn` was "supported" by `$5m`; lakh/crore, trillion, km/miles likewise). Scales are now multiplied out and units kept; unlisted unit words after a space are still ignored (residual). |
| W1-AC11 conflicts with both citations | **Candidates, heuristic** (D7, 2026-10-11): conflicts are flagged from the structured number reader and shown with both citations; URI does not decide which source is right, and a missed conflict cannot put a wrong value into the answer (D7). Known misses: numbers written as words and currency-only differences (R8-02, R8-03). Earlier status, kept for audit: MET after the R6 repair (dates and other compound numerals; multi-value sentences: L-W1-6) | conflict tests incl. near-duplicate pages; R4-02 magnitude cases (`$5m` vs `$5bn`, `2 lakh` vs `2 crore` were 0 conflicts before); `test_w1_r6_review_regressions.py`. **Correction (review R6 of `08a4569`):** the earlier MET was false for a different date — two sources stating `2026-11-10` and `2026-10-11` (or `11/10/2026` and `10/11/2026`, or a reversed range/ratio/time) gave 0 conflicts because both read as the same digit set (see W1-AC10). |
| W1-AC12 prompt-injection resistance | MET for the paths tested (malicious page, feed, data-block escape, steering notes) | `test_malicious_page_cannot_redirect_the_pipeline` and F3 tests |
| W1-AC13 bounded background research, progress, cancel, fixed statuses | MET after the R4 repair (Brain synthesis itself not cancellable: L-W1-3) | pipeline/bridge tests, F1 deferred start; R4-03: cancel now cuts a fetch while headers/chunk framing drip (was CANCELLED only after 12 s, or never) |
| W1-AC14 read-only Mastodon/Bluesky | MET with fake HTTP; **live NOT VERIFIED** (egress policy denied the hosts) | social tests; `evidence/w1_live_proxy_egress_denied.json` |
| W1-AC15 A2UI rendering, no URLs, no new action | MET after the R6 repair |  surface tests; Dart renderer test; `test_w1_r6_review_regressions.py`. **Correction (review R6 of `08a4569`):** the earlier MET was false — conflict statements and source titles were rendered from raw page text: an instruction-like sentence with `www.` links and e-mail addresses appeared in the 'Sources disagree' card, and an instruction-like `og:title` with a `www.` link in the source list (the surface stripped only `scheme://`). Conflict statements now obey the answer's rules (no instruction-like or link/contact sentence), an instruction-like title is replaced by a notice, and every web-derived surface text has links, e-mail and IP addresses masked; the `host/path` citation label is kept. |
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
- **L-W1-6** (recorded at review R6) Numbers are checked per sentence as a set of whole values; a number is not bound
  to its referent. A source sentence `5% in 2025 and 10% in 2026` still "supports" a claim `10% in 2025`, and two
  sources whose multi-value sentences differ only in that pairing are not a conflict. `between 10 and 20` is not read as
  a range (`and` is too ambiguous), so it is not equated with `10-20`. An ambiguous numeric date is kept in written order
  (`11/10/2026` is never equated with `2026-10-11` or `2026-11-10`), and dotted dates (`11.10.2026`) are separate
  literals, so a claim in another notation is dropped (fails closed). Lexical, like L-W1-1.
- **SSRF-1 (pre-existing, frozen)**: `uri_core/tools/fetch_url.py` remains unsafe; owner decision.
