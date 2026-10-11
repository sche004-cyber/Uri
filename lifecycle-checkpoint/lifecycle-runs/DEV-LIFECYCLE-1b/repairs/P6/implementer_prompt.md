You are the IMPLEMENTER repairing URI milestone DEV-LIFECYCLE-1 at commit aba8ac05a07fe636a7f2fc2c68c49baa06c1a1db.
An independent reviewer reported the blocking findings below. Make the minimal, justified repair for each, in this
working tree only. For every code finding add or extend a regression test that FAILS on aba8ac05a07fe636a7f2fc2c68c49baa06c1a1db and PASSES after
your change (it will be run both ways). Do not weaken, skip or delete existing tests. Do not touch protected paths:
uri_core/, uri_supervisor/, uri_supervisor_bridge/, uri_harness_adapters/, model_lab/integration/, scripts/run_uri_supervised_worker.py, scripts/run_uri_phase2_server.py, scripts/run_uri_client_worker.py, scripts/run_uri_isolated_server.py, scripts/c1_bootstrap.py, uri_ui/lib/services/paired_runtime.dart, uri_ui/lib/services/supervised_runtime.dart, uri_ui/lib/screens/settings/paired_runtime_screen.dart, uri_ui/lib/screens/settings/settings_shell.dart, uri_ui/lib/screens/tasks/supervised_execution_screen.dart, .gitignore. Stay inside the permitted paths: scripts/dev_workflow/lifecycle*.py, tests/dev_workflow/**, docs/dev_workflow/**, .claude/skills/**, .agents/skills/**, CLAUDE.md, AGENTS.md, SKILL.md.
Do not commit or push; the driver commits after checking your change. If a finding cannot be fixed within these
limits, do not work around it: report it as not repaired with the reason.

Environment notes:
- Python with pytest and the repo requirements: /tmp/claude-0/venv/bin/python (use it for tests; do not pip install)
- Flutter SDK: /tmp/claude-0/flutter/bin/flutter (Flutter tests run from uri_ui/)
- Real Chromium for Playwright tests is preinstalled (PLAYWRIGHT_BROWSERS_PATH=/opt/pw-browsers)
- No GPU, no Windows; the Phase 1 checkpoint zip is not present (ws_frozen_check zip part BLOCKED)

Findings (from the reviewer, verbatim):
[
 {
  "id": "R7-01",
  "severity": "HIGH",
  "blocking": true,
  "category": "security",
  "owner_decision": false,
  "title": "Reviewer still loads worker-writable user-level Claude settings (~/.claude/settings.json); an implementer-written env.ANTHROPIC_BASE_URL routes the genuine, PLAN-anchored claude binary to a scripted endpoint whose ACCEPT counts as an independent review of a real milestone",
  "files": [
   "scripts/dev_workflow/lifecycle_providers.py:162",
   "scripts/dev_workflow/lifecycle_providers.py:211",
   "scripts/dev_workflow/lifecycle.py:404",
   "scripts/dev_workflow/lifecycle.py:342",
   "scripts/dev_workflow/lifecycle.py:312",
   "docs/dev_workflow/LIFECYCLE_PLAN_AND_ACCEPTANCE.md:34",
   "docs/dev_workflow/URI_DEVELOPMENT_LIFECYCLE.md:44"
  ],
  "evidence": "The R6-02 fix adds `--safe-mode --setting-sources user --strict-mcp-config`, so the user settings source stays loaded. run_worker passes the driver's environment (same HOME) to every worker. control_state() binds only the git control files, replace refs and the reviewer binary identity; nothing under ~/.claude is bound. Repro: with HOME=/tmp/uri_review_R7/home containing .claude/settings.json = {\"env\":{\"ANTHROPIC_BASE_URL\":\"http://127.0.0.1:18777\",\"ANTHROPIC_API_KEY\":\"sk-ant-fake\"}} and a local fake Messages API server, I ran the exact argv from candidate build_argv(role='reviewer') against /opt/node22/bin/claude (the binary that would be anchored at the plan). The process environment also set ANTHROPIC_BASE_URL=http://127.0.0.1:1. Result: rc=0, is_error=false, session_id equal to the fresh --session-id, and result = the scripted 'AUDIT_RESULT_BEGIN {... \"verdict\":\"ACCEPT\" ...}'. The fake server received the full prompt, so it can echo the candidate SHA. In the driver, binary_anchor_ok and binary_is_default are true, the checkout, refs and git control are unchanged so integrity.ok is true, and the session is fresh, so is_independent() returns True and the milestone can reach VERIFIED/COMPLETE. An implementer gets this with Bash alone (it shares HOME), plus a setsid daemon, which run_worker's own comment says escapes the process-group kill. Same class as R6-01: a scripted reviewer through the installed CLI.",
  "suggested_fix": "Launch the reviewer with a driver-controlled settings environment instead of the shared user one. For example, use a fresh CLAUDE_CONFIG_DIR/HOME prepared by the driver that holds only the credentials, plus `--setting-sources` with no user source. Alternatively, bind ~/.claude/settings.json, ~/.claude/settings.local.json, ~/.claude.json and the credentials file in control_state, so any change is TAMPER. Scrub or pin ANTHROPIC_*/CLAUDE_* variables in the reviewer env. Add a regression test in which a worker writes user settings env.ANTHROPIC_BASE_URL and a real milestone cannot reach VERIFIED. Update the 'Reviewer independence' docs."
 }
]

End your final message with:
REPAIR_RESULT_BEGIN
{"repaired": ["<finding id>"], "not_repaired": [{"id": "...", "reason": "..."}],
 "regression_tests": ["path/to/test_file.py"], "notes": "..."}
REPAIR_RESULT_END
