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
# M39-3 (audit) / R1-B (re-audit): a quoted name is unambiguous even when it
# contains spaces ("my report.py"), and taking it whole is the only way to
# avoid matching just the trailing ".py"/".xlsx" fragment of it. Straight
# ASCII quotes are not the only way people quote a name: Word/macOS/iOS
# auto-correct to curly quotes, and a chat/markdown client may use backticks
# instead. All of these count as quote delimiters, and (as with the original
# straight-quote pattern) a name is accepted even if its open/close markers
# don't match each other -- this module has no way to guess which side is
# "wrong", so it takes the text between whichever two quote-class characters
# bound it.
_QUOTE_CHARS = "\"'“”‘’`"
_QUOTE_CLASS = "[" + re.escape(_QUOTE_CHARS) + "]"
_NOT_QUOTE_CLASS = "[^" + re.escape(_QUOTE_CHARS) + "]"
_PY_QUOTED = re.compile(_QUOTE_CLASS + r"(" + _NOT_QUOTE_CLASS + r"{1,260}\.py)" + _QUOTE_CLASS, re.IGNORECASE)
_XLSX_QUOTED = re.compile(_QUOTE_CLASS + r"(" + _NOT_QUOTE_CLASS + r"{1,260}\.(?:xlsm|xlsx))" + _QUOTE_CLASS, re.IGNORECASE)
_SCRIPT_PHRASE = re.compile(r"\b(?:this|the|my)\s+(?:[a-z]+\s+){0,2}?script\b", re.IGNORECASE)
_WORKBOOK_PHRASE = re.compile(r"\b(?:this|the|my)\s+(?:[a-z]+\s+){0,2}?(?:spreadsheet|workbook|sheet)\b", re.IGNORECASE)
# A character that continues a filename-like token: if it sits immediately
# before/after an unquoted match, the match is only part of a longer token
# ("report.py" inside "report.py.bak") and must not be silently accepted.
# R1-D (re-audit, regression): a sentence-final "." (or "...") is punctuation,
# not a continuation of the filename -- "make report.py work with sales.xlsx."
# and "Please fix report.py. It should work with sales.xlsx" must still parse.
# It is a continuation only when something that could extend the token (not
# whitespace/end-of-text) follows the run of dots, e.g. "report.py.bak".
# R1-B (re-audit): an unquoted filename immediately preceded by a single word
# that isn't one of this request grammar's own function words could just as
# well be part of the filename itself ("my report.py" is a real file, not
# necessarily "report.py" possessed by "my"). Without seeing the real files,
# this module cannot tell the two apart, so it refuses rather than guesses;
# only quoting (any of the recognised quote characters) or one of these safe
# words disambiguates it.
_SAFE_PRECEDING_WORDS = frozenset({
    "make", "get", "fix", "have", "with", "the", "a", "an", "this", "that",
    "or", "and", "to", "in", "on", "from", "file", "script", "spreadsheet",
    "workbook", "sheet",
})

_MAX_LEN = 2000


@dataclass(frozen=True)
class ParsedRequest:
    ok: bool
    reason: str | None = None      # REASON_* when not ok
    role: str | None = None        # which role had the problem, for ROLE_MISSING/ROLE_AMBIGUOUS
    spans: dict | None = None      # {"script": (a, b), "workbook": (a, b)} when ok


def _spans_of(pattern, text):
    return [(m.start(), m.end()) for m in pattern.finditer(text)]


def _group_spans(pattern, text):
    return [(m.start(1), m.end(1)) for m in pattern.finditer(text)]


# Re-audit R2-3 (repair round 3): which characters end a token. Anything
# else touching an unquoted match (a digit, CJK, "\\", "~", ":" inside a
# drive letter, ...) could be part of a longer real filename, so the match is
# refused as ambiguous rather than bound as the bare name. This replaces the
# earlier ASCII-only allowlist (`[\\w./\\-]` continuations, ASCII-letter
# preceding words), which let "Q1 sales.xlsx", "2024 report.py",
# "C:\\old\\report.py", "../report.py" and "sales.xlsx~" bind the bare name.
_OPENERS = "(\"'\u201c\u201d\u2018\u2019`[{"
_CLOSERS = ",;:!?)]}\"'\u201c\u201d\u2018\u2019`"


