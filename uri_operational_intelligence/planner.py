"""Bounded multi-step plan proposals (NORMAL tier, schema-constrained), validated deterministically.

A plan is a PROPOSAL shown to the user. It never executes anything. Each executable step carries a `source_span`
that must be copied verbatim from the user's own request: when the step is later run, Core receives the user's own
words (not model-written text), so Intent Discovery, confirmation, gates and approval apply exactly as for a
single request. A span that is not verbatim makes the step unusable (it is downgraded to ask_user), never
"repaired" with model text.
"""
from __future__ import annotations

import json
import re

from . import brain_client as BC
from .reasoning_policy import NORMAL, tier_params

MAX_STEPS = 8
KINDS = ("answer", "action", "harness", "ask_user")

PLANNER_SYSTEM = (
    "You are URI's planner. Break the user's request into the smallest ordered list of steps (at most 8). "
    "Step kinds: \"answer\" = URI writes text in its reply (explain, draft, summarise, compute); \"action\" = URI "
    "must change something or use a tool (remember, send, create/edit/move/delete files, search the user's mail or "
    "drive, schedule); \"harness\" = code, repository, build, test or deployment work for an external coding agent; "
    "\"ask_user\" = information only the user can give. For action and harness steps copy source_span EXACTLY, "
    "character for character, from the user's message: the words that ask for that step. Use depends_on for steps "
    "that need an earlier step's result. capability: one id from the provided list, or null when none fits. "
    "Never invent capabilities, people, files or values. List missing information under clarifications.")


def plan_schema(capability_ids):
    cap = {"anyOf": [{"type": "string", "enum": sorted(capability_ids)}, {"type": "null"}]} if capability_ids else {"type": "null"}
    step = {"type": "object", "additionalProperties": False,
            "required": ["id", "description", "kind", "capability", "source_span", "depends_on"],
            "properties": {"id": {"type": "string", "pattern": "^s[1-8]$"},
                           "description": {"type": "string", "maxLength": 200},
                           "kind": {"type": "string", "enum": list(KINDS)},
                           "capability": cap,
                           "source_span": {"anyOf": [{"type": "string", "maxLength": 300}, {"type": "null"}]},
                           "depends_on": {"type": "array", "items": {"type": "string", "pattern": "^s[1-8]$"}, "maxItems": 7}}}
    return {"type": "object", "additionalProperties": False, "required": ["goal", "steps", "clarifications"],
            "properties": {"goal": {"type": "string", "maxLength": 200},
                           "steps": {"type": "array", "items": step, "minItems": 1, "maxItems": MAX_STEPS},
                           "clarifications": {"type": "array", "items": {"type": "string", "maxLength": 200}, "maxItems": 4}}}


def _norm(s):
    return re.sub(r"\s+", " ", s or "").strip().lower()


# A verbatim span can still drop the words that negate it ("Do not under any circumstances email Ravi" contains
# "email Ravi"). Rule (fail closed): a negation or exclusion ANYWHERE earlier in the same clause rejects the span.
_NEGATION = re.compile(r"\b(?:don'?t|dont|do not|does not|never|not|no need to|without|stop|avoid|instead of|"
                       r"rather than|shouldn'?t|mustn'?t|won'?t|can'?t|cannot|no longer|forget about)\b", re.I)
_CLAUSE_BREAK = re.compile(r"[.;!?\n]|\bbut\b|\bthen\b|\bafter that\b|\balso\b", re.I)


def _span_regex(span):
    words = [re.escape(w) for w in (span or "").split()]
    return re.compile(r"\s+".join(words), re.I) if words else None


def exact_user_span(text, span):
    """The user's own characters for a span that matches case/whitespace-insensitively, or None. Core then receives
    the user's exact substring, never the model's re-typed copy."""
    rx = _span_regex(span)
    m = rx.search(text) if rx else None
    return m.group(0) if m else None


