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
             "respected", "revered", "madam", "sir", "monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"}
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
_NAME_END = {"ias", "ips", "ifs", "irs", "esq", "esq.", "under", "regarding", "sanctioned", "with", "retd",
             "retd.", "phd", "ph.d.", "mbbs"}
# FB10 R2-02: "Ji" is trimmed only when it is the last word of a name ("Shri Ramesh Ji,", "Sharma Ji"); inside a
# name it is a name word ("Shri Ram Ji Lal").
_TRAILING_ONLY = {"ji"}


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


# FB12 R2-01: courtesy and designation words written before a title ("Hon'ble Shri", "Late Shri", "Minister Shri",
# "Minister of State Shri", "MLA Shri", "Collector Shri") are not a middle name and not part of the name. "Kumari"
# after such a word stays a middle name, as FB9 R2-01 reads it ("Joint Secretary Kumari Xavier" is one longer run).
_BEFORE_TITLE = {"hon'ble", "hon’ble", "honble", "hon", "honourable", "honorable", "late", "esteemed",
                 "adarniya", "aadarniya", "mla", "mp", "mlc", "minister", "ministers", "secretary", "collector",
                 "commissioner", "director", "chairman", "chairperson", "president", "governor", "mayor", "member",
                 "state", "deputy", "joint", "additional", "chief", "magistrate", "judge", "officer", "inspector",
                 "registrar", "superintendent", "principal", "ambassador", "consul", "tehsildar", "tahsildar", "sdm",
                 "bdo", "councillor", "sarpanch", "speaker"}


def _courtesy_only(words) -> bool:
    return all(w.lower().rstrip(".,") in _BEFORE_TITLE or w.lower() in _CONNECTORS for _, w in words)


def _split_at_honorifics(start, words):
    """FB4 R5-01: every honorific starts a new name ("Shri Ram Kumar and Smt. Sita Devi" is two names)."""
    parts, cur = [], []
    for i, (a, w) in enumerate(words):
        # a second honorific right after one ("Dr. (Smt.)") belongs to the same person; FB8: an honorific word at the
        # end of a run is a surname ("Anjali Kumari"), not the start of another name
        last = i == len(words) - 1
        # FB9 R2-01: a dotless honorific word after a name word, not after "and", is a middle name ("Sunita Kumari
        # Singh", "Anil Kumari Prasad", "Shri Ramesh Shri Vastava"); "Shri Ram Kumar and Smt Sita Devi" still splits
        # (a comma ends the run anyway). FB10: not after a salutation or another word that is not a name word
        # ("Respected Shri Ramesh Ji", "Dear Shri Anil").
        prev = words[i - 1][1] if i else ""
        # FB12: only honorific words that are also name words can be a middle name ("Kumari", "Shri"); "Smt", "Dr",
        # "Mr", "Ms", "Prof" ... after a name start the next person ("Shri Ram Kumar Smt Sita Devi")
        middle = (not w.endswith(".") and not w.startswith("(") and prev and not _is_hon(prev)
                  and w.lower() in ("kumari", "kum", "km", "shri")
                  and prev.lower() not in _CONNECTORS and prev.lower().rstrip(".,") not in _NOT_NAME
                  and (prev.lower().rstrip(".,") not in _BEFORE_TITLE or w.lower() in ("kumari", "km", "kum")))
        if _is_hon(w) and not last and not middle and cur and not all(_is_hon(x) for _, x in cur):
            if not _courtesy_only(cur):          # "Hon'ble Minister" before "Shri ..." is dropped, not a name
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
    while words and (bad(words[-1][1]) or words[-1][1].lower().rstrip(".") in _TRAILING_ONLY):
        words.pop()
    return words


# ---- presence ----------------------------------------------------------------------------------------------------------
def _norm(s: str) -> str:
    return " ".join(_clean(s or "").split())


def _after_word(hay: str, end: int) -> str:
    m = re.match(r"[\s-]+(?:and\s+)?(\w+)", hay[end:])
    return m.group(0).lower() if m else ""


