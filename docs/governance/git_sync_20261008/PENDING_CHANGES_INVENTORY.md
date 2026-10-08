# Pending Changes Inventory — 2026-10-08

Every uncommitted file in every worktree of the URI repository, as of 2026-10-08 ~08:50 IST, with its disposition in the git sync candidates. Full per-file data (status, git blob, bytes, class, disposition): `PENDING_CHANGES_INVENTORY.json`. Method and verification: `GIT_SYNC_AUDIT.md` sections 1 and 8.

Classes: `ON_GH_SAME_PATH` = identical content already at that path on GitHub; `ON_LOCAL_SAME_PATH` = identical only in a local unpushed commit; `ON_GH_OTHER_PATH` = identical bytes exist on GitHub under another path (usually empty files); `VARIANT` = path exists in some commit with different content; `NEW_PATH` = path in no commit. No file of class VARIANT or NEW_PATH matched any blob in the 348 reachable commits.

Disposition codes: `A1`–`A9` = commits on `integration/git-sync-20261008`; `B1`–`B6` = `preserve/*` branches; `ALREADY_ON_GITHUB`; `EXCLUDED_*` with reason.

## Summary by worktree

| Worktree | Dirty | Class counts | Disposition counts |
|---|---|---|---|
| `~/Development/uri-agent` | 93 | NEW_PATH 26, ON_GH_SAME_PATH 61, ON_LOCAL_SAME_PATH 6 | A2_phase0 26, ALREADY_ON_GITHUB 61, EXCLUDED_DEV_ARTIFACT 6 |
| `~/.codex/worktrees/batch-audit-canonical/_V1` | 0 |  |  |
| `~/.codex/worktrees/harness-connections-console/_V1` | 96 | NEW_PATH 82, VARIANT 14 | B3_hc 66, EXCLUDED_RUNTIME_STATE_SENSITIVE 30 |
| `~/.codex/worktrees/intent-discovery/_V1` | 47 | NEW_PATH 34, VARIANT 13 | B4_id 47 |
| `~/.codex/worktrees/m33-audit-baseline/_V1` | 3 | ON_GH_SAME_PATH 3 | ALREADY_ON_GITHUB 3 |
| `~/.codex/worktrees/m33-audit-candidate/_V1` | 20 | ON_GH_SAME_PATH 15, VARIANT 5 | B5_m333r 20 |
| `~/.codex/worktrees/uri-phase1-integration/uri-agent` | 658 | NEW_PATH 638, ON_GH_OTHER_PATH 9, VARIANT 11 | A1_phase1 121, A3_runtime_v1 537 |
| `~/.codex/worktrees/uri-phase2a/uri-agent` | 256 | NEW_PATH 231, ON_GH_OTHER_PATH 13, VARIANT 12 | A1_phase1 121, A4_phase2_r6 117, A7_phase2close_f 15, A9_phase2close_post_acceptance_docs 3 |
| `~/Development/Uri/_V1` | 475 | NEW_PATH 434, ON_GH_OTHER_PATH 2, ON_GH_SAME_PATH 3, ON_LOCAL_SAME_PATH 4, VARIANT 32 | B2_v1 437, EXCLUDED_DEV_ARTIFACT 6, EXCLUDED_RUNTIME_STATE_SENSITIVE 32 |
| `~/Development/uri-agent/.tmp_m33_1_batch4_baseline_5973f6d` | 19 | DELETED_OR_DIR 1, NEW_PATH 18 | EXCLUDED_DELETION_IN_THROWAWAY_BASELINE 1, EXCLUDED_PYTEST_TEMP 18 |
| `~/Development/uri-batch-candidate` | 2 | VARIANT 2 | B6_batchcand 2 |
| `~/Development/uri-dictation` | 0 |  |  |
| `~/Development/uri-m37-m39-integration` | 59 | NEW_PATH 37, VARIANT 22 | B1_desktop_int 57, EXCLUDED_RUNTIME_PID 2 |
| `~/Development/Uri_edge_experiments` | 0 |  |  |
| **Total** | **1728** | | |

## Content by worktree and top-level area

### `~/Development/uri-agent`

