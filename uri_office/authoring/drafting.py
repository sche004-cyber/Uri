"""OD-2 (plan 16 section 3): deterministic parts of drafting a Word document from an owner's instruction.

* `choose_layout`: the document kind from keywords in the instruction (no Brain). The earliest keyword in the text
  wins, so "write an office order asking staff to report" is an office order, not a report. No keyword -> None (the
  service asks which kind).
* `extract_facts` / `missing_facts`: numbers (digits, and number words such as "twenty five thousand"), dates,
  reference numbers, amounts, capitalised name sequences and one capitalised word after to/from/Shri/Smt/Mr/Mrs/Ms/Dr
  in the instruction. Every one must appear in the draft as a whole token run (FB1 R2-01: "7" is not found inside
  "17"); one that does not is reported by name (FACT_MISSING), never dropped silently. The check is deliberately
  literal: "23rd October" in the instruction and "23 October" in the draft is reported, so the owner looks.
  Not extracted (stated in plan 16): lowercase names, a single name without a cue word, ordinal and fraction words.
"""
from __future__ import annotations

import re

MAX_INSTRUCTION = 2000

# (layout id, pattern). Word boundaries; "order" alone is not an office order.
_KEYWORDS = (
    ("office_order", re.compile(r"\boffice\s+orders?\b", re.I)),
    ("notesheet", re.compile(r"\bnote\s*-?\s*sheets?\b|\bnoting\s+sheets?\b", re.I)),
    ("circular", re.compile(r"\bcirculars?\b", re.I)),
    ("memo", re.compile(r"\bmemo(?:randum|randa|s)?\b|\boffice\s+memorandum\b", re.I)),
    ("minutes", re.compile(r"\bminutes\b", re.I)),
    ("notice", re.compile(r"\bnotices?\b", re.I)),
    ("letter", re.compile(r"\bletters?\b|\bd\.?\s?o\.?\s+letter\b", re.I)),
    ("report", re.compile(r"\breports?\b", re.I)),
)


def choose_layout(instruction: str) -> str | None:
    best = None
    for lid, rx in _KEYWORDS:
        m = rx.search(instruction or "")
        if m and (best is None or m.start() < best[0]):
            best = (m.start(), lid)
    return best[1] if best else None


_MONTHS = ("january|february|march|april|may|june|july|august|september|october|november|december|"
           "jan|feb|mar|apr|jun|jul|aug|sep|sept|oct|nov|dec")
_DATE_WORDS = re.compile(r"\b\d{1,2}(?:st|nd|rd|th)?\s+(?:" + _MONTHS + r")\.?,?\s+\d{4}\b"
                         r"|\b(?:" + _MONTHS + r")\.?\s+\d{1,2}(?:st|nd|rd|th)?,?\s+\d{4}\b", re.I)
_DATE_NUM = re.compile(r"^\d{1,2}[./-]\d{1,2}[./-]\d{2,4}$|^\d{4}-\d{2}-\d{2}$")
_REF = re.compile(r"\b(?:F\.\s?)?No\.\s*([A-Za-z0-9][\w./()-]*\d[\w./()-]*)", re.I)
_AMOUNT_PREFIX = re.compile(r"(?:rs\.?|inr|₹)\s*$", re.I)
_HONORIFIC = r"(?:Shri|Smt|Sh|Km|Kumari|Dr|Mr|Mrs|Ms|Prof)\.?"
_CAP = r"[A-Z][A-Za-z'.-]*"
_NAMES = re.compile(r"\b" + _HONORIFIC + r"\s+" + _CAP + r"(?:\s+" + _CAP + r")*"
                    r"|\b" + _CAP + r"(?:\s+(?:of|and|for|the)\s+" + _CAP + r"|\s+" + _CAP + r")+")
# Words that start a capitalised run without being part of a name (sentence-initial verbs, document words).
_NOT_NAME = {"write", "draft", "prepare", "compose", "please", "kindly", "issue", "make", "create", "send", "the", "a",
             "an", "to", "dear", "subject", "sub", "ref", "no", "no.", "dated", "date", "file", "office", "order",
             "notice", "circular", "memo", "memorandum", "minutes", "report", "letter", "note", "sheet", "notesheet",
             "i", "we", "it", "this", "that", "with", "from", "for", "and", "of", "on", "in", "by", "all", "also",
             "copy", "regarding", "about", "inform", "informing", "asking", "request", "requesting", "pay", "rs",
             "inr", "dt", "w.e.f", "wef", "transfer", "sanction", "ask", "hold", "grant", "appoint", "direct",
             "depute", "relieve", "post", "approve", "forward", "submit", "reply"}
_MONTH_SET = set(_MONTHS.split("|"))
_CUE_NAME = re.compile(r"\b(?:to|from|Shri|Smt|Mr|Mrs|Ms|Dr)\.?\s+([A-Z][A-Za-z'-]+)")
_NUM_WORD = (r"(?:one|two|three|four|five|six|seven|eight|nine|ten|eleven|twelve|thirteen|fourteen|fifteen|sixteen|"
             r"seventeen|eighteen|nineteen|twenty|thirty|forty|fifty|sixty|seventy|eighty|ninety|hundred|thousand|"
             r"lakhs?|crores?)")
