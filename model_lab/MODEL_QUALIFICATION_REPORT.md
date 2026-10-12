# URI post-Phase-1 local model qualification

Date: 2026-10-06. Machine: Windows 11 Pro 26200, Ryzen 9 5900X, Radeon RX 7900 GRE (16 368 MiB), 24 GiB RAM, C: NVMe SSD, D: SATA HDD.
Frozen Core: `work/c1/checkpoints/final-closure-20261005-phase1.zip`, sha256 `31a34dcb…98cf7` (re-verified at start and end, §11).
All work lives in the untracked `model_lab/` folder and `D:\uri-model-lab\`. Nothing in `uri_core`, the frozen 121-file inventory or git history was modified. Nothing was committed, pushed or cut over.

## 1. Decision

**Use one resident local model, with no second local model.**

| # | Item | Decision |
|---|---|---|
| 1 | Primary local intelligence | **Qwen3.6-35B-A3B** (MoE, 35B total / 3B active, Apache-2.0) |
| 2 | Exact artifact | `unsloth/Qwen3.6-35B-A3B-GGUF` @ `a483e9e6…`, file `Qwen3.6-35B-A3B-UD-IQ3_S.gguf`, sha256 `66a3ca88…ec66`; projector `mmproj-F16.gguf`, sha256 `8971ee4f…887f` |
| 3 | Runtime | llama.cpp b11425 Vulkan (`llama-server`). Flags: `-c 32768 -ngl 999 -fa on -ctk q8_0 -ctv q8_0 -np 1 -b 2048 -ub 1024 --load-mode none --cache-ram 1024 --jinja --reasoning-format deepseek --mmproj …`. Configuration is in `model_lab/integration/local_brain.json` |
| 4 | Residency | **Resident.** It fully fits the GPU with vision loaded: 15.6 GB VRAM, ≈1.3–1.7 GB server RAM, 14+ GB of system RAM left free |
| 5 | Reasoning levels | **fast** (thinking off): every Core seam, conversation, extraction, drafting, vision. **normal** (thinking on, 768-token budget): analysis, planning, hard reasoning. **Unbounded thinking is never used.** |
| 6 | Second reasoning model? | **No.** Qwen3.8-27B is better at long context, but it is not better at hard reasoning (0.88 = 0.88), it is 2–3× slower, and it cannot co-reside on the card |
| 7 | Vision specialist? | **No separate model.** Vision is the same resident model plus its 0.84 GB projector. This is justified: 5/5 visual tasks correct, against an OCR path that fabricated answers |
| 8 | Stays deterministic in Core | Turn State, preselection, reference binding (RAR/ARN), intent schemas and slot extraction, groundedness, budgeted clarification, confirmation digests, gates, permissions, approval, tickets, execution, verification, persistence, provider selection with no fallback |
| 9 | Model owns | Decision-contract proposals (mode and capability), slot suggestions that are verbatim user words, conversational and drafting language, extraction, advisory routing (answer, capability, clarify, escalate), bounded analysis, image understanding |
| 10 | Escalate to an external harness | Multi-file code changes, running test suites, build or deploy, large document sets, deep multi-source research, any normal-tier answer that runs out of budget, anything needing authenticated external tools |
| 11 | Measured cost | Decision turn: first token 0.96 s, total 2.4–2.5 s (p95 2.9 s). Plain answer 0.4 s. Resolved-context answer 1.0 s. Generation ≈100 tok/s. 18k-token prefill 8.6 s (2 160 tok/s), repeat turn 0.29 s. Warm load 6–9 s; cold load from the HDD 83 s. Hash check 10 s. 150-call soak: 0 errors, no latency drift, flat memory |
| 12 | Known weaknesses | See §7 |
| 13 | Rejected finalists | See §8 |

**Is "no permanent main brain" the better architecture? No.** With no model, the Phase 1 loop passed 8/12 scenarios. With the model it passed 12/12. The model contributed exactly what Core cannot do deterministically: implicit facts, "Remember: …" phrasing, and prefixed or noisy text. Core's guarantees held either way. A small resident model as the only local intelligence was also tested and rejected (Qwen3.5-2B, §8). Harness-only local intelligence would add network latency, quota and authentication dependencies to every turn. It would also leave per-turn intent work with no fallback while the harnesses remain `NOT_AUTHENTICATED`.

## 2. Acceptance criteria (set before benchmarking)

1. Any model is judged on the real frozen boundary where one exists (decision contract via `propose_decision`; Phase 1 loop via `create_app(composition=…)`), never on Core changes.
2. Hallucination discipline and Core cooperation outrank benchmark breadth: any model that fabricates URI state is disqualified for the resident role.
3. A fast path must keep an ordinary decision turn near 2–3 s and trivial replies under 1 s on this machine.
4. The resident footprint must leave ≥10 GB of system RAM for the desktop (Chrome, Claude, Windows).
5. Each extra model or tier must show a measured gain that justifies its cost.
6. Scores are deterministic (code-checked keys; no model grades itself). Every scorer correction is applied to every model, and the raw outputs are kept.

## 3. Method

- **Research and shortlist:** `model_lab/RESEARCH_SHORTLIST.md` covers fit-driven candidate selection and rejections on fit (Qwen3.8-Flash-Next ≈63 GB; Gemma-4-31B, Granite-4.2-30B and Mistral-Small-4 for dense spill or size).
- **Downloads:** each file was checked against its Hugging Face LFS sha256 (`D:\uri-model-lab\dl\manifest.jsonl`). Pre-existing Ollama and LM Studio models were only read. The existing Gemma-4-26B file matched its Hub hash.
- **Harness:** `model_lab/run_bench.py`, `lab/*.py`. llama-server per configuration, streaming client measuring first token / first answer token / total, server timings, a VRAM/RAM/CPU sampler, warm-up excluded. Evidence is stored per run under `model_lab/evidence/runs/<model>/<stamp>/` (results, summary, server log, argv, model sha256).
- **Suites** (deterministic scoring):

| Suite | What | Boundary |
|---|---|---|
| D / DG | 57 accepted M30 golden cases + 15 new cases (implicit facts, corrections, claimed approval, failed history, harness, trivia). DG adds a JSON-schema grammar with a capability enum | **Real Core**: `propose_decision`, `_validate_contract`, `evaluate_against_golden` |
| P | 12 scenarios through the real paired server: ambiguity → clarification → confirmation → approval → ticket → execution → independent verification → persistence. Also follow-up, correction, implicit fact, trivia, destructive request, ungranted harness, injected approval, vague reference, typed "confirm" | **Real Core**: `create_app(composition={policy, proposer, interpreter})` |
| C | 14 resolved-state packages: current vs superseded, unknown fields, uncertain/failed receipts, unresolved references, embedded injected instructions, disconnected capability, claimed approval | Integration-layer prompt |
| H | 22 route decisions (answer locally, use capability, clarify, escalate to harness, refuse) | Integration-layer prompt |
| R / RH | 12 standard + 8 hard reasoning tasks. RH answer keys are computed by brute force or execution, and uniqueness is asserted | — |
| S | 6 extraction documents, with prompt-only and grammar variants; null-for-missing | — |
| O | 4 office drafts: required facts, no invented numbers, length | — |
| L | Session dossiers at 4k/16k/32k tokens: early standing instruction, superseded fact, ordinal reference among distractors, scattered entity set, JSON contract | — |
| F | 10 trivial turns × 3 repeats (latency) | — |
| V | 5 synthetic images (UI error, noisy scanned table, chart, diagram, checkboxes): VLM vs Core's Tesseract OCR → same model | — |

- **Reasoning depth:**
  - fast: thinking off.
  - normal: thinking on, `thinking_budget_tokens` 768.
  - deep: unbounded.
  - gpt-oss uses effort low/medium/high, because it cannot switch reasoning off.

## 4. Results (fast path unless noted; D excludes 2 Core-preselection-gap cases, §6 B-2)

| Model (quant) | D | DG | C | H | P | L | R | RH | S | O | Decision turn | gen tok/s | VRAM / server RSS |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| **Qwen3.6-35B-A3B UD-IQ3_S** | 0.86 | 0.86 | **1.00** | **1.00** | 11/12 lab, **12/12 production adapter** | 0.93 | 0.96 | 0.62 (normal **0.88**) | 1.00 | 1.00 | **2.6 s** | **100** | 14.5 GB (15.6 with vision, 32k) / 0.7–1.7 GB |
| Qwen3.6-35B-A3B UD-Q4_K_M (`--fit`, experts on CPU) | 0.90 | 0.90 | 1.00 | 0.91 | 12/12 | 0.93 | 0.92 | — | 1.00 | 1.00 | 6.1 s | 41 | 15.6 GB / 7.9–14 GB, 30 % CPU, free RAM fell to 0.6 GB |
| Qwen3.8-27B UD-IQ4_XS (dense) | **0.90–0.91** | 0.91 | 1.00 | 1.00 | 12/12 | **1.00** | 0.92 | 0.88 (normal 0.88 @ 26 s) | 1.00 | 1.00 | 7.6–8.4 s | 26–30 | 14.9–15.7 GB / spills at 40k |
| gpt-oss-20b MXFP4 (effort low) | 0.74 | **0.90** | 0.92 | 0.91 | 12/12 (grammar) | 0.60 | 0.92 | **0.75** | 1.00 | 1.00 | **1.7 s** | **133** | 12.9 GB / 0.9–1.8 GB |
| Gemma-4-26B-A4B QAT Q4_0 | 0.80 | 0.80 | 1.00 | 1.00 | 10/12* | 0.73 | 1.00 | 0.62 | 0.97 | 1.00 | 3.6 s | ≈100 | 15.4 GB / 0.9–2.8 GB |
| Qwen3.5-9B Q4_K_M (incumbent, llama.cpp) | 0.76 | 0.76 | 1.00 | 0.91 | 11/12* | 0.73 | 0.92 | — | 1.00 | 1.00 | 3.0 s | 76 | 7.0 GB / 0.8–6.2 GB |
| gemma4:12b (incumbent, Ollama 0.34.1 defaults) | **0.00** (0/70 valid) | 0.21 | 0.79 | 0.95 | 2/12 | — | — | — | — | — | 8.1 s | — | Ollama ROCm, ctx 4096 |
| Qwen3.5-2B Q4_K_M | 0.31 | 0.33 | 0.96 | 0.55 | 9/12 | — | — | — | — | — | 1.2 s | 204 | 2.7 GB |
| Nemotron-3.5-Lightning-30B-A3B Q4_0 | 0.51 | 0.51 | 0.98 | 0.73 | 2/12 | 0.60 (leaked roll numbers at 32k) | 0.88 | — | 0.99 | 0.96 | 4.3 s | 54 | 15.5 GB / 4.8–9.4 GB |

\* Run before the adapter's span-snapping fix (§6 C-3). Gemma's p11 miss and Qwen3.5-9B's miss are the class that fix addresses. They were not re-run.

Hallucination counts (C suite, fast): 0 for every finalist; 1 for Qwen3.5-2B. Fields invented in extraction: 0 for all. Over-escalation to the harness: 0 for every finalist; 4 for Qwen3.5-2B.

### 4.1 Incumbents as deployed

- **`gemma4:12b` through Ollama 0.34.1:**
  - Thinking stays on, because Ollama ignores the template switch.
  - The default context is 4096 tokens, so larger URI packages are silently truncated.
  - Every decision exhausted the 500-token cap or dropped required contract fields.
  - Result: 0/70 valid decisions (8.1 s median); with a JSON schema 0.21 (9.5 s); resolved-state answers 0.79; Phase 1 loop 2/12.
  - This measures the current deployment, not the model ceiling. Both defaults are integration hazards for any Ollama-hosted model.
- **`qwen3.5:9b` run through llama.cpp:** clearly behind the selected model on decisions (0.76 vs 0.86), routing and long context, and slower per decision.

### 4.2 Reasoning-depth experiment

| Model | Decision contract fast → normal → deep | Hard reasoning fast → normal → deep |
|---|---|---|
| Qwen3.6 IQ3_S | 0.86 (2.6 s) → 0.89 (10.2 s) → not run | 0.62 → **0.88 (12.7 s)** → 0.62 (85 s; 3/8 looped to 12k tokens) |
| Qwen3.6 Q4_K_M | 0.90 → 0.90 (25 s) | — |
| Qwen3.8-27B | 0.90 → 0.86 (35 s) | 0.88 (55 s) → 0.88 (26 s) |
| Qwen3.5-9B | 0.76 → 0.81 (13 s) → **0.34 (81 s)** | — |
| gpt-oss-20b | 0.74 → 0.77 (4.8 s) → **0.39 (44 s; 34/72 never answered)** | 0.75 at low |
| Gemma-4-26B | 0.80 → 0.81 (11 s) | 0.62 → 0.62 → **0.00 (126 s; 16/20 looped)** |

All decision figures exclude the two preselection-gap cases (§6 B-2).

Conclusions:

- Bounded thinking adds 0–5 points to the decision contract at 3–5× the latency (Qwen3.8 loses 4). That is not worth it on every turn, so Core seams stay on fast.
- Unbounded thinking collapses the contract (two families) and loops on hard problems (three families).
- A **bounded** budget is the only depth setting with a net gain, and only for genuine analysis. Qwen3.6 IQ3_S gains +26 points on RH at less latency than its fast path, which writes chain-of-thought into the answer.
- One model with dynamic depth therefore replaces a multi-model setup without making URI sluggish: Core seams always use fast, and only analysis uses normal.

### 4.3 Vision (projector loaded on the same resident model)

| Image task | Qwen3.6 IQ3_S VLM | Gemma-4-26B VLM | Core path: Tesseract OCR → same model |
|---|---|---|---|
| UI error + toggle states | correct (2.4 s) | correct | error right, **toggles fabricated** |
| Noisy scanned marks table | correct (0.8 s) | correct | "Arjun Das, 64" (**wrong**) / "cannot be determined" |
| Bar chart extremes | correct | correct | cannot be determined |
| Process diagram | correct | correct | partial |
| Form checkboxes | correct | correct | "yes" (**wrong**) / cannot be determined |

The unmet need is real: Core's OCR loses visual state, and the model then guesses. Cost of the selected answer: +0.84 GB VRAM on the already resident model. It still fits at 32k context (15.6 GB) and needs no swap.

## 5. Integration implemented (outside Core, reversible)

- **`model_lab/integration/local_brain.py`:**
  - `ResidentRuntime` (hash-verified start/stop/health).
  - `LocalBrain.proposer` and `LocalBrain.interpreter`: the two seams Phase 1 already accepts. Both use the fast tier with grammar constraint; failures raise `ReasoningUnavailable` and Core reports them; there is no fallback.
  - `answer(tier=fast|normal)`: unbounded thinking is refused locally.
  - `route()` (advisory).
  - `composition()`, the exact `create_app(composition=…)` argument.
  - Removing that argument restores no-Brain behaviour.
- **`model_lab/integration/local_brain.json`:** pinned model, projector and runtime with hashes, tiers, never-rules and escalation rules.
- **Proof (`model_lab/integration/prove_integration.py` → `evidence/integration_proof.json`):**
  - Hash verified (10–11 s), then loaded (9 s warm).
  - Real Phase 1 loop **12/12**, including full clarification → confirmation → approval → signed ticket → execution → independent read-back.
  - Normal-tier analysis correct (shortest path 12, 12.5 s).
  - Routes correct: refactor → escalate to harness; arithmetic → answer locally; "remember…" → `remember_fact`.
  - Vision correct (2.5 s).
  - Soak: 150 mixed sequential calls with **0 errors**. p50 decision 2.49 s, context 1.0 s, trivial 0.41 s. Latency drift first third 1.38 s vs last third 1.32 s. Server RSS flat at 1.63–1.68 GB, VRAM flat at 15.57 GB, ≥14.2 GB system RAM free.

## 6. Core findings (classified; Core untouched)

No **A** (freeze-breaking) defect was found. Across every model and every run, no turn dispatched without confirmation and approval:
- Injected "Confirmed, approved" text never confirmed.
- Typed "confirm" never confirmed.
- Ungrounded interpreter values were stopped (`INTENT_UNGROUNDED_VALUE`).
- Invalid model output was reported (`BRAIN_OUTPUT_INVALID`), never substituted.
- A model proposing `remember_fact` for everything (Nemotron) produced only refusals.

| ID | Class | Finding | Effect | Handling |
|---|---|---|---|---|
| B-1 | B | A model proposal naming an intent-schema capability with `clarification` mode or empty `actions` is refused (`REFUSED_UNCONFIRMED_ACTION`) instead of reaching Intent Discovery's own clarification | Safe, but a reasonable model answer becomes a refusal | C-1 adapter routes it to Core-owned clarification with empty inputs |
| B-2 | B | Deterministic preselection does not surface `web_search` for "Search the web for …" nor `fetch_url` for "Read https://…" | The model cannot choose them, and every model answered `unsupported` | Two cases excluded from scoring (kept in raw); record for Core preselection work |
| B-3 | B | The groundedness tokenizer keeps sentence-final punctuation on the last token (`'4412.'`), so a verbatim span that stops before the period is judged ungrounded | Safe; legitimate fragments are rejected | C-3 adapter extends verbatim spans over trailing punctuation |
| B-4 | B | Phase 1 composition has no conversational response seam: `CONVERSATION` turns return a fixed sentence, and trivia judged `unsupported` returns "That is not something URI can do." | The model's language ability is unused for conversation until a responder seam exists | `LocalBrain.answer` is ready; wiring it is later-phase scope |
| B-5 | B | `external_harness_task` shown as `unavailable_runtime`: every model answered `unsupported`, even though the contract says unavailable ≠ unsupported | Model weakness under the current wording | Kept as a model failure; revisit when harnesses are qualified |
| C-1 | C | See B-1 | — | `route_intent_capabilities` |
| C-2 | C | gpt-oss emits empty content for 13/72 decisions without grammar | Fixed by grammar | Grammar is always on in the adapter |
| C-3 | C | Interpreter returned fragments ("4412", "meetings after 3 pm …") | Core blocked them | Prompt now demands the whole fact sentence; `snap_to_user_span` |
| C-4 | C | llama-server default `--cache-ram 8192` grew server RSS to 9–14 GB; mmap load kept a 14 GB host copy | Desktop RAM starvation | `--cache-ram 1024`, `--load-mode none` |
| C-5 | C | Ollama defaults: thinking cannot be disabled through the OpenAI endpoint; `num_ctx` is 4096 | Silent truncation, contract failures | Use llama.cpp for the resident model |
| Obs | — | The legacy (non-Phase-1) Gmail capability directory exposes `archive_message` and `apply_label`. The user's standing rule is draft-only (never archive) | Not on the Phase 1 paired path | Raised for the owner's decision; not changed |

## 7. Known weaknesses of the selected configuration

- **Decision contract 0.86 vs 0.90 for its Q4_K_M sibling, Qwen3.8 and gpt-oss+grammar:**
  - Misses lean towards `conversation` for implicit personal disclosures (2 golden cases) and `clarification` for office drafting (2 cases).
  - Core's gates and Intent Discovery prevent harm, but these turns get a weaker first response.
- **Hard reasoning:**
  - Without thinking: 0.62.
  - Bounded thinking: 0.88.
  - Problems needing long search (knapsack, interval packing) can exhaust any local budget; those must escalate (`finish_reason=length` is the trigger).
- **Long context:** missed the ordinal reference once at 4k, while 16k and 32k were correct (0.93 overall). Qwen3.8-27B was perfect here, at 3–4× the latency.
- **Quantization:** IQ3_S is a 3-bit quant. Quality is ≈1–4 points below Q4_K_M on D and R in exchange for a full-GPU fit, 2.3× speed and 6–12 GB less RAM. Revisit if VRAM grows.
- **Cold load from the D: HDD is ~80 s.** Placing the two files on C: (NVMe, 165 GB free) is recommended at cutover (not done).
- **VRAM headroom ≈0.7 GB** with vision and 32k context. A large desktop GPU consumer could force a reload; ctx 16k frees ≈0.4 GB if needed.
- **Benchmarks are synthetic and modest** (≈200 scored items per model plus 12 live scenarios). Differences of one or two items are within noise; the selection rests on consistent margins in latency, memory and hallucination behaviour, not on single points.

## 8. Rejected finalists

| Candidate | Reason |
|---|---|
| Qwen3.6-35B-A3B UD-Q4_K_M | Best decision quality per active parameter, but it cannot fit 16 GB. Experts on CPU give 41 tok/s, 6.1 s decisions, 30 % CPU, 8–14 GB RSS and 0.6 GB free RAM. Fails the RAM criterion |
| Qwen3.8-27B | Best long context (1.00) and decisions (0.91), but dense: 26–30 tok/s, 7.6–8.4 s per decision, 40–82 s at 16–32k. No hard-reasoning gain over the selected model's normal tier, and cannot co-reside. Rejected as primary and as on-demand second model |
| gpt-oss-20b | Fastest (1.7 s, 133 tok/s) with excellent DG and RH. Rejected for long context 0.60 (ordinal and entity failures at every size), C 0.92, no reasoning-off switch (even "low" emits reasoning), grammar required, no vision |
| Gemma-4-26B-A4B QAT | Strong C/H/O and vision, but decisions 0.80 and long context 0.73 (misses the ordinal at all sizes). Prefill is half the selected model's. Bounded thinking gave no gain; unbounded thinking looped |
| Qwen3.5-9B / gemma4:12b (incumbents) | Weaker on decisions, routing and long context. The Ollama deployment fails the contract outright |
| Qwen3.5-2B (fast tier for a two-model architecture B) | Decisions 0.31, routing 0.55, only 0.5 s faster than gpt-oss. A small router would degrade the turns it is meant to accelerate |
| Nemotron-3.5-Lightning-30B-A3B | Decisions 0.51, P 2/12, roll-number leak at 32k. Downloaded file deleted |
| Qwen3.8-Flash-Next, Gemma-4-31B, Granite-4.2-30B, Mistral-Small-4 | Rejected on fit before download (§3) |

## 9. Corrections made during the run (audit trail)

All raw outputs are kept. Corrections were applied to every model through `rescore.py`, and invalidated runs are listed in `compare.py:INVALID`.

1. **Thinking-path token caps.** The 600–700-token caps measured truncation. Gemma's first deep run was invalidated, and thinking paths now get at least 4000 tokens.
2. **gpt-oss low effort still reasons.** Its first L/O/P runs were invalidated and re-run.
3. **Pre-fix adapter runs.** gpt-oss normal/deep P runs used the pre-fix adapter and were invalidated. The Phase 1 seams always use fast.
4. **Scorer fixes:**
   - p10 expectation (Core auto-confirms complete verbatim requests).
   - Over-strict keyword checks (negation phrases, "1st November").
   - Narrow/non-breaking spaces and "75 %".
   - Lists answered as JSON strings.
   - Reasoning correctness separated from output format (`format_ok`).
5. **Truth puzzle.** A non-unique puzzle was caught by the uniqueness assertion and replaced.
6. **Preselection-gap cases** (B-2) excluded from D/DG.
7. **Deep runs trimmed.** Deep decision runs on later models were cut after two families showed collapse, to save ≈90 minutes per model; one Qwen deep-D data point was kept.

## 10. Reproduction

```
.venv\Scripts\python.exe model_lab\run_bench.py --name <n> --model <gguf> --family qwen|qwen38|gemma|gptoss --ngl -1 --paths fast --suites F,D,DG,C,H,S,O,R,RH,L,P
.venv\Scripts\python.exe model_lab\rescore.py && .venv\Scripts\python.exe model_lab\compare.py
.venv\Scripts\python.exe model_lab\integration\prove_integration.py 150
.venv\Scripts\python.exe model_lab\verify_freeze.py
```

Supporting files:
- Downloads: `D:\uri-model-lab\dl\manifest.jsonl`.
- Runtime help snapshot: `D:\uri-model-lab\runtime\server_help_b11425.txt`.
- Per-run evidence: `model_lab/evidence/runs/`.
- Cross-model table: `model_lab/evidence/comparison.json`.
- Resources: `model_lab/evidence/resources_table.json`.
- Tuning: `model_lab/evidence/tuning_qwen36-iq3s.json`.

## 11. Freeze verification

`model_lab/verify_freeze.py`:
- At start: 121/121 inventory files identical, archive sha256 matches (`evidence/freeze_check_start.json`).
- At end: 121/121 identical, archive sha256 `31a34dcb…98cf7` matches (`evidence/freeze_check_end.json`).

The `git diff --binary` hash at start was `20F2334D…4C4D` (`evidence/baseline_git_diff.patch`). At the end it was byte-identical (`20F2334D…4C4D`, `evidence/end_git_diff.patch`), and `git status --porcelain` was identical to the baseline: no Core, test or doc file changed. Processes started by this task were stopped, including the Ollama app/server that the initial inventory command auto-launched (it was not running before the task). The GPU returned to the 0.96 GB desktop baseline.

## 12. Disk and cleanup

**Removed (introduced by this task and conclusively rejected):**
- Nemotron GGUF (17.6 GB).
- llama.cpp ROCm runtime and its archive (1.3 GB; it reports no device on this driver).

**Retained for reproduction** (all under `D:\uri-model-lab\models`, removable on request):
- gpt-oss-20b (12.1 GB).
- Qwen3.6 Q4_K_M (20.6 GB).
- Qwen3.8-27B IQ4_XS (13.3 GB).

**Untouched:** pre-existing Ollama and LM Studio models.


