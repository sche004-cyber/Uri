# Phase 2 UI/operations: response to independent review round 1 (implementer's repair record)

Date 2026-10-07. Author: Claude (implementer/orchestrator). NOT a review; accepts nothing. Reviewer: Codex CLI 0.158.0,
model gpt-6-sol, `codex exec` (fresh session, workspace-write sandbox, thread `01a116ad-91c5-77d0-94fb-0e2b72af9e93`);
verdict **UI/OPERATIONS SLICE REJECTED**; report kept verbatim at `evidence\phase2ops_review\round1\CODEX_REVIEW_round1.md`.
Reviewed candidate `phase2ops-candidate-20261007.zip` (SHA-256 `ce935c4b...13d9d8`) is preserved unchanged. Pre-repair
copies: `evidence\phase2ops_review\round1\execution_before_round1_repair.py.txt`,
`supervised_execution_screen_before_round1_repair.dart.txt`.

| Reviewer ID | Severity (reviewer) | Implementer response | Regression tests |
|---|---|---|---|
| OPS-1 a valid-schema register record saying `completed` was relayed as completed although no ledger task, journal receipt or server settlement corroborated it (reconnect could show false success) | High | REPAIRED. `execution.corroborate()`: a harness execution is reported `completed` only while the ledger says COMPLETE, the journal says `verified`, the server (when it answers) says `reply` for the same operation, and the code is `SETTLED_VERIFIED`; a local (no-task) execution only while the server answers `reply`. Any gap -> `uncertain`, `UNCORROBORATED_COMPLETION:<gaps>`, with `recorded_state` and a `corroboration` block kept beside it. Applied to `execution_status` AND `execution_list`. The Dart model carries `recordedState`/`corroboration`; the card says when the record's claim was not confirmed and shows no receipt. | `test_reconnect.py::test_ops1_a_record_claiming_completed_is_uncertain_unless_ledger_journal_and_server_agree` (forged record with no facts; forged record pointing at a REAL cancelled task; genuine completion keeps `completed`; deleting the journal downgrades it), widget test "an uncorroborated record is shown as UNCERTAIN ..." |
| OPS-2 valid JSON without `execution_id` (or wrong id / non-string state) raised `KeyError` in listing and could abort restart reconciliation | Medium | REPAIRED. `ExecutionRegister.get()` treats a record whose `execution_id` is not the file's own, or whose `state` is not a string, as an uncertain `RECORD_SCHEMA` stub (same as non-JSON). Listing, status and restart reconciliation never abort. | `test_reconnect.py::test_ops2_valid_json_but_malformed_records_never_break_listing_or_restart` |
| OPS-3 the approval card did not render `approval_request.arguments` verbatim (C6 contract) | Medium | REPAIRED. The card shows the exact arguments object (indented JSON) and the argument digest above the approval/proposal digests, before the button. | widget test "approval card renders the exact arguments object verbatim" |

Implementer's own hardening while repairing OPS-1 (found by self-audit, not by the reviewer): a record could borrow
ANOTHER execution's genuinely completed `task_id`/`turn_id` and be corroborated by that task's facts. `ledger_view` now
also returns the task's own request row (turn, operation, session, capability, provider, model, approval/argument
digests) and `corroborate()` requires it to equal the record's turn and proposal (`LEDGER_REQUEST_MISMATCH`); a
local execution additionally requires the server's `session_id` to be the record's. Limit stated honestly: for a local
(no-task) execution the record's text is attested only by the server's turn state/session, not by a supervisor row.
Test: `test_ops1_*` (c2): borrowed task with another selection -> `uncertain`; a faithful copy of the same facts and
selection stays `completed`.

Reviewer determinations acknowledged, no change: (d) real Flutter UI = PARTIAL until a human click (DEFERRED, user
physical presence); the Tasks route is an opt-in parallel route, Chat `/ask` migration and a pinned UI build stay C7
gates; Context Capsule / Task Compiler remain design-only, later, not the next mandatory slice.

Post-repair evidence (ORCHESTRATOR-PRODUCED; the reviewer's sandbox cannot run pytest or Flutter): `evidence\phase2ops_r1\`
(phase2_all.log, phase1_authority.log, phase1_full.log, flutter_all.log, ui_bridge_live.json, codex_cli_lifecycle_*.json).

Files changed by this repair: `uri_supervisor_bridge/execution.py`, `uri_ui/lib/services/supervised_runtime.dart`,
`uri_ui/lib/screens/tasks/supervised_execution_screen.dart`, `tests/phase2ops/test_reconnect.py`,
`uri_ui/test/supervised_execution_screen_test.dart`, `docs/plans/PHASE2OPS_REPORT.md` (correction record), this file.
Frozen Phase 1 files: none changed.
