# Working System — publication and operational hardening plan

Date: 2026-10-09. Author: Claude. Branch `integration/ws-hardening-20261009`, worktree
`C:\Users\cheta\Development\uri-ws-hardening`, based on the accepted, published integration tip `68cac3d`.
This is the frozen plan for this phase. Changes to it are recorded in §7.

## 1. Verified baseline (primary evidence, 2026-10-09 01:20-01:40 IST)

| Item | Evidence |
|---|---|
| Integration branch `integration/working-system-20261008` | tip `68cac3d50b0b…`, tree `22c9492c…`, worktree clean, `037229c` is an ancestor, `git fsck` clean |
| Frozen boundaries | `scripts/ws_frozen_check.py`: `ok: true`, 121/121 Phase 1 files byte-identical, no protected path changed |
| Scope of `037229c..68cac3d` | 197 files. Every path is a UI candidate path (`569cf7c`), an OI candidate path (`9306dc1`) or a documented WS path. Edited candidate files: 4 Living Dart files (UI) and `oi_materialize_test_runtime.py`; `.gitignore` restored to frozen bytes (FB-1) |
| Canonical repository | `uri-repo` = `github.com/sche004-cyber/Uri`. Canonical development branch `integration/git-sync-20261008` = `037229c` (consolidation receipt). No `master`/`main` on that remote |
| Publication | `integration/working-system-20261008` pushed as a new branch (no force) = `68cac3d`; a fresh clone shows the same commit and tree `22c9492c` |
| Running processes | Legacy `\URIServer` on 8000 (untouched). Integrated dev server on 18300 from `uri-ws-final` (this work stream). Innovation Lab 18481/18482/18490/18491. Ollama with `qwen3.5:0.8b` resident (1.6 GB dedicated). Adaptive Runtime R2 campaign running (`run_r2_profiles.sh`, its own llama-server on 18497) |
| GPU | Contended by the Adaptive Runtime session at baseline time. Runtime v1 stopped |

Prior accepted findings carried into this phase: PERF-W1 (restart at 27 tok/s, no DEGRADED state), R-BUSY (alive
but silent worker leaves the UI busy), L-DASH (mock Dashboard Brain card), L-MD (raw markdown), GPU-1 (no GPU
coordination across sessions), R-SHUT, L-MUTEX, L-CLASSIC, L-RT, L-PLAN, OI-SEC-1.

Research inputs (read, not imported): Adaptive Runtime R1 (`research/adaptive-runtime`, committed report) and its R2
interim ledger. Measured facts used here: the frozen server requests 15.26 GiB device-local memory on a 16 GiB card;
the driver demotes 1 GiB blocks when another process holds ~1 GB, and decode then falls from 110-127 to ~25 tok/s for
the life of the process; the demotion is visible per process as "Non Local Usage" but its size does not separate slow
from fast loads, so only measured decode does. OI-PERF-1: 107-117 to 35-42 tok/s after eviction while running.

## 2. Acceptance criteria (defined before implementation)

