# Runtime v1 throughput loss with the URI UI open: investigation

Date: 2026-10-09. Owner question: Runtime v1 decoded at about 111-132 tok/s before, but only 33-40 tok/s while the
URI UI was open (the UI was reported at about 700 MiB GPU). Several development threads were running, and a duplicate
Brain instance existed briefly after a reboot. Is the UI the cause, or is the loss interference from concurrent work?

Every hypothesis below is judged only on recorded evidence. Each item names its evidence level:
**MEASURED-HERE** means this session measured it in a controlled run (§5). **RECORDED** means another accepted phase's
receipt recorded it; the file is named and was re-read for this report. **NOT MEASURED** means no evidence exists.

## 1. Acceptance criteria for this investigation

- AC-P1: Name the mechanism of the loss with evidence, not by elimination.
- AC-P2: Separate the UI's own cost (GPU memory, GPU compute, CPU) from interference by concurrent workloads.
- AC-P3: Test every competing hypothesis from the owner's brief, and mark each one supported, refuted or not tested.
- AC-P4: Make no optimization change unless it shows an improvement over the frozen baseline.
- AC-P5: State every limit of the evidence.

## 2. Mechanism (RECORDED, reproduced by two independent phases)

Frozen Runtime v1 asks for **15,626 MiB of device-local memory** on a **16,368 MiB** card (Adaptive Runtime R1:
weights 12.34 GiB, vision 1.08, MTP draft 1.13, KV/compute 0.73). The idle desktop alone takes about 650 MiB
(census at 09:39 today: 657 MiB attributed, dwm.exe 326 MiB). That leaves about **85 MiB** for everything else.
When the total is larger, the AMD driver moves whole 1 GiB suballocation blocks of the Brain to system memory. If a
weight block is moved, every decode step streams it over PCIe:

