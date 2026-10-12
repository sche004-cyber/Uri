"""W1-A0 closure review round 3 (R3) regressions for Web Intelligence.

R3-01: the link detector failed open: an ASCII 'label.Tld' was a link only if its TLD was all-lower, all-upper or on
       a hard-coded list, so real mixed-case gTLDs ('Refundsportal.Cash', '.Lol', '.CaSh'), spaced defangs
       ('portal [.] com', 'portal dot com') and phone numbers passed has_link_or_contact, verify(), the extractive
       answer and the research surface.
R3-02: D7's excerpt rule let a claim skip up to two unrecognised source words, so a qualifier next to a quantity
       word the list did not know ('nearly doubling', 'possibly halving', 'barely rose') was dropped and the
       shortened claim shown in the Brain's words.

Self-contained: no fixture files; everything is built here.
"""
import json

import pytest

from uri_a2ui.validate import require_valid
from uri_web import pipeline as P
from uri_web import synthesize as SY
from uri_web import untrusted as U
from uri_web.surface import build_surface

# ---- R3-01 -----------------------------------------------------------------------------------------------------------

LINKS = ("Refundsportal.Cash", "refundsportal.Lol", "refundsportal.CaSh", "Refundsportal.Exchange",
         "Refundsportal.Deals", "refundsportal [.] com", "refundsportal dot com", "1800 555 0199",
         # beyond the reviewer's strings
         "refundsportal ( . ) com", "refundsportal [ dot ] com", "refundsportal . com", "Refundsportal.Zorbq",
         "+44 20 7946 0958", "1-800-555-0199", "555.123.4567")
SENT = "Claim your energy rebate refund at {} before the deadline."


@pytest.mark.parametrize("link", LINKS)
def test_r3_01_detector_fails_closed(link):
    assert U.has_link_or_contact(SENT.format(link)), link


@pytest.mark.parametrize("link", LINKS)
def test_r3_01_verify_and_extractive_never_keep_it(link):
    src = SENT.format(link) + " Energy rebate refunds take two weeks."
    v = SY.verify(SENT.format(link)[:-1] + " [1].", [src])
    assert not v.claims and v.dropped[0]["reason"] == "LINK_OR_CONTACT", link
    e = SY.extractive("energy rebate refund deadline", [src])
    assert e.claims and all("deadline" not in c.text for c in e.claims), link


@pytest.mark.parametrize("link", LINKS)
def test_r3_01_surface_masks_the_whole_span(link):
    r = {"job_id": "j1", "query": "energy rebate", "status": P.COMPLETED_WITH_RESULT,
         "answer": [{"text": SENT.format(link), "citations": [1], "quoted": True}],
         "sources": [{"number": 1, "title": "Rebates via " + link, "url": "https://gov.example/rebates",
                      "record": {"retrieved_at": "z"}, "analysed_scope": "full_text", "injection_flags": []}],
         "conflicts": [], "providers": [], "dropped_claims": [], "synthesis_method": "brain", "elapsed_s": 1}
    s = build_surface(r)
    require_valid(s.messages(), set(s.actions))
    dump = json.dumps(s.messages(), ensure_ascii=False)
    for bad in ("efundsportal", "0199", "7946", "4567"):
        assert bad not in dump, (link, bad)
    assert "[link removed]" in dump and "gov.example/rebates" in dump


def test_r3_01_ordinary_text_is_still_not_a_link():
    for s in ("The fee rose.The board met on Monday.", "e.g. the U.S. rate is 4.5% at 10 a.m. today.",
              "Ph.D students pay less.", "He said so.Then left.", "Café prices rose.Été is busy.",
              "価格は100円。安い。", "東京は大きい。次は大阪です。", "It opened on 2024-10-11 in the city.",
              "Fees rose in 2019-2020.", "It was dated 11.10.2026.", "About 1,234,567 people live there."):
        assert not U.has_link_or_contact(s), s


# ---- R3-02 -----------------------------------------------------------------------------------------------------------

PAIRS = (("Rents in the capital are doubling under the new rules [1].",
          "Rents in the capital are nearly doubling under the new rules."),
         ("Rents in the capital are halving under the new rules [1].",
          "Rents in the capital are possibly halving under the new rules."),
         ("Rents in the capital quintupled under the new rules [1].",
          "Rents in the capital almost quintupled under the new rules."),
         ("Rents in the capital sextupled under the new rules [1].",
          "Rents in the capital barely sextupled under the new rules."),
         ("Inspections in the capital are biweekly under the new rules [1].",
          "Inspections in the capital are roughly biweekly under the new rules."),
         ("Rents in the capital are doubling under the new rules [1].",
          "Rents in the capital are about doubling under the new rules."),
         ("Rents in the capital rose under the new rules [1].", "Rents in the capital barely rose under the new rules."),
         ("The hostel fee is waived for students [1].", "The hostel fee is rarely waived for students."))


@pytest.mark.parametrize("claim,src", PAIRS)
def test_r3_02_a_dropped_qualifier_is_never_shown_in_the_brains_words(claim, src):
    v = SY.verify(claim, [src])
    assert all(c.quoted and c.text == src for c in v.claims), [(c.text, c.quoted) for c in v.claims]


@pytest.mark.parametrize("claim,src", [("Rents are zorbing under the rules", "Rents are nearly zorbing under the rules."),
                                       ("Rents are zorbing", "Rents are about zorbing."),
                                       ("The fee is glorped", "The fee is seldom glorped."),
                                       ("Rents zorbed in town", "Rents reportedly zorbed in town.")])
def test_r3_02_excerpt_does_not_depend_on_the_quantity_list(claim, src):
    # Invented words: no word list can know them, so only the structural rule can refuse the skip.
    assert not SY.states_quantity(src)
    assert not SY._excerpt(claim, src)


def test_r3_02_noun_phrase_modifiers_may_still_be_left_out():
    assert SY._excerpt("approved the rules after consultation", "approved the rules after a long public consultation.")
    assert SY._excerpt("The bridge reopened after the repairs", "The bridge reopened after repairs.")


@pytest.mark.parametrize("text", ["Rents are doubling.", "Fees are halving.", "Rents tripled.", "Rents quintupled.",
                                  "Rents sextupled.", "Inspections are biweekly.", "It is bimonthly.",
                                  "Reviews are semiannual.", "It is triennial.", "Costs multiplied.", "It is 3‰.",
                                  "Levels are high in ppm.", "It rose a few pct."])
def test_r3_02_more_quantity_forms(text):
    assert SY.states_quantity(text)
