"""FB4 (plan 16): a corpus-driven property test of the OD-2 fact check. For every case in
data/office_fact_corpus.json:
  (a) extract_facts gives exactly the expected facts, in order;
  (b) an identical draft never warns;
  (c) a draft that changes exactly one fact warns about that fact. The changes are made here, from the fact's kind:
      a name's surname or first name, a date's day or month, an amount's or number's digits, a number's unit or
      number word, a reference's last digit; and a digit put in front of a day, number or reference ("3" -> "13",
      "7 days" -> "17 days", "12/2026" -> "112/2026") so a fact found inside a longer token is caught.
A new case gets (b) and (c) without writing them."""
from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

from uri_office.authoring import drafting as DR

CORPUS = json.loads((Path(__file__).parent / "data" / "office_fact_corpus.json").read_text(encoding="utf-8"))["cases"]
IDS = [c["id"] for c in CORPUS]

# Independent of the module under test, so the same file runs against older commits.
_HON = re.compile(r"(?:Shri|Smt|Sh|Km|Kum|Kumari|Sushri|Dr|Mr|Mrs|Ms|Prof)\.?$")
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
        first = 1 if _HON.match(words[0]) and len(words) > 1 else 0
        last = words[-1].rstrip(".")
        out.append(("surname", " ".join(words[:-1] + [last + ("a" if last.endswith("i") else "i")])))
        if first < len(words) - 1:
            w = list(words)
            w[first] = w[first] + "a"
            out.append(("first name", " ".join(w)))
    elif kind == "date":
        m = re.search(r"\b(\d{1,2})(st|nd|rd|th)?\b", text)
        day = int(m.group(1))
        nd = day % 28 + 1
        new_day = (str(nd).zfill(len(m.group(1)))) + (_ordinal(nd) if m.group(2) else "")
        out.append(("day", text[:m.start()] + new_day + text[m.end():]))
        if day < 10 and len(m.group(1)) == 1:            # "3 November" inside "13 November" (FB1 R2-01 class)
            out.append(("day prefix", text[:m.start()] + "1" + text[m.start():]))
        mm = re.search(r"[A-Za-z]+", text.replace(m.group(0), ""))
        mon = mm.group(0)
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
            w[0] = _same_case(_NUM_SWAP[w[0].lower()], w[0])
            out.append(("number word", " ".join(w)))
    elif kind == "reference":
        out.append(("digit", _digit_up(text, last=True)))
        i = re.search(r"\d", text).start()                  # "12/2026" inside "112/2026"
        out.append(("digit prefix", text[:i] + "1" + text[i:]))
    return out


def _replace_fact(instruction: str, fact: str, new: str) -> str:
    rx = re.compile(r"(?<![\w/])" + re.escape(fact) + r"(?![\w])(?!/(?!-))")
    m = rx.search(instruction)
    if m is None:                                # "3 (three) posts": the fact is read from the cleaned text
        instruction = _BRACKET_WORDS.sub("", instruction)
        m = rx.search(instruction)
    assert m, (fact, instruction)
    return instruction[:m.start()] + new + instruction[m.end():]


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
            draft = _replace_fact(ins, text, new)
            if text not in [w["text"] for w in DR.missing_facts(ins, draft)]:
                missed.append(f"{kind} '{text}' -> {what} '{new}'")
    assert not missed, (ins, missed)
