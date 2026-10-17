# GPU memory demotion of the Brain (llama.cpp b11425 Vulkan, RX 7900 GRE, Windows 11): research for profile P1

Date 2026-10-17. Read-only research: no llama-server was started, the GPU was not used, and no repository or tracked
file was modified. This file is the only output (it is outside any git repository).

Profiles referred to: **P1** = 64K context + vision projector on GPU, MTP off (`65536,gpu,0`, id `c64k-visgpu-mtpoff`,
request 14,764 MiB). **P2** = 64K main only (`65536,off,0`, request 13,658). **P3** = 32K + vision on GPU (request 14,360,
measured in RUNTIME-VRAM-R1 section 3; never soaked).

## 0. Acceptance criteria for this report (written before the analysis)

| id | criterion |
|---|---|
| A1 | Every number in "Verified facts" is re-read from a primary file (soak JSON, server log, source file, earlier report) and the file is named. |
| A2 | Mechanism claims cite Microsoft/Khronos documentation where it exists; where no documentation was found, the claim is marked HYPOTHESIS and says what would verify it. |
| A3 | The question "which buffer was demoted" is answered from buffer sizes and allocation layout, with the alternatives tested against the numbers, not asserted. |
| A4 | Each mitigation lists its expected effect, the evidence (with n), and the cost to decode, prefill and vision; a candidate the task names that does not exist in b11425 is said not to exist. |
| A5 | The recovery policy states when a restart helps and when it hurts, and is derived from measured recovery timing. |
| A6 | The headroom rule states its sample size and confidence; P1 and P3 are classified from it. |
| A7 | Contradictions with earlier reports are recorded as corrections, not silently overwritten. |
| A8 | The measurement plan uses ordinary desktop load only and states the pass/fail criteria before the runs. |

Self-review against A1-A8 is in section 7.

## 1. Verified facts (primary evidence re-read this session)

### 1.1 P1 soak (`D:\uri-dev\uri-profiles-live\evidence\soak\soak-p1\soak.json`, classification `COMPLETED_WITH_RESULT`)

- 120 samples, one every 30 s, 120/120 turns HTTP 200 and valid JSON. Text-only turns (the turn records carry
  `decode_tps`, `prompt_tps`, `cache_n`; no image turns). Events: `ui_open` t=0, `chrome_open` t=1200, `chrome_closed` t=2400.
- Admission (host fit): card 16,368, others 1,386.4, free 14,981.6, required 14,764, **margin +217.6 -> AT_RISK**.
  Calibration 103.7 tok/s.
- t=0-1830: Brain dedicated 14,984.7-14,984.9, non-local 561.8, decode 95-100 tok/s.
- Chrome opened at 1200: Chrome dedicated 59.9 -> 398.1 -> 607.1 (t=1260) -> 507.4 (t=1380-1830); dwm 907 -> 965-968.
  **Adapter total peaked at 16,296.7 MiB at t=1260-1290 (71 MiB below the card size) with no demotion**, then sat at
  16,196.7 (171 MiB free) from t=1380 to 1830.
- **t=1860**: Chrome 507.4 -> 598.5 (+91), Brain dedicated 14,984.9 -> **13,963.2**, non-local 561.8 -> **1,583.5**
  (growth **1,021.7 MiB**), adapter 15,267.3 (1,101 MiB free), decode **99.7 -> 20.9 tok/s**.
- t=1890: host `residency_alert` set (`growth_mib` 1,021.7); the host took no action (by design, `ws_brain_host.py`
  lines 57-63, 307-320: sample every 60 s, alert at growth >= 512 MiB).
- t=1860-2370 (Chrome open, adapter free 1,100-1,135 MiB): **the block stayed in system memory for 9 minutes although
  more free VRAM than the block size existed**. Decode 20.5-21.1 throughout.
- t=2400 Chrome closed: adapter 14,685 (1,683 free). Still demoted at 2580 (adapter 14,689.3).
- **t=2610**: dedicated back to 14,984.9, non-local 561.8 (decode 27.5 in the turn that straddled the change); t=2640
  onwards 99.4-101.7 tok/s. **The block returned 180-210 s after Chrome closed** (between samples 2580 and 2610).
