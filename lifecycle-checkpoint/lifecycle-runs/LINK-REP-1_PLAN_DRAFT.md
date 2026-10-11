# LINK-REP-1: known-scam check for real web addresses, plus scam red flags (owner decision D22)

Owner, 2026-10-11: "Yes" to LINK-REP-1 (after the proposal: check real addresses against known-scam lists, add
urgency and mismatched-link flags; sends addresses to an outside service). Branch from the canonical tip after IDN-1.
Run through the lifecycle skill (independent review, then D1).

## Scope
1. **Known-scam lookup** for every address URI is about to fetch (user URL, search hit, redirect) and every real
   address found in a source. Provider chosen at plan time; candidates: abuse.ch URLhaus (free key), Google Web Risk
   (paid key). Only the address is sent (no page text, no user data). A listed address is refused before any fetch.
2. **Fail closed, visibly:** if the lookup is unavailable, the source is fetched only if the owner setting allows it;
   default is to skip it with a plain note.
3. **Red flags** added to the existing source flags: urgency phrases ("act now", "urgent action required", "account
   suspended"), link text that differs from its real destination, number-heavy or very long hosts. Flagged sources
   are shown with a short warning and ranked lower; they are never the only support for a claim.
4. **Plain message (D18)** when a site is blocked: "Blocked: this site is on a known-scam list." / "Not checked: the
   scam-list service was unavailable, so this site was skipped."

## Owner inputs needed before the run
- Which provider, and its API key placed in `.env` by the owner (never shown or logged).
- Whether "lookup unavailable" should skip (default) or allow the source.

## Acceptance criteria (draft)
| # | Criterion |
|---|---|
| LR-AC1 | A listed address is refused before DNS/fetch on every route; the job completes with the other sources. |
| LR-AC2 | Only the normalised address leaves the machine; a test inspects the outgoing request. The key never appears in logs, events or reports. |
| LR-AC3 | Lookup failure follows the owner setting; the default skips with the plain note. |
| LR-AC4 | Red-flag phrases and mismatched links are flagged; a flagged source cannot be a claim's only support. |
| LR-AC5 | Messages follow D18. Each new test fails on the pre-change commit and passes on the candidate. |
