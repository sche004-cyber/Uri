# URI Milestone 1: three-user prototype and App Hosting Foundation. Architecture audit and plan

- Baseline: `54ad7be72847675ae662e2fd4f3b3b9d253e6d4e`, the tip of `integration/git-sync-20261008` on
  `github.com/sche004-cyber/Uri`.
- Status: research and planning only. No implementation is authorized by this document.
- Evidence grades used below:
  - **CODE**: read in source at the baseline.
  - **RUN**: `COMPLETED_WITH_RESULT` test run in this cloud session.
  - **DOC**: a project record, not re-executed here.
  - **EXT**: an external provider page. "primary" means fetched live; "secondary" means from search results only.

---

## 0. Baseline identification

| Fact | Evidence |
|---|---|
| The authoritative repository is `sche004-cyber/Uri`. `sche004-cyber/uri-agent` is a historical mirror: `master` = `e8e3b65`, unchanged since 2026-09-20. | `docs/governance/consolidation/URI_CANONICAL_BRANCH_DECISION.md` §1; `git ls-remote` on both remotes |
| The operative canonical line is `integration/git-sync-20261008` = `54ad7be` (2026-10-09). It is identical to `integration/ti-on-ws-hardening-20261009`, and it contains `integration/ws-hardening-20261009`, `integration/working-system-20261008` and `phase/text-intelligence` (checked with `git merge-base --is-ancestor`). | git; `docs/integration/ti_ws_20261009/TIWS_INTEGRATION_RECEIPT.md` §1 ("Canonical branch: `integration/git-sync-20261008`") |
| The owner authorized fast-forwarding that branch with accepted work. **Formal promotion to `main` is still PROPOSED.** | `docs/governance/consolidation/URI_UNIFIED_CONSOLIDATION_PLAN.md:96`; `URI_CANONICAL_BRANCH_DECISION.md:3` |
| `Uri` has no `master`. Its GitHub default HEAD is the stale `claude/edge-harness-minimum-0oj7fe` (`610c8f8`, 2026-09-28, classified HISTORICAL). The session branch `claude/uri-milestone-1-audit-c4sl13` points at the same commit and is not the baseline. | `git ls-remote --symref origin HEAD`; `URI_CANONICAL_BRANCH_DECISION.md:75` |
| Non-canonical lines, kept as tagged donors or preserved, never merged: <br>• desktop mainline `experimental/desktop-recovery-repair` `eb73693` (M36-M39, INT-ARN-1, the UI the owner currently uses) <br>• superseded base `62d564c` <br>• the six `preserve/*` branches <br>• side branches: dynamic planning `e4dea8c`, dictation `f1e13e9`, harness-first `86de4c0`, edge-pair `e0950d4` NOT QUALIFIED, `wip/batch3-codex-partial` unreviewed | `docs/governance/git_sync_20261008/GIT_SYNC_AUDIT.md` §4-§6 |
| Production is still the **legacy** `\URIServer` on port 8000. There has been no cutover (CUT-1, owner decision). The committed canonical branch cannot run under the frozen launcher as is: `runtime_identity.py` requires HEAD `e8e3b65`, so the runtime is a materialized overlay (CONS-7). | `docs/working_system/WS_REMAINING_LIMITATIONS.md:11,19`; `URI_CANONICAL_BRANCH_DECISION.md` §3 |
| **Frozen prefixes.** They must not differ from `037229c` without authorization: `uri_core/`, `uri_supervisor/`, `uri_supervisor_bridge/`, `uri_harness_adapters/`, `model_lab/integration/`, five runtime scripts, five Dart runtime files, and `.gitignore`. Runtime v1 itself is frozen too. | `scripts/ws_frozen_check.py:18-26`; `model_lab/URI_RESIDENT_INTELLIGENCE_RUNTIME_V1_FREEZE.md` |
| No document in the tree defines a new "Milestone 1". This plan uses "M1" only for the owner's new assignment. | grep for `Milestone 1` (governance audit) |

**Unverified:** local work on the offline PC after `54ad7be`. The TIWS receipt §5 "Push record" is unfilled, and no
`TIWS_STAGING_RECEIPT.md` exists. Some staging or push work may exist only on the PC. **Effect:** this does not change
the architecture verdict. It does mean every slice must start by re-checking the canonical tip once the PC is back.

---

## 1. Current architecture and capability inventory

URI contains **two server lines** that share `uri_core/`.

**Line A: the classic multi-user HTTP server**
- Code: `uri_core/app/server.py` (FastAPI, 4,048 lines, 89 classified routes).
- Accounts, bearer sessions, per-user stores, grants and modes.
- The Brain is reached through `ModelRouter` and `provider_registry`. Every role defaults to Ollama `qwen3:14b`
  (`uri_core/model_providers/base.py:150`).
- This is the lineage of the production legacy server.

**Line B: the Working System**
- Composition: Phase 1 paired Core (`uri_core/app/paired_server.py`, `/client/v1`), Phase 2 supervisor and bridge,
  Operational Intelligence (`uri_operational_intelligence/`), and the Flutter Living UI.
- The resident Brain is **Runtime v1**: llama.cpp b11425 Vulkan with Qwen3.6-35B-A3B UD-IQ3_S on 127.0.0.1:18470.
- One owner per client root. Loopback only. The UI talks to a local stdio worker.

