# URI Engine research: Strata-inspired runtime options for Qwen3.6-35B-A3B on URI's hardware

Status: CLOSED research record, 2026-10-06/07 (two machine interruptions and two recoveries on the same day; section 9).
Outcome: **URI Resident Intelligence Runtime v1 — FROZEN** (section 11; `URI_RESIDENT_INTELLIGENCE_RUNTIME_V1_FREEZE.md` §17).
Scope: research only. No Core change, no commit, no cutover. All evidence is machine-readable under
`model_lab/evidence/uri_engine/` and reproducible from the scripts in `model_lab/uri_engine/`.

Working tree: `C:\Users\cheta\.codex\worktrees\uri-phase1-integration\uri-agent` (Phase 1 frozen inventory verified
before, between and after the runs: `freeze_check_recovery_start.json`, `freeze_check_recovery_start2.json`,
`freeze_check_recovery_end.json`, 121 files, 0 differences, archive sha256 `31a34dcb...` matches).

## 0. Question and answer in one paragraph

Question: can Qwen3.6's repeated URI context be processed substantially faster by safely reusing stable
prefix / recurrent state, and which runtime architecture (stock llama.cpp, small extension, fork, dedicated engine,
Strata adaptation) captures most of the measured gain?

Answer: see section 10 (written after the queue finished). The sections below are the evidence in priority order:
prefix/state reuse (1), repeated-context prefill latency (2), correctness (3), VRAM/RAM (4), decision latency (5),
MTP/speculative decoding (6), raw generation (7), then the Strata analysis (8) and the crash record (9).

Qualified production baseline (local_brain.json): `llama-server` b11425 Vulkan release, `Qwen3.6-35B-A3B-UD-IQ3_S.gguf`
(sha256 `66a3ca88...`) + `mmproj-F16.gguf`, 32k context, q8_0 KV, flash attention, `-b 2048 -ub 1024 --cache-ram 1024`,
`-ngl 999`, one slot. Reproduced qualification scores (ue_base, 221 cases): C 1.000, D 0.861, DG 0.861, F 1.000,
H 1.000, L 0.933, O 1.000, P 12/12, S 1.000.

## 1. Prefix / recurrent-state reuse on the hybrid model (highest priority)

### 1.1 What llama.cpp b11425 already does for a hybrid (GDN + full-attention) model

Qwen3.6-35B-A3B is `qwen35moe`: 30 Gated-DeltaNet blocks with a recurrent state and 10 full-attention blocks with a
KV cache (details in section 8.2). A recurrent state cannot be "rolled back" to an arbitrary earlier token, so plain
KV-prefix reuse does not apply. The server instead keeps *context checkpoints* (recurrent state + KV up to a
position, 62.8 MiB of recurrent state per checkpoint plus KV) and a host-RAM *prompt cache* (`--cache-ram`) that stores
whole slot states with their checkpoints and restores the one with the longest common token prefix.

Checkpoints are created (server trace, `-lv 4`) at: (a) the start of every user message, (b) one ubatch before the
end of the prompt ("near end"), (c) with `--checkpoint-min-step` smaller than the ubatch, nowhere else in stock
b11425 (`server-context.cpp`: ordinary mid-prompt checkpoints are skipped unless `is_user_start || near_prompt_end`).
When the new prompt diverges from the cached one after the last usable checkpoint, the server logs
`forcing full prompt re-processing due to lack of cache data (likely due to SWA or hybrid/recurrent memory)` and
recomputes from the last checkpoint before the divergence, or from zero.

### 1.2 Repeated-URI-context benchmark (bench_context_reuse.py)

Context layout, sized by the server tokenizer to ~4k / ~16k / ~30k tokens (prompts are built once per layout,
`context_reuse/prompts_<layout>.json`, so every configuration sees byte-identical input):

```
[STABLE URI SYSTEM CONTRACT]  (the real DECISION_CONTRACT_SYSTEM_PROMPT)
[CAPABILITY DEFINITIONS]      (real capability summaries / affordances from the Core directory)
[PERMISSION STATE]            (JSON, version 7)
--- end of system message; the stable part is ~4,038-4,129 tokens ---
[SESSION STATE]               (facts, recent conversation)
[RETRIEVED EVIDENCE]          (N dossier blocks; one changed block at 75% for scenario D)
[CURRENT USER TURN]           (JSON-only instruction)
```

Scenarios, run as one sequence against a resident server (state carries over exactly as in URI), two sequences per
size (different evidence seed):

| scenario | logically new tokens (first differing token vs A, from the tokenized prompt) |
|---|---|
| A_fresh | all |
| B_repeat | 0 |
| C_new_turn | 26 (only the user turn differs) |
| A_reprime | 0 (A again) |
| D_evidence_changed | ~112 at 4k, ~3,100-3,400 at 16k, ~6,300-6,700 at 30k (one block at 75% of the evidence, everything after it shifts) |
| A_reprime2 | 0 |
| E_permission_changed | everything after token ~4,038 (permission version bump inside the system message) |
| A_after_E | 0 (is the A state still cached after D and E?) |

Measured per call: server `prompt_n` (tokens actually recomputed), `cache_n` (reused), `prompt_ms`, client TTFT and
total wall, output text (48 tokens, greedy), and `excess_recompute = prompt_n - logically_new_tokens`. The last number
is the one the research question is about: how much computation URI pays for a change it did not make.

### 1.3 Results (release b11425 binary unless noted; full tables in 1.5)

Control (`--cache-ram 0 --ctx-checkpoints 0`): every scenario costs the full prompt, 1.8 s at 4k, 7.2 s at 16k,
15.6 s at 30k of prefill (~1,900-2,100 prompt tok/s); nothing is reused.

