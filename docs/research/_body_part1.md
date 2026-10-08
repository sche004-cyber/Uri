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
**14,943-15,689 MiB resident and 600-900 MiB of its device-local requests demoted to system memory** (non-local
1,121-1,820 MiB minus the 872 MiB that are host-visible by design). Which ~1 GiB suballocation block is demoted is not
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
| E-A | `GGML_VK_ENABLE_MEMORY_PRIORITY=1` (VK_EXT_memory_priority, every ggml allocation at priority 1.0; stock env, present in b11425) | stock env | __EA__ |
| E-U | `-ub 512` | stock flag | decode 116.6 tok/s but **30k prefill collapses to 679 tok/s (TTFT 45.3 s)**; 1k/8k 1,772/1,957; rejected |
| E-N | `--no-mmproj-offload` (vision encoder on the CPU; frees 1,106 MiB device memory) | stock flag | __EN__ |
| E-B / E-C | upstream b11510 Vulkan release, plain and with memory priority | newer stock binary | neutral (section 4.3) |
| E-R | 4 alternating loads plain vs memory priority (placement distribution) | measurement | __ER__ |
| E-K | `llama-bench` pp1024/8192/32768 + tg128 on both binaries (kernel level, no MTP) | measurement | __EK__ |
| E-S | 200-turn soak of the memory-priority candidate with vision and cancellation | measurement | __ES__ |
| ROCm | llama.cpp b11510 `win-rocm-10.0` release, three DLL arrangements (bundled runtime; System32 `amdhip64_7.dll` from the AMD driver; Ollama's ROCm 7.1 runtime DLLs), plus Ollama's own bundled `llama-server.exe` | alternative GPU execution path | `Available devices: (none)` in all four; section 8 |

No fork, patch, kernel, model, quantization or Core change was made. Model files used for Phase C are byte-identical
NVMe copies (sha256 verified: `66a3ca88…ec66`, `8971ee4f…887f`, `40ca608f…8768`).
