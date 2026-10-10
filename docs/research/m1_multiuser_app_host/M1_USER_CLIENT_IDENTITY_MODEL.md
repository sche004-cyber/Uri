# M1 user, client and session identity model

**Status:** research and planning only. This report extends `M1_THREE_USER_SERVER_ARCHITECTURE.md` §3 (identity
propagation) with an explicit data model and security tests. That section remains the summary; the identity details
live here.

## 0. Acceptance criteria (set before drafting)

- **IA-1.** Existing identity code in Line A and Line B is inventoried and reused before anything new is proposed.
- **IA-2.** User, Client and Session are distinct identifiers with explicit binding rules.
- **IA-3.** The owner is identified only by an authenticated role, never by a special client, device or ambient
  fallback.
- **IA-4.** Every execution path (storage, harness, browser, plugin, scheduler, app) carries the authenticated
  principal.
- **IA-5.** A test exists for each listed attack, with cloud or Windows labelled.
- **IA-6.** Migration keeps existing tokens, data and the paired-client contract working, or states the break
  explicitly.
- **IA-7.** R8/H-1 is resolved with evidence, not inference.

## 1. What exists today (re-verified at `54ad7be`)

### 1.1 Identifiers

| Identifier | Line A (classic server) | Line B (paired Working System) | Evidence |
|---|---|---|---|
| **User ID** | `user_id` = uuid4 per account, created at signup. Users are stored in `uri_workspace/user_accounts.json`. Every per-user path goes through `user_scoped_path`, which accepts UUIDs only. | `principal_id` = any UUID set at provisioning. **Not linked to the Line A account store.** | `uri_core/core/user_accounts.py`; `portable_paths.py`; `uri_core/core/client_pairing.py:66-83` |
| **Role** | `USER` / `ADMIN`. The first account is ADMIN. `require_admin` is enforced on 6 routes. | **Hard-coded `"USER"`** per pairing | `user_accounts.py:208-217`; `authorization.py`; `client_pairing.py:79` |
| **Client / device ID** | `device_id`: **client self-reported, optional, never shape-validated, carries "no authentication or authorization meaning"**. It is only a grouping label on a session. | `client_id`: a real registered client. Provisioning creates a pairing token plus a principal token. `resolve(token, claimed_client_id)` rejects a token used under another client id, and rejects a pairing whose principal differs. Secrets are DPAPI-protected (Windows). | `server.py:1136-1153`; `auth_session.py:101-188`; `devices.py`; `client_pairing.py:85-130` |
| **Session ID** | The bearer token (hashed at rest) with a `session_ref`, 24 h fixed TTL. The conversation `session_id` is a separate concept (`state.py`). | Paired session token from `acquire()` | `auth_session.py:77,134-201` |
| **Install identity** | `portable_identity.json`: a per-install `user_id`, plus a runtime `device_id`. The ambient (no-login) state is migrated **into this install user's directory at startup**. | Server identity `server_id` with an Ed25519 proof | `identity.py:47-91`; `server.py:809-864`; `runtime_identity.py` |

### 1.2 Requirements already satisfied