Production flags (`--cache-ram 1024`, checkpoints on, URI's one-JSON-request shape = layout "single"):

| scenario | what happens | 16k | 30k |
|---|---|---|---|
| B exact repeat | whole slot state reused | 4 tokens, 54 ms prompt, TTFT 0.32 s | 4 tokens, 63 ms, TTFT 0.33 s |
| C new user turn (26 new tokens) | resumes from the "near end" checkpoint one ubatch before the end | 1,025 tokens (excess 999), 0.63 s, TTFT 0.89 s | 1,025 tokens, 0.79 s, TTFT 1.06 s |
| D one evidence block changed at 75% (3.2k / 6.6k new tokens) | no checkpoint between the system boundary and the change: resumes from the system boundary (4,129) | 11,934 tokens (**excess 8,698**), 5.7 s | 25,816 tokens (**excess 19,171**), 14.0 s |
| A again after D (0 new tokens) | the A state was not saved before D (f_keep 0.81 > 0.5, section 1.4) | 11,910 tokens, 5.7 s | 25,817 tokens, 14.0 s |
| E permission version bump (everything after 4,038 is new) | correct invalidation; resumes from the nearest earlier checkpoint | 12,441 tokens (excess 440), 5.9 s | 26,348 tokens (excess 440), 14.3 s |
| A again after E | the 16k/30k A state was evicted from the 1 GiB cache (entries of 544-691 MiB) | 12,441 tokens, 5.9 s | 26,348 tokens, 14.3 s |

So with the production flags the excess computation for a mid-context evidence change is 8.7k tokens at 16k and
19.2k tokens at 30k (73-74% of the prompt), and returning to a previously seen 16k/30k context costs the full
prompt again. The 4k case is already fine (excess <= 480 tokens) because the whole evidence fits in the last ubatch.

What each candidate changed (same prompts, same binary unless noted; numbers at 16k / 30k, median of two sequences):

| candidate | mechanism | C new turn | D evidence changed (excess) | A after D | A after E | cost |
|---|---|---|---|---|---|---|
| `--checkpoint-min-step 1024 --ctx-checkpoints 16` (ctx_ckpt1024) | none in practice: stock creates mid-prompt checkpoints only at user-message starts and near the prompt end | 1,025 / 1,025 | 8,698 / 19,171 | full | full | identical to production in every row |
| layout "split": the current turn as its own user message after an "Acknowledged." assistant turn (ctx_prod_split) | user-message-start checkpoint right before the turn | **50 / 50 tokens, TTFT 0.54 / 0.58 s** | 9,213 / 19,686 | full | full | none (URI-side prompt shape) |
| `--cache-ram 4096` (ctx_cache4096) | the 16k/30k states fit the cache | 1,025 | 8,698 / 19,171 | full (not saved, 1.4) | **4 tokens, TTFT 0.63 / 0.78 s** | server RSS 3.3 GB (+1.5 GB) |
| `--cache-ram 4096 --slot-prompt-similarity 0` (ctx_sim0_cache4096) | LRU slot path: the slot state is always saved before a different prompt is loaded (1.4) | 1,025 | 8,698 / 19,171 | **4 tokens, TTFT 0.50 / 0.59 s** | **4 tokens** | server RSS 5.1 GB, min free RAM 5.8 GB |
| layout "multi": evidence as 4 acknowledged user messages (ctx_prod_multi) | a checkpoint at each part start, but stock skips user-start checkpoints closer than `--checkpoint-min-step` (default 8,192) to the previous one | 50 / 50 | 9,067 / **6,326** (only the 30k parts are > 8k apart) | full | full | prompt shape only |
| multi + `--checkpoint-min-step 512 --ctx-checkpoints 32 --cache-ram 4096 --slot-prompt-similarity 0` (ctx_prod_multi_ms512, **stock flags + prompt shape**) | every part start gets a checkpoint; every state is saved | 50 / 50 (TTFT 0.43 / 0.56 s) | **2,780 / 6,326** (= the distance from the start of the evidence part that contains the change; 6,067 / 12,999 tokens, 3.7 / 8.5 s) | **4 / 4** | **4 / 4** | server RSS 5.3 GB, min free RAM 5.6 GB; prefill rate unchanged (1,801 tok/s) |
| patched build, `-ub 1024 --checkpoint-min-step 512 --ctx-checkpoints 8` (ctx_ux_fine1024) | mid-prompt checkpoint at every ubatch boundary (patch 2) | 1,021 / 1,238 | **506** / 23,300 (the 8-entry ring evicted the system-boundary checkpoint at 30k) | 3,718 / full | full (boundary evicted) | +0.4 GB RSS |
| patched build, `-ub 512 --checkpoint-min-step 256 --ctx-checkpoints 16` (ctx_ux_fine512) | same, finer | 643 / 516 | **250 / 227** | 3,462 / 6,873 | full (boundary evicted) | +0.4 GB RSS; prefill rate unchanged vs the equally built stock binary (566 vs 542 tok/s at 30k) |
| patched build, split layout, `-ub 2048 --checkpoint-min-step 1024 --ctx-checkpoints 32 --cache-ram 4096 --slot-prompt-similarity 0` (ctx_ux_best2_split) | a checkpoint at every 2,048-token ubatch boundary, 32 of them cover the context, always-save cache | 50 / 50 (TTFT 0.56 / 0.64 s on the slow build) | **506 / 739** (3,758 / 7,400 tokens) | **4 / 4** | **4 / 4** | server RSS 6.9 GB, **min free RAM 3.9 GB** (too tight for this 24 GB machine; 16 checkpoints or a 2 GiB cache would halve it); E keeps its boundary (excess 696 / 1,483) |
| (ctx_ux_best_split, same with `-ub 1024 --checkpoint-min-step 1024`) | mis-configured: the patch needs min-step < ubatch, so no fine checkpoints were created; D identical to stock (8,698 / 19,171) while C/A rows match the row above | - | - | - | - | kept as evidence of the patch's activation condition |

Reading: the stock server already removes the repeated-context cost for the two most common URI shapes, an exact
repeat and a new turn on an unchanged context, provided the turn is a separate user message (50 tokens instead of
1,025, 0.5 s TTFT at 30k). The remaining excess is structural: (1) a change inside a long message is resumed from the
last *message boundary* before it, because stock creates no checkpoints inside a message; (2) the slot state is not
saved to the prompt cache when the next prompt shares more than half of it, which on a hybrid model throws the state
away; (3) the default 1 GiB cache holds one 16k/30k state. (2) and (3) are fixed by two stock flags
(`--slot-prompt-similarity 0 --cache-ram 4096`) at a RAM cost; (1) is fixed either by prompt shaping (message
boundaries where the content can change, with `--checkpoint-min-step` lowered so stock honours them) or by the
7-line checkpoint patch, which brings the excess down to the ubatch size.

### 1.4 Why the stock server loses the A state before D (`tools/server/server-context.cpp`, b11425)

`get_available_slot`: a slot is chosen by longest-common-prefix similarity; the current slot state is saved to the
prompt cache only `if (f_keep < 0.5f)`, i.e. when the new prompt keeps less than half of it. D keeps 81% of A
(12,954 / 16,039 tokens), so nothing is saved; the hybrid model then cannot use the kept 81% past its last checkpoint
(4,129) and recomputes 11,934 tokens, and A's full state is gone for good. With `--slot-prompt-similarity 0` the
similarity path is disabled, the LRU path is taken and `update_cache = true` unconditionally, so A is saved (and
restored in 4 tokens when it returns). `server_prompt_cache::load` then picks the cached entry with the better
`f_keep`/`f_sim` than the current slot. Checkpoint creation (`create_checkpoint`) evicts FIFO when the list is full
and skips user-start checkpoints closer than `--checkpoint-min-step` (default 8,192) to the previous one; "near end"
means one ubatch before the end of the prompt.

### 1.5 Full tables (generated by `model_lab/uri_engine/ctx_report.py`; also stored as `context_reuse/TABLES_*.md`)

Release b11425 binary (production runtime). TTFT values of the runs stamped 18:35-20:09 include the ~0.1 s sampler
confound of section 2; the 14:11-14:24 runs (ctx_control, ctx_prod) and the runs from 20:12 on do not.

| run | layout | extra flags | binary | load s | peak VRAM MiB | peak RSS MiB | min free RAM MiB | A_fresh prefill tok/s (30k) |
|---|---|---|---|---|---|---|---|---|
| ctx_control | single | `-b 2048 -ub 1024 --cache-ram 0 --ctx-checkpoints 0` | release | 6.32 | 15115.7 | 812.7 | 14607.9 | 1919 |
| ctx_prod | single | `-b 2048 -ub 1024 --cache-ram 1024` | release | 8.56 | 15114.9 | 1797.5 | 14295.6 | 1834 |
| ctx_prod_split | split | `-b 2048 -ub 1024 --cache-ram 1024` | release | 96.61 | 15557.9 | 1797.3 | 9114.6 | 1842 |
| ctx_ckpt1024 | single | `-b 2048 -ub 1024 --cache-ram 1024 --checkpoint-min-step 1024 --ctx-checkpoints 16` | release | 85.11 | 15580.2 | 1794.3 | 9379.1 | 1831 |
| ctx_cache4096 | single | `-b 2048 -ub 1024 --cache-ram 4096` | release | 84.34 | 15573.4 | 3297.0 | 7656.9 | 1831 |
| ctx_sim0_cache4096 | single | `-b 2048 -ub 1024 --cache-ram 4096 --slot-prompt-similarity 0` | release | 82.88 | 15754.6 | 5131.5 | 5791.7 | 1838 |
| ctx_prod_multi | multi | `-b 2048 -ub 1024 --cache-ram 1024` | release | 88.25 | 15754.8 | 1916.9 | 8134.6 | 1828 |
| ctx_prod_multi_ms512 | multi | `-b 2048 -ub 1024 --cache-ram 4096 --slot-prompt-similarity 0 --checkpoint-min-step 512 --ctx-checkpoints 32` | release | 83.58 | 15752.6 | 5307.3 | 5626.2 | 1801 |

Cells: prompt_n recomputed / excess over the logical change / TTFT s (median of the two sequences per size).

| size : scenario | logical new | ctx_control | ctx_prod | ctx_prod_split | ctx_ckpt1024 | ctx_cache4096 | ctx_sim0_cache4096 | ctx_prod_multi | ctx_prod_multi_ms512 |
|---|---|---|---|---|---|---|---|---|---|
| 4k : A_fresh | 0 | 4606 / 4606 / 2.06 | 2542 / 2542 / 1.41 | 2835 / 2835 / 1.77 | 2542 / 2542 / 1.53 | 2542 / 2542 / 1.52 | 2542 / 2542 / 1.46 | 2884 / 2884 / 1.64 | 2555 / 2555 / 1.58 |
| 4k : B_repeat | 0 | 4606 / 4606 / 2.05 | 4 / 4 / 0.30 | 4 / 4 / 0.39 | 4 / 4 / 0.44 | 4 / 4 / 0.40 | 4 / 4 / 0.40 | 4 / 4 / 0.31 | 4 / 4 / 0.46 |
| 4k : C_new_turn | 26 | 4603 / 4577 / 2.05 | 474 / 448 / 0.56 | 50 / 24 / 0.49 | 474 / 448 / 0.65 | 474 / 448 / 0.65 | 474 / 448 / 0.55 | 50 / 24 / 0.40 | 50 / 24 / 0.40 |
| 4k : A_reprime | 0 | 4606 / 4606 / 2.05 | 477 / 477 / 0.56 | 53 / 53 / 0.46 | 477 / 477 / 0.70 | 477 / 477 / 0.68 | 4 / 4 / 0.43 | 53 / 53 / 0.41 | 4 / 4 / 0.48 |
| 4k : D_evidence_changed | 128 | 4593 / 4481 / 2.05 | 464 / 352 / 0.55 | 737 / 609 / 0.84 | 464 / 352 / 0.62 | 464 / 352 / 0.67 | 464 / 352 / 0.62 | 786 / 658 / 0.76 | 377 / 249 / 0.71 |
| 4k : A_reprime2 | 0 | 4606 / 4606 / 2.07 | 477 / 477 / 0.55 | 751 / 751 / 0.80 | 477 / 477 / 0.66 | 477 / 477 / 0.64 | 4 / 4 / 0.42 | 800 / 800 / 0.76 | 4 / 4 / 0.45 |
| 4k : E_permission_changed | 682 | 4606 / 4038 / 2.07 | 1047 / 479 / 0.85 | 1028 / 443 / 0.89 | 1047 / 479 / 1.01 | 1047 / 479 / 0.99 | 762 / 194 / 0.79 | 1028 / 345 / 0.84 | 719 / 36 / 0.94 |
| 4k : A_after_E | 0 | 4606 / 4606 / 2.06 | 1028 / 1028 / 0.82 | 1028 / 1028 / 0.93 | 1028 / 1028 / 0.97 | 1028 / 1028 / 0.92 | 4 / 4 / 0.42 | 1028 / 1028 / 0.83 | 4 / 4 / 0.44 |
| 16k : A_fresh | 0 | 16039 / 16039 / 7.42 | 11910 / 11910 / 5.99 | 12441 / 12441 / 6.41 | 11910 / 11910 / 6.09 | 11910 / 11910 / 6.13 | 11910 / 11910 / 5.99 | 12363 / 12363 / 6.36 | 11946 / 11946 / 6.27 |
| 16k : B_repeat | 0 | 16039 / 16039 / 7.42 | 4 / 4 / 0.32 | 4 / 4 / 0.41 | 4 / 4 / 0.47 | 4 / 4 / 0.41 | 4 / 4 / 0.50 | 4 / 4 / 0.32 | 4 / 4 / 0.53 |
| 16k : C_new_turn | 26 | 16036 / 16010 / 7.42 | 1025 / 999 / 0.89 | 50 / 24 / 0.54 | 1025 / 999 / 1.04 | 1025 / 999 / 0.97 | 1025 / 999 / 0.96 | 50 / 24 / 0.44 | 50 / 24 / 0.43 |
| 16k : A_reprime | 0 | 16039 / 16039 / 7.44 | 1028 / 1028 / 0.87 | 53 / 53 / 0.51 | 1028 / 1028 / 0.98 | 1028 / 1028 / 0.98 | 4 / 4 / 0.53 | 53 / 53 / 0.43 | 4 / 4 / 0.62 |
| 16k : D_evidence_changed | 3287 | 16063 / 12827 / 7.45 | 11934 / 8698 / 5.94 | 12465 / 9213 / 6.32 | 11934 / 8698 / 6.05 | 11934 / 8698 / 6.03 | 11934 / 8698 / 5.96 | 12354 / 9067 / 6.28 | 6067 / 2780 / 3.70 |
| 16k : A_reprime2 | 0 | 16039 / 16039 / 7.44 | 11910 / 11910 / 5.93 | 12441 / 12441 / 6.33 | 11910 / 11910 / 6.05 | 11910 / 11910 / 6.06 | 4 / 4 / 0.50 | 12363 / 12363 / 6.31 | 4 / 4 / 0.57 |
| 16k : E_permission_changed | 12037 | 16039 / 4038 / 7.44 | 12441 / 440 / 6.36 | 12441 / 424 / 6.50 | 12441 / 440 / 6.54 | 12176 / 174 / 6.37 | 11910 / -91 / 6.07 | 12363 / 326 / 6.47 | 12402 / 365 / 6.61 |
| 16k : A_after_E | 0 | 16039 / 16039 / 7.43 | 12441 / 12441 / 6.33 | 12441 / 12441 / 6.56 | 12441 / 12441 / 6.51 | 4 / 4 / 0.63 | 4 / 4 / 0.48 | 12363 / 12363 / 6.49 | 4 / 4 / 0.52 |
| 30k : A_fresh | 0 | 29946 / 29946 / 15.87 | 25817 / 25817 / 14.50 | 26348 / 26348 / 14.94 | 25817 / 25817 / 14.71 | 25817 / 25817 / 14.71 | 25817 / 25817 / 14.50 | 26197 / 26197 / 14.81 | 25780 / 25780 / 14.76 |
| 30k : B_repeat | 0 | 29946 / 29946 / 15.86 | 4 / 4 / 0.33 | 4 / 4 / 0.50 | 4 / 4 / 0.48 | 4 / 4 / 0.45 | 4 / 4 / 0.51 | 4 / 4 / 0.33 | 4 / 4 / 0.52 |
| 30k : C_new_turn | 26 | 29943 / 29917 / 15.85 | 1025 / 999 / 1.06 | 50 / 24 / 0.58 | 1025 / 999 / 1.21 | 1025 / 999 / 1.17 | 1025 / 999 / 1.05 | 50 / 24 / 0.44 | 50 / 24 / 0.56 |
| 30k : A_reprime | 0 | 29946 / 29946 / 15.84 | 1028 / 1028 / 1.04 | 53 / 53 / 0.57 | 1028 / 1028 / 1.15 | 1028 / 1028 / 1.15 | 4 / 4 / 0.61 | 53 / 53 / 0.45 | 4 / 4 / 0.61 |
| 30k : D_evidence_changed | 6673 | 29945 / 23300 / 15.88 | 25816 / 19171 / 14.30 | 26347 / 19686 / 14.68 | 25816 / 19171 / 14.37 | 25816 / 19171 / 14.41 | 25816 / 19171 / 14.44 | 12999 / 6326 / 8.32 | 12999 / 6326 / 8.50 |
| 30k : A_reprime2 | 0 | 29946 / 29946 / 15.89 | 25817 / 25817 / 14.32 | 26348 / 26348 / 14.61 | 25817 / 25817 / 14.42 | 25817 / 25817 / 14.46 | 4 / 4 / 0.59 | 12972 / 12972 / 8.31 | 4 / 4 / 0.60 |
| 30k : E_permission_changed | 25871 | 29946 / 4038 / 15.88 | 26348 / 440 / 14.76 | 26348 / 424 / 14.88 | 26348 / 440 / 14.94 | 26083 / 174 / 14.86 | 26102 / 194 / 14.60 | 26197 / 326 / 14.78 | 26236 / 365 / 14.95 |
| 30k : A_after_E | 0 | 29946 / 29946 / 15.88 | 26348 / 26348 / 14.77 | 26348 / 26348 / 14.89 | 26348 / 26348 / 14.87 | 4 / 4 / 0.78 | 4 / 4 / 0.57 | 26197 / 26197 / 14.82 | 4 / 4 / 0.59 |

Self-built binaries (stock and patched, both without cooperative-matrix shaders: prefill 2.5-3.4x slower than the
release binary; compare token counts across all tables, times only within this table).

| run | layout | extra flags | binary | load s | peak VRAM MiB | peak RSS MiB | min free RAM MiB | A_fresh prefill tok/s (30k) |
|---|---|---|---|---|---|---|---|---|
| ctx_sb_prod | single | `-b 2048 -ub 1024 --cache-ram 1024` | stock self-built | 89.86 | 15669.5 | 1896.0 | 8006.0 | 542 |
| ctx_ux_fine1024 | single | `-b 1024 -ub 1024 --cache-ram 1024 --checkpoint-min-step 512 --ctx-checkpoints 8` | patched self-built | 88.22 | 16079.2 | 2279.9 | 7557.4 | 587 |
| ctx_ux_fine512 | single | `-b 512 -ub 512 --cache-ram 1024 --checkpoint-min-step 256 --ctx-checkpoints 16` | patched self-built | 84.81 | 15741.4 | 2327.5 | 7881.7 | 566 |
| ctx_ux_best_split | split | `-b 1024 -ub 1024 --cache-ram 4096 --slot-prompt-similarity 0 --checkpoint-min-step 1024 --ctx-checkpoints 32` | patched self-built | 83.98 | 15785.9 | 5087.6 | 5238.0 | 547 |
| ctx_ux_best2_split | split | `-b 2048 -ub 2048 --cache-ram 4096 --slot-prompt-similarity 0 --checkpoint-min-step 1024 --ctx-checkpoints 32` | patched self-built | 84.21 | 15152.0 | 6883.6 | 3901.0 | 534 |

Cells: prompt_n recomputed / excess over the logical change / TTFT s (median of the two sequences per size).

| size : scenario | logical new | ctx_sb_prod | ctx_ux_fine1024 | ctx_ux_fine512 | ctx_ux_best_split | ctx_ux_best2_split |
|---|---|---|---|---|---|---|
| 4k : A_fresh | 0 | 2542 / 2542 / 3.50 | 2542 / 2542 / 3.50 | 2542 / 2542 / 2.96 | 2558 / 2558 / 2.36 | 2558 / 2558 / 2.32 |
| 4k : B_repeat | 0 | 4 / 4 / 0.38 | 4 / 4 / 0.42 | 4 / 4 / 0.42 | 4 / 4 / 0.42 | 4 / 4 / 0.44 |
| 4k : C_new_turn | 26 | 474 / 448 / 0.90 | 474 / 448 / 0.87 | 474 / 448 / 0.89 | 50 / 24 / 0.47 | 50 / 24 / 0.47 |
| 4k : A_reprime | 0 | 477 / 477 / 0.86 | 477 / 477 / 0.88 | 477 / 477 / 1.06 | 4 / 4 / 0.45 | 4 / 4 / 0.47 |
| 4k : D_evidence_changed | 128 | 464 / 352 / 0.85 | 464 / 352 / 0.86 | 464 / 352 / 0.88 | 480 / 352 / 0.99 | 480 / 352 / 1.01 |
| 4k : A_reprime2 | 0 | 477 / 477 / 0.85 | 477 / 477 / 0.87 | 477 / 477 / 0.88 | 4 / 4 / 0.44 | 4 / 4 / 0.46 |
| 4k : E_permission_changed | 584 | 1047 / 479 / 1.79 | 1043 / 475 / 1.79 | 1022 / 454 / 1.51 | 1043 / 459 / 1.44 | 1280 / 696 / 1.60 |
| 4k : A_after_E | 0 | 1028 / 1028 / 1.36 | 1024 / 1024 / 1.36 | 1022 / 1022 / 1.47 | 4 / 4 / 0.42 | 4 / 4 / 0.46 |
| 16k : A_fresh | 0 | 11910 / 11910 / 14.97 | 13975 / 13975 / 16.72 | 13975 / 13975 / 18.44 | 11926 / 11926 / 14.98 | 11926 / 11926 / 15.26 |
| 16k : B_repeat | 0 | 4 / 4 / 0.48 | 4 / 4 / 0.47 | 4 / 4 / 0.42 | 4 / 4 / 0.50 | 4 / 4 / 0.57 |
| 16k : C_new_turn | 26 | 1025 / 999 / 2.13 | 1021 / 995 / 2.10 | 643 / 617 / 1.68 | 50 / 24 / 0.56 | 50 / 24 / 0.56 |
| 16k : A_reprime | 0 | 1028 / 1028 / 2.09 | 1024 / 1024 / 2.12 | 515 / 515 / 1.32 | 4 / 4 / 0.54 | 4 / 4 / 0.64 |
| 16k : D_evidence_changed | 3252 | 11934 / 8698 / 14.91 | 3742 / 506 / 6.23 | 3486 / 250 / 6.27 | 11950 / 8698 / 15.09 | 3758 / 506 / 6.53 |
| 16k : A_reprime2 | 0 | 11910 / 11910 / 14.96 | 3718 / 3718 / 6.27 | 3462 / 3462 / 6.31 | 4 / 4 / 0.57 | 4 / 4 / 0.61 |
| 16k : E_permission_changed | 12017 | 12441 / 440 / 15.67 | 16039 / 4038 / 18.36 | 16039 / 4038 / 20.13 | 12437 / 420 / 15.63 | 12713 / 696 / 16.00 |
| 16k : A_after_E | 0 | 12441 / 12441 / 15.68 | 16039 / 16039 / 18.40 | 16039 / 16039 / 20.19 | 4 / 4 / 0.51 | 4 / 4 / 0.56 |
| 30k : A_fresh | 0 | 25817 / 25817 / 48.24 | 29946 / 29946 / 51.63 | 29946 / 29946 / 53.32 | 25833 / 25833 / 47.71 | 25833 / 25833 / 48.86 |
| 30k : B_repeat | 0 | 4 / 4 / 0.45 | 4 / 4 / 0.45 | 4 / 4 / 0.45 | 4 / 4 / 0.52 | 4 / 4 / 0.68 |
| 30k : C_new_turn | 26 | 1025 / 999 / 3.46 | 1238 / 1212 / 4.12 | 516 / 490 / 1.98 | 50 / 24 / 0.65 | 50 / 24 / 0.64 |
| 30k : A_reprime | 0 | 1028 / 1028 / 3.44 | 1027 / 1027 / 3.72 | 513 / 513 / 1.98 | 4 / 4 / 0.63 | 4 / 4 / 0.74 |
| 30k : D_evidence_changed | 6661 | 25816 / 19171 / 47.55 | 29945 / 23300 / 51.23 | 6872 / 227 / 18.99 | 25832 / 19171 / 47.53 | 7400 / 739 / 20.48 |
| 30k : A_reprime2 | 0 | 25817 / 25817 / 47.53 | 29946 / 29946 / 51.31 | 6873 / 6873 / 18.92 | 4 / 4 / 0.60 | 4 / 4 / 0.77 |
| 30k : E_permission_changed | 25924 | 26348 / 440 / 48.23 | 29946 / 4038 / 51.59 | 29946 / 4038 / 53.24 | 26364 / 439 / 48.00 | 27407 / 1483 / 50.08 |
| 30k : A_after_E | 0 | 26348 / 26348 / 48.15 | 29946 / 29946 / 51.46 | 29946 / 29946 / 53.19 | 4 / 4 / 0.60 | 4 / 4 / 0.73 |


## 2. Repeated-context prefill latency

Prefill rate of the release Vulkan binary on this card: 2,100 prompt tok/s at 16k, 1,830-1,920 tok/s at 30k
(attention cost grows with position), 2,350 tok/s for a 4.6k prompt. A full 30k re-processing is therefore ~14-16 s,
a 16k one ~6-7 s, and every 1,000 tokens of excess recompute cost ~0.5 s of TTFT. The levers in section 1 translate
directly: C new turn 1.06 -> 0.58 s TTFT at 30k (split layout), A after D/E 14.3 -> 0.6 s (always-save cache),
D evidence change 14.0 -> ~3.5-4 s expected on the release binary with ubatch-granular checkpoints (patched build:
19,171 -> 227 excess tokens; the patched binary itself runs at 550-590 prompt tok/s because it was compiled without
the cooperative-matrix / integer-dot shaders, see below).

Two measurement caveats, both recorded in the evidence:

- Self-built binaries (stock and patched, `D:\uri-model-lab\build\*`) were compiled with the Android NDK glslc
  (shaderc 2022.3), which lacks `GL_KHR_cooperative_matrix`, `GL_EXT_integer_dot_product` and `GL_EXT_bfloat16`
  (`rsseq_cfg.log`). Their prefill is 2.5-3.4x slower than the release binary (542 vs 1,834 prompt tok/s at 30k)
  and decode ~20 tok/s in the first call; token counts (`prompt_n`, `cache_n`) are byte-for-byte the same as the
  release binary in all 48 rows of ctx_sb_prod vs ctx_prod, so the patched-build results are read as token counts and
  as time relative to the equally built stock binary. A rebuild with a current Vulkan SDK glslc is required before any
  patched binary is timed against production (no newer glslc exists on this machine; downloading one was left to the
  user).
- The runs between 18:35 and 20:09 carry ~100-140 ms of extra client-side latency per request from the first version
  of the post-crash telemetry sampler (two PowerShell processes spawned per 3 s sample; measured as TTFT minus server
  `prompt_ms` on the 4-token B_repeat rows: 259-265 ms before, 357-403 ms during). Server-side `prompt_ms` and all
  token counts are unaffected; TTFT/total comparisons across that boundary are read with that offset. The sampler was
  replaced by a single long-lived counter reader from 20:12 on.
- Loads after the reboot are cold HDD loads (83-97 s) because the OS file cache no longer holds the 13.7 GB model;
  the pre-crash warm loads were 6.3-8.6 s (section 7).

## 3. Correctness and equivalence

### 3.1 Suite-level correctness (run_bench.py, real Core seams, 221 cases)

| run | ctx | flags | C | D | DG | F | H | L | O | P | S | D p50 |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| ue_base (qualification reproduced) | 32k | production | 1.000 | 0.861 | 0.861 | 1.000 | 1.000 | 0.933 | 1.000 | 12/12 | 1.000 | 2.585 s |
| ue_ckpt1024 | 32k | + `--checkpoint-min-step 1024 --ctx-checkpoints 16` | 1.000 | 0.861 | 0.861 | 1.000 | 1.000 | 0.933 | 1.000 | 12/12 | 1.000 | 2.519 s |
| ue_base16k (post-crash) | 16k | production, L sizes 4k/12k | 1.000 | 0.861 | 0.861 | 1.000 | 1.000 | 0.800 (1 common L case) | 1.000 | 12/12 | 1.000 | 2.723 s (+0.14 s: client-side telemetry confound, section 2) |
| ue_mtp3_16k (post-crash) | 16k | production + `draft-mtp` n_max 3 | 1.000 | 0.861 | 0.861 | 1.000 | 1.000 | 0.900 (2 common L cases) | 1.000 | 12/12 | 1.000 | 2.271 s |
| ue_base16k_rep (post-crash, fixed sampler) | 16k | production, L sizes 4k/12k | 1.000 | 0.861 | 0.861 | 1.000 | 1.000 | 0.900 | 1.000 | 12/12 | 1.000 | 2.518 s |

ue_base16k_rep vs ue_base16k: 220/220 outputs identical, every score identical. Three fresh production sessions
(ue_base at 32k, ue_base16k, ue_base16k_rep) therefore agree byte-for-byte on every case; the within-session
divergence of section 3.2 does not appear across fresh sessions because each case is processed with the same layout.
The D p50 difference (2.72 vs 2.52 s) is the client-side sampler confound of section 2; 2.52 s matches the 32k
pre-crash baseline (2.585 s).

ue_mtp3_16k vs ue_base16k (`diff_ue_mtp3_16k.json`, 220 common cases): every suite score identical, zero
score-changing cases, D p50 2.72 -> 2.27 s, DG 2.72 -> 2.10 s, H 0.87 -> 0.69 s, C 1.15 -> 0.84 s. Stored outputs
differ in 132/220 cases (D 57/72, DG 58/72, H 10/22, C 5/14, O 2/4; F, P, S, L identical): the differences are
free-text wording in `goal`/`reason`/answer prose, never the scored decision fields. This is the expected signature
of greedy decoding under speculative verification on a backend whose numerics are layout-dependent (section 3.2):
score-equivalent, not byte-equivalent.

ue_base16k vs ue_base: 219 common cases, every suite score identical, outputs identical 219/219 (`diff_outputs.py`).

ue_base vs ue_ckpt1024: every suite score identical and 221/221 stored outputs identical (`diff_ue_ckpt1024.json`;
D/DG are compared on the first 600 characters the harness stores). Two *fresh* server sessions therefore produce the
same greedy output for every case, which is consistent with the layout finding below: a fresh session processes each
case with the same ubatch layout.

### 3.2 The "188 vs 192 tokens" determinism anomaly

Stored evidence (`spec/*.json`, nine fresh sessions): the first greedy `decision_contract` call of a session gave the
same 188-token JSON (sha `24d00b2474`) in 9/9 sessions; the second occurrence in the same session gave a 192-token
text (sha `56e91a5c63`) in 5/5 plain runs and a 198-token text in the 4 runs with accepted drafts. Prompt bytes,
seed (7), temperature (0), top-k/top-p/min-p (server defaults 20 / 0.95 / 0.05, irrelevant at temperature 0),
grammar (same JSON schema) and `cache_n` (0 both times) were identical. The only difference is inside the free-text
`reason` string ("...that fully satisfy the capability's requirements." vs "...that fit the 'draft_institutional_order'
capability."); the JSON structure and every other field are identical.

determinism_probe.py (3 fresh servers x 5 calls, `-lv 4` trace):

| config | 5 calls (stream, non-stream x2, after 4 filler tasks x2) |
|---|---|
| production (`--cache-ram 1024`, checkpoints on) | 5/5 = 188-token text |
| `--cache-ram 0` | 5/5 = 188-token text |
| `--cache-ram 0 --ctx-checkpoints 0` | 5/5 = a third text, 198 tokens (`6e3b63a840`), differs in `goal` and `reason` |

The trace shows why: with checkpoints enabled the prompt is processed in ubatches split at the checkpoint positions
(message boundaries: `cached n_tokens = 19`, `= 231`, then the rest), without checkpoints it runs in plain
1024-token ubatches. The rep1 case in bench_spec resumed from a *restored* checkpoint (`n_past = 54`), a third layout.
Different ubatch layouts change the floating-point accumulation order of the GDN chunked recurrence and the MoE
kernels; a near-tie token flips and the greedy path diverges from there. The probe did not reproduce the 192-token
text because it ran only 4 of the 8 bench_spec tasks between occurrences (different checkpoint state).

A second, smaller effect is visible in ctx_control (`--cache-ram 0 --ctx-checkpoints 0`, full recompute every call,
identical layout): the same A prompt gave a different 48-token output in 6 of 30 occurrences, mostly at 16k-30k
(e.g. 30k rep1 B_repeat differs from A_fresh one call earlier). That is same-layout, run-to-run variation.

determinism_probe2.py (after the second crash; `determinism_probe2.json`, server trace `-lv 4`):

| part | setting | result |
|---|---|---|
| replay | production flags, the exact bench_spec order (8 tasks x 2 reps) | rep0 = 188-token text `24d00b2474`, rep1 = 192-token text `56e91a5c63`: **both stored texts reproduced exactly**. First divergent token is #178: rep0 chose " fully" with a top-2 margin of 0.56 nat; rep1 chose " fit" with a margin of **0.0019 nat** (" fit" -1.1951 vs " fully" -1.1970). The trace shows rep1's prompt processed with ubatch boundaries at 2,048 / 2,766 / 3,051 / 4,075 (checkpoints at the Core system-prompt boundary and near the end) while rep0's was split at 19 / 231 / ... (the boundaries of the previous task's checkpoints). |
| layout | no cache, no checkpoints, `-ub 1024`, 6 calls (3 before and 3 after a 16k filler) | 6/6 = 198-token text `6e3b63a840` |
| layout | same, `-ub 512`, 3 calls | call 0 = 192-token text, calls 1-2 = 198-token text |
| layout | same, `-ub 256`, 3 calls | call 0 = 198-token text, calls 1-2 = 188-token text |

So there are two effects, both at near-tie tokens (the three texts differ only in "institutional office order" vs
"office order" at token 9, margin 0.05-0.11 nat, and "fully satisfy" / "fit" / "matches" at token 176-178, margin
0.002-0.10 nat): (1) a systematic dependence on the ubatch layout (checkpoint boundaries, `-ub`), and (2) run-to-run
jitter inside one layout (first call vs later calls at `-ub 512` and `-ub 256`), i.e. the Vulkan kernels are not
bit-reproducible. Neither is a cache or state-contamination bug: `cache_n` was 0 in every call, the restored-checkpoint
runs reproduce their own outputs, and all three texts are the same decision (same capability, mode and action; only
the free-text `goal`/`reason` wording differs). Classification of the anomaly: **nondeterministic GPU numerics at a
near-tie token, with the ubatch layout as the dominant systematic factor**; not whitespace, not tokenization, not
speculative decoding, not a configuration mismatch.

Consequence for the research: "byte-identical output" is not a usable equivalence criterion on this runtime, not
because reuse is unsafe but because greedy decoding on Vulkan flips near-tie tokens whenever the prompt layout
changes. Equivalence is judged on suite scores (3.1) and on the divergence rate of a candidate against the
baseline's own repeat variance. Checkpoint reuse itself is exact in the sense that matters: the restored state is
the serialized state of the same computation, and the restored path reproduces its own output (B_repeat and
A_reprime rows are identical to A_fresh in every production run where the restore happened).

## 4. VRAM / RAM stability

| configuration | peak dedicated VRAM | server RSS | min free system RAM | note |
|---|---|---|---|---|
| production, 32k, vision, idle after load | 15,115 MiB | 0.8-1.8 GB (grows with `--cache-ram`) | ~14.3 GB | ctx_prod / ctx_control |
| production + MTP draft (16k + vision, or 32k without vision) | 15,820 MiB | 3.3 GB | 12.8 GB | mtp3_16k_vision |
| `-ctk f16 -ctv f16` | 15,889 MiB (+266 MiB at 32k) | - | - | kv_f16 |
| `-np 3 -kvu` | - | +4 GB RAM | 10,175 MiB | np3_kvu; rejected |
| ngram-mod stock (hung) | 15,601 MiB | 1.8 GB | 14.4 GB | last sample before the hang |
| production + MTP draft n_max 2, 32k + vision (fit test) | 15,861 MiB | 3.5 GB | 7.3 GB | mtp2_32k_vision; the post-reboot desktop holds ~1.0 GB of the 16 GB |
| production + MTP draft n_max 3 on the URI session, 16k | 15,974 MiB | 3.1 GB | 7.4 GB | uri_mtp3_16k |
| `--cache-ram 4096` | 15,573 MiB | 3.3 GB | 7.7 GB | ctx_cache4096 |
| `--cache-ram 4096 --slot-prompt-similarity 0` (every state saved) | 15,755 MiB | 5.1 GB | 5.8 GB | ctx_sim0_cache4096 |
| same + multi-part evidence + `--checkpoint-min-step 512 --ctx-checkpoints 32` | 15,753 MiB | 5.3 GB | 5.6 GB | ctx_prod_multi_ms512 (stock flags, recommended shape) |
| patched build, 32 ubatch checkpoints + 4 GiB cache | 15,152 MiB | 6.9 GB | 3.9 GB | ctx_ux_best2_split; over the RAM budget for this machine |

RAM is the binding constraint for the reuse levers, not VRAM: checkpoints (62.8 MiB of recurrent state each) and
cached prompt states (544-691 MiB per 16k-30k state) live in host RAM. The always-save cache with 32 checkpoints
costs ~3.5 GB over production on a 24 GB machine that already runs the desktop, URI Core and the Flutter UI; a 2 GiB
cache with 16 checkpoints is the realistic ceiling and still covers two 30k states plus a full 32k checkpoint ladder
at 2,048 spacing. No run of the day hit a Vulkan allocation error; no run exceeded 16 GB dedicated.

Headroom at 32k + vision was ~770 MiB before the reboot and ~100-200 MiB after it (desktop VRAM use grew from
0.46 to ~1.0 GB). MTP with n_max 3 fits at 16k-24k + vision or 32k without vision; 32k + vision fits n_max 2. A second resident sequence (`-np 2`) would add ~63 MiB of recurrent state plus KV; `n_rs_seq` snapshots add
63 MiB each.

## 5. Normal URI decision-turn latency (bench_uri.py, 32k, vision loaded, production flags unless noted)

Decision turn = 2,763-token Core system prompt + ~1,300-1,500-token request (grammar on, canonical JSON). The server
reuses the system prefix every turn (`cache_n` 2,766-3,047) even when interpreter/answer prompts run in between.

| variant | dec cache_n | dec prompt_n | dec prompt ms | dec total p50 | 16k follow-up ms (cache_n) | 29k follow-up ms | gen tok/s | min free RAM |
|---|---|---|---|---|---|---|---|---|
| base_prod | 2,766 | 1,504 | 722 | 2.49 s | 611 (16,933) | n/a | 101.5 | 12,710 MiB |
| ckpt_fine (`--checkpoint-min-step 1024 --ctx-checkpoints 16`, canonical JSON) | 3,047 | 1,024 | 485 | 2.32 s | 615 (16,933) | 759 (30,897) | 101.4 | 14,044 |
| `--cache-ram 0` | 0 | 4,051 | 1,677 | 3.22 s | 611 | 759 | 101.5 | 14,348 |
| `--ctx-checkpoints 0` | 0 | 4,070 | 1,559 | 3.53 s | 8,195 (0) | 16,901 (0) | 101.6 | 14,027 |
| `-np 3 -kvu` | 3,047 | 1,024 | 480 | 2.31 s | 610 | 828 | 87.2 | 10,175 |
| `-b 4096 -ub 2048` | 2,766 | 1,304 | 587 | 2.32 s | 1,174 (15,909) | 1,455 (29,873) | 101.6 | 14,092 |
| `--n-cpu-moe 4` | - | - | - | 3.36 s | - | - | 53 | - |
| `-ctk f16 -ctv f16` | - | - | - | 2.26 s | - | - | 103.6 | - |
| no grammar | - | - | - | 2.29 s | - | - | - | - |
| uri_base_16k: 16k context, canonical JSON, no vision/long cases (post-crash run) | 3,047 | 1,024 | 500 | 2.51 s | - | - | 96.3 | 8,920 |
| uri_mtp3_16k: same + `draft-mtp` n_max 3 | 3,047 | 1,024 | 550 | **2.05 s** | - | - | **147.3** | 7,423 |

Self-built binaries on the same canonical session (32k, no vision/long/decode cases, fixed sampler): stock
self-built (sb_prod_canon) decision 2.769 s / 94.5 tok/s, patched self-built (ux_prod_canon) 2.764 s / 94.4 tok/s,
identical `prompt_n`/`cache_n` in every phase. The research patches are neutral on the normal decision turn under
production flags (no fine checkpoints are created when `--checkpoint-min-step` is left at 8,192). The self-built
decode speed is within 2% of the release binary; only their prefill is slower (section 2).

uri_mtp3_16k vs uri_base_16k on the real URI session (12 proposer decisions, 8 interpreter calls, 4 answers, 6
trivial turns, 0 errors each): decision p50 2.51 -> 2.05 s (-18%), repeat decision 2.40 -> 1.95 s, interpreter
0.76 -> 0.73 s, answer 1.36 -> 1.20 s, trivial unchanged (0.63 s, fixed-cost bound); prompt time +50 ms per decision
(the draft layer prefills too); peak VRAM 15,515 -> 15,974 MiB, server RSS 1.86 -> 3.14 GB. Context size itself is
not a lever: the 16k and 32k production runs have the same decision latency (2.51 vs 2.49 s).

Per-request fixed overhead (overhead.py): Jinja render 1.7-2.0 ms, tokenizing the 4,079-token decision prompt
6.6 ms, wall minus server time 2.6-9.9 ms; the floor is one 40-block graph pass of 43-45 ms for a 4-token batch.
Grammar costs nothing measurable on the decision prompt (9.89 vs 9.96 ms/token).

Streaming overhead (stream_overhead.py, post-crash, fixed sampler; same 27-token request, 19 cached, 2 generated
tokens, 6 calls each): non-streaming wall 0.161 s (server prompt 146 ms + decode 14 ms + 2.7 ms unaccounted) vs
streaming TTFT **0.386 s** and total 0.40 s. The SSE path as used by the lab client costs ~0.22 s per request on top
of the server's own time; the bench_uri "trivial" turn (0.47-0.63 s) is therefore mostly this overhead, and a
decision turn carries the same ~0.2 s.

stream_probe2.py (same production server, a 27-token / 2-token request, 6 calls per path, fixed sampler) locates it:

| path | time to first content token (p50) |
|---|---|
| raw TCP socket, streamed SSE (first byte 23 ms, headers 23 ms) | **74 ms** (server prompt 56 ms + first decode) |
| one persistent `httpx.Client`, streamed | 78 ms |
| lab client (`httpx.stream`, a new client per call, `iter_lines`) | 301 ms |
| `httpx.post` non-streaming, a new client per call | 308 ms |

The server's SSE delivery adds ~4 ms over the raw non-streaming floor; the ~0.22 s is the Python client constructing
a new `httpx` client (and its TLS context) per request. Consequences: (1) every TTFT/total figure in this report
measured through the lab client includes ~0.22-0.23 s that the server does not spend; server-side `prompt_ms` and
token counts are exact; (2) this is a URI-side check, not a runtime lever: URI's Brain provider must reuse one
HTTP client per server (if it does not, a decision turn loses ~0.2 s of its 2.3-2.5 s to connection setup).
Prompt eval cost vs batch size on the production server:
19 new tokens 138 ms, 103 tokens 188 ms, 419 tokens 262 ms, 1,955 tokens 796 ms (0.41 ms/token), i.e. ~130 ms of
fixed per-request prompt cost plus ~0.4 ms per new token.

## 6. MTP and speculative decoding (lowest priority; measured because the GPU time was cheap)

The qualified GGUF carries no MTP tensors (0 of 733). An MTP draft was exported from the HF checkpoint
(`mtp-qwen36-35b-a3b-Q4_K_M.gguf`, 1.26 GB; `-otd token_embd.weight=CPU`).

| variant | ctx / vision | median gen speedup (rep0, first sight of each prompt) | decision_contract tok/s | outputs identical to plain on rep0 |
|---|---|---|---|---|
| draft-mtp n_max 3 | 16k + vision | 1.62x | 99 -> 152 (acceptance 136/153) | 6/8 (office_draft, conversational differ) |
| draft-mtp n_max 3 | 32k, no vision | 1.62x | 99 -> 155 | 6/8 |
| draft-mtp n_max 2 | 32k, no vision | 1.48x | 99 -> 140 | 6/8 |
| ngram-mod (n_match 24, n_min 48, n_max 64) | 32k + vision | 1.64x median but only quote_back 3.3x / code_patch 1.6x / rewrite 1.2x; everything else 0.98-1.01x | 97 (no drafts) | 8/8 |
| ngram-simple (n 12, m 8) | 32k + vision | 0.99x, no drafts on any task | 98 | 8/8 |
| ngram-simple (n 12, m 8) on the real URI session (uri_ngram_simple, post-crash) | 32k, no vision/long cases | no draft on any of 42 requests; decision 2.27 s / 99.8 tok/s = plain | 100 | n/a |
| ngram-map-k (n 8) | 32k + vision | 0.99x; drafts on 2 tasks, 3/8 and 4/8 accepted, those tasks 0.87x | 86 | 8/8 |
| draft-mtp n_max 3 on the real URI session (uri_mtp3_16k) | 16k, projector loaded, no vision cases | decision gen 96 -> 147 tok/s, decision turn 2.51 -> 2.05 s | see section 5 | correctness: section 3.1 (ue_mtp3_16k) |
| draft-mtp n_max 2 (fit test, post-crash) | 32k + vision | median 1.45x (149 tok/s); 809/948 drafts accepted | 99 -> 141 | peak VRAM 15,861 MiB, RSS 3.46 GB, 0 errors |
| draft-mtp n_max 3 (fit test) | 24k + vision | median 1.61x (165 tok/s); 910/1,116 accepted | 99 -> 156 | 15,787 MiB, RSS 3.43 GB |
| draft-mtp n_max 2 (fit test) | 16k + vision | median 1.45x (149 tok/s); 809/948 accepted | 99 -> 141 | 15,858 MiB, RSS 3.15 GB |
| draft-mtp n_max 4 (fit test) | 16k + vision | median 1.69x (173 tok/s); 963/1,276 accepted | 99 -> 166 | 15,766 MiB, RSS 3.50 GB |

MTP fit: every tested combination up to 32k + vision + n_max 2 and 24k + vision + n_max 3 loaded and ran all 8
tasks without error at a peak of 15.8-15.9 GB dedicated VRAM on the 16 GB card (the post-reboot desktop itself holds
~0.9-1.1 GB, so the headroom is ~100-200 MiB). n_max 4 at 16k gives the best decode (173 tok/s median, acceptance
0.75) but the 32k + vision production shape only fits n_max 2 (1.45x). These are single-sequence fit tests
(`--repeats 1`); the decode gain is bounded by the first-sight acceptance rate, 0.75-0.85 for structured outputs and
~0.5 for free prose.

n-gram rep1 numbers (second sight of a prompt) are NOT evidence of URI acceleration: the server-wide n-gram pool had
memorised the previous answer (decision_contract 128/128 drafts accepted, 144 tok/s). URI's decision prompts are
first-sight prompts. The stock ngram-mod configuration also hung the server for 18 minutes on a proposer prompt
(`hang_ngram_mod_stock_b11425.log`) and a second ngram-mod run was in progress at the first PC freeze.

**n-gram speculation: REJECTED / SUPERSEDED (closed 2026-10-06, final milestone).** ngram-simple produced no draft
on any URI request (spec run and the 42-request URI session); ngram-map-k drafted on 2 of 8 tasks with 3/8 and 4/8
accepted and ran those tasks 13% slower; ngram-mod's first-sight speed equals the baseline on every URI-shaped task
(0.98-1.01x) and its repeat gains come from answer memorisation, while its stock implementation hung the server.
MTP delivers the genuine, first-sight gain (1.45-1.69x) with score-equivalent outputs. The two blocked queue entries
(`uri_ngram_mod16`, `ux_ngram_mod8`) are closed without further GPU time; the `n_rs_seq` research patch for n-gram
drafters is retained as historical evidence only.

MTP cost: TTFT +0.05-0.2 s (the draft layer also prefills), +1.33 GB VRAM, +1.2 GB RSS; decision_contract end-to-end
3.92 -> 3.41 s (-13%) on the long spec prompt. On URI's real decision turn (prefill 0.5-0.7 s, ~100-175 generated
tokens) the generation share is ~1.0-1.7 s, so the realistic MTP gain is ~0.4-0.6 s per decision.

## 7. Raw generation and storage

Decode is 99-104 tok/s in every configuration without speculation. Per-token weight traffic is ~1.9 GiB
(dense projections 0.98 GiB + head 0.39 GiB + shared experts 0.10 GiB + 8 of 256 routed experts x 40 blocks 0.34 GiB);
at 576 GB/s that is ~3.5 ms of a measured 10.1 ms token, so decode is launch/synchronisation-bound, not
bandwidth-bound. Experts are only ~18% of per-token bytes.

Cold / warm load (coldload.py; OS standby list evicted by reading 30 GiB of other files first):

| | HDD D: | NVMe C: (copy, hashes verified identical) |
|---|---|---|
| sha256 of the 13.68 GB GGUF, cold | 90.5 s | 17.1 s |
| llama-server to /health, cold (model + projector, 32k, vision) | 85.6 s | 16.0 s |
| llama-server warm | 6.4 s | 6.4 s |
| sha256 warm | 9.8 s | 9.9 s |

Raw unbuffered sequential read: HDD 120 MB/s, NVMe 1,964 MB/s. Both warm numbers come from the OS file cache.
Hash verification is CPU-bound once cached (~1.4 GB/s).

Expert activation skew (llama-imatrix, URI corpus of 207 real prompts, ~400k tokens): the 64 most-used experts of a
block serve 70.2% of routed assignments, 128 serve 90.3%, mean Gini 0.61; a half-size hot cache would still miss
~10% per assignment (~55% of tokens miss at least one of their 8 experts per block). Moot on this card: all experts
are resident. `--n-cpu-moe 4` (smallest possible offload) halves decode (101 -> 53 tok/s): the Strata CPU-expert-pool
class is strictly negative on URI's hardware.

## 8. Strata analysis and the Qwen3.6 mapping

### 8.1 Strata (github.com/Niko1221/Strata, MIT; clone `D:\uri-model-lab\strata_research\strata`, 852 files, ~98k lines)

Strata targets Qwen3.8-Flash-Next (48 layers, 24,576 experts, a 28.8 GB per-layer n-gram embedding table, one MTP
layer); its kernel geometry is compiled in (`expert_source.hpp`: "A different n_embd or a different expert width is
REFUSED"). Its headline problem is "a 125B MoE on 12 GB": make non-resident experts fast. URI's problem is the
opposite: the whole model is resident, and the costs are per-turn prefill, generation length and fixed per-request
overhead. Technique-by-technique classification (A = already in llama.cpp, B = tune/port a concept, C = needs a new
backend, D = not applicable to Qwen3.6, E = nothing to gain on this model, F = measured negative on this hardware):

| technique | Strata source | class for URI | evidence |
|---|---|---|---|
| expert placement / VRAM expert tier | `expert_cache.hpp/.cpp` | E | 10.8 GiB of experts fully resident |
| hot-expert adaptivity | `expert_cache.cpp` | E | same |
| GPU/CPU expert concurrency | `kernels/cpu/pool.hpp`, doorbell | F | `--n-cpu-moe 4`: 53 tok/s; `--fit` Q4_K_M: 41 tok/s |
| expert streaming during prefill | `prefill/prefill.hpp` | E | no non-resident experts |
| RAM pinning / pinned arena | `pinned.cu` | F | 24 GB RAM with a >= 10 GB desktop floor |
| SSD-backed PLE table | `ple_reader.hpp`, `direct_file.cpp` | D | PLE is a Qwen3.8 feature; Qwen3.6 has none |
| prefill chunking | `prefill.hpp` | B (already) | `-b/-ub` + chunked GDN kernel (`delta-net-base.cpp`, CS=64) |
| prompt kernels (CUDA/HIP int8, hipBLASLt) | `kernels/cuda/*`, `AMD_HIP_PERFORMANCE.md` | C | URI runs Vulkan (ROCm reports no device on this driver); int8 coopmat already landed in llama.cpp Vulkan (#27952) |
| MTP / self-speculative decoding | `mtp.hpp`, `verify.hpp` | B (already) | `--spec-type draft-mtp` + `n_rs_seq` rollback; section 6 |
| prompt-lookup drafter + cost-aware policy | `suffix_drafter.hpp`, `draft_policy.cpp` | B | llama.cpp has `ngram-*`; the cost-aware policy is what it lacks; stock ngram-mod hangs on this model |
| KV-cache management (host-authoritative, paged) | `kv_stream.hpp` | E | 10 full-attention blocks: 10.6 KiB/token, 340 MiB at 32k |
| recurrent-state handling | `session.hpp`, `verify.hpp` | B (already) | `n_rs_seq` snapshot ring (63 MiB each) |
| prefix / session reuse ("conversation cache") | `docs/DETAILS.md` | A | `--ctx-checkpoints` + `--cache-ram`; section 1 |
| scheduling (`--batch N`) | `generate.cpp`, `BATCHING.md` | F | `-np 3`: -14% decode, +4 GB RAM |
| Vulkan vs CUDA | none (CUDA, HIP, SYCL only) | C | a port is a new backend, not an adaptation |
| memory planning | `strata-device` | B (concept) | URI pins its budget in `local_brain.json` |
| quantization assumptions (own Q2_0, rotated 4-bit KV) | `DETAILS.md` | E | URI's artifact is pinned by hash; requantizing re-opens qualification |

### 8.2 Qwen3.6-35B-A3B as URI runs it (GGUF `general.architecture = qwen35moe`, 733 tensors, 12.73 GiB)

- 40 blocks, `full_attention_interval 4`: blocks 3,7,...,39 are gated full attention (10), the other 30 are Gated
  DeltaNet. Full attention: 16 Q heads x 256, 2 KV heads x 256 (GQA 8), partial RoPE 64 dims, M-RoPE [11,11,10].
- DeltaNet: `ssm_state_size 128`, 16 K heads, 32 V heads, `ssm_inner_size 4096`, conv kernel 4. Recurrent state per
  sequence 62.8 MiB (F32); with `n_rs_seq = n` snapshots the recurrent buffer is x(1+n).
- MoE on every block: 256 routed experts (IQ2_S gate/up, IQ3_S down), top-8, one shared expert (Q6_K). Routed experts
  are 10.78 GiB (84.7% of the file); attention/DeltaNet projections 1.0 GiB; embedding + head 0.78 GiB.
- KV per token (10 blocks, q8_0): 10.6 KiB -> 43 MiB at 4k, 170 MiB at 16k, 340 MiB at 32k.
- Context checkpoint (recurrent state + KV up to the position): ~90 MiB at a 2.8k system prefix, ~240 MiB at 16k;
  prompt-cache entries of 125-690 MiB were evicted at the 1,024 MiB limit in the 16k/30k runs (section 1).
- MTP: the HF config has `mtp_num_hidden_layers: 1` (19 `mtp.*` tensors in shards 25-26); the unsloth GGUFs carry none.
- Vision: `mmproj-F16.gguf` 0.84 GiB, `qwen3vl_merger`, 27 ViT blocks.
- Vulkan: every Qwen3.6 op has a b11425 Vulkan kernel (`GATED_DELTA_NET`, `SSM_CONV`, `SOLVE_TRI`, `CUMSUM`, `TRI`), so
  `-ngl 999` keeps the whole graph on the GPU; "graphs reused" counters confirm graph reuse across decode steps.

### 8.3 Builds

Exact baseline rebuilt from source: commit `e117148` (= tag b11425), MSVC 19.51.36260, Vulkan, `D:\uri-model-lab\build\stock`
(stock) and `D:\uri-model-lab\build\rsseq` (URI research patches, `model_lab/uri_engine/patches/uri-ext-b11425.diff`:
(1) n-gram speculative types use the bounded `n_rs_seq` recurrent rollback instead of full-state checkpoints per
draft round; (2) `--checkpoint-min-step` smaller than the ubatch creates mid-prompt checkpoints at batch granularity).
The missing `spirv/unified1/spirv.hpp` include was supplied via `-DCMAKE_PREFIX_PATH=D:/uri-model-lab/vk/spirv-headers-install`.
Both binaries report `version: 0.5.0-dev (build 1, commit e117148)`.

## 9. Crash and recovery record (2026-10-06)

Two machine interruptions, both recorded by Windows as `Kernel-Power 41` with `BugcheckCode 0`, no WHEA, no
display-driver TDR (4101), no minidump, no reliability record other than the unexpected-shutdown entry.

Classification (corrected 2026-10-06 evening, `crash_record_correction_20261006.json`):

- **First interruption (12:06-13:30): CAUSE UNKNOWN.** The OS evidence is an unexpected power-loss/hang signature
  with nothing further; the running ngram-mod experiment is a correlation only, and Vulkan/GPU causation is not
  inferred from it.
- **Second interruption (14:25-18:18): external electrical power outage** (cause supplied by the user after the
  session; OS-observed evidence: unexpected power loss, truncated log and lock-file writes). It is NOT evidence of
  llama.cpp or Vulkan instability and is excluded from the runtime stability assessment. Only the first,
  unexplained freeze remains relevant to stability (section 12 of the freeze record covers the final soak).

| | first freeze | second freeze |
|---|---|---|
| freeze window | 12:06:24 - 13:30:30 (restart 13:30:30) | 14:25:13 - 18:18:12 (restart 18:18:12) |
| running experiment | `uri_ngram_mod16` (stock ngram-mod speculation, 29/45 requests done, ~15.6 GB VRAM) | `ctx_prod_split` (production flags, no speculation), server ~0.5 s old, model load not yet logged |
| last write | server log line at 12:06:24 | server log truncated mid-line at 14:25:12.9; `queue_runner.lock` holds 4 NUL bytes (data never reached disk) |
| telemetry | none inside the run (old harness wrote peaks only at the end) | none (sampler had not started) |
| record | `crash_recovery_20261006.json` | `crash_recovery_20261006_second.json` |

For the first freeze: no overclock is configured (MSI Afterburner startup profile empty, AMD `PP_AutoODActive=0`);
no temperature source is available on this machine (no ACPI thermal zone, HWiNFO logging off, pyadl Overdrive5
fails on RDNA3); ~35 llama-server sessions completed that day without incident. The earlier reading that "the only
common factor of both freezes is a llama-server/Vulkan session" is withdrawn: the second interruption had an
external cause. The two stock ngram-mod entries were not rerun (closed as REJECTED / SUPERSEDED, section 6).

Harness hardening after the crashes (`model_lab/uri_engine/queue_runner.py`): on-disk manifest rewritten atomically
(tmp + fsync + rename) before and after every entry with command line, binary and model sha256, start/end timestamps,
exit code, boot time and verified required outputs (must exist, be newer than the start and parse as JSON); an entry
is "done" only when all of that holds; a running entry found on restart is marked "interrupted" with the boot-time
comparison and the last telemetry sample; host telemetry (free RAM, dedicated VRAM, GPU utilisation, server RSS/CPU)
is appended and fsynced every 3 s to `queue_logs/telemetry_<id>_<stamp>.csv`; a silence watchdog kills a hung
llama-server (420 s without log output) and a hard per-entry timeout kills the entry.

Post-crash queue (three passes: 14:07-14:25 before the second freeze, 18:35-20:09 and 20:12-20:59, 20:59-21:14;
`queue_manifest.json`, generated by `queue_summary.py`, stored as `QUEUE_SUMMARY.md`, which is the complete final
table; the table below is the state at the end of the research phase, 20:59). Entries carry the command line, model
sha256 `66a3ca88...`, binary sha256 set, boot time, start/end, exit code, verified outputs and the telemetry peaks. The
pass boundaries at 20:09 and 20:59 were deliberate restarts (sampler fix; added entries). Final state 2026-10-07:
45 entries, 43 done, 2 rejected_superseded, 0 open (section 11). Three Claude sessions (pre-crash, 13:50 recovery,
18:35+ continuation) resumed from this one manifest: no completed GPU experiment was rerun for lack of a record and
none was lost; the single interrupted attempt (`ctx_prod_split` at 14:25) was re-run once.

| id | group | status | attempts | start | elapsed s | rc | peak VRAM MiB | min free RAM MiB | outputs |
|---|---|---|---|---|---|---|---|---|---|
| freeze_start | safety | done | 1 | 14:07:49 | 2.2 | 0 | - | - | freeze_check_recovery_start.json |
| determinism_probe | correctness | done | 1 | 14:07:55 | 227.8 | 0 | - | - | determinism_probe.json |
| ctx_control | context_reuse | done | 1 | 14:11:48 | 484.1 | 0 | - | - | ctx_control_20261006-141151.json |
| ctx_prod | context_reuse | done | 1 | 14:19:56 | 285.5 | 0 | - | - | ctx_prod_20261006-141959.json |
| ctx_prod_split | context_reuse | done | 2 | 18:35:14 | 410.4 | 0 | 15553.2 | 9033.0 | ctx_prod_split_20261006-183518.json |
| ctx_ckpt1024 | context_reuse | done | 1 | 18:42:09 | 374.0 | 0 | 15573.4 | 9526.0 | ctx_ckpt1024_20261006-184213.json |
| ctx_cache4096 | context_reuse | done | 1 | 18:48:28 | 329.9 | 0 | 15573.4 | 7625.0 | ctx_cache4096_20261006-184831.json |
| ctx_prod_multi | context_reuse | done | 1 | 20:09:30 | 363.6 | 0 | 15754.8 | 7696.0 | ctx_prod_multi_20261006-200933.json |
| ctx_prod_multi_ms512 | context_reuse | done | 1 | 20:59:34 | 266.2 | 0 | 15752.6 | 5801.0 | ctx_prod_multi_ms512_20261006-205937.json |
| ctx_sim0_cache4096 | context_reuse | done | 1 | 20:15:38 | 280.8 | 0 | 15754.6 | 5926.0 | ctx_sim0_cache4096_20261006-201541.json |
| ctx_ux_best_split | context_reuse | done | 1 | 20:20:23 | 541.6 | 0 | 15785.9 | 5526.0 | ctx_ux_best_split_20261006-202026.json |
| ctx_ux_best2_split | context_reuse | done | 1 | 21:04:05 | 480.6 | 0 | 15152.0 | 3836.0 | ctx_ux_best2_split_20261006-210408.json |
| ctx_sb_prod | context_reuse | done | 1 | 18:54:02 | 828.9 | 0 | 15661.3 | 7983.0 | ctx_sb_prod_20261006-185406.json |
| ctx_ux_fine1024 | context_reuse | done | 1 | 19:07:55 | 839.7 | 0 | 16078.5 | 6878.0 | ctx_ux_fine1024_20261006-190759.json |
| ctx_ux_fine512 | context_reuse | done | 1 | 19:22:00 | 717.5 | 0 | 15736.2 | 7953.0 | ctx_ux_fine512_20261006-192203.json |
| determinism_probe2 | correctness | done | 1 | 19:34:02 | 474.3 | 0 | 15718.8 | 8740.0 | determinism_probe2.json |
| uri_base_16k | bench_uri | done | 1 | 19:42:00 | 184.8 | 0 | 15515.2 | 8929.0 | uri_base_16k_20261006-194205.json |
| uri_mtp3_16k | bench_uri | done | 1 | 19:45:09 | 179.5 | 0 | 15953.2 | 7461.0 | uri_mtp3_16k_20261006-194513.json |
| ue_base16k | correctness | done | 1 | 19:48:13 | 669.0 | 0 | 15566.2 | 6757.0 | summary.json |
| ue_mtp3_16k | correctness | done | 1 | 19:59:27 | 570.1 | 0 | 16176.4 | 5066.0 | summary.json |
| ue_base16k_rep | correctness | done | 1 | 20:29:29 | 620.6 | 0 | 15533.3 | 8517.0 | summary.json |
| mtp2_32k_vision | bench_spec | done | 1 | 20:39:54 | 119.3 | 0 | 15859.5 | 7241.0 | mtp2_32k_vision.json |
| mtp3_24k_vision | bench_spec | done | 1 | 20:41:57 | 117.7 | 0 | 15787.4 | 7702.0 | mtp3_24k_vision.json |
| mtp2_16k_vision | bench_spec | done | 1 | 20:43:59 | 119.3 | 0 | 15856.7 | 7814.0 | mtp2_16k_vision.json |
| mtp4_16k_vision | bench_spec | done | 1 | 20:46:03 | 119.2 | 0 | 15764.9 | 7703.0 | mtp4_16k_vision.json |
| stream_overhead | overhead | done | 1 | 20:48:06 | 96.2 | 0 | 15642.8 | 9977.0 | stream_overhead.json |
| stream_probe2 | overhead | done | 1 | 21:12:10 | 99.6 | 0 | 15635.6 | 8509.0 | stream_probe2.json |
| sb_prod_canon | bench_uri | done | 1 | 20:49:46 | 179.0 | 0 | 15736.4 | 9013.0 | sb_prod_canon_20261006-204951.json |
| ux_prod_canon | bench_uri | done | 1 | 20:52:50 | 177.1 | 0 | 15734.6 | 8925.0 | ux_prod_canon_20261006-205253.json |
| uri_ngram_simple | bench_uri | done | 1 | 20:55:51 | 173.0 | 0 | 15704.1 | 9088.0 | uri_ngram_simple_20261006-205555.json |
| uri_ngram_mod16 | bench_uri | blocked | 0 |  | - | - | - | - | identical settings to the run in progress at the crash (stock ngram-mod on a hybrid model); needs user decision |
| ux_ngram_mod8 | bench_spec | blocked | 0 |  | - | - | - | - | n-gram speculation on the hybrid model (patched rs-seq path); crash-adjacent class, needs user decision |
| freeze_end | safety | done | 1 | 20:58:48 | 2.7 | 0 | None | 11268.0 | freeze_check_recovery_end.json |


## 10. Conclusion

Answer to the research question: yes, Qwen3.6's repeated URI context can be processed substantially faster by
reusing stable prefix/recurrent state, and almost all of the measured gain is available in stock llama.cpp b11425
through its context-checkpoint + prompt-cache mechanism, provided URI shapes its prompts and server flags for a
hybrid model. The remaining gap (a change inside a long message) is closed either by prompt shaping or by a 7-line
server patch; nothing in Strata applies beyond concepts llama.cpp already implements.

Measured on the production binary (release b11425 Vulkan, 32k, vision loaded), 30k-token URI context:

| URI situation | production today | with the findings | mechanism |
|---|---|---|---|
| exact repeat | 4 tokens, TTFT 0.33 s | same | prompt cache |
| new user turn on an unchanged context | 1,025 tokens, TTFT 1.06 s | 50 tokens, TTFT 0.58 s | current turn as its own user message (checkpoint at the user-message start) |
| one evidence block changed mid-context | 25,816 tokens, 14.0 s | stock: resume from the last message boundary before the change (6.3k excess with evidence in 4 messages; smaller with more boundaries and `--checkpoint-min-step` lowered); patched: 227-506 excess tokens, ~3.5-4 s expected at release prefill speed | message-boundary checkpoints (stock) or ubatch-granular checkpoints (patch) |
| return to a context seen earlier (after a different one) | 25,817 tokens, 14.0 s | 4 tokens, TTFT 0.6 s | `--slot-prompt-similarity 0 --cache-ram 4096` (always save; cache holds several 30k states) |
| permission/session-state change early in the prefix | everything after it recomputed (correct), excess 440 | same | correct invalidation, nothing to gain |
| generation | 96-102 tok/s | 141-173 tok/s with the exported MTP draft (fits at 32k+vision only with n_max 2); decision turn 2.51 -> 2.05 s | `--spec-type draft-mtp`; score-equivalent (section 3.1) |

Architecture verdict (acceptable conclusions A-E):

- **A, stock llama.cpp, is the primary result**: the checkpoint/prompt-cache machinery, `--slot-prompt-similarity 0`,
  `--cache-ram 4096`, `--checkpoint-min-step`, and MTP are all stock b11425. The gains that matter for URI's workload
  (new turn 2x faster TTFT at 30k, context switch-back 14 s -> 0.6 s, generation 1.5x) need no runtime change, only
  (1) a URI prompt shape with message boundaries around the parts that change (current turn; evidence sections),
  (2) three server flags, (3) ~3-4 GB more host RAM for the prompt cache and checkpoints, (4) the MTP draft file.
- **B, llama.cpp + a small URI-specific extension, is justified for exactly one case**: a change inside a long
  message when URI cannot put a message boundary there. The 7-line `fine_ckpt` patch
  (`patches/uri-ext-b11425.diff`, server-only, no kernel or model change) reduces the excess from ~19k tokens to the
  ubatch size at 30k. It should be carried as a patch on top of the pinned upstream commit, or proposed upstream
  (a `--checkpoint-min-step` below the ubatch is a natural way to ask for it), not as a fork. The second research
  patch (`n_rs_seq` for n-gram drafters) is not needed: n-gram speculation produces no drafts on URI's first-sight
  prompts and the stock ngram-mod path hung the server.
- **C, a URI-maintained fork, is not justified**: every measured gain is a flag, a prompt shape or a 7-line patch.
- **D, a dedicated URI engine, is not justified**: decode is launch-bound at ~100 tok/s with experts only ~18% of
  per-token bytes, prefill runs at ~1,900-2,100 tok/s, and the Vulkan backend already has every Qwen3.6 kernel; a new
  engine would start without cooperative-matrix shaders (the self-built binaries show what that costs: 2.5-3.4x slower
  prefill).
- **E, a Strata adaptation, is not applicable**: Strata's gains come from making non-resident experts fast (expert
  tiers, pinned host arenas, SSD-backed PLE tables, CPU expert pools) for a 125B model on 12 GB; URI's 12.7 GiB model
  is fully resident on 16 GB, and the one Strata technique that maps to URI (conversation-cache checkpoints) is
  already in llama.cpp. Strata is CUDA/HIP only; URI runs Vulkan.

Correctness: checkpoint and prompt-cache reuse reproduce the same outputs as a fresh computation in every case
where the restore happened (B_repeat, A_reprime rows), and three fresh production sessions agree on all 221/220
suite cases. "Byte-identical" is not a usable criterion on this backend (section 3.2: the ubatch layout and
run-to-run Vulkan numerics flip near-tie tokens inside free-text fields); suite scores and score-changing-case
counts are. MTP is score-equivalent (0 score-changing cases of 220).

Smallest architecture that captures most of the measured gain: **A (stock llama.cpp b11425) with URI-side prompt
shaping and three server flags**, carrying the 7-line checkpoint patch (B) only if URI needs sub-message reuse
granularity and can afford the host RAM for a 16-32 entry checkpoint ladder. Recommended production candidate to
qualify next (not applied here): `-b 2048 -ub 1024 --cache-ram 2048 --slot-prompt-similarity 0 --checkpoint-min-step
512 --ctx-checkpoints 16`, prompts shaped as [system contract + capabilities + permission state] / [session state +
evidence, split into acknowledged user messages at the points where evidence is expected to change] / [current turn
as its own user message], plus `--spec-type draft-mtp --spec-draft-n-max 2` with the exported draft when the 32k +
vision VRAM budget allows it. Each element is a stock flag or a prompt shape; the correctness gate is the suite run
(section 3.1), not byte equality.

Open items at the end of the research phase (all closed in the final milestone, section 11): (1) the patched build
was timed on a glslc-limited binary; (2) the ~0.22 s per-request overhead is the lab client's per-call `httpx`
client construction, not the server; (3) the first freeze remains CAUSE UNKNOWN; (4) the two stock ngram-mod
entries were blocked; (5) the recommended candidate had not been run through the 221-case suite.

## 11. Final closure addendum (2026-10-06 evening; freeze record `URI_RESIDENT_INTELLIGENCE_RUNTIME_V1_FREEZE.md`)

- **Fair build comparison.** Vulkan SDK 1.4.363.0 (LunarG installer sha256 `94a82d37...`, payload carved, no
  system change; `build_provenance_sdk.json`) supplied glslc shaderc v2026.4. Stock and patched trees were rebuilt
  with all seven shader extensions detected (`build/stock2`, `build/rsseq2`). The SDK-built stock binary equals the
  official release binary (1,822 vs 1,830 prompt tok/s at 30k, identical `prompt_n`/`cache_n` in every row), so the
  earlier 2.5-3.4x gap was entirely the missing shaders.
- **Patch decision: REJECTED.** On the v1 context layout (`CONTEXT_ARCHITECTURE_V1.md`; `TABLES_final_layout.md`)
  the stock server resumes a changed evidence part with 169-332 excess tokens, a permission change with 383, a new
  turn with 23, a return to a previous context with 4; the patched binary is equal or worse in every row (673-1,087
  excess at ubatch 2,048, 1,403-1,990 on permission changes, lost return-to-context at 30k) and costs 0.8-1.2 GB
  more RSS. The patch is kept only as evidence.
- **Client overhead closed.** `local_brain.py` now uses one persistent keep-alive client (`BrainClient`): 2.5-10.6 ms
  overhead instead of 234-238 ms; decision turn 2.17 -> 1.95 s; reconnects after a server restart in one retried call.
- **Second interruption reclassified** as an external power outage (user-supplied cause; section 9); the first
  remains CAUSE UNKNOWN and is the only stability-relevant event.
- **n-gram speculation closed** as REJECTED / SUPERSEDED (section 6); the blocked entries were not rerun.
- **Candidate qualification:** `ue_cand` / `ue_cand_mtp2` / `ue_cand_normal` / `ue_cand_mtp2_normal` / `uri_cand_mtp2`
  — every suite score identical to the qualification baseline, 0 score-changing cases, 0 errors (freeze record §11).
- **Final soak (2026-10-06 22:57 -> 2026-10-07 00:14, `soak_final.json`):** exact candidate with MTP, 77.3 min,
  68 cycles, 1,036 calls (trivial, decision contract with grammar, extraction, drafting, grounded answer, NORMAL-tier
  reasoning, 16k cached-context sequence, vision), 16 idle pauses, one mid-run server restart + client reconnect
  (`ConnectError` while down, first call after the 92 s cold reload 0.70 s): **0 errors, 0 invalid structured outputs,
  0 Windows System events**; server RSS 4,305 -> 4,315 MiB (+10 MiB), VRAM 15,849-15,851 MiB flat, free RAM >= 5.5 GB,
  last-third latency = first-third latency for every call kind. Two behaviours recorded, neither a defect: the 48-token
  harness cap truncates pretty-printed 16k JSON answers, and under mixed traffic the 2 GiB prompt cache holds ~3 of the
  four distinct 16k states, so "back to A" resumes from the evidence-part boundary (12,759 of 16,060 tokens, 2.7 s)
  instead of 4 tokens (freeze record §12, §15).
- **Final freeze check** `freeze_check_runtime_v1.json` (00:14:40): 121/121, 0 differences, archive hash matches;
  `git status`/`git diff` identical to the pre-research baseline; `uri_core/` untouched; GPU idle afterwards
  (no `llama-server.exe`, 1,065 MiB desktop VRAM).
- **Queue closure (2026-10-07):** 45 entries, 43 done; `uri_ngram_mod16` and `ux_ngram_mod8` resolved from existing
  evidence as REJECTED / SUPERSEDED without GPU time; nothing pending, running, blocked or interrupted
  (`QUEUE_SUMMARY.md`; freeze record §17.1).
- **Strata investigation: CLOSED** — concepts harvested, no Strata-style engine justified (section 8, verdicts C/D/E).
- **Verdict: A — STOCK** (stock optimized llama.cpp b11425 + URI prompt shaping and configuration). The 7-line patch is
  REJECTED, not carried. **URI Resident Intelligence Runtime v1 — FROZEN** (freeze record §17; reopening criteria §14
  there). Research on this question stops here.

## Appendix: evidence index

- `evidence/uri_engine/queue_manifest.json` - every run after the first crash with status, hashes, timings, outputs
- `evidence/uri_engine/context_reuse/` - section 1/2 runs, `compare_*.json`, `prompts_single.json`, `prompts_split.json`, server logs
- `evidence/uri_engine/runs/` - bench_uri variants (section 5), `*.calls.jsonl` per request
- `evidence/uri_engine/spec/` - bench_spec runs and `compare_*.json` (section 6)
- `evidence/runs/ue_*/` - correctness suites (section 3.1), `diff_ue_ckpt1024.json`
- `evidence/uri_engine/determinism_probe.json`, `determinism_probe2.json`, `determinism_logs/` (section 3.2)
- `evidence/uri_engine/overhead.json`, `stream_overhead.json`, `diag_ckpt.json`, `coldload_*.json`, `expert_stats_*.json`
- `evidence/uri_engine/crash_recovery_20261006.json`, `crash_recovery_20261006_second.json`, `hang_ngram_mod_stock_b11425.log`
- `evidence/uri_engine/freeze_check_recovery_*.json`, `freeze_check_runtime_v1.json`, `freeze_check_after_prove_v1.json` - Phase 1 freeze checks
- `evidence/uri_engine/build_provenance_sdk.json`, `D:\uri-model-lab\vk\VulkanSDK-1.4.363.0\CARVE_RECORD.json` - Vulkan SDK toolchain and SDK-built binaries (final milestone)
- `evidence/uri_engine/context_reuse/TABLES_final_layout.md`, `ctx_rel_final_*`, `ctx_sb2_*`, `ctx_ux2_*` - v1 layout, fair build comparison
- `evidence/uri_engine/client_overhead.json`, `stream_probe2.json` - HTTP client overhead and reconnect
- `evidence/runs/ue_cand*/` - candidate qualification suites (fast, normal, with and without MTP)
- `evidence/uri_engine/soak_final.json`, `soak_logs/`, `queue_logs/telemetry_soak_final_*.csv` - 77-minute stability soak
- `evidence/integration_proof.json` (v1 adapter proof), `integration_proof_20261006-0851_prefreeze.json` (pre-freeze proof, preserved)
- `evidence/uri_engine/crash_record_correction_20261006.json` - second interruption reclassified as an external power outage
- `uri_engine/CONTEXT_ARCHITECTURE_V1.md`, `URI_RESIDENT_INTELLIGENCE_RUNTIME_V1_FREEZE.md` - normative v1 documents
- `uri_engine/NOTES_architecture.md` - working notes (superseded by this document)
