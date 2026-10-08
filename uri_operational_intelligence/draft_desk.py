"""Draft desk: Brain-assisted drafting, correction, rewriting and revision with versioned, verifiable drafts.

Language work only. The desk has NO authority: it never sends, saves, overwrites or executes anything and never
changes the Brain selection. It uses the selected Brain (Runtime v1 by default) through the same client, readiness
check, cancellation tokens and deadlines as the orchestrator's answer channel.

One Brain call per request (FAST tier, thinking off, temperature 0, JSON schema output over the streaming seam):
  * create (DRAFT_NEW / EXPAND): the model resolves self-corrections FIRST (facts with superseded values), then writes
    blocks; missing material information becomes [placeholders].
  * edit (REVISE / CORRECT / REWRITE): the model returns edit operations on block ids. The desk applies them
    deterministically, so untouched blocks keep their exact bytes. When the user named a specific part, edits
    outside it are dropped and reported.
Every result is checked deterministically (`text_verify`) against the USER's words; findings are shown as flags.
"""
from __future__ import annotations

import json
import re
import threading
import time

from . import brain_client as BC
from . import draft_store as DS
from . import text_input as TI
from . import text_intent as TX
from . import text_verify as V
from .reasoning_policy import FAST, tier_params

MAX_DRAFT_TOKENS = 1800
MAX_EDIT_TOKENS = 1500
MAX_SESSIONS = 64
TIMEOUT = BC.Deadlines(first_token_s=60.0, idle_s=30.0, total_s=180.0)

_FACT = {"type": "object", "properties": {"key": {"type": "string"}, "value": {"type": "string"},
                                          "superseded": {"type": "array", "items": {"type": "string"}}},
         "required": ["key", "value", "superseded"], "additionalProperties": False}
_NULLABLE_STR = {"anyOf": [{"type": "string"}, {"type": "null"}]}

CREATE_SCHEMA = {
    "type": "object",
    "properties": {
        "clarification": _NULLABLE_STR,
        "facts": {"type": "array", "items": _FACT},
        "exclusions": {"type": "array", "items": {"type": "string"}},
        "doc_type": {"type": "string"},
        "tone": {"type": "string"},
        "blocks": {"type": "array", "items": {"type": "object", "properties": {
            "role": {"type": "string", "enum": list(DS.ROLES)}, "text": {"type": "string"}},
            "required": ["role", "text"], "additionalProperties": False}},
        "missing": {"type": "array", "items": {"type": "string"}},
        "summary": {"type": "string"},
    },
    "required": ["clarification", "facts", "exclusions", "doc_type", "tone", "blocks", "missing", "summary"],
    "additionalProperties": False,
}

EDIT_SCHEMA = {
    "type": "object",
    "properties": {
        "action": {"type": "string", "enum": ["edit", "clarify", "not_an_edit"]},
        "clarification": _NULLABLE_STR,
        "fact_updates": {"type": "array", "items": _FACT},
        "exclusions_add": {"type": "array", "items": {"type": "string"}},
        "edits": {"type": "array", "items": {"type": "object", "properties": {
            "op": {"type": "string", "enum": ["replace", "delete", "insert_after", "insert_before"]},
            "block_id": {"type": "string"},
            "role": {"type": "string", "enum": list(DS.ROLES)},
            "text": {"type": "string"}},
            "required": ["op", "block_id", "role", "text"], "additionalProperties": False}},
        "summary": {"type": "string"},
    },
    "required": ["action", "clarification", "fact_updates", "exclusions_add", "edits", "summary"],
    "additionalProperties": False,
}

_COMMON_RULES = (
    "Never invent names, dates, days, numbers, places, reference numbers, authorities, signatures, quotations or "
    "events. Use only details the user gave. Where a document normally needs information the user did not give "
    "(sender name, designation, recipient name, date, institution name, contact details), write a placeholder in "
    "square brackets such as [Your Name] or [Date] and list it in missing. Do not add accusations, reasons, "
    "consequences, promises or requests the user did not state; ordinary courteous phrasing is fine. Keep the "
    "user's language register: Indian English office conventions are welcome where they fit (\"Respected Sir/Madam\", "
    "\"Thanking you\", \"Yours faithfully\"). Hindi or Hinglish instructions are understood, but write the document in "
    "English unless the user asks for another language.")

