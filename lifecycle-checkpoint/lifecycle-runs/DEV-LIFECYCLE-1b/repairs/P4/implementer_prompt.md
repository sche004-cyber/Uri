You are the IMPLEMENTER repairing URI milestone DEV-LIFECYCLE-1 at commit 6784424d48df221bedd271707ff2b687c0719e4e.
An independent reviewer reported the blocking findings below. Make the minimal, justified repair for each, in this
working tree only. For every code finding add or extend a regression test that FAILS on 6784424d48df221bedd271707ff2b687c0719e4e and PASSES after
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
  "id": "R5-01",
  "severity": "MEDIUM",
  "blocking": true,
  "category": "security",
  "owner_decision": false,
  "title": "Merge-mode integration runs candidate gate code after the last control-drift check; a test that writes ~/.gitconfig insteadOf redirects the push and its ls-remote verification, yielding a false COMPLETE",
  "files": [
   "scripts/dev_workflow/lifecycle.py:1212",
   "scripts/dev_workflow/lifecycle.py:1252",
   "scripts/dev_workflow/lifecycle.py:1264",
   "scripts/dev_workflow/lifecycle.py:1266",
   "scripts/dev_workflow/lifecycle.py:1269"
  ],
  "evidence": "integrate() calls evidence_ok (incl. control_drift) once at the top; in mode=merge it then runs qualify(cfg, st, result_sha, wt=iwt), executing the candidate's test code, and pushes and verifies via ls-remote with no further control check. Probe /tmp/uri_review_R5/test_probe_r5.py (HOME=/tmp/uri_review_R5/home, DEVTEST fixture, mode merge, authorized): candidate tests/conftest.py appends [url fake.git] insteadOf=canonical.git to $HOME/.gitconfig only when cwd is the 'integration' worktree. Result: stage COMPLETE, integration status INTEGRATED, push_stderr 'To .../fake.git 9c379a5..ca5248b', target_tip_after == result_commit read via the redirected ls-remote; real canonical canon still at base 9c379a5; L.verify(cfg) == []. Same redirection class as R4-01, through a path its repair does not check.",
  "suggested_fix": "Re-run control_drift (and refs/replace check) after the combined-gate qualify and immediately before and after the push; block TAMPER on drift. Resolve the remote URL once from the anchored config and push/ls-remote against that explicit URL (with -c url.*.insteadOf unset / GIT_CONFIG_GLOBAL=/dev/null for the push), or run gate commands with HOME/GIT_CONFIG_GLOBAL pointed at a throwaway directory."
 }
]

End your final message with:
REPAIR_RESULT_BEGIN
{"repaired": ["<finding id>"], "not_repaired": [{"id": "...", "reason": "..."}],
 "regression_tests": ["path/to/test_file.py"], "notes": "..."}
REPAIR_RESULT_END
