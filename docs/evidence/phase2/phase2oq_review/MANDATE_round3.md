# Independent re-review mandate (operational qualification, round 3)

ROLE. You are the INDEPENDENT REVIEWER. Round 2 (C:\Users\cheta\.codex\worktrees\uri-phase2a\evidence\phase2oq_review\round2\CODEX_REVIEW_OQ_round2.md)
rejected candidate -b (5d5e111bf2377a6a09eb2a7d81c4d02fb11da710a4fe0a3e6aa2577aa55c5706) on OQ-R2-1 (the phase1-full
equivalence gate could pass with a missing test or lost pass offset by another test) and found OQ-R1-1..3 repaired.
The implementer (a different agent) changed scripts/phase2close_chain.py (per-test rule, collection baseline,
phase1-scope gate), added tests/phase2oq/test_chain_equivalence.py and appended section M to
C:\Users\cheta\.codex\worktrees\uri-phase2a\uri-agent\docs\plans\PHASE2OQ_REPORT.md. Those are CLAIMS.
Decide from files, commands and probes you run yourself.

Rules (unchanged): modify no repository file; write only under
C:\Users\cheta\.codex\worktrees\uri-phase2a\evidence\phase2oq_review\round3\ and runtime state your probes create under
C:\Users\cheta\.codex\worktrees\uri-phase2a\uri-agent\work\c1\. No login/logout, no credential reads (nothing under any
.codex or .claude home, including client profiles' auth files), no global/account configuration change, no
administrator action, no reboot/power-cycle, no commit/push/merge, do not kill processes you did not start.

SUBJECT. ROUND3_SUBJECT.txt beside this mandate. Live tree C:\Users\cheta\.codex\worktrees\uri-phase2a\uri-agent
(HEAD e8e3b65, uncommitted). The closure -f, round-7 and Phase 1 frozen checkpoints must be unchanged.

EVIDENCE. Orchestrator chain C:\Users\cheta\.codex\worktrees\uri-phase2a\evidence\phase2oq\chain6\ (ORCHESTRATOR-PRODUCED).
chain5 was aborted (ABORTED.txt inside it).

TASKS.
A. Integrity: -c hash, manifest vs tree, frozen boundary, exact change set vs -b.
B. OQ-R2-1: attack `phase1_equivalence`, `phase1_collection`, `skip_multiset`, `passed_ids`, `failed_ids` and
   `phase1_scope_check` in scripts/phase2close_chain.py. Can any missing test, added test, lost pass, new failure or new
   skip pass the gate? Is the collection baseline (evidence\phase2oq\phase1_collection_baseline.txt) trustworthy as a
   stand-in for the accepted baseline, given how it may be written? Are the adversarial tests meaningful?
C. Is chain6 a single green full chain on the -c tree?
D. OQ-R1-1..3 still repaired; round-1 B-K dispositions still hold.
E. New defects.
F. EXACTLY ONE final verdict:
   PHASE 2 OPERATIONAL CANDIDATE REJECTED
   PHASE 2 OPERATIONAL CANDIDATE ACCEPTED — READY FOR OWNER PHYSICAL ACCEPTANCE
   PHASE 2 ACCEPTED AND QUALIFIED

OUTPUT. Full report to C:\Users\cheta\.codex\worktrees\uri-phase2a\evidence\phase2oq_review\round3\CODEX_REVIEW_OQ_round3.md
with sections A-F, a DEFECTS table, a disposition table for OQ-R1-1..4 and OQ-R2-1, NOT VERIFIED, FINAL VERDICT. Print the FINAL
VERDICT line and both tables as your last message.
