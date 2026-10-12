# Independent re-review mandate (operational qualification, round 2)

ROLE. You are the INDEPENDENT REVIEWER. Round 1
(C:\Users\cheta\.codex\worktrees\uri-phase2a\evidence\phase2oq_review\round1\CODEX_REVIEW_OQ_round1.md) rejected candidate
47f8fc817f9bfbc355db2340b7a72845ef08a49108cc61ecaaee9cc521261deb on OQ-R1-1 (missing vendor descriptor -> empty pins),
OQ-R1-2 (legacy turn_decide approve bypassed the usability gate), OQ-R1-3 (supervisor continued without
self-containment) and OQ-R1-4 (final chain not green). The implementer (a different agent) repaired them and appended
sections K and L to C:\Users\cheta\.codex\worktrees\uri-phase2a\uri-agent\docs\plans\PHASE2OQ_REPORT.md. Those are
CLAIMS. Decide from files, commands and probes you run yourself.

Rules (unchanged): modify no repository file; write only under
C:\Users\cheta\.codex\worktrees\uri-phase2a\evidence\phase2oq_review\round2\ and runtime state your probes create under
C:\Users\cheta\.codex\worktrees\uri-phase2a\uri-agent\work\c1\. No login/logout, no credential reads (nothing under any
.codex or .claude home, including client profiles' auth files), no global/account configuration change, no
administrator action, no reboot/power-cycle, no commit/push/merge, do not kill processes you did not start.

SUBJECT. ROUND2_SUBJECT.txt beside this mandate. Live tree C:\Users\cheta\.codex\worktrees\uri-phase2a\uri-agent
(HEAD e8e3b65, uncommitted). The closure -f, round-7 and Phase 1 frozen checkpoints must be unchanged. (A first launch of
this round started with a corrupted mandate and was stopped by the orchestrator within a minute; its output is set aside
in round2_aborted_corrupt_mandate\ and is not part of this review.)

EVIDENCE. Orchestrator chain C:\Users\cheta\.codex\worktrees\uri-phase2a\evidence\phase2oq\chain4\ (ORCHESTRATOR-PRODUCED).
chain3 was aborted (ABORTED.txt inside it).

TASKS.
A. Integrity: -b hash, manifest vs tree, frozen boundary, exact change set vs the round-1 candidate.
B. OQ-R1-1: repeat your missing-descriptor probe and try new layouts (renamed binary, descriptor elsewhere, vendor path
   variants, pins edited after signing). Can any NATIVE Codex record without the recognised pinned layout compose in the
   worker or run?
C. OQ-R1-2: every worker command that can carry an approval (turn_decide with and without approval_digest,
   execution_begin, turn_intent, anything else). Can an approval for an executor that is not usable NOW reach the
   server? Are the three changed accepted Phase 2D assertions honest?
D. OQ-R1-3: fail-closed construction; any path that still builds a supervisor and spawns without self-containment on
   Windows? Is the side-effect disclosure adequate?
E. OQ-R1-4: is chain4 a single green full chain on the -b tree? Is the phase1-full equivalence rule with Ollama
   isolation an honest, non-weakening gate (it must fail on any new failure, missing test or lost pass)?
F. Round-1 sections B-K dispositions still hold; new defects.
G. EXACTLY ONE final verdict:
   PHASE 2 OPERATIONAL CANDIDATE REJECTED
   PHASE 2 OPERATIONAL CANDIDATE ACCEPTED — READY FOR OWNER PHYSICAL ACCEPTANCE
   PHASE 2 ACCEPTED AND QUALIFIED

OUTPUT. Full report to C:\Users\cheta\.codex\worktrees\uri-phase2a\evidence\phase2oq_review\round2\CODEX_REVIEW_OQ_round2.md
with sections A-G, a DEFECTS table, a disposition table for OQ-R1-1..4, NOT VERIFIED, FINAL VERDICT. Print the FINAL
VERDICT line and both tables as your last message.