| # | Requirement | State | Evidence |
|---|---|---|---|
| 1 | Stable User ID | **Met** (Line A) | uuid4, UUID-validated paths |
| 2 | Unique Client ID per installation | **Partly.** Line B: met. Line A: `device_id` is an unauthenticated label. | above |
| 3 | Session ID per authenticated session | **Met** | `auth_session.py` |
| 4 | Each Client ID bound to one User | **Line B met** (`pair["principal_id"]`). Line A: a `device_id` can appear under several users, with no binding. | `client_pairing.py:117` |
| 5 | Owner by role, not by client | **Partly.** Role ADMIN exists, but the **ambient fallback maps no-login requests to the install user's data**, which in practice is the owner's (R1). | `server.py:653-677` |
| 6 | Multiple devices per user | **Met** (several sessions per user) | `test_devices.py`, `test_multi_client_runtime.py` (RUN pass) |
| 7 | Ordinary clients cannot inherit owner data | Met for logged-in users. **Violated for requests without a header** (R1/R2). | — |
| 8 | Every execution path bound to the principal | **Partly.** Tools get `principal` (`orchestrator.py:2641-2642`). Harness tickets carry `principal_id` (`uri_supervisor_bridge/authority.py:57-58`). The scheduler is one principal per instance, but its default owner is the literal string `"owner"` (`uri_scheduler/service.py:49`). Multi-action Gmail ignores the user (R3). Approved actions fail (DEF-H1, §2). | — |
| 9 | Server validates identity, client, session and permission | User and session: met. Client: Line B only. Permission: met for logged-in users. | — |
| 10 | Reject unauthenticated requests | **Not met** (R1, intentional legacy behaviour, `URI_M22_ARCHITECTURE.md` §20.7) | — |
| 11 | Device registration, listing, revocation, lost-device removal | Listing and revocation by `device_id`: **met**. Registration: **missing** (any login creates a "device"). Lost-device removal: revoking the device id ends its sessions, but a thief can log in again with the password. | `devices.py`; `/auth/devices` routes |
| 12 | Clients cannot supply arbitrary User IDs | **Met.** No Line A request body has a `user_id` field; identity comes only from the token. Admin routes take a path `user_id` and are admin-only. The scheduler refuses `PRINCIPAL_MISMATCH`. | grep of `BaseModel` fields in `server.py`; `SCHEDULER_ARCHITECTURE.md:77` |
| 13 | Shared Core, Brain and harness; private data | Shared Core and Brain met. Private data met for logged-in users. Harness sharing needs P1-6. | — |
| 14 | Preserve server/client contracts | Line B paired contract is frozen and loopback-only | `runtime_identity.py:313` |

## 2. DEF-H1: approved actions lose the principal (resolves suspected R8)

**Evidence: `COMPLETED_WITH_RESULT`, component level.** A probe used the real `ApprovalGate`, `ApprovalStore`,
`CapabilityRegistry` and `PrincipalContext`, plus a recording dispatcher, on tool `gmail_create_draft`
(`evidence/CLOUD_TEST_EVIDENCE.md` Run 4).

| Case | Result |
|---|---|
| No principal (ambient) | Approve → executes |
| Principal in kwargs (this is what the orchestrator passes for logged-in users, `orchestrator.py:2641-2642`), same gate | Approve → **`error`**: "approved arguments do not match the arguments requested for execution". **Not executed.** |
| Principal in kwargs, fresh gate on the same store file | Same error. Not executed. |

The persisted `arguments.principal` is a plain `dict`.

**Mechanism:**
1. `approval_store._save` serializes arguments with `asdict`, turning the `PrincipalContext` into a dict.
2. `ApprovalGate.decide` consumes `record.arguments` as loaded from disk (`approval_gate.py:280-301`).
3. Their fingerprint no longer matches the one computed at proposal time, so the action fails closed.
4. Even if it did not, the dispatcher reads `getattr(principal, "user_id")` (`dispatcher.py:80-81`), which is `None`
   on a dict. That would select the install-wide Google token.

**Conclusion and correction record:**
- The round-1 suspicion R8/H-1, "may execute with the install-wide token", is **disproved for this path**.
- The actual defect is **DEF-H1**: approval-gated actions proposed with a principal **cannot execute**. Logged-in users
  cannot complete Gmail drafts, Drive uploads or any future approval-gated plugin action.
- It fails closed, so there is no leak. But it blocks every consequential M1 feature.

**Not verified:**
- The full HTTP `/ask` → `/approve` flow. `/approve` uses the same per-user orchestrator (`server.py:2114-2152`), so the
  same failure is expected. Confirming it is P0-2.
- Why the existing approval tests pass: they do not pass a principal. That is an inference from the probe, and their
  fixtures have not been read.

**Repair direction** (frozen, under P1-5):
- Never persist live identity objects in proposal arguments.
- Store `principal_user_id` (a UUID string) as a first-class field of the `ProposedAction`, outside the fingerprinted
  arguments.
- On `decide`/`consume`, require `record.principal_user_id == current principal.user_id`. Refuse on mismatch.
- Re-inject the live `PrincipalContext` from the *current authenticated request* into dispatch. Never rebuild it from
  storage.

## 3. Target model