- Summary block: decode min 20.5, median 99.2; min dedicated 13,963.2; max non-local 1,583.5.

### 1.2 P2 soak (`...\soak-p2\soak.json`, `COMPLETED_WITH_RESULT`)

- Admission: free 14,916.1, required 13,658, **margin +1,258.1 -> FITS**.
- Same protocol (Chrome 1200-2400). Chrome 515-680 MiB, dwm up to 1,041. Adapter peak 15,297.3 (**1,071 MiB free at
  the worst sample**). Brain dedicated 13,876.4 / non-local 561.8 for all 120 samples; decode min 96.2, median 99.3.

### 1.3 Buffer layout (server logs)

P1 buffers (`D:\uri-dev\uri-runtime-vram-r1\research\runtime_vram_r1\evidence\coexist\20261017-090541_co-c64k-vis\server*.log`,
the same profile): Vulkan0 model 12,634.81, KV 680.00, RS 62.81, compute 280.30, mmproj (clip) 857.60, clip compute
248.10; Vulkan_Host model 397.85 + compute 160.31 = 558.2 (matches the 561.8 MiB non-local baseline).

The main weights are not one allocation. The b11425 memory-logger run
(`C:\Users\cheta\Development\uri-adaptive-runtime\research\adaptive_runtime\evidence\server_expM_b11425_memlog_20261008_223850.log`,
lines 33-57, same model file and hash) shows the 12,634.8 MiB weight buffer created as **13 separate device
allocations in this order: 1,021.72, 926.29, 1,020.53, 992.53, 1,023.89, 916.08, 1,020.53, 992.53, 1,023.89,
1,020.53, 942.08, 992.53, 741.64 MiB** (sum 12,634.77). Each is one `vkAllocateMemory` (source:
`ggml-vulkan-buffers.cpp` `ggml_vk_create_buffer`; `ggml_backend_vk_buffer_type_get_max_size` returns
`suballocation_block_size`, default 1 GiB, `ggml-vulkan.cpp` lines 4213-4221 and 13071-13073; `ggml-alloc.c` packs
tensors into chunks no larger than that).

### 1.4 The same block moved in a second, independent case

RUNTIME-VRAM-R1 coexistence, 64K + MTP (`evidence\coexist\20261017-083209_co-c64k-mtpon\coexist.json`): non-local
1,000.3 -> 2,022.1 when Chrome opened = **growth 1,021.8 MiB**, decode 134 -> 44 tok/s. MTP does not change the main
weight buffers, so the same 13-allocation layout applies.

### 1.5 llama.cpp source facts (b11510 tree; the env-var names are also present in the b11425 DLL per R1)

- `GGML_VK_ENABLE_MEMORY_PRIORITY` (not `GGML_VK_MEMORY_PRIORITY`, which does not exist): if the device exposes
  `VK_EXT_memory_priority`, **every** ggml allocation gets `VkMemoryPriorityAllocateInfoEXT{1.0}`
  (`ggml-vulkan-buffers.cpp` lines 70-76, `ggml-vulkan.cpp` 4100-4102). There is no per-buffer priority.
- `VK_EXT_pageable_device_local_memory` / `vkSetDeviceMemoryPriorityEXT`: **not referenced anywhere** in ggml-vulkan
  (grep of the whole tree). It cannot be turned on by environment or flag. Whether the AMD Windows driver exposes it
  was not checked (`C:\Windows\System32\vulkaninfo.exe` exists; not run, because the task forbids GPU use).
- `GGML_VK_SUBALLOCATION_BLOCK_SIZE` sets the maximum buffer chunk; a tensor bigger than the chunk gets its own
  allocation of its own size (R2 report section 3).
