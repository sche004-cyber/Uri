"""FB4 (plan 16): a corpus-driven property test of the OD-2 fact check. For every case in
data/office_fact_corpus.json:
  (a) extract_facts gives exactly the expected facts, in order;
  (b) an identical draft never warns;
  (c) a draft that changes exactly one fact warns about that fact. The changes are made here, from the fact's kind:
      a name's surname or first name, a date's day or month, an amount's or number's digits, a number's unit or
      number word, a reference's last digit; and a digit put in front of a day, number or reference ("3" -> "13",
      "7 days" -> "17 days", "12/2026" -> "112/2026") so a fact found inside a longer token is caught.
      FB12 (OD-OD-6): each of these replaces the fact, so the warning is FACT_MISSING. The reference changes that
      keep the fact word for word and extend it ("-1", "(Pt.)", "A-") give FACT_CHECK.
  (d) FB6: a faithful MULTI-BLOCK draft, joined with newlines as the service joins the Brain's blocks, with each fact
      in its own block between realistic neighbour blocks (designation, section, "Sir,", "Guard File", signature),
      never warns; and each one-fact change of (c) made in that draft still warns.
  (e) FB7: each fact inside text, as real drafts write it: a title-case heading ("Subject: <Noun> of <name>", the
      noun taken from the instruction's own "<noun> of <name>" when it has one and "Deputation" otherwise; other
      facts get "Subject: <fact>"), a capitalised "To" block ("The Tehsildar of <name>") for names, and a body
      sentence that repeats the instruction's own wording. The faithful draft never warns; a one-fact change made
      everywhere the fact appears still warns.
  (f) FB8: for every name, a draft that extends it into a longer name ("Subject: Deputation of <name> Xavier", or a
      "To" block "<name> Xavier") while the body changes or drops the name must warn: the longer name is another
      person, so it never stands in for the fact. FB12 (OD-OD-6): the name is still there word for word, so the
      warning is FACT_CHECK ("'<name>' appears only as '<name> Xavier'"). FB9 adds "<name> Kumari Xavier" (an honorific word as a middle
      name) and "<name> xavier" for a lowercase titled name at the end of a block; (e) adds a faithful draft with
      "<name> IAS" and "Subject: Deputation of <name> Under Rule 12"; references get "-1", "(Pt.)" and "A-" changes.
  (g) FB10: a case may list explicit faithful drafts (never warn) and changed drafts (must warn), for forms the
      generated drafts cannot express ("No-<file>", "<file>-dated", "(2 pages)", "Shri Ram Ji Lal", a lowercase titled
      name followed by a verb). FB12: a changed draft must give FACT_MISSING; checked drafts (the fact only inside a
      longer name or reference) give FACT_CHECK and no FACT_MISSING.
  (h) FB12 (OD-OD-6): every fact wrapped in the forms a faithful draft writes around it ("Hon'ble", "Late",
      "Minister", "Minister of State" before a title; a subject line ending in a participle; "/dated", "/dt.",
      "-W.E.F.", "-Date", "-Copy", "(A)" after a reference) never gives FACT_MISSING. FB13: the same courtesy and
      designation words written before a titled name in the INSTRUCTION ("to Hon'ble Minister Shri <name>", "to
      Joint Secretary Kumari <name>") leave the facts unchanged, so the plain faithful draft gives no warning; and an
      amount written with ".00" or ".0" (OD-OD-7) is the same amount, also before a unit ("2.00 lakh", FB14). FB14:
      the designations before the title are generated from head words, qualifiers and tails (41 forms), so the rule
      "a titled name starts at its honorific" is tested generically.
A new case gets (b) to (f) and (h) without writing them.
OD-OD-8 (FB15): a changed or dropped name without a title gives FACT_CHECK, not FACT_MISSING, in (c) to (e) and
(g); every titled name, date, amount, number and reference keeps FACT_MISSING.
Commits before FB12 have no FACT_CHECK: a warning without a code is read as FACT_MISSING."""
from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

from uri_office.authoring import drafting as DR

