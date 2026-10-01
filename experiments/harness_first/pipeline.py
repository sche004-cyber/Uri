"""Harness-first turn pipeline (experimental, PROVISIONAL).

URI does every deterministic step first and calls a model only for the remaining bounded
semantic residue. See docs/plans/HARNESS_FIRST_EDGE_ARCHITECTURE_MAP.md.

Real URI components (imported read-only, never modified):
  uri_v1.turn.turn_frame_builder.build_turn_frame          surface frame (frozen)
  uri_core.core.approval_resumption.classify_confirmation   pending-approval yes/no
  uri_core.core.conversational_classifier patterns          greeting/thanks/farewell/self question
  uri_core.core.lifecycle_intent_interpreter.interpret      lifecycle grammar
  uri_v1.memory.contracts.negated                           M36 negation gate (frozen)
  uri_v1.turn.rar_deterministic                             RAR (frozen)
  uri_v1.reference_clarification builder/template_renderer  S1 binding + clarification (frozen)
  uri_core.core.edge.routing_policy.evaluate_intelligence_route   S6, the only router
  uri_core.core.tool_call_translator / decision_gates       translation and gates
  uri_core.tools.system_performance.SystemPerformanceTool   real read-only execution
Test doubles and fixtures (labelled in every record): session context from the corpus,
execution of every action except system_performance, EdgeRuntimeInventory profile,
declared wrong-binding impact per action (experiment profile).

This module makes no model call itself. Model calls happen in run.py through the EPQ-1
adapters, on the bounded jobs this module prepares.
"""
from __future__ import annotations

import json
import re
import sys
import time
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
EPQ = HERE.parent / "edge_pair_qual"
for p in (str(REPO), str(EPQ)):
    if p not in sys.path:
        sys.path.insert(0, p)

from catalogue import ACTIONS  # noqa: E402  (EPQ-1 typed projection of the 17 registered actions)
from uri_core.capabilities import MultiActionCapabilityRegistry  # noqa: E402
from uri_core.core import conversational_classifier as conv  # noqa: E402
from uri_core.core.approval_resumption import classify_confirmation  # noqa: E402
from uri_core.core.capability_directory import CapabilityDirectory  # noqa: E402
from uri_core.core.capability_feasibility import CapabilityFeasibility  # noqa: E402
from uri_core.core.capability_registry import CapabilityRegistry  # noqa: E402
from uri_core.core.capability_relevance import plausible_matches  # noqa: E402
from uri_core.core.decision_engine import DecisionOutcome  # noqa: E402
from uri_core.core.decision_gates import evaluate_gates  # noqa: E402
from uri_core.core.edge.routing_policy import (  # noqa: E402
    IntelligenceRouteRequest, RouteTarget, WorkRole, evaluate_intelligence_route)
from uri_core.core.edge.runtime_inventory import EdgeRuntimeInventory, RuntimeProfile  # noqa: E402
from uri_core.core.edge.settings import EdgeSettings  # noqa: E402
from uri_core.core.lifecycle_intent_interpreter import interpret as lifecycle_interpret  # noqa: E402
from uri_core.core.model_providers.base import ToolCall  # noqa: E402
from uri_core.core.tool_call_translator import translate_tool_calls  # noqa: E402
from uri_core.tools.system_performance import SystemPerformanceTool  # noqa: E402
from uri_v1.memory.contracts import negated  # noqa: E402
from uri_v1.reference_clarification.builder import build_clarification  # noqa: E402
from uri_v1.reference_clarification.template_renderer import presented_options, render_template  # noqa: E402
from uri_v1.turn.rar_clarification_contract import BindingState, WrongBindingImpact  # noqa: E402
from uri_v1.turn.rar_contracts import RARCandidate, RARDeterministicAnchor, RAREvidence, RARQuery  # noqa: E402
from uri_v1.turn.rar_deterministic import resolve_rar_deterministic_extended  # noqa: E402
from uri_v1.turn.turn_frame_builder import build_turn_frame  # noqa: E402