- Default memory type order for device buffers (discrete GPU, no env): first `DEVICE_LOCAL | HOST_VISIBLE |
  HOST_COHERENT` (ReBAR/SAM), then `DEVICE_LOCAL` (`ggml-vulkan-buffers.cpp` 214-225). Other memory env vars exist:
  `GGML_VK_PREFER_HOST_MEMORY`, `GGML_VK_DISABLE_HOST_VISIBLE_VIDMEM`, `GGML_VK_ALLOW_SYSMEM_FALLBACK`.
- `ggml_backend_vk_get_device_memory` reports free = `heapBudget - heapUsage` from `VK_EXT_memory_budget`.

### 1.6 Earlier research (re-read)

- Adaptive Runtime R1: default 1 GiB blocks demote whole; memory priority had no effect against another process
  (25.0 vs 25.1 tok/s); 256 MiB blocks 77-82 tok/s under a 1.09 GB consumer but **one idle load at 45 tok/s**;
  128 MiB 94-106 tok/s in 4/4 pressure loads; `-ub 512` collapses 30K prefill to 679 tok/s; `--no-mmproj-offload` frees
  1,106 MiB, image encode 5.0 s instead of 1.6 s.
- Adaptive Runtime R2 (the report file has unfilled `RESULTS_PENDING` sections; numbers below are from
  `evidence\R2_SUMMARY_TABLES.md` and `r2\SESSION_LEDGER.md`): 128 MiB blocks under pressure 9 of 10 loads fast, **1 of
  10 collapsed (27.6 tok/s)**, so AC1 ("no load below 60") failed; under pressure **30K prefill fell to 687-1,183 tok/s
  (TTFT 26-45 s) against 1,557-1,584 for 1 GiB blocks**; on an idle desktop with the full frozen profile (250-380 MiB
  demoted even idle) 30K prefill 916-933 vs 1,771-1,791 tok/s, so **AC3 failed**. llama-bench with everything resident
  showed no intrinsic block-size cost; the ledger attributes the server-level prefill loss to demoted chunks. 128 MiB
  vision encode was faster (0.79-0.83 s vs 1.86 s) because the projector stayed resident.
- VRAM efficiency report: no lever reaches 13-14 GiB without dropping vision or MTP.
- RUNTIME-VRAM-R1: per-profile requests and margins; 64K + vision survived one short Chrome test (+308 margin that
  day); 64K + MTP (+29) demoted with Chrome and "stays after close".

### 1.7 Correction to an earlier conclusion (A7)

RUNTIME-VRAM-R1 section 7 says the 64K + MTP demotion "persisted after everything closed (sticky, as R1 found)". The
record shows phase D was measured **38 s** after phase C (`t` 1792206287.3 -> 1792206325.3) and the server stopped right
after. The P1 soak shows the block returning **180-210 s** after Chrome closed. So that observation does not show
process-lifetime stickiness; it is consistent with a delayed return that was not waited for. R1's "stable for the life of
the process" applies to a different case: the request itself exceeded the budget at load, so free memory never
appeared. The earlier text stands as history; this is the correction.

## 2. Mechanism

### 2.1 What Windows does (documented)

