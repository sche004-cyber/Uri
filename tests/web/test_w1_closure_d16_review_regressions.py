"""W1-A0 closure review round 10 finding R10-01, repaired under owner decision D16. Each R10/D16 case fails on 7b1252f7.

R10-01: a look-alike dot from a listed script, repeated or mixed ('portal ٠ ٠ com/claim', 'portal 丶 丶 shop',
        'portal ٠۰ shop'), passed every check. D16 ("the separator does not matter"): a name, then anything, then a
        real top-level domain from the complete list (uri_web/tld_list.py) is a link; letters spelt out with spaces
        are joined first ('c o m', 'c om'). Only ordinary prose between the words limits this to the core domains.

Self-contained: no fixture files; everything is built here.
"""
import json

import pytest

from uri_a2ui.validate import require_valid
from uri_web import pipeline as P
from uri_web import synthesize as SY
from uri_web import untrusted as U
from uri_web.surface import build_surface

LINKS = ("refunds-portal ٠ ٠ com/claim", "refunds-portal 丶 丶 shop", "refunds-portal ٠۰ shop",
         # spelt out (formerly D15 residual risk)
         "refunds-portal . c om/claim", "refunds-portal . c o m", "refunds-portal c o m", "refunds-portal c o m/claim",
         # beyond the reviewer's strings: any separator before any real ending
         "refunds-portal ~ cash", "refunds-portal ˌ shop", "refunds-portal * * claims", "refunds-portal ^ in",
         "refunds-portal 〇 xyz", "refunds-portal, com", "refunds-portal (dot) shop")
SENT = "Claim your energy rebate refund at {} before the deadline."


def test_d16_the_ending_list_is_complete_enough():
    from uri_web.tld_list import TOP_LEVEL_DOMAINS
    assert len(TOP_LEVEL_DOMAINS) > 1400
    assert {"com", "in", "shop", "cash", "xyz", "gov", "рф", "भारत", "中国"} <= TOP_LEVEL_DOMAINS


@pytest.mark.parametrize("link", LINKS)
def test_d16_is_a_link(link):
    assert U.has_link_or_contact(SENT.format(link)), link
    assert "portal" not in U.mask_links(SENT.format(link), "[link removed]"), link


@pytest.mark.parametrize("link", LINKS)
def test_d16_verify_and_extractive_never_keep_it(link):
    src = SENT.format(link) + " Energy rebate refunds take two weeks."
    v = SY.verify(SENT.format(link)[:-1] + " [1].", [src])
    assert not v.claims and v.dropped[0]["reason"] == "LINK_OR_CONTACT", link
    e = SY.extractive("energy rebate refund deadline", [src])
    assert all("deadline" not in c.text for c in e.claims), link


@pytest.mark.parametrize("link", LINKS)
def test_d16_surface_masks_it(link):
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
        "Gangtok, in Sikkim, is the capital.", "Sikkim (2020) in Ravangla.", "The board met. In 2020 it changed.",
        "The U.S. Army replied.", "NIT Sikkim (सिक्किम) in Ravangla.", "Rules for the shop, one by one.",
        "Students, college and staff attended.", "He bought 5 shares, 10 toys.", "Options a, b, c apply.",
        "Fees: Rs 5,000 per year; see the table.", "The Ltd. Co. was formed.", "Profit (net) rose.",
        "Profit before tax rose by 4.5% to Rs 3.2 lakh.", "I am a co founder.", "Home > News > Energy",
        "Plan A or plan B.", "A plain sentence with snake_case words.", "The rate is 4.5% at 10 a.m. today."))
def test_d16_ordinary_text_is_not_a_link(text):
    assert not U.has_link_or_contact(text), text
