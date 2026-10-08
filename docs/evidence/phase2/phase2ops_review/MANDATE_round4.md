# Independent re-review mandate (round 4): URI Phase 2 UI/operations repaired candidate

ROLE. You are the INDEPENDENT REVIEWER. Three earlier independent reviews (same role) rejected earlier candidates:
C:\Users\cheta\.codex\worktrees\uri-phase2a\evidence\phase2ops_review\round1\CODEX_REVIEW_round1.md,
round2\CODEX_REVIEW_round2.md and round3\CODEX_REVIEW_round3.md (OPS-4 High, OPS-1R, OPS-2R, OPS-5, VAL-1). The
implementer (a different agent) changed the code again and wrote <tree>\docs\plans\PHASE2OPS_REVIEW_REPAIR_ROUND3.md
(and ..._ROUND1/2.md) plus correction records at the end of <tree>\docs\plans\PHASE2OPS_REPORT.md. Those records and
every implementer document are CLAIMS. Decide from files, commands and probes you run yourself.

Rules: do not modify any source, test, document or configuration file in the repository. Write only under
C:\Users\cheta\.codex\worktrees\uri-phase2a\evidence\phase2ops_review\round4\ and runtime state your own probes create
under <tree>\work\c1\. Do not log in/out, read credential files, change global or account configuration, reboot or
power-cycle, run `codex login`, or commit/push/merge.

SUBJECT. New candidate path and expected SHA-256 in ROUND4_SUBJECT.txt next to this mandate (sidecar .json beside the
zip). Live tree C:\Users\cheta\.codex\worktrees\uri-phase2a\uri-agent (HEAD e8e3b65, uncommitted). Earlier candidates must
be unchanged: -r2 05127e2fe87ef869e83eeddcdcae47cc3eb804dd5bce791b34860b966b1cbead; -r1
bffa742ac9f8b4e6aadebde8bb91aa6c22638be6b4feeca6a5cfb7a0a1aa8ec7; original
ce935c4be0e29c67d0d34772c9584e8ce3ac836e118e490ad167d8447d13d9d8; Phase 2D r2
cbec537adffcd629d5b7aec907e50c8eeea6f83d8edf52e05b658deb0968688d. Phase 1 frozen checkpoint
31a34dcbb37ee48e1b06a1bcd60418a2e52ff9a0c65fd8cc7f3c59defeb98cf7: every checkpoint file byte-identical.

TEST-EXECUTION NOTE. Your sandbox cannot run pytest or Flutter. Post-repair orchestrator logs:
C:\Users\cheta\.codex\worktrees\uri-phase2a\evidence\phase2ops_r3\ (phase2_all.log, phase1_authority.log,
phase1_full.log, flutter_all.log, ui_bridge_live_1..5.json, codex_cli_lifecycle_*.json, native_codex_stdout.txt) —
ORCHESTRATOR-PRODUCED claims; check commands, scope, counts, failure IDs, and that the native run and every live bridge
run actually ended as claimed; reproduce what your sandbox allows (direct-import probes; read-only sqlite on the
preserved work/c1 ledgers). Say what you reproduced and what you only read.

TASKS.
A. Integrity and Phase 1 frozen boundary (as before).
B. Disposition of OPS-4, OPS-1R, OPS-2R, OPS-5, VAL-1 (and OPS-1..3); attack the repairs:
   - OPS-4: does any other composition seam still call `bridge.execute(work)` without keywords? did the native run
     (lifecycle + mid-run cancel) genuinely complete on this exact tree?
   - OPS-1R residual: `TASK_OMITTED` (harness kind, or server operation that is a supervisor task) — any remaining
     way for a no-task record to be shown `completed` on borrowed facts? local records (deterministic row) still
     corroborated correctly?
   - OPS-2R residual: `_well_typed` nested rules vs the Dart tolerant readers (`_str/_bool/_num/_map/_maps`): any
     valid-JSON shape that still throws in Python (listing, status, restart, cancel, close) or in the Dart decoders?
   - OPS-5: `ledger_view` with non-object `request_json`; any other ledger shape that raises?
   - VAL-1: the implementer could not reproduce the HTTP 403 (two reruns passed, five more in phase2ops_r3) and enabled
     uvicorn access logging in the Phase 2 server PROFILE only. Judge: is an unexplained intermittent failure of the
     live bridge acceptable for this slice, and is the access-log change itself clean (no bodies/bearers)?
C. New defects introduced by the repair (cite file:line; say if reproduced).
D. Confirm or update: UI wiring truth table (a)-(e); what remains USER-PHYSICAL; remaining Phase 2 slices; research
   ledger overstatements.
E. EXACTLY ONE final verdict:
   UI/OPERATIONS SLICE REJECTED
   UI/OPERATIONS SLICE ACCEPTED — MORE PHASE 2 WORK REMAINS
   PHASE 2 IMPLEMENTATION COMPLETE — USER QUALIFICATION REMAINS
   READY TO FREEZE

OUTPUT. Full report to C:\Users\cheta\.codex\worktrees\uri-phase2a\evidence\phase2ops_review\round4\CODEX_REVIEW_round4.md
with sections A-E, DEFECTS table, disposition table for every earlier finding, NOT VERIFIED, FINAL VERDICT. Print the
FINAL VERDICT line and both tables as your last message.
