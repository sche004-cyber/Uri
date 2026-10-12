# URI Resident Intelligence Runtime v1 — freeze record

Status: **FROZEN — URI Resident Intelligence Runtime v1** (qualification and soak passed 2026-10-07 00:14; verdict A — STOCK).
Date: 2026-10-06/07. Machine: Windows 11 Pro 26200, Ryzen 9 5900X, Radeon RX 7900 GRE 16 GB (driver 32.0.31041.1004),
24 GB RAM, C: NVMe, D: SATA HDD. Frozen Phase 1 Core untouched (121-file inventory and archive sha256 `31a34dcb...98cf7`
verified at the start, between passes and at the end of this milestone; `evidence/uri_engine/freeze_check_*.json`).
Nothing committed, pushed, merged, cut over or activated. All artifacts live under `model_lab/` and `D:\uri-model-lab\`.

> URI Resident Intelligence Runtime v1 is considered optimized and qualified for the current URI architecture and
> current hardware. Model/runtime optimization is CLOSED. It should not be reopened merely to search for marginal
> improvements. (Reopening criteria: section 14.)

Architecture: **Deterministic URI Core <-> Resident Intelligence -> optional External Harness.** One resident model
handles fast semantic interpretation, bounded reasoning, conversation, drafting, extraction, advisory routing and
vision. Runtime architecture verdict: **A — STOCK.** Stock optimized llama.cpp b11425 (official release binary) plus
URI prompt shaping and configuration; no fork, no patch, no dedicated engine, no Strata adaptation (sections 5, 13).

## 1. Exact artifacts

| item | value |
|---|---|
| model repository / revision | `unsloth/Qwen3.6-35B-A3B-GGUF` @ `a483e9e6cbd595906af30beda3187c2663a1118c` (Apache-2.0) |
| model file | `D:\uri-model-lab\models\unsloth__Qwen3.6-35B-A3B-GGUF\Qwen3.6-35B-A3B-UD-IQ3_S.gguf` (13.68 GB) |
| model sha256 | `66a3ca888ce13482b40c333db2432c0ebde3a7b13754fc29f0c6f5e89703ec66` |
| vision projector | `mmproj-F16.gguf`, sha256 `8971ee4f331ff0a4c609374f32984b3d4e6dc086c0aa35f1d637fad1829e887f` |
| MTP draft | `D:\uri-model-lab\mtp\mtp-qwen36-35b-a3b-Q4_K_M.gguf` (1.26 GB), exported from the HF checkpoint shards 1/25/26 with `convert_hf_to_gguf.py --mtp`; sha256 `40ca608fee5134ae13921007bbf5549acd5da5577852975491453983ccc08768` |
| runtime | llama.cpp **b11425** (commit `e117148`), official Windows x64 Vulkan release archive, sha256 `a3287ac487ab5d128aefddc507db31c087f2a41c6e03b01f37fbe0bc45e8717d`; `llama-server.exe` sha256 `4fdc1a67a8c1333429ea82186087a77db202fb588c2442dcdfa442b2182d0306`, `ggml-vulkan.dll` `3742b48f47a09eec0c04c27b8ff109e4ef125692822c0092bcec0235b9223210` |
| binary provenance | upstream release build (coopmat / integer-dot / bf16 Vulkan shaders present); no URI patch. The SDK-rebuilt stock (`build/stock2`) and patched (`build/rsseq2`) binaries are research evidence only (section 5) |
| Vulkan | AMD driver 32.0.31041.1004 (Vulkan 1.4); build-comparison toolchain: Vulkan SDK 1.4.363.0 (LunarG installer sha256 `94a82d378f7a5e3e54c9db7d2fb7016af136e14ac0a18dbf0f2f67a36352d141`, payload carved without installation, glslc shaderc v2026.4) |

## 2. llama-server flags (complete)

```
llama-server.exe -m <model> -c 32768 -ngl 999 -fa on -ctk q8_0 -ctv q8_0 -np 1 --host 127.0.0.1 --port <port>
  --jinja --reasoning-format deepseek --no-webui --load-mode none
  -b 2048 -ub 1024
  --cache-ram 2048 --slot-prompt-similarity 0 --checkpoint-min-step 512 --ctx-checkpoints 16
  --mmproj <mmproj-F16.gguf>
  -md <mtp-qwen36-35b-a3b-Q4_K_M.gguf> --spec-type draft-mtp --spec-draft-n-max 2 -otd token_embd.weight=CPU
