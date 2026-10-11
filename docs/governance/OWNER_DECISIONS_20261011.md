# Owner decision ledger — 11 October 2026

Source: the owner's message "URI — Owner Decisions: All Six Resolved (11 October 2026)" in Claude Code session
`session_01P2p3uVP5b87uL5UMyWApaJ`. Recorded verbatim in substance; the owner asked not to be asked again for these
six approvals unless a new action exceeds the authorised scope. Production deployment / cutover remains separately
owner-authorised and is NOT covered by any decision below.

| # | Decision | Authorised scope | Boundaries | How it is applied |
|---|---|---|---|---|
| D1 | Canonical integration | Conditional integration into `integration/git-sync-20261008` | Only after an independent ACCEPT on the exact candidate commit, all blocking findings resolved, provenance verified, frozen-file integrity checked and combined regression gates passed; an integration receipt is generated. No production cutover | lifecycle integration policy `mode: merge`, `authorized: true` (the driver still refuses without its evidence checks); receipts in each milestone's lifecycle state |
| D2 | SSRF-1 repair in frozen `uri_core/tools/fetch_url.py` | Narrow security repair in an isolated branch/worktree | Only changes needed for SSRF-1; security + regression tests; independent review; controlled integration; the vulnerable capability stays restricted until qualified | separate milestone `SSRF-1`, `authorized_protected_changes: ["uri_core/tools/fetch_url.py"]` only |
| D3 | Tavily credential | Reuse the key in the `.env` of the URI development folder for W1 | Never expose the value in logs, Git, reports or chat; no per-search login; verify live search when the environment is available | W1 reads `TAVILY_API_KEY` from `.env` (same convention as `uri_core/tools/web_search.py`); the value is never stored or returned. Live search: NOT VERIFIED until run where the `.env` exists |
| D4 | Windows/GPU live verification | Agents may attempt live Runtime, Assist and Vision verification on the owner's PC | Existing permissions and GPU lease controls; no bypass of owner gates; no interference with parallel sessions; failures/unavailable = NOT VERIFIED | not reachable from the cloud session: NOT VERIFIED; runbook in `docs/assist/OWNER_RETURN_CHECKLIST.md` items 5-7 |
| D5 | Assist adapters (browser, Windows UI Automation, screen capture) | Phased development and integration | Remembered, revocable, application-scoped permissions with expiry; observation and suggestions first; sensitive actions need explicit authorisation; software installation, elevated privileges and new sensitive OS permissions need separate approval; no silent capture, no sensitive-data learning, no autonomous form submission | recorded; phased plan to be written as its own milestone; no adapter work started in this session |
| D6 | Skill location | Keep the Automated Independent Audit & Repair skill under `.claude/` | Force-add only approved skill files; the frozen `.gitignore` stays unchanged; independent acceptance before canonical integration | `.claude/skills/uri-development-lifecycle/SKILL.md` force-added; `.gitignore` unchanged |

## Effect on earlier records

- `docs/assist/OWNER_RETURN_CHECKLIST.md` items 1 (Codex audit), 2-4 and 8-10 are superseded or answered by D1-D6
  where they overlap; that file is kept as history.
- Earlier statements that "nothing is integrated without a Codex ACCEPT" are superseded by the owner directive of
  2026-10-11 (Codex optional) and D1 (independent separate-process ACCEPT on the exact commit).