def _negated(text, span):
    """True when any occurrence of the span has a negation earlier in its clause."""
    rx = _span_regex(span)
    for m in (rx.finditer(text) if rx else ()):
        left = _CLAUSE_BREAK.split(text[:m.start()])[-1]
        if _NEGATION.search(left):
            return True
    return False


def validate_plan(plan, user_text, capability_ids) -> dict:
    """Deterministic checks. Returns {"ok", "plan" (normalised), "problems", "downgraded"}."""
    problems, downgraded = [], []
    if not isinstance(plan, dict) or not isinstance(plan.get("steps"), list) or not plan["steps"]:
        return {"ok": False, "plan": None, "problems": ["PLAN_SHAPE"], "downgraded": []}
    steps = plan["steps"][:MAX_STEPS]
    seen, norm_text = [], _norm(user_text)
    for s in steps:
        sid = s.get("id")
        if sid in seen:
            problems.append("DUPLICATE_STEP_ID:" + str(sid))
        bad_deps = [d for d in s.get("depends_on") or [] if d not in seen]
        if bad_deps:
            problems.append("FORWARD_OR_UNKNOWN_DEPENDENCY:%s->%s" % (sid, ",".join(bad_deps)))
            s["depends_on"] = [d for d in s["depends_on"] if d in seen]
        seen.append(sid)
        if s.get("kind") not in KINDS:
            problems.append("UNKNOWN_KIND:" + str(sid))
            s["kind"] = "ask_user"
        if s.get("capability") is not None and s["capability"] not in capability_ids:
            problems.append("UNKNOWN_CAPABILITY:" + str(sid))
            s["capability"] = None
        if s["kind"] in ("action", "harness"):
            span = s.get("source_span")
            exact = exact_user_span(user_text, span) if span else None
            if not exact:
                downgraded.append(sid)
                s["kind"], s["unusable_reason"] = "ask_user", "SOURCE_SPAN_NOT_VERBATIM"
                s["source_span"] = None
            elif _negated(user_text, span):
                downgraded.append(sid)
                s["kind"], s["unusable_reason"] = "ask_user", "SOURCE_SPAN_NEGATED"
                s["source_span"] = None
            else:
                s["source_span"] = exact
                if s["kind"] == "action" and s.get("capability") is None:
                    s["unusable_reason"] = "NO_MATCHING_CAPABILITY"
        else:
            s["source_span"] = None
    fatal = [p for p in problems if p.startswith("DUPLICATE")]
    out = dict(plan, steps=steps)
    return {"ok": not fatal, "plan": out, "problems": problems, "downgraded": downgraded}


def propose_plan(client: BC.BrainClient, user_text, capability_ids, *, history_summary=None, timeout_s=90.0) -> dict:
    user = {"request": user_text, "capabilities": sorted(capability_ids)}
    if history_summary:
        user["context"] = history_summary
    body = {"model": "local", "messages": [{"role": "system", "content": PLANNER_SYSTEM},
                                           {"role": "user", "content": json.dumps(user, ensure_ascii=False)}],
            "response_format": {"type": "json_schema", "json_schema": {"name": "plan", "schema": plan_schema(capability_ids),
                                                                       "strict": True}},
            **tier_params(NORMAL, use="plan")}
    res = client.complete_json(body, timeout_s=timeout_s)
    meta = {"status": res.status, "total_s": res.total_s, "reasoning_chars": len(res.reasoning),
            "predicted_n": res.timings.get("predicted_n"), "finish_reason": res.finish_reason}
    if res.status != BC.COMPLETE:
        return {"ok": False, "plan": None, "problems": ["PLANNER_" + res.status], "downgraded": [], "meta": meta,
                "escalation_candidate": res.status == BC.INCOMPLETE_LENGTH}
    try:
        parsed = json.loads(res.text)
    except ValueError:
        return {"ok": False, "plan": None, "problems": ["PLANNER_OUTPUT_INVALID"], "downgraded": [], "meta": meta}
    v = validate_plan(parsed, user_text, set(capability_ids))
    v["meta"] = meta
    return v
