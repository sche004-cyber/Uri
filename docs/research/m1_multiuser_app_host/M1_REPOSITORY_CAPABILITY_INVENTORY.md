# M1 repository capability inventory

- **Baseline:** `54ad7be72847675ae662e2fd4f3b3b9d253e6d4e`, tip of `integration/git-sync-20261008` on
  `github.com/sche004-cyber/Uri`. Re-checked on 2026-10-10: the remote tip had not moved.
- **Scope:** what exists and how far each capability has progressed. Proposals live in the other reports.

## 1. Baseline identification

| Fact | Evidence |
|---|---|
| The authoritative repository is `sche004-cyber/Uri`. `sche004-cyber/uri-agent` is a historical mirror whose `master` (`e8e3b65`) has not moved since 2026-09-20. | `docs/governance/consolidation/URI_CANONICAL_BRANCH_DECISION.md` §1; `git ls-remote` on both remotes |
| The operative canonical line is `integration/git-sync-20261008` at `54ad7be`. It is identical to `integration/ti-on-ws-hardening-20261009`. It contains `integration/ws-hardening-20261009`, `integration/working-system-20261008` and `phase/text-intelligence`, verified with `git merge-base --is-ancestor`. | git; `docs/integration/ti_ws_20261009/TIWS_INTEGRATION_RECEIPT.md` §1 |
| The owner authorized fast-forwarding that branch. Promoting it to `main` is still **PROPOSED**. | `docs/governance/consolidation/URI_UNIFIED_CONSOLIDATION_PLAN.md:96`; `URI_CANONICAL_BRANCH_DECISION.md:3` |
| `Uri` has no `master`. GitHub's default HEAD is the stale `claude/edge-harness-minimum-0oj7fe` (`610c8f8`, classified HISTORICAL). | `git ls-remote --symref`; `URI_CANONICAL_BRANCH_DECISION.md:75` |
| These lines are **not** canonical: the desktop donor line `experimental/desktop-recovery-repair` (`eb73693`, which is the UI the owner uses today), the superseded base `62d564c`, the six `preserve/*` branches, and the side branches for dynamic planning, dictation, harness-first, edge-pair (NOT QUALIFIED) and `wip/batch3-codex-partial` (unreviewed). | `docs/governance/git_sync_20261008/GIT_SYNC_AUDIT.md` §4-§6 |
| Production is still the **legacy** `\URIServer` on port 8000. There has been no cutover (CUT-1). The canonical branch cannot be run directly by the frozen launcher, because `runtime_identity.py` requires HEAD `e8e3b65` (CONS-7). | `docs/working_system/WS_REMAINING_LIMITATIONS.md:11,19`; `URI_CANONICAL_BRANCH_DECISION.md` §3 |
| **Frozen paths:** `uri_core/`, `uri_supervisor/`, `uri_supervisor_bridge/`, `uri_harness_adapters/`, `model_lab/integration/`, five runtime scripts, five Dart runtime files and `.gitignore`, all compared against `037229c`. Runtime v1 is also frozen. | `scripts/ws_frozen_check.py:18-26`; `model_lab/URI_RESIDENT_INTELLIGENCE_RUNTIME_V1_FREEZE.md` |

**Unverified:** whether the PC holds local work after `54ad7be`. The TIWS receipt's §5 push record is unfilled and no
`TIWS_STAGING_RECEIPT.md` exists. Every implementation slice must re-check the canonical tip first.

## 2. Maturity ladder used here

| Stage | Meaning | Required evidence |
|---|---|---|
| **Planned** | Exists only as a design or plan document | The document |
| **Prototyped** | Code exists on a non-canonical branch, or on canonical but wired to no runtime path | git |
| **Implemented** | Code on canonical, reachable from a runtime path | Source |
| **Tested** | Targeted automated tests exist. *(RUN)* means `COMPLETED_WITH_RESULT` in this cloud session. *(Win)* means the tests need Windows and were not run here. | Test files and run |
| **Independently accepted** | A recorded verdict from someone other than the implementer: a Claude, Codex or owner closure record | Verdict document |
| **Integrated** | Part of the canonical line *and* of a composed runtime, with an integration receipt | Receipt |

