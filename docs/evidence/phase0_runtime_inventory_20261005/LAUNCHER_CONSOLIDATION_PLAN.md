# URI Launcher Consolidation Plan — Phase 1

Date: 2026-10-05. Status: PROPOSED. No existing shortcut, task, launcher, service or model configuration is changed in Phase 1.

## Existing launch authorities to preserve

Desktop and Start Menu URI shortcuts target `uri-m37-m39-integration/Launch URI.bat`. `URIServer` logon task targets master `scripts/run_uri_server.py` on 8000. The 8021 harness composition belongs to another worktree. Existing launch scripts, task registration, shortcut files, state roots and builds are preservation artifacts. Keep their entry points callable under their original identity until a separately authorized cutover.

The main launcher uses generic health/process-name reuse; the integration desktop launcher already checks exact process/script/socket owner and checkout identity. Reuse those stronger checks. Its experimental warm-up/residency defaults are a separate policy and must not be copied into the authoritative server by default.

## Authoritative launcher designs

Two independent entry points, no combined client-specific Core server:

```text
URI Server launcher -> explicit server manifest -> one Core server process
URI Client launcher --client <installation-id> -> that client's Flutter UI + private worker
```

Client launch never installs/reconfigures a Windows server task, chooses a checkout implicitly, launches Ollama, warms a Brain, or changes another client's preferences. If the server is unavailable, the UI reports unavailable and offers the explicit developer server-start action; automatic bootstrap is deferred.

Initial implementation is an opt-in isolated development launcher alongside existing entry points. The names/locations below describe future files in the isolated worktree, not files currently created or installed:

- `scripts/uri_server.ps1`: validate/start/status; future explicit install action only after separate deployment authorization.
- `scripts/uri_client.ps1`: launch/status for one installation; no server lifecycle ownership.
- `scripts/uri_server_manifest.schema.json`: strict server manifest contract.
- `scripts/uri_client_manifest.schema.json`: strict client manifest contract.

Stop/restart controls are not part of the first implementation slice. When later added, require exact owned process tree/socket/generation identity; never a bare python/uri_ui name or stale PID. Existing stop launchers stay unchanged.

## Server manifest

Fields: schema version; stable server installation ID; exact checkout/source checkpoint and dirty-source manifest digest; composition ID; contract version; absolute entrypoint; absolute interpreter; dependency manifest digest; explicit server state root; loopback host/port; minimal control-ledger root; public catalogue; log policy; lazy model policy. No credential values in this manifest.

Target defaults: `127.0.0.1`; final installed server default 8000 only after cutover; isolated integration validation default 8031 if free. Port conflicts abort without stopping or adopting existing listeners. The phase's prepared worktree will not bind any port. A changed port does not create a new authority; server ID/manifest remain the identity.

Server cwd is the explicit server state root, not whichever repository terminal happens to be current. Imports use the explicit source root. Server state contains pairing/operation metadata and public catalogue, not existing client databases. Legacy ambient-store compatibility runs only in its existing composition; the new server surface may not create private stores accidentally at startup/import.

This is the final server contract. C1 identity/launcher validation may temporarily launch the accepted compatibility composition with every legacy path contained in a fresh synthetic fixture root. Accepted lifespan currently includes user-store initialization and legacy copy migration, so cwd alone is not proof of containment: trace all constructors/default paths and inject explicit roots before launch. Synthetic compatibility stores are declared test fixtures, not independent client persistence. C2/C3 remove that dependency from the final client-facing composition. If containment requires broader refactoring, revise the slice before implementation rather than weakening the target ownership rule.

### Startup algorithm

1. Validate manifest schema, source/interpreter availability, permitted host and dependency identity. Fail with safe diagnostics before creating runtime state if invalid.
2. Acquire `Local\URI_Server_<server-id>` mutex. A second launch waits boundedly, then rechecks identity.
3. Inspect listening socket and owning process executable/argument/start time. A PID alone never establishes identity.
4. If the expected server exists, verify `/runtime/identity` fields and control proof; report already running. Do not accept generic `/health` success.
5. If a foreign listener or mismatched manifest exists, report conflict and abort without signaling it.
6. Launch exact interpreter/entrypoint with explicit source/state/manifest arguments, detached and hidden. No environment inheritance of client API keys. Allowlist required runtime/system environment fields.
7. Wait boundedly for that process to own the socket and report expected identity/readiness. Record PID/generation only then, using atomic local bookkeeping.
8. Release mutex and report status. Timeout identifies the failed attempt accurately; it is not readiness.

