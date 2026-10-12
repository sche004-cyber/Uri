"""C5 Intent Discovery: the canonical "what did the user ask for" stage of the paired loop.

    request -> interpretation (deterministic rules or a provider-neutral interpreter seam)
            -> session-first context (session files, confirmed session references)
            -> deterministic reference binding (RAR + S1 BindingService, uri_core.reference_binding)
            -> ARN cold-start retrieval for references the session cannot resolve
            -> budgeted clarification only for material, still-unresolved information
            -> explicit user confirmation when anything was inferred, bound or corrected
            -> Confirmed Intent Contract (digest) handed to the existing gate/approval/ticket loop

Owns no store. The pending/confirmed intent lives in the client's existing SessionState
(`active_workflow*`, the representation Turn State already projects as a pending interaction),
signed by the server so a client-side edit cannot forge a confirmation. Confirmed values are
mirrored into `current_facts` through the existing `update_fact` supersession path only after an
explicit confirmation, so a correction keeps the obsolete value in `fact_history`.

Invariants enforced here (not by any model):
* every slot value is grounded: verbatim user text, or the title of a candidate the user or
  deterministic RAR certainty bound - nothing is invented to fill a gap;
* an answered slot is never asked again; the same question is never reissued; at most
  MAX_QUESTIONS questions and MAX_NO_PROGRESS consecutive unproductive answers per intent;
* CONFIRMED is reachable only by (a) a structured user decision carrying the current digest or
  (b) a complete request whose every value is the user's own verbatim wording and whose
  references (if any) were bound with RAR certainty;
* a downstream execution proposal that differs from the confirmed intent is rejected and the
  execution proposal is recompiled from the confirmed intent (never reinterpreted).
"""
from __future__ import annotations

from copy import deepcopy
from dataclasses import asdict
import re
import threading
import uuid

from uri_core.client_contracts import canonical, digest
from uri_core.core.arn.engine import ARNEngine
from uri_core.core.arn.models import ARNState, ARNStatus, CostCeiling
from uri_core.core.client_state_ports import NeedsContext
from uri_core.reference_binding.binding import BindingService
from uri_core.reference_binding.builder import build_clarification
from uri_core.reference_binding.rar_clarification_contract import (
    BindingState, ClarificationKind, ClarificationResponse, ResponseKind, WrongBindingImpact)
from uri_core.reference_binding.rar_contracts import RARCandidate, RAREvidence, RAROutcome, RARQuery
from uri_core.reference_binding.rar_deterministic import resolve_rar_deterministic_extended
from uri_core.reference_binding.fingerprints import candidate_fingerprint
from uri_core.reference_binding.safeguards import ClarificationSafeguards

SCHEMA = "uri.intent.v1"
DOMAIN = b"uri.intent.v1\x00"
MAX_QUESTIONS = 5
MAX_NO_PROGRESS = 2
OPEN = {"CLARIFYING", "AWAITING_CONFIRMATION", "CONFIRMED", "EXECUTION_UNCERTAIN"}
FILE_RE = re.compile(r"(?<![\w.-])([A-Za-z0-9][\w-]{0,63}\.[A-Za-z0-9]{1,8})(?![\w.-])")
_REF_NOUNS = ("report", "document", "doc", "file", "sheet", "spreadsheet", "email", "letter", "presentation",
              "deck", "memo", "draft", "invoice", "contract", "proposal", "note", "notes", "plan", "minutes",
              "form", "agenda", "brief", "slides")
_DEFINITE = re.compile(r"\b(?:the|that|this)\s+((?:[\w'-]+\s+){0,3}?(?:%s))\b" % "|".join(_REF_NOUNS), re.I)
# Only entity pronouns: a leading "this/that ..." usually points at the statement itself.
_PRONOUN = re.compile(r"^(it|they)\b", re.I)
_CORRECTION = re.compile(r"^\s*(?:no[,.!:]?\s+|nope[,.!]?\s+|actually[,:]?\s+|correction[:,]?\s+|sorry[,]?\s+i\s+meant\s+|"
                         r"i\s+meant\s+|wait[,]?\s+)", re.I)
_CHANGE = re.compile(r"^(?:please\s+)?(?:change|replace|make)\s+(.+?)\s+(?:to|with|into)\s+(.+?)[.!]?$", re.I)
_NOT_BUT = re.compile(r"^(?:it'?s?\s+|it\s+is\s+)?not\s+(.+?)[,;]\s*(?:but\s+|it'?s\s+)?(.+?)[.!]?$", re.I)
_BUT_NOT = re.compile(r"^(.+?)[,;]\s+not\s+(.+?)[.!]?$", re.I)   # comma required: "Monday, not Friday"
_NON_ANSWER = re.compile(r"^\s*(?:i\s+)?(?:don'?t\s+know|not\s+sure|no\s+idea|dunno|whatever|hmm+|skip|pass|\?+)\b", re.I)
_YES = re.compile(r"^\s*(?:yes|yep|yeah|correct|that one|right)\b", re.I)
_NO = re.compile(r"^\s*(?:no|nope|neither|none)\b", re.I)


class IntentError(ValueError):
    """Typed failure; the message is the reason code."""


def _norm(text):
    return " ".join(str(text).casefold().split())


def _tokens(text):
    return re.findall(r"[\w'.-]+", _norm(text))


# ---- trusted capability intent schemas -----------------------------------------------------------

def _extract_remember(text):
    m = re.match(r"^(?:please\s+)?(?:remember|save)(?:\s+(?:that\b|this\b\s*[:,]?))?\s*(.*)$", text.strip(), re.I | re.S)
    return {"statement": m.group(1).strip().rstrip(".") or None} if m else {}


def _extract_harness(text):
    m = re.match(r"^(?:please\s+)?(?:use|ask)\s+(?:the\s+)?harness\s+to\s+(.+)$", text.strip(), re.I | re.S)
    if not m:
        return {}
    instruction = m.group(1).strip()
    f = re.search(r"\b(?:to|into|as|in)\s+(?:a\s+file\s+(?:named|called)\s+)?" + FILE_RE.pattern, instruction)
    return {"instruction": instruction, "expected_file": f.group(1) if f else None}


SCHEMAS = {
    "remember_fact": {
        "slots": ("statement",), "reference_slot": "statement", "impact": WrongBindingImpact.RECOVERABLE,
        "extract": _extract_remember,
        "questions": {"statement": ("What would you like me to remember?",
                                    "I still need the fact itself. What exactly should I remember?")},
        "labels": {"statement": ("fact", "statement", "note", "detail")},
    },
    "external_harness_task": {
        "slots": ("instruction", "expected_file"), "reference_slot": None, "impact": WrongBindingImpact.CONSEQUENTIAL,
        "extract": _extract_harness,
        "questions": {"instruction": ("What should the harness do?", "I still need the task. What should the harness do?"),
                      "expected_file": ("What file name should the result be saved as (for example summary.txt)?",
                                        "I still need a file name ending in an extension, like notes.txt. What should it be called?")},
        "labels": {"instruction": ("instruction", "task"), "expected_file": ("file name", "filename", "output file", "file")},
        "validators": {"expected_file": lambda v: bool(FILE_RE.fullmatch(v or ""))},
    },
}


