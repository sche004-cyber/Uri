You are the IMPLEMENTER repairing URI milestone DEV-LIFECYCLE-1 at commit 6bcfd1d854c1d477bda4d2e5c955c0c475a24bc3.
An independent reviewer reported the blocking findings below. Make the minimal, justified repair for each, in this
working tree only. For every code finding add or extend a regression test that FAILS on 6bcfd1d854c1d477bda4d2e5c955c0c475a24bc3 and PASSES after
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
  "category": "code",
  "owner_decision": false,
  "title": "Gate-finding repairs skip the fail-before proof for class-based pytest tests and every Flutter test: a repair that weakens the failing test is committed and integrated",
  "files": [
   "scripts/dev_workflow/lifecycle.py:601-606",
   "scripts/dev_workflow/lifecycle.py:867-873",
   "scripts/dev_workflow/lifecycle.py:1192-1194",
   "docs/dev_workflow/URI_DEVELOPMENT_LIFECYCLE.md:44"
  ],
  "evidence": "_test_file maps a junit id to head.replace('.', '/') + '.py' relative to the repo root. A class-based id 'tests.pkg.test_k.TestK::test_a' becomes 'tests/pkg/test_k/TestK.py', which does not exist. A Flutter id 'test/x_test.dart::x' is relative to the gate cwd uri_ui, not the root (probe: is_file False for both). _commit_and_prove keeps only gate tests where (wt/path).is_file(), so gate_tests is empty. GATE findings have category 'test', so defect=False, need_fail_before=False and must_fail is empty: the repair only has to pass afterwards. End-to-end probe (/tmp/uri_review_R5/p1/probe_weaken.py) uses the fixture with a broken pkg/other.py and an implementer that changes 'assert VALUE == 2' to 'assert VALUE in (2, 3)'. With a function test the repair is REFUSED 3x ('gate test tests/test_other.py did not fail before'). With the same test inside a class: COMMITTED, stage COMPLETE, remote canon == candidate, and the repair commit touches only tests/test_other.py. The docs claim 'gate tests named by gate findings must each fail before'.",
  "suggested_fix": "Resolve gate tests from the gate's own report: junit 'file' attribute, or strip trailing class segments until a .py file exists, and use the gate cwd for Flutter ids. If a GATE finding's test file cannot be resolved, refuse the repair rather than treating it as coverage-only. Also refuse repairs that modify (not just delete) a test named by a gate finding unless the modified test still fails on the pre-repair commit."
 },
 {
  "id": "R5-02",
  "severity": "MEDIUM",
  "blocking": true,
  "category": "code",
  "owner_decision": false,
  "title": "Baseline comparison keys are non-deterministic: plain-assert causes include run-specific values and Flutter load-failure ids include the absolute worktree path, so historical failures count as new",
  "files": [
   "scripts/dev_workflow/lifecycle.py:453-456",
   "scripts/dev_workflow/lifecycle.py:491-497",
   "scripts/dev_workflow/lifecycle.py:589-598"
  ],
  "evidence": "pytest junit messages for bare asserts carry no exception type ('assert 21013 == 1', 'assert <object object at 0x7f0eb3781760> is None'), so _cause returns the assertion text including pids and addresses, and compare() reports changed_cause, i.e. a new failure. Real 'flutter test --machine' runs of the same broken test file in two directories gave failures {'::loading /tmp/uri_review_R5/fl/A/test/broken_test.dart'} vs {'::loading /tmp/uri_review_R5/fl/B/test/broken_test.dart'}. compare() => new_failures=[A id], ok=False. Candidate (work_dir/qualify) and baseline (work_dir/baseline) always run in different worktrees, so a historical load failure always blocks qualification and is routed to FIXING until RETRY_LIMIT. The plan's decision 6 specifies cause = exception type.",
  "suggested_fix": "Normalise causes (AssertionError for bare asserts, or strip numbers, hex addresses and paths). For Flutter, derive the id from the test's url or the suite path made relative to the worktree, and strip the worktree prefix from 'loading <path>' names and error text. Add tests with two different worktree paths."
 }
]

End your final message with:
REPAIR_RESULT_BEGIN
{"repaired": ["<finding id>"], "not_repaired": [{"id": "...", "reason": "..."}],
 "regression_tests": ["path/to/test_file.py"], "notes": "..."}
REPAIR_RESULT_END
