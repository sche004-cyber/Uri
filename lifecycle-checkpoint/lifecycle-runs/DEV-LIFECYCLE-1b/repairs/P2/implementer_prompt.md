You are the IMPLEMENTER repairing URI milestone DEV-LIFECYCLE-1 at commit 39ed499bd6a6b836a317ac422ad2a180330e67f1.
An independent reviewer reported the blocking findings below. Make the minimal, justified repair for each, in this
working tree only. For every code finding add or extend a regression test that FAILS on 39ed499bd6a6b836a317ac422ad2a180330e67f1 and PASSES after
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
  "id": "R3-01",
  "severity": "MEDIUM",
  "blocking": true,
  "category": "security",
  "owner_decision": false,
  "title": "Config allowlist added in 39ed499 hides worker-written remote.*.fetch refspecs, which the driver's integration fetch then uses to force-overwrite other local branches of the main repository",
  "files": [
   "scripts/dev_workflow/lifecycle.py:325",
   "scripts/dev_workflow/lifecycle.py:1181",
   "scripts/dev_workflow/lifecycle.py:1143"
  ],
  "evidence": "_ROUTINE_CONFIG excludes remote.<r>.fetch/prune/mirror and branch.* from git_control_digest. integrate() runs `git fetch -q <remote> <target>`, and git updates the configured remote-tracking destination for the fetched ref. Probe /tmp/uri_review_R3/probe_fetch.py on the test fixture: the implementer worker runs `git -C <repo> config --add remote.origin.fetch +refs/heads/canon:refs/heads/session-b` and makes the real fix. Result at 39ed499: run() == COMPLETE, integration INTEGRATED, verify() == [], and refs/heads/session-b (another session's branch, with its own commit 3ee1d50) is force-moved to the baseline 16d4165. The same probe at 1f720ed (probe_fetch_old.py) stops BLOCKED with TAMPER 'git hooks or config changed during the repair', and session-b is untouched. The anchored control state (R1-04) and do_repair's ctl0 check both miss the change now. remote.<r>.mirror is also excluded; it makes the integration push fail (DoS only).",
  "suggested_fix": "Remove remote.*.fetch (and mirror/prune/tagopt) from _ROUTINE_CONFIG, or at least run integrate's fetch with `--refmap=` (no opportunistic ref updates) and an explicit no-destination refspec, and add a regression test in which a worker-written fetch refspec is either TAMPER or provably cannot move any local ref. Keep the doc in sync."
 }
]

End your final message with:
REPAIR_RESULT_BEGIN
{"repaired": ["<finding id>"], "not_repaired": [{"id": "...", "reason": "..."}],
 "regression_tests": ["path/to/test_file.py"], "notes": "..."}
REPAIR_RESULT_END
