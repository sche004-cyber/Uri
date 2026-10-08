"""Runtime v1 as a Core Brain row, through Core's accepted seam (no Core change).

Core's C5 transport (`uri_core.core.paired_brain.brain_composition`) accepts `{(kind, provider, model): ModelProvider}`
and serves the proposer, interpreter and planner seams from the user's explicitly selected row. This adapter is that
ModelProvider for Runtime v1:

  * every call is FAST tier (thinking off, temperature 0): rule 1 of the reasoning policy;
  * JSON-only output is enforced by the server's grammar (`response_format: json_object`), because every Core seam
    expects one JSON object; Core still validates the contract and fails closed on anything else;
  * a runtime failure raises ProviderUnavailableError / ProviderTimeoutError; Core maps it to
    SELECTED_MODEL_UNAVAILABLE and never substitutes another source.

`runtime_v1_composition()` is a DEVELOPMENT composition. Offering a server_local_model row in a production server is
an owner decision (uri_supervisor_bridge.composition: "Cloud-model and server-local-model rows stay owner decisions").
"""
from __future__ import annotations

import time

from uri_core.core.model_providers.base import (ModelProvider, ModelProviderStatus, ModelResponse,
                                                ProviderResponseError, ProviderTimeoutError,
                                                ProviderUnavailableError)

from . import brain_client as BC
from .reasoning_policy import FAST, tier_params

PROVIDER_ID = "llamacpp-runtime-v1"


def selection_row(cfg):
    return ("server_local_model", PROVIDER_ID, cfg["model"]["id"])


def selection(cfg):
    kind, provider, model = selection_row(cfg)
    return {"kind": kind, "provider": provider, "model": model}


class RuntimeV1Provider(ModelProvider):
    def __init__(self, cfg, client: BC.BrainClient, *, timeout_s=60.0, readiness=None):
        self.cfg, self.client, self.timeout_s = cfg, client, timeout_s
        self.readiness = readiness            # optional callable -> Readiness (for describe())
        self.calls = []                       # observability: one row per seam call (no prompt content)

    def complete(self, *, system, user, temperature=0.0, max_tokens=None, tools=None) -> ModelResponse:
        body = {"model": "local", "messages": [{"role": "system", "content": system}, {"role": "user", "content": user}],
                "response_format": {"type": "json_object"}, **tier_params(FAST, use="seam", max_tokens=max_tokens)}
        t0 = time.monotonic()
        res = self.client.complete_json(body, timeout_s=self.timeout_s)
        self.calls.append({"status": res.status, "s": round(time.monotonic() - t0, 3), "finish": res.finish_reason,
                           "prompt_n": res.timings.get("prompt_n"), "predicted_n": res.timings.get("predicted_n"),
                           "cache_n": res.timings.get("cache_n"), "retried": res.retried})
        if res.status == BC.UNREACHABLE:
            raise ProviderUnavailableError("RUNTIME_V1_UNREACHABLE")
        if res.status == BC.DEADLINE_EXCEEDED:
            raise ProviderTimeoutError("RUNTIME_V1_TIMEOUT")
        if res.status == BC.INCOMPLETE_LENGTH:
            # A truncated JSON object is not a proposal. Core reports BRAIN_OUTPUT_INVALID / unavailable.
            raise ProviderResponseError("RUNTIME_V1_OUTPUT_TRUNCATED")
        if res.status != BC.COMPLETE:
            raise ProviderUnavailableError("RUNTIME_V1_" + res.status)
        return ModelResponse(content=res.text, model=self.cfg["model"]["id"], provider=PROVIDER_ID,
                             prompt_tokens=res.timings.get("prompt_n"), eval_tokens=res.timings.get("predicted_n"),
                             duration_seconds=res.total_s)

    def describe(self) -> ModelProviderStatus:
        state, detail = "UNKNOWN", None
        if self.readiness is not None:
            try:
                r = self.readiness()
                state, detail = r.state, r.detail
            except Exception as exc:   # describe() must never raise
                state, detail = "UNKNOWN", type(exc).__name__
        return ModelProviderStatus(provider_name=PROVIDER_ID, model_name=self.cfg["model"]["id"], location="local",
                                   context_window=int(self.cfg["runtime"]["ctx"]), supports=("text", "vision"),
                                   available=state == "READY", detail=detail or state)


