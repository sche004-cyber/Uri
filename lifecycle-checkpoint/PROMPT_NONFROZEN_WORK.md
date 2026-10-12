# Prompt: URI work that needs no frozen-code change (drafted 2026-10-12)

Work on the URI repository (canonical: https://github.com/sche004-cyber/Uri, branch `integration/git-sync-20261008`).
Read first: `lifecycle-checkpoint/AWAY_MODE.md`, `lifecycle-checkpoint/OWNER_ACTIONS.md` and the plan drafts in
`lifecycle-checkpoint/lifecycle-runs/` on branch `ccr-cab5ed06-9hwyc4`.

## Hard rule for this prompt
Change NO frozen file. Frozen: everything under `uri_core/`, `uri_supervisor/`, `uri_supervisor_bridge/`,
`uri_harness_adapters/`, `model_lab/integration/`; `scripts/run_uri_supervised_worker.py`,
`scripts/run_uri_phase2_server.py`, `scripts/run_uri_client_worker.py`, `scripts/run_uri_isolated_server.py`,
`scripts/c1_bootstrap.py`; `uri_ui/lib/services/paired_runtime.dart`, `uri_ui/lib/services/supervised_runtime.dart`,
`uri_ui/lib/screens/settings/paired_runtime_screen.dart`, `uri_ui/lib/screens/settings/settings_shell.dart`,
`uri_ui/lib/screens/tasks/supervised_execution_screen.dart`; `.gitignore`. Set `authorized_protected_changes: []` in
every lifecycle config. If a task turns out to need a frozen file, stop that part, record it in OWNER_ACTIONS.md as
a question, and move on.

## Work, in this order (each through the `uri-development-lifecycle` skill: plan with acceptance criteria first,
implement in its own worktree, independent review, D1 integration)
1. **LINK-REP-1** (D22, D25): known-scam check (URLhaus) plus urgency and mismatched-link flags. Without the Settings
   tab: read an optional `urlhaus_api_key` from the existing hand-placed `<client_root>/control/web/search_keys.json`;
   no key or service down = check skipped, never a blocker. The key is never shown, logged or returned.
2. **IDN-2** (D34, D35; after LINK-REP-1): open a blocked non-English address by the user's choice, in restricted
   mode, per `IDN-2_PLAN_DRAFT.md`, with A2UI buttons "Close (recommended)" and "Proceed" (Proceed only when the scam
   check ran and the copy check passed). Leave out the "Sites you opened anyway" list in Settings > Security (needs
   SETTINGS-1, parked on Q7); the 24-hour expiry still applies.
3. **ONBOARD-1**: first-use explainer cards, per `ONBOARD-1_PLAN_DRAFT.md` (reopen entry in a non-frozen Help screen).
4. **W2a, then W2b**, per `W2_PLAN_AND_ACCEPTANCE.md`, but WITHOUT the D11 Graphify document pointers
   (`uri_core/core/graphify_index.py`, `decision_engine.py`): move those to a later W2a-G milestone and mark the
   affected criteria as deferred, not passed.
5. Small follow-ups (one milestone each, or batched where the files are the same):
   - IDN-1c: the two IDN-1b LOW findings (known limitation L6).
   - SSRF-GZIP-1 and the other SSRF-1 LOWs in `uri_web/` (gzip reported as unsupported, UTF-8 charset default,
     extra_types vs robots, numeric-ambiguous wording).
   - DEV-LIFECYCLE-3: add the D18 brief-summary rule to the lifecycle skill.

## Not in this prompt (need the owner)
SETTINGS-1a/1b (Q7), known limitations L1-L5, GRAPHIFY-SKILL-1 (`server.py`), W2 Graphify pointers, Codex setup (A5).

## Standing rules
D5 (no silent capture, no sensitive-data learning, no autonomous form submission); no new dependencies, OS
permissions or production cutover; never show or log any key; D18 brief plain summaries; never weaken gates,
suppress findings or self-approve; never push to integration/milestone/research/master yourself (the driver
integrates per D1); never edit `.gitignore` or `~/.gitconfig`. After each milestone: send REPORT.html with stage,
what was done and what needs the owner, and update AWAY_MODE.md and OWNER_ACTIONS.md. Use Codex for reviewer and
implementer if it is installed and keyed (D32); otherwise Claude, and say so.
