# URI Server / Client Ownership — Phase 1

Date: 2026-10-05. Phase 1 updates the existing Phase 0 ownership report in place. The User has settled the high-level server/client decisions and authorized preservation/preparation. Interface and migration details remain proposed for review; runtime code and milestone status are unchanged. The Phase 0 version was preserved in the encrypted master-checkout archive before this update.

## Ownership principle

The server hosts shared intelligence and deterministic control services. Each client owns its private database, workspace, configuration, native accounts and harness processes. A client sending bounded context to a server does not transfer database ownership. Per-user server directories are a useful existing compatibility mechanism, but do not satisfy independent client installations under one user account.

Runtime authority remains propose → validate → approve → execute. A client harness receipt, model proposal or coordinator message cannot grant capabilities or approve its own side effects. The developer retains full local development control; production administration and multi-user policy expansion are deferred.

## Classification of discovered components

Categories: **1 Server; 2 Client; 3 Shared library; 4 Development tooling; 5 Legacy preserve/migrate; 6 Retirement candidate after verification.** A component can have a primary category and a transitional disposition.

| Existing component / actual location | Primary category | Target owner and disposition |
|---|---|---|
| `uri_core/app/server.py`, route classification and principal/authorization logic | 1 | Reuse HTTP boundary; add strict authenticated client boundary; retain compatibility routes during migration |
| Decision engine, model router, canonical execution, approval/capability validation | 1 | Shared server services; approvals remain deterministically validated and bound to the requesting client/task |
| Core store schemas, serialization, path validation, context budgets | 3 | Reuse schema/algorithms in both ends; move private persistence ownership behind an interface |
| Profile, memory, growth, skills, sessions/history, uploads, private graph SQLite | 2 (currently backend hosted) | Client persistence and workspace; staged migration from existing server user roots, never a shared server database |
| Account/session authentication records | 1/2 split | Server stores minimal URI pairing/session validation metadata; client stores its own URI session securely. Native external account authentication stays client-only |
| Per-user provider configs, provider encrypted keys, OAuth connection credentials | 2 | Client owns preferences and credentials. Server may request explicitly authorized client-side service execution; it must not own an install-wide union of client accounts |
| Runtime Graphify catalogue/index | 1 | Server shares public capability catalogue; private skill/memory/service pointer overlays remain client-scoped |
| `graph_store.py`, graph query algorithms | 3 | Engine can run server-side over bounded authorized input; private graph persistence remains client-side |
| `graphify-out` developer graphs/CLI | 4 | Development navigation only; do not deploy the repository graph as user memory or duplicate runtime Graphify |
| ARN.1 deterministic engine and NOT_FOUND integration | 1/3 | Reuse accepted engine; task/client/session-scoped state and evidence. Do not expand into paused ARN.2 |
| V1 RAR deterministic contracts/active context | 3, invoked by 1 | Reuse qualified resolution semantics over scoped candidates; persist binding/journal in client state |
| INT-ARN reference clarification desktop seams | 5 pending qualification | Preserve existing behavior and opt-in status; reconcile with RAR/ARN, not a second universal inference engine |
| Core Turn State builder and bounded evidence/context assembly | 1/3 | Server assembles a bounded request from explicit client context; no ambient private-database scans |
| Legacy `context_builder.py` and V1 `context` scaffold | 5 / 6 | Preserve; old task-requirement helper has no production imports found, V1 namespace has no resolution implementation. Do not advertise a standalone working Context Builder server |
| V1 M36 MemoryLog/Recorder/SourceRegistry/context package | 2 persistence + 3 contracts | Client owns source registries and logs; reuse provenance/freshness rules. Do not merge records with legacy memory by filename |
| V1 M37 Edge local inspection / local runner | 3; deployment split | Pure parsers/diagnostics are reusable. Workspace access, scratch/run files and local tool execution belong to client; shared server inference remains separate |
| V1 M38 capsules, acceptance/receipt/verifier contracts | 3 | Reuse grant/approval/artifact/receipt semantics; bind client identity before transport |
| ClaudeCodeAdapter, CodexAdapter, HarnessRunner/process supervisor | 2 | Run in each client installation with that client's native CLI/account and workspace; server never invokes its own global harness account on a client's behalf |
| AntigravityAdapter and discovery registry | 2 / 4 provisional | Keep discovery honestly separate from execution. Current execute path is explicitly containment-unqualified |
| M39 Office flow/bootstrap/writeback | 3 + 2 | Client document/workspace access; shared validated orchestration can coordinate it. Preserve current explicit unsafe-harness refusal |
| Flutter `uri_ui` and Develop mode | 2 | Preserve screens, files, auth/server settings, turn/task/approval behavior. Add installation isolation underneath; UX mode is not authority |
| Legacy `uri_ui.py` PyQt direct-Core UI | 5 / 6 | Preserve as migration reference until feature parity and lack of launch dependence are established |
| V1 voice listener/transcriber, device controls | 2 | Microphone, speaker, status and hotkeys belong to local client; optional shared transcription inference must require explicit bounded audio delegation |
| `uri_dictation` standalone helper | 2; experimental | Preserve separate utility, caches, dictionary and polish settings; optional server inference, no forced dependency on local Main Brain |
| Main Brain providers and optional Edge model workers | 1 | Shared server inference if selected; models need not be loaded for external-harness clients. Client mode/preference does not grant model lifecycle authority |
| Harness-first social classifier/chat seam | 5 | Preserve source/evidence; qualify narrow social behavior independently. It is not a general harness adapter or full no-Brain solution |
| Desktop Ollama residency seam | 5 / 4 pending policy | Current cross-application unload behavior needs explicit ownership policy before server adoption; do not silently carry it into shared inference |
| Single server lifecycle / health metadata | 1 | One explicit manifest and interpreter; independent client launchers connect without creating competing servers |
| Windows shortcut/task scripts, audit/qualification scripts, Codex/Gemma/Claude development loop | 4 | Development/deployment tooling. Development harness usage and URI runtime harness adapters are distinct roles |
| `scheduler_proto`, `qwen_scheduler_benchmark` apps | 4 / 6 | Separate prototypes; no proved canonical URI scheduler. Preserve rather than reimplement assumptions |
| System performance capability | 1/3 | Existing metrics primitive; no proof of a persistent URI monitor/scheduler follows from it |
| Duplicate caches, stale PID files, scratch tests/builds | 4 / 6 | Inventory/retention candidates only; never delete before release and recovery evidence |

