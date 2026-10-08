# URI Adaptive Runtime — Research & Experimental Development, Round 1

Status: **RESEARCH REPORT — nothing accepted, integrated, merged, pushed or activated.**
Session: 2026-10-08, start 16:38:08Z (monotonic ledger in section 13), hard limit 4 h (20:38:08Z).
Branch / worktree: `research/adaptive-runtime` at `C:\Users\cheta\Development\uri-adaptive-runtime`, created from the
published baseline `037229c` (`integration/git-sync-20261008`). Research-owned storage outside the repo:
`C:\Users\cheta\Development\uri-adaptive-lab\` (runtime binaries, llama.cpp source, hash-identical NVMe copies of the
pinned model files). Frozen components untouched (section 11 verification).

Owner authorisation: this round is an explicit owner request. The Runtime v1 freeze record (section 14) lists
"a reproducible correctness/stability defect of the frozen runtime" and "a major upstream inference improvement with a
credible, measured expected benefit" as valid reopening criteria; section 1 below reports a reproducible performance
defect of the frozen configuration, which independently satisfies the first criterion.

## 1. Executive findings

1. **The frozen Runtime v1 configuration has a reproducible performance defect: it oversubscribes the 16 GB card.** Its
   llama-server requests 15.26 GiB of device-local memory (weights 12.34, vision projector 1.08, MTP draft 1.13, KV and
   compute 0.73) on an adapter that can give one process 15.0-15.6 GB next to the desktop. The AMD driver demotes 0.25-1.8
   GB of 1 GiB suballocation blocks to system memory; which block is demoted is not deterministic. When a weight block is
   demoted, every decode step streams it over PCIe: **24.7 tok/s decode and 4.4 s decision turns instead of 110-127 tok/s
   and 1.3-1.5 s**, stable for the life of the process, with prefill nearly unaffected. This is the "24 tok/s under GPU
   memory pressure" phenomenon in the brief, now attributed and reproduced on demand (one 1.09 GB GPU consumer next to the
   server is enough; section 6.3). The freeze record's telemetry (adapter dedicated usage only) could not see it.
2. **It is not an engine problem.** Decode is 103-104 tok/s at kernel level on both the pinned b11425 and upstream
   b11510 (identical to the freeze record); prefill 1,850-2,780 tok/s; prompt-cache reuse, cancellation, timeouts and
   stability all behave as accepted. Upstream b11510 is +1-4% at kernel level and neutral at server level. Strata remains
   not applicable; a fork, a dedicated engine and the ROCm/HIP path (no device on this driver, four arrangements tried)
   are rejected again.
3. **Memory priority is not a mitigation.** `GGML_VK_ENABLE_MEMORY_PRIORITY=1` (stock env, all ggml allocations at
   priority 1.0) changes nothing against another process: identical 25 tok/s and identical demoted split under pressure.
   `-ub 512` frees nothing useful and collapses 30k prefill (679 tok/s). `-c 16384` and `-c 24576` free 85-170 MiB — not a
   block. **Allocation granularity, however, is a lever**: with `GGML_VK_SUBALLOCATION_BLOCK_SIZE=134217728` (128 MiB ggml
   suballocation blocks instead of 1 GiB; stock environment variable) the same ~1.8 GB is demoted under pressure but the
   driver's choice falls on cold chunks: **94-106 tok/s and 1.5-1.7 s decisions in 4 of 4 loads next to the 1.09 GB
   consumer, against 25 tok/s in 7 of 7 default-block loads**; 116 tok/s on an idle desktop (no cost). Smallest useful
   change of the round; needs more samples, a prefill check at 128 MiB and the qualification suite.
4. **The other lever is fitting the request under the budget that exists while the process runs.**
   Measured: vision encoder on the CPU (stock `--no-mmproj-offload`, −1,106 MiB device memory) keeps 32k + MTP healthy
   with ~0.7 GB headroom on an idle desktop (113 tok/s, decision 1.43 s, image encode 5.0 s instead of 1.6 s) but still
   fails next to a 1.09 GB consumer; vision on CPU + no MTP (−2,241 MiB) survives that consumer (103.5 tok/s, 1.49 s
   decisions, nothing demoted). Every further gigabyte of tolerance costs a feature; there is no free configuration.
5. **What an "adaptive runtime" should therefore be for URI**: not a new inference engine but (a) a **VRAM budget
   planner** that, at Brain launch, reads the adapter's free memory and the per-component costs measured here and picks
   the largest profile that fits with an owner-chosen headroom (vision on GPU / vision on CPU / no MTP / smaller context);
   (b) a **residency watchdog** (prototyped here, read-only) that samples the server's non-local GPU memory and flags the
   demoted state so OI can report it and reload a smaller profile instead of running a session at 25 tok/s; (c) the model
   files on NVMe so that a reload costs 10-25 s, not 90-360 s. All three are configuration and telemetry around the stock
   runtime; no fork.
6. **No stronger Brain becomes practical.** The card has no spare VRAM; the realistic headroom is negative. The current
   model stays; quality levers remain the NORMAL tier and escalation.
7. **Recommendation: CONTINUE RESEARCH** on the narrow scope of items 3 and 5 (128 MiB suballocation blocks as the first
   candidate to qualify; budget planner + watchdog + NVMe placement; a vision-placement decision by the owner), **REJECT**
   engine/fork/Strata/ROCm work, and **report the frozen configuration's VRAM oversubscription as a reproducible defect**
   under the freeze record's own reopening criteria (§14). Nothing in this round is accepted or integrated; the acceptance
   gate for any change is the 221-case suite plus the soak and an independent review.


## 2. Sources examined and versions

| source | version / identity | licence | what was used |
|---|---|---|---|
| llama.cpp pinned runtime (Runtime v1) | release **b11425**, commit `e117148`, Windows x64 Vulkan zip; `llama-server.exe` sha256 `4fdc1a67…2306` (verified this session) | MIT | baseline and all b11425 experiments |
| llama.cpp upstream release | **b11510** (published 2026-10-08T16:15Z), `llama-b11510-bin-win-vulkan-x64.zip` sha256 `1137d7ff…8891`; `llama-server.exe` sha256 `427edf09…fb0d`; source clone tag b11510 = `c35b667` | MIT | upstream-delta experiments; source inspection of `ggml-vulkan*.cpp` |
| llama.cpp upstream release, ROCm | `llama-b11510-bin-win-rocm-10.0-x64.zip` sha256 `67da2696…16d1` (257.9 MB) | MIT | alternative GPU path test (section 8) |
| Ollama 0.34.1 bundled runtime | `%LOCALAPPDATA%\Programs\Ollama\lib\ollama\` (`rocm_v7_1\ggml-hip.dll` 480 MB, ROCm 7.1 runtime DLLs, Sept 15 2026 build) | MIT (llama.cpp) / Ollama | read-only device-detection test (section 8); nothing in the Ollama install was modified |
| Strata | github.com/Niko1221/Strata, local clone `D:\uri-model-lab\strata_research\strata` at `6f32ec0` (2026-10-04); upstream at 0.1.41 (2026-10-08, commits `fb58e0d`, `0a45d54`) | MIT | technique mapping (re-used from `URI_ENGINE_STRATA_RESEARCH.md` §8, re-checked); `docs/AMD_HIP.md` VRAM-reserve guidance |
| llama.cpp upstream commits b11425→b11510 | 85 commits; Vulkan: `ff5888f` TOP_K fix, `dac3087` sparse FA coopmat2, `4d756bc` AMD slow checkpoint read fix, `6c59c40` FA shmem OOB fix, `b3daa07` sparse FA for quantized K/V; `3c9e747` mul_mat_id tile revert is **already inside b11425** (compare 3c9e747…e117148 = ahead 2) | MIT | expectation setting for the upstream-delta experiment |
| Vulkan `VK_EXT_memory_priority` | llama.cpp `ggml-vulkan-buffers.cpp:70-75` (b11510; string also present in the b11425 DLL): `GGML_VK_ENABLE_MEMORY_PRIORITY` → every ggml allocation gets priority 1.0 | — | experiment E-A |
| Prior URI evidence | `model_lab/URI_RESIDENT_INTELLIGENCE_RUNTIME_V1_FREEZE.md`, `URI_ENGINE_STRATA_RESEARCH.md`, `MODEL_QUALIFICATION_REPORT.md`, `integration/local_brain.json` (uri-phase1-integration worktree, read-only) | — | pinned configuration, historical numbers, rejected alternatives |
| Web (orientation only) | Phoronix ROCm 7.1 vs Vulkan (RDNA4), llama.cpp discussion #10879, ROCm docs (Windows ROCm 7.14 needs Adrenalin 26.6.4+, hipblas/rocblas no longer bundled), 16 GB model guides | — | section 8/9 context; no number from these is used as evidence |

## 3. Exact current Brain and baseline configuration (discovered, not assumed)

From `local_brain.json` (decided 2026-10-07) and the freeze record §1-2, all hashes re-verified where files were touched:

| item | value |
|---|---|
| model | `unsloth/Qwen3.6-35B-A3B-GGUF` @ `a483e9e6…118c`, file `Qwen3.6-35B-A3B-UD-IQ3_S.gguf` (13.68 GB), sha256 `66a3ca88…ec66` (NVMe copy verified identical) |
| architecture | `qwen35moe`: 40 blocks, 30 Gated DeltaNet + 10 gated full-attention blocks, 256 routed experts top-8 + 1 shared, 3-bit UD-IQ3_S (routed experts IQ2_S/IQ3_S) |
| vision projector | `mmproj-F16.gguf` 0.84 GiB, sha256 `8971ee4f…887f` (NVMe copy verified) |
| MTP draft | `mtp-qwen36-35b-a3b-Q4_K_M.gguf` 1.26 GB, sha256 `40ca608f…8768` (NVMe copy verified) |
| runtime | llama.cpp b11425 Vulkan release, `llama-server.exe` sha256 `4fdc1a67…2306` |
| flags | `-c 32768 -ngl 999 -fa on -ctk q8_0 -ctv q8_0 -np 1 --jinja --reasoning-format deepseek --no-webui --load-mode none -b 2048 -ub 1024 --cache-ram 2048 --slot-prompt-similarity 0 --checkpoint-min-step 512 --ctx-checkpoints 16 --mmproj … -md … --spec-type draft-mtp --spec-draft-n-max 2 -otd token_embd.weight=CPU` (this harness adds only `--metrics`) |
| accepted baseline numbers (freeze record §6/§10) | generation 142 tok/s on decisions with MTP, 96-105 without; decision turn 1.91 s lab p50 (TTFT 0.87 s); prefill 1,830-2,100 tok/s; VRAM peak 15,772-15,828 MiB dedicated; RSS 2.3-4.3 GB |
| hardware (verified) | Ryzen 9 5900X, RX 7900 GRE 16,368 MiB (driver 32.0.31041.1004, 2026-08-17), 24,501 MB RAM, Windows 11 26200; model files on D: (SATA HDD); C: NVMe 119.6 GB free |

GPU ownership before benchmarking: dedicated VRAM 809 MiB (desktop only); one other `llama-server.exe` (PID 7956, Innovation
Lab embedding server, `-ngl 0`, CPU only, port 18481) and `ollama.exe` (idle) were present and were not touched. Innovation
Lab `turn_driver.py` / `brain_proxy.py` processes from another session were running throughout; none held GPU memory
during this session's runs (per-process GPU counters sampled every 5 s, `evidence/residency_probes_phasec.csv`).

## 4. Bottlenecks identified (measured this session)

### 4.1 Primary: the frozen configuration oversubscribes VRAM, and decode throughput depends on which buffers the driver demotes

Measured with Windows per-process GPU counters (`GPU Process Memory\Local Usage` = resident in VRAM, `Non Local Usage` =
resident in system memory, reachable over PCIe) and llama.cpp's own allocation log (`GGML_VK_MEMORY_LOGGER=1`,
run `expM_b11425_memlog`):

| requested by llama-server (frozen flags, 32k, vision, MTP) | device-local MiB | host-visible MiB |
|---|---|---|
| main model weights (12 blocks of ~1 GiB suballocations) | 12,636 (12.34 GiB) | 398 |
| KV cache (q8_0, 32k) + recurrent state + first compute buffers | 340 + 188 + 216 | — |
| MTP draft model (Q4_K_M, token embedding on CPU) | 919 + 64 + 152 | 273 + 96 + 80 |
| vision projector `mmproj-F16` (encoder + its compute buffer) | 858 + 248 | — |
| **total at steady state** | **15,626 (15.26 GiB)** | **872** |

The adapter has 16,368 MiB; the desktop (dwm, Edge WebView, the Claude app, ExitLag) holds 600-900 MiB at idle and more
when windows redraw; the driver keeps its own reserve. In every full-configuration load of this session the server got
**14,943-15,689 MiB resident on an idle desktop and 250-950 MiB of its device-local requests demoted to system memory**
(non-local 1,121-1,820 MiB minus the 872 MiB that are host-visible by design); next to a 1.09 GB consumer it got
14,083-14,256 MiB resident with 1,780-1,910 MiB demoted (section 6.3). Which ~1 GiB suballocation block is demoted is not
deterministic. When a weight block is demoted, every decode step streams it over PCIe:

| load (b11425, identical flags, model, hashes) | server local / non-local MiB | decode tok/s p50 (256 tok, MTP) | decision turn p50 (≈1k prompt, ~100 out) |
|---|---|---|---|
| `base_b11425_mtp` (first load, HDD) | 15,015 / 1,820 | **24.7** | **4.37 s** (TTFT 0.60 s) |
| `probe_v32k_full` (second load) | n/a (counter query bug fixed afterwards) | 74.0 | 2.07 s |
| `probe_v16k` (-c 16384; started while the previous server still held VRAM) | 13,783 / 2,585 | 24.9 | 4.28 s |
| `expM_b11425_memlog` (NVMe copies) | 14,953 / 1,730 | 116.6 | — |
| `expA_b11425_memprio` (`GGML_VK_ENABLE_MEMORY_PRIORITY=1`) | 15,689 / 1,149 | 116.7 | 1.34 s |
| `expB_b11510_plain` | 15,689 / 1,149 | 109.8 | 1.41 s |
| `expC_b11510_memprio` | 15,079 / 1,758 | 111.8 | 1.40 s |

Same binary, same flags, same files: decode **24.7 vs 116.7 tok/s**, decision turn **4.4 s vs 1.3 s**. The slow state is
stable for the life of the process (20-turn stability run at 3.9 s p50, 4.5 s p95, no drift, 0 errors), so a URI session
that starts in it stays 3x slower than the accepted baseline until the server is restarted. Prefill is affected far less
(30k fresh: 1,589 tok/s in the slow state vs 1,784 in the fast state; 1k: 1,869 vs 1,979), because a large batch amortises the
PCIe traffic of a demoted block.

Removing any one of the three big optional consumers brings the request under the available VRAM and every such load was
fast (one load each, so this is consistent evidence, not a distribution):

| variant (b11425, 32k unless noted) | device request change | local / non-local MiB | decode tok/s p50 | decision p50 |
|---|---|---|---|---|
| no vision projector (`probe_v32k_novision`) | −1,106 MiB | 14,752 / 872 | 114.3 (MTP) | 1.45 s |
| no MTP (`probe_v32k_nomtp`) | −1,135 MiB | 14,599 / 498 | 104.2 (no MTP) | 1.79 s |
| `-c 24576` (`probe_v24k`) | −~85 MiB KV, smaller FA scratch | 15,481 / 1,091 | 121.3 (MTP) | 1.37 s (at the edge: ~220 MiB still demoted) |

This is the "under GPU memory pressure, decoding fell to approximately 24 tokens/sec" phenomenon in the owner's brief,
now attributed: it is not an external process taking the GPU, it is the frozen configuration itself requesting
~15.3 GiB of device-local memory on a card that can give it ~15.0-15.6 GiB, with the shortfall placed by the driver
without regard to what the decode loop touches. The freeze record's VRAM telemetry (adapter "Dedicated Usage" only,
peak 15,772-15,828 MiB) could not see this: dedicated usage is capped at the card size, and the demoted part is only
visible in the per-process non-local counter, which the lab never sampled. The record's 141 tok/s runs were loads in
which the demoted block happened to be cold (vision encoder or draft tensors), like `expM`/`expA` here.

### 4.2 Secondary: cold load from the D: HDD and page-cache thrash

Load to `/health`: 91.6 s (first HDD load), then 360.7 s, 163.6 s, 84.5 s, 79.5 s, 25.2 s for the HDD probes (the OS page
cache cannot hold 15.8 GB of model files next to a 4-GB server and the desktop; consecutive loads evict each other), vs
**9.7-24.6 s from hash-identical NVMe copies** (all Phase C runs). The freeze record already recommends NVMe at cutover;
this session adds that repeated restarts from the HDD (the recovery action for 4.1) cost 1.5-6 minutes each.

### 4.3 Measured non-bottlenecks

- Prefill: 1,869-1,979 tok/s at 1k, 1,957-2,281 at 8k, 1,589-1,784 at 30k fresh (server `prompt_per_second`); 30k fresh
  TTFT 17.4-19.5 s; exact repeat 0.41-0.43 s (cache_n 30,610 of 30,614); new user turn on a cached 30k context 49 tokens,
  0.47 s. Identical to the freeze record. Prompt processing is not where URI's decision turns lose time.
- Cancellation: client disconnect 1.5 s into a 1,024-token generation → next request answered in 0.46 s, server healthy;
  client-side 1 s timeout during a fresh 8k prefill → the server finishes the abandoned prefill, next request answered
  after 2.26 s (the queued prefill remainder), healthy. No hang, no leak (`base_b11425_mtp.cancel`).
- Upstream delta b11425 → b11510 (85 commits, 10 Vulkan): decode 109.8-111.8 vs 116.6-116.7 tok/s, decision 1.40-1.41 vs
  1.34 s, pp30k 1,686-1,754 vs 1,784 tok/s, vision 1.75-1.86 s both. Within the run-to-run spread; no measurable gain,
  no regression. The mul_mat_id tile revert is already in b11425; sparse FA does not apply to Qwen3.6.
- Host RAM: server RSS 2.3 GB after load → 3.4-4.4 GB after the prompt cache fills (2 GiB cap) — as in the freeze record.
- Vision: 605 prompt tokens per 768-px image, encode 1.55-1.63 s, total 1.75-1.86 s, correct answer in every run; with
  `-ub 512` the encode drops to 0.62-0.70 s (the image batch fits one ubatch differently) — noted, not pursued.

## 5. Experimental changes (all research-only, nothing applied to Runtime v1)

| id | change | kind | result (section 6) |
|---|---|---|---|
| harness | `research/adaptive_runtime/bench_runtime.py` — controlled server profile with server-side timings, per-process GPU local/non-local split, VRAM-release waits between launches, synthetic vision call, cancellation/timeout and stability phases | new research tooling | used for every run |
| harness | `residency_watch.py` — read-only 5 s sampler of every llama-server's local/non-local GPU memory, flags `DEMOTED` | prototype of a residency watchdog | 45-minute trace `evidence/residency_probes_phasec.csv` |
| probes | `-c 16384`, `-c 24576`, no vision, no MTP | stock flags | section 4.1 table |
| E-M | `GGML_VK_MEMORY_LOGGER=1` | stock env (diagnostic) | allocation ledger, section 4.1 |
| E-A | `GGML_VK_ENABLE_MEMORY_PRIORITY=1` (VK_EXT_memory_priority, every ggml allocation at priority 1.0; stock env, present in b11425) | stock env | decode 116.7 tok/s, decision 1.34 s on an idle desktop; **no effect under cross-process pressure** (25.0 tok/s, identical split to plain; section 6.3) |
| E-U | `-ub 512` | stock flag | decode 116.6 tok/s but **30k prefill collapses to 679 tok/s (TTFT 45.3 s)**; 1k/8k 1,772/1,957; rejected |
| E-N | `--no-mmproj-offload` (vision encoder on the CPU; frees 1,106 MiB device memory) | stock flag | idle desktop: 113.2 tok/s, decision 1.43 s, 14,826 / 900 MiB (nothing hot demoted), image encode 5.0 s on CPU; **fails next to a 1.09 GB consumer** (25.2 tok/s); with MTP also off it survives (103.5 tok/s) |
| E-B / E-C | upstream b11510 Vulkan release, plain and with memory priority | newer stock binary | neutral (section 4.3) |
| E-R | 4 alternating loads plain vs memory priority (placement distribution) | measurement | 8 of 8 NVMe loads on an idle desktop fast (111.5-116.0 tok/s): 6 at 15,562 / 1,121 MiB, 2 at 14,953 / 1,730 MiB (the demoted block was cold); no difference between plain and memory priority |
| E-K | `llama-bench` pp1024/8192/32768 + tg128 on both binaries (kernel level, no MTP) | measurement | b11425: pp1024 2,664, pp8192 2,437, pp32768 1,848, tg128 102.9; b11510: 2,778 / 2,462 / 1,928 / 103.9 tok/s (+4 / +1 / +4 / +1%) |
| E-S | 200-turn soak of the memory-priority candidate with vision and cancellation | measurement | 200 decision turns, 0 errors, 1.02 s p50 / 1.42 s p95, no drift (first third 1.04, last third 0.98 s); vision 1.86 s; cancellation and timeout recovery healthy |
| E-P | controlled pressure: an already-installed Ollama service holding its already-pulled `qwen3.5:0.8b` (1.09 GB VRAM) while each candidate loads next to it | measurement | section 6.3: frozen, memory priority, vision-on-CPU, vision-on-CPU + 16k all fail (25 tok/s); vision-on-CPU + no MTP survives (103.5) |
| E-Q | `GGML_VK_SUBALLOCATION_BLOCK_SIZE` 256 MiB / 128 MiB (default 1 GiB; stock env) under the same pressure and on an idle desktop | stock env | 256 MiB: 77-82 tok/s under pressure, 45 tok/s in one idle load (still hit hot weights); **128 MiB: 94-106 tok/s in 4 of 4 pressure loads (control 25.2), 116 tok/s idle (2 loads)**; section 6.3 |
| ROCm | llama.cpp b11510 `win-rocm-10.0` release, three DLL arrangements (bundled runtime; System32 `amdhip64_7.dll` from the AMD driver; Ollama's ROCm 7.1 runtime DLLs), plus Ollama's own bundled `llama-server.exe` | alternative GPU execution path | `Available devices: (none)` in all four; section 8 |

No fork, patch, kernel, model, quantization or Core change was made. Model files used for Phase C are byte-identical
NVMe copies (sha256 verified: `66a3ca88…ec66`, `8971ee4f…887f`, `40ca608f…8768`).

## 6. Before/after benchmark tables

Full machine-generated tables: `research/adaptive_runtime/evidence/SUMMARY_TABLES.md` (from `summarize_evidence.py`).
"Before" = the frozen Runtime v1 configuration as it loaded first in this session (`base_b11425_mtp`); "reference" = the
same configuration in a load where the demoted block was cold (`expA`, `rep*`), which is what the freeze record measured.

### 6.1 Server profile (b11425 unless noted; server-side timings; p50 / p95)

| configuration | decode tok/s (256 tok, MTP) | decision turn total s (≈1k prompt, ~100 out) | decision TTFT s | prefill 1k / 8k / 30k tok/s | 30k fresh TTFT s | vision (768 px) total s | server GPU local / non-local MiB |
|---|---|---|---|---|---|---|---|
| **before**: frozen v1, first load (HDD) | 24.7 / 25.2 | 4.37 / 4.91 | 0.60 | 1,869 / 1,957 / 1,589 | 19.5 | not run | 15,015 / 1,820 |
| reference: frozen v1, cold block demoted (`expA`, with memory priority) | 116.7 / 119.0 | 1.34 / 1.41 | 0.53 | 1,979 / 2,281 / 1,784 | 17.4 | 1.82 | 15,689 / 1,149 |
| frozen v1, 8 repeated NVMe loads (`rep1-4_plain/memprio`) | 111.5-116.0 (all eight) | — | — | — | — | — | 15,562 / 1,121 (6 loads), 14,953 / 1,730 (2 loads) |
| `-c 24576` | 121.3 / 124.2 | 1.37 / 1.46 | 0.57 | — | — | 2.12 | 15,481 / 1,091 |
| no vision projector | 114.3 / 123.4 | 1.45 / 1.51 | 0.57 | — | — | n/a | 14,752 / 872 |
| no MTP | 104.2 / 105.0 | 1.79 / 1.90 | 0.65 | — | — | — | 14,599 / 498 |
| **E-N** `--no-mmproj-offload` (vision encoder on CPU) | 113.2 / 115.8 | 1.43 / 1.49 | 0.57 | 2,101 / 2,269 / 1,761 | 17.6 | **5.25** (encode 5.0 s on CPU) | **14,826 / 900** (nothing hot demoted; ~0.7 GB headroom) |
| E-U `-ub 512` | 116.6 / 120.4 | 1.43 / 1.57 | 0.62 | 1,772 / 1,957 / **679** | **45.3** | 0.92 | 15,670 / 872 |
| E-B upstream b11510 | 109.8 / 113.0 | 1.41 / 1.52 | 0.55 | 393* / 2,279 / 1,686 | 18.4 | 2.28 | 15,689 / 1,149 |
| E-C upstream b11510 + memory priority | 111.8 / 117.5 | 1.40 / 1.50 | 0.55 | 1,986 / 2,207 / 1,754 | 17.7 | 1.81 | 15,079 / 1,758 |
| E-S soak, frozen v1 + memory priority, 200 decision turns (120-token cap, 5 rotating prompts) | — | **1.02 / 1.42**, first third 1.04, last third 0.98, 0 errors | — | — | — | 1.86 | 15,529 / 1,221 |

\* first 1k request on the b11510 binary after a cold pipeline cache (TTFT 2.59 s); the same size later ran at 2,279 tok/s
at 8k. Prompt-cache behaviour was identical in every run: exact repeat `cache_n` 995 / 7,951 / 30,610, new user turn
prompt_n 19-20 / 49, TTFT 0.11-0.47 s (table B of `SUMMARY_TABLES.md`).

### 6.2 Kernel level (`llama-bench`, no server, no MTP, `-fa 1 -ctk q8_0 -ctv q8_0 -b 2048 -ub 1024`, r=3 / r=2 for 32k)

| binary | pp1024 | pp8192 | pp32768 | tg128 |
|---|---|---|---|---|
| b11425 `e117148` | 2,664 ± 24 | 2,437 ± 5 | 1,848 ± 26 | 102.9 ± 1.0 |
| b11510 `c35b667` | 2,778 ± 55 (+4%) | 2,462 ± 19 (+1%) | 1,928 ± 3 (+4%) | 103.9 ± 0.6 (+1%) |

Upstream b11510 is a small, consistent prefill gain at kernel level (+4% at 1k and 32k) and no decode change; at the
server level it is inside the noise (section 6.1). Not a reopening-grade improvement on its own.

### 6.3 Controlled VRAM pressure (E-P)

The failure was then reproduced on demand. A research-owned stand-in for "another GPU consumer" — the already-installed
Ollama service holding its already-pulled `qwen3.5:0.8b` (1,087 MB, `size_vram` 1,086,869,994; nothing pulled or written;
unloaded with `keep_alive: 0` afterwards) — raised the adapter's baseline from 448 to 2,047 MiB. Each candidate was then
loaded next to it (NVMe copies, b11425, 3 decode rounds, 4 decision turns, 2 vision calls):

| configuration next to a 1.09 GB consumer | device-local request (from the ledger) | server local / non-local MiB | decode tok/s p50 / p95 | decision s p50 / p95 | vision s | verdict |
|---|---|---|---|---|---|---|
| frozen v1 (32k, vision on GPU, MTP) | 15,626 | 14,086 / 2,652 (1,780 demoted) | **25.1 / 25.6** | **4.23 / 4.67** | 2.43 | fails |
| frozen v1 + `GGML_VK_ENABLE_MEMORY_PRIORITY=1` | 15,626 | 14,086 / 2,652 | 25.0 / 25.5 | 4.25 / 4.65 | 2.41 | fails; priority does not evict another process |
| `--no-mmproj-offload` (vision encoder on CPU) | 14,520 | 13,833 / 1,792 (920 demoted) | 25.2 / 25.7 | 4.19 / 4.64 | 5.56 | fails: 0.7 GB of headroom is not enough against a 1.09 GB consumer |
| `--no-mmproj-offload` + memory priority | 14,520 | 13,833 / 1,792 | 25.1 / 25.5 | 4.26 / 4.68 | 5.54 | fails |
| `--no-mmproj-offload` + `-c 16384` | ~14,350 | 13,582 / 1,728 | 25.2 / 25.6 | 4.19 / 4.60 | 5.80 | fails: over by ~50 MiB still costs a whole 1 GiB block |
| **`--no-mmproj-offload` + no MTP** | 13,385 | **13,491 / 498 (nothing demoted)** | **103.5 / 104.2** | **1.49 / 1.54** | 4.92 | survives (MTP's 1.4x generation gain given up; vision 3x slower) |
| frozen v1 + `GGML_VK_SUBALLOCATION_BLOCK_SIZE=268435456` (256 MiB blocks) | 15,626 | 14,194 / 2,548 (1,676 demoted) | 77.4 | 1.86 | 2.75 | partial: the demoted set is finer-grained and mostly cold |
| `--no-mmproj-offload` + 256 MiB blocks | 14,520 | 14,162 / 1,466 | 81.5 | 1.79 | 5.09 | partial |
| **frozen v1 + `GGML_VK_SUBALLOCATION_BLOCK_SIZE=134217728` (128 MiB blocks)**, 4 loads | 15,626 | 14,161-14,256 / 2,694-2,784 (1,820-1,910 demoted) | **105.5, 101.8, 101.1, 93.5** | **1.52, 1.61, 1.60, 1.66** | 2.68 | **survives with the full feature set**: 4 of 4 loads fast while the default-block control in the same series stayed at 25.2 (7 of 7 default-block pressure loads slow) |
| `--no-mmproj-offload` + 128 MiB blocks | 14,520 | 14,267 / 1,405 | 85.2 | 1.56 | 5.08 | partial (one load) |
| 128 MiB blocks on an idle desktop (control), 2 loads | 15,626 | 15,698 / 1,247 | 115.7, 116.2 | 1.40, 1.42 | — | no cost when not under pressure |
| 256 MiB blocks on an idle desktop (control), 1 load | 15,626 | 15,296 / 1,547 (675 demoted) | 45.0 | 2.59 | 2.05 | one idle load still hit hot weights at 256 MiB granularity; prefill unchanged (1,857 / 2,232 / 1,780 tok/s) |

Reading: the driver demotes in whole ggml suballocation blocks (1 GiB by default); being over budget by tens of MiB
costs a full block and, if that block holds hot weights, 4x of decode throughput. Two levers exist. (1) Fit the request
under the budget *that will exist while the process runs*, with headroom equal to the largest other GPU consumer URI
must tolerate: vision off the GPU buys ~0.7 GB, vision and MTP off buy ~2.2 GB (at 1.4x slower generation and 3.3 s more
per image). (2) Make the demotion granularity fine enough that the driver's choice falls on cold memory: with 128 MiB
blocks (`GGML_VK_SUBALLOCATION_BLOCK_SIZE=134217728`, a stock ggml-vulkan environment variable) the same 1.8-1.9 GB is
still demoted, but decode stays at 94-106 tok/s in 4 of 4 pressure loads and 116 tok/s on an idle desktop, with no
prefill cost measured at 256 MiB. Lever 2 is the cheapest candidate of this round; it needs more loads (n=4 under
pressure, n=2 idle so far), a prefill/TTFT check at 128 MiB and the 221-case suite before it can be more than a candidate.


## 7. Hardware and memory measurements

| quantity | value | source |
|---|---|---|
| adapter VRAM | 16,368 MiB; idle desktop 600-900 MiB (dwm 337, Edge WebView 56, Claude app 50-124, ExitLag 83, CPU-only embedding server 222) | perf counters |
| frozen v1 device-local request | 15,626 MiB (15.26 GiB): weights 12,636; vision 1,106; MTP draft 1,135; KV 340; recurrent state 188; compute 216 | `GGML_VK_MEMORY_LOGGER` |
| frozen v1 host-visible request | 872 MiB (model 398, draft 273+96+80, misc) | same |
| frozen v1 resident in VRAM across 12 idle-desktop loads | 14,943-15,689 MiB; demoted 250-950 MiB (non-local minus 872) | per-process counters |
| frozen v1 next to the 1.09 GB consumer (7 loads, default and 128 MiB blocks) | 14,083-14,256 MiB resident; 1,780-1,910 MiB demoted | `expP*` records |
| adapter peak during frozen v1 with memory priority | 16,277-16,313 of 16,368 MiB (desktop squeezed to ~600 MiB) | `expA`, `expS` |
| E-N (vision on CPU) resident / non-local | 14,826 / 900 MiB; adapter peak 15,442 | `expN` |
| server RSS | 2.3 GB after load; 3.4-4.4 GB with a full 2 GiB prompt cache; E-N 4.25 GB (vision encoder weights 0.84 GB in host RAM) | psutil |
| system RAM available | 11.2 GB after the first load; minimum 4.7 GB observed during back-to-back HDD loads; 8.4-9.0 GB during steady runs | psutil / CIM |
| load to `/health` | HDD: 91.6, 360.7, 163.6, 84.5, 79.5, 25.2 s (page-cache dependent); NVMe copies: 9.7-24.6 s (14 loads) | harness |
| GPU release after process exit | the previous server's 13-15 GB stayed allocated for up to ~2 minutes after `terminate()` in one case (`residency_probes_phasec.csv` 22:29:58-22:32:02); normally 4-5 s | residency sampler |
| CPU | server process 0.3-3 s of CPU per minute of inference (GPU-bound); E-N adds the ViT encode on CPU (5.0 s per image) | psutil |
| GPU temperature / clocks | not available on this machine | — |

## 8. Failed or inconclusive experiments

| experiment | outcome | why / what is missing |
|---|---|---|
| ROCm/HIP execution path (llama.cpp b11510 `win-rocm-10.0`, bundled `amdhip64_7.dll` + `rocm_kpack.dll`) | **failed**: `Available devices: (none)` | the Windows ROCm 7.14/10.0 runtime needs Adrenalin 26.6.4 or newer (ROCm docs); the machine runs driver 32.0.31041.1004 (2026-08-17). Installing a driver/HIP SDK is a global change and was out of scope |
| same binary with the driver's own `amdhip64_7.dll` from System32 (bundled copies removed in an isolated copy) | failed, `(none)` | the driver-supplied HIP runtime does not expose the device to this build either |
| same binary with Ollama's ROCm 7.1 runtime DLLs (`amdhip64_7`, `amd_comgr_3`, `rocblas`, `hipblas`, `hipblaslt`) copied into an isolated directory | failed, `(none)` | runtime/kernel-package mismatch (ROCm 7.1 runtime vs ROCm 10.0 `rocm_kpack` build) |
| Ollama's bundled `llama-server.exe` (its vendored llama.cpp with `rocm_v7_1\ggml-hip.dll`) run in place, read-only | failed, `(none)` | its backend loader found neither HIP nor Vulkan from that entry point; Ollama loads backends from its own runner, which was not exercised (it would import the 13.7 GB model into the user's Ollama store) |
| `-ub 512` (E-U) | **negative** | 30k prefill 679 tok/s (−62%); only 1k/8k unaffected. Not a candidate |
| `-c 16384` probe | **confounded** | started while the previous server still held 13 GB of VRAM (release lags process exit; fixed in the harness afterwards with a VRAM-release wait); its 24.9 tok/s shows the demotion mechanism, not the effect of 16k |
| first `--no-mmproj-offload` attempt | harness error | argparse consumed the flag; re-run as `--extra=--no-mmproj-offload` (E-N) |
| Strata adaptation | **not applicable** (unchanged from the 2026-10-06 research) | upstream now at 0.1.41 with AMD/Intel SYCL work (`f-141-amdintel`), still CUDA/HIP/SYCL only, still built around non-resident experts for 125B-class models on 12 GB. The one transferable idea this session used is its VRAM-reserve rule (`--vram-reserve-mib`, `docs/AMD_HIP.md`: "with the cache filling the card, the desktop's next VRAM need makes amdgpu move GPU memory to system RAM") — the same failure class as section 4.1 |
| dedicated URI inference engine / fork | **not pursued** | the bottleneck found is a memory-planning defect of the configuration, fixable with stock flags; a new engine would inherit the same 16 GB arithmetic and start without llama.cpp's cooperative-matrix shaders (2026-10-06 research §10) |
| 1K/8K/32K prefill at higher precision (p95 with large samples) | **partial** | one fresh sample per size per run (prefill is deterministic to ±5% here); p50/p95 were taken only for decode (n=4-5), decision turns (n=6-10) and the stability runs (n=20/200) |
| cold-load measurement with a controlled page cache | **not controlled** | loads are reported as observed (HDD 25-361 s, NVMe 9.7-24.6 s); the freeze record's controlled cold/warm numbers (HDD 84-100 s / NVMe 16 s cold, 6-9 s warm) stand |
| GPU temperature / clock telemetry | **unavailable** on this machine (as in the freeze record) | an alternative explanation for a slow process (thermal/clock state) cannot be excluded by telemetry; it is excluded by evidence: the slow state correlates with the per-process non-local figure and disappears when the request fits (section 4.1), while prefill stays near normal |

## 9. Potential stronger Brain candidates

The engine finding reverses the premise: today's card has **no spare VRAM** for a stronger model; the frozen Brain already
needs 0.1-0.7 GB more than it reliably gets. What the round changes is the *reliability* of the existing Brain, not the
budget for a bigger one.

| candidate | class | measured / estimated | feasibility on 16 GB VRAM + 24 GB RAM | verdict |
|---|---|---|---|---|
| Qwen3.6-35B-A3B UD-IQ3_S (current) | MoE 35B/3B active, hybrid DeltaNet | **measured**: 110-127 tok/s decode (MTP), decision 1.3-1.5 s when resident; 25 tok/s when demoted | fits only without ~1 GiB of optional consumers (section 4.1) | keep; fix placement |
| Qwen3.6-35B-A3B UD-Q4_K_M | same model, 4-bit | **measured 2026-10-06**: 41 tok/s with experts on CPU, 6.1 s decisions | 20.4 GB file: does not fit | rejected (unchanged) |
| Qwen3.8-27B dense IQ4_XS | dense | **measured 2026-10-06**: 26-30 tok/s, 7.6-8.4 s decisions | fits, slow | rejected (unchanged) |
| gpt-oss-20b MXFP4 | MoE 21B/3.6B | **measured 2026-10-06**: long-context 0.60, no reasoning-off, no vision | fits | rejected (unchanged) |
| Gemma-4-26B-A4B QAT | MoE | **measured 2026-10-06**: decisions 0.80, unbounded thinking loops | ~15 GB, same budget problem | rejected (unchanged) |
| GLM-4.7-Flash, Ornith 1.5 35B-A3B (web guides, Oct 2026) | MoE ~30-35B/3B | **vendor/community reports only**; no URI-suite evidence | GLM-4.7-Flash at Q4 ≈ 17-18 GB: does not fit resident; Ornith is a Qwen3.6-class fine-tune with the same footprint | not evaluated; no evidence of URI benefit (freeze record §14 "invalid" class) |
| a second resident specialist (vision or draft) | — | this session shows vision (1.1 GiB) and the MTP draft (1.1 GiB) are exactly the margin | co-residence is the problem, not the solution | rejected |

No evidence emerged that a stronger Brain architecture becomes practical on this hardware with a better engine. The
realistic lever for *quality* remains the NORMAL reasoning tier and escalation (freeze record §4), unchanged.
Model switching stays optional: nothing here binds URI to one engine; the recommended changes are configuration and
telemetry, portable to any llama.cpp release.

## 10. Reproduction instructions

All commands from `C:\Users\cheta\Development\uri-adaptive-runtime\research\adaptive_runtime\` with the uri-agent venv
(`C:\Users\cheta\Development\uri-agent\.venv\Scripts\python.exe`, Python 3.13.15, httpx 0.28.1, psutil 7.2.2, Pillow 12.3.0).
Pinned artifacts are read from `pinned_runtime_v1.json` (paths + hashes copied from `local_brain.json`); `--model-dir`
points at hash-identical copies.

```bash
# 0. GPU must be idle (dedicated usage < 2.5 GB; harness waits up to 120 s and records other llama-server owners)
# 1. baseline profile of the frozen configuration on the pinned binary
python bench_runtime.py --name base_b11425_mtp --binary-dir D:/uri-model-lab/runtime/llama-b11425-bin-win-vulkan-x64
# 2. allocation ledger
python bench_runtime.py --name expM --binary-dir <b11425> --model-dir C:/Users/cheta/Development/uri-adaptive-lab/models \
   --env GGML_VK_MEMORY_LOGGER=1 --skip prefill,decision,cancel,stability,vision --decode-rounds 2