def _trailing_continuation(text, b):
    """True iff the text right after an unquoted match still continues the
    same token. A run of one or more "." right at the match's end is only a
    continuation when something token-like follows it once the dots are
    skipped (report.py.bak); a "." (or "...") followed by whitespace or the
    end of the text is ordinary sentence punctuation (R1-D). Otherwise any
    character that is not whitespace or closing punctuation continues the
    token (R2-3: "sales.xlsx~")."""
    j = b
    while text[j:j + 1] == ".":
        j += 1
    tail = text[j:j + 1]
    if not tail or tail.isspace() or tail in _CLOSERS:
        return False
    return not (j > b and tail == ".")


def _leading_continuation(text, a):
    """True iff the text right before an unquoted match still continues the
    same token: anything but whitespace or an opening quote/bracket (R2-3:
    "\\", ":", "..", a digit, CJK). A leading "./" that itself starts a token
    is a normal, unambiguous way to name a file in the current folder (R1-D);
    "../" is not -- it names a file somewhere else."""
    if a <= 0:
        return False
    before = text[a - 1]
    if before.isspace() or before in _OPENERS:
        return False
    if before == "/" and a >= 2 and text[a - 2] == ".":
        start = a - 2
        return not (start == 0 or text[start - 1].isspace() or text[start - 1] in _OPENERS)
    return True


def _strict_substring(text, a, b):
    return _trailing_continuation(text, b) or _leading_continuation(text, a)


def _unquoted_prefix_ambiguous(text, a):
    """R1-B / R2-3: an unquoted filename preceded (across whitespace only) by
    a token that is not one of this grammar's own safe function words is
    ambiguous: the token could be part of the real filename ("my report.py",
    "Q1 sales.xlsx", "2024 report.py", "报告 report.py"). A token ending in
    clause punctuation ("this:", "else,") is a separate clause, not part of a
    name."""
    m = re.search(r"(\S+)\s+$", text[:a])
    if not m:
        return False
    token = m.group(1)
    if token[-1] in ",;:.!?)]}":
        return False
    return token.lstrip(_OPENERS).casefold() not in _SAFE_PRECEDING_WORDS


def _filename_spans(quoted_pattern, plain_pattern, text):
    """Quoted names (inner text, spaces and all) are taken as-is. An unquoted
    match that is a strict substring of a longer token -- not covered by a
    quote -- is a refusal (`bad=True`), never a silent partial match (M39-3).
    So is an unquoted match with an unsafe preceding word (R1-B): never a
    silent guess at which part of the text is the filename.
    """
    quoted_spans = _group_spans(quoted_pattern, text)
    quoted_ranges = [(m.start(), m.end()) for m in quoted_pattern.finditer(text)]
    bad = False
    plain = []
    for a, b in _spans_of(plain_pattern, text):
        if any(qa <= a and b <= qb for qa, qb in quoted_ranges):
            continue  # already covered by the quoted match
        if _strict_substring(text, a, b) or _unquoted_prefix_ambiguous(text, a):
            bad = True
            continue
        plain.append((a, b))
    return quoted_spans + plain, bad


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

    py_names, py_bad = _filename_spans(_PY_QUOTED, _PY, raw_text)
    if py_bad:
        return ParsedRequest(False, REASON_ROLE_AMBIGUOUS, "script")
    py_unique = {raw_text[a:b].strip().casefold() for a, b in py_names}
    if len(py_unique) > 1:
        return ParsedRequest(False, REASON_ROLE_AMBIGUOUS, "script")
    script_phrases = _spans_of(_SCRIPT_PHRASE, raw_text)

    xl_names, xl_bad = _filename_spans(_XLSX_QUOTED, _XLSX, raw_text)
    if xl_bad:
        return ParsedRequest(False, REASON_ROLE_AMBIGUOUS, "workbook")
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
