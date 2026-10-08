# C2 — Frozen implementation baseline

Status: FROZEN FOR IMPLEMENTATION — PROVISIONAL — AWAITING INDEPENDENT REVIEW. User authorization: 2026-10-05 resolve prerequisites and continue C2–C7. This freeze is not acceptance or production approval.

## Governing boundary

The approved Phase 1 ownership/interface/launcher plans and accepted model/runtime contracts govern. This baseline resolves their implementation prerequisites; it does not alter execution authority, production permissions, UI role assignments, donor qualification or production cutover requirements. C1 remains provisional.

## Evidence and complete method coverage

Core anchor: e8e3b65259c45fc823addc3ef8969425a265bd1b. `_build_user_context` constructs private stores and credentials keyed only by user ID; `_resolve_context` retains ambient fallback for legacy routes. The new paired surface cannot use either function. Constructors, file paths, corruption recovery, native credential reads and account discovery execute only in the owning client.

Machine-readable source signatures, hashes and method dispositions: [C2_STORE_METHOD_CONTRACT.json](C2_STORE_METHOD_CONTRACT.json). Every discovered public method is assigned read, deferred mutation or client-local-only responsibility.

| Store | Read projection methods | Deferred mutation methods | Local-only |
|---|---|---|---|
| profile |  | load_or_create, save |  |
| memory | list_all, get | add, propose, confirm, update, delete |  |
| memory_settings | load | update |  |
| growth | list_all, summary | record_event |  |
| approvals | get, list_pending | propose, decide, consume |  |
| sessions | get_session | save_session, reset_session |  |
| experience | list_all, recent | add |  |
| skills | confidence, find_matching_skill, list_skills | record_outcome, learn_skill, record_failure |  |
| history | get_session, list_sessions | append_turn, annotate_latest_turn, delete_session |  |
| files | get, list_for_session, references_for | save, delete | path_for |
| graph | get_node, get_node_by_external_ref, list_nodes, get_edge, list_edges | upsert_node, delete_node, upsert_edge, set_edge_status |  |
| evidence | get, query, resolve | add |  |
| operations | get, list_all, recovered_pending | create, mark_outcome_unknown, complete, claim_completion |  |
| external_capabilities | state_is_readable, get, list_all | register_descriptor, replace_qualified_descriptor, configure, authenticate, report_health, enable, disable, remove |  |
| connections | get_service_descriptor, state_is_readable, get_status, list_services | register_service, connect, disconnect |  |
| credentials |  |  | set_credential, get_credential, has_credential, delete_credential |

Profile `load_or_create` is a mutation because it writes defaults; session `get_session` may create an in-memory session but does not persist it. Snapshot reads are exact, bounded client projections, not generic server-side method invocation. File `path_for` and credential methods never cross transport. Approvals and external capability projections are untrusted private context; they cannot create server grants, qualification or consent.

## Versioned wire schemas

All schemas are strict (`extra=forbid`), version `uri.client.v1`; booleans are not integer versions. IDs use UUID validation but are never authority. Snapshot binding includes server/client/principal/session IDs derived or checked against an authenticated pairing. Each read names an allowlisted store/read method, JSON arguments and keyword arguments, result projection, nonnegative store version and SHA-256 result digest. Its query digest binds store/method/arguments. Missing reads raise typed `needs_context`; no ambient store or default result is substituted. Context maximum is 256 KiB; API/frame maximum 2 MiB. Credential/path-bearing field names and absolute filesystem paths are prohibited in transferred projections. Existing store serialization is used client-side; no arbitrary Python class deserialization is allowed.

Mutation sets contain the same binding, operation/idempotency IDs, typed store/write method and arguments, base store version, previous projection digest and payload digest. They are proposals until client scope/consent validation and successful CAS. Pending mutations do not imply persistence. Client receipts bind operation, mutation digest, committed versions and verified result; the server cannot report saved before receipt. Unsupported or missing projections remain explicit.

