# URI Local Inference Optimization — Recovery and Reproduction (2026-10-08)

Question from the owner: an earlier local inference experiment ("Ollama.cpp optimization") reportedly reached about
140 tokens/second on the Radeon RX 7900 GRE. Which engine and change produced it, does it still exist, is it
reproducible, what does the number measure, and does it help URI's Brain workload?

## 1. Acceptance criteria (set before the investigation)

1. The source of the ~140 tok/s figure is identified from primary evidence (run logs, configs, binaries), not memory.
2. Engine, backend, model, quantization, context, flags and generation conditions are stated exactly.
3. The metric is classified (decode vs prompt processing vs end-to-end).
4. Every pinned artifact is re-hashed; the result is reproduced on today's machine against an unmodified baseline
   under the same settings, with correctness scores, prompt processing, memory and errors — not tok/s alone.
5. A newly created optimization is never presented as the recovered original.
6. Integration into URI happens only through the configurable inference adapter, without Core governance changes;
   if that is not possible without new work, the gap is stated.

## 2. Findings

| Question | Answer | Evidence |
|---|---|---|
| Which engine? | **llama.cpp b11425** (commit `e117148`), the **official Windows x64 Vulkan release binary** — not Ollama, not ROCm/HIP, not a custom build | `model_lab/URI_RESIDENT_INTELLIGENCE_RUNTIME_V1_FREEZE.md` §1; `local_brain.json` |
| Which modification produced the gain? | **MTP speculative decoding**: the model's own multi-token-prediction head exported to GGUF (`convert_hf_to_gguf.py --mtp`, Q4_K_M, 1.26 GB) and run with `--spec-type draft-mtp --spec-draft-n-max 2 -otd token_embd.weight=CPU`. It is a configuration of stock llama.cpp, not a code patch | freeze record §6 |
| What about the "patch"? | A 7-line checkpoint patch (`model_lab/uri_engine/patches/uri-ext-b11425.diff`) was tested on SDK rebuilds and **REJECTED** (equal or worse). It is unrelated to the tok/s figure. n-gram speculation also REJECTED | freeze record §5, research §6 |
| Model / quantization | `unsloth/Qwen3.6-35B-A3B-GGUF` @ `a483e9e6…`, `UD-IQ3_S` (13.68 GB, MoE, 3B active) + `mmproj-F16` vision projector | freeze record §1 |
| Context / settings | `-c 32768 -ngl 999 -fa on -ctk q8_0 -ctv q8_0 -np 1 -b 2048 -ub 1024 --cache-ram 2048 --slot-prompt-similarity 0 --checkpoint-min-step 512 --ctx-checkpoints 16 --load-mode none`, vision loaded, single slot | freeze record §2 |
| Hardware | Ryzen 9 5900X, RX 7900 GRE 16 GB (driver 32.0.31041.1004 — unchanged today), 24 GB RAM; model on D: (HDD) | freeze record header; `Win32_VideoController` today |
| What does "~140 tok/s" measure? | **Sustained decode (generation) throughput per request**, median, on URI's own suites (decision contracts 141, extraction 156, reasoning 152). Prompt processing is a separate figure (~1,900–2,050 tok/s). Without MTP decode is ~100 tok/s | frozen runs `ue_cand`, `ue_cand_mtp2` |
| Does it help URI's Brain workload? | Yes, measured on URI's suites at **identical scores**: decision turn 2.56 → 2.21 s, extraction 1.31 → 1.00 s, normal-tier reasoning 13.5 → 10.3 s; a 77-minute soak with 0 errors | freeze record §6, §12 |
| Still present? | Yes. All five pinned artifacts re-hashed today and match (model, mmproj, MTP head, `llama-server.exe`, `ggml-vulkan.dll`) | `docs/evidence/consolidation/inference_repro_20261008/runtime_hashes.json` |
| In Git? | Yes: research, configs, scripts and run evidence in `model_lab/` since `f791d65` (tag `accepted/runtime-v1-freeze-20261007`); binaries and models are not in Git (pinned by SHA-256 on `D:\uri-model-lab`) | — |

The earlier Ollama deployment of other models was measured and **rejected** for URI (thinking cannot be disabled,
4,096 default context, 0/70 valid decisions; freeze record §13). The ~140 figure never came from Ollama.

## 3. Reproduction on 2026-10-08 (this consolidation)

Same release binary, model, projector, MTP head and flags; 32k context, vision loaded; suites F, D, DG, C, H, S, O,
R, P, V (260 cases each run); runner `model_lab/run_bench.py` from the Phase 1 integration worktree; runs
`repro20261008_mtp2` (15:08) and `repro20261008_nomtp` (15:19). Frozen comparators: `ue_cand_mtp2`, `ue_cand`
(2026-10-06). Values are medians; scores are contract/semantic scores.

