# URI Adaptive Runtime — Round 2 Qualification Report

**Status: research candidate. Nothing in this report is accepted, integrated or activated.** Branch
`research/adaptive-runtime` (worktree `C:\Users\cheta\Development\uri-adaptive-runtime`), building on
`ADAPTIVE_RUNTIME_RESEARCH_R1.md`. Frozen Runtime v1, `local_brain.json`, the Core and every other worktree are
untouched (section 13). No merge, push, cutover or model change was performed.

Owner authorisation: "URI Adaptive Runtime — R2 Qualification" (2026-10-08). Scope: qualify the 128 MiB Vulkan
suballocation-block candidate from R1 and establish reliable GPU memory management for the existing Brain; no engine
replacement, no Strata, no model switch, no rebuild of Runtime v1.

## 1. Executive findings

RESULTS_PENDING_SECTION_1

## 2. Acceptance criteria (defined before any R2 measurement)

| id | criterion | pass rule | result |
|---|---|---|---|
| AC1 | 128 MiB blocks under pressure, ≥ 10 independent loads | decode p50 per load ≥ 90 tok/s in ≥ 9 of 10 loads; no load below 60 tok/s; decision-turn p50 ≤ 1.3× the idle baseline; 0 errors | RESULT_AC1 |
| AC2 | the pressure is real | default-block control loads under the same consumer reproduce the R1 collapse (decode p50 < 40 tok/s) in the majority of control loads | RESULT_AC2 |
| AC3 | no idle cost | 128 MiB vs default on an idle desktop, n ≥ 3 each: decode, decision, prefill 1k/8k/30k, vision within ± 5 % (p50) | RESULT_AC3 |
| AC4 | correctness retained | 221-case suite (F, D, DG, C, H, S, O, L, P) plus R, RH, V with 128 MiB blocks: 0 score-changing cases vs `ue_cand_mtp2` / `repro20261008_mtp2`, 0 errors; idle and under pressure | RESULT_AC4 |
| AC5 | sustained | soak ≥ 60 min with 128 MiB blocks under pressure: 0 errors, first/last-third p50 within 10 %, restart + reconnect succeeds | RESULT_AC5 |
| AC6 | residency evidence | per-process Local / Non Local Usage recorded at load and at the end of every load; demoted loads identified by Non Local Usage, not only by throughput | RESULT_AC6 |
| AC7 | planner | unit tests pass; live runs on an idle and on a pressured desktop select the expected profile; headroom rule stated with the measurements behind it | RESULT_AC7 |
| AC8 | watchdog | isolated test: 0 false alarms across healthy loads, alarm on every pressured default load whose decode p50 < 60 tok/s; detection latency recorded | RESULT_AC8 |
| AC9 | NVMe | ≥ 3 loads per location in one session, same binary and hashes; storage and deployment implications written down | RESULT_AC9 |

Evidence rule (CLAUDE.md): only harness records with `healthy_end: true` and no `fatal`, suite runs with a written
`summary.json`, and watchdog/soak files written at normal exit support a positive claim.

## 3. Sources, versions and identity