| Area | Files by disposition |
|---|---|
| `(root)` | ALREADY_ON_GITHUB 7 |
| `.tmp_m26_render` | ALREADY_ON_GITHUB 1 |
| `2026-10-05/uri-phase-0-runtime-inventory-and` | A2_phase0 26 |
| `docs/governance` | ALREADY_ON_GITHUB 2 |
| `docs/plans` | ALREADY_ON_GITHUB 2 |
| `graphify-out` | EXCLUDED_DEV_ARTIFACT 2 |
| `graphify-out/converted` | EXCLUDED_DEV_ARTIFACT 3 |
| `graphify-out/reflections` | EXCLUDED_DEV_ARTIFACT 1 |
| `scripts` | ALREADY_ON_GITHUB 3 |
| `uri_core/app` | ALREADY_ON_GITHUB 2 |
| `uri_core/core` | ALREADY_ON_GITHUB 5 |
| `uri_core/services` | ALREADY_ON_GITHUB 1 |
| `uri_core/tools` | ALREADY_ON_GITHUB 1 |
| `uri_ui/lib` | ALREADY_ON_GITHUB 27 |
| `uri_ui/test` | ALREADY_ON_GITHUB 7 |
| `uri_ui/windows` | ALREADY_ON_GITHUB 2 |
| `uri_workspace` | ALREADY_ON_GITHUB 1 |

### `~/.codex/worktrees/harness-connections-console/_V1`

| Area | Files by disposition |
|---|---|
| `(root)` | B3_hc 3 |
| `docs/architecture` | B3_hc 1 |
| `docs/design_library` | B3_hc 1 |
| `docs/plans` | B3_hc 20 |
| `docs/research` | B3_hc 1 |
| `scratch/candidate_desktop_state` | EXCLUDED_RUNTIME_STATE_SENSITIVE 30 |
| `scratch/codex_containment_probe` | B3_hc 3 |
| `scripts` | B3_hc 4 |
| `tests` | B3_hc 3 |
| `uri_ui` | B3_hc 2 |
| `uri_ui/lib` | B3_hc 12 |
| `uri_ui/test` | B3_hc 6 |
| `uri_ui/test_driver` | B3_hc 4 |
| `uri_v1/app` | B3_hc 1 |
| `uri_v1/desktop_harness` | B3_hc 5 |

### `~/.codex/worktrees/intent-discovery/_V1`

| Area | Files by disposition |
|---|---|
| `docs/architecture` | B4_id 1 |
| `docs/evidence` | B4_id 2 |
| `docs/plans` | B4_id 2 |
| `docs/research` | B4_id 1 |
| `experimental/intent_workflow` | B4_id 5 |
| `scripts` | B4_id 2 |
| `tests` | B4_id 4 |
| `uri_core/core` | B4_id 2 |
| `uri_ui` | B4_id 3 |
| `uri_ui/lib` | B4_id 13 |
| `uri_ui/test` | B4_id 7 |
| `uri_v1/desktop_harness` | B4_id 5 |

### `~/.codex/worktrees/m33-audit-baseline/_V1`

| Area | Files by disposition |
|---|---|
| `uri_ui/windows` | ALREADY_ON_GITHUB 3 |

### `~/.codex/worktrees/m33-audit-candidate/_V1`

| Area | Files by disposition |
|---|---|
| `docs/governance` | B5_m333r 2 |
| `docs/plans` | B5_m333r 2 |
| `fixtures/m33_3_s5` | B5_m333r 1 |
| `scripts` | B5_m333r 2 |
| `tests` | B5_m333r 1 |
| `uri_core/core` | B5_m333r 1 |
| `uri_ui/lib` | B5_m333r 1 |
| `uri_ui/test` | B5_m333r 1 |
| `uri_ui/windows` | B5_m333r 3 |
| `uri_v1/evaluation` | B5_m333r 3 |
| `uri_v1/reference_clarification` | B5_m333r 1 |
| `uri_v1/results` | B5_m333r 1 |
| `uri_v1/wording` | B5_m333r 1 |

### `~/.codex/worktrees/uri-phase1-integration/uri-agent`

| Area | Files by disposition |
|---|---|
| `(root)` | A1_phase1 25 |
| `docs/architecture` | A1_phase1 2 |
| `docs/governance` | A1_phase1 1 |
| `docs/plans` | A1_phase1 15 |
| `fixtures/c4_harness` | A1_phase1 1 |
| `model_lab` | A3_runtime_v1 14 |
| `model_lab/evidence` | A3_runtime_v1 471 |
| `model_lab/integration` | A3_runtime_v1 3 |
| `model_lab/lab` | A3_runtime_v1 9 |
| `model_lab/uri_engine` | A3_runtime_v1 40 |
| `scripts` | A1_phase1 16 |
| `tests/reference_binding` | A1_phase1 10 |
| `uri_core` | A1_phase1 2 |
| `uri_core/app` | A1_phase1 5 |
| `uri_core/capabilities` | A1_phase1 1 |
| `uri_core/client_runtime` | A1_phase1 11 |
| `uri_core/core` | A1_phase1 11 |
| `uri_core/reference_binding` | A1_phase1 14 |
| `uri_harness_adapters` | A1_phase1 1 |
| `uri_ui/lib` | A1_phase1 3 |
| `uri_ui/test` | A1_phase1 2 |
| `uri_workspace` | A1_phase1 1 |