REG = CapabilityRegistry(registry_path=str(REPO / "uri_workspace" / "capabilities_registry.json"))
DIRECTORY = CapabilityDirectory(capability_feasibility=CapabilityFeasibility(capability_registry=REG),
                                multi_action_registry=MultiActionCapabilityRegistry(), include_procedures=False)
PRINCIPAL = {"user_id": "hf-experiment-user", "role": "owner"}
BRAIN_MODEL = "qwen3.5:9b"

# Experiment profile (labelled): declared wrong-binding impact per action. Read-only actions are
# reversible (RECOVERABLE); anything that writes or sends is CONSEQUENTIAL (User rule: consequence-
# aware binding). The live registry declares none of these today (Edge pair r2 §5.1 P-1).
def declared_impact(action: str) -> WrongBindingImpact:
    a = ACTIONS.get(action)
    if a and a["_effect"] == "read_only" and a["_approval"] == "none":
        return WrongBindingImpact.RECOVERABLE
    return WrongBindingImpact.CONSEQUENTIAL


# Which argument of an action is grounded by which binding kind (URI fills it; the model never does).
BINDING_ARGS = {
    "read_attached_file": ("attachment_name", "att"),
    "convert_document": ("attachment_name", "att"),
    "drive_upload": ("file_name", "att"),
    "fetch_url": ("url", "url"),
    "extract_student_records": ("roll_number", "roll"),
    "fetch_drive_spreadsheet": ("spreadsheet_id", "sheet"),
}
VERBATIM_TURN_ARGS = {"query", "question", "fact", "purpose"}   # real URI tools take request_text verbatim

EXT_TYPE = {"pdf": "document", "docx": "document", "doc": "document", "txt": "document", "xlsx": "spreadsheet",
            "xls": "spreadsheet", "csv": "spreadsheet", "jpg": "media", "png": "media", "pptx": "document"}
KIND_TAGS = {"att": ("file", "attachment", "document"), "url": ("link", "page", "url", "web"),
             "roll": ("student", "record", "roll"), "sheet": ("sheet", "spreadsheet", "range"),
             "contact": ("contact", "person", "mail"), "query": ("query", "search", "thing"),
             "topic": ("topic", "thing"), "action": ("action",)}
POINTER_KIND = {"last_attachment": "att", "last_url": "url", "urls": "url", "last_roll_number": "roll",
                "last_spreadsheet": "sheet", "last_contact": "contact", "last_web_query": "query",
                "last_topic": "topic", "last_action": "action"}
TYPE_NOUNS = (r"attachment|attached file|file|document|pdf|spreadsheet|sheet|workbook|report|circular|minutes|notice|"
              r"link|url|page|budget|timetable|menu|record|one")
GENERIC_ARTIFACT = re.compile(r"\b(the|this|that)\s+(?:[\w'-]+\s+){0,2}?(" + TYPE_NOUNS + r")\b"
                              r"|\b(it|them|him|her|same|other one)\b"
                              r"|\b(that|this)(?=\s*(?:[.!?,]|$|\s+again\b|\s+one\b))", re.I)
URL_RE = re.compile(r"https?://\S+", re.I)
EMAIL_RE = re.compile(r"\b[\w.+-]+@[\w-]+\.[\w.]+\b")
LITERAL_ID_RE = re.compile(r"\b(?=[A-Za-z0-9_-]*\d)(?=[A-Za-z0-9_-]*[A-Za-z])[A-Za-z0-9][A-Za-z0-9_-]{3,}\b")
FILENAME_RE = re.compile(r"(?<![\w.])[\w\-.()]+\.(pdf|docx?|xlsx?|csv|txt|pptx|jpg|png)\b", re.I)
OBJECT_PRONOUN_RE = re.compile(r"^\s*(?:please\s+)?[a-z]+\s+(it|that|this|them)\b", re.I)
DEICTIC = re.compile(r"\b(the other one|same|it|them|him|her)\b|\b(that|this)(?=\s*(?:[.!?,]|$|\s+again\b|\s+one\b))",
                     re.I)
IMPERATIVE_VERBS = {"upload", "delete", "fetch", "search", "email", "read", "open", "send", "convert", "print", "share",
                    "summarise", "summarize", "forward", "download", "show", "check", "find", "get", "pull", "look",
                    "translate", "attach", "draft", "make", "use", "review", "edit", "save", "export", "compare"}