CORPUS = json.loads((Path(__file__).parent / "data" / "office_fact_corpus.json").read_text(encoding="utf-8"))["cases"]
IDS = [c["id"] for c in CORPUS]

# Independent of the module under test, so the same file runs against older commits.
_HON = re.compile(r"\(?(?:Shri|Smt|Sh|Km|Kum|Kumari|Sushri|Dr|Mr|Mrs|Ms|Prof)\.?\)?$")
_BRACKET_WORDS = re.compile(r"\s*\((?:[a-z]+[\s-]*)+\)", re.I)
_MONTHS = ["january", "february", "march", "april", "may", "june", "july", "august", "september", "october",
           "november", "december"]
_ABBR = ["jan", "feb", "mar", "apr", "may", "jun", "jul", "aug", "sep", "oct", "nov", "dec"]
_UNIT_SWAP = {"day": "week", "days": "weeks", "week": "month", "weeks": "months", "months": "years",
              "month": "year", "years": "days", "km": "miles", "posts": "vacancies", "vacancies": "posts",
              "copies": "pages", "sets": "units", "nos.": "sets", "officers": "persons", "hrs": "mins", "am": "pm",
              "pm": "am", "a.m.": "p.m.", "p.m.": "a.m.", "lakh": "crore", "crore": "lakh"}
_NUM_SWAP = {"one": "two", "two": "three", "three": "four", "four": "five", "five": "six", "six": "seven",
             "seven": "eight", "eight": "nine", "nine": "ten", "ten": "eleven", "twenty": "thirty",
             "thirty": "forty", "forty": "fifty", "fifty": "sixty", "hundred": "thousand", "thousand": "hundred",
             "lakh": "crore", "crore": "lakh"}


def _same_case(new: str, old: str) -> str:
    if old.isupper():
        return new.upper()
    if old[:1].isupper():
        return new[:1].upper() + new[1:]
    return new


def _digit_up(s: str, last: bool = False) -> str:
    idx = [i for i, ch in enumerate(s) if ch.isdigit()]
    i = idx[-1] if last else idx[0]
    d = (int(s[i]) + 1) % 10
    if d == 0 and not last:
        d = 9 if s[i] != "9" else 1
    return s[:i] + str(d) + s[i + 1:]


def _ordinal(n: int) -> str:
    return "th" if 10 <= n % 100 <= 20 else {1: "st", 2: "nd", 3: "rd"}.get(n % 10, "th")


