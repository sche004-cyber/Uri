"""W1-A0 closure review round 9 finding R9-01. Each R9 case fails on 66a4765a.

R9-01: spaced dot look-alikes were not links: U+2027 HYPHENATION POINT ('refunds-portal ‧ shop': its name had no
       dot word, so it was not dot-like), and a lone letter or digit of another script standing between two words like
       a dot (U+0660/U+06F0 Arabic-Indic zero, U+0966 Devanagari zero, U+4E36/U+2F02 dot stroke, an anusvara). Marks
       drawn as dots are now dot-like, and a lone token of one non-Latin character between two words of other scripts
       spans both neighbours.

Self-contained: no fixture files; everything is built here.
"""
import json

import pytest

from uri_a2ui.validate import require_valid
from uri_web import pipeline as P
from uri_web import synthesize as SY
from uri_web import untrusted as U
from uri_web.surface import build_surface

LINKS = ("refunds-portal ‧ cash", "refunds-portal ‧ cash/claim", "refunds-portal ‧ shop",
         "refunds-portal ٠ com/claim", "refunds-portal ٠ com", "refunds-portal ۰ com",
         "refunds-portal ० com", "refunds-portal 丶 shop", "refunds-portal ⼂ shop",
         "refunds-portal ٠ shop", "refunds-portal ं shop", "refunds-portal ့ shop",
         "refunds ‧ portal ‧ shop",
         # beyond the reviewer's strings
         "refunds-portal ๐ com", "refunds-portal ஃ com", "refunds-portal ٠٠ shop",
         "refunds-portal ⁁ shop", "refunds-portal ⁜ shop", "refunds-portal ∴ shop")
SENT = "Claim your energy rebate refund at {} before the deadline."


@pytest.mark.parametrize("link", LINKS)
def test_r9_01_is_a_link(link):
    assert U.has_link_or_contact(SENT.format(link)), link
    assert "portal" not in U.mask_links(SENT.format(link), "[link removed]"), link


@pytest.mark.parametrize("link", LINKS)
def test_r9_01_verify_and_extractive_never_keep_it(link):
    src = SENT.format(link) + " Energy rebate refunds take two weeks."
    v = SY.verify(SENT.format(link)[:-1] + " [1].", [src])
    assert not v.claims and v.dropped[0]["reason"] == "LINK_OR_CONTACT", link
    e = SY.extractive("energy rebate refund deadline", [src])
    assert all("deadline" not in c.text for c in e.claims), link


@pytest.mark.parametrize("link", LINKS)
def test_r9_01_surface_masks_it(link):
    r = {"job_id": "j1", "query": "energy rebate", "status": P.COMPLETED_WITH_RESULT,
         "answer": [{"text": SENT.format(link), "citations": [1], "quoted": True}],
         "sources": [{"number": 1, "title": "Rebates via " + link, "url": "https://gov.example/rebates",
                      "record": {"retrieved_at": "z"}, "analysed_scope": "full_text", "injection_flags": []}],
         "conflicts": [], "providers": [], "dropped_claims": [], "synthesis_method": "brain", "elapsed_s": 1}
    s = build_surface(r)
    require_valid(s.messages(), set(s.actions))
    dump = json.dumps(s.messages(), ensure_ascii=False).lower()
    assert "portal" not in dump, link
    assert "[link removed]" in dump and "gov.example/rebates" in dump


@pytest.mark.parametrize("text", (
        "Café prices rose in Zürich.", "Москва большой город.", "東京は大きい。次は大阪です。",
        "गंगटोक सिक्किम की राजधानी है।", "서울 中 부산 사이", "The rate is 4.5% at 10 a.m. today.",
        "Vitamin C and vitamin D help.", "Room 5 is open.", "He said “yes” – twice…"))
def test_r9_01_ordinary_text_is_not_a_link(text):
    assert not U.has_link_or_contact(text), text