def _fact_rx(t: str, slash_after: bool = False):
    """The word-for-word token rule. FB12: for a reference a "/" may follow ("14/7/2026-Vig/dated"), and so may a
    date word written without a space ("HR/Trg/2026/145dt. 3.10.2026"); whether what follows makes another file is
    then a FACT_CHECK question (_REF_SUFFIX), never a FACT_MISSING one."""
    body = re.escape(t)
    body = re.sub(r"(?i)\b(lakh|crore)s?\b", r"\1s?", body)
    if slash_after:
        after = r"(?:(?![^\W_])|(?=(?:dated|dtd|dt)\b))(?![,.]\d)"
    else:
        after = r"(?![^\W_])(?!/(?!-))(?![,.]\d)"
    return re.compile(r"(?<![^\W_])(?<![/])(?<!\d[,.])" + body + after, re.I)


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


def _sentence_continuation(name: str, big: str, rest: str, lead: str = "") -> bool:
    """FB10 R2-03 / FB11 R2-02: a longer draft name whose extra words are all lowercase is an extension when it
    reaches a block end (a newline or the end: "To / Shri ramesh kumar sharma", "To / Shri mohammad ahmed"). Before
    punctuation inside a block it is an extension unless an extra word looks like a verb ("Shri ramesh kumar
    retired."). Followed by more words, it is sentence text ("Shri ramesh kumar reported for duty").
    FB12 R2-03: at a block end an -ed/-ing word is a verb ending a subject line ("Subject: Leave of Shri ramesh
    kumar sanctioned") unless the name starts its block (an address line); `lead` is the text before it on its line."""
    extra = _norm(big)[len(_norm(name)):].split() if _norm(big).lower().startswith(_norm(name).lower()) else []
    if not extra or not all(w[:1].islower() for w in extra):
        return False
    if re.match(r"[ \t]*(?:\n|$)", rest):
        return bool(lead.strip()) and any(re.search(r"(?:ed|ing)$", w) for w in extra)
    if re.match(r"[ \t]*[.,;:()!?]", rest):
        return any(re.search(r"(?:ed|ing)$", w) for w in extra)
    return True


def _name_occurrences(name: str, text: str, longer: list, draft_longer=()) -> list:
    """FB12 (OD-OD-6): every word-for-word occurrence of a name, each paired with the longer name the rules read it
    as part of (None when it stands on its own). Occurrences inside a longer name of the INSTRUCTION are not listed
    at all (FB5 R6-02: "Shri Anil Kumar" next to "Shri Anil Kumar Singh" is two people, in any case), so a draft
    with only the longer one has no occurrence of the shorter: FACT_MISSING. Longer names found only in the draft
    cover only their own, case-sensitive run positions (FB7 R2-01); they, a hyphen ("Anjali-Sharma", FB8) and a
    capitalised word after a lowercase name ("Shri ramesh kumar Xavier", FB8) make an occurrence a longer name:
    FACT_CHECK when every occurrence is one."""
    # spacing is normalised within each line; a newline (a block boundary) is kept
    hay = "\n".join(" ".join(line.split()) for line in _clean(text or "").splitlines())
    covers = [(m.start(), m.end()) for big in longer if _extends(name, big) for m in _fact_rx(_norm(big)).finditer(hay)]
    draft_covers = [(m.start(), m.end()) for big in draft_longer if _extends(name, big)
                    for m in re.finditer(r"(?<![^\W_])" + re.escape(_norm(big)) + r"(?![^\W_])", hay)
                    if not _sentence_continuation(name, big, hay[m.end():],
                                                  hay[hay.rfind("\n", 0, m.start()) + 1:m.start()])]
    lower = any(w[:1].islower() and w.lower() not in _CONNECTORS for w in _norm(name).split())

    def continued(end):
        # only a capitalised word on the same line ("Shri ramesh kumar Xavier"); a lowercase word after a lowercase
        # name ("asha devi requests ...") is ordinary prose, and a newline is a block boundary
        nxt = re.match(r" ([A-Z][A-Za-z'-]*)", hay[end:])
        ok = bool(lower and nxt and nxt.group(1).lower() not in _NOT_NAME and not _is_hon(nxt.group(1))
                  and nxt.group(1).lower().rstrip(".") not in _NAME_END and nxt.group(1) != "MD")
        return nxt.group(1) if ok else None

    def inside(a, b, spans):
        return next(((x, y) for x, y in spans if x <= a and b <= y and (y - x) > (b - a)), None)

    out = []
    for m in _fact_rx(_norm(name)).finditer(hay):
        a, b = m.start(), m.end()
        if inside(a, b, covers):
            continue
        cover = inside(a, b, draft_covers)
        if cover:
            # the longer name as the owner would read it: from the last connector before the name ("Deputation of
            # Anjali Sharma" -> "Anjali Sharma")
            cuts = list(_CONNECTOR_WORD.finditer(hay, cover[0], a))
            out.append(hay[cuts[-1].end() if cuts else cover[0]:cover[1]].strip())
        elif re.match(r"-[^\W\d_]", hay[b:b + 2]):              # FB8: "Anjali-Sharma"
            out.append(hay[a:b] + re.match(r"-[^\W\d_][\w'-]*", hay[b:]).group(0))
        elif re.search(r"[^\W\d_]-$", hay[:a]):
            out.append(re.search(r"[\w'-]*[^\W\d_]-$", hay[:a]).group(0) + hay[a:b])
        elif continued(b):
            out.append(hay[a:b] + " " + continued(b))
        else:
            out.append(None)
    return out


