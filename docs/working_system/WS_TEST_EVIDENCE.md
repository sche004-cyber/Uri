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
| GPU contention (foreign) | live host | Ollama case: host report text quoted in the session log (02:05, not committed as a file); 913 MB case: `brain_host_report_0858_before_freeze.json` (start fit AT_RISK −913.5 MB; the 29.9 tok/s start calibration was later overwritten in that file by the 33.7 tok/s re-measurement); `H04`, `H05` | Ollama 1.6 GB → WAITING_FOR_GPU with explanation; another session's 3 app windows (~1 GB) → DEGRADED + Restart Brain offered (threshold then tightened, plan §7) |
| Eviction after load | live host + WIDGET | `ws_ui_live_hardening.json` (27-38 tok/s with health still READY) → fix; host report `brain_host_report_0858_before_freeze.json`: start at a 913.5 MB shortfall (AT_RISK under the then 1 GiB rule) → DEGRADED; re-measurement at 08:37:16 with reason `RESIDENCY_CHANGED` → 33.7 tok/s, still DEGRADED | Re-measurement observed once live with an intermediate version; that mechanism was then replaced (Codex r7-r8) by a reported warning with no request to the Brain (SIM-tested; not observed live, no Brain loaded after SAFE-1). Detection latency not measured |
| Cross-session resource contention (URI lease) | live | `gpu_lease_history_20261009.jsonl` | Text-intelligence session held the lease (90 min declared); my experiment refused (`GPU_LEASE_HELD`); hand-over 0.24 s after my release; nothing terminated |
| Quiet window | SIM + live | tests; live: host started in a gap between another session's loads (observed, stopped) → fix + persisted window | — |
| Unexpected worker exit | WIDGET | `ws_ui_live_hardening.json` `worker_exit_restart_uri` | real worker killed (pid 5080) → the Restart URI button is shown → the controller's `restartWorker()` (the method the button calls) was invoked directly in a real async zone, because the widget tester's fake zone does not advance real process I/O → new worker (pid 4356) answered; open card withdrawn, nothing approved. The button tap itself is covered only at SIM level; an APP-level click was **not** verified |
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
- **SAFE-1**: second unclean hard hang at ~08:58 (host heartbeat and chain log both stop at 08:58:22-08:58:32; reboot 09:14:35, BugcheckCode 0). At that time: this phase's Brain resident and DEGRADED (3,678 MiB in system memory in the last residency sample; receipt `brain_host_report_0858_before_freeze.json`, the lease acquisition at 08:30 without a release in `gpu_lease_history_20261009_after_freeze.jsonl`), the regression chain in phase1-full, and another session's four app windows. The interrupted chain output is kept as `evidence/ws_hardening_chain_interrupted_0858` in the gate tree; the chain was re-run afterwards with no Brain loaded. No Brain was loaded again in this phase after the hang.
- **INC-1**: during scripted APP capture another session's app window (companion-voice) came to the foreground; one
  click and one typed sentence of the capture script may have reached that window instead of URI. GUI automation was
  stopped immediately; no further input was sent. The owner should know their companion-voice session may have
  received the text "Give three benefits of regular backups as a markdown bullet list, …".

## 4. Performance summary (measured, Runtime v1, this card)

| Condition | Decode tok/s | Source |
|---|---|---|
| Healthy start calibration (160-token decode) | 124.6-158.1 | `restart_exp_2.json` (151-158), host reports (124.6, 141.2, 148.0) |
| Real answers, healthy | 101.8-131.1 | `worker_live_20261009-081634.json` |
| Demoted start (desktop only, 1 of 5 loads) | 31.7-32.4 | `restart_exp_2.json` cold |
| Evicted after load by another session's apps | 27.3-38.3 (real answers), 33.7 (re-measurement) | `ws_ui_live_hardening.json`, `brain_host_report_0858_before_freeze.json` |
| VRAM release after a stop | 1.5-1.9 s | `restart_exp_2.json` |
| Load time (frozen argv, artifact check + load) | 93.5-96.2 s | `restart_exp_2.json` |

## 5. Levels not reached

- APP-level click of Restart URI and Restart Brain (only SIM taps; live paths via the controller / worker command).
- APP-level markdown answer (INC-1 stopped GUI automation).
- Core (integrated server) restart while the UI is open: not exercised.
- Live observation of the final residency-warning mechanism (no Brain loaded after SAFE-1 hang 2).

## 6. Runtime tree provenance

`uri-ws-hard` was materialized from `9f2545a` (code = Codex-accepted round-6 `9808fb6`). Copied in afterwards for the
live runs: `scripts/ws_brain_host.py` and `tests/ws/test_ws_hardening.py` at `1af99e4`, `uri_operational_intelligence/gpu_lease.py`
at `2083724`. The live UI-widget and worker runs therefore used the host and lease versions of those commits, not the
final ones (the final host no longer re-measures; the final rule is identical to `2083724`'s). No Brain run used the
final `ws_brain_host.py`.

## 7. Final gates

| Gate | Tree / commit | Result |
|---|---|---|
| Frozen check (`scripts/ws_frozen_check.py`) | worktree, final tip | see receipt §7 |
| Flutter full suite | `1401aba` (content = `9ae28f4`) | 313 passed, 3 skipped (session-reported; output not committed) |
| OI + WS Python | `1401aba` | 226 passed, 20 skipped (session-reported; output not committed) |
| WS Python (`test_ws_hardening`, `test_ws_worker_bridge`, `test_ws_cloud_and_composition`) | final docs commit (code = `1401aba`) | **65 passed** (`hardening/evidence/pytest_ws_final.txt`) |
| Flutter `test/ws` | same | **36 passed** (`hardening/evidence/flutter_test_ws_final.txt`) |
| Chain: phase2 | gate tree `uri-ws-gate3` from `2083724` | **486 passed / 0 failed / 2 skipped** (PASS) |
| Chain: authority | same | **134 passed / 0 failed** (PASS) |
| Chain: phase1-scope | same | PASS (outside Phase 2 scope = ∅; importers of Phase 2 = ∅; 98 frozen files byte-identical) |
| Chain: residue | same | PASS |
| Chain: phase1-full outcome identity | same | **NOT ESTABLISHED.** Run 1 (09:18-09:41): 2,698 ids, missing = added = ∅, two outcome changes vs the accepted baseline: `test_gemma_worker_mcp.LiveOllamaIntegrationTests::test_live_ollama_status_and_model` passed → skipped (Ollama not running after the reboot) and `test_phase1_offline_components::test_offline_checkpoint_restore_hashes_and_no_application_start` passed → failed (`FileNotFoundError: work\c1\checkpoints\c3-provisional-source.zip`: the local Phase 1 checkpoint fixtures were not copied into the new gate tree). Both are environment/fixture causes, not code: the fixtures were then copied from the canonical Phase 1 worktree (byte-identical to the previous gate tree's) and an idle Ollama started. Run 2 was cut off by SAFE-1 hang 3 at ~78%. The chain's own verdict for this tree is therefore FAIL/incomplete, and no claim of Phase 1 regression identity is made for this phase |

The earlier chain run (`evidence/ws_hardening_chain_interrupted_0858`) was cut off by hang 2 during phase1-full.