def runtime_v1_composition(cfg, client, **extra):
    """Core's stock `brain_composition` with the Runtime v1 row (proposer + interpreter + planner seams).
    Kept as the comparison baseline; Suite P measured 9/12 with it (see OI_BENCHMARKS.md)."""
    from uri_core.core.paired_brain import brain_composition
    provider = RuntimeV1Provider(cfg, client)
    comp = brain_composition({selection_row(cfg): provider}, **extra)
    return comp, provider


# Interpreter wording qualified with Runtime v1 in Suite P (model_lab/lab/paired.py INTERPRETER_SYSTEM, 12/12).
INTERPRETER_SYSTEM = (
    "You fill slots for URI's intent discovery. Given the user's message, the capability and the slot names, return "
    "a JSON object mapping each slot to the EXACT substring of the user's message that supplies it, or null if the "
    "message does not supply it. Copy words verbatim; never paraphrase, complete, translate or add information. For "
    "a \"statement\" slot return the WHOLE sentence that states the fact (subject included, final punctuation kept), "
    "never a lone value such as a number or name. Reply ONLY with JSON.")


def snap_to_user_span(value, text):
    """Extend a verbatim span over sentence punctuation that immediately follows it in the user's text (Core finding
    B-3: Core's groundedness tokenizer keeps that punctuation on the final token). Never adds a word; a value that is
    not verbatim is returned unchanged and Core rejects it (INTENT_UNGROUNDED_VALUE)."""
    if not isinstance(value, str):
        return value
    i = text.find(value)
    if i < 0:
        return value
    j = i + len(value)
    while j < len(text) and text[j] in ".!?;:,":
        j += 1
    return text[i:j]


def route_intent_capabilities(obj, prepared):
    """Documented limitation B-1: a proposal that names an Intent-Discovery capability without an action would make
    Core fail closed with REFUSED_UNCONFIRMED_ACTION. Route it to Core's own budgeted clarification by naming the
    capability's action with NO inputs. Arguments still come only from the user's confirmed words."""
    from uri_core.core.intent_discovery import SCHEMAS
    cap = obj.get("capability") if isinstance(obj, dict) else None
    if obj.get("mode") in ("clarification", "single_action") and cap in SCHEMAS and not obj.get("actions"):
        detail = prepared["directory"].describe(cap)
        if detail and detail.get("actions"):
            obj = dict(obj, mode="single_action", clarification=None,
                       actions=[{"name": sorted(detail["actions"])[0], "inputs": {}}])
    return obj


def oi_composition(cfg, client):
    """The OI development composition for `create_app(runtime, composition=...)`.

    Same accepted seam and the same Core validation as `brain_composition`, with three adapter-level differences
    measured on Suite P: (1) B-1 routing on the proposer output, (2) the qualified interpreter wording plus verbatim
    span snapping, (3) NO planner seam: for single-action capabilities the planner's proposals only conflicted with
    the confirmed intent (Core rejected and recompiled them) and cost one extra Brain call per action.
    """
    from uri_core.core.paired_brain import DETERMINISTIC, BrainProposer
    from uri_core.core.paired_reasoning import ReasoningSelectionPolicy, ReasoningUnavailable
    provider = RuntimeV1Provider(cfg, client)
    row = selection_row(cfg)
    core_proposer = BrainProposer({row: provider})

    def proposer(prepared, request, selection):
        return route_intent_capabilities(core_proposer(prepared, request, selection), prepared)

    def interpreter(text, capability, slots, selection):
        if (selection.kind, selection.provider, selection.model) == DETERMINISTIC:
            return {}
        if (selection.kind, selection.provider, selection.model) != row:
            raise ReasoningUnavailable("SELECTED_MODEL_UNAVAILABLE")
        import json as _json
        try:
            resp = provider.complete(system=INTERPRETER_SYSTEM, user=_json.dumps(
                {"message": text, "capability": capability, "slots": list(slots)}, ensure_ascii=False), max_tokens=200)
            parsed = _json.loads(resp.content)
        except ReasoningUnavailable:
            raise
        except ValueError:
            raise ReasoningUnavailable("BRAIN_OUTPUT_INVALID") from None
        except Exception:
            raise ReasoningUnavailable("SELECTED_MODEL_UNAVAILABLE") from None
        if not isinstance(parsed, dict):
            raise ReasoningUnavailable("BRAIN_OUTPUT_INVALID")
        # Core re-checks every value against the user's words and always asks for confirmation.
        return {k: snap_to_user_span(v, text) for k, v in parsed.items()
                if k in slots and isinstance(v, str) and v.strip()}

    comp = {"policy": ReasoningSelectionPolicy(core_proposer.rows()), "proposer": proposer, "interpreter": interpreter}
    return comp, provider
