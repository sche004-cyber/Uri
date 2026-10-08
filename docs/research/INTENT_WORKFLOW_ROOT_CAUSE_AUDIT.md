# Intent workflow integration reconnaissance — 2026-10-04

Development candidate only; no production adoption or independent qualification.
Scope authority: User's Intent Discovery, Intent Audit & Harness Workflow Integration assignment in the current Codex chat.

| Existing interface | Actual scope | Connection |
|---|---|---|
| `ModelReasoningGateway.build_reasoning_request`, `reason`; `default_model_callable` | Existing Core reasoning/provider boundary; no capability execution in gateway | Reuse for adaptive interpretation, never a fixed questionnaire |
| `assemble_turn_state`, `build_task_context` | Read-only context projection; ContextBuilder requirements are task-specific | Preserve facts/evidence separation; readiness is not intent understanding |
| `GraphifyIndex.relevant_subset`, `graph_query`, `build_graph_context` | Existing capability pointers and per-user entity graph | Use existing caller-owned data, not repository graph as user memory |
| `RARQuery`, `resolve_rar_deterministic_extended` | Bounded research/reference resolver, not general production adoption | Read-only candidate resolution; preserve uncertainty and provenance |
| `ARNEngine`, `trigger_not_found_recovery` | ARN.1 narrowing/repeat avoidance, not a cross-session memory store | Track missed lookups; history comes from existing memory/history |
| `Retriever.retrieve`, `MemoryAdapter.project`, `URIIntake.capture` | URI-Memory grounded retrieval; integration unadopted | Operator-supplied, user-scoped retrieval collaborator; no fabricated source IDs |
| Context Bridge `capsule verify`, `show --claim` | Human-curated, freshness-bound offline experiment | Optional evidence collaborator; hash agreement is not semantic authority |
| HarnessController / DesktopHarnessTest / checkpoint inspector | Provisional fixed-task preparation, approvals, recovery | Reuse discovery and presentation; never send general packages to fixed repair |

Missing: cycle-scoped question accounting, version-bound acceptance/correction, general intent envelope, preparation-only endpoint/UI connection. Production RAR/Memory adoption (S13/INT), qualified general execution, native-session input transport, and observed profile admission remain separate gates.

Protected: URI Core and frozen M37/M38/reference sources; installed accounts/configuration; existing candidate/assigned checkout; native credentials. No provider launch, production promotion, commit or push.
