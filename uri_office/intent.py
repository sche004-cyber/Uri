"""Office intent routing (plan §5 `intent.py`, §6.1 step 2, §9.5, AC-O2-10, AC-O2-11; contract §4 IntentResult).

Stage 1 is a deterministic phrase matcher over a closed intent set. Stage 2 (the Brain, `OfficeBrain.classify`) runs
only when stage 1 has no unique answer and the Brain is available; it may only name one intent from the closed set and
the missing inputs, never facts. With no Brain, or an unusable answer, the result is a clarification with chips from
the capability registry. A planned capability always answers "not available yet" and never starts anything.

What stage 2 sees: the request text, at most the last 4 owner turns, and the KIND of the active file. Never a file
name, an outline title or document text (plan §9.5).
"""
from __future__ import annotations

import re
import uuid

from . import capabilities as CAP

INTENTS = ("open_document", "view_pdf", "save_as_pdf", "print_document", "open_workbook", "new_workbook_from_files",
           "write_document", "edit_document", "ask_pdf", "summarize_pdf", "make_presentation", "edit_presentation",
           "pdf_tables_to_excel", "combine_report")
# Intents that act on the ACTIVE file. A stage-2 answer naming one of them while a file of another kind is active does
# not fit what the owner is looking at (C1-1: "shorten it" on a presentation came back as edit_document, a Word-only
# intent); it becomes a clarification, never a plan for a different kind of file.
ACTS_ON_ACTIVE = ("edit_document", "edit_presentation", "ask_pdf", "summarize_pdf", "view_pdf", "pdf_tables_to_excel")
MISSING = ("input_file", "output_format", "page_scope", "input_role")
VIEWS = {"pdf": "pdfs", "pdfs": "pdfs", "document": "documents", "documents": "documents", "word": "documents",
         "presentation": "presentations", "presentations": "presentations", "slides": "presentations",
         "decks": "presentations", "spreadsheet": "spreadsheets", "spreadsheets": "spreadsheets",
         "workbook": "spreadsheets", "workbooks": "spreadsheets", "excel": "spreadsheets", "recent": "recent",
         "templates": "templates", "workflows": "workflows", "tasks": "workflows", "home": "home"}
MAX_TEXT = 2000

_W = r"[a-z0-9'-]+"
# Each rule: (intent, compiled pattern). Order does not decide: all rules are tried and a unique intent wins.
_RULES = [
    ("save_as_pdf", re.compile(r"\b(convert|save|export|turn|make|change|produce|create|generate|get)\b"
                               r"(?:\s+" + _W + r"){0,5}?\s+(?:as|to|into|in|a|an)?\s*\bpdf\b")),
    ("save_as_pdf", re.compile(r"^\s*(?:save|export|convert)\s+(?:as|to)\s+pdf\b")),
    ("save_as_pdf", re.compile(r"\bpdf\s+(?:of|from|version of)\s+(?:this|the|my)\b")),
    ("print_document", re.compile(r"\bprint(?:\s+out)?\b(?!\s+preview)")),
    ("summarize_pdf", re.compile(r"\b(summari[sz]e|summary|gist|key points)\b")),
    ("write_document", re.compile(r"\b(write|draft|compose|prepare)\b(?:\s+" + _W + r"){0,3}?\s+"
                                  r"\b(letter|notice|memo|memorandum|office order|order|minutes|circular|"
                                  r"corrigendum|report)\b")),
    ("make_presentation", re.compile(r"\b(make|create|build|prepare|turn)\b(?:\s+" + _W + r"){0,4}?\s+"
                                     r"\b(presentation|slides|slide deck|deck)\b(?!\s+into)")),
    ("pdf_tables_to_excel", re.compile(r"\b(extract|pull|copy|get)\b(?:\s+" + _W + r"){0,3}?\s+\btables?\b"
                                       r"(?:\s+" + _W + r"){0,3}?\s+\b(excel|spreadsheet|workbook)\b")),
    ("combine_report", re.compile(r"\b(report|summary)\s+from\s+(several|these|multiple|all)\s+files\b")),
    ("new_workbook_from_files", re.compile(r"\bnew\s+(workbook|spreadsheet)\s+from\b")),
    ("open_document", re.compile(r"^\s*open\s+(?:a|an|the|my)?\s*(document|file|pdf|presentation|word file|"
                                 r"letter|deck)\s*$")),
    ("open_workbook", re.compile(r"^\s*open\s+(?:a|an|the|my)?\s*(workbook|spreadsheet|excel file)\s*$")),
    ("view_pdf", re.compile(r"\b(search|find)\b(?:\s+" + _W + r"){0,3}?\s+\b(pdf|document)\b\s+for\b")),
]
_NAV = re.compile(r"^\s*(?:show|open|go to|switch to|take me to)?\s*(?:me\s+)?(?:my\s+|the\s+)?"
                  r"(?:(recent)(?:\s+files)?|(running\s+)?(workflows|tasks)|(pdfs|documents|presentations|"
                  r"spreadsheets|workbooks|templates))\s*$")
