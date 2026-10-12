# URI Working System Integration — Frozen Implementation Blueprint

Date: 2026-10-08. Branch: `integration/working-system-20261008` (worktree
`C:\Users\cheta\Development\uri-working-system`), created from the published baseline `037229c`.
Status: FROZEN after the owner decisions WS-D1..WS-D4 (below). Earlier proposals in `docs/ui_phase/UI_INTEGRATION_PLAN.md`
and `docs/operational_intelligence/OI_INTEGRATION_READINESS.md` §5 are inputs and historical; this document governs.

## 0. Acceptance criteria (defined before implementation)

| ID | Criterion | Evidence |
|---|---|---|
| AC-1 | Provenance: each candidate commit descends from `037229c`; its last independent verdict is recorded, with commit and SHA | `WS_PROVENANCE.md` |
| AC-2 | Frozen integrity: the 121 Phase 1 checkpoint files are byte-identical; the accepted Phase 2 files (OQ `-g` overlay) are unchanged; no file under `uri_core/`, `uri_supervisor/`, `uri_supervisor_bridge/`, Runtime v1 config/artifacts, or the frozen Dart files is edited | `ws_frozen_check.py` output, git diff name-status |
| AC-3 | The UI receives real events from Core + OI through a stdio worker (WS-D1), not over HTTP | live Dart test + demo receipts |
| AC-4 | Streaming: `answer.delta` events arrive incrementally and render as they arrive; cancellation stops generation and ends with `CANCELLED` | worker unit test, live demo |
| AC-5 | Reasoning: the tier (Fast / Thinking) and `thinking.progress` are visible; reasoning text is never sent | events + widget test |
| AC-6 | Approvals: an action reaches Core and stops at `approval.required`; only a button press (structured `oi_decide` with the digest the card showed) approves; typed text never approves; a denial changes nothing | unit + live |
| AC-7 | Memory: remember (Core `remember_fact`, approval-gated) and recall/list (deterministic client read, no model) | live |
| AC-8 | Readiness and performance: Brain state (READY/STOPPED/DEGRADED/…), model id, and per-answer metrics (TTFT, decode tok/s) come from Runtime v1 / OI | live |
| AC-9 | Runtime v1 is the default Brain row; alternatives are listed only with their real qualification state; the user can select a qualified alternative; no silent fallback | unit + UI |
| AC-10 | Deterministic commands (presentation commands, memory list, Brain status, cancel, unavailable-runtime refusal) work with the Brain stopped | live with Runtime v1 stopped |
| AC-11 | Launcher starts only the integrated runtime (materialized tree, integrated server profile, Runtime v1 host) and refuses port 8000, the legacy `uri-agent` checkout and the M37-M39 donor | launcher self-test |
| AC-12 | Cloud providers: interface + $5/month policy + single-use manual approvals; there are no paid calls, no credential storage and no activation path | unit tests (network forbidden) |
| AC-13 | Combined regression: OI unit, Flutter full suite, Phase 2/authority/Phase 1 chain on the materialized combined tree with the exact-path scope extension (WS-D3) | chain receipts |
| AC-14 | Journeys demonstrated live from the Flutter UI: normal answer, reasoning, supervised action (approve + deny), refusal, cancellation, restart (worker + Brain), unavailable runtime | screenshots + event receipts |
| AC-15 | Independent Codex review of the final candidate; findings repaired and affected tests rerun | review record |

## 1. Owner decisions (2026-10-08, this session)

- **WS-D1 transport**: a new stdio *integrated worker* profile. It uses the same C1 gates and composition as the
  accepted supervised worker, adds the OI orchestrator, and streams `uri.oi.event.v1` frames. The accepted worker
  file is not edited.
- **WS-D2 OI-SEC-1**: the Runtime v1 argv stays frozen (no `--api-key`). Loopback exposure is a recorded limitation.
- **WS-D3 scope guards**: extend the guards with exact new paths only. The byte-identity checks stay unchanged.
- **WS-D4 UI**: Living Companion is the default shell. The Hybrid shell stays reachable through a Settings toggle.
- The orb stays as the provisional visual. There is no redesign.

## 2. Discoveries that shape the design

1. FB-1: OI commit `04ef4f0` edited the frozen root `.gitignore`. Repaired in `385250f`: the frozen bytes are
   restored and a tracked `work/oi/.gitignore` is added.
2. Frozen `runtime_identity.py` runs only when `HEAD == e8e3b65` (CONS-7). The integrated runtime is therefore a
   **materialized tree**: `e8e3b65` + the accepted Phase 2 OQ overlay (273 paths) + the integration's new paths. It is
   never a committed branch tip. The materializer is `scripts/oi_materialize_test_runtime.py`, extended with the new
   paths.
3. The OI dev server attaches no Core (`core=None`); real Core was only exercised through a test fixture. The
   integrated worker is the first product composition of `PairedCoreGateway`.
