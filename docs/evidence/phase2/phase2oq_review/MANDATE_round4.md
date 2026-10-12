# Independent re-review mandate (operational qualification, round 4)

ROLE. You are the INDEPENDENT REVIEWER. Round 3 (C:\Users\cheta\.codex\worktrees\uri-phase2a\evidence\phase2oq_review\round3\CODEX_REVIEW_OQ_round3.md)
rejected candidate -c (a2c11441bb51975fcb3fbbec84f89760d13f24e9f815d2f13d9e88452f049602) on OQ-R3-1 (pass/skip swap under
one skip-summary key passed the Phase 1 gate) and OQ-R3-2 (self-made collection baseline; scope check exempted the Phase 1
runner); OQ-R1-1..3 repaired. The implementer (a different agent) replaced the gate with per-test outcome identity against
a baseline made with the ACCEPTED -f runner bytes, bound the runner in the scope check, and appended section N and Record
H4 to C:\Users\cheta\.codex\worktrees\uri-phase2a\uri-agent\docs\plans\PHASE2OQ_REPORT.md. Those are CLAIMS.
Decide from files, commands and probes you run yourself.

Rules (unchanged): modify no repository file; write only under
C:\Users\cheta\.codex\worktrees\uri-phase2a\evidence\phase2oq_review\round4\ and runtime state your probes create under
C:\Users\cheta\.codex\worktrees\uri-phase2a\uri-agent\work\c1\. No login/logout, no credential reads (nothing under any
.codex or .claude home, including client profiles' auth files), no global/account configuration change, no
administrator action, no reboot/power-cycle, no commit/push/merge, do not kill processes you did not start.

SUBJECT. ROUND4_SUBJECT.txt beside this mandate. Live tree C:\Users\cheta\.codex\worktrees\uri-phase2a\uri-agent
(HEAD e8e3b65, uncommitted). The closure -f, round-7 and Phase 1 frozen checkpoints must be unchanged.

EVIDENCE. Orchestrator chain C:\Users\cheta\.codex\worktrees\uri-phase2a\evidence\phase2oq\chain7\ (ORCHESTRATOR-PRODUCED). Outcome baseline run: C:\Users\cheta\.codex\worktrees\uri-phase2a\evidence\phase2oq\outcome_baseline\.

TASKS.
A. Integrity: -d hash, manifest vs tree, frozen boundary, exact change set vs -c.
B. OQ-R3-1: attack `outcome_identity` / `junit_outcomes` and the phase1-full gate in scripts/phase2close_chain.py. Can a
   missing test, added test, lost pass, pass/skip swap, new failure or new skip pass? Do JUnit IDs collide or drop tests?
C. OQ-R3-2: is `phase1_outcome_baseline.json` bound to the ACCEPTED runner (runner_argv capture from the -f zip, SHA-256,
   argv) and anchored to the accepted log? Can a modified current runner, ini or Phase 1 input pass `phase1_scope_check`?
   Is the disclosed `--ignore=tests/phase2oq` addition and the stated residual limitation acceptable?
D. Is chain7 a single green full chain on the -d tree? OQ-R1-1..3 and round-1 B-K dispositions still hold?
E. New defects.
F. EXACTLY ONE final verdict:
   PHASE 2 OPERATIONAL CANDIDATE REJECTED
   PHASE 2 OPERATIONAL CANDIDATE ACCEPTED — READY FOR OWNER PHYSICAL ACCEPTANCE
   PHASE 2 ACCEPTED AND QUALIFIED

OUTPUT. Full report to C:\Users\cheta\.codex\worktrees\uri-phase2a\evidence\phase2oq_review\round4\CODEX_REVIEW_OQ_round4.md
with sections A-F, a DEFECTS table, a disposition table for OQ-R1-1..4, OQ-R2-1, OQ-R3-1, OQ-R3-2, NOT VERIFIED, FINAL VERDICT. Print the FINAL
VERDICT line and both tables as your last message.
