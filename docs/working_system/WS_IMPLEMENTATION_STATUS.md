# Working System hardening — implementation status

Branch `integration/ws-hardening-20261009` (worktree `C:\Users\cheta\Development\uri-ws-hardening`), based on the
accepted and published integration tip `68cac3d`. Status ladder: Researched → Planned → Prototyped → Implemented →
Tested → Independently Accepted → Frozen. "Tested" names the level (simulation / worker / widget / app; see
`WS_TEST_EVIDENCE.md`). Nothing here is Frozen; nothing is in production.

| Item | What exists | Status |
|---|---|---|
| Publication of the accepted integration | `uri-repo/integration/working-system-20261008` = `68cac3d`, new branch, no force; fresh-clone tree identical | Done (receipt §7) |
| GPU lease (`uri_operational_intelligence/gpu_lease.py`) | Machine-wide OS-lock lease, wait/timeout, stale-owner recovery, overdue report, history; `run` wraps a workload in the holder's kill-on-close job; never terminates other processes | Implemented · Tested (simulation with real processes; live: refused while another session held it, queued hand-over 0.24 s) · Independently Accepted (Codex hardening round 10 at `9ae28f4`, ACCEPT WITH FINDINGS) |
| GPU census + budget | Windows per-process and adapter counters; FITS / AT_RISK / CONTENDED with the measured request (15,626 MiB) and a half-block (512 MiB) shortfall rule (first 1 GiB; corrected after a live slow start, plan §7); explanation names consumers; persisted quiet window (180 s) | Implemented · Tested (simulation + live census) · Independently Accepted (round 10) |
| Brain host (`scripts/ws_brain_host.py`) | Lease → contention wait → measured VRAM release wait → accepted `RuntimeManager` → calibration bound to the server instance → report; residency alert after load (no request to the Brain after the start calibration); explicit restart/stop/start with DONE markers; stop honored during load; heartbeat | Implemented · Tested (simulation; live: contention wait, AT_RISK start 90.8 tok/s, launcher reuse) · Independently Accepted (round 10) |
| Health model (`brain_health.py` + bridge `brain_health`) | READY / BUSY / DEGRADED / UNAVAILABLE / RECOVERING from accepted readiness, host report and real-turn timings (accepted `PerfMonitor`), keyed to the verified server instance; threshold 60 tok/s with its measured provenance | Implemented · Tested (simulation; live worker: UNAVAILABLE/GPU_CONTENDED) · Independently Accepted (round 10) |
| Restart degradation (PERF-W1) | Investigation and policy: measured release wait + calibration | see `WS_TEST_EVIDENCE.md` §H-AC4 |
| Worker failure handling (R-BUSY) | `oi_turn_status`; UI liveness monitor (probe bound 40 s > worker's 30 s join), hang-before-reply detection, Restart URI without retry, stale-reply isolation; restart gate on turns while a Brain restart is pending | Implemented · Tested (simulation; live worker: suspended process detected) · Independently Accepted (round 10) |
| Dashboard Brain card | Real worker report (provider, model, engine, state, speed with source, thinking depth, GPU, reasons, recovery buttons); mock tile badged without the worker | Implemented · Tested (widget simulation) · Independently Accepted (round 10) |
| Markdown | Dependency-free subset renderer; links never opened; HTML literal | Implemented · Tested (simulation) · Independently Accepted (round 10) |
| Launcher | Uses the Brain host; reuses a live host; refuses a second window; keeps legacy refusals; `-OverrideGpu` owner flag | Implemented · Tested (live launches) · Independently Accepted (round 10) |
| Scope guards / materialization | Four exact paths added under WS-D3; materializer copies the host | Implemented · Tested (frozen check) · regression chain: see evidence |

## Still simulated (badged in the UI)

Tasks, Documents, connected clients, permissions, harness discovery and the selected harness (no paired-Core backend);
Listening/Speaking previews; cloud providers (interfaces only, activation disabled).