4. Phase 2 `composition.py` refuses `server_local_model` rows (`ALLOWED_KINDS`). A new server profile offers the
   Runtime v1 row without editing that file. The mandate makes this the owner's choice (OI readiness §4 item 1).
5. The client worker holds a per-client named mutex: one worker per client root. In integrated mode the integrated
   worker is that worker. The Hybrid supervised screens cannot start a second worker for the same client while it
   runs. This is recorded as a limitation, not hidden.
6. The paired Core server serves `/client/v1` only, not the Hybrid HTTP API. In integrated mode the Hybrid data
   surfaces (tasks list, devices, history) have no backend. They run over the mock client with their existing
   Simulated badges, so port 8000 is never contacted.

## 3. Architecture

```
Flutter UriApp (integrated mode: URI_CLIENT_MANIFEST + control/ui-integrated-profile.json)
  └─ IntegratedRuntime (Dart) ── framed stdio ──► scripts/run_uri_integrated_worker.py   (client profile, C1 gates)
        requests  → {"result": ...}                 ├─ SupervisedWorkerService (accepted; all Phase 2 commands)
        events    ← {"event": uri.oi.event.v1}      └─ IntegratedTurns (uri_operational_intelligence/worker_bridge.py)
                                                         Orchestrator(core=PairedCoreGateway(service runner))
                                                              │ answer channel ──► Runtime v1 (127.0.0.1:18470)
                                                              │ Core turns ──► paired server (loopback, signed)
scripts/run_uri_integrated_server.py (server profile, C1 gates) = Phase 2 policy rows + Runtime v1 row + oi seams
uri_operational_intelligence.host = the only starter of Runtime v1 (kill-on-close job, frozen argv)
scripts/launch_uri_working_system.ps1 = verifies materialized tree → Runtime v1 host → server → UI
```

## 4. Work items

| # | Item | Files (all new unless noted) |
|---|---|---|
| W1 | Worker event bridge: OI turns on a background thread, event frames under a write lock, worker-held Core envelopes (the UI never sends envelopes), digest-bound decisions, cancel, Brain status, brain catalog, memory list; while a turn runs, store-mutating commands are refused | `uri_operational_intelligence/worker_bridge.py` |
| W2 | Integrated worker profile script | `scripts/run_uri_integrated_worker.py` |
| W3 | Integrated server profile script: Phase 2 rows + Runtime v1 row, `oi_composition` proposer/interpreter | `scripts/run_uri_integrated_server.py` |
| W4 | Brain catalog: Runtime v1 default; deterministic row; other local rows only with qualification evidence; cloud rows disabled | `uri_operational_intelligence/brain_catalog.py` |
| W5 | Cloud policy: $5/month cap, single-use manual approvals, no transport | `uri_operational_intelligence/cloud_policy.py` |
| W6 | Provisioning (fresh roots inside the materialized tree, policy file, opt-in file) and materializer path list | `scripts/ws_provision.py`, edit `scripts/oi_materialize_test_runtime.py` (OI candidate file, not accepted) |
| W7 | Launcher with legacy refusal and self-test | `scripts/launch_uri_working_system.ps1`, `Launch URI Working System.bat` |
| W8 | Dart runtime: spawn, framing, event stream, commands | `uri_ui/lib/services/integrated_runtime.dart` |
| W9 | Dart conversation model, companion source, readiness, Brain picker, approval card, cancel, tier chip, metrics; wired into the Living workspace and companion | `uri_ui/lib/living/integration/**` + small edits in `lib/living/**` (UI candidate files) |
| W10 | Mount: integrated mode in `UriApp`. Living is the default; Settings toggle opens Hybrid | `uri_ui/lib/app.dart` (already an accepted-allowlisted non-checkpoint file), `lib/main.dart` (not frozen) |
| W11 | Scope-guard extension with exact paths (WS-D3) | `tests/phase2a/test_frozen_core.py` `ALLOWED_NEW` additions only; chain phase1-scope list |
| W12 | Tests: Python unit (worker bridge, catalog, cloud policy, server composition), Dart unit/widget (runtime framing, conversation model), live Dart test against the real worker | `tests/ws/**`, `uri_ui/test/ws/**` |
| W13 | Evidence: provenance, regression receipts, demo receipts, status report, integration receipt | `docs/working_system/**` |

## 5. Invariants (stop conditions)

Stop and report, rather than work around, if any of these happens:

- Any change appears to a frozen Phase 1 file or to an accepted Phase 2 file outside the WS-D3 allowlist lines.
- Any path lets typed text, a Brain output or a presentation command approve, execute or change the Brain selection.
- Any silent fallback to another model or provider.
- Any contact with port 8000, the legacy checkout or the donor launcher.
- Any network call or credential read in the cloud policy.
- A second resident model is started.

## 6. Out of scope

Production cutover, containment (`uri_containment.ps1 -Apply`), shortcut changes, paid API activation, voice input
(listening has no source), Brain-originated `ui_present` frames (AMBER bridge change), document capability, and
physical gates PA-1..PA-13.
