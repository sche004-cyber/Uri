# Brain VRAM headroom investigation (2026-10-17)

Context: after the UI-V2-POSTINT integration (canonical `integration/git-sync-20261008` = `25048709`), the
post-integration live checks could not start the frozen Brain. Canonical is unchanged. Nothing about the frozen Brain
was modified or substituted.

## 1. Why the frozen Brain requests 15,626 MiB

`uri_operational_intelligence/gpu_lease.py` `RUNTIME_V1_DEVICE_MIB = 15626` is the **measured** device-local request
of the frozen Runtime v1 llama-server (Adaptive Runtime research R1, 2026-10-08):

| Part | GiB |
|---|---|
| Model weights (Qwen3.6-35B-A3B UD-IQ3_S, `-ngl 999`) | 12.34 |
| Vision projector (`--mmproj mmproj-F16.gguf`, vision_enabled true) | 1.08 |
| MTP draft (`-md mtp-qwen36-35b-a3b-Q4_K_M.gguf`, `--spec-type draft-mtp`) | 1.13 |
| KV cache and compute (`-c 32768`, `-ctk/-ctv q8_0`, `-b 2048 -ub 1024`) | 0.73 |
| **Total device-local** | **15.26 (15,626 MiB)** |

Host-visible memory (0.85 GiB) is not counted. Source of truth: `model_lab/integration/local_brain.json` (frozen).

Admission rule (`assess_fit`): free = card (16,368 MiB) − dedicated memory of every other process − unattributed
memory; margin = free − 15,626. CONTENDED (start refused) when the shortfall is ≥ 512 MiB; AT_RISK (start allowed, then
post-start calibration classifies the instance) when the margin is below +512 MiB; FITS otherwise. The 512 MiB
threshold comes from measured starts on this card: when the AMD driver demotes 1 GiB blocks to host memory, decode
falls from ~90-150 tok/s to ~25-30 tok/s.

## 2. Measured state (2026-10-17, `evidence_post_integration_20261017/gpu_fit_20261017.json`)

Free 15,072 MiB, margin −554 MiB → CONTENDED, only ~42 MiB past the refusal threshold. Consumers: dwm.exe 804 MiB,
ChatGPT.exe 103, claude.exe ~60-66, msedgewebview2.exe 62, msedge.exe 44, explorer.exe 38, TextInputHost 37, others
small. The Office session started the same frozen runtime earlier on 2026-10-16 (its a12 run), so this is environment
(dwm growth since login), not a code regression.

## 3. Can an existing qualified configuration give more headroom?

**No.** Runtime v1 has exactly one frozen and qualified configuration (verdict A STOCK b11425 + prompt shaping + MTP,
frozen 2026-10-07). Earlier research measured alternatives, but **none is qualified**:

| Option (research only) | Saves | Cost measured | Status |
|---|---|---|---|
| Vision on CPU (`--no-mmproj-offload`) | 1,106 MiB | image encode 1.8 → 4.9-5.0 s | owner trade, not qualified |
| Vision on CPU + no MTP | ~2.2 GiB | MTP speed-up lost | not qualified |
| MTP draft experts on CPU | ~498 MiB | −17 % decode | rejected (regression) |
| `--n-cpu-moe 1` | — | −37 % decode | rejected |
| KV q4_0 | 225 MiB | quality risk | too small, not qualified |
| `-c 16k/24k` | < 1 GiB block | shorter context | not qualified |

Source: VRAM efficiency report (branch `research/vram-efficiency-20261010`, `research/vram_efficiency/VRAM_EFFICIENCY_REPORT.md`)
and Adaptive Runtime R1 (`docs/research/ADAPTIVE_RUNTIME_RESEARCH_R1.md`, branch `research/adaptive-runtime`).
Using any of them for this qualification would substitute the Brain configuration, which the owner has forbidden.
Qualifying one (most likely vision-on-CPU) would be a separate milestone with its own owner decision.

## 4. What frees enough headroom without changing the Brain

- Close ChatGPT, Edge and other GPU-using apps (~200-250 MiB): shortfall ~300-350 MiB → AT_RISK. The start is
  allowed, but the speed is not guaranteed (1 of 5 earlier loads at a small positive margin came up slow).
- Sign out and back in, or reboot: resets dwm.exe. Earlier measured desktop-only margin was +340 MiB → AT_RISK, near
  FITS. This is the recommended action.

## 5. Blocked checks (preserved evidence in `evidence_post_integration_20261017/`)

| Run | Mode | Result |
|---|---|---|
| pi1 | main, first-time | Brain WAITING_FOR_LEASE then WAITING_FOR_GPU (GPU_CONTENDED); UI `NO_BRAIN_READY` after 30 min; stopped by harness stop file |
| pi2 | returning | Brain WAITING_FOR_GPU; stopped with the host stop file |
| pi3 | perf | stopped before the lease (`EXIT_BEFORE_LEASE`) |
| pn1 | main, no Brain by design | J1 startup PASS (connected 9.5 s, V2 default, dashboard first, onboarding 8 steps, no raw codes); later journeys need the Brain, test timed out at 40 min |

Still not verified on canonical `25048709`: J2 navigation, J3-J16 (Brain turns, approvals, Documents/Office entry,
companion frameless shaped window J7, theme, failure journey), returning-user R-*, perf P-*. Office real-app live checks
(Office session) are blocked by the same shortfall. Last passing live set for identical code: l22/l23/l24 on
`165dac8a` (code identical to `25048709` outside `docs/`).

## 6. Rule for the next attempt

No identical GPU launch is retried until the measured fit changes from CONTENDED (a watcher checks the census and
lease, without starting anything). Then: tell the Office session, take the lease exclusively, run UI V2 main /
returning / perf, release, then the Office session runs its live checks.
