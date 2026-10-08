"""Reasoning-depth policy: FAST / NORMAL / ESCALATE (freeze record section 4, implemented here).

Rules (frozen policy; this module only implements them):
  1. Core seams (proposer, interpreter, planner) are FAST, always.
  2. A language task is FAST unless its class is analysis / planning / comparison / conflicting evidence /
     debugging (deterministic triage), in which case NORMAL.
  3. NORMAL that ends with finish_reason == "length" is reported INCOMPLETE and becomes an ESCALATE candidate;
     it is never retried locally with a larger budget.
  4. ESCALATE is a Core / user decision (harness availability, authentication, approval); this module only
     recommends it.
  5. The model cannot change its own budget: request parameters are built here from the tier, never from
     model output.
  DEEP (unbounded thinking) is never offered locally: it collapsed contracts and looped in qualification.

User control: depth "auto" (policy), "fast" or "normal" (explicit). "deep" is refused locally and turned into an
escalation offer. An explicit user depth applies to language work only; Core seams stay FAST (rule 1).
"""
from __future__ import annotations

from dataclasses import dataclass

from . import triage as T

FAST, NORMAL, ESCALATE = "FAST", "NORMAL", "ESCALATE"
USER_DEPTHS = ("auto", "fast", "normal", "deep")

# Output caps per use (tokens). NORMAL keeps the qualified floor of 4,000 output tokens (thinking 768 + answer).
MAX_TOKENS = {"trivial": 200, "answer": 900, "normal": 4000, "plan": 4000, "seam": 600}
THINKING_BUDGET = 768


@dataclass(frozen=True)
class TierDecision:
    tier: str
    selected_by: str          # "policy" | "user" | "core_seam"
    reason: str
    escalation_offer: bool = False

    def to_dict(self):
        return {"tier": self.tier, "selected_by": self.selected_by, "reason": self.reason,
                "escalation_offer": self.escalation_offer}


def decide(triage_kind: str, user_depth: str = "auto") -> TierDecision:
    if user_depth not in USER_DEPTHS:
        raise ValueError("UNKNOWN_DEPTH")
    if user_depth == "deep":
        return TierDecision(ESCALATE, "user", "deep_reasoning_not_offered_locally", escalation_offer=True)
    if triage_kind in (T.ACTION, T.HARNESS):
        return TierDecision(FAST, "core_seam", "core_decides_actions_on_fast_seams")
    if user_depth == "fast":
        return TierDecision(FAST, "user", "user_selected_fast")
    if user_depth == "normal":
        return TierDecision(NORMAL, "user", "user_selected_normal")
    if triage_kind == T.ESCALATE:
        return TierDecision(ESCALATE, "policy", "beyond_resident_scope", escalation_offer=True)
    if triage_kind in (T.ANALYSIS, T.MULTI_STEP):
        return TierDecision(NORMAL, "policy", "analysis_or_planning")
    return TierDecision(FAST, "policy", "simple_language_task")


def tier_params(tier: str, *, use: str = "answer", max_tokens: int | None = None) -> dict:
    """Server-side request parameters for a tier. The only place budgets are set."""
    if tier == FAST:
        cap = MAX_TOKENS["seam" if use == "seam" else ("trivial" if use == "trivial" else "answer")]
        return {"temperature": 0.0, "max_tokens": min(max_tokens or cap, 4000),
                "chat_template_kwargs": {"enable_thinking": False}}
    if tier == NORMAL:
        return {"temperature": 0.0, "max_tokens": max(max_tokens or 0, MAX_TOKENS["normal"]),
                "chat_template_kwargs": {"enable_thinking": True}, "thinking_budget_tokens": THINKING_BUDGET}
    raise ValueError("NO_LOCAL_PARAMS_FOR_" + tier)


def after_result(tier: str, status: str) -> dict:
    """Rule 3: what a finished local call means for escalation."""
    if tier == NORMAL and status == "INCOMPLETE_LENGTH":
        return {"complete": False, "escalation_candidate": True, "reason": "normal_budget_exhausted"}
    if status == "INCOMPLETE_LENGTH":
        return {"complete": False, "escalation_candidate": False, "reason": "answer_truncated"}
    return {"complete": status == "COMPLETE", "escalation_candidate": False, "reason": None}