CREATE_SYSTEM = (
    "You are URI's writing desk. You turn the user's request into a finished, professional document. You only "
    "write text: you never send, save or file anything, and you never say that you did.\n"
    "The request may be dictated speech. Speakers correct themselves mid-sentence (\"five, sorry, seven\", "
    "\"yesterday, no wait, on the 6th\", \"not Monday but Tuesday\", \"I mean\", \"actually\"). Use only the value "
    "the user finally settled on. Fill `facts` FIRST: every concrete detail from the user's words (people, counts, "
    "dates, days, times, places, institutions, amounts, the incident) as key + value, with the replaced values in "
    "`superseded` when the user corrected themselves. Values must be the user's own words.\n"
    + _COMMON_RULES + "\n"
    "Write the document as blocks in reading order. Roles: recipient (address block, one block), subject, salutation, "
    "body (one block per paragraph), closing (e.g. Yours faithfully), signature (name/designation lines, one block), "
    "line (anything else, e.g. a date line or heading). E-mails have a subject, salutation, body, closing and "
    "signature but no address block. Notices and circulars have a heading line, body and signature. Keep it as "
    "short as the content allows; do not pad.\n"
    "`exclusions`: literal words the user asked you not to use or mention. `summary`: one short sentence saying what "
    "you wrote. If the request is contradictory or so ambiguous that any draft would be a guess about a material "
    "fact, put ONE short question in `clarification` and return no blocks; otherwise clarification is null.")

EDIT_SYSTEM = (
    "You are URI's writing desk, revising an existing document. You only write text: you never send, save or file "
    "anything. You receive the document as blocks with ids and roles, the accepted facts, and the user's "
    "instruction (possibly dictated speech with self-corrections; the newest value wins).\n"
    "Return edit operations. Change ONLY what the instruction asks. Blocks you do not edit stay exactly as they are, "
    "so never list a block you are not changing. For replace, give the complete new text of that block. "
    "\"Paragraph N\" means the N-th block whose role is body. \"Previous sentence\" or \"that\" means the text "
    "changed most recently (listed in last_changed). A tone instruction (\"more diplomatic\", \"more formal\") may "
    "touch every block that needs it, but every fact, name, date and number and the wording the user dictated "
    "earlier must keep its meaning. \"Keep everything else the same\" means the smallest possible edit.\n"
    "When the user corrects a fact, put it in fact_updates with the old value in superseded and edit every block "
    "that states the old value. When the user asks not to mention something, remove it and add the literal words to "
    "exclusions_add.\n"
    + _COMMON_RULES + "\n"
    "If the instruction is ambiguous about something material (which of two dates, which person, what the new value "
    "is), set action to clarify with ONE short question and no edits. If the message is not about editing this "
    "document at all (a question or a new topic), set action to not_an_edit. Otherwise action is edit and "
    "clarification is null. `summary`: one short sentence describing the change.")

CORRECT_RULE = (
    "MODE: grammar-only correction. Fix grammar, spelling, punctuation and capitalisation only. Keep the meaning, "
    "the words where they are already correct, every name, number and date, the paragraphs and the register. Do not "
    "add or remove information, do not restyle, do not make it more formal.")
REWRITE_RULE = (
    "MODE: rewrite. Restyle the text as the instruction asks (tone, length, clarity, formality), keeping every fact, "
    "name, number and date and the intended meaning.")


class DeskError(RuntimeError):
    def __init__(self, code, message=""):
        super().__init__(code)
        self.code, self.message = code, message


def _split_paragraphs(text):
    parts = [p.strip() for p in re.split(r"\n\s*\n", text.strip()) if p.strip()]
    if len(parts) == 1 and "\n" in parts[0] and len(parts[0]) < 4000:
        lines = [ln.strip() for ln in parts[0].splitlines() if ln.strip()]
        if len(lines) > 1 and all(len(ln) < 400 for ln in lines):
            parts = lines
    return parts