# 3. residency sampler (read-only) in a second shell
python residency_watch.py --seconds 2700 --interval 5 --out evidence/residency_<tag>.csv
# 4. Phase C and part 2 (sequential, one GPU owner at a time; deadline epoch refuses late starts)
bash run_phase_c.sh <deadline_epoch>; bash run_phase_c2.sh <deadline_epoch>
# 4b. controlled pressure (needs the local Ollama service with qwen3.5:0.8b already pulled): run_phase_c3.sh (frozen / vision-on-CPU /
#     memory priority), c4 (vision-on-CPU + no MTP / + priority / + 16k), c5-c7 (256 and 128 MiB suballocation blocks, idle controls)
# 5. tables
python summarize_evidence.py > evidence/SUMMARY_TABLES.md
```

Evidence: `research/adaptive_runtime/evidence/*.json` (one record per run: argv, binary/model hashes, environment, GPU
owners before start, every call's server timings, p50/p95, resource snapshots), `server_*.log` (git-ignored, kept on
disk), `residency_probes_phasec.csv`, `phase_c_console.txt`, `phase_c2_console.txt`, `llama_bench_*.json`.
Upstream artifacts: `C:\Users\cheta\Development\uri-adaptive-lab\dl\` (zips with the sha256 values of section 2),
`runtime\b11510-vulkan`, `runtime\b11510-rocm*`, `llama.cpp-b11510` (shallow clone, tag b11510).

## 11. Known risks and limitations

- **Sample sizes.** Each configuration was loaded once except the E-R repetition set (8 loads). The placement
  distribution is the quantity that matters and it is only estimated to the resolution of those loads.
- **Desktop state is a hidden variable.** The Claude desktop app, Edge WebView, dwm and ExitLag held 600-900 MiB of VRAM
  during the session; a heavier desktop (browser video, a game) shrinks the budget further. The watchdog data show the
  *server's* split, not what the desktop will need next.
- **Memory priority shifts the problem.** With `GGML_VK_ENABLE_MEMORY_PRIORITY=1` the server reached 15,689 MiB resident
  and the adapter 16,313 of 16,368 MiB: the desktop is what gets demoted. Desktop responsiveness under that condition was
  not measured. It is a mitigation, not a budget fix.
- **128 MiB suballocation blocks** were measured in 4 pressure loads and 2 idle loads, decode and decision turns only; prefill
  and TTFT at 1k/8k/30k, vision and the soak were not run at 128 MiB (256 MiB showed no prefill cost in one idle load). Any
  per-allocation overhead of 8x more blocks is unmeasured.
- **Vision on the CPU** (E-N) changes the image-encode latency and CPU load profile; the qualification suite V (5 VLM
  cases) was not re-run here.
- **Prompt cache / checkpoints are host memory**: unchanged, but the server's 3.4-4.4 GB RSS plus a 16 GB page cache for
  the model files leaves the 24 GB machine with 4.7-9 GB free during loads; HDD loads thrash.
- **No qualification-suite run.** No change proposed here alters model outputs by design (same weights, quantization,
  sampling, flags for the text path), but the 221-case suite was not executed in this round; it is the acceptance gate.
- **Two confounded runs** (`probe_v32k_full`, `probe_v16k`) are reported with their confound; they are not used for any
  conclusion other than "placement is not deterministic".
- **Interference.** Other sessions' Innovation Lab processes were running; none held GPU memory (counters), but their CPU
  use was not controlled. The CPU-only embedding `llama-server` (PID 7956) held 222 MiB of VRAM for its process context.
- **Not independently accepted.** Every number here is self-measured. Per the URI evidence rules this report supports a
  finding and a candidate, not an acceptance.

## 12. Final recommendation

**CONTINUE RESEARCH — narrowly.** Sub-verdicts:

| item | verdict | basis |
|---|---|---|
| URI-built adaptive inference engine / llama.cpp fork / Strata adaptation | **REJECT** | the measured bottleneck is memory planning, not kernels; kernel-level decode and prefill equal the accepted numbers on both binaries; ROCm path unavailable on this driver; prior 2026-10-06 verdicts stand |
| upstream llama.cpp b11510 as a drop-in | **not now** | +1-4% kernel level, neutral at server level; not a §14 "major upstream improvement"; re-check at the next planned runtime review |
| `GGML_VK_ENABLE_MEMORY_PRIORITY`, `-ub 512`, `-c 16384/24576` as fixes | **REJECT** | no effect against another GPU consumer / 30k prefill collapse / sub-block savings |
| frozen Runtime v1 VRAM oversubscription | **report as a reproducible defect** (freeze record §14, first criterion) | section 4.1 and 6.3: 25 tok/s reproduced on demand with a 1.09 GB consumer; 1 of 3 unaided HDD-era loads slow; 0 of 8 NVMe loads slow on an idle desktop |
| VRAM budget planner (launch-time profile selection with measured per-component costs and an owner-chosen headroom) + residency watchdog (non-local GPU memory per server) + NVMe placement | **CONTINUE RESEARCH → candidate for the Operational Intelligence layer** | every element is stock configuration and read-only telemetry; prototypes exist in `research/adaptive_runtime/` |
| smaller Vulkan suballocation blocks (`GGML_VK_SUBALLOCATION_BLOCK_SIZE`) as a cliff softener | **CONTINUE RESEARCH — first candidate to qualify** | 128 MiB blocks: 4/4 pressure loads at 94-106 tok/s vs 0/7 for the default; idle 116 tok/s; stock env var, no code; needs n≥10 loads, prefill/TTFT at 128 MiB, the 221-case suite, soak, independent review |
| vision placement (GPU 1.6 s/image with no headroom vs CPU 5.0 s/image with 0.7 GB; or vision + MTP trade) | **owner decision** | section 6.3 table; depends on how much other GPU use URI must tolerate and how often it sees images |

Acceptance gate for any profile that leaves this research: the 221-case suite (`run_bench.py` suites F,D,DG,C,H,S,O,R,RH,L,P,V)
on the exact profile, the 75-minute soak, Core freeze check, and an independent (Codex) review — none of which ran here.

## 13. Status ledger and session record

| item | Researched | Prototyped | Implemented | Benchmarked | Independently accepted | Integrated |
|---|---|---|---|---|---|---|
| VRAM oversubscription finding (frozen v1) | yes | — | — | yes (12 loads + 6 pressure runs) | no | no |
| per-process GPU residency telemetry (`residency_watch.py`) | yes | yes (read-only sampler) | no | yes (45-min trace) | no | no |
| controlled benchmark harness (`bench_runtime.py`, `run_llama_bench.py`, `summarize_evidence.py`) | yes | yes | no (research tooling) | self-validated | no | no |
| vision encoder on CPU (`--no-mmproj-offload`) | yes | yes (stock flag) | no | yes (idle: healthy; 1.09 GB pressure: fails) | no | no |
| vision on CPU + no MTP profile | yes | yes (stock flags) | no | yes (survives 1.09 GB pressure) | no | no |
| memory priority env | yes | yes | no | yes (negative) | no | no |
| 256 / 128 MiB suballocation blocks | yes | yes (stock env) | no | yes (4 pressure + 2 idle loads at 128 MiB; 2 pressure + 1 idle at 256 MiB) | no | no |
| `-ub 512`, `-c 16k/24k` | yes | yes | no | yes (negative / insufficient) | no | no |
| upstream b11510 | yes | — | no | yes (neutral) | no | no |
| ROCm / HIP path | yes | attempted | no | no device | no | no |
| Strata techniques | re-reviewed | — | no | — | no | no |
| VRAM budget planner | concept only | **no** | no | no | no | no |
| stronger Brain candidates | desk review | no | no | no | no | no |

Nothing above is an accepted URI feature. Nothing was merged, pushed, cut over or activated. Branch
`research/adaptive-runtime` holds the harness, evidence and this report (commits listed in the session record below).

### Session record (monotonic, UTC)

| time | elapsed | event |
|---|---|---|
| 16:38:08 | 0:00 | start; worktrees and GPU owners inspected (809 MiB desktop; CPU-only embedding server PID 7956 left alone) |
| 16:40-16:46 | 0:08 | Phase A: freeze record, Strata research, local_brain.json read; b11510 Vulkan (33 MB) and ROCm (258 MB) releases fetched and hashed; branch + worktree created from 037229c |
| 16:47-16:52 | 0:14 | Phase B baseline `base_b11425_mtp` (slow state observed: 24.7 tok/s, 1,820 MiB non-local) |
| 16:53-17:08 | 0:30 | residency probes (v32k_full, v16k, novision, nomtp, v24k); ROCm detection tests (none); memory-logger ledger |
| 17:08-17:16 | 0:38 | Phase C part 1: memprio, ub512, b11510 plain / memprio (NVMe copies, hash-verified) |
| 17:16-17:31 | 0:53 | part 2: vision-on-CPU, 8 repeated loads, llama-bench both binaries, 200-turn soak |
| 17:31-17:46 | 1:08 | part 3/4: controlled pressure with the Ollama 0.8B consumer (6 runs; first consumer attempt with an oversized embedding ubatch crashed and was discarded) |
| 17:46-17:49 | 1:11 | part 5: 256 MiB suballocation blocks under pressure (2 runs) |
| 17:49-17:54 | 1:16 | part 6: 256 MiB idle control; 128 MiB blocks under pressure (2 runs) |
| 17:54-18:01 | 1:23 | part 7: 128 MiB under pressure x3 + default control; 128 MiB idle x2 (last experiment ended 18:01:33Z) |
| 18:08:00 | 1:30 | all research-owned processes stopped, consumer unloaded, GPU back to desktop idle; report written; branch committed; stop |

Hard limit 20:38:08Z was not approached; no experiment was launched after 18:01:33Z. No extension requested.

### Verification of boundaries (end of session)

- Frozen Phase 1 Core / Runtime v1 files: not opened for writing; `uri-phase1-integration` worktree `git status` still 90
  entries (the freeze record's pre-research count); pinned `llama-server.exe` sha256 `4fdc1a67…2306` unchanged;
  `local_brain.json` unchanged (read only).
- No other worktree, branch or the Ollama installation was modified; Ollama's model store was used read-only (an already
  pulled model loaded and unloaded through its API).
- Research-owned processes: every `llama-server` started by the harness was terminated by the harness and its VRAM
  release confirmed (adapter back to 405-448 MiB between runs); the embedding server PID 7956 (other session) was never
  touched.
- Nothing pushed; no PR; no merge; the research branch exists only locally.