## Minimum interfaces to add or adapt

These are proposed contracts using the current FastAPI/HTTP and existing dataclasses; no new framework or message broker is justified by this inventory.

| Interface | Required behavior | Existing seam to reuse |
|---|---|---|
| Runtime identity/handshake | Stable server installation ID, source/composition identity, contract version and capability readiness; no private paths/secrets on public health | `/health`, integration `/desktop/status` and launcher ownership checks |
| Authenticated ClientContext | Server-issued/validated pairing, client installation identity, principal, session and workspace scope. Client ID is not a model-supplied authority claim | Principal resolution, auth-session store and route classification |
| ClientState port | Versioned scoped context reads and validated persistence requests/results; fail closed on wrong client or stale version. Private database stays on the client | Existing injected stores in `_build_user_context`, portable paths, V1 memory schemas |
| Intelligence request | Bounded evidence/candidate/context package with provenance, consent and identifiers; context assembly remains model-general | Turn State, context budgets, M36 bounded context package |
| Client execution capsule | Client/task/session/workspace binding, capability grant, expiry, approval state, expected evidence and verifier identity | M38 capsule/runner and Core approval/capability boundary |
| Result receipt / feedback | Idempotent execution ID, verified status, scoped artifact references, bounded error and usage data; feed actual result back into canonical reasoning | Core execution result flow, M36 recorder, M38 claims/acceptance, result ledger |
| Harness inventory | Client reports installed/authenticated/qualified/available separately; never sends credentials or login transcripts | Desktop harness registry and native adapter discovery |
| Optional model readiness | Distinguish absent, installed, resident, qualified, selected and unavailable; explicit policy for who may load/unload shared workers | Provider registry/router, Edge lifecycle; retain bypass/no-Brain paths |

The ClientState port must have an explicit outage contract. A disconnected client cannot have its private mutations acknowledged as saved. For consequential operations, bind approval to the exact operation/workspace/version and confirm persistence/receipt without replay. Server restart cannot reconstruct client private databases from ambient leftovers. Long-running client work requires durable client checkpoints and recovery, not a server assumption that a missing receipt means failure.

## Data boundary and credentials

Server may persist its own configuration, public catalogue, minimal pairing/session validation records, and carefully scoped operation/approval metadata needed for deterministic safety. It must not persist transcripts, documents, private graphs, native harness credentials or full context as an accidental side effect of audit/telemetry. Redacted/minimal server audit data remains sensitive and needs an explicit retention rule.

