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

__EXEC__

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

__BODY__
