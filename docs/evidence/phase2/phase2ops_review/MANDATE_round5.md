# Independent re-review mandate (round 5): URI Phase 2 UI/operations repaired candidate

ROLE. You are the INDEPENDENT REVIEWER. Four earlier independent reviews (same role) rejected earlier candidates
(C:\Users\cheta\.codex\worktrees\uri-phase2a\evidence\phase2ops_review\round1..round4\CODEX_REVIEW_round*.md; round 4 left
OPS-4 residual, OPS-1R residual, OPS-2R residual, VAL-1). The implementer (a different agent) changed the code again and
wrote <tree>\docs\plans\PHASE2OPS_REVIEW_REPAIR_ROUND4.md (and ..._ROUND1/2/3.md) plus correction records at the end of
<tree>\docs\plans\PHASE2OPS_REPORT.md. Those records and every implementer document are CLAIMS. Decide from files,
commands and probes you run yourself.

Rules: do not modify any source, test, document or configuration file in the repository. Write only under
C:\Users\cheta\.codex\worktrees\uri-phase2a\evidence\phase2ops_review\round5\ and runtime state your own probes create
under <tree>\work\c1\. Do not log in/out, read credential files, change global or account configuration, reboot or
power-cycle, run `codex login`, or commit/push/merge.

SUBJECT. New candidate path and expected SHA-256 in ROUND5_SUBJECT.txt next to this mandate (sidecar .json beside the
zip). Live tree C:\Users\cheta\.codex\worktrees\uri-phase2a\uri-agent (HEAD e8e3b65, uncommitted). Earlier candidates must
be unchanged: -r3 fdfb78edf9621ee8828d6a4a10c5a466fa3116f22e8c82cfea100a2e05937b64; -r2
05127e2fe87ef869e83eeddcdcae47cc3eb804dd5bce791b34860b966b1cbead; -r1
bffa742ac9f8b4e6aadebde8bb91aa6c22638be6b4feeca6a5cfb7a0a1aa8ec7; original
ce935c4be0e29c67d0d34772c9584e8ce3ac836e118e490ad167d8447d13d9d8; Phase 2D r2
cbec537adffcd629d5b7aec907e50c8eeea6f83d8edf52e05b658deb0968688d. Phase 1 frozen checkpoint
31a34dcbb37ee48e1b06a1bcd60418a2e52ff9a0c65fd8cc7f3c59defeb98cf7: every checkpoint file byte-identical.

TEST-EXECUTION NOTE. Your sandbox cannot run pytest or Flutter. Post-repair orchestrator logs:
C:\Users\cheta\.codex\worktrees\uri-phase2a\evidence\phase2ops_r4\ (phase2_all.log, phase1_authority.log,
phase1_full.log, flutter_all.log, ui_bridge_live_1..10.json, refusals.txt, codex_cli_lifecycle_*.json,
native_codex_stdout.txt) — ORCHESTRATOR-PRODUCED claims; check commands, scope, counts, failure IDs, and that the
native run and every live bridge run ended as claimed. Reproduce what your sandbox allows (direct-import probes; the
preserved work/c1 state: execution records, the operations index under control/supervisor/executions/operations/,
read-only sqlite on ledgers and journals). Say what you reproduced and what you only read.

TASKS.
A. Integrity and Phase 1 frozen boundary (as before).
B. Disposition of every earlier finding (OPS-1..3, OPS-1R, OPS-2R, OPS-4, OPS-5, VAL-1); attack the repairs:
   - operation ownership: `ExecutionRegister.claim_operation` (create-once), `corroborate()` requirements
     (OPERATION_MISSING / OPERATION_NOT_OWNED / OPERATION_TASK_MISMATCH / SERVER_OPERATION_MISMATCH / JOURNAL_NOT_VERIFIED
     for local records too). Can any record (local or harness) still be shown `completed` on borrowed facts, in status
     or list? Is the claim written at the right moment (ticket verified, before dispatch)? What if the claim file is
     missing, corrupt, or claimed by a crashed earlier execution? State the trust boundary honestly.
   - OPS-4: `grep` every composition seam for `execute(work` without keywords; did the native run complete on this tree?
   - OPS-2R: nested evidence/proposal rules vs the Dart `is`-checked reads; anything left that throws?
   - VAL-1: `RefusalLog` in scripts/run_uri_phase2_server.py (profile only): is it clean (no bodies/bearers logged for
     success; codes only), and what do the ten live-bridge runs and refusals.txt show?
C. New defects introduced by the repair (cite file:line; say if reproduced).
D. Confirm or update: UI wiring truth table (a)-(e); what remains USER-PHYSICAL; remaining Phase 2 slices; research
   ledger overstatements.
E. EXACTLY ONE final verdict:
   UI/OPERATIONS SLICE REJECTED
   UI/OPERATIONS SLICE ACCEPTED — MORE PHASE 2 WORK REMAINS
   PHASE 2 IMPLEMENTATION COMPLETE — USER QUALIFICATION REMAINS
   READY TO FREEZE

OUTPUT. Full report to C:\Users\cheta\.codex\worktrees\uri-phase2a\evidence\phase2ops_review\round5\CODEX_REVIEW_round5.md
with sections A-E, DEFECTS table, disposition table for every earlier finding, NOT VERIFIED, FINAL VERDICT. Print the
FINAL VERDICT line and both tables as your last message.
