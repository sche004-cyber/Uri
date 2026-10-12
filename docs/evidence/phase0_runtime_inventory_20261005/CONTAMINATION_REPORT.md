# URI Phase 0 — Contamination Report

Date: 2026-10-05, Asia/Calcutta. Read-only findings. See [Runtime inventory](RUNTIME_INVENTORY.md) for paths, methodology and snapshot limits.

## Finding categories

**Observed** means OS/filesystem evidence; **source-confirmed** means implemented behavior traced in code; **risk** means a possible effect not reproduced; **historical** means earlier recorded evidence, not fresh qualification. Coexisting copies are not automatically corruption. No data loss, active cross-client leakage or duplicate production execution was demonstrated.

## Verified conflicts and inconsistencies

### C01 — Two default launcher authorities for port 8000

Observed: Desktop/Start Menu URI shortcuts target integration's `Launch URI.bat`; `URIServer` logon task targets master's `scripts/run_uri_server.py`. Integration uses `run_desktop_server.py` and validates checkout identity; master's `scripts/launch_uri.ps1` accepts successful `/health` and checks UI by process name. Both default to 8000.

Consequence: machine startup and double-click select different code/state roots. Integration can refuse an already-running master server; master launcher can reuse another healthy backend or another checkout's UI. **These are source-confirmed collision paths; no simultaneous port conflict was observed.** The active 8021 test server is a third, isolated composition.

Action after review: choose an explicit launch manifest with backend/source/state/interpreter identity; reconcile both entry points at one controlled checkpoint. Do not stop, disable or repoint anything during Phase 0.

### C02 — Installed task differs from current controller source

Observed: `URIServer` is Ready, latest result 0xC000013A; installed `StopOnIdleEnd=True`. Dirty controller now specifies `-DontStopOnIdleEnd`. Master source edits have not updated the registered task settings.

Consequence: reading the current script does not establish deployed lifecycle behavior. The result indicates interruption; idle transition as its exact cause remains unverified. No scheduled URI service was running on 8000 when inspected.

Action: capture/export existing task configuration before a later accepted reinstall; test logout/idle/restart semantics then. Do not silently rerun install now.

### C03 — Experimental defaults reach the ordinary shortcut path

Source-confirmed: integration `run_desktop_server.py` sets `URI_HARNESS_FIRST=1` and warms `qwen3:0.6b`. Its Core `/ask` calls `uri_desktop_seams.harness_first.seam.try_harness_first`. The residency optimization in `uri_desktop_seams/ollama_residency.py` is imported by its Ollama provider and can unload other large models via `keep_alive:0`.

Consequence: experimental code is in the ordinary launcher composition, rather than merely stored on a dormant branch. Warm-up and cross-model residency intervention do not meet the intended no-local-Brain external-harness posture. The residency guard tracks its own in-flight work, not every other application using Ollama.

**Actual model eviction or resource contention was not observed now.** Preserve current behavior as a donor; qualify and explicitly scope the model-management policy before placing it in the consolidated server.

### C04 — Divergent implementations with substantial uncommitted work

Observed: master 65, V1 247, integration 48 dirty entries. Master and integration both change production paths. Source hashes differ for `server.py`, canonical execution and other key files across checkouts. Integration's Ollama provider imports a desktop seam absent from accepted master provider code.

Consequence: Git SHA alone does not identify what the source directory would execute, and cherry-picking an advertised branch does not capture all desktop behavior. Some large master diffs may include line-ending changes; diff size alone is not a measure of semantic change.

Action: source/behavior manifest and bounded donor reconciliation before consolidation. No merge, reset, snapshot commit or tracker update was made here.

### C05 — Stale PID files and a detached test server

Observed: integration PID files record server 20488 and UI 24496; both absent. Harness server PID 16188 listens on 8021; recorded parent 10188 was absent.

Consequence: PID files do not prove ownership or liveness. Detached harness process may be intentionally persistent; it cannot be called abandoned based solely on parent absence. Integration launcher already has stronger executable/argument/socket checks, which should be reused.

Action: future status must report stale/detached states distinctly. No process was stopped and no PID file was removed.

### C06 — Incomplete model artifact

Observed: LM Studio `Qwen/Qwen3-14B-Q4_K_M/Qwen3-14B-Q4_K_M.gguf` is zero bytes. Several model families also exist in both Ollama and LM Studio stores; dictation has two Whisper-small cache locations with identical sizes.

Consequence: directory/filename inventory can overstate installed capability; redundant storage is present or suspected, but loaded-model duplication is not demonstrated. Equality, integrity and provenance were not verified by loading or full checksums.

Action: label the zero-byte artifact unavailable; retain everything until verification. Do not uninstall or redownload during this assessment.

### C07 — Documentation and source status disagree

