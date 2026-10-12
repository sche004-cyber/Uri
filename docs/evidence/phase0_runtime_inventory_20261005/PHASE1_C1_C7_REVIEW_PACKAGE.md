# Phase 1 C1–C7 independent review package

Date: 2026-10-05. **PROVISIONAL — AWAITING INDEPENDENT REVIEW.** This supersedes the earlier C4-stop handoff for dependency-independent implementation. No independent acceptance, merge, release commit, push, production migration or cutover occurred.

The User authorized continued implementation while Claude is quota-unavailable, with exact native/live blockers recorded rather than stopping all work. Independent Claude audit/release remains durably **WAITING_FOR_MODEL**; Codex remains the implementation worker. Frozen architecture, approval/permission authority, client data ownership and existing UI roles are unchanged.

## Actual status

| Slice | Implemented and tested | Gate still outstanding |
|---|---|---|
| C1 | Runtime identity/readiness and exact single-instance server launcher | Independent audit; historical C1 manifest is not current source |
| C2 | Frozen per-store method matrix, paired bounded API, request-scoped ports, minimal control ledger | Independent audit; full subsystem integration through later loop |
| C3 | Isolated worker/private stores, DPAPI/ACL protection, journal/CAS/recovery, exact headless client launcher | Independent audit; desktop launcher parity belongs to C6 |
| C4 | Strict signed ticket/receipt contracts, one-time claim/cancel/reconcile control, client intent journal, locally tested Windows process-tree component, durable quota checkpoint | Native account authentication and provider-specific tool/filesystem containment; cloud/harness bridge integration and qualified verifier callbacks |
| C5 | Core Turn State/Directory/Graphify/proposal/gate preparation with exact private ports and grant intersection; exact provider selection/no fallback | Full RAR/ARN adaptation, provider transports, canonical approve/execute/receipt-feedback/persistence loop; no-Brain live turn |
| C6 | Worker preflight with exact client manifest/UI provenance checks; live honest UI-pending status | Governed UI implementation, C5-dependent parity/voice, historical owner/key lineage and separately authorized copy-first migration |
| C7 | Source recovery tooling, five actual offline restore rehearsals, deployment and rollback gate procedure | All prerequisite behaviors independently accepted and separate explicit cutover authorization |

C4–C6 are **partial component implementations**, not complete milestones. C7 is offline preparation only. New execution control and canonical-preparation libraries are unmounted/uncomposed by design: absent trusted callbacks refuse authority; the paired coordinator still reports CANONICAL_COMPOSITION_PENDING_C5. No substitute reasoning or fabricated harness success is provided.

## Frozen contracts and changes

Implementation baselines: [C2 frozen baseline](C2_FROZEN_IMPLEMENTATION_BASELINE.md), [16-store method contract](C2_STORE_METHOD_CONTRACT.json), [C3 worker/persistence baseline](C3_FROZEN_IMPLEMENTATION_BASELINE.md). Explicit C3-driven C2 amendments retain client-owned profile initialization, session codecs/replacement binding, file validation and credential-bearing connection operations locally. No governing ADR/security contract was silently changed.

[C4–C7 component evidence](C4_C7_COMPONENT_EVIDENCE.md) records exact tested component contracts, source mapping, qualification scope and pending gates. These extend the approved [interface plan](SERVER_CLIENT_INTERFACE_PLAN.md), [ownership matrix](SERVER_CLIENT_OWNERSHIP.md), [launcher plan](LAUNCHER_CONSOLIDATION_PLAN.md) and [implementation plan](PHASE1_IMPLEMENTATION_PLAN.md); they do not replace them.

New source areas: `execution_contracts.py`, `core/client_execution_control.py`, `client_runtime/execution_journal.py`, `client_runtime/process_tree.py`, `core/paired_reasoning.py`, `client_runtime/readiness.py`, and `scripts/phase1_offline_rollback.py`. Existing provisional ClientService gains durable quota checkpoint/expiry handling; the worker gains strict preflight. Accepted stores, model providers/router, decision gates, approval/execution safeguards, RAR/ARN and Graphify are reused, not replaced. No Flutter code, model configuration or experimental branch merge was introduced.

