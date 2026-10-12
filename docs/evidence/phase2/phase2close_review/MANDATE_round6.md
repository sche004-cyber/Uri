# Independent re-review mandate (closure round 6): URI Phase 2 closure, repaired candidate

ROLE. You are the INDEPENDENT REVIEWER. Round 5 (C:\Users\cheta\.codex\worktrees\uri-phase2a\evidence\phase2close_review\round5\CODEX_REVIEW_round5.md)
rejected candidate -e (14362501a8bf6f9e3c788107daa562ca16502f838c0d43dfab7c5a6113c5e32b) on D7 (Medium: a self-consistent FULL record whose requested count
was not what ran, verdict SERIES_FAIL, was assessed sufficient) and a Low power-method limitation (arbitrary commands
accepted), with every earlier finding closed or recorded (K1). The implementer (a different agent) changed the harness,
its tests and documents, and appended "Correction record 5" and "Record H6" to <tree>\docs\plans\PHASE2CLOSE_REPORT.md.
Those are CLAIMS. Decide from files, commands and probes you run yourself.

Rules (unchanged): do not modify any repository file; write only under
C:\Users\cheta\.codex\worktrees\uri-phase2a\evidence\phase2close_review\round6\ and runtime state your probes create under
<tree>\work\c1\. No login/logout, no credential file reads (nothing under any `.codex` or `.claude` home), no global or
account configuration change, no reboot/power-cycle, no `codex login`, no commit/push/merge.

SUBJECT. ROUND6_SUBJECT.txt next to this mandate. Live tree C:\Users\cheta\.codex\worktrees\uri-phase2a\uri-agent
(HEAD e8e3b65, uncommitted). Round-7 candidate 9a0be52c1ae5e59bf9ae16617e283c5a9f58ba098a1c2ae1d9649e184affb50a and the
Phase 1 frozen checkpoint 31a34dcbb37ee48e1b06a1bcd60418a2e52ff9a0c65fd8cc7f3c59defeb98cf7 must be unchanged.

EVIDENCE. Orchestrator chain C:\Users\cheta\.codex\worktrees\uri-phase2a\evidence\phase2close\run9\ (ORCHESTRATOR-PRODUCED;
check commands, counts, failure IDs, outcomes). Reproduce what your sandbox allows and say what you reproduced versus read.

TASKS.
A. Integrity: -f hash, manifest vs tree, frozen boundary, exact change set vs -e (expected: the power-loss harness, its
   test file, documents).
B. D4: attack `assess` / `assess_series` / `replay_series` in `scripts/phase2close_powerloss_harness.py`: can any
   incoherent, truncated, mislabeled, tampered or weak pair of series directories still yield
   EVIDENCE_SUFFICIENT_PENDING_OWNER_ATTESTATION? Is the replay faithful to what `campaign` records? Repeat your round-2..round-5
   probes and try new ones.
C. D5, D6, the power-method rule and the runbook/checklist: consistent with the code?
D. Is run9 a single green full chain on the -f tree?
E. Round-1..5 dispositions still hold (D1, D2, D3, K1, VAL-1 text, LOG-3, VAL-1 resend, CAP-1, ISO-1, changed accepted tests)?
F. New defects.
G. Is "PHASE 2 TECHNICALLY READY — PHYSICAL/OWNER GATES PENDING" supported, with C7 NOT READY and physical/owner gates pending?
H. EXACTLY ONE final verdict:
   PHASE 2 CLOSURE REJECTED
   PHASE 2 CLOSURE ACCEPTED — PHYSICAL/OWNER GATES PENDING
   PHASE 2 ACCEPTED AND QUALIFIED

OUTPUT. Full report to C:\Users\cheta\.codex\worktrees\uri-phase2a\evidence\phase2close_review\round6\CODEX_REVIEW_round6.md
with sections A-H, DEFECTS table, disposition table for every round-1..5 finding, NOT VERIFIED, FINAL VERDICT.
Print the FINAL VERDICT line and both tables as your last message.
