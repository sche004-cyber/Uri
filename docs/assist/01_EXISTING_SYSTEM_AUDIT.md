# Existing implementation, capability audit and reuse assessment (W1 / A0)

Date: 2026-10-10. Canonical tip inspected: `ffdf534` (`integration/git-sync-20261008` =
`integration/final-qualification-20261010`). Method: direct reading of source, configuration, tests and receipts;
three read-only inspection agents were used to locate material and every claim they made that this document relies
on was re-checked against the file cited (spot checks recorded in the session log).

Acceptance criteria for this audit: (a) every capability the brief names is classified with evidence;
(b) frozen boundaries are stated from the mechanism, not from documents alone; (c) each reuse decision names the
component reused; (d) contradictions with the brief are stated.

## 1. Capability audit

Levels: RESEARCHED · PLANNED · IMPLEMENTED · TESTED · INDEPENDENTLY ACCEPTED · INTEGRATED · STAGED · ACTIVATED.

| Area | State on canonical `ffdf534` | Evidence |
|---|---|---|
| Brain | Runtime v1 FROZEN: **Qwen3.6-35B-A3B UD-IQ3_S** + `mmproj-F16` + MTP draft, llama.cpp b11425 Vulkan, `127.0.0.1:18470`, ctx 32k, `-np 1`. STAGED 146 tok/s calibration, live answers 121-125 tok/s | `model_lab/integration/local_brain.json:9-34`; `runtime_v1.py:76-87`; `STAGING_QUALIFICATION.md:26` |
| Brain vision | Model/runtime level QUALIFIED (V suite 5/5; vision p50 1.64 s in soak; ~1.8-2.0 s per 768 px image). **Not wired**: no application code sends an image (`core_provider.py:45` sends strings) | freeze record lines 145, 213, 239, 287 |
| GPU lease / advisory | INTEGRATED (`gpu_lease.py`); app windows are not lease clients; any second GPU workload is refused while the Brain host holds the lease | `gpu_lease.py:21,200-225`; `ws_brain_host.py:168-182` |
| VRAM headroom | AT_RISK, margin −57 to +72 MB with the Companion open; a 700 MiB window → WILL_DEGRADE_BRAIN | `STAGING_QUALIFICATION.md:27-28` |
| Web search | IMPLEMENTED in frozen Core: Tavily only (`uri_core/tools/web_search.py`), server-wide key `TAVILY_API_KEY` | `web_search.py:28,74` |
| URL fetch | IMPLEMENTED in frozen Core with **no address checks; redirects followed (SSRF-1)** | `uri_core/tools/fetch_url.py:117-130` |
| SafeFetcher, SourceRecord, providers beyond Tavily, feeds, social, citation verification | **Absent** on canonical; designed only on research branch `research/m1-multiuser-app-host` (P3-1..P3-7, P4) | `git show origin/research/m1-multiuser-app-host:docs/research/m1_multiuser_app_host/M1_IMPLEMENTATION_SLICES.md` |
| Browser automation / extension | Absent (no Playwright/CDP/extension code) | M1 research §1; grep |
| Desktop perception (UIA, screen capture) | Absent in the app. `capture_ws.ps1` captures URI's own window for evidence only; M33.2 B2 perception is benchmark-only with fixture pathways | `capture_ws.ps1:73-83`; `M33_2_BATCH_B2_COMPLETION_REPORT.md:13,69-70` |
| Companion UI | INTEGRATED + STAGED: Living shell with Companion / Workspace / Dashboard (`UiPresentationMode`), one travelling orb (`LivingShell.orbKey`), companion identities and themes | `presentation_controller.dart:4`; `living_shell.dart:49-81,301-316` |
| A2UI | INTEGRATED: catalog `uri:a2ui/catalog/v1`, refuses URLs everywhere, digest-bound actions; Python authority + Dart mirror with shared fixtures | `uri_a2ui/catalog.py`, `validate.py:19,150` |
| UI ↔ runtime transport | Framed stdio to `scripts/run_uri_integrated_worker.py` (not HTTP); `worker_bridge.COMMANDS` exact key sets; events `uri.oi.event.v1` with a closed type registry | `worker_bridge.py:42-58`; `events.py:15` |
| Scheduler | INTEGRATED (not activated) | ledger |
| Developer Console | **None** exists. Closest: classic Diagnostics screen (frozen file), FrameStatsOverlay, A2UI hub timings | UI audit |

