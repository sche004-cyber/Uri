### A. Server profile runs (decode p50/p95 tok/s; decision turn p50/p95 s; server GPU local / non-local MiB)

| run | configuration | load s | decode tok/s p50 / p95 | decision total p50 / p95 s | decision TTFT p50 s | prefill 1k / 8k / 30k tok/s | 30k fresh TTFT s | GPU local / non-local MiB | adapter peak MiB | RSS MiB |
|---|---|---|---|---|---|---|---|---|---|---|
| `base_b11425_mtp` | frozen v1 (32k, vision, MTP), b11425, HDD, first load | 91.6 | 24.7 / 25.2 | 4.37 / 4.91 | 0.60 | 1869 / 1957 / 1589 | 19.50 | - / - | 15838 | 4222 |
| `probe_v32k_full` | frozen v1 again (started before previous server released VRAM) | 360.7 | 74.0 / 74.1 | 2.07 / 2.08 | 0.66 | - / - / - | - | - / - | 15476 | 2694 |
| `probe_v16k` | frozen v1 with -c 16384 (started before previous server released VRAM) | 163.6 | 24.9 / 25.3 | 4.28 / 4.77 | 0.64 | - / - / - | - | - / - | 15939 | 4054 |
| `probe_v32k_novision` | frozen v1 without the vision projector | 84.5 | 114.3 / 123.4 | 1.45 / 1.51 | 0.57 | - / - / - | - | 14752 / 872 | 15352 | 2338 |
| `probe_v32k_nomtp` | frozen v1 without MTP | 79.5 | 104.2 / 105.0 | 1.79 / 1.90 | 0.65 | - / - / - | - | 14599 / 498 | 15235 | 1809 |
| `probe_v24k` | frozen v1 with -c 24576 | 25.1 | 121.3 / 124.2 | 1.37 / 1.46 | 0.57 | - / - / - | - | 15481 / 1091 | 16118 | 2893 |
| `expM_b11425_memlog` | frozen v1 + GGML_VK_MEMORY_LOGGER=1 (NVMe copies) | 18.8 | 116.6 / 118.4 | - / - | - | - / - / - | - | 14953 / 1730 | 15575 | 2434 |
| `expA_b11425_memprio` | frozen v1 + GGML_VK_ENABLE_MEMORY_PRIORITY=1 | 19.7 | 116.7 / 119.0 | 1.34 / 1.41 | 0.53 | 1979 / 2281 / 1784 | 17.37 | 15689 / 1149 | 16313 | 3558 |
| `expU_b11425_ub512` | frozen v1 with -ub 512 | 9.7 | 116.6 / 120.4 | 1.43 / 1.57 | 0.62 | 1772 / 1957 / 679 | 45.33 | 15670 / 872 | 16297 | 3360 |
| `expN_b11425_mmproj_cpu` | frozen v1 with --no-mmproj-offload (vision encoder on CPU) | 19.9 | 113.2 / 115.8 | 1.43 / 1.49 | 0.57 | 2101 / 2269 / 1761 | 17.62 | 14826 / 900 | 15442 | 4249 |
| `expB_b11510_plain` | frozen v1 flags on upstream b11510 | 24.6 | 109.8 / 113.0 | 1.41 / 1.52 | 0.55 | 393 / 2279 / 1686 | 18.37 | 15689 / 1149 | 16297 | 3666 |
| `expC_b11510_memprio` | upstream b11510 + GGML_VK_ENABLE_MEMORY_PRIORITY=1 | 19.5 | 111.8 / 117.5 | 1.40 / 1.50 | 0.55 | 1986 / 2207 / 1754 | 17.65 | 15079 / 1758 | 15691 | 4172 |
| `rep1_plain` | repeat load 1, frozen v1 | 18.9 | 116.0 / 118.6 | - / - | - | - / - / - | - | 15562 / 1121 | 16173 | 1824 |
| `rep1_memprio` | repeat load 1, + memory priority | 12.2 | 112.2 / 115.2 | - / - | - | - / - / - | - | 15562 / 1121 | 16175 | 1825 |
| `rep2_plain` | repeat load 2, frozen v1 | 12.3 | 115.4 / 117.7 | - / - | - | - / - / - | - | 15562 / 1121 | 16178 | 1824 |
| `rep2_memprio` | repeat load 2, + memory priority | 15.0 | 115.6 / 118.2 | - / - | - | - / - / - | - | 15562 / 1121 | 16179 | 1825 |
| `rep3_plain` | repeat load 3, frozen v1 | 13.0 | 113.6 / 115.1 | - / - | - | - / - / - | - | 15562 / 1121 | 16191 | 1826 |
| `rep3_memprio` | repeat load 3, + memory priority | 16.2 | 115.7 / 118.3 | - / - | - | - / - / - | - | 14953 / 1730 | 15567 | 2434 |
| `rep4_plain` | repeat load 4, frozen v1 | 20.1 | 115.0 / 117.0 | - / - | - | - / - / - | - | 15562 / 1121 | 16172 | 1825 |
| `rep4_memprio` | repeat load 4, + memory priority | 15.8 | 111.5 / 113.1 | - / - | - | - / - / - | - | 14953 / 1730 | 15640 | 2434 |

### B. Prompt-cache behaviour per run (prompt_n fresh / repeat cache_n / new-turn prompt_n; TTFT s)

