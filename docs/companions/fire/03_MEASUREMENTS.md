# Ember - Measurements

Hardware: Windows 11 Pro 10.0.26200, Ryzen 9 5900X, 24 GB RAM, AMD Radeon RX 7900 GRE 16 GB (the owner's PC).
Every number below comes from a file under `evidence/`; nothing is typed from memory.

## M-1 Real-window renderer cost: Ember vs Solar (run 1, commit 8a1438ec, before the pacing repair)

Harness: `uri_ui/tool/capture/ember_perf_app.dart` (profile build, real Windows window, Impeller), one companion at
476 px (320 dp x presence scale x largest size preference), all nine states for 6 s each. GPU and VRAM from Windows
GPU performance counters for the process (`run_ember_perf.ps1`). No Brain was resident (`brain_pids_at_start: []`).
Evidence: `evidence/perf/summary.json`, `*_per_state.json`, `*_gpu.json`, `grid.jpg`.

| Metric | Ember | Solar (shader) |
|--------|-------|----------------|
| Frames produced / s (harness has no frame cap) | 156.1 | 145.6 |
| Build p50 / p90 (ms) | 0.07 / 0.10 | 0.08 / 0.12 |
| Raster p50 / p90 / p99 (ms) | 0.62 / 0.80 / 1.00 | 0.83 / 1.05 / 1.29 |
| Frames over 16.7 ms | 0 % | 0 % |
| GPU 3D engine utilisation, median / max | 1.30 % / 1.51 % | 6.04 % / 7.62 % |
| Dedicated VRAM, median / max (MB) | 152.7 / 173.2 | 110.7 / 112.4 |
| CPU time over the run (s, ~60 s wall) | 10.48 | 16.59 |
| Process RSS start / end / max (MB) | 138.7 / 126.7 / 143.0 | 149.4 / 106.4 / 151.3 |
| Decoded Ember atlases resident at the end (MB) | 42.2 | - |

Reading: Ember costs about a fifth of Solar's GPU time and about two thirds of its CPU time, and it raises dedicated
VRAM by about 42-62 MB (the decoded atlases). Run 1 still produced a frame on every vsync (review R1-07); the pacing
repair is measured in M-3.

## M-2 Atlas budget (shipped assets)

From `uri_ui/assets/companions/ember/manifest.json`: 8 shipped clips, 320 px cells, 24 fps. 96-frame clips (idle,
thinking, depleted) decode to 3840 x 2560 x 4 = 37.5 MiB; 48-frame clips to 2880 x 1920 x 4 = 21.1 MiB. On disk the
eight atlases plus thumbnail total about 14 MiB (fierce, 1.9 MB, is no longer shipped).
Worst resident case while Ember is on screen: the two most recent atlases plus a third pinned during a fade, about
96 MiB (two 96-frame clips and one 48-frame clip), plus mipmaps if the backend builds them (not measured).
After the R1-05 repair, all atlases are disposed when no Ember widget remains.

## M-3 Pacing repairs (runs 2 and 4)

Same harness and window size. No Brain resident in either run.

| | Run 1 (8a1438ec) | Run 2 (7d83947d, R1-07 sleep between frames) | Run 4 (R2 wake fix + 8 ms margin + 30 fps pulse) | Solar (run 2) |
|---|---|---|---|---|
| Frames requested / s, whole run | 156.1 | 56.5 | 45.1 | 145.7 |
| Frames / s, idle | - | 59.7 | 60.3 | 145.2 |
| Frames / s, listening / thinking / speaking / working / error | - | 35.8 / 38.8 / 35.7 / 39.3 / 37.5 | 35.3 / 36.8 / 35.7 / 36.2 / 37.7 | 145-160 |
| Frames / s, awaiting approval (pulse) | - | 147.3 | 56.0 | 145.0 |
| GPU 3D median / max (%) | 1.30 / 1.51 | 0.24 / 1.51 | 0.23 / 0.56 | 6.20 / 7.90 |
| Dedicated VRAM median / max (MB) | 152.7 / 173.2 | 153.9 / 174.9 | 153.9 / 174.9 | 108.7 / 110.7 |
| Raster p50 / p99 (ms) | 0.62 / 1.00 | 0.64 / 1.12 | 0.68 / 1.19 | 0.83 / 1.25 |

Evidence: `evidence/perf_run2/` (commit 7d83947d), `evidence/perf_run4/` (built from the working tree that was then
committed unchanged as 59157120 - the build preceded the commit; recorded in `perf_run4/summary.json`).

Reading: sleeping between sprite frames cut Ember's requested frames by about two thirds and its GPU time to about
4 % of Solar's. The goal of one frame per sprite frame (24 / s) is NOT reached: 48-frame clips request about 36 / s and
the idle and success clips about 60 / s. The cause of the remaining extra deliveries is not established (the
harness uses Ember's own ticker, not the app's shared clock). This does not affect correctness; the cost is already
far below every shader companion. An earlier version of `02_STATE_MATRIX.md` said "about 24 frames per second"
before it was measured (review R2-04); it now gives these measured values.

## M-4 Brain coexistence (to be measured)

Status: BLOCKED at the time of writing. Runtime v1 needs 15.3 GB; with dwm.exe (1.4 GB), the URI window (0.33 GB)
and other apps (0.35 GB) it does not fit on the 16 GB card without oversubscription (owner authorised `-OverrideGpu`
for this run only, `evidence/live/OWNER_GPU_OVERRIDE_AUTHORIZATION.json`). The GPU lease was then taken by another
session's regression chain; this work does not start a Brain while another session holds the lease.
