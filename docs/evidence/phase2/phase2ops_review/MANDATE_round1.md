# Independent review mandate (round 1): URI Phase 2 UI/operations slice candidate

ROLE. You are the INDEPENDENT REVIEWER of a bounded implementation slice. The implementer (a different agent, working
while the owner is away for weeks) built it on the Phase 2D candidate you accepted in round 3
(C:\Users\cheta\.codex\worktrees\uri-phase2a\evidence\phase2d_review\round3\CODEX_REVIEW_round3.md, verdict
"PHASE 2D ACCEPTED — MORE PHASE 2 SLICES REMAIN"). Every implementer document, report, log and test is a CLAIM. Decide
from files, commands and probes you run yourself. Do not accept a claim because it is well written.

Rules: do not modify any source, test, document or configuration file in the repository. Write only under
C:\Users\cheta\.codex\worktrees\uri-phase2a\evidence\phase2ops_review\round1\ and runtime state your own probes create
under <tree>\work\c1\. Do not log in/out, read credential files, change global or account configuration, reboot or
power-cycle, run `codex login`, or commit/push/merge. Do not tell the implementer what to build; report defects.

SUBJECT. Candidate zip and expected SHA-256 in ROUND1_SUBJECT.txt next to this mandate (sidecar .json beside the zip).
Live tree C:\Users\cheta\.codex\worktrees\uri-phase2a\uri-agent (HEAD e8e3b65, uncommitted). Earlier candidates must be
unchanged: phase2d-candidate-20261007-r2.zip cbec537adffcd629d5b7aec907e50c8eeea6f83d8edf52e05b658deb0968688d
(and r1 0fa06ac34e2eb30141259d02c764c8dad24a8352c2e7c2c36b28c15484230240, original
6c7cb4f87d82d45c97bdea2bf16c439f9ffe327dfa5591417af15d055d3c6785). Phase 1 frozen checkpoint (path in
tests/phase2a/test_frozen_core.py) 31a34dcbb37ee48e1b06a1bcd60418a2e52ff9a0c65fd8cc7f3c59defeb98cf7: every
checkpoint file must be byte-identical in the live tree. Note that uri_ui/lib/app.dart (NOT in the checkpoint) was
modified; uri_ui/lib/services/paired_runtime.dart, uri_ui/lib/screens/settings/paired_runtime_screen.dart and
uri_ui/lib/screens/settings/settings_shell.dart ARE in the checkpoint and must be unchanged.

IMPLEMENTER DOCUMENTS (claims): <tree>\docs\architecture\PHASE2OPS_UI_OPERATIONS.md, <tree>\docs\plans\PHASE2OPS_REPORT.md,
superseding notes in <tree>\docs\architecture\PHASE2D_COMPOSITION.md. Governing documents: the Phase 2A-2D architecture
notes and reports, docs/plans/C6_UI_INTEGRATION_CONTRACT.md, docs/plans/C7_CUTOVER_REQUIREMENTS.md, and your own
round-3 section D (plan reconstruction, UI truth table, cancellation, power loss, remaining slices).

TEST-EXECUTION NOTE. In rounds 1-3 your sandbox could not run pytest (WinError 5 temp dirs; icacls) and cannot run
Flutter. The orchestrator ran the suites outside the sandbox: C:\Users\cheta\.codex\worktrees\uri-phase2a\evidence\phase2ops\
(phase2_all_final.log, phase1_authority_final.log, phase1_full.log, flutter_all_final.log, ui_bridge_live.json,
codex_cli_lifecycle_*.json, claude_code_lifecycle_*.json). ORCHESTRATOR-PRODUCED claims: check their commands, scope,
counts and failure IDs; reproduce what your sandbox allows (direct-import probes of uri_supervisor_bridge.execution
worked for you before; read-only sqlite on the preserved work/c1 ledgers is possible). Say what you reproduced and what
you only read. The real-Codex evidence ran under the shell's run-scoped auth (same posture as 2C/2D); you must NOT log in.

TASKS.
A. Integrity: candidate hash, sidecar, MANIFEST.json vs live tree, earlier candidates unchanged, Phase 1 frozen boundary
   (byte identity AND tests/phase2a/test_frozen_core.py ALLOWED_NEW: is uri_ui/lib/app.dart a legitimate exception?).
