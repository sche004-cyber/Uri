# URI Working System — status report

Date: 2026-10-08. Branch `integration/working-system-20261008` (local only, not pushed). Code tip `cfe4e88`.
The blueprint and acceptance criteria are in `WS_BLUEPRINT.md`, the inputs in `WS_PROVENANCE.md`, and the commit
ids, hashes and receipts in `WS_INTEGRATION_RECEIPT.md`.

**Verdict.** URI runs as one coordinated application on this PC, in the materialized development runtime. The real
Flutter Living Companion drives the real integrated worker. That worker reaches real Core (Intent Discovery,
approval, signed ticket, client execution, independent verification) and real Runtime v1, which is the default Brain.
It is **not production**: there is no cutover, the live PC still runs the legacy `\URIServer`, and no shortcut was
changed. Remaining gaps are listed in §4.

**Evidence boundaries.** Each claim below names the surface it was shown on.
- **Worker** means a scripted driver of the real integrated worker (`tests/ws/test_ws_worker_live.py`).
- **UI-widget** means the real Living widgets, driven in the Flutter test harness against the real worker
  (`uri_ui/test/ws_live`).
- **App** means the built Windows executable, driven by keyboard and mouse and captured
  (`tools/capture_ws.ps1`, screenshots).

The independent Codex review accepted the code at `fcfed5c` (round 4). Round 5 reviewed the later diff and the
reports: candidate ACCEPT WITH FINDINGS; its report findings are repaired in this version. The combined regression
chain and the live runtime used the tree materialized from `abe2f9b`. Changes made after `abe2f9b` are listed in
`WS_INTEGRATION_RECEIPT.md` §1: the identity tool's error path, the launcher default root, the capture tool's
attach checks, and stricter live-test assertions. None of them is in a Phase 1/2 test scope. The A and G labels
below refer to those commits.

| Journey (mandate) | Worker | UI-widget | App |
|---|---|---|---|
| Normal response | yes | yes | yes (02) |
| Reasoning | yes | yes | yes (03, 04) |
| Supervised action, approve / deny | yes / yes | yes / yes | approve (05, 06) |
| Refusal | `REFUSED_UNSUPPORTED` (fresh session) | no card, nothing executed; Core asked about the just-denied intent (`INTENT_CONFIRMED_NOT_EXECUTED`) | not captured |
| Cancellation | yes | yes (Stop pressed while streaming, asserted) | Stop button visible while thinking (03); press not captured |
| Restart | worker restart: memory kept | worker restart: memory kept | Brain stop and restart in one PID-verified app process (07a, 07, 08) |
| Unavailable runtime | yes | yes | yes (07) |

## 1. What each item has reached

Legend: **I** implemented · **T** automated tests pass · **L** live-demonstrated in this session · **A** accepted by
the independent Codex review of this candidate · **G** integrated (on the integration branch, combined regression
gate passed) · **M** still mocked or simulated

