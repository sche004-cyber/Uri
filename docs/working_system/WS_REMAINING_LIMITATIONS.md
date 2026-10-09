# Working System — remaining limitations after hardening

Status on branch `integration/ws-hardening-20261009`. Each item says what is missing, why, and its effect. Items the
hardening closed are listed at the end with the evidence that closed them.

## Still open

| id | limitation | effect | owner action / next step |
|---|---|---|---|
| CUT-1 | No production cutover. The live PC runs the legacy `\URIServer` on 8000 (restarted by its scheduled task after the 2026-10-09 06:52 reboot); shortcuts point to the legacy app | The working system is a development installation started by `Launch URI Working System.bat` | Owner decision (RED) |
| GPU-2 | The GPU lease coordinates URI workloads that use it (Brain host, `gpu_lease run`). A session that does not use it (the Adaptive Runtime campaign scripts, Ollama) is only *detected* by the census; URI waits for it but it does not wait for URI | Another session's benchmark can still start next to a resident Brain (its own guard waits for memory, so in practice it waits; nothing prevents a non-cooperating tool) | Owner: ask other sessions to wrap GPU jobs in `python -m uri_operational_intelligence.gpu_lease run --purpose benchmark -- ...` |
| GPU-3 | AT_RISK band: a start with a shortfall under half a 1 GiB demotion block (512 MiB) is allowed and then classified by calibration. Which buffers the driver demotes is nondeterministic (Adaptive Runtime R2) | A load can come up slow; it is then shown as DEGRADED with Restart Brain | Adaptive Runtime research (budget planner) may tighten this |
| GPU-4 | The census costs ~5-6 s (PowerShell counters) | Pre-start checks and the 60 s residency samples are slow; never on the turn path | Acceptable; a native counter reader would be faster |
| R-SHUT | A Core call that outlives the 30 s shutdown join cannot release its approval card | The server's 15-minute idle expiry releases it | Carried from the accepted integration |
| R-STALL | A turn stalled inside a blocking Core call cannot be cancelled in-process; the user is told and offered Restart URI, which ends the worker (outcome reported as unknown, never retried) | Recovery costs a worker restart | By design (no silent retry) |
| L-MUTEX | One worker per client root; the launcher refuses a second window of the same build | The classic interface's supervised screens cannot run while Living holds the worker | Carried |
| L-CLASSIC | The classic shell is blocked when its saved server is the legacy port 8000 | Carried | Carried |
| L-RT | The runtime is a materialized tree (frozen `runtime_identity.py` needs HEAD `e8e3b65`) | Every code change must be re-materialized into the runtime tree | Carried (CONS-7) |
| L-SIM | Tasks, Documents, clients, permissions, harness discovery regions remain simulated (badged); the paired Core has no backend for them | Badged SIMULATED in the UI | Future phases |
| L-PLAN | Plan/harness picker and voice not built in this UI | — | Future phases |
| OI-SEC-1 | Runtime v1 listens on 127.0.0.1:18470 without an API key | Local processes can query the Brain | Accepted by the owner (WS-D2) |
| CLOUD | Cloud providers: interfaces and the $5/month single-use approval policy exist; activation is disabled, no credentials | No cloud Brain | Owner decision (RED) |
| MD-1 | The markdown renderer is a deliberate subset (no tables layout, no images, links shown as text only) | Tables render as monospace text | Acceptable |

## Closed by the hardening

(Evidence references are in `WS_TEST_EVIDENCE.md`.)

| former id | what changed |
|---|---|
| GPU-1 | Machine-wide URI GPU lease, census with the measured budget rule, contention wait with explanation, persisted quiet window, owner override |
| PERF-W1 | Restart waits for measured VRAM release; post-start calibration; DEGRADED state with Restart Brain |
| R-BUSY | Liveness monitor (alive-but-silent and hang-before-reply detection), Restart URI without retry |
| L-DASH | Dashboard Brain card shows the real worker report |
| L-MD | Brain answers render markdown |
