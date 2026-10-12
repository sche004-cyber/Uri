# IDN-1: block site addresses with non-English letters, and tell the user why (owner decision D21)

Owner, 2026-10-11: "Option 1. Also when a genuine site is blocked, uri should inform why the website was blocked."
O2 (owner, 2026-10-11): Hebrew vowel points on Hebrew letters are ordinary text.
Baseline: canonical `integration/git-sync-20261008` at `e761ce8f` (after SSRF-1 and GRAPHIFY-LEAK-1).

## Scope
- `uri_web/netpolicy.py` `check_url`: a host name with any character outside ASCII, or any `xn--` label, is refused
  with `HOST_NON_ENGLISH` before DNS. `check_url` runs for user URLs, every redirect hop (`safe_fetch`) and every
  search hit (`search._hit_refusal`), so all routes are covered. Full-width digits that spell an IP address keep
  `HOST_NUMERIC_AMBIGUOUS` (checked first).
- `uri_web/search.py`: hits refused this way are dropped and counted (`SearchResult.blocked_non_english`).
- `uri_web/pipeline.py`: `ResearchResult.blocked_non_english` = blocked search hits + refused user URLs, feeds and
  redirect targets.
- `uri_web/surface.py`: one plain note in the research result (D18), without the address:
  "Blocked: this site's address uses non-English letters. Scam sites use them to copy real sites. If you trust it,
  open it yourself in your browser." (for several sites: "Blocked N sites: their addresses use ...").
- O2, `uri_web/untrusted.py` `_unusual`: HEBREW POINT SHIN DOT / SIN DOT on a Hebrew letter (other Hebrew points may
  sit between) count as Hebrew, not as an unusual dot. Alone or on a letter of another script they stay unusual.
- No allow-list or override (a separate owner decision if ever wanted).

## Not in scope (frozen)
`uri_core/tools/fetch_url.py` (the chat fetch tool) is under the frozen `uri_core/`; its SSRF-1 exception (D2) does not
cover IDN-1. The tool already refuses these hosts (it uses `check_url`) but says only "URI refused to fetch that URL."
Adding the plain reason there needs an owner decision (asked separately); it is not changed here.

## Acceptance criteria
| # | Criterion |
|---|---|
| IDN-AC1 | `check_url` refuses `http://раураl.com/`, `http://xn--80ak6aa92e.com/`, `http://bücher.de/`, `http://例え.jp/`, an `xn--` top-level label, upper-case `XN--` and a zero-width character in the host with `HOST_NON_ENGLISH`; ASCII hosts (including `xn.example.com`, `axn--b.example.com`) and IP literals are unchanged. |
| IDN-AC2 | A search hit with such a host is dropped and counted; a user URL and a redirect to such a host are refused and recorded; such a host is never contacted; the job still completes with the other sources (no INTERNAL_ERROR). |
| IDN-AC3 | The research result shows the plain note once when any site was blocked (one or several, with or without other sources), validates against the A2UI catalog, and contains no address; no note when nothing was blocked. |
| IDN-AC4 | The note follows D18: short sentences, plain words. |
| IDN-AC5 | O2: pointed Hebrew is not masked; a point alone, on another script's letter or between a name and an ending is still a link. |
| IDN-AC6 | Each change test in `tests/web/test_idn_1.py` fails on `e761ce8f` and passes on the candidate (16 of 27; the other 11 are guards that hold on both); `tests/web` and `tests/ssrf` pass; the root fetch_url tests give the same result on both. |

## Evidence (implementer, before independent review)
- `tests/web/test_idn_1.py`: 27 passed on the candidate; on `e761ce8f` 16 failed, 11 passed (all guards).
- `tests/web` + `tests/ssrf`: 3770 passed.
- Root tests touching fetch_url (`test_m32_capability_effect_classification.py`, `test_orchestrator_evidence_transport.py`,
  `test_m20_skill_discovery_boundary.py`, `test_m19_office_readiness.py`, `test_m20_research_recovery.py`): 68 passed
  on both, with import-only placeholders for the Google client libraries that are not installed here.

## Known cost
Genuine sites whose address uses non-English letters (`.рф`, `.中国`, `bücher.de`) cannot be opened by URI; the user is
told why and can open them in a browser. Supersedes SSRF-1 R2-01 (IDN hosts could not be fetched: the pin compared the
wrong form) — they are now refused on purpose, with a reason.