| item | value |
|---|---|
| hardware | AMD Ryzen 9 5900X, 24,501 MiB RAM, AMD Radeon RX 7900 GRE 16,368 MiB (registry `HardwareInformation.qwMemorySize` 17,163,091,968 bytes); C: Lexar 500 GB NVMe SSD (100 GB free), D: Seagate ST1000DM010 1 TB SATA HDD (489 GB free) |
| OS / driver | Windows 11 Pro 10.0.26200; AMD driver 32.0.31041.1004 (2026-08-17); no driver, OS or GPU setting changed |
| engine | llama.cpp release b11425, Vulkan, win x64, pinned archive `D:\uri-model-lab\runtime\llama-b11425-bin-win-vulkan-x64\` — `llama-server.exe` sha256 `4fdc1a67a8c13334…`, `ggml-vulkan.dll` sha256 `3742b48f47a09eec…` (unchanged from the freeze record and R1) |
| model files | Qwen3.6-35B-A3B-UD-IQ3_S.gguf `66a3ca88…ec66`, mmproj-F16.gguf `8971ee4f…e887f`, mtp-qwen36-35b-a3b-Q4_K_M.gguf `40ca608f…8768`; hash-identical NVMe copies in `C:\Users\cheta\Development\uri-adaptive-lab\models\` (made in R1) used for all R2 loads unless a row says HDD |
| frozen command line | section 2 of `URI_RESIDENT_INTELLIGENCE_RUNTIME_V1_FREEZE.md`: `-c 32768 -ngl 999 -fa on -ctk q8_0 -ctv q8_0 -np 1 --jinja --reasoning-format deepseek --no-webui --load-mode none -b 2048 -ub 1024 --cache-ram 2048 --slot-prompt-similarity 0 --checkpoint-min-step 512 --ctx-checkpoints 16 --mmproj <mmproj> -md <mtp> --spec-type draft-mtp --spec-draft-n-max 2 -otd token_embd.weight=CPU` (the harness adds `--metrics`) |
| candidate | the stock environment variable `GGML_VK_SUBALLOCATION_BLOCK_SIZE=134217728` read by `ggml-vulkan.cpp` (b11510 source lines 4213-4221: default 1 GiB, capped by `max_memory_allocation_size`; `ggml_backend_vk_buffer_type_get_max_size` returns it, so `ggml_backend_alloc_ctx_tensors` packs tensors into ≤ 128 MiB buffers; a tensor larger than the block gets a buffer of its own size — the model has five such tensors: `output.weight` 398 MiB, `token_embd.weight` 398 MiB on the CPU, three `ffn_down_exps` of 136 MiB; the MTP draft has five, the vision projector none). No code change. |
| pressure consumer | installed Ollama 0.34.1 service holding its already-pulled `qwen3.5:0.8b` (Q8_0, 873 M parameters) through the API with `keep_alive`; measured `size_vram` 1,086,869,994 bytes at `num_ctx` 4096 (1.09 GB), 1.31 GB at 16k, 1.54 GB at 32k (`evidence/r2_consumer_probe.txt`). Nothing pulled or written; unloaded with `keep_alive: 0` after each campaign. |
| harness | `research/adaptive_runtime/bench_runtime.py` (R1, unchanged), `model_lab/run_bench.py` + `model_lab/lab/*` (frozen qualification suite, byte-identical to the phase-1 worktree copy), `model_lab/uri_engine/soak_final.py` (unchanged, wrapped by `r2/soak_r2.py`), Python 3.13.15, httpx 0.28.1, psutil 7.2.2, pytest 9.1.1 |
| R2 prototypes | `research/adaptive_runtime/r2/`: `gpu_guard.py`, `vram_planner.py`, `residency_watchdog.py`, `test_r2_units.py`, `run_r2_pressure.sh`, `run_r2_suites.sh`, `soak_r2.py`, `summarize_r2.py`, `SESSION_LEDGER.md` |

## 4. Session record and the GPU-sharing incident

RESULTS_PENDING_SECTION_4

## 5. 128 MiB suballocation blocks under pressure (AC1, AC2, AC6)

RESULTS_PENDING_SECTION_5

## 6. Idle cost and prefill at 128 MiB (AC3)

RESULTS_PENDING_SECTION_6

## 7. Regression suites (AC4)

RESULTS_PENDING_SECTION_7

## 8. Soak (AC5)

RESULTS_PENDING_SECTION_8

## 9. Launch-time VRAM budget planner (AC7)

Prototype `research/adaptive_runtime/r2/vram_planner.py` (read-only; it never edits `local_brain.json` and never
starts a server). It is the launch-time half of the memory management the brief asks for; the watchdog (section 10)
is the run-time half.

**Inputs.** Adapter size from the registry (`HardwareInformation.qwMemorySize`, 16,368 MiB; falls back to the pinned
constant), current adapter `Dedicated Usage` (everything other processes hold at that moment, desktop included), a
headroom, and an ordered list of profiles. **Budget** = total − used-by-others − headroom. The first profile in the
order whose measured device-local request fits the budget is chosen; if none fits, the smallest is chosen and the
expected demotion is reported instead of hidden.

**Profile table** (device-local requests from the R1 allocation ledger, resident/non-local from R1/R2 loads):

| profile | device request MiB | host-visible MiB | features kept | llama-server delta |
|---|---|---|---|---|
| `full` (frozen Runtime v1) | 15,626 | 872 | GPU vision, MTP, 32k | — |
| `vision_cpu` | 14,520 | ~900 | CPU vision (encode 5.0 s vs 1.6 s), MTP, 32k | `--no-mmproj-offload` |
| `no_mtp` | 14,491 | 498 | GPU vision, 32k, no draft (decode ~104 vs ~115 tok/s) | drop `-md … --spec-type draft-mtp --spec-draft-n-max 2 -otd token_embd.weight=CPU` |
| `vision_cpu_no_mtp` | 13,385 | 498 | CPU vision, 32k | both |

**Headroom rule (768 MiB default) and the measurements behind it.** Desktop idle band 433-900 MiB across R1/R2
sessions (dwm 295-337, Edge WebView 56, Claude app 50-124, ExitLag 83, the other session's CPU embedding server
222); window redraw / browser video adds ~200-400; the driver never handed out the last 55-90 MiB (adapter peak
16,277-16,313 of 16,368 under memory priority); a previous server's VRAM is released seconds (once ~2 min) after exit,
so the planner must sample after the GPU-owner guard, not before. 768 = burst 400 + reserve 90 + margin. The owner can
raise it for a heavier desktop; the planner prints the arithmetic so the choice is auditable.

**What the arithmetic says for this machine.** With the idle desktop at 465-871 MiB the budget is 14,729-15,135 MiB:
`full` (15,626) never fits with headroom, and does not fit even at headroom 0 unless the desktop is below ~740 MiB.
`vision_cpu` fits at idle (margin ~200-600 MiB). Next to the 1.09 GB consumer the budget is ~13,500 MiB and only
`vision_cpu_no_mtp` fits. This is the quantitative form of R1's finding that the frozen configuration is oversubscribed
by design, and it is why "retain every feature under a 1 GB external consumer" is not achievable on this card by
memory placement alone (section 12).

**Order policy.** Default `full, vision_cpu, no_mtp, vision_cpu_no_mtp` keeps MTP before GPU vision because R1/R2
measured the decode cost of losing MTP (~10 %) as larger than the cost of CPU vision for text turns (none) while the
image encode cost (5.0 s vs 1.6 s per image) only hits vision turns. The brief's preference for GPU vision is honoured
by the alternative order `full, no_mtp, vision_cpu, vision_cpu_no_mtp` (`--order`), a one-line switch; the
measurements for both branches are in section 5/6. **Blocks policy** (`--blocks always|when_oversubscribed|never`)
decides whether the 128 MiB environment variable is attached — the R2 verdict in section 12 sets the recommended value.

**Tests.** `r2/test_r2_units.py`: 8 planner tests (full never fits with headroom; fits only without headroom on an idle
desktop; `vision_cpu` next at idle; 1 GB consumer drops to `no_mtp`/`vision_cpu_no_mtp`; nothing-fits reports the
demotion; owner order; blocks policy; within-headroom risk class) — RESULT_PLANNER_TESTS. Live runs: RESULT_PLANNER_LIVE.
Validation loads of the chosen profiles under the consumer: section 5 (`r2V_*`).

## 10. Residency watchdog in isolation (AC8)

Prototype `research/adaptive_runtime/r2/residency_watchdog.py` (read-only; attaches to a llama-server by PID or by
its `--port`, polls every 5 s, writes CSV samples, JSONL transitions and a summary; never restarts or signals anything).

**Why two signals.** R1/R2 data show that the amount of demoted memory does not identify the slow state: 2.7 GB
non-local with 128 MiB blocks ran at 101-104 tok/s, 1.5 GB non-local with 256 MiB blocks ran at 45 tok/s, and in R2 the
slow and the fast 128 MiB loads carried the same ~1.85-1.94 GB demoted (section 5). So:

1. **residency** — per-process `GPU Process Memory\Non Local Usage` minus the profile's host-visible share
   (872 MiB for `full`) = demoted MiB; `partially_demoted` above 256 MiB → state `AT_RISK`;
2. **throughput** — passive decode rate from the server's own `/metrics` counters
   (`llamacpp:tokens_predicted_total` / `llamacpp:tokens_predicted_seconds_total` deltas) over windows that generated
   ≥ 32 tokens; below 0.6 × expected (110 tok/s) for two consecutive windows → `DEGRADED`; back above 0.8 × expected →
   `RECOVERED`. No extra load on the server. An optional active probe (24 tokens, only when the server is idle and no
   window produced tokens for 5 min) exists for quiet production hours and is off by default.

**Tests.** 7 state-machine/parser tests in `r2/test_r2_units.py` (healthy load no alarm; demoted slow load alarms after
two windows; demoted-but-fast stays `AT_RISK`, never `DEGRADED`; small windows ignored; recovery after restart;
Prometheus parser; guard parsing/allow list) — RESULT_WATCHDOG_TESTS. Isolated live results (one watchdog per
R2 server, started before the server, stopped when it exits): RESULT_WATCHDOG_LIVE

## 11. NVMe placement (AC9)

RESULTS_PENDING_SECTION_11

## 12. Qualification verdicts, risks and the Codex review candidate

RESULTS_PENDING_SECTION_12

## 13. Status ledger and boundary verification

RESULTS_PENDING_SECTION_13
