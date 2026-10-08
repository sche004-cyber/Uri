# Independent re-review mandate (closure round 2): URI Phase 2 closure, repaired candidate

ROLE. You are the INDEPENDENT REVIEWER. Round 1 (C:\Users\cheta\.codex\worktrees\uri-phase2a\evidence\phase2close_review\round1\CODEX_REVIEW_round1.md)
rejected candidate -a (8fc1d5e818dc99bb15511d7e29bb3786678cab85c69f6f8f17249329099e2470) on D1 (High: `qualify` inherited
shell provider tokens), D2 (High: power-loss host verdict could pass for a physical qualification), D3 (Medium: no
single green full chain), with K1 (Low, known: suspended orphan window) and a VAL-1 text overstatement. The implementer
(a different agent) changed code and documents and appended "Correction record 1" and "Record H2" to
<tree>\docs\plans\PHASE2CLOSE_REPORT.md. Those are CLAIMS. Decide from files, commands and probes you run yourself.

Rules (unchanged): do not modify any repository file; write only under
C:\Users\cheta\.codex\worktrees\uri-phase2a\evidence\phase2close_review\round2\ and runtime state your probes create under
<tree>\work\c1\. No login/logout, no credential file reads (nothing under any `.codex` or `.claude` home), no global or
account configuration change, no reboot/power-cycle, no `codex login`, no commit/push/merge.

SUBJECT. ROUND2_SUBJECT.txt next to this mandate. Live tree C:\Users\cheta\.codex\worktrees\uri-phase2a\uri-agent
(HEAD e8e3b65, uncommitted). Round-7 candidate 9a0be52c1ae5e59bf9ae16617e283c5a9f58ba098a1c2ae1d9649e184affb50a and the
Phase 1 frozen checkpoint 31a34dcbb37ee48e1b06a1bcd60418a2e52ff9a0c65fd8cc7f3c59defeb98cf7 must be unchanged.

EVIDENCE. Orchestrator chain C:\Users\cheta\.codex\worktrees\uri-phase2a\evidence\phase2close\run5\ (ORCHESTRATOR-PRODUCED;
check commands, counts, failure IDs, outcomes). Your sandbox previously could not run pytest fixtures (temp directory
access denied); reproduce what it allows and say what you reproduced versus read.

TASKS.
A. Integrity: -b hash, manifest vs tree, frozen boundary, exact change set vs -a (expected: acceptance/harness scripts,
   their tests, the regression scope unchanged, documents).
B. D1: attack `probe_environment` and `qualify` (`scripts/phase2close_acceptance.py`): can any credential still reach the
   probe or the auth-status check (other variable names, case variants, the CODEX_HOME value, inherited handles), can the
   caller's environment be left modified, can a record still be persisted without a client-profile login?
C. D2: attack `scripts/phase2close_powerloss_harness.py` (`campaign`, `host`, `assess`, `iteration_verdict`): can any
   output still read as a physical qualification; can `assess` accept a weak or mislabeled series; are the runbook
   instructions consistent with the code?
D. D3: is run5 a single green full chain on the -b tree?
E. K1 and the VAL-1 correction: is the recording honest and the severity right?
F. New defects; round-1 confirmations (LOG-3, VAL-1 resend, CAP-1, ISO-1, changed accepted tests) still hold?
G. Is "PHASE 2 TECHNICALLY READY — PHYSICAL/OWNER GATES PENDING" supported, with C7 NOT READY and the physical/owner
   gates pending?
H. EXACTLY ONE final verdict:
   PHASE 2 CLOSURE REJECTED
   PHASE 2 CLOSURE ACCEPTED — PHYSICAL/OWNER GATES PENDING
   PHASE 2 ACCEPTED AND QUALIFIED

OUTPUT. Full report to C:\Users\cheta\.codex\worktrees\uri-phase2a\evidence\phase2close_review\round2\CODEX_REVIEW_round2.md
with sections A-H, DEFECTS table, disposition table for every round-1 finding, NOT VERIFIED, FINAL VERDICT. Print the
FINAL VERDICT line and both tables as your last message.