| Component | Where | Status at baseline | Evidence |
|---|---|---|---|
| User accounts (PBKDF2-SHA256 at 260k iterations; first account ADMIN, later accounts USER) | `uri_core/core/user_accounts.py` | IMPLEMENTED + TESTED | CODE; RUN (`test_user_accounts.py`, `test_m22_2_roles_sessions.py` pass) |
| Bearer sessions (hashed, persisted, 24 h TTL), per-device revoke | `uri_core/core/auth_session.py:77`, `uri_core/core/devices.py` | IMPLEMENTED + TESTED | RUN (`test_auth_session.py`, `test_devices.py`, `test_multi_client_runtime.py`) |
| Admin-only route guard (6 ADMIN routes) | `uri_core/core/authorization.py`; `uri_core/app/route_classification.py:69-76` | IMPLEMENTED + TESTED | RUN (`test_m22_3_route_authorization.py`, `test_m22_4_grant_endpoints.py`) |
| Per-user isolation for logged-in users: about 20 stores under `uri_workspace/users/<uuid>/` (profile, memory, sessions, history, uploads, graph, approvals, usage, provider keys, Google token, …) | `server.py` `_build_user_context` (350-582); `uri_core/core/portable_paths.py` | IMPLEMENTED + TESTED | RUN (`test_multi_user_isolation.py`, `test_m21_file_store_isolation.py`, `test_graph_isolation.py`, `test_usage_endpoints_isolation.py`, `test_m32_gmail_user_scoping.py`) |
| **Anonymous fallback**: a request with no `Authorization` header gets the shared ambient (owner) state | `server.py:653-677` | IMPLEMENTED BY DESIGN; **blocks a networked multi-user setup** | CODE (re-verified); asserted by `test_multi_user_isolation.py` |
| Capability grants ∩ mode ∩ registry | `uri_core/core/capability_resolver.py`; `approval_gate.py:119-125` | IMPLEMENTED + TESTED. Grants are skipped when neither principal nor grants store is set, which is the anonymous path. | RUN (`test_m22_4_capability_resolver.py`); CODE |
| Approvals (single-use, expiring, session- and fingerprint-bound) | `uri_core/core/approval_store.py` | IMPLEMENTED + TESTED | DOC/CODE |
| Bind safety (loopback default; non-loopback needs TLS or an explicit insecure override), CORS allow-list, login and signup rate limits, `/ask` size cap | `scripts/run_uri_server.py:72`; `server.py:962-997`; `uri_core/app/edge.py` | IMPLEMENTED + TESTED | RUN (`test_m22_3_bind_refusal.py`, `_cors`, `_rate_limiting`) |
| Gmail and Drive, per-user OAuth token (single-action tools) | `uri_core/services/gmail_service.py`, `drive_service.py`, `core/google_auth_common.py:19-32` | IMPLEMENTED + TESTED. Tokens are **plaintext JSON**. | RUN (`test_m32_gmail_user_scoping.py`); CODE |
| Google consent flow | `gmail_service.py:126` `InstalledAppFlow.run_local_server`; `server.py:3301-3386` loopback-only check | IMPLEMENTED. **Must be completed at the server PC.** | CODE |
| Google Calendar | — | **MISSING** | grep |
| Provider API keys (Fernet, per user) | `uri_core/core/provider_keys.py` | IMPLEMENTED + TESTED. **The default secret is a hard-coded string** (`server.py:37`, `run_uri_server.py:47-48`). | RUN (`test_provider_keys_boundary.py`, `test_m22_5_providers_endpoints.py`); CODE |
| Paired client surface (Ed25519 server proof, DPAPI secrets, pairing token) | `uri_core/core/client_pairing.py`, `app/client_routes.py`, `client_runtime/transport.py` | IMPLEMENTED + TESTED (Windows). **Loopback-only by frozen rule** (`runtime_identity.py:313`). Principals are not linked to accounts. | CODE; DOC |
| Runtime v1 Brain (Vulkan, AMD RX 7900 GRE 16 GB, single slot `-np 1`; `-np 3 -kvu` measured and rejected) | `model_lab/integration/local_brain.json`; freeze doc :34, :291; `uri_operational_intelligence/runtime_v1.py` | FROZEN. IMPLEMENTED; live only on the owner's PC. | DOC; CODE |
| Brain client (SSE, cancel, deadlines) and Brain host (lease held for the host's lifetime, no auto-restart) | `uri_operational_intelligence/brain_client.py`, `scripts/ws_brain_host.py` | IMPLEMENTED + TESTED (fake server) | CODE |
| GPU lease (machine-wide, exclusive OS byte lock, no queue or priority, `max_hold_s` reported only) | `uri_operational_intelligence/gpu_lease.py` | IMPLEMENTED + TESTED on Windows only. Not runnable in the cloud (`msvcrt`). | CODE; RUN shows the lease tests fail on Linux for `msvcrt` |
| Turn concurrency | WS worker refuses a second turn (`worker_bridge.py:176` `TURN_IN_PROGRESS`). Line A `/ask` is uncapped (default threadpool). D5 stream cap 8 (`stream_tool_loop.py:57`). D4 tool workers 4. | IMPLEMENTED. **No per-user fairness anywhere.** | CODE |
| Supervisor (durable attempts, SQLite admission pools with priority and aging, circuit breakers, named Job Objects with kill-on-close) | `uri_supervisor/` | IMPLEMENTED + TESTED (Windows). **No CPU or memory limits** (`winproc.py:267` sets kill-on-close only). | CODE; DOC |
| Supervisor bridge (signed Core `ExecutionTicket`, approval-digest binding, revoke-on-restart) | `uri_supervisor_bridge/` | IMPLEMENTED + TESTED | CODE; DOC |
| Harness adapters: Claude Code (`claude -p`, workspace-scoped file tools, Bash denied, budget cap) and Codex (`exec --sandbox workspace-write`); Antigravity refused; no Gemini CLI | `uri_harness_adapters/__init__.py`; `uri_core/client_runtime/harness.py` (bypass flags refused :33; API keys never forwarded :37) | IMPLEMENTED + TESTED (Windows). `default_registry()` qualifies nothing. | CODE (re-verified); `test_m31_harness_boundary.py` RUN pass |
| Per-client CLI homes (each client's own native login; `CODEX_HOME` pinned so that a "shared client authentication" is a stop condition) | `uri_supervisor_bridge/qualification.py:377-430`; `native_auth_probe` :454 never reads credential files | IMPLEMENTED. Live test needs the owner's login. | CODE (re-verified) |
| Process-tree containment | `uri_core/client_runtime/process_tree.py:168` (`WINDOWS_REQUIRED`); `uri_supervisor/winproc.py` | IMPLEMENTED, Windows only | CODE |
| Scheduler (persistent jobs; festival-GIF harness template; one owner per instance; bearer API on 127.0.0.1:18520) | `uri_scheduler/` | IMPLEMENTED + TESTED. Not activated (logon task not registered). Live Claude run BLOCKED (not logged in). | RUN (`tests/scheduler` 56 pass, 15 skip); DOC |
| A2UI (subset of A2UI v0.9.1, catalog `uri:a2ui/catalog/v1`, 13 components; URLs refused; action registry with named authorities; surface digest) | `uri_a2ui/`; Flutter `uri_ui/lib/living/a2ui/` | IMPLEMENTED + TESTED. **The only producer is the scheduler.** No webview or iframe by design. | RUN (`tests/a2ui` pass); CODE (`validate.py:19`) |
| External capability contract (in_process, cli, loopback-http transports; per-user operation and evidence stores) | `uri_core/external/` | IMPLEMENTED + TESTED offline. Its doc still says DRAFT. | CODE; DOC |
| Flutter client: classic HTTP (configurable URL, bearer, device id), paired stdio, scheduler HTTP | `uri_ui/lib/services/http_uri_client.dart`, `paired_runtime.dart`, `session_store.dart` | Windows IMPLEMENTED + TESTED (per project records). Android/web are scaffolding only. **Token stored in plaintext `SharedPreferences`.** | CODE; DOC. Flutter is not available in this cloud. |
| Remote access (Tailscale, WireGuard, reverse proxy) | — (one Dart comment mentions Tailscale relays) | **MISSING** | grep |
| App registry, hosted apps, plugin host | — | **MISSING** | grep |
| Office backend `uri_v1/office` (M39 R0) | branch `claude/project-thread-uyzemj` and donor `eb73693` only | Not in canonical. It is a file-run feature, not app hosting. | git |

---

## 2. Gap analysis against Milestone 1

| M1 requirement | What exists | Gap | Severity |
|---|---|---|---|
| Shared Core and intelligence | Line A Core is multi-user. Line B Core is single-owner. | Choose one front door. Line A is the only one with accounts. | Architecture decision D-1 |
| Shared local Brain with GPU scheduling | Runtime v1 (one slot); exclusive GPU lease held for the host's lifetime; WS worker refuses concurrent turns | Line A is not connected to Runtime v1 (no `18470` anywhere in `uri_core`). There is no per-user fair queue in front of the single slot, and no "Brain unavailable: GPU lease held by X" state for remote users. | High |
| Centrally installed harnesses | Adapters, supervisor and per-client CLI homes exist, but run on the **client side** as the **same Windows user** | Server-side per-user execution identity. Per-user native login for remote users. Remote progress and approval UX. | High (security and terms) |
| Equivalent capabilities for all three users | Grants default to the full registry; modes are per user | Mostly met for Line A capabilities. Harnesses, scheduler and A2UI are single-owner. | Medium |
| Individual conversations, memories, files, sessions, preferences | About 20 per-user stores, tested (315 pass in this cloud) | Shared leftovers: R3 (multi-action Gmail uses the install-wide token), R5 (shared temp folders), R6 (shared registries and logs), R7 (graphify index carries owner memory metadata), tier/mode reset bug | High (R3), Medium (others) |
| Individual Gmail, Drive and Calendar auth | Per-user Gmail/Drive tokens for single-action tools | R3. Plaintext tokens. Consent only at the server PC, one at a time. Any user can overwrite the shared OAuth client secret (`POST /connections/credentials`). **Calendar missing.** Google publishing-status limits (D-5). | High |
| Administrator-only server management | 6 ADMIN routes, `require_admin` | Signup is PUBLIC and open. No invite, suspension, role change, delete or password reset. `status` field unused. | High (with network exposure) |
| Independent client authentication | Bearer per device, revoke per device | Any request without a header is served as the owner (R1/R2). Token is plaintext on the client. Fixed 24 h with no refresh. | **Critical** |
| Remote access through a private network | Bind safety and TLS flags | No private-network layer; no proxy-aware client identity; rate-limit keys collapse behind a proxy | High |
| Server-managed application services | Supervisor (Job Objects), scheduler service pattern | No app registry or lifecycle; no CPU or memory limits | Medium (new foundation) |
| Clients display hosted applications via UI/A2UI | A2UI renderer, actions, authority, digest | Only the scheduler produces surfaces. No app→surface channel. Catalog too small for future Office (no table or rich text). | Medium |

---

## 3. Recommended three-user architecture

Principle: **put a thin, non-frozen boundary in front of the already-tested multi-user Line A Core.** Fix the remaining
leaks in frozen Core only through authorized, bounded repairs. Reuse Runtime v1, the GPU lease, the supervisor and A2UI
unchanged.

```
 three client devices (Flutter, classic HTTP client)
        │  HTTPS over the private network (Tailscale tailnet; TLS by `tailscale serve` or `tailscale cert`)
        ▼
 ┌──────────────────────── URI server PC (Windows, AMD 16 GB) ────────────────────────┐
 │ uri_gateway (NEW, non-frozen, Python, no new dependencies: FastAPI + httpx already  │
 │ in requirements)                                                                    │
 │   • requires a valid bearer on every non-PUBLIC route (closes R1/R2/R4)             │
 │   • blocks remote signup, OAuth authorize, credential upload, shadow-audit          │
 │   • ADMIN routes only from admin principals; optional tailnet identity binding      │
 │   • per-user in-flight cap + round-robin fair queue for Brain-bound turns           │
 │   • strips X-Forwarded-*, content-free audit log                                    │
 │        │ loopback only                                                              │
 │        ▼                                                                            │
 │ Line A Core: uri_core/app/server.py on 127.0.0.1 (FROZEN; repaired only by S3)      │
 │   per-user stores, grants, approvals, Gmail/Drive per-user tokens                   │
 │        │ provider "lm_studio" (openai_compatible) base_url → 127.0.0.1:18470/v1     │
 │        ▼  (configuration, not code: provider_registry.py:184-187 base_url override) │
 │ Runtime v1 Brain host (FROZEN; holds the machine GPU lease for its lifetime)        │
 │ Supervisor + harness adapters (FROZEN) → per-user Windows accounts (S7)             │
 │ App host (NEW, S8) → apps under supervisor Job Objects, UI only via A2UI            │
 └─────────────────────────────────────────────────────────────────────────────────────┘
```

**Why Line A rather than Line B as the front door**
- Line B's paired surface is loopback-only by a frozen rule (`runtime_identity.py:313`
  `NONPRODUCTION_LOOPBACK_REQUIRED`).
- Its principals are not linked to user accounts.
- It runs one worker per client root (L-MUTEX).
- Making Line B multi-user would mean changing several frozen files.
- Line A already has accounts, sessions, devices and per-user stores, all passing in this cloud.
- Long term (D-1), the owner may prefer to make Line B multi-user and retire Line A. M1 should not decide that silently.
  The gateway works in front of either line.

**Why a gateway rather than editing Core first**
- R1, R2, R4, open signup and the loopback-bypass risk can all be closed at the boundary with **no frozen-file change**.
- R3, R5, R7, plaintext tokens and the tier/mode bug cannot be closed at a boundary. They are grouped into one authorized
  frozen repair slice (S3).
- Until S3 lands, the gateway can mitigate R3 by **revoking the multi-action `Gmail` capability from non-owner users**
  through the existing `PUT /admin/users/{id}/grants`. Those users keep the per-user single-action Gmail tools. Whether
  that is enough must be verified by test S3-T2 before it is relied on.

**Brain sharing**
- Keep one resident model and one slot. Multi-slot `-np 3 -kvu` was measured negative on this card (freeze doc :291).
- Fairness lives in the gateway:
  - at most one Brain-bound turn per user in flight;
  - round-robin between users;
  - streamed queue position back to the client.
- When the GPU lease is held by a non-Brain workload, clients get a truthful `BRAIN_UNAVAILABLE` with the holder's
  purpose, never a silent hang. The `brain_client.py:182-185` comment notes that llama-server can withhold headers for
  minutes when queued.
- Ollama must not run beside Runtime v1 (GPU-2). Line A's Ollama default is therefore replaced per user by configuration.
- **Unverified:** whether Line A's `openai_compatible` adapter, tool calling and timeouts work against llama-server's
  `/v1` endpoint. This is PC-blocked live verification (S4).

---

## 4. Subscription-harness access and licensing assessment

| Question | Technically possible | Permitted | Source |
|---|---|---|---|
| One owner Claude Pro/Max login used by all three users through URI | Yes (a shared CLI home) | **No.** "You may not share your Account login information… You also may not make your Account available to anyone else." | EXT primary: anthropic.com/legal/consumer-terms |
| URI collecting or storing users' Claude.ai tokens and injecting them | Yes (`CLAUDE_CODE_OAUTH_TOKEN` is in `AUTH_VARS`) | **No** for a third-party developer: "may not collect, store, or intermediate Claude.ai credentials or session tokens — sign-in to a Claude account must complete through Anthropic's own flow" | EXT primary: code.claude.com/docs/en/legal-and-compliance |
| Each user signs in to the **unmodified** Claude Code binary with **their own** subscription, on a host that runs Claude Code for them | Yes (per-user CLI homes already exist) | **Allowed by the docs' wording:** "Nor does it prevent an end user from signing in to the unmodified Claude Code binary with their own Claude subscription, including where a platform hosts Claude Code". Note: offering Claude Code inside "products or services (e.g. hosted sandboxes)" requires the Commercial Terms. Whether a household server counts as such a "service" is **a legal-interpretation question for the owner (D-4)**. | EXT primary, same page |
| Unattended or scheduled harness runs on a consumer subscription | Yes (`claude -p` from the scheduler) | **Unclear / risky.** Consumer terms forbid automated access "except when you are accessing our Services via an Anthropic API Key or where we otherwise explicitly permit it". Advertised plan limits "assume ordinary, individual usage of Claude Code and the Agent SDK". Recommendation: unattended runs use an API key billed to their owner (the existing CLOUD policy), or run only when the user is present. | EXT primary (both pages) |
| One Codex/ChatGPT login shared by three users | Yes (one `auth.json`) | **No.** OpenAI's help centre says an account is for the individual who created it (secondary search summary; the openai.com pages were unreachable from this sandbox) | EXT secondary |
| Each user's own `codex login` in their own `CODEX_HOME` | Yes (already pinned per client: `qualification.py:377-390`) | Yes, as ordinary individual use. OpenAI says to treat `auth.json` like a password. Codex can use the OS keyring (`cli_auth_credentials_store`). | EXT secondary (developers.openai.com unreachable) |
| Gemini CLI with a personal Google login | — (no adapter exists) | Third-party sources report that personal-login access was retired in mid-2026 and that OAuth use through third-party tools violates the terms. **Unverified.** No effect on the verdict: nothing depends on it. | EXT secondary |
| Agent SDK / API-key route | Yes | Permitted and billed to the key owner. This is the compliant path for any URI-built (non-Claude-Code) agent and for unattended work. | EXT primary |

**Compliant design rules for M1, all already consistent with existing code:**
1. Use only the unmodified CLIs. Never pass bypass flags. This is enforced already by `harness.py:33,52`.
2. Each user authenticates natively, in their own CLI home, through the provider's own flow. The native-login hints in
   `AUTH_ACTIONS` already do this.
3. URI never reads, copies or injects subscription tokens. `native_auth_probe` already only runs `auth status`. **Drop
   `CLAUDE_CODE_OAUTH_TOKEN` from server-side forwarding** unless the owner decides otherwise (D-4). It is a frozen
   file (S7).
4. No shared login. The existing ISO-1 stop condition is extended to "per URI user", not just "per client".
5. Remote users run native login through the CLI's own device or URL flow (`codex login --device-auth`; `claude`'s
   URL/code flow). They do this in a terminal session under their own Windows account on the server. **URI does not
   relay the codes.** This keeps sign-in "through Anthropic's own flow" without interpretation risk.

