You are the IMPLEMENTER repairing URI milestone DEV-LIFECYCLE-1 at commit 2d419f6922380f16cf1486c7380f4c8619d66b00.
An independent reviewer reported the blocking findings below. Make the minimal, justified repair for each, in this
working tree only. For every code finding add or extend a regression test that FAILS on 2d419f6922380f16cf1486c7380f4c8619d66b00 and PASSES after
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
  "id": "R10-01",
  "severity": "MEDIUM",
  "blocking": true,
  "category": "code",
  "owner_decision": false,
  "title": "Timeout path calls communicate() without a timeout before the R8-01 orphan sweep: a setsid descendant holding stdout hangs the driver indefinitely and the sweep is never reached",
  "files": [
   "scripts/dev_workflow/lifecycle.py:663",
   "scripts/dev_workflow/lifecycle.py:665",
   "scripts/dev_workflow/lifecycle.py:669",
   "scripts/dev_workflow/lifecycle_providers.py:426",
   "scripts/dev_workflow/lifecycle_providers.py:430",
   "scripts/dev_workflow/lifecycle_providers.py:442"
  ],
  "evidence": "run_cmd and _run call communicate(timeout), then on TimeoutExpired call killpg and communicate() with no timeout. killpg does not reach a child that called setsid(), and the sweep_orphans() that would kill it comes only after communicate returns. Probe /tmp/uri_review_R10/hang.py: run_cmd([python,-c,'Popen([\"setsid\",\"sleep\",\"30\"])'], '.', 3) had not returned after 15 s. Probe /tmp/uri_review_R10/worker.py: run_worker(command 'setsid sleep 40 & echo done', timeout_s=3) had not returned after 20 s. Any gate, test or worker child can keep the driver blocked indefinitely (a malicious implementer can also open its CLI's stdout through /proc/$PPID/fd/1). The only recovery is killing the driver, which moves the orphan outside the subreaper tree (see R10-02).",
  "suggested_fix": "After TimeoutExpired (and before any blocking second communicate), killpg then sweep_orphans() first, and bound the second communicate with a timeout (or close the pipes and kill). Do the same in _run. Add tests where a setsid child keeps stdout open."
 },
 {
  "id": "R10-02",
  "severity": "MEDIUM",
  "blocking": false,
  "category": "security",
  "owner_decision": false,
  "title": "contained=true is recorded although workers or orphans of an earlier, killed driver process are still running (outside the subreaper tree); documented limitation, but realistic and reachable through R10-01",
  "files": [
   "scripts/dev_workflow/lifecycle_providers.py:402",
   "scripts/dev_workflow/lifecycle_providers.py:443",
   "docs/dev_workflow/URI_DEVELOPMENT_LIFECYCLE.md:79"
  ],
  "evidence": "Probe: a driver running run_worker(sleep 300) was killed with SIGKILL. The worker kept running (ppid 1, its own session), and a new driver's sweep_orphans() returned {'contained': True, 'killed': 0}. Workers run with start_new_session, so a launcher timeout that kills the driver (or R10-01 forcing one) leaves them alive while the resumed run records contained=true.",
  "suggested_fix": "Record each worker's/command's session id (pid) in state before launch. At run start, scan /proc for live processes in those sessions and kill them, or refuse contained=true until none is left."
 }
]

End your final message with:
REPAIR_RESULT_BEGIN
{"repaired": ["<finding id>"], "not_repaired": [{"id": "...", "reason": "..."}],
 "regression_tests": ["path/to/test_file.py"], "notes": "..."}
REPAIR_RESULT_END
