"""W1-A0 closure review round 6 (R6) regressions, under owner decisions D13 and D14. Each R6 case fails on 29771992.

R6-01 / D13: a one-sided spaced dot ('refunds-portal .com/claim') or a dot-like separator ('·', '・', '∙', '{.}', '<.>')
       was not a link. D13: any dot-like mark, with optional spaces, or any bracketed dot or 'dot', joins two words
       into a link; a full stop followed by a space is a sentence break unless the next word is lower case and not a
       known non-domain word.
R6-02 / D14: a claim could drop a qualifier set off by commas at its edges ('Analysts said that, at most, a quintet
       of firms ...'). D14: a claim in the Brain's words runs from the sentence start (determiners aside) to its end.

Self-contained: no fixture files; everything is built here.
"""
import json

import pytest

from uri_a2ui.validate import require_valid
from uri_web import pipeline as P
from uri_web import synthesize as SY
from uri_web import untrusted as U
from uri_web.surface import build_surface

# ---- R6-01 / D13 -----------------------------------------------------------------------------------------------------

DOTTED = ("refunds-portal .com/claim", "refunds-portal .com", "refunds-portal·com", "refunds-portal・com",
          "refunds-portal∙com", "refunds-portal{.}com",
          # beyond the reviewer's strings
          "refunds-portal<.>com", "refunds-portal ⋅ com", "refunds-portal‧com", "refunds-portal•com",
          "refunds-portal{dot}com", "refunds-portal <dot> com", "refunds-portal ·com", "refunds-portal. com/claim",
          "refunds-portal. cash", "refunds-portal ･com", "refunds-portal·com", "refunds-portal⸼com")
SENT = "Claim your energy rebate refund at {} before the deadline."


@pytest.mark.parametrize("link", DOTTED)
def test_r6_01_dot_like_separator_is_a_link(link):
    assert U.has_link_or_contact(SENT.format(link)), link
    assert U.has_link_or_contact(link), link


@pytest.mark.parametrize("link", DOTTED)
def test_r6_01_verify_and_extractive_never_keep_it(link):
    src = SENT.format(link) + " Energy rebate refunds take two weeks."
    v = SY.verify(SENT.format(link)[:-1] + " [1].", [src])
    assert not v.claims and v.dropped[0]["reason"] == "LINK_OR_CONTACT", link
    e = SY.extractive("energy rebate refund deadline", [src])
    assert all("deadline" not in c.text for c in e.claims), link


@pytest.mark.parametrize("link", DOTTED)
def test_r6_01_surface_masks_it(link):
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


@pytest.mark.parametrize("text", ("The board approved the plan. The students agreed.", "No. of posts: see the table.",
                                  "Use a form, e.g. the one below.", "Version 2.5 was released.", "Mr. Smith agreed.",
                                  "The U.S. Army replied.", "See pp. 12 to 14."))
def test_d13_ordinary_sentences_are_still_not_links(text):
    assert not U.has_link_or_contact(text), text


# ---- R6-02 / D14 -----------------------------------------------------------------------------------------------------

EDGE = (("A quintet of firms control the regional market [1].",
         "Analysts said that, at most, a quintet of firms control the regional market."),
        ("A plurality of voters backed the measure [1].", "By some estimates, a plurality of voters backed the measure."),
        ("A quorum of members attended the session [1].", "A quorum of members attended the session, or nearly so."),
        ("A plurality of voters backed the measure [1].", "A plurality of voters backed the measure, at least initially."),
        # beyond the reviewer's strings
        ("A dozen firms bid [1].", "Reportedly, a dozen firms bid."),
        ("A quorum attended [1].", "A quorum attended (barely)."),
        ("The council approved the budget [1].", "The council approved the budget - in principle."))


@pytest.mark.parametrize("claim,src", EDGE)
def test_r6_02_any_edge_drop_forces_a_quote(claim, src):
    v = SY.verify(claim, [src])
    assert v.claims and all(c.quoted and c.text == src for c in v.claims), (claim, v)


@pytest.mark.parametrize("claim,src", (
        ("The council approved the budget [1].", "The council approved the budget."),
        ("Council approved the budget [1].", "The council approved the budget."),
        ("The council approved the budget [1].", "Council approved the budget."),
        ("The council approved the budget after review [1].", "The council approved the budget after a detailed review.")))
def test_d14_whole_sentences_are_still_the_brains_words(claim, src):
    v = SY.verify(claim, [src])
    assert len(v.claims) == 1 and v.claims[0].quoted is False, (claim, v)
