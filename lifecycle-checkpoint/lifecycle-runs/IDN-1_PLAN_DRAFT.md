# IDN-1: block site addresses with non-English letters, and tell the user why (owner decision D21)

Owner, 2026-10-11: "Option 1. Also when a genuine site is blocked, uri should inform why the website was blocked."
Branch cut from the canonical tip after SSRF-1. Run through the lifecycle skill (independent review, then D1).

## Scope
- `uri_web/netpolicy.py` `check_url`: refuse a host with any non-ASCII letter or any ACE label (`xn--`), before DNS and
  for every route: user URLs, search hits, redirects. New refusal code `HOST_NON_ENGLISH`.
- Brief, plain message (D18) shown wherever the refusal surfaces: the research source card / attempts list and the
  answer note. Text: "Blocked: this site's address uses non-English letters. Scam sites use them to copy real sites.
  If you trust it, open it yourself in your browser." The message never shows the raw address as a link.
- No allow-list or override in this milestone (an owner-approved exception list would be a separate decision).

## Acceptance criteria
| # | Criterion |
|---|---|
| IDN-AC1 | `check_url` refuses `http://раураl.com/`, `http://xn--80ak6aa92e.com/`, `http://bücher.de/`, `http://例え.jp/` with `HOST_NON_ENGLISH`; ASCII hosts are unchanged. |
| IDN-AC2 | A redirect to such a host and a search hit with such a host are refused the same way; the job still completes with the other sources (no INTERNAL_ERROR). |
| IDN-AC3 | The user sees the plain message above for each blocked site, in the research surface and its A2UI output; the address is not clickable. |
| IDN-AC4 | Messages follow D18: one or two short sentences, plain words. |
| IDN-AC5 | Each new test fails on the pre-change commit and passes on the candidate; all web tests pass. |

## Known cost
Genuine sites whose address uses non-English letters (e.g. `.भारत`, `.中国`) cannot be opened by URI; most also have an
English-letter address. Supersedes R11-06 (IDN hosts could not be fetched anyway: the pin compared the wrong form).

## Added scope (owner, 2026-10-11, O2)
Hebrew points on Hebrew letters (e.g. 'שָׁלוֹם', HEBREW POINT SHIN DOT / SIN DOT) are not treated as dot-like by the D15 allow-list; a point standing alone, or on a letter of another script, is still caught. Test: pointed Hebrew reads normally; 'portal \u05c1 com' and 'portal c\u05c1om' stay links.
