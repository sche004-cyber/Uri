# GRF-P0-1 — Graphify hint rule in the paired (working-system) path: plan and acceptance criteria

Owner decision OPEN-14, 2026-10-22 ("URI — Consolidated Owner Authorization & Execution Directive", item 4): narrowly
scoped frozen-Core exception for `uri_core/core/paired_reasoning.py` to repair the existing Graphify integration so
that `GRAPHIFY_HINT_ENABLED` and the skill/memory filtering rule are enforced. No Graphify redesign, no feature
expansion, no other frozen change, no dependency change, no canonical integration without separate owner approval.
Baseline: canonical `2aa0141e`. Finding source: P0 audit 2026-10-21 (`developmental.md` §J GRF-P0-1, evidence file
`docs/audit/p0_20261021/evidence/50_lifecycle_graphify_skills.md` on branch `audit/p0-comprehensive-20261021`).

## Problem (source evidence)

- Canonical decision path, `uri_core/core/decision_engine.py:1061-1071`: the Turn State hint is built only when
  `graphify_hint_enabled()` (env `GRAPHIFY_HINT_ENABLED`, default on, `"0"` disables); only records with
  `kind in ("skill", "memory_pointer")` pass (capabilities already reach the Brain through the capability
  directory); an index error gives no hint.
- Paired path, `uri_core/core/paired_reasoning.py` `prepare_canonical_context` (canonical `2aa0141e`): passed
  `index.relevant_subset(request.text, limit=5)` straight into `assemble_turn_state(capability_index_hint=...)`:
  the killswitch was ignored, capability/workflow/connected-service records reached the Brain's Turn State, and an
  index error propagated.

## Change (one frozen file)

`prepare_canonical_context`: import `graphify_hint_enabled` from `decision_engine` (the existing function) and build
the hint with the same rule as the canonical path: killswitch first (index not queried when disabled), keep only
`skill` and `memory_pointer` records, `None` when nothing passes or the index fails. The index is still built and
returned in `prepared["graphify"]` (existing callers and tests unchanged).

Effect today: the paired index is built from the capability directory only, so with this rule the paired hint is
`None` (reported by Turn State as `capability_index_hint` unavailable) until skills or memory pointers are indexed
for that path. That is the existing canonical behaviour for such an index, not a new feature.

Frozen exception record: `scripts/ws_frozen_check.py` `APPROVED["uri_core/core/paired_reasoning.py"]` (exact blob
SHA-256, decision `OPEN-14/GRF-P0-1`, anchor = the code commit, provenance = this file pinned by SHA-256), the same
mechanism as GRAPHIFY-LEAK-1/D12, FCV-01 and FCV-05.

## Acceptance criteria

- AC-1 Enabled (default or `"1"`): only `skill` and `memory_pointer` records reach `capability_index_hint`, in index
  order.
- AC-2 Disabled (`"0"`): no hint, and the index is not queried.
- AC-3 Rejected kinds (`capability`, `workflow`, `connected_service`) never reach the hint; nothing left -> `None`.
- AC-4 An index error or a malformed record gives no hint and no exception.
- AC-5 Same rule text as the canonical path (`decision_engine`).
- AC-6 `prepared["graphify"]` still returns the index; no other behaviour of `prepare_canonical_context` changes.
- AC-7 Only `uri_core/core/paired_reasoning.py` changes among PROTECTED paths; `ws_frozen_check` passes with the new
  exact-blob exception and refuses any other drift.
- AC-8 Tests: `tests/graphify/test_grf_p0_1_paired_hint.py` (9 tests; all 9 fail on `2aa0141e`); Graphify, Phase 1
  boundary and working-system/OI regression suites show no new failures against `2aa0141e`.

## Review

Lifecycle V3 driver (Codex primary, `claude_cli` fallback); a fresh isolated subagent only if the driver records
`NO_INDEPENDENT_REVIEWER` on the exact commit (DEC-095). Canonical integration needs separate owner approval.
