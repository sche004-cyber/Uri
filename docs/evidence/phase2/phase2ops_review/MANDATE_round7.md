# Independent re-review mandate (round 7): URI Phase 2 UI/operations repaired candidate

ROLE. You are the INDEPENDENT REVIEWER. Six earlier independent reviews (same role) rejected earlier candidates
(C:\Users\cheta\.codex\worktrees\uri-phase2a\evidence\phase2ops_review\round1..round6\CODEX_REVIEW_round*.md). Round 6
kept every execution/UI finding REPAIRED, judged VAL-1 a physical-qualification item rather than a slice blocker, and
rejected on LOG-1R (format check instead of an allow-list in the refusal logger) and LOG-2 (`/client/v1evil` prefix).
The implementer (a different agent) changed the code again and wrote <tree>\docs\plans\PHASE2OPS_REVIEW_REPAIR_ROUND6.md
(and ..._ROUND1-5.md) plus correction records at the end of <tree>\docs\plans\PHASE2OPS_REPORT.md. Those records and
every implementer document are CLAIMS. Decide from files, commands and probes you run yourself.

Rules: do not modify any source, test, document or configuration file in the repository. Write only under
C:\Users\cheta\.codex\worktrees\uri-phase2a\evidence\phase2ops_review\round7\ and runtime state your own probes create
under <tree>\work\c1\. Do not log in/out, read credential files, change global or account configuration, reboot or
power-cycle, run `codex login`, or commit/push/merge.

SUBJECT. New candidate path and expected SHA-256 in ROUND7_SUBJECT.txt next to this mandate (sidecar .json beside the
zip). Live tree C:\Users\cheta\.codex\worktrees\uri-phase2a\uri-agent (HEAD e8e3b65, uncommitted). Earlier candidates must
be unchanged: -r5 1daa73f75f096ee039f9a039b96516cd821574724d8f663b8eea4acb46f6c047; -r4
fc9c96ec2b5b44a70f8486dccd9d0aa2b2eb28dafa01f9ac6f6e1594e251ed58; -r3
fdfb78edf9621ee8828d6a4a10c5a466fa3116f22e8c82cfea100a2e05937b64; -r2
05127e2fe87ef869e83eeddcdcae47cc3eb804dd5bce791b34860b966b1cbead; -r1
bffa742ac9f8b4e6aadebde8bb91aa6c22638be6b4feeca6a5cfb7a0a1aa8ec7; original
ce935c4be0e29c67d0d34772c9584e8ce3ac836e118e490ad167d8447d13d9d8; Phase 2D r2
cbec537adffcd629d5b7aec907e50c8eeea6f83d8edf52e05b658deb0968688d. Phase 1 frozen checkpoint
31a34dcbb37ee48e1b06a1bcd60418a2e52ff9a0c65fd8cc7f3c59defeb98cf7: every checkpoint file byte-identical.

TEST-EXECUTION NOTE. Your sandbox cannot run pytest or Flutter. Post-repair orchestrator logs:
C:\Users\cheta\.codex\worktrees\uri-phase2a\evidence\phase2ops_r6\ (phase2_all.log, phase1_authority.log,
phase1_full.log, flutter_all.log, ui_bridge_live_1..10.json, refusals.txt, codex_cli_lifecycle_*.json) —
ORCHESTRATOR-PRODUCED claims; check commands, scope, counts, failure IDs, and that the native run and every live bridge
run ended as claimed. Reproduce what your sandbox allows. Say what you reproduced and what you only read.

TASKS.
A. Integrity and Phase 1 frozen boundary (as before). Verify by digest that only `uri_supervisor_bridge/refusal_log.py`,
   its test, and documents changed since -r5.
B. Disposition of LOG-1R and LOG-2; attack `refusal_log.py` once more (`KNOWN_CODES` allow-list vs the frozen server's
   actual refusal codes: anything missing, anything that should not be there? `in_scope`, `route_shape`, method and
   status handling, body truncation). Confirm the earlier findings remain repaired on this tree. VAL-1: with the
   diagnostic in place and ten more clean runs, restate whether it blocks this slice.
C. New defects introduced by the repair (cite file:line; say if reproduced).
D. Confirm or update: UI wiring truth table (a)-(e); what remains USER-PHYSICAL; remaining Phase 2 slices; research
   ledger overstatements.
E. EXACTLY ONE final verdict:
   UI/OPERATIONS SLICE REJECTED
   UI/OPERATIONS SLICE ACCEPTED — MORE PHASE 2 WORK REMAINS
   PHASE 2 IMPLEMENTATION COMPLETE — USER QUALIFICATION REMAINS
   READY TO FREEZE

OUTPUT. Full report to C:\Users\cheta\.codex\worktrees\uri-phase2a\evidence\phase2ops_review\round7\CODEX_REVIEW_round7.md
with sections A-E, DEFECTS table, disposition table for every earlier finding, NOT VERIFIED, FINAL VERDICT. Print the
FINAL VERDICT line and both tables as your last message.