## Identity and readiness API

`GET /health` stays unchanged for compatibility. Add `GET /runtime/identity` as public **minimal metadata only**: server ID, composition ID, contract version, source checkpoint and build-manifest digest, process generation. No cwd/source paths, user IDs, tokens, client list, private model configuration or credential state.

Add `GET /runtime/status` using existing authenticated-principal enforcement: identity plus readiness categories and safe failure codes. Full paths belong in local developer diagnostics, not public HTTP output. Route table entries and enumeration tests must cover both routes.

These new routes are implementation scope for the next milestone, not currently deployed endpoints. Launcher identity uses both socket-owner provenance and a locally provisioned control credential or signed identity challenge; a malicious loopback responder must not be trusted solely because it echoes a known server ID. A local developer process under the same Windows account is still outside the deferred adversarial OS-user threat boundary.

Selected identity proof: a locally pinned Ed25519 public key, using the existing cryptography dependency. The server signs a supplied nonce together with its ID/generation/manifest digest. The private signing key is server-owned and Windows-protected; the manifest holds only its public fingerprint. Pairing/bootstrap is explicit local developer provisioning. Never derive an identity proof credential from stored bearer-token hashes.

Readiness distinguishes HTTP accepting requests, public catalogue ready, selected model availability, paired client availability, qualified adapter availability and degraded optional services. A missing optional Brain/Edge/Ollama is not server-start failure. No model-generated health probe or warm-up occurs on startup. Detailed readiness can mark a selected route unavailable honestly.

## Client manifest and launch algorithm

Client manifest: schema version; immutable installation ID; paired server ID/address/contract range; exact UI and private-worker binaries/digests; private data root; workspace handles; private config root; protected-session store locator; model preference locator; qualified native harness profile locator; log policy. Locators contain no token/password values. Clients A and B must have distinct roots and native profile scope where the adapter supports qualified isolation.

Acquire `Local\URI_Client_<client-id>` mutex; locate only this client's exact UI/worker command, executable, start time and generation. Focus that UI when present. Reject stale PID reuse. Validate the saved server identity before sending its pairing token. Start the worker in the client root with a bounded, framed stdio channel and start the UI with its manifest. Treat partial UI/worker startup as an explicit recoverable state; do not attach to another checkout's same-named UI.

Existing SharedPreferences namespace/session/server URL are retained for the legacy desktop. New clients use installation-specific roots and keys; they do not read or overwrite `com.example/uri_ui/shared_preferences.json` implicitly. A deliberate settings import is a later migration action, never launch behavior.

Model selection and harness accounts are client configuration. Client launch does not require a resident Main Brain. External-harness-only clients may connect to a server with no model daemon running. Native account availability is discovered truthfully without dumping authentication metadata or activating tasks.

## Deployment stages and rollback

1. Implement/test identity and opt-in launcher in the isolated worktree with synthetic state on a free development port.
2. Verify wrong-listener, concurrent launch, unrelated process, stale/reused PID, missing dependencies, readiness timeout and no-model startup. Existing desktop routes remain untouched.
3. Qualify client manifests/worker lifecycle after client-state contracts exist. Client launcher initially uses a synthetic installation and independent namespace.
4. Only after client/database/adapter/UI validation, seek explicit cutover authorization for the production/default shortcut and `URIServer` task.
5. Preserve old entry points with distinguishable legacy/development identities, not deletion. Save task XML/shortcut hashes before any future registration change.

Rollback restores an earlier opt-in manifest/new installation, without changing production/default entry points. Later authorized cutover rollback uses the preserved task XML/shortcut files and exact source/state manifest, with listener ownership checked first. Do not execute restore commands against occupied production roots, migrate databases backward, revoke native accounts, or replay uncertain side effects.

## First milestone acceptance

The first slice adds runtime identity and the server launcher only; it does not create private clients or transport adapters yet. The client launcher design is ready, but its implementation depends on client-state and worker contracts. This avoids launching a UI that falsely claims client-owned persistence while still using backend stores.

Pass criteria: one intended dev backend from concurrent launches; correct exact source/state/interpreter identity; foreign listeners untouched; status never claims ready on generic health alone; no implicit production task/shortcut/config changes; no Brain warm-up; restart generation distinguishable; existing Core auth/route/approval regressions pass; controlled live dev identity/start behavior works. Record the exact source/build and residual failures. Independent audit/release requirements remain applicable.