| Source | State | Decode |
|---|---|---|
| Adaptive Runtime R1 (`research/adaptive-runtime`, `docs/research/ADAPTIVE_RUNTIME_RESEARCH_R1.md`) | idle desktop | 110-127 tok/s |
| same | one idle 1.09 GB Ollama model next to it (no compute) | 24.7 tok/s, 7 of 7 loads |
| WS hardening `brain_host_report_0858_before_freeze.json` (08:37:22) | server 12,998 MiB dedicated + **3,678 MiB non-local**; other processes 2,343 MiB, including several `uri_ui.exe` | **33.7 tok/s**, DEGRADED |
| WS hardening `WS_TEST_EVIDENCE.md` | memory taken from the Brain after load (other sessions' app windows) | 141 -> 27-38 tok/s |
| WS hardening restart experiment `restart_exp_2.json` | idle desktop, warm restarts | 151-158 tok/s, 4 of 4 |

The loss comes from **memory residency**. GPU compute is not the cause. An idle consumer that does no GPU work gives
the same 25 tok/s as a busy one (R1). The size of the loss (3-5x) matches PCIe streaming of demoted weights. It does
not match a compute share of a few percent (§3, H2).

## 3. Hypotheses

| # | Hypothesis (owner's brief) | Verdict | Evidence |
|---|---|---|---|
| H1 | The UI's GPU **memory** pushes the Brain over the card | **Supported, as a contributor.** One Living window uses 126-180 MiB on average, with peaks up to 482 MiB (companion-voice `VOICE_PRESENCE_REPORT.md` §8.1). Integrated Living windows were recorded at 159-454 MiB (hardening host reports, pids 5716, 8588, 2436, 4340, 1340, 9992, 11484). The budget has about 85 MiB of slack, so one window can cause a shortfall and demotion, but the result is not certain (AT_RISK). | RECORDED |
| H2 | The UI's GPU **compute** (Orb animation) slows the Brain | **Small effect; not the cause of a 3x loss.** The companion's own share of the 3D engine is 3-19% (companion-voice §8.1). The reverse direction is RECORDED: while the Brain generates, the companion drops to 100-108 fps (AMBER stutter finding). The effect of companion compute on the Brain's tok/s is measured in §5 (condition B vs C). | RECORDED + §5 |
| H3 | **Concurrent development threads** (several UI windows, benchmarks) | **Supported. This is the largest recorded factor.** At 08:37 and 08:57 the host saw 3-5 `uri_ui.exe` windows from different sessions at the same time (2.34 GB of other-process memory), and the Brain had 3.68 GB demoted. The hardening session found 4 companion-voice windows (~1.4 GB) at 08:58. | RECORDED |
| H4 | A **duplicate Brain instance** | **Supported for 07:05-07:08 only.** This session started Runtime v1 without the lease while the hardening experiment held it. Two servers were loaded for about 2 minutes, and that experiment produced zero runs (`TI_REPORT.md` §6.1). Since then, every Brain start goes through the machine-wide lease, and the census reports a second llama-server. | RECORDED |
| H5 | **CPU, RAM, paging or disk** contention from tests | **Not supported.** Decode is GPU-bound: all layers are offloaded and the MoE experts are in VRAM. Prefill and decode do not change with CPU load in R1. The effect of CPU-only test load on tok/s is measured in §5 (condition D). Disk matters only for loading: NVMe 10-25 s, HDD 25-361 s (R1). | §5 |
| H6 | **Configuration** change (offload, KV, context) | **Refuted.** Every recorded run uses the frozen argv (`local_brain.json`, freeze record v1), and the host pins it. No phase changed it. | RECORDED |
| H7 | **Warm-up or restart** timing | **Refuted as a cause.** VRAM is released 1.5-1.9 s after stop, against about 94 s for a load. Immediate restarts were healthy in 2 of 2 runs. The old "27 tok/s right after a restart" was one nondeterministic demotion (hardening `restart_exp_2.json`). | RECORDED |
| H8 | **Thermal** limits | **Not tested.** No GPU temperature or clock samples exist. Healthy runs between degraded ones (151-158 tok/s) make a slow thermal cause unlikely, but this is not proven. | NOT MEASURED |

## 4. Answer to the owner's question

- With the UI open, the 33-40 tok/s state is a **demoted Brain**. It occurs when the total GPU memory of all processes
  exceeds what the card can give, so the driver moves part of the Brain to system memory. On the recorded occasions,
  most of the extra memory came from **several app windows of different development sessions**, not from one URI UI.
- A single Living window can cause the same state, because the frozen profile leaves only about 85 MiB of slack. A
  single window does not cause it reliably. Which block the driver demotes is nondeterministic (R1, R2).
- The Orb's compute cost is small (3-19% of the 3D engine). It cannot explain a 3-5x loss. §5 measures its effect on
  tok/s when no memory is demoted.
- TI's own physical-app run (`TI_TEST_MATRIX.md` §3) recorded one `uri_ui.exe` at 447 MiB, with llama-server at
  14.8 GiB dedicated and **1.9 GiB non-local**, decoding at 33-40 tok/s. So one Living window has coincided with
  demotion. That record does not list the other GPU processes present at the time, so it cannot show whether the
  window was the only consumer.

## 5. Controlled comparison (A/B/C/D)

**Status: answered by reused controlled evidence. This session did not re-measure.**
- The companion-voice session ran the controlled comparison today (14:47-15:05 IST) under the machine-wide lease
  (`gpu_lease run --purpose benchmark`). Its setup: its own Runtime v1 instance (pinned b11425 binary, frozen model
  and argv, private port 18499), the Runtime v1 calibration prompt, 256 tokens, temperature 0, MTP on.
- Record: `phase/companion-voice` @ `417cd26`, `docs/companions/settings/COMPANION_SETTINGS_REPORT.md` §4.4, raw
  files `docs/companions/settings/evidence/perf/brain/*.json` and `*.samples.csv`.
- The owner's brief allows reuse (the TI changes do not touch the GPU path), and it matches the reference figures the
  owner quoted.
- Mapping to this report's conditions:

| Condition | Evidence | Brain decode | Companion |
|---|---|---|---|
| A Brain alone | companion-voice, before and after both orders | 159.3-161.9 tok/s | — |
| C UI open + Orb animating, **window opened before the Brain loaded** (UI-first) | companion-voice order 2 | 132.7-146.9 tok/s (62 requests, median ~140) | 144.7 FPS while generating, raster p99 3.6 ms, 0.05% frames over 16.7 ms |
| C' UI opened **after** the Brain loaded (Brain-first) | companion-voice order 1 | 45-50 tok/s, **staying ~51 tok/s after the window closed** | 144.5 / 103.7 / 29.9 FPS at 144 / Adaptive / 30 |
| B UI open, no rendering | not measured. A minimised Flutter window does not render, and its effect would lie between A and C | — | — |
| D CPU-only workload in parallel | not measured. Decode is GPU-bound (H5) | — | — |

What this shows:
1. With the Brain resident in VRAM, the UI's own rendering costs about **12% of decode** (160 → ~140). That is the
   compute share (H2).
2. A window opened **after** the Brain loaded leaves the Brain at about a third of its speed for the life of that
   server, even after the window closes. That pattern matches demotion (§2: memory moved out at load or at eviction
   stays out), not live contention. Companion-voice did not record residency in those runs, so the mechanism is
   inferred there. It is measured directly in the hardening host report at 08:37 (3,678 MiB non-local at 33.7 tok/s).
3. Start order, not the companion's settings, decides most of the loss. That is the "UI-first" behaviour: open URI's
   window first, then start the Brain. The lease fit check then accounts for the window, and the host's residency
   alert (`GPU_MEMORY_TAKEN_AFTER_LOAD`, Restart Brain) covers the other order.

Distinction asked for in the brief:
- UI overhead ≈ 12% of decode when everything fits.
- Concurrent-workload interference: several app windows of other sessions, or a GPU consumer that starts after the
  Brain loaded. It causes the 3-5x loss through VRAM demotion, and it persists until the Brain restarts.

Protocol this session had prepared (kept for the record; not run, because the evidence above answers the question and
SAFE-1 argues against unnecessary GPU load):
- Same frozen Runtime v1 (host-started under the lease), same prompt, `n_predict` 256, temperature 0, `cache_prompt`
  false. 5 repetitions per condition, after one discarded warm-up.
- Per repetition: llama-server `timings` (`predicted_per_second`, `prompt_per_second`) plus the server's per-process
  dedicated and non-local GPU memory before and after.
- **Validity rule:** a condition counts only when the server's non-local memory stays within 256 MiB of condition A.
  Otherwise the result is labelled DEMOTED and is not used as a compute measurement.
- **Safety rule (SAFE-1):** if non-local memory rises by more than 512 MiB, or the census says CONTENDED, stop the
  Brain and end the run.
- A: Brain alone (desktop only). B: Living app open but minimised (Flutter does not render a minimised window).
  C: Living app in the foreground with the Orb animating. D: Brain alone plus a CPU-only test workload
  (`pytest tests/ws -q`).

## 6. Concurrent-development resource governance

What exists (WS hardening, accepted): a machine-wide OS-lock lease in `%LOCALAPPDATA%\URI\gpu`
(`uri_operational_intelligence/gpu_lease.py`); `gpu_lease run` for workloads; a census with the measured budget rule
(FITS / AT_RISK / CONTENDED); a Brain host that waits for contention and VRAM release; a residency alert and
DEGRADED state after load. Observed in use today:
- the Brain host held the lease;
- the TI, hardening and canonical chains held it as `regression_chain`, to keep GPU-heavy tests off while CPU suites
  ran;
- companion-voice wrapped its contention benchmarks in it (`benchmark`, `--wait`);
- hand-overs took 0.24-0.5 s, and no process was ever terminated by another session.

Requirement by requirement:

| Requirement (owner's brief) | Covered by | Gap |
|---|---|---|
| One exclusive owner for GPU-intensive Brain benchmarks or live tests | lease (exclusive OS lock) | none for cooperating tools |
| Explicit acquisition and release | `acquire`/`run`, history file | none |
| Detect duplicate model instances before starting another | census lists every `llama-server.exe`; the host refuses a start under contention | none since 07:08 (H4) |
| Distinguish UI-only testing from GPU-intensive inference | — | **GAP G-1**: app windows are not lease clients. Each Living window uses 126-482 MiB. Several sessions opened windows while a Brain was resident (08:37/08:57, 2.3 GB); the census saw them only after the fact |
| Record contention and benchmark validity | host calibration, residency alert, census in each report | benchmark scripts outside URI (e.g. this report's §5) must record the server's non-local memory themselves. §5 does |
| Keep CPU-only work and audits parallel | Codex reviews are remote. Chains hold the lease only to keep GPU work off | none |
| Never terminate another session's processes | lease never kills; it only waits | none |

**Smallest compatible repair proposed for G-1 (P-GOV-1, not implemented).** Before a session opens a URI app window
for testing or capture (`capture_ws.ps1`, `run_perf.ps1`, the launcher), it calls the existing `gpu_lease status`. If
the holder's purpose is `runtime_v1_brain` with a live test or benchmark label, or is `benchmark`, the session waits
or asks its owner first. An ordinary resident Brain for daily use does not block windows: the host's residency alert
already reports the effect. This needs no new lock, scheduler or resource manager, only a check in the scripts that
open windows. Why it is not implemented here:
- those scripts belong to other threads (hardening's launcher and capture tool, companion-voice's perf runner);
- the right blocking set is an owner choice;
- an unenforced policy line would protect nothing.

Owner decision: adopt P-GOV-1, and say which session implements it.

## 7. Limits of this evidence

- One card (RX 7900 GRE), one driver (32.0.31041.1004).
- Thermal state was not sampled (H8).
- Reduced motion cannot be set from outside the app (EffectsSettings is not persisted and has no environment
  switch), so B uses a minimised window instead of a stopped animation.
