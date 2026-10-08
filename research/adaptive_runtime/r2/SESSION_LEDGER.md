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
