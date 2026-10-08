# URI Working System — status report

Date: 2026-10-08. Branch `integration/working-system-20261008` (local only, not pushed). Code tip `cfe4e88`.
The blueprint and acceptance criteria are in `WS_BLUEPRINT.md`, the inputs in `WS_PROVENANCE.md`, and the commit
ids, hashes and receipts in `WS_INTEGRATION_RECEIPT.md`.

**Verdict.** URI runs as one application on this PC, in the materialized development runtime. The real Flutter
Living Companion drives the real integrated worker. That worker reaches real Core: Intent Discovery, approval, signed
ticket, client execution and independent verification. Runtime v1 is the default Brain. Everything that does not
need the GPU was demonstrated live. **Live journeys that need the Runtime v1 GPU (normal answer, reasoning,
mid-stream cancel) were not demonstrated in this session**, because another session's GPU benchmarks held the GPU.
Their code paths pass with a scripted llama-server and in the earlier OI live runs (8/8 real Core with Runtime v1,
recorded on the OI branch). This is **not production**: there is no cutover, the live PC still runs the legacy
`\URIServer`, and no shortcut was changed.

## 1. What each item has reached

Legend: **I** implemented · **T** automated tests pass · **L** live-demonstrated in this session · **A** accepted by
the independent Codex review of this candidate · **G** integrated (on the integration branch, combined regression
gate passed) · **M** still mocked or simulated

| Capability | State | Evidence |
|---|---|---|
| UI ↔ Core/OI over the stdio integrated worker (WS-D1) | I T L A G | `run_uri_integrated_worker.py`, `worker_bridge.py`, `integrated_runtime.dart`; live UI test (real widgets, real worker) |
| Streaming answers (`answer.delta`) | I T A G (L only for the transport) | unit tests with scripted llama-server; real Runtime v1 streaming **not shown live this session** |
| Cancellation (Stop button → `oi_cancel`) | I T A G | unit tests (fake llama, 400-chunk stream → `CANCELLED`); live cancel needs Runtime v1 |
| Reasoning tier (Fast/Thinking chip, progress count, no reasoning text) | I T A G | unit tests; live needs Runtime v1 |
| Supervised action: approve → `SETTLED_VERIFIED`; deny → `APPROVAL_DENIED`, nothing changed | I T L A G | live UI and worker runs (deterministic row explicitly selected, because the Brain was stopped); screenshots 03, 04 |
| Typed text never approves; approval bound to the card's digest; forged digest refused | I T L A G | unit tests; live `forged_digest` journey → `APPROVAL_DIGEST_MISMATCH`, memory unchanged |
| Refusal (destructive request with no qualified capability) | I T L A G | live: `REFUSED_UNSUPPORTED` (fresh session) / `INTENT_CONFIRMED_NOT_EXECUTED` (session holding a just-denied intent); no approval card in either case |
| Unavailable runtime | I T L A G | live: `BRAIN_UNAVAILABLE` and nothing sent to a model; orb shows "Unavailable · Brain STOPPED"; screenshots 01, 02 |
| Restart (fresh worker process over the same client root) | I T L G | live: memory preserved, readiness re-read. Brain restart not exercised (GPU) |
| Memory: remember (approval-gated) and list (deterministic client read) | I T L A G | live; Settings panel (screenshot 05) |
| Readiness and performance indicators | I T L(readiness) A G | Brain state, model id and artifact match shown live; per-answer TTFT / tok/s rendering tested; live metrics need Runtime v1 |
| Runtime v1 as the default Brain; explicit selection; no fallback | I T L A G | catalog live (screenshot 05); deterministic row only by explicit choice; other local models NOT_QUALIFIED |
| Deterministic paths without a model | I T L A G | presentation commands, memory list, Brain status, refusal and unavailable-runtime all work with the Brain stopped |
| Integrated server profile (Phase 2 rows + Runtime v1 row) | I T L A G | live under the C1 gates on 18300; identity proven |
| Launcher (`Launch URI Working System.bat`) | I T L A G | self-test: legacy root, foreign UI and port 8000 refused; signed identity proof required; wrong-key proof refused |
| Cloud providers: $5/month, single-use manual approvals, no calls | I T A G | 6 tests, network forbidden; activation **disabled**, no credentials |
| Living Companion default shell; Hybrid via Settings (WS-D4) | I T L A G | the classic shell closes the worker first and never contacts port 8000 (a saved `localhost:8000` is blocked) |
| Workspace context panel (Brain, model, approvals) | I T L A G | UI-1 repaired: shows the real Brain; approvals state Core's rule |
| Dashboard "Brain & models" card | **M** | still the Hybrid mock card, carrying a **Simulated** badge (screenshot 06). Not wired |
| Dashboard harness/permission captions read "(mock)" although readiness is real | **M** (label only) | not edited; see §4 |
| Tasks, Documents, work items, clients, permissions | **M** | the UI's existing simulator, every region badged **Simulated**; no backend serves them on the paired Core |
| Listening/speaking voice states | **M** (no source) | no voice layer in this integration |
| Multi-step plans, harness choice, escalation offers | I (OI) T, not wired to UI controls | events are received and shown as text/route chips; no plan-approval or provider-picker UI yet |

