# M1 three-user server architecture

- This document is a proposal. Its evidence comes from `M1_REPOSITORY_CAPABILITY_INVENTORY.md` (IDs such as R1 and
  SSRF-1 are defined there).
- Licensing is covered in `M1_HARNESS_ACCESS_AND_LICENSING.md`; storage in `M1_STORAGE_ACCESS_DESIGN.md`.

## 1. Principle

Put a thin, **non-frozen** boundary in front of the already multi-user and independently accepted Line A Core. Leaks
that a boundary cannot close are fixed by bounded, authorized repairs to frozen code. Runtime v1, the GPU lease, the
supervisor, A2UI and the scheduler are reused without changes.

## 2. Topology

```
 Owner, User B and User C devices (Flutter classic HTTP client; later the PWA/Android plan M22.9)
        │ HTTPS over a private tailnet (Tailscale; TLS from `tailscale serve` or `tailscale cert`)
        ▼
 ┌───────────────────────── URI server: the owner's Windows PC, AMD 16 GB ─────────────────────────┐
 │ uri_gateway (NEW, non-frozen)                                                                   │
 │   authn on every non-PUBLIC route · per-principal rate limits · remote blocks · fair Brain queue│
 │   identity: Core bearer, optionally bound to the Tailscale login (Tailscale-User-Login header)  │
 │        │ 127.0.0.1 only                                                                         │
 │ Line A Core (FROZEN; repaired only under authorization D-2)                                     │
 │   per-user stores · grants · approvals · tools · usage ceilings                                 │
 │        ├── Brain: provider "lm_studio" base_url=http://127.0.0.1:18470/v1 (configuration only)  │
 │        ├── StorageBroker (NEW)  ── see M1_STORAGE_ACCESS_DESIGN.md                              │
 │        ├── Web Intelligence service (NEW) ── see M1_WEB_INTELLIGENCE_ARCHITECTURE.md            │
 │        ├── Supervisor + harness adapters (FROZEN) → per-user Windows accounts                   │
 │        ├── App host (NEW) ── see M1_APP_HOSTING_DESIGN.md                                       │
 │        └── Scheduler: one instance per user (state dir and lock per user; engine.py:106-119)    │
 │ Runtime v1 Brain host (FROZEN; holds the machine GPU lease)                                     │
 └─────────────────────────────────────────────────────────────────────────────────────────────────┘
```

### Why Line A, not Line B, is the front door (owner decision D-1)

- Line B's paired surface is loopback-only by a frozen rule (`runtime_identity.py:313`).
- Line B principals are not linked to accounts.
- Line B allows one worker per client root (L-MUTEX).

Making Line B multi-user would need several frozen changes. The gateway is line-neutral, so the owner can still move to
Line B later. The Phase 1 ownership principle (client owns its content) still governs client-device data. See D-9 in the
storage design.

## 3. Identity propagation (the invariant every tool keeps)

| Hop | Identity carried | Existing or proposed |
|---|---|---|
| Device → gateway | Bearer token from `/auth/login` with a device id. Optionally the gateway also checks the tailnet identity against an owner-maintained map. | Existing token; mapping is proposed |
| Gateway → Core | The same bearer. Core resolves the `user_id` principal. Requests without a header are refused at the gateway (closes R1/R2). | Proposed boundary; resolution exists (`server.py:680-708`) |
| Core → tool | The `principal` and `user_id` passed to `dispatcher` | Existing (`dispatcher.py:80-81`). H-1 must be verified for approved actions. |
| Tool → StorageBroker, web service, app broker | A broker call carries `{user_id, requester_kind, requester_id, task_id}`. The broker never accepts an identity from the model. | Proposed |
| Core → supervisor → harness | `ExecutionTicket`, signed by Core and bound to the user and the approval digest | Existing (`uri_supervisor_bridge/authority.py`); per-user OS account is proposed |
| Scheduler → Core | That user's scheduler instance calls the gateway with its own principal token. It never uses the owner's. | Proposed (uses the existing one-principal-per-instance rule, `SCHEDULER_ARCHITECTURE.md:77`) |

