# URI-RUNTIME-VRAM-R1 — acceptance criteria (defined before measurement)

Milestone: owner brief "URI RUNTIME — VRAM OPTIMIZATION & RESOURCE-AWARE BRAIN" (2026-10-17).
Branch `research/runtime-vram-r1-20261017`, worktree `D:\uri-dev\uri-runtime-vram-r1`, base canonical `25048709`.

Reopening basis (freeze record section 14): "an unacceptable stability problem under realistic use". The frozen Brain
cannot start on the ordinary desktop (request 15,626 MiB, free 15,069-15,072 MiB on 2026-10-17), which blocks the UI V2
and Office live qualifications. Model, quantization, binary and engine stay unchanged (Qwen3.6-35B-A3B UD-IQ3_S,
llama.cpp b11425 Vulkan, stock). Only allocation-level launch parameters are in scope.

## Rules

- R1 Frozen files untouched: `model_lab/integration/local_brain.json`, the freeze record, pinned artifacts. Verified by
  `git diff 25048709 -- model_lab/integration/local_brain.json model_lab/URI_RESIDENT_INTELLIGENCE_RUNTIME_V1_FREEZE.md`
  being empty and the sha256 check of the artifacts.
- R2 Every lab GPU load holds the machine GPU lease (`gpu_lease.acquire`, purpose `benchmark`, declared
  `expected_vram_mib` and `max_hold_s`), uses a lab port (never 18470), and refuses to start while another
  llama-server runs or the lease is held.
- R3 Evidence classification: only a run that completed with a result supports a claim. Failed, killed or timed-out
  runs are recorded as such.
- R4 Measured, not estimated. Every number in the final tables cites an evidence file. Estimates are labeled.
- R5 Intentional CPU placement (host buffers we asked for) is reported separately from demotion (device buffers that
  are not resident).
- R6 No aggressive stress tests. Coexistence uses ordinary desktop apps only.

## Acceptance criteria

| ID | Criterion | Evidence |
|---|---|---|
| AC1 | Root cause of the 15,626 MiB request and of the startup block is explained with log-level buffer accounting, and discrepancies between earlier reports are reconciled | buffer parse of a frozen-equivalent load |
| AC2 | VRAM breakdown per component (weights, KV, recurrent state, compute, MTP draft, vision weights, vision compute, host-visible) for each tested profile | `evidence/probe/*/probe.json` |
| AC3 | Each candidate profile: request, residency, non-local, demoted amount, decode tok/s (n>=3 requests), prefill, load time | same |
| AC4 | Context / Vision / MTP compatibility matrix with the measured fit margin on the 2026-10-17 desktop | report table |
| AC5 | MTP benefit measured on more than one prompt type (prose and URI-style structured output) at the same context | speed rows |
| AC6 | Vision cost measured: GPU vs CPU encode time on the same image; resource release after a vision-off reload | vision rows, release samples |
| AC7 | Thinking: per-request on/off and budget verified on the running server without reload; no simulated capability | thinking probe |
| AC8 | 64K: long-context retrieval suite at 64K on the candidate default profile, plus the 221-case fast suite with 0 score-changing cases vs the frozen baseline (or the differences listed) | suite results |
| AC9 | Profile switch: reload time, VRAM release lag, history kept, refusal when the new context is smaller than the live conversation | switch test |
| AC10 | Runtime candidate code: profiles derived from the frozen config without editing it, per-profile measured `required_mib` used by the existing lease fit check, minimal UI contract; unit tests; existing OI/lease tests still pass | pytest |
| AC11 | Coexistence: candidate default loaded next to Chrome and the URI UI, demotion and decode recorded | multitask rows |
| AC12 | Independent review status recorded honestly (PENDING AUDIT if no reviewer is available) | report section |

A verdict that 64K can become the default requires AC3, AC5, AC8 and AC11 to pass for that profile.