def _answer_value(capability, slot, text):
    """Extract a slot value from an answer using ONLY the user's own words."""
    text = text.strip()
    if slot == "expected_file":
        m = FILE_RE.search(text)
        return m.group(1) if m else None
    return text.rstrip(".") or None


# ---- the engine --------------------------------------------------------------------------------

class IntentDiscovery:
    def __init__(self, key, *, max_questions=MAX_QUESTIONS, max_no_progress=MAX_NO_PROGRESS,
                 arn_ceiling=None, interpreter=None):
        self.key = key                      # server Ed25519 key (domain-separated signatures)
        self.max_questions, self.max_no_progress = max_questions, max_no_progress
        self.arn_ceiling = arn_ceiling or CostCeiling(max_searches=4, max_cost_units=4)
        # Optional provider-neutral interpreter: (text, capability, slots) -> {slot: value}. Its output is
        # treated exactly like user-derived extraction and must pass the same groundedness check.
        self.interpreter = interpreter
        self._binding = {}                  # (principal, session) -> BindingService (process-local)
        self._lock = threading.RLock()

    # ---- signed record codec ---------------------------------------------------------------------
    def _sign(self, record):
        body = {k: v for k, v in record.items() if k != "signature"}
        record["signature"] = self.key.sign(DOMAIN + canonical(body)).hex()
        return record

    def _verified(self, record, binding):
        try:
            body = {k: v for k, v in record.items() if k != "signature"}
            self.key.public_key().verify(bytes.fromhex(record["signature"]), DOMAIN + canonical(body))
        except Exception:
            return False
        return (record.get("schema") == SCHEMA and record.get("principal_id") == binding["principal_id"]
                and record.get("client_id") == binding["client_id"] and record.get("session_id") == binding["session_id"])

    def load(self, session, binding):
        """-> (record | None, problem | None). A tampered or foreign record is discarded, never trusted."""
        pointer = (session or {}).get("active_workflow")
        if not isinstance(pointer, dict) or pointer.get("schema") != SCHEMA:
            return None, None
        if not self._verified(pointer, binding):
            return None, "INTENT_STATE_INVALID"
        if pointer.get("status") not in OPEN:
            return None, None
        return deepcopy(pointer), None

    @staticmethod
    def intent_digest(record):
        return digest({k: record[k] for k in ("intent_id", "revision", "capability", "action")} |
                      {"slots": {n: s["value"] for n, s in record["slots"].items()},
                       "references": {n: {k: r.get(k) for k in ("candidate_id", "title", "state")}
                                      for n, r in record["references"].items()}})

    @staticmethod
    def public(record):
        """What the user is shown/confirms. No signature, no binding internals."""
        if record is None:
            return None
        return {"intent_id": record["intent_id"], "revision": record["revision"], "status": record["status"],
                "capability": record["capability"], "request": record["request"],
                "values": {n: s["value"] for n, s in record["slots"].items()},
                "sources": {n: s["source"] for n, s in record["slots"].items()},
                "references": {n: {k: r.get(k) for k in ("expression", "title", "state", "rule")}
                               for n, r in record["references"].items()},
                "corrections": [h for h in record["history"] if h["kind"] == "correction"],
                "superseded": record["superseded"], "questions_asked": record["questions_asked"],
                "digest": IntentDiscovery.intent_digest(record)}

    # ---- session projection updates ------------------------------------------------------------
    @staticmethod
    def _codec():
        from uri_core.core.state import SessionManager
        return SessionManager.__new__(SessionManager)

    def cleared(self, session):
        """Session projection with the pending-intent pointer removed (tampered/stale/abandoned state)."""
        out = dict(session or {})
        out.update(active_workflow=None, active_workflow_status=None, active_workflow_question=None,
                   active_workflow_required_field=None)
        return out

    def session_with(self, session, record, *, clear=False, recent_subject=None):
        """Return a full SessionState projection for the client to persist (consented save_session).

        Confirmed slot values stay inside the signed intent record (with their superseded history);
        only the user-confirmed referent becomes a session fact, through update_fact supersession,
        so a later "it" can be resolved session-first without asking again."""
        from uri_core.core.state import SessionState
        from uri_core.core.facts import Fact
        from uri_core.core.fact_manager import update_fact
        codec = self._codec()
        data = deepcopy(session or {})
        state = SessionState(session_id=data.get("session_id") or record["session_id"])
        for name in ("current_facts", "evidence_facts", "historical_facts"):
            setattr(state, name, codec._deserialize_fact_collection(data.get(name, {})))
        state.fact_history = codec._deserialize_fact_history(data.get("fact_history", {}))
        if recent_subject:
            update_fact(state, Fact(name="reference.recent_subject", value=recent_subject["title"],
                                    status="CONFIRMED", source="user_confirmed_intent", confirmed_by="user",
                                    evidence_ids=[recent_subject["candidate_id"]],
                                    notes=recent_subject.get("candidate_type") or "document"))
        out = dict(data)
        out["session_id"] = state.session_id
        for name in ("current_facts", "evidence_facts", "historical_facts"):
            out[name] = codec._serialize_fact_collection(getattr(state, name))
        out["fact_history"] = codec._serialize_fact_history(state.fact_history)
        if clear or record["status"] not in OPEN:
            out.update(active_workflow=None, active_workflow_status=None, active_workflow_question=None,
                       active_workflow_required_field=None)
        else:
            pending = record.get("pending") or {}
            out.update(active_workflow=self._sign(record),
                       active_workflow_status={"CLARIFYING": "waiting_for_input",
                                               "AWAITING_CONFIRMATION": "awaiting_confirmation"}.get(record["status"],
                                                                                                    record["status"].lower()),
                       active_workflow_question=pending.get("question"),
                       active_workflow_required_field=pending.get("slot"))
        return out

    # ---- context -----------------------------------------------------------------------------------
    def _service(self, binding):
        with self._lock:
            key = (binding["principal_id"], binding["session_id"])
            if key not in self._binding:
                if len(self._binding) >= 256:      # bounded: oldest session's rounds are rebuilt on demand
                    self._binding.pop(next(iter(self._binding)))
                self._binding[key] = BindingService(safeguards=ClarificationSafeguards(self.max_no_progress, 8))
            return self._binding[key]

    @staticmethod
    def _type(media_type, filename):
        name = (filename or "").lower()
        if name.endswith((".xlsx", ".xls", ".csv")) or "sheet" in (media_type or ""):
            return "spreadsheet"
        if name.endswith((".pptx", ".ppt")):
            return "presentation"
        return "document"

    def session_candidates(self, ports, binding, session):
        """Session-first context: this session's files plus the session's confirmed recent subject."""
        files = ports.read("files", "list_for_session", binding["session_id"])
        items = sorted((f for f in files if isinstance(f, dict) and f.get("file_id") and f.get("filename")),
                       key=lambda f: str(f.get("created_at") or ""), reverse=True)
        recent = ((session or {}).get("current_facts") or {}).get("reference.recent_subject")
        recent_data = recent.get("data") if isinstance(recent, dict) and recent.get("__type__") == "Fact" else None
        recent_id = (recent_data.get("evidence_ids") or [None])[0] if recent_data else None
        candidates = []
        for rank, f in enumerate(items):
            tags = ("session_file",) + (("recently_discussed",) if f["file_id"] == recent_id else ())
            candidates.append(RARCandidate(id=f["file_id"], title=f["filename"], recency_rank=rank,
                                           candidate_type=self._type(f.get("media_type"), f["filename"]), domain_tags=tags))
        if recent_data and recent_id and recent_id not in {c.id for c in candidates}:
            candidates.append(RARCandidate(id=recent_id, title=recent_data["value"], recency_rank=len(candidates),
                                           candidate_type=recent_data.get("notes") or "document",
                                           domain_tags=("recently_discussed", "session_fact")))
        return tuple(candidates)

    @staticmethod
    def _graph_candidates(nodes, start_rank):
        out = []
        # Shape of the real GraphStore.list_nodes projection (GraphNode: entity_id, canonical_name).
        for i, n in enumerate(nodes if isinstance(nodes, list) else []):
            if isinstance(n, dict) and n.get("entity_id") and n.get("canonical_name"):
                out.append(RARCandidate(id="graph:" + str(n["entity_id"]), title=str(n["canonical_name"]),
                                        candidate_type=str(n.get("entity_type") or "document"),
                                        recency_rank=start_rank + i, domain_tags=("graph",)))
        return tuple(out)

    def _stale_references(self, record, ports, binding, session):
        """Slots whose session-file referent no longer exists with the title the user confirmed."""
        bound = {slot: ref for slot, ref in record["references"].items()
                 if ref.get("candidate_id") and not str(ref["candidate_id"]).startswith(("user:", "graph:"))}
        if not bound:
            return []
        current = {c.id: c.title for c in self.session_candidates(ports, binding, session)}
        return [slot for slot, ref in bound.items() if current.get(ref["candidate_id"]) != ref.get("title")]

    # ---- grounding -------------------------------------------------------------------------------
    @staticmethod
    def user_text(record):
        return "\n".join([record["request"], *[h["text"] for h in record["history"] if h["kind"] in ("answer", "correction")]])

    def verbatim(self, record, value):
        """True iff value appears contiguously in the user's own text (case/space-insensitive).

        Stricter than grounded(): reordering or dropping words (e.g. losing a 'not') fails."""
        return bool(value) and _norm(value) in _norm(self.user_text(record))

    def grounded(self, record, value, extra_titles=()):
        """True iff every token of value comes from the user's own words or a bound candidate title."""
        allowed = set(_tokens(self.user_text(record)))
        for r in record["references"].values():
            if r.get("title"):
                allowed |= set(_tokens(r["title"]))
        for t in extra_titles:
            allowed |= set(_tokens(t))
        return all(tok in allowed for tok in _tokens(value or ""))

    # ---- compile / conflict ----------------------------------------------------------------------
    def rendered(self, record, slot):
        value = record["slots"][slot]["value"]
        ref = record["references"].get(slot)
        if not ref or not ref.get("title") or not value:
            return value
        expr = ref["expression"]
        idx = value.casefold().find(expr.casefold())
        if idx < 0:
            return value
        return value[:idx] + ref["title"] + value[idx + len(expr):]

    def compile(self, record):
        """The ONLY translation from confirmed meaning to execution arguments."""
        cap = record["capability"]
        if cap == "remember_fact":
            inputs = {"request_text": "remember that " + self.rendered(record, "statement")}
        elif cap == "external_harness_task":
            inputs = {"instruction": record["slots"]["instruction"]["value"],
                      "expected_file": record["slots"]["expected_file"]["value"]}
        else:
            raise IntentError("NO_INTENT_SCHEMA")
        return {"goal": record["request"][:200], "mode": "single_action", "capability": cap,
                "actions": [{"name": record["action"], "inputs": inputs}], "clarification": None,
                "unsupported_reason": None, "requires_approval": False, "confidence": 1.0,
                "reason": "compiled_from_confirmed_intent"}

    def conflicts(self, record, proposal):
        """Differences between a downstream proposal and the confirmed intent (empty = consistent)."""
        compiled = self.compile(record)
        reasons = []
        if not isinstance(proposal, dict):
            return ["proposal_not_object"]
        if proposal.get("capability") != compiled["capability"]:
            reasons.append("capability_changed")
        acts = proposal.get("actions") or []
        if len(acts) != 1 or not isinstance(acts[0], dict):
            reasons.append("action_shape_changed")
        else:
            if acts[0].get("name") != record["action"]:
                reasons.append("action_changed")
            want, got = compiled["actions"][0]["inputs"], acts[0].get("inputs") or {}
            for key in sorted(set(want) | set(got)):
                if want.get(key) != got.get(key):
                    reasons.append("input_changed:" + key)
        return reasons

    # ---- record lifecycle --------------------------------------------------------------------------
    def _new(self, binding, capability, action, text, values, turn_id, interpreted=()):
        schema = SCHEMAS[capability]
        record = {"schema": SCHEMA, "intent_id": uuid.uuid4().hex, "revision": 1, "status": "CLARIFYING",
                  "principal_id": binding["principal_id"], "client_id": binding["client_id"],
                  "session_id": binding["session_id"], "capability": capability, "action": action,
                  "request": text, "slots": {}, "references": {}, "superseded": [], "pending": None,
                  "questions_asked": 0, "asked": [], "no_progress": 0, "reissued_after_restart": 0,
                  "arn": None, "history": [{"kind": "request", "text": text, "turn_id": turn_id}],
                  "confirmed_digest": None, "confirmation_basis": None, "execution": None}
        for slot in schema["slots"]:
            v = values.get(slot)
            if v and self.verbatim(record, v) and schema.get("validators", {}).get(slot, lambda _v: True)(v):
                # The words are the user's, but WHICH slot they fill was a model's reading: that is an inference,
                # so it must be shown and explicitly confirmed (never the complete-explicit-request path).
                source = "interpreted_from_request" if slot in interpreted else "user_request"
                record["slots"][slot] = {"value": v, "source": source, "turn_id": turn_id}
        ref_slot = schema["reference_slot"]
        if ref_slot and ref_slot in record["slots"]:
            expr = self._reference_expression(record["slots"][ref_slot]["value"])
            if expr:
                record["references"][ref_slot] = {"expression": expr["text"], "pronoun": expr["pronoun"],
                                                  "state": "UNRESOLVED", "candidate_id": None, "title": None}
        return record

    @staticmethod
    def _reference_expression(statement):
        m = _PRONOUN.match(statement or "")
        if m:
            return {"text": m.group(1), "pronoun": True}
        m = _DEFINITE.search(statement or "")
        if m:
            return {"text": m.group(0), "pronoun": False}
        return None

    def _bump(self, record):
        record["revision"] += 1
        if record["status"] == "CONFIRMED" or record["confirmed_digest"]:
            record["history"].append({"kind": "confirmation_invalidated", "text": "",
                                      "digest": record["confirmed_digest"]})
        record["confirmed_digest"] = None
        record["confirmation_basis"] = None

    def _ask(self, record, slot, kind, question, **extra):
        """Issue a question under budget / no-repeat rules. Returns an outcome."""
        key = slot + "|" + _norm(question)
        if key in record["asked"] and not extra.get("reissue"):
            return self._stop(record, "CLARIFICATION_REPEAT_BLOCKED",
                              f"I could not resolve '{slot}' without repeating a question. Nothing was assumed; "
                              "please restate the request with that detail.")
        if not extra.get("reissue"):
            if record["questions_asked"] >= self.max_questions:
                return self._stop(record, "CLARIFICATION_BUDGET_EXHAUSTED",
                                  "I have asked as many questions as I will for one request and still lack "
                                  f"'{slot}'. Nothing was assumed or done; please restate the request.")
            record["questions_asked"] += 1
            record["asked"].append(key)
        record["status"] = "CLARIFYING"
        record["pending"] = {"slot": slot, "kind": kind, "question": question,
                             **{k: v for k, v in extra.items() if k != "reissue"}}
        record["history"].append({"kind": "question", "text": question, "slot": slot})
        return {"kind": "clarify", "code": "INTENT_CLARIFICATION", "record": record, "message": question,
                "clarification": {"slot": slot, "kind": kind, "question": question,
                                  "options": extra.get("options", []), "intent_id": record["intent_id"],
                                  "revision": record["revision"]}}

    @staticmethod
    def _stop(record, code, message):
        record["revision"] += 1          # stopped meaning is superseded: an older replayed record is stale
        record["status"] = "ABANDONED"
        record["pending"] = None
        record["history"].append({"kind": "stopped", "text": code})
        return {"kind": "stopped", "code": code, "record": record, "message": message}

    def _no_progress(self, record):
        record["no_progress"] += 1
        return record["no_progress"] > self.max_no_progress

    # ---- reference resolution ---------------------------------------------------------------------
    def _contract_question(self, contract, expr):
        options = [{"candidate_id": c.candidate_id, "label": next((f.value for f in c.display_facts if f.key == "title"), c.candidate_id),
                    "rank": c.rank} for c in contract.candidates]
        if contract.kind == ClarificationKind.CONFIRM_ONE and options:
            return f"By '{expr}', do you mean {options[0]['label']}?", options
        if contract.kind == ClarificationKind.CHOOSE_ATTRIBUTE:
            values = [o.value for o in contract.attribute_options]
            return f"Which '{expr}' do you mean? It differs by {contract.attribute_axis}: " + ", ".join(values) + ".", \
                [{"option_key": o.option_key, "label": o.value} for o in contract.attribute_options]
        listed = "; ".join(f"{o['rank']}) {o['label']}" for o in options)
        more = f" (and {contract.overflow_count} more)" if contract.overflow_count else ""
        return f"Which one do you mean by '{expr}'? {listed}{more}.", options

    def _bind(self, record, slot, ref, state, candidate, rule, source):
        ref.update(state=state, candidate_id=candidate.id, title=candidate.title, rule=rule,
                   candidate_type=candidate.candidate_type, bound_by=source)
        record["pending"] = None
        record["no_progress"] = 0

    def _resolve_reference(self, record, slot, ports, binding, session, turn_id):
        ref = record["references"][slot]
        try:
            candidates = self.session_candidates(ports, binding, session)
        except NeedsContext as missing:
            return {"kind": "needs_context", "reads": [missing.query.model_dump()], "record": record}
        expr = ref["expression"]
        evidence = RAREvidence(clause_text=record["slots"][slot]["value"], recency_hint="same" if ref["pronoun"] else None)
        query = RARQuery(reference_expression=expr, candidates=candidates, local_evidence=evidence)
        resolution = resolve_rar_deterministic_extended(query).resolution if candidates else None
        if resolution is None or (resolution.outcome == RAROutcome.UNKNOWN and not resolution.ambiguous_candidate_ids):
            # ARN: session-first retrieval found nothing usable; widen once to the graph, never repeat a search.
            arn = ARNEngine(state=ARNState(task_goal=record["intent_id"]), cost_ceiling=self.arn_ceiling)
            for source, q in (record["arn"] or {}).get("checked", []):
                arn.record_source_checked(source, q, [])
            if not arn.is_search_repeated("session_context", expr):
                arn.record_source_checked("session_context", expr, [c.id for c in candidates])
            term = max((t for t in _tokens(expr) if t not in {"the", "my", "our", "that", "this", "it", "they"}),
                       key=len, default=None)
            graph = ()
            if term and not arn.is_search_repeated("graph", term) and arn.state.status is ARNStatus.ACTIVE:
                try:
                    nodes = ports.read("graph", "list_nodes", name_contains=term, limit=10)
                except NeedsContext as missing:
                    record["arn"] = {"expression": expr, "checked": [[s.source, s.query] for s in arn.state.sources_checked]}
                    return {"kind": "needs_context", "reads": [missing.query.model_dump()], "record": record}
                arn.record_source_checked("graph", term, nodes)
                graph = self._graph_candidates(nodes, len(candidates))
            record["arn"] = {"expression": expr, "checked": [[s.source, s.query] for s in arn.state.sources_checked]}
            if graph:
                candidates = candidates + graph
                query = RARQuery(reference_expression=expr, candidates=candidates, local_evidence=evidence)
                resolution = resolve_rar_deterministic_extended(query).resolution
            if resolution is None or (resolution.outcome == RAROutcome.UNKNOWN and not candidates):
                return self._ask(record, slot, "reference_free", f"I couldn't find what '{expr}' refers to. What is it?")
        built = build_clarification(query, resolution, session_id=binding["session_id"], turn_id=turn_id,
                                    wrong_binding_impact=SCHEMAS[record["capability"]]["impact"])
        svc = self._service(binding)
        result = svc.register(built, query)
        if result.state in (BindingState.CONFIRMED, BindingState.TENTATIVE):
            self._bind(record, slot, ref, result.state.value, query.get_candidate(result.candidate_id),
                       resolution.rule_used.value if resolution.rule_used else None, "rar")
            return None
        contract = built.contract
        if contract.kind == ClarificationKind.FREE_INPUT_ONLY:
            # Candidates existed (e.g. graph nodes sharing one word with the expression) but none is plausible
            # for it: there is nothing to choose from, so ask freely instead of "Which one ...?" with no options
            # (fifth review: that empty question could only be answered into CLARIFICATION_REPEAT_BLOCKED).
            svc.close_round(contract.ambiguity_id, session_id=binding["session_id"])
            return self._ask(record, slot, "reference_free", f"I couldn't find what '{expr}' refers to. What is it?")
        question, options = self._contract_question(contract, expr)
        if record.pop("_variant", False):
            question = (f"I still need to know which one you mean by '{expr}'. Reply with its number or its name: "
                        + "; ".join(f"{o.get('rank', i + 1)}) {o['label']}" for i, o in enumerate(options)) + ".")
        return self._ask(record, slot, "reference", question, options=options, ambiguity_id=contract.ambiguity_id,
                         set_fingerprint=contract.candidate_set_fingerprint, scope=list(contract.scope_candidate_ids),
                         scope_fingerprints=dict(contract.scope_fingerprints), contract_kind=contract.kind.value)

    def _round(self, record, ports, binding, session, turn_id):
        """The live BindingService round for the pending reference question; rebuilt after a restart."""
        pending = record["pending"]
        svc = self._service(binding)
        try:
            candidates = self.session_candidates(ports, binding, session)
        except NeedsContext:
            candidates = ()
        current = {c.id: c for c in candidates}
        for cid in pending.get("scope", []):     # graph candidates are re-derived from the round itself
            if cid.startswith("graph:") and cid not in current:
                stored = svc.store.rounds.get(pending.get("ambiguity_id"))
                c = stored.query.get_candidate(cid) if stored else None
                if c:
                    current[cid] = c
        query = RARQuery(reference_expression=record["references"][pending["slot"]]["expression"],
                         candidates=tuple(current.values()))
        if pending.get("ambiguity_id") in svc.store.rounds:
            return svc, pending["ambiguity_id"], query
        # Server restart: never deserialize binding authority. Rebuild an equivalent round from FRESH evidence
        # only if every scoped candidate still exists with the same fingerprint.
        scope = [current.get(cid) for cid in pending.get("scope", [])]
        if not scope or any(c is None or candidate_fingerprint(c) != pending["scope_fingerprints"].get(c.id) for c in scope):
            return svc, None, query
        from uri_core.reference_binding.rar_contracts import RARResolution, RARBasis
        scoped = RARQuery(reference_expression=query.reference_expression, candidates=tuple(scope))
        res = (RARResolution(query.reference_expression, RAROutcome.AMBIGUOUS, ambiguous_candidate_ids=tuple(c.id for c in scope),
                             basis=RARBasis.DETERMINISTIC_ANCHOR) if len(scope) > 1 else
               RARResolution(query.reference_expression, RAROutcome.UNKNOWN, basis=RARBasis.DETERMINISTIC_ANCHOR))
        built = build_clarification(scoped, res, session_id=binding["session_id"], turn_id=turn_id,
                                    wrong_binding_impact=SCHEMAS[record["capability"]]["impact"], attribute_narrowed=len(scope) == 1)
        if built.contract is None:
            return svc, None, query
        svc.register(built, scoped)
        record["reissued_after_restart"] += 1
        pending.update(ambiguity_id=built.contract.ambiguity_id, set_fingerprint=built.contract.candidate_set_fingerprint,
                       contract_kind=built.contract.kind.value,
                       options=[{"candidate_id": c.candidate_id, "rank": c.rank,
                                 "label": next((f.value for f in c.display_facts if f.key == "title"), c.candidate_id)}
                                for c in built.contract.candidates])
        return svc, built.contract.ambiguity_id, query

    def _answer_reference(self, record, text, selection, ports, binding, session, turn_id):
        pending = record["pending"]
        slot = pending["slot"]
        ref = record["references"][slot]
        if pending["kind"] == "reference_free":
            value = text.strip().rstrip(".")
            if not value or _NON_ANSWER.match(value) or _NO.match(value):
                return "no_progress"
            ref.update(state="USER_SUPPLIED", candidate_id="user:" + digest(value)[:16], title=value,
                       rule="USER_FREE_INPUT", candidate_type="document", bound_by="user_answer")
            record["pending"] = None
            record["no_progress"] = 0
            return "bound"
        svc, ambiguity_id, query = self._round(record, ports, binding, session, turn_id)
        if ambiguity_id is None:
            record["pending"] = None
            ref.update(state="UNRESOLVED", candidate_id=None, title=None)
            return "stale"
        contract = svc.store.rounds[ambiguity_id].contract
        options = pending.get("options") or []
        chosen = None
        if selection:
            chosen = selection
        else:
            m = re.fullmatch(r"\s*(?:option\s+|number\s+|#)?(\d)\s*[.)]?\s*", text)
            if m:
                chosen = next((o["candidate_id"] for o in options if str(o.get("rank")) == m.group(1)), None)
            elif contract.kind == ClarificationKind.CONFIRM_ONE and _YES.match(text) and options:
                chosen = options[0]["candidate_id"]
            elif contract.kind == ClarificationKind.CONFIRM_ONE and _NO.match(text):
                svc.close_round(ambiguity_id, session_id=binding["session_id"])
                record["pending"] = None
                ref["excluded"] = sorted(set(ref.get("excluded", [])) | {o["candidate_id"] for o in options})
                return "rejected_option"
        impact = SCHEMAS[record["capability"]]["impact"]
        if chosen:
            response = ClarificationResponse(ambiguity_id, ResponseKind.CANDIDATE, candidate_id=chosen,
                                             candidate_set_fingerprint=contract.candidate_set_fingerprint)
        else:
            response = ClarificationResponse(ambiguity_id, ResponseKind.FREE_INPUT, text=text.strip())
        result = svc.respond(binding["session_id"], response, query, wrong_binding_impact=impact)
        if result.state in (BindingState.CONFIRMED, BindingState.TENTATIVE):
            self._bind(record, slot, ref, result.state.value, query.get_candidate(result.candidate_id),
                       "ACTIVE_UI" if chosen else "USER_FREE_INPUT", "user_selection" if chosen else "user_answer")
            return "bound"
        if result.next_contract_id:
            nxt = svc.store.rounds[result.next_contract_id].contract
            if not nxt.scope_candidate_ids and contract.scope_candidate_ids:
                # The answer matched nothing: a free-input-only round would drop the displayed choices.
                svc.close_round(nxt.ambiguity_id, session_id=binding["session_id"])
                return "no_progress"
            question, opts = self._contract_question(nxt, ref["expression"])
            record["pending"] = None
            record["_next"] = {"question": question, "options": opts, "ambiguity_id": nxt.ambiguity_id,
                               "set_fingerprint": nxt.candidate_set_fingerprint, "scope": list(nxt.scope_candidate_ids),
                               "scope_fingerprints": dict(nxt.scope_fingerprints), "contract_kind": nxt.kind.value,
                               "progress": len(nxt.scope_candidate_ids) < len(contract.scope_candidate_ids)}
            return "narrowed"
        if result.reason == "clarification budget exhausted":
            return "budget"
        return "no_progress"

    # ---- correction ------------------------------------------------------------------------------
    def _apply_correction(self, record, body, ports, binding, session, turn_id):
        """Change only what the user named, using only the user's words. Returns list of changes or None."""
        schema = SCHEMAS[record["capability"]]
        changes = []

        def replace(slot, new_value, how):
            old = record["slots"].get(slot)
            if old and old["value"] == new_value:
                return
            validator = schema.get("validators", {}).get(slot)
            if validator and not validator(new_value):
                raise IntentError("CORRECTION_INVALID_VALUE")
            if old:
                record["superseded"].append({"slot": slot, "value": old["value"], "source": old["source"],
                                             "replaced_by": new_value, "turn_id": turn_id})
            record["slots"][slot] = {"value": new_value, "source": "user_correction", "turn_id": turn_id}
            changes.append({"slot": slot, "from": old["value"] if old else None, "to": new_value, "how": how})
            if slot == schema["reference_slot"]:
                ref = record["references"].get(slot)
                expr = self._reference_expression(new_value)
                if ref and expr and _norm(expr["text"]) == _norm(ref["expression"]):
                    pass     # the referent is unchanged; keep the binding
                elif expr:
                    record["references"][slot] = {"expression": expr["text"], "pronoun": expr["pronoun"],
                                                  "state": "UNRESOLVED", "candidate_id": None, "title": None}
                else:
                    record["references"].pop(slot, None)

        old_new = None
        for pattern, order in ((_CHANGE, (1, 2)), (_NOT_BUT, (1, 2)), (_BUT_NOT, (2, 1))):
            m = pattern.match(body)
            if m:
                old_new = (m.group(order[0]).strip(), m.group(order[1]).strip())
                break
        if old_new:
            old, new = old_new
            targets = [s for s, v in record["slots"].items() if re.search(r"(?<!\w)" + re.escape(old) + r"(?!\w)", v["value"], re.I)]
            labelled = [s for s, labels in schema["labels"].items() if _norm(re.sub(r"^(the|my)\s+", "", old, flags=re.I)) in labels]
            ref_hits = [s for s, r in record["references"].items() if r.get("title") and _norm(old) in _norm(r["title"])]
            if len(targets) == 1:
                s = targets[0]
                v = record["slots"][s]["value"]
                m2 = re.search(r"(?<!\w)" + re.escape(old) + r"(?!\w)", v, re.I)
                replace(s, v[:m2.start()] + self._new_part(v[:m2.start()], new) + v[m2.end():], "explicit_old_new")
                return changes
            if len(labelled) == 1 and not targets:
                value = _answer_value(record["capability"], labelled[0], new)
                if value:
                    replace(labelled[0], value, "named_field")
                    return changes
            if len(ref_hits) == 1 and not targets:
                return self._rebind(record, ref_hits[0], new, ports, binding, session, turn_id)
            return None
        # No explicit old value: a referent correction ("the Q3 one") or a restated statement.
        for slot, ref in record["references"].items():
            if ref.get("state") in ("CONFIRMED", "TENTATIVE", "USER_SUPPLIED") and not _PRONOUN.match(body):
                rebound = self._rebind(record, slot, body, ports, binding, session, turn_id, quiet=True)
                if rebound:
                    return rebound
        for slot, value in list(record["slots"].items()):
            s, b = _tokens(value["value"]), _tokens(body)
            k = 0
            while k < min(len(s), len(b)) and s[k] == b[k]:
                k += 1
            if k >= 2 and k < len(b):
                # Keep the user's own wording for the new tail; the shared prefix is unchanged.
                words = body.strip().rstrip(".").split()
                prefix = value["value"].split()[:k]
                replace(slot, " ".join(prefix + words[k:]), "restated_tail")
                return changes
        return None

    @staticmethod
    def _new_part(before, new):
        """'it is due on Monday' replacing 'Friday' in '... is due on Friday' -> 'Monday'.

        Drop a restated lead-in only when it repeats, word for word, the text right before the old
        value (optionally after one or two subject words such as 'it'). Otherwise keep the user's
        whole new phrase: never synthesise words the user did not say."""
        words, ctx = new.split(), _tokens(before)
        best = 0
        for j in (0, 1, 2):
            for i in range(len(words) - 1, j, -1):
                seg = [_norm(w) for w in words[j:i]]
                if seg and len(seg) <= len(ctx) and ctx[-len(seg):] == seg:
                    best = max(best, i)
                    break
        return " ".join(words[best:]) if best else new

    def _rebind(self, record, slot, expression, ports, binding, session, turn_id, quiet=False):
        ref = record["references"][slot]
        try:
            candidates = self.session_candidates(ports, binding, session)
        except NeedsContext:
            candidates = ()
        query = RARQuery(reference_expression=expression, candidates=candidates)
        if not candidates:
            return None
        res = resolve_rar_deterministic_extended(query).resolution
        if res.outcome != RAROutcome.RESOLVED or res.candidate_id == ref.get("candidate_id"):
            return None
        cand = query.get_candidate(res.candidate_id)
        old = {"candidate_id": ref.get("candidate_id"), "title": ref.get("title")}
        record["superseded"].append({"slot": slot + ".reference", "value": old["title"], "source": ref.get("bound_by"),
                                     "replaced_by": cand.title, "turn_id": turn_id})
        # A user correction is user-supplied evidence, still shown for confirmation (heuristic, not certainty).
        self._bind(record, slot, ref, "TENTATIVE", cand, res.rule_used.value if res.rule_used else None, "user_correction")
        return [{"slot": slot + ".reference", "from": old["title"], "to": cand.title, "how": "rebind"}]

    # ---- evaluation ----------------------------------------------------------------------------
    def _evaluate(self, record, ports, binding, session, turn_id):
        schema = SCHEMAS[record["capability"]]
        nxt = record.pop("_next", None)
        if nxt:
            if not nxt.pop("progress") and self._no_progress(record):
                return self._stop(record, "CLARIFICATION_NO_PROGRESS",
                                  "Your answers have not narrowed this down, so I stopped rather than guess. "
                                  "Nothing was done; please restate the request.")
            question = nxt.pop("question")
            return self._ask(record, schema["reference_slot"], "reference", question, **nxt)
        for slot in schema["slots"]:
            if slot not in record["slots"]:
                asked = sum(1 for k in record["asked"] if k.startswith(slot + "|"))
                variants = schema["questions"][slot]
                return self._ask(record, slot, "value", variants[min(asked, len(variants) - 1)])
        for slot, ref in record["references"].items():
            if ref["state"] == "UNRESOLVED":
                outcome = self._resolve_reference(record, slot, ports, binding, session, turn_id)
                if outcome:
                    return outcome
        # Groundedness of the compiled arguments (defence in depth for interpreter/correction paths).
        compiled = self.compile(record)
        for value in compiled["actions"][0]["inputs"].values():
            if not self.grounded(record, value, extra_titles=("remember that",)):
                return self._stop(record, "INTENT_UNGROUNDED_VALUE",
                                  "I could not build this request from your own words, so I did not proceed.")
        explicit = (all(s["source"] == "user_request" for s in record["slots"].values())
                    and all(r["state"] == "CONFIRMED" and r.get("bound_by") == "rar"
                            # A referent found only by widening beyond the session (ARN graph) is shown first.
                            and not str(r.get("candidate_id") or "").startswith("graph:")
                            for r in record["references"].values())
                    and not record["superseded"] and record["questions_asked"] == 0)
        record["pending"] = None
        if explicit:
            record["status"] = "CONFIRMED"
            record["confirmed_digest"] = self.intent_digest(record)
            record["confirmation_basis"] = "explicit_complete_request"
            return {"kind": "confirmed", "record": record}
        record["status"] = "AWAITING_CONFIRMATION"
        summary = self.compile(record)["actions"][0]["inputs"]
        return {"kind": "confirm", "code": "INTENT_CONFIRMATION_REQUIRED", "record": record,
                "message": "Please confirm before I continue: " + "; ".join(f"{k} = {v}" for k, v in summary.items()),
                "confirmation": {"intent_id": record["intent_id"], "revision": record["revision"],
                                 "digest": self.intent_digest(record), "arguments": summary}}

    # ---- entry point -------------------------------------------------------------------------------
    def handle(self, *, text, decision, proposal, binding, session, ports, turn_id, interpreter=None):
        """-> outcome dict with kind in {passthrough, clarify, confirm, confirmed, stopped, needs_context}.

        interpreter: per-turn override of self.interpreter, bound by the caller to the user's explicit
        reasoning selection for THIS turn (never a different source)."""
        interpreter = interpreter or self.interpreter
        record, problem = self.load(session, binding)
        if problem:
            return {"kind": "stopped", "code": problem, "record": None, "clear": True,
                    "message": "The saved request could not be verified, so I did not act on it. Please restate it."}
        new_request = (isinstance(proposal, dict) and proposal.get("mode") == "single_action"
                       and proposal.get("capability") in SCHEMAS)
        if decision is not None:
            if record is None or decision.intent_id != record["intent_id"] or decision.revision != record["revision"]:
                return {"kind": "stopped", "code": "INTENT_DECISION_STALE", "record": None,
                        "message": "That confirmation refers to an older version of the request; nothing was done."}
            record["history"].append({"kind": decision.decision, "text": "", "turn_id": turn_id})
            if decision.decision == "abandon":
                # Abandoned meaning is superseded meaning: advance the revision so a client that later
                # replays the pre-abandon record (rollback, stale device) is refused as INTENT_STATE_STALE.
                self._bump(record)
                record["status"] = "ABANDONED"
                return {"kind": "stopped", "code": "INTENT_ABANDONED", "record": record,
                        "message": "Okay, I dropped that request. Nothing was done."}
            if decision.decision == "select":
                if not record.get("pending") or record["pending"]["kind"] != "reference":
                    return {"kind": "stopped", "code": "NO_PENDING_SELECTION", "record": None,
                            "message": "There is no choice waiting for an answer."}
                answer = self._answer_reference(record, "", decision.candidate_id, ports, binding, session, turn_id)
                return self._after_answer(record, answer, ports, binding, session, turn_id)
            # confirm
            if record["status"] == "EXECUTION_UNCERTAIN":
                return {"kind": "stopped", "code": "INTENT_EXECUTION_UNCERTAIN", "record": None,
                        "message": "The last attempt's outcome is uncertain. Check the result first; "
                                   "start a new request if it really needs to be done again."}
            rerun = record["status"] == "CONFIRMED" and decision.digest == record["confirmed_digest"] == self.intent_digest(record)
            if not rerun and (record["status"] != "AWAITING_CONFIRMATION" or decision.digest != self.intent_digest(record)):
                return {"kind": "stopped", "code": "INTENT_DECISION_STALE", "record": None,
                        "message": "That confirmation does not match the current request; nothing was done."}
            # A digest names the meaning, not the world: a session file bound earlier must still be the same
            # file now. If it is gone or renamed, the confirmation is stale and the reference is resolved again.
            try:
                stale = self._stale_references(record, ports, binding, session)
            except NeedsContext as missing:
                return {"kind": "needs_context", "reads": [missing.query.model_dump()], "record": record}
            if stale:
                for slot in stale:
                    record["references"][slot].update(state="UNRESOLVED", candidate_id=None, title=None)
                record["history"].append({"kind": "reference_stale", "text": ",".join(stale), "turn_id": turn_id})
                self._bump(record)
                return self._evaluate(record, ports, binding, session, turn_id)
            if rerun:
                # Already-confirmed meaning whose execution did not happen (declined approval, executor
                # unavailable, failure): the preserved intent may be executed again, with a fresh approval.
                return {"kind": "confirmed", "record": record}
            record["status"] = "CONFIRMED"
            record["confirmed_digest"] = self.intent_digest(record)
            record["confirmation_basis"] = "explicit_user_confirmation"
            return {"kind": "confirmed", "record": record, "newly_confirmed": True}
        superseded = None
        if (record is not None and record["status"] == "EXECUTION_UNCERTAIN"
                and not (new_request and SCHEMAS[proposal["capability"]]["extract"](text))):
            # An attempt that may already have run is never re-evaluated, corrected or offered for confirmation
            # again (only the server ledger stood between that offer and a second execution). Set it aside.
            return {"kind": "stopped", "code": "INTENT_EXECUTION_UNCERTAIN", "record": None, "clear": True,
                    "message": "The last attempt at that request may already have run, so I set it aside and will "
                               "not repeat it. Check the result; start a new request if it really needs doing again."}
        if record is not None:
            correction = _CORRECTION.match(text)
            body = text[correction.end():].strip() if correction else text.strip()
            if correction and (record.get("pending") or {}).get("kind") in ("reference", "reference_free"):
                # "no, the Q3 one" answering a reference question is an answer, not a correction.
                record["history"].append({"kind": "answer", "text": body, "turn_id": turn_id,
                                          "slot": record["pending"]["slot"]})
                return self._after_answer(record, self._answer_reference(record, body, None, ports, binding, session,
                                                                         turn_id), ports, binding, session, turn_id)
            if correction or (record["status"] in ("AWAITING_CONFIRMATION", "CONFIRMED") and not new_request
                              and (_CHANGE.match(body) or _NOT_BUT.match(body) or _BUT_NOT.match(body))):
                try:
                    changes = self._apply_correction(record, body, ports, binding, session, turn_id)
                except IntentError:
                    changes = None
                record["history"].append({"kind": "correction", "text": text, "turn_id": turn_id, "changes": changes or []})
                if not changes:
                    return self._ask(record, "correction_target", "value",
                                     "Which detail should change, and to what? (for example: change Friday to Monday)")
                self._bump(record)
                record["pending"] = None
                return self._evaluate(record, ports, binding, session, turn_id)
            if new_request and SCHEMAS[proposal["capability"]]["extract"](text):
                # A new explicit request replaces the open one (never merged into it); the old intent
                # is not executed and its id is kept as provenance on the new record. "Explicit" is
                # judged from the user's own words, never from a proposer's classification alone: a Brain
                # that labels an answer ("the Q4 one") as a new request must not discard the open intent.
                superseded = record["intent_id"]
                record = None
            elif record.get("pending"):
                record["history"].append({"kind": "answer", "text": text, "turn_id": turn_id,
                                          "slot": record["pending"]["slot"]})
                pending = record["pending"]
                if pending["slot"] == "correction_target":
                    record["pending"] = None
                    try:
                        changes = self._apply_correction(record, body, ports, binding, session, turn_id)
                    except IntentError:
                        changes = None
                    if not changes:
                        return self._stop(record, "CORRECTION_UNRESOLVED",
                                          "I could not tell which detail to change, so nothing was changed or done. "
                                          "Please restate the request.")
                    self._bump(record)
                    return self._evaluate(record, ports, binding, session, turn_id)
                if pending["kind"] == "value":
                    value = _answer_value(record["capability"], pending["slot"], text)
                    validator = SCHEMAS[record["capability"]].get("validators", {}).get(pending["slot"])
                    if value and (validator is None or validator(value)) and self.grounded(record, value):
                        record["slots"][pending["slot"]] = {"value": value, "source": "user_answer", "turn_id": turn_id}
                        if pending["slot"] == SCHEMAS[record["capability"]]["reference_slot"]:
                            expr = self._reference_expression(value)
                            if expr:
                                record["references"][pending["slot"]] = {"expression": expr["text"], "pronoun": expr["pronoun"],
                                                                         "state": "UNRESOLVED", "candidate_id": None, "title": None}
                        record["pending"] = None
                        record["no_progress"] = 0
                        self._bump(record)
                        return self._evaluate(record, ports, binding, session, turn_id)
                    record["pending"] = None
                    if self._no_progress(record):
                        return self._stop(record, "CLARIFICATION_NO_PROGRESS",
                                          "I still don't have a usable answer, so I stopped rather than guess. Nothing was done.")
                    return self._evaluate(record, ports, binding, session, turn_id)
                answer = self._answer_reference(record, text, None, ports, binding, session, turn_id)
                return self._after_answer(record, answer, ports, binding, session, turn_id)
            else:
                # Plain text while a confirmation is outstanding: re-present it, change nothing.
                outcome = self._evaluate(record, ports, binding, session, turn_id) if record["status"] != "CONFIRMED" else None
                if outcome is None:
                    outcome = {"kind": "confirm", "code": "INTENT_CONFIRMED_NOT_EXECUTED", "record": record,
                               "message": "This request is already confirmed but has not been carried out. "
                                          "Confirm it again to continue, or say what to change.",
                               "confirmation": {"intent_id": record["intent_id"], "revision": record["revision"],
                                                "digest": record["confirmed_digest"],
                                                "arguments": self.compile(record)["actions"][0]["inputs"]}}
                elif outcome.get("kind") == "confirm":
                    # Unrecognised text (e.g. a bare "it is not due on Friday") is never guessed into a change;
                    # say so, so the unchanged request is not mistaken for an applied correction.
                    outcome["message"] = ("I did not change anything. To change a detail, say what to change "
                                          "(for example: change Friday to Monday). " + outcome["message"])
                return outcome
        if record is None and new_request:
            schema = SCHEMAS[proposal["capability"]]
            values = schema["extract"](text)
            rejected, interpreted = [], set()
            if interpreter is not None and any(not values.get(slot) for slot in schema["slots"]):
                # Consulted only for what the user's words did not already fill deterministically.
                suggested = interpreter(text, proposal["capability"], schema["slots"]) or {}
                for slot, value in (suggested.items() if isinstance(suggested, dict) else ()):
                    if values.get(slot):
                        continue          # deterministic user-derived value wins; the model cannot override it
                    if (slot in schema["slots"] and isinstance(value, str) and value.strip()
                            and _norm(value) in _norm(text)):
                        values[slot] = value.strip()
                        interpreted.add(slot)
                    else:
                        rejected.append(str(slot))
            action = proposal["actions"][0]["name"] if proposal.get("actions") else None
            if not action:
                return {"kind": "passthrough"}
            record = self._new(binding, proposal["capability"], action, text, values, turn_id, interpreted)
            if rejected:
                record["history"].append({"kind": "ungrounded_interpretation_dropped", "text": ",".join(rejected)})
            if superseded:
                record["history"].append({"kind": "supersedes_intent", "text": superseded, "turn_id": turn_id})
            dropped = [s for s, v in values.items() if v and s not in record["slots"]]
            if dropped:
                record["history"].append({"kind": "ungrounded_interpretation_dropped", "text": ",".join(dropped)})
            return self._evaluate(record, ports, binding, session, turn_id)
        return {"kind": "passthrough"}

    def _after_answer(self, record, answer, ports, binding, session, turn_id):
        if answer == "bound":
            self._bump(record)
            return self._evaluate(record, ports, binding, session, turn_id)
        if answer == "budget":
            return self._stop(record, "CLARIFICATION_BUDGET_EXHAUSTED",
                              "I've reached the clarification limit for this request without a safe answer. Nothing was done.")
        if answer in ("stale", "rejected_option", "narrowed"):
            return self._evaluate(record, ports, binding, session, turn_id)
        if self._no_progress(record):
            return self._stop(record, "CLARIFICATION_NO_PROGRESS",
                              "Your answers have not identified it, so I stopped rather than guess. Nothing was done.")
        # Same unresolved question: never reissued verbatim; one distinct variant, then stop.
        free = (record.get("pending") or {}).get("kind") == "reference_free"
        record["pending"] = None
        slot = next(iter(record["references"]))
        record["references"][slot].update(state="UNRESOLVED", candidate_id=None, title=None)
        if free:
            return self._ask(record, slot, "reference_free",
                             f"I still need to know what '{record['references'][slot]['expression']}' refers to "
                             "(for example its name). What is it?")
        record["_variant"] = True
        return self._evaluate(record, ports, binding, session, turn_id)

    # ---- execution feedback ----------------------------------------------------------------------
    def after_execution(self, record, outcome, proposal_digest, replanned):
        record = deepcopy(record)
        record["execution"] = {"outcome": outcome, "proposal_digest": proposal_digest, "replanned": replanned}
        record["status"] = {"verified": "EXECUTED", "execution_uncertain": "EXECUTION_UNCERTAIN"}.get(outcome, "CONFIRMED")
        record["history"].append({"kind": "execution", "text": outcome})
        return record