| id | criterion | evidence required |
|---|---|---|
| H-AC1 | Publication: the accepted branch is on the canonical remote, no force, verified by a fresh clone | ls-remote + clone tree hash (done: §1) |
| H-AC2 | GPU lease: one machine-wide URI GPU lease (acquire, wait with timeout, release, automatic stale-owner recovery when the holder dies); a second URI GPU workload cannot start while it is held; nothing is ever terminated | unit tests incl. a real second process; live: Brain host vs a benchmark wrapper |
| H-AC3 | Contention detection: before a Brain start, foreign GPU processes are listed with their memory, and a budget check (card − others − unattributed vs the measured 15.26 GiB request) decides FITS / AT_RISK / CONTENDED (revised 2026-10-09, see §7). CONTENDED, an unmeasurable GPU and an unfinished VRAM release wait (do not start) and explain; only an explicit owner override starts anyway, is recorded, and the result is calibrated | unit tests with recorded census samples; live census with the real Ollama consumer |
| H-AC4 | Restart degradation: the cause of 27 vs 117 tok/s is investigated with measurements; the restart policy waits on a measured release signal, not a fixed delay; the post-start calibration classifies the instance | measurement record (release lag, restart immediately vs after release), live restart through the host |
| H-AC5 | Health: the worker reports READY / BUSY / DEGRADED / UNAVAILABLE / RECOVERING with reasons, measured decode, calibration and GPU state; the DEGRADED threshold is justified by measured distributions | bridge tests; live READY and live DEGRADED (real contention) |
| H-AC6 | Recovery: a Restart Brain action exists, is refused while a turn runs, never bypasses Core, and the UI shows progress (RECOVERING) and the outcome | bridge tests + live restart from the UI or worker |
| H-AC7 | Worker failure: an alive-but-unresponsive worker and a stalled turn are detected within a bounded time; the UI offers Stop and Restart worker; a restart never retries an uncertain action and says the outcome is unknown | Dart tests with a fake worker; live: suspended worker process |
| H-AC8 | Dashboard Brain card shows real worker data (model, provider, backend, readiness, thinking mode, measured performance, GPU condition, errors, recovery) and no mock badge when it is real; mock remains badged without the integrated worker | widget tests both modes; real-app screenshot |
| H-AC9 | Markdown in Brain answers is rendered (headings, bold, italic, inline code, code blocks, lists) without links executing or HTML | widget tests; real-app screenshot |
| H-AC10 | No regression: frozen check ok; accepted chain ALL_PASS with the same 11 known Phase 1 failures; Flutter and OI/WS suites pass; live worker and UI journeys pass with Runtime v1 | chain summary + suite logs + live JSON |
| H-AC11 | Independent Codex review accepts the candidate (ACCEPT or ACCEPT WITH FINDINGS, findings repaired or recorded) | Codex verdict file |
| H-AC12 | Integration: canonical development branch fast-forwarded to the accepted tip only after H-AC10 and H-AC11; receipt with commits, checksums, remote confirmation; no cutover | receipt + ls-remote + clone |

Out of scope (RED, owner only): production cutover, `\URIServer`, production shortcuts/tasks, paid APIs, credentials,
force push, terminating other sessions.

## 3. Design (smallest additions; accepted modules reused, not edited)