def mutations(kind: str, text: str) -> list:
    """Drafts of one fact that differ from it, each paired with what was changed."""
    out = []
    words = text.split()
    if kind == "name":
        first = 0
        while first < len(words) - 1 and _HON.match(words[first]):    # skip "Dr. (Smt.)"
            first += 1
        last = words[-1].rstrip(".")
        out.append(("surname", " ".join(words[:-1] + [last + ("a" if last.endswith("i") else "i")])))
        if first < len(words) - 1:
            w = list(words)
            w[first] = w[first] + "a"
            out.append(("first name", " ".join(w)))
    elif kind == "date":
        m = re.search(r"\b(\d{1,2})(st|nd|rd|th)?\b", text)
        if m:                                           # "April 2026" and "April to June" have no day
            day = int(m.group(1))
            nd = day % 28 + 1
            new_day = (str(nd).zfill(len(m.group(1)))) + (_ordinal(nd) if m.group(2) else "")
            out.append(("day", text[:m.start()] + new_day + text[m.end():]))
            if day < 10 and len(m.group(1)) == 1:        # "3 November" inside "13 November" (FB1 R2-01 class)
                out.append(("day prefix", text[:m.start()] + "1" + text[m.start():]))
        y = re.search(r"\b\d{4}\b", text)
        if y:
            out.append(("year", text[:y.start()] + _digit_up(y.group(0), last=True) + text[y.end():]))
        rest = text.replace(m.group(0), "", 1) if m else text
        mon = next((w for w in re.findall(r"[A-Za-z]+", rest)
                   if w.lower() in _MONTHS or w.lower() in _ABBR or w.lower() == "sept"), None)
        if mon is None:                                 # "12.05.2026": the day and year changes above suffice
            return out
        names = _MONTHS if mon.lower() in _MONTHS else _ABBR
        nxt = names[(names.index(mon.lower()) + 1) % 12]
        out.append(("month", re.sub(r"\b" + re.escape(mon) + r"\b", _same_case(nxt, mon), text, count=1)))
    elif kind in ("amount", "number"):
        if re.search(r"\d", words[0]):
            out.append(("value", " ".join([_digit_up(words[0])] + words[1:])))
            out.append(("value prefix", "1" + text))       # "7 days" inside "17 days", "25,000" in "1,25,000"
            if len(words) > 1 and words[-1].lower() in _UNIT_SWAP:
                out.append(("unit", " ".join(words[:-1] + [_same_case(_UNIT_SWAP[words[-1].lower()], words[-1])])))
        else:
            w = list(words)
            w[0] = _same_case(_NUM_SWAP.get(w[0].lower(), "eleven" if w[0].lower() != "eleven" else "twelve"),
                              w[0])
            out.append(("number word", " ".join(w)))
            if len(words) > 1 and words[-1].lower() in _UNIT_SWAP and not words[-1].lower() in _NUM_SWAP:
                out.append(("unit", " ".join(words[:-1] + [_same_case(_UNIT_SWAP[words[-1].lower()], words[-1])])))
    elif kind == "reference":
        out.append(("digit", _digit_up(text, last=True)))
        i = re.search(r"\d", text).start()                  # "12/2026" inside "112/2026"
        out.append(("digit prefix", text[:i] + "1" + text[i:]))
        # FB9 R2-03: a section suffix, a part file and a letter prefix make another file
        out += [("suffix", text + "-1"), ("part file", text + "(Pt.)"),
                ("prefix", ("B-" if text.startswith("A-") else "A-") + text)]
    return out


def _replace_fact(instruction: str, fact: str, new: str, others=()) -> str:
    """Replaces the fact's own occurrence: not one inside a longer fact of the same case ("Shri Anil Kumar" inside
    "Shri Anil Kumar Singh")."""
    rx = re.compile(r"(?<![\w/])" + re.escape(fact) + r"(?![\w])(?!/(?!-))")
    for attempt in (instruction, _BRACKET_WORDS.sub("", instruction)):   # "3 (three) posts": the cleaned text
        covers = [(c.start(), c.end()) for o in others if len(o) > len(fact) and fact in o
                  for c in re.finditer(re.escape(o), attempt)]
        for m in rx.finditer(attempt):
            if not any(a <= m.start() and m.end() <= b for a, b in covers):
                return attempt[:m.start()] + new + attempt[m.end():]
    raise AssertionError((fact, instruction))


def _codes(instruction: str, draft: str) -> dict:
    """fact text -> warning code (FACT_MISSING when a commit before FB12 gives no code)."""
    return {w["text"]: w.get("code", "FACT_MISSING") for w in DR.missing_facts(instruction, draft)}


# FB12: the mutations that keep the fact word for word and extend it (another file), not replace it
_EXTENDING = {"suffix", "part file", "prefix"}


def _expected(what: str, kind: str = "", text: str = "") -> str:
    """FB12: an extension gives FACT_CHECK. OD-OD-8 (FB15): a name without a title gives FACT_CHECK when it is
    changed or dropped; titled names, dates, amounts, numbers and references keep FACT_MISSING."""
    if kind == "name" and not _HON.match(text.split()[0]):
        return "FACT_CHECK"
    return "FACT_CHECK" if what in _EXTENDING else "FACT_MISSING"


def test_corpus_is_large_and_varied():
    assert len(CORPUS) >= 150
    names = " ".join(f[1] for c in CORPUS for f in c["facts"] if f[0] == "name")
    for hon in ("Shri", "Smt.", "Kum.", "Dr", "Sushri", "Mr", "Ms"):
        assert hon in names


@pytest.mark.parametrize("case", CORPUS, ids=IDS)
def test_a_facts_are_extracted(case):
    got = [[f["kind"], f["text"]] for f in DR.extract_facts(case["instruction"])]
    assert got == case["facts"], case["instruction"]


