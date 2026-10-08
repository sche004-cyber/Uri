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
# 5. tables
python summarize_evidence.py > evidence/SUMMARY_TABLES.md
```

Evidence: `research/adaptive_runtime/evidence/*.json` (one record per run: argv, binary/model hashes, environment, GPU
owners before start, every call's server timings, p50/p95, resource snapshots), `server_*.log` (git-ignored, kept on
disk), `residency_probes_phasec.csv`, `phase_c_console.txt`, `phase_c2_console.txt`, `llama_bench_*.json`.
Upstream artifacts: `C:\Users\cheta\Development\uri-adaptive-lab\dl\` (zips with the sha256 values of section 2),
`runtime\b11510-vulkan`, `runtime\b11510-rocm*`, `llama.cpp-b11510` (shallow clone, tag b11510).

## 11. Known risks and limitations

- **Sample sizes.** Each configuration was loaded once except the E-R repetition set (__ERN__ loads). The placement
  distribution is the quantity that matters and it is only estimated to the resolution of those loads.
- **Desktop state is a hidden variable.** The Claude desktop app, Edge WebView, dwm and ExitLag held 600-900 MiB of VRAM
  during the session; a heavier desktop (browser video, a game) shrinks the budget further. The watchdog data show the
  *server's* split, not what the desktop will need next.
- **Memory priority shifts the problem.** With `GGML_VK_ENABLE_MEMORY_PRIORITY=1` the server reached 15,689 MiB resident
  and the adapter 16,313 of 16,368 MiB: the desktop is what gets demoted. Desktop responsiveness under that condition was
  not measured. It is a mitigation, not a budget fix.
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