_NUM_WORDS = re.compile(r"\b" + _NUM_WORD + r"(?:[\s-]+(?:and\s+)?" + _NUM_WORD + r")*\b", re.I)
_SMALL_NUMS = {"one", "two", "three", "four", "five", "six", "seven", "eight", "nine", "ten"}
_TRAIL = ".,;:)]}'\""
_LEAD = "([{'\""


def _strip(tok: str) -> str:
    return tok.strip(_TRAIL).lstrip(_LEAD).rstrip(_TRAIL)


def extract_facts(instruction: str) -> list:
    """[{kind: date|reference|amount|number|name, text}] in order of appearance, without duplicates."""
    text = instruction or ""
    out, seen, spans = [], set(), []

    def add(kind, value, start=None, end=None):
        value = value.strip()
        if value and value.lower() not in seen:
            seen.add(value.lower())
            out.append({"kind": kind, "text": value, "_at": start if start is not None else len(text)})
        if start is not None:
            spans.append((start, end))

    def taken(a, b):
        return any(a < y and x < b for x, y in spans)

    for m in _DATE_WORDS.finditer(text):
        add("date", m.group(0).rstrip(_TRAIL), m.start(), m.end())
    for m in _REF.finditer(text):
        if not taken(m.start(1), m.end(1)):
            add("reference", _strip(m.group(1)), m.start(1), m.end(1))
    for m in re.finditer(r"\S+", text):
        if taken(m.start(), m.end()) or not re.search(r"\d", m.group(0)):
            continue
        tok = _strip(m.group(0))
        tok = re.sub(r"^(?:rs\.?|inr|₹)", "", tok, flags=re.I)
        if not re.search(r"\d", tok):
            continue
        if _DATE_NUM.match(tok):
            kind = "date"
        elif "/" in tok or re.search(r"[A-Za-z]", tok) and re.search(r"\d", tok) and "-" in tok:
            kind = "reference"
        elif _AMOUNT_PREFIX.search(text[:m.start()]) or "," in tok:
            kind = "amount"
        else:
            kind = "number"
        add(kind, tok, m.start(), m.end())
    for m in _NAMES.finditer(text):
        words = m.group(0).split()
        hon = [i for i, w in enumerate(words) if i > 0 and re.fullmatch(_HONORIFIC, w)]
        if hon:                                   # "Relieve Shri Ram Kumar": the name starts at the honorific
            words = words[hon[0]:]
        while words and (words[0].lower().rstrip(".") in _NOT_NAME or words[0].lower().rstrip(".") in _MONTH_SET):
            words.pop(0)
        while words and (words[-1].lower().rstrip(".") in _NOT_NAME or words[-1].lower().rstrip(".") in _MONTH_SET):
            words.pop()
        honorific = bool(words) and re.fullmatch(_HONORIFIC, words[0]) is not None
        if len(words) >= 2 or (honorific and len(words) >= 2):
            name = " ".join(words).rstrip(_TRAIL)
            if not any(name.lower() in f["text"].lower() or f["text"].lower() in name.lower()
                       for f in out if f["kind"] == "name"):
                add("name", name, m.start())
    # FB1 R2-03: one capitalised word after a cue ("a memo to Ramesh", "from Sharma") is a name too.
    for m in _CUE_NAME.finditer(text):
        w = m.group(1).rstrip(_TRAIL)
        if w.lower().rstrip(".") in _NOT_NAME or w.lower().rstrip(".") in _MONTH_SET or len(w) < 2:
            continue
        if not any(w.lower() in f["text"].lower() for f in out if f["kind"] == "name"):
            add("name", w, m.start(1))
    # FB1 R2-03: numbers written in words ("twenty five thousand"); a lone "one".."ten" is too common to check.
    for m in _NUM_WORDS.finditer(text):
        words = m.group(0).lower().split()
        if len(words) >= 2 or words[0] not in _SMALL_NUMS:
            add("number", m.group(0), m.start(), m.end())
    out.sort(key=lambda f: f["_at"])
    return [{"kind": f["kind"], "text": f["text"]} for f in out]


def _norm(s: str) -> str:
    return " ".join((s or "").split())


def fact_present(fact: str, draft_text: str) -> bool:
    """FB1 R2-01: a fact counts as present only as a whole token run: no letter or digit or '/' directly before or
    after it, and no digit group continuing it ("25,000" is not inside "1,25,000"; "7" is not inside "17"; "Kumar" is
    not inside "Kumari"). Spacing is normalised on both sides; case is ignored (names, month names and number words;
    digits have no case)."""
    t = _norm(fact)
    if not t:
        return True
    rx = re.compile(r"(?<![^\W_])(?<![/])(?<!\d[,.])" + re.escape(t) + r"(?![^\W_])(?![/])(?![,.]\d)",
                    re.I)
    return rx.search(_norm(draft_text)) is not None


def missing_facts(instruction: str, draft_text: str) -> list:
    """Facts from the instruction that the draft does not contain as whole tokens (case and spacing ignored).
    Returns warnings {code: FACT_MISSING, kind, text, message}."""
    out = []
    for f in extract_facts(instruction):
        present = fact_present(f["text"], draft_text)
        if not present:
            out.append({"code": "FACT_MISSING", "kind": f["kind"], "text": f["text"],
                        "message": f"The draft does not contain the {f['kind']} '{f['text']}' from your instruction. "
                                   "Check it before saving."})
    return out
