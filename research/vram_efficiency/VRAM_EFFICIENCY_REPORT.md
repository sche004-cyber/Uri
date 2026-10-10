# VRAM efficiency research: Brain + Companion on the RX 7900 GRE (2026-10-10)

**Status: research. Nothing here is accepted, integrated or activated. The frozen Runtime v1 profile is unchanged.**
Branch `research/vram-efficiency-20261010` (worktree `C:\Users\cheta\Development\uri-vram-research`, from Adaptive
Runtime R2 `7d035aa`). UI experiment: branch `research/ui-vram-cache-20261010` (worktree `uri-vram-ui-exp`, from
canonical `ffdf534`).

Owner brief: reduce the combined Brain + Companion GPU footprint, aiming for 13-14 GB if achievable without material
regressions. Constraints: no change to model quality or the accepted quantization; keep context, throughput, orb
resolution, animation fidelity and responsiveness.

## 1. Answer

Units: MiB as Windows and llama.cpp report them. The card's "16 GB" is 16,368 MiB, so the 13-14 GB target is read as
13-14 GiB (13,312-14,336 MiB). Combined figures below are **estimates by addition** unless a row says measured.

**The 13-14 GiB target is not reachable on this card without a material regression**, among the configurations
examined. The frozen Brain alone requests 15,698 MiB (15.3 GiB) of device memory. Of the levers that keep the model and its quantization, only two free a gigabyte each, and
both cost something the brief protects:

| Lever | Device memory freed | Cost | Source |
|---|---|---|---|
| Vision encoder on the CPU (`--no-mmproj-offload`) | 1,106 MiB | image turns 1.8 s → about 5.0 s (2.7×); text decode unchanged | R1 (measured), this round's screening (4.94 s) |
| No MTP draft | 1,135 MiB | decode about 117 → 104 tok/s (−11%) | R1 (measured) |
| Both | 2,241 MiB → Brain about 13,457 MiB + Companion about 401 MiB ≈ **13,858 MiB (13.5 GiB), estimate** | both costs | baseline 15,698 (measured) − R1 savings (measured) + Companion (measured); the combined load itself was not measured |

Everything else measured in this round frees too little or costs too much (section 3). The Companion window holds about
350-400 MiB. In this round no tunable part of it was found: the cache cap had no measurable effect,
and the larger rail orb added about 5 MiB in the Workspace.

**Recommendation:** keep Runtime v1 as frozen. The cheapest real saving is **vision on CPU** (1,106 MiB, decode
kept, image turns about 3 s slower). It brings Brain + Companion to about 14,993 MiB (14.6 GiB, estimate), which is
still above the target. Reaching the target needs the MTP draft dropped as well (estimate 13.5 GiB, decode −11%).
Whether that trade is worth it is an owner decision (OWNER DECISIONS). It would need the 221-case suite, a soak and a
Codex review before any profile change (frozen-runtime rule). No code from this round is proposed for integration, so
no Codex integration review is pending.

## 2. Baseline (measured, this round, idle desktop, same binary, hashes and NVMe model copies)

| Item | Value |
|---|---|
| Brain device request (llama.cpp memory logger, peak) | 15,698 MiB device + 900 MiB host-visible |
| Brain residency at end of load (Windows counters) | 15,689 MiB local, 1,149 MiB non-local |
| Brain performance | decode 117.7 tok/s p50 (MTP acceptance 0.60), decision turn 1.35 s, prefill 2,124 / 2,302 / 1,807 tok/s at 1k / 8k / 30k, 30k TTFT 17.2 s, vision 1.84 s |
| R1 component split (reused, measured) | weights 12,636; KV 340 + recurrent state 188 + compute 216; MTP draft 919 + 64 + 152; vision 858 + 248 (MiB) |
| Companion window (integrated mode, 1384×861, n = 3 × 8 samples) | Companion view 401 MiB (359-420); Workspace 347-353 MiB |
| Desktop (dwm, WebView, terminal etc.) | about 500 MiB (census) |

