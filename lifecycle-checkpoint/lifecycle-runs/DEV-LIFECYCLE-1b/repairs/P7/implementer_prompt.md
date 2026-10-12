You are the IMPLEMENTER repairing URI milestone DEV-LIFECYCLE-1 at commit e029675cc9f229596af26365277f2ae536be232b.
An independent reviewer reported the blocking findings below. Make the minimal, justified repair for each, in this
working tree only. For every code finding add or extend a regression test that FAILS on e029675cc9f229596af26365277f2ae536be232b and PASSES after
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
  "id": "R8-01",
  "severity": "HIGH",
  "blocking": true,
  "category": "security",
  "owner_decision": false,
  "title": "R7-01 config isolation is a post-run end-state check: a lingering setsid worker child injects env.ANTHROPIC_BASE_URL into the fresh reviewer CLAUDE_CONFIG_DIR, removes it after CLI startup, and the scripted ACCEPT is recorded with config_isolated=true",
  "files": [
   "scripts/dev_workflow/lifecycle_providers.py:213",
   "scripts/dev_workflow/lifecycle_providers.py:246",
   "scripts/dev_workflow/lifecycle_providers.py:292",
   "scripts/dev_workflow/lifecycle_providers.py:326",
   "scripts/dev_workflow/lifecycle.py:315",
   "docs/dev_workflow/URI_DEVELOPMENT_LIFECYCLE.md:44",
   "docs/dev_workflow/URI_DEVELOPMENT_LIFECYCLE.md:79"
  ],
  "evidence": "reviewer_config_dir() creates /tmp/uri-reviewer-claude-* (predictable prefix, same user as the workers). config_dir_clean() only inspects the directory after the run. Probe /tmp/uri_review_R8/p1: daemon.py calls os.setsid() (escapes _killpg, an accepted threat per URI_DEVELOPMENT_LIFECYCLE.md section 6), polls the temp dir, writes {env:{ANTHROPIC_BASE_URL:http://127.0.0.1:18777, ANTHROPIC_API_KEY:...}} into .claude.json, then removes the key after HOLD seconds. probe.py calls run_worker({provider: claude_cli, _anchor: reviewer_executable(...)}, 'reviewer', ...) on the real /opt/node22/bin/claude 2.1.296. With HOLD=1.5 and HOLD=0.8: the local server received POST /v1/messages; reviewer_result.txt = 'AUDIT_RESULT_BEGIN {\"verdict\":\"ACCEPT\",\"findings\":[]} AUDIT_RESULT_END'; record status=COMPLETED, binary_anchor_ok=true, binary_is_default=true, config_isolated=true. That satisfies is_independent's R6-01 and R7-01 conditions. With HOLD=8, config_isolated=false, showing the check sees only the end state. Also checked directly: CLAUDE_CONFIG_DIR=<dir with env in .claude.json> claude -p --safe-mode --setting-sources '' --strict-mcp-config sends its requests to the env base URL. Run with the host-injected ANTHROPIC_BASE_URL and CLAUDE_CODE_PROVIDER_MANAGED_BY_HOST unset, as on the owner's PC; in this cloud host those vars take priority. Incidental confirmation: while the injector was alive, 3 R7-01 regression tests failed because their fake reviewer saw the injected env; all 185 passed once it exited. The documentation says lingering setsid children are 'detected, not prevented'; this channel is neither.",
  "suggested_fix": "Do not rely on a post-run snapshot of a same-user-writable directory. Options: (a) before launching any reviewer, verify that no process from earlier workers survives: run every worker in its own cgroup, PID namespace or systemd scope and kill or verify the whole unit, not just the process group; (b) watch the config dir during the run (inotify/fanotify) and set config_isolated=false on any write not made by the reviewer process tree; (c) pass the base URL and credentials only via the driver-built environment and make the CLI ignore config-file env, e.g. a read-only bind-mounted config dir in a mount namespace. Add a regression test with a setsid injector that writes and then removes env during the run."
 }
]

End your final message with:
REPAIR_RESULT_BEGIN
{"repaired": ["<finding id>"], "not_repaired": [{"id": "...", "reason": "..."}],
 "regression_tests": ["path/to/test_file.py"], "notes": "..."}
REPAIR_RESULT_END