**REA (Reverse Engineer Anything) assessment:** not warranted. Every URI component is source code. The only
undocumented surfaces are the providers' credential stores, and inspecting or reusing those would itself breach the
credential rules above. Use REA only if a future compiled third-party app must be hosted and has no documentation.

---

## 5. Minimal App Hosting Foundation

Reuse first. Every piece below already exists except the four marked NEW.

| Need | Reuse | NEW (smallest addition) |
|---|---|---|
| Register applications | External capability descriptor pattern (`uri_core/external/contract.py`, closed transport set) | NEW `uri_apphost/registry.py`: a signed, static `app.json` manifest. Fields: id, version, entry argv, transport (`stdio` or `loopback-http`), declared A2UI actions, requested URI services, resource limits. Owner-installed only, with the SHA-256 recorded (same idea as `verify_artifacts`). |
| Launch and terminate safely | `uri_supervisor` attempts + named Job Objects (`winproc.py`), admission pools, revoke-on-restart | NEW: set the existing unused Job limit fields (`JOB_OBJECT_LIMIT_JOB_MEMORY`, `ACTIVE_PROCESS`, CPU rate control). This is a frozen-supervisor change, or a non-frozen wrapper that applies limits to the job by name (D-6). |
| Present UI in URI Workspace | A2UI catalog, validator, digest, `A2uiHub`, workspace dock (`placement: workspace`). The scheduler's `a2ui_host.py` is the precedent producer. | NEW `uri_apphost/surface_bridge.py`: an app emits A2UI messages, which are validated server-side with `uri_a2ui.validate` before relay. No webview, no iframe, no URLs. This keeps the existing `_URLISH` refusal (`validate.py:19`). |
| Controlled URI intelligence and services | Gateway fair queue (Brain), capability resolver plus grants, approval gate, A2UI action authorities | NEW `uri_apphost/broker.py`: per-app, per-user tokens limited to the manifest's services (`brain.complete`, `files.read_own`, `notify`). Every consequential action goes through Core's approval gate. |
| App state and user data | `user_scoped_path()` (UUID-only ids) | Convention: `users/<uid>/apps/<app_id>/`. The app process gets only that directory. |
| Prevent cross-user privilege escalation | Gateway authentication; per-user stores; digest-bound actions | One app instance per (user, app). It runs as that user's low-privilege Windows account (same mechanism as S7) and never as the server account. |
| Resource limits | Admission pools (capacity), GPU lease | Job memory/CPU/process limits (above). GPU-using apps must take `gpu_lease` and are refused while the Brain holds it. |

