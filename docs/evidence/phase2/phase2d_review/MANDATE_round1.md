# Independent review mandate: URI Phase 2D closure candidate

ROLE. You are the INDEPENDENT REVIEWER. The implementer (a different agent) produced the candidate below. Its reports and
docstrings are CLAIMS to verify, not evidence. Base every conclusion on files you read, commands you run, and test results
you observe yourself. Do not modify any source, test, document or configuration file in the repository. You may write only:
(a) your report and scratch files under C:\Users\cheta\.codex\worktrees\uri-phase2a\evidence\phase2d_review\, and
(b) runtime state the test suites create themselves (git-ignored work/c1/*, temp dirs). Do not log in or out of anything,
do not read credential files, do not change any global or account configuration, do not reboot or power-cycle the machine,
do not commit/push/merge.

SUBJECT.
- Candidate zip: C:\Users\cheta\.codex\worktrees\uri-phase2a\evidence\phase2d-candidate-20261007.zip
  Expected SHA-256 6c7cb4f87d82d45c97bdea2bf16c439f9ffe327dfa5591417af15d055d3c6785 (sidecar phase2d-candidate-20261007.json).
- Live tree the candidate was cut from: C:\Users\cheta\.codex\worktrees\uri-phase2a\uri-agent (git HEAD should be e8e3b65,
  all Phase 2 work uncommitted). Check that the zip's MANIFEST.json entries match the live tree files byte for byte.
- Previous Phase 2C candidate: ...\evidence\phase2c-candidate-20261007.zip, SHA-256 4e8126539da1f0ede3989f6d307253b5b4267be4fe1ce4ae405d19e761840f71.
- Phase 1 frozen checkpoint: C:\Users\cheta\.codex\worktrees\uri-phase1-integration\uri-agent\work\c1\checkpoints\final-closure-20261005-phase1.zip,
  SHA-256 31a34dcbb37ee48e1b06a1bcd60418a2e52ff9a0c65fd8cc7f3c59defeb98cf7.
- Python for tests: <tree>\.venv\Scripts\python.exe, always with -I.
- Evidence directories: ...\evidence\phase2c\ and ...\evidence\phase2d\ (run records, logs). Treat them as claims too:
  recompute what you can (hashes, ledger contents referenced, argv hashes) rather than trusting summaries.

TASKS (answer every item; mark anything you could not verify as NOT VERIFIED with the reason).

1. Verify the candidate SHA-256 and the MANIFEST against the live tree.
2. Verify Phase 1 frozen boundaries: every file in the Phase 1 checkpoint zip is byte-identical in the tree; nothing outside the
   checkpoint and the Phase 2 paths changed relative to e8e3b65; frozen entrypoints/launchers/UI unchanged in behaviour.
3. Reconstruct the actual Phase 2 plan from repository documents yourself (search docs/, root *.md, docs/governance, docs/plans,
   docs/architecture, Phase 1 closure/cutover documents, URI_MILESTONE_TRACKER.md, PROJECT_MEMORY.md, ARCHITECTURE.md and
   anything else you find relevant). Do not rely on the implementer's summary of the plan. Cite the documents you used.
4. Review the Phase 2D implementation (uri_supervisor_bridge/qualification.py, composition.py, worker_service.py, the edits to
   uri_supervisor/supervisor.py and uri_supervisor_bridge/bridge.py, scripts/run_uri_supervised_worker.py,
   scripts/run_uri_phase2_server.py, scripts/phase2d_*, tests/phase2d/) in the context of 2A/2B/2C. Attack, and report findings
   with file:line and a concrete failure scenario for each: qualification persistence; provider/model/executable binding;
   authentication boundary; forged/stale authority; approval digest; permission expansion; replay; cancellation; retry; duplicate
   execution; duplicate external side effects; crash/recovery; stale and cross-task sessions; copying a qualification record to
   another client/provider/model; binary or launcher-shim replacement. Write and run your own probe scripts (under the review
   dir) where reading is not enough.
5. F-C1: decide independently whether URI's governed resumable Codex-session design is correct, or whether `--ephemeral` (no
   Codex-side session persistence) is actually required by URI's governing rules. Give the reasoning and the documents relied on.
6. The implementer's documents describe UI wiring in several places. Report separately, each as YES / NO / PARTIAL with evidence:
   (a) worker protocol implemented; (b) composition path tested end to end; (c) opt-in Phase 2 launcher/profile implemented;
   (d) the actual URI Flutter UI wired to the supervised worker; (e) production cutover performed. Identify any contradictions
   between the implementer's statements.
7. Decide whether mid-run cancellation over the worker protocol is required before Phase 2 can be frozen, based on the
   governing documents.
8. Inspect the abrupt-termination tests and docs/plans/PHASE2A_POWER_LOSS_TEST_PLAN.md; decide whether physical power-loss
   qualification is genuinely a Phase 2 freeze blocker under the governing documents. Do not reboot or power-cycle anything.
9. Re-run tests yourself. Use a scope that never recursively collects work/, evidence/, rollback copies, checkpoints or other
   worktrees (scripts/phase2d_pytest.ini and scripts/phase2d_regression.py exist; inspect them before trusting them, or build
   your own explicit command). At minimum: tests/phase2d, all Phase 2 suites (tests/phase2a..2d), the Phase 1 authority suites.
   Run the full Phase 1 repository suite (Phase 2 suites excluded) if time allows; the canonical Phase 1 baseline is 2698
   collected, 2675 passed, 12 skipped, 11 known failures (IDs in docs/plans/PHASE1_FINAL_CLOSURE_REPORT.md). Compare failures
   by ID. Some tests need Windows facilities (DPAPI, icacls, named mutexes, job objects, subprocesses); if your sandbox blocks
   them, report that as an environment limitation with the exact error rather than as a product result.
10. MOST IMPORTANT: determine from the governing documents whether Phase 2D is actually the last Phase 2 implementation slice.
    In particular determine whether the governing architecture still requires, as Phase 2 work:
    - a CONTEXT / TASK PACKAGE slice (bounded URI-owned context; discover broadly / load narrowly; confirmed-intent binding;
      provenance; authorized sources and attachments; RAR/ARN/Graphify references; permission recheck; capability state;
      execution constraints; focused project context; task-package generation; harness session state treated only as cache).
      docs/architecture/PHASE2C_TASK_COMPILER_PLACEMENT.md is a design note; check whether any of it is implemented.
    - a UI / OPERATIONS slice (actual URI UI wiring; provider/model selection; approval interaction; streamed authoritative
      execution state; cancellation; reconnect/recovery; receipt/evidence display; auth/capability/quota status;
      human-in-the-loop events).
    For each, say REQUIRED IN PHASE 2 / PLACED IN A LATER PHASE / NOT PLANNED, with citations, and give the reconstructed slice
    sequence for the rest of Phase 2 if any remains.
11. Research ledger: find what the repository and docs say about research derived from Strata, Paperclip, AG-UI, A2UI / GenUI,
    MCP and capability-policy concepts, context engineering, model residency / resource ownership, deterministic scheduling /
    monitoring, and long-term URI Memory architecture (also check research_notes/, docs/, and the Phase 1 worktree
    C:\Users\cheta\.codex\worktrees\uri-phase1-integration including any model_lab directory, and C:\Users\cheta\Development\Uri\_V1
    docs if readable). Classify each relevant capability as RESEARCHED / PLANNED / PROTOTYPED / IMPLEMENTED / TESTED / QUALIFIED /
    FROZEN / DEFERRED / REJECTED-NOT-NEEDED with evidence. Researched does not mean required.
12. Choose EXACTLY ONE final verdict:
    PHASE 2D REJECTED
    PHASE 2D ACCEPTED — MORE PHASE 2 SLICES REMAIN
    PHASE 2 IMPLEMENTATION COMPLETE — USER QUALIFICATION REMAINS
    READY TO FREEZE

OUTPUT. Write your full report to C:\Users\cheta\.codex\worktrees\uri-phase2a\evidence\phase2d_review\CODEX_REVIEW_round1.md
with sections numbered 1-12 matching the tasks, then: DEFECTS (table: id, severity, file:line, failure scenario, evidence,
whether it blocks the verdict), NOT VERIFIED (what and why), and FINAL VERDICT (one of the four strings, then the reasons).
Also print the FINAL VERDICT line and the DEFECTS table as your last message.
