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

## Added scope (owner, 2026-10-11, D26): Security tab for the key
- A new **Security** tab in URI settings with a field to add the URLhaus key, so the owner never edits `.env` by hand.
- **Frozen exception (owner-approved, tab entry only):** `uri_ui/lib/screens/settings/settings_shell.dart` gets only
  the entry that shows the new tab. The tab itself is a new file (`uri_ui/lib/screens/settings/security_screen.dart`).
  No other frozen file changes; set `authorized_protected_changes` to that one path.
- **Key handling:** sent once to the local URI server over the existing authenticated local connection and stored
  in the local secrets file readable only by the current user (same place as `URLHAUS_AUTH_KEY`). Never shown again
  (only "Key saved"; see D27), never logged, never sent anywhere but URLhaus. Buttons: Save,
  Remove, Test (one lookup of a known-safe address, plain result).
- Status line in plain words: "Scam check: on" / "Scam check: off (no key) - URI still works, sites are not
  scam-checked" / "Scam check: service unavailable".

| # | Criterion |
|---|---|
| LR-AC6 | The Security tab saves, tests and removes the key; the key is never displayed (D27), logged, or included in reports, events or A2UI output. |
| LR-AC7 | Only `settings_shell.dart`'s tab entry changes among frozen files (driver protected-path check). |
| LR-AC8 | Flutter tests cover the tab: empty state, saved state (no characters shown), remove, test result, and the off/unavailable status lines. |

## Added scope (owner, 2026-10-11, D27): Tavily key slot
- The Security tab also has a **Tavily search key** slot (W1 web search, today read from `.env` per D3).
- Same handling for both keys, tightened for the standing rule "never expose the Tavily key value": after saving,
  the tab shows only "Key saved" (no characters at all), for both keys. Save, Remove, Test (one small search for
  Tavily; one known-safe lookup for URLhaus), plain results.
- Precedence: a key saved in the tab is used; otherwise the existing `.env` value (D3) keeps working unchanged.
  Removing a key in the tab never edits `.env`.
- Status line for search: "Web search: on" / "Web search: off (no key)".

| # | Criterion |
|---|---|
| LR-AC9 | Both slots save, test and remove; neither key is ever displayed (not even partly), logged, or included in reports, events or A2UI output. |
| LR-AC10 | With no tab key, W1 still reads TAVILY_API_KEY from `.env` exactly as before (existing D3 tests pass unchanged). |

## Note (D28)
The Security tab, key storage and `.env` import are built in SETTINGS-1, which runs first. LINK-REP-1 only wires the URLhaus slot to the check.
