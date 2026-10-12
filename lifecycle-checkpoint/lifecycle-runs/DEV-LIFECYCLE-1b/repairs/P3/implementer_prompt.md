You are the IMPLEMENTER repairing URI milestone DEV-LIFECYCLE-1 at commit 475533a28021ca7795f2cb495fb131c9c45e20c7.
An independent reviewer reported the blocking findings below. Make the minimal, justified repair for each, in this
working tree only. For every code finding add or extend a regression test that FAILS on 475533a28021ca7795f2cb495fb131c9c45e20c7 and PASSES after
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
  "id": "R4-01",
  "severity": "MEDIUM",
  "blocking": true,
  "category": "security",
  "owner_decision": false,
  "title": "Git control-state tamper check covers only the repository config; worker-written user-level git config (~/.gitconfig) silently redirects the driver's push and its push verification, and smudge filters make reviewer/gate checkouts differ from the candidate commit",
  "files": [
   "scripts/dev_workflow/lifecycle.py:342",
   "scripts/dev_workflow/lifecycle.py:372",
   "scripts/dev_workflow/lifecycle.py:79",
   "scripts/dev_workflow/lifecycle.py:1232",
   "scripts/dev_workflow/lifecycle.py:1234",
   "scripts/dev_workflow/lifecycle.py:421",
   "scripts/dev_workflow/lifecycle_providers.py:131"
  ],
  "evidence": "Probe /tmp/uri_review_R4/p1/probe.py (HOME set to a temp dir): after appending to $HOME/.gitconfig only, L.git_control_digest(repo) and L.control_state(...) are unchanged (True True). (a) A [url \"<fake.git>\"] insteadOf=<origin> entry: driver-style push `[*GIT, -C, repo, push, origin, sha:refs/heads/main]` exits 0 and `git(repo, 'ls-remote', 'origin', ...)` returns the pushed sha, so integrate() would record INTEGRATED and reach COMPLETE, but the real origin main was never updated (printed: real origin main: False). (b) A global [filter \"x\"] smudge/clean plus a committed `.gitattributes` (a.py filter=x): blob in commit is 'DEFECT = True', the file in the driver's add_worktree() checkout reads 'DEFECT = False', and worktree_changes() reports the checkout clean, so the reviewer reads and the gates test content that is not the candidate tree, and the integrity check passes. Workers inherit HOME (lifecycle_providers.py:131) and can write ~/.gitconfig with plain shell (the Bash(git config*) prefix denial does not cover `cat >> ~/.gitconfig`). Same class as R1-04/R3-01 (worker-written config steering driver git commands), outside the monitored set.",
  "suggested_fix": "Include the effective global/system config files (git config --show-origin --list --global/--system, or GIT_CONFIG_GLOBAL / XDG paths) and the default core.attributesFile ($XDG_CONFIG_HOME/git/attributes) in control_state/git_control_digest, or run driver git with GIT_CONFIG_GLOBAL/GIT_CONFIG_NOSYSTEM isolation (plus a separately pinned credential/push configuration). Verify pushes against the remote URL recorded at PLAN (e.g. `git remote get-url` resolved without insteadOf, bound in the chain). Add regression tests for the insteadOf and smudge-filter cases."
 }
]

End your final message with:
REPAIR_RESULT_BEGIN
{"repaired": ["<finding id>"], "not_repaired": [{"id": "...", "reason": "..."}],
 "regression_tests": ["path/to/test_file.py"], "notes": "..."}
REPAIR_RESULT_END