## Authentication and authority

Local current-account provisioning binds a client installation to a principal and server, stores only pairing/token hashes on the server, and writes raw credentials only to DPAPI-protected client storage. Reuse `AuthSessionStore` for high-entropy principal and paired-session tokens, expiry and revocation. New session acquisition requires both an existing principal bearer and separate pairing proof. Self-reported `device_id` is never binding. Bound principal role/mode and explicit grants originate in developer provisioning/control records, never request context. Existing resolver intersection and gates remain authoritative; missing explicit new-surface grants mean empty grants. Remote binding remains unsupported.

## Composition, lifecycle and compatibility

A separate opt-in composition factory exposes the paired routes using the existing FastAPI/uvicorn stack and Core modules; it is not a second reasoning engine or framework. It must not import legacy `server.py`, construct private stores, or run user migration. Legacy app/default launch behavior remains intact; new classified client routes mounted there fail closed unless the explicit paired service is installed. C1 compatibility composition and manifest remain identifiable.

New turn state is ephemeral, client/session-bound, at most four active turns and one per client session, with 15-minute idle/60-minute wall expiry. Minimal durable control metadata contains only binding/request/receipt hashes, versions, operation states, expiry and idempotency metadata. Private responses/context remain memory-only and client-owned durably. Restart reports context required or outcome unknown; it never replays uncertain side effects. Exact retries while context is live return the previous envelope; reused keys with different payload fail conflict.

C2 establishes pairing, snapshots, strict state ports, continuation/cancellation and minimal control records. C3 implements worker transactions/launcher. C4 adds qualified ticket/claim/receipt transport. C5 wires the existing canonical reasoning/gates and result feedback to those ports. C2 must not claim completed inference, harness execution or client persistence before their owning slices.

## Persistence, rollback and validation gates

Retain existing JSON/JSONL/SQLite formats and validators. A client journal durably records intent before changes; recovery reconciles incomplete operations without replaying external side effects. CAS covers all affected store versions under one client writer. Cross-store crash atomicity is not assumed: journal recovery is mandatory. Graph writes retain SQLite transaction behavior. Originals are never copied or migrated in these slices; only fresh synthetic roots are provisioned.

Source checkpoints are hashed Git dirty overlays on exact accepted HEAD, with no commit/release authority used. C1 checkpoint archive: work/c1/checkpoints/c1-provisional-source.zip, SHA-256 6af55603b8feb9b3dfa8f96f4c745994a46a4560ae8c5034bdf13390ce5e460d. Rollback restores into a new isolated root, preserves pending receipts/newer schemas, and never changes legacy installation or replays unknown operations.

C2 gates: malformed schema/scope/digest/unknown fields rejected; anonymous/invalid/expired/stale pairing denied; same-account clients cannot read each other’s session/graph/files/approvals/receipts; missing reads yield needs_context; writes yield mutation proposals only; request replay/version conflict/cancellation/expiry/restart tested; no private store constructed by new server; existing authorization/approval/canonical/ARN/Graphify regressions retained. Later full canonical-loop and live UI gates remain mandatory for C5/C6; no model or adapter is qualified by schema tests.

## Explicit implementation amendment — C3 signature validation

Actual SessionManager.save_session accepts only a session ID; transporting that call alone would silently lose state changes. Mutation now permits a digest-bound serialized replacement only for this exact method, validated against SessionState fields and binding and decoded with existing fact codecs. Profile load_or_create is served as a read-only _load projection after client-owned bootstrap initialization; the server cannot trigger default creation. ConnectedServiceStore.connect accepts credential material and is therefore client-local-only, not a wire mutation. FileStore.save receives bounded base64 bytes plus content SHA through the existing validator. These are explicit codec/ownership corrections, not changes to execution authority or persisted store formats. The machine matrix is authoritative for the corrected dispositions; the earlier profile row is historical.
