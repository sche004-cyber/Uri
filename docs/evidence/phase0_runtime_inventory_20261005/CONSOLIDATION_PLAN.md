# URI Phase 0 — Consolidation Plan

Date: 2026-10-05. **Recommendation for review, not an accepted implementation blueprint.** Stop after this assessment. No consolidation, model changes, service changes, milestone-state edits, commit or push is authorized by this report.

Phase 1 update: the User subsequently authorized preservation and architecture preparation. That preparation is recorded in [Preservation manifest](PRESERVATION_MANIFEST.md), the updated [Ownership matrix](SERVER_CLIENT_OWNERSHIP.md), [Interface plan](SERVER_CLIENT_INTERFACE_PLAN.md), [Launcher plan](LAUNCHER_CONSOLIDATION_PLAN.md) and [Phase 1 implementation plan](PHASE1_IMPLEMENTATION_PLAN.md). This Phase 0 roadmap remains historical evidence. Its stop statement describes Phase 0; Phase 1 also stops before consolidation implementation. Use the Phase 1 package for the proposed C1 scope and current preparation status.

## Recommendation

Reuse URI Core and its existing FastAPI API, principal/capability/approval controls, provider boundary, Graphify hints, context budgets and ARN.1. Start from the accepted `uri-agent` **`e8e3b65` source checkpoint**, while preserving the dirty master, current shortcut-targeted integration desktop, V1/harness-console work and their data as separate donors. Do not promote the entire integration checkout or the active 8021 provisional test composition as authoritative.

“Authoritative Core” means the accepted control/execution lineage to build upon. It does not mean clean master already contains every desktop/V1 capability, or that its UI should immediately replace the app the User launches. The server candidate must reconcile exact required donor behavior before cutover. Source hashes, qualification scope and client data ownership matter more than highest milestone number.

The **safest first implementation milestone is Runtime Identity and Launcher Authority**, after the User reviews this assessment and its four-stage package is accepted. It should make source/interpreter/state/composition identity observable and launcher decisions reliable; it must not relocate private databases, change active models, expand adapters or retire code.

## Why consolidation is feasible, and where it is not yet ready

| Objective | Reusable foundation | Minimum necessary change / qualification |
|---|---|---|
| Authenticated clients | Existing HTTP auth/principal and route classification | Strict client installation identity and pairing on the new surface; preserve compatibility fallback only until callers migrate |
| Shared Core/intelligence | Decision engine, router, canonical execution, Graphify and bounded contexts | Inject request-scoped client context/state access; separate private persistence from engine lifetime |
| Private client databases | Existing per-user store schemas and V1 provenance/log schemas | Client-owned state implementation and scoped protocol; user_id alone is insufficient |
| Client-local harnesses | M38 adapters/capsules/runner plus desktop discovery | Move process launch/discovery/credentials/workspaces into client; qualify Windows containment and exact adapter roles |
| RAR/ARN preservation | Qualified deterministic RAR contracts, accepted ARN.1, existing clarification seams | Explicit scope/lineage mapping; retain opt-ins and task ceilings; no ARN.2 expansion |
| Graphify preservation | Runtime index, private graph engine, Turn State hints | Shared public catalogue plus isolated private overlays; retain advisory authority boundary |
| External harness without Main Brain | Proposal/receipt contracts and client executor | Complete reasoning-source round trip, model-optional startup/UI/routing; don't equate executor with Brain replacement |
| Existing UI | Flutter HTTP client/screens/state, release binaries, file handling | Contract compatibility plus installation-scoped preferences/session persistence and client state; live parity checks |
| One server launcher | Existing runner/controller, integration ownership/socket/mutex checks | One explicit launch manifest; no generic health/process-name reuse; interpreter and state roots explicit |

No replacement backend framework, new graph engine or generalized scheduler is justified. A separate microservice for each intelligence engine would increase process duplication without demonstrated need.

## Required preparation: preserve and reconcile evidence

This is planning work before implementation, not permission to perform it now.