```
User (user_id UUID, role ∈ {ADMIN, USER}, status ∈ {active, suspended})
  └─ Client (client_id UUID, owner user_id, name, platform, registered_at, client_secret_hash, status ∈ {active, revoked, lost})
       └─ Session (session_id = token hash ref, client_id, user_id, issued_at, expires_at, last_seen, revoked)
Principal for every request = (user_id, role, client_id, session_id, mode)   ← resolved ONLY by the server
```

### Binding rules

| Rule | Implementation |
|---|---|
| A client belongs to exactly one user at a time | `Client.user_id` is set at registration. Re-assignment means revoking the client and registering a new `client_id`. |
| Owner = role ADMIN | Never derived from the client, the device or "no login". The owner's devices are ordinary clients of an ADMIN user. |
| Session ⊂ client ⊂ user | A session is valid only if its client is `active` **and** `client.user_id == session.user_id`. This reuses Line B's check (`client_pairing.py:117`). |
| No anonymous principal on the network path | The gateway refuses (P1-1). After P1-5, Core refuses too: the ambient branch is reachable only from the local CLI and tests, behind an explicit `URI_LOCAL_AMBIENT=1`. |

### Client registration (reuses Line B pairing semantics on Line A)

1. A logged-in user, or the admin for that user, requests a **registration code**: single use, 10-minute lifetime.
2. The new device presents the code plus a device-generated public key, or receives a client secret.
3. The server creates `client_id` and stores the secret hash, bound to `user_id`.
4. Login from that device thereafter sends `client_id` + proof. The proof is an HMAC of a server nonce with the client
   secret. A signature from a key held in the OS keystore is the later, preferred option.
5. **Unregistered device:** the login is refused, or (configurable for the first M1 release) accepted with the device
   placed in `pending` until the user approves it from an existing client.
6. **Lost device:** mark the client `lost`. All of its sessions are revoked, and that `client_id` can never log in
   again, even with the right password.

## 4. Principal propagation (requirement 8)

| Path | Carried identity | Status after M1 |
|---|---|---|
| Storage operations | Broker call `{user_id, client_id, session_id, requester}`, resolved by the gateway and Core, never accepted from tools | Proposed (P2-1) |
| Harness jobs | `ExecutionTicket.principal_id` (exists). Add `client_id` and `session_id` for audit. The OS account comes from the user → account map (P1-6). | Partly exists |
| Browser sessions | Context or profile keyed `(user_id, task_id)` on the server; on the client, it is the client's own user | Proposed (P4) |
| Plugin calls | ConnectorHost process per `(user_id, connector)`. The credential key is `(user_id, connector, group)`. | Proposed (PL-1) |
| Scheduler jobs | One instance per user. Its `--owner` **must be the user's UUID**, not the literal `"owner"`. Its API token is a dedicated service token for that user. On startup reconcile, jobs resume only under the instance owner, and a job whose stored owner ≠ instance owner is quarantined (`NEEDS_ATTENTION`). | Proposed (ID-4) |
| Hosted-app sessions | App instance per `(user_id, app_id)`. Broker token scoped to that pair and to the client session that opened it. | Proposed (P5) |
| Approvals | `principal_user_id` field (§2 repair) | Proposed (P1-5 T1) |

## 5. Migration compatibility

| Item | Plan |
|---|---|
| Existing Line A tokens (no `client_id`) | Accepted until expiry, at most 24 h, as `client_id = legacy:<device_id or none>`, in a `legacy` client state. Clients must register on the next login. The flag `URI_REQUIRE_REGISTERED_CLIENT` turns on enforcement after a grace period. |
| Existing `device_id` values | Become the display name of the auto-created legacy client. They are not trusted as identifiers. |
| Ambient (install-user) data | Already migrated into `users/<install_user_id>/` at startup (`server.py:809-864`). **The owner decides (D-13)** whether that install user *is* the owner's account. If so, link `install_user_id` to the owner account's `user_id` by a one-off admin migration that renames the directory and has a backup. Otherwise it stays a dormant profile reachable by nobody over the network. |
| Line B paired clients | Unchanged: loopback, frozen. Long term, `principal_id` should be an account `user_id` and the role should come from the account. That is a frozen change and is deferred. |
| Flutter clients | Gain registration UI and secure storage for the client secret (D-7). The existing `device_identity.dart` id becomes the client's display id. |
| Tests that assert ambient fallback (`test_no_authorization_header_falls_back_to_legacy_ambient_*`) | Kept for local mode, and inverted for network mode (§6, ID-T9) |

