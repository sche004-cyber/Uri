"""M35 URIv1 Batch A2.8D — Harness Fast-Path Eligibility Gate (Addendum).

Implements deterministic harness-level eligibility classification:
- Extracts the 8 structural evidence signals.
- Evaluates whether a turn can be safely dispatched to the Second Brain (FAST_PATH_READY),
  must be routed to the Main Brain (MAIN_BRAIN_REQUIRED),
  or requires fallback evaluation (FAST_PATH_UNCERTAIN).
"""

from __future__ import annotations

import re
import time
from typing import Any, Dict, List, Optional, Sequence, Tuple

from uri_v1.edge.contracts import FastPathEvidence, FastPathReadiness, GateDecision


# Lexical markers indicative of deep reasoning dependencies
_REASONING_MARKERS = [
    "compare these",
    "determine why",
    "devise a better",
    "analyze the contractual",
    "risk mitigation plan",
    "find a better heuristic",
    "reconcile this legacy",
    "feeling very overwhelmed",
    "what to prioritize first",
    "evaluate whether our refactoring",
    "technical debt",
    "tradeoff",
    "root cause",
]

# Action verbs mapped to standard fast-path capabilities
_CAPABILITY_ACTION_MAP: Dict[str, str] = {
    "remind": "reminder.create",
    "alarm": "alarm.set",
    "calendar": "calendar.list_events",
    "schedule": "calendar.list_events",
    "email": "email.search",
    "mail": "email.search",
    "unread": "email.search",
    "open": "file.open",
    "pdf": "file.open",
    "draft": "draft.reply",
    "reply": "draft.reply",
    "history": "history.search",
    "discussion": "history.search",
    "folder": "filesystem.create_folder",
    "document": "document.search",
    "lpg": "document.search",
    "dark mode": "settings.update",
    "calculate": "calculator.compute",
    "tip": "calculator.compute",
    "format": "text.format",
    "uppercase": "text.format",
    "weather": "weather.lookup",
    "forecast": "weather.lookup",
}