ACTION_VERBS = IMPERATIVE_VERBS | {"write", "plan", "update", "explain", "create", "generate", "remember", "recall",
                                   "reply", "schedule", "calculate", "analyse", "analyze", "recommend", "list"}


def _now_ms(t0: float) -> float:
    return (time.perf_counter() - t0) * 1000.0


# ------------------------------------------------------------------ session -> RAR candidates
def build_candidates(session: dict) -> List[RARCandidate]:
    cands: List[RARCandidate] = []
    seen = set()
    last_att = session.get("pointers", {}).get("last_attachment")
    for name in session.get("attachments", []):
        ext = name.rsplit(".", 1)[-1].lower() if "." in name else ""
        tags = (("recently_discussed",) if name == last_att else ()) + KIND_TAGS["att"]
        cands.append(RARCandidate(id=f"att:{name}", title=name, candidate_type=EXT_TYPE.get(ext, "document"),
                                  recency_rank=0, is_attachment=True, domain_tags=tags,
                                  exact_aliases=(name.rsplit(".", 1)[0],) if "." in name else ()))
        seen.add(f"att:{name}")
    for key, val in session.get("pointers", {}).items():
        kind = POINTER_KIND.get(key)
        if not kind:
            continue
        vals = val if isinstance(val, list) else [val]
        for i, v in enumerate(reversed(vals)):  # "urls (oldest first)": newest gets rank 0
            cid = f"{kind}:{v}"
            if cid in seen:
                continue
            seen.add(cid)
            ext = v.rsplit(".", 1)[-1].lower() if kind == "att" and "." in v else ""
            cands.append(RARCandidate(id=cid, title=v, candidate_type=EXT_TYPE.get(ext, kind if kind != "att" else "document"),
                                      recency_rank=1 + i if kind == "att" else i, is_attachment=False,
                                      domain_tags=(("recently_discussed",) if i == 0 and len(vals) == 1 else ())
                                      + KIND_TAGS[kind]))
    return cands


@dataclass
class Binding:
    state: str                      # NONE | CONFIRMED | TENTATIVE | CLARIFY
    candidate_id: Optional[str] = None
    expression: Optional[str] = None
    rule: Optional[str] = None
    rar_outcome: Optional[str] = None
    clarification: Optional[dict] = None


