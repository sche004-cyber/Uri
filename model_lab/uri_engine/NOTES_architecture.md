> Superseded on 2026-10-06 by model_lab/URI_ENGINE_STRATA_RESEARCH.md (the post-crash research record). Kept as the working draft.

# Working notes: Strata analysis and Qwen3.6 mapping (merged into URI_ENGINE_STRATA_RESEARCH.md at the end)

## Strata (github.com/Niko1221/Strata, MIT; clone at D:\uri-model-lab\strata_research\strata, 852 files, ~98k lines)

Target model: Qwen3.8-Flash-Next, 48 layers (12 QSA sparse-attention + 36 GDN), 24,576 experts (48 x 512), top-10,
hyper-connection residual (hc=4, n_embd 2560), a PLE (per-layer n-gram embedding) module whose table is 28.8 GB,
one MTP layer. Geometry is compiled in (`include/strata/core/expert_source.hpp`: "THE KERNEL'S GEOMETRY IS FIXED BY
THE ARTIFACT (H = 2560, FF = 640, BLOB = 1,382,400) ... A different n_embd or a different expert width is REFUSED").

Technique -> where it lives -> what it does -> relevance to Qwen3.6 on the RX 7900 GRE:

| Technique | Source | Mechanism (from source/docs) | Class for URI |
|---|---|---|---|
| Expert placement / VRAM expert tier | `include/strata/core/expert_cache.hpp`, `src/core/expert_cache.cpp` | Static profile (`profile.bin`, ranked (layer, expert) by routing frequency, `tools/make_profile.py`) fills a slot arena; per-layer admission (R4.2g) because a global arrival-order fill put all slots on two layers (2.97% hit); no eviction in the static tier; adaptive tier swaps between VRAM and RAM between tokens (`--adapt-every`). Measured h_expert 0.64 held-out at 4,105 of 24,576 slots. | E/F: Qwen3.6 IQ3_S's 10.8 GiB of experts are fully resident; nothing to place |
| Hot-expert adaptivity | `expert_cache.cpp` (`rank_learned_profile`, `--expert-profile-save`) | heat counters since start, swaps with the RAM copy | E/F (same reason) |
| GPU/CPU expert concurrency | `include/strata/kernels/cpu/pool.hpp`, `include/strata/core/session.hpp` (doorbell) | CPU pool computes missed experts (AVX2/AVX-512, DRAM-bound 42.5 GB/s on 6 cores) while GPU runs the layer; residual chain is serial so overlap window is only the shared expert ("A per-layer CPU pool cannot be hidden behind a strictly serial residual chain") | F: the Q4_K_M `--n-cpu-moe` qualification run already measured this class on URI's hardware: 41 tok/s, 6.1 s decisions, RAM starvation. Not for the resident IQ3_S |
| Expert streaming during prefill | `include/strata/prefill/prefill.hpp` | chunks up to 8,192 tokens; routed experts grouped by expert, non-resident ones streamed through a pinned ring on a copy stream; byte-sized ring (0.1.39b) | E: no non-resident experts to stream |
| RAM pinning / pinned arena | `src/core/pinned.cu` (2 MB-aligned reservation, large pages, shared tmpfs arena) | all experts pinned in host RAM for DMA | F: needs RAM URI does not have (24 GB total, >=10 GB desktop floor) |
| SSD-backed data | `include/strata/ngram/ple_reader.hpp`, `src/platform/direct_file.cpp` | unbuffered 4 KiB reads of the 28.8 GB PLE table, 16 rows/token, issue/collect split hides latency behind layer 0 | D: PLE is a Qwen3.8 architecture feature; Qwen3.6 has none |
| Prefill chunking | `prefill.hpp` (`--prefill auto`, 8,192) | GDN recurrences "walk the chunk inside one kernel"; QSA indexer append batched | B: llama.cpp already has `-b/-ub` chunking and a chunked GDN kernel (`src/models/delta-net-base.cpp`, CS=64, `ggml_solve_tri`); tune, don't port |
| Prompt kernels | `src/kernels/cuda/*.cu`, `src/prefill/moe_fused*.cu`, `gemm.cu`, HIP MMQ (`docs/AMD_HIP_PERFORMANCE.md`) | dequant->FP16 tensor-core GEMM, fused int8 experts (CUDA-only), hipBLASLt tuning tables per arch | F/C: CUDA/HIP only; URI runs Vulkan (ROCm reports no device on this driver, qualification §12). Kernel ideas (int8 coopmat) already landed in llama.cpp Vulkan (#27952, 2026-09-24) |
| MTP / self-speculative decoding | `include/strata/core/mtp.hpp`, `include/strata/core/verify.hpp` | one captured verify graph for T tokens; argmax per row "BIT FOR BIT" the greedy token; commit replays GDN state for accepted tokens; 2.4-3.2 tokens/pass | B: llama.cpp has `--spec-type draft-mtp` for qwen35moe (`common/speculative.cpp` "neither (qwen35 / qwen35moe): a single trained MTP head") and bounded recurrent rollback (`n_rs_seq`). Blocker: the qualified GGUF carries no `nextn` tensors (verified: 0 of 733) |
| Prompt lookup (suffix drafter) | `include/strata/spec/suffix_drafter.hpp`, `src/spec/draft_policy.cpp` | trigram index of history, longest-suffix match, policy picks MTP vs lookup from measured acceptance and round cost (EMA) | B: llama.cpp `ngram-simple/ngram-map-k/ngram-mod`; the cost-aware policy is the part llama.cpp lacks |
| KV-cache management | `include/strata/kernels/kv_stream.hpp` (`--kv-resident 32768`, int8/K8V4/Q4 formats, CLOCK page residency) | authoritative KV in pinned host memory, VRAM page pool for the selected blocks | E/F: 10 full-attention layers x 2 KV heads x 256 = 10.6 KiB/token at q8_0; 32k = 340 MiB. Nothing to stream |
| Recurrent-state handling | `include/strata/core/session.hpp` (36 GDN states), `verify.hpp` commit replay | GDN state untouched during the verify window, replayed on commit | B: llama.cpp's `n_rs_seq` snapshot ring does the same role (VRAM cost: recurrent memory x (1+n_rs_seq)) |
| Prefix / session reuse | `docs/DETAILS.md` "Conversation cache": checkpoints at every assistant-turn start and every 16K prompt tokens, root checkpoint at the end of a >=2,048-token system prompt kept for good, parked conversations in bounded host RAM | exact-token-prefix match only | A (already in llama.cpp): `--ctx-checkpoints` (checkpoint at user-message starts, `--checkpoint-min-step`), `--cache-ram` prompt cache that stores slot states with their checkpoints and is matched by longest common prefix (`tools/server/server-task.cpp::server_prompt_cache::load`) |
| Scheduling | `src/program/generate.cpp`, `docs/BATCHING.md` | one request at a time by default; opt-in `--batch N` slots decoded together; layer graphs captured per layer so the host decides when each layer runs | F: URI is single-user, single-slot; llama-server `-np` covers multi-slot |
| Vulkan vs CUDA | none: CUDA, HIP (gfx1100/1101/1200/1201/1030) and SYCL only | HIP = CUDA-shaped calls mapped to hipBLAS, wave32 shuffles | F: no Vulkan backend; the Windows HIP zip "has not run a model on a discrete card yet" (AMD_HIP.md). A port would be a new backend, not an adaptation |
| AMD-specific | `docs/AMD_HIP.md`, `AMD_HIP_PERFORMANCE.md` | RX 7900 XTX measured on Linux ROCm 7.1: 447-967 tok/s prefill, 55-59 tok/s decode for a 125B MoE at IQ3_XXS; WDDM budget workaround (#380) | reference only |
| Memory planning | `strata-device` planner, `--vram-reserve-mib`, `conversation-cache-min-free-mib`, Windows page-file warning | plans the expert tier from live free VRAM | B (concept): URI already pins its budget deterministically (`local_brain.json`) |
| Quantization assumptions | `docs/DETAILS.md` (Q2_0, IQ2_XS, IQ3_XXS, IQ3_S, Coder IQ1_M pruned) | own Q2_0 format for fused int8 experts, Hadamard-rotated 4-bit KV | E: URI's artifact is pinned by hash; requantizing re-opens qualification |

Headline: Strata solves "a 125B MoE on 12 GB" by making non-residency fast. URI's problem is the opposite: the whole
model is already resident, and the costs are per-turn prefill, generation length and fixed per-request overhead.

## Qwen3.6-35B-A3B as URI runs it (GGUF `general.architecture = qwen35moe`, 733 tensors, 12.73 GiB)

- 40 blocks: `full_attention_interval 4` -> blocks 3,7,...,39 are gated full attention (10), the other 30 are
  Gated DeltaNet (`llama_model_qwen35moe::load_arch_hparams`: `is_recr = (i+1) % 4 != 0`).
- Full attention: 16 Q heads x 256, 2 KV heads x 256 (GQA 8), partial RoPE 64 dims, M-RoPE sections [11,11,10]
  (`rope.dimension_sections`), `rope.freq_base 1e7`, q/k norm, attn_output_gate.
- Gated DeltaNet: `ssm_state_size 128`, `ssm_group_count 16` (K heads), `ssm_time_step_rank 32` (V heads),
  `ssm_inner_size 4096`, conv kernel 4; tensors `attn_qkv [2048, 8192]`, `attn_gate [2048, 4096]`, `ssm_conv1d [4, 8192]`,
  `ssm_alpha/beta [2048, 32]`, `ssm_a [32]`, `ssm_dt.bias [32]`, `ssm_norm [128]`, `ssm_out [4096, 2048]`.
- MoE on every block: 256 routed experts (`ffn_gate_exps/up_exps IQ2_S [2048, 512, 256]`, `ffn_down_exps IQ3_S
  [512, 2048, 256]`, 3 layers IQ4_XS), top-8 (`expert_used_count 8`), one shared expert (ffn 512, Q6_K) with its own
  sigmoid gate (`ffn_gate_inp_shexp`), router `ffn_gate_inp F32 [2048, 256]`.
- Embedding/head: `token_embd Q6_K 397.9 MiB`, `output Q6_K 397.9 MiB` (untied), vocab 248,320.
- MTP: HF config `mtp_num_hidden_layers: 1`, 19 `mtp.*` tensors in shards 25-26 of the HF repo; the unsloth GGUFs
  (IQ3_S, Q4_K_M checked) carry none. llama.cpp expects them as `blk.40.nextn.*` + `blk.40.{attn,ffn}*`
  (`load_block_mtp`), so an MTP draft file must be exported from the HF checkpoint (`convert_hf_to_gguf.py --mtp`).
- Vision: `mmproj-F16.gguf` 0.84 GiB, `clip.projector_type qwen3vl_merger`, 27 ViT blocks, hidden 1152, patch 16,
  spatial merge 2, image size 768.
- Bytes per block (IQ3_S artifact): routed experts 274.5 MiB (gate 82 + up 82 + down 110), DeltaNet block dense
  19.7 MiB (qkv 13.1 + gate 6.6) + ssm_out 6.6, full-attention block dense 21.3 MiB, shared expert 2.5 MiB,
  router 2.0 MiB. Totals: routed experts 10.78 GiB (84.7%), attention/DeltaNet projections 1.0 GiB, embd+head 0.78 GiB.
- Per-token weight traffic at decode (what the GPU must read for one token): dense projections ~0.98 GiB + shared
  experts 0.10 GiB + routers 0.08 GiB + head 0.39 GiB + 8 of 256 experts per block = 8 x 1.07 MiB x 40 = 0.34 GiB
  -> ~1.9 GiB/token. At the card's 576 GB/s that is ~3.5 ms; measured 10.1 ms/token (99 tok/s) -> decode is not
  bandwidth-bound; ~2/3 of the token time is kernel-launch / synchronization / sampling overhead. Experts are only
  ~18% of per-token bytes: an expert cache cannot help, and speculation (amortizing fixed cost over several tokens)
  is the lever that fits this profile.
- Recurrent state per sequence (F32, `llama-memory-recurrent.cpp`): r = (4-1) x (4096 + 2 x 16 x 128) = 24,576 floats
  (96 KiB) per DeltaNet block, s = 128 x 4096 = 524,288 floats (2 MiB) per block -> 30 x 2.09 MiB = 62.8 MiB per
  sequence; with `n_rs_seq = n` snapshots the recurrent buffer is x(1+n).
- KV per token (10 full-attention blocks, q8_0 K and V): 10 x 2 x 2 heads x 256 x 1.0625 B = 10.6 KiB -> 4k 43 MiB,
  16k 170 MiB, 32k 340 MiB.
- Context checkpoints (`common_prompt_checkpoint`, `LLAMA_STATE_SEQ_FLAGS_PARTIAL_ONLY`): recurrent state + KV up to
  the checkpoint -> ~90 MiB at a 2.8k-token system prefix, ~240 MiB at 16k. The prompt cache (`--cache-ram`) stores
  whole slot states plus their checkpoints; the baseline log shows entries of 125-628 MiB being evicted at the 1024 MiB limit.
- Vulkan path: every Qwen3.6 op has a Vulkan kernel in b11425 (`GGML_OP_GATED_DELTA_NET`, `SSM_CONV`, `SOLVE_TRI`,
  `CUMSUM`, `TRI`; `ggml/src/ggml-vulkan/vulkan-shaders/gated_delta_net.comp`), so `-ngl 999` keeps the whole graph
  on the GPU; "graphs reused" counters in the server log confirm graph reuse across decode steps.

## Interim measurements (2026-10-06, bench_uri.py; production flags = `-b 2048 -ub 1024 --cache-ram 1024`, 32k, vision loaded)

Decision turn anatomy (proposer seam, grammar on, canonical JSON): prompt = 2,763-token Core system prompt +
~1,300-1,500-token request (capability_summaries 1,251 tokens of it). Server reuses the system prefix every turn
(cache_n 2,766) even when interpreter/answer prompts run in between (prompt cache `--cache-ram` swaps slot states by
longest common prefix). Remaining cost: ~0.49-0.72 s prefill of the request + ~1.0-1.7 s generating 100-175 tokens at
~98 tok/s + ~0.25 s fixed. Total p50 2.3-2.5 s.

| variant | dec cache_n | dec prompt_n | dec prompt ms | dec total | repeat total | 16k follow-up ms (cache_n) | 29k follow-up ms | gen tok/s | min free RAM MiB |
|---|---|---|---|---|---|---|---|---|---|
| base_prod (lab JSON order) | 2766 | 1504 | 722 | 2.49 | 2.43 | 611 (16933) | n/a | 101.5 | 12710 |
| canonical JSON + `--checkpoint-min-step 1024 --ctx-checkpoints 16` | 3047 | 1024 | 485 | 2.32 | 2.18 | 615 (16933) | 759 (30897) | 101.4 | 14044 |
| `--cache-ram 0` | 0 | 4051 | 1677 | 3.22 | 2.31 | 611 | 759 | 101.5 | 14348 |
| `--ctx-checkpoints 0` | 0 | 4070 | 1559 | 3.53 | 3.43 | 8195 (0) | 16901 (0) | 101.6 | 14027 |
| `-np 3 -kvu` | 3047 | 1024 | 480 | 2.31 | 2.22 | 610 | 828 | **87.2** | **10175** |
| `-b 4096 -ub 2048` | 2766 | 1304 | 587 | 2.32 | 2.22 | 1174 (15909) | 1455 (29873) | 101.6 | 14092 |
| stable-first JSON | 3201 | 1158 | 573 | 2.35 | 2.32 | - | - | - | 14070 |

Reading: (1) llama.cpp's context checkpoints + prompt cache already deliver the "conversation cache" Strata describes:
without them a decision turn costs 3.5 s and a 16k follow-up 8.2 s. (2) Reuse granularity follows the ubatch: the
"near end" checkpoint lands one ubatch before the prompt end, so canonical (sorted-key) JSON + ub 1024 reuses
3,047 tokens; ub 2048 falls back to the system boundary. (3) -np 3 costs 14% decode speed and 4 GB RAM: rejected.
(4) Serialization order beyond production's canonical sort buys nothing measurable.

Raw sequential read (FILE_FLAG_NO_BUFFERING): D: HDD 120 MB/s -> 113.8 s for the 13.68 GB GGUF; C: NVMe 1,964 MB/s
-> 7.0 s (+0.47 s projector). Observed cold loads from D: 85-140 s (I/O-bound; the 140 s run had concurrent
downloads to D:), warm 8.2 s.

MTP: exported `mtp-qwen36-35b-a3b-Q4_K_M.gguf` (1.26 GB; experts Q4_K 432 MiB, output Q6_K, token_embd q4_0 kept on
CPU via `-otd token_embd.weight=CPU`) from HF shards 1, 25, 26 with `convert_hf_to_gguf.py --mtp`. VRAM headroom at
32k+vision is ~770 MiB, so MTP is tested at 16k+vision and 32k without vision.

### Determinism finding (spec_off run, bench_spec.py)
Two identical greedy requests (temperature 0, seed 7, same prompt_n, cache_n 0 both times) diverged late in the output
for 2 of 8 tasks (decision_contract at char 625/671, office_draft at char 512/761); 6 of 8 were byte-identical. The
divergence is not prompt-cache related (no cached prefix either time): the Vulkan backend's MoE/attention kernels are
not bit-reproducible run to run (near-tie tokens flip). Consequence: "byte-identical output" is not a usable
correctness criterion on this runtime; regression checks must use suite scores plus divergence rates, and speculative
decoding is judged by rep0 (fresh) equality against the baseline's own repeat variance.

### n-gram speculation (stock b11425, ngram-mod n_match 24 / n_min 48 / n_max 64; rep0 = first sight of each prompt)
quote_back 102 -> 339 tok/s (167/192 drafts accepted), code_patch 104 -> 169, rewrite_circular 102 -> 124; tasks with
nothing to look up unchanged (97-104). Outputs identical to baseline on all rep0 tasks. rep1 (same prompts again) is
inflated by the server-wide hash pool remembering the previous answer (decision_contract 128/128 accepted) and shows the
miss cost: office_draft 103 -> 79 tok/s with 30/128 accepted. VRAM unchanged (15.6 GB), RSS 2.09 GB.

### MTP (draft-mtp, exported head, Q4_K_M draft, token_embd on CPU)
16k + vision (fits: 15.82 GB VRAM peak, RSS 3.3 GB, free RAM 12.8 GB): median gen speedup 1.62x; decision_contract
99 -> 152 tok/s (acceptance 0.89, mean accepted length 3.67 of 4), extraction/code/quote 1.65-1.72x, free-form prose
1.02-1.18x (acceptance 0.43-0.58). 32k without vision: identical pattern (1.62x median, n_max 2: 1.48x). Cost: TTFT
+0.05-0.2 s (the draft layer also prefills the prompt), +1.33 GB VRAM, +1.2 GB RSS. decision_contract end-to-end
3.92 -> 3.41 s (-13%); shorter contracts (~150 tokens) gain proportionally less because prefill dominates.
Outputs: identical to the plain run on 6 of 8 tasks. office_draft differs, but the plain runtime is itself not
repeat-stable on that task (rep0 != rep1 in every plain run; decision_contract likewise, systematically on the second
occurrence). conversational differs although the plain runtime is repeat-stable there: batched verification of
3 drafts changes a near-tie token in free-form prose. So MTP is "greedy-equivalent up to backend numerics", not
bit-equivalent; it is judged on suite scores (correctness2.sh).

### Expert activation skew (llama-imatrix per-expert counts, IQ3_S model, -c 2048)
URI corpus (207 real URI prompts, ~400k tokens): the 64 most-used experts of a block serve 70.2% of routed
assignments, 128 serve 90.3%; mean Gini 0.61; only 36 of 10,240 (block, expert) pairs never fire. Generic dossier
corpus: 74.1% / 92.5%, Gini 0.66. Routing is skewed but not sparse enough for a half-size hot cache (5.4 GiB) to
avoid a ~10% miss rate per assignment, i.e. ~55% of tokens would miss at least one of their 8 experts per block.
Moot on this card: all 10.7 GiB of experts are already resident, and experts are ~18% of per-token bytes.

### CPU/GPU expert split (`--n-cpu-moe 4`, i.e. 4 of 40 blocks' experts on the Ryzen 5900X)
Decode 101 -> 53 tok/s, decision turn 2.32 -> 3.36 s, trivial 0.46 -> 0.57 s, server CPU 31% of the machine, VRAM
freed only 1.1 GB. Even the smallest offload roughly halves generation: the Strata CPU-expert pool class of
technique is strictly negative on URI's hardware (consistent with the Q4_K_M `--fit` qualification run: 41 tok/s).

### Per-request fixed overhead (overhead.py, non-streaming, cached prompt, max_tokens 1)
Jinja template render 1.7-2.0 ms; tokenizing the 4,079-token decision prompt 6.6 ms; wall minus server
prompt+decode time 2.6-9.9 ms. The floor is the server's own smallest decode/prefill step: 43-45 ms for a 4-token
batch (one 40-block graph pass), i.e. ~4 decode-token equivalents. Grammar (JSON schema -> GBNF) costs nothing
measurable on the decision prompt: 9.89 vs 9.96 ms/token; the whole `nogrammar` run matched the grammar run
(decision 2.29 vs 2.32 s). `-ctk f16 -ctv f16`: decode 103.6 vs 101.4 tok/s, decision 2.26 vs 2.32 s (within noise;
VRAM cost noted below).
f16 KV peak VRAM 15,889 MiB vs 15,623 MiB for q8_0 (+266 MiB at 32k): the ~2% decode gain is not worth halving the
remaining VRAM headroom beside the vision projector.

### Cold/warm load (coldload.py; standby list evicted by reading 30 GiB of other files first)
| | HDD (D:) | NVMe (C: copy, hashes verified identical) |
|---|---|---|
| sha256 of the 13.68 GB GGUF, cold | 90.5 s | 17.1 s |
| llama-server to /health, cold (model + projector, 32k, vision) | 85.6 s | 16.0 s |
| llama-server warm | 6.4 s | 6.4 s |
| sha256 warm | 9.8 s | 9.9 s |
Raw unbuffered sequential read: HDD 120 MB/s, NVMe 1,964 MB/s. Warm numbers are identical because both come from the
OS file cache; hash verification is CPU-bound once cached (~1.4 GB/s).

### Correctness: production flags vs `--checkpoint-min-step 1024 --ctx-checkpoints 16` (run_bench.py, real Core seams, 32k, vision)
Base (fresh session): C 1.000, D 0.861, DG 0.861, F 1.000, H 1.000, L 0.933, O 1.000, P 12/12, S 1.000 - matches the
qualification report. Candidate: every suite score identical and 221/221 case outputs byte-identical (D/DG compared
on the first 600 characters the harness stores). D p50 2.585 -> 2.519 s. Two fresh server sessions produce identical
greedy outputs for every case, so the rep0/rep1 differences seen inside one bench_spec session are a within-session
second-occurrence effect (slot state after prompt-cache restore), not run-to-run GPU randomness.

### Stability defect: ngram-mod on the hybrid model hung (stock b11425 release, URI workload)
`--spec-type ngram-mod --spec-ngram-mod-n-match 24 --spec-ngram-mod-n-min 48 --spec-ngram-mod-n-max 64` with the
production flags: after 34 requests the slot started task 2280 (a proposer prompt) and produced no log line, no
tokens and no completion for 18 minutes (process CPU time kept growing; killed manually at 12:05). The previous
request had drafted 252 tokens with 12% acceptance (mean draft length 8.75). Log preserved as
`evidence/uri_engine/hang_ngram_mod_stock_b11425.log`. Long n-gram drafts on a recurrent model go through the
full-state checkpoint path (no `n_rs_seq` for n-gram types); whatever the exact cause, the stock configuration is
not stable enough for a resident service. A watchdog (`D:\uri-model-lab\watchdog.sh`) guards the remaining runs.
