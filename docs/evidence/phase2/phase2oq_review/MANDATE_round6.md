# Independent re-review mandate (operational qualification, round 6)

ROLE. You are the INDEPENDENT REVIEWER. Round 5 (C:\Users\cheta\.codex\worktrees\uri-phase2a\evidence\phase2oq_review\round5\CODEX_REVIEW_OQ_round5.md)
rejected candidate -e (a914d086eda82b3d4e6fd45d7430a08099354a4cb3c2d4e512fc10743552ea3f) on OQ-R5-1 (XML vs summary counts
compared only in total) and OQ-R5-2 (baseline JSON map not rebound to its XML at each gate); OQ-R4-1 repaired. The
implementer (a different agent) changed `junit_integrity` and the phase1-full gate, added tests, and appended section P
and Record H6 to C:\Users\cheta\.codex\worktrees\uri-phase2a\uri-agent\docs\plans\PHASE2OQ_REPORT.md.
Those are CLAIMS. Decide from files, commands and probes you run yourself.

Rules (unchanged): modify no repository file; write only under
C:\Users\cheta\.codex\worktrees\uri-phase2a\evidence\phase2oq_review\round6\ and runtime state your probes create under
C:\Users\cheta\.codex\worktrees\uri-phase2a\uri-agent\work\c1\. No login/logout, no credential reads (nothing under any
.codex or .claude home, including client profiles' auth files), no global/account configuration change, no
administrator action, no reboot/power-cycle, no commit/push/merge, do not kill processes you did not start.

SUBJECT. ROUND6_SUBJECT.txt beside this mandate. Live tree C:\Users\cheta\.codex\worktrees\uri-phase2a\uri-agent
(HEAD e8e3b65, uncommitted). The closure -f, round-7 and Phase 1 frozen checkpoints must be unchanged.

EVIDENCE. Orchestrator chain C:\Users\cheta\.codex\worktrees\uri-phase2a\evidence\phase2oq\chain9\ (ORCHESTRATOR-PRODUCED). Outcome baseline run: C:\Users\cheta\.codex\worktrees\uri-phase2a\evidence\phase2oq\outcome_baseline\.

TASKS.
A. Integrity: -f hash, manifest vs tree, frozen boundary, exact change set vs -e.
B. OQ-R5-1/OQ-R5-2: repeat your probes; attack the Phase 1 gate as a whole once more (`junit_records`, `junit_integrity`,
   `outcome_identity`, baseline binding, `phase1_scope_check`, `runner_argv`). Any remaining way for a missing, added,
   lost-pass, swapped, newly failing or newly skipped test, or an altered baseline, to pass?
C. Is chain9 a single green full chain on the -f tree? Every earlier OQ finding and round-1 B-K disposition still holds?
D. Is the candidate ready for the owner's physical acceptance (PA gates and owner decisions remain open by design)?
E. New defects.
F. EXACTLY ONE final verdict:
   PHASE 2 OPERATIONAL CANDIDATE REJECTED
   PHASE 2 OPERATIONAL CANDIDATE ACCEPTED — READY FOR OWNER PHYSICAL ACCEPTANCE
   PHASE 2 ACCEPTED AND QUALIFIED

OUTPUT. Full report to C:\Users\cheta\.codex\worktrees\uri-phase2a\evidence\phase2oq_review\round6\CODEX_REVIEW_OQ_round6.md
with sections A-F, a DEFECTS table, a disposition table for OQ-R1-1..4, OQ-R2-1, OQ-R3-1, OQ-R3-2, OQ-R4-1, OQ-R5-1, OQ-R5-2, NOT VERIFIED, FINAL VERDICT. Print the FINAL
VERDICT line and both tables as your last message.