def resolve_reference(text: str, session: dict, frame, impact: WrongBindingImpact) -> Binding:
    """RAR + S1. Returns NONE when the turn carries no reference that needs a session binding."""
    cands = build_candidates(session)
    low = text.casefold()
    titled = [c for c in cands if c.title.casefold() in low or any(a.casefold() in low for a in c.exact_aliases if len(a) > 3)]
    no_urls = URL_RE.sub(" ", text)
    generic = GENERIC_ARTIFACT.search(no_urls)
    explicit_filename = FILENAME_RE.search(no_urls)
    literal_ids = URL_RE.findall(text) + EMAIL_RE.findall(text) + LITERAL_ID_RE.findall(no_urls)
    if not titled and not generic and not explicit_filename:
        return Binding("NONE")
    if not titled and literal_ids and not explicit_filename:
        return Binding("NONE")          # the turn states its own identifier: a verbatim span, not a session reference
    first = (re.findall(r"[a-z]+", low) or [""])[0]
    if not cands and not explicit_filename and not OBJECT_PRONOUN_RE.match(text) and not (
            generic and generic.group(2) and first in IMPERATIVE_VERBS):
        return Binding("NONE")          # no session object and no object-taking command: nothing to bind
    if len(titled) == 1 and titled[0].title.casefold() in low:
        expression = titled[0].title
    elif len(titled) == 1:
        expression = next(x for x in titled[0].exact_aliases if x.casefold() in low)   # RAR Level 0 exact alias
    elif explicit_filename:
        expression = explicit_filename.group(0)
    elif generic and generic.group(2):
        expression = generic.group(0)
    else:
        d = DEICTIC.search(text)
        expression = d.group(0) if d else (generic.group(0) if generic else text)
    attachments = [c for c in cands if c.is_attachment]
    anchor = RARDeterministicAnchor(
        unique_title_match=titled[0].id if len(titled) == 1 and titled[0].title.casefold() in low else None,
        current_attachment_id=attachments[0].id if len(attachments) == 1 and not titled and generic
        and re.search(r"\b(it|this|that|the attachment|the attached file|the file|the document)\b", low) else None,
    )
    if re.search(r"\b(previous|earlier|older)\b", low):
        recency = "previous"
    elif re.search(r"\b(latest|newest|most recent)\b", low):
        recency = "latest"
    elif re.search(r"\b(it|that|again|same|him|her|them)\b", low) and any("recently_discussed" in c.domain_tags for c in cands):
        recency = "same"
    else:
        recency = None
    type_hint = "spreadsheet" if re.search(r"\b(spreadsheet|workbook|xlsx|excel)\b", low) else None
    query = RARQuery(reference_expression=expression, candidates=tuple(cands),
                     local_evidence=RAREvidence(clause_text=text, negation_spans=tuple(frame.negation_spans),
                                                recency_hint=recency, target_type_hint=type_hint),
                     deterministic_anchor=anchor if anchor.has_any_anchor else None)
    trace = resolve_rar_deterministic_extended(query)
    res = trace.resolution
    built = build_clarification(query, res, session_id="hf-session", turn_id=str(uuid.uuid4()),
                                wrong_binding_impact=impact, reference_required=True)
    b = Binding(state=built.state.value if built.state in (BindingState.CONFIRMED, BindingState.TENTATIVE) else "CLARIFY",
                candidate_id=built.candidate_id, expression=expression, rule=(res.rule_used.value if res.rule_used else None),
                rar_outcome=res.outcome.value)
    if built.contract is not None:
        out = render_template(built.contract)
        b.clarification = {"question": out.question, "options": [list(o) for o in presented_options(built.contract, out)],
                           "kind": built.contract.kind.value,
                           "option_candidate_ids": list(getattr(built.contract, "candidate_ids", ()) or
                                                        [c.candidate_id for c in getattr(built.contract, "candidates", ())])}
    return b


# ------------------------------------------------------------------ deterministic stages
def conversational_intent(text: str) -> Optional[str]:
    """Pattern part of uri_core's conversational classifier only (whole message for chat, substring
    for the self-question patterns). The live classifier additionally waits for a Main Brain
    semantic result; this experiment replaces that with structural checks (no artifact, no
    reference, no action verb), recorded as the experimental change."""
    whole = conv._TRAILING_PUNCTUATION.sub("", (text or "").strip()).strip()
    for i, pat in enumerate(conv._WHOLE_MESSAGE_PATTERNS):
        if pat.match(whole):
            if re.search(r"good\s+night", whole, re.I):
                return "farewell"            # the live pattern groups "good night" with greetings
            return ("greeting", "thanks", "farewell")[i]
    core = re.sub(r"^(uri[,]?\s+)|(\s*,?\s*uri)$", "", whole, flags=re.I).strip()
    if any(p.fullmatch(core) for p in conv._SUBSTRING_PATTERNS):   # experimental: whole message only
        return "self"
    return None


def capability_summary() -> List[str]:
    return [e.get("capability_id") for e in DIRECTORY.summaries()]


def deterministic_reply(intent: str) -> str:
    """Deterministic wording (G1; composable-Brain rule). 'self' lists the real directory."""
    if intent == "greeting":
        return "Hello, I'm URI. What would you like to do?"
    if intent == "thanks":
        return "You're welcome."
    if intent == "farewell":
        return "Goodbye."
    caps = ", ".join(c.replace("_", " ") for c in capability_summary())
    return f"I can currently help with: {caps}."


