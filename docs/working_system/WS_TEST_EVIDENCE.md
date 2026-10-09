# Working System hardening — test evidence

All evidence files are under `docs/working_system/hardening/evidence/` and `docs/working_system/hardening/screenshots/`
unless noted. Levels are never merged: **SIM** = automated simulation (fakes, recorded counter samples, real OS locks
and child processes where stated) · **WORKER** = scripted driver of the real integrated worker over the real server,
Core and Runtime v1 · **WIDGET** = the real Living widgets in the Flutter test harness against the real worker ·
**APP** = the built Windows executable, captured on screen.

Runtime tree for every live run after 08:00: `C:\Users\cheta\Development\uri-ws-hard`, materialized from `9f2545a`
(code identical to the Codex-accepted `9808fb6`); host and lease-rule changes after that were copied in and are listed
in §6. The earlier tree (from `99f8041`, before the Codex repairs) was discarded; results from it are marked
"pre-repair" and are not used as acceptance evidence.

## 1. Automated suites

| Suite | Commit | Result |
|---|---|---|
| `tests/ws/test_ws_hardening.py` | `2083724` | 43 passed (SIM; real OS locks and child processes for the lease; real HTTP endpoint for calibration) |
| OI + WS Python (`tests/ws tests/oi`) | see §7 | see §7 |
| Flutter `test/ws` | `2083724` | 35 passed (SIM) |
| Flutter full suite | see §7 | see §7 |
| Accepted regression chain | see §7 | see §7 |

## 2. Scenario matrix (mandate §6)

| Scenario | Level | Evidence | Result |
|---|---|---|---|
| Cold Brain startup | WORKER/live host | `restart_exp_2.json` (cold run), host reports | load ~94-96 s; calibration classifies: healthy 124-156 tok/s; one cold load slow (31.7 tok/s) → reported DEGRADED |
| Warm restart | WORKER | `restart_exp_2.json`; `worker_live_20261009-081634.json` `brain_restart` | 4/4 restarts healthy (151-158 tok/s); restart through the worker: RECOVERING 88 s then READY 141 tok/s, first answer 102 tok/s |
| Restart degradation investigation | WORKER | `restart_exp_2.json` | VRAM release after kill 1.5-1.9 s (n=3) vs ~94 s load: an immediate restart cannot allocate before release; immediate restarts healthy (2/2). PERF-W1's slow state = nondeterministic demotion (1 of 5 loads with the desktop only), not restart timing |
| GPU contention (foreign) | live host | host reports; `H04`, `H05` | Ollama 1.6 GB → WAITING_FOR_GPU with explanation; another session's 3 app windows (~1 GB) → start at 913 MB shortfall came up at 29.9 tok/s → DEGRADED + Restart Brain offered (threshold then tightened, plan §7) |
| Eviction after load | live host + WIDGET | `ws_ui_live_hardening.json` (27-38 tok/s with health still READY) → fix; host recalibration at 08:37:16 (`RESIDENCY_CHANGED`) → DEGRADED 34 tok/s | Detected within one residency period after the fix |
| Cross-session resource contention (URI lease) | live | `gpu_lease_history_20261009.jsonl` | Text-intelligence session held the lease (90 min declared); my experiment refused (`GPU_LEASE_HELD`); hand-over 0.24 s after my release; nothing terminated |
| Quiet window | SIM + live | tests; live: host started in a gap between another session's loads (observed, stopped) → fix + persisted window | — |
| Unexpected worker exit | WIDGET | `ws_ui_live_hardening.json` `worker_exit_restart_uri` | real worker killed (pid 5080) → banner → Restart URI → new worker (pid 4356) answered; open card withdrawn, nothing approved |
| Worker unresponsive but alive | WORKER + SIM | `worker_live_20261009-081634.json` `unresponsive_worker`; Dart tests | suspended process: probe silent for its bound, alive throughout, reply arrives after resume, FIFO preserved; UI detection and Restart URI in SIM |
| Model unavailable | WORKER (Brain waiting for GPU) | `worker_live_20261009-020446.json` | health UNAVAILABLE / GPU_CONTENDED with explanation; question → honest BRAIN_UNAVAILABLE; deterministic actions still work |
| Mid-stream cancellation | WORKER + WIDGET | both live receipts | CANCELLED |
| Approval and denial | WORKER + WIDGET | both live receipts | SETTLED_VERIFIED / APPROVAL_DENIED, memory unchanged on deny |
| Destructive request refusal | WORKER | `worker_live_20261009-081634.json` | REFUSED_UNSUPPORTED, no card |
| Restart refused while a turn runs | WORKER | same | TURN_IN_PROGRESS; health BUSY |
| Core restart | — | not exercised in this phase (integrated server restarted between runs only) | not claimed |
| UI reconnect | WIDGET | `restart` journey: fresh worker over the same client root, memory preserved (5 facts) | pass |
| Legacy server present | APP/launcher | legacy `\URIServer` on 8000 running throughout; launcher refusals unchanged (self-test §7) | never contacted |
| Repeated application launch | APP/launcher | launcher output "Brain host: already running … reused"; second-window refusal | pass |
| Real Dashboard Brain card | WIDGET + APP | `dashboard_brain_card_real` ("141 tok/s · speed check at start"); `H05` (DEGRADED, 30 tok/s, GPU CONTENDED, reasons) | pass |
| Markdown | WIDGET | `markdown_rendered` (3 list items, no raw `**` shown) | pass; APP capture not taken (INC-1) |
| Health banner / chip | APP | `H04` ("Slow · 30 tok/s", explanation, GPU users, Restart Brain) | pass |

## 3. Incidents and anomalies

- **EXP-1**: first restart-experiment run after the 06:52 reboot: the server reset the connection on its first
  request, log truncated. Not reproduced (next run 156 tok/s). The host reports such a case as CALIBRATION_FAILED.
- **Unclean reboot 06:52** (Kernel-Power 41) after the Adaptive Runtime chain stopped mid-load at ~02:55; no process
  of this phase was using the GPU then.
- **INC-1**: during scripted APP capture another session's app window (companion-voice) came to the foreground; one
  click and one typed sentence of the capture script may have reached that window instead of URI. GUI automation was
  stopped immediately; no further input was sent. The owner should know their companion-voice session may have
  received the text "Give three benefits of regular backups as a markdown bullet list, …".

## 4-6. (filled at the end: performance summary, levels not reached, files copied into the runtime tree)

## 7. Final gates

(filled when the chain and suites finish)