Observed: AGENTS/M22 architecture resume wording points to M22.3, while actual master is ARN.1 and later governance records exist. V1 batch audit reports provisional/not frozen with M38 live qualification still required. A V1 context namespace exists but contains only the A0 scaffold. Legacy model-role comments still describe a single provider although imports include later providers.

Consequence: documentation names cannot establish implemented, reachable or qualified capability. Roadmap numbers also identify different historical work across these branches.

Action: use SHA + source hashes + exact acceptance evidence. Do not repeat complete historical audits or retroactively change milestone states.

## Confirmed ownership mismatches and unproven isolation risks

### R01 — Server-hosted private stores are user-scoped, not client-owned

Source: master `server.py::_build_user_context` constructs profile, memory, growth, approvals, sessions, experience, skills, history, uploads and `GraphStore` beneath `uri_workspace/users/<user_id>`. External credentials/services also use this backend root. Core `portable_paths.py` scopes by user UUID, without a client-installation axis.

This is a **confirmed architectural mismatch** with the requested private-client database architecture. Two clients signed into one user currently resolve the same backend context unless a new isolation boundary is introduced. **No live two-client leakage was tested.** Many filesystem user directories and SQLite files are likely a mixture of tests and real use, but that split is unknown without an approved migration inventory.

Do not deduplicate same-named graph/memory files or combine accounts. Distinct checkouts have distinct roots; counts alone prove neither divergent records nor shared database writes.

### R02 — Flutter builds appear to share one local preference namespace

Observed: `AppData/Roaming/com.example/uri_ui/shared_preferences.json` exists. Source uses common `uri.serverBaseUrl`, `uri.session.token` and username keys; Windows app metadata uses `com.example` and `uri_ui` across builds. V1 harness mode can override server URL to 8018 after loading saved preferences.

Risk: different installs/builds can share or overwrite address/session/UI settings. The token is not tied to a server identity in `SessionStore`; restoring it after a server change can produce a wrong-backend session attempt. Token validity still depends on backend checks.

**Preference contents were not read, and a cross-build overwrite was not reproduced.** Give each client an explicit installation namespace and bind URI session persistence to server identity. Do not copy the existing token into all clients.

### R03 — Legacy anonymous ambient fallback remains in current Core

Source: `_resolve_authenticated_user_id` returns None when Authorization is absent; route classification documents USER fallback to shared legacy state. Invalid/expired supplied tokens fail with 401. This was an accepted compatibility decision, not a newly discovered bypass to relabel as M22.3 unfinished work.

Risk: the consolidated authenticated-client surface must not map missing client identity to ambient private data. Use a separate strict client boundary while preserving current compatibility until callers migrate. Developer control does not eliminate request provenance, approval or capability checks.

### R04 — Credentials and configuration precedence need explicit ownership

Observed: provider encrypted stores, integration OAuth token artifacts, a checkout-hashed LocalAppData desktop secret file, native harness homes, root model roles and per-user provider configs coexist. Master launcher contains legacy literal encryption defaults; their values are deliberately omitted here. Integration runner preserves encryption compatibility for existing keys.

Risk: moving encrypted files without their key provenance makes them unreadable; pooling native harness homes under the server gives it client account authority; allowing environment-only defaults to determine all clients' routes collapses private preferences into shared policy. No credential collision was demonstrated.

Keep native authentication on its client installation. Prefer native reauthorization where scoped credential portability cannot be proven. Never expose credential values in migration manifests.

### R05 — Graphify has public catalogue and private pointer domains

Source: runtime Graphify includes capability/skill/workflow/memory/service pointers, server startup loader and per-context copies; URI graph SQLite is a separate private entity store. Developer `graphify-out/graph.json` is yet another graph.

Risk: hosting the intelligence index centrally must not pool clients' private memory/service pointers or evidence graphs. Scope overlays, caches, query identities and invalidation to client/session. A cache key that includes only user_id is insufficient for independent clients under one account. No live cache leakage was observed.

## What was not demonstrated

No two production URI API processes concurrently served the same capability; only one URI Python listener was found. No current simultaneous Main Brain/Edge model loading was observed. AST inspection found no duplicate explicit method/path declarations in the three inspected `server.py` files (77/73/75 declarations respectively); these counts exclude dynamically mounted routers and framework documentation routes. Repeated endpoints across checkouts are separate code deployments, not duplicate handlers in one app.

No verified abandoned implementation can be retired yet. Legacy PyQt, scheduler prototypes, dormant branches, model copies, test scratch roots and stale build outputs are **retirement candidates after provenance/coverage/retention review**, not authorized deletions. Existing voice controls/probes are artifacts, not evidence of active voice workers. OS monitor tasks and Electron helpers are not URI scheduling engines.

## Priority

1. Resolve launcher/source identity and freeze an exact preservation manifest.
2. Introduce explicit client-owned state and credential boundaries without relocating private databases to the server.
3. Separate qualified server engines from client harness execution and optional model residency.
4. Validate compatibility/live behavior before any retirement or state migration.
