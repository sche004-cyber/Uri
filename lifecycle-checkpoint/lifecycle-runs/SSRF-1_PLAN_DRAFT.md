# SSRF-1 — plan and acceptance criteria (DRAFT, not started)

Status: DRAFT written 2026-10-11 while W1/A0 round 9 review runs. Implementation starts only after W1/A0 is in
canonical (W1's SafeFetcher must be on the base). Authority: owner decision D2 (narrow repair of frozen
`uri_core/tools/fetch_url.py`, isolated branch, security + regression tests, independent review, controlled
integration under D1). Lifecycle config: `authorized_protected_changes: ["uri_core/tools/fetch_url.py"]` only.

## Defect (pre-existing, canonical)

`FetchUrlTool.execute` calls `requests.get(url, stream=True)` with default redirect following and no address checks
(`fetch_url.py` ~L125). A URL in the user/goal text — or a public page that redirects — reaches loopback, private
ranges, link-local/metadata (169.254.169.254), the key-less Runtime v1 endpoint, etc. DNS rebinding is also open.

## Design (smallest change, reuse W1)

1. `fetch_url.py` stops using `requests` for the network hop and fetches through `uri_web.safe_fetch.SafeFetcher`
   (per-hop `netpolicy.check_url`, resolve once, refuse if ANY answer is non-public, pinned connection, redirects
   handled and re-checked per hop, byte cap, total deadline, no env proxies/cookies/credentials).
2. Gap found while planning: SafeFetcher only returns bodies for text kinds (`TEXT_TYPES`); PDF/DOCX/XLSX/CSV come back
   `UNSUPPORTED_CONTENT_TYPE` with no body, but `fetch_url` must keep reading those. Smallest fix: an optional
   SafeFetcher constructor argument `extra_types` (mime → kind, default empty) so existing W1 behaviour is byte-for-byte
   unchanged; `fetch_url` passes its five document types with kind `"document"`. (`uri_web/` is not frozen.)
3. Behaviour kept: no model-supplied URL (regex on request_text only), http(s) only, 10 MB cap, 15 s budget, same
   output dict keys/statuses (`success`, `input_required`, `unavailable`, `empty`, `unsupported`, extraction dict for
   documents), same HTML-to-text parser, same 8000-char truncation.
4. Behaviour changed (intended): refused targets return `status: "unavailable"` with message "URI will not fetch that
   address (private or local network)." and a `refusal_code` (from netpolicy) — no address, body or error detail of the
   internal target. Redirects: at most 5, each re-checked.
5. robots.txt: not applied (`honour_robots=False`) — `fetch_url` is a single user-directed read, not a crawler; this
   matches current behaviour. Recorded as an explicit choice for review.
6. Egress mode: `direct` (production). Proxy mode only via explicit config, never from env.
7. Restriction until qualified (D2): `fetch_url` stays as is in grants until the milestone is accepted; no widening.

## Acceptance criteria

- S-AC1  Refused with no connection attempted: loopback (127/8, ::1, localhost, *.localhost), RFC1918, CGNAT,
         link-local + 169.254.169.254, unspecified, multicast, IPv4-mapped/embedded IPv6, decimal/octal/hex host forms,
         userinfo, non-allowed ports, non-http(s) schemes.
- S-AC2  A public URL redirecting (301/302/303/307/308) to any S-AC1 target is refused at that hop; nothing is sent there.
- S-AC3  DNS answer with ANY non-public address is refused; connection goes to the validated address only (rebinding).
- S-AC4  `requests` is no longer used for the network hop in `fetch_url.py` (static check + test with `requests`
         patched to raise).
- S-AC5  Existing outputs unchanged for public HTML, text, PDF/DOCX/XLSX/CSV, empty page, HTTP error, unsupported type,
         oversize (>10 MB), no URL, ftp:// (existing tests in test_m19/test_m20/test_orchestrator_evidence_transport pass).
- S-AC6  W1 unchanged by default: all W1/A0 tests pass; `extra_types` defaults to none.
- S-AC7  Each security test fails on the pre-repair commit and passes after (lifecycle regression proof).
- S-AC8  Only `uri_core/tools/fetch_url.py` among frozen files changes; frozen-file integrity check passes.
- S-AC9  Independent separate-process ACCEPT on the exact commit; combined gates no new failures vs baseline; D1 merge
         with integration receipt.
- S-AC10 Live public fetch: NOT VERIFIED in the cloud container if egress blocks it; marked as such, does not block.

## Open points for the reviewer (not owner decisions)

robots choice (item 5); refusal message wording; whether `session=` injection parameter (unused by tests) is kept as a
transport injection for tests or removed.
