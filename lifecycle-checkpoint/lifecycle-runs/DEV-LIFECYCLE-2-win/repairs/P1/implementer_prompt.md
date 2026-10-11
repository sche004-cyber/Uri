You are the IMPLEMENTER repairing URI milestone DEV-LIFECYCLE-2 at commit f3706e03402f496ae91a08a69db515df4bf89245.
An independent reviewer reported the blocking findings below. Make the minimal, justified repair for each, in this
working tree only. For every code finding add or extend a regression test that FAILS on f3706e03402f496ae91a08a69db515df4bf89245 and PASSES after
your change (it will be run both ways). Do not weaken, skip or delete existing tests. Do not touch protected paths:
uri_core/, uri_supervisor/, uri_supervisor_bridge/, uri_harness_adapters/, model_lab/integration/, scripts/run_uri_supervised_worker.py, scripts/run_uri_phase2_server.py, scripts/run_uri_client_worker.py, scripts/run_uri_isolated_server.py, scripts/c1_bootstrap.py, uri_ui/lib/services/paired_runtime.dart, uri_ui/lib/services/supervised_runtime.dart, uri_ui/lib/screens/settings/paired_runtime_screen.dart, uri_ui/lib/screens/settings/settings_shell.dart, uri_ui/lib/screens/tasks/supervised_execution_screen.dart, .gitignore. Stay inside the permitted paths: scripts/dev_workflow/lifecycle*.py, scripts/dev_workflow/containment.py, tests/dev_workflow/**, docs/dev_workflow/**, .claude/skills/uri-development-lifecycle/**, CLAUDE.md.
Do not commit or push; the driver commits after checking your change. If a finding cannot be fixed within these
limits, do not work around it: report it as not repaired with the reason.

Environment notes:
- Python with pytest and the repo requirements: /tmp/claude-0/venv/bin/python (use it for tests; do not pip install)
- Linux cloud container: no Windows, no GPU. Windows-only tests (marker windows_only) are reported as PLATFORM-GATED here; the Windows code must be reviewed by reading it. The driver under review is the candidate's; this run itself is driven by the canonical ce1a90c driver.
- Regression proof: the driver copies ONLY the files you list in regression_tests into a clean checkout of the pre-repair commit and runs them there; new fixture/helper files are NOT copied. Make each regression test self-contained (embed fixture HTML/JS in the test file and write it to tmp_path at run time). A test that is skipped on the pre-repair commit counts as NOT failing, so it must not skip for a missing fixture.
- graphify: do NOT run `graphify update` (or any graphify command that writes) in this working tree, and do not delete or edit anything under graphify-out/: those files are tracked and outside the permitted paths, so the change would be refused. The repository rule 'run graphify update after modifying code' is satisfied by the coordinator, who rebuilds the graph outside the repository. For code navigation use read-only queries: `graphify query "..." --graph /home/user/uri-wt/graphs/canonical/graphify-out/graph.json` (also `path`, `explain`).

Findings (from the reviewer, verbatim):
[
 {
  "blocking": true,
  "category": "code",
  "evidence": "lifecycle.py:749 _test_file returns str(Path(base) / c), which gives backslashes on Windows. test_r1r2_03_gate_test_ids_resolve_to_files fails on Windows: 'uri_ui\\\\test\\\\widget_test.dart' != 'uri_ui/test/widget_test.dart'. Callers (lifecycle.py:1630) compare against git's '/' paths, so regression proof for gates with a cwd breaks on Windows.",
  "files": [
   "scripts/dev_workflow/lifecycle.py:749",
   "scripts/dev_workflow/lifecycle.py:1630"
  ],
  "id": "W-1",
  "owner_decision": false,
  "severity": "MEDIUM",
  "suggested_fix": "Use .as_posix(). A cross-platform regression test is possible with PureWindowsPath or monkeypatch.",
  "title": "_test_file builds gate test file paths with OS separators (backslashes on Windows)"
 },
 {
  "blocking": true,
  "category": "security",
  "evidence": "On Windows shutil.which('claude') resolves to the npm shim %APPDATA%\\\\npm\\\\claude.cmd, a batch file that runs %~dp0\\\\node_modules\\\\@anthropic-ai\\\\claude-code\\\\bin\\\\claude.exe %*. reviewer_executable() hashes only the shim (interpreter=null), so a replaced claude.exe behind it is NOT detected as TAMPER (DEV-LIFECYCLE-1 R6-01 guarantee). Launching a .cmd also sends every argv item (including the --settings JSON deny rules, with quotes) through cmd.exe parsing, which subprocess list2cmdline does not quote for.",
  "files": [
   "scripts/dev_workflow/lifecycle_providers.py"
  ],
  "id": "W-2",
  "owner_decision": false,
  "severity": "HIGH",
  "suggested_fix": "Resolve an npm .cmd/.ps1 shim to its target executable, bind that executable's path and hash, and launch it directly (never via cmd.exe). If a shim cannot be resolved unambiguously, refuse. The parsing logic can be tested on Linux with a fixture shim file.",
  "title": "Windows: the reviewer CLI binding hashes the npm claude.cmd shim, not the executable it runs; .cmd launch goes through cmd.exe parsing"
 },
 {
  "blocking": true,
  "category": "test",
  "evidence": "Windows 11, Python 3.13.15, pytest tests/dev_workflow at f3706e03: 17 failed, 194 passed, 6 skipped (at ce1a90c: 72 failed, 114 passed, 6 skipped; 0 new failures). Causes: fake `claude` shell scripts with no .exe/.cmd (WAITING_FOR_MODEL instead of the expected state: r6_01 x4, r7_01 managed_policy); `sh -c sleep` children (r1_06, r1r2_01[False]); Windows paths written unescaped into gitconfig ('bad config line 2': r4_01 x2, r5_01); writing `.git` in a worktree (PermissionError: r2_03); seen.json / reviewer_r* files never produced because the fake CLI could not run (r7_01 x4, r8_01). Skipped with 'Linux-only' reasons instead of DL2 platform-gated reporting: r1r2_01[True], r8_01 x2, r10_01 x3. Against DL2-AC 'never silently skipped'.",
  "files": [
   "tests/dev_workflow/"
  ],
  "id": "W-3",
  "owner_decision": false,
  "severity": "MEDIUM",
  "suggested_fix": "Make the fixtures portable (Python fake CLIs launched via sys.executable, gitconfig paths as_posix) where the guarantee applies on Windows. Where it truly does not (setsid), mark the test windows_only/linux_only so the conftest reports it by name. Windows confirmation is done by the owner-PC coordinator re-running the Windows gate on each new candidate SHA.",
  "title": "tests/dev_workflow fixtures are not portable to Windows (17 failures) and 6 older tests skip with 'Linux-only' reasons instead of named platform-gated reporting"
 }
]

End your final message with:
REPAIR_RESULT_BEGIN
{"repaired": ["<finding id>"], "not_repaired": [{"id": "...", "reason": "..."}],
 "regression_tests": ["path/to/test_file.py"], "notes": "..."}
REPAIR_RESULT_END
