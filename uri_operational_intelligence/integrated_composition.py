"""Working-system server composition: the accepted Phase 2 policy rows plus the Runtime v1 Brain row.

`create_app(runtime, composition=...)` input for `scripts/run_uri_integrated_server.py` (WS blueprint W3).

The result offers these selection rows:
  * the deterministic no-Brain row (always present);
  * every `client_external_harness` row in the server's Phase 2 policy file, which was read with the accepted loader
    (`uri_supervisor_bridge.composition.load_policy_rows`, so a malformed file still refuses startup);
  * exactly one `server_local_model` row: Runtime v1 (`llamacpp-runtime-v1`, the model id from the frozen
    `local_brain.json`).

Seams are routed by the turn's explicit selection:
  * Runtime v1 row: the OI proposer (Core's BrainProposer + B-1 routing) and the qualified interpreter
    (`core_provider.oi_composition`, Suite P 12/12). There is no planner seam, the same as `oi_composition`.
  * Any other row: Core's own `deterministic_proposer`, and no interpreter suggestion. This is exactly what the
    accepted Phase 2 profile does for harness rows, because that profile passes no proposer and no interpreter.

Nothing here substitutes one row for another. An unavailable Runtime v1 surfaces as SELECTED_MODEL_UNAVAILABLE from
the provider and is never replaced by the deterministic row.
"""
from __future__ import annotations


def integrated_server_composition(policy_file, cfg, client) -> dict:
    from uri_core.core.paired_coordinator import deterministic_proposer
    from uri_core.core.paired_reasoning import ReasoningSelectionPolicy
    from uri_supervisor_bridge.composition import QUALIFIED_CAPABILITIES, load_policy_rows

    from .core_provider import oi_composition, selection_row

    phase2_rows = load_policy_rows(policy_file)          # raises PolicyError on a malformed file (fail closed)
    oi, provider = oi_composition(cfg, client)
    row = selection_row(cfg)

    def is_brain(selection):
        return (selection.kind, selection.provider, selection.model) == row

    def proposer(prepared, request, selection):
        if is_brain(selection):
            return oi["proposer"](prepared, request, selection)
        return deterministic_proposer(prepared, request, selection)

    def interpreter(text, capability, slots, selection):
        if is_brain(selection):
            return oi["interpreter"](text, capability, slots, selection)
        return {}

    rows = frozenset(phase2_rows) | {row}
    return {"policy": ReasoningSelectionPolicy(rows), "proposer": proposer, "interpreter": interpreter,
            "qualified": QUALIFIED_CAPABILITIES}, provider


def offered_rows(composition) -> list:
    """The rows a composition offers, sorted, as (kind, provider, model) triples (diagnostics and tests)."""
    return sorted(composition["policy"].supported, key=str)