@pytest.mark.parametrize("case", CORPUS, ids=IDS)
def test_b_identical_draft_never_warns(case):
    assert DR.missing_facts(case["instruction"], case["instruction"]) == []


@pytest.mark.parametrize("case", CORPUS, ids=IDS)
def test_c_changing_one_fact_warns_about_it(case):
    ins = case["instruction"]
    missed = []
    for kind, text in case["facts"]:
        for what, new in mutations(kind, text):
            assert new != text
            draft = _replace_fact(ins, text, new, [t for _, t in case["facts"]])
            got = _codes(ins, draft).get(text)
            if got != _expected(what, kind, text):
                missed.append(f"{kind} '{text}' -> {what} '{new}': {got}")
    assert not missed, (ins, missed)


# (d) FB6 R2-01: the neighbour blocks a real draft has around a name, a date or a number (none repeats a corpus fact,
# so a changed fact cannot be found again in a neighbour). Each starts with capitals,
# which is what made a name and the next block one long "draft name" before the repair.
_HEAD = ["Office Memorandum", "Subject: Draft for approval", "To"]
_NEIGHBOURS = ["Assistant Section Officer", "Pension Cell", "Deputy Secretary", "Guard File", "Joint Secretary",
               "Sir,", "Copy to:", "Establishment Section"]
_TAIL = ["Yours faithfully,", "Under Secretary", "Copy to: Guard File"]


def _blocks(case, replace=None):
    blocks = list(_HEAD)
    for i, (kind, text) in enumerate(case["facts"]):
        blocks.append(replace[1] if replace and replace[0] == i else text)
        blocks.append(_NEIGHBOURS[i % len(_NEIGHBOURS)])
    return "\n".join(blocks + _TAIL)


@pytest.mark.parametrize("case", CORPUS, ids=IDS)
def test_d_multi_block_draft(case):
    ins = case["instruction"]
    assert DR.missing_facts(ins, _blocks(case)) == [], ins
    missed = []
    for i, (kind, text) in enumerate(case["facts"]):
        for what, new in mutations(kind, text):
            got = _codes(ins, _blocks(case, (i, new))).get(text)
            if got != _expected(what, kind, text):
                missed.append(f"{kind} '{text}' -> {what} '{new}': {got}")
    assert not missed, (ins, missed)


# (e) FB7 R2-02: facts inside headings, "To" blocks and the instruction's own sentence.
def _embedded(case, replace=None):
    ins = case["instruction"]
    blocks = ["Office Order"]
    body = ins
    for i, (kind, text) in enumerate(case["facts"]):
        t = replace[1] if replace and replace[0] == i else text
        if kind == "name":
            # the heading title-cases the instruction's own "<noun> of <name>" when it has one ("the deputation of
            # Anjali" -> "Subject: Deputation of Anjali"), which is what a drafter writes
            m = re.search(r"\b([A-Za-z]+)\s+of\s+" + re.escape(text) + r"\b", ins)
            noun = m.group(1).title() if m and m.group(1).lower() not in ("the", "a", "an") else "Deputation"
            blocks += [f"Subject: {noun} of {t}", "To", f"The Tehsildar of {t}"]
        else:
            blocks.append(f"Subject: {t}")
    if replace:
        body = _replace_fact(ins, case["facts"][replace[0]][1], replace[1], [t for _, t in case["facts"]])
    return "\n".join(blocks + [body, "Under Secretary", "Guard File"])


def _post_nominal(case):
    """FB9 R2-04: a faithful draft that writes a post-nominal or a heading word after each name ("<name> IAS",
    "Subject: Deputation of <name> Under Rule 12")."""
    blocks = ["Office Order"]
    for kind, text in case["facts"]:
        if kind == "name":
            blocks += [f"Subject: Deputation of {text} Under Rule 12", "To", f"{text} IAS"]
    return "\n".join(blocks + [case["instruction"], "Under Secretary"])