Combined Brain + Companion today: about **16,099 MiB requested** (15,698 + 401; 15.7 GiB, estimate by addition) on a
16,368 MiB card that the desktop also uses. In this baseline load the Brain ended with 1,149 MiB non-local against
900 MiB requested host-visible, so about 249 MiB was demoted by the driver (R1/R2 measured 250-950 MiB on idle
desktops). Decode stays fast while the demoted part is cold.

## 3. Candidates screened this round (one load each, n = 1, idle desktop, `research/vram_efficiency/screen_table.md`)

| Variant | Device request MiB | Δ vs baseline | Decode tok/s | Decision s | 30k prefill tok/s | Vision s | Verdict |
|---|---|---|---|---|---|---|---|
| frozen (baseline) | 15,698 | — | 117.7 | 1.35 | 1,807 | 1.84 | — |
| MTP draft experts off the GPU (`-otd blk.40.ffn_*_exps=CPU`) | 15,370 | −328 (+503 host-visible) | 97.5 | 1.72 | 1,436 | 0.86 | **reject**: −17% decode; the tensors move to host-visible memory the GPU reads over PCIe, so the saving is small |
| + draft `output.weight` off the GPU | 14,971 | −727 | 48.8 | 2.58 | 1,669 | 1.01 | **reject**: decode halved |
| + `--n-cpu-moe 1` (main model layer-0 experts on the CPU) | 15,165 | −533 | 74.6 | 1.86 | 1,612 | 0.98 | **reject**: −37% decode |
| + KV cache q4_0 | 15,145 | −225 vs draft-experts row | 98.7 | 1.57 | 1,582 | 0.86 | **not pursued**: about 225 MiB; KV quantization changes long-context quality (would need the full suite) |
| + vision on CPU | 14,264 | −1,106 vs draft-experts row | 98.9 | 1.57 | 1,676 | 4.94 | confirms R1: −1.1 GB, vision 2.7× slower |

These are screening numbers (n = 1). The decode losses are far larger than load-to-load noise (R2: idle loads
111.9-115.9 tok/s), so the rejections stand. Any candidate going forward would need n ≥ 3, the suite and a soak.

Companion side (measured, n = 3 runs × 8 samples per view, integrated mode, same window size):

| Build | Companion view MiB | Workspace MiB |
|---|---|---|
| `54ad7be` (72 px rail orb) | 401.5 | 347.1 |
| `0215887` (132 px centred rail orb) | 400.5 | 352.1 |
| `0215887` + engine resource-cache cap 48 MB (`Skia.setResourceCacheMaxBytes`) | 400.0 | 352.9 |
| `0215887` control for the cap | 401.4 | 352.9 |

The cap had no measurable effect (n = 3). Why is not established: the engine contains both Impeller and Skia, and
which one this build uses was not determined. These samples do not show what the window's memory consists of. Not
proposed.

**Correction (recorded):** a first UI comparison without a client manifest measured 98-103 MiB. That run rendered the
classic sign-in screen, not the Living Companion, so it is invalid for the orb question and is not used above
(`ui_vram.jsonl`, `ui_vram_ab.jsonl`; screenshot `ui_demo_state.png`).

## 4. Not tested, with reasons

- Smaller context (`-c 24576` / `16384`): R1 measured −85 / −170 MiB. Too small, and the context requirement stays.
- `-ub 512`: R1 measured that it collapses 30k prefill.
- A smaller quantization, or mmproj Q8: excluded by the brief (accepted quantization).
- Lower orb quality or FPS caps: excluded (fidelity). FPS settings do not change the window's allocation.
- A 60-minute soak or the 221-case suite: not run, because no candidate qualified for them.

## 5. Incident and environment

INC-1 (host resets on 2026-10-09/10) is recorded in the integration ledger. This round ran with an fsynced heartbeat
(`docs/integration/final_20261010/evidence/staging2/heartbeat.jsonl` in the integration worktree). No reset occurred.
All six loads ran inside one machine-wide GPU lease (purpose `benchmark`); each ended with `healthy_end: true` and
0 errors.
