"""Deterministic request parser for one task family (M39 §4.2 request.py).

Recognizes the intent ("make/get/fix ... work/run with ...") and extracts two
role spans: filename tokens (`*.py` -> script; `*.xlsx`/`*.xlsm` -> workbook),
role phrases ("this/the script", "this/the spreadsheet/workbook/sheet", "the
sales script"). Negated requests are handled downstream by the binding layer
(uri_v1/memory/uri_adapter/envelope.py `ground`, M36 audit F-1): the whole
trusted turn is checked there, so a request that only excludes one candidate
file ("don't use old_report.py, use new_report.py") still extracts spans here
and is refused at binding time instead of being guessed away here.

No model call. Unsupported intent, a missing role, or more than one candidate
reference for a role never guesses: it returns a typed reason instead.
"""
from __future__ import annotations

from dataclasses import dataclass
import re

REASON_UNSUPPORTED = "UNSUPPORTED_REQUEST"
REASON_ROLE_MISSING = "ROLE_MISSING"
REASON_ROLE_AMBIGUOUS = "ROLE_AMBIGUOUS"

ROLES = ("script", "workbook")

# "make/get/fix/have <script> [to] work/run with <workbook>", in either order,
# within a short bounded window (filenames may contain '.', so the gap is
# bounded by length, not by excluding punctuation).
_INTENT = re.compile(
    r"\b(?:make|get|fix|have)\b.{0,80}?\b(?:work|works|working|run|runs|running)\b.{0,20}?\bwith\b",
    re.IGNORECASE | re.DOTALL,
)

_PY = re.compile(r"\b[\w][\w\-./]*\.py\b", re.IGNORECASE)
_XLSX = re.compile(r"\b[\w][\w\-./]*\.xlsm\b|\b[\w][\w\-./]*\.xlsx\b", re.IGNORECASE)
_SCRIPT_PHRASE = re.compile(r"\b(?:this|the|my)\s+(?:[a-z]+\s+){0,2}?script\b", re.IGNORECASE)
_WORKBOOK_PHRASE = re.compile(r"\b(?:this|the|my)\s+(?:[a-z]+\s+){0,2}?(?:spreadsheet|workbook|sheet)\b", re.IGNORECASE)

_MAX_LEN = 2000


@dataclass(frozen=True)
class ParsedRequest:
    ok: bool
    reason: str | None = None      # REASON_* when not ok
    role: str | None = None        # which role had the problem, for ROLE_MISSING/ROLE_AMBIGUOUS
    spans: dict | None = None      # {"script": (a, b), "workbook": (a, b)} when ok


def _spans_of(pattern, text):
    return [(m.start(), m.end()) for m in pattern.finditer(text)]


def _pick(names, phrases):
    """Prefer an unambiguous filename literal; fall back to a role phrase.

    Returns (span, problem) where problem is None, "MISSING" or "AMBIGUOUS".
    Multiple mentions of the *same* filename are not an ambiguity (audit-style
    conservatism: never invent a choice between two mentions of one file).
    """
    if len(names) >= 1:
        first = names[0]
        return (first, None)
    if len(phrases) > 1:
        return (None, "AMBIGUOUS")
    if len(phrases) == 1:
        return (phrases[0], None)
    return (None, "MISSING")


def parse(raw_text: str) -> ParsedRequest:
    if not isinstance(raw_text, str) or not raw_text or len(raw_text) > _MAX_LEN:
        return ParsedRequest(False, REASON_UNSUPPORTED)
    if not _INTENT.search(raw_text):
        return ParsedRequest(False, REASON_UNSUPPORTED)

    py_names = _spans_of(_PY, raw_text)
    py_unique = {raw_text[a:b].strip().casefold() for a, b in py_names}
    if len(py_unique) > 1:
        return ParsedRequest(False, REASON_ROLE_AMBIGUOUS, "script")
    script_phrases = _spans_of(_SCRIPT_PHRASE, raw_text)

    xl_names = _spans_of(_XLSX, raw_text)
    xl_unique = {raw_text[a:b].strip().casefold() for a, b in xl_names}
    if len(xl_unique) > 1:
        return ParsedRequest(False, REASON_ROLE_AMBIGUOUS, "workbook")
    workbook_phrases = _spans_of(_WORKBOOK_PHRASE, raw_text)

    script_span, script_problem = _pick(py_names, script_phrases)
    if script_problem == "AMBIGUOUS":
        return ParsedRequest(False, REASON_ROLE_AMBIGUOUS, "script")
    if script_problem == "MISSING":
        return ParsedRequest(False, REASON_ROLE_MISSING, "script")

    workbook_span, workbook_problem = _pick(xl_names, workbook_phrases)
    if workbook_problem == "AMBIGUOUS":
        return ParsedRequest(False, REASON_ROLE_AMBIGUOUS, "workbook")
    if workbook_problem == "MISSING":
        return ParsedRequest(False, REASON_ROLE_MISSING, "workbook")

    if script_span == workbook_span:
        # A single span cannot serve both roles (e.g. "the file" matched both
        # generic phrase patterns some other way); refuse rather than guess.
        return ParsedRequest(False, REASON_ROLE_AMBIGUOUS, "workbook")

    return ParsedRequest(True, spans={"script": script_span, "workbook": workbook_span})
