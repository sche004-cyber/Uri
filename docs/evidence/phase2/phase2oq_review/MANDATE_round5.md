# Independent re-review mandate (operational qualification, round 5)

ROLE. You are the INDEPENDENT REVIEWER. Round 4 (C:\Users\cheta\.codex\worktrees\uri-phase2a\evidence\phase2oq_review\round4\CODEX_REVIEW_OQ_round4.md)
rejected candidate -d (822c49be4e9841cacfe824d91d4a64fbb4c8da7f92f350dc27933cb9dedd0b8b) on OQ-R4-1 (colliding JUnit
classname::name collapsed, so an added colliding test passed the Phase 1 outcome gate) and found OQ-R3-1/OQ-R3-2 and
OQ-R1-1..3 repaired. The implementer (a different agent) added `junit_records`/`junit_integrity` and regression tests, and
appended section O and Record H5 to C:\Users\cheta\.codex\worktrees\uri-phase2a\uri-agent\docs\plans\PHASE2OQ_REPORT.md.
Those are CLAIMS. Decide from files, commands and probes you run yourself.

Rules (unchanged): modify no repository file; write only under
C:\Users\cheta\.codex\worktrees\uri-phase2a\evidence\phase2oq_review\round5\ and runtime state your probes create under
C:\Users\cheta\.codex\worktrees\uri-phase2a\uri-agent\work\c1\. No login/logout, no credential reads (nothing under any
.codex or .claude home, including client profiles' auth files), no global/account configuration change, no
administrator action, no reboot/power-cycle, no commit/push/merge, do not kill processes you did not start.

SUBJECT. ROUND5_SUBJECT.txt beside this mandate. Live tree C:\Users\cheta\.codex\worktrees\uri-phase2a\uri-agent
(HEAD e8e3b65, uncommitted). The closure -f, round-7 and Phase 1 frozen checkpoints must be unchanged.

EVIDENCE. Orchestrator chain C:\Users\cheta\.codex\worktrees\uri-phase2a\evidence\phase2oq\chain8\ (ORCHESTRATOR-PRODUCED). Outcome baseline run: C:\Users\cheta\.codex\worktrees\uri-phase2a\evidence\phase2oq\outcome_baseline\.

TASKS.
A. Integrity: -e hash, manifest vs tree, frozen boundary, exact change set vs -d.
B. OQ-R4-1: repeat your real-pytest collision and attack `junit_records`, `junit_integrity`, `outcome_identity` and the
   phase1-full gate again (duplicates, count mismatches, missing/added/swapped tests, malformed XML). Is the stored baseline
   run itself verified at every gate?
C. Is chain8 a single green full chain on the -e tree? OQ-R1-1..3, OQ-R2-1, OQ-R3-1, OQ-R3-2 and round-1 B-K still hold?
D. Is the candidate ready for the owner's physical acceptance (PA gates and owner decisions remain open by design)?
E. New defects.
F. EXACTLY ONE final verdict:
   PHASE 2 OPERATIONAL CANDIDATE REJECTED
   PHASE 2 OPERATIONAL CANDIDATE ACCEPTED — READY FOR OWNER PHYSICAL ACCEPTANCE
   PHASE 2 ACCEPTED AND QUALIFIED

OUTPUT. Full report to C:\Users\cheta\.codex\worktrees\uri-phase2a\evidence\phase2oq_review\round5\CODEX_REVIEW_OQ_round5.md
with sections A-F, a DEFECTS table, a disposition table for OQ-R1-1..4, OQ-R2-1, OQ-R3-1, OQ-R3-2, OQ-R4-1, NOT VERIFIED, FINAL VERDICT. Print the FINAL
VERDICT line and both tables as your last message.