# ------------------------------------------------------------------ S6 (single routing authority)
def s6_route(edge_model: Optional[str], *, deterministic: bool, edge_sufficient: bool, edge_qualified: bool,
             mode: str = "HYBRID", capable_available: bool = True):
    enabled = edge_model is not None
    settings = EdgeSettings(enabled=enabled, intelligence_mode=mode,
                            edge={"runtime_id": "hf-edge", "model_id": edge_model} if enabled else {"runtime_id": None, "model_id": None})
    inv = EdgeRuntimeInventory(runtimes={"hf-edge": RuntimeProfile("hf-edge", frozenset({edge_model} if edge_model else set()))})
    return evaluate_intelligence_route(settings, inv, IntelligenceRouteRequest(
        role=WorkRole.SUBSTANTIVE, auto_capable_model_id=BRAIN_MODEL, capable_available=capable_available,
        deterministic_sufficient=deterministic, edge_role_qualified=edge_qualified, edge_warm=True,
        resource_admitted=True, edge_sufficient=edge_sufficient))


# ------------------------------------------------------------------ validation + execution
def fill_arguments(action: str, binding: Binding, text: str, session: dict, model_args: dict) -> tuple[Optional[dict], str]:
    """URI fills every argument. A model value is used only when it is a whole verbatim span of the
    trusted text (request plus session pointer values). Returns (args, reason)."""
    spec = ACTIONS[action]["parameters"]["properties"]
    trusted = text + " " + " ".join(str(v) for v in session.get("pointers", {}).values()) + " " + " ".join(session.get("attachments", []))
    args: Dict[str, Any] = {}
    bind = BINDING_ARGS.get(action)
    for p, schema in spec.items():
        if bind and p == bind[0] and binding.candidate_id and binding.candidate_id.startswith(bind[1] + ":"):
            args[p] = binding.candidate_id.split(":", 1)[1]
        elif p in VERBATIM_TURN_ARGS:
            args[p] = text
        elif "enum" in schema:
            hits = [v for v in schema["enum"] if re.search(rf"\b{re.escape(v)}\b", text, re.I)]
            if len(hits) == 1:
                args[p] = hits[0]
            else:
                return None, f"UNFILLABLE_ENUM:{p}"
        else:
            v = (model_args or {}).get(p)
            if isinstance(v, str) and v and re.search(rf"(?<![\w]){re.escape(v)}(?![\w])", trusted):
                args[p] = v
            else:
                return None, f"UNFILLABLE:{p}"
    return args, "FILLED"


def gates(action: str, offered: List[str], text: str) -> dict:
    tr = translate_tool_calls([ToolCall(id=str(uuid.uuid4()), name=action, arguments={"request_text": text})],
                              offered_tool_names=offered, principal=PRINCIPAL)
    if not tr["ok"]:
        return {"translate_ok": False, "outcome": "TRANSLATE_FAILED"}
    g = evaluate_gates(DecisionOutcome(status="ok", contract=tr["contract"]), capability_directory=DIRECTORY,
                       principal=PRINCIPAL, turn_state_data={"turn": {"user_text": text}})
    d = g.to_dict()
    return {"translate_ok": True, "outcome": d.get("outcome"), "reasons": d.get("reasons")}


ENV_UNAVAILABLE = {"DISCONNECTED", "UNAVAILABLE", "INVALID_PROPOSAL"}  # no OAuth/registry in this offline env


def execute(action: str, args: dict, offered: List[str], text: str) -> dict:
    """Containment then execution. Only read-only, approval-free actions execute (one real, others
    test doubles); everything else is HELD as a proposal for the approval / Brain-composition path."""
    meta = ACTIONS[action]
    g = gates(action, offered, text)
    if meta["_effect"] != "read_only" or meta["_approval"] != "none":
        return {"status": "HELD", "action": action, "args": args, "gate": g, "verified": None}
    if not g["translate_ok"] or (g["outcome"] not in ("READY",) and g["outcome"] not in ENV_UNAVAILABLE):
        return {"status": "REJECTED_BY_GATE", "action": action, "gate": g, "verified": False}
    if action == "system_performance" and g["outcome"] == "READY":
        t = time.perf_counter()
        out = SystemPerformanceTool().report()
        ok = isinstance(out, dict) and any(k in json.dumps(out).lower() for k in ("cpu", "memory"))
        return {"status": "EXECUTED", "action": action, "args": args, "gate": g, "mode": "REAL_EXECUTION",
                "exec_ms": _now_ms(t), "verified": ok}
    mode = "TEST_DOUBLE" if g["outcome"] == "READY" else "TEST_DOUBLE_ENV_UNAVAILABLE"
    return {"status": "EXECUTED", "action": action, "args": args, "gate": g, "mode": mode, "verified": None}


