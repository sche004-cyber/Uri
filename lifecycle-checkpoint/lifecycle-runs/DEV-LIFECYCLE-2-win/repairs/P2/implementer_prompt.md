You are the IMPLEMENTER repairing URI milestone DEV-LIFECYCLE-2 at commit fcc0ebdde656ff4a4db2f4cb82d9b50faf9a07ef.
An independent reviewer reported the blocking findings below. Make the minimal, justified repair for each, in this
working tree only. For every code finding add or extend a regression test that FAILS on fcc0ebdde656ff4a4db2f4cb82d9b50faf9a07ef and PASSES after
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
  "id": "R2-01",
  "severity": "MEDIUM",
  "blocking": true,
  "category": "security",
  "owner_decision": false,
  "title": "Windows precheck() is fail-open after an earlier worker/command that had no job or whose TerminateJobObject failed",
  "files": [
   "scripts/dev_workflow/containment.py:258",
   "scripts/dev_workflow/containment.py:263",
   "scripts/dev_workflow/containment.py:276",
   "scripts/dev_workflow/lifecycle.py:681",
   "scripts/dev_workflow/lifecycle_providers.py:480",
   "docs/dev_workflow/URI_DEVELOPMENT_LIFECYCLE.md:43"
  ],
  "evidence": "finish(): when job is None (create/assign failed) it only calls kill_pid_tree (taskkill /T, which misses a detached grandchild whose parent already exited) and returns contained=False without recording anything; when api.terminate/_wait_empty raises OSError it returns contained=False without appending the job to _OPEN_JOBS (handle also never closed, so KILL_ON_JOB_CLOSE never fires). precheck() inspects only _OPEN_JOBS, so the next reviewer's containment_pre is contained=True. run_cmd ignores finish()'s result for gates. Repro with a fake kernel32: /tmp/uri_review_R2/probe_precheck.py prints 'implementer finish: {contained: False, job not created...}' then 'reviewer precheck : {contained: True, killed: 0}' and 'reviewer finish: {contained: True}'; /tmp/uri_review_R2/probe_terminate.py prints 'job 1 active: 1' then 'precheck: {contained: True}'. This contradicts the plan's design ('any containment API failure: contained=False (fail closed)'; 'Before each worker, every earlier job must still show 0') and the doc claim at URI_DEVELOPMENT_LIFECYCLE.md, and reopens the R8-01 threat (an earlier worker's process running alongside the reviewer) on Windows.",
  "suggested_fix": "Keep a module-level 'tainted' record: any spawn without a job, or any finish() whose terminate/verify raised, makes every later precheck() return contained=False (until the owner unblocks), or keep the failed job in _OPEN_JOBS so precheck re-checks it. Add fake-kernel32 tests for both sequences (uncontained implementer/gate then reviewer precheck; terminate failure then precheck)."
 }
]

End your final message with:
REPAIR_RESULT_BEGIN
{"repaired": ["<finding id>"], "not_repaired": [{"id": "...", "reason": "..."}],
 "regression_tests": ["path/to/test_file.py"], "notes": "..."}
REPAIR_RESULT_END
