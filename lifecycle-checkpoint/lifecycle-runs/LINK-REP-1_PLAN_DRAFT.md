# LINK-REP-1: known-scam check for real web addresses, plus scam red flags (owner decision D22)

Owner, 2026-10-11: "Yes" to LINK-REP-1 (after the proposal: check real addresses against known-scam lists, add
urgency and mismatched-link flags; sends addresses to an outside service). Branch from the canonical tip after IDN-1.
Run through the lifecycle skill (independent review, then D1).

## Scope
1. **Known-scam lookup** for every address URI is about to fetch (user URL, search hit, redirect) and every real
   address found in a source. Provider chosen at plan time; candidates: abuse.ch URLhaus (free key), Google Web Risk
   (paid key). Only the address is sent (no page text, no user data). A listed address is refused before any fetch.
2. **Added security, never a blocker (owner, 2026-10-11, D25):** with no key, or when URLhaus is down or slow, URI
   works exactly as it does today (all existing protections stay: link masking, IDN-1, egress checks) and the
   source shows a short note: "Not scam-checked: the scam-list service was unavailable." A site is refused only when
   URLhaus positively lists it. The lookup has a short time limit so it never slows research noticeably.
3. **Red flags** added to the existing source flags: urgency phrases ("act now", "urgent action required", "account
   suspended"), link text that differs from its real destination, number-heavy or very long hosts. Flagged sources
   are shown with a short warning and ranked lower; they are never the only support for a claim.
4. **Plain message (D18)** when a site is blocked: "Blocked: this site is on a known-scam list." / "Not checked: the
   scam-list service was unavailable, so this site was skipped."

## Owner inputs
- Provider: **abuse.ch URLhaus** (owner, 2026-10-11). Key name in `.env`: `URLHAUS_AUTH_KEY`, placed by the owner;
  never shown or logged. The milestone is built and tested without it (a fake URLhaus in tests); the key only turns
  the live check on.
- Lookup unavailable: **continue without it**, with the plain note (owner D25, replacing the earlier "skip" default).

## Acceptance criteria (draft)
| # | Criterion |
|---|---|
| LR-AC1 | A listed address is refused before DNS/fetch on every route; the job completes with the other sources. |
| LR-AC2 | Only the normalised address leaves the machine; a test inspects the outgoing request. The key never appears in logs, events or reports. |
| LR-AC3 | No key, an error or a timeout never blocks research: the source is used as today with the 'Not scam-checked' note; only a positive listing blocks. |
| LR-AC4 | Red-flag phrases and mismatched links are flagged; a flagged source cannot be a claim's only support. |
| LR-AC5 | Messages follow D18. Each new test fails on the pre-change commit and passes on the candidate. |