| run | 1k fresh / repeat / new turn | 8k | 30k |
|---|---|---|---|
| `base_b11425_mtp` | 999 / 995 / 20 ; TTFT 0.59 / 0.14 / 0.22 | 7955 / 7951 / 19 ; TTFT 4.19 / 0.22 / 0.26 | 30614 / 30610 / 49 ; TTFT 19.50 / 0.41 / 0.47 |
| `expA_b11425_memprio` | 999 / 995 / 20 ; TTFT 0.55 / 0.13 / 0.23 | 7955 / 7951 / 19 ; TTFT 3.63 / 0.16 / 0.21 | 30614 / 30610 / 49 ; TTFT 17.37 / 0.43 / 0.47 |
| `expU_b11425_ub512` | 999 / 995 / 19 ; TTFT 0.62 / 0.15 / 0.30 | 7955 / 7951 / 51 ; TTFT 4.20 / 0.25 / 0.31 | 30614 / 30610 / 20 ; TTFT 45.33 / 0.47 / 0.35 |
| `expN_b11425_mmproj_cpu` | 999 / 995 / 20 ; TTFT 0.53 / 0.11 / 0.20 | 7955 / 7951 / 19 ; TTFT 3.62 / 0.18 / 0.23 | 30614 / 30610 / 49 ; TTFT 17.62 / 0.38 / 0.43 |
| `expB_b11510_plain` | 999 / 995 / 20 ; TTFT 2.59 / 0.12 / 0.21 | 7955 / 7951 / 19 ; TTFT 3.61 / 0.18 / 0.25 | 30614 / 30610 / 49 ; TTFT 18.37 / 0.52 / 0.79 |
| `expC_b11510_memprio` | 999 / 995 / 20 ; TTFT 0.55 / 0.11 / 0.20 | 7955 / 7951 / 19 ; TTFT 3.73 / 0.16 / 0.25 | 30614 / 30610 / 49 ; TTFT 17.65 / 0.46 / 0.45 |

### C. Vision, cancellation, timeout, stability

| run | vision total p50 s (prompt_n) | disconnect mid-gen: follow-up s / healthy | client timeout in prefill: follow-up s / healthy | stability n / errors / total p50 / p95 / first-third / last-third |
|---|---|---|---|---|
| `base_b11425_mtp` | - (-) | 0.46 / True | 2.26 / True | 20 / 0 / 3.87 / 4.46 / 4.30 / 3.81 |
| `probe_v32k_full` | - (-) | - / - | - / - | - / - / - / - / - / - |
| `probe_v16k` | - (-) | - / - | - / - | - / - / - / - / - / - |
| `probe_v32k_novision` | - (-) | - / - | - / - | - / - / - / - / - / - |
| `probe_v32k_nomtp` | - (-) | - / - | - / - | - / - / - / - / - / - |
| `probe_v24k` | 2.12 (605) | - / - | - / - | - / - / - / - / - / - |
| `expM_b11425_memlog` | - (-) | - / - | - / - | - / - / - / - / - / - |
| `expA_b11425_memprio` | 1.82 (605) | - / - | - / - | - / - / - / - / - / - |
| `expU_b11425_ub512` | 0.92 (605) | - / - | - / - | - / - / - / - / - / - |
| `expN_b11425_mmproj_cpu` | 5.25 (605) | - / - | - / - | - / - / - / - / - / - |
| `expB_b11510_plain` | 2.28 (605) | - / - | - / - | - / - / - / - / - / - |
| `expC_b11510_memprio` | 1.81 (605) | - / - | - / - | - / - / - / - / - / - |
| `rep1_plain` | - (-) | - / - | - / - | - / - / - / - / - / - |
| `rep1_memprio` | - (-) | - / - | - / - | - / - / - / - / - / - |
| `rep2_plain` | - (-) | - / - | - / - | - / - / - / - / - / - |
| `rep2_memprio` | - (-) | - / - | - / - | - / - / - / - / - / - |
| `rep3_plain` | - (-) | - / - | - / - | - / - / - / - / - / - |
| `rep3_memprio` | - (-) | - / - | - / - | - / - / - / - / - / - |
| `rep4_plain` | - (-) | - / - | - / - | - / - / - / - / - / - |
| `rep4_memprio` | - (-) | - / - | - / - | - / - / - / - / - / - |

### D. llama-bench (kernel level, no server, no MTP)


`llama_bench_b11510_20261008_225518.json` binary sha256 e2470afd8028… env {}

| test | avg t/s | stddev | build |
|---|---|---|---|
| pp1024 tg0 | 2777.8 | 54.9 | c35b66744 |
| pp8192 tg0 | 2462.0 | 18.8 | c35b66744 |
| pp0 tg128 | 103.9 | 0.6 | c35b66744 |
| pp32768 tg0 | 1928.0 | 2.7 | c35b66744 |

`llama_bench_base_b11425_20261008_225334.json` binary sha256 70e5f55ead71… env {}

| test | avg t/s | stddev | build |
|---|---|---|---|
| pp1024 tg0 | 2664.3 | 23.6 | e117148a4 |
| pp8192 tg0 | 2437.4 | 4.9 | e117148a4 |
| pp0 tg128 | 102.9 | 1.0 | e117148a4 |
| pp32768 tg0 | 1848.1 | 25.8 | e117148a4 |