@pytest.mark.parametrize("case", CORPUS, ids=IDS)
def test_e_facts_inside_headings_and_sentences(case):
    ins = case["instruction"]
    assert DR.missing_facts(ins, _embedded(case)) == [], ins
    assert DR.missing_facts(ins, _post_nominal(case)) == [], ins
    missed = []
    for i, (kind, text) in enumerate(case["facts"]):
        for what, new in mutations(kind, text):
            got = _codes(ins, _embedded(case, (i, new))).get(text)
            if got != _expected(what, kind, text):
                missed.append(f"{kind} '{text}' -> {what} '{new}': {got}")
    assert not missed, (ins, missed)


# (f) FB8 R2-02: a longer name in a heading or a "To" block never stands in for a changed or dropped name.
def _extended(case, i, body_new, where, extra="Xavier"):
    ins, text = case["instruction"], case["facts"][i][1]
    body = _replace_fact(ins, text, body_new, [t for _, t in case["facts"]])
    head = [f"Subject: Deputation of {text} {extra}"] if where == "heading" else ["To", f"{text} {extra}", "Assistant"]
    return "\n".join(["Office Order"] + head + [body, "Under Secretary"])


@pytest.mark.parametrize("case", [c for c in CORPUS if any(k == "name" for k, _ in c["facts"])],
                         ids=[c["id"] for c in CORPUS if any(k == "name" for k, _ in c["facts"])])
def test_f_a_longer_name_never_stands_in_for_the_fact(case):
    ins = case["instruction"]
    missed = []
    for i, (kind, text) in enumerate(case["facts"]):
        if kind != "name":
            continue
        changed = mutations(kind, text)[0][1]
        # FB9 R2-01: "Kumari" as a middle name; R2-02: a lowercase continuation of a lowercase titled name
        extras = ["Xavier"]
        # FB13 R2-01: "Joint Secretary Kumari Xavier" is a designation and a person, not a longer name
        if text.split()[-1][:1].isupper() and text.split()[-1].lower() not in _DESIGNATIONS:
            extras.append("Kumari Xavier")
        if text.split()[-1][:1].islower() and re.match(r"(?:Shri|Smt|Sh|Km|Kum|Kumari|Sushri|Dr|Mr|Mrs|Ms|Prof)\b",
                                                         text):
            extras.append("xavier")
        for extra in extras:
            for where in ("heading", "to"):
                for body_new in (changed, "the officer"):
                    draft = _extended(case, i, body_new, where, extra)
                    got = _codes(ins, draft).get(text)
                    if got != "FACT_CHECK":            # FB12: still there word for word, inside a longer name
                        missed.append(f"'{text}' + '{extra}' in the {where}, body -> '{body_new}': {got}")
    assert not missed, (ins, missed)


# (g) FB10: explicit faithful and changed drafts listed in the corpus
G_CASES = [c for c in CORPUS if c.get("faithful_drafts") or c.get("changed_drafts") or c.get("checked_drafts")]


@pytest.mark.parametrize("case", G_CASES, ids=[c["id"] for c in G_CASES])
def test_g_listed_faithful_and_changed_drafts(case):
    ins = case["instruction"]
    for blocks in case.get("faithful_drafts", []):
        assert DR.missing_facts(ins, "\n".join(blocks)) == [], (ins, blocks)
    for blocks in case.get("changed_drafts", []):
        assert "FACT_MISSING" in _codes(ins, "\n".join(blocks)).values(), (ins, blocks)
    for blocks in case.get("checked_drafts", []):
        codes = _codes(ins, "\n".join(blocks))
        assert codes and set(codes.values()) == {"FACT_CHECK"}, (ins, blocks, codes)


_DESIGNATIONS = {"secretary", "collector", "minister", "commissioner", "director", "officer", "chairman", "member",
                 "registrar", "superintendent", "principal", "president", "governor", "inspector", "magistrate",
                 "tehsildar", "deputy", "joint", "additional", "chief", "state", "section", "engineer", "district",
                 "block", "assistant", "senior", "junior", "executive", "general", "special", "divisional"}


