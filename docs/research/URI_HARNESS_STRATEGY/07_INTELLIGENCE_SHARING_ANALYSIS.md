# 07 — Intelligence-Sharing Analysis

## Goal

The user configures URI once. External harnesses consume the intelligence URI already has: local Edge and Capable models, and cloud providers with URI-held keys. They do not need a second "Hermes brain" or "Codex brain". The design must not duplicate model loading.

## 1. Current URI facts (`_V1` worktree)

- URI is an OpenAI-compatible **client** only:
  - `uri_core/core/model_providers/openai_compatible_provider.py`
  - `ollama_provider.py`
  - `anthropic_provider.py`
  - **URI exposes no model endpoint.**
- Qualification runtime is LM Studio. The production default Brain is Ollama (`config/model_roles.py:78-79`). This inconsistency is already flagged by the repository audit.
- Keys are encrypted per user and write-only (`core/provider_keys.py`).
- Measured residency on the target machine (repository evidence, LM Studio):
  - Resident 9B Q4 main brain: 5.63 GB VRAM loaded. KV cache is about 1.80 GB at 16,128 context with 4 slots. Peak VRAM is about 7.43 GB (`docs/plans/M35_URIV1_A2_7_RESIDENT_MAIN_BRAIN_SEMANTIC_QUALIFICATION.md:51-60`).
  - Edge resident +1.7 GB GPU; Capable resident +6.0 GB GPU; co-resident 9.4 GB GPU (`docs/plans/M33_3_R_IMPLEMENTATION_REPORT.md` §6).
  - Host RAM reached 21.7 GB in one Batch A run (`docs/plans/M33_3_URI_BRAIN_ARCHITECTURE_PROPOSAL.md:233,316`).

## 2. Harness compatibility with URI-brokered intelligence

| Harness | Accepts external endpoint? | Wire | Extra requirements | Can consume URI intelligence? |
|---|---|---|---|---|
| Hermes | Yes: `provider: custom` + `base_url`; `lmstudio` first-class (local source) | Chat completions (Responses also served by Hermes itself) | ≥64k context; tool calling; llama.cpp `--jinja` (web docs) | **Yes, conditionally** (context) |
| OpenCode | Yes: `@ai-sdk/openai-compatible` baseURL | Chat completions | tool calling | Yes |
| Goose | Yes: 15+ providers incl. Ollama | Varies | tool calling | Yes |
| OpenHands | Yes, "any LLM" (L) | LiteLLM | tool calling | Likely |
| Codex | Yes: custom provider / `--oss` | **Responses only** | Responses-capable server (Ollama ≥0.13.3 has `/v1/responses`) | Yes if endpoint speaks Responses (D-A applies) |
| Claude Agent SDK | Anthropic-format gateways, **Claude models only** | Anthropic Messages | — | **No** (cloud Claude via URI-held key is the only route) |
| Gemini CLI | Gemini only (L) | — | — | **No** |
| LangGraph / Agents SDK / MS Agent Framework (fallback) | Yes (library) | any | — | Yes, natively through URI's own providers |

## 3. Options

### Option I-1: Shared model server (point the harness at URI's managed LM Studio/Ollama)
- URI's lifecycle manager configures the harness profile with `base_url` set to the same loopback server URI uses.
- **Pros:** zero new code on the model path; one copy of each model; residency is shared naturally.
- **Cons:**
  - URI loses per-request visibility. The harness talks straight to the model server, so there is no URI metering, budget or trace.
  - Cloud keys would have to be copied into harness config, which breaks R-A5 unless the harness is local-only.
  - The context setting is global per server.
- **Brick wall check:** Ollama's default 4k context must be overridden (R-R3). LM Studio context is per loaded instance.

### Option I-2: URI Intelligence Broker (loopback OpenAI-compatible, optionally Responses, endpoint in front of URI's router)
- URI serves `http://127.0.0.1:<port>/v1` with a per-run token. Requests pass through the existing `ModelRouter`, so budgets, usage metering, auth-error-no-fallback, the model override and trace ids all apply.
- **Pros:**
  - Configure once.
  - Vendor keys never leave URI.
  - Per-run budgets and metering.
  - The model can be switched without touching the harness.
  - Works for every harness in the table except Claude and Gemini.
- **Cons:**
  - New surface, needed for streaming and tool-call pass-through fidelity.
  - Responses-wire translation is needed only for Codex.
  - Latency overhead is UNMEASURED; expected small on loopback.
- **Precedent:** M24 explicitly did not build "Gateways" because URI had no backend concept. This gives it one, with a narrow scope.
- **Security:** loopback-only, reusing the loopback-and-redirect lessons in `uri_core/external/adapters/http.py`. Per-run scoped token, revoked at run end.

### Option I-3: Harness owns its own brain
Rejected. It violates configure-once, duplicates keys and models, and hides cost.

**Recommendation:** use **I-2 as the target** and **I-1 as the first experiment** (cheapest proof). The broker must *front* the same shared model server, so models load once.

## 4. Edge interaction

- Edge models never serve harness loops. Harness loops need tool calling and long context; qualified Edge tasks are narrow.
- The harness can *use* Edge-qualified URI capabilities indirectly, through the URI MCP broker (for example `uri.lookup_reference` backed by RAR and ARN). This is how "Edge intelligence" participates in agentic runs without being loaded into the harness.
- **Residency policy:** during a harness run on local intelligence, the Capable model plus harness KV may crowd out Edge co-residency. The lifecycle manager must hold leases (reusing `core/edge/lease_ownership.py` semantics) and choose between the options below. This decision is data-driven through E-P3.
  - evict Edge
  - run the harness on cloud Capable
  - queue the task

## 5. Resource arithmetic (ESTIMATES ONLY — all UNMEASURED)

- The 16 GB GPU holds the 9B Q4 weights (5.63 GB measured) plus KV. KV grows roughly linearly with context. The measured about 1.80 GB at 16,128 context (4 slots) implies a 64k-context harness run would need materially more KV. The exact figure depends on slots, KV quantisation and whether LM Studio allocates per slot. **UNMEASURED; E-P3 measures it.**
- Co-residency with Edge (+1.7 GB) at 64k context may not fit alongside a browser and the desktop compositor. **UNMEASURED.**
- CPU/RAM overhead of a harness process (Python for Hermes/OpenHands, Node for OpenCode/OpenClaw, Rust for Goose/Codex): **UNMEASURED; E-P9.**

## 6. Conclusion

Configure-once intelligence sharing is **architecturally feasible** for every open harness candidate through I-2 or I-1. It is not feasible for Claude Agent SDK or Gemini CLI. The binding constraint is not API compatibility. It is **context length versus local VRAM**. Whether fully local harness runs are practical on this machine is unknown until E-P3/E-P5. Until then, the architecture must allow harness runs on a cloud Capable Brain through URI-held keys, with the user's awareness of cost and privacy.
