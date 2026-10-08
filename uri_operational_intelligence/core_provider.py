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
    """`create_app(runtime, composition=...)` input: deterministic row + the Runtime v1 row (development)."""
    from uri_core.core.paired_brain import brain_composition
    provider = RuntimeV1Provider(cfg, client)
    comp = brain_composition({selection_row(cfg): provider}, **extra)
    return comp, provider
