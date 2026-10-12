# Independent review mandate (closure round 1): URI Phase 2 closure candidate

ROLE. You are the INDEPENDENT REVIEWER. The implementer (Claude, a different agent) started from the Phase 2
UI/operations candidate you accepted in round 7 (`phase2ops-candidate-20261008-r6.zip`, SHA-256
9a0be52c1ae5e59bf9ae16617e283c5a9f58ba098a1c2ae1d9649e184affb50a, verdict "UI/OPERATIONS SLICE ACCEPTED — MORE PHASE 2
WORK REMAINS") and made closure changes. Its report `<tree>\docs\plans\PHASE2CLOSE_REPORT.md` and every implementer
document are CLAIMS. Decide from files, commands and probes you run yourself.

Rules: do not modify any source, test, document or configuration file in the repository. Write only under
C:\Users\cheta\.codex\worktrees\uri-phase2a\evidence\phase2close_review\round1\ and runtime state your own probes create
under <tree>\work\c1\. Do not log in/out, read credential files (nothing under any `.codex` or `.claude` home), change
global or account configuration, reboot or power-cycle, run `codex login`, or commit/push/merge.

SUBJECT. Candidate path and expected SHA-256 in ROUND1_SUBJECT.txt next to this mandate (sidecar .json beside the zip).
Live tree C:\Users\cheta\.codex\worktrees\uri-phase2a\uri-agent (HEAD e8e3b65, uncommitted). The round-7 candidate and
the Phase 1 frozen checkpoint (31a34dcbb37ee48e1b06a1bcd60418a2e52ff9a0c65fd8cc7f3c59defeb98cf7) must be unchanged; every
frozen checkpoint file byte-identical in the tree.

TEST-EXECUTION NOTE. Your sandbox has not been able to run pytest or Flutter on this machine. Orchestrator logs:
C:\Users\cheta\.codex\worktrees\uri-phase2a\evidence\phase2close\run4\ (chain_summary.json, phase2_all.log,
phase1_authority.log, phase1_full.log, flutter_all.log, ui_bridge_live_*.json, refusals.txt, native\) — ORCHESTRATOR-
PRODUCED claims. Check commands, scope, counts, failure IDs and outcomes. Reproduce what your sandbox allows and say
what you reproduced and what you only read. Aborted chains run1-run3 are kept with ABORTED.txt; they are not evidence.

CLAIMED CHANGES (verify each by diff against the round-7 candidate):
1. LOG-3: `uri_supervisor_bridge/refusal_log.py` retains at most 4096 bytes of an error body.
2. VAL-1: cause claimed = the frozen check `issued_at == int(clock())` in `uri_core/core/client_execution_control.py:77`
   crossing a wall-clock second after `paired_coordinator.py:303`, re-raised as 403 at `paired_coordinator.py:314-316`
   before any state change. Mitigation in `uri_supervisor_bridge/execution.py` (`_decide`, `_approval_provably_unapplied`):
   one resend of the same approval only when the server's status proves the turn unchanged; second refusal ->
   `failed/APPROVAL_REFUSED_NOT_APPLIED`. Tests `tests/phase2ops/test_val1_clock_boundary.py`.
3. CAP-1: worker releases abandoned approval_required turns via the frozen server cancel route
   (`worker_service.release_turn/release_pending`, `ExecutionController._release`, worker close/EOF). Three accepted
   test assertions changed (tests/phase2d/test_worker_service.py, tests/phase2d/test_worker_process.py,
   the round-7-accepted behaviour "dropped turn holds its session"). Tests `tests/phase2ops/test_capacity_release.py`,
   `test_worker_process.py::test_cap1_*`.
4. ISO-1: Codex ignores USERPROFILE; worker pins CODEX_HOME to `<client_root>/home/.codex`
   (`qualification.client_cli_homes`, `scripts/run_uri_supervised_worker.py`). Tests `tests/phase2close/test_iso1_cli_home.py`.
5. EXE-1 recorded as BLOCKED (owner decision), not repaired.
6. Inert conversation-to-task handoff `uri_ui/lib/services/task_handoff.dart` + `SupervisedExecutionScreen(draft:)`;
   Chat not wired (owner decision 2).
7. New scripts: phase2close_chain.py, phase2close_powerloss_harness.py, phase2close_acceptance.py,
   phase2close_checkpoint.py; docs PHASE2CLOSE_*, URI_DEVELOPMENT_TODO.md; ALLOWED_NEW and the regression scope
   extended.

TASKS.
A. Integrity: candidate hash, manifest vs tree, Phase 1 frozen boundary, exact change set vs round 7.
B. Attack each change 1-4: is the claimed root cause of VAL-1 correct and complete (other 403 paths?), can the resend
   ever approve something the user did not approve, run twice, or turn an applied approval into `failed`? Can the CAP-1
   release ever cancel a dispatched or approved turn, or hide an effect? Is the ISO-1 pin correct for every probe and
   executor path (auth probe, version probe, executor launch)? Is LOG-3 bounded for every body shape?
C. Were the three changed accepted-test assertions changed honestly (behaviour change disclosed, not a weakened gate)?
D. Power-loss harness and acceptance tooling: can any output be mistaken for a physical qualification? Does `qualify`
   fail closed without a client-profile login?
E. New defects (file:line; reproduced or not). Earlier round-7 dispositions still hold?
F. Is the closure report's verdict ("PHASE 2 TECHNICALLY READY — PHYSICAL/OWNER GATES PENDING" or whatever it states)
   supported? Are C7 readiness and the ledger free of overstatement?
G. EXACTLY ONE final verdict:
   PHASE 2 CLOSURE REJECTED
   PHASE 2 CLOSURE ACCEPTED — PHYSICAL/OWNER GATES PENDING
   PHASE 2 ACCEPTED AND QUALIFIED

OUTPUT. Full report to C:\Users\cheta\.codex\worktrees\uri-phase2a\evidence\phase2close_review\round1\CODEX_REVIEW_round1.md
with sections A-G, DEFECTS table, NOT VERIFIED, FINAL VERDICT. Print the FINAL VERDICT line and the DEFECTS table as
your last message.
