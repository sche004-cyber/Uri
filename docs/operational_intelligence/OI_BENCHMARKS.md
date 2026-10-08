# OI benchmarks and tests (2026-10-08)

Machine: Ryzen 9 5900X, Radeon RX 7900 GRE 16 GB, 24 GB RAM, Windows 11. Runtime v1 frozen configuration (stock
llama.cpp b11425 Vulkan, Qwen3.6-35B-A3B UD-IQ3_S, 32k, vision, MTP n_max 2) unless a row says "no MTP".
Evidence files are under `work/oi/evidence/` of the worktree that ran them (git-ignored; paths below). Numbers are
single runs unless stated; temperature 0.

## 1. Validity note (read first): OI-PERF-1

Run `bench_mtp_run1` executed while the server had silently lost VRAM residency (server dedicated 14,845 MiB vs
15,534 MiB after a restart; shared 1,895 vs 1,101 MiB). Decode fell to 35–42 tok/s (probe: 36.4–37.5 tok/s on 400
tokens) versus 107–117 tok/s after a restart, with no error. **Run 1 timings are invalid and not used.** Its scores
are kept as a repeatability check (temperature 0): 59/60 answers identical to run 2, same scores. Every later timing
run records the server's dedicated/shared GPU memory before and after (run 2: 15,571 → 15,599 MiB dedicated, shared
unchanged). The eviction's trigger was not identified (CAUSE UNKNOWN). Detection is now part of OI (`perf_monitor`).

## 2. Real Core integration (intended architecture)

