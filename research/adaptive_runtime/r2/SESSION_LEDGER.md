# Adaptive Runtime R2 — session ledger (monotonic, UTC)

Start of execution: 2026-10-08T18:13:56Z (first command of the R2 session).
Branch `research/adaptive-runtime`, worktree `C:\Users\cheta\Development\uri-adaptive-runtime`, base commit c041798.

## Acceptance criteria (defined before any R2 measurement)

| id | criterion | pass rule |
|---|---|---|
| AC1 | 128 MiB blocks under pressure, >= 10 independent loads | decode p50 per load >= 90 tok/s in >= 9 of 10 loads; no load below 60 tok/s; decision-turn p50 <= 1.3x the idle baseline; 0 errors |
| AC2 | pressure is real | default-block control loads under the same consumer reproduce the R1 collapse (decode p50 < 40 tok/s) in the majority of control loads |
| AC3 | no idle cost | 128 MiB vs default on an idle desktop, n >= 3 each: decode, decision, prefill 1k/8k/30k, vision within +/- 5 % (p50) |
| AC4 | correctness retained | 221-case suite (F,D,DG,C,H,S,O,L,P) + R,RH,V with 128 MiB: 0 score-changing cases vs `ue_cand_mtp2` / `repro20261008_mtp2`, 0 errors; both idle and under pressure |
| AC5 | sustained | soak >= 60 min with 128 MiB under pressure: 0 errors, first/last-third p50 within 10 %, restart + reconnect succeeds |
| AC6 | residency evidence | per-process Local / Non Local Usage recorded at load and end for every load; demoted loads identified by Non Local Usage, not only by throughput |
| AC7 | planner | unit tests pass; live run on idle and on pressured desktop selects the expected profile; headroom rule stated with the measurements behind it |
| AC8 | watchdog | isolated test: 0 false alarms across healthy loads, alarm on every pressured default load whose decode p50 < 60 tok/s; detection latency recorded |
| AC9 | NVMe | >= 3 loads per location in one session, same binary and hashes; storage and deployment implications written down |

Positive claims use only COMPLETED_WITH_RESULT evidence (JSON records with `healthy_end` true and no `fatal`).

