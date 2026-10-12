# Independent review mandate (operational qualification, round 1): URI Phase 2 operational-qualification candidate

ROLE. You are the INDEPENDENT REVIEWER. The Phase 2 closure was accepted in closure round 6
(C:\Users\cheta\.codex\worktrees\uri-phase2a\evidence\phase2close_review\round6\CODEX_REVIEW_round6.md) on candidate -f
(fcd0d72e0cd91412c361edec9114e2edaebbf70ede052046b808f3c4fc571298). A different agent (the implementer) then did the
"operational qualification" slice and wrote <tree>\docs\plans\PHASE2OQ_REPORT.md and related documents. Everything in
those documents is a CLAIM. Decide from files, commands and probes you run yourself.

Rules: do not modify any repository file; write only under
C:\Users\cheta\.codex\worktrees\uri-phase2a\evidence\phase2oq_review\round1\ and runtime state your probes create under
<tree>\work\c1\. No login/logout, no `codex login`, no credential file reads (nothing under any `.codex` or `.claude`
home, including a client profile's Codex home `auth*` files), no global or account configuration change, no
administrator action, no reboot/power-cycle, no commit/push/merge. Do NOT kill processes you did not start.

SUBJECT. ROUND1_SUBJECT.txt next to this mandate (candidate zip + SHA-256). Live tree
C:\Users\cheta\.codex\worktrees\uri-phase2a\uri-agent (HEAD e8e3b65, uncommitted). The closure candidate -f, the round-7
candidate 9a0be52c1ae5e59bf9ae16617e283c5a9f58ba098a1c2ae1d9649e184affb50a and the Phase 1 frozen checkpoint
31a34dcbb37ee48e1b06a1bcd60418a2e52ff9a0c65fd8cc7f3c59defeb98cf7 must be unchanged.

EVIDENCE. Orchestrator chain C:\Users\cheta\.codex\worktrees\uri-phase2a\evidence\phase2oq\chain2\ (ORCHESTRATOR-PRODUCED;
check commands, counts, failure IDs, outcomes), probes in evidence\phase2oq\ (sandbox_probes, native_try2,
sup1_orphan_observed_20261008.json). Reproduce what your sandbox allows; say what you reproduced versus read.

TASKS.
A. Integrity: candidate hash, manifest vs tree, frozen boundary, the exact change set vs -f (list it).
B. EXE-1 (owner approved resolving it inside existing authority): does qualifying the npm-vendored NATIVE codex.exe
   (`qualification.codex_native_launch_chain`, `native_executable`) keep executable identity verified, add no
   interpreter, no PATH widening, no name resolution, no arbitrary executable authority? Can a modified/replaced vendor
   file, an unknown layout, a `.cmd` record, or a swapped binary still compose or run? Attack it.
C. CODEX_HOME / ISO-1: `check_codex_client_home` (worker composition and every execution via `still_valid`). Can a
   worker composition or a later execution run Codex with CODEX_HOME absent, pointing elsewhere, or changed after
   composition? Is the in-process (non-worker) path's lack of the check acceptable as stated?
D. EXE-1b: the claim that `unelevated` confines writes but not network, and that the backend choice is the owner's.
   Is the fail-closed refusal (`CODEX_WINDOWS_SANDBOX_NOT_CONFIGURED`) correct and is nothing defaulting a backend?
E. OQ-1: `execution_begin` refuses `HARNESS_NOT_USABLE` before the approval reaches the server and releases the turn.
   Any path where an approval for an unusable executor still reaches the server or runs? Is the changed accepted
   assertion (tests/phase2ops/test_lifecycle.py) honest?
F. SUP-1: `winproc.contain_current_process` + `Supervisor.__init__`. Does it close the suspended-orphan window without
   weakening containment, recovery or identity, and without new authority? Side effects on the hosting process
   (pytest, worker, guest) acceptable?
G. D8: `unclean_shutdown_witnessed` / `assess_series`. Can a VM series without a real unclean shutdown per iteration
   still be sufficient? Is `qualified` still always false with attestation required?
H. C6 Option B (owner accepted): does the Chat action ever send, approve, choose an executor, or put one request into two
   approval paths? Abandonment, restart, stale run, too-long message, return navigation.
I. Acceptance tooling: `login-guide` never runs or reads credentials; `status` keeps installed / authenticated /
   qualified / operational apart; `provision --codex-sandbox` never defaults; the guest bundle and its installer guard.
J. Is chain2 a single green full chain on the candidate tree? Do LOG-3, VAL-1 resend, CAP-1, ISO-1 and every closure
   round-1..6 disposition still hold?
K. Are the shipping-line recommendation and the UI/voice plan supported by the evidence they cite (no simulated or
   widget evidence presented as device evidence)?
L. New defects.
M. EXACTLY ONE final verdict:
   PHASE 2 OPERATIONAL CANDIDATE REJECTED
   PHASE 2 OPERATIONAL CANDIDATE ACCEPTED — READY FOR OWNER PHYSICAL ACCEPTANCE
   PHASE 2 ACCEPTED AND QUALIFIED

OUTPUT. Full report to C:\Users\cheta\.codex\worktrees\uri-phase2a\evidence\phase2oq_review\round1\CODEX_REVIEW_OQ_round1.md
with sections A-M, a DEFECTS table (ID, severity, finding, evidence), NOT VERIFIED, FINAL VERDICT. Print the FINAL
VERDICT line and the DEFECTS table as your last message.