# ------------------------------------------------------------------ the harness
@dataclass
class HarnessResult:
    decided: bool                     # True = harness finished the turn with no model call
    outcome: Dict[str, Any] = field(default_factory=dict)
    residue: Optional[Dict[str, Any]] = None   # bounded job for Edge / Main when not decided
    stages: List[Dict[str, Any]] = field(default_factory=list)
    harness_ms: float = 0.0


MULTI_VERB_SPLIT = re.compile(r"\b(and then|then|and also|after that|, and)\b", re.I)


def run_harness(case: dict) -> HarnessResult:
    t0 = time.perf_counter()
    text, session = case["text"], case["session"]
    offered = list(case.get("offered") or [])
    r = HarnessResult(decided=False)
    frame = build_turn_frame(text)
    r.stages.append({"stage": "frame", "actions": [a.verb for a in frame.candidate_actions],
                     "refs": [x.expression for x in frame.candidate_references], "neg": list(frame.negation_spans)})

    # Extraction / label jobs: schema supplied by the corpus (X-P1 absent). Bounded residue by construction.
    if case["kind"] in ("extract", "label"):
        r.residue = {"job": case["kind"].upper(), "admitted": True, "reason": "closed_schema_supplied"}
        r.harness_ms = _now_ms(t0)
        return r

    # 1. Pending approval resumption (runs first, as in the live /ask chain after the bypass).
    pending = session.get("pending_approval")
    conf = classify_confirmation(text)
    if conf is not None and not pending and conversational_intent(text):
        conf = None                      # "ok" with nothing pending is acknowledgement, not approval
    if conf is not None:
        if pending:
            r.decided = True
            r.outcome = {"status": "APPROVAL_DECIDED", "approve": bool(conf), "action": pending["action"],
                         "executed": False, "note": "approval decision recorded; dispatch re-runs live checks (test double)"}
        else:
            # Nothing pending: a bare yes/no has no referent. Ask (deterministic), never invent an approval.
            r.decided = True
            r.outcome = {"status": "CLARIFY", "by": "harness", "question": "There is nothing waiting for your approval. What would you like me to do?"}
        r.stages.append({"stage": "approval_resumption", "result": r.outcome["status"]})
        r.harness_ms = _now_ms(t0)
        return r
    if pending:
        r.stages.append({"stage": "approval_resumption", "result": "not_a_bare_confirmation"})

    # 2. Conversational fast path (structural guard: no artifact, no reference, no action verb, no pending).
    intent = conversational_intent(text)
    structural_clean = not frame.candidate_actions and not frame.artifact_mentions and not pending \
        and not (set(re.findall(r"[a-z]+", text.casefold())) & ACTION_VERBS) \
        and not re.search(r"\b[\w\-]+\.(pdf|docx?|xlsx?|csv)\b", text, re.I)
    r.stages.append({"stage": "conversational", "intent": intent, "structural_clean": structural_clean})
    if intent and structural_clean:
        r.decided = True
        r.outcome = {"status": "REPLIED", "intent": intent, "reply": deterministic_reply(intent), "wording": "deterministic_template"}
        r.harness_ms = _now_ms(t0)
        return r

    # 3. Lifecycle grammar.
    lc = lifecycle_interpret(text)
    if lc:
        r.decided = True
        r.outcome = {"status": "LIFECYCLE_PROPOSED", "operation": lc["operation"], "target": lc["target_id"], "executed": False}
        r.stages.append({"stage": "lifecycle", "result": lc})
        r.harness_ms = _now_ms(t0)
        return r

    # 4. Admission facts that keep the turn away from the Edge job.
    is_negated = negated(text)
    has_doc = bool(case.get("document"))
    tokens = re.findall(r"[a-z]+", text.casefold())
    distinct_verbs = {a.verb for a in frame.candidate_actions} | {t for t in tokens if t in ACTION_VERBS}
    multi_action = len(distinct_verbs) >= 2 or bool(MULTI_VERB_SPLIT.search(text) and len(frame.clauses) >= 2)

    # 5. Reference resolution + binding / clarification (RAR + S1). Impact is the most consequential
    #    offered action that could consume this reference (fail-closed before an action is chosen).
    binding = resolve_reference(text, session, frame, WrongBindingImpact.RECOVERABLE)
    r.stages.append({"stage": "rar_s1", "state": binding.state, "candidate": binding.candidate_id, "rule": binding.rule,
                     "rar_outcome": binding.rar_outcome, "expression": binding.expression})
    if binding.state == "CLARIFY":          # S1 authority holds for negated turns too (H4 repair R1)
        r.decided = True
        r.outcome = {"status": "CLARIFY", "by": "S1", "clarification": binding.clarification}
        r.harness_ms = _now_ms(t0)
        return r

    # 6. Capability discovery: the feasible offered set; relevance kept as a diagnostic only (map §4.1).
    feasible = [a for a in offered if a in ACTIONS]
    r.stages.append({"stage": "discovery", "feasible": feasible,
                     "relevance_diag": [m["capability"] for m in plausible_matches(DIRECTORY, text)][:3]})

    reasons = []
    if is_negated:
        reasons.append("negated_turn")
    if has_doc:
        reasons.append("untrusted_content")
    if multi_action:
        reasons.append("multi_action_surface")
    admitted = not reasons
    r.residue = {"job": "SELECT_ACTION", "admitted": admitted, "reasons": reasons, "binding": binding.__dict__,
                 "feasible": feasible}
    r.stages.append({"stage": "admission", "admitted": admitted, "reasons": reasons})
    r.harness_ms = _now_ms(t0)
    return r