- **Future URI Office:** it would be an app on this host. It needs richer A2UI components (Table, RichText, file
  picker), added to the catalog via the existing versioned `uri:a2ui/catalog/v1` → `v2`. M39's `uri_v1/office` stays a
  donor and is **not** imported in M1.
- **Rejected:** embedding web apps in a Flutter WebView. It would add a dependency, break the no-URL A2UI rule, and open
  a cross-origin token-theft surface.
- **Rejected:** containers (Docker or WSL). They add a heavy dependency on Windows, give poor AMD GPU passthrough under
  WSL for Vulkan, and Job Objects already exist.

---

## 6. Threat model

Assets:
- each user's conversations, memory, files and Google tokens;
- harness logins;
- the server OS;
- the GPU;
- owner-only admin functions.

Actors:
- a household user, curious or compromised;
- a stolen client device;
- a malicious app or prompt-injected harness;
- tailnet peers;
- a LAN attacker.

| ID | Threat | Today | M1 control | Slice |
|---|---|---|---|---|
| T-1 | Unauthenticated request reads or acts on the owner's ambient state | **Open** (R1/R2) | The gateway rejects any non-PUBLIC request without a valid bearer. Core binds to loopback only. | S1 |
| T-2 | Self-registration by anyone who can reach the server | Open (`/auth/signup` PUBLIC) | The gateway blocks remote signup; accounts are created by the admin locally. | S1 |
| T-3 | A user overwrites the shared Google OAuth client secret | Open (`POST /connections/credentials`, any user) | Gateway: ADMIN only. | S1 |
| T-4 | Cross-user mailbox access via multi-action Gmail | **Open** (R3, `server.py:542,600`; `google_auth_common.py:32`) | Interim: revoke the `Gmail` grant from non-owners. Real fix: per-user `GmailService(user_id)` | S1 (grant), S3 (fix) |
| T-5 | Tokens and keys readable at rest | Google tokens plaintext; Fernet keys under a hard-coded default secret | Gateway refuses to start unless non-default secrets are set. Encrypt Google tokens (S3). | S2, S3 |
| T-6 | A same-host proxy makes every caller look loopback, bypassing the "authorize only at the PC" rule and collapsing IP rate limits | Latent (it appears once a proxy is added) | The gateway blocks `/connections/*/authorize` for remote callers and rate-limits by principal, not by IP | S1 |
| T-7 | A harness reads another user's CLI home or files (Claude tool scoping is not OS-enforced, F2; same Windows user) | Open for multi-user | One low-privilege Windows account per URI user; ACLs on homes and workspaces | S7 |
| T-8 | A harness or app escapes resource bounds (memory, process bombs) | Kill-on-close only | Job limits (D-6); admission pools | S7, S8 |
| T-9 | An app reaches URLs or the network, or injects a UI action not in its manifest | A2UI refuses URLs and unknown actions | Server-side validation of app surfaces; manifest-declared actions only; broker-scoped tokens | S8 |
| T-10 | Prompt injection via email or files leads to a consequential action | Approval gate, digest-bound | Unchanged. Approvals stay per user and are never cross-approvable (already tested). | — |
| T-11 | Brain starvation by one user, or a GPU experiment silently stalling everyone | No fairness; lease is exclusive | Fair queue; `BRAIN_UNAVAILABLE` with the lease holder | S1, S4 |
| T-12 | Local processes query the Brain directly (OI-SEC-1: no API key on 18470) | Owner-accepted | Unchanged in M1. Users never get OS access to the server. Revisit if apps run local code (S8 runs them as low-privilege accounts; a Windows Firewall rule can restrict loopback by program; **unverified**) | S8 |
| T-13 | Lost client device | Per-device revoke exists; token plaintext in SharedPreferences | Admin and user can revoke the device. Secure storage on the client (new dependency, D-7). Tailnet device removal. | S9 |
| T-14 | Subscription terms breach | Not currently exposed (single owner) | §4 rules | S7 |