**Rule.** Any component that cannot show an end-to-end principal refuses the work. "Ambient" or owner fallback is not
allowed on the networked path.

## 4. Shared intelligence and GPU scheduling

- **One resident Brain with one slot.** Multi-slot was measured negative on this card (freeze doc :291).
- **Fair queue in the gateway:**
  - at most one Brain-bound turn in flight per user;
  - round-robin across users;
  - the queue position is streamed to the client.
- **Priorities:**
  1. interactive turns;
  2. app broker calls;
  3. scheduled jobs.
- Lower priorities age, the same idea as `uri_supervisor/admission.py:163`. Scheduled work never pre-empts a running
  turn.
- **When something else holds the GPU lease** (a benchmark, an experiment), clients get `BRAIN_UNAVAILABLE` with the
  holder's purpose. They never see a silent hang: `brain_client.py:182-185` notes that queued llama-server requests can
  withhold headers for minutes.
- Ollama must not be resident alongside Runtime v1 (GPU-2), so Line A users get the Runtime v1 provider by
  configuration.
- **Unverified (PC-blocked):** whether Line A's `openai_compatible` adapter, tool calling and timeouts work against
  llama-server `/v1`, and what the p95 queue wait is for three users.

## 5. Central management vs per-user ownership

| Managed centrally by the server (admin = owner) | Kept separate per user |
|---|---|
| Core and Brain processes, GPU lease, gateway policy | Account, sessions, devices |
| Installed harness *binaries* (unmodified) | Harness **logins**: own CLI home, own Windows account |
| App catalogue: owner-installed manifests | App instance state under `users/<uuid>/apps/` |
| Scheduler binaries | One scheduler instance and job set per user |
| Web Intelligence service, provider API keys owned by the owner (if D-4b is chosen) | Web history, monitored sources, cached pages, browser profiles |
| Admin-published shared folders | Storage roots, grants, workspaces, delivery queue |
| Google OAuth *client* configuration (admin-only upload) | Google tokens (per user, encrypted after the repair) |

**What admin authority does not include.** The admin does not get access to another user's private data through URI.
Admin routes cover users, grants, skills and published folders. They never cover reading another user's memory, files,
tokens or browser profiles.

**Physical admin access remains.** The owner administers the Windows host, so OS-level access to user directories is
technically possible. This is disclosed to users in onboarding. Encryption at rest with per-user keys narrows it but
does not remove it.

## 6. Network and remote access

| Option | Fit | Notes |
|---|---|---|
| **Tailscale, Personal plan (recommended, D-3)** | Windows client, ACLs, MagicDNS, `tailscale cert`/`serve` for TLS, identity headers | Plan limits come from secondary sources only (3-6 users depending on date). Re-check the pricing page. |
| Headscale (self-hosted control server) + Tailscale clients | Same clients, no SaaS dependency | Another service to run; a Linux host is preferred |
| Plain WireGuard | Minimal | Manual keys; no identity layer |
| Port-forwarding with a public TLS reverse proxy | Rejected | Exposes signup, OAuth and Core to the internet |

**Gateway duties for the network** (closes T-6 from the threat model):
- strip `X-Forwarded-*` and `Forwarded`;
- refuse `/connections/*/authorize` and `POST /connections/credentials` to anything that is not physically local;
- rate-limit per principal, because behind `serve` every caller appears as 127.0.0.1.

## 7. Limits and uncertainty

- Everything that runs on the PC is unverified here: Brain sharing latency, Tailscale, TLS, the Windows account model.
- Line A has never served three concurrent users on Runtime v1.
- SAFE-1, the unexplained whole-PC hangs, must be resolved or explicitly accepted before the server serves other
  people.
