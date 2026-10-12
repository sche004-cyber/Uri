# IDN-2: open a blocked site anyway, in restricted mode (owner decision D34, plan adopted 2026-10-12 "Ok")

Runs after LINK-REP-1 (needs its scam-check provider). Through the lifecycle skill (independent review, then D1).

## When the user may open a blocked site
All must hold, else the site stays blocked (fail closed):
1. LINK-REP-1 scam check ran and the site is not listed (provider unreachable => no option).
2. Copy check: each label is a single script and its skeleton (Unicode confusables, `uri_web/confusables_ascii.py`)
   does not match an ASCII address; a copy is refused outright, no option.
3. The user sees the address in ASCII form plus the reason and taps "Open anyway". Per site only; a redirect to
   another non-English address asks again.

## Restricted mode
Applies to sites opened this way, and to sites LINK-REP-1 marks suspicious (urgency, mismatched links). A listed scam
site or a copy of a real address is never offered it.
- Read only on request: fetched only when the user taps "Read this page"; never in background research, from search
  results, or by refresh.
- Text only: no scripts, images or media; RW1 rendered web / WebView2 never used.
- Same page: no following links or redirects to other hosts without asking again.
- Blocked: forms, logins, cookies, clicks, agent actions, downloads, attachments, saved copies.
- Nothing from it goes into memory or skills, or is used as evidence for other questions; no personal data sent.
- Shown in a marked "Restricted" frame with the ASCII address; links inside hidden.
- Summary only when the user asks, marked "from a site you chose to open; not verified".
- Choice lasts 24 hours per site; removable from "Sites you opened anyway" in Settings > Security (SETTINGS-1).
- Every choice and every read is logged.

## Acceptance criteria (draft; finalised at milestone start)
| # | Criterion |
|---|---|
| IDN2-AC1 | No "Open anyway" unless checks 1-2 pass; provider down, listed or copy => blocked, no option. |
| IDN2-AC2 | Restricted fetch only on an explicit user action; never from research, search, refresh. |
| IDN2-AC3 | Every blocked capability above is refused in restricted mode (tests per item). |
| IDN2-AC4 | Nothing from a restricted site reaches memory, skills or other answers. |
| IDN2-AC5 | Choice is per site, expires after 24 h, is removable, and is logged. |
| IDN2-AC6 | UI text D18-brief; A2UI-valid; no clickable address. |