---

## 7. Prioritized implementation slices

Each slice runs in its own branch and worktree from the then-current canonical tip, gets independent review, and is
integrated only by fast-forward under owner authorization.

### S0. Owner decisions (no code)

| ID | Decision |
|---|---|
| D-1 | Line A as the M1 front door (recommended) vs. making Line B multi-user first |
| D-2 | Authorize the frozen-Core repair scope in S3 |
| D-3 | Private network: Tailscale Personal (recommended; Windows client; third-party sources report a free tier of 3-6 users, re-check the current plan) vs. self-hosted Headscale or plain WireGuard |
| D-4 | Harness hosting interpretation (§4); whether `CLAUDE_CODE_OAUTH_TOKEN` forwarding stays |
| D-5 | Google OAuth publishing status. *Testing*: 7-day token expiry. *Production, unverified*: personal-use warning screen, <100 users. Whether the owner's Cloud project hosts all three users. |
| D-6 | Job Object limits: change the frozen supervisor, or use a non-frozen wrapper |
| D-7 | Client secure token storage (new Flutter dependency) |
| D-8 | Whether non-owner users get harness access in M1, or only after S7 |
| D-9 | Storage ownership: whether server-private and admin-published server folders are acceptable for M1 beside the Phase 1 rule "client owns content" (see `M1_STORAGE_ACCESS_MANAGER.md` §2) |

