You are the IMPLEMENTER repairing URI milestone DEV-LIFECYCLE-2 at commit 0ee6885a68ec14eabec7645b4501f87d17bde6f0.
An independent reviewer reported the blocking findings below. Make the minimal, justified repair for each, in this
working tree only. For every code finding add or extend a regression test that FAILS on 0ee6885a68ec14eabec7645b4501f87d17bde6f0 and PASSES after
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
  "category": "security",
  "evidence": "Probe /tmp/uri_review_R1/test_probe_w2.py: launcher '\"%~dp0cmd.exe\" /c \"%~dp0real.bat\" %*' gives realpath real.bat, interpreter cmd.exe, no error/unlaunchable. Any non-.exe/.com quoted file, including .bat/.cmd, counts as the 'script', and '%*' is accepted anywhere in the text (e.g. in a REM line). The reviewer then runs through cmd.exe, without /c, so stdin (the prompt) could be read as commands. This contradicts the plan's 'never through cmd.exe'. It needs a launcher already trusted at PLAN.",
  "files": [
   "scripts/dev_workflow/lifecycle_providers.py:288",
   "scripts/dev_workflow/lifecycle_providers.py:297"
  ],
  "id": "r2.R1-02",
  "owner_decision": false,
  "severity": "LOW",
  "suggested_fix": "Owner criterion: a .cmd launcher that names cmd.exe (or powershell/pwsh) and a .bat/.cmd/.ps1 must not be bound or launched; %* must be on the launch line itself (not anywhere in the text, e.g. a REM line). Reviewer suggestion: Refuse a bound program whose basename is cmd.exe/powershell.exe/pwsh.exe, and refuse scripts with .bat/.cmd/.ps1 extensions; require %* on the line that names the program.",
  "title": "A .cmd launcher naming cmd.exe and a .bat is bound and launched as [cmd.exe, x.bat] (DEV-LIFECYCLE-2-r2 R1-02, LOW, routed to repair by owner decision)"
 },
 {
  "blocking": true,
  "category": "test",
  "evidence": "Run at ce1a90c with only the new test files copied: test_w2_launcher_that_cannot_be_bound_is_unlaunchable (3 params) and test_w2_ps1_only_is_not_a_reviewer_cli PASS, because shutil.which finds no claude.cmd on Linux and the assertion `ident.get('unlaunchable') or ident.get('error')` also accepts {'error': 'not found'}. The plan and LIFECYCLE_QUALIFICATION claim all 10 fail on ce1a90c (DL2-AC11). test_lifecycle_platform.py fails on the baseline only at collection (ImportError), not per test.",
  "files": [
   "tests/dev_workflow/test_lifecycle_windows_cli.py:106",
   "tests/dev_workflow/test_lifecycle_windows_cli.py:116"
  ],
  "id": "r2.R1-03",
  "owner_decision": false,
  "severity": "LOW",
  "suggested_fix": "Owner criterion: every new W-2 test must fail on ce1a90c on Linux as well, for its own reason; no test may accept {'error': 'not found'} as a pass. Reviewer suggestion: Assert the 'unlaunchable' key (or the exact launcher error), not 'error: not found'; assert that the launcher was found.",
  "title": "Four new W-2 tests pass on baseline ce1a90c on Linux (vacuous 'not found' acceptance) (DEV-LIFECYCLE-2-r2 R1-03, LOW, routed to repair by owner decision)"
 },
 {
  "blocking": true,
  "category": "documentation",
  "evidence": "Focus 6 and DL2-AC9 require Windows to stay NOT VERIFIED until the PC qualification run; the ledger row says 'TESTED on the PC (Job Objects ...)'. The URI_DEVELOPMENT_LIFECYCLE reviewer-independence row still describes the identity as 'realpath, SHA-256 and a script's interpreter', with no launcher/launch binding, and claims every earlier job is re-checked (see R1-01).",
  "files": [
   "docs/dev_workflow/CAPABILITY_LEDGER.md:12",
   "docs/dev_workflow/URI_DEVELOPMENT_LIFECYCLE.md"
  ],
  "id": "r2.R1-04",
  "owner_decision": false,
  "severity": "LOW",
  "suggested_fix": "Owner criterion: CAPABILITY_LEDGER says Windows containment = windows_only unit tests passed on the owner's PC, and containment in a real milestone run is NOT VERIFIED; URI_DEVELOPMENT_LIFECYCLE.md documents the W-2 identity binding (launcher, program, interpreter, launch) and does not overstate the earlier-job re-check. Reviewer suggestion: Mark Windows containment NOT VERIFIED (logic tested with a fake kernel32; real-job tests reported by the owner), document the launch/launcher identity, and correct the re-check claim.",
  "title": "CAPABILITY_LEDGER claims Windows containment 'TESTED on the PC'; lifecycle doc omits the W-2 reviewer identity and overstates the earlier-job re-check (DEV-LIFECYCLE-2-r2 R1-04, LOW, routed to repair by owner decision)"
 },
 {
  "blocking": true,
  "category": "code",
  "evidence": "_run catches OSError from proc.communicate() (after containment.spawn succeeded and the process was resumed) and returns status FAILED without containment.finish(proc). On Windows the job is neither terminated, nor appended to _OPEN_JOBS, nor recorded in _TAINTED, and the handle stays open, so KILL_ON_JOB_CLOSE does not fire. Probe /tmp/uri_review_R2/probe/test_probe_unfinished.py with the repo's FakeApi/FakeProc: communicate raises OSError(23): job 1 = {'active': 1, 'terminated': False}, _OPEN_JOBS=[], _TAINTED=[], next C.precheck() = {'contained': True, 'killed': 0}. On Linux the leftover worker is a direct child in another session and the next sweep_orphans kills it, so only Windows is affected. Low likelihood: CPython swallows BrokenPipeError/EINVAL on the stdin write.",
  "files": [
   "scripts/dev_workflow/lifecycle_providers.py:582",
   "scripts/dev_workflow/containment.py:172",
   "scripts/dev_workflow/containment.py:293"
  ],
  "id": "r2.R2-01",
  "owner_decision": false,
  "severity": "LOW",
  "suggested_fix": "Coordinator-recommended, owner-approved: same fail-open class as R1-01 (fixed in 0ee6885a); every path after a successful spawn must end in containment.finish or leave the job tracked/tainted so the next precheck() fails closed. Fake-kernel32 regression test required. Reviewer suggestion: Register each job in _OPEN_JOBS at spawn time (remove it only once precheck/finish verified it empty), or call containment.finish(proc) in a finally on every path after a successful spawn (also run_cmd on non-TimeoutExpired exceptions).",
  "title": "Windows: a worker whose communicate() raises OSError after spawn is never finished; its job stays unterminated and untracked, and the next precheck() reports contained=True (DEV-LIFECYCLE-2-r2 R2-01, LOW, routed to repair by owner decision)"
 }
]

End your final message with:
REPAIR_RESULT_BEGIN
{"repaired": ["<finding id>"], "not_repaired": [{"id": "...", "reason": "..."}],
 "regression_tests": ["path/to/test_file.py"], "notes": "..."}
REPAIR_RESULT_END