| Suite | Score (all four runs) | Decode tok/s frozen no-MTP → MTP | Decode tok/s today no-MTP → MTP | p50 latency today no-MTP → MTP |
|---|---|---|---|---|
| D decision contract | 0.861 | 101.0 → 141.2 | 98.3 → 133.8 | — |
| DG decision + grammar | 0.861 | 100.8 → 139.7 | 98.1 → 132.7 | — |
| C grounded answers | 1.000 | 103.9 → 141.7 | 100.8 → 134.5 | 1.11 → 0.99 s |
| H routing | 1.000 | 103.8 → 136.6 | 100.2 → 127.9 | 0.90 → 0.81 s |
| S extraction | 1.000 | 104.1 → 156.2 | 101.2 → 146.9 | 1.30 → 1.09 s |
| O drafting | 1.000 | 104.3 → 139.5 | 101.7 → 131.6 | 1.94 → 1.60 s |
| F trivial turns | 1.000 | 99.2 → 128.2 | 94.7 → 123.3 | 0.51 → 0.49 s |
| R reasoning (fast) | 0.958 | 104.6 → 152.3 | 102.0 → 143.8 | 4.77 → 3.41 s |
| P Phase 1 production-adapter loop | 12/12 | — | — | — |
| V vision (VLM 5/5; the OCR comparison path 0.467) | 0.733 combined | — | — | 0.79 → 0.99 s |
| **All cases** | errors 0 in every run | **101.0 → 141.2** | **98.3 → 133.2** | — |

Other measurements today: prompt processing on decisions 2,047 (no-MTP) / 1,871 (MTP) tok/s; MTP draft acceptance
85.2 % (21,799 / 25,580; frozen run 86.8 % over a larger suite set including L and RH); load 84.6 / 83.5 s from the
HDD; peak dedicated VRAM 15,108 MiB (no-MTP) / 16,127 MiB (MTP) of 16,368; peak server RSS 0.92 / 1.21 GB; minimum
free system RAM 10.4 GB.

Reading:
- **Recovered and reproduced.** The MTP configuration still gives a 1.28–1.45× decode speed-up by suite (1.36× on decisions) with every score
  identical and zero errors. Today's absolute decode figures are 2–7 % below the 2026-10-06 runs in both arms.
  Possible contributors, not isolated: the legacy URI server and the Ollama app were running, and the MTP run's
  peak VRAM was 356 MiB higher (VRAM headroom 241 MiB). No cause is claimed. The figure "~140 tok/s" is accurate for
  the frozen run and is **~134 tok/s median today** (127–147 by suite).
- **Reasoning quality and context capacity were not traded away:** same model, same 32k context, same scores;
  the long-context (L) and hard-reasoning (RH) suites were not re-run today (their frozen results stand).
- **No new optimization was created.** Runtime v1 remains frozen; this run is a reproduction under freeze record
  §16, not a reopening under §14.

## 4. Integration status (not done — owner decision)

The Core's configurable adapters are `ollama` (Ollama `/api/*` protocol) and `openai_compatible` (requires an
authenticated principal; built for cloud providers) in `uri_core/config/model_roles.py` and
`uri_core/core/provider_registry.py`. `llama-server` speaks the OpenAI protocol, but wiring Runtime v1 as the
resident Brain needs the persistent `BrainClient`, the v1 context layout, the FAST/NORMAL tier policy and a
loopback provider row — the scope of the **Operational Intelligence Integration** milestone (freeze record §18),
which has not started and which touches frozen Phase 1 files (`uri_core/app/server.py`, `uri_core/core/paired_brain.py`)
and the C5 Brain activation policy (C7 gate 3). It is therefore **not integrated** in this consolidation, and nothing
assumes a Brain model must be loaded: the Core stays model-optional.

| Level | Runtime v1 status |
|---|---|
| Researched / planned | yes |
| Implemented | yes (standalone runtime + `local_brain.py` client in `model_lab/integration/`) |
| Tested | yes (2026-10-06/07 qualification and soak; 2026-10-08 reproduction) |
| Independently accepted | frozen by owner ruling on Claude's qualification; **no Codex audit** of the runtime |
| Physically qualified | standalone soak on this PC only; not in a URI deployment |
| Production-active | **no** (no listener on 18470 outside benchmarks; not wired into the Core) |

## 5. Reproduce

```powershell
cd C:\Users\cheta\.codex\worktrees\uri-phase1-integration\uri-agent
$M = 'D:\uri-model-lab\models\unsloth__Qwen3.6-35B-A3B-GGUF'
.venv\Scripts\python.exe model_lab\run_bench.py --name <name> --model "$M\Qwen3.6-35B-A3B-UD-IQ3_S.gguf" `
  --mmproj "$M\mmproj-F16.gguf" --family qwen --ctx 32768 --ngl 999 --port 18491 --paths fast `
  --suites F,D,DG,C,H,S,O,R,P,V `
  --extra="-b 2048 -ub 1024 --cache-ram 2048 --slot-prompt-similarity 0 --checkpoint-min-step 512 --ctx-checkpoints 16 -md D:/uri-model-lab/mtp/mtp-qwen36-35b-a3b-Q4_K_M.gguf --spec-type draft-mtp --spec-draft-n-max 2 -otd token_embd.weight=CPU"
```

Drop the `-md … -otd …` part for the no-MTP baseline. Compare with
`docs/evidence/consolidation/inference_repro_20261008/compare_repro.py`.