### `~/.codex/worktrees/uri-phase2a/uri-agent`

| Area | Files by disposition |
|---|---|
| `(root)` | A1_phase1 25 |
| `docs/architecture` | A1_phase1 2, A4_phase2_r6 5, A7_phase2close_f 1 |
| `docs/governance` | A1_phase1 1 |
| `docs/plans` | A1_phase1 15, A4_phase2_r6 14, A7_phase2close_f 3, A9_phase2close_post_acceptance_docs 3 |
| `fixtures/c4_harness` | A1_phase1 1 |
| `scripts` | A1_phase1 16, A4_phase2_r6 12, A7_phase2close_f 4 |
| `tests/phase2a` | A4_phase2_r6 24 |
| `tests/phase2b` | A4_phase2_r6 11 |
| `tests/phase2c` | A4_phase2_r6 5 |
| `tests/phase2close` | A7_phase2close_f 4 |
| `tests/phase2d` | A4_phase2_r6 11 |
| `tests/phase2ops` | A4_phase2_r6 7, A7_phase2close_f 2 |
| `tests/reference_binding` | A1_phase1 10 |
| `uri_core` | A1_phase1 2 |
| `uri_core/app` | A1_phase1 5 |
| `uri_core/capabilities` | A1_phase1 1 |
| `uri_core/client_runtime` | A1_phase1 11 |
| `uri_core/core` | A1_phase1 11 |
| `uri_core/reference_binding` | A1_phase1 14 |
| `uri_harness_adapters` | A1_phase1 1 |
| `uri_supervisor` | A4_phase2_r6 14 |
| `uri_supervisor_bridge` | A4_phase2_r6 9 |
| `uri_ui/lib` | A1_phase1 3, A4_phase2_r6 3, A7_phase2close_f 1 |
| `uri_ui/test` | A1_phase1 2, A4_phase2_r6 2 |
| `uri_workspace` | A1_phase1 1 |

### `~/Development/Uri/_V1`

| Area | Files by disposition |
|---|---|
| `(root)` | B2_v1 24 |
| `.agents/skills` | B2_v1 1 |
| `docs/architecture` | B2_v1 3 |
| `docs/design_library` | B2_v1 4 |
| `docs/governance` | B2_v1 3 |
| `docs/plans` | B2_v1 83 |
| `docs/research` | B2_v1 23 |
| `experimental/dynamic_planning_benchmark` | B2_v1 13 |
| `experimental/edge_model_tests` | B2_v1 61 |
| `experimental/real_tool_pilot` | B2_v1 5 |
| `fixtures/dynamic_planning` | B2_v1 3 |
| `graphify-out` | EXCLUDED_DEV_ARTIFACT 2 |
| `graphify-out/converted` | EXCLUDED_DEV_ARTIFACT 3 |
| `graphify-out/reflections` | EXCLUDED_DEV_ARTIFACT 1 |
| `scratch` | B2_v1 40 |
| `scratch/backup_untracked` | B2_v1 10 |
| `scratch/desktop_harness_test_state` | EXCLUDED_RUNTIME_STATE_SENSITIVE 32 |
| `scratch/voice_validation` | B2_v1 3 |
| `scripts` | B2_v1 67 |
| `tests` | B2_v1 17 |
| `uri_ui` | B2_v1 2 |
| `uri_ui/lib` | B2_v1 10 |
| `uri_ui/test` | B2_v1 7 |
| `uri_ui/test_driver` | B2_v1 3 |
| `uri_ui/windows` | B2_v1 3 |
| `uri_v1/app` | B2_v1 1 |
| `uri_v1/arn` | B2_v1 13 |
| `uri_v1/context` | B2_v1 1 |
| `uri_v1/desktop_harness` | B2_v1 5 |
| `uri_v1/execution` | B2_v1 9 |
| `uri_v1/intelligence` | B2_v1 7 |
| `uri_v1/recovery` | B2_v1 1 |
| `uri_v1/safety` | B2_v1 1 |
| `uri_v1/turn` | B2_v1 14 |

### `~/Development/uri-agent/.tmp_m33_1_batch4_baseline_5973f6d`