The process-tree donor is one inspected module, SHA-256 `525ece290a9c0baccc4d4e07e853fa9ab8d5ff606b06f074ae3e2fe64db60ba4`; adapted SHA-256 `dde411fb3da30257b86e227a9304d10137303eb354ce8a0f6594fc160eb6728a`. Bounded changes make spawn Windows-only/hidden, reject shell/containment overrides, refuse unowned PID cleanup and add job-membership evidence. Ten real synthetic Windows process tests passed. This does not qualify a Claude/Codex/Antigravity tool boundary or adversarial filesystem sandbox.

## Checkpoints and recovery

Accepted anchor: `e8e3b65259c45fc823addc3ef8969425a265bd1b`. Integration worktree: `C:/Users/cheta/.codex/worktrees/uri-phase1-integration/uri-agent`. All changes remain uncommitted.

| Source overlay | SHA-256 | Actual offline restore |
|---|---|---|
| C1 | `6af55603b8feb9b3dfa8f96f4c745994a46a4560ae8c5034bdf13390ce5e460d` | 16 overlay files + accepted runtime source |
| C2 | `b5f5a470d7e35db27a6f4b417e8e8ee81a6b7591fd11f9a0deb445db77fa024d` | 25 overlay files + accepted runtime source |
| C3 | `7b2a7a563ae7a58bb7273eee98fbd19a3f21f0dec75c65a3e900b066b6fc4c2f` | 39 overlay files + accepted runtime source |
| C4–C7 components | `03fb18e38511f0f9a160542627f68e25ca56a192b6cbc195892ad6b1aaaaca4e` | 51 overlay files + accepted runtime source |

Archives are under the integration worktree's `work/c1/checkpoints`. They contain source, tests and implementation documentation, excluding ignored client/server state, secrets, databases and dependencies. Current r2 overlay predates this final consolidated handoff update; runtime code and component evidence are captured. File listing is in `c4-c7-checkpoint.json`. Historical overlays do not include subsequent amendments.

Five actual recoveries reconstructed 260 accepted runtime source files plus each overlay into different fresh current-account/SYSTEM-protected integration roots. Hashes and overlay Python compilation passed; no imports/application/model/services were started. [Offline recovery evidence](C7_OFFLINE_RECOVERY_EVIDENCE.json) records counts/digests and precise limits. Recovery is source-level, not a runnable installation, restored live database or native account login. Recreate exact-base checkout/dependencies and fresh pinned synthetic manifests before any later authorized launch. Never extract into existing production/client roots or downgrade newer schemas.

Original [preservation manifest](PRESERVATION_MANIFEST.md) and recovery vault `D:/URI-preservation/phase1-20261005-0037` remain intact. Client recovery still requires account-bound DPAPI, journal/schema checks and reconciliation of unsettled operations. Neither store restore nor a repeated claim acknowledgement grants permission to repeat external side effects.

## Validation and repair evidence

Broad [focused suite](PHASE1_C1_C7_FOCUSED_TESTS.xml): **102 passed**, zero failures/errors/skips, one existing dependency deprecation warning. Includes C1 exact launcher/concurrency/foreign/stale identity; C2 pairing/roles/grants/projections/expiry/replay; C3 private stores/journal/frames/native PowerShell; 33 dependency-independent control/preparation/rollback tests; 10 live synthetic Windows job tests.

A final C7 self-review found archive expansion bounds were checked after CRC decompression. They now run before decompression/allocation, with compressed size and member-count caps. [All 8 affected rollback tests](C7_ROLLBACK_FINAL_TESTS.xml) passed afterward, including the additional compressed expansion-limit case. The source checkpoint is r2; the 102-test broad run predates this bounded rollback-only repair. No runtime code changed in that repair.

