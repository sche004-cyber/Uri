You are the IMPLEMENTER repairing URI milestone DEV-LIFECYCLE-1 at commit d5fccdf9119a4c31f6183e9240c9962974a42bc0.
An independent reviewer reported the blocking findings below. Make the minimal, justified repair for each, in this
working tree only. For every code finding add or extend a regression test that FAILS on d5fccdf9119a4c31f6183e9240c9962974a42bc0 and PASSES after
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
  "id": "R2-01",
  "severity": "HIGH",
  "blocking": true,
  "category": "security",
  "owner_decision": false,
  "title": "Forged duplicate round record plus edited resume_to brings a real milestone to VERIFIED; verify() reports no error",
  "files": [
   "scripts/dev_workflow/lifecycle.py:1135",
   "scripts/dev_workflow/lifecycle.py:1174-1176",
   "scripts/dev_workflow/lifecycle.py:589-593",
   "scripts/dev_workflow/lifecycle.py:936-940",
   "docs/dev_workflow/URI_DEVELOPMENT_LIFECYCLE.md:44"
  ],
  "evidence": "Probe /tmp/uri_review_R2/forge.py: milestone 'W1-REAL', command reviewer printing ACCEPT -> R1 NOT_INDEPENDENT -> WAITING_FOR_MODEL. In state.json, inserted a copy of round 1 with independent=true/effective_verdict=ACCEPT/status=COMPLETED_WITH_RESULT BEFORE the genuine record and set resume_to='VERIFYING'. verify() -> []. run() -> READY_TO_RESUME -> VERIFYING -> VERIFIED, evidence_ok_for_candidate=True, verify() still []. verify builds rounds={r['round']: r}, so the last (genuine) duplicate is compared and the forged one is never checked; accepted_review iterates every list entry. resume_to and blocker are not covered by verify at all. The docs say verify checks every state.json round.",
  "suggested_fix": "Have verify reject duplicate or unsequenced round/repair numbers (the list must equal exactly the recorded REVIEW_RECORDED/REPAIR_* events, in order). Derive accepted_review and resume targets from round.json files and events whose hashes check out, not from state.json fields. Record resume_to in the BLOCK/WAITING stage event and check it."
 },
 {
  "id": "R2-02",
  "severity": "HIGH",
  "blocking": true,
  "category": "security",
  "owner_decision": false,
  "title": "Worker-created git replace refs hide a protected-path change from every driver check; it is committed and pushed to canonical",
  "files": [
   "scripts/dev_workflow/lifecycle.py:71",
   "scripts/dev_workflow/lifecycle.py:245-265",
   "scripts/dev_workflow/lifecycle.py:762-790",
   "scripts/dev_workflow/lifecycle.py:547"
  ],
  "evidence": "Probe /tmp/uri_review_R2/replace_probe.py + evil_impl.py (DEVTEST fixture, protected 'core/'): the implementer edits and stages core/frozen.py, builds commits with that tree and the original parents, and runs `git replace` for HEAD and origin/canon, then fixes pkg/calc.py and adds a test. Result: repair COMMITTED, run COMPLETE, verify []. `git --git-dir canonical.git show canon:core/frozen.py` -> 'PATCHED_BY_WORKER = True'. worktree_changes, changed_paths and qualify's protected check all resolve the substituted trees. refs_digest and git_control_digest do not cover refs/replace, and git replace is not in GIT_WRITE_DENY.",
  "suggested_fix": "Run every driver git command with GIT_NO_REPLACE_OBJECTS=1 (and --no-replace-objects). Include refs/replace/* (or all non-branch refs) in the integrity snapshot and treat any change as TAMPER. Compute scope and protected checks from explicit tree objects (ls-tree/diff-tree of the commit's real tree)."
 },
 {
  "id": "R2-03",
  "severity": "MEDIUM",
  "blocking": true,
  "category": "security",
  "owner_decision": false,
  "title": "Revert after a refused repair is not limited to the implementation worktree: a rewritten .git gitfile makes reset --hard move the main checkout's branch",
  "files": [
   "scripts/dev_workflow/lifecycle.py:729-733",
   "scripts/dev_workflow/lifecycle.py:762-769",
   "scripts/dev_workflow/lifecycle.py:806"
  ],
  "evidence": "Probe /tmp/uri_review_R2/gitfile_probe.py + evil_impl2.py: the implementer rewrites impl/.git to 'gitdir: <common dir>'. The driver reports 'TAMPER: implementer moved HEAD...', but _restore then runs `git -C impl reset --hard <candidate>` against the MAIN gitdir. The main repo's refs/heads/canon moved 5f427cc -> a0ec99a (the candidate) and its index was reset; `git status` in main shows 'D pkg/feature.py'. The run blocks TAMPER after the damage is done.",
  "suggested_fix": "Before any git command in the implementation worktree, check that `git -C wt rev-parse --git-dir` equals the recorded worktree gitdir and --show-toplevel equals wt. Otherwise refuse with TAMPER and do not reset. Alternatively pass explicit --git-dir/--work-tree."
 },
 {
  "id": "R2-04",
  "severity": "MEDIUM",
  "blocking": true,
  "category": "code",
  "owner_decision": false,
  "title": "Repair that deletes a test file crashes regression_proof; the unproven repair commit stays and is adopted as the candidate",
  "files": [
   "scripts/dev_workflow/lifecycle.py:705-707",
   "scripts/dev_workflow/lifecycle.py:791",
   "scripts/dev_workflow/lifecycle.py:914-917"
  ],
  "evidence": "Probe /tmp/uri_review_R2/del_probe.py: the implementer deletes tests/test_calc.py and edits pkg/calc.py. tests = committed paths matching test_globs, which includes the deleted file. shutil.copy2(post/t, pre/t) raises FileNotFoundError, which propagates out of run(). The impl worktree keeps commit c7bf80a 'fix(DEVTEST-LC): repair R1-01 (lifecycle P1)', which has no regression proof; state.json has repairs=[] (record lost). The next run() logs CANDIDATE_MOVED and sets candidate=c7bf80a. R1-08 (timeout) is fixed, but the general uncaught-exception path is not.",
  "suggested_fix": "Exclude deleted paths from regression tests (refuse a repair that deletes an existing test), and wrap the post-commit section of do_repair in try/except that records REFUSED and restores the worktree to the pre-repair SHA."
 },
 {
  "id": "R2-05",
  "severity": "MEDIUM",
  "blocking": true,
  "category": "code",
  "owner_decision": false,
  "title": "GPU lease busy (gpu_lease run exit 75) is classified as a gate failure and routed to repair, not BLOCKED (RESOURCE)",
  "files": [
   "scripts/dev_workflow/lifecycle.py:488-495",
   "scripts/dev_workflow/lifecycle.py:499-516",
   "uri_operational_intelligence/gpu_lease.py:533-548"
  ],
  "evidence": "gpu_lease `status` always returns 0, so the pre-check passes even when the GPU is held. `gpu_lease run --wait N` returns 75 on GpuBusy. run_gate treats that rc as a normal result: a command gate gets failure 'exit 75'; a pytest gate has no junit, so 'no test report'. qualify reports a new failure, and run() creates GATE-* findings and moves to FIXING, asking the implementer to fix a contention event. This contradicts L-AC17 (lease unavailable => BLOCKED RESOURCE). Code evidence only; not executed (no GPU).",
  "suggested_fix": "For gpu gates, map exit 75 (and the {'refused': ...} stderr) to status BLOCKED with the lease detail. Add a unit test with a fake lease module returning 75."
 }
]

End your final message with:
REPAIR_RESULT_BEGIN
{"repaired": ["<finding id>"], "not_repaired": [{"id": "...", "reason": "..."}],
 "regression_tests": ["path/to/test_file.py"], "notes": "..."}
REPAIR_RESULT_END
