# Independent re-review mandate (round 3): URI Phase 2 UI/operations repaired candidate

ROLE. You are the INDEPENDENT REVIEWER. Two earlier independent reviews (same role) rejected earlier candidates:
C:\Users\cheta\.codex\worktrees\uri-phase2a\evidence\phase2ops_review\round1\CODEX_REVIEW_round1.md and
C:\Users\cheta\.codex\worktrees\uri-phase2a\evidence\phase2ops_review\round2\CODEX_REVIEW_round2.md (OPS-1R, OPS-2R).
The implementer (a different agent) changed the code again and wrote <tree>\docs\plans\PHASE2OPS_REVIEW_REPAIR_ROUND2.md
(and ..._ROUND1.md) plus a correction record at the end of <tree>\docs\plans\PHASE2OPS_REPORT.md. Those records and
every implementer document are CLAIMS. Decide from files, commands and probes you run yourself.

Rules: do not modify any source, test, document or configuration file in the repository. Write only under
C:\Users\cheta\.codex\worktrees\uri-phase2a\evidence\phase2ops_review\round3\ and runtime state your own probes create
under <tree>\work\c1\. Do not log in/out, read credential files, change global or account configuration, reboot or
power-cycle, run `codex login`, or commit/push/merge.

SUBJECT. New candidate path and expected SHA-256 in ROUND3_SUBJECT.txt next to this mandate (sidecar .json beside the
zip). Live tree C:\Users\cheta\.codex\worktrees\uri-phase2a\uri-agent (HEAD e8e3b65, uncommitted). Earlier candidates must
be unchanged: -r1 bffa742ac9f8b4e6aadebde8bb91aa6c22638be6b4feeca6a5cfb7a0a1aa8ec7; original
ce935c4be0e29c67d0d34772c9584e8ce3ac836e118e490ad167d8447d13d9d8; Phase 2D r2
cbec537adffcd629d5b7aec907e50c8eeea6f83d8edf52e05b658deb0968688d. Phase 1 frozen checkpoint
31a34dcbb37ee48e1b06a1bcd60418a2e52ff9a0c65fd8cc7f3c59defeb98cf7: every checkpoint file byte-identical.

TEST-EXECUTION NOTE. Your sandbox cannot run pytest or Flutter. Post-repair orchestrator logs:
C:\Users\cheta\.codex\worktrees\uri-phase2a\evidence\phase2ops_r2\ — ORCHESTRATOR-PRODUCED claims; check commands,
scope, counts, failure IDs; reproduce what your sandbox allows (direct-import probes worked in rounds 1-2; the preserved
work/c1 ledgers are readable with read-only sqlite, so you can check that a real COMPLETE task row carries the
`execution_id` of exactly its record). Say what you reproduced and what you only read.

TASKS.
A. Integrity and Phase 1 frozen boundary (as before).
B. Disposition of OPS-1R and OPS-2R; attack the repairs:
   - the ledger binding: `SupervisorBridge.execute(work, context=...)` -> task `request_json.execution_id`; is the
     context ever authority-bearing? can it be absent/forged (a bridge call without context, a record whose id matches
     because the forger also wrote the ledger — state the trust boundary honestly)? `corroborate()` rules for harness
     and local records, status vs list parity, server operation/session requirements, offline policy;
   - `_well_typed` in the register: any valid-JSON shape that still raises anywhere in listing, status, restart
     reconciliation, cancel or close? nested shapes inside `proposal`/`evidence`/`restart_ledger`?
C. New defects introduced by the repair (cite file:line; say if reproduced).
D. Confirm or update your determinations: UI wiring truth table (a)-(e); what remains USER-PHYSICAL; remaining Phase 2
   slices (is Context Capsule / Task Compiler next?); research/implementation ledger overstatements.
E. EXACTLY ONE final verdict:
   UI/OPERATIONS SLICE REJECTED
   UI/OPERATIONS SLICE ACCEPTED — MORE PHASE 2 WORK REMAINS
   PHASE 2 IMPLEMENTATION COMPLETE — USER QUALIFICATION REMAINS
   READY TO FREEZE

OUTPUT. Full report to C:\Users\cheta\.codex\worktrees\uri-phase2a\evidence\phase2ops_review\round3\CODEX_REVIEW_round3.md
with sections A-E, DEFECTS table, disposition table for every earlier finding (OPS-1..3, OPS-1R, OPS-2R), NOT VERIFIED,
FINAL VERDICT. Print the FINAL VERDICT line and both tables as your last message.
