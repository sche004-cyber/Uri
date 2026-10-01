# Batch broad-suite regression check (M36 405db1f → M37 → M38)

- **Run by:** Claude Code (implementer), 2026-09-28, Linux container, Python 3.11.15. Self-run, not independent.
- **HEAD run:** `python -m pytest test_*.py -q` at the M38 working tree → 2,639 passed, 66 skipped, **15 failed**.
- **Baseline run:** the same 15 node IDs, run in a clean `git worktree` at `405db1ff21f11f6927fe1b74990ff6b88a97a28d` (M36 repair, before any M37/M38 file) → **15 failed** (all 15; 291 s).
- **Conclusion:** every broad-suite failure at HEAD also fails at `405db1f`. No broad-suite regression is attributable to M37 or M38 in this environment. Causes were not root-caused here; the M36 report recorded 11 failures on the User's Windows machine, so part of the set is environment-specific (packages, network, Tesseract, Linux).
- **Caveat:** only the 15 failing IDs were re-run at the baseline, not the whole suite; a test passing at HEAD and failing at baseline would not be detected (that direction is not a regression).

## Failing node IDs (identical at HEAD and at 405db1f)

```
test_capability_directory.py::PrivacyTests::test_no_credentials_tokens_or_secrets_appear_in_serialized_output
test_m20_feasibility_validation.py::UnavailableCapabilityIsNotPromotedTests::test_strict_single_action_proposal_for_unavailable_capability_falls_back
test_m20_recovery_loop.py::CapabilityPlannerFailureReachesRecoveryTests::test_capability_planner_failure_reaches_recovery_loop
test_m20_recovery_loop.py::LearnedSkillFailureReachesRecoveryTests::test_learned_skill_failure_reaches_recovery_loop
test_m20_semantic_interpreter_resilience.py::SemanticInterpreterFailureDegradesHonestlyTests::test_capability_planner_gets_the_degraded_result_without_raising
test_m20_semantic_interpreter_resilience.py::SemanticInterpreterFailureDegradesHonestlyTests::test_raising_interpreter_does_not_fail_the_whole_turn
test_m33_1_batch2_yt_dlp.py::TestM33_1Batch2YtDlp::test_execution_through_generic_cli_bridge_and_canonical_loop
test_m33_1_batch2_yt_dlp.py::TestM33_1Batch2YtDlp::test_live_lifecycle_refresh_without_restart
test_m33_1_batch3_github_package.py::Batch3LifecycleAcceptanceTests::test_corrupt_user_state_fails_closed_and_does_not_leak_to_another_user
test_m33_1_batch3_github_package.py::Batch3LifecycleAcceptanceTests::test_real_install_execute_live_retirement_update_remove_and_isolation
test_m33_1_batch4_lifecycle_intent.py::LifecycleIntentTests::test_strip_json_comments_install_update_remove_and_rejected_install_leave_no_trace
test_m33_1_batch4_live_ask_lifecycle.py::LiveAskLifecycleIntentTests::test_remove_known_skill_end_to_end
test_orchestrator_session_workflow.py::TestOrchestratorSessionWorkflow::test_session_facts_are_used_for_clarification
test_usage_import_boundary.py::test_orchestrator_newline_count_does_not_increase
test_workflow_restart_recovery.py::TestWorkflowRestartRecovery::test_workflow_survives_restart_and_resumes
```
