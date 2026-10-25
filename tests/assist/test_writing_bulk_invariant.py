"""Writing Intelligence safety properties after the bulk accept was removed (plan 16 WI-4, reviews FB3-FB5).

History: driver r4 (Codex, 7 rounds) and fallback reviews FB3, FB4 and FB5 showed that for free text no bulk-apply
set is safe by construction (doubled particles, letter case of units and acronyms, references, paths, names). The
strip therefore has no "Accept all corrections"; every suggestion is applied by its own Accept after the owner saw
it (writing_assist.dart; Flutter test 'FB5: there is no Accept all ...'). Bringing back a narrow bulk accept is the
owner's decision OD-WI-3.

What stays checked here, with every probe from the reviews:
1. Any Brain change that touches a number, date, name, negation, reference or punctuation is labelled `rewrite`
   ("May change meaning"), never a plain `correction`.
2. Windows word replacements are `rewrite` or `guess` (Windows cannot tell a name from a typo).
3. No suggestion of any kind touches a link, e-mail address, path, key=value token, ratio or time notation, file or
   command token, or a word with an inner capital.
"""
from __future__ import annotations

import json
import os
import re

import pytest

from uri_assist import writing as W
from uri_operational_intelligence import brain_client as BC

# Brain answers that change meaning in the ways reviewers found (FB1-FB5, Codex r4).
BRAIN = {
    "I can't approve the leave of Shri Sharma. We received nothing. Send three copies by 5 january.":
        "I can approve the leave of Shri Sharma. We received something. Send two copies by 5 june.",
    "as per clause (ii) of rule 4 and Section 5(a) applies.": "as per clause (iii) of rule 4 and Section 5(an) applies.",
    "The leave of Mrs Gupta is sanctioned.": "The leave of Mr Gupta is sanctioned.",
    "forward to mehta for comments": "forward to mehra for comments",
    "Transfer the file from Delhi to Mumbai.": "Transfer the file to Delhi from Mumbai.",
    "Payment is due on 5 June.": "Payment is due by 5 June.",
    "please confirm the date; report weekly; permission is granted.":
        "please conform the date; report weakly; permission is grantee.",
    "the officer was present": "the officers were present",
    "Ref. 12/3/2026 applies.": "Ref. 12-3-2026 applies.",
    "Ref. 12.3 applies. They was informed.": "Ref. 12:3 applies. They were informed.",
    "Ref. 12, 2026 applies. They was informed.": "Ref. 12: 2026 applies. They were informed.",
    "Ref. 12/3 is pending. Annexure A is attached.": "Ref: 12/3 is pending. Annexure An is attached.",
}
AGREEMENT = [frozenset(x) for x in ({"is", "are"}, {"was", "were"}, {"has", "have"}, {"do", "does"})]

# (text, protected substring): no suggestion may overlap the substring.
PROTECTED = [
    ("i see https://example.gov.in/a,b for details.", "https://example.gov.in/a,b"),
    ("Mail admin.section@example.gov.in now.", "admin.section@example.gov.in"),
    ("Send the file to ramesh.Kumar@nic.in today.", "ramesh.Kumar@nic.in"),
    ("Set PATH=C:\\bin;D:\\tools now.", "PATH=C:\\bin;D:\\tools"),
    ("Server=dbhost;Database=uri is the setting.", "Server=dbhost;Database=uri"),
    ("In the ratio 60 : 40 the cost is shared.", "60 : 40"),
    ("Time 10 : 30 hrs is fixed.", "10 : 30"),
    ("Copy it with cp a.txt .", "a.txt ."),
    ("The reading was taken. pH is 7.2 in the tank.", "pH"),
    ("Done. eKYC is required.", "eKYC"),
    ("No. 12/3/2024-Estt. dated 5.6.2024.", "12/3/2024-Estt. dated"),
    # review FB5 R7-04 / R7-05
    ("See the attached file. report.pdf has the figures.", "report.pdf"),
    ("Visit the site. example.com has it.", "example.com"),
    ("Use --fields name,age for the export.", "name,age"),
    ("Use the :: operator in C.", "::"),
    ("Rows A..D are filled.", "A..D"),
]


class FakeBrain:
    base_url = "http://127.0.0.1:18080"

    def __init__(self, text):
        self.text = text

    def stream_chat(self, body, cancel=None, deadlines=None):
        return BC.CallResult(status=BC.COMPLETE, text=json.dumps({"status": "ok", "message": "", "text": self.text}),
                             total_s=0.1)


def _words(s):
    return re.findall(r"\w+(?:['’]\w+)*", s.lower())


@pytest.mark.parametrize("text", list(BRAIN))
def test_meaning_changing_brain_edits_are_labelled_rewrite(text):
    r = W.proofread(text, client=FakeBrain(BRAIN[text]))
    assert r["suggestions"], text
    for s in r["suggestions"]:
        o, rep = s["original"], s["replacements"][0]
        ow, rw = _words(o), _words(rep)
        agreement = (ow and len(ow) == len(rw) and not re.search(r"[^\w\s']", o + rep)
                     and all(a == b or any(a in g and b in g for g in AGREEMENT) for a, b in zip(ow, rw)))
        if o.strip().lower() != rep.strip().lower() and not agreement:
            assert s["class"] == "rewrite", (text, o, rep, s["class"])


@pytest.mark.skipif(os.name != "nt", reason="Windows Spell Checking API")
def test_windows_word_replacements_are_rewrite_or_guess():
    res = W.check("forward to mehta and recieve the thier report from karmachari")
    words = [s for s in res["suggestions"] if s["source"] == "windows_spell" and s["kind"] == "spelling"]
    assert words and all(s["class"] == "rewrite" or s.get("confidence") == "guess" for s in words)


@pytest.mark.parametrize("text,keep", PROTECTED)
def test_no_suggestion_touches_protected_tokens(text, keep):
    a = text.index(keep)
    b = a + len(keep)
    for s in W.check(text)["suggestions"]:
        inside = a < s["end"] and s["start"] < b if s["start"] != s["end"] else a < s["start"] < b
        assert not inside, (text, keep, s["original"], s["replacements"], s["source"])