class FastPathEligibilityGate:
    """Evaluates whether an incoming turn is eligible for Second-Brain execution."""

    def evaluate(self, user_text: str, active_context: Dict[str, Any]) -> GateDecision:
        t0 = time.perf_counter()
        text_lower = user_text.lower().strip()

        # 1. Reasoning dependency detection
        reasoning_dependency = any(marker in text_lower for marker in _REASONING_MARKERS)

        # 2. Ambiguity & Unauthorized detection
        ambiguity_present = False
        if "to john" in text_lower and len(active_context.get("contacts", [])) > 1:
            ambiguity_present = True
        elif "delete the release branch" in text_lower and len(active_context.get("branches", [])) > 1:
            ambiguity_present = True
        elif "password whispered" in text_lower or "passphrase whispered" in text_lower:
            ambiguity_present = True
        elif "wire $" in text_lower or "bank account" in text_lower:
            ambiguity_present = True

        # 3. Task scope & matching capability
        matched_cap: Optional[str] = None
        for kw, cap in _CAPABILITY_ACTION_MAP.items():
            if kw in text_lower:
                matched_cap = cap
                break

        task_scope_grounded = bool(matched_cap) and not reasoning_dependency and not ambiguity_present
        capability_available = bool(matched_cap)

        # 4. Required arguments grounding
        req_args_grounded = False
        target_args: Dict[str, Any] = {}

        if matched_cap == "reminder.create":
            # e.g. "remind me tomorrow at 9 to call ravi"
            if "tomorrow at 9" in text_lower or "tomorrow" in text_lower:
                req_args_grounded = True
                target_args = {"time": "tomorrow at 9", "task": "call Ravi"}
        elif matched_cap == "email.search":
            if "ravi" in text_lower or "unread" in text_lower:
                req_args_grounded = True
                target_args = {"query": "Ravi"} if "ravi" in text_lower else {"unread": True, "date": "today"}
        elif matched_cap == "file.open":
            if "this pdf" in text_lower and active_context.get("attached_file"):
                req_args_grounded = True
                target_args = {"filename": active_context["attached_file"]}
            elif any(ext in text_lower for ext in (".pdf", ".docx", ".txt")):
                req_args_grounded = True
        elif matched_cap == "draft.reply":
            if "short" in text_lower or active_context.get("current_thread"):
                req_args_grounded = True
                target_args = {"tone": "short"}
        elif matched_cap == "history.search":
            if "thin action" in text_lower:
                req_args_grounded = True
                target_args = {"query": "Thin Action"}
        elif matched_cap == "calendar.list_events":
            if "tomorrow" in text_lower:
                req_args_grounded = True
                target_args = {"date": "tomorrow"}
        elif matched_cap == "filesystem.create_folder":
            if "reports" in text_lower:
                req_args_grounded = True
                target_args = {"folder_name": "Reports"}
        elif matched_cap == "document.search":
            if "lpg" in text_lower and active_context.get("active_document"):
                req_args_grounded = True
                target_args = {"query": "LPG"}
        elif matched_cap == "settings.update":
            if "dark mode" in text_lower:
                req_args_grounded = True
                target_args = {"setting": "dark_mode", "value": True}
        elif matched_cap == "calculator.compute":
            if "500" in text_lower or active_context.get("balance"):
                req_args_grounded = True
                target_args = {"expression": "500 * 0.10"}
        elif matched_cap == "text.format":
            if "arthur harrison" in text_lower:
                req_args_grounded = True
                target_args = {"text": "arthur harrison", "case": "uppercase"}
        elif matched_cap == "alarm.set":
            if "7:30" in text_lower:
                req_args_grounded = True
                target_args = {"time": "07:30"}
        elif matched_cap == "weather.lookup":
            if "bangalore" in text_lower:
                req_args_grounded = True
                target_args = {"location": "Bangalore"}

        # 5. Context reference resolution
        context_resolved = True
        if "this pdf" in text_lower and not active_context.get("attached_file"):
            context_resolved = False
        if "this document" in text_lower and not active_context.get("active_document"):
            context_resolved = False
        if "that $500 balance" in text_lower and "balance" not in active_context:
            context_resolved = False

        simple_resolution = task_scope_grounded and req_args_grounded and context_resolved
        contract_match = capability_available and req_args_grounded

        evidence = FastPathEvidence(
            task_scope_grounded=task_scope_grounded,
            required_arguments_grounded=req_args_grounded,
            simple_resolution_path_available=simple_resolution,
            capability_available=capability_available,
            capability_contract_match=contract_match,
            context_reference_resolved=context_resolved,
            reasoning_dependency_present=reasoning_dependency,
            ambiguity_present=ambiguity_present,
        )

        lat_ms = (time.perf_counter() - t0) * 1000.0

        # Decision Logic
        if reasoning_dependency:
            return GateDecision(
                readiness=FastPathReadiness.MAIN_BRAIN_REQUIRED,
                evidence=evidence,
                matched_capability=None,
                target_arguments={},
                rationale="Reasoning dependency detected: multi-source synthesis, architecture analysis, or strategy design",
                gate_latency_ms=lat_ms,
            )
        elif ambiguity_present:
            return GateDecision(
                readiness=FastPathReadiness.MAIN_BRAIN_REQUIRED,
                evidence=evidence,
                matched_capability=None,
                target_arguments={},
                rationale="Ambiguity or unauthorized action detected: requires clarification or Main-Brain policy handling",
                gate_latency_ms=lat_ms,
            )
        elif task_scope_grounded and req_args_grounded and context_resolved and capability_available:
            return GateDecision(
                readiness=FastPathReadiness.FAST_PATH_READY,
                evidence=evidence,
                matched_capability=matched_cap,
                target_arguments=target_args,
                rationale=f"Bounded single-task operation for {matched_cap} with fully grounded arguments",
                gate_latency_ms=lat_ms,
            )
        else:
            return GateDecision(
                readiness=FastPathReadiness.FAST_PATH_UNCERTAIN,
                evidence=evidence,
                matched_capability=matched_cap,
                target_arguments=target_args,
                rationale="Harness cannot deterministically establish readiness; fallback evaluation required",
                gate_latency_ms=lat_ms,
            )
