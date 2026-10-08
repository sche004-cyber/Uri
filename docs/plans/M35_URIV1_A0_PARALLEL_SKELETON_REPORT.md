# M35 — Batch A0: URIv1 Parallel Skeleton — Report

## 1. Branch / worktree / HEAD

- Source repository: `C:\Users\cheta\Development\uri-agent` (branch `master`, HEAD `e8e3b65259c45fc823addc3ef8969425a265bd1b`, in sync with `origin/master`, 0 ahead / 0 behind).
- The existing prototype worktree carried **65 uncommitted paths** (52 modified + 13 untracked, ~2906 insertions / 365 deletions) across `uri_core/` and `uri_ui/`. This was recorded as **intentional and protected** — the working URI prototype was left completely untouched throughout A0. `git status --porcelain` in that worktree showed the same 65 paths before and after this batch.
- New worktree created via `git worktree add` (not a branch in the same working directory) so the prototype's uncommitted state could not be disturbed:
  ```
  git worktree add "C:\Users\cheta\Development\Uri\_V1" -b m35-uri-v1-parallel-architecture e8e3b65259c45fc823addc3ef8969425a265bd1b
  ```
- New worktree path: `C:\Users\cheta\Development\Uri\_V1`
- New branch: `m35-uri-v1-parallel-architecture`
- Starting HEAD (new worktree): `e8e3b65259c45fc823addc3ef8969425a265bd1b` (identical to source — no commits made in A0).
- `git worktree list` confirms both worktrees exist independently, each on its own branch, plus a pre-existing unrelated detached-HEAD worktree (`.tmp_m33_1_batch4_baseline_5973f6d`) that predates this batch and was not touched.

## 2. Files created

All new, all inside `C:\Users\cheta\Development\Uri\_V1`. Nothing in `uri_core/` or `uri_ui/` was modified.

```
uri_v1/__init__.py
uri_v1/app/__init__.py
uri_v1/turn/__init__.py
uri_v1/turn/contracts.py
uri_v1/turn/decoder.py
uri_v1/context/__init__.py
uri_v1/intelligence/__init__.py
uri_v1/intelligence/edge/__init__.py
uri_v1/intelligence/edge/provider.py
uri_v1/intelligence/local/__init__.py
uri_v1/intelligence/local/provider.py
uri_v1/intelligence/extended/__init__.py
uri_v1/intelligence/extended/provider.py
uri_v1/execution/__init__.py
uri_v1/recovery/__init__.py
uri_v1/knowledge/__init__.py
uri_v1/safety/__init__.py
test_m35_uriv1_a0_skeleton.py
docs/plans/M35_URIV1_A0_PARALLEL_SKELETON_REPORT.md  (this file)
```

## 3. Architecture tree

```
uri_v1/
├── __init__.py
├── app/
│   └── __init__.py
├── turn/
│   ├── __init__.py
│   ├── contracts.py       # DecodedRequest, ContextPack, EdgeOutcome, IntelligenceResult, FinalizedTurn
│   └── decoder.py         # SemanticDecoder provider slot (Step 1)
├── context/
│   └── __init__.py        # Step 2 placeholder — no resolution logic
├── intelligence/
│   ├── __init__.py
│   ├── edge/
│   │   ├── __init__.py
│   │   └── provider.py    # EdgeIntelligenceProvider slot
│   ├── local/
│   │   ├── __init__.py
│   │   └── provider.py    # LocalIntelligenceProvider slot
│   └── extended/
│       ├── __init__.py
│       └── provider.py    # ExtendedIntelligenceProvider slot
├── execution/
│   └── __init__.py        # placeholder
├── recovery/
│   └── __init__.py        # placeholder
├── knowledge/
│   └── __init__.py        # placeholder
└── safety/
    └── __init__.py        # deliberately empty; explicit hooks only, none required yet
```

Deviation from the batch spec's originally proposed tree: the Semantic Decoder interface lives at `uri_v1/turn/decoder.py`, not inside `intelligence/edge/`. This follows an explicit refinement during plan review — the decoder is conceptually Step 1 (turn/request layer), separate from Step 3's Edge Intelligence tier, even though Needle 3 is the planned first implementation of both.

## 4. Contracts introduced

