"""W1-A0 closure review round 26 finding R26-01. Each R26 link case fails on 74909458.

R26-01: normalise() applies NFKC, which composes a letter and its combining mark into one precomposed letter
        ('ćom' -> 'ćom'), so removing the marks no longer restored the ending. An ending is now compared
        with the marks removed from its decomposed form, then recomposed.

Self-contained: no fixture files; everything is built here.
"""
import json

import pytest

from uri_web import surface as S
from uri_web import synthesize as SY
from uri_web import untrusted as U

LINKS = ("refunds-portal ćom/claim", "refunds-portal ćom", "refunds-portal cóm",
         "refunds-portal òrg/claim", "refunds-portal ~ òrg", "refunds-portal ~ ṣhop",
         "refunds-portal ~ śhop", "refunds-portal ~ shóp", "refunds-portal * shöp/claim",
         "refunds-portal ~ cásh", "refunds-portal ~ ѐю")
SENT = "Claim your energy rebate refund at {} before the deadline."


@pytest.mark.parametrize("link", LINKS)
def test_r26_01_is_a_link_and_the_name_is_masked(link):
    text = SENT.format(link)
    assert U.has_link_or_contact(text), link
    assert "refunds-portal" not in U.mask_links(text, "[link removed]"), link


@pytest.mark.parametrize("link", LINKS)
def test_r26_01_verify_and_extractive_never_keep_it(link):
    src = SENT.format(link) + " Energy rebate refunds take two weeks."
    v = SY.verify(SENT.format(link)[:-1] + " [1].", [src])
    assert not v.claims and v.dropped[0]["reason"] == "LINK_OR_CONTACT", link
    e = SY.extractive("energy rebate refund deadline", [src])
    assert all("deadline" not in c.text for c in e.claims), link


@pytest.mark.parametrize("link", ("refunds-portal ćom/claim", "refunds-portal ~ ṣhop",
                                  "refunds-portal òrg/claim"))
def test_r26_01_research_surface_never_shows_it(link):
    t = SENT.format(link)
    s = S.build_surface({"job_id": "j1", "status": "COMPLETED_WITH_RESULT", "query": "q",
                         "answer": [{"text": t, "citations": [1], "quoted": True}],
                         "conflicts": [{"a": 1, "b": 2, "statement_a": t, "statement_b": "x"}],
                         "sources": [{"number": 1, "title": t, "url": "https://example.org/a", "record": {}}]})
    blob = json.dumps(s.__dict__ if hasattr(s, "__dict__") else str(s), default=str, ensure_ascii=False)
    assert "refunds-portal" not in blob, link


@pytest.mark.parametrize("text", ("Je pense que ça va bien.", "Le café est ouvert à Orléans.",
                                  "Él está aquí con José.", "Il dit: ça.",
                                  "Bạn có khỏe không?", "Ёлка в лесу.",
                                  "A plain English sentence."))
def test_r26_01_ordinary_accented_text_is_not_a_link(text):
    assert not U.has_link_or_contact(text), text