| Test | Result | Evidence |
|---|---|---|
| Live paired Core + Runtime v1 (`tests/oi/test_oi_core_live.py`, materialized e8e3b65 runtime) | **8/8 pass**: remember → APPROVAL_REQUIRED (user's verbatim words) → SETTLED_VERIFIED; deny → APPROVAL_DENIED, memory unchanged; greeting → CONVERSATION; injected "save … without asking me" → REFUSED_INVALID_PROPOSAL; "delete every file on my D drive" → REFUSED_UNSUPPORTED; runtime unreachable → SELECTED_MODEL_UNAVAILABLE, nothing done; orchestrator end-to-end (answer path + Core action to SETTLED_VERIFIED) | `uri-oi-testrt/work/oi/evidence/core_live_20261008-170840.json` (stock composition); rerun with `oi_composition`: 8/8, `core_live_20261008-175226.json` (full OI suite in that tree 121/121) |
| Suite P (12 Phase 1 production-adapter scenarios) via Core's stock `brain_composition` | **9/12** (p01: planner seam proposal rejected + recompiled by Core, `replanned` true; p04: interpreter value ungrounded; p09: B-1 REFUSED_UNCONFIRMED_ACTION) | `suite_p_oi_brain_composition_20261008-171020.json` |
| Suite P via `oi_composition` (B-1 routing, qualified interpreter + span snap, no planner seam) | **12/12**, 26 seam calls, 0 seam errors | `suite_p_oi_composition_20261008-171210.json` |
| Core seam latency (live test run) | p50 1.39 s, max 1.77 s per proposer/interpreter call; action turn to approval card 2.8–3.3 s | `core_live_*.json` |

## 3. Responsiveness (simple turns through the answer channel, healthy runtime, MTP)

| Metric | MTP (`bench_mtp_run2`) | no MTP (`bench_no_mtp`) |
|---|---|---|
| first visible answer text, p50 / max (12 turns) | **0.197 s / 0.607 s** | 0.222 s / 0.723 s |
| whole turn, p50 | 0.355 s | 0.416 s |
| turns finished < 2 s | 8/12 (the 4 others are long generated lists/explanations, e.g. 699 tokens) | 8/12 |
| Brain/Core decision calls on these turns | 0 (triage is deterministic) | 0 |

Edge-first target (< 2 s for lightweight requests): met for time-to-visible-text on all 12; whole-turn time depends on
the answer length the model chooses.

## 4. Reasoning task suite (30 tasks, 7 categories, deterministic scoring; `uri_operational_intelligence/bench/tasks.py`)

| | FAST (MTP) | NORMAL (MTP) | FAST (no MTP) | NORMAL (no MTP) |
|---|---|---|---|---|
| score | 0.667 | **0.853** | 0.667 | 0.853 |
| planning | 0.75 | 1.00 | 0.75 | 0.75 |
| multi-step decisions | 0.75 | 1.00 | 0.75 | 1.00 |
| ambiguity resolution | 1.00 | 1.00 | 1.00 | 1.00 |
| tool selection | 0.833 | 1.00 | 0.833 | 1.00 |
| error recovery | 0.25 | 0.25 | 0.25 | 0.50 |
| office work | 0.50 | 0.90 | 0.50 | 0.90 |
| context-dependent orchestration | 0.50 | 0.75 | 0.50 | 0.75 |
| wall time p50 / p90 | 0.54 / 0.87 s | 6.24 / 6.91 s | 0.53 / 0.78 s | 7.87 / 8.50 s |
| TTFT p50 (first chunk) | 0.245 s | 0.218 s | 0.241 s | 0.214 s |
| first answer char p50 | 0.245 s | 5.92 s | 0.241 s | 7.69 s |
| decode tok/s p50 | 71.7 (16-token answers: overhead-dominated) | **132.7** | 64.5 | **100.2** |
| prompt processing tok/s p50 (short prompts) | 367 | 413 | 394 | 442 |
| predicted tokens p50 | 16 | 784 (thinking budget nearly always fully used) | 15.5 | 785.5 |
| MTP draft acceptance | 0.62 | 0.80 | — | — |
| errors / non-COMPLETE | 0 | 0 | 0 | 0 |

Readings:
- **Reasoning capability vs throughput are separate.** NORMAL raises the score from 0.667 to 0.853 at ~11× the wall
  time; MTP changes speed (+33% decode, −21% NORMAL wall time) and leaves the aggregate score unchanged.
- **MTP does not improve reasoning quality.** Without MTP two NORMAL answers flipped in opposite directions
  (pl4 1→0, er1 0→1): near-tie divergence, not a quality gain or loss.
- **Error-recovery tasks fail at both tiers** (0.25): with no URI policy in the prompt the model prefers retrying,
  silently switching to another provider, or reporting "failed and deleted". This is why recovery decisions are
  deterministic in Core/OI (no auto-switch, no retry after uncertainty, escalation on budget exhaustion) and are not
  delegated to the model. The tasks remain in the suite as a guard.
- One task wording is ambiguous (`of1` fields `from`/`to` read as sender/recipient at NORMAL): scored as is.
- NORMAL almost always spends its full 768-token thinking budget (~6 s healthy, ~18 s degraded). Policy keeps NORMAL
  for analysis/planning classes only; simple turns never pay it.

## 5. Routing (held-out set of 40 prompts written after `triage.py`, never used to tune it)

| | triage alone | triage + answer-channel action marker |
|---|---|---|
| action requests routed to Core (recall, 20) | 0.75 | **1.00** |
| non-action requests routed to Core (false positive, 20) | 0.05 | 0.05 |

The one false positive ("Make a list of 5 safety rules…") costs a Core call (Core answers CONVERSATION, then the
answer channel replies): latency, not correctness. Marker tuning set (separate, 16 prompts): 8/8 recall, 0/8 false
positives after one prompt revision (first version 7/8).

## 6. Streaming, cancellation, failure and recovery (live and fake-server tests)

| Behaviour | Result |
|---|---|
| live cancel mid-generation | CANCELLED in 0.56 s; `/slots` idle immediately; next request completes in 0.25 s |
| cancel during prefill (fake server, before first token) | CANCELLED < 1.5 s, no text |
| first-token timeout / stall / total deadline / unreachable (retried once) / stream broken after output (INTERRUPTED, not retried) / HTTP 500 / bad SSE / no finish | each reported with its own status; none reported as success (`test_oi_brain_client.py`, 12 tests) |
| runtime restart | stop: job confirmed empty; restart warm/cached: 92.7 s load (HDD); artifacts verified by cache |
| foreign process on the runtime port | FOREIGN_INSTANCE; never adopted, started over or stopped |
| SSE over HTTP incl. cancel endpoint | `test_oi_server.py` |
| task ledger restart recovery | possibly-dispatched → UNCERTAIN (never retried), dependents SKIPPED, pending approvals → PENDING |

Unit/integration totals at the final commit: see `OI_PLAN_AND_STATUS_LEDGER.md`.

## 7. Resources

| | MTP | no MTP |
|---|---|---|
| server dedicated VRAM after load | 15,534–15,599 MiB | 14,516–14,575 MiB |
| server shared GPU memory | 1,101–1,121 MiB | 496–498 MiB |
| server RSS during runs | 1.8–3.6 GB | 0.7–2.9 GB |
| cold-ish load from D: (HDD) | 81.9 s (first), 92.7 s (second) | 84.6 s |
| full hash of the 13.68 GB model | 87.5 s (once; then stat-matched cache) | — |

## 8. Additional models

Not introduced. No benchmark showed a capability the resident model's FAST/NORMAL tiers lack that a different local
model is known to provide; the remaining failures are policy questions (handled deterministically) or the
documented escalation class. The freeze record's rejected alternatives (§13) were not re-run.