def trusted_state(case: dict, binding: Optional[dict]) -> Optional[str]:
    """What the model may see from the session: bound values and pointer facts, nothing else."""
    parts = []
    s = case["session"]
    if binding and binding.get("candidate_id"):
        parts.append(f'"{binding.get("expression")}" refers to {binding["candidate_id"].split(":", 1)[1]}')
    if s.get("attachments"):
        parts.append("attachments = [" + ", ".join(s["attachments"]) + "]")
    for k, v in s.get("pointers", {}).items():
        parts.append(f"{k} = {v}")
    if s.get("pending_approval"):
        parts.append("pending approval: " + s["pending_approval"]["summary"])
    return "; ".join(parts) or None


def validate_selection(calls: List[dict], feasible: List[str]) -> tuple[Optional[str], str, Optional[str]]:
    """Closed set, exactly one choice. Returns (action, state, control)."""
    controls = {"ask_clarification": "CLARIFY", "escalate_to_main_brain": "ESCALATE", "decline_unsupported": "DECLINE"}
    names = [c.get("name") for c in calls]
    acts = [n for n in names if n in ACTIONS]
    ctrls = [n for n in names if n in controls]
    if len(acts) + len(ctrls) == 0:
        return None, "REJECT_EMPTY", None
    if len(acts) + len(ctrls) > 1 or len(names) != len(acts) + len(ctrls):
        return None, "REJECT_MULTIPLE_OR_UNKNOWN", None
    if ctrls:
        return None, "ABSTAIN", controls[ctrls[0]]
    if acts[0] not in feasible:
        return None, "REJECT_UNOFFERED", None
    return acts[0], "ACCEPTED", None


def validate_extract(values: dict, case: dict) -> tuple[bool, List[str]]:
    """N5: every present value is a verbatim span of the document; enums closed; ABSENT allowed."""
    bad = []
    doc = case.get("document") or ""
    for f in case["fields"]:
        v = values.get(f)
        if v in (None, "", "ABSENT"):
            continue
        if not isinstance(v, str):
            bad.append(f)
        elif f in case.get("enums", {}):
            if v not in case["enums"][f]:
                bad.append(f)
        elif v not in doc:
            bad.append(f)
    return not bad, bad


def validate_label(values: dict, case: dict) -> bool:
    return isinstance(values.get("value"), str) and values["value"] in case["enum"]
