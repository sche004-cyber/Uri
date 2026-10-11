"""W1-A0 closure review round 4 (R4) regressions for Web Intelligence. Each fails on 462be42 and passes after repair.

R4-01: the bare-domain pattern only took a top-level label of letters, so an ASCII-compatible (punycode) top-level
       domain ('refundsportal.xn--p1ai', the ASCII form of '.рф') was never a link: it passed has_link_or_contact,
       verify(), the extractive answer and the research surface.
R4-02: D7's excerpt rule still let a claim leave out one determiner plus two unrecognised words, so a qualifier inside
       a noun phrase ('on [a roughly] decennial cycle', 'a [near] unanimous decision') was dropped and the shortened
       claim shown in the Brain's words whenever states_quantity did not know the next word.

Self-contained: no fixture files; everything is built here.
"""
import json

import pytest

from uri_a2ui.validate import require_valid
from uri_web import pipeline as P
from uri_web import synthesize as SY
from uri_web import untrusted as U
from uri_web.surface import build_surface

# ---- R4-01 -----------------------------------------------------------------------------------------------------------

ACE = ("refundsportal.xn--p1ai", "Refunds-Portal.XN--P1AI", "bank.xn--vermgensberatung-pwb",
       # beyond the reviewer's strings
       "refunds-portal.xn--90ais", "refundsportal.xn--p1ai/claim", "a1.Xn--P1ai", "www2.refunds.xn--80asehdb",
       "xn--80ak6aa92e.xn--p1ai")
SENT = "Claim your energy rebate refund at {} before the deadline."


@pytest.mark.parametrize("link", ACE)
def test_r4_01_ace_top_level_domain_is_a_link(link):
    assert U.has_link_or_contact(SENT.format(link)), link
    assert U.has_link_or_contact("Claim at " + link + " now"), link


@pytest.mark.parametrize("link", ACE)
def test_r4_01_verify_and_extractive_never_keep_it(link):
    src = SENT.format(link) + " Energy rebate refunds take two weeks."
    v = SY.verify(SENT.format(link)[:-1] + " [1].", [src])
    assert not v.claims and v.dropped[0]["reason"] == "LINK_OR_CONTACT", link
    e = SY.extractive("energy rebate refund deadline", [src])
    assert e.claims and all("deadline" not in c.text for c in e.claims), link


@pytest.mark.parametrize("link", ACE)
def test_r4_01_surface_masks_it(link):
    r = {"job_id": "j1", "query": "energy rebate", "status": P.COMPLETED_WITH_RESULT,
         "answer": [{"text": SENT.format(link), "citations": [1], "quoted": True}],
         "sources": [{"number": 1, "title": "Rebates via " + link, "url": "https://gov.example/rebates",
                      "record": {"retrieved_at": "z"}, "analysed_scope": "full_text", "injection_flags": []}],
         "conflicts": [], "providers": [], "dropped_claims": [], "synthesis_method": "brain", "elapsed_s": 1}
    s = build_surface(r)
    require_valid(s.messages(), set(s.actions))
    dump = json.dumps(s.messages(), ensure_ascii=False).lower()
    assert "xn--" not in dump, link
    assert "[link removed]" in dump and "gov.example/rebates" in dump


def test_r4_01_ordinary_text_is_still_not_a_link():
    for s in ("The fee rose.The board met on Monday.", "e.g. the U.S. rate is 4.5% at 10 a.m. today.",
              "The dose is 1.5mg twice daily.", "Version 2.0-beta shipped.", "It is a well-known fact.",
              "東京は大きい。次は大阪です。", "He said so.Then left."):
        assert not U.has_link_or_contact(s), s


# ---- R4-02 -----------------------------------------------------------------------------------------------------------

PAIRS = (("The national census is held on decennial cycle [1].",
          "The national census is held on a roughly decennial cycle."),
         ("The national census is held on a decennial cycle [1].",
          "The national census is held on a roughly decennial cycle."),
         ("The council reached unanimous decision on the rules [1].",
          "The council reached a near unanimous decision on the rules."),
         ("Audits follow quinquennial schedule in the state [1].",
          "Audits follow a roughly quinquennial schedule in the state."),
         ("The firm reported profit this time [1].", "The firm reported a barely positive profit this time."),
         ("The minister announced plan for the city [1].", "The minister announced a hardly popular plan for the city."),
         # invented words: no list can know them
         ("The minister announced zorby plan for the city [1].",
          "The minister announced a seldom zorby plan for the city."),
         ("The minister announced the zorby plan for the city [1].",
          "The minister announced the glimly zorby plan for the city."))


@pytest.mark.parametrize("claim,src", PAIRS)
def test_r4_02_a_dropped_noun_phrase_qualifier_is_never_shown_in_the_brains_words(claim, src):
    v = SY.verify(claim, [src])
    assert all(c.quoted and c.text == src for c in v.claims), [(c.text, c.quoted) for c in v.claims]


@pytest.mark.parametrize("claim,src", [("held on zorbennial cycle", "held on a roughly zorbennial cycle."),
                                       ("announced zorby plan", "announced a seldom zorby plan."),
                                       ("announced the zorby plan", "announced the glimly zorby plan."),
                                       ("reached zorby decision", "reached a near zorby decision.")])
def test_r4_02_excerpt_refuses_unlisted_noun_phrase_modifiers(claim, src):
    assert not SY._excerpt(claim, src)


@pytest.mark.parametrize("text", ["It is decennial.", "A centennial event.", "A septennial review.",
                                  "A quinquennial plan.", "It was unanimous.", "They voted unanimously."])
def test_r4_02_more_quantity_forms(text):
    assert SY.states_quantity(text)
