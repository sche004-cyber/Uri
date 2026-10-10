# Performance comparison (W1 / A0)

Acceptance criteria: every figure names its source, host and date; figures from different hosts are never compared as
if alike; what was not measured says so and whether it affects a verdict.

## 1. Baselines (historical, owner's PC — not re-measured here)

| Quantity | Value | Source (date) |
|---|---|---|
| Brain decode, live answers | 121-125 tok/s, first token 0.8-0.9 s | `STAGING_QUALIFICATION.md:26` (2026-10-10) |
| Brain calibration (synthetic decode) | 146 / 156.5 tok/s | same; `staging2/brain_host_after_restart.json` |
| Vision turn, 768 px image | 1.84 s p50 (encode ≈ 1.98 s + 0.3 s in freeze record) | VRAM report line 44; freeze record line 213 |
| GPU residency with Companion open | AT_RISK, margin −57 MB / +72 MB | `STAGING_QUALIFICATION.md:27` |
| Companion window VRAM | 401 MiB (359-420); Workspace 347-353 MiB | `research/vram-efficiency-20261010` report line 46 |
| Second resident model | rejected at freeze (cannot co-reside in 16 GB) | freeze record lines 282-287 |

## 2. Measured in this session (Linux cloud container, 4 vCPU, no GPU; 2026-10-10)

Source: `evidence/a0_w1_cpu_bench.json` (script `evidence/a0_w1_cpu_bench.py`).

| Operation | p50 | p95 |
|---|---|---|
| HTML extraction, 20 paragraphs | 0.27 ms | 0.31 ms |
| HTML extraction, 310 KB page (3000 paragraphs) | 47 ms | 50 ms |
| Citation verification, 6 claims × 6 sources | 2.2 ms | 2.4 ms |
| Extractive synthesis, 6 sources | 9.0 ms | 10.7 ms |
| Whole pipeline, 6 pages, mocked network, no Brain | 6.6-9.9 ms | 8.3-11.0 ms |
| A2UI result surface build + validation | 0.55 ms | 0.62 ms |
| Extension DOM snapshot, in real Chromium (eval round trip) | 5 ms | max 23 ms |
| Chromium launch + load + snapshot + screenshot (test harness, not runtime) | 690-734 ms | — |
| URI normalisation + second redaction of a real snapshot | 0.43 ms | 0.87 ms |
| Live Assist findings | 0.05 ms | 0.11 ms |
| Screenshot black-out + downscale (1000×900 PNG) | 66 ms | 78 ms |
| Live retrieval, direct pinned mode, pypi.org | 25-120 ms per page | `evidence/w1_live_direct_pinned.json` |

## 3. Expected effect on the Brain and GPU (reasoned, NOT VERIFIED)

- **VRAM: no change by design.** W1 and A0 add no GPU-resident component; vision reuses the projector already loaded
  by Runtime v1. The only new UI is a Flutter view inside the existing window (no new window, no new texture-heavy
  effect). Measuring the Assist view's GPU memory needs the PC (owner checklist item 6).
- **Decode speed: unchanged when Assist is idle.** All W1/A0 work is CPU-side in the worker process.
- **Contention:** the Brain has one slot. Ask URI (≤ 600 tokens) is streamed with a cancel token and is cancelled the
  moment a user turn starts (interim review F4). Research synthesis (≤ 700 tokens ≈ 6 s at 120 tok/s) yields at start
  if a user turn is running, but a user turn that starts *during* a synthesis queues behind it (L-W1-3). Vision adds ≈ 1.8 s per question. Mitigation options for the owner: make
  research synthesis extractive-only, or lower its token cap (limitation L-W1-3).
- **Not measured here (no GPU, no Runtime v1, no Windows, no display):** Brain VRAM allocation with Assist, Flutter GPU
  overhead of the Assist view, vision latency through the application path, GPU contention under concurrent URI
  threads, Windows UIA responsiveness, live provider latency. These are listed in the owner-return checklist. They do
  not affect the W1/A0 code verdicts, which are about correctness and boundaries; they block ACTIVATION.
