"""The /ask seam for harness-first handling (default off: URI_HARNESS_FIRST=1 enables it).

Current scope, set by measured evidence (docs/plans/HARNESS_FIRST_EDGE_DEV_RESULTS.md): only purely
social turns are handled here, by a local Edge text model with URI validation. Every other turn
returns None and continues down the existing /ask chain unchanged. The single routing authority is
S6 (`evaluate_intelligence_route`); this seam only supplies its inputs and never routes by itself.
"""
from __future__ import annotations

import os
import time
from datetime import datetime, timezone
from typing import Any, Optional
from urllib.parse import urlparse

from uri_core.core.edge.routing_policy import (IntelligenceRouteRequest, RouteTarget, WorkRole,
                                                evaluate_intelligence_route)
from uri_core.core.edge.runtime_inventory import EdgeRuntimeInventory, RuntimeProfile
from uri_core.core.edge.settings import EdgeSettings

from . import edge_chat
from .social import social_intent

FLAG = "URI_HARNESS_FIRST"
_RUNTIME = "harness-edge-ollama"


def enabled() -> bool:
    return os.environ.get(FLAG, "").strip().lower() in {"1", "true", "on", "yes"}


def _loopback(url: str) -> bool:
    return (urlparse(url).hostname or "") in {"127.0.0.1", "localhost", "::1"}


def _pending_approvals(context, session_id) -> bool:
    try:
        from uri_core.core.approval_resumption import find_resumable_actions
        store = getattr(getattr(context.orchestrator, "approval_gate", None), "approval_store", None)
        return bool(store is not None and find_resumable_actions(store, session_id))
    except Exception:
        return True   # unknown counts as pending: never answer chat over a possible approval


def _workflow_waiting(context, session_id) -> bool:
    try:
        session = context.orchestrator.session_manager.get_session(session_id)
        return session.active_workflow is not None and session.active_workflow_status == "waiting_for_input"
    except Exception:
        return True   # unknown counts as waiting


def _user_settings(principal) -> EdgeSettings:
    try:
        from uri_core.core.edge.settings import EdgeSettingsStore
        if principal is not None and getattr(principal, "user_id", None):
            return EdgeSettingsStore(principal.user_id).load()
    except Exception:
        pass
    return EdgeSettings()


def route_social(settings: EdgeSettings, model: str):
    """S6 evaluation for the Edge chat specialist using a settings view (user's mode and Edge ON/OFF
    unchanged; only the evaluated Edge model is the chat specialist). Nothing is written back."""
    view = EdgeSettings(**{**settings.__dict__, "edge": {"runtime_id": _RUNTIME, "model_id": model}})
    inv = EdgeRuntimeInventory(runtimes={_RUNTIME: RuntimeProfile(_RUNTIME, frozenset({model}))})
    return evaluate_intelligence_route(view, inv, IntelligenceRouteRequest(
        role=WorkRole.SUBSTANTIVE, capable_available=True, auto_capable_model_id="configured-main-brain",
        edge_role_qualified=True, edge_warm=True, resource_admitted=True, edge_sufficient=True))


def try_harness_first(*, context: Any, principal: Any, payload: Any, current_turn_attachments) -> Optional[dict]:
    if not enabled():
        return None
    t0 = time.perf_counter()
    text = getattr(payload, "text", "") or ""
    if current_turn_attachments or getattr(payload, "model_override", None) is not None:
        return None
    intent = social_intent(text)
    sid = getattr(payload, "session_id", None)
    if intent is None or _pending_approvals(context, sid) or _workflow_waiting(context, sid):
        return None
    if not _loopback(edge_chat.OLLAMA_URL):
        return None
    model = edge_chat.DEFAULT_MODEL
    route = route_social(_user_settings(principal), model)
    if route.target != RouteTarget.EDGE:
        return None     # Edge off, MAIN_BRAIN_PREFERRED or limitation: the normal chain decides
    inspect_ms = (time.perf_counter() - t0) * 1000
    chat = edge_chat.generate(text, intent, model=model)
    total_ms = (time.perf_counter() - t0) * 1000
    cls = "HARNESS_PLUS_EDGE" if chat.source == "edge_model" else "HARNESS_COMPLETE"
    try:
        context.orchestrator.conversation_history.append_turn(
            session_id=payload.session_id, turn_id=f"turn-{datetime.now(timezone.utc).timestamp()}",
            user_text=text, response_text=chat.text, status="success",
            serving_provider="ollama (edge)" if chat.source == "edge_model" else "uri (deterministic)",
            serving_model=model if chat.source == "edge_model" else None)
    except Exception:
        pass
    harness = {"class": cls, "intent": intent, "edge_model": model if chat.source == "edge_model" else None,
               "reply_source": chat.source, "reject_reason": chat.reject_reason,
               "inspect_ms": round(inspect_ms, 2), "edge_ms": round(chat.latency_ms, 1), "total_ms": round(total_ms, 1),
               "edge_prompt_chars": chat.prompt_chars, "route": route.target.value, "route_reasons": list(route.reason_codes)}
    return {
        "status": "success",
        "session_id": payload.session_id,
        "semantic_analysis": None,
        "execution": {"status": "not_required", "capability": None, "source": "harness_first_social"},
        "response": {"message": chat.text},
        "narrative": chat.text,
        "error": None,
        "_harness": harness,
        "_edge_routing": {
            "disposition": "HARNESS_EDGE_CHAT" if chat.source == "edge_model" else "HARNESS_TEMPLATE",
            "reason_codes": ("HARNESS_FIRST", "SOCIAL_TURN", chat.source.upper()),
            "candidate": model, "runtime_id": "ollama", "latency_ms": int(round(chat.latency_ms)),
            "confidence": None, "threshold_percent": None, "shortlist_size": None, "capability_id": None,
        },
    }