Latest [Core regression sweep](PHASE1_CORE_REGRESSION_TESTS.xml): **303 tests plus 29 subtests passed**, zero failures/errors. Existing route authorization/bind/CORS/limits, auth/roles, grants/capability/graph authority, approvals/resumption, canonical execution, ARN narrowing, Graphify, portable paths and scoped startup are covered. This is focused coverage, not the full repository suite.

Self-review repairs: client journal settlement now checks full ownership/verifier binding; default ticket validation refuses; claim versions/idempotency keys are strict; deadlines and restart preserve uncertainty; quota expiry preserves durable WAITING_FOR_MODEL; rollback validates accepted base as well as overlay and restricts fresh destination ACLs. An initial Windows breakaway test failed because it assumed access denied rather than checking actual containment. The created child remained in URI's exact job; corrected membership/death tests passed. The failed artifact is retained locally (`work/c1/c3-c4-windows-final.xml`) and is superseded by the passing final suite; no failure was hidden or counted as acceptance.

Latest live server/two-client validation passed signed identities, exact repeat-server recognition, pinned authenticated sessions, local consented mutation, identical receipt replay, second-client isolation and framed preflight reporting UI pending. All test-owned workers/server were cleaned with their owned channels/identity proofs. No model, UI or native harness ran. Test mutations came from trusted fixture control, not a qualified Brain loop.

Reproduction uses the isolated `.venv/Scripts/python.exe`: pytest on the five milestone test modules; `scripts/validate_c1_regression.py`; `scripts/validate_c3_live.py`; source rehearsal `scripts/phase1_offline_rollback.py --archive <isolated checkpoint> --sha256 <recorded digest>`. Each creates fresh synthetic state. [Machine review evidence](C1_C7_REVIEW_EVIDENCE.json) links test counts, safe live results, checkpoint metadata, native prerequisite status and preservation observations.

## Preservation observations and exact blockers

Compared with the earlier baseline: **4,571 protected files checked; 3 hash differences; 0 missing**. Differences classify as one legacy log, one Codex development configuration file and one Claude development metadata file. No implementation operation targeted those files; their writers/causes are unverified. They were not reverted or overwritten. Reports contain aggregate categories, not private contents/paths/hashes. This replaces the earlier zero-difference observation; it is not evidence of byte-identical preservation of every account artifact throughout the session.

Original URIServer task XML still matches the preserved copy and its state is Ready. Final read-only inspection found no listeners on 8000/8021/8031/11434/1234. The prior handoff's 8021/PID16188 and C1 8031/PID6504 observations are historical, not claims those processes currently remain alive. This implementation did not stop those services; test cleanup was confined to freshly launched owned instances. Existing launcher/shortcut/application/database/model artifacts in the comparison have no observed changed hashes; the legacy log and development-account metadata differences remain explicit attribution limitations.

Prior fresh-profile probes: Claude Code 2.1.287 and Codex 0.158.0 returned NOT_AUTHENTICATED. No new login, legacy-account import, provider request, quota substitution or paid inference was attempted. Exact pending gates: native profile authentication; provider-specific proposal-only/tool containment; cloud credential transport; trustworthy verifier registration and artifact freshness; approval/claim/receipt integration; C5 RAR/ARN/state/feedback adaptation; UI build provenance/parity; historical owner/key lineage. Synthetic process tests cannot satisfy those gates. Antigravity execute refusal remains.

## Production readiness and next review

**Production readiness is NOT ESTABLISHED.** C7 deployment procedure is prepared but unexecuted. Retain legacy entrypoints; require exact accepted server/client/UI manifests and explicit owner mappings; validate qualification/backup/rollback gates; obtain separate User cutover authorization before any task/shortcut/default-port change. Preserve unsettled receipts/newer schemas, never replay uncertain side effects or run recovery against occupied production roots. The full future procedure and stop conditions are recorded in the component evidence and existing launcher plan.

Claude's independent audit should trace actual reachable/unreachable paths and callback authority, investigate preservation differences, review scope/contract amendments, validate journal recovery/claims and qualify live provider/UI behavior before any release. Codex self-review and these tests do not confer independent acceptance.