## 6. Security regression tests

Each test must fail on the current base where it targets a defect.

| ID | Attack or case | Expected after M1 | Base behaviour today | Where it runs |
|---|---|---|---|---|
| ID-T1 | Ordinary user calls owner-only actions (`/admin/users`, grants, skill enable, server settings, published folders) | 403 | 403 for the 6 ADMIN routes (RUN pass) | Cloud |
| ID-T2 | User 2 reads or acts on User 3's files, memory, plugins, credentials, approvals, scheduler jobs or app state | 404-shaped refusal; nothing returned | Files and memory isolated (RUN). Plugins and credentials per user (M33 tests). Scheduler and apps are new. | Cloud |
| ID-T3 | Client ID substitution: a session token used with another client's `client_id`; a `client_id` registered to user 2 presented with user 3's token | 401 or 403 | Line B rejects (`client_pairing.py:117`). Line A has no client binding. | Cloud |
| ID-T4 | Expired, revoked or logged-out session; session of a `lost` or `revoked` client | 401 | Expired and revoked are already 401 (RUN `test_auth_session.py`). Client states are new. | Cloud |
| ID-T5 | Unregistered device logs in with a correct password | Refused or `pending` | Accepted today | Cloud |
| ID-T6 | Harness job: the principal of the ticket, the supervisor task and the executed OS account all equal the initiating user; tampered `principal_id` → refused | Equal / refused | Ticket binding exists; OS account is new | Cloud (ticket), **Windows** (OS account) |
| ID-T7 | Scheduler restart: a job whose stored owner ≠ instance owner is not resumed; the instance cannot run with `--owner owner` | Quarantined / refused | The default owner string is `"owner"` | Cloud |
| ID-T8 | Approved action keeps the principal through persist and restore, and executes under the same user. A principal mismatch at `decide` → refused. | Executes as the same user / refused | **DEF-H1: fails** (RUN, Run 4) | Cloud |
| ID-T9 | Missing, malformed or invalid `Authorization` on every non-PUBLIC route via the gateway (and Core in network mode) | 401, never ambient | **Ambient served** (R1, asserted by existing tests) | Cloud |
| ID-T10 | Client-supplied `user_id` in any body or query (fuzz all routes) | Ignored or refused | No such field exists (grep) | Cloud |
| ID-T11 | Suspended user's existing sessions | 401 on the next request | `status` unused | Cloud |
| ID-T12 | Admin cannot read another user's private stores or tokens through any route | Refused | No such route exists today; guard against new ones | Cloud |

## 7. Slices

These IDs are registered in `M1_IMPLEMENTATION_SLICES.md`.

| ID | Slice | Frozen? | Where |
|---|---|---|---|
| ID-1 | Characterization tests ID-T3, T5, T7, T8, T9 failing on the base (part of P0-2) | No | Cloud |
| ID-2 | Gateway enforcement: reject unauthenticated; principal-keyed limits (part of P1-1) | No | Cloud |
| ID-3 | Client registry + registration codes + client proof + lost-device state on Line A | **Yes** (`auth_session`, server routes) | Cloud; Flutter part on PC |
| ID-4 | Scheduler owner = user UUID, per-user service token, owner-mismatch quarantine | No (`uri_scheduler/` is not protected) | Cloud |
| ID-5 | DEF-H1 repair: `principal_user_id` field, re-injection, mismatch refusal (P1-5 T1) | **Yes** | Cloud |
| ID-6 | Install-user ↔ owner-account linkage migration (D-13) | **Yes** | Cloud (logic), PC (real data) |
| ID-7 | Harness OS-account binding check (ID-T6, Windows half) (with P1-6) | Yes | **Windows** |

## 8. Cloud vs Windows validation

- **Cloud (Linux):** everything except DPAPI-protected client secrets, OS-account execution and the Flutter
  registration UI. The Line A identity suites already run here (315 pass).
- **Windows PC:**
  - ID-7;
  - DPAPI and keystore storage of client secrets;
  - the Line B paired regression (frozen chain);
  - Flutter registration and lost-device flows on real devices;
  - the D-13 migration against the real `uri_workspace` (with a backup).