## 2. Regression and acceptance evidence

| Gate | Result |
|---|---|
| Frozen boundary (`ws_frozen_check.py`) | 121/121 Phase 1 checkpoint files byte-identical; no protected path changed or added (tracked + untracked) |
| Accepted chain on the combined materialized tree, `ws_chain1` (at `a80dc58`) | **ALL_PASS**: phase2 486/0, authority 134/0, phase1-full outcome identity (2,698 ids, the same 11 known failures), phase1-scope (outside = ∅, importers = ∅), residue |
| Accepted chain, final tree `ws_chain_final` (at `abe2f9b`) | see `WS_INTEGRATION_RECEIPT.md` |
| Flutter full suite | 294 passed, 3 skipped (2 baseline live tests and the opt-in WS live test) |
| OI + WS Python | 182 passed, 16 skipped (opt-in live tests) |
| Live worker (final tree, Brain stopped) | 6 passed, 2 skipped (Runtime v1 needed) |
| Live UI journeys (final tree, Brain stopped) | passed: unavailable runtime, approve, deny, refusal, local presentation command, restart |
| Independent review (Codex `gpt-6-sol`, medium, read-only clone) | r1 REJECT (5) → r2 REJECT (3 partial + 2 new) → r3 ACCEPT WITH FINDINGS (1 new MEDIUM) → r4 **ACCEPT WITH FINDINGS** at `fcfed5c`; every finding confirmed in source, repaired and tested (`WS_INTEGRATION_RECEIPT.md` §4) |
| Not run | flutter/bridge/native steps of the accepted chain (unchanged packages; the native step needs a client-profile Codex login, PA-8/9) |

## 3. Defects found and repaired in this session (beyond the Codex rounds)

- FB-1: the OI branch edited the frozen root `.gitignore`. Restored.
- The OI orchestrator emits decision events under Core's turn id, so the UI lost the outcome. Events are now keyed
  by the OI turn id.
- Core requires UUID session ids; the memory read used a non-UUID id.
- Reply/event race: the worker started a job before writing the reply. The live UI deny journey hung on this.
- UI-1: the context panel showed the mock Brain without a badge.
- PrintWindow returned stale frames for the GPU-rendered window; the capture tool now copies from screen.

## 4. Limitations and open items (recorded, not hidden)

| ID | Item | Affects |
|---|---|---|
| GPU-1 | Live Runtime v1 journeys not demonstrated: another session's GPU benchmarks (`bench_runtime.py`, `residency_watch.py`) held the GPU. Two concurrent 13.7 GB loads stalled both (`LOCAL_BRAIN_START_TIMEOUT`); my host was stopped and theirs left untouched. The OI start lock is per state directory, so it does not serialize starts across trees or other tools | AC-14 partially |
| OI-SEC-1 | Runtime v1 has no API key and CORS `*` (frozen argv). Accepted as a recorded limitation (WS-D2) | local exposure |
| R-BUSY | The UI stays busy if the worker stays alive but never replies and never finishes a turn. A worker exit clears it. There is no in-app recovery control yet (Codex r4 residual) | responsiveness |
| R-SHUT | A Core call that outlives the 30 s shutdown join cannot release its card; the frozen server's 15-minute idle expiry is the backstop (Codex r3 residual) | server capacity |
| L-MUTEX | One worker per client root. The Hybrid supervised screens cannot run while the integrated worker holds the client | classic shell |
| L-CLASSIC | On this PC the classic shell's saved server is the legacy `localhost:8000`, so it is blocked; Hybrid is reachable only against another server | classic shell |
| L-DASH | The Dashboard Brain card is mock (badged); the harness/permission captions say "(mock)". A file read needed for this edit was refused by the session's permission layer, so I did not edit it | dashboard honesty (badged) |
| L-RT | The runtime is a materialized tree (`e8e3b65` + overlay + integration paths), because frozen `runtime_identity` pins HEAD (CONS-7). After materialization, `scripts/ws_server_identity.py` in `uri-ws-final` was replaced by its `cfe4e88` version (hash recorded) | evidence integrity (disclosed) |
| L-PLAN | Plan approval, harness picker and escalation UI controls are not built; their events render as text | multi-step tasks |
| Owner | Production cutover, containment of `\URIServer`, shortcut changes, paid API activation, physical gates PA-1..PA-13 | out of scope by mandate |

## 5. How to run it (development)

```
C:\Users\cheta\Development\uri-working-system\Launch URI Working System.bat -RuntimeRoot C:\Users\cheta\Development\uri-ws-final
```

The launcher verifies the materialized tree. It then attaches to Runtime v1 or starts it through the OI host
(frozen argv, kill-on-close job), starts and identity-checks the integrated server, and opens the app.