| Area | Files by disposition |
|---|---|
| `(root)` | EXCLUDED_DELETION_IN_THROWAWAY_BASELINE 1 |
| `.tmp_m33_c2_pytest/c3_adapter` | EXCLUDED_PYTEST_TEMP 1 |
| `.tmp_m33_c2_pytest/c3_brain_feedback` | EXCLUDED_PYTEST_TEMP 2 |
| `.tmp_m33_c2_pytest/c3_completion` | EXCLUDED_PYTEST_TEMP 2 |
| `.tmp_m33_c2_pytest/c3_orchestrator` | EXCLUDED_PYTEST_TEMP 1 |
| `.tmp_m33_c2_pytest/composition` | EXCLUDED_PYTEST_TEMP 4 |
| `.tmp_m33_c2_pytest/evidence_atomic` | EXCLUDED_PYTEST_TEMP 1 |
| `.tmp_m33_c2_pytest/evidence_corrupt` | EXCLUDED_PYTEST_TEMP 1 |
| `.tmp_m33_c2_pytest/evidence_redaction` | EXCLUDED_PYTEST_TEMP 1 |
| `.tmp_m33_c2_pytest/evidence_restart` | EXCLUDED_PYTEST_TEMP 1 |
| `.tmp_m33_c2_pytest/operation_corrupt` | EXCLUDED_PYTEST_TEMP 1 |
| `.tmp_m33_c2_pytest/operation_isolation` | EXCLUDED_PYTEST_TEMP 1 |
| `.tmp_m33_c2_pytest/operation_pending` | EXCLUDED_PYTEST_TEMP 1 |
| `.tmp_m33_c2_pytest/operation_restart` | EXCLUDED_PYTEST_TEMP 1 |

### `~/Development/uri-batch-candidate`

| Area | Files by disposition |
|---|---|
| `docs/plans` | B6_batchcand 2 |

### `~/Development/uri-m37-m39-integration`

| Area | Files by disposition |
|---|---|
| `(root)` | B1_desktop_int 6 |
| `docs/architecture` | B1_desktop_int 2 |
| `docs/plans` | B1_desktop_int 12 |
| `docs/research` | B1_desktop_int 3 |
| `scratch/document_layout_qualification` | B1_desktop_int 9 |
| `scratch/presentation_repair_baseline` | B1_desktop_int 2 |
| `scripts` | B1_desktop_int 1 |
| `uri_core/app` | B1_desktop_int 1 |
| `uri_core/core` | B1_desktop_int 9 |
| `uri_core/services` | B1_desktop_int 2 |
| `uri_core/tools` | B1_desktop_int 3 |
| `uri_desktop_seams/reference_clarification` | B1_desktop_int 1 |
| `uri_ui/lib` | B1_desktop_int 3 |
| `uri_ui/test` | B1_desktop_int 2 |
| `uri_workspace` | B1_desktop_int 1, EXCLUDED_RUNTIME_PID 2 |

## Files held or excluded (explicit list)