All in `uri_v1/turn/contracts.py`, plain frozen `@dataclass`, matching the style found in `uri_core/capabilities/base.py` (`from __future__ import annotations`, frozen dataclasses, module docstring, minimal fields):

- `DecodedRequest` — output of Step 1. `raw_text`, optional `intent`, `metadata` dict.
- `ContextPack` — output of Step 2. Wraps a `DecodedRequest` plus a `context` dict.
- `EdgeOutcome` — result of an intelligence-tier attempt. `handled: bool`, optional `result`, optional `escalate_reason`.
- `IntelligenceResult` — result from whichever tier handled the turn. `tier`, `output`, `metadata`.
- `FinalizedTurn` — output of Finalization. Wraps the `ContextPack` and the winning `IntelligenceResult`.

**Deferred, not defined:**
- `TaskSlice` — no A0 consumer forces a shape yet; premature to guess whether it's per-capability, per-tool-call, or something else before Step 2/3 design exists.
- `KnowledgeDelta` — belongs to the `knowledge/` write-back path, which A0 explicitly does not implement; defining its shape now would be speculative.

Both are left for the batch that first needs them (likely A1 for `TaskSlice`, a later knowledge-integration batch for `KnowledgeDelta`).

## 5. Provider boundaries established

Four replaceable slots, each an `abc.ABC` with one `@abstractmethod`, no concrete implementation, verified abstract (instantiation raises `TypeError`, tested in `test_provider_slots_are_abstract`):

| Slot | Interface | Location |
|---|---|---|
| Semantic Decoder | `SemanticDecoder.decode(raw_text) -> DecodedRequest` | `uri_v1/turn/decoder.py` |
| Edge Intelligence | `EdgeIntelligenceProvider.attempt(context_pack) -> EdgeOutcome` | `uri_v1/intelligence/edge/provider.py` |
| Local Agentic Intelligence | `LocalIntelligenceProvider.attempt(context_pack) -> EdgeOutcome` | `uri_v1/intelligence/local/provider.py` |
| Extended Intelligence | `ExtendedIntelligenceProvider.handle(context_pack) -> IntelligenceResult` | `uri_v1/intelligence/extended/provider.py` |

None of Needle 3, Qwen, Mistral, Claude, GPT, Gemini, Ollama, LM Studio, or llama.cpp appear anywhere in `uri_v1/`. Each `__init__.py` in the owning package re-exports its public type only (no interface bodies in `__init__.py`, per plan refinement).

## 6. Existing infrastructure reuse map

Inspected via graphify query against `uri_core`, not modified.

| Component | Location | Classification |
|---|---|---|
| `GraphStore` | `uri_core/core/graph_store.py` | `ADAPT` — persistent-context primitive Step 2 will need; likely needs a URIv1-facing interface wrapper rather than direct reuse. |
| `ConversationHistoryStore` | `uri_core/core/conversation_history.py` | `SHARE` — session/turn history is provider-neutral state, reusable as-is. |
| `FileStore` | `uri_core/core/file_store.py` | `SHARE` — artifact storage has no orchestration coupling. |
| `ExperienceStore` | `uri_core/core/experience_store.py` | `ADAPT` — knowledge-building shape may differ under URIv1's `KnowledgeDelta` model once defined. |
| `ModelRouter` / model provider abstractions | `uri_core/core/model_router.py`, `uri_core/core/model_providers/` | `ADAPT` — the low-level provider transport (HTTP/streaming to Ollama, OpenAI-compatible, etc.) is reusable; the routing policy above it is not (see DO-NOT-INHERIT). |
| `ToolDispatcher` | `uri_core/core/dispatcher.py` | `COPY-LATER` — execution-layer candidate for `uri_v1/execution/`, but not needed until a later batch actually wires tool calls. |
| `WorkflowExecutor` | `uri_core/core/workflow_executor.py` | `COPY-LATER` — same rationale as `ToolDispatcher`. |
| ARN (deterministic narrowing core) | referenced in recent commit history (`feat(arn.1)`) | `ADAPT` — Step 2 explicitly calls for "ARN only when unresolved"; needs inspection at that time, not now. |
| Edge/Needle bridge | `uri_core/core/edge_lifecycle/` | `ADAPT` — closest existing analog to Step 3's Edge tier; current shape is coupled to the old routing funnel and needs re-shaping against `EdgeIntelligenceProvider`, not straight reuse. |
| Telemetry / audit | `AuditTrail` (`uri_core/core/audit_trail.py`) | `SHARE` — audit logging is provider-neutral. |