| Capability | State | Evidence |
|---|---|---|
| UI ↔ Core/OI over the stdio integrated worker (WS-D1) | I T L A G | `run_uri_integrated_worker.py`, `worker_bridge.py`, `integrated_runtime.dart`; live UI test (real widgets, real worker) |
| Streaming answers (`answer.delta`) | I T L A G | live: 42 deltas, first token 0.45-0.79 s, 124-129 tok/s; screenshot 02 |
| Cancellation (Stop button → `oi_cancel`) | I T L A G | live: Stop pressed mid-stream in the UI, `CANCELLED` (worker and UI runs) |
| Reasoning tier (Fast/Thinking chip, progress count, no reasoning text) | I T L A G | live: NORMAL tier, 3,040 reasoning characters counted and not shown, 120-131 tok/s; screenshots 03, 04 |
| Supervised action: approve → `SETTLED_VERIFIED`; deny → `APPROVAL_DENIED`, nothing changed | I T L A G | live through the **Runtime v1 row** (Brain READY) and through the explicit deterministic row (Brain stopped); screenshots 05, 06 |
| Typed text never approves; approval bound to the card's digest; forged digest refused | I T L A G | unit tests; live `forged_digest` journey → `APPROVAL_DIGEST_MISMATCH`, memory unchanged |
| Refusal (destructive request with no qualified capability) | I T L A G | worker: `REFUSED_UNSUPPORTED` in a fresh session. UI-widget: in a session holding a just-denied intent Core returned `INTENT_CONFIRMED_NOT_EXECUTED`; asserted no card and memory unchanged |
| Unavailable runtime | I T L A G | live: `BRAIN_UNAVAILABLE` and nothing sent to a model; Brain status shows STOPPED; screenshot 07 |
| Restart: worker and Brain | I T L G | worker: a fresh process over the same client root kept memory. Brain (app, PID 11272, provenance in `screenshots/capture_run_11272_*.json`): 111 tok/s, then stopped and refused honestly, then restarted after a 60 s VRAM-release wait and answered at 117 tok/s; screenshots 07a, 07, 08 |
| Memory: remember (approval-gated) and list (deterministic client read) | I T L A G | live; Settings panel (screenshot 09) |
| Readiness and performance indicators | I T L A G | Brain state, model id, artifact match, and per-answer first-token time and tok/s shown live. **Degradation (OI-PERF-1) is not surfaced**: see PERF-W1 |
| Runtime v1 as the default Brain; explicit selection; no fallback | I T L A G | catalog live (screenshot 09); deterministic row only by explicit choice; other local models NOT_QUALIFIED |
| Deterministic paths without a model | I T L A G | presentation commands, memory list, Brain status, refusal and unavailable-runtime all work with the Brain stopped |
| Integrated server profile (Phase 2 rows + Runtime v1 row) | I T L A G | live under the C1 gates on 18300; identity proven |
| Launcher (`Launch URI Working System.bat`) | I T L A G | self-test: legacy root, foreign UI and port 8000 refused; signed identity proof required; wrong-key proof refused |
| Cloud providers: $5/month, single-use manual approvals, no calls | I T A G | 6 tests, network forbidden; activation **disabled**, no credentials |
| Living Companion default shell; Hybrid via Settings (WS-D4) | I T L A G | the classic shell closes the worker first and never contacts port 8000 (a saved `localhost:8000` is blocked) |
| Workspace context panel (Brain, model, approvals) | I T L A G | UI-1 repaired: shows the real Brain; approvals state Core's rule |
| Dashboard "Brain & models" card | **M** | still the Hybrid mock card, carrying a **Simulated** badge (screenshot 10). Not wired |
| Dashboard harness/permission captions read "(mock)" although the harness list is real (0/3 usable: no client-profile logins) | **M** (label only) | not edited; see §4; screenshot 10 |
| Tasks, Documents, work items, clients, permissions | **M** | the UI's existing simulator, every region badged **Simulated**; no backend serves them on the paired Core |
| Listening/speaking voice states | **M** (no source) | no voice layer in this integration |
| Multi-step plans, harness choice, escalation offers | I (OI) T, not wired to UI controls | events are received and shown as text/route chips; no plan-approval or provider-picker UI yet |

## 2. Regression and acceptance evidence

| Gate | Result |
|---|---|
| Frozen boundary (`ws_frozen_check.py`) | 121/121 Phase 1 checkpoint files byte-identical; no protected path changed or added (tracked + untracked) |
| Accepted chain on the combined materialized tree, `ws_chain1` (at `a80dc58`) | **ALL_PASS**: phase2 486/0, authority 134/0, phase1-full outcome identity (2,698 ids, the same 11 known failures), phase1-scope (outside = ∅, importers = ∅), residue |
| Accepted chain, final tree `ws_chain_final` (at `abe2f9b`) | **ALL_PASS**: phase2 486/0, authority 134/0, phase1-full outcome identity, phase1-scope, residue |
| Flutter full suite | 294 passed, 3 skipped (2 baseline live tests and the opt-in WS live test) |
| OI + WS Python | 182 passed, 16 skipped (opt-in live tests) |
| Live worker (final tree) | Brain stopped: 6 passed, 2 skipped; Brain READY: **8/8 passed** |
| Live UI journeys (final tree) | Brain stopped: passed (unavailable runtime, approve, deny, refusal, local command, restart). Brain READY: **passed** (normal response, reasoning, Stop/cancel, approve and deny through Runtime v1, refusal, local command, restart) |
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
| GPU-1 | Another session's benchmarks shared the GPU. Two concurrent 13.7 GB loads stalled both (`LOCAL_BRAIN_START_TIMEOUT`); I stopped my host and, on your instruction, waited for the GPU to be free. The OI start lock is per state directory, so it does not serialize starts across trees or other tools. A machine-wide GPU-use policy is still an owner decision (OI readiness §4) | GPU residency predictability |
| PERF-W1 | An immediate Brain restart gave **27 tok/s** (first start: 124). After a 60 s wait it gave 117 tok/s. This matches the VRAM-block-demotion state documented by the Adaptive Runtime research. The integrated worker has no OI `PerfMonitor`, so the UI shows the speed but no DEGRADED state or recovery option | responsiveness after restart |
| L-MD | Answer markdown renders as plain text (`**`) | readability |
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