| Worktree | File | Disposition |
|---|---|---|
| `Development/uri-agent` | `graphify-out/.graphify_learning.json` | EXCLUDED_DEV_ARTIFACT (in local 869fae5) |
| `Development/uri-agent` | `graphify-out/.vocab.txt` | EXCLUDED_DEV_ARTIFACT (in local 869fae5) |
| `Development/uri-agent` | `graphify-out/converted/Detailed_Noting_Draft_320b2725.md` | EXCLUDED_DEV_ARTIFACT (in local 869fae5) |
| `Development/uri-agent` | `graphify-out/converted/Extension_Noting_Draft_e9795f18.md` | EXCLUDED_DEV_ARTIFACT (in local 869fae5) |
| `Development/uri-agent` | `graphify-out/converted/Heavy_Noting_Draft_4bbb881d.md` | EXCLUDED_DEV_ARTIFACT (in local 869fae5) |
| `Development/uri-agent` | `graphify-out/reflections/LESSONS.md` | EXCLUDED_DEV_ARTIFACT (in local 869fae5) |
| `harness-connections-console/_V1` | `scratch/candidate_desktop_state/analysis.log` | EXCLUDED_RUNTIME_STATE_SENSITIVE |
| `harness-connections-console/_V1` | `scratch/candidate_desktop_state/app.stderr.log` | EXCLUDED_RUNTIME_STATE_SENSITIVE |
| `harness-connections-console/_V1` | `scratch/candidate_desktop_state/app.stdout.log` | EXCLUDED_RUNTIME_STATE_SENSITIVE |
| `harness-connections-console/_V1` | `scratch/candidate_desktop_state/core.stderr.log` | EXCLUDED_RUNTIME_STATE_SENSITIVE |
| `harness-connections-console/_V1` | `scratch/candidate_desktop_state/core.stdout.log` | EXCLUDED_RUNTIME_STATE_SENSITIVE |
| `harness-connections-console/_V1` | `scratch/candidate_desktop_state/desktop.stderr.log` | EXCLUDED_RUNTIME_STATE_SENSITIVE |
| `harness-connections-console/_V1` | `scratch/candidate_desktop_state/desktop.stdout.log` | EXCLUDED_RUNTIME_STATE_SENSITIVE |
| `harness-connections-console/_V1` | `scratch/candidate_desktop_state/flutter_tests.log` | EXCLUDED_RUNTIME_STATE_SENSITIVE |
| `harness-connections-console/_V1` | `scratch/candidate_desktop_state/launcher.stderr.log` | EXCLUDED_RUNTIME_STATE_SENSITIVE |
| `harness-connections-console/_V1` | `scratch/candidate_desktop_state/launcher.stdout.log` | EXCLUDED_RUNTIME_STATE_SENSITIVE |
| `harness-connections-console/_V1` | `scratch/candidate_desktop_state/navigation_tests.log` | EXCLUDED_RUNTIME_STATE_SENSITIVE |
| `harness-connections-console/_V1` | `scratch/candidate_desktop_state/python_tests.log` | EXCLUDED_RUNTIME_STATE_SENSITIVE |
| `harness-connections-console/_V1` | `scratch/candidate_desktop_state/uri_workspace/auth_sessions.json` | EXCLUDED_RUNTIME_STATE_SENSITIVE |
| `harness-connections-console/_V1` | `scratch/candidate_desktop_state/uri_workspace/device_identity.json` | EXCLUDED_RUNTIME_STATE_SENSITIVE |
| `harness-connections-console/_V1` | `scratch/candidate_desktop_state/uri_workspace/friction_log.json` | EXCLUDED_RUNTIME_STATE_SENSITIVE |
| `harness-connections-console/_V1` | `scratch/candidate_desktop_state/uri_workspace/graph.sqlite3` | EXCLUDED_RUNTIME_STATE_SENSITIVE |
| `harness-connections-console/_V1` | `scratch/candidate_desktop_state/uri_workspace/graphify_index.json` | EXCLUDED_RUNTIME_STATE_SENSITIVE |
| `harness-connections-console/_V1` | `scratch/candidate_desktop_state/uri_workspace/portable_identity.json` | EXCLUDED_RUNTIME_STATE_SENSITIVE |
| `harness-connections-console/_V1` | `scratch/candidate_desktop_state/uri_workspace/skill_memory.json` | EXCLUDED_RUNTIME_STATE_SENSITIVE |
| `harness-connections-console/_V1` | `scratch/candidate_desktop_state/uri_workspace/user_accounts.json` | EXCLUDED_RUNTIME_STATE_SENSITIVE |
| `harness-connections-console/_V1` | `scratch/candidate_desktop_state/uri_workspace/users/4fdfc8d2-005d-407c-b9f5-82ca67cff24b/graph.sqlite3` | EXCLUDED_RUNTIME_STATE_SENSITIVE |
| `harness-connections-console/_V1` | `scratch/candidate_desktop_state/uri_workspace/users/4fdfc8d2-005d-407c-b9f5-82ca67cff24b/skill_memory.json` | EXCLUDED_RUNTIME_STATE_SENSITIVE |
| `harness-connections-console/_V1` | `scratch/candidate_desktop_state/uri_workspace/users/6a9b4db9-d275-4d09-95f7-aad1b6dca381/graph.sqlite3` | EXCLUDED_RUNTIME_STATE_SENSITIVE |
| `harness-connections-console/_V1` | `scratch/candidate_desktop_state/uri_workspace/users/6a9b4db9-d275-4d09-95f7-aad1b6dca381/skill_memory.json` | EXCLUDED_RUNTIME_STATE_SENSITIVE |
| `harness-connections-console/_V1` | `scratch/candidate_desktop_state/uri_workspace/users/f9868cce-4df0-403f-a8b1-49acd02421da/graph.sqlite3` | EXCLUDED_RUNTIME_STATE_SENSITIVE |
| `harness-connections-console/_V1` | `scratch/candidate_desktop_state/uri_workspace/users/f9868cce-4df0-403f-a8b1-49acd02421da/provider_keys.enc` | EXCLUDED_RUNTIME_STATE_SENSITIVE |
| `harness-connections-console/_V1` | `scratch/candidate_desktop_state/uri_workspace/users/f9868cce-4df0-403f-a8b1-49acd02421da/providers.json` | EXCLUDED_RUNTIME_STATE_SENSITIVE |
| `harness-connections-console/_V1` | `scratch/candidate_desktop_state/uri_workspace/users/f9868cce-4df0-403f-a8b1-49acd02421da/skill_memory.json` | EXCLUDED_RUNTIME_STATE_SENSITIVE |
| `harness-connections-console/_V1` | `scratch/candidate_desktop_state/windows_build.log` | EXCLUDED_RUNTIME_STATE_SENSITIVE |
| `harness-connections-console/_V1` | `scratch/candidate_desktop_state/workspace_tests.log` | EXCLUDED_RUNTIME_STATE_SENSITIVE |
| `Uri/_V1` | `graphify-out/.graphify_learning.json` | EXCLUDED_DEV_ARTIFACT |
| `Uri/_V1` | `graphify-out/.vocab.txt` | EXCLUDED_DEV_ARTIFACT |
| `Uri/_V1` | `graphify-out/converted/Detailed_Noting_Draft_320b2725.md` | EXCLUDED_DEV_ARTIFACT (in local 869fae5) |
| `Uri/_V1` | `graphify-out/converted/Extension_Noting_Draft_e9795f18.md` | EXCLUDED_DEV_ARTIFACT (in local 869fae5) |
| `Uri/_V1` | `graphify-out/converted/Heavy_Noting_Draft_4bbb881d.md` | EXCLUDED_DEV_ARTIFACT (in local 869fae5) |
| `Uri/_V1` | `graphify-out/reflections/LESSONS.md` | EXCLUDED_DEV_ARTIFACT (in local 869fae5) |
| `Uri/_V1` | `scratch/desktop_harness_test_state/harness/checkpoints/cb03a28caa65487c9f0c9f0494dcdb2c.json` | EXCLUDED_RUNTIME_STATE_SENSITIVE |
| `Uri/_V1` | `scratch/desktop_harness_test_state/harness/fixtures/61d0ce26-9690-4c68-ac5a-555828b3a55f/a72a247b86654982b01dbfa4ffb5d3d5/report.py` | EXCLUDED_RUNTIME_STATE_SENSITIVE |
| `Uri/_V1` | `scratch/desktop_harness_test_state/harness/fixtures/61d0ce26-9690-4c68-ac5a-555828b3a55f/a72a247b86654982b01dbfa4ffb5d3d5/sales.xlsx` | EXCLUDED_RUNTIME_STATE_SENSITIVE |
| `Uri/_V1` | `scratch/desktop_harness_test_state/harness/private/61d0ce26-9690-4c68-ac5a-555828b3a55f/memory/attestations/534815232b2c482bb4334d10812bb17f.json` | EXCLUDED_RUNTIME_STATE_SENSITIVE |
| `Uri/_V1` | `scratch/desktop_harness_test_state/harness/private/61d0ce26-9690-4c68-ac5a-555828b3a55f/memory/events/dfb4cd7081514232be253ee1de5f0cee.json` | EXCLUDED_RUNTIME_STATE_SENSITIVE |
| `Uri/_V1` | `scratch/desktop_harness_test_state/harness/private/61d0ce26-9690-4c68-ac5a-555828b3a55f/memory/log-2026-10.jsonl` | EXCLUDED_RUNTIME_STATE_SENSITIVE |
| `Uri/_V1` | `scratch/desktop_harness_test_state/harness/private/61d0ce26-9690-4c68-ac5a-555828b3a55f/memory/sources.json` | EXCLUDED_RUNTIME_STATE_SENSITIVE |
| `Uri/_V1` | `scratch/desktop_harness_test_state/harness/private/61d0ce26-9690-4c68-ac5a-555828b3a55f/memory/telemetry-2026-10.jsonl` | EXCLUDED_RUNTIME_STATE_SENSITIVE |
| `Uri/_V1` | `scratch/desktop_harness_test_state/harness/private/61d0ce26-9690-4c68-ac5a-555828b3a55f/memory/write.guard` | EXCLUDED_RUNTIME_STATE_SENSITIVE |
| `Uri/_V1` | `scratch/desktop_harness_test_state/harness/runs/61d0ce26-9690-4c68-ac5a-555828b3a55f/execution/runs.jsonl` | EXCLUDED_RUNTIME_STATE_SENSITIVE |
| `Uri/_V1` | `scratch/desktop_harness_test_state/harness/runs/61d0ce26-9690-4c68-ac5a-555828b3a55f/execution/runs.jsonl.lock` | EXCLUDED_RUNTIME_STATE_SENSITIVE |
| `Uri/_V1` | `scratch/desktop_harness_test_state/harness/scratch/61d0ce26-9690-4c68-ac5a-555828b3a55f/workspaces/9fe01bc849784d3c9f39378dd30f50b8/bundle/INSTRUCTIONS.md` | EXCLUDED_RUNTIME_STATE_SENSITIVE |
| `Uri/_V1` | `scratch/desktop_harness_test_state/harness/scratch/61d0ce26-9690-4c68-ac5a-555828b3a55f/workspaces/9fe01bc849784d3c9f39378dd30f50b8/bundle/harness.log` | EXCLUDED_RUNTIME_STATE_SENSITIVE |
| `Uri/_V1` | `scratch/desktop_harness_test_state/harness/scratch/61d0ce26-9690-4c68-ac5a-555828b3a55f/workspaces/9fe01bc849784d3c9f39378dd30f50b8/files/report.py` | EXCLUDED_RUNTIME_STATE_SENSITIVE |
| `Uri/_V1` | `scratch/desktop_harness_test_state/harness/scratch/61d0ce26-9690-4c68-ac5a-555828b3a55f/workspaces/9fe01bc849784d3c9f39378dd30f50b8/files/sales.xlsx` | EXCLUDED_RUNTIME_STATE_SENSITIVE |
| `Uri/_V1` | `scratch/desktop_harness_test_state/harness/scratch/61d0ce26-9690-4c68-ac5a-555828b3a55f/workspaces/9fe01bc849784d3c9f39378dd30f50b8/manifest.json` | EXCLUDED_RUNTIME_STATE_SENSITIVE |
| `Uri/_V1` | `scratch/desktop_harness_test_state/harness/scratch/61d0ce26-9690-4c68-ac5a-555828b3a55f/workspaces/9fe01bc849784d3c9f39378dd30f50b8/verify/b5a12fe262304f878f2ae7b3786b180e/report.py` | EXCLUDED_RUNTIME_STATE_SENSITIVE |
| `Uri/_V1` | `scratch/desktop_harness_test_state/harness/scratch/61d0ce26-9690-4c68-ac5a-555828b3a55f/workspaces/9fe01bc849784d3c9f39378dd30f50b8/verify/b5a12fe262304f878f2ae7b3786b180e/sales.xlsx` | EXCLUDED_RUNTIME_STATE_SENSITIVE |
| `Uri/_V1` | `scratch/desktop_harness_test_state/launcher.stderr.log` | EXCLUDED_RUNTIME_STATE_SENSITIVE |
| `Uri/_V1` | `scratch/desktop_harness_test_state/launcher.stdout.log` | EXCLUDED_RUNTIME_STATE_SENSITIVE |
| `Uri/_V1` | `scratch/desktop_harness_test_state/uri_workspace/auth_sessions.json` | EXCLUDED_RUNTIME_STATE_SENSITIVE |
| `Uri/_V1` | `scratch/desktop_harness_test_state/uri_workspace/device_identity.json` | EXCLUDED_RUNTIME_STATE_SENSITIVE |
| `Uri/_V1` | `scratch/desktop_harness_test_state/uri_workspace/friction_log.json` | EXCLUDED_RUNTIME_STATE_SENSITIVE |
| `Uri/_V1` | `scratch/desktop_harness_test_state/uri_workspace/graph.sqlite3` | EXCLUDED_RUNTIME_STATE_SENSITIVE |
| `Uri/_V1` | `scratch/desktop_harness_test_state/uri_workspace/graphify_index.json` | EXCLUDED_RUNTIME_STATE_SENSITIVE |
| `Uri/_V1` | `scratch/desktop_harness_test_state/uri_workspace/portable_identity.json` | EXCLUDED_RUNTIME_STATE_SENSITIVE |
| `Uri/_V1` | `scratch/desktop_harness_test_state/uri_workspace/skill_memory.json` | EXCLUDED_RUNTIME_STATE_SENSITIVE |
| `Uri/_V1` | `scratch/desktop_harness_test_state/uri_workspace/user_accounts.json` | EXCLUDED_RUNTIME_STATE_SENSITIVE |
| `Uri/_V1` | `scratch/desktop_harness_test_state/uri_workspace/users/61d0ce26-9690-4c68-ac5a-555828b3a55f/graph.sqlite3` | EXCLUDED_RUNTIME_STATE_SENSITIVE |
| `Uri/_V1` | `scratch/desktop_harness_test_state/uri_workspace/users/61d0ce26-9690-4c68-ac5a-555828b3a55f/skill_memory.json` | EXCLUDED_RUNTIME_STATE_SENSITIVE |
| `Uri/_V1` | `scratch/desktop_harness_test_state/uri_workspace/users/c63f8f7c-217b-46f9-baef-8e020f3df116/graph.sqlite3` | EXCLUDED_RUNTIME_STATE_SENSITIVE |
| `Uri/_V1` | `scratch/desktop_harness_test_state/uri_workspace/users/c63f8f7c-217b-46f9-baef-8e020f3df116/skill_memory.json` | EXCLUDED_RUNTIME_STATE_SENSITIVE |
| `uri-agent/.tmp_m33_1_batch4_baseline_5973f6d` | `.tmp_m33_c2_pytest/c3_adapter/11111111-1111-1111-1111-111111111111/evidence_records.json` | EXCLUDED_PYTEST_TEMP |
| `uri-agent/.tmp_m33_1_batch4_baseline_5973f6d` | `.tmp_m33_c2_pytest/c3_brain_feedback/11111111-1111-1111-1111-111111111111/evidence_records.json` | EXCLUDED_PYTEST_TEMP |
| `uri-agent/.tmp_m33_1_batch4_baseline_5973f6d` | `.tmp_m33_c2_pytest/c3_brain_feedback/11111111-1111-1111-1111-111111111111/operations.json` | EXCLUDED_PYTEST_TEMP |
| `uri-agent/.tmp_m33_1_batch4_baseline_5973f6d` | `.tmp_m33_c2_pytest/c3_completion/11111111-1111-1111-1111-111111111111/evidence_records.json` | EXCLUDED_PYTEST_TEMP |
| `uri-agent/.tmp_m33_1_batch4_baseline_5973f6d` | `.tmp_m33_c2_pytest/c3_completion/11111111-1111-1111-1111-111111111111/operations.json` | EXCLUDED_PYTEST_TEMP |
| `uri-agent/.tmp_m33_1_batch4_baseline_5973f6d` | `.tmp_m33_c2_pytest/c3_orchestrator/11111111-1111-1111-1111-111111111111/evidence_records.json` | EXCLUDED_PYTEST_TEMP |
| `uri-agent/.tmp_m33_1_batch4_baseline_5973f6d` | `.tmp_m33_c2_pytest/composition/11111111-1111-1111-1111-111111111111/graph.sqlite3` | EXCLUDED_PYTEST_TEMP |
| `uri-agent/.tmp_m33_1_batch4_baseline_5973f6d` | `.tmp_m33_c2_pytest/composition/11111111-1111-1111-1111-111111111111/skill_memory.json` | EXCLUDED_PYTEST_TEMP |
| `uri-agent/.tmp_m33_1_batch4_baseline_5973f6d` | `.tmp_m33_c2_pytest/composition/22222222-2222-2222-2222-222222222222/graph.sqlite3` | EXCLUDED_PYTEST_TEMP |
| `uri-agent/.tmp_m33_1_batch4_baseline_5973f6d` | `.tmp_m33_c2_pytest/composition/22222222-2222-2222-2222-222222222222/skill_memory.json` | EXCLUDED_PYTEST_TEMP |
| `uri-agent/.tmp_m33_1_batch4_baseline_5973f6d` | `.tmp_m33_c2_pytest/evidence_atomic/11111111-1111-1111-1111-111111111111/evidence_records.json` | EXCLUDED_PYTEST_TEMP |
| `uri-agent/.tmp_m33_1_batch4_baseline_5973f6d` | `.tmp_m33_c2_pytest/evidence_corrupt/11111111-1111-1111-1111-111111111111/evidence_records.json` | EXCLUDED_PYTEST_TEMP |
| `uri-agent/.tmp_m33_1_batch4_baseline_5973f6d` | `.tmp_m33_c2_pytest/evidence_redaction/11111111-1111-1111-1111-111111111111/evidence_records.json` | EXCLUDED_PYTEST_TEMP |
| `uri-agent/.tmp_m33_1_batch4_baseline_5973f6d` | `.tmp_m33_c2_pytest/evidence_restart/11111111-1111-1111-1111-111111111111/evidence_records.json` | EXCLUDED_PYTEST_TEMP |
| `uri-agent/.tmp_m33_1_batch4_baseline_5973f6d` | `.tmp_m33_c2_pytest/operation_corrupt/11111111-1111-1111-1111-111111111111/operations.json` | EXCLUDED_PYTEST_TEMP |
| `uri-agent/.tmp_m33_1_batch4_baseline_5973f6d` | `.tmp_m33_c2_pytest/operation_isolation/11111111-1111-1111-1111-111111111111/operations.json` | EXCLUDED_PYTEST_TEMP |
| `uri-agent/.tmp_m33_1_batch4_baseline_5973f6d` | `.tmp_m33_c2_pytest/operation_pending/11111111-1111-1111-1111-111111111111/operations.json` | EXCLUDED_PYTEST_TEMP |
| `uri-agent/.tmp_m33_1_batch4_baseline_5973f6d` | `.tmp_m33_c2_pytest/operation_restart/11111111-1111-1111-1111-111111111111/operations.json` | EXCLUDED_PYTEST_TEMP |
| `uri-agent/.tmp_m33_1_batch4_baseline_5973f6d` | `Launch URI.bat` | EXCLUDED_DELETION_IN_THROWAWAY_BASELINE (tracked Launch URI.bat deleted in old M33.1 baseline worktree; file exists in git history) |
| `Development/uri-m37-m39-integration` | `uri_workspace/uri_server.pid` | EXCLUDED_RUNTIME_PID |
| `Development/uri-m37-m39-integration` | `uri_workspace/uri_ui.pid` | EXCLUDED_RUNTIME_PID |

Phase 2 note: 15 files accepted in r6 were changed again by the closure; A4 holds their r6 bytes and A7 their accepted closure (-f) bytes. Three closure docs edited at 08:31 after acceptance are in A9. Nothing remains held (correction record: `GIT_SYNC_AUDIT.md` §12).
