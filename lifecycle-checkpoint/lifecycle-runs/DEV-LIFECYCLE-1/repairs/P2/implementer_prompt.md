You are the IMPLEMENTER repairing URI milestone DEV-LIFECYCLE-1 at commit c1ba808e07add92554e09a64b3515bc782ea56d9.
An independent reviewer reported the blocking findings below. Make the minimal, justified repair for each, in this
working tree only. For every code finding add or extend a regression test that FAILS on c1ba808e07add92554e09a64b3515bc782ea56d9 and PASSES after
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
  "id": "R3-01",
  "severity": "MEDIUM",
  "blocking": true,
  "category": "security",
  "owner_decision": false,
  "title": "Revert after a refused repair resets whatever branch the implementation worktree's HEAD names: a redirected HEAD makes the driver move another branch (incl. the main checkout's) to the candidate SHA",
  "files": [
   "scripts/dev_workflow/lifecycle.py:800-807",
   "scripts/dev_workflow/lifecycle.py:880-881",
   "scripts/dev_workflow/lifecycle.py:899",
   "docs/dev_workflow/URI_DEVELOPMENT_LIFECYCLE.md:45"
  ],
  "evidence": "Probe /tmp/uri_review_R3/probe_restore.py: implementer writes 'ref: refs/heads/other' (then 'ref: refs/heads/canon', the main checkout's branch) into its own worktree git dir HEAD and edits a file. worktree_identity() still passes (gitfile untouched). do_repair: head != sha -> TAMPER reason -> _restore() -> `git reset --hard <sha>` updates the symbolic ref. Result: branch 'other' moved 1077e67 -> b097513 (candidate), its commit dropped; second run: 'canon' (checked out in main repo) moved a839efc -> c097ed5 and the main checkout shows 'D pkg/feature.py'. repair.json records restored=True while impl HEAD is refs/heads/other|canon, not the candidate branch. R2-03's class (revert not limited to the implementation worktree) persists via this sibling vector.",
  "suggested_fix": "Before resetting, require `git symbolic-ref HEAD` == refs/heads/<candidate.branch> (else TAMPER, no reset); restore with `update-ref refs/heads/<branch> <sha> <expected-old>` + `symbolic-ref HEAD refs/heads/<branch>` + `reset --hard` / `clean -fd`, and include the HEAD symref in the restored check and in the review integrity snapshot."
 },
 {
  "id": "R3-02",
  "severity": "MEDIUM",
  "blocking": true,
  "category": "code",
  "owner_decision": false,
  "title": "A non-COMPLETED baseline gate result (TIMED_OUT, GPU lease busy, BLOCKED) is cached by SHA+cmd and permanently blocks qualification",
  "files": [
   "scripts/dev_workflow/lifecycle.py:604-614",
   "scripts/dev_workflow/lifecycle.py:1103-1105"
  ],
  "evidence": "Probe /tmp/uri_review_R3/probe_cache.py (A): baseline-only transient hang -> run1 BLOCKED 'baseline gate slow: TIMED_OUT'; cause removed, owner unblock, run2 BLOCKED with the identical reason; state baseline_gates.slow.result.status == 'TIMED_OUT'. The cache is reused whenever key matches regardless of status; editing state.json to clear it is TAMPER. Same path for exit-75 GPU lease busy on the baseline (R2-05), contradicting 'provide the resource and re-run'.",
  "suggested_fix": "Cache baseline results only when status == COMPLETED_WITH_RESULT (or re-run when the cached status is not), recording each attempt as a BASELINE_GATE event."
 },
 {
  "id": "R3-03",
  "severity": "MEDIUM",
  "blocking": true,
  "category": "code",
  "owner_decision": false,
  "title": "Candidate moved during VERIFYING/VERIFIED blocks with resume_to=VERIFYING, so every resume re-blocks and the new commit is never re-audited",
  "files": [
   "scripts/dev_workflow/lifecycle.py:186-191",
   "scripts/dev_workflow/lifecycle.py:1017-1022",
   "scripts/dev_workflow/lifecycle.py:1130-1133"
  ],
  "evidence": "Probe probe_cache.py (B): run to VERIFIED (BLOCKED OWNER_AUTHORIZATION), commit to the candidate branch outside the driver, then unblock+run three times: each run goes READY_TO_RESUME -> VERIFYING -> gates -> evidence_ok fails -> BLOCKED 'no independent ACCEPT on this exact commit' with resume_to VERIFYING again; rounds stays 1, verify() == []. The 'needs: re-audit' remedy is unreachable (L-AC14 liveness).",
  "suggested_fix": "When the candidate changed or the blocker is EVIDENCE (no accepted review for the current SHA), set resume_to=AUDITING; generally resume to AUDITING whenever accepted_review(current sha) is None."
 },
 {
  "id": "R3-04",
  "severity": "MEDIUM",
  "blocking": true,
  "category": "security",
  "owner_decision": false,
  "title": "Milestone policy (protected-path authorisation, gates, integration authorisation, reviewer) is re-read every run; a changed config is only logged, so any writer can relax policy mid-milestone",
  "files": [
   "scripts/dev_workflow/lifecycle.py:1003-1005",
   "scripts/dev_workflow/lifecycle.py:100-125",
   "scripts/dev_workflow/lifecycle.py:929"
  ],
  "evidence": "Probe /tmp/uri_review_R3/probe_config.py: candidate changes protected core/frozen.py; run1 -> WAITING_FOR_MODEL (reviewer unavailable). Config file edited between runs (authorized_protected_changes ['core/**'], gates []) - the file sits outside every integrity check, writable by implementer/reviewer/escaped child or coordinator. run2 -> COMPLETE, protected change pushed to the bare canonical remote; only a CONFIG_CHANGED event; verify() == []. Under the original config this stops BLOCKED (OWNER_DECISION) (L-AC11/L-AC12).",
  "suggested_fix": "Bind the config hash in the PLAN event; on a changed config block (OWNER_DECISION/CONFIG) until `unblock --note` acknowledges it, and record the policy-relevant fields in the chain; consider keeping authorisation flags out of the agent-written config."
 }
]

End your final message with:
REPAIR_RESULT_BEGIN
{"repaired": ["<finding id>"], "not_repaired": [{"id": "...", "reason": "..."}],
 "regression_tests": ["path/to/test_file.py"], "notes": "..."}
REPAIR_RESULT_END