### S1. `uri_gateway`: authenticated boundary and fair Brain queue

- NON-FROZEN, **fully cloud-testable**.
- Acceptance criteria. Each AC needs a test that fails without the code:
  - **AC-1.** For every route in `route_classification.py` classified USER or ADMIN, a request without `Authorization`
    → 401 at the gateway. Core is never called (checked with a recording Core stub and against the real Line A app via
    `TestClient`).
  - **AC-2.** PUBLIC routes are allow-listed explicitly. `/auth/signup`, `/audit/shadow-comparison` and `/identity` are
    refused from remote callers.
  - **AC-3.** ADMIN routes forwarded only when Core's `/auth/me` reports role ADMIN.
  - **AC-4.** `/connections/*/authorize` and `POST /connections/credentials` are refused for every non-loopback caller,
    whatever the forwarded headers say.
  - **AC-5.** Incoming `X-Forwarded-*` and `Forwarded` headers are stripped. Rate limits are keyed by principal.
  - **AC-6.** At most one in-flight `/ask`/`/ask/stream` per user. Round-robin service across 3 simulated users with a
    fake Brain shows bounded wait. A second request from the same user gets `TURN_IN_PROGRESS`.
  - **AC-7.** A lease-held state (simulated) → `BRAIN_UNAVAILABLE {holder_purpose}` within 1 s.
  - **AC-8.** The audit log records principal, route, status and latency. Prompt or response content is never recorded
    (same pattern as `test_usage_meter_no_content_stored.py`).
  - **AC-9.** The gateway refuses to bind non-loopback without TLS, reusing `check_bind_is_safe` semantics.
  - **AC-10.** No change under the frozen prefixes (`scripts/ws_frozen_check.py` part 2).