B. Attack the implementation (cite file:line, give the failure scenario, say whether you reproduced it):
   1. approval binding: execution_proposal / proposal_digest (uri_supervisor_bridge/execution.py) — can a UI approve
      something other than what it displayed? change provider/model/arguments/turn/session after the card? reuse a digest?
      is typed text ever an approval? is the frozen turn_decide path weakened?
   2. lifecycle truth: can `completed` arise from anything but SETTLED_VERIFIED? what do exceptions, unmapped codes,
      server loss at approval/claim/settle, record corruption produce? are timestamps/phases honest?
   3. mid-run cancellation: before approval, between approval and dispatch, while running, after terminal, during close
      and stdin EOF; races between cancel and the execution thread; does the harness and its descendants die (job)?
      is anything re-admitted or retried after a cancel? is `cancelled` ever reported when something ran?
   4. reconnect/restart: durable register under control/supervisor/executions/, reconcile_restart, frozen journal
      recover() call at worker start (is calling it correct? side effects?), worker crash mid-run, server restart,
      stale UI, duplicate/replay, two workers; can UI-local state ever override Core/supervisor state?
   5. authority: did any authority move to the worker thread, the register, or the UI? EXECUTION_IN_PROGRESS gating of
      snapshot/consent/commit/turn_*; thread-safety of the shared runner/transport/persistence; the three runner hooks.
   6. receipt/status: what is exposed (secrets? tickets? tokens?); is `server_turn` honest when unreachable?
   7. Flutter: uri_ui/lib/services/supervised_runtime.dart (opt-in file, spawn, profile check, never
      --allow-fixture-qualification from fromManifest), uri_ui/lib/screens/tasks/supervised_execution_screen.dart (card
      contents, executor lock while pending, cancel, polling, reconnect, uncertain wording, no fallback), app.dart entry.
      Is this "the actual URI Flutter UI wired", an opt-in, or a parallel mechanism? Is Chat (/ask) wiring required?
   8. Phase 2D preservation: signed client-bound records, expiry, evidence re-hash/content, launch-chain pins, per-run
      revalidation, native record = probed model; the R3-1/R3-2 repair (qualification.py _check_evidence) and its tests;
      any regression in tests/phase2d or the frozen Phase 1 suites.
   9. the fake-harness in-band scenario marker (tests/phase2b/helpers/fake_harness.py "(fake scenario: X)"): test-only?
      could instruction text ever steer a REAL executor's behaviour through URI code?
C. New defects introduced by this slice (anything not covered above).
D. Determinations, each with citations: (1) is the UI/operations connection now IMPLEMENTED / TESTED / what remains
   USER-PHYSICAL (human click, native login in the client profile, physical power loss, cutover)? (2) the UI wiring
   truth table (a) protocol (b) programmatic composition (c) opt-in profiles (d) real Flutter UI driving the supervised
   worker (e) cutover — YES/NO/PARTIAL with evidence; (3) remaining Phase 2 slices from the governing documents (is the
   Context Capsule / Task Compiler next? anything else required before a Phase 2 freeze?); (4) the research/implementation
   ledger (Strata, Paperclip, AG-UI/A2UI, MCP broker, Context Capsule, Task Compiler, model residency, supervisor
   scheduling/recovery, physical power loss): does any entry overstate its status?
E. EXACTLY ONE final verdict:
   UI/OPERATIONS SLICE REJECTED
   UI/OPERATIONS SLICE ACCEPTED — MORE PHASE 2 WORK REMAINS
   PHASE 2 IMPLEMENTATION COMPLETE — USER QUALIFICATION REMAINS
   READY TO FREEZE

OUTPUT. Full report to C:\Users\cheta\.codex\worktrees\uri-phase2a\evidence\phase2ops_review\round1\CODEX_REVIEW_round1.md
with sections A-E, a DEFECTS table (id, severity, file:line, failure scenario, evidence/reproduced?, blocks verdict?),
NOT VERIFIED, FINAL VERDICT. Print the FINAL VERDICT line and the DEFECTS table as your last message.
