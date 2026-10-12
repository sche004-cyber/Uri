You are the IMPLEMENTER repairing URI milestone W1-A0-closure at commit 67aff5042c0f166392281e072fb5f9db906779c5.
An independent reviewer reported the blocking findings below. Make the minimal, justified repair for each, in this
working tree only. For every code finding add or extend a regression test that FAILS on 67aff5042c0f166392281e072fb5f9db906779c5 and PASSES after
your change (it will be run both ways). Do not weaken, skip or delete existing tests. Do not touch protected paths:
uri_core/, uri_supervisor/, uri_supervisor_bridge/, uri_harness_adapters/, model_lab/integration/, scripts/run_uri_supervised_worker.py, scripts/run_uri_phase2_server.py, scripts/run_uri_client_worker.py, scripts/run_uri_isolated_server.py, scripts/c1_bootstrap.py, uri_ui/lib/services/paired_runtime.dart, uri_ui/lib/services/supervised_runtime.dart, uri_ui/lib/screens/settings/paired_runtime_screen.dart, uri_ui/lib/screens/settings/settings_shell.dart, uri_ui/lib/screens/tasks/supervised_execution_screen.dart, .gitignore. Stay inside the permitted paths: uri_web/**, uri_assist/**, tests/web/**, tests/assist/**, uri_ui/lib/living/**, uri_ui/test/living/**, docs/assist/**, scripts/run_uri_integrated_worker.py.
Do not commit or push; the driver commits after checking your change. If a finding cannot be fixed within these
limits, do not work around it: report it as not repaired with the reason.

Environment notes:
- Python with pytest and the repo requirements: /tmp/claude-0/venv/bin/python (use it for tests; do not pip install)
- Flutter SDK: /tmp/claude-0/flutter/bin/flutter (Flutter tests run from uri_ui/)
- Real Chromium for Playwright tests is preinstalled (PLAYWRIGHT_BROWSERS_PATH=/opt/pw-browsers)
- No GPU, no Windows; the Phase 1 checkpoint zip is not present (ws_frozen_check zip part BLOCKED)
- Regression proof: the driver copies ONLY the files you list in regression_tests into a clean checkout of the pre-repair commit and runs them there; new fixture/helper files are NOT copied. Make each regression test self-contained (embed fixture HTML/JS in the test file and write it to tmp_path at run time). A test that is skipped on the pre-repair commit counts as NOT failing, so it must not skip for a missing fixture.
- graphify: do NOT run `graphify update` (or any graphify command that writes) in this working tree, and do not delete or edit anything under graphify-out/: those files are tracked and outside the permitted paths, so the change would be refused. The repository rule 'run graphify update after modifying code' is satisfied by the coordinator, who rebuilds the graph outside the repository. For code navigation use read-only queries: `graphify query "..." --graph /home/user/uri-wt/graphs/W1-A0/graphify-out/graph.json` (also `path`, `explain`).

Findings (from the reviewer, verbatim):
[
 {
  "id": "GATE-python-1",
  "severity": "HIGH",
  "blocking": true,
  "category": "test",
  "title": "gate python: new failure tests.oi.test_oi_answer_planner_ledger::test_action_marker_split_across_chunks_is_never_shown",
  "files": [
   "tests/oi/test_oi_answer_planner_ledger.py"
  ],
  "evidence": "failed on teardown with \"ModuleNotFoundError: No module named 'msvcrt'\""
 },
 {
  "id": "GATE-python-2",
  "severity": "HIGH",
  "blocking": true,
  "category": "test",
  "title": "gate python: new failure tests.oi.test_oi_answer_planner_ledger::test_documented_status_is_labelled_and_never_offered",
  "files": [
   "tests/oi/test_oi_answer_planner_ledger.py"
  ],
  "evidence": "failed on teardown with \"ModuleNotFoundError: No module named 'msvcrt'\""
 },
 {
  "id": "GATE-python-3",
  "severity": "HIGH",
  "blocking": true,
  "category": "test",
  "title": "gate python: new failure tests.oi.test_oi_answer_planner_ledger::test_documented_status_without_manifest_is_unknown",
  "files": [
   "tests/oi/test_oi_answer_planner_ledger.py"
  ],
  "evidence": "failed on teardown with \"ModuleNotFoundError: No module named 'msvcrt'\""
 },
 {
  "id": "GATE-python-4",
  "severity": "HIGH",
  "blocking": true,
  "category": "test",
  "title": "gate python: new failure tests.oi.test_oi_answer_planner_ledger::test_harness_choice_explicit_and_history",
  "files": [
   "tests/oi/test_oi_answer_planner_ledger.py"
  ],
  "evidence": "failed on teardown with \"ModuleNotFoundError: No module named 'msvcrt'\""
 },
 {
  "id": "GATE-python-5",
  "severity": "HIGH",
  "blocking": true,
  "category": "test",
  "title": "gate python: new failure tests.oi.test_oi_answer_planner_ledger::test_harness_choice_never_selects_without_the_user",
  "files": [
   "tests/oi/test_oi_answer_planner_ledger.py"
  ],
  "evidence": "failed on teardown with \"ModuleNotFoundError: No module named 'msvcrt'\""
 },
 {
  "id": "GATE-python-6",
  "severity": "HIGH",
  "blocking": true,
  "category": "test",
  "title": "gate python: new failure tests.oi.test_oi_answer_planner_ledger::test_harness_choice_quota_exclusion_and_reasons",
  "files": [
   "tests/oi/test_oi_answer_planner_ledger.py"
  ],
  "evidence": "failed on teardown with \"ModuleNotFoundError: No module named 'msvcrt'\""
 },
 {
  "id": "GATE-python-7",
  "severity": "HIGH",
  "blocking": true,
  "category": "test",
  "title": "gate python: new failure tests.oi.test_oi_answer_planner_ledger::test_ledger_ids_are_uuids_only",
  "files": [
   "tests/oi/test_oi_answer_planner_ledger.py"
  ],
  "evidence": "failed on teardown with \"ModuleNotFoundError: No module named 'msvcrt'\""
 },
 {
  "id": "GATE-python-8",
  "severity": "HIGH",
  "blocking": true,
  "category": "test",
  "title": "gate python: new failure tests.oi.test_oi_answer_planner_ledger::test_ledger_restart_recovery_never_retries_possible_execution",
  "files": [
   "tests/oi/test_oi_answer_planner_ledger.py"
  ],
  "evidence": "failed on teardown with \"ModuleNotFoundError: No module named 'msvcrt'\""
 },
 {
  "id": "GATE-python-9",
  "severity": "HIGH",
  "blocking": true,
  "category": "test",
  "title": "gate python: new failure tests.oi.test_oi_answer_planner_ledger::test_ledger_transitions_and_completion",
  "files": [
   "tests/oi/test_oi_answer_planner_ledger.py"
  ],
  "evidence": "failed on teardown with \"ModuleNotFoundError: No module named 'msvcrt'\""
 },
 {
  "id": "GATE-python-10",
  "severity": "HIGH",
  "blocking": true,
  "category": "test",
  "title": "gate python: new failure tests.oi.test_oi_answer_planner_ledger::test_messages_layout_is_stable_system_first_current_turn_last",
  "files": [
   "tests/oi/test_oi_answer_planner_ledger.py"
  ],
  "evidence": "failed on teardown with \"ModuleNotFoundError: No module named 'msvcrt'\""
 },
 {
  "id": "GATE-python-11",
  "severity": "HIGH",
  "blocking": true,
  "category": "test",
  "title": "gate python: new failure tests.oi.test_oi_answer_planner_ledger::test_negated_spans_are_never_executable[Do not delete the old files; archive them.-delete the old files-True]",
  "files": [
   "tests/oi/test_oi_answer_planner_ledger.py"
  ],
  "evidence": "failed on teardown with \"ModuleNotFoundError: No module named 'msvcrt'\""
 },
 {
  "id": "GATE-python-12",
  "severity": "HIGH",
  "blocking": true,
  "category": "test",
  "title": "gate python: new failure tests.oi.test_oi_answer_planner_ledger::test_negated_spans_are_never_executable[Don't email Ravi, just draft the reply.-email Ravi-True]",
  "files": [
   "tests/oi/test_oi_answer_planner_ledger.py"
  ],
  "evidence": "failed on teardown with \"ModuleNotFoundError: No module named 'msvcrt'\""
 },
 {
  "id": "GATE-python-13",
  "severity": "HIGH",
  "blocking": true,
  "category": "test",
  "title": "gate python: new failure tests.oi.test_oi_answer_planner_ledger::test_negated_spans_are_never_executable[Draft the reply instead of emailing Ravi.-emailing Ravi-True]",
  "files": [
   "tests/oi/test_oi_answer_planner_ledger.py"
  ],
  "evidence": "failed on teardown with \"ModuleNotFoundError: No module named 'msvcrt'\""
 },
 {
  "id": "GATE-python-14",
  "severity": "HIGH",
  "blocking": true,
  "category": "test",
  "title": "gate python: new failure tests.oi.test_oi_answer_planner_ledger::test_negated_spans_are_never_executable[Draft the reply, then email Ravi.-email Ravi-False]",
  "files": [
   "tests/oi/test_oi_answer_planner_ledger.py"
  ],
  "evidence": "failed on teardown with \"ModuleNotFoundError: No module named 'msvcrt'\""
 },
 {
  "id": "GATE-python-15",
  "severity": "HIGH",
  "blocking": true,
  "category": "test",
  "title": "gate python: new failure tests.oi.test_oi_answer_planner_ledger::test_negated_spans_are_never_executable[I don't know the date, but remember that the audit is on Monday.-remember that the audit is on Monday-False]",
  "files": [
   "tests/oi/test_oi_answer_planner_ledger.py"
  ],
  "evidence": "failed on teardown with \"ModuleNotFoundError: No module named 'msvcrt'\""
 },
 {
  "id": "GATE-python-16",
  "severity": "HIGH",
  "blocking": true,
  "category": "test",
  "title": "gate python: new failure tests.oi.test_oi_answer_planner_ledger::test_negated_spans_are_never_executable[Never send it to the principal.-send it to the principal-True]",
  "files": [
   "tests/oi/test_oi_answer_planner_ledger.py"
  ],
  "evidence": "failed on teardown with \"ModuleNotFoundError: No module named 'msvcrt'\""
 },
 {
  "id": "GATE-python-17",
  "severity": "HIGH",
  "blocking": true,
  "category": "test",
  "title": "gate python: new failure tests.oi.test_oi_answer_planner_ledger::test_normal_answer_is_released_and_marker_check_does_not_delay_much",
  "files": [
   "tests/oi/test_oi_answer_planner_ledger.py"
  ],
  "evidence": "failed on teardown with \"ModuleNotFoundError: No module named 'msvcrt'\""
 },
 {
  "id": "GATE-python-18",
  "severity": "HIGH",
  "blocking": true,
  "category": "test",
  "title": "gate python: new failure tests.oi.test_oi_answer_planner_ledger::test_normal_tier_request_parameters_and_length_escalation",
  "files": [
   "tests/oi/test_oi_answer_planner_ledger.py"
  ],
  "evidence": "failed on teardown with \"ModuleNotFoundError: No module named 'msvcrt'\""
 },
 {
  "id": "GATE-python-19",
  "severity": "HIGH",
  "blocking": true,
  "category": "test",
  "title": "gate python: new failure tests.oi.test_oi_answer_planner_ledger::test_plan_validation_accepts_verbatim_spans",
  "files": [
   "tests/oi/test_oi_answer_planner_ledger.py"
  ],
  "evidence": "failed on teardown with \"ModuleNotFoundError: No module named 'msvcrt'\""
 },
 {
  "id": "GATE-python-20",
  "severity": "HIGH",
  "blocking": true,
  "category": "test",
  "title": "gate python: new failure tests.oi.test_oi_answer_planner_ledger::test_plan_validation_downgrades_model_written_spans",
  "files": [
   "tests/oi/test_oi_answer_planner_ledger.py"
  ],
  "evidence": "failed on teardown with \"ModuleNotFoundError: No module named 'msvcrt'\""
 },
 {
  "id": "GATE-python-21",
  "severity": "HIGH",
  "blocking": true,
  "category": "test",
  "title": "gate python: new failure tests.oi.test_oi_answer_planner_ledger::test_plan_validation_rejects_unknown_capability_and_forward_dependencies",
  "files": [
   "tests/oi/test_oi_answer_planner_ledger.py"
  ],
  "evidence": "failed on teardown with \"ModuleNotFoundError: No module named 'msvcrt'\""
 },
 {
  "id": "GATE-python-22",
  "severity": "HIGH",
  "blocking": true,
  "category": "test",
  "title": "gate python: new failure tests.oi.test_oi_answer_planner_ledger::test_propose_plan_uses_normal_tier_and_schema",
  "files": [
   "tests/oi/test_oi_answer_planner_ledger.py"
  ],
  "evidence": "failed on teardown with \"ModuleNotFoundError: No module named 'msvcrt'\""
 },
 {
  "id": "GATE-python-23",
  "severity": "HIGH",
  "blocking": true,
  "category": "test",
  "title": "gate python: new failure tests.oi.test_oi_answer_planner_ledger::test_reply_that_is_a_strict_prefix_of_the_marker_is_still_delivered",
  "files": [
   "tests/oi/test_oi_answer_planner_ledger.py"
  ],
  "evidence": "failed on teardown with \"ModuleNotFoundError: No module named 'msvcrt'\""
 },
 {
  "id": "GATE-python-24",
  "severity": "HIGH",
  "blocking": true,
  "category": "test",
  "title": "gate python: new failure tests.oi.test_oi_answer_planner_ledger::test_unverified_action_claim_is_flagged_and_corrected",
  "files": [
   "tests/oi/test_oi_answer_planner_ledger.py"
  ],
  "evidence": "failed on teardown with \"ModuleNotFoundError: No module named 'msvcrt'\""
 },
 {
  "id": "GATE-python-25",
  "severity": "HIGH",
  "blocking": true,
  "category": "test",
  "title": "gate python: new failure tests.oi.test_oi_audit_r1_regressions::test_attach_requires_artifact_match",
  "files": [
   "tests/oi/test_oi_audit_r1_regressions.py"
  ],
  "evidence": "failed on teardown with \"ModuleNotFoundError: No module named 'msvcrt'\""
 },
 {
  "id": "GATE-python-26",
  "severity": "HIGH",
  "blocking": true,
  "category": "test",
  "title": "gate python: new failure tests.oi.test_oi_audit_r1_regressions::test_complete_json_unknown_finish_reason_is_not_success",
  "files": [
   "tests/oi/test_oi_audit_r1_regressions.py"
  ],
  "evidence": "failed on teardown with \"ModuleNotFoundError: No module named 'msvcrt'\""
 },
 {
  "id": "GATE-python-27",
  "severity": "HIGH",
  "blocking": true,
  "category": "test",
  "title": "gate python: new failure tests.oi.test_oi_audit_r1_regressions::test_core_receives_the_users_exact_characters",
  "files": [
   "tests/oi/test_oi_audit_r1_regressions.py"
  ],
  "evidence": "failed on teardown with \"ModuleNotFoundError: No module named 'msvcrt'\""
 },
 {
  "id": "GATE-python-28",
  "severity": "HIGH",
  "blocking": true,
  "category": "test",
  "title": "gate python: new failure tests.oi.test_oi_audit_r1_regressions::test_decide_step_denied_never_marks_executing",
  "files": [
   "tests/oi/test_oi_audit_r1_regressions.py"
  ],
  "evidence": "failed on teardown with \"ModuleNotFoundError: No module named 'msvcrt'\""
 },
 {
  "id": "GATE-python-29",
  "severity": "HIGH",
  "blocking": true,
  "category": "test",
  "title": "gate python: new failure tests.oi.test_oi_audit_r1_regressions::test_decide_step_transport_error_marks_uncertain",
  "files": [
   "tests/oi/test_oi_audit_r1_regressions.py"
  ],
  "evidence": "failed on teardown with \"ModuleNotFoundError: No module named 'msvcrt'\""
 },
 {
  "id": "GATE-python-30",
  "severity": "HIGH",
  "blocking": true,
  "category": "test",
  "title": "gate python: new failure tests.oi.test_oi_audit_r1_regressions::test_hash_cache_requires_file_identity",
  "files": [
   "tests/oi/test_oi_audit_r1_regressions.py"
  ],
  "evidence": "failed on teardown with \"ModuleNotFoundError: No module named 'msvcrt'\""
 },
 {
  "id": "GATE-python-31",
  "severity": "HIGH",
  "blocking": true,
  "category": "test",
  "title": "gate python: new failure tests.oi.test_oi_audit_r1_regressions::test_long_range_negation_rejected[Do not under any circumstances email Ravi.-email Ravi]",
  "files": [
   "tests/oi/test_oi_audit_r1_regressions.py"
  ],
  "evidence": "failed on teardown with \"ModuleNotFoundError: No module named 'msvcrt'\""
 },
 {
  "id": "GATE-python-32",
  "severity": "HIGH",
  "blocking": true,
  "category": "test",
  "title": "gate python: new failure tests.oi.test_oi_audit_r1_regressions::test_long_range_negation_rejected[I never want you to send it to the principal.-send it to the principal]",
  "files": [
   "tests/oi/test_oi_audit_r1_regressions.py"
  ],
  "evidence": "failed on teardown with \"ModuleNotFoundError: No module named 'msvcrt'\""
 },
 {
  "id": "GATE-python-33",
  "severity": "HIGH",
  "blocking": true,
  "category": "test",
  "title": "gate python: new failure tests.oi.test_oi_audit_r1_regressions::test_long_range_negation_rejected[Please don't, whatever happens tomorrow, delete the reports.-delete the reports]",
  "files": [
   "tests/oi/test_oi_audit_r1_regressions.py"
  ],
  "evidence": "failed on teardown with \"ModuleNotFoundError: No module named 'msvcrt'\""
 },
 {
  "id": "GATE-python-34",
  "severity": "HIGH",
  "blocking": true,
  "category": "test",
  "title": "gate python: new failure tests.oi.test_oi_audit_r1_regressions::test_skip_propagates_transitively",
  "files": [
   "tests/oi/test_oi_audit_r1_regressions.py"
  ],
  "evidence": "failed on teardown with \"ModuleNotFoundError: No module named 'msvcrt'\""
 },
 {
  "id": "GATE-python-35",
  "severity": "HIGH",
  "blocking": true,
  "category": "test",
  "title": "gate python: new failure tests.oi.test_oi_audit_r1_regressions::test_sse_disconnect_cancels_turn",
  "files": [
   "tests/oi/test_oi_audit_r1_regressions.py"
  ],
  "evidence": "failed on teardown with \"ModuleNotFoundError: No module named 'msvcrt'\""
 },
 {
  "id": "GATE-python-36",
  "severity": "HIGH",
  "blocking": true,
  "category": "test",
  "title": "gate python: new failure tests.oi.test_oi_audit_r1_regressions::test_step_is_durably_executing_before_core_receives_the_approval",
  "files": [
   "tests/oi/test_oi_audit_r1_regressions.py"
  ],
  "evidence": "failed on teardown with \"ModuleNotFoundError: No module named 'msvcrt'\""
 },
 {
  "id": "GATE-python-37",
  "severity": "HIGH",
  "blocking": true,
  "category": "test",
  "title": "gate python: new failure tests.oi.test_oi_audit_r1_regressions::test_success_allowlists",
  "files": [
   "tests/oi/test_oi_audit_r1_regressions.py"
  ],
  "evidence": "failed on teardown with \"ModuleNotFoundError: No module named 'msvcrt'\""
 },
 {
  "id": "GATE-python-38",
  "severity": "HIGH",
  "blocking": true,
  "category": "test",
  "title": "gate python: new failure tests.oi.test_oi_audit_r1_regressions::test_waiting_for_model_emits_choice_without_switching",
  "files": [
   "tests/oi/test_oi_audit_r1_regressions.py"
  ],
  "evidence": "failed on teardown with \"ModuleNotFoundError: No module named 'msvcrt'\""
 },
 {
  "id": "GATE-python-39",
  "severity": "HIGH",
  "blocking": true,
  "category": "test",
  "title": "gate python: new failure tests.oi.test_oi_audit_r2_regressions::test_action_step_conversation_is_refused_and_blocks_dependents",
  "files": [
   "tests/oi/test_oi_audit_r2_regressions.py"
  ],
  "evidence": "failed on teardown with \"ModuleNotFoundError: No module named 'msvcrt'\""
 },
 {
  "id": "GATE-python-40",
  "severity": "HIGH",
  "blocking": true,
  "category": "test",
  "title": "gate python: new failure tests.oi.test_oi_audit_r2_regressions::test_claim_cannot_be_taken_twice",
  "files": [
   "tests/oi/test_oi_audit_r2_regressions.py"
  ],
  "evidence": "failed on teardown with \"ModuleNotFoundError: No module named 'msvcrt'\""
 },
 {
  "id": "GATE-python-41",
  "severity": "HIGH",
  "blocking": true,
  "category": "test",
  "title": "gate python: new failure tests.oi.test_oi_audit_r2_regressions::test_concurrent_advance_dispatches_once",
  "files": [
   "tests/oi/test_oi_audit_r2_regressions.py"
  ],
  "evidence": "failed on teardown with \"ModuleNotFoundError: No module named 'msvcrt'\""
 },
 {
  "id": "GATE-python-42",
  "severity": "HIGH",
  "blocking": true,
  "category": "test",
  "title": "gate python: new failure tests.oi.test_oi_audit_r2_regressions::test_partial_word_spans_rejected[Please deactivate account 42 today.-activate account]",
  "files": [
   "tests/oi/test_oi_audit_r2_regressions.py"
  ],
  "evidence": "failed on teardown with \"ModuleNotFoundError: No module named 'msvcrt'\""
 },
 {
  "id": "GATE-python-43",
  "severity": "HIGH",
  "blocking": true,
  "category": "test",
  "title": "gate python: new failure tests.oi.test_oi_audit_r2_regressions::test_partial_word_spans_rejected[Reschedule the meeting.-schedule the meeting]",
  "files": [
   "tests/oi/test_oi_audit_r2_regressions.py"
  ],
  "evidence": "failed on teardown with \"ModuleNotFoundError: No module named 'msvcrt'\""
 },
 {
  "id": "GATE-python-44",
  "severity": "HIGH",
  "blocking": true,
  "category": "test",
  "title": "gate python: new failure tests.oi.test_oi_audit_r2_regressions::test_partial_word_spans_rejected[Unsubscribe me from the newsletter.-subscribe me]",
  "files": [
   "tests/oi/test_oi_audit_r2_regressions.py"
  ],
  "evidence": "failed on teardown with \"ModuleNotFoundError: No module named 'msvcrt'\""
 },
 {
  "id": "GATE-python-45",
  "severity": "HIGH",
  "blocking": true,
  "category": "test",
  "title": "gate python: new failure tests.oi.test_oi_audit_r2_regressions::test_record_step_cannot_settle_an_approval_directly",
  "files": [
   "tests/oi/test_oi_audit_r2_regressions.py"
  ],
  "evidence": "failed on teardown with \"ModuleNotFoundError: No module named 'msvcrt'\""
 },
 {
  "id": "GATE-python-46",
  "severity": "HIGH",
  "blocking": true,
  "category": "test",
  "title": "gate python: new failure tests.oi.test_oi_audit_r2_regressions::test_status_ready_requires_artifacts",
  "files": [
   "tests/oi/test_oi_audit_r2_regressions.py"
  ],
  "evidence": "failed on teardown with \"ModuleNotFoundError: No module named 'msvcrt'\""
 },
 {
  "id": "GATE-python-47",
  "severity": "HIGH",
  "blocking": true,
  "category": "test",
  "title": "gate python: new failure tests.oi.test_oi_audit_r2_regressions::test_whole_word_span_still_accepted",
  "files": [
   "tests/oi/test_oi_audit_r2_regressions.py"
  ],
  "evidence": "failed on teardown with \"ModuleNotFoundError: No module named 'msvcrt'\""
 },
 {
  "id": "GATE-python-48",
  "severity": "HIGH",
  "blocking": true,
  "category": "test",
  "title": "gate python: new failure tests.oi.test_oi_audit_r3_regressions::test_concurrent_confirm_step_reaches_core_once",
  "files": [
   "tests/oi/test_oi_audit_r3_regressions.py"
  ],
  "evidence": "failed on teardown with \"ModuleNotFoundError: No module named 'msvcrt'\""
 },
 {
  "id": "GATE-python-49",
  "severity": "HIGH",
  "blocking": true,
  "category": "test",
  "title": "gate python: new failure tests.oi.test_oi_audit_r3_regressions::test_quota_pause_after_approval",
  "files": [
   "tests/oi/test_oi_audit_r3_regressions.py"
  ],
  "evidence": "failed on teardown with \"ModuleNotFoundError: No module named 'msvcrt'\""
 },
 {
  "id": "GATE-python-50",
  "severity": "HIGH",
  "blocking": true,
  "category": "test",
  "title": "gate python: new failure tests.oi.test_oi_audit_r3_regressions::test_ready_rechecked_on_every_probe",
  "files": [
   "tests/oi/test_oi_audit_r3_regressions.py"
  ],
  "evidence": "failed on teardown with \"ModuleNotFoundError: No module named 'msvcrt'\""
 },
 {
  "id": "GATE-python-51",
  "severity": "HIGH",
  "blocking": true,
  "category": "test",
  "title": "gate python: new failure tests.oi.test_oi_audit_r3_regressions::test_second_process_cannot_write_or_recover",
  "files": [
   "tests/oi/test_oi_audit_r3_regressions.py"
  ],
  "evidence": "failed on teardown with \"ModuleNotFoundError: No module named 'msvcrt'\""
 },
 {
  "id": "GATE-python-52",
  "severity": "HIGH",
  "blocking": true,
  "category": "test",
  "title": "gate python: new failure tests.oi.test_oi_audit_r3_regressions::test_single_turn_apis_refuse_plan_step_turns",
  "files": [
   "tests/oi/test_oi_audit_r3_regressions.py"
  ],
  "evidence": "failed on teardown with \"ModuleNotFoundError: No module named 'msvcrt'\""
 },
 {
  "id": "GATE-python-53",
  "severity": "HIGH",
  "blocking": true,
  "category": "test",
  "title": "gate python: new failure tests.oi.test_oi_audit_r3_regressions::test_span_boundaries[Don't re-send the invoice.-send the invoice-False]",
  "files": [
   "tests/oi/test_oi_audit_r3_regressions.py"
  ],
  "evidence": "failed on teardown with \"ModuleNotFoundError: No module named 'msvcrt'\""
 },
 {
  "id": "GATE-python-54",
  "severity": "HIGH",
  "blocking": true,
  "category": "test",
  "title": "gate python: new failure tests.oi.test_oi_audit_r3_regressions::test_span_boundaries[Email: send it (now)-send it (now)-True]",
  "files": [
   "tests/oi/test_oi_audit_r3_regressions.py"
  ],
  "evidence": "failed on teardown with \"ModuleNotFoundError: No module named 'msvcrt'\""
 },
 {
  "id": "GATE-python-55",
  "severity": "HIGH",
  "blocking": true,
  "category": "test",
  "title": "gate python: new failure tests.oi.test_oi_audit_r3_regressions::test_span_boundaries[Please activate account 42.-activate account-True]",
  "files": [
   "tests/oi/test_oi_audit_r3_regressions.py"
  ],
  "evidence": "failed on teardown with \"ModuleNotFoundError: No module named 'msvcrt'\""
 },
 {
  "id": "GATE-python-56",
  "severity": "HIGH",
  "blocking": true,
  "category": "test",
  "title": "gate python: new failure tests.oi.test_oi_audit_r3_regressions::test_span_boundaries[Please de-activate account 42.--activate account-False]",
  "files": [
   "tests/oi/test_oi_audit_r3_regressions.py"
  ],
  "evidence": "failed on teardown with \"ModuleNotFoundError: No module named 'msvcrt'\""
 },
 {
  "id": "GATE-python-57",
  "severity": "HIGH",
  "blocking": true,
  "category": "test",
  "title": "gate python: new failure tests.oi.test_oi_audit_r3_regressions::test_span_boundaries[Please de-activate account 42.-activate account-False]",
  "files": [
   "tests/oi/test_oi_audit_r3_regressions.py"
  ],
  "evidence": "failed on teardown with \"ModuleNotFoundError: No module named 'msvcrt'\""
 },
 {
  "id": "GATE-python-58",
  "severity": "HIGH",
  "blocking": true,
  "category": "test",
  "title": "gate python: new failure tests.oi.test_oi_audit_r3_regressions::test_unexpected_reply_after_approval_is_uncertain",
  "files": [
   "tests/oi/test_oi_audit_r3_regressions.py"
  ],
  "evidence": "failed on teardown with \"ModuleNotFoundError: No module named 'msvcrt'\""
 },
 {
  "id": "GATE-python-59",
  "severity": "HIGH",
  "blocking": true,
  "category": "test",
  "title": "gate python: new failure tests.oi.test_oi_audit_r3_regressions::test_unicode_punctuation[Email\\xa0Ravi the timetable.-Email Ravi-ok]",
  "files": [
   "tests/oi/test_oi_audit_r3_regressions.py"
  ],
  "evidence": "failed on teardown with \"ModuleNotFoundError: No module named 'msvcrt'\""
 },
 {
  "id": "GATE-python-60",
  "severity": "HIGH",
  "blocking": true,
  "category": "test",
  "title": "gate python: new failure tests.oi.test_oi_audit_r3_regressions::test_unicode_punctuation[Please de\\u2013activate account 42.-activate account-no_match]",
  "files": [
   "tests/oi/test_oi_audit_r3_regressions.py"
  ],
  "evidence": "failed on teardown with \"ModuleNotFoundError: No module named 'msvcrt'\""
 },
 {
  "id": "GATE-python-61",
  "severity": "HIGH",
  "blocking": true,
  "category": "test",
  "title": "gate python: new failure tests.oi.test_oi_audit_r3_regressions::test_unicode_punctuation[Please don\\u2019t email Ravi.-email Ravi-negated]",
  "files": [
   "tests/oi/test_oi_audit_r3_regressions.py"
  ],
  "evidence": "failed on teardown with \"ModuleNotFoundError: No module named 'msvcrt'\""
 },
 {
  "id": "GATE-python-62",
  "severity": "HIGH",
  "blocking": true,
  "category": "test",
  "title": "gate python: new failure tests.oi.test_oi_audit_r3_regressions::test_unicode_punctuation[Please re\\u2010send invoice 7.-send invoice-no_match]",
  "files": [
   "tests/oi/test_oi_audit_r3_regressions.py"
  ],
  "evidence": "failed on teardown with \"ModuleNotFoundError: No module named 'msvcrt'\""
 },
 {
  "id": "GATE-python-63",
  "severity": "HIGH",
  "blocking": true,
  "category": "test",
  "title": "gate python: new failure tests.oi.test_oi_audit_r5_regressions::test_registry_is_bounded",
  "files": [
   "tests/oi/test_oi_audit_r5_regressions.py"
  ],
  "evidence": "failed on teardown with \"ModuleNotFoundError: No module named 'msvcrt'\""
 },
 {
  "id": "GATE-python-64",
  "severity": "HIGH",
  "blocking": true,
  "category": "test",
  "title": "gate python: new failure tests.oi.test_oi_audit_r5_regressions::test_spliced_payload_under_registered_id_refused",
  "files": [
   "tests/oi/test_oi_audit_r5_regressions.py"
  ],
  "evidence": "failed on teardown with \"ModuleNotFoundError: No module named 'msvcrt'\""
 },
 {
  "id": "GATE-python-65",
  "severity": "HIGH",
  "blocking": true,
  "category": "test",
  "title": "gate python: new failure tests.oi.test_oi_audit_r5_regressions::test_tampered_approval_envelope_refused_and_single_use",
  "files": [
   "tests/oi/test_oi_audit_r5_regressions.py"
  ],
  "evidence": "failed on teardown with \"ModuleNotFoundError: No module named 'msvcrt'\""
 },
 {
  "id": "GATE-python-66",
  "severity": "HIGH",
  "blocking": true,
  "category": "test",
  "title": "gate python: new failure tests.oi.test_oi_audit_r5_regressions::test_unicode_categories_folded[Please de\\u2015activate account 42.-activate account-SOURCE_SPAN_NOT_VERBATIM]",
  "files": [
   "tests/oi/test_oi_audit_r5_regressions.py"
  ],
  "evidence": "failed on teardown with \"ModuleNotFoundError: No module named 'msvcrt'\""
 },
 {
  "id": "GATE-python-67",
  "severity": "HIGH",
  "blocking": true,
  "category": "test",
  "title": "gate python: new failure tests.oi.test_oi_audit_r5_regressions::test_unicode_categories_folded[Please don\\u02bct delete the files.-delete the files-SOURCE_SPAN_NEGATED]",
  "files": [
   "tests/oi/test_oi_audit_r5_regressions.py"
  ],
  "evidence": "failed on teardown with \"ModuleNotFoundError: No module named 'msvcrt'\""
 },
 {
  "id": "GATE-python-68",
  "severity": "HIGH",
  "blocking": true,
  "category": "test",
  "title": "gate python: new failure tests.oi.test_oi_audit_r5_regressions::test_unicode_categories_folded[Please don\\u201bt email Ravi.-email Ravi-SOURCE_SPAN_NEGATED]",
  "files": [
   "tests/oi/test_oi_audit_r5_regressions.py"
  ],
  "evidence": "failed on teardown with \"ModuleNotFoundError: No module named 'msvcrt'\""
 },
 {
  "id": "GATE-python-69",
  "severity": "HIGH",
  "blocking": true,
  "category": "test",
  "title": "gate python: new failure tests.oi.test_oi_audit_r5_regressions::test_unicode_categories_folded[Please re\\u2e3asend invoice 7.-send invoice-SOURCE_SPAN_NOT_VERBATIM]",
  "files": [
   "tests/oi/test_oi_audit_r5_regressions.py"
  ],
  "evidence": "failed on teardown with \"ModuleNotFoundError: No module named 'msvcrt'\""
 },
 {
  "id": "GATE-python-70",
  "severity": "HIGH",
  "blocking": true,
  "category": "test",
  "title": "gate python: new failure tests.oi.test_oi_brain_client::test_abandoned_header_wait_disconnects_and_pool_recovers",
  "files": [
   "tests/oi/test_oi_brain_client.py"
  ],
  "evidence": "failed on teardown with \"ModuleNotFoundError: No module named 'msvcrt'\""
 },
 {
  "id": "GATE-python-71",
  "severity": "HIGH",
  "blocking": true,
  "category": "test",
  "title": "gate python: new failure tests.oi.test_oi_brain_client::test_cancel_during_prefill_before_first_token",
  "files": [
   "tests/oi/test_oi_brain_client.py"
  ],
  "evidence": "failed on teardown with \"ModuleNotFoundError: No module named 'msvcrt'\""
 },
 {
  "id": "GATE-python-72",
  "severity": "HIGH",
  "blocking": true,
  "category": "test",
  "title": "gate python: new failure tests.oi.test_oi_brain_client::test_cancel_mid_stream_closes_connection_and_server_sees_disconnect",
  "files": [
   "tests/oi/test_oi_brain_client.py"
  ],
  "evidence": "failed on teardown with \"ModuleNotFoundError: No module named 'msvcrt'\""
 },
 {
  "id": "GATE-python-73",
  "severity": "HIGH",
  "blocking": true,
  "category": "test",
  "title": "gate python: new failure tests.oi.test_oi_brain_client::test_complete_json_paths",
  "files": [
   "tests/oi/test_oi_brain_client.py"
  ],
  "evidence": "failed on teardown with \"ModuleNotFoundError: No module named 'msvcrt'\""
 },
 {
  "id": "GATE-python-74",
  "severity": "HIGH",
  "blocking": true,
  "category": "test",
  "title": "gate python: new failure tests.oi.test_oi_brain_client::test_deadline_and_cancel_work_while_waiting_for_response_headers",
  "files": [
   "tests/oi/test_oi_brain_client.py"
  ],
  "evidence": "failed on teardown with \"ModuleNotFoundError: No module named 'msvcrt'\""
 },
 {
  "id": "GATE-python-75",
  "severity": "HIGH",
  "blocking": true,
  "category": "test",
  "title": "gate python: new failure tests.oi.test_oi_brain_client::test_first_token_timeout",
  "files": [
   "tests/oi/test_oi_brain_client.py"
  ],
  "evidence": "failed on teardown with \"ModuleNotFoundError: No module named 'msvcrt'\""
 },
 {
  "id": "GATE-python-76",
  "severity": "HIGH",
  "blocking": true,
  "category": "test",
  "title": "gate python: new failure tests.oi.test_oi_brain_client::test_http_error_and_bad_sse",
  "files": [
   "tests/oi/test_oi_brain_client.py"
  ],
  "evidence": "failed on teardown with \"ModuleNotFoundError: No module named 'msvcrt'\""
 },
 {
  "id": "GATE-python-77",
  "severity": "HIGH",
  "blocking": true,
  "category": "test",
  "title": "gate python: new failure tests.oi.test_oi_brain_client::test_length_is_incomplete_not_success",
  "files": [
   "tests/oi/test_oi_brain_client.py"
  ],
  "evidence": "failed on teardown with \"ModuleNotFoundError: No module named 'msvcrt'\""
 },
 {
  "id": "GATE-python-78",
  "severity": "HIGH",
  "blocking": true,
  "category": "test",
  "title": "gate python: new failure tests.oi.test_oi_brain_client::test_seam_timeout_disconnects_so_the_server_can_drop_the_generation",
  "files": [
   "tests/oi/test_oi_brain_client.py"
  ],
  "evidence": "failed on teardown with \"ModuleNotFoundError: No module named 'msvcrt'\""
 },
 {
  "id": "GATE-python-79",
  "severity": "HIGH",
  "blocking": true,
  "category": "test",
  "title": "gate python: new failure tests.oi.test_oi_brain_client::test_stall_after_output_began",
  "files": [
   "tests/oi/test_oi_brain_client.py"
  ],
  "evidence": "failed on teardown with \"ModuleNotFoundError: No module named 'msvcrt'\""
 },
 {
  "id": "GATE-python-80",
  "severity": "HIGH",
  "blocking": true,
  "category": "test",
  "title": "gate python: new failure tests.oi.test_oi_brain_client::test_stream_broken_after_output_is_interrupted_not_retried",
  "files": [
   "tests/oi/test_oi_brain_client.py"
  ],
  "evidence": "failed on teardown with \"ModuleNotFoundError: No module named 'msvcrt'\""
 },
 {
  "id": "GATE-python-81",
  "severity": "HIGH",
  "blocking": true,
  "category": "test",
  "title": "gate python: new failure tests.oi.test_oi_brain_client::test_stream_complete_separates_reasoning_and_answer",
  "files": [
   "tests/oi/test_oi_brain_client.py"
  ],
  "evidence": "failed on teardown with \"ModuleNotFoundError: No module named 'msvcrt'\""
 },
 {
  "id": "GATE-python-82",
  "severity": "HIGH",
  "blocking": true,
  "category": "test",
  "title": "gate python: new failure tests.oi.test_oi_brain_client::test_stream_without_finish_is_interrupted",
  "files": [
   "tests/oi/test_oi_brain_client.py"
  ],
  "evidence": "failed on teardown with \"ModuleNotFoundError: No module named 'msvcrt'\""
 },
 {
  "id": "GATE-python-83",
  "severity": "HIGH",
  "blocking": true,
  "category": "test",
  "title": "gate python: new failure tests.oi.test_oi_brain_client::test_total_deadline",
  "files": [
   "tests/oi/test_oi_brain_client.py"
  ],
  "evidence": "failed on teardown with \"ModuleNotFoundError: No module named 'msvcrt'\""
 },
 {
  "id": "GATE-python-84",
  "severity": "HIGH",
  "blocking": true,
  "category": "test",
  "title": "gate python: new failure tests.oi.test_oi_brain_client::test_unreachable_is_reported_after_one_retry",
  "files": [
   "tests/oi/test_oi_brain_client.py"
  ],
  "evidence": "failed on teardown with \"ModuleNotFoundError: No module named 'msvcrt'\""
 },
 {
  "id": "GATE-python-85",
  "severity": "HIGH",
  "blocking": true,
  "category": "test",
  "title": "gate python: new failure tests.oi.test_oi_core_provider::test_describe_never_raises_and_reports_readiness",
  "files": [
   "tests/oi/test_oi_core_provider.py"
  ],
  "evidence": "failed on teardown with \"ModuleNotFoundError: No module named 'msvcrt'\""
 },
 {
  "id": "GATE-python-86",
  "severity": "HIGH",
  "blocking": true,
  "category": "test",
  "title": "gate python: new failure tests.oi.test_oi_core_provider::test_provider_failures_raise_typed_errors_never_text",
  "files": [
   "tests/oi/test_oi_core_provider.py"
  ],
  "evidence": "failed on teardown with \"ModuleNotFoundError: No module named 'msvcrt'\""
 },
 {
  "id": "GATE-python-87",
  "severity": "HIGH",
  "blocking": true,
  "category": "test",
  "title": "gate python: new failure tests.oi.test_oi_core_provider::test_provider_is_fast_tier_json_grammar",
  "files": [
   "tests/oi/test_oi_core_provider.py"
  ],
  "evidence": "failed on teardown with \"ModuleNotFoundError: No module named 'msvcrt'\""
 },
 {
  "id": "GATE-python-88",
  "severity": "HIGH",
  "blocking": true,
  "category": "test",
  "title": "gate python: new failure tests.oi.test_oi_core_provider::test_selection_row_is_explicit_server_local_model",
  "files": [
   "tests/oi/test_oi_core_provider.py"
  ],
  "evidence": "failed on teardown with \"ModuleNotFoundError: No module named 'msvcrt'\""
 },
 {
  "id": "GATE-python-89",
  "severity": "HIGH",
  "blocking": true,
  "category": "test",
  "title": "gate python: new failure tests.oi.test_oi_core_provider::test_snap_and_b1_routing",
  "files": [
   "tests/oi/test_oi_core_provider.py"
  ],
  "evidence": "failed on teardown with \"ModuleNotFoundError: No module named 'msvcrt'\""
 },
 {
  "id": "GATE-python-90",
  "severity": "HIGH",
  "blocking": true,
  "category": "test",
  "title": "gate python: new failure tests.oi.test_oi_orchestrator::test_action_goes_to_core_with_the_explicit_brain_selection",
  "files": [
   "tests/oi/test_oi_orchestrator.py"
  ],
  "evidence": "failed on teardown with \"ModuleNotFoundError: No module named 'msvcrt'\""
 },
 {
  "id": "GATE-python-91",
  "severity": "HIGH",
  "blocking": true,
  "category": "test",
  "title": "gate python: new failure tests.oi.test_oi_orchestrator::test_answer_channel_marker_reroutes_to_core_without_showing_text",
  "files": [
   "tests/oi/test_oi_orchestrator.py"
  ],
  "evidence": "failed on teardown with \"ModuleNotFoundError: No module named 'msvcrt'\""
 },
 {
  "id": "GATE-python-92",
  "severity": "HIGH",
  "blocking": true,
  "category": "test",
  "title": "gate python: new failure tests.oi.test_oi_orchestrator::test_brain_not_ready_is_an_honest_error",
  "files": [
   "tests/oi/test_oi_orchestrator.py"
  ],
  "evidence": "failed on teardown with \"ModuleNotFoundError: No module named 'msvcrt'\""
 },
 {
  "id": "GATE-python-93",
  "severity": "HIGH",
  "blocking": true,
  "category": "test",
  "title": "gate python: new failure tests.oi.test_oi_orchestrator::test_cancel_turn",
  "files": [
   "tests/oi/test_oi_orchestrator.py"
  ],
  "evidence": "failed on teardown with \"ModuleNotFoundError: No module named 'msvcrt'\""
 },
 {
  "id": "GATE-python-94",
  "severity": "HIGH",
  "blocking": true,
  "category": "test",
  "title": "gate python: new failure tests.oi.test_oi_orchestrator::test_core_conversation_falls_back_to_answer_channel",
  "files": [
   "tests/oi/test_oi_orchestrator.py"
  ],
  "evidence": "failed on teardown with \"ModuleNotFoundError: No module named 'msvcrt'\""
 },
 {
  "id": "GATE-python-95",
  "severity": "HIGH",
  "blocking": true,
  "category": "test",
  "title": "gate python: new failure tests.oi.test_oi_orchestrator::test_core_envelope_mapping_never_reads_unknown_as_success[env0-WAITING_APPROVAL]",
  "files": [
   "tests/oi/test_oi_orchestrator.py"
  ],
  "evidence": "failed on teardown with \"ModuleNotFoundError: No module named 'msvcrt'\""
 },
 {
  "id": "GATE-python-96",
  "severity": "HIGH",
  "blocking": true,
  "category": "test",
  "title": "gate python: new failure tests.oi.test_oi_orchestrator::test_core_envelope_mapping_never_reads_unknown_as_success[env1-VERIFIED]",
  "files": [
   "tests/oi/test_oi_orchestrator.py"
  ],
  "evidence": "failed on teardown with \"ModuleNotFoundError: No module named 'msvcrt'\""
 },
 {
  "id": "GATE-python-97",
  "severity": "HIGH",
  "blocking": true,
  "category": "test",
  "title": "gate python: new failure tests.oi.test_oi_orchestrator::test_core_envelope_mapping_never_reads_unknown_as_success[env2-UNCERTAIN]",
  "files": [
   "tests/oi/test_oi_orchestrator.py"
  ],
  "evidence": "failed on teardown with \"ModuleNotFoundError: No module named 'msvcrt'\""
 },
 {
  "id": "GATE-python-98",
  "severity": "HIGH",
  "blocking": true,
  "category": "test",
  "title": "gate python: new failure tests.oi.test_oi_orchestrator::test_core_envelope_mapping_never_reads_unknown_as_success[env3-FAILED]",
  "files": [
   "tests/oi/test_oi_orchestrator.py"
  ],
  "evidence": "failed on teardown with \"ModuleNotFoundError: No module named 'msvcrt'\""
 },
 {
  "id": "GATE-python-99",
  "severity": "HIGH",
  "blocking": true,
  "category": "test",
  "title": "gate python: new failure tests.oi.test_oi_orchestrator::test_core_envelope_mapping_never_reads_unknown_as_success[env4-CANCELLED]",
  "files": [
   "tests/oi/test_oi_orchestrator.py"
  ],
  "evidence": "failed on teardown with \"ModuleNotFoundError: No module named 'msvcrt'\""
 },
 {
  "id": "GATE-python-100",
  "severity": "HIGH",
  "blocking": true,
  "category": "test",
  "title": "gate python: new failure tests.oi.test_oi_orchestrator::test_core_envelope_mapping_never_reads_unknown_as_success[env5-REFUSED]",
  "files": [
   "tests/oi/test_oi_orchestrator.py"
  ],
  "evidence": "failed on teardown with \"ModuleNotFoundError: No module named 'msvcrt'\""
 },
 {
  "id": "GATE-python-101",
  "severity": "HIGH",
  "blocking": true,
  "category": "test",
  "title": "gate python: new failure tests.oi.test_oi_orchestrator::test_core_envelope_mapping_never_reads_unknown_as_success[env6-WAITING_USER_CHOICE]",
  "files": [
   "tests/oi/test_oi_orchestrator.py"
  ],
  "evidence": "failed on teardown with \"ModuleNotFoundError: No module named 'msvcrt'\""
 },
 {
  "id": "GATE-python-102",
  "severity": "HIGH",
  "blocking": true,
  "category": "test",
  "title": "gate python: new failure tests.oi.test_oi_orchestrator::test_core_envelope_mapping_never_reads_unknown_as_success[env7-FAILED]",
  "files": [
   "tests/oi/test_oi_orchestrator.py"
  ],
  "evidence": "failed on teardown with \"ModuleNotFoundError: No module named 'msvcrt'\""
 },
 {
  "id": "GATE-python-103",
  "severity": "HIGH",
  "blocking": true,
  "category": "test",
  "title": "gate python: new failure tests.oi.test_oi_orchestrator::test_core_envelope_mapping_never_reads_unknown_as_success[env8-FAILED]",
  "files": [
   "tests/oi/test_oi_orchestrator.py"
  ],
  "evidence": "failed on teardown with \"ModuleNotFoundError: No module named 'msvcrt'\""
 },
 {
  "id": "GATE-python-104",
  "severity": "HIGH",
  "blocking": true,
  "category": "test",
  "title": "gate python: new failure tests.oi.test_oi_orchestrator::test_core_failure_is_reported_never_guessed",
  "files": [
   "tests/oi/test_oi_orchestrator.py"
  ],
  "evidence": "failed on teardown with \"ModuleNotFoundError: No module named 'msvcrt'\""
 },
 {
  "id": "GATE-python-105",
  "severity": "HIGH",
  "blocking": true,
  "category": "test",
  "title": "gate python: new failure tests.oi.test_oi_orchestrator::test_core_path_with_brain_down_fails_fast_without_calling_core",
  "files": [
   "tests/oi/test_oi_orchestrator.py"
  ],
  "evidence": "failed on teardown with \"ModuleNotFoundError: No module named 'msvcrt'\""
 },
 {
  "id": "GATE-python-106",
  "severity": "HIGH",
  "blocking": true,
  "category": "test",
  "title": "gate python: new failure tests.oi.test_oi_orchestrator::test_deep_depth_is_an_escalation_offer_not_local_unbounded_thinking",
  "files": [
   "tests/oi/test_oi_orchestrator.py"
  ],
  "evidence": "failed on teardown with \"ModuleNotFoundError: No module named 'msvcrt'\""
 },
 {
  "id": "GATE-python-107",
  "severity": "HIGH",
  "blocking": true,
  "category": "test",
  "title": "gate python: new failure tests.oi.test_oi_orchestrator::test_harness_request_needs_explicit_choice_and_calls_nothing",
  "files": [
   "tests/oi/test_oi_orchestrator.py"
  ],
  "evidence": "failed on teardown with \"ModuleNotFoundError: No module named 'msvcrt'\""
 },
 {
  "id": "GATE-python-108",
  "severity": "HIGH",
  "blocking": true,
  "category": "test",
  "title": "gate python: new failure tests.oi.test_oi_orchestrator::test_multi_step_plan_then_steps_through_core",
  "files": [
   "tests/oi/test_oi_orchestrator.py"
  ],
  "evidence": "failed on teardown with \"ModuleNotFoundError: No module named 'msvcrt'\""
 },
 {
  "id": "GATE-python-109",
  "severity": "HIGH",
  "blocking": true,
  "category": "test",
  "title": "gate python: new failure tests.oi.test_oi_orchestrator::test_orchestrator_surfaces_degraded_brain",
  "files": [
   "tests/oi/test_oi_orchestrator.py"
  ],
  "evidence": "failed on teardown with \"ModuleNotFoundError: No module named 'msvcrt'\""
 },
 {
  "id": "GATE-python-110",
  "severity": "HIGH",
  "blocking": true,
  "category": "test",
  "title": "gate python: new failure tests.oi.test_oi_orchestrator::test_perf_monitor_detects_throughput_and_residency_degradation",
  "files": [
   "tests/oi/test_oi_orchestrator.py"
  ],
  "evidence": "failed on teardown with \"ModuleNotFoundError: No module named 'msvcrt'\""
 },
 {
  "id": "GATE-python-111",
  "severity": "HIGH",
  "blocking": true,
  "category": "test",
  "title": "gate python: new failure tests.oi.test_oi_orchestrator::test_simple_question_never_calls_core",
  "files": [
   "tests/oi/test_oi_orchestrator.py"
  ],
  "evidence": "failed on teardown with \"ModuleNotFoundError: No module named 'msvcrt'\""
 },
 {
  "id": "GATE-python-112",
  "severity": "HIGH",
  "blocking": true,
  "category": "test",
  "title": "gate python: new failure tests.oi.test_oi_orchestrator::test_simulator_emits_only_contract_events[answer]",
  "files": [
   "tests/oi/test_oi_orchestrator.py"
  ],
  "evidence": "failed on teardown with \"ModuleNotFoundError: No module named 'msvcrt'\""
 },
 {
  "id": "GATE-python-113",
  "severity": "HIGH",
  "blocking": true,
  "category": "test",
  "title": "gate python: new failure tests.oi.test_oi_orchestrator::test_simulator_emits_only_contract_events[approval]",
  "files": [
   "tests/oi/test_oi_orchestrator.py"
  ],
  "evidence": "failed on teardown with \"ModuleNotFoundError: No module named 'msvcrt'\""
 },
 {
  "id": "GATE-python-114",
  "severity": "HIGH",
  "blocking": true,
  "category": "test",
  "title": "gate python: new failure tests.oi.test_oi_orchestrator::test_simulator_emits_only_contract_events[error]",
  "files": [
   "tests/oi/test_oi_orchestrator.py"
  ],
  "evidence": "failed on teardown with \"ModuleNotFoundError: No module named 'msvcrt'\""
 },
 {
  "id": "GATE-python-115",
  "severity": "HIGH",
  "blocking": true,
  "category": "test",
  "title": "gate python: new failure tests.oi.test_oi_orchestrator::test_simulator_emits_only_contract_events[plan]",
  "files": [
   "tests/oi/test_oi_orchestrator.py"
  ],
  "evidence": "failed on teardown with \"ModuleNotFoundError: No module named 'msvcrt'\""
 },
 {
  "id": "GATE-python-116",
  "severity": "HIGH",
  "blocking": true,
  "category": "test",
  "title": "gate python: new failure tests.oi.test_oi_orchestrator::test_simulator_emits_only_contract_events[quota]",
  "files": [
   "tests/oi/test_oi_orchestrator.py"
  ],
  "evidence": "failed on teardown with \"ModuleNotFoundError: No module named 'msvcrt'\""
 },
 {
  "id": "GATE-python-117",
  "severity": "HIGH",
  "blocking": true,
  "category": "test",
  "title": "gate python: new failure tests.oi.test_oi_orchestrator::test_simulator_emits_only_contract_events[reasoning]",
  "files": [
   "tests/oi/test_oi_orchestrator.py"
  ],
  "evidence": "failed on teardown with \"ModuleNotFoundError: No module named 'msvcrt'\""
 },
 {
  "id": "GATE-python-118",
  "severity": "HIGH",
  "blocking": true,
  "category": "test",
  "title": "gate python: new failure tests.oi.test_oi_orchestrator::test_uncertain_step_blocks_dependents",
  "files": [
   "tests/oi/test_oi_orchestrator.py"
  ],
  "evidence": "failed on teardown with \"ModuleNotFoundError: No module named 'msvcrt'\""
 },
 {
  "id": "GATE-python-119",
  "severity": "HIGH",
  "blocking": true,
  "category": "test",
  "title": "gate python: new failure tests.oi.test_oi_policy_triage::test_normal_length_becomes_escalation_candidate_never_local_retry",
  "files": [
   "tests/oi/test_oi_policy_triage.py"
  ],
  "evidence": "failed on teardown with \"ModuleNotFoundError: No module named 'msvcrt'\""
 },
 {
  "id": "GATE-python-120",
  "severity": "HIGH",
  "blocking": true,
  "category": "test",
  "title": "gate python: new failure tests.oi.test_oi_policy_triage::test_policy_rules",
  "files": [
   "tests/oi/test_oi_policy_triage.py"
  ],
  "evidence": "failed on teardown with \"ModuleNotFoundError: No module named 'msvcrt'\""
 },
 {
  "id": "GATE-python-121",
  "severity": "HIGH",
  "blocking": true,
  "category": "test",
  "title": "gate python: new failure tests.oi.test_oi_policy_triage::test_tier_params_are_server_side_and_bounded",
  "files": [
   "tests/oi/test_oi_policy_triage.py"
  ],
  "evidence": "failed on teardown with \"ModuleNotFoundError: No module named 'msvcrt'\""
 },
 {
  "id": "GATE-python-122",
  "severity": "HIGH",
  "blocking": true,
  "category": "test",
  "title": "gate python: new failure tests.oi.test_oi_policy_triage::test_triage_labels[1. remember that the audit is on Monday\\n2. create a checklist file\\n3. email it to Ravi-MULTI_STEP]",
  "files": [
   "tests/oi/test_oi_policy_triage.py"
  ],
  "evidence": "failed on teardown with \"ModuleNotFoundError: No module named 'msvcrt'\""
 },
 {
  "id": "GATE-python-123",
  "severity": "HIGH",
  "blocking": true,
  "category": "test",
  "title": "gate python: new failure tests.oi.test_oi_policy_triage::test_triage_labels[Can you save this note to my documents?-ACTION]",
  "files": [
   "tests/oi/test_oi_policy_triage.py"
  ],
  "evidence": "failed on teardown with \"ModuleNotFoundError: No module named 'msvcrt'\""
 },
 {
  "id": "GATE-python-124",
  "severity": "HIGH",
  "blocking": true,
  "category": "test",
  "title": "gate python: new failure tests.oi.test_oi_policy_triage::test_triage_labels[Compare SSD and HDD for a school office and recommend one.-ANALYSIS]",
  "files": [
   "tests/oi/test_oi_policy_triage.py"
  ],
  "evidence": "failed on teardown with \"ModuleNotFoundError: No module named 'msvcrt'\""
 },
 {
  "id": "GATE-python-125",
  "severity": "HIGH",
  "blocking": true,
  "category": "test",
  "title": "gate python: new failure tests.oi.test_oi_policy_triage::test_triage_labels[Delete all the files on my desktop-ACTION]",
  "files": [
   "tests/oi/test_oi_policy_triage.py"
  ],
  "evidence": "failed on teardown with \"ModuleNotFoundError: No module named 'msvcrt'\""
 },
 {
  "id": "GATE-python-126",
  "severity": "HIGH",
  "blocking": true,
  "category": "test",
  "title": "gate python: new failure tests.oi.test_oi_policy_triage::test_triage_labels[Do a deep research literature review of all the papers on MoE routing-ESCALATE]",
  "files": [
   "tests/oi/test_oi_policy_triage.py"
  ],
  "evidence": "failed on teardown with \"ModuleNotFoundError: No module named 'msvcrt'\""
 },
 {
  "id": "GATE-python-127",
  "severity": "HIGH",
  "blocking": true,
  "category": "test",
  "title": "gate python: new failure tests.oi.test_oi_policy_triage::test_triage_labels[Draft a leave letter and save it to my desktop as leave.docx-ACTION]",
  "files": [
   "tests/oi/test_oi_policy_triage.py"
  ],
  "evidence": "failed on teardown with \"ModuleNotFoundError: No module named 'msvcrt'\""
 },
 {
  "id": "GATE-python-128",
  "severity": "HIGH",
  "blocking": true,
  "category": "test",
  "title": "gate python: new failure tests.oi.test_oi_policy_triage::test_triage_labels[Draft a short leave application for two days.-QUESTION]",
  "files": [
   "tests/oi/test_oi_policy_triage.py"
  ],
  "evidence": "failed on teardown with \"ModuleNotFoundError: No module named 'msvcrt'\""
 },
 {
  "id": "GATE-python-129",
  "severity": "HIGH",
  "blocking": true,
  "category": "test",
  "title": "gate python: new failure tests.oi.test_oi_policy_triage::test_triage_labels[Explain the difference between RAM and VRAM.-QUESTION]",
  "files": [
   "tests/oi/test_oi_policy_triage.py"
  ],
  "evidence": "failed on teardown with \"ModuleNotFoundError: No module named 'msvcrt'\""
 },
 {
  "id": "GATE-python-130",
  "severity": "HIGH",
  "blocking": true,
  "category": "test",
  "title": "gate python: new failure tests.oi.test_oi_policy_triage::test_triage_labels[Fix the failing unit tests in the repo-HARNESS]",
  "files": [
   "tests/oi/test_oi_policy_triage.py"
  ],
  "evidence": "failed on teardown with \"ModuleNotFoundError: No module named 'msvcrt'\""
 },
 {
  "id": "GATE-python-131",
  "severity": "HIGH",
  "blocking": true,
  "category": "test",
  "title": "gate python: new failure tests.oi.test_oi_policy_triage::test_triage_labels[How do I remember names better?-QUESTION]",
  "files": [
   "tests/oi/test_oi_policy_triage.py"
  ],
  "evidence": "failed on teardown with \"ModuleNotFoundError: No module named 'msvcrt'\""
 },
 {
  "id": "GATE-python-132",
  "severity": "HIGH",
  "blocking": true,
  "category": "test",
  "title": "gate python: new failure tests.oi.test_oi_policy_triage::test_triage_labels[Is it safe to delete temp files on Windows?-QUESTION]",
  "files": [
   "tests/oi/test_oi_policy_triage.py"
  ],
  "evidence": "failed on teardown with \"ModuleNotFoundError: No module named 'msvcrt'\""
 },
 {
  "id": "GATE-python-133",
  "severity": "HIGH",
  "blocking": true,
  "category": "test",
  "title": "gate python: new failure tests.oi.test_oi_policy_triage::test_triage_labels[Please remember that the VC meeting moved to Thursday.-ACTION]",
  "files": [
   "tests/oi/test_oi_policy_triage.py"
  ],
  "evidence": "failed on teardown with \"ModuleNotFoundError: No module named 'msvcrt'\""
 },
 {
  "id": "GATE-python-134",
  "severity": "HIGH",
  "blocking": true,
  "category": "test",
  "title": "gate python: new failure tests.oi.test_oi_policy_triage::test_triage_labels[Refactor the Flutter settings screens across 14 files and run the tests.-HARNESS]",
  "files": [
   "tests/oi/test_oi_policy_triage.py"
  ],
  "evidence": "failed on teardown with \"ModuleNotFoundError: No module named 'msvcrt'\""
 },
 {
  "id": "GATE-python-135",
  "severity": "HIGH",
  "blocking": true,
  "category": "test",
  "title": "gate python: new failure tests.oi.test_oi_policy_triage::test_triage_labels[Search my mail for the fee circular, then draft a reply and send it to the principal.-MULTI_STEP]",
  "files": [
   "tests/oi/test_oi_policy_triage.py"
  ],
  "evidence": "failed on teardown with \"ModuleNotFoundError: No module named 'msvcrt'\""
 },
 {
  "id": "GATE-python-136",
  "severity": "HIGH",
  "blocking": true,
  "category": "test",
  "title": "gate python: new failure tests.oi.test_oi_policy_triage::test_triage_labels[Send an email to Meena about the exam-ACTION]",
  "files": [
   "tests/oi/test_oi_policy_triage.py"
  ],
  "evidence": "failed on teardown with \"ModuleNotFoundError: No module named 'msvcrt'\""
 },
 {
  "id": "GATE-python-137",
  "severity": "HIGH",
  "blocking": true,
  "category": "test",
  "title": "gate python: new failure tests.oi.test_oi_policy_triage::test_triage_labels[Thanks URI!-TRIVIAL]",
  "files": [
   "tests/oi/test_oi_policy_triage.py"
  ],
  "evidence": "failed on teardown with \"ModuleNotFoundError: No module named 'msvcrt'\""
 },
 {
  "id": "GATE-python-138",
  "severity": "HIGH",
  "blocking": true,
  "category": "test",
  "title": "gate python: new failure tests.oi.test_oi_policy_triage::test_triage_labels[What are the pros and cons of moving our timetable to Google Sheets?-ANALYSIS]",
  "files": [
   "tests/oi/test_oi_policy_triage.py"
  ],
  "evidence": "failed on teardown with \"ModuleNotFoundError: No module named 'msvcrt'\""
 },
 {
  "id": "GATE-python-139",
  "severity": "HIGH",
  "blocking": true,
  "category": "test",
  "title": "gate python: new failure tests.oi.test_oi_policy_triage::test_triage_labels[What is an office order?-QUESTION]",
  "files": [
   "tests/oi/test_oi_policy_triage.py"
  ],
  "evidence": "failed on teardown with \"ModuleNotFoundError: No module named 'msvcrt'\""
 },
 {
  "id": "GATE-python-140",
  "severity": "HIGH",
  "blocking": true,
  "category": "test",
  "title": "gate python: new failure tests.oi.test_oi_policy_triage::test_triage_labels[Why does my laptop slow down after an hour? Diagnose likely causes.-ANALYSIS]",
  "files": [
   "tests/oi/test_oi_policy_triage.py"
  ],
  "evidence": "failed on teardown with \"ModuleNotFoundError: No module named 'msvcrt'\""
 },
 {
  "id": "GATE-python-141",
  "severity": "HIGH",
  "blocking": true,
  "category": "test",
  "title": "gate python: new failure tests.oi.test_oi_policy_triage::test_triage_labels[Write a haiku about rain.-QUESTION]",
  "files": [
   "tests/oi/test_oi_policy_triage.py"
  ],
  "evidence": "failed on teardown with \"ModuleNotFoundError: No module named 'msvcrt'\""
 },
 {
  "id": "GATE-python-142",
  "severity": "HIGH",
  "blocking": true,
  "category": "test",
  "title": "gate python: new failure tests.oi.test_oi_policy_triage::test_triage_labels[forget my old phone number-ACTION]",
  "files": [
   "tests/oi/test_oi_policy_triage.py"
  ],
  "evidence": "failed on teardown with \"ModuleNotFoundError: No module named 'msvcrt'\""
 },
 {
  "id": "GATE-python-143",
  "severity": "HIGH",
  "blocking": true,
  "category": "test",
  "title": "gate python: new failure tests.oi.test_oi_policy_triage::test_triage_labels[good morning-TRIVIAL]",
  "files": [
   "tests/oi/test_oi_policy_triage.py"
  ],
  "evidence": "failed on teardown with \"ModuleNotFoundError: No module named 'msvcrt'\""
 },
 {
  "id": "GATE-python-144",
  "severity": "HIGH",
  "blocking": true,
  "category": "test",
  "title": "gate python: new failure tests.oi.test_oi_policy_triage::test_triage_labels[hi-TRIVIAL]",
  "files": [
   "tests/oi/test_oi_policy_triage.py"
  ],
  "evidence": "failed on teardown with \"ModuleNotFoundError: No module named 'msvcrt'\""
 },
 {
  "id": "GATE-python-145",
  "severity": "HIGH",
  "blocking": true,
  "category": "test",
  "title": "gate python: new failure tests.oi.test_oi_policy_triage::test_triage_labels[how are you today?-TRIVIAL]",
  "files": [
   "tests/oi/test_oi_policy_triage.py"
  ],
  "evidence": "failed on teardown with \"ModuleNotFoundError: No module named 'msvcrt'\""
 },
 {
  "id": "GATE-python-146",
  "severity": "HIGH",
  "blocking": true,
  "category": "test",
  "title": "gate python: new failure tests.oi.test_oi_policy_triage::test_triage_labels[remember that my favourite colour is teal-ACTION]",
  "files": [
   "tests/oi/test_oi_policy_triage.py"
  ],
  "evidence": "failed on teardown with \"ModuleNotFoundError: No module named 'msvcrt'\""
 },
 {
  "id": "GATE-python-147",
  "severity": "HIGH",
  "blocking": true,
  "category": "test",
  "title": "gate python: new failure tests.oi.test_oi_runtime_v1::test_config_is_the_frozen_runtime_v1",
  "files": [
   "tests/oi/test_oi_runtime_v1.py"
  ],
  "evidence": "failed on teardown with \"ModuleNotFoundError: No module named 'msvcrt'\""
 },
 {
  "id": "GATE-python-148",
  "severity": "HIGH",
  "blocking": true,
  "category": "test",
  "title": "gate python: new failure tests.oi.test_oi_runtime_v1::test_expected_argv_is_exactly_the_frozen_flag_set",
  "files": [
   "tests/oi/test_oi_runtime_v1.py"
  ],
  "evidence": "failed on teardown with \"ModuleNotFoundError: No module named 'msvcrt'\""
 },
 {
  "id": "GATE-python-149",
  "severity": "HIGH",
  "blocking": true,
  "category": "test",
  "title": "gate python: new failure tests.oi.test_oi_runtime_v1::test_foreign_instance_on_port_is_never_adopted_or_started_over",
  "files": [
   "tests/oi/test_oi_runtime_v1.py"
  ],
  "evidence": "failed on teardown with \"ModuleNotFoundError: No module named 'msvcrt'\""
 },
 {
  "id": "GATE-python-150",
  "severity": "HIGH",
  "blocking": true,
  "category": "test",
  "title": "gate python: new failure tests.oi.test_oi_runtime_v1::test_live_identity_problems",
  "files": [
   "tests/oi/test_oi_runtime_v1.py"
  ],
  "evidence": "failed on teardown with \"ModuleNotFoundError: No module named 'msvcrt'\""
 },
 {
  "id": "GATE-python-151",
  "severity": "HIGH",
  "blocking": true,
  "category": "test",
  "title": "gate python: new failure tests.oi.test_oi_runtime_v1::test_missing_artifacts_refuse_start",
  "files": [
   "tests/oi/test_oi_runtime_v1.py"
  ],
  "evidence": "failed on teardown with \"ModuleNotFoundError: No module named 'msvcrt'\""
 },
 {
  "id": "GATE-python-152",
  "severity": "HIGH",
  "blocking": true,
  "category": "test",
  "title": "gate python: new failure tests.oi.test_oi_runtime_v1::test_pinned_artifacts_cover_binary_dll_model_projector_and_mtp",
  "files": [
   "tests/oi/test_oi_runtime_v1.py"
  ],
  "evidence": "failed on teardown with \"ModuleNotFoundError: No module named 'msvcrt'\""
 },
 {
  "id": "GATE-python-153",
  "severity": "HIGH",
  "blocking": true,
  "category": "test",
  "title": "gate python: new failure tests.oi.test_oi_runtime_v1::test_start_lock_excludes_a_second_starter",
  "files": [
   "tests/oi/test_oi_runtime_v1.py"
  ],
  "evidence": "failed on teardown with \"ModuleNotFoundError: No module named 'msvcrt'\""
 },
 {
  "id": "GATE-python-154",
  "severity": "HIGH",
  "blocking": true,
  "category": "test",
  "title": "gate python: new failure tests.oi.test_oi_runtime_v1::test_status_stopped_when_nothing_listens",
  "files": [
   "tests/oi/test_oi_runtime_v1.py"
  ],
  "evidence": "failed on teardown with \"ModuleNotFoundError: No module named 'msvcrt'\""
 },
 {
  "id": "GATE-python-155",
  "severity": "HIGH",
  "blocking": true,
  "category": "test",
  "title": "gate python: new failure tests.oi.test_oi_runtime_v1::test_stop_never_touches_an_instance_it_did_not_start",
  "files": [
   "tests/oi/test_oi_runtime_v1.py"
  ],
  "evidence": "failed on teardown with \"ModuleNotFoundError: No module named 'msvcrt'\""
 },
 {
  "id": "GATE-python-156",
  "severity": "HIGH",
  "blocking": true,
  "category": "test",
  "title": "gate python: new failure tests.oi.test_oi_runtime_v1::test_verify_artifacts_match_cached_mismatch_missing",
  "files": [
   "tests/oi/test_oi_runtime_v1.py"
  ],
  "evidence": "failed on teardown with \"ModuleNotFoundError: No module named 'msvcrt'\""
 },
 {
  "id": "GATE-python-157",
  "severity": "HIGH",
  "blocking": true,
  "category": "test",
  "title": "gate python: new failure tests.oi.test_oi_server::test_auth_required_everywhere",
  "files": [
   "tests/oi/test_oi_server.py"
  ],
  "evidence": "failed on teardown with \"ModuleNotFoundError: No module named 'msvcrt'\""
 },
 {
  "id": "GATE-python-158",
  "severity": "HIGH",
  "blocking": true,
  "category": "test",
  "title": "gate python: new failure tests.oi.test_oi_server::test_bad_depth_and_simulator",
  "files": [
   "tests/oi/test_oi_server.py"
  ],
  "evidence": "failed on teardown with \"ModuleNotFoundError: No module named 'msvcrt'\""
 },
 {
  "id": "GATE-python-159",
  "severity": "HIGH",
  "blocking": true,
  "category": "test",
  "title": "gate python: new failure tests.oi.test_oi_server::test_cancel_over_http",
  "files": [
   "tests/oi/test_oi_server.py"
  ],
  "evidence": "failed on teardown with \"ModuleNotFoundError: No module named 'msvcrt'\""
 },
 {
  "id": "GATE-python-160",
  "severity": "HIGH",
  "blocking": true,
  "category": "test",
  "title": "gate python: new failure tests.oi.test_oi_server::test_internal_error_still_finishes_the_stream",
  "files": [
   "tests/oi/test_oi_server.py"
  ],
  "evidence": "failed on teardown with \"ModuleNotFoundError: No module named 'msvcrt'\""
 },
 {
  "id": "GATE-python-161",
  "severity": "HIGH",
  "blocking": true,
  "category": "test",
  "title": "gate python: new failure tests.oi.test_oi_server::test_turn_streams_contract_events",
  "files": [
   "tests/oi/test_oi_server.py"
  ],
  "evidence": "failed on teardown with \"ModuleNotFoundError: No module named 'msvcrt'\""
 },
 {
  "id": "GATE-python-162",
  "severity": "HIGH",
  "blocking": true,
  "category": "test",
  "title": "gate python: new failure tests.ws.test_ws_hardening::test_a_load_stopped_before_its_spawn_is_reaped_before_the_lease_goes",
  "files": [
   "tests/ws/test_ws_hardening.py"
  ],
  "evidence": "ModuleNotFoundError"
 },
 {
  "id": "GATE-python-163",
  "severity": "HIGH",
  "blocking": true,
  "category": "test",
  "title": "gate python: new failure tests.ws.test_ws_hardening::test_a_long_living_loader_keeps_the_lease_and_exit_leaves_release_to_the_os",
  "files": [
   "tests/ws/test_ws_hardening.py"
  ],
  "evidence": "ModuleNotFoundError"
 },
 {
  "id": "GATE-python-164",
  "severity": "HIGH",
  "blocking": true,
  "category": "test",
  "title": "gate python: new failure tests.ws.test_ws_hardening::test_advise_cli_exit_codes",
  "files": [
   "tests/ws/test_ws_hardening.py"
  ],
  "evidence": "ValueError"
 },
 {
  "id": "GATE-python-165",
  "severity": "HIGH",
  "blocking": true,
  "category": "test",
  "title": "gate python: new failure tests.ws.test_ws_hardening::test_advise_does_not_wait_for_the_callers_own_lease",
  "files": [
   "tests/ws/test_ws_hardening.py"
  ],
  "evidence": "ValueError"
 },
 {
  "id": "GATE-python-166",
  "severity": "HIGH",
  "blocking": true,
  "category": "test",
  "title": "gate python: new failure tests.ws.test_ws_hardening::test_advise_fails_closed_when_unmeasurable",
  "files": [
   "tests/ws/test_ws_hardening.py"
  ],
  "evidence": "ModuleNotFoundError"
 },
 {
  "id": "GATE-python-167",
  "severity": "HIGH",
  "blocking": true,
  "category": "test",
  "title": "gate python: new failure tests.ws.test_ws_hardening::test_advise_never_takes_the_lock_or_writes_lease_files",
  "files": [
   "tests/ws/test_ws_hardening.py"
  ],
  "evidence": "ModuleNotFoundError"
 },
 {
  "id": "GATE-python-168",
  "severity": "HIGH",
  "blocking": true,
  "category": "test",
  "title": "gate python: new failure tests.ws.test_ws_hardening::test_advise_waits_for_a_heavy_holder_and_ignores_the_users_brain_host",
  "files": [
   "tests/ws/test_ws_hardening.py"
  ],
  "evidence": "ValueError"
 },
 {
  "id": "GATE-python-169",
  "severity": "HIGH",
  "blocking": true,
  "category": "test",
  "title": "gate python: new failure tests.ws.test_ws_hardening::test_capture_tool_runs_the_advisory_from_the_repository_root",
  "files": [
   "tests/ws/test_ws_hardening.py"
  ],
  "evidence": "FileNotFoundError"
 },
 {
  "id": "GATE-python-170",
  "severity": "HIGH",
  "blocking": true,
  "category": "test",
  "title": "gate python: new failure tests.ws.test_ws_hardening::test_cli_run_refuses_while_held_and_runs_when_free",
  "files": [
   "tests/ws/test_ws_hardening.py"
  ],
  "evidence": "assert (1 == 0)"
 },
 {
  "id": "GATE-python-171",
  "severity": "HIGH",
  "blocking": true,
  "category": "test",
  "title": "gate python: new failure tests.ws.test_ws_hardening::test_cli_workload_dies_with_its_lease_holder",
  "files": [
   "tests/ws/test_ws_hardening.py"
  ],
  "evidence": "FileNotFoundError"
 },
 {
  "id": "GATE-python-172",
  "severity": "HIGH",
  "blocking": true,
  "category": "test",
  "title": "gate python: new failure tests.ws.test_ws_hardening::test_dead_holder_is_recovered_without_touching_anyone",
  "files": [
   "tests/ws/test_ws_hardening.py"
  ],
  "evidence": "ValueError"
 },
 {
  "id": "GATE-python-173",
  "severity": "HIGH",
  "blocking": true,
  "category": "test",
  "title": "gate python: new failure tests.ws.test_ws_hardening::test_host_waits_for_another_uri_lease_holder",
  "files": [
   "tests/ws/test_ws_hardening.py"
  ],
  "evidence": "ValueError"
 },
 {
  "id": "GATE-python-174",
  "severity": "HIGH",
  "blocking": true,
  "category": "test",
  "title": "gate python: new failure tests.ws.test_ws_hardening::test_lease_acquire_release_and_history",
  "files": [
   "tests/ws/test_ws_hardening.py"
  ],
  "evidence": "ModuleNotFoundError"
 },
 {
  "id": "GATE-python-175",
  "severity": "HIGH",
  "blocking": true,
  "category": "test",
  "title": "gate python: new failure tests.ws.test_ws_hardening::test_overdue_holder_is_reported_not_broken",
  "files": [
   "tests/ws/test_ws_hardening.py"
  ],
  "evidence": "ValueError"
 },
 {
  "id": "GATE-python-176",
  "severity": "HIGH",
  "blocking": true,
  "category": "test",
  "title": "gate python: new failure tests.ws.test_ws_hardening::test_override_is_recorded",
  "files": [
   "tests/ws/test_ws_hardening.py"
  ],
  "evidence": "ModuleNotFoundError"
 },
 {
  "id": "GATE-python-177",
  "severity": "HIGH",
  "blocking": true,
  "category": "test",
  "title": "gate python: new failure tests.ws.test_ws_hardening::test_second_workload_refused_with_holder_and_wait_times_out",
  "files": [
   "tests/ws/test_ws_hardening.py"
  ],
  "evidence": "ValueError"
 },
 {
  "id": "GATE-python-178",
  "severity": "HIGH",
  "blocking": true,
  "category": "test",
  "title": "gate python: new failure tests.ws.test_ws_hardening::test_wait_ui_window_behaviour_on_real_processes",
  "files": [
   "tests/ws/test_ws_hardening.py"
  ],
  "evidence": "FileNotFoundError"
 }
]

End your final message with:
REPAIR_RESULT_BEGIN
{"repaired": ["<finding id>"], "not_repaired": [{"id": "...", "reason": "..."}],
 "regression_tests": ["path/to/test_file.py"], "notes": "..."}
REPAIR_RESULT_END
