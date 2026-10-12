"""Brain catalog for the working system: which reasoning sources the user can select, and why the others cannot be.

Rules (WS blueprint AC-9):
  * Runtime v1 is the default Brain row. It is the frozen, qualified local Brain.
  * A row is selectable only if it is qualified AND the server composition offers it
    (`integrated_composition.integrated_server_composition`). Today that means Runtime v1 and the deterministic
    no-Brain row. Any other local model is listed only as "not qualified". There is no probing, no discovery from
    installed binaries and no advertisement-based rows.
  * Cloud rows come from `cloud_policy` and are never selectable: activation is disabled.
  * Availability (READY or not) is reported. It never changes the selection; there is no fallback.
  * Only an explicit, structured `brain_select` from the user changes the selection, never a model or typed text.
"""
from __future__ import annotations

from . import cloud_policy
from .core_provider import PROVIDER_ID

DETERMINISTIC = {"kind": "server_local_model", "provider": "uri-deterministic", "model": None}


def runtime_v1_selection(cfg) -> dict:
    return {"kind": "server_local_model", "provider": PROVIDER_ID, "model": cfg["model"]["id"]}


def catalog(cfg, readiness_state: str | None, selected: dict) -> dict:
    rv1 = runtime_v1_selection(cfg)
    rows = [
        {"id": "runtime-v1", "display": "Runtime v1 (local)", "selection": rv1, "default": True, "selectable": True,
         "qualified": True, "qualification": "Runtime v1 freeze 2026-10-07 (stock llama.cpp b11425 + MTP)",
         "answers_questions": True, "available": readiness_state == "READY", "state": readiness_state or "UNKNOWN",
         "why_not": None if readiness_state == "READY" else "Runtime v1 is " + (readiness_state or "UNKNOWN")},
        {"id": "deterministic", "display": "No Brain (deterministic rules)", "selection": dict(DETERMINISTIC),
         "default": False, "selectable": True, "qualified": True, "qualification": "Core deterministic source",
         "answers_questions": False, "available": True, "state": "READY",
         "why_not": None, "note": "Core acts on recognised commands only; open questions are not answered."},
        {"id": "other-local", "display": "Other local models", "selection": None, "default": False,
         "selectable": False, "qualified": False, "qualification": None, "answers_questions": False,
         "available": False, "state": "NOT_QUALIFIED",
         "why_not": "No qualification record. A model must pass the model_lab qualification before it can be offered."},
    ]
    for p in cloud_policy.providers():
        rows.append({"id": "cloud-" + p["id"], "display": p["display"] + " (cloud)", "selection": None,
                     "default": False, "selectable": False, "qualified": False, "qualification": None,
                     "answers_questions": False, "available": False, "state": "DISABLED",
                     "why_not": "Cloud activation is disabled (no credentials, $%.2f/month policy)." % cloud_policy.MONTHLY_CAP_USD})
    for r in rows:
        r["selected"] = r["selection"] is not None and r["selection"] == selected
    return {"rows": rows, "selected": selected, "fallback": "none"}


def resolve(cfg, row_id: str) -> dict:
    """Selection for an explicit user choice. Unknown or non-selectable rows are refused (fail closed)."""
    if row_id == "runtime-v1":
        return runtime_v1_selection(cfg)
    if row_id == "deterministic":
        return dict(DETERMINISTIC)
    raise ValueError("BRAIN_ROW_NOT_SELECTABLE")
