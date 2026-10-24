"""OD-2 (plan 16 section 3): deterministic parts of drafting a Word document from an owner's instruction.

* `choose_layout`: the document kind from keywords in the instruction (no Brain). The earliest keyword in the text
  wins, so "write an office order asking staff to report" is an office order, not a report. No keyword -> None (the
  service asks which kind).
* `extract_facts` / `missing_facts`: the facts of an instruction and the ones a draft does not contain.

FB4 (plan 16): the extractor is one pipeline. Each stage claims character spans in the instruction, and later stages
never use a claimed span:
  1. references: the designator and the code together ("F.No. A-12/2026-Estt.", "O.M. No. ...", "D.O. No. ...",
     "No. ..."); the fact is the code;
  2. dates: day ranges in one month, "Nth (day) of Month", day and month, or month and day (with or without a
     year), month-to-month periods and "Month YYYY" (FB5 R6-01), standalone months including office periods,
     or a relative month such as "next April".
     "may" remains excluded as a modal; capitalised "May" is also recognised in period wording while
     question and subject forms stay excluded from the bare-month fallback;
  3. numbers in digits, with a following unit (days, km, posts, lakh, AM/PM, ... see UNITS) as part of the fact; an
     amount after Rs/INR/the rupee sign; "/-" is dropped;
  4. numbers in words ("twenty five thousand");
  5. names: runs of capitalised words, broken by punctuation, claimed spans and sentence ends, then split at every
     honorific so "Shri Ram Kumar and Smt. Sita Devi" is two names, each keeping its honorific;
  6. one capitalised word after a cue ("to Ramesh", "Smt. Sharma") outside every claimed span;
  7. a full name after an explicit person label or a letter recipient cue, including lowercase names
     ("staff member ramesh kumar", "letter to ramesh kumar").
Names are deduplicated only on exact repeats; a name's occurrence inside a longer name of the same instruction does
not count in the draft (FB5 R6-02).
A fact counts as present in a draft only as a whole token run (FB1 R2-01). The check is literal on purpose; plan 16
lists what it does not catch.
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


# ---- vocabulary ------------------------------------------------------------------------------------------------------
_MONTHS = ("january|february|march|april|may|june|july|august|september|october|november|december|"
           "jan|feb|mar|apr|jun|jul|aug|sep|sept|oct|nov|dec")
_MONTH_SET = set(_MONTHS.split("|"))
_ORD = r"(?:st|nd|rd|th)"
_YEAR = r"(?:,?\s+\d{4}\b)"
_DAY_MONTH = re.compile(r"\b(\d{1,2})(" + _ORD + r")?\s+(" + _MONTHS + r")\b\.?(" + _YEAR + r")?", re.I)
_MONTH_DAY = re.compile(r"\b(" + _MONTHS + r")\b\.?\s+(\d{1,2})(" + _ORD + r")?\b(" + _YEAR + r")?", re.I)
# FB5 R6-01: "the 5th of June, 2026", "12th day of March 2026", "April 2026", "April, 2026 to March, 2027" and
# "April to June 2026" are dates too.
_DAY_OF_MONTH = re.compile(r"\b(\d{1,2})(" + _ORD + r")?\s+(?:day\s+)?of\s+(" + _MONTHS + r")\b\.?(" + _YEAR + r")?",
                           re.I)
# A range of days in one month ("9th-10th November", "3rd to 7th October 2026", "8 and 9 October 2026") is one fact.
# FB7 (found with the FB5 probes): "5-May-2026", "06/Jun/2026", "5.Nov.26" are one date each.
_DASH_DATE = re.compile(r"\b(\d{1,2})[-/.](" + _MONTHS + r")\.?[-/.](\d{2}|\d{4})\b", re.I)
_DAY_RANGE = re.compile(r"\b(\d{1,2})(" + _ORD + r")?\s*(?:-|–|to|and|&)\s*(\d{1,2})(" + _ORD + r")?\s+(" + _MONTHS
                        + r")\b\.?(" + _YEAR + r")?", re.I)
_MONTH_YEAR = re.compile(r"\b(" + _MONTHS + r")\b\.?,?\s+(\d{4})\b", re.I)
_PERIOD = re.compile(r"\b(" + _MONTHS + r")\b\.?\s+(?:to|till|until|through|-|–)\s+(" + _MONTHS + r")\b\.?(" + _YEAR + r")?",
                     re.I)
_MAY_CUE = re.compile(r"\b(?:on|by|from|till|until|dated|before|after|of)\s+$", re.I)
_STANDALONE_MONTH = re.compile(r"\b(?:in|during|by|before|after|throughout|for|of|from|until|till|on)\s+"
                               r"(?:the\s+month\s+of\s+)?(" + _MONTHS + r")\b", re.I)
_BARE_MONTH = re.compile(r"\b(" + _MONTHS + r")\b", re.I)
_MAY_AS_PERIOD = re.compile(r"\b(?:the|this|next|last)\s+$", re.I)
_MAY_MODAL_FOLLOW = re.compile(r"\s*(?:\d+\b|I\b|we\b|you\b|he\b|she\b|it\b|they\b)", re.I)
_RELATIVE_MONTH = re.compile(r"\b(?:next|this|last)\s+(" + _MONTHS + r")\b", re.I)
_DATE_NUM = re.compile(r"^\d{1,2}[./-]\d{1,2}[./-]\d{2,4}$|^\d{4}-\d{2}-\d{2}$")
# FB4 R5-04: the designator is part of the claimed span, so it never becomes a name word.
_REF = re.compile(r"\b(?:F\.\s?No\.?|O\.\s?M\.\s?No\.?|D\.\s?O\.\s?No\.?|No\.)\s*([A-Za-z0-9][\w./()-]*\d[\w./()-]*)",
                  re.I)
_AMOUNT_PREFIX = re.compile(r"(?:rs\.?|inr|₹)\s*$", re.I)
# FB4 R5-01: Kum, Km, Kumari and Sushri are honorifics too.
HONORIFICS = ("Shri", "Smt", "Sh", "Km", "Kum", "Kumari", "Sushri", "Dr", "Mr", "Mrs", "Ms", "Prof")
_HONORIFIC = r"(?:" + "|".join(HONORIFICS) + r")\.?"
_HON_RX = re.compile(_HONORIFIC + r"$")
_CUE_NAME = re.compile(r"\b(?:to|from|" + "|".join(HONORIFICS) + r")\.?\s+([A-Z][A-Za-z'-]+)")
# An explicit person label lets a lowercase full name be checked without treating arbitrary lowercase prose as names.
# Stop at a clause or prepositional phrase, rather than treating its words as a third/fourth name part.
_PERSON_CLAUSE_START = (r"(?:is|was|will|shall|has|had|who|and|the|a|an|be|can|may|must|should|would|could|"
                        r"about|after|against|as|at|before|by|concerning|during|for|from|in|into|of|on|over|"
                        r"regarding|through|to|under|with|without)")
_PERSON_NAME_WORD = r"(?!(?:" + _PERSON_CLAUSE_START + r")\b)[A-Za-z][A-Za-z'-]+"
_PERSON_NAME = re.compile(r"\b(?:staff\s+member|employee\s+named|officer\s+named|person\s+named)\s+("
                          + _PERSON_NAME_WORD + r"(?:\s+" + _PERSON_NAME_WORD + r"){1,3})"
                          + r"(?=\s*(?:[.,;:(]|$|\b" + _PERSON_CLAUSE_START + r"\b))",
                          re.I)
# FB6 R2-02: an honorific followed by a lowercase full name ("Shri ramesh kumar", "Smt. anita sharma").
# FB9 R2-02: the name may also end at a newline (a "To" block or a heading), and may have up to four words.
_HON_LOWER_NAME = re.compile(r"\b(" + _HONORIFIC + r")[ \t]+([a-z][a-z'-]+(?:[ \t]+(?!(?:" + _PERSON_CLAUSE_START
                             + r")\b)[a-z][a-z'-]+){0,3})(?=[ \t]*(?:\n|[.,;:()]|$)|\s+" + _PERSON_CLAUSE_START
                             + r"\b)")
# FB6 R2-03: "of" is a name cue ("the transfer of Ramesh", "the deputation of Anjali"), except after a designation or
# an institution ("the collector of Pune", "the director of Kolkata office"), where the next word is a place or a
# body, not a person. Multi-word capitalised names ("Ministry of Finance", "Government of India", "Shri Ram Kumar")
# are claimed by the name stage first, so this cue only reads a single capitalised word.
_OF_NOT_AFTER = {
    "collector", "collectors", "director", "directors", "secretary", "secretaries", "commissioner", "commissioners",
    "ministry", "ministries", "government", "governments", "department", "departments", "office", "offices",
    "state", "states", "university", "bank", "district", "districts", "city", "board", "member", "members",
    "chairman", "chairperson", "head", "heads", "officer", "officers", "inspector", "registrar", "controller",
    "superintendent", "principal", "president", "minister", "governor", "mayor", "municipality", "corporation",
    "council", "court", "college", "school", "institute", "directorate", "division", "section", "branch", "unit",
    "zone", "region", "circle", "village", "town", "block", "tehsil", "taluka", "province", "people", "citizens",
    "residents", "rest", "part", "parts", "copy", "copies", "annexure", "chapter", "rule", "rules", "act", "article",
    "clause", "schedule", "list", "map", "government", "state", "union", "capital", "outskirts", "city", "port",
    "airport", "station", "embassy", "consulate", "mission", "high", "republic", "bureau", "agency", "authority",
    "registrar", "magistrate", "judge", "police", "ambassador", "consul", "chief", "deputy", "joint", "additional",
    "under", "assistant", "kingdom", "name", "tehsildar", "tahsildar", "sdm", "bdo", "sho", "talathi",
    "patwari", "collectorate"}
_OF_CUE_NAME = re.compile(r"\b([A-Za-z-]+)\s+of\s+([A-Z][a-z][A-Za-z'-]*)\b(?!\s+[A-Z])")
_LETTER_RECIPIENT = re.compile(r"\bletters?\s+to\s+(" + _PERSON_NAME_WORD
                               + r"(?:\s+" + _PERSON_NAME_WORD + r"){1,3})"
                               + r"(?=\s*(?:[.,;:]|$|\b" + _PERSON_CLAUSE_START + r"\b))", re.I)
# A lone capitalised appointee is a person when the appointment verb and "as" bound the name,
# including when a comma-delimited designation intervenes.
_SINGLE_APPOINTEE = re.compile(r"\b(?i:appoint(?:ing|ed|s)?)\s+([A-Z][a-z][A-Za-z'-]*)"
                                 r"(?:\s+|,\s+[A-Z][A-Za-z'-]*(?:\s+[A-Z][A-Za-z'-]*)+,\s*)as\b")
_CONNECTORS = {"of", "and", "for", "the"}
# Words that start or end a capitalised run without being part of a name (verbs, document words, designators).
_NOT_NAME = {"write", "draft", "prepare", "compose", "please", "kindly", "issue", "make", "create", "send", "the", "a",
             "an", "to", "dear", "subject", "sub", "ref", "refer", "reference", "no", "dated", "date", "file",
             "office", "order", "notice", "circular", "memo", "memorandum", "minutes", "report", "letter", "note",
             "sheet", "notesheet", "i", "we", "it", "this", "that", "with", "from", "for", "and", "of", "on", "in",
             "by", "all", "also", "copy", "regarding", "about", "inform", "informing", "asking", "request",
             "requesting", "pay", "rs", "inr", "dt", "w.e.f", "wef", "transfer", "sanction", "ask", "hold", "grant",
             "appoint", "direct", "depute", "relieve", "post", "approve", "forward", "submit", "reply", "under",
             "f.no", "o.m", "d.o", "put", "up", "meeting", "rupees", "only", "training", "purchase", "notify",
             "fill", "allot", "budget", "fine", "sanctioning", "granting", "relieving", "transferring", "on",
             "monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"}
_NUM_WORD = (r"(?:one|two|three|four|five|six|seven|eight|nine|ten|eleven|twelve|thirteen|fourteen|fifteen|sixteen|"
             r"seventeen|eighteen|nineteen|twenty|thirty|forty|fifty|sixty|seventy|eighty|ninety|hundred|thousand|"
             r"lakhs?|crores?)")
_NUM_WORD_RX = re.compile(_NUM_WORD + r"$", re.I)
_NUM_WORDS = re.compile(r"\b" + _NUM_WORD + r"(?:[\s-]+(?:and\s+)?" + _NUM_WORD + r")*\b", re.I)
_SMALL_NUMS = {"one", "two", "three", "four", "five", "six", "seven", "eight", "nine", "ten"}
# "3 (three) posts": a number repeated in words in brackets is read as the number alone (instruction and draft).
_BRACKET_WORDS = re.compile(r"\s*\((?:" + _NUM_WORD + r")(?:[\s-]+(?:and\s+)?" + _NUM_WORD + r")*\)", re.I)
# FB2 R3-02 / FB3 R4-04: the unit after a number is part of the fact. Plan 16 lists exactly these.
UNITS = ("lakh", "crore", "thousand", "hundred", "day", "week", "month", "year", "hour", "hrs", "minute", "per cent",
         "percent", "am", "pm", "a.m.", "p.m.", "km", "kg", "metre", "meter", "kilometre", "kilometer", "kilogram",
         "litre", "liter", "post", "vacancy", "copy", "page", "person", "member", "officer", "employee", "set",
         "unit", "seat", "file", "room", "nos")
_UNIT = re.compile(r"^\s+(a\.m\.|p\.m\.|lakhs?|crores?|thousand|hundred|days?|weeks?|months?|years?|hours?|hrs?|"
                   r"minutes?|per\s?cent|percent|am|pm|kms?|kgs?|kilo(?:metre|meter|gram)s?|metres?|meters?|"
                   r"litres?|liters?|posts?|vacanc(?:y|ies)|cop(?:y|ies)|pages?|persons?|members?|officers?|"
                   r"employees?|sets?|units?|seats?|files?|rooms?|nos\.?)(?![\w])", re.I)
_TRAIL = ".,;:)]}'\""
_LEAD = "([{'\""


def _strip(tok: str) -> str:
    return tok.lstrip(_LEAD).rstrip(_TRAIL)


def _code(tok: str) -> str:
    """A reference code without trailing punctuation, keeping a closing bracket that closes one in the code."""
    t = tok.rstrip(".,;:'\"")
    while t.endswith(")") and t.count(")") > t.count("("):
        t = t[:-1].rstrip(".,;:")
    return t


def _clean(text: str) -> str:
    return _BRACKET_WORDS.sub("", text or "")


# ---- extraction ------------------------------------------------------------------------------------------------------
def extract_facts(instruction: str) -> list:
    """[{kind: date|reference|amount|number|name, text}] in order of appearance, without duplicates."""
    text = _clean(instruction)
    out, seen, spans = [], set(), []

    def add(kind, value, start, end=None):
        value = value.strip()
        if value and value.lower() not in seen:
            seen.add(value.lower())
            out.append({"kind": kind, "text": value, "_at": start})
        if end is not None:
            spans.append((start, end))

    def taken(a, b):
        return any(a < y and x < b for x, y in spans)

    # 1. references, designator included in the claimed span
    for m in _REF.finditer(text):
        code = _code(m.group(1))
        add("reference", code, m.start(), m.start(1) + len(code))
        spans.append((m.start(), m.start(1) + len(code)))
    # 2. dates. FB5 R6-01: "Nth (day) of Month" first, then day-month and month-day, then "Month YYYY" and
    # month-to-month periods, all before the digit stage so their numbers are not read as plain numbers.
    for m in _DASH_DATE.finditer(text):
        if not taken(m.start(), m.end()) and 1 <= int(m.group(1)) <= 31:
            add("date", m.group(0), m.start(), m.end())
    for m in _DAY_RANGE.finditer(text):
        if taken(m.start(), m.end()) or not (1 <= int(m.group(1)) <= 31 and 1 <= int(m.group(3)) <= 31):
            continue
        mon = m.group(5)
        if mon.lower() == "may" and not (m.group(4) or m.group(6) or mon in ("May", "MAY")) \
                and not _MAY_CUE.search(text[:m.start()]):
            continue
        add("date", m.group(0).rstrip(".,;:"), m.start(), m.end())
    for m in _DAY_OF_MONTH.finditer(text):
        if not taken(m.start(), m.end()) and 1 <= int(m.group(1)) <= 31:
            add("date", m.group(0).rstrip(".,;:"), m.start(), m.end())
    for rx, day_i, ord_i, mon_i, year_i in ((_DAY_MONTH, 1, 2, 3, 4), (_MONTH_DAY, 2, 3, 1, 4)):
        for m in rx.finditer(text):
            if taken(m.start(), m.end()) or not 1 <= int(m.group(day_i)) <= 31:
                continue
            # "may": a month with an ordinal day, a year or a preposition before it; after a day also when written
            # "May"/"MAY". Not "aged 55 may apply", "you may 3 times" or "May 3 officers be deputed?".
            mon = m.group(mon_i)
            if mon.lower() == "may" and not (m.group(ord_i) or m.group(year_i)) \
                    and not _MAY_CUE.search(text[:m.start()]) and not (rx is _DAY_MONTH and mon in ("May", "MAY")):
                continue
            add("date", m.group(0).rstrip(".,;:"), m.start(), m.end())
    for m in _PERIOD.finditer(text):
        if taken(m.start(), m.end()):
            continue
        if "may" in (m.group(1).lower(), m.group(2).lower()) and not (m.group(3) or _MAY_CUE.search(text[:m.start()])
                or "May" in (m.group(1), m.group(2)) or "MAY" in (m.group(1), m.group(2))):
            continue                              # "you may to June" is not a period; "from May to June" is
        add("date", m.group(0).rstrip(".,;:"), m.start(), m.end())
    for m in _MONTH_YEAR.finditer(text):           # a following year satisfies the "may" rule
        if not taken(m.start(), m.end()):
            add("date", m.group(0).rstrip(".,;:"), m.start(), m.end())
    for m in _RELATIVE_MONTH.finditer(text):
        mon = m.group(1)
        if not taken(m.start(), m.end()) and (mon.lower() != "may" or mon in ("May", "MAY")):
            add("date", m.group(0), m.start(), m.end())
    for m in _STANDALONE_MONTH.finditer(text):
        mon = m.group(1)
        if not taken(m.start(1), m.end(1)) and (mon.lower() != "may" or mon in ("May", "MAY")):
            add("date", mon, m.start(1), m.end(1))
    # A month can name an office period without a time preposition ("June roster", "October duty chart").
    # Bare "may" is also a modal verb: keep lowercase may and question/subject forms out of this fallback.
    for m in _BARE_MONTH.finditer(text):
        mon = m.group(1)
        if taken(m.start(), m.end()):
            continue
        if mon.lower() == "may":
            if mon not in ("May", "MAY"):
                continue
            if not _MAY_AS_PERIOD.search(text[:m.start()]):
                after = text[m.end():]
                if _MAY_MODAL_FOLLOW.match(after) or "?" in re.split(r"[.!]", after, maxsplit=1)[0]:
                    continue
        add("date", mon, m.start(), m.end())
    # 3. numbers in digits (amounts, numbers with units, numeric dates, codes without a designator)
    for m in re.finditer(r"\S+", text):
        if taken(m.start(), m.end()) or not re.search(r"\d", m.group(0)):
            continue
        tok = _strip(m.group(0))
        tok = re.sub(r"^(?:rs\.?|inr|₹)", "", tok, flags=re.I)
        if tok.endswith("/-"):
            tok = tok[:-2]
        if not re.search(r"\d", tok):
            continue
        if _DATE_NUM.match(tok):
            kind = "date"
        elif re.fullmatch(r"(?i)\d+-(?:day|week|month|year|hour)s?", tok):       # "5-day workshop"
            kind = "number"
        elif "/" in tok or (re.search(r"[A-Za-z]", tok) and "-" in tok):
            kind = "reference"
        elif _AMOUNT_PREFIX.search(text[:m.start()]) or re.match(r"(?i)(?:rs\.?|inr|₹)\d", m.group(0)) \
                or "," in tok:
            kind = "amount"
        else:
            kind = "number"
        end = m.end()
        if kind in ("number", "amount") and not m.group(0).rstrip("/-").endswith(tuple(",;:)")):
            u = _UNIT.match(text[end:])
            if u:
                tok, end = f"{tok} {u.group(1)}", end + u.end()
        add(kind, tok, m.start(), end)
    # 4. numbers in words; a lone "one".."ten" is too common to check
    for m in _NUM_WORDS.finditer(text):
        if taken(m.start(), m.end()):
            continue
        words = m.group(0).lower().split()
        u = _UNIT.match(text[m.end():])
        unit = u if u and not _NUM_WORD_RX.match(u.group(1)) else None
        # FB5 R6-03: a lone "one".."ten" is a fact when a unit follows it ("seven days", "two officers")
        if len(words) >= 2 or words[0] not in _SMALL_NUMS or unit:
            value, end = m.group(0), m.end()
            if unit:
                value, end = f"{value} {unit.group(1)}", end + unit.end()
            add("number", value, m.start(), end)
        else:
            spans.append((m.start(), m.end()))
    # 5a. an honorific with a lowercase full name (FB6 R2-02), claimed before the capitalised runs so a heading
    # "Pension of Shri ramesh kumar sharma" does not lend "Shri" to the run "Pension of Shri" (FB9 R2-02)
    for m in _HON_LOWER_NAME.finditer(text):
        if not taken(m.start(), m.end()) and m.group(2).split()[0] not in _NOT_NAME:
            add("name", m.group(0).rstrip(".,;:"), m.start(), m.end())
    # 5. Claim explicitly labelled people before looking at capitalised runs. A title-cased
    # designation after a person can otherwise be mistaken for a second person's name.
    person_spans = []
    for m in _PERSON_NAME.finditer(text):
        if not taken(m.start(1), m.end(1)):
            add("name", m.group(1), m.start(1), m.end(1))
            person_spans.append((m.start(1), m.end(1), True))
    for m in _SINGLE_APPOINTEE.finditer(text):
        if not taken(m.start(1), m.end(1)) and m.group(1).lower() not in _NOT_NAME:
            add("name", m.group(1), m.start(1), m.end(1))
            person_spans.append((m.start(1), m.end(1), True))

    runs = _cap_runs(text, taken)
    parts = [part for start, words in runs for _, part in _split_at_honorifics(start, words)]
    for part in parts:
        name = _trim(part)
        if len(name) >= 2 and any(not _is_hon(w) and w.lower().rstrip(".") not in _NOT_NAME for _, w in name):
            person_spans.append((name[0][0], name[-1][0] + len(name[-1][1]), _is_hon(name[0][1])))
    designation_spans = []
    for part in parts:
        name = _trim(part)
        if not name or _is_hon(name[0][1]):
            continue
        start, end = name[0][0], name[-1][0] + len(name[-1][1])
        if any(re.fullmatch(r"\s+as\s+(?:the\s+)?", text[person_end:start], re.I)
                or (confident_person and re.fullmatch(r",\s+", text[person_end:start])
                    and (text[end:].startswith(",") or re.match(r"\s+as\b", text[end:], re.I)))
                or (confident_person and re.fullmatch(r"\s*\(\s*", text[person_end:start])
                    and re.match(r"\s*\)", text[end:]))
               for _, person_end, confident_person in person_spans if person_end < start):
            designation_spans.append((start, end))
    spans.extend(designation_spans)

    for start, words in runs:
        for part_start, part in _split_at_honorifics(start, words):
            if taken(part[0][0], part[-1][0] + len(part[-1][1])):
                continue
            name = _trim(part)
            # FB5 R6-04: a name needs a word that is not an honorific or a designator ("Dr", "Room" alone are not)
            if len(name) >= 2 and any(not _is_hon(w) and w.lower().rstrip(".") not in _NOT_NAME for _, w in name):
                value = re.sub(r"['’]s$", "", " ".join(w for _, w in name).rstrip(".,;:"))   # "Natarajan's"
                # FB5 R6-02: only an exact repeat is a duplicate ("Shri Anil Kumar" next to "Shri Anil Kumar
                # Singh" is a second person)
                add("name", value, name[0][0], name[-1][0] + len(name[-1][1]))
    # 6. one capitalised word after a cue
    cues = list(_CUE_NAME.finditer(text))
    cues += [m for m in _OF_CUE_NAME.finditer(text) if m.group(1).lower() not in _OF_NOT_AFTER]
    for m in sorted(cues, key=lambda x: x.start()):
        g = m.lastindex                       # the name word is the last group of either pattern
        w = m.group(g).rstrip(_TRAIL)
        # FB5 R6-02: only a word inside a claimed span (a name, date, number or reference) is skipped.
        # FB6 R2-02: an honorific alone ("to Shri ramesh") is never a name.
        if taken(m.start(g), m.end(g)) or w.lower() in _NOT_NAME or w.lower() in _MONTH_SET or len(w) < 2 \
                or _is_hon(w):
            continue
        add("name", w, m.start(g), m.end(g))
    for m in _LETTER_RECIPIENT.finditer(text):
        # "letter to request transfer" is a purpose, not a recipient.
        if not taken(m.start(1), m.end(1)) and m.group(1).split()[0].lower() not in _NOT_NAME:
            add("name", m.group(1), m.start(1), m.end(1))
    out.sort(key=lambda f: f["_at"])
    return [{"kind": f["kind"], "text": f["text"]} for f in out]


# A bracketed honorific ("Dr. (Smt.) Kavita Krishnan") is one word of the name (FB5 R6-04).
_BRACKET_HON = r"\((?:" + "|".join(HONORIFICS) + r")\.?\)"
_WORD = re.compile(_BRACKET_HON + r"|[^\s,;:()\[\]\"]+")
# Abbreviations that end in a dot without ending a sentence (FB5 R6-04).
_NON_TERMINAL = {"mohd.", "md.", "mohd", "md", "jr.", "sr.", "st."}


def _is_hon(w: str) -> bool:
    return bool(_HON_RX.match(w) or re.fullmatch(_BRACKET_HON, w))


def _is_cap(w: str) -> bool:
    return bool(re.match(r"[A-Z][A-Za-z'.-]*$", w) or re.fullmatch(_BRACKET_HON, w))


# FB9 R2-04: post-nominals and heading words end a name; they are never part of it ("Shri Ramesh Kumar IAS",
# "Subject: Deputation of Anjali Under Rule 12", "Leave of Ramesh Sanctioned").
_NAME_END = {"ias", "ips", "ifs", "irs", "esq", "esq.", "under", "regarding", "sanctioned", "with", "ji", "retd",
             "retd.", "phd", "ph.d.", "mbbs"}


def _cap_runs(text: str, taken):
    """Runs of capitalised words (with of/and/for/the between them). A run ends at punctuation other than a dot
    inside a word, at a claimed span, at a lowercase word and after a word that ends a sentence."""
    runs, run, prev_end = [], [], None
    for m in _WORD.finditer(text):
        w, a, b = m.group(0), m.start(), m.end()
        gap = text[prev_end:a] if prev_end is not None else ""
        # FB6 R2-01: a newline is a block boundary in a draft ("Shri Venkatesh Iyer" / "Assistant Section Officer")
        breaks = bool(re.search(r"[,;:()\[\]\"\n]", gap)) or taken(a, b)
        if run and not breaks and prev_end is not None:
            last = run[-1][1]
            # a word ending in "." ends the sentence unless it is an honorific, an initial ("A.", "O.M.") or a
            # name abbreviation ("Mohd.")
            if last.endswith(".") and not _is_hon(last) and last.lower() not in _NON_TERMINAL \
                    and len(last.rstrip(".").replace(".", "")) > 2:
                breaks = True
        # "MD" in capitals is a post-nominal; "Md." is a name word
        if w.lower() in _NAME_END or w.lower().rstrip(".") in _NAME_END or w == "MD":
            breaks = True
        if breaks or not (_is_cap(w) or w.lower() in _CONNECTORS):
            if run:
                runs.append(run)
            run = []
            if not taken(a, b) and _is_cap(w) and w.lower().rstrip(".") not in _NAME_END and w != "MD":
                run = [(a, w)]
        else:
            run.append((a, w))
        prev_end = b
    if run:
        runs.append(run)
    return [(r[0][0], r) for r in runs]


def _split_at_honorifics(start, words):
    """FB4 R5-01: every honorific starts a new name ("Shri Ram Kumar and Smt. Sita Devi" is two names)."""
    parts, cur = [], []
    for i, (a, w) in enumerate(words):
        # a second honorific right after one ("Dr. (Smt.)") belongs to the same person; FB8: an honorific word at the
        # end of a run is a surname ("Anjali Kumari"), not the start of another name
        last = i == len(words) - 1
        # FB9 R2-01: a dotless honorific word after a name word, not after "and", is a middle name ("Sunita Kumari
        # Singh", "Anil Kumari Prasad"); "Shri Ram Kumar and Smt Sita Devi" still splits (a comma ends the run anyway)
        prev = words[i - 1][1] if i else ""
        middle = (not w.endswith(".") and not w.startswith("(") and prev and not _is_hon(prev)
                  and prev.lower() not in _CONNECTORS)
        if _is_hon(w) and not last and not middle and cur and not all(_is_hon(x) for _, x in cur):
            parts.append(cur)
            cur = []
        cur.append((a, w))
    if cur:
        parts.append(cur)
    return [(p[0][0], p) for p in parts]


def _trim(words):
    def bad(w):
        k = w.lower().rstrip(".")
        return k in _NOT_NAME or k in _MONTH_SET or k in _CONNECTORS
    words = list(words)
    while words and bad(words[0][1]) and not _is_hon(words[0][1]):
        words.pop(0)
    while words and bad(words[-1][1]):
        words.pop()
    return words


# ---- presence ----------------------------------------------------------------------------------------------------------
def _norm(s: str) -> str:
    return " ".join(_clean(s or "").split())


def _after_word(hay: str, end: int) -> str:
    m = re.match(r"[\s-]+(?:and\s+)?(\w+)", hay[end:])
    return m.group(0).lower() if m else ""


def _fact_rx(t: str):
    body = re.escape(t)
    body = re.sub(r"(?i)\b(lakh|crore)s?\b", r"\1s?", body)
    return re.compile(r"(?<![^\W_])(?<![/])(?<!\d[,.])" + body + r"(?![^\W_])(?!/(?!-))(?![,.]\d)", re.I)


_CONNECTOR_WORD = re.compile(r"(?i)\b(?:of|for|the|and|to|from|in|on|at|by)\b")


def _extends(name: str, big: str) -> bool:
    """Does `big` extend the name `name` into a longer name of another person ("Shri Anil Kumar" -> "Shri Anil Kumar
    Singh")?
    - Words after the name that continue it make an extension, whatever comes before it ("Deputation of Anjali
      Sharma", "Promotion of Kavitha Reddy to the Grade of UDC": FB8 R2-01).
    - With nothing after it (or a connector next), only the words between the last connector and the name count:
      none ("Deputation of Anjali", "The Tehsildar of Haveli", "Filling Up of the Post of Superintendent": FB7 R2-01)
      or honorifics only ("Shri Ramesh": FB7 R2-03) is the same name, not an extension."""
    n, b = _norm(name).lower(), _norm(big).lower()
    for m in _fact_rx(n).finditer(b):
        before, after = b[:m.start()], b[m.end():]
        nxt = after.split()[0] if after.split() else ""
        if nxt and not _CONNECTOR_WORD.fullmatch(nxt):
            return True                           # more name words after it: another, longer name
        cuts = list(_CONNECTOR_WORD.finditer(before))
        lead = _norm(big)[cuts[-1].end():m.start()] if cuts else _norm(big)[:m.start()]
        if all(_HON_RX.match(w) or re.fullmatch(_BRACKET_HON, w) for w in lead.split()):
            continue                              # nothing or only titles before it: the same name
        return True
    return False


def _name_hits(name: str, text: str, longer: list, draft_longer=()) -> int:
    """Count occurrences of a name outside a longer name that extends it. Longer names of the instruction cover their
    occurrences in any case (FB5 R6-02); longer names found only in the draft cover only their own, case-sensitive
    run positions (FB7 R2-01), so a title-case heading never hides the same words in a lowercase body sentence."""
    # spacing is normalised within each line; a newline (a block boundary) is kept
    hay = "\n".join(" ".join(line.split()) for line in _clean(text or "").splitlines())
    covers = [(m.start(), m.end()) for big in longer if _extends(name, big) for m in _fact_rx(_norm(big)).finditer(hay)]
    covers += [(m.start(), m.end()) for big in draft_longer if _extends(name, big)
               for m in re.finditer(r"(?<![^\W_])" + re.escape(_norm(big)) + r"(?![^\W_])", hay)]
    # FB8: a name with a lowercase word ("Shri ramesh kumar") is not seen by the capitalised-run stage, so in the
    # draft an occurrence followed directly on the same line by a capitalised name word ("Shri ramesh kumar Xavier")
    # is a longer name, not this one. A lowercase word after it is read as prose (plan 16 limitation).
    lower = any(w[:1].islower() and w.lower() not in _CONNECTORS for w in _norm(name).split())

    def continued(end):
        # only a capitalised word on the same line ("Shri ramesh kumar Xavier"); a lowercase word after a lowercase
        # name ("asha devi requests ...") is ordinary prose, and a newline is a block boundary
        nxt = re.match(r" ([A-Z][A-Za-z'-]*)", hay[end:])
        return bool(lower and nxt and nxt.group(1).lower() not in _NOT_NAME and not _is_hon(nxt.group(1))
                    and nxt.group(1).lower().rstrip(".") not in _NAME_END and nxt.group(1) != "MD")
    # FB8: a name joined to another word by a hyphen ("Anjali-Sharma") is part of a longer name, not the name itself
    return sum(1 for m in _fact_rx(_norm(name)).finditer(hay)
               if not re.match(r"-[^\W\d_]", hay[m.end():m.end() + 2]) and not re.search(r"[^\W\d_]-$", hay[:m.start()])
               and not continued(m.end())
               and not any(a <= m.start() and m.end() <= b and (b - a) > (m.end() - m.start()) for a, b in covers))


_REF_SUFFIX = re.compile(r"(?:-[A-Za-z0-9]|\([A-Za-z0-9]|\.[-/(]|/[A-Za-z0-9])")
_REF_PREFIX = re.compile(r"[A-Za-z0-9]-$")


def fact_present(fact: str, draft_text: str, instruction: str | None = None, kind: str | None = None) -> bool:
    """A fact counts as present only as a whole token run: no letter or digit or '/' directly before or after it, and
    no digit group continuing it ("25,000" is not inside "1,25,000"; "Kumar" is not inside "Kumari"). Spacing and
    case are ignored; "lakh" also matches "lakhs"; an amount may end in "/-".
    FB4 R5-03: a number-word fact ("two lakh") or a digit fact ("12") followed in the draft by another number
    word ("two lakh fifty thousand", "12 thousand") is a changed number, unless the instruction has the same
    following word (an identical draft never warns)."""
    t = _norm(fact)
    if not t:
        return True
    rx = _fact_rx(t)
    hay = _norm(draft_text)
    words = t.split()
    ends_num_word = bool(_NUM_WORD_RX.match(words[-1]))
    ends_plain_digit = bool(re.fullmatch(r"\d[\d,]*(?:\.\d+)?", words[-1]))
    starts_num_word = bool(_NUM_WORD_RX.match(words[0]))
    same_after = set()
    if instruction is not None and (ends_num_word or ends_plain_digit):
        src = _norm(instruction)
        for m in rx.finditer(src):
            same_after.add(_after_word(src, m.end()))
    for m in rx.finditer(hay):
        # FB9 R2-03: "14/2/2026-1", "...-Estt.-II", "...-Estt.(Pt.)", "...-Estt./1" and "A-14/2/2026" are other files
        if kind == "reference" and (_REF_SUFFIX.match(hay[m.end():]) or _REF_PREFIX.search(hay[:m.start()])):
            continue
        if ends_num_word or ends_plain_digit:
            after = hay[m.end():]
            cont = re.match(r"[\s-]+" + _NUM_WORD + r"\b", after, re.I) or \
                re.match(r"\s+and\s+" + _NUM_WORD + r"[\s-]+" + _NUM_WORD + r"\b", after, re.I)
            if cont and _after_word(hay, m.end()) not in same_after:
                continue
        if starts_num_word and re.search(r"\b" + _NUM_WORD + r"[\s-]+$", hay[:m.start()], re.I):
            continue
        return True
    return False


def missing_facts(instruction: str, draft_text: str) -> list:
    """Facts from the instruction that the draft does not contain as whole tokens (case and spacing ignored).
    Returns warnings {code: FACT_MISSING, kind, text, message}."""
    out = []
    facts = extract_facts(instruction)
    names = [f["text"] for f in facts if f["kind"] == "name"]
    draft_names = [f["text"] for f in extract_facts(draft_text) if f["kind"] == "name"] if names else []
    for f in facts:
        if f["kind"] == "name":
            # A shorter name inside a longer one is not the same person, whether the longer name was in the
            # instruction or appeared only in the draft. Exact repeats still need just one occurrence.
            low = _norm(f["text"]).lower()
            longer = [n for n in names if n != f["text"] and low in _norm(n).lower()]
            draft_longer = [n for n in draft_names if n not in names and n != f["text"] and low in _norm(n).lower()]
            present = _name_hits(f["text"], draft_text, longer, draft_longer) >= 1
        else:
            present = fact_present(f["text"], draft_text, instruction, f["kind"])
        if not present:
            out.append({"code": "FACT_MISSING", "kind": f["kind"], "text": f["text"],
                        "message": f"The draft does not contain the {f['kind']} '{f['text']}' from your instruction. "
                                   "Check it before saving."})
    return out