Client owns the durable private content and native harness authentication (`.claude`, `.codex`, Antigravity native account store or dedicated supported installation profile). Running several clients under one Windows account does not automatically isolate native CLI homes: supported per-install profile selection or isolation must be qualified. Do not copy account files or set provider API keys as a substitute for subscription authentication.

Provider API credentials and Google OAuth are distinct from harness subscriptions. Where existing Core tools need authenticated remote calls, choose a client execution bridge or explicit limited delegation; never silently migrate them to a server-global credential store. Preserve encryption provenance and prefer reauthorization when account portability is uncertain.

Private Graphify overlays, RAR candidate sets, ARN histories, retrieval results, temporary files and model prompt caches must use client/session/task scope even when the algorithms are shared. A shared user account alone is insufficient isolation.

## External harness without local Main Brain

Feasible as a target by reusing the existing proposal/validation/execution contracts and client adapters, but **not proven end-to-end by this inventory**. Two roles need explicit support: external harness as task executor, and external harness as reasoning/proposal source. An execution adapter by itself does not replace Core's Brain-dependent decision/drafting calls.

Route client-supplied or harness-produced reasoning through existing validation and deterministic gates; return tool receipts to that same reasoning source. UI and server startup must tolerate no Ollama daemon and no resident Main Brain. Disable warm-up only through a future accepted policy change, not as an assessment side effect. Claude, Codex and Antigravity must each qualify their own supported role; current Antigravity execution refusal is retained until evidence permits otherwise.

## Phase 1 implementation ownership and migration boundaries

The classification above is retained for continuity. This section makes the settled ownership executable as an implementation plan. [Server–client interface plan](SERVER_CLIENT_INTERFACE_PLAN.md) defines the transport/state contracts; [Launcher plan](LAUNCHER_CONSOLIDATION_PLAN.md) defines process ownership. [Preservation manifest](PRESERVATION_MANIFEST.md) records protected source/data recovery.

