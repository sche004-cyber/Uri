You are the IMPLEMENTER repairing URI milestone DEV-LIFECYCLE-1 at commit fbac43727f89b6e43188a8dee5772cf4b49ee65c.
An independent reviewer reported the blocking findings below. Make the minimal, justified repair for each, in this
working tree only. For every code finding add or extend a regression test that FAILS on fbac43727f89b6e43188a8dee5772cf4b49ee65c and PASSES after
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
  "id": "R1-01",
  "severity": "HIGH",
  "blocking": true,
  "category": "security",
  "owner_decision": false,
  "title": "Effective verdict is read from an unbound, mutable reviewer_result.txt; a lingering worker child can turn a genuine REJECT into ACCEPT and verify() stays clean",
  "files": [
   "scripts/dev_workflow/lifecycle.py:751",
   "scripts/dev_workflow/lifecycle.py:752",
   "scripts/dev_workflow/lifecycle.py:1507",
   "scripts/dev_workflow/lifecycle_providers.py:174",
   "docs/dev_workflow/URI_DEVELOPMENT_LIFECYCLE.md:6"
  ],
  "evidence": "do_review pops w['result_text'] (in-memory text whose sha is result_text_sha256) and instead re-reads rounds/R<n>/reviewer_result.txt after the post-run snapshot; nothing compares that file to result_text_sha256, and verify() only hashes reviewer_stdout.txt for non-imported rounds. Probe /tmp/uri_review_R1/probe_forge.py (DEVTEST fixture, reviewer=always_reject): implementer /tmp/uri_review_R1/evil_impl.py makes a plausible fix and starts a start_new_session watcher (escapes killpg) that overwrites rounds/R2/reviewer_result.txt with {candidate:<sha from reviewer_prompt.md>, verdict: ACCEPT, findings: []}. Result: stage COMPLETE, R2 recorded ACCEPT/COMPLETED_WITH_RESULT/independent, integration INTEGRATED (remote tip == candidate), verify() == []; reviewer_stdout.txt still holds the genuine REJECT with HIGH R2-01. Same code path for claude_cli. Disproves the doc limit that setsid children's later writes are 'caught by the clean-worktree checks' (state_dir is not checked).",
  "suggested_fix": "Parse the verdict from the in-memory result_text returned by run_worker (or re-derive it from reviewer_stdout.txt and require sha256 == stdout_sha256/result_text_sha256 before parsing); make verify() check reviewer_result.txt against result_sha256 and re-derive the parsed result from the hashed raw output; keep state_dir outside anything workers can reach or check it in the integrity snapshot; correct the \u00a76 limitation text."
 },
 {
  "id": "R1-02",
  "severity": "MEDIUM",
  "blocking": true,
  "category": "code",
  "owner_decision": false,
  "title": "Malformed findings (dict, strings, scalar) are silently dropped and yield ACCEPT",
  "files": [
   "scripts/dev_workflow/lifecycle.py:264"
  ],
  "evidence": "effective_verdict({'verdict':'ACCEPT','findings':{'R1-01':{'severity':'HIGH','blocking':True}}}) -> ('ACCEPT', []); same for findings=['R1-01 HIGH: auth bypass'] and findings='HIGH: something'. Non-dict items and non-list containers are filtered out instead of making the result unparseable, contrary to L-AC3/L-AC4 (no false ACCEPT).",
  "suggested_fix": "Treat a result whose findings is not a list of dicts (or any finding missing severity/id) as NO_RESULT/unparseable (WAITING_FOR_MODEL), never ACCEPT; add a regression test."
 },
 {
  "id": "R1-03",
  "severity": "MEDIUM",
  "blocking": true,
  "category": "code",
  "owner_decision": false,
  "title": "Gate-finding regression proof skips class-based pytest ids and Flutter ids (earlier R5 finding still unrepaired)",
  "files": [
   "scripts/dev_workflow/lifecycle.py:618",
   "scripts/dev_workflow/lifecycle.py:935",
   "docs/dev_workflow/LIFECYCLE_QUALIFICATION.md:104"
  ],
  "evidence": "_test_file('tests.dev_workflow.test_state_machine.TestX::test_y') -> 'tests.dev_workflow.test_state_machine.TestX' (not a file); _test_file('test/widget_test.dart::App renders') -> 'test/widget_test.dart' (relative to the gate cwd uri_ui/, not the repo root). _commit_and_prove keeps only gate files that exist under wt, so such gate tests are dropped from must_fail and defect stays False (category 'test'): the failing gate test is never proven to fail before/pass after, contrary to URI_DEVELOPMENT_LIFECYCLE.md \u00a73 'gate tests named by gate findings must each fail before'. LIFECYCLE_QUALIFICATION.md says the R5 findings 'stay pending'.",
  "suggested_fix": "Map junit classname to the module path (strip trailing class components until a file exists) and resolve Flutter ids against the gate's cwd; refuse a gate repair whose named test cannot be resolved instead of silently relaxing the proof."
 },
 {
  "id": "R1-04",
  "severity": "MEDIUM",
  "blocking": true,
  "category": "security",
  "owner_decision": false,
  "title": "Git hooks/config/info tamper detection is not anchored: a change caught once becomes the new baseline, and the diagnosis worker is never checked",
  "files": [
   "scripts/dev_workflow/lifecycle.py:733",
   "scripts/dev_workflow/lifecycle.py:739",
   "scripts/dev_workflow/lifecycle.py:981",
   "scripts/dev_workflow/lifecycle.py:1020"
  ],
  "evidence": "do_review takes a fresh 'before' git_control_digest each round and do_repair a fresh ctl0; neither is compared with a digest bound at PLAN. A reviewer that changes .git/config or info/ makes its own round NOT_INDEPENDENT -> WAITING_FOR_MODEL, which resumes automatically on the next run with no owner step, and the changed config is then the 'before' state of every later round. do_diagnosis checks only that its worktree is clean and HEAD unchanged (line 981): it does not check refs_digest or git_control_digest, although the docs say the diagnoser 'changes nothing'. Impact through config-executed commands (e.g. core.fsmonitor running on the driver's git status) is NOT verified here (the probe command was denied).",
  "suggested_fix": "Record git_control_digest (and refs_digest of protected refs) in the PLAN event and require equality before every worker and at evidence_ok; any drift -> BLOCKED TAMPER (owner), not WAITING_FOR_MODEL. Apply the same before/after snapshot to the diagnosis worker. Consider -c core.fsmonitor=false in GIT."
 }
]

End your final message with:
REPAIR_RESULT_BEGIN
{"repaired": ["<finding id>"], "not_repaired": [{"id": "...", "reason": "..."}],
 "regression_tests": ["path/to/test_file.py"], "notes": "..."}
REPAIR_RESULT_END