1. Freeze a machine-readable source/behavior manifest for accepted Core and each necessary donor, including dirty source hashes, launch composition, built UI provenance, interpreter/package versions and existing acceptance evidence. Keep credentials and private data out of the source manifest.
2. Have the User identify which existing data installations belong to which future client. The hundreds of user directories cannot be treated as real accounts or automatically merged. Record paths/owners/schema/key provenance with redaction and permissioned local handling.
3. Inventory the exact required current desktop behaviors: ask/stream, history/tasks, attachments and Office output, auth/server settings, providers/Edge diagnostics, connections, approvals, Develop mode, voice and harness console. Separate historical qualification from current dirty changes.
4. Reconcile M36–M39 acceptance evidence by source checkpoint. The inspected 62d564c batch audit remains provisional; M38 requires fresh subscription-backed live qualification. Integration Office code still has `KNOWN_UNSAFE_HARNESS_SUBSTRATE=True` and refuses normal harness construction. Preserve that refusal until a reviewed candidate earns different behavior.
5. Use this Phase 0 assessment as Stage 1 evidence. Produce the canonical Stage 2 design and Stage 3 migration plan under future approved governance, then freeze the bounded implementation blueprint. Do not mark these reports as a completed accepted milestone or alter the tracker.

Existing AO-4 and UI-initiative role restrictions continue to govern their applicable work; Codex does not self-approve or release. Plans are ordinarily auto-approved under standing governance, but this User expressly required review before consolidation, and moving ownership/security boundaries needs that review. Do not auto-start the next phase.

## Ordered implementation milestones

Identifiers C1–C7 below are proposal labels, not new M-number assignments. Each follows Audit → Architecture → Migration → Implementation/Validation, with no release before its specified evidence and appropriate independent approval.

### C1 — Runtime Identity and Launcher Authority

Scope: explicit runtime manifest and non-sensitive identity/status; idempotent ownership-aware launcher checks. Source candidates: `scripts/run_uri_server.py`, `scripts/uri_server_ctl.ps1`, `scripts/launch_uri.ps1`, integration `run_desktop_server.py` / `launch_desktop.ps1`, and existing desktop status adapter.

Implement a stable server installation ID, source/composition/contract version, explicit interpreter and state root, and consistent status reporting. Separate public health from authenticated detailed status; do not publish private filesystem paths. Reuse the integration socket-owner and exact executable/script identity checks. A healthy unrelated URI instance must be reported as a different server, not silently adopted or terminated.

The first slice should retain the presently chosen launch compositions and only establish reliable identity. A later, separately reviewed deployment step reconciles desktop shortcuts and installed task to the single qualified manifest. Save the old task/shortcut settings before that step. Do not copy the integration warm-up/residency policy merely because its launcher is the current shortcut target.

Required checks: unrelated listener, wrong-checkout healthy URI, stale/reused PID, concurrent double-clicks, missing interpreter/build, interrupted launch, server restart, accurate state-root identity, loopback binding, existing desktop attach, and installed task settings versus declared policy. Controlled live startup/lifecycle checks happen only in the later approved validation environment; Phase 0 did not run them.

Acceptance: every supported URI entry point explains its selected server/client; one manifest starts at most one intended backend; conflicting instances fail visibly without stopping others; current UI capabilities still operate against their intended backend; independent release checkpoint and rollback evidence exist. No data/model changes are bundled into C1.

### C2 — Client identity and injectable state boundary

Depends on C1. Introduce validated client-installation identity bound to URI authentication and a versioned ClientState contract. Do not trust caller-supplied client IDs, user IDs or model text to select private roots.

Refactor the narrow composition seam around `server.py::_build_user_context`, `_resolve_context`, portable paths and injected stores. Reuse store schemas and Core gates. Provide a legacy backend-state adapter so existing UI continues to work, plus a strict new-client surface that cannot fall back to ambient data. Keep shared catalogue/services independent of client persistence.

Required tests: two clients under one account; cross-client/user/session reads, attachments, graph queries, approvals and receipts; missing/stale pairing; invalid/expired token; malformed scope/path; state version conflict; client outage; audit redaction; no capability escalation from context or Graphify. Exercise actual canonical tool paths, not just store unit tests.

Acceptance: each new-client operation has validated client identity and isolated state context; private database access occurs through the client port; compatibility tests pass; execution/approval semantics remain intact. No private-data migration yet.

