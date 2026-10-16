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

DROP = "DROP_QUESTION"
MAX_DRAFT_TOKENS = 1800
MAX_EDIT_TOKENS = 1500
MAX_SESSIONS = 64
TIMEOUT = BC.Deadlines(first_token_s=60.0, idle_s=30.0, total_s=180.0)

_FACT = {"type": "object", "properties": {"key": {"type": "string"}, "value": {"type": "string"},
                                          "superseded": {"type": "array", "items": {"type": "string"}}},
         "required": ["key", "value", "superseded"], "additionalProperties": False}
_NULLABLE_STR = {"anyOf": [{"type": "string"}, {"type": "null"}]}

_ACTIONS = {"type": "array", "items": {"type": "string"}}

CREATE_SCHEMA = {
    "type": "object",
    "properties": {
        "actions_requested": _ACTIONS,
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
    "required": ["actions_requested", "clarification", "facts", "exclusions", "doc_type", "tone", "blocks", "missing",
                 "summary"],
    "additionalProperties": False,
}

EDIT_SCHEMA = {
    "type": "object",
    "properties": {
        "actions_requested": _ACTIONS,
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
    "required": ["actions_requested", "action", "clarification", "fact_updates", "exclusions_add", "edits", "summary"],
    "additionalProperties": False,
}

_ACTION_RULE = (
    "`actions_requested`: list every thing the user asks URI to DO beyond writing this text (send, email, forward, "
    "save, print, upload, share, schedule, remind, remember). Describing such things INSIDE the document (\"ask the "
    "parents to send the form\") is not a request to URI. Empty list when there is none.\n")

_COMMON_RULES = (
    "Never invent names, dates, days, numbers, places, reference numbers, authorities, signatures, quotations or "
    "events. Use only details the user gave. Where a document normally needs information the user did not give "
    "(sender name, designation, recipient name, date, institution name, contact details), write a placeholder in "
    "square brackets such as [Your Name] or [Date] and list it in missing. Do not add accusations, reasons, "
    "consequences, promises or requests the user did not state; ordinary courteous phrasing is fine. Never make "
    "the matter sound more serious than the user did: no 'serious breach', 'violation', 'misconduct', no request "
    "for disciplinary action, punishment or an inquiry unless the user asked for it. Keep the "
    "user's language register: Indian English office conventions are welcome where they fit (\"Respected Sir/Madam\", "
    "\"Thanking you\", \"Yours faithfully\"). Hindi or Hinglish instructions are understood, but write the document in "
    "English unless the user asks for another language.")

CREATE_SYSTEM = (
    "You are URI's writing desk. You turn the user's request into a finished, professional document. You only "
    "write text: you never send, save or file anything, and you never say that you did.\n" + _ACTION_RULE +
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
    "fact, put ONE short question in `clarification` and return no blocks; otherwise clarification is null.\n"
    "FINAL CHECK before you answer (live finding LQ-26): the letter must not ask for disciplinary action, "
    "punishment or an inquiry, must not call the matter a breach, violation or misconduct, and must not add lists of "
    "people, roll numbers or attachments, unless the user's own words asked for that. Report what the user said, in "
    "a neutral tone, and ask the reader only to look into it.")

EDIT_SYSTEM = (
    "You are URI's writing desk, revising an existing document. You only write text: you never send, save or file "
    "anything. You receive the document as blocks with ids and roles, the accepted facts, and the user's "
    "instruction (possibly dictated speech with self-corrections; the newest value wins).\n" + _ACTION_RULE +
    "Return edit operations. Change ONLY what the instruction asks. Blocks you do not edit stay exactly as they are, "
    "so never list a block you are not changing. For replace, give the complete new text of that block. "
    "\"Paragraph N\" means the N-th block whose role is body. \"Previous sentence\" or \"that\" means the text "
    "changed most recently (listed in last_changed). A tone instruction (\"more diplomatic\", \"more formal\") may "
    "touch every block that needs it, but every fact, name, date and number must stay, and wording the user "
    "dictated (\"say they left without ...\") and every fact value must appear VERBATIM in the new text. \"Keep everything else the same\" means the smallest possible edit.\n"
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


def _draft_text(d):
    """The open draft's current text, for anchoring revisions to the document (UIV2-F1); None without one."""
    return d.current.text() if d is not None and d.current is not None else None


class DraftDesk:
    def __init__(self, orchestrator):
        self.o = orchestrator
        self.drafts = {}             # session_id -> Draft (one active draft per session)
        self.pending_new = {}        # session_id -> {"request", "question", "input"} (create awaiting an answer)
        self._lock = threading.Lock()
        self.tier = FAST             # qualified tier for desk calls (live matrix may compare NORMAL)

    # ---- state ------------------------------------------------------------------------------------
    def active(self, session_id):
        return self.drafts.get(session_id)

    def _set(self, session_id, draft):
        with self._lock:
            old = self.drafts.get(session_id)
            if old is not None and old is not draft and old.current is not None:
                # UIV2-F1: keep the replaced draft (one level, its own older chain dropped) so Undo can bring it back.
                old.replaced, old.replaced_by, old.replaced_by_cursor = None, None, None
                draft.replaced = old
            self.drafts[session_id] = draft
            while len(self.drafts) > MAX_SESSIONS:
                self.drafts.pop(next(iter(self.drafts)))

    def classify(self, text, session_id) -> TX.TextIntent:
        """An open question (draft.pending_question or a pending create) lives for ONE user turn: the next turn either
        answers it, drops it explicitly ("never mind"), or goes elsewhere, which also drops it."""
        d = self.active(session_id)
        has_question = (d is not None and bool(d.pending_question)) or session_id in self.pending_new
        if has_question and TX.drops_question(text):
            return TX.TextIntent(DROP, ["drop_open_question"], instruction=text)
        intent = self._classify(text, session_id, d)
        if has_question and intent.reasons[:1] != ["answer_to_clarification"]:
            self.pending_new.pop(session_id, None)
            if d is not None:
                d.pending_question = None
        return intent

    def drop_open_question(self, session_id):
        """Dictation and command input never answer an open question; it is dropped (one-turn lifetime)."""
        self.pending_new.pop(session_id, None)
        d = self.active(session_id)
        if d is not None:
            d.pending_question = None

    def _classify(self, text, session_id, d):
        pend = self.pending_new.get(session_id)
        if pend and pend.get("ambiguous"):
            # L-2: the user answers "is this sentence part of the text, or should URI do it?". A choice is taken only
            # when the WHOLE reply is one of the offered choices ("write it in" / "do it", with an optional please/ok);
            # nothing is read out of a longer or negated reply (Codex TIWS r2 L2-R2-1, r3 L2-R3-1/2).
            reply = _CHOICE_TRIM.sub("", (text or "").strip().lower())
            if reply in _CHOICE_CONTENT:
                return TX.TextIntent(TX.DRAFT_NEW, ["answer_to_clarification", "ambiguity_content"], instruction=text)
            if reply in _CHOICE_ACTION:
                # The original request goes to the ordinary path unchanged; Core decides and asks for approval.
                return TX.TextIntent(TX.NONE, ["ambiguity_action"], payload=pend["original"], instruction=text)
            plain = TX.classify(text, has_draft=d is not None and d.current is not None, draft_text=_draft_text(d))
            own_question = (text or "").rstrip().endswith("?") or bool(_OWN_QUESTION.match(text or ""))
            if plain.kind == TX.NONE and plain.reasons[:1] in (["not_a_text_task"], ["trivial"], ["unanchored_with_draft"]) \
                    and not own_question:
                # "yes", "no", "dont do it", "hmm": not a choice and not a new request -> asked again, never guessed
                return TX.TextIntent(TX.DRAFT_NEW, ["answer_to_clarification", "ambiguity_unclear"], instruction=text)
            # anything else is a new request: the question is dropped (one-turn lifetime) and it routes as usual
        intent = TX.classify(text, has_draft=d is not None and d.current is not None, draft_text=_draft_text(d))
        # An open draft question accepts elliptical answers, but a new imperative request is not an answer.
        answers = ("not_a_text_task", "foreign_object", "unanchored_with_draft")
        if intent.reasons[:1] == ["trivial"] and _SHORT_ANSWER.match(text or ""):
            answers += ("trivial",)            # yes/no may answer a matching open question
        # A question of the user's own ("what is ...?") is not an answer to URI's question.
        own_question = (text or "").rstrip().endswith("?") or bool(_OWN_QUESTION.match(text or ""))
        question = d.pending_question if d is not None and d.pending_question else \
            (pend or {}).get("question")
        if intent.kind == TX.NONE and intent.reasons and intent.reasons[0] in answers \
                and not own_question and _looks_like_answer(text, question):
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
                if d.cursor == 0 and d.replaced is not None:
                    back = d.replaced                 # UIV2-F1: back to the draft this one replaced
                    back.replaced_by = d
                    back.replaced_by_cursor = back.cursor
                    with self._lock:
                        self.drafts[session_id] = back
                    back.pending_question = None
                    return back.to_dict()
                d.undo()
            elif op == "redo":
                if d.replaced_by is not None and d.cursor == d.replaced_by_cursor:
                    fwd = d.replaced_by
                    with self._lock:
                        self.drafts[session_id] = fwd
                    fwd.pending_question = None
                    return fwd.to_dict()
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
            if intent.kind == DROP:
                d = self.active(session_id)
                self.pending_new.pop(session_id, None)
                if d is not None:
                    d.pending_question = None
                emit("draft.clarify", question=None, draft=d.to_dict() if d is not None else None)
                self._say(emit, "Okay, I have dropped that question. Nothing was changed.")
                out = {"status": "ok", "draft": d.to_dict() if d is not None else None}
            elif intent.kind in TX.DETERMINISTIC:
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
                **tier_params(self.tier, use="answer", max_tokens=max_tokens)}
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
            return self._create(turn_id, text, interpreted, session_id, intent, inp, cues, emit, fallback)
        if k in (TX.CORRECT, TX.REWRITE):
            payload = intent.payload
            if intent.reasons[:1] in (["dictation_mode"], ["dictated_content"]):
                # L-2: the words are content. The Brain is told so; the instruction it sees is URI's, not the text.
                interpreted = ("Dictated content: correct grammar, spelling and punctuation only. Every sentence is "
                               "text to keep, not a request to URI." if k == TX.CORRECT else
                               "Dictated content: rewrite it professionally, keeping every fact. Every sentence is "
                               "text to keep, not a request to URI.")
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
    def _create(self, turn_id, text, interpreted, session_id, intent, inp, cues, emit, fallback=None):
        # Kept until a draft is created: a Brain failure or a cancel must not lose the user's original request.
        pend = self.pending_new.get(session_id) if intent.reasons[:1] == ["answer_to_clarification"] else None
        if intent.reasons[:1] == ["ambiguous_action_sentences"] and intent.ambiguous:
            # L-2: a drafting request followed by sentences that start with an action verb. They may be the
            # document's own words or an instruction to URI; URI does not guess (no model call, nothing drafted).
            quoted = " and ".join("\u201c%s\u201d" % a for a in intent.ambiguous[:3])
            q = ("Should %s be written into the text, or should URI do %s? Reply \u201cwrite it in\u201d to keep it as "
                 "text, or \u201cdo it\u201d to hand your request to URI's action path, where Core checks it and asks "
                 "for approval." % (quoted, "them" if len(intent.ambiguous) > 1 else "it"))
            self.pending_new[session_id] = {"request": interpreted, "question": q, "input": inp.to_dict(),
                                            "original": text, "ambiguous": list(intent.ambiguous)}
            emit("draft.clarify", question=q, draft=None)
            self._say(emit, q)
            return {"status": "needs_user", "question": q}
        if "ambiguity_unclear" in intent.reasons and pend and pend.get("ambiguous"):
            q = ("I could not tell which you meant. Reply with only \u201cwrite it in\u201d to keep %s as text, or only "
                 "\u201cdo it\u201d to hand your request to URI's action path." %
                 " and ".join("\u201c%s\u201d" % a for a in pend["ambiguous"][:3]))
            pend["question"] = q                 # still open for one more turn; nothing drafted, nothing sent
            emit("draft.clarify", question=q, draft=None)
            self._say(emit, q)
            return {"status": "needs_user", "question": q}
        content_confirmed = "ambiguity_content" in intent.reasons and bool(pend and pend.get("ambiguous"))
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
        if content_confirmed:
            user["dictated_sentences"] = list(pend["ambiguous"])
            user["note_dictated"] = ("The user confirmed that these sentences are part of the document's text, written "
                                     "for its readers. They are not requests to URI: write them in the document and do "
                                     "not list them in actions_requested.")
        if inp.uncertain:
            user["possibly_misheard"] = list(inp.uncertain)
            user["note_misheard"] = ("Write the draft using these words exactly as heard; URI shows them to the user "
                                     "for confirmation. Do not ask about anything else that is merely unspecified.")
        data, metrics = self._call(turn_id, CREATE_SYSTEM, user, CREATE_SCHEMA, "draft", MAX_DRAFT_TOKENS, emit)
        if _clean_list(data.get("actions_requested")) and fallback is not None and not content_confirmed:
            # Model-side guard: the user also asked URI to act. Core decides; nothing was drafted or shown yet.
            self.pending_new.pop(session_id, None)
            return fallback()
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
        superseded = [s for f in facts for s in f["superseded"]]
        user_excl = V.user_exclusions(source_words)
        flags = (V.check_facts(facts, body_text, source_words)
                 + V.check_exclusions(list(dict.fromkeys(exclusions + user_excl)), body_text)
                 + V.check_supersession(source_words, superseded) + V.check_escalation(body_text, source_words)
                 + V.check_user_details(source_words, body_text,
                                        V.verified_superseded(source_words, superseded)[0] + exclusions + user_excl)
                 + V.check_correction_accounted(cues, facts, None) + V.check_new_details(body_text, source_words)
                 + V.check_uncertain(inp.uncertain, body_text)
                 + V.check_reassignment(source_words, body_text)
                 + (_dictated_flag(pend["ambiguous"]) if content_confirmed else []))
        exclusions = list(dict.fromkeys(exclusions + user_excl))     # kept on the version: later edits are checked too
        # One list: the [placeholders] in the text, plus any missing item the model named that no placeholder covers.
        holes = ["[%s]" % p for p in V.placeholders(body_text)]
        low = " ".join(holes).lower()
        missing = holes + [m for m in _clean_list(data.get("missing")) if m.lower() not in low]
        self.pending_new.pop(session_id, None)
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
                "document": {"doc_type": d.doc_type, "blocks": [b.to_dict() for b in cur.blocks],
                             # live finding LQ-12: the model miscounted paragraphs; give it the numbering
                             "paragraphs": {str(i + 1): bid for i, bid in enumerate(cur.body_ids())}},
                "facts": [dict(f) for f in cur.facts], "exclusions": list(cur.exclusions),
                "last_changed": list(cur.changed)[-3:],
                "recent_instructions": [v.instruction for v in d.versions[max(0, d.cursor - 2):d.cursor + 1]][-3:]}
        if q:
            user["your_question"] = q
            user["note"] = "The instruction is the user's answer to your question."
        if cues and mode != "correct":
            user["self_correction_cues"] = cues[:4]
        allowed = None
        dates = V.date_mentions(DS.render(cur.blocks))
        if mode == "revise" and not q and re.search(r"\b(?:change|update|correct|fix|move|shift)\s+the\s+(?:date|day)\b",
                                                   interpreted, re.I) \
                and len(dates) >= 2 and not any(dt in interpreted.lower() for dt in dates):
            question = "Which date should change: %s?" % " or ".join("the " + x if x[0].isdigit() else x.capitalize()
                                                                     for x in dates[:3])
            d.pending_question = question
            emit("draft.clarify", question=question, draft=d.to_dict())
            self._say(emit, question)
            return {"status": "needs_user", "question": question}
        if mode == "revise":
            allowed, unresolved = _allowed_ids(cur, intent.targets)
            if unresolved:
                question = "I could not find %s in the draft. Which part should I change?" % " or ".join(unresolved[:2])
                d.pending_question = question
                emit("draft.clarify", question=question, draft=d.to_dict())
                self._say(emit, question)
                return {"status": "needs_user", "question": question}
        system = EDIT_SYSTEM + ("\n" + CORRECT_RULE if mode == "correct" else "\n" + REWRITE_RULE if mode == "rewrite" else "")
        data, metrics = self._call(turn_id, system, user, EDIT_SCHEMA, "edit", MAX_EDIT_TOKENS, emit)
        action = data.get("action")
        if _clean_list(data.get("actions_requested")) and fallback is not None:
            d.pending_question = None   # the user also asked URI to act: Core decides; the open question is dropped
            return fallback()
        if action == "not_an_edit" and fallback is not None and not q:
            return fallback()           # not an edit: the ordinary path
        if action == "clarify" or (action == "not_an_edit"):
            question = (data.get("clarification") or "").strip() or "Which part of the draft should I change?"
            d.pending_question = question
            emit("draft.clarify", question=question, draft=d.to_dict())
            self._say(emit, question, metrics=metrics)
            return {"status": "needs_user", "question": question}
        edits = [e for e in (data.get("edits") or []) if isinstance(e, dict)]
        blocks, applied, dropped = DS.apply_edits(d, cur.blocks, edits, allowed_ids=allowed)
        changed, removed = DS.diff_ids(cur.blocks, blocks)
        if not changed and not removed:
            d.pending_question = None
            if edits:
                msg = ("I could not apply that change to this draft (%d proposed edit(s) did not match it). The draft "
                       "is unchanged; please say which part to change." % len(edits))
            else:
                msg = "I did not change anything: %s" % (str(data.get("summary") or "no edit was needed")[:200])
            emit("draft.updated", op="unchanged", draft=d.to_dict())
            self._say(emit, msg, metrics=metrics)
            return {"status": "ok", "draft": d.to_dict(), "unchanged": True}
        facts = _merge_facts(cur.facts, _clean_facts(data.get("fact_updates")))
        # "Don't say X, say Y": a fact whose value contains X is retired deterministically (live finding LQ-9: the
        # model did not always update it, so the stale value was demanded in the next version).
        # "Don't say X, say Y": the fact holding X is retired and Y becomes a required fact, so the replacement is
        # checked (Codex TI r12); "don't mention X" alone retires the fact (the user asked for its removal).
        pairs = V.swap_pairs(interpreted)
        swapped = [x.lower() for x, _ in pairs] + [p.lower() for p in V.user_exclusions(interpreted) if p]
        for f in facts:
            if any(p and p in f["value"].lower() for p in swapped):
                f["superseded"] = list(dict.fromkeys(f["superseded"] + [f["value"]]))
                f["value"] = ""
        facts = [f for f in facts if f["value"]]
        for x, y in pairs:
            if y and not any(f["value"].lower() == y.lower() for f in facts):
                facts.append({"key": "your wording", "value": y, "superseded": [x]})
        exclusions = list(dict.fromkeys(list(cur.exclusions) + _clean_list(data.get("exclusions_add"))))
        new_text, old_text = DS.render(blocks), DS.render(cur.blocks)
        user_words = "\n".join([d.original_text] + [v.instruction for v in d.versions] + [text, interpreted])
        known = user_words + "\n" + old_text
        exclusions = list(dict.fromkeys(exclusions + V.user_exclusions(interpreted)))
        excl_low = [e.lower() for e in exclusions]
        for f in facts:                       # "Don't mention the student's name" -> the name fact is retired (LQ-22)
            if any(f["value"].lower() in e or e in f["value"].lower() for e in excl_low if len(e) > 2):
                f["superseded"] = list(dict.fromkeys(f["superseded"] + [f["value"]]))
                f["value"] = ""
        facts = [f for f in facts if f["value"]]
        flags = V.check_facts(facts, new_text, user_words) + V.check_exclusions(exclusions, new_text)
        if mode == "correct":
            flags += V.check_meaning_preserved(old_text, new_text)
        else:
            flags += V.check_escalation(new_text, user_words + "\n" + old_text)
            new_sup = [s for f in _clean_facts(data.get("fact_updates")) for s in f["superseded"]]
            flags += V.check_supersession(interpreted + "\n" + user_words, new_sup, instruction=interpreted,
                                          previous_text=old_text)
            gone = (V.verified_superseded(user_words, [s for f in facts for s in f["superseded"]])[0] + exclusions
                    + V.verified_across_turns(interpreted, old_text, new_sup))
            flags += V.check_details_kept(old_text, new_text, gone + [interpreted])
            flags += V.check_new_details(new_text, known)
            if not V.correction_visible(interpreted, old_text, new_text):
                flags += V.check_correction_accounted(cues, _clean_facts(data.get("fact_updates")), None)
        flags += V.check_uncertain(inp.uncertain, new_text)
        # L-4: a value moved to another entry (amounts between students, dates between events). Advisory; the user's
        # own instruction can ask for it, which is shown as such.
        flags += V.check_reassignment(old_text, new_text, instruction=interpreted)
        if intent.reasons[:1] in (["dictation_mode"], ["dictated_content"]):
            flags += _dictated_flag(TX.action_sentences(old_text))
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


_SHORT_ANSWER = re.compile(r"^\s*(?:yes|yeah|yep|yup|no|nope|nah|ok(?:ay)?|sure|haan|ha|nahi|theek hai)\b", re.I)
_OWN_QUESTION = re.compile(r"^\s*(?:what|why|how|who|whom|whose|when|where|which|can you|could you|do you|does|is there)\b", re.I)
_NEW_REQUEST = re.compile(r"^\s*(?:(?:uri|please|could you|can you)\s+)*(?:tell me|show me|give me|help me|"
                          r"start|set (?:a|the)\b|play|open|launch|search|find|look up|explain|create|"
                          r"write|compose|make me|change your|update me|add|remove)\b", re.I)
_DATE_QUESTION = re.compile(r"\b(?:date|day)\b", re.I)
_WEEKDAY = r"monday|tuesday|wednesday|thursday|friday|saturday|sunday"
_MONTH = r"january|february|march|april|may|june|july|august|september|october|november|december"
_DATE_REPLY = re.compile(
    r"(?:(?:on|the|for)\s+)*(?:today|tomorrow|yesterday|(?:next|this)\s+(?:" + _WEEKDAY + r")|"
    r"(?:" + _WEEKDAY + r")|\d{4}-\d{1,2}-\d{1,2}|\d{1,2}[/-]\d{1,2}(?:[/-]\d{2,4})?|"
    r"\d{1,2}(?:st|nd|rd|th)?(?:\s+(?:of\s+)?(?:" + _MONTH + r"))?(?:,?\s+\d{4})?)",
    re.I)
_YES_NO_QUESTION = re.compile(r"^\s*(?:is|are|was|were|do|does|did|can|could|should|would|will|have|has)\b", re.I)


def _looks_like_answer(text, question):
    """Accept an elliptical answer only when its content fits the pending question.

    A semicolon may follow the answer with more instructions; the desk's action guard still handles those.
    """
    reply = (text or "").strip()
    if not question or _NEW_REQUEST.match(reply):
        return False
    first = reply.split(";", 1)[0].strip(" .,!?\t\n")
    if _DATE_QUESTION.search(question):
        return bool(_DATE_REPLY.fullmatch(first))
    if _YES_NO_QUESTION.match(question):
        return bool(_SHORT_ANSWER.fullmatch(first))
    # Unrecognized open questions require an explicit edit request; shape alone does not establish relevance.
    return False


_ORD_NAME = {0: "the first paragraph", 1: "the second paragraph", 2: "the third paragraph", 3: "the fourth paragraph",
             4: "the fifth paragraph", -1: "the last paragraph"}


def _allowed_ids(version, targets):
    """(block ids the user named, unresolved part names). ids is None for a whole-document instruction. A named part
    that does not exist in the draft is reported as unresolved: URI asks instead of widening the edit."""
    if not targets or targets.get("global", True):
        return None, []
    body = version.body_ids()
    ids, unresolved = set(), []
    for i in targets.get("body") or ():
        if -len(body) <= i < len(body):
            ids.add(body[i])
        else:
            unresolved.append(_ORD_NAME.get(i, "paragraph %d" % (i + 1)))
    for role in targets.get("roles") or ():
        found = {b.id for b in version.blocks if b.role == role}
        ids |= found
        if not found:
            unresolved.append("the " + role)
    for p in targets.get("phrases") or ():
        toks = [t for t in re.findall(r"[a-z0-9]+", p.lower()) if len(t) > 2]
        found = {b.id for b in version.blocks
                 if p.lower() in b.text.lower() or (toks and all(t in b.text.lower() for t in toks))}
        ids |= found
        if not found:
            unresolved.append("'%s'" % p)
    return ids, unresolved


_CHOICE_TRIM = re.compile(r"^(?:(?:ok(?:ay)?|please|pls|yes|haan)[,!]?\s+)*|[\s.!,]*(?:please)?[\s.!]*$")
_CHOICE_CONTENT = {"write it in", "write them in", "put it in", "put them in", "keep it as text", "keep them as text",
                   "as text", "it is text", "it's text", "text", "part of the text", "in the text", "include it",
                   "include them"}
_CHOICE_ACTION = {"do it", "do them", "do that", "go ahead and do it", "carry it out", "carry them out"}


def _dictated_flag(sentences):
    """Shown, never silent: sentences that read as instructions were written as text and not carried out."""
    s = [x for x in sentences if x][:3]
    if not s:
        return []
    return [{"code": "DICTATED_INSTRUCTION", "severity": "info",
             "detail": "written as text, not carried out: " + "; ".join("\u201c%s\u201d" % x[:80] for x in s)}]


def _clean_list(items):
    return [str(x).strip()[:200] for x in (items or []) if isinstance(x, str) and x.strip()][:40]


_NOT_A_FACT = re.compile(r"^\s*(?:tone|style|format|formality|register|language|length|document[ _]?type|doc[ _]?type|"
                         r"type of document|kind)\s*$", re.I)


def _clean_facts(items):
    out = []
    for f in items or []:
        if isinstance(f, dict) and str(f.get("value") or "").strip() and not _NOT_A_FACT.match(str(f.get("key") or "")):
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
    rev = [f for f in v.flags if f["severity"] == "review"]      # "info" lines are shown in the panel, not counted
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