1. `uri_operational_intelligence/gpu_lease.py` (new). Machine-wide lease in `%LOCALAPPDATA%\URI\gpu\`: an OS byte lock
   held for the holder's lifetime (the OS frees it when the holder dies, which is the stale-owner recovery) plus a
   descriptive `lease.json` and an append-only history. GPU census from Windows "GPU Process Memory" / "GPU Adapter
   Memory" counters; card size from the display-adapter registry key. Budget rule from the measured request. CLI
   `status | census | run --purpose ... -- <command>` so benchmarks in other sessions can hold the lease.
2. `scripts/ws_brain_host.py` (new; the launcher uses it instead of `uri_operational_intelligence.host`). Uses the
   accepted `RuntimeManager` unchanged: lease → census → wait while CONTENDED (unless override) → wait for measured VRAM
   release → `ensure_ready` → calibration decode → report. Reports `brain_host.json` into the client's
   `control/oi/` (readable by the guarded worker without widening its guard) and serves restart/stop requests
   written there by the worker. Periodic residency samples while READY.
3. `uri_operational_intelligence/brain_health.py` (new). Pure function combining readiness, host report, the accepted
   `PerfMonitor` (fed from `answer.done` timings), and busy state into the five states with reasons and recovery options.
4. `worker_bridge.py` (WS-owned): commands `brain_health` (open while busy), `brain_restart` (refused while busy),
   `oi_turn_status` (open while busy: job alive, age, seconds since its last event). Feeds `PerfMonitor`.
5. UI (WS files + the Dashboard tile): health polling, state chip, real Dashboard Brain card, worker liveness monitor
   (probe with a bound longer than the worker's longest legitimate block, `JOIN_S`=30 s), Restart worker
   (kill + respawn; the interrupted turn is marked outcome unknown and never retried), minimal safe markdown renderer
   (no new dependency).
6. Launcher: uses the new host; refuses a second UI instance from the same build; keeps all legacy refusals.
7. Scope guards: new exact paths added to `ALLOWED_NEW`/`WS_EXACT` under owner decision WS-D3 (exact paths only).

## 4. Task ledger

Status ladder: Researched → Planned → Prototyped → Implemented → Tested → Independently Accepted → Frozen.

| id | task | status |
|---|---|---|
| T0 | Baseline verification, publication of `68cac3d` | Tested (H-AC1 met) |
| T1 | GPU lease + census + budget | Planned |
| T2 | Brain host (release wait, calibration, report, control) + restart measurement | Planned |
| T3 | Health model + bridge commands | Planned |
| T4 | Worker failure handling (UI liveness, restart worker) | Planned |
| T5 | Dashboard Brain card | Planned |
| T6 | Markdown | Planned |
| T7 | Launcher + materialization + scope guards | Planned |
| T8 | Regression chain, suites, live journeys, real-app captures | Planned |
| T9 | Codex review rounds | Planned |
| T10 | Publication + fast-forward of the canonical development branch + receipts | Planned |

## 5. Test levels (never merged in reporting)

Automated simulation (Python/Dart unit tests with fakes) · worker-level integration (real worker process, scripted) ·
real widget tests (Living widgets against the real worker) · physical Windows application (built exe, captured).

## 6. Risks

GPU availability depends on other sessions (the Adaptive Runtime campaign holds it at baseline); live measurements wait
for a free GPU per the owner's standing instruction. Performance counters cost ~1-2 s per PowerShell sample; sampling
stays off the turn path.

## 7. Change log

- 2026-10-09: initial version.
- 2026-10-09 (correction, before any acceptance): H-AC3 first said "CONTENDED when free < request". Live evidence
  disproved it as a start rule: with only the desktop and a URI window open the free memory was 15.2 GB (78 MB short of
  the request), yet the instance loaded healthy (calibration 90.8 tok/s), and earlier WS runs with the app open ran at
  111-131 tok/s. Adaptive Runtime R1 shows the frozen server tolerates 250-950 MiB of demotion; the collapse needs a
  ~1 GB consumer (shortfall ~1.2-1.4 GB). Rule now: CONTENDED (wait) at a shortfall of one 1 GiB demotion block;
  smaller shortfalls start as AT_RISK and the post-start calibration classifies the instance (DEGRADED if slow).
- 2026-10-09: quiet window (180 s, persisted machine-wide) added after contention, because a host started on a
  momentarily free GPU between another session's benchmark loads (observed live; the host was stopped at once).
- 2026-10-09: Codex hardening round 1 REJECT (5 findings: stopped load could spawn after lease release; restart vs new
  turn race; unmeasurable GPU proceeded; release-wait timeout proceeded; hang before the turn reply undetected). All
  confirmed in source and repaired with tests. Rounds 2-5 REJECT, round 6 ACCEPT (see WS_INDEPENDENT_AUDIT.md).
- 2026-10-09 (correction after live validation): the CONTENDED shortfall was first one demotion block (1 GiB). A live
  start at a 913 MB shortfall (another session opened three app windows, ~1 GB of GPU memory) came up at 29.9 tok/s
  and was correctly reported DEGRADED by the calibration. The threshold is now half a block (512 MiB): a 913 MB
  shortfall waits. The 78 MB shortfall that loaded healthy stays AT_RISK.
- 2026-10-09 (live finding): GPU apps of another session opened after the Brain loaded evicted 1.6 GB of it (decode
  141 -> 27-38 tok/s) while health still showed the start calibration. The host now re-measures speed when its 60 s
  residency sample shows the Brain's system-memory share grew by >= 512 MiB.
  Superseded after Codex rounds 7-8: a host-side re-measurement cannot be guaranteed not to compete with a user
  turn, so the host now only REPORTS the residency growth (warning GPU_MEMORY_TAKEN_AFTER_LOAD with Restart Brain,
  state stays READY/BUSY) and sends nothing to the Brain after the start calibration; real-answer timings decide
  DEGRADED. Fewer GPU requests also suits the open SAFE-1 question.
- 2026-10-09 (finding, H-AC4): the restart experiment disproved "an immediate restart is slow because VRAM is not yet
  released": release takes 1.5-1.9 s and a load takes ~94 s; immediate restarts were healthy (2/2) and a cold start
  with the desktop only was slow (1 of 5 loads). PERF-W1's 27 tok/s was the nondeterministic demotion, not the restart.