def _name_hits(name: str, text: str, longer: list, draft_longer=()) -> int:
    """Occurrences of a name that stand on their own (not read as part of a longer name)."""
    return sum(1 for o in _name_occurrences(name, text, longer, draft_longer) if o is None)


# FB11 R2-01: a positive, code-shaped rule. A reference is another file only when it is followed directly (or
# after a dot) by "-" or "/" plus digits or a capitalised section code of at most six letters ("-1", "-II", "-Admn",
# "-ESTT", "/2"), or by a part-file bracket ("(1)", "(II)", "(Pt.)", "(Pt.II)", "(Part-I)", "(Part II)",
# "(Vol.2)"). A hyphen or slash followed by a lowercase word ("-dtd.", "-wef", "-reminder", "./dated") or by a
# date or reference word in any case ("-Dated", "-Dt.", "-DT", "-Reg.", "-Wef", "-Ref", "-Vide"), and a bracket
# holding an ordinary word ("(copy)", "(PDF)",
# "(2 pages)"), are not. Only a letter code of at most three capitals or digits before a hyphen is a prefix ("A-",
# "B-"); a designator or a word joined by a hyphen ("No-", "F.No-", "Ref-", "Letter-", "Memo-") is not.
_REF_CODE = r"(?:\d|(?!(?i:dated|date|dtd|dt|reg|wef|w\.e\.f|ref|vide)\b)[A-Z][A-Za-z]{0,5}(?![A-Za-z]))"
_REF_PART = r"\((?:\d+|[IVX]+|[A-Z]|Pt\.?\s?(?:[IVX]+|\d+)?|Part[-\s]?(?:[IVX]+|\d+)|Vol\.?\s?(?:\d+|[IVX]+))\)"
_REF_SUFFIX = re.compile(r"\.?(?:[-/]" + _REF_CODE + r"|" + _REF_PART + r")")
_REF_PREFIX = re.compile(r"(?:^|[^A-Za-z0-9.])(?:[A-Z]{1,3}|\d+)-$")
_REF_DESIGNATOR_HYPHEN = re.compile(r"(?i)(?:\bno|\bref|\bf\.?\s?no|\bo\.?\s?m\.?\s?no|\bd\.?\s?o\.?\s?no)\.?-$")