# (h) FB12 (OD-OD-6): what a faithful draft writes around a fact never makes it FACT_MISSING
def _faithful_forms(kind: str, text: str) -> list:
    forms = []
    if kind == "name":
        if _HON.match(text.split()[0]):
            forms += [f"Hon'ble {text},", f"Late {text}", f"Minister {text}", f"Hon'ble Minister {text}",
                      f"Minister of State {text} will attend.", f"MLA {text}", f"Collector {text}"]
        forms += [f"Subject: Leave of {text} sanctioned", f"Subject: Leave application of {text} received",
                  f"Leave of {text} pending"]
    elif kind == "reference":
        forms += [f"Please refer to No. {text}/dated 3.10.2026.", f"No. {text}/dt. 3.10.2026", f"No. {text}/Dt. 3.10.2026",
                  f"No. {text}/Dated 3.10.2026", f"No. {text}-W.E.F. 3.10.2026", f"No. {text}-w.e.f. 3.10.2026",
                  f"No. {text}-Date 3.10.2026", f"No. {text}dt. 3.10.2026", f"No. {text}-Copy enclosed.",
                  f"No. {text}(A)"]
    else:
        forms += [f"Subject: {text} sanctioned", f"Subject: Note on {text} received"]
        if kind == "amount" and re.fullmatch(r"[\d,]+", text):
            forms += [f"Rs. {text}.00 sanctioned", f"Rs. {text}.0 sanctioned", f"Rs. {text}.00/- sanctioned"]
        unit = re.fullmatch(r"([\d,]+) (lakhs?|crores?|thousand)", text)
        if kind == "amount" and unit:                   # FB14 R2-04: "Rs. 2.00 lakh" is "Rs. 2 lakh"
            forms += [f"Rs. {unit.group(1)}.00 {unit.group(2)} sanctioned", f"Rs. {unit.group(1)}.0 {unit.group(2)}"]
    return forms


# FB14 R2-02: designations generated from head words and qualifiers, so the rule "a titled name starts at its
# honorific" is tested generically, not by a word list
_HEAD_WORDS = ["Director", "Secretary", "Officer", "Engineer", "Collector", "Commissioner", "Superintendent",
               "Magistrate", "Minister", "Registrar", "Inspector", "Development Officer"]
_QUALIFIERS = ["", "District ", "Divisional ", "Block ", "Sub-Divisional ", "Deputy ", "Joint ", "Additional ",
               "Chief ", "Senior ", "Junior ", "Executive ", "Assistant ", "Hon'ble ", "Hon'ble Union "]
_TAILS = ["", " of Police", " of State for Finance", " General", " (Revenue)"]
_COURTESY = ["Hon'ble ", "Late ", "MLA ", "Drawing and Disbursing Officer ", "Vice Chancellor "] + [
    f"{_QUALIFIERS[i % len(_QUALIFIERS)]}{_HEAD_WORDS[i % len(_HEAD_WORDS)]}{_TAILS[i % len(_TAILS)]} "
    for i in range(36)]

@pytest.mark.parametrize("case", CORPUS, ids=IDS)
def test_h_faithful_surroundings_never_give_fact_missing(case):
    ins = case["instruction"]
    wrong = []
    for i, (kind, text) in enumerate(case["facts"]):
        for form in _faithful_forms(kind, text):
            got = _codes(ins, _blocks(case, (i, form)))
            if "FACT_MISSING" in got.values():
                wrong.append(f"{kind} '{text}' as '{form}'")
    # FB13 R2-01: the instruction side. A courtesy or designation word before a titled name does not change the facts
    for i, (kind, text) in enumerate(case["facts"]):
        if kind != "name" or not _HON.match(text.split()[0]):
            continue
        for word in _COURTESY:
            ins2 = _replace_fact(ins, text, word + text, [t for _, t in case["facts"]])
            got_facts = [[f["kind"], f["text"]] for f in DR.extract_facts(ins2)]
            if got_facts != case["facts"]:
                wrong.append(f"instruction '{word}{text}': facts {got_facts}")
            elif "FACT_MISSING" in _codes(ins2, _blocks(case)).values():
                wrong.append(f"instruction '{word}{text}': FACT_MISSING on the faithful draft")
    assert not wrong, (ins, wrong)