## 2. Frozen and protected boundaries (mechanism, not description)

`scripts/ws_frozen_check.py:21-26` refuses any tracked or untracked change versus `037229c` under: `uri_core/`,
`uri_supervisor/`, `uri_supervisor_bridge/`, `uri_harness_adapters/`, `model_lab/integration/`, five `scripts/run_*` /
`c1_bootstrap.py`, five `uri_ui` Dart files, and `.gitignore`; plus byte identity of 121 Phase 1 files against a
checkpoint zip that exists only on the owner's PC. `tests/phase2a/test_frozen_core.py` keeps an exact-path
`ALLOWED_NEW` list for the materialized runtime (owner decision WS-D3). The Runtime v1 profile is frozen by its
freeze record §14 (reopening criteria exclude benchmark gains).

Consequences:
- Every Core registration point (`uri_workspace/capabilities_registry.json`, `registry.py`, `tool_schema.py`,
  `orchestrator.py`, `fetch_url.py`, `web_search.py`) is frozen. **W1 cannot become a Brain tool and SSRF-1 cannot be
  repaired without an owner decision** (M1 research calls this D-2). W1 therefore ships as a new package reachable
  from the UI through the worker, not through Core's tool loop.
- New packages follow the OI/scheduler/A2UI precedent: new top-level directories, exact paths added to the
  materializer and to `ALLOWED_NEW`.

## 3. Contradictions with the brief

| Brief | Verified fact | Effect |
|---|---|---|
| "Qwen3.5-based Brain" | Qwen3.6-35B-A3B | none on design; all docs use the verified id |
| "121-125 tok/s" | live answers 121-125 tok/s; calibration 146-156.5 tok/s (synthetic decode) | both reported, with their measurement kind |
| "URI Core authoritative for permissions" | `uri_core/` is frozen; Core's capability gates cannot see Assist | Assist's permission authority is a new non-frozen module inside the worker process (the same trust boundary as OI); consequential actions remain Core-only. Recorded as an architectural decision for owner review |
| "Existing Web & Social Intelligence and browser security plans … unified P-series" | exist only on an unmerged research branch; not accepted | used as design input (SafeFetcher rules, SourceRecord fields, threat list), not as accepted contracts |
| "Developer Console" | none exists | diagnostics added inside the Assist view and as a worker command; no new console built |

## 4. Architecture and reuse assessment

| Need | Reused | New (and why) |
|---|---|---|
| Retrieval | — (frozen `fetch_url` is unsafe) | `uri_web.safe_fetch` (SSRF-safe, pinned) |
| Search | Tavily provider and its `TAVILY_API_KEY` convention | provider abstraction + Brave/SearXNG (optional) |
| HTML/feeds | stdlib `html.parser` approach of `fetch_url` | `uri_web.extract`, `feeds` (no new dependency) |
| Untrusted text typing | concept of Core's evidence typing | `uri_web.untrusted` data blocks + flags |
| Synthesis | Runtime v1 through OI `BrainClient.complete_json` and `reasoning_policy.tier_params(FAST)` | citation verifier |
| Presentation | A2UI catalog v1, `Surface`, Dart `A2uiHub` + `A2uiSurfaceView` (no catalog or action change) | — |
| UI transport | integrated worker framed stdio, exact-key command pattern, event envelope | `web_*` / `assist_*` command sets, schema `uri.assist.event.v1` |
| Assist UI | Living shell, single orb, `UriColors`/`GlassPanel`, mode chips, keyboard map | Assist view, scope line, Dashboard tile |
| Vision | resident Runtime v1 + its loaded projector; OI `BrainClient` | request builder + gate (no second model) |
| Permissions | pattern of digest-bound A2UI actions and Core approval gate (for later A1 insert) | `uri_assist.access` (separate permissions, generations) |
| Browser perception | Playwright/Chromium only as a test harness | MV3 `activeTab` extension snapshot script |

Not introduced: no second resident model, no new Python dependency (httpx and Pillow are already used by the
runtime), no Playwright/browser-use runtime dependency, no change to Runtime v1, no change to any frozen path.
