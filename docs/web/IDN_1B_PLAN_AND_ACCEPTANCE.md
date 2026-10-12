# IDN-1b: clearer block message, also in the chat fetch tool (owner decision D33)

Owner, 2026-10-12 (Q6): "ok yes make things clear that due to security reason, the website could not be opened in uri
however the same may be opened in an external browser (Rephrase)". Baseline: canonical `368188b7` (after IDN-1).

## Scope
- `uri_web/netpolicy.py` `NON_ENGLISH_MESSAGE` and `uri_web/surface.py` `blocked_note`: new wording (D18 brief):
  "For security reasons, URI did not open this site. Its address uses non-English letters, a trick scam sites use.
  You can open it in your web browser instead." Several sites: "... did not open N sites. Their addresses ... You can
  open them in your web browser instead."
- `uri_core/tools/fetch_url.py` (frozen; exception D33): one `_REFUSAL_MESSAGES` entry `HOST_NON_ENGLISH` ->
  `NON_ENGLISH_MESSAGE`, plus its import. Nothing else in `uri_core/` changes.
- IDN-1 review LOWs R1-03 / R2-01 (refused without the reason):
  - `check_url`: a host whose `%` escapes decode to non-ASCII is refused with `HOST_NON_ENGLISH`; other `%` hosts stay
    `HOST_INVALID`.
  - `safe_fetch`: a `_LocationTap` transport keeps the raw `Location` of a redirect; when httpx itself rejects the
    target (a full-width host), that Location is checked with `check_url` so the refusal keeps its code. The target is
    still never contacted; ordinary redirects are unchanged.

## Acceptance criteria
| # | Criterion |
|---|---|
| B-AC1 | The research note and the chat fetch tool give the D33 message (one site / several sites); D18 short sentences; no address. |
| B-AC2 | Only the one message entry and its import change in `uri_core/tools/fetch_url.py`. |
| B-AC3 | Percent-encoded non-English hosts give `HOST_NON_ENGLISH` on every route; ASCII-decoding `%` hosts stay `HOST_INVALID`. |
| B-AC4 | A redirect to a host httpx rejects is `REFUSED` with `HOST_NON_ENGLISH`, counted, never contacted; the job completes; normal redirects unchanged. |
| B-AC5 | Each change test in `tests/web/test_idn_1b.py` fails on `368188b7` and passes on the candidate (9 of 13; 4 guards hold on both); `tests/web/test_idn_1.py` is updated only for the new wording; `tests/web`, `tests/ssrf` and the root fetch_url tests pass. |

## Evidence (implementer, before independent review)
- `tests/web/test_idn_1b.py`: 13 passed on the candidate; on `368188b7` 9 failed, 4 passed (guards).
- `tests/web` + `tests/ssrf`: 3792 passed on the candidate.
- Root fetch_url tests (`test_m32_*`, `test_orchestrator_evidence_transport.py`, `test_m20_*`, `test_m19_office_readiness.py`)
  + `tests/ssrf`: 133 passed on both, with import-only placeholders for the Google client libraries not installed here.