- WDDM 2.x gives each process a residency **budget** "imposed when the system is under memory pressure"; the budget
  "can change over time" ([Process residency budgets](https://learn.microsoft.com/en-us/windows-hardware/drivers/display/process-residency-budgets)).
  D3D12 docs: the budget "can fluctuate noticeably as background processes wake-up and sleep; and fluctuate dramatically
  when the user switches away to another application" ([Residency](https://learn.microsoft.com/en-us/windows/win32/direct3d12/residency)).
- "Heaps cannot be made partially resident", and "kernel can shift some heaps on discrete adapters from video memory to
  system memory ... only as an extreme last resort" (same page). This is the **demotion** we see: the allocation moves
  whole into system memory, the GPU keeps reading it over PCIe, and it shows as the per-process "Non Local Usage" counter.
  It is not eviction: GPU access to a non-resident allocation "is illegal and will result in the device removed"
  ([Driver residency in WDDM 2.0](https://learn.microsoft.com/en-gb/windows-hardware/drivers/display/driver-residency-in-wddm-2-0)).
  That is why the Brain kept answering correctly at 21 tok/s instead of crashing.
- Since WDDM 2.0, "VidMm no longer has visibility into the allocations being referenced in a particular command
  buffer ... no longer in a position to track allocation usage"
  ([Allocation usage tracking](https://learn.microsoft.com/en-us/windows-hardware/drivers/display/allocation-usage-tracking)).
  **So the kernel has no access-recency information for a Vulkan compute process's allocations.** Its choice is based on
  priority, size and placement, not on which buffer the decode loop touches.
- Priority is the only documented application-side input: "influence which heaps and resources will be preferred to
  stay resident when memory pressure requires that some of its resources be demoted" (D3D12 Residency page).
  `VK_EXT_memory_priority`: priority "may be used to determine which allocations are more likely to remain in
  device-local memory", relevant "when the total memory used across all processes exceeds the size of the heap"
  ([VK_EXT_memory_priority](https://docs.vulkan.org/refpages/latest/refpages/source/VK_EXT_memory_priority.html)).
  `VK_EXT_pageable_device_local_memory` adds `vkSetDeviceMemoryPriorityEXT` to change priorities after allocation
  ([VK_EXT_pageable_device_local_memory](https://docs.vulkan.org/refpages/latest/refpages/source/VK_EXT_pageable_device_local_memory.html)).
  The Vulkan specification's default priority without the structure is 0.5 (from the specification text, not re-fetched
  this session).

### 2.2 What is not documented (HYPOTHESIS)

- **How priority compares across processes.** Microsoft documents priority as ranking a process's own heaps. R1
  measured that raising all Brain allocations to 1.0 changed nothing against another process. Hypothesis: VidMm first
  decides which process must give memory back (budget, foreground status), and only then uses priority to pick among
  that process's allocations. All-1.0 then just means "no preference", as before.
- **AMD driver policy.** No AMD document describing its Windows KMD demotion choice was found. The AMD driver declares
  the segments and the allocation's preferred and fallback segments. The Vulkan heaps are backed by VRAM (with ReBAR the
  whole VRAM is CPU-visible, and llama.cpp picks that memory type first) and by the system-memory aperture. Whether
  Smart Access Memory is enabled on this PC was not verified. What is measured is the outcome: a whole allocation moved,
  and the moved allocation was not the coldest one (2.4).
- **Why minutes after Chrome opens.** Opening Chrome does not trigger it by itself. In P1 the adapter reached 16,296.7
  (71 MiB free) at t=1260 without demotion. Demotion happened at t=1860, when Chrome grew again (+91 MiB in the 30 s
  sample, with more probably in between: YouTube, WebGL and map tabs allocate in bursts as they play, decode and load
  tiles). Reading: demotion happens at the first **allocation request that cannot be satisfied** from free local memory,
  not at a usage threshold. Chrome then gets its memory from what the Brain gave up. The 30 s sampling cannot show the
  peak, so the exact trigger size is unknown.
- **Why it reverses minutes after Chrome closes, and not before.** With Chrome open, 1,100 MiB was free for 9 minutes
  and the 1,022 MiB block did not come back. After Chrome closed (1,683 free) it came back within 180-210 s. Hypothesis:
  promotion back to the preferred segment is a deferred, background decision with hysteresis. It needs free memory well
  above the allocation size and/or the end of the pressure state (Chrome's budget claim gone), and it is not attempted
  immediately. One sample only; the exact rule and timer are undocumented (searched, nothing found). It is reproducible
  only by repeating the measurement (section 6, M4).

### 2.3 Which buffer was demoted: weights (strong inference)

The non-local growth was **1,021.7 MiB** in P1 and **1,021.8 MiB** in the independent 64K + MTP case. Candidates from
1.3:

| candidate | size MiB | matches 1,021.7? |
|---|---|---|
| first main-weight allocation | **1,021.72** | yes (to 0.02 MiB; the only weight chunk of that size) |
| other weight chunks | 916-1,023.89 | no (1,020.53 is 1.2 off; 1,023.89 is 2.2 off) |
| KV cache | 680.0 | no |
| mmproj weights | 857.6 | no |
| mmproj + clip compute | 1,105.7 | no |
| KV + RS + compute (3 allocations) | 1,023.1 | 1.4 off, and it needs three separate allocations demoted together |

The decode rate gives an independent check. Per-token time went from 10.1 ms (99 tok/s) to 47.6 ms (21 tok/s), so
**+37.5 ms per token**. A block holding only routed-expert tensors would add only a few ms per token, because a token
reads 8 of 256 experts (~3% of those bytes). A 5x slowdown needs on the order of 0.4-1 GB read over PCIe **per token**
(0.4 GB / 37.5 ms ~ 11 GB/s, a plausible effective PCIe 4.0 rate for GPU reads of system memory; this bandwidth was not
measured here). That fits a chunk holding tensors read in full on every step. HYPOTHESIS: llama.cpp creates
`output_norm` and `output.weight` (397.9 MiB, the LM head; the equal-size `token_embd` is the Vulkan_Host buffer) before
the layers, so the first 1 GiB chunk is likely `output.weight` plus the dense and attention tensors of the first
~2 blocks. The tensor-to-chunk map was not dumped. Verify with `-lv 4` or a `GGML_VK_MEMORY_LOGGER` run plus a tensor
listing.

**The idle mmproj (857.6 MiB, no image turn in the whole soak) was not the one demoted.** This confirms the documented
point that VidMm does not know usage, and shows that a cold buffer does not protect the hot ones.

Conclusion: **weights (very likely the first chunk, which contains the LM head), not the KV cache and not the mmproj.**
Confidence high for "weights" (size match in 2 of 2 events) and moderate for "the LM head is in that chunk".

## 3. Mitigation options with costs (b11425, no patch, frozen Runtime v1 defaults untouched; profile-level env/flags only)

| option | expected effect on P1 | evidence | decode | prefill | vision | verdict |
|---|---|---|---|---|---|---|
| **A. Fit more headroom: drop to P3 (32K + vision GPU)** | -404 MiB request, margin about +622 on the P1 desktop; removes the trigger for an ordinary browser | P2 (+1,258) survived the same soak; P1 (+218) did not; P3 itself has no soak (n=0) | none | none (smaller KV) | none (0.51 s) | **first candidate**; costs 32K of context |
| **B. Vision on CPU (`--no-mmproj-offload`) at 64K** | -1,106 MiB, request about 13,658 (P2-sized), margin about +1,320 | P2 soak at the same request survived; R1: E-N healthy idle; this exact profile never measured (VRAM-R1: "not selectable") | none | none | **encode 4.2-5.0 s instead of 0.5 s**; +0.84 GB host RAM, CPU busy while encoding | strong fallback when 64K is required |
| **C. `GGML_VK_SUBALLOCATION_BLOCK_SIZE=268435456` (256 MiB)** | the same ~100-200 MiB shortfall would cost one 256 MiB chunk instead of 1 GiB, and the chance of hitting the LM-head chunk falls (that tensor alone is 398 MiB, so it becomes its own allocation) | R1: 77-82 tok/s under a 1.09 GB consumer (n=2); **one idle load at 45 tok/s** (n=1); no R2 data; never tested with a small shortfall | when it hits a hot chunk: partial loss (45-82 tok/s measured) | R2 measured 128 MiB prefill loss when chunks were demoted; 256 MiB had one idle load with prefill unchanged | unchanged while resident | **candidate to measure**, not to adopt |
| **D. `GGML_VK_SUBALLOCATION_BLOCK_SIZE=134217728` (128 MiB)** | finest granularity | R2: 9/10 fast under pressure, 1/10 collapsed; **30K prefill halved** whenever chunks were demoted (idle and pressure) | mostly kept | **-40 to -55% at 30K when demoted** | better (projector stays resident) | **failed R2 AC1/AC3**; only worth re-testing on a profile that is fully resident (P1/P3) |
| E. `GGML_VK_ENABLE_MEMORY_PRIORITY=1` | all allocations at 1.0; no cross-process effect | R1: identical 25 tok/s under pressure (n=2) | — | — | — | **reject** |
| F. `VK_EXT_pageable_device_local_memory` / per-buffer priority | would let URI rank mmproj/KV below weights | not implemented in ggml-vulkan; needs a patch (out of scope) | — | — | — | **not available** |
| G. "Separate, smaller mmproj allocation" | already separate (857.6 + 248.1 are their own allocations) | log 1.3 | — | — | — | **no-op**; the mmproj was not the one demoted |
| H. `-ub 512` | saves part of the 280 MiB compute buffer only | R1: 30K prefill 679 tok/s (-62%) | — | **-62% at 30K** | encode faster | **reject** |
| I. `GGML_VK_DISABLE_HOST_VISIBLE_VIDMEM` | uses plain DEVICE_LOCAL instead of the ReBAR type; might change which segments VidMm may use | none | unknown | unknown | unknown | untested, low prior; leave |
| J. Close or limit other GPU apps | removes the trigger | P1 recovered 3.5 min after Chrome closed | — | — | — | user-facing advice, part of section 4 |

Notes:
- C/D move the cost rather than remove it (R2 ledger: "block size moves the cost of oversubscription; it does not remove
  it"). They are worth trying only because P1 is **fully resident at idle**, unlike the frozen profile R2 tested. The
  idle prefill penalty R2 measured came with 250-380 MiB already demoted, so for P1 it may not appear. That is a
  hypothesis for M2.
- A and B are the only options with soak-grade evidence at the same request size (P2).

## 4. Detection-and-recovery policy proposal

Measured inputs: detection is already in place (60 s non-local sample, alert at +512 MiB; it fired 30 s after the event).
The block came back by itself **180-210 s after the pressure ended** (n=1). It did **not** come back while Chrome stayed
open, even with 1.1 GB free (9 min). A real host restart takes 29.1 s to READY, plus about 10 s of re-prefill per 20K
tokens (about 45-49 s for a full 64K); the conversation is kept, the KV state is not (VRAM-R1 sections 5 and 8).

**When a restart hurts:** while the pressure source is still open. At restart the fit would see about 16,368 -
(dwm ~965 + Chrome ~590 + URI ~75 + system) left for 14,764. That is roughly at or below zero margin, so the host either
refuses (CONTENDED) or loads straight into the demoted state. The user pays 30-80 s for nothing.
**When a restart helps:** (a) the pressure is gone and the block has not returned after a grace period longer than the
measured 3.5 min; (b) the demotion happened at load (R1's sticky case, where no free memory appears by itself); (c) the
user switches to a smaller profile (P2, or B) that fits with the pressure source still open.

Proposed policy (simplest safe version; nothing automatic mid-turn):

1. **Detect**: `DEMOTED` = non-local minus the profile's host-visible share >= 512 MiB (existing alert), confirmed by the
   next turn's decode < 0.6x calibration (or two `/metrics` windows). The two signals are required because R2 showed
   demotion that did not slow decode.
2. **Tell the user at once**, without blocking: "The Brain slowed down because another app (Chrome: N MiB) needs GPU
   memory. It recovers by itself a few minutes after that app closes." Offer two actions:
   - **"Switch to a lighter profile"** (P2, or vision-on-CPU) — the only action that helps while the app stays open.
     It runs the fit check first and shows the cost (vision off/slow, 25-80 s, conversation kept).
   - **"Restart Brain"** with the same profile — **shown only when the fit check now says FITS**. Otherwise it is greyed
     out with the reason.
3. **Wait-and-watch**: while the pressure source is open, do nothing else. When adapter free memory >= demoted size +
   512 MiB, start a 5-minute grace timer (above the measured 3.5 min). If the block returns, clear the alert and say so.
4. **Idle-only automatic restart (opt-in setting, default off)**: only if the grace period expired, the fit says FITS,
   no turn is running and none ran in the last 2 minutes, and no image or long prompt is pending. At most one automatic
   restart per hour.
5. **Never** auto-restart into an AT_RISK/CONTENDED fit, mid-turn, or more than once without the user.

Telemetry to add (read-only): record the adapter free memory and the top other GPU consumer at the alert, and the
time from pressure gone to block returned. That turns the single 180-210 s sample into a distribution.

## 5. Headroom rule

Data (margin = the host fit's margin at admission; "actual free" = 16,368 - adapter total once the Brain is resident):

| profile | request | margin | actual free after load, URI open | browser test | outcome | quality of sample |
|---|---|---|---|---|---|---|
| P2 64K main | 13,658 | +1,258 | ~1,769 | 60-min soak, Chrome 515-680 | never demoted | soak, n=1 |
| 64K main (VRAM-R1) | 13,658 | +1,414 | n/r | short, Chrome 549 | resident | short, n=1 |
| 32K + MTP | 14,515 | +557 | n/r | short (~1 min), Chrome 600 | resident | short, n=1 |
| 64K + vision (VRAM-R1) | 14,764 | +308 | n/r | short (~1 min), Chrome 581 | resident | short, n=1 |
| **P1 64K + vision** | 14,764 | **+218** | ~658 | 60-min soak, Chrome 507-607 | **demoted 1,022 after 11 min, back 3.5 min after close** | soak, n=1 |
| 64K + MTP | 15,043 | +29 | n/r | short, Chrome 575 | demoted 1,022 at once | short, n=1 |
| frozen 32K+MTP+vision | 15,621 | -549 | — | — | demoted at load | n=1 + R1 |

Reading:
- An ordinary 6-tab Chrome added **~490-590 MiB** to the adapter (P1: 15,709.5 -> 16,196.7/16,296.7; P2: 14,597 ->
  15,170.9/15,297.3), dwm about +60. Its peaks between samples are larger; the P1 trigger happened with 171 MiB showing
  free.
- The short tests at +308/+557 do not separate the classes: P1 survived the first 10 minutes of its soak too. **Only the
  two soaks count: +218 failed, +1,258 passed.** The threshold lies between them.
- Physical estimate (HYPOTHESIS): actual free after the Brain is resident must cover Chrome's sampled peak (~590) +
  dwm growth (~60) + unsampled bursts (>= ~170, from the P1 trigger) + the driver's untouchable reserve (55-90, R2) =
  **~900 MiB actual free**. On the two soak days actual free was margin + ~440-510 (the fit's "others" over-counts
  shared desktop memory), so this is **margin >= about +450 to +500**, close to the existing AT_RISK boundary (+512).

**Answers:**
- **P1 at +218 is inherently insufficient** for an ordinary browser: it is ~250-300 MiB short of the estimate, and it
  failed the one soak. High confidence that it fails often with a video/map-heavy browser. Not certain it fails every
  time: the trigger depends on Chrome's burst size, and the short test survived once.
- **P3 at +622 is likely safe** with the same ordinary browser: predicted actual free ~1,060 MiB (P1's 658 + 404),
  about 150 MiB above the estimate. **Moderate-to-low confidence.** There is no P3 soak, the margin over the estimate is
  smaller than one Chrome burst could be, and a second GPU app (an Electron chat app, Office, video) would remove it.
- Proposed rule: keep **FITS >= +512** (supported, not contradicted). Add a "browser-tolerant" label only at **>= +600
  with a passing soak of that profile**. Label anything below +512 "will slow down if a browser or video plays". Basis:
  n=2 soaks plus 4 short tests, one desktop, one Chrome tab set. Treat it as a provisional rule.

## 6. Minimal measurement plan (later; GPU required; ordinary desktop load only; no stress)

Common protocol: the existing soak harness, 75 min (20 min UI only, Chrome with the same 6-tab lab profile for 20 min,
close, then 35 min to observe recovery). **Sampling every 10 s instead of 30 s**, plus the adapter-total peak between
samples if the counter API allows it. Text turns as before, plus one image turn every 5 minutes on vision profiles to
measure encode latency under pressure. One profile per run, inside the GPU lease. Read-only first step:
`vulkaninfo --summary` to record the memory heaps/types, whether `VK_EXT_memory_priority` and
`VK_EXT_pageable_device_local_memory` are exposed, and whether ReBAR is on.

| # | run | pass criteria (fixed before running) | why |
|---|---|---|---|
| M1 | **P3 soak** (32K + vision GPU, default blocks) | 0 demotion (non-local stays at baseline), decode >= 90 tok/s in every sample, vision encode <= 0.7 s | tests the headroom rule's prediction; first candidate |
| M2a | **P1 + `GGML_VK_SUBALLOCATION_BLOCK_SIZE=268435456`**: idle check first (decode, prefill 1K/8K/30K, vision x3), then the soak | idle within ±5% of default P1 (prefill 30K included); under Chrome decode >= 80 tok/s, non-local growth <= 512 MiB | tests whether a small shortfall costs one small chunk instead of the LM-head chunk |
| M2b | same with 128 MiB (only if M2a fails on granularity, not on prefill) | as M2a | R2 failure may not apply to a fully resident profile |
| M3 | 64K + `--no-mmproj-offload` short probe (load, request from log, 3 decode, 3 image encodes, 30K prefill) | request <= 13,700, decode equal to P2, encode measured | makes option B selectable (VRAM-R1 requires a measured request) |
| M4 | **P1 default repeat** (same as the first soak), with 10 s sampling | reproduces the demotion (or not); times when the block returns after close | turns n=1 into n=2 for the trigger and the recovery timing (section 4 depends on it) |

Order: M1, M2a, M4, M3, then M2b only if needed. About 4-5 GPU hours in total. Decision after the runs: if M1 passes,
P3 is the vision profile; if M2a passes both idle and pressure criteria, P1 + 256 MiB becomes a candidate for the
qualification suite; otherwise 64K with vision means option B.

## 7. Self-review (acceptance criteria) and what is not verified

| id | check | status |
|---|---|---|
| A1 | All soak numbers re-read from the JSON (time series dumped this session); buffer sizes from two server logs; source lines read | met |
| A2 | Microsoft/Khronos quotes fetched this session and linked; undocumented parts marked HYPOTHESIS | met; **no AMD documentation found** |
| A3 | Alternatives tabulated against 1,021.7; decode-rate cross-check | met; the tensor-to-chunk map is not verified |
| A4 | Every listed candidate covered; `GGML_VK_MEMORY_PRIORITY` corrected to `GGML_VK_ENABLE_MEMORY_PRIORITY`; pageable extension shown not implemented | met |
| A5 | Restart helps/hurts derived from the 180-210 s and 9-minute observations | met; n=1 |
| A6 | Sample sizes stated (2 soaks, 4 short tests) | met |
| A7 | Correction 1.7 (VRAM-R1 "sticky" observed for only 38 s); R2 report body is unfilled, so the numbers come from its tables/ledger | met |
| A8 | Plan uses the ordinary Chrome tab set; criteria fixed in the table | met |

Gaps found during self-review and repaired: (1) a first draft read the adapter total and per-process dedicated memory
as additive. They are not (P1: adapter 15,713.8 - Brain 14,984.7 = 729 < dwm 907, because shared desktop surfaces are
counted per process), so the headroom section now uses the adapter total for "actual free". (2) The task's "128 MiB
failed some criteria in R2" was checked: the R2 report has no results. AC1 and AC3 failures come from the
ledger/summary tables and are cited from there.

Not verified, and whether it changes a verdict:
- The tensors in the 1,021.72 MiB chunk (affects only the "LM head" detail, not "weights").
- AMD KMD demotion/promotion rules and timers; promotion timing is n=1 (affects the grace timer in section 4, not the
  policy's shape).
- Whether ReBAR/SAM is on and whether the driver exposes the pageable extension (would matter only for a future patch).
- PCIe read bandwidth from system memory on this PC (affects only the plausibility check in 2.3).
- P3 has no soak; the P3 verdict is a prediction (M1).
- One desktop composition (dwm 900-1,040 MiB) and one Chrome tab set; heavier desktops need more margin.
