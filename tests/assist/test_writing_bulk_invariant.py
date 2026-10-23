"""Bulk-accept invariant (driver WRITING-INTELLIGENCE-r4 BLOCKED RETRY_LIMIT after 7 rounds of case-by-case variants).

"Accept all corrections" in the UI applies exactly the items with class 'correction', confidence other than 'guess'
and a source other than the Brain (writing_assist.dart). Whatever the input, applying that set may change only:
letter case, whitespace, a repeated word, doubled punctuation, a space before punctuation, and a/an. It may never
change a word, a number, a name, a reference, a link or any other punctuation. This test checks the invariant on
the corpus, the reviewers' probe sentences and Brain answers that change meaning, instead of listing variants.
"""
from __future__ import annotations

import json
import os
import re
from pathlib import Path

import pytest

from uri_assist import writing as W
from uri_operational_intelligence import brain_client as BC

CORPUS = [x["text"] for x in json.loads((Path(__file__).parent / "data" / "writing_corpus.json")
                                         .read_text(encoding="utf-8"))["items"]]
PROBES = [
    "I can't approve the leave of Shri Sharma. We received nothing. Send three copies by 5 january.",
    "as per clause (ii) of rule 4 and Section 5(a) applies.", "The leave of Mrs Gupta is sanctioned.",
    "forward to mehta for comments", "Transfer the file from Delhi to Mumbai.", "Payment is due on 5 June.",
    "please confirm the date; report weekly; permission is granted.", "the officer was present",
    "Ref. 12/3/2026 applies.", "Ref. 12.3 applies. They was informed.", "Ref. 12, 2026 applies. They was informed.",
    "Ref. 12/3 is pending. Annexure A is attached. Annexure a is not.", "i see https://example.gov.in/a,b for details.",
    "Mail admin.section@example.gov.in now.", "No. 12/3/2024-Estt. dated 5.6.2024.", "i forwarded the file to mehta.",
    "i  recieve the the letter , on tuesday!!  thier work.", "sub-clause i, ii and iii apply. see item i above.",
]
# Brain answers that change meaning in the ways reviewers found; the bulk set must never carry them.
BRAIN = {
    PROBES[0]: "I can approve the leave of Shri Sharma. We received something. Send two copies by 5 june.",
    PROBES[1]: "as per clause (iii) of rule 4 and Section 5(an) applies.",
    PROBES[2]: "The leave of Mr Gupta is sanctioned.",
    PROBES[3]: "forward to mehra for comments",
    PROBES[4]: "Transfer the file to Delhi from Mumbai.",
    PROBES[5]: "Payment is due by 5 June.",
    PROBES[6]: "please conform the date; report weakly; permission is grantee.",
    PROBES[7]: "the officers were present",
    PROBES[8]: "Ref. 12-3-2026 applies.",
    PROBES[9]: "Ref. 12:3 applies. They were informed.",
    PROBES[10]: "Ref. 12: 2026 applies. They were informed.",
    PROBES[11]: "Ref: 12/3 is pending. Annexure An is attached. Annexure an is not.",
}


class FakeBrain:
    base_url = "http://127.0.0.1:18080"

    def __init__(self, text):
        self.text = text

    def stream_chat(self, body, cancel=None, deadlines=None):
        return BC.CallResult(status=BC.COMPLETE, text=json.dumps({"status": "ok", "message": "", "text": self.text}),
                             total_s=0.1)


def bulk(items):
    """The UI's Accept all rule (writing_assist.dart), non-overlapping from the start."""
    out, end = [], -1
    for s in sorted(items, key=lambda x: (x["start"], x["end"])):
        if s["class"] == "correction" and s.get("confidence") != "guess" and s["source"] != "brain" and s["start"] >= end:
            out.append({"start": s["start"], "end": s["end"], "original": s["original"],
                        "replacement": s["replacements"][0] if s["replacements"] else ""})
            end = s["end"]
    return out


def norm(t: str) -> str:
    t = t.lower()
    t = re.sub(r"\b(an?)\b", "a", t)                       # a / an
    t = re.sub(r"([,;:!?])\1+", r"\1", t)                  # doubled punctuation
    t = re.sub(r"(?<![.\w])(\w+)\.\.(?!\.)", r"\1.", t)
    t = re.sub(r"\s+([,;:!?.])(?=\s|$)", r"\1", t)          # space before punctuation
    t = re.sub(r"\b(\w+)(\s+\1\b)+", r"\1", t)              # repeated word
    return re.sub(r"\s+", " ", t).strip()


@pytest.mark.parametrize("text", CORPUS + PROBES)
def test_bulk_accept_of_deterministic_checks_changes_nothing_but_form(text):
    res = W.check(text)                                    # real Windows spelling where available
    after = W.apply(text, bulk(res["suggestions"]))["text"]
    assert norm(after) == norm(text), (text, after, [(s["original"], s["replacements"][:1], s["class"],
                                                      s.get("confidence"), s["source"]) for s in res["suggestions"]])


@pytest.mark.parametrize("text", list(BRAIN))
def test_no_brain_item_is_ever_in_the_bulk_set(text):
    r = W.proofread(text, client=FakeBrain(BRAIN[text]))
    assert bulk(r["suggestions"]) == []
    # and every change that alters a word, number, reference or punctuation is labelled rewrite
    for s in r["suggestions"]:
        rep = s["replacements"][0]
        agreement = W._words(s["original"]) and len(W._words(s["original"])) == len(W._words(rep)) and all(
            W._swap(a, b) for a, b in zip(W._words(s["original"]), W._words(rep))) and \
            not re.search(r"[^\w\s']", s["original"] + rep)
        if norm(s["original"]) != norm(rep) and not agreement:
            assert s["class"] == "rewrite", (text, s["original"], rep, s["class"])


@pytest.mark.skipif(os.name != "nt", reason="Windows Spell Checking API")
def test_windows_word_replacements_are_never_bulk():
    res = W.check("forward to mehta and recieve the thier report from karmachari")
    words = [s for s in res["suggestions"] if s["source"] == "windows_spell" and s["kind"] == "spelling"]
    assert words and not any(s in bulk(res["suggestions"]) for s in words)
    assert all(s["class"] == "rewrite" or s.get("confidence") == "guess" for s in words)
