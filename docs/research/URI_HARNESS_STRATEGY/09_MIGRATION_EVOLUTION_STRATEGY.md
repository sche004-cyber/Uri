# 09 — Migration / Evolution Strategy

## Principles

- **Additive, not destructive.** Proven mechanisms are kept, and none are rewritten to fit the new architecture. Harness integration arrives as new ports beside the existing canonical path. This is the same pattern M33 used for the External Capability Contract.
- **Frozen work stays frozen.** The M33.3-R closing audit is in progress (`docs/governance/URI_STATE.yaml`). Nothing here touches the following:
  - `uri_v1/`
  - `uri_core/core/edge/*`
  - RAR/ARN contracts
  - `docs/plans/M33_3_*`
  - governance state
- **Standing rules apply.** Production adoption happens only through explicit INT-* integration events (currently `integration_events: []`). The Four-Stage lifecycle and the Permanent Acceptance Rule apply. `orchestrator.py` must never grow. Experience tier never gates authorisation.
- **Replacement over accretion.** The legacy lesson is that adding decision paths *beside* old ones produced four or more competing mechanisms in `orchestrator.py`. When the harness path takes over agentic work, the corresponding legacy workflow paths are retired in the same milestone. They are not left dormant.

## Stages

| Stage | What | Depends on | Touches production? |
|---|---|---|---|
| **S0 — Finish current work** | Close M33.3-R per its own plan. No change from this study. | — | Per its plan |
| **S1 — Evidence (Wave 0)** | E-N1, E-N2, E-N4, E-N5; then E-N3 as a Four-Stage Stage-1/Stage-2 package for a new milestone (for example "External Harness Provider Bridge") | S0 not required (docs only) | No |
| **S2 — Foundations (Wave 1)** | E-P1, E-P3, E-P2 on at least 2 harness families. Experiment code only in `scratch/` or a research tree. | S1 | No |
| **S3 — Build the seams** (first implementation milestone, if authorised) | (a) HarnessProvider port as an extension of `uri_core/external/`; (b) URI MCP broker exposing *existing* gated capabilities; (c) intelligence broker (I-1 config, then I-2); (d) engine lifecycle for one pinned harness; (e) execution capsule plus a minimal verifier (files/spreadsheets). Feature-flagged OFF. | S2 posture evidence | Flag-off only |
| **S4 — Office exemplar** | E-P5 and E-P7 flows through S3 seams; UI "watch execution" view consuming normalised events; router rule "delegate only when bounded paths do not apply" | S3 | Behind flag; live-verified per the Permanent Acceptance Rule |
| **S5 — Integration event** | INT-* event promoting the harness path for a named task class; retire the superseded legacy workflow paths (for example `workflow_planner.py` templates) in the same milestone | S4 live verification | Yes |
| **S6 — Domain-pack extraction** | Move Office-specific services and rules behind a URI Office pack boundary (E-N5 inventory). Core becomes domain-neutral. | Independent of S3–S5; can run in parallel after S1 | Refactor with behaviour-preservation proof |
| **S7 — Second harness / portability** | Qualify a second harness family through the same port; this satisfies the cross-agent portability rule | S5 | Yes |

## What is reused (not rebuilt)

| Existing asset (`_V1`) | Role in target |
|---|---|
| `uri_core/external/*` (contract, qualification, lifecycle, transports, `operation_store`, `evidence_adapter`, `result_normalizer`, `credentials`) | Base of HarnessProvider and MCP-client capability transport |
| `approval_gate.py`, `approval_store.py`, `decision_gates.py`, `capability_resolver.py`, `EffectType`, `permission_binding.py` | Authority for the broker and for harness permission decisions |
| `capabilities/wrong_binding.py`, RAR/ARN | Capsule references and consequence classes |
| `model_router.py`, providers, `provider_keys.py`, usage meter and ceilings | Behind the intelligence broker |
| `edge_lifecycle/*`, `lease_ownership.py`, M33.1 pinned-install pattern | Engine lifecycle and residency leases |
| `file_store.py` | Workspace staging |
| `uri_v1/evaluation/*`, `uri_v1/results/*` (after their own adoption) | Trace propagation, result versions |
| `scripts/gemma_worker_mcp.py` (development-only) | Pattern reference for MCP guardrails only |

## What is retired (eventually, with evidence)

- The Hermes-derived skill registry/router shadow path (`skill_router_v1.py`, `skill_evaluator_v1.py`, `build_skill_registry_v1.py`, `uri_workspace/skill_registry.json`). It was already unwired in M20. Harness discovery replaces static inventory scans.
- Dead Hermes remnants (`core/skill_evaluator.py:19,333-354`, `core/prompt_builder.py:23`, `core/dispatcher.py:142`, `core/context_budget.py:131,337`). This is a cleanup candidate, not an action of this study.
- Template workflow planning for agentic tasks, once S5 promotes the harness path.

## Stale-documentation findings (recorded here, not fixed)

This study found the following repository documents out of date. It records them for a later governance pass instead of editing them silently.

1. `ARCHITECTURE.md:47-51` still says "M22.3 is next".
2. `docs/architecture/EXTERNAL_CAPABILITY_CONTRACT.md` header says "DRAFT", but it was implemented in M33 A–D.
3. M32.1 is `RESERVED_NOT_STARTED` in `URI_STATE.yaml`, yet `approval_resumption.py` is committed (FLAG-OFF) with a completion report.
4. The `canonical_execution.py` docstring says "Default OFF", but the code defaults ON.
5. `ARCHITECTURE.md` "AO-2" roles section predates AO-4.
6. The `uri-agent` main worktree carries substantial uncommitted work (38 modified tracked files, including `server.py` +981 lines). Any legacy-derived evidence from those files is unreleased.
