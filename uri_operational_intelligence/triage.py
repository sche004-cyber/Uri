"""Deterministic request triage: no model call, sub-millisecond.

Purpose: keep simple turns fast (edge-first rule: a lightweight request must not pay a Brain decision call) and send
anything that might change state to URI Core, which alone decides actions. Triage is deliberately biased: when a
request MIGHT ask URI to do something, it goes to Core (a slower but safe path). The answer channel adds a second,
model-side guard (`answer.ACTION_MARKER`) for action requests triage misses.

Classes:
  TRIVIAL      greeting / thanks / acknowledgement
  QUESTION     ordinary question or conversation (answer channel, FAST)
  ANALYSIS     comparison, planning-as-advice, diagnosis, multi-constraint reasoning (answer channel, NORMAL)
  ACTION       URI is asked to change something or use a capability (Core)
  HARNESS      code / repository / build / test / deploy work (Core harness path; escalation candidate)
  MULTI_STEP   several dependent actions in one request (plan proposal, then Core per step)
  ESCALATE     beyond the resident tier by policy: deep multi-source research, large document sets
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field

TRIVIAL, QUESTION, ANALYSIS, ACTION, HARNESS, MULTI_STEP, ESCALATE = (
    "TRIVIAL", "QUESTION", "ANALYSIS", "ACTION", "HARNESS", "MULTI_STEP", "ESCALATE")

_TRIVIAL = re.compile(
    r"^\s*(hi|hello|hey|hiya|yo|good (morning|afternoon|evening|night)|thanks|thank you|thx|ok(ay)?|cool|great|"
    r"nice|got it|sure|yes|no|bye|goodbye|see you|how are you( doing)?( today)?|what'?s up|namaste)"
    r"[\s!.,?]*(uri|there|again|so much|a lot)?[\s!.,?]*$", re.I)

# Verbs that ask URI to change state or use a capability. Imperative position or "can you/please/could you X".
_ACTION_VERBS = (
    r"remember|memori[sz]e|save|store|note down|delete|remove|erase|wipe|trash|send|email|e-mail|mail|reply|forward|"
    r"schedule|book|cancel|reschedule|create|make|write|generate|draft|export|convert|rename|move|copy|upload|download|"
    r"attach|open|close|install|uninstall|update|upgrade|edit|modify|change|set|turn on|turn off|enable|disable|"
    r"run|execute|launch|start|stop|kill|restart|print|share|publish|post|forget|add|append|insert|replace|fix|"
    r"organi[sz]e|archive|sort|backup|back up|restore|search my|find my|look up my|read my|check my|summari[sz]e my")
_POLITE = r"(?:please\s+|pls\s+|kindly\s+|can you\s+|could you\s+|would you\s+|will you\s+|go ahead and\s+|uri,?\s+|now\s+|also\s+|and\s+)*"
_ACTION_START = re.compile(r"^\s*" + _POLITE + r"(?:" + _ACTION_VERBS + r")\b", re.I)
_ACTION_ANYWHERE = re.compile(r"\b(?:i want you to|i need you to|you should|go and|for me)\b", re.I)
_REMEMBER = re.compile(r"\b(remember|forget) (that|this|my)\b", re.I)
# Drafting text in the reply (no file, no send) is language work, not an action.
_DRAFT_ONLY = re.compile(r"^\s*" + _POLITE + r"(?:draft|write|compose)\b(?!.*\b(file|save|send|email it|mail it|to (my )?(desktop|folder|drive)|\.docx|\.pdf)\b)", re.I)

_HARNESS = re.compile(
    r"\b(refactor|repo(sitory)?|codebase|pull request|\bpr\b|commit|git |unit tests?|test suite|run (the )?tests|"
    r"compile|build (the|my) (app|project)|deploy|flutter|python script|source files?|multi-file|across \d+ files|"
    r"stack ?trace|debug (the|my) (code|app)|implement (a|the) (feature|function|class))\b", re.I)

_MULTI_SEQ = re.compile(r"\b(and then|then|after that|afterwards|once (that'?s|it'?s|you'?ve) done|finally|next,?)\b", re.I)
_NUMBERED = re.compile(r"(?m)^\s*(\d+[.)]|[-*])\s+\S")

_ANALYSIS = re.compile(
    r"\b(compare|comparison|versus|vs\.?|trade-?offs?|pros and cons|analy[sz]e|analysis|evaluate|assess|diagnos\w*|"
    r"why (does|did|is|are|would|do)|root cause|plan (out|for|my|a|the)|how should i|what should i|which (option|is better|one should)|"
    r"step[- ]by[- ]step|prove|derive|optimi[sz]e|prioriti[sz]e|schedule .* constraints?|constraints?|conflicting|"
    r"reconcile|calculate .* (and|then)|estimate|recommend(ation)?|strategy|decide between|best way to)\b", re.I)

_ESCALATE = re.compile(
    r"\b(deep research|literature review|research (thoroughly|in depth|across)|all (the )?(papers|sources)|"
    r"hundreds of|entire (folder|archive|mailbox|drive)|every (document|file|email) in|"
    r"(100|[2-9]\d\d|\d{4,})[- ]page)\b", re.I)


@dataclass
class Triage:
    kind: str
    reasons: list = field(default_factory=list)
    action_clauses: int = 0

    def to_dict(self):
        return {"kind": self.kind, "reasons": list(self.reasons), "action_clauses": self.action_clauses}


def _clauses(text):
    parts = re.split(r"(?:,|;|\.|\band then\b|\bthen\b|\bafter that\b|\band\b|\n)+", text, flags=re.I)
    return [p.strip() for p in parts if p and p.strip()]


def triage(text: str) -> Triage:
    t = (text or "").strip()
    if not t:
        return Triage(TRIVIAL, ["empty"])
    if _TRIVIAL.match(t):
        return Triage(TRIVIAL, ["greeting_or_ack"])
    reasons = []
    action_clauses = sum(1 for c in _clauses(t) if _ACTION_START.match(c))
    if _NUMBERED.search(t):
        action_clauses = max(action_clauses, sum(1 for line in t.splitlines()
                                                 if _NUMBERED.match(line) and _ACTION_START.match(re.sub(r"^\s*(\d+[.)]|[-*])\s+", "", line))))
    if _ESCALATE.search(t):
        return Triage(ESCALATE, ["beyond_resident_scope"], action_clauses)
    if _HARNESS.search(t) and (action_clauses or _ACTION_ANYWHERE.search(t)):
        return Triage(HARNESS, ["code_or_build_work"], action_clauses)
    if action_clauses >= 2 and (_MULTI_SEQ.search(t) or _NUMBERED.search(t) or action_clauses >= 3):
        return Triage(MULTI_STEP, ["multiple_dependent_actions"], action_clauses)
    if _REMEMBER.search(t):
        return Triage(ACTION, ["remember_or_forget"], max(action_clauses, 1))
    if action_clauses and not (_DRAFT_ONLY.match(t) and action_clauses == 1):
        return Triage(ACTION, ["imperative_action_verb"], action_clauses)
    if _ACTION_ANYWHERE.search(t) and re.search(_ACTION_VERBS, t, re.I):
        return Triage(ACTION, ["delegated_action_phrase"], max(action_clauses, 1))
    if _ANALYSIS.search(t):
        reasons.append("analysis_cue")
    elif len(t.split()) > 60 and t.count("?") >= 2:
        reasons.append("long_multi_question")
    if reasons:
        return Triage(ANALYSIS, reasons, action_clauses)
    return Triage(QUESTION, ["default_conversation"], action_clauses)