```

| group | setting | why (evidence) |
|---|---|---|
| context | 32,768 tokens, one slot | qualification size; 16k gives the same decision latency (2.51 vs 2.49 s) |
| KV cache | q8_0 K/V, flash attention | f16 gains 2% decode for +266 MiB VRAM that the vision projector needs |
| batching | `-b 2048 -ub 1024` | prefill 1,830-2,100 tok/s; the ubatch is the invalidation cost unit (365-999 tokens) |
| prompt cache | `--cache-ram 2048 --slot-prompt-similarity 0` | always save the slot state before a different prompt; ~3 cached 30k states; return-to-context 14 s -> 0.6 s |
| checkpoints | `--checkpoint-min-step 512 --ctx-checkpoints 16` | a checkpoint at every message boundary of the v1 layout; new turn 1,025 -> 50 tokens |
| load | `--load-mode none` | frees the 13.7 GB host copy after upload (server RSS 0.8-1.8 GB) |
| MTP | `--spec-type draft-mtp --spec-draft-n-max 2` with the exported head | section 6: score-equivalent, 1.4-1.5x generation, decision 2.56 -> 2.21 s; n_max 2 is the largest draft that fits 32k + vision |

## 3. Context architecture and cache invalidation

See `model_lab/uri_engine/CONTEXT_ARCHITECTURE_V1.md` (normative). Summary: seven sections delivered as separate
messages from most stable to most volatile — `URI_SYSTEM`, `CAPABILITY_SCHEMA`, `PERMISSION_STATE` (one system
message), `SESSION_STATE` + `MEMORY_EVIDENCE` (acknowledged user message), `TASK_EVIDENCE` parts (acknowledged user
messages, most stable first), `CURRENT_TURN` (last user message). Authority never comes from the cache: a permission
or capability change bumps a version inside the system message and forces recomputation of everything after it
(measured excess 365-440 tokens); session changes recompute from the session message; evidence changes recompute
the changed part and later parts only; return to an earlier context is a 4-token restore; a server restart empties
every cache. Measured on the release binary with the final layout and the section-2 flags (`ctx_rel_final`,
median of two sequences, prompt tokens recomputed / excess over the logical change / TTFT through the lab client):

| URI situation | 4k | 16k | 30k |
|---|---|---|---|
| completely new context (A_fresh after another context) | 2,541 / 2,541 / 1.8 s | 11,944 / 11,944 / 6.3 s | 25,821 / 25,821 / 14.5 s |
| exact repeat (B) | 4 / 4 / 0.4 s | 4 / 4 / 0.5 s | 4 / 4 / 0.5 s |
| new user turn, unchanged context (C) | 49 / 23 / 0.41 s | 49 / 23 / 0.43 s | 49 / 23 / 0.44 s |
| one evidence block changed inside TASK_EVIDENCE part 3 of 3 (D) | 367 / 240 / 0.7 s | 3,398 / 169 / 2.3 s | 6,965 / 332 / 5.0 s |
| session-state change (S) | - | 11,972 / 69 / 6.4 s | 25,660 / 69 / 14.4 s |
| permission-state version bump (E) | 1,047 / 383 / 1.1 s | 12,418 / 383 / 6.5 s | 26,295 / 383 / 14.8 s |
| return to the earlier context after D, E or S | 4 / 4 / 0.45 s | 4 / 4 / 0.5 s | 4 / 4 / 0.6 s |

Reading: the only turns that pay a full prefill are genuinely new contexts and authority/session changes, and in
those the excess over the logical change is 69-383 tokens (< 0.2 s). Session state must therefore hold only slowly
changing facts (rule 4 of the invalidation rules); per-turn facts belong in the current turn.

## 4. Reasoning tiers (frozen policy)

| tier | thinking | use for | evidence |
|---|---|---|---|
| FAST | off (`enable_thinking: false`), temperature 0, grammar where the seam is structured | every Core seam (proposer, interpreter, route), conversation, simple drafting, extraction, classification, slot proposals, simple grounded answers, vision interpretation | decision contract 0.86 at 2.5 s; thinking adds 0-5 points at 3-5x latency; C/H/S/O 1.00 |
| NORMAL | on, `thinking_budget_tokens: 768`, at least 4,000 output tokens | multi-constraint reasoning, planning, difficult comparisons, conflicting evidence, harder debugging, tasks shown to benefit | hard reasoning 0.62 -> 0.88 at 12.7 s (qualification); on the frozen candidate R 1.000, RH 0.750 at 10.3 s p50 with MTP (section 6) |
| DEEP / unbounded | **never** | — | collapses the contract (0.33-0.38) and loops on hard problems (3/8 to 12k tokens, 85 s); refused in `LocalBrain.answer` |
| ESCALATE (external harness) | — | normal budget insufficient (`finish_reason == "length"` on the normal tier), multi-file coding/execution, builds/tests/deploy, document sets beyond the resident context, deep multi-source research, authenticated external tooling | qualification §1 item 10; `local_brain.json: escalate_to_harness` |

Deterministic / advisory selection rule URI should implement (Operational Intelligence milestone):
1. Core seams are FAST, always (deterministic, by seam).
2. A language task is FAST unless its classification is one of {analysis, planning, comparison, conflicting-evidence,
   debugging} (advisory route from the FAST tier, or an explicit Core task type), in which case NORMAL.
3. NORMAL that ends with `finish_reason == "length"` is reported as incomplete and becomes an ESCALATE candidate;
   it is never retried with a larger budget locally.
4. ESCALATE is a Core decision (harness availability, authentication, user approval); the model only advises.
5. The resident model cannot change its own budget: the budget is a server-side request parameter set by the
   provider from the tier, never from model output.

## 5. The checkpoint patch — final decision

**REJECTED. Runtime v1 uses stock llama.cpp b11425 without any URI patch.** The patch (`model_lab/uri_engine/patches/uri-ext-b11425.diff`,
7 lines in `tools/server/server-context.cpp` enabling mid-message checkpoints at ubatch granularity when
`--checkpoint-min-step < n_ubatch`, plus an unrelated `n_rs_seq` change for n-gram drafters) is preserved as
historical evidence.

Fair comparison (both binaries rebuilt with the Vulkan SDK 1.4.363.0 glslc; cooperative-matrix / integer-dot /
bf16 shaders present in both; SDK stock equals the official release binary: 1,822 vs 1,830 prompt tok/s, identical
`prompt_n`/`cache_n` in all 60 rows of the final layout), v1 context layout, 2 sequences x 3 sizes, release-class
timings, `context_reuse/TABLES_final_layout.md`:

| scenario (30k / 16k) | stock SDK build, v1 flags | patched, `-ub 2048 --checkpoint-min-step 1024 --ctx-checkpoints 16` | patched, `-ub 1024 --checkpoint-min-step 512 --ctx-checkpoints 32` |
|---|---|---|---|
| new turn | 49 tokens, 0.45 s | 49, 0.46 s | 49, 0.46 s |
| evidence changed inside part 3/3 (excess) | **332 / 169** | 1,087 / 673 | 332 / 189 |
| permission change (excess) | **383 / 383** | 1,990 / 1,403 | 379 / 379 |
| return to a previous context | **4 tokens, 0.6 s** | 7,722 tokens at 30k (5.7 s) | 6,967 / 3,444 tokens (5.0 / 2.6 s) |
| prefill tok/s (30k fresh) | 1,822 | 1,784 | 1,753 |
| server RSS / min free RAM | 3.3 GB / 7.5 GB | 4.5 GB / 6.1 GB | 4.1 GB / 6.1 GB |

Against the five retention criteria: (1) improvement is not material on realistic URI workloads: with the v1
message layout the stock server already resumes within one evidence part (excess 142-380 tokens, 0.1-0.2 s), and
the patch is equal or worse in every row; (2) correctness is unaffected either way (token counts, suite scores);
(3) memory is worse (+0.8-1.2 GB RSS for the checkpoint ladder); (4) maintenance cost of carrying a server patch
across upstream releases is not justified by a zero gain; (5) URI prompt shaping captures all of the benefit
(the earlier "227-739 excess tokens" result of the patch was measured against a single-message layout that URI
will not use). Stock wins outright; no "maybe later" remains.

## 6. MTP / speculative decoding — final decision

**ACCEPTED.** Final parameters: `-md D:\uri-model-lab\mtp\mtp-qwen36-35b-a3b-Q4_K_M.gguf --spec-type draft-mtp
--spec-draft-n-max 2 -otd token_embd.weight=CPU` (the exported single MTP head, Q4_K_M, its token embedding kept on
the CPU; 2 draft tokens per round, the largest draft that fits the 32k + vision VRAM budget).

Qualification on the exact candidate (release binary, section-2 flags, 32k, vision loaded; `ue_cand` vs `ue_cand_mtp2`,
`ue_cand_normal` vs `ue_cand_mtp2_normal`; contract/semantic scoring, not byte identity):

| suite (path) | without MTP | with MTP n_max 2 | p50 latency | generation |
|---|---|---|---|---|
| D decision contract / DG with grammar (fast) | 0.861 / 0.861 | 0.861 / 0.861 | 2.56 -> 2.21 s | 101 -> 141 tok/s |
| C grounded answers (fast) | 1.000, 0 hallucinations | 1.000, 0 | 0.99 -> 0.90 s | 104 -> 141 |
| H routing (fast) | 1.000, 0 over/under-escalation | 1.000, 0 | 0.83 -> 0.73 s | 104 -> 136 |
| S extraction (prompt + grammar) | 1.000 / 1.000 | 1.000 / 1.000 | 1.31 -> 1.00 s | 104 -> 157 |
| O drafting | 1.000 | 1.000 | 1.96 -> 1.72 s | 104 -> 153 |
| F trivial turns | 1.000 | 1.000 | 0.45 -> 0.43 s | 99 -> 127 |
| L long context 4k / 12k / 28k | 0.933 | 0.933 | 7.4 -> 7.5 s (prefill-bound) | 97 -> 142 |
| P Phase 1 production-adapter loop | 12/12 | 12/12 | - | - |
| V vision (VLM) | 5/5 | 5/5 | 0.70 -> 0.76 s | - |
| R reasoning (fast / normal) | 0.958 / 1.000 | 0.958 / 1.000 | 4.8 -> 3.2 s / 8.2 -> 6.1 s | 105 -> 152 / 105 -> 150 |
| RH hard reasoning, NORMAL tier (policy path) | 0.750 (rh3, rh7 wrong) | 0.750 (rh3 wrong, rh6 knapsack hits the cap) | 13.5 -> 10.3 s | 105 -> 149 |
| RH hard reasoning, FAST path (not a policy path) | 0.875 (1 truncated) | 0.625 (3 truncated at the 3,000-token cap) | 13.9 -> 10.8 s | 105 -> 151 |
| errors | 0 | 0 | | |
| peak VRAM / server RSS | 15,614 MiB / 0.9 GB | 15,771 MiB / 2.3 GB | | |

Reading: every contract, grounding, routing, extraction, drafting, long-context, loop and vision score is identical;
score-changing cases across the 221-case fast suite: 0. The one difference is on the FAST path of the 8-case hard
reasoning suite, where long free-form chain-of-thought answers are brittle against the token cap and the MTP path
(greedy-equivalent up to near-tie numerics, section 7) pushed two more of them over it. That path is excluded by the
reasoning policy (hard reasoning runs on NORMAL, where the score is unchanged and 24% faster) and the two
long-search cases (knapsack, rooms) are the documented escalation class. Stability: 0 errors across the suites and
the soak (section 12); memory: +157 MiB VRAM, +1.4 GB RSS, within the envelope (section 9). Decode gain on real URI
turns: decision 2.51 -> 2.05 s (uri_mtp3_16k) and 2.56 -> 2.21 s in the suite; generation 1.4-1.5x.

n-gram speculation (ngram-simple, ngram-map-k, ngram-mod): REJECTED / SUPERSEDED (research report section 6).

## 7. Determinism policy

Rule: **Deterministic guarantees belong to URI Core. Neural inference is not required to be byte-identical.
Resident Intelligence must satisfy deterministic contracts, schemas, grounding rules, safety/authority gates and
qualification thresholds.** The 188-vs-192-token anomaly is closed: identical greedy requests diverge at a near-tie
token (top-2 margin 0.0019 nat) because the Vulkan kernels' floating-point accumulation depends on the ubatch
layout (checkpoint boundaries, `-ub`) and shows run-to-run jitter; `cache_n` was 0 in every occurrence, restored
states reproduce their own outputs, and three fresh production sessions agree on all 220-221 suite cases. Byte-for-byte
equality is not an acceptance criterion for the Brain unless a specific operation genuinely requires it (none does
today: Core re-validates every structured field, grounds every slot, and gates every action).

## 8. HTTP client behaviour

`model_lab/integration/local_brain.py: BrainClient` — one persistent HTTP/1.1 keep-alive pool per server (max 4
keep-alive connections, 300 s expiry), reconnect once on transport error. Measured: client overhead 2.5 ms (trivial)
and 10.6 ms (cached decision turn) instead of 234-238 ms with a new client per request; decision turn 2.17 -> 1.95 s
wall; after a server restart the first call fails with `ConnectError` while the server is down and the next call
succeeds in 0.63 s once it is healthy. Streaming is not used for structured seams (non-streaming JSON); the server's
SSE path itself adds only ~4 ms when streaming is wanted for user-visible prose.

## 9. Memory / VRAM / RAM envelope

| resource | value on the candidate | source |
|---|---|---|
| dedicated VRAM, 32k + vision + MTP, peak | 15,772-15,828 MiB of 16,368 (includes ~1.0-1.1 GB of desktop use after the day's reboot; the server's own share is ~14.7 GB) | `ue_cand_mtp2`, `uri_cand_mtp2` |
| dedicated VRAM without MTP | 15,614 MiB | `ue_cand` |
| server RSS, steady | 2.3-3.3 GB (prompt cache 2 GiB limit + checkpoints 16 x 63 MiB + draft host tensors) | `ue_cand_mtp2`, `ctx_rel_final` |
| server RSS, peak in the URI session with vision + several cached contexts | 4.7 GB | `uri_cand_mtp2` |
| system RAM left for everything else | >= 19 GB of 24 GB by the server's own footprint; observed minimum free RAM 5.9-7.5 GB with the lab's desktop load (Claude, browser, IDE) | same runs |
| host RAM growth over the 77-minute mixed soak | +10 MiB (4,305 -> 4,315 MiB server RSS; max 4,317 MiB outside the reload) | `soak_final` |
| CPU | server mean 0.3-2 % of the 12-core machine; prefill and decode are GPU-bound | telemetry CSVs |
| disk | model 13.68 GB + projector 0.84 GB + draft 1.26 GB on D: (HDD); page cache of ~14 GB keeps warm loads at 6-9 s when RAM allows | `coldload_*.json` |

Budget rule carried into v1: the prompt cache stays at 2 GiB and checkpoints at 16 so that the server's host
footprint stays under ~5 GB; raising either is a reopening decision (section 14), not a tuning knob.

## 10. Expected latency (release binary, persistent client)

Measured on the exact candidate (`uri_cand_mtp2`: the real URI session of 12 proposer decisions, 8 interpreter
calls, 4 answers, 6 trivial turns, 2 vision turns, 32k, vision loaded, MTP on; `ue_cand_mtp2` suites; `ctx_rel_final`).
Lab-client numbers include ~0.2 s of per-request client construction that the persistent provider removes
(section 8); the "URI provider" column subtracts the measured 234 ms where the row is a single request.

| turn | server prompt / decode | lab client total p50 | expected with the persistent provider |
|---|---|---|---|
| decision turn (Core system prompt cached, ~1,024 new request tokens, 100-175 generated) | 0.53 s + ~1.1 s | 1.91 s (TTFT 0.87 s) | ~1.7 s |
| repeat of the same decision prompt | 0.05 s | 1.25 s | ~1.0 s |
| interpreter call (verbatim slot proposal) | 0.16 s + 0.2 s | 0.62 s | ~0.4 s |
| resolved-context answer | 0.20 s + 0.5 s | 1.00 s | ~0.8 s |
| trivial conversational turn | 0.14 s + 0.03 s | 0.47 s | ~0.25 s |
| vision turn (one 768-px image + question) | 1.98 s (image encode) + 0.3 s | 2.48 s | ~2.3 s |
| new user turn on a cached 30k context | 0.17 s | 0.44 s (TTFT) | ~0.25 s |
| return to a previously seen 30k context | 0.06 s | 0.6 s (TTFT) | ~0.4 s |
| changed evidence part at 30k (~6.6k new tokens) | 4.5 s | 5.0 s (TTFT) | ~4.8 s |
| completely new 4k / 16k / 30k context | 1.1 / 5.9 / 14.0 s | 1.4 / 6.3 / 14.5 s | same minus 0.2 s |
| NORMAL-tier hard reasoning (768-token budget) | - | 10.3 s p50 | - |
| generation | 142 tok/s on decisions (MTP), 127-157 tok/s across suites; 96-105 tok/s without MTP | | |
| warm load / cold load from the D: HDD | 6-9 s / 84-100 s | | |

## 11. Qualification evidence

All runs on the exact candidate (section 1 artifacts, section 2 flags, release binary, 32k context, vision loaded,
MTP on unless the row says otherwise), evidence under `model_lab/evidence/runs/ue_cand*/` and
`model_lab/evidence/uri_engine/`. Scoring is deterministic contract/semantic scoring (code-checked keys, real Core
seams for D/DG/P); byte identity is not a criterion (section 7).

| boundary item | run | result |
|---|---|---|
| 221-case suite, fast path (F, D, DG, C, H, S, O, L, P) | `ue_cand_mtp2` (and `ue_cand` without MTP) | C 1.000, D 0.861, DG 0.861, F 1.000, H 1.000, S 1.000, O 1.000, L 0.933, P 12/12; identical to the qualification baseline (`ue_base`) and to the no-MTP candidate; 0 score-changing cases; 0 errors |
| Phase 1 12/12 production-adapter loop (clarification -> confirmation -> approval -> signed ticket -> execution -> verification -> persistence; injected approval, typed "confirm", destructive request, ungranted harness) | suite P in `ue_cand`, `ue_cand_mtp2` | 12/12, proposer_invalid 0 (both) |
| decision contracts | D/DG | 0.861 (golden 0.912, extra 0.667), 0 invalid, p50 2.21 s with MTP |
| groundedness / resolved-state answers | C | 1.000, 0 hallucinations |
| clarification / intent interactions | P scenarios p01-p12 (Intent Discovery), H routing | 12/12; H 1.000 with 0 over- and 0 under-escalation |
| conversation, drafting, extraction | F, O, S | 1.000 / 1.000 / 1.000 (prompt and grammar) |
| fast reasoning | R fast | 0.958 (r05 half credit) |
| normal bounded reasoning (768-token budget) | `ue_cand_mtp2_normal` | R 1.000, RH 0.750 (knapsack hits the cap = escalation class) |
| vision | V (5 VLM cases) | 5/5 (1.000); the OCR-path comparison scores 0.467, confirming the VLM path |
| 4k / 16k / ~30k context | L 4k/12k/28k and the final-layout context runs at 4k/16k/30k | L 0.8 / 1.0 / 1.0 (the known ordinal miss at 4k); context runs 0 errors |
| repeated-prefix reuse, changed evidence, changed permission state, changed session state, return to previous context | `ctx_rel_final` (section 3 table) | 4 / 49 / 3.4k-7.0k / full+383 / full+69 / 4 tokens respectively; outputs of restored states identical to their fresh computation |
| malformed model output | Core seam behaviour (qualification §6: `BRAIN_OUTPUT_INVALID`, never substituted) re-exercised by P and DG grammar runs; 0 invalid decisions in 144 D/DG calls | pass (Core reports, never executes) |
| restart / reconnect | `client_overhead.json`, `soak_final.json` | first call while down: `ConnectError`; first call after restart succeeds (0.63 s) with one retried request |
| MTP correctness | section 6 | score-equivalent on all contract suites and the NORMAL tier |
| memory / VRAM stability, repeated-inference soak | section 12 | 77 min, 1,036 calls, 0 errors, 0 invalid, RSS flat (4,305 -> 4,315 MiB), VRAM max 15,851 MiB, no latency drift, no Windows hardware/driver events |
| Phase 1 freeze | `freeze_check_runtime_v1.json` | 121/121 inventory files identical, archive sha256 matches (also at every earlier pass boundary) |

## 12. Stability evidence

`soak_final.py` on the exact candidate (release binary, section-2 flags with MTP, 32k, vision loaded, persistent
`BrainClient`), 2026-10-06 22:57 to 2026-10-07 00:14 (77 min, 68 cycles, 1,036 sequential calls), per-cycle host
telemetry and the queue runner's 3-second telemetry (`queue_logs/telemetry_soak_final_*.csv`):

| item | result |
|---|---|
| mixture per cycle | 3 fast trivial turns, 1 decision contract (grammar), 1 extraction, 1 drafting, 1 grounded answer, 1 NORMAL-tier reasoning task, a 16k cached-context sequence (fresh, repeat, new turn, changed evidence, changed session state, back to the first context), 1 vision turn; every 4th cycle a 90 s idle pause followed by a decision turn |
| calls / errors / invalid structured outputs / HTTP failures | 1,036 / **0** / **0** / 0 |
| decision contract p50 (4,079-token first-sight prompt, prompt cache evicted by the 16k contexts) | 3.22 s, first third 3.22 s, last third 3.22 s; 147 tok/s; after a 90 s idle: 3.21 s (no wake penalty) |
| 16k context: repeat / new turn / changed evidence / back to first context | 0.64 s / 0.60 s / 2.64 s / 2.71 s (cache_n 16,056 / 16,008 / 12,759 / 12,759) |
| NORMAL reasoning p50 | 6.54 s (first third 6.55, last third 6.54) |
| vision p50 | 1.64 s |
| latency drift (first third vs last third, every kind) | none (all within 10 ms) |
| server RSS first / last / max | 4,305 / 4,315 / 4,317 MiB (flat; peak 4,969 MiB during the restart's reload) |
| dedicated VRAM max | 15,851 MiB (15,864 during reload) |
| min free system RAM | 4.9 GB during the reload, 5.5 GB otherwise (lab desktop load present) |
| server restart + client reconnect (mid-run, 23:36-23:38) | call while down: `ConnectError`; reload 92 s (cold HDD); first call after restart 0.70 s, HTTP 200, drafts 6/6 accepted |
| Windows System log during the run (41, 1001, 4101/4102, 6008, WHEA, Critical) | none |
| GPU after the run | returned to the desktop idle level; no llama-server process left |

No unexplained freeze, hang, allocation failure or driver event occurred under the final candidate during the soak
nor during the 4 h 20 min of pass-2/3/4 runs on the same binary and model (31 + 13 queue entries). The single
unexplained machine freeze of 2026-10-06 12:06 (stock ngram-mod run, CAUSE UNKNOWN) involved a configuration that
is rejected and not part of v1; the 14:25 interruption was an external power outage. Stability of the frozen
configuration is therefore evidenced by this soak and the day's run history, with the limitation that no GPU
temperature telemetry exists on this machine.

## 13. Rejected alternatives (closed)

| alternative | verdict | evidence |
|---|---|---|
| Qwen3.6-35B-A3B UD-Q4_K_M | REJECTED: does not fit 16 GB; experts on CPU give 41 tok/s, 6.1 s decisions, 0.6 GB free RAM | qualification §8 |
| Qwen3.8-27B (dense) | REJECTED as primary and as second model: 26-30 tok/s, 7.6-8.4 s decisions, no hard-reasoning gain over the selected normal tier, cannot co-reside | qualification §4, §8 |
| gpt-oss-20b | REJECTED: long context 0.60, no reasoning-off switch, grammar required, no vision | qualification §8 |
| Gemma-4-26B-A4B QAT | REJECTED: decisions 0.80, long context 0.73, half the prefill, unbounded thinking loops | qualification §8 |
| Ollama deployment (gemma4:12b, qwen3.5:9b) | REJECTED: thinking cannot be disabled, 4,096 default context, 0/70 valid decisions | qualification §4.1 |
| second resident reasoning model | REJECTED: no candidate beats the selected model's bounded tier; none co-resides in 16 GB | qualification §1 item 6 |
| tiny router (Qwen3.5-2B) | REJECTED: decisions 0.31, routing 0.55, only 0.5 s faster | qualification §8 |
| separate vision specialist | REJECTED: the resident model + 0.84 GB projector scores 5/5 against an OCR path that fabricates | qualification §4.3 |
| deep / unbounded reasoning | REJECTED: contract collapse and loops | qualification §4.2 |
| ngram-simple / ngram-map-k / ngram-mod | REJECTED / SUPERSEDED by MTP | research §6 |
| Qwen3.6 Q4_K_M `--fit`, `-np 3 -kvu`, `--n-cpu-moe`, f16 KV | REJECTED: RAM/VRAM/speed trade-offs measured negative | research §5, §7 |
| dedicated Strata port | NOT APPLICABLE: Strata solves non-resident experts for a 125B model on 12 GB (CUDA/HIP only); URI's model is resident on Vulkan; its one relevant technique (conversation checkpoints) is already in llama.cpp | research §8 |
| dedicated URI inference engine | REJECTED: decode is launch-bound at ~100 tok/s with experts ~18% of per-token bytes; the Vulkan backend has every Qwen3.6 kernel; a new engine would start without cooperative-matrix shaders | research §10 |
| URI-maintained llama.cpp fork | REJECTED: every gain is a flag, a prompt shape or (at most) a 7-line patch | research §10, this record §5 |

## 14. Reopening criteria

Valid: a material URI workload failure; a reproducible correctness defect of the frozen runtime; an unacceptable
stability problem under realistic use; a new capability requirement the frozen runtime cannot satisfy; a meaningful
hardware change (VRAM, RAM, GPU vendor); a materially superior model or runtime technology supported by evidence on
URI's own suites; a major upstream inference improvement with a credible, measured expected benefit for URI.

Invalid: curiosity; marginal benchmark gains; a newly released model without evidence of URI benefit; preference for
a larger parameter count; theoretical optimization without a demonstrated URI bottleneck.

## 15. Known limitations

- Decision contract 0.86 (two implicit-disclosure and two drafting golden cases lean to `conversation`/`clarification`);
  Core gates prevent harm.
- Hard reasoning needs the NORMAL tier (0.88); long-search problems must escalate.
- IQ3_S is a 3-bit quant: ~1-4 points below Q4_K_M in exchange for a full-GPU fit.
- VRAM headroom at 32k + vision is ~0.1-0.8 GB depending on desktop GPU use; a large desktop GPU consumer could force
  a reload (ctx 16k frees ~0.4 GB).
- Cold load from the D: HDD is 83-100 s; warm 6-9 s; the files should be placed on C: (NVMe, 16 s cold) at cutover.
- Host RAM for the prompt cache and checkpoints: ~2-3.5 GB over the bare server; the desktop floor of 10 GB free is
  kept at the chosen settings (section 9); under mixed traffic the 2 GiB cache holds about three 16k states, so a
  context revisited after several other large contexts resumes from its nearest part boundary (12,759 of 16,060
  tokens, 2.7 s in the soak) rather than in 4 tokens (section 12).
- No GPU temperature telemetry exists on this machine; stability evidence is utilisation/VRAM/RAM/event-log based.
- One machine freeze on 2026-10-06 remains CAUSE UNKNOWN (the second interruption was an external power outage).

## 16. Rollback / reproduction

- Reproduce the runtime: verify the model sha256, start `llama-server` with the flags of section 2 from the pinned
  release archive (`D:\uri-model-lab\runtime\llama-b11425-bin-win-vulkan-x64\`), load `local_brain.json`.
- Reproduce the qualification: `.venv\Scripts\python.exe model_lab\run_bench.py --name ue_cand --model <gguf> --mmproj
  <mmproj> --family qwen --ctx 32768 --ngl 999 --paths fast --suites F,D,DG,C,H,S,O,R,RH,L,P,V --l-sizes 4000,12000,28000
  --extra "<flags of section 2>"`; normal tier: `--paths normal --suites R,RH`; context reuse:
  `model_lab\uri_engine\bench_context_reuse.py --name ctx_rel_final --extra "<flags>" --layout final`; soak:
  `model_lab\uri_engine\soak_final.py --minutes 75`; freeze check: `model_lab\verify_freeze.py`.
- Rollback: the previous production configuration (qualification report §1: `--cache-ram 1024`, no
  `--slot-prompt-similarity`, default checkpoints, no MTP) is a strict subset of section 2 and remains valid; it loses
  only the context-reuse and MTP gains.
- Evidence index: `model_lab/evidence/uri_engine/` (queue manifest and summary, context-reuse runs and tables,
  determinism probes, stream/client probes, MTP fit tests, crash records and corrections, freeze checks, soak),
  `model_lab/evidence/runs/ue_*` (suite runs), `model_lab/URI_ENGINE_STRATA_RESEARCH.md`, `model_lab/MODEL_QUALIFICATION_REPORT.md`.

## 17. Closure record (2026-10-07 00:25 IST)

### 17.1 Queue resolution — every entry terminal

`evidence/uri_engine/queue_manifest.json` / `QUEUE_SUMMARY.md`: 45 entries, **43 done, 2 rejected_superseded;
0 pending, running, blocked or interrupted.**

| entry | terminal state | basis |
|---|---|---|
| `uri_ngram_mod16` (stock ngram-mod n_max 16 on the URI session) | REJECTED / SUPERSEDED, not rerun | resolved from existing evidence: ngram-mod first-sight speed = baseline on URI-shaped tasks (0.98-1.01x), repeat gains are answer memorisation, the stock path hung the server for 18 min, ngram-simple drafted nothing on 42 URI requests; MTP n_max 2 is the accepted, score-equivalent gain. No material first-sight, task-relevant improvement that would change the selected runtime |
| `ux_ngram_mod8` (patched rs-seq n-gram path) | REJECTED / SUPERSEDED, not rerun | the rs-seq patch changes only how n-gram drafts roll back recurrent state; it cannot create drafts where none exist. Patch retained as evidence only; Runtime v1 is stock |
| `ctx_sb2_prod` | done (attempt 2) | attempt 1 failed on a harness defect (`KeyError: 'S'`: the final layout had just gained scenario S, the pre-built single-layout prompts had none); attempt 2 (00:15-00:21, started by a parallel session after the soak) completed and duplicates `ctx_sb2_final`'s binary-equivalence evidence; no decision rests on it |

### 17.2 Final decisions

- **Selected production candidate:** section 1 artifacts + section 2 flags, exactly:
  `llama-server.exe -m Qwen3.6-35B-A3B-UD-IQ3_S.gguf -c 32768 -ngl 999 -fa on -ctk q8_0 -ctv q8_0 -np 1 --host 127.0.0.1
  --jinja --reasoning-format deepseek --no-webui --load-mode none -b 2048 -ub 1024 --cache-ram 2048
  --slot-prompt-similarity 0 --checkpoint-min-step 512 --ctx-checkpoints 16 --mmproj mmproj-F16.gguf
  -md mtp-qwen36-35b-a3b-Q4_K_M.gguf --spec-type draft-mtp --spec-draft-n-max 2 -otd token_embd.weight=CPU`
  on the official llama.cpp b11425 Windows x64 Vulkan release binary, with the v1 context layout
  (`CONTEXT_ARCHITECTURE_V1.md`), the persistent `BrainClient`, and the FAST/NORMAL/ESCALATE policy of section 4.
- **7-line checkpoint patch: REJECTED** (section 5). On the v1 layout stock is equal or better in every measured row
  and uses 0.8-1.2 GB less RSS; a fork or carried patch has no material real-work benefit to justify its maintenance.
- **n-gram speculation: CLOSED, REJECTED / SUPERSEDED** by MTP (section 6; research report section 6).
- **Strata investigation: CLOSED.** Architectural concepts harvested (conversation-cache checkpoints, MTP verify,
  cost-aware draft policy, deterministic memory planning); none justifies a Strata-style engine: URI's model is fully
  resident on Vulkan, Strata's gains target non-resident experts on CUDA/HIP (research report section 8; verdicts C
  fork, D dedicated engine and E Strata adaptation all rejected / not applicable).
- **Machine interruptions:** second (14:25-18:18) = OS-observed unexpected power loss (`Kernel-Power 41`, BugcheckCode
  0, no WHEA/TDR/minidump) with user-supplied cause **external electrical power outage**; not Vulkan or runtime
  instability; excluded from the stability assessment (`crash_record_correction_20261006.json`). First (12:06-13:30)
  stays **CAUSE UNKNOWN**; no new evidence appeared during the day's remaining ~45 server sessions or the soak.
- **Session continuity:** the pre-crash session, the 13:50 recovery session (its own background runs were orphaned by
  the 14:25 outage) and the 18:35-00:21 continuation sessions all resumed from the same durable manifest: every `done`
  entry carries start/end, exit code, model and binary sha256 and verified outputs; the one entry caught by the outage
  (`ctx_prod_split`, attempt 1) was marked interrupted and re-run once; no completed experiment was repeated for lack of
  a record and none was lost (`QUEUE_SUMMARY.md`, `crash_recovery_20261006*.json`, `recovery_final_20261006.json`).

### 17.3 Acceptance gates

| gate | result |
|---|---|
| 221-case fast suite identical to the qualification baseline, 0 score-changing cases, 0 errors (with and without MTP) | PASS (`ue_cand`, `ue_cand_mtp2`) |
| Phase 1 production-adapter loop 12/12 | PASS |
| NORMAL tier reasoning unchanged with MTP (R 1.000, RH 0.750) | PASS |
| vision 5/5 | PASS |
| context reuse: repeat 4 tokens, new turn 49, evidence change within one part, authority/session change fully invalidated, return to context 4 tokens | PASS (`ctx_rel_final`) |
| 75-minute mixed soak with idle pauses and a restart: 0 errors, 0 invalid outputs, no memory growth, no latency drift, no OS events | PASS (77.3 min, 68 cycles, 1,036 calls; section 12) |
| VRAM <= 16 GB with 32k + vision + MTP; host RSS < 5 GB | PASS (15.9 GB peak; 4.3 GB) |
| frozen Phase 1 Core untouched before, between and after | PASS (`freeze_check_runtime_v1.json` 121/121 at 00:14:40; `git status` 90 entries and `git diff` identical to the pre-research baseline; `uri_core/` unchanged) |
| experimental processes stopped, GPU back to idle | PASS (no `llama-server.exe`; dedicated VRAM 1,065 MiB = desktop only, 00:22) |
| no commit, push, merge, cutover, Core change or Operational Intelligence implementation | PASS (`model_lab/` is untracked research; nothing committed) |

### 17.4 Verdict

**URI Resident Intelligence Runtime v1 — FROZEN.** Brain Runtime v1 = stock optimized llama.cpp b11425 (official
release) + Qwen3.6-35B-A3B-UD-IQ3_S + mmproj-F16 + exported MTP head (n_max 2) + the v1 flags, context layout,
persistent client and reasoning policy above. Benchmarking, model hunting, cache experimentation, speculative-decoding
experiments and runtime tuning stop here. Reopen only under section 14: a material real-work failure, a reproducible
correctness or stability defect, a new required capability, a meaningful hardware/runtime change, or a materially
superior technology supported by evidence on URI's own suites.

## 18. Transition

Next milestone: **URI Operational Intelligence Integration** — cache-aware Context Bridge (section 3 layout),
persistent Brain provider (section 8), fast/normal reasoning selection (section 4), responder/conversation seam,
capability-state awareness, the Observe -> Propose -> Core Validate -> Execute -> Observe -> Finish loop, operational
memory/learning, controlled vision/tool observations, external-harness escalation. Not started in this milestone.
