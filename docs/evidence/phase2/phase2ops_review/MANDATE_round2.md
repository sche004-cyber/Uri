# Independent re-review mandate (round 2): URI Phase 2 UI/operations repaired candidate

ROLE. You are the INDEPENDENT REVIEWER. An earlier independent review (same role) rejected the first candidate:
C:\Users\cheta\.codex\worktrees\uri-phase2a\evidence\phase2ops_review\round1\CODEX_REVIEW_round1.md (OPS-1 High, OPS-2
Medium, OPS-3 Medium). The implementer (a different agent) changed the code and wrote
<tree>\docs\plans\PHASE2OPS_REVIEW_REPAIR_ROUND1.md plus a correction record at the end of <tree>\docs\plans\PHASE2OPS_REPORT.md.
Those records and every implementer document are CLAIMS. Decide from files, commands and probes you run yourself; you
may disagree with the earlier review.

Rules: do not modify any source, test, document or configuration file in the repository. Write only under
C:\Users\cheta\.codex\worktrees\uri-phase2a\evidence\phase2ops_review\round2\ and runtime state your own probes create
under <tree>\work\c1\. Do not log in/out, read credential files, change global or account configuration, reboot or
power-cycle, run `codex login`, or commit/push/merge.

SUBJECT. New candidate path and expected SHA-256 in ROUND2_SUBJECT.txt next to this mandate (sidecar .json beside the
zip). Live tree C:\Users\cheta\.codex\worktrees\uri-phase2a\uri-agent (HEAD e8e3b65, uncommitted). Earlier candidates
must be unchanged: phase2ops-candidate-20261007.zip ce935c4be0e29c67d0d34772c9584e8ce3ac836e118e490ad167d8447d13d9d8;
phase2d-candidate-20261007-r2.zip cbec537adffcd629d5b7aec907e50c8eeea6f83d8edf52e05b658deb0968688d. Phase 1 frozen
checkpoint 31a34dcbb37ee48e1b06a1bcd60418a2e52ff9a0c65fd8cc7f3c59defeb98cf7 (path in tests/phase2a/test_frozen_core.py):
every checkpoint file byte-identical; uri_ui/lib/app.dart is outside it (round-1 finding: legitimate ALLOWED_NEW entry).

TEST-EXECUTION NOTE. Your sandbox cannot run pytest (WinError 5) or Flutter. Post-repair orchestrator logs:
C:\Users\cheta\.codex\worktrees\uri-phase2a\evidence\phase2ops_r1\ (phase2_all.log, phase1_authority.log, phase1_full.log,
flutter_all.log, ui_bridge_live.json, ui_bridge_stdout.txt, codex_cli_lifecycle_*.json, native_codex_stdout.txt) —
ORCHESTRATOR-PRODUCED claims; check commands, scope, counts, failure IDs; reproduce what your sandbox allows
(your round-1 direct-import register probes under work/c1 worked). Say what you reproduced and what you only read.

TASKS.
A. Integrity and Phase 1 frozen boundary (as in round 1).
B. Disposition of OPS-1, OPS-2, OPS-3; attack the repairs:
   - `corroborate()` in uri_supervisor_bridge/execution.py: can any record still be relayed as `completed` without
     ledger COMPLETE + journal verified + server reply (harness) or server reply (local)? listing vs status parity;
     a forged record pointing at ANOTHER execution's genuinely completed task_id/turn_id (does the corroboration check
     the right operation?); server unreachable; `recorded_state`/`corroboration` honesty; does any legitimate
     completion now get wrongly downgraded (e.g. harness completion while the server is down: intended `completed`
     with the server gap tolerated — is that right?);
   - ExecutionRegister.get() stub rules: any valid-JSON shape that still raises? reconcile_restart over stubs;
   - the approval card: are the arguments rendered verbatim and bound (argument digest) before the button?
C. New defects introduced by the repair (anything else you find; cite file:line; say if reproduced).
D. Confirm or update your round-1 determinations: UI wiring truth table (a)-(e); what remains USER-PHYSICAL; remaining
   Phase 2 slices and whether Context Capsule / Task Compiler is next; research/implementation ledger overstatements.
E. EXACTLY ONE final verdict:
   UI/OPERATIONS SLICE REJECTED
   UI/OPERATIONS SLICE ACCEPTED — MORE PHASE 2 WORK REMAINS
   PHASE 2 IMPLEMENTATION COMPLETE — USER QUALIFICATION REMAINS
   READY TO FREEZE

OUTPUT. Full report to C:\Users\cheta\.codex\worktrees\uri-phase2a\evidence\phase2ops_review\round2\CODEX_REVIEW_round2.md
with sections A-E, DEFECTS table (id, severity, file:line, failure scenario, evidence/reproduced?, blocks verdict?),
disposition table for OPS-1..3, NOT VERIFIED, FINAL VERDICT. Print the FINAL VERDICT line and both tables as your last message.
