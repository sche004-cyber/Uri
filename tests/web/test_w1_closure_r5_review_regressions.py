"""W1-A0 closure review round 5 (R5) regressions for Web Intelligence. Each fails on f5a5b8e and passes after repair.

R5-01: the bare-domain lookarounds treated '_' and '-' as part of the surrounding word, so a link wrapped in
       underscores or hyphens ('_refunds-portal.com_', markdown emphasis) was never a link.
R5-02: D7's excerpt rule checked only the gaps between matched words, so a claim could drop a leading qualifier
       ('[Less than] a plurality of voters backed the measure') or a trailing one, and be shown in the Brain's words.

Self-contained: no fixture files; everything is built here.
"""
import json

import pytest

from uri_a2ui.validate import require_valid
from uri_web import pipeline as P
from uri_web import synthesize as SY
from uri_web import untrusted as U
from uri_web.surface import build_surface

# ---- R5-01 -----------------------------------------------------------------------------------------------------------

WRAPPED = ("_refunds-portal.com_", "refunds-portal.com_", "_refunds-portal.com", "-refunds-portal.com",
           "__refunds.cash__", "refunds.com-", "_refundsportal.xn--p1ai_",
           # beyond the reviewer's strings
           "*_refunds-portal.com_*", "~refunds-portal.com~", "_refunds-portal.com/claim_", "--refunds.net--",
           "_www.refunds-portal.org_")
SENT = "Claim your energy rebate refund at {} before the deadline."


@pytest.mark.parametrize("link", WRAPPED)
def test_r5_01_wrapped_domain_is_a_link(link):
    assert U.has_link_or_contact(SENT.format(link)), link
    assert U.has_link_or_contact(link), link
    masked = U.mask_links(SENT.format(link), "[link removed]")
    assert "refunds" not in masked.lower(), (link, masked)


@pytest.mark.parametrize("link", WRAPPED)
def test_r5_01_verify_and_extractive_never_keep_it(link):
    src = SENT.format(link) + " Energy rebate refunds take two weeks."
    v = SY.verify(SENT.format(link)[:-1] + " [1].", [src])
    assert not v.claims and v.dropped[0]["reason"] == "LINK_OR_CONTACT", link
    e = SY.extractive("energy rebate refund deadline", [src])
    assert all("deadline" not in c.text for c in e.claims), link


@pytest.mark.parametrize("link", WRAPPED)
def test_r5_01_surface_masks_it(link):
    r = {"job_id": "j1", "query": "energy rebate", "status": P.COMPLETED_WITH_RESULT,
         "answer": [{"text": SENT.format(link), "citations": [1], "quoted": True}],
         "sources": [{"number": 1, "title": "Rebates via " + link, "url": "https://gov.example/rebates",
                      "record": {"retrieved_at": "z"}, "analysed_scope": "full_text", "injection_flags": []}],
         "conflicts": [], "providers": [], "dropped_claims": [], "synthesis_method": "brain", "elapsed_s": 1}
    s = build_surface(r)
    require_valid(s.messages(), set(s.actions))
    dump = json.dumps(s.messages(), ensure_ascii=False).lower()
    assert "refunds" not in dump.replace("energy rebate refund", ""), link
    assert "[link removed]" in dump and "gov.example/rebates" in dump


@pytest.mark.parametrize("text", ("A plain sentence with snake_case words.", "Self-service kiosks open at noon.",
                                  "The well-known rose.The end."))
def test_r5_01_ordinary_text_is_still_not_a_link(text):
    assert not U.has_link_or_contact(text), text

# ---- R5-02 -----------------------------------------------------------------------------------------------------------

EDGE = (("A plurality of voters backed the measure [1].", "Less than a plurality of voters backed the measure."),
        ("A quorum of members attended the vote [1].", "Well short of a quorum of members attended the vote."),
        ("A quintet of firms control the national market [1].",
         "Fewer than a quintet of firms control the national market."),
        # beyond the reviewer's strings: trailing qualifiers, and a clause word is no clause boundary
        ("The council approved the budget [1].", "The council approved the budget only in part."),
        ("The board backed the plan [1].", "The board backed the plan by a whisker."),
        ("A cohort of students passed [1].", "Not even a cohort of students passed."),
        ("A majority supported it [1].", "Far more than a majority supported it."))


@pytest.mark.parametrize("claim,src", EDGE)
def test_r5_02_edge_qualifier_forces_a_quote(claim, src):
    v = SY.verify(claim, [src])
    assert all(c.quoted for c in v.claims), (claim, v)
    assert all(c.text == src for c in v.claims), (claim, v)


@pytest.mark.parametrize("claim,src", (
        ("The district board approved the new hostel rules [1].",
         "The district board approved the new hostel rules."),
        ("The district board approved the new hostel rules [1].",
         "On Monday, the district board approved the new hostel rules."),
        ("The district board approved the new hostel rules [1].",
         "The district board approved the new hostel rules; students welcomed them."),
        ("District board approved the new hostel rules [1].",
         "The district board approved the new hostel rules.")))
def test_r5_02_whole_clauses_are_still_the_brains_words(claim, src):
    v = SY.verify(claim, [src])
    assert len(v.claims) == 1 and v.claims[0].quoted is False, (claim, v)