## 7. Components intentionally not inherited

Per batch spec §10, confirmed absent from any `uri_v1/` import (see §8 static check):

- `DECISION_CONTRACT_SYSTEM_PROMPT`
- The forced `ROLE_REASONING -> ROLE_DRAFTING` funnel
- Legacy orchestrator behavior (`uri_core/core/orchestrator.py`)
- Premature Edge routing before context resolution
- Hard-coded two-tool reflex dictionaries
- Lowest-common-denominator model restrictions
- Governance gates that exist only to second-guess model intelligence rather than implement genuine safety

None of these systems were deleted or changed in `uri_core/` — they simply have no dependency edge from `uri_v1/`.

## 8. Tests run and results

All run inside the new worktree (`C:\Users\cheta\Development\Uri\_V1`), Python 3.13.15, pytest 9.1.1.

**New focused suite** — `test_m35_uriv1_a0_skeleton.py`:
```
7 passed, 20 subtests passed in 0.17s
```
Covers: package + all submodules import cleanly; contracts are usable plain dataclasses; all four provider slots are genuinely abstract (`TypeError` on direct instantiation); static AST-based import-graph scan finds zero edges from any `uri_v1/*.py` file to `uri_core.core.orchestrator`, `uri_core.core.decision_engine`, or `uri_core.core.capability_registry`; importing `uri_v1` pulls in no `uri_core.core.orchestrator` or `uri_core.core.model_providers` module into `sys.modules`; `uri_core` itself still imports cleanly.

**Existing smoke subset** — `test_m22_5_providers_endpoints.py` (chosen because it exercises `uri_core` server/provider endpoints without requiring a live model or network):
```
8 passed, 1 warning in 44.80s
```
(Warning is a pre-existing `anyio`/`starlette` deprecation notice, unrelated to this batch.)

Full suite was not run, per batch spec §11.

## 9. Deviations from proposed structure and reasons

1. **Decoder location** — `SemanticDecoder` placed at `uri_v1/turn/decoder.py`, not embedded in `intelligence/edge/`. Explicit correction during plan review: Step 1 belongs to the turn/request layer, distinct from Step 3.
2. **No interface bodies in `__init__.py`** — each provider interface got its own `provider.py` module; `__init__.py` files only re-export. Explicit plan refinement to avoid overloading package-init files with substantial code.
3. **`TaskSlice` and `KnowledgeDelta` deferred** — not defined, per batch spec §7's own escape hatch ("if defining all seven would create premature design commitment, define only the subset genuinely required"). No A0 consumer needs either yet.
4. **Worktree instead of same-directory branch** — the batch spec's literal §1 describes creating a branch in the existing working directory. This was revised during planning: the existing worktree had 65 uncommitted paths that the user wants preserved untouched, so a separate `git worktree add` was used instead, achieving the same "new dedicated branch from stable baseline" outcome without touching the prototype's working files, index, or uncommitted state.

## 10. Risks / open questions for A1

- `ContextPack.context` and `DecodedRequest.metadata` are untyped `Dict[str, Any]` for now — A1 (Context Resolution) will need to decide whether these stay loosely typed or get their own sub-contracts (session state, Graphify context, ARN result) once real Step 2 logic exists.
- The `EdgeOutcome`/`IntelligenceResult` split assumes edge and local tiers return `EdgeOutcome` (handled/escalate) while extended returns a terminal `IntelligenceResult`. A1/A2 should confirm this shape survives contact with a real local-tier implementation, since local intelligence might also need a genuinely terminal outcome (handled without further escalation) distinct from "escalate."
- `uri_core/core/edge_lifecycle/` is the closest existing analog to the new Edge tier but is currently coupled to the old routing funnel per the reuse map (§6) — A1 should decide whether to adapt pieces of it or design `EdgeIntelligenceProvider` implementations fresh.
- ARN's exact invocation contract ("ARN only when unresolved") was not inspected in A0 — deferred per scope guard §14; needed before Step 2 design can be finalized.
- The existing prototype worktree's 65 uncommitted paths remain uncommitted and untouched; they are unrelated to this batch but the user should be aware they still need eventual attention on their own schedule.