class DraftDesk:
    def __init__(self, orchestrator):
        self.o = orchestrator
        self.drafts = {}             # session_id -> Draft (one active draft per session)
        self.pending_new = {}        # session_id -> {"request", "question", "input"} (create awaiting an answer)
        self._lock = threading.Lock()

    # ---- state ------------------------------------------------------------------------------------
    def active(self, session_id):
        return self.drafts.get(session_id)

    def _set(self, session_id, draft):
        with self._lock:
            self.drafts[session_id] = draft
            while len(self.drafts) > MAX_SESSIONS:
                self.drafts.pop(next(iter(self.drafts)))

    def classify(self, text, session_id) -> TX.TextIntent:
        d = self.active(session_id)
        intent = TX.classify(text, has_draft=d is not None and d.current is not None)
        if intent.kind == TX.NONE and intent.reasons and intent.reasons[0] in ("not_a_text_task", "foreign_object"):
            if d is not None and d.pending_question:
                return TX.TextIntent(TX.REVISE, ["answer_to_clarification"], instruction=text,
                                     targets=TX.targets_for(text))
            if session_id in self.pending_new:
                return TX.TextIntent(TX.DRAFT_NEW, ["answer_to_clarification"], instruction=text)
        return intent

    def snapshot(self, session_id):
        d = self.active(session_id)
        return d.to_dict() if d is not None else None

    # ---- deterministic operations (no model; work with the Brain stopped) -------------------------------
    def op(self, session_id, op, n=None):
        d = self.active(session_id)
        if d is None or d.current is None:
            raise DeskError("NO_ACTIVE_DRAFT", "There is no draft in this conversation yet.")
        try:
            if op == "undo":
                d.undo()
            elif op == "redo":
                d.redo()
            elif op == "restore":
                if not isinstance(n, int) or isinstance(n, bool):
                    raise DeskError("VERSION_INVALID")
                d.restore(n)
            elif op == "discard":
                with self._lock:
                    self.drafts.pop(session_id, None)
                return None
            elif op not in ("show", "original"):
                raise DeskError("DRAFT_OP_UNKNOWN")
        except DS.DraftError as exc:
            raise DeskError(exc.code) from None
        return d.to_dict()

    # ---- a turn -------------------------------------------------------------------------------------------
    def handle(self, turn_id, text, session_id, intent: TX.TextIntent, inp: TI.TextInput, sink, *, fallback=None):
        """Run one text turn and emit uri.oi.event.v1 events. `fallback(text)` runs the ordinary orchestrator turn
        when the Brain says the message is not an edit after all. Returns a dict with status and the draft."""
        emit = lambda t, **d: sink.emit(turn_id, t, **d)
        t0 = time.monotonic()
        emit("turn.started", text_chars=len(text), depth="auto")
        emit("companion.state", state="thinking")
        tier = {"tier": FAST if intent.kind in TX.BRAIN_KINDS else "NONE", "selected_by": "draft_desk",
                "reason": "text_task_" + intent.kind.lower()}
        emit("turn.routed", route="draft", triage={"kind": "TEXT_TASK", "text_kind": intent.kind,
                                                   "reasons": intent.reasons, "source": inp.source}, tier=tier)
        try:
            if intent.kind in TX.DETERMINISTIC:
                out = self._deterministic(intent, session_id, emit)
            else:
                out = self._brain_turn(turn_id, text, session_id, intent, inp, emit, fallback)
        except DS.DraftError as exc:      # a model edit that breaks a draft limit: refused, draft unchanged
            exc = DeskError("DRAFT_OUTPUT_INVALID", "The Brain's edit was not usable (%s); the draft was not changed."
                            % exc.code)
            emit("error", code=exc.code, message=exc.message, recoverable=True, recovery_options=["retry"])
            out = {"status": "error", "code": exc.code}
        except DeskError as exc:
            emit("error", code=exc.code, message=exc.message or exc.code, recoverable=True,
                 recovery_options=_recovery(exc.code))
            out = {"status": "error", "code": exc.code}
        if out.get("delegated"):
            return out
        out["total_s"] = round(time.monotonic() - t0, 4)
        emit("turn.finished", status=out["status"], route="draft", total_s=out["total_s"])
        emit("companion.state", state={"needs_user": "waiting_user", "error": "error"}.get(out["status"], "idle"))
        return out

    def _say(self, emit, text, *, metrics=None, flags=()):
        emit("companion.state", state="speaking")
        emit("answer.delta", text=text)
        emit("answer.done", status="COMPLETE", complete=True, escalation_candidate=False, flags=list(flags),
             metrics=metrics or {"model_used": False})

    def _deterministic(self, intent, session_id, emit):
        op = {TX.UNDO: "undo", TX.REDO: "redo", TX.ORIGINAL: "original", TX.DISCARD: "discard", TX.SHOW: "show"}[intent.kind]
        d = self.active(session_id)
        if op == "original" and d is not None:
            src = d.source
            what = "your original words" if src.get("source") != "transcript" else (
                "the original transcript" + (" (simulated input)" if src.get("simulated") else ""))
            snap = d.to_dict()
            emit("draft.updated", op="original", draft=snap)
            self._say(emit, "Here is %s:\n\n%s" % (what, d.original_text))
            return {"status": "ok", "draft": snap}
        snap = self.op(session_id, op)
        if op == "discard":
            emit("draft.updated", op="discard", draft=None)
            self._say(emit, "Draft closed. Nothing was saved or sent.")
            return {"status": "ok", "draft": None}
        emit("draft.updated", op=op, draft=snap)
        cur = snap["current"]
        msg = {"undo": "Undone. Showing version %d of %d (%s).", "redo": "Redone. Showing version %d of %d (%s).",
               "show": "This is version %d of %d (%s)."}[op] % (snap["position"], snap["count"], cur["summary"] or cur["op"])
        self._say(emit, msg)
        return {"status": "ok", "draft": snap}

    def _ready(self):
        r = self.o.readiness() if self.o.readiness is not None else None
        if r is not None and r.state != "READY":
            raise DeskError("BRAIN_UNAVAILABLE", "The local Brain is not ready (%s); the draft was not changed. "
                            "Undo, redo and the original still work." % r.state)

    def _call(self, turn_id, system, user_obj, schema, name, max_tokens, emit):
        self._ready()
        cancel = self.o.cancels.setdefault(turn_id, BC.CancelToken())
        chars = {"n": 0, "last": 0}

        def on_delta(kind, chunk):
            chars["n"] += len(chunk)
            if chars["n"] - chars["last"] >= 120:
                chars["last"] = chars["n"]
                emit("draft.progress", chars=chars["n"])

        body = {"model": "local", "messages": [{"role": "system", "content": system},
                                               {"role": "user", "content": json.dumps(user_obj, ensure_ascii=False)}],
                "response_format": {"type": "json_schema", "json_schema": {"name": name, "schema": schema, "strict": True}},
                **tier_params(FAST, use="answer", max_tokens=max_tokens)}
        try:
            res = self.o.client.stream_chat(body, cancel=cancel, deadlines=TIMEOUT, on_delta=on_delta)
        finally:
            self.o.cancels.pop(turn_id, None)
        metrics = {"model_used": True, "ttft_s": res.ttft_s, "total_s": res.total_s,
                   "prompt_n": res.timings.get("prompt_n"), "predicted_n": res.timings.get("predicted_n"),
                   "predicted_per_second": res.timings.get("predicted_per_second"),
                   "cache_n": res.timings.get("cache_n"), "retried": res.retried}
        if self.o.perf is not None and res.status == BC.COMPLETE:
            self.o.perf.record(res.timings)
        if res.status == BC.CANCELLED:
            raise DeskError("CANCELLED", "Stopped. The draft was not changed.")
        if res.status != BC.COMPLETE:
            raise DeskError("BRAIN_" + res.status, "The local Brain did not finish (%s); the draft was not changed."
                            % res.status)
        try:
            data = json.loads(res.text)
        except ValueError:
            raise DeskError("DRAFT_OUTPUT_INVALID", "The Brain's answer was not usable; the draft was not changed.") from None
        if not isinstance(data, dict):
            raise DeskError("DRAFT_OUTPUT_INVALID", "The Brain's answer was not usable; the draft was not changed.")
        return data, metrics

    def _brain_turn(self, turn_id, text, session_id, intent, inp, emit, fallback):
        interpreted = TI.clean_transcript(text) if inp.is_transcript else text.strip()
        cues = TI.correction_cues(interpreted)
        k = intent.kind
        if k in (TX.DRAFT_NEW, TX.EXPAND):
            return self._create(turn_id, text, interpreted, session_id, intent, inp, cues, emit)
        if k in (TX.CORRECT, TX.REWRITE):
            payload = intent.payload
            if payload is None:
                raise DeskError("TEXT_MISSING", "Please include the text, for example: \"Correct this: <your text>\".")
            draft = DS.Draft(session_id=session_id, doc_type="text", tone="as given", source=inp.to_dict(),
                             original_text=text)
            blocks = [DS.Block(draft.new_id(), "body", p) for p in _split_paragraphs(payload)]
            if not blocks:
                raise DeskError("TEXT_MISSING", "There was no text to work on.")
            draft.push(blocks=blocks, facts=(), exclusions=(), missing=(), op="original", instruction=text,
                       summary="Your text as given.", changed=[b.id for b in blocks], removed=(), flags=())
            mode = "correct" if k == TX.CORRECT else "rewrite"
            out = self._edit(turn_id, intent.instruction or text, interpreted, draft, intent, inp, cues, emit,
                             mode=mode, fallback=None)
            if out["status"] == "ok":
                self._set(session_id, draft)
            return out
        d = self.active(session_id)
        if d is None or d.current is None:
            raise DeskError("NO_ACTIVE_DRAFT", "There is no draft to change yet.")
        mode = "correct" if intent.reasons and intent.reasons[0] == "correct_active_draft" else "revise"
        return self._edit(turn_id, text, interpreted, d, intent, inp, cues, emit, mode=mode, fallback=fallback)

    # ---- create ---------------------------------------------------------------------------------------------
    def _create(self, turn_id, text, interpreted, session_id, intent, inp, cues, emit):
        pend = self.pending_new.pop(session_id, None) if intent.reasons[:1] == ["answer_to_clarification"] else None
        request = interpreted
        source_words = interpreted
        original = text
        if pend:
            request = "%s\n\nYou asked: %s\nThe user answered: %s" % (pend["request"], pend["question"], interpreted)
            source_words = pend["request"] + "\n" + interpreted
            original = pend["original"] + "\n" + text
            inp_dict = pend["input"]
        else:
            inp_dict = inp.to_dict()
        user = {"request": request, "kind": "expand_notes" if intent.kind == TX.EXPAND else "new_document",
                "input_source": "dictated speech" if inp.is_transcript else "typed"}
        if cues:
            user["note"] = "The user corrected themselves (%s). Use only the final values." % ", ".join(cues[:4])
        if inp.uncertain:
            user["possibly_misheard"] = list(inp.uncertain)
        data, metrics = self._call(turn_id, CREATE_SYSTEM, user, CREATE_SCHEMA, "draft", MAX_DRAFT_TOKENS, emit)
        q = (data.get("clarification") or "").strip()
        if q and not data.get("blocks"):
            self.pending_new[session_id] = {"request": request, "question": q, "input": inp_dict, "original": original}
            emit("draft.clarify", question=q, draft=None)
            self._say(emit, q, metrics=metrics)
            return {"status": "needs_user", "question": q}
        draft = DS.Draft(session_id=session_id, doc_type=str(data.get("doc_type") or "document")[:60],
                         tone=str(data.get("tone") or "")[:60], source=inp_dict, original_text=original)
        try:
            blocks = DS.blocks_from_model(draft, data.get("blocks") or [])
        except DS.DraftError as exc:
            raise DeskError("DRAFT_OUTPUT_INVALID", "The Brain returned no usable draft (%s)." % exc.code) from None
        facts = _clean_facts(data.get("facts"))
        exclusions = _clean_list(data.get("exclusions"))
        body_text = DS.render(blocks)
        flags = (V.check_facts(facts, body_text, source_words) + V.check_exclusions(exclusions, body_text)
                 + V.check_correction_accounted(cues, facts, None) + V.check_new_details(body_text, source_words)
                 + V.check_uncertain(inp.uncertain, body_text))
        missing = sorted(set(_clean_list(data.get("missing"))) | set("[%s]" % p for p in V.placeholders(body_text)))
        v = draft.push(blocks=blocks, facts=facts, exclusions=exclusions, missing=missing, op="created",
                       instruction=text, summary=str(data.get("summary") or "Draft created.")[:300],
                       changed=[b.id for b in blocks], removed=(), flags=flags)
        self._set(session_id, draft)
        snap = draft.to_dict()
        emit("draft.updated", op="created", draft=snap)
        self._say(emit, _status_line(draft, v), metrics=metrics, flags=[f["code"] for f in flags])
        return {"status": "ok", "draft": snap}

    # ---- edit -----------------------------------------------------------------------------------------------
    def _edit(self, turn_id, text, interpreted, d, intent, inp, cues, emit, *, mode, fallback):
        cur = d.current
        q = d.pending_question
        user = {"instruction": interpreted, "input_source": "dictated speech" if inp.is_transcript else "typed",
                "document": {"doc_type": d.doc_type, "blocks": [b.to_dict() for b in cur.blocks]},
                "facts": [dict(f) for f in cur.facts], "exclusions": list(cur.exclusions),
                "last_changed": list(cur.changed)[-3:],
                "recent_instructions": [v.instruction for v in d.versions[max(0, d.cursor - 2):d.cursor + 1]][-3:]}
        if q:
            user["your_question"] = q
            user["note"] = "The instruction is the user's answer to your question."
        if cues and mode != "correct":
            user["self_correction_cues"] = cues[:4]
        system = EDIT_SYSTEM + ("\n" + CORRECT_RULE if mode == "correct" else "\n" + REWRITE_RULE if mode == "rewrite" else "")
        data, metrics = self._call(turn_id, system, user, EDIT_SCHEMA, "edit", MAX_EDIT_TOKENS, emit)
        action = data.get("action")
        if action == "not_an_edit" and fallback is not None and not q:
            return fallback()
        if action == "clarify" or (action == "not_an_edit"):
            question = (data.get("clarification") or "").strip() or "Which part of the draft should I change?"
            d.pending_question = question
            emit("draft.clarify", question=question, draft=d.to_dict())
            self._say(emit, question, metrics=metrics)
            return {"status": "needs_user", "question": question}
        allowed = _allowed_ids(cur, intent.targets) if mode == "revise" else None
        edits = [e for e in (data.get("edits") or []) if isinstance(e, dict)]
        blocks, applied, dropped = DS.apply_edits(d, cur.blocks, edits, allowed_ids=allowed)
        changed, removed = DS.diff_ids(cur.blocks, blocks)
        if not changed and not removed:
            d.pending_question = None
            msg = "I did not change anything: %s" % (str(data.get("summary") or "no edit was needed")[:200])
            emit("draft.updated", op="unchanged", draft=d.to_dict())
            self._say(emit, msg, metrics=metrics)
            return {"status": "ok", "draft": d.to_dict(), "unchanged": True}
        facts = _merge_facts(cur.facts, _clean_facts(data.get("fact_updates")))
        exclusions = list(dict.fromkeys(list(cur.exclusions) + _clean_list(data.get("exclusions_add"))))
        new_text, old_text = DS.render(blocks), DS.render(cur.blocks)
        user_words = "\n".join([d.original_text] + [v.instruction for v in d.versions] + [text, interpreted])
        known = user_words + "\n" + old_text
        flags = V.check_facts(facts, new_text, user_words) + V.check_exclusions(exclusions, new_text)
        if mode == "correct":
            flags += V.check_meaning_preserved(old_text, new_text)
        else:
            flags += V.check_new_details(new_text, known) + V.check_correction_accounted(
                cues, _clean_facts(data.get("fact_updates")), None)
        flags += V.check_uncertain(inp.uncertain, new_text)
        if dropped:
            flags.append({"code": "EDIT_OUTSIDE_TARGET", "severity": "review",
                          "detail": "%d change(s) outside the part you named were not applied" % len(dropped)})
        missing = ["[%s]" % p for p in V.placeholders(new_text)]
        op = {"correct": "corrected", "rewrite": "rewritten"}.get(mode, "revised")
        v = d.push(blocks=blocks, facts=facts, exclusions=exclusions, missing=missing, op=op, instruction=text,
                   summary=str(data.get("summary") or "Draft revised.")[:300], changed=changed, removed=removed,
                   flags=flags)
        snap = d.to_dict()
        emit("draft.updated", op=op, draft=snap)
        self._say(emit, _status_line(d, v), metrics=metrics, flags=[f["code"] for f in flags])
        return {"status": "ok", "draft": snap}


