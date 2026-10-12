"""C5 Brain transport: a configurable, provider-neutral proposer for the paired coordinator.

URI's Brain is whichever ModelProvider the trusted composition maps to an exact reasoning
selection row. Nothing here names or prefers a model: the composition supplies
{("server_local_model", provider, model): ModelProvider}, and the user selects a row explicitly.

The Brain only PROPOSES, using the existing decision contract (DECISION_CONTRACT_SYSTEM_PROMPT,
the canonical decision request already prepared from Turn State, and the existing validator).
Intent discovery, deterministic gates, approval, ticket, claim and independent verification are
unchanged and still decide. A selected Brain that fails or answers outside the contract is
reported as unavailable or invalid; URI never substitutes another reasoning source.

External execution harnesses are not Brains: they stay client-side execution providers
(uri_harness_adapters), selected per task, and never receive this proposer role.
"""
from __future__ import annotations

import json

from uri_core.client_contracts import canonical
from uri_core.core.paired_reasoning import ReasoningSelectionPolicy, ReasoningUnavailable

DETERMINISTIC = ("server_local_model", "uri-deterministic", None)
# Server-side transport only. A client cloud model would need client-held credentials and a client
# transport; it is not provided here and stays unavailable.
BRAIN_KINDS = {"server_local_model"}
MAX_TOKENS = 500


class BrainProposer:
    def __init__(self, brains, deterministic=None):
        rows = dict(brains)
        for key in rows:
            if (not isinstance(key, tuple) or len(key) != 3 or key[0] not in BRAIN_KINDS or key == DETERMINISTIC
                    or not isinstance(key[1], str) or not key[1]):
                raise ValueError("BRAIN_ROW_INVALID")
        self.brains = rows
        if deterministic is None:
            from uri_core.core.paired_coordinator import deterministic_proposer as deterministic
        self.deterministic = deterministic

    def rows(self):
        return set(self.brains) | {DETERMINISTIC}

    def _ask(self, selection, system, user):
        """One call to exactly the selected Brain row -> parsed JSON. Never another source, never a retry."""
        provider = self.brains.get((selection.kind, selection.provider, selection.model))
        if provider is None:
            raise ReasoningUnavailable("SELECTED_MODEL_UNAVAILABLE")
        try:
            response = provider.complete(system=system, user=user, temperature=0.0, max_tokens=MAX_TOKENS)
            text = (getattr(response, "content", None) or "").strip()
        except Exception:
            # No retry against another provider or the deterministic rules: the user chose this Brain.
            raise ReasoningUnavailable("SELECTED_MODEL_UNAVAILABLE") from None
        if text.startswith("```"):
            text = text.replace("```json", "").replace("```", "").strip()
        try:
            return json.loads(text)
        except ValueError:
            raise ReasoningUnavailable("BRAIN_OUTPUT_INVALID") from None

    @staticmethod
    def _contract(parsed, prepared):
        from uri_core.core.decision_engine import _validate_contract
        directory = prepared["directory"]
        known = {entry["capability_id"] for entry in directory.summaries()}
        outcome = _validate_contract(parsed, known, directory)
        if outcome.status != "ok" or not isinstance(outcome.contract, dict):
            raise ReasoningUnavailable("BRAIN_OUTPUT_INVALID")
        return outcome.contract

    def __call__(self, prepared, request, selection):
        """Proposer seam: what the user is asking for, in the existing decision contract."""
        if (selection.kind, selection.provider, selection.model) == DETERMINISTIC:
            return self.deterministic(prepared, request, selection)
        return self._contract(self._ask(selection, _system_prompt(), canonical(prepared["request"]).decode()),
                              prepared)

    def interpret(self, text, capability, slots, selection):
        """Interpreter seam: which of the user's own words fill which slot. Intent discovery keeps only values
        that occur verbatim in the user's text and always asks the user to confirm them."""
        if (selection.kind, selection.provider, selection.model) == DETERMINISTIC:
            return {}
        parsed = self._ask(selection, INTERPRETER_PROMPT,
                           canonical({"text": text, "capability": capability, "slots": list(slots)}).decode())
        if not isinstance(parsed, dict):
            raise ReasoningUnavailable("BRAIN_OUTPUT_INVALID")
        return {k: v for k, v in parsed.items() if k in slots and isinstance(v, str) and v.strip()}

    def plan(self, prepared, request, selection, confirmed_intent):
        """Planner seam: the execution proposal for exactly the confirmed intent (None = no elaboration).
        The coordinator rejects any proposal that changes WHAT was confirmed and recompiles it."""
        if (selection.kind, selection.provider, selection.model) == DETERMINISTIC:
            return None
        user = canonical({"decision_request": prepared["request"], "confirmed_intent": confirmed_intent,
                          "task": "Return the single_action decision contract that carries out exactly the "
                                  "confirmed_intent: same capability, its values unchanged."}).decode()
        return self._contract(self._ask(selection, _system_prompt(), user), prepared)


def _system_prompt():
    from uri_core.core.decision_engine import DECISION_CONTRACT_SYSTEM_PROMPT
    return DECISION_CONTRACT_SYSTEM_PROMPT


INTERPRETER_PROMPT = (
    "You map a user's request onto named slots. Reply with ONE JSON object whose keys are slot names and whose "
    "values are copied EXACTLY, character for character, from the user's text, or null when the text does not "
    "contain that value. Never paraphrase, translate, complete, correct or invent a value. No prose.")


def brain_composition(brains, **extra):
    """Trusted composition: the deterministic no-Brain row plus exactly the configured Brain rows.

    The same explicitly selected row serves all three seams of a turn: proposer, interpreter, planner."""
    proposer = BrainProposer(brains)
    return {"policy": ReasoningSelectionPolicy(proposer.rows()), "proposer": proposer,
            "interpreter": proposer.interpret, "planner": proposer.plan, **extra}