| Major component / source seam | Durable owner | Process that performs work | Minimum interface | Compatibility / first migration action |
|---|---|---|---|---|
| HTTP edge, `server.py`, route classification, principal resolution | Server control metadata | Server | Paired ClientContext and contract version | Keep existing desktop composition; add strict new surface separately |
| Auth sessions / account verification | Server hashes/binding records; client raw session | Both respective runtimes | Client-bound URI session | Existing device_id stays informational; no new production admin system |
| Capability registry/directory/resolver and grants | Server public definitions/control records | Server | Qualified catalogue + scoped grant | Preserve registry ceiling and per-capability checks |
| ApprovalGate / approval store | Client full private approval record; server minimal decision/digest/expiry | Server validates; client presents consent | Exact operation/version-bound approval | Keep decline/expiry/revalidation behavior; don't serialize model approval as consent |
| Decision engine / canonical executor / native-tool loop / multi-action dispatch | Client private turn journal; server minimal operation ledger | Server coordinator | Versioned turn continuation / ticket / receipt | One canonical execution authority; preserve feedback and aggregate outcomes |
| Dispatcher and tools | Public metadata server; inputs/outputs owning client | Server for public pure services; client for private/workspace/credential actions | Execution-location descriptor + scoped ticket | Location comes from trusted registry, never model routing preference |
| User profile / memory / settings / growth / experience / learned skills | Client | Client worker | Snapshot + typed mutation set + CAS receipt | Reuse formats; no data copied into server merely for compatibility |
| Sessions / history / uploads / file evidence / file operations | Client | Client worker | Bounded conversation/evidence/artifact descriptors | Preserve explicit attachment/session scoping; no absolute path on server |
| GraphStore / graph ingest and query algorithms | Client private SQLite graph | Client persistence; reusable bounded engine server or client | Scoped graph query/evidence port | Root and user graphs have separate provenance; never deduplicate by filename |
| Graphify public index / startup catalogue | Server | Server | Catalogue generation/digest | No private memory/service pointers in shared persisted index |
| Graphify private overlays / relevant subset / cache | Client durable overlay; server ephemeral turn view | Shared engine with client scope | Overlay snapshot + version/expiry | Cache keys include client/session/operation; stale index cannot grant authority |
| RAR contracts/resolution/active context | Client bindings/candidates/history | Shared pure resolver | Candidate/evidence IDs with provenance/version | Adopt only qualified variants from exact donor source; ambiguity stays explicit |
| ARN.1 deterministic narrowing / first NOT_FOUND recovery | Client task trace | Shared engine / canonical loop | Task-scoped ARN projection | Preserve costs, candidate tracking and terminal states; ARN.2 stays outside scope |
| INT-ARN clarification journal/seams | Client journal | Shared resolver + client UI/persistence | Clarification continuation / exact response binding | Preserve opt-in source behavior as donor; no duplicate recovery authority |
| Context budgets / Turn State / M36 context package | Client sources, server ephemeral bounded package | Server assembly over snapshots | needs_context continuation | Legacy helper/scaffold is not a second Context Builder implementation |
| Model router / provider APIs / serving selection | Client private preferences; server shared model inventory/policy | Server local model; client cloud/harness request | Explicit ReasoningSelection / ReasoningProposal | Preserve provider contract; fallback empty unless explicitly configured |
| Main Brain and Edge model residency / lifecycle | Server model policy; client model choice | Server only for shared workers | Installed/resident/qualified/selected readiness | No automatic warm-up, install, unload or experimental promotion in preparation |
| Native Claude/Codex/Antigravity discovery and execution | Client native account/profile | Client worker / contained descendants | Harness advertisement + capsule + verified receipt | Accounts never pooled at server; per-install native profile isolation must qualify |
| V1 M36 MemoryLog/Recorder/SourceRegistry / result ledger | Client | Client worker / shared schemas | Provenance/freshness/context/receipt contracts | Preserve task IDs/history; no implicit conversion to old memory semantics |
| V1 M37 Edge inspection/local runner | Client workspace/scratch/run records | Client worker | Local inspection result / qualified verifier | Pure parsers reusable; executable runner doesn't belong in shared server filesystem |
| V1 M38 acceptance/verifiers/process containment | Client run record; server qualified verifier metadata | Both validation boundaries | Bound verifier identity and implementation digest | Live qualification required; claims alone not verified output |
| V1 M39 Office / existing Office/PDF tools | Client files/version ledger | Client worker; shared planning/validation | Artifact/result-head references | Preserve writeback guards, fonts/format behavior and current unsafe-harness refusal |
| Google/other connections and provider keys | Client | Client credential-bearing requests/tools | Credential-free advertisement + delegated operation | Never migrate account secrets into server-owned global connection store |
| Flutter UI, Develop mode, preferences, device/session identities | Client | Flutter + private worker | Client manifest, isolated local protocol | Legacy prefs untouched; new installation gets its own namespace; mode stays UX-only |
| Voice listener/STT/OCR/VLM/device capture/dictation | Client devices/audio/settings; server optional qualified inference engine | Client capture; optional explicit inference delegation | Bounded media request + result | Preserve standalone helper and voice paths; unqualified models remain unavailable |
| System metrics / diagnostic tools | Server installation metrics or scoped client metrics | Respective owning runtime | Redacted readiness/metrics | Don't infer scheduler/watch capability from one metrics tool |
| Scheduler prototypes / future watches | Existing prototype state preserved | Development-only until qualified | No new runtime interface in this phase | A future scheduler needs its own evidence/lifecycle; no rebuild assumed |
| Launchers/tasks/shortcuts/builds/qualification scripts/dev Graphify | Deployment/development records | Development tooling | Source/build/manifest identity | Preserve originals; new opt-in launchers only after implementation review |

## Server/client root layout

Future installation roots, separate from all existing production roots:

```text
<server-root>/manifest.json            identity, paths and policy; no secrets
<server-root>/control/                 pairing/token hashes + minimal execution ledger
<server-root>/catalogue/               public capability/qualification metadata
<server-root>/logs/                    redacted operational logs
<client-root>/<installation-id>/manifest.json
<client-root>/<installation-id>/private/   memory/profile/graph/history/approval/task stores
<client-root>/<installation-id>/workspace/ artifact/source handles and journals
<client-root>/<installation-id>/config/    client preferences and model selection
<client-root>/<installation-id>/secure/    protected URI/cloud credentials or native profile locator
```

Exact destination roots are deployment manifests, never ambient relative paths. Future native harness profiles must use supported, qualified isolation. A directory named secure does not itself secure credentials; apply Windows protected storage/ACLs and keep secrets out of Git/logs. Credentials preserved in the backup vault remain archives, not provisioned credentials for the isolated worktree.

## Qualification and review status

High-level ownership is authorized by the User's Phase 1 instruction. Protocol details are proposed. The prepared integration worktree starts at accepted Core only; donor source and qualified artifacts remain separate. No private data is migrated and no adapter/model is promoted.

First implementation scope: runtime identity and opt-in server launcher. Later client-state work requires store method coverage and explicit historical-data ownership. External-harness reasoning/execution requires adapter-specific containment/authentication evidence; presence of an installed CLI or an executable adapter does not satisfy it. Existing UI role restrictions and independent release authority remain applicable.
