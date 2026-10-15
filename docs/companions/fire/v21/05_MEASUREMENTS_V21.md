# Ember V2.1 - Performance, memory and Brain coexistence

## Method

- **Harness:** V1/V2's controlled harness, unchanged: `uri_ui/tool/capture/ember_perf_app.dart` (profile Windows build,
  one companion at the largest Companion-mode size, 476 px; all 9 `CompanionState`s for 6 s each; engine frame
  timings, RSS) and `run_ember_perf.ps1` (per-process Windows GPU counters at 1 Hz).
- **Series runner:** `uri_ui/tool/capture/run_ember_perf_v21.ps1`. It runs V2.1 Ember, V2 Ember and Solar alternately,
  twice each, **inside the machine-wide GPU lease**:
  `python -m uri_operational_intelligence.gpu_lease run --purpose benchmark ...`.
  - Before and after every run it checks that the lease is held by its own process tree and that no `llama-server`
    is resident.
  - On failure it stops and writes `BLOCKED.txt`. Log: `evidence/perf/lease_checks.txt`, all 12 checks passed.
- **Builds** (`C:\Users\cheta\Development\_v21perf`):
  - V2.1 Ember and Solar from the V2.1 worktree at `9933ca2b` (the assets measured are the committed ones);
  - V2 Ember from the V2 worktree at `b73bd26c`.
- **Attempts, all kept:**
  - Attempt 1 (`evidence/perf/attempt1_overwritten/`) ran correctly under the lease. A defect in my build script
    gave all three builds the same output folder, so four of the six frame-timing files were overwritten. Its GPU
    samples are valid but not used.
  - Attempt 2 was refused: the lease was held by the FCV recovery session (`attempt2_refused.txt`).
  - Attempt 3 waited for the lease and ran cleanly. Its results are below.
- **Census** of other GPU users before and after: `census_before.json`, `census_after.json`. The "before" census was
  taken when the run was queued, not when it started.
- Summary: `evidence/perf/summary.json`, made by `summarise_perf.py`.

## Results (attempt 3)

| Run | Brain | GPU 3D median (max) | Dedicated VRAM median (max) | Shared | Frames/s | Frame p50 / p99 | Decoded atlases |
|---|---|---|---|---|---|---|---|
| V2.1 Ember r1 | no | 0.28 % (0.88) | 147.2 MB (175.2) | 3.8 MB | 48.3 | 1.50 / 2.84 ms | 42.5 MiB |
| V2.1 Ember r2 | no | 0.27 % (1.36) | 147.2 MB (175.2) | 3.8 MB | 46.9 | 1.72 / 3.25 ms | 42.5 MiB |
| V2 Ember r1 | no | 0.29 % (0.30) | 141.8 MB (160.7) | 3.8 MB | 47.6 | 1.79 / 4.15 ms | 42.7 MiB |
| V2 Ember r2 | no | 0.28 % (0.91) | 147.4 MB (175.4) | 3.8 MB | 45.4 | 1.54 / 2.82 ms | 42.7 MiB |
| Solar r1 | no | 7.35 % (8.86) | 106.7 MB (108.4) | 2.8 MB | 168.4 | 1.55 / 2.81 ms | - |
| Solar r2 | no | 6.89 % (9.09) | 104.7 MB (106.7) | 2.8 MB | 160.5 | 1.55 / 2.81 ms | - |

## Against the criteria

| Measure | Result | Status |
|---|---|---|
| GPU utilisation | V2.1 uses 0.27-0.28 % median, the same as V2 and about 4 % of Solar's 6.9-7.4 % | **MET** |
| Dedicated VRAM | V2.1 147 MB, the same as V2 (142-147); +41 MB over Solar. Decoded atlases 42.5 MiB (at most 2 clips at once) | Bounded; same as V2 |
| Shared memory | 3.8 MB, the same as V2 | |
| Frame pacing | 47-48 frames requested per second (24 fps sprites plus vsync wakes); p99 2.8-3.3 ms | Same as V2 |
| Idle rendering | No runtime code changed in V2.1, so V2's contract holds: no frames between sprite frames, none while frozen or hidden | Unchanged |
| State transitions | V1/V2 cross-fade unchanged. Backdrops of different panels cross-fade as whole frames | Not timed separately |
| Disk | 3.27 MiB of atlases (V2: 9.7 MiB). A mostly opaque cell compresses better | Improved |
| Memory residency / demotion | See the Brain section | |

## Brain coexistence (live, real Runtime v1 Brain, our own, under the lease)

From live run 1 (`06_LIVE_QUALIFICATION_V21.md`, `evidence/live/run1_first/observations-first.json`).
- **Brain ownership:** the driver proved ownership (server pid 12336 in this runtime's `brain_host.json`;
  `our_brain: true`).
- **Override:** started with `-OverrideGpu`, under OD-V21-1.
- **Residency:** the host recorded verdict `CONTENDED`: 14.7 GB dedicated, 1.98 GB non-local (demoted), with the
  test UI (497 MB) and the desktop compositor present.
- **Probe:** the same prompt each turn, 88 tokens predicted. Ember and Solar alternated on screen, three pairs.

| Pair | Ember on screen | Solar on screen |
|---|---|---|
| 1 | 115.3 tok/s (draft accepted 48/78) | 149.2 tok/s (58/58) |
| 2 | 144.3 tok/s (58/58) | 144.1 tok/s (58/58) |
| 3 | 144.7 tok/s (58/58) | 152.1 tok/s (58/58) |
| Greeting (Ember) | 139.6 tok/s | |

**Reading:**
- In pairs 2 and 3, where speculative-draft acceptance was equal, Ember and Solar were within 0.2-7.4 tok/s, and
  the pair-2 difference favours Ember.
- Pair 1's lower Ember rate coincides with a lower draft acceptance (48 of 78 against 58 of 58). Acceptance depends
  on the generated text, not on the companion's GPU load.
- With three pairs this is **evidence of no material slowdown**, not a precise A/B: about 2-5 % either way cannot
  be excluded. V2's measurement had been inconclusive because the Brain was demoted mid-run. Here the rates held at
  139-152 tok/s throughout, despite partial demotion.

## Limits

- Other GPU users not under the lease (desktop compositor, other apps) were present and recorded in the censuses.
- The perf harness shows one companion in a dedicated window, not the full app.