### S2. Deployment hardening configuration

- NON-FROZEN; cloud-testable logic, PC-blocked deploy.
- **AC-1.** Gateway start fails if `URI_PROVIDER_KEY_SECRET` or `URI_EXTERNAL_CREDENTIAL_SECRET` equals the
  hard-coded defaults or is shorter than 32 bytes.
- **AC-2.** Core is launched bound to 127.0.0.1 only.
- **AC-3.** A runbook for creating 3 accounts locally. The admin account is created first.

### S3. Authorized frozen-Core repair batch

- FROZEN-TOUCH; needs D-2. Cloud-testable.
- **T1 (characterize first).** Test H-1: does an approved Gmail/Drive action execute with the requesting user's token?
  Fix only if it fails.
- **T2.** The multi-action `GmailCapability` and the evidence, linked-document and draft-context services take
  `user_id`. A test with two users and two fake token files proves there is no cross-read.
- **T3.** Per-user temp folders for attachments and Drive downloads. `purge_downloads` is scoped.
- **T4.** The graphify index is built per user.
- **T5.** `set_experience_tier` preserves `mode` (regression test).
- **T6.** Google `token.json` is encrypted at rest using the per-user Fernet pattern, with migration.
- **T7.** `status=suspended` is honoured by `authenticate()`, and an admin endpoint toggles it.
- **T8.** A config flag closes signup.
- Gate: the full `test_*` suite in the cloud with no new failures, plus the owner-PC chain later.

### S4. Brain bridge and fairness live check

