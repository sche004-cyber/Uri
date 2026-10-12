You are the IMPLEMENTER repairing URI milestone DEV-LIFECYCLE-1 at commit 43467152d92ec7b630bfa5dc3b8587577af96443.
An independent reviewer reported the blocking findings below. Make the minimal, justified repair for each, in this
working tree only. For every code finding add or extend a regression test that FAILS on 43467152d92ec7b630bfa5dc3b8587577af96443 and PASSES after
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
  "title": "Policy binding covers only the config file hash: the default protected list (ws_frozen_check) is re-read every run from the main checkout's working tree and a relaxed list reaches VERIFIED with no CONFIG_CHANGED and verify() clean",
  "files": [
   "scripts/dev_workflow/lifecycle.py:117-118",
   "scripts/dev_workflow/lifecycle.py:143-146",
   "scripts/dev_workflow/lifecycle.py:1031-1071",
   "scripts/dev_workflow/lifecycle.py:1027",
   "docs/dev_workflow/lifecycle/TEMPLATE.json:8",
   "docs/dev_workflow/URI_DEVELOPMENT_LIFECYCLE.md:44"
  ],
  "evidence": "/tmp/uri_review_R4/probe_policy.py: DEVTEST fixture, config protected_paths='ws_frozen_check', repo/scripts/ws_frozen_check.py PROTECTED=('core/',...), candidate changes core/frozen.py. Run 1 (reviewer script absent) -> WAITING_FOR_MODEL, PLAN event protected=['core/','scripts/ws_frozen_check.py']. Then only the main checkout's working-tree scripts/ws_frozen_check.py was edited to PROTECTED=('nothing/',) (config file byte-identical) and the reviewer script created. Run 2 -> VERIFIED; events contain no CONFIG_CHANGED; changed_paths(base,candidate) includes core/frozen.py; L.verify(cfg) == []; evidence_ok == (True, []). policy(cfg) is recorded in PLAN/CONFIG_CHANGED but never compared; config_binding() compares only _config_sha256. The main checkout is excluded from integrity checks (doc \u00a76), so a worker, another session, or a branch switch/pull in the main checkout silently relaxes L-AC11.",
  "suggested_fix": "Bind and compare the resolved policy, not just the file hash: e.g. compute chash(policy(cfg)) (with the resolved protected list) into PLAN/CONFIG_CHANGED and have config_binding/run block CONFIG when it differs; or resolve 'ws_frozen_check' once at PLAN time (or from the baseline commit via git show <baseline>:scripts/ws_frozen_check.py) and read the protected list from the chain thereafter. Add a regression test that edits ws_frozen_check.py between runs."
 }
]

End your final message with:
REPAIR_RESULT_BEGIN
{"repaired": ["<finding id>"], "not_repaired": [{"id": "...", "reason": "..."}],
 "regression_tests": ["path/to/test_file.py"], "notes": "..."}
REPAIR_RESULT_END