## Timeline
| UTC | elapsed | event |
|---|---|---|
| 18:13:56 | 0:00 | session start; GPU owners checked (desktop 871 MiB, other session's CPU llama-server PID 7956, Ollama idle, no loaded models) |
| 18:15:48 | 0:02 | INCIDENT (detected 18:24): another session (Operational Intelligence host, worktree `uri-ws-final`, `python -m uri_operational_intelligence.host --minutes 60`) started the frozen Brain server (PID 16100, port 18470) on the GPU two minutes after this session's owner check had shown the GPU idle. This session's consumer-size probe (Ollama qwen3.5:0.8b at num_ctx 4096/16384/32768, 1.09/1.31/1.54 GB VRAM, ~10 s each, 18:21-18:22) ran next to it. At 18:24 PID 16100 showed Local 12,807 / Non Local 3,910 MiB (about 3.0 GB demoted beyond its 872 MiB host-visible share), i.e. the slow state. Causality is likely but not proven (the frozen configuration demotes 250-950 MiB on its own). No further GPU use by this session until PID 16100 exits; a GPU-owner guard is added to every R2 script so a load never starts next to a foreign GPU process. |
| 18:15-18:37 | 0:02-0:23 | GPU owned by the other session's Brain loads (PIDs 16100 18:15:48 → 13452 18:27 → 8096 18:32 → 10952 18:37, all `uri_operational_intelligence.host` 60/30-minute runs or short loads). This session's first campaign launch (18:29) stalled on a guard bug (its own command line matched `--block-cmd`); fixed. Second launch (18:30) waited 401 s for a 180 s quiet GPU, loaded the consumer at 18:37:04, and the per-load guard then saw a new foreign server (PID 10952, 1,602 MiB, loading) — INCIDENT 2: consumer resident ~35 s next to a foreign load. Consumer unloaded 18:37:3x and the campaign stopped. Fix: per-load guard with timeout 0 → consumer unloaded immediately on any foreign owner, re-wait 300 s quiet. |
| 18:44 | 0:30 | CORRECTION of incident 2: the "foreign" server seen at 18:37 (PID 10952) and again at 18:43 was this session's own pressure consumer — Ollama 0.34 runs its model in a child process `C:\Users\cheta\AppData\Local\Programs\Ollama\lib\ollama\llama-server.exe` (parent `ollama.exe`, 1,602 / 349 MiB), which the guard's name-only allow list did not recognise. Verified by loading the consumer alone and reading the parent chain. Incident 2 is withdrawn; incident 1 (PID 16100, Operational Intelligence host) stands. Guard now matches the parent name and executable path. |
| 19:05 | 0:51 | SESSION CUT (Claude usage limit). Pressure campaign `r2/run_r2_pressure.sh` left running unattended to completion (started 18:45:24Z; 6 of 15 loads done; it unloads the consumer and exits by itself; results in `evidence/r2P_*.json`, `evidence/r2_watch/`, console `evidence/r2_pressure_console.txt`). The chained launch of `run_r2_profiles.sh` was cancelled so no unattended GPU work continues after the campaign. |

## Interim results (6 of 15 pressure loads, 1.09 GB consumer, same binary/flags/hashes)

| load | blocks | decode tok/s p50 | decision s p50 | prefill 30k tok/s (TTFT s) | local / non-local MiB |
|---|---|---|---|---|---|
| r2P_sub128_r1 | 128 MiB | 27.6 | 3.83 | 933 (33.1) | 14,240 / 2,810 |
| r2P_sub128_r2 | 128 MiB | 103.1 | 1.55 | 719 (42.8) | 14,251 / 2,798 |
| r2P_default_r1 | 1 GiB | 25.0 | 4.24 | 1,584 (19.5) | 14,160 / 2,677 |
| r2P_sub128_r3 | 128 MiB | 98.9 | 1.60 | 743 (41.4) | 14,246 / 2,803 |
| r2P_sub128_r4 | 128 MiB | 103.6 | 1.58 | 726 (42.4) | 14,246 / 2,804 |
| r2P_default_r2 | 1 GiB | 24.7 | 4.25 | 1,565 (19.8) | — |

Reading so far: the 128 MiB candidate does not qualify as "retain performance under pressure" — 1 of 4 loads collapsed on decode (AC1 "no load below 60 tok/s" already failed) and every 128 MiB load under pressure halves the 30k prefill rate (TTFT 42 s vs 19.5 s) while the default halves decode instead. Demotion (~1.85-1.94 GB) appears at the end of load, is the same size in slow and fast loads, and which buffers are demoted is nondeterministic. The watchdog detected every degraded load (AT_RISK at ~15 s, DEGRADED at ~37-40 s) and stayed AT_RISK-only on the fast ones. The planner arithmetic (budget = 16,368 − used − 768) says `full` never fits with headroom; the fit-under-budget profiles are the evidence-supported alternative and are the next thing to validate.

## Remaining work (not started)
1. Finish reading the 15-load campaign; AC3 idle comparison with prefill (`run_r2_profiles.sh idle`, needs an idle GPU, ~20 min).
2. Planner-profile validation under the consumer (`run_r2_profiles.sh pressure`, ~25 min).
3. Suites (`run_r2_suites.sh`: sub128 idle, sub128 pressure, default pressure; ~15 min each) — AC4.
4. Soak 60 min, 128 MiB under pressure (`GGML_VK_SUBALLOCATION_BLOCK_SIZE=134217728 URI_R2_MODEL_DIR=C:/Users/cheta/Development/uri-adaptive-lab/models python r2/soak_r2.py --minutes 60`) — AC5.
5. NVMe vs HDD loads (3 + 3) — AC9. 6. Planner live runs idle/pressure, watchdog false-alarm count across all healthy loads. 7. `r2/summarize_r2.py`, fill report sections 1, 4-8, 11-13, verdicts, Codex review candidate.
