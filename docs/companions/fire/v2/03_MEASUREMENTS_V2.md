# Ember V2 - Performance and Memory Measurements

## Method

- **Harness:** V1's controlled harness, unchanged (`uri_ui/tool/capture/ember_perf_app.dart` with
  `run_ember_perf.ps1`).
- **App:** a profile Windows build that shows one companion at the largest Companion-mode size (476 px). It steps
  through all 9 `CompanionState`s for 6 s each and records engine frame timings and RSS.
- **External sampling:** Windows GPU counters, taken per process (dedicated VRAM, 3D engine utilisation).
- **Builds:**
  - V2 Ember and Solar: built from `fce51708`, which has the final assets.
  - V1 Ember: built from `89ccf461`.
- **Order:** V2, Solar, V1, then repeated, so two runs each.
- **Raw data:** `evidence/perf/<run>/`, summary in `evidence/perf/summary.json`.
- **Brain residency:** recorded per run (`brain_residency.txt`). Another session's Brain (pid 19004) was resident and
  serving during several runs. This could not be controlled from this session, and it is marked below.
- **Preliminary runs:** made on the CP4 assets, kept in `evidence/perf_prelim_cp4/`. They agree.

## Results

| Run | Brain resident | GPU 3D median | GPU 3D max | Dedicated VRAM median (max) | Frames requested/s | Frame total p50 / p99 | RSS max | Decoded atlases |
|---|---|---|---|---|---|---|---|---|
| V2 Ember r1 | no | **0.29 %** | 0.31 % | 142.9 MB (162.7) | 47.8 | 1.59 / 2.90 ms | 134 MB | 42.7 MiB |
| V2 Ember r2 | yes | **0.14 %** | 0.30 % | 141.8 MB (175.4) | 45.6 | 1.51 / 2.94 ms | 135 MB | 42.7 MiB |
| V1 Ember r1 | yes | 0.14 % | 10.61 % | 145.4 MB (189.7) | 44.3 | 1.58 / 2.94 ms | 142 MB | 42.2 MiB |
| V1 Ember r2 | yes | 5.47 % | 7.08 % | 148.7 MB (197.7) | 44.4 | 1.71 / 13.51 ms | 142 MB | 42.2 MiB |
| Solar r1 | no | 3.77 % | 8.21 % | 108.9 MB (110.9) | 148.4 | 1.57 / 2.85 ms | 152 MB | - |
| Solar r2 | yes | 11.04 % | 64.72 % | 106.7 MB (126.2) | 136.8 | 1.75 / 33.84 ms | 151 MB | - |

## Against AC-7

| Measure | Result | Status |
|---|---|---|
| GPU cost | V2 uses about 1.3-7.7 % of Solar's 3D engine time (0.14-0.29 % vs 3.8-11 %; review R1-08). It is the same cost as V1: one textured quad per sprite frame, plus a small lid patch during a blink. | **Must not exceed Solar: MET** |
| Additional VRAM | +33-36 MB over Solar, and 2.5-6.9 MB under V1. At most 2 clips are decoded at once (≤ 42.7 MiB), plus the 40 KB blink atlas. Everything is freed when Ember is unmounted (unit test). | **Bounded and stated: MET** |
| Frame pacing | 46-48 frames requested per second: the 24 fps sprite cadence, plus wakes on the vsync. Solar asks for 137-148. p99 frame time is 2.9 ms. | |
| Idle rendering | Same contract as V1. No frames are requested between sprite frames, while frozen (reduced motion or the still picker tile) or while hidden. Blinks never request frames of their own; a blink is drawn only on sprite frames the player already draws. Covered by widget tests. | |
| Transitions | V1's additive cross-fade, unchanged: one extra textured quad while it runs. Not measured separately. | |
| Disk / bundle size | 9.7 MB of atlases (V1: 14 MB), 22 KB thumbnail and 40 KB blink atlas | |
| Brain token rate | See `05_LIVE_QUALIFICATION_V2.md`. No evidence that Ember slows the Brain, but a clean A/B comparison is **INCONCLUSIVE**: a demoted Brain, 2 samples each, and another session's processes present. | **INCONCLUSIVE** |

## Limits

- **Variance from the other session's Brain.** Its Brain made Solar and V1 r2 noisy (V1 r2's 5.5 % median, Solar
  r2's 11 %). V2 measured the same with and without that Brain present.
- **No separate transition timing.** The cross-fade is the same as V1's and was not timed on its own.