def _allowed_ids(version, targets):
    """Block ids the user named, or None when the instruction is about the whole document."""
    if not targets or targets.get("global", True):
        return None
    body = version.body_ids()
    ids = set()
    for i in targets.get("body") or ():
        if -len(body) <= i < len(body):
            ids.add(body[i])
    for role in targets.get("roles") or ():
        ids.update(b.id for b in version.blocks if b.role == role)
    for p in targets.get("phrases") or ():
        toks = [t for t in re.findall(r"[a-z0-9]+", p.lower()) if len(t) > 2]
        for b in version.blocks:
            low = b.text.lower()
            if p.lower() in low or (toks and all(t in low for t in toks)):
                ids.add(b.id)
    return ids or None


def _clean_list(items):
    return [str(x).strip()[:200] for x in (items or []) if isinstance(x, str) and x.strip()][:40]


def _clean_facts(items):
    out = []
    for f in items or []:
        if isinstance(f, dict) and str(f.get("value") or "").strip():
            out.append({"key": str(f.get("key") or "")[:80], "value": str(f["value"]).strip()[:300],
                        "superseded": _clean_list(f.get("superseded"))})
    return out[:40]


def _merge_facts(old, updates):
    merged = [dict(f) for f in old]
    for u in updates:
        hit = None
        for f in merged:
            if f["key"].lower() == u["key"].lower() or any(s.lower() == f["value"].lower() for s in u["superseded"]):
                hit = f
                break
        if hit is not None:
            hit["superseded"] = list(dict.fromkeys(list(hit.get("superseded") or []) + [hit["value"]] + u["superseded"]))
            hit["superseded"] = [s for s in hit["superseded"] if s.lower() != u["value"].lower()]
            hit["value"], hit["key"] = u["value"], u["key"] or hit["key"]
        else:
            merged.append(dict(u))
    return merged


def _status_line(d, v):
    parts = ["%s (version %d of %d): %s" % (d.doc_type.capitalize() if d.doc_type else "Draft", d.cursor + 1,
                                              len(d.versions), v.summary)]
    if v.missing:
        parts.append("Missing: " + ", ".join(v.missing[:6]) + ".")
    errs = [f for f in v.flags if f["severity"] == "error"]
    rev = [f for f in v.flags if f["severity"] == "review"]
    if errs or rev:
        parts.append("%d check(s) need your attention." % (len(errs) + len(rev)))
    parts.append("Nothing has been sent or saved.")
    return " ".join(parts)


def _recovery(code):
    if code == "BRAIN_UNAVAILABLE":
        return ["start_brain", "retry", "undo"]
    if code in ("CANCELLED",):
        return ["retry"]
    if code.startswith("BRAIN_") or code == "DRAFT_OUTPUT_INVALID":
        return ["retry"]
    return []