### C3 — Client-owned persistence and reversible data migration

Depends on C2 and owner mapping. Keep databases/workspaces/configurations in each client installation. Implement local persistence with existing formats where practical; do not change database engines merely to relocate ownership.

Adapt history/sessions/memory/profile/skills/uploads/private graphs, source registries, per-client journals and preferences. Scope Flutter storage by client installation and server identity; move URI session handling to suitable protected client storage. Preserve current UX behavior while changing ownership underneath.

Migration is copy-first into a new destination, never merge-in-place. Carry original identity and provenance where required; record explicit old-to-new identifiers rather than inventing equivalence. Verify schema, relationships, attachment references, versions and encryption provenance locally without exposing contents in logs. Maintain backups and originals through acceptance.

Acceptance: client A cannot observe client B's database/config/workspace even under the same developer account; server restart does not own/reconstruct private state; offline changes/version conflicts resolve deterministically; all migrated UI/history/file behaviors work; no source files or credentials are overwritten. A server's operation ledger stores only approved minimal metadata, never full private context.

### C4 — Client-local harness execution and credentials

Depends on C2; migrate credentials only through C3's agreed ownership rules. Reuse M38 capsules, grants, approval expiry/decline checks, process supervision, verifier identity, run settlement and receipts. Move adapters/discovery/process launch into the client installation; the server coordinates validated requests but never reads native harness account homes.

Qualify Claude Code first if its supported subscription posture remains intended. Preserve metered-API denial and permission/sandbox bypass rejection already encoded in adapters. Codex and Antigravity qualify separately; Antigravity's current execute refusal must remain until real containment evidence exists. Native CLI profile separation on Windows needs evidence; merely passing another working directory is not account isolation.

Required checks: wrong client/workspace, capsule tampering, expiry, approval decline, plugin/MCP grant injection, descendant process containment, credential isolation, forbidden bypass flags, account/quota unavailable, cancellation, duplicate receipt, restart after launch, uncertain completion and non-replayed recovery. Return actual execution evidence to Core's reasoning loop. Do not use private real files as a containment experiment.

Acceptance: server has no client harness credentials or native account authority; one approved client task runs within its scope and returns a verified receipt; denial/quota states are truthful; no silent provider substitution; live qualification on the exact candidate source is complete for each enabled adapter.

### C5 — Shared intelligence, RAR/ARN/Graphify and model-optional loop

Depends on C2/C4; use C3 for persistent overlays. Reuse Core Turn State/context budgeting and V1 memory context packages rather than rebuild “Context Builder.” Adopt only qualified RAR behavior; keep experimental decoders/attachment-order variants outside default routes. Preserve ARN.1 NOT_FOUND recovery, repeated-search/candidate tracking and ceilings. INT-ARN clarifications are reconciled by actual contract and production path, not by similar names.

Shared Graphify is a public capability catalogue plus isolated private overlays. Private entity graph databases remain clients' property; shared graph algorithms receive only authorized bounded evidence. Graphify cannot grant, approve or execute.

Support an external harness as reasoning/proposal source as well as executor, with deterministic validation and receipts fed back into the same reasoning source. Server startup and UI must work with no Ollama daemon, no locally resident Main Brain and optional Edge absent. Model load/unload is explicit shared-server policy, never a desktop-side implicit optimization affecting other applications.

Acceptance battery: qualified RAR challenge/ambiguity/provenance cases; ARN search exhaustion and terminal states; Graphify disabled/stale/unavailable behavior and authority tests; client-isolated context/cache tests; local/cloud model compatibility; a full external-harness turn with no local Brain showing discovery → proposal → validation → approval → execution → feedback → grounded user reply. Warm-up and inference counters must prove no unwanted local loading. Preserve existing local-Brain behavior separately.

### C6 — UI, voice, scheduling and full compatibility qualification

Depends on C3–C5. Preserve Flutter screens and actual current desktop behavior through contract adapters. Keep Develop mode UX separate from runtime authorization. Preserve standalone dictation and V1 voice rather than combine their caches/device ownership blindly.