_HOME = re.compile(r"^\s*(?:(?:go to|open|show)\s+)?(?:uri\s+)?office(?:\s+home)?\s*$|^\s*office home\s*$")
_HELP = re.compile(r"^\s*(help|what can you do|what can i do here)\??\s*$")


def normalize(text: str) -> str:
    t = text.lower().replace("’", "'")
    t = re.sub(r"[^\w\s'-]", " ", t)
    return re.sub(r"\s+", " ", t).strip()


def stage1(text: str, target_kind: str | None) -> dict | None:
    """Deterministic match. Returns an IntentResult, or None when there is no unique answer."""
    t = normalize(text)
    if not t:
        return None
    if _HELP.match(t):
        return {"result": "help", "stage": 1}
    if _HOME.match(t):
        return {"result": "navigate", "view": "home", "stage": 1}
    m = _NAV.match(t)
    if m:
        word = m.group(1) or m.group(3) or m.group(4)
        return {"result": "navigate", "view": VIEWS.get(word, "workflows" if word in ("workflows", "tasks") else
                                                         word), "stage": 1}
    hits = {intent for intent, rx in _RULES if rx.search(t)}
    if len(hits) != 1:
        return None
    return resolve(hits.pop(), target_kind, stage=1)


def resolve(intent: str, target_kind: str | None, *, stage: int) -> dict:
    """An IntentResult for a known intent: planned capabilities answer honestly; missing inputs are named."""
    cap = CAP.get(intent)
    if cap is not None and cap["status"] != "available":
        return {"result": "planned", "intent": intent, "phase": CAP.phase_of(intent),
                "message": CAP.planned_message(intent), "stage": stage}
    needed = []
    if intent == "save_as_pdf" and target_kind not in ("docx", "pptx", "xlsx"):
        needed.append("input_file")
    if intent in ("open_document", "open_workbook", "new_workbook_from_files"):
        needed.append("input_file")
    if intent == "view_pdf" and target_kind != "pdf":
        needed.append("input_file")
    out = {"result": "matched", "intent": intent, "capability": intent, "stage": stage, "inputs_needed": needed}
    if cap is not None and cap.get("route"):
        out["route"] = cap["route"]          # OD-2: write_document runs through POST /authoring/draft, not a workflow
    return out


def clarify(target_kind: str | None) -> dict:
    """Fixed-text clarification with chips for what is available now, preferring ones that fit the active file."""
    reg = CAP.registry()["capabilities"]
    chips = []
    for c in reg:
        if c["status"] != "available" or c["id"] in ("open_workbook",):
            continue
        if target_kind and target_kind not in c["inputs"] and c["inputs"]:
            continue
        chips.append({"label": c["title"], "intent": c["id"]})
    chips = chips[:4] or [{"label": "Open a document", "intent": "open_document"}]
    return {"result": "clarify", "question_id": uuid.uuid4().hex[:12], "question": "What would you like to do?",
            "chips": chips, "stage": 1}


def route(text: str, target_kind: str | None, history: list | None, brain=None, chip: str | None = None) -> dict:
    if chip is not None:
        if chip not in INTENTS:
            return clarify(target_kind)
        return resolve(chip, target_kind, stage=0)           # a chip names a fixed intent and skips the matcher
    if not isinstance(text, str) or not text.strip() or len(text) > MAX_TEXT:
        return clarify(target_kind)
    r = stage1(text, target_kind)
    if r is not None:
        return r
    if brain is None:
        return clarify(target_kind)
    owner_turns = [h for h in (history or []) if isinstance(h, str)][-4:]
    try:
        got = brain.classify(text.strip(), target_kind=target_kind, history=owner_turns)
    except Exception as e:  # noqa: BLE001 - any Brain failure becomes a clarification, never a guess
        # The reason is kept (code only, no text) so a Brain that never decides can be seen (real-app run r4).
        code = str(getattr(e, "code", "") or "")
        # Codex O2-R6-01: a fixed shape only (an upper-case code), never free text from an exception.
        return {**clarify(target_kind), "brain_outcome": code if re.fullmatch(r"[A-Z][A-Z0-9_]{0,39}", code)
                else "BRAIN_ERROR"}
    intent = got.get("intent") if isinstance(got, dict) else None
    if intent not in INTENTS:
        return {**clarify(target_kind), "brain_outcome": intent if intent == "unclear" else "NOT_AN_INTENT"}
    cap = CAP.get(intent)
    if intent in ACTS_ON_ACTIVE and target_kind and cap is not None and target_kind not in cap["inputs"]:
        return {**clarify(target_kind), "brain_outcome": "KIND_MISMATCH"}
    res = resolve(intent, target_kind, stage=2)
    if res["result"] == "matched":
        extra = [m for m in (got.get("missing") or []) if m in MISSING and m not in res["inputs_needed"]]
        res["inputs_needed"] += extra
    return res
