# Operational Intelligence: architecture, runtime integration contract, reasoning and orchestration design

Branch `phase/operational-intelligence` (base `037229c`). Package `uri_operational_intelligence/` (new). No frozen
Phase 1 file, accepted Phase 2 file or Runtime v1 artifact was edited (proof: `OI_BASELINE_AND_ISOLATION.md`).

## 1. Design in one picture

```
 user text ──► triage (deterministic, <1 ms) ──► reasoning policy (FAST / NORMAL / ESCALATE)
                 │
   TRIVIAL/QUESTION/ANALYSIS          ACTION                    MULTI_STEP              HARNESS / ESCALATE
                 │                       │                          │                          │
        answer channel (Runtime v1)   URI Core paired loop       planner (NORMAL, schema)   harness choice
        stream, cancel, deadlines     (frozen Phase 1:           → plan proposal            (options, recommendation,
        action-marker guard ──────►   Intent Discovery,          → user approves plan       never selects)
        action-claim guard            confirmation, gates,       → steps: answer channel /
                 ▲                    approval, signed ticket,     Core with the user's
                 └── Core says        client execution,            verbatim words /
                     CONVERSATION     independent verification)    harness choice
                                         │
                                Runtime v1 serves Core's proposer + interpreter seams
                                through oi_composition (create_app(composition=...))
```

Authority does not move. URI Core decides every action. Runtime v1 proposes (Core seams) and talks (answer channel).
OI never approves, claims, settles, or retries an uncertain execution.

## 2. Runtime integration contract (Runtime v1)

| Item | Contract | Implementation |
|---|---|---|
| Configuration | `model_lab/integration/local_brain.json` (frozen, read-only) | `runtime_v1.load_config` |
| Process | at most one `llama-server.exe` on 127.0.0.1:18470 with exactly the frozen argv (freeze record §2) | `runtime_v1.expected_argv` (test pins every frozen flag) |
| Artifact identity | SHA-256 of server binary, `ggml-vulkan.dll`, model, mmproj, MTP draft; full hash on first use and on any size/mtime change, otherwise a stat-matched cache reported as method `cached` | `verify_artifacts` |
| Live identity | listener pid's executable path + exact argv; `/props` model path, `n_ctx` 32768, build `b11425`, 1 slot | `inspect_process`, `live_identity_problems` |
| Start / attach | attach if an authorized instance is READY or LOADING; refuse FOREIGN_INSTANCE / IDENTITY_MISMATCH; start only after artifact MATCH, under a cross-process start lock, inside a kill-on-close Job Object (Phase 2 `spawn_contained`, reused unchanged) | `RuntimeManager.ensure_ready` |
| Stop | only an instance this manager started; success only when the job is confirmed empty | `RuntimeManager.stop` |
| Readiness states | NOT_CONFIGURED, ARTIFACT_MISSING, IDENTITY_MISMATCH, STOPPED, STARTING, LOADING, READY, FOREIGN_INSTANCE, FAILED (+ DEGRADED from performance health) | `Readiness` |
| Streaming | SSE `/v1/chat/completions`; reasoning and answer deltas separated; llama-server `timings` captured verbatim | `brain_client.stream_chat` |
| Cancellation | watcher thread closes the HTTP stream; llama-server sees the disconnect and frees the slot (verified live: slot idle immediately, next request 0.25 s) | `CancelToken` |
| Deadlines | first token 60 s (covers a 30k prefill), idle gap 30 s, total 300 s (configurable) | `Deadlines` |
| Errors | COMPLETE, INCOMPLETE_LENGTH, CANCELLED, TIMEOUT_FIRST_TOKEN, STALLED, DEADLINE_EXCEEDED, INTERRUPTED, UNREACHABLE, HTTP_ERROR, PROTOCOL_ERROR; only COMPLETE is success | `brain_client` |
| Recovery | one automatic retry only for a transport failure before any output (inference has no side effects); never after output began; never to another model | `stream_chat`, `complete_json` |
| Performance health | per-process GPU dedicated/shared memory vs the READY baseline and rolling decode rate → DEGRADED with recovery options (OI-PERF-1) | `perf_monitor` |
| Observability | per call: status, ttft, first answer, total, prompt_n, prompt tok/s, predicted_n, decode tok/s, cache_n, MTP draft_n / accepted | `AnswerOutcome.metrics`, `RuntimeV1Provider.calls` |

Coexistence: the legacy server (port 8000) and Ollama (11434) are never contacted or stopped. Runtime v1 uses only
its configured port. A second OI process attaches instead of starting a competing instance; a foreign process on
18470 is reported, never adopted or killed.

## 3. Core integration (the intended architecture)

Core already exposes the seam: `uri_core.app.paired_server.create_app(runtime, composition=...)` with
`PairedCoordinator(policy, proposer, interpreter, planner)`. OI provides:

- `RuntimeV1Provider`: a `ModelProvider` (Core's provider boundary). FAST tier, temperature 0, thinking off,
  `response_format: json_object`, typed errors (`ProviderUnavailableError`, `ProviderTimeoutError`,
  `ProviderResponseError`) that Core maps to `SELECTED_MODEL_UNAVAILABLE` / `BRAIN_OUTPUT_INVALID`.
- `oi_composition(cfg, client)`: Core's own `BrainProposer` and contract validation, plus three adapter-level
  changes measured on Suite P: B-1 routing of Intent-Discovery capabilities, the qualified interpreter wording with
  verbatim span snapping, and no planner seam. Suite P: stock `brain_composition` 9/12, `oi_composition` 12/12.
- Selection row `("server_local_model", "llamacpp-runtime-v1", "qwen3.6-35b-a3b-ud-iq3_s")`. The user selects it
  explicitly; Core's policy refuses any other row; a down runtime is `SELECTED_MODEL_UNAVAILABLE`, never a fallback.

Owner decision required before production: Phase 2's server profile only lists `client_external_harness` rows
(`uri_supervisor_bridge/composition.py`: server-local-model rows are owner decisions). OI does not change that file;
a production profile that offers the Runtime v1 row needs the owner's approval and its own acceptance.

Constraint found: frozen `runtime_identity.py` refuses unless `git HEAD == e8e3b65` (CONS-7). Live Core tests
therefore run in a materialized test runtime (`scripts/oi_materialize_test_runtime.py`: e8e3b65 + committed Phase 2
OQ overlay + OI files), the same method as the consolidation runbook.

## 4. Reasoning policy (freeze record §4, implemented)

| Rule | Implementation |
|---|---|
| Core seams are FAST | `RuntimeV1Provider` always uses FAST params; `decide(ACTION, "normal")` still returns FAST / `core_seam` |
| Language task FAST unless analysis/planning/comparison/conflict/debugging | deterministic `triage` → `decide` |
| NORMAL = thinking on, budget 768, ≥ 4,000 output tokens | `tier_params(NORMAL)` |
| NORMAL ending at `length` → INCOMPLETE + escalation candidate, never a bigger local retry | `after_result`, `escalation.offer` event |
| ESCALATE is a Core / user decision | OI only emits `escalation.offer` with harness options |
| The model cannot change its budget | budgets exist only in `tier_params` (server-side request parameters) |
| DEEP never local | `depth="deep"` → escalation offer |
| User control | `depth` = auto / fast / normal / deep per turn; applies to language work only |

## 5. Orchestration

- **Simple turns** (TRIVIAL / QUESTION) go straight to the answer channel with zero Core / Brain decision calls
  (edge-first rule). Measured first visible text ~0.25 s on a healthy runtime (see `OI_BENCHMARKS.md`).
- **Action guard (two layers).** Triage sends anything that may change state to Core. For misses, the answer
  channel's system prompt makes the model emit `<<ACTION>>`; the first characters are held back until they cannot be
  the marker, then the generation is cancelled and the turn re-routed to Core with no text shown. Held-out set:
  triage recall 0.75 alone, 1.00 with the marker, false positives 0.05.
- **Action-claim guard.** An answer claiming a completed action while no Core execution happened is flagged
  `UNVERIFIED_ACTION_CLAIM` and corrected in-stream.
- **Core CONVERSATION fallback.** If Core finds nothing to act on, the language request is answered on the answer
  channel (no action ran).
- **Multi-step.** NORMAL-tier planner with a JSON schema (thinking + grammar verified to work together on b11425).
  Deterministic validation: ≤ 8 steps, unique ids, backward-only dependencies, known capabilities only, and every
  action/harness step's `source_span` must be verbatim from the user's request (else downgraded to ask_user).
  Nothing runs before the user approves the plan. Action steps go to Core with the user's verbatim words, so Intent
  Discovery, confirmation, gates and approval apply unchanged.
- **Task ledger.** One JSON file per task (atomic replace + fsync), step state machine, restart recovery: a step
  that may have dispatched becomes UNCERTAIN and is never retried; dependents of an unsuccessful step are SKIPPED;
  pending approvals return to PENDING (Core keeps approvals in memory and fails closed after restart).
- **Harness coordination.** Separate from Brain selection. Options carry usable / why_not (policy, qualification,
  auth, quota, source). `requires_user_choice` is false only for the user's explicit, still-usable choice. Quota:
  Core's own `WAITING_FOR_MODEL` checkpoint + `continue_waiting` (frozen client) is reused; OI excludes the exhausted
  provider from the new options.

## 6. What OI deliberately does not do

- No Core / Phase 2 / Runtime v1 edits; no new reasoning engine, store or permission system inside Core.
- No unbounded local reasoning; no second resident model (no benchmark showed a need: see `OI_BENCHMARKS.md`).
- No shelling out to Claude Code / Codex as a Brain (standing rule); harnesses remain execution providers.
- No production wiring, no service, no startup entry, no change to the legacy server.