- NON-FROZEN config plus gateway; **PC-blocked live**.
- **AC-1.** Line A turns for 3 users complete against Runtime v1 via `lm_studio` base_url `127.0.0.1:18470/v1`.
- **AC-2.** Tool calling works or fails honestly.
- **AC-3.** No Ollama process is resident.
- **AC-4.** Decode stays healthy (≥60 tok/s, the host's own DEGRADED threshold) with the client app open.
- **AC-5.** Three concurrent users are served in round-robin. Measured p95 wait is recorded.

### S5. Private network

- Configuration; **PC-blocked**.
- Tailnet with ACLs that allow only the gateway port to the server. HTTPS via `tailscale serve` or `tailscale cert`.
- The client base URL is the tailnet name.
- **AC:**
  - non-tailnet LAN hosts cannot connect;
  - TLS certificate is valid;
  - a remote device logs in and runs a turn.

### S6. Per-user Google and Calendar

- FROZEN-TOUCH for Calendar code; consent is **PC-blocked**.
- Calendar as a new per-user capability. Read-only scope first, writes behind approval.
- A consent procedure per D-5.
- **AC:**
  - three users, three distinct mailboxes and calendars;
  - cross-user test negative;
  - tokens encrypted (S3-T6).

### S7. Per-user harness execution

- FROZEN-TOUCH (adapters, supervisor bridge); **PC-blocked** (Windows accounts, native logins).
- One low-privilege Windows account per URI user. CLI homes and workspaces ACL'd to that account. The supervisor
  launches attempts under that account.
- **AC:**
  - user B's harness cannot read user A's CLI home (an attempted read is denied by the OS);
  - each user's own native login, with no shared login (extend the ISO-1 test);
  - Job limits are applied.

### S8. App Hosting Foundation

- NEW `uri_apphost/`. The registry, manifest validation, surface bridge and broker are **cloud-testable**. Launch and
  containment are **PC-blocked** (Windows).
- **AC:**
  - unsigned or hash-mismatched manifests are refused;
  - an app surface containing a URL or an undeclared action is refused before reaching any client;
  - user B cannot open, act on or read state of user A's app instance;
  - a memory-hog app is killed at its limit;
  - termination kills the whole tree;
  - one demo app (a read-only "notes" app) renders in the Workspace dock.

### S9. Client updates

- Flutter; **PC-blocked** (no Flutter in this cloud).
- Gateway base URL; queue and `BRAIN_UNAVAILABLE` states; secure token storage (D-7); app surfaces in the dock.

**Order and dependencies:**
- S0 → S1 → S2 → (S3 ∥ S4 ∥ S5) → S6 → S7 → S8 → S9.
- **The smallest usable M1 is S1+S2+S4+S5 with the S1 interim grant.** That gives three users chat, memory, files and
  per-user single-action Gmail/Drive over a private network. S3 follows immediately.

---

## 8. Independent audit and integration procedure

1. **Open.** The implementer opens a branch and worktree from the canonical tip, after re-checking that tip (see §0
   "Unverified").
2. **Characterize first.** Characterization tests come first and must fail on the base where they target a defect.
3. **Implementer's hand-off package:**
   - diff;
   - per-AC test names;
   - full `pytest` result in the cloud (pass/fail/skip counts compared with the base);
   - `scripts/ws_frozen_check.py` output;
   - a secret scan (masked).
4. **Independent review.** A different agent (Codex or a fresh Claude session) re-runs everything from a clean
   checkout, attacks the ACs adversarially, and records ACCEPT / ACCEPT WITH FINDINGS / REJECT. The implementer never
   approves their own work (`AGENTS.md:62`).
5. **Windows/PC gate (owner present).** Phase 1/2 chain, `tests/ws`, `tests/oi`, `tests/phase2*`, live S4/S5/S7 checks
   under the GPU lease (`gpu_lease run --purpose …`). SAFE-1 (unexplained hard hangs) must be resolved or explicitly
   accepted first.
6. **Integration.** Fast-forward of the canonical branch only, with the owner's authorization. No force, no rebase of
   published history (`TIWS_INTEGRATION_RECEIPT.md:12`). Record the receipt.
7. **Production.** Production remains a separate owner authorization (CUT-1).

---

## 9. Cloud-testable vs PC-blocked

| Work | Cloud | Blocked by offline PC |
|---|---|---|
| S1 gateway, all ACs (Linux, `TestClient`, fake Brain) | ✔ | |
| S2 secret-guard logic | ✔ | deployment |
| S3 repairs and their tests (Line A suites run in the cloud: 315 pass, see evidence) | ✔ (after D-2) | Windows chain re-run |
| S8 registry, manifest, A2UI surface bridge, broker | ✔ | Job Object launch, limits |
| Re-running Windows-only suites (`gpu_lease`, `msvcrt`, Job Objects, DPAPI) | ✘ (fail on Linux for `msvcrt` / `WINDOWS_REQUIRED`) | ✔ |
| Runtime v1 / Brain live, VRAM, fairness timing | ✘ | ✔ |
| Tailscale, TLS, remote devices | ✘ | ✔ |
| Google consent, Calendar live, token refresh | ✘ | ✔ |
| Native harness logins, per-user Windows accounts | ✘ | ✔ |
| Flutter client build and tests | ✘ (no Flutter SDK here) | ✔ |
| Confirming local-only work after `54ad7be` | ✘ | ✔ |

---

## 11. Storage and Access Manager (extension added 2026-10-10)

The full design is in `M1_STORAGE_ACCESS_MANAGER.md`. It covers:
- user-controlled folders, drives and cloud locations;
- separate read, create, edit and delete permissions;
- named workspaces and default output folders;
- temporary per-task grants;
- approval, revocation and recovery;
- the client-local vs server-side access model;
- path and reparse-point safety;
- multi-user isolation;
- slices S10-S17 with tests.

Summary:
- **One server-side `StorageBroker`.** It is a new non-frozen `uri_storage/` package, consulted from the *existing*
  approval/resolver decision point; that integration is the frozen-touch slice S11. It becomes the single copy step for
  user turns, harnesses (copy-in and copy-out around the existing per-run workspaces), hosted apps (S8 broker
  `files.*`), the scheduler and future Office.
- **Client folders.** These stay on the device: scoped transfer through the existing `/files` API. The server never
  sees device paths.
- **OS-level isolation** depends on S7.
- **Owner decision D-9** is required (above).


---

## Conclusion

**Recommended smallest M1:** a new, non-frozen `uri_gateway` in front of the already multi-user, tested Line A Core.
- It closes anonymous access, open signup, remote credential upload and remote consent.
- It adds per-user fair queuing to the single-slot Runtime v1 Brain, reached by provider configuration.
- It is served over a Tailscale tailnet with TLS.
- Until the authorized frozen repair (S3) lands, multi-action Gmail is restricted to the owner through existing grants.
- Harness use and app hosting follow as separate slices.
- No Line B redesign, no new framework, no container runtime, no webviews.

**Estimated complexity:**

| Slice | Size | Scope |
|---|---|---|
| S1 | Medium | about 600-900 lines plus tests, one session |
| S2 | Small | |
| S3 | Medium | 8 bounded repairs across about 8 frozen files |
| S4 | Small code | live measurement on the PC |
| S5 | Small | configuration |
| S6 | Medium | |
| S7 | Large | Windows account and ACL plumbing in frozen supervisor paths |
| S8 | Medium-Large | |
| S9 | Medium | |

Minimal M1 (S1+S2+S4+S5) is about 2-3 focused sessions plus one owner-present PC session.

**Major risks:**
1. Frozen-system authorization is needed for the real leak fixes (R3 et al.).
2. Single-slot Brain latency under three users (measured only on the PC).
3. Subscription-terms interpretation for hosted harnesses (D-4).
4. Google publishing-status token expiry (D-5).
5. Machine stability (SAFE-1).
6. Possible unpushed local work on the PC.
7. Same-Windows-user trust until S7.

**Storage extension:** the smallest useful storage slice set is S10 + S12 + S11 + S13 (Python side). It is
Medium-Large, about 2-3 sessions. S10, S12 and the S13 Python side are cloud-testable and non-frozen. S11 needs the
D-2 frozen authorization. S14 and S15 are PC-blocked.

**Work that can proceed safely in the cloud now** (each needs separate authorization to implement):
- S1 in full;
- S2 logic;
- S3 characterization tests (no frozen edits; test files only), including H-1;
- S8 registry, manifest, surface-bridge and broker design with tests;
- writing the S5 and S7 runbooks.

None of these touch canonical branches or frozen prefixes, except S3 fixes, which wait for D-2.