def _fact_occurrences(fact: str, draft_text: str, instruction: str | None = None, kind: str | None = None) -> list:
    """FB12 (OD-OD-6): every word-for-word occurrence of a non-name fact, each paired with the longer reference the
    rules read it as part of (None when it stands on its own). A word-for-word occurrence is a whole token run: no
    letter or digit or '/' directly before or after it (a reference may be followed by '/'), and no digit group
    continuing it ("25,000" is not inside "1,25,000"; "3 November" is not inside "13 November"). Spacing and case
    are ignored; "lakh" also matches "lakhs"; an amount may end in "/-".
    FB4 R5-03: a number-word fact ("two lakh") or a digit fact ("12") followed in the draft by another number word
    ("two lakh fifty thousand", "12 thousand") is a different number, not an occurrence, unless the instruction has
    the same following word (an identical draft never warns).
    FB9 R2-03 / FB11 R2-01: a reference followed by a section code, a part file or a further number ("-1", "-II",
    "(Pt.)", "(A)", "/2") or preceded by a letter code ("A-") is read as another file: FACT_CHECK, not absence."""
    t = _norm(fact)
    if not t:
        return [None]
    rx = _fact_rx(t, slash_after=kind == "reference")
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
    out = []
    for m in rx.finditer(hay):
        if ends_num_word or ends_plain_digit:
            after = hay[m.end():]
            cont = re.match(r"[\s-]+" + _NUM_WORD + r"\b", after, re.I) or \
                re.match(r"\s+and\s+" + _NUM_WORD + r"[\s-]+" + _NUM_WORD + r"\b", after, re.I)
            if cont and _after_word(hay, m.end()) not in same_after:
                continue
        if starts_num_word and re.search(r"\b" + _NUM_WORD + r"[\s-]+$", hay[:m.start()], re.I):
            continue
        if kind == "reference":
            suffix = _REF_SUFFIX.match(hay[m.end():])
            before = hay[:m.start()]
            if suffix:
                tail = re.match(r"[A-Za-z0-9]*\)?", hay[m.end() + suffix.end():]).group(0)
                out.append(hay[m.start():m.end() + suffix.end()] + tail)
                continue
            if _REF_PREFIX.search(before) and not _REF_DESIGNATOR_HYPHEN.search(before):
                out.append(re.search(r"(?:[A-Z]{1,3}|\d+)-$", before).group(0) + hay[m.start():m.end()])
                continue
        out.append(None)
    return out


def fact_present(fact: str, draft_text: str, instruction: str | None = None, kind: str | None = None) -> bool:
    """A fact is present when it occurs word for word and at least one occurrence stands on its own (see
    _fact_occurrences)."""
    return any(o is None for o in _fact_occurrences(fact, draft_text, instruction, kind))


def missing_facts(instruction: str, draft_text: str) -> list:
    """FB12 (OD-OD-6): two signals per marked fact of the instruction.
    - FACT_MISSING: the fact does not appear word for word (per-kind token boundaries; a name inside a longer
      name of the instruction does not count). No extension rule ever produces it, so a faithful draft never
      gets it, whatever surrounds the fact.
    - FACT_CHECK: the fact appears word for word, but every occurrence is inside what the rules read as a longer
      name or reference ("Anjali" only as "Anjali Sharma"; "14/2/2026" only as "14/2/2026-1").
    Returns warnings {code, kind, text, message} (FACT_CHECK also has `found`: the longer form)."""
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
            occ = _name_occurrences(f["text"], draft_text, longer, draft_longer)
        else:
            occ = _fact_occurrences(f["text"], draft_text, instruction, f["kind"])
        if any(o is None for o in occ):
            continue
        if not occ:
            out.append({"code": "FACT_MISSING", "kind": f["kind"], "text": f["text"],
                        "message": f"The draft does not contain the {f['kind']} '{f['text']}' from your instruction. "
                                   "Check it before saving."})
        else:
            what = "file" if f["kind"] == "reference" else "person"
            out.append({"code": "FACT_CHECK", "kind": f["kind"], "text": f["text"], "found": occ[0],
                        "message": f"'{f['text']}' appears only as '{occ[0]}'. Check it is the same {what}."})
    return out