Live UI matrix: startup/sign-in/server changes, ask/stream continuity, attachment upload/read/generation, approvals/resumption, history/tasks, providers/Edge status, connections, Develop behavior, disconnected server, external-harness-only operation, microphone/speaker controls, dictation paste/polish and restart. Voice recording remains local client data unless explicitly delegated.

Scheduling and monitoring are not established canonical runtime capabilities by this audit. If requested later, first identify proven reusable code and apply the lifecycle; do not include a new scheduler as speculative consolidation scope. Test device/hotkey conflict only if both voice paths are deliberately enabled.

Acceptance: component + integration + canonical agent-loop + live user-visible evidence on Windows. Report historical/environment failures against an exact baseline; do not advertise an old delivery count as a fresh pass. Apply the standing UI-initiative role override to relevant UI work.

### C7 — Controlled cutover and retirement review

Depends on C1–C6 independently accepted. Point supported launchers to the one qualified server and independent clients. Retain old installations/data/configuration for an agreed recovery window. Retirement requires a separately reviewed list with ownership, consumers, parity evidence, backups and rollback.

Potential candidates: legacy PyQt direct-Core launcher, superseded generic launch scripts, duplicate scratch/build outputs and model caches, scheduler demo apps, unqualified experimental routing. Frozen V1 implementations, native account homes and private client data are not cleanup targets by default.

Acceptance: one intended backend serves multiple isolated clients; default launch/logon/restart behavior is reliable; external-harness client needs no local Brain; all protected capabilities and UI functions remain available; no unexpected shared private state or duplicate side effects; rollback has been rehearsed. Release remains with the authorized role, not this assessment worker.

## Migration inventory requirements

| Data class | Destination | Migration rule |
|---|---|---|
| Legacy root memory/profile/history/approvals | Specifically identified client | Determine true owner; copy original plus manifest; don't mix with existing user-scoped stores |
| `users/<user>/graph.sqlite3`, sessions, uploads, learned skills | Client database/workspace | Preserve references and scope; root graph and per-user graphs are not duplicates by assumption |
| V1 task logs/sources/result ledgers/reference journals | Owning client | Preserve provenance/version/task IDs and freshness; no replay of unfinished work |
| Provider/OAuth credentials | Owning client only | Preserve encryption key lineage outside reports; prefer explicit reauthorization if portability cannot be proved |
| Native Claude/Codex/Antigravity authentication | Native client account/profile | No server import, token export or pooled account home |
| UI preference/session file | One explicitly designated client, then isolated stores | Copy only approved preferences; bind session to server identity; don't broadcast old bearer token |
| Public capability/Graphify catalogue | Server | Rebuild from existing authoritative registry with qualification metadata; exclude private overlays |
| Voice dictionaries/settings/caches | Owning local helper/client | Preserve device and polish settings; cache reuse only after identity/integrity verification |

No automatic deletion based on folder age, user-directory count, model size, dirty status or absence from the active process list. Quarantine/removal itself requires later authorization.

## Rollback strategy

Maintain exact source/build/environment manifests and independent backups of old state and encryption provenance before mutations. Use new state roots and backward-compatible adapters; never overwrite accepted legacy data. Gate new client routes, harness bridge and model-optional routing independently. Roll back a failed slice to its prior composition and launcher manifest without switching account ownership or replaying uncertain work.

Before migration cutover, document schema/version downgrade behavior and detect newer destination state. A rollback must not write newer formats through older code. Restore old task/shortcut configuration deliberately and check listener identity; never kill a process using a stale PID alone. Retain minimal execution IDs/receipts needed to prevent duplicate side effects. Handle unknown completion as recovery requiring evidence, not blind retry.

## Assessment completion and unresolved verification

Phase 0 established the actual shortcut target, competing task registration, current isolated harness listener, source/configuration divergence, model files and ownership mismatch. It did not establish current UI parity, adapter authentication/containment, database contents/owners, loaded-model performance, or a working no-Brain canonical turn. Those require approved implementation/validation work and are explicit acceptance gates above.

**Decision requested at the next review:** confirm the proposed accepted-Core anchor plus preservation of desktop/V1 donors, and approve the bounded C1 four-stage package. Do not begin migration or consolidation merely because this plan exists.
