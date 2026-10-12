You are the IMPLEMENTER repairing URI milestone DEV-LIFECYCLE-2 at commit 73bdbef1e34e0b0a9456ee13e8b7b3f9c0e51f47.
An independent reviewer reported the blocking findings below. Make the minimal, justified repair for each, in this
working tree only. For every code finding add or extend a regression test that FAILS on 73bdbef1e34e0b0a9456ee13e8b7b3f9c0e51f47 and PASSES after
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
  "id": "R1-01",
  "severity": "HIGH",
  "blocking": true,
  "category": "security",
  "owner_decision": false,
  "title": "Windows precheck() reports contained=True after an earlier worker/gate ran without a job or whose TerminateJobObject/empty-wait failed (R2-01 not fixed)",
  "files": [
   "scripts/dev_workflow/containment.py:272",
   "scripts/dev_workflow/containment.py:279",
   "scripts/dev_workflow/containment.py:287",
   "scripts/dev_workflow/lifecycle.py:681"
  ],
  "evidence": "finish() returns contained=False when job is None (create/assign failed; process resumed outside any job) or when api.terminate/_wait_empty raises, but records nothing: _OPEN_JOBS is appended only on the success path, and the leaked job handle is never closed, so KILL_ON_JOB_CLOSE never fires. precheck() only iterates _OPEN_JOBS, so it returns contained=True. Probe /tmp/uri_review_R1/test_probe_r201.py using the repo's FakeApi: assign_fails -> finish {'contained': False} -> precheck {'contained': True, 'killed': 0}; terminate raising OSError -> finish {'contained': False, 'reason': 'job not verified: ...'} -> precheck {'contained': True, 'killed': 0}. run_cmd discards finish()'s result, so a gate's leftover process (taskkill /T is best effort and misses re-parented orphans) can run alongside the next reviewer, whose containment_pre is True. URI_DEVELOPMENT_LIFECYCLE.md claims every earlier job is re-checked.",
  "suggested_fix": "Keep a module-level 'tainted' record: any spawn without a job, any finish() failure (terminate/query error, n>0) must make every later precheck() return contained=False until the owner clears it (or keep the failed job in _OPEN_JOBS and close it on terminate failure). Add fake-kernel32 tests for assign_fails/create_fails/terminate-raises followed by precheck()."
 }
]

End your final message with:
REPAIR_RESULT_BEGIN
{"repaired": ["<finding id>"], "not_repaired": [{"id": "...", "reason": "..."}],
 "regression_tests": ["path/to/test_file.py"], "notes": "..."}
REPAIR_RESULT_END