Production deployment is **outside** this ladder. No canonical capability is in production (CUT-1).

There are two server lines:
- **Line A** is the classic multi-user FastAPI server, `uri_core/app/server.py`. It is the M22 lineage, accepted on
  base `e8e3b65`, which is the root of canonical.
- **Line B** is the Working System composition: the paired Core, Phase 2 supervisor, Operational Intelligence, Runtime
  v1 and the Living UI. Line B is what the canonical integration receipts cover.

## 3. Capability classification

| Area | Capability | Stage reached | Evidence |
|---|---|---|---|
| **Core / server-client** | Line A server: accounts, sessions, per-user stores | **Independently accepted.** Present on canonical but **not** part of the Line B composition. | `URI_MILESTONE_TRACKER.md:107-112` (M22.2-M22.7 DONE, VERIFIED by Claude); RUN: 315 pass (`evidence/CLOUD_TEST_EVIDENCE.md`) |
| | Line B paired Core (`/client/v1`, Ed25519 proof, DPAPI secrets). Loopback only by a frozen rule. | **Integrated** (Phase 1 freeze; WS receipts) | `runtime_identity.py:313`; `GIT_SYNC_AUDIT.md` §5; `docs/working_system/WS_INTEGRATION_RECEIPT.md` |
| | Server/client ownership principle: the client owns private content, workspace, credentials and harnesses | **Planned and owner-authorized.** Its protocol details are proposed. | `docs/evidence/phase0_runtime_inventory_20261005/SERVER_CLIENT_OWNERSHIP.md:7,71,96,138` |
| **Brain / inference** | Runtime v1: llama.cpp b11425 on Vulkan, Qwen3.6-35B-A3B, AMD RX 7900 GRE 16 GB, one slot `-np 1`. Multi-slot `-np 3` was measured and rejected. | **Integrated** (frozen; live only on the owner's PC) | `model_lab/integration/local_brain.json`; freeze doc :34, :291; `uri_operational_intelligence/__init__.py:3` |
| | Brain client and host: SSE, cancel, deadlines. The host holds the lease for its lifetime and has no auto-restart. | **Integrated** | `uri_operational_intelligence/brain_client.py`; `scripts/ws_brain_host.py` |
| | Line A model router and provider registry (Ollama default `qwen3:14b`; `openai_compatible` with `base_url` override) | **Independently accepted** (M22.5, M32). **Not connected to Runtime v1**: `18470` appears nowhere in `uri_core`. | `provider_registry.py:184-187`; `uri_core/core/model_providers/base.py:150` |
| | GPU lease: machine-wide, exclusive OS byte lock, no queue or priority | **Integrated** (WS hardening, Codex r10). **Tested (Win)**. In the cloud its tests fail with `msvcrt` missing. | `uri_operational_intelligence/gpu_lease.py`; evidence file |
| | Per-user fair Brain queue | **Missing** | `worker_bridge.py:176` refuses with `TURN_IN_PROGRESS`; Line A `/ask` is uncapped |
| | Edge / second brain | **Prototyped**: contracts and settings exist, routing is unwired and the inventory is empty | `uri_core/core/edge/routing_policy.py:44`; `runtime_inventory.py:56` |
| **Harnesses** | Claude Code and Codex adapters: bypass flags refused, environment allow-list, API keys never forwarded | **Integrated** (Phase 1/2). **Tested (Win).** | `uri_harness_adapters/__init__.py`; `uri_core/client_runtime/harness.py:33,37` |
| | Device identity. Line A `device_id` is client self-reported and unauthenticated. Line B `client_id` is registered and bound to one principal. | Line A: **Independently accepted** (M22.2), label only. Line B: **Integrated**. | `server.py:1136-1153`; `client_pairing.py:85-130`; see `M1_USER_CLIENT_IDENTITY_MODEL.md` |
| | Per-client native CLI homes. A shared login is a stop condition. | **Independently accepted** (Phase 2 closure ISO-1). Its live test needs a login. | `uri_supervisor_bridge/qualification.py:377-390` |
| | Supervisor: admission pools, Job Objects with kill-on-close, no CPU or memory limits | **Integrated**, **Tested (Win)** | `uri_supervisor/admission.py`; `winproc.py:267` |
| | Antigravity | Refused stub | `uri_harness_adapters/__init__.py:87-90` |
| | Gemini CLI, separate OS user per URI user | **Missing** | grep |
| **Auth and authorization** | PBKDF2 accounts, first account becomes ADMIN, six ADMIN routes, bearer sessions with 24 h TTL, per-device revoke | **Independently accepted**, **Tested (RUN)** | `user_accounts.py`; `route_classification.py:69-76`; `auth_session.py:77` |
| | Capability grants ∩ mode ∩ registry | **Independently accepted** (M22.4), **Tested (RUN)**. Defaults to the full registry. | `capability_resolver.py` |
| | Approval gate: single-use, expiring, bound to an argument fingerprint, per user | **Independently accepted**, Tested | `approval_store.py`; `test_server_approval_endpoints.py` |
| | User suspension, invites, role change, password reset | **Planned** (`URI_M22_ARCHITECTURE.md` §4.5) / **Missing** | grep |
| **A2UI / Workspace** | A2UI v0.9.1 subset: 13 components, URLs refused, action registry, surface digest | **Integrated** (`A2UI_CANONICAL_INTEGRATION_RECEIPT.md`), **Tested (RUN)** | `uri_a2ui/`; `validate.py:19` |
| | Workspace dock or "placement: workspace". Only the scheduler produces surfaces. | **Integrated** (UI), single producer | `uri_ui/lib/living/a2ui/`; `uri_scheduler/a2ui_host.py` |
| | `uri_workspace/` directory | A data folder, not a feature | — |
| **Scheduler** | Persistent jobs, festival-GIF template, one owner per instance (lock is per state directory) | **Integrated** (`SCHEDULER_CANONICAL_INTEGRATION_RECEIPT.md`), **Tested (RUN 56 pass)**. **Not activated**; the logon task is unregistered. | `uri_scheduler/engine.py:106-119`; `docs/scheduler/SCHEDULER_ARCHITECTURE.md:75-77` |
| **Web, search, automation** | `web_search` (Tavily, server-wide `TAVILY_API_KEY`) | **Independently accepted** (M15.1 DONE) | `uri_core/tools/web_search.py:28,74`; `URI_MILESTONE_TRACKER.md:99` |
| | `fetch_url`: http(s) only, byte cap, text extraction. **No private-address guard, and it follows redirects.** | **Independently accepted** (M19 DONE). **Defect SSRF-1** (RUN, see §4). | `uri_core/tools/fetch_url.py:103-131`; `capabilities/registry.py:20` (READ_ONLY, so no approval) |
| | `skill.yt_dlp`: one `dump_json` action, URL pattern pinned to Wikimedia Commons, pinned version | **Independently accepted** (M33.1 Batch 2). It is *not* a YouTube capability. | `uri_core/external/descriptors/yt_dlp.py` |
| | External capability contract (in_process, cli, loopback-http) | **Independently accepted** (M33/M33.1). Its documentation still says DRAFT. | `uri_core/external/` |
| | Browser automation (Playwright, Selenium, CDP) | **Missing**: no hits in Python, Dart or JSON files | grep |
| | Social platform APIs (YouTube Data API, Reddit, X, Meta, LinkedIn) | **Missing** | grep |
| **Files, storage, approvals** | Per-user `FileStore`: UUID names, realpath containment, extension allow-list, 25 MB cap | **Independently accepted**, **Tested (RUN)** | `file_store.py:157-190` |
| | Per-run harness workspace with verified, symlink-refusing copy-out | **Integrated** (Phase 1/2) | `client_runtime/turn_runner.py:225-262`; `uri_supervisor/postconditions.py:100-104` |
| | Fail-closed per-user permission binding for external capabilities | **Independently accepted** | `uri_core/external/permission_binding.py:1-21` |
| | User folders, drives, per-verb grants, named workspaces, folder picker | **Missing** | see `M1_STORAGE_ACCESS_DESIGN.md` §1 |
| | Google Drive and Gmail with a per-user token (single-action tools), stored as plaintext JSON | **Independently accepted**, **Tested (RUN)** | `google_auth_common.py:19-32` |
| | Google Calendar | **Missing** | grep |
| **App hosting / plugins** | App registry, lifecycle, broker | **Missing** | grep |
| | M39 Office backend `uri_v1/office` | **Prototyped** (donor branches only). Out of scope. | `origin/claude/project-thread-uyzemj`; `URI_SALVAGE_AND_RETIREMENT_LEDGER.md:49` |
| **Voice** | Live voice on faster-whisper, plus text intelligence | **Integrated** (`6b48830`, TIWS receipt) | `TIWS_INTEGRATION_RECEIPT.md` |

## 4. Defects and risks found during this research

All of these were re-verified in source by the author unless marked otherwise.

| ID | Finding | Severity | Evidence |
|---|---|---|---|
| R1 | A request with no `Authorization` header is served the owner's ambient state. | Critical for networked use | `server.py:653-677`; asserted by `test_multi_user_isolation.py` |
| R2 | The anonymous path skips capability grants. | High | `approval_gate.py:119-125` |
| R3 | Multi-action Gmail and the evidence, linked-document and draft-context services use the install-wide `token.json`. | High | `server.py:542,600`; `capability.py:28`; `google_auth_common.py:32` |
| **SSRF-1** | `fetch_url` fetched a loopback-only page, both directly and through a 302 redirect. On the server this exposes `127.0.0.1:18470`, the Brain with no API key (OI-SEC-1), along with other loopback services and the LAN. | High once other users or untrusted text drive it | RUN: `evidence/CLOUD_TEST_EVIDENCE.md` Run 3 |
| **DEF-H1** (was H-1 / suspected R8) | An approved action proposed with a principal **fails closed and never executes**: the persisted principal becomes a dict and the fingerprint mismatches. The suspected leak to the install token does not occur on this path. Logged-in users cannot complete approval-gated actions. | High (functional; blocks every consequential M1 feature) | RUN: `evidence/CLOUD_TEST_EVIDENCE.md` Run 4; `approval_gate.py:280-301`; `dispatcher.py:80-81`. Correction record in `M1_USER_CLIENT_IDENTITY_MODEL.md` §2. |
| R4-R7 | Shared temporary folders, shared registries, an owner-graphify index leak, open signup, and a hard-coded default secret for key encryption. | Medium | `server.py:37`; `route_classification.py:82`; subagent audit |
| BUG-1 | Setting the experience tier resets the user's mode. | Low | `user_accounts.py:258-267` (subagent; not re-verified) |
| D-REQ-1 | The Google client libraries are imported but not declared in `requirements.txt`. | Low | RUN: 11 collection errors before installing them |
| ZIP-1 | Zip extraction has no bound on decompressed size. | Low | `linked_document_service.py:167-207` |

## 5. Reusable, accepted capabilities (P0 output)

These are reused rather than rebuilt:
- Line A accounts, sessions, per-user stores, grants and approvals.
- Bind refusal, CORS and the auth rate limits.
- Runtime v1 and the GPU lease.
- The supervisor's Job Objects and admission pools.
- The harness adapters and per-client CLI homes.
- A2UI's contract, renderer and action authority.
- The scheduler, with one instance per user.
- The external capability contract and fail-closed permission binding.
- `FileStore`, and the verified copy-out pattern.
- `web_search` (Tavily) and `file_extraction`.
- The usage meter and ceilings (M22.7) for per-user web and API budgets.
- faster-whisper from the voice stack, for transcribing audio that users supply themselves.
