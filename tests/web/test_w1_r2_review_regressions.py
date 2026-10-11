"""W1-A0 closure review round 2 (R2) regressions for Web Intelligence.

R2-01: link forms the R1-01 detector missed (title-case TLD, zero-width space, IDN host, soft hyphen, ideographic full
       stop, Cyrillic look-alike in the TLD) passed has_link_or_contact, verify(), the extractive answer, a
       ResearchJob(use_brain=False) and the research surface, which also showed the invisible characters.
R2-02: D7 rested on a quantity-word list: the order test was a subsequence test, so a claim joining the subject of
       one clause to the quantity (or any predicate) of another was shown in the Brain's words.

Self-contained: helpers come from test modules that existed before the repair; pages are built here.
"""
import json

import pytest

from uri_a2ui.validate import require_valid
from uri_web import pipeline as P
from uri_web import synthesize as SY
from uri_web import untrusted as U
from uri_web.surface import build_surface

from .d7_invariant import only_source_quotes
from .test_w1_pipeline_citations_injection import FakeProvider, page, web

# ---- R2-01 -----------------------------------------------------------------------------------------------------------

LINKS = ("refunds-portal.Net/claim", "refunds-portal​.net/claim", "refunds-pörtal.net",
         "refunds­portal.n­et", "refunds-portal。net/claim", "refunds-portal.сom",
         # beyond the reviewer's strings: other invisible characters, dots, cases and scripts
         "refunds-portal.n⁠et/claim", "refunds-portal﻿.org", "refunds-portal｡net", "refunds-portal.COM",
         "refundsportal.Info", "refunds-portal.Xyzq/claim", "refunds-portal.онлайн",
         "refunds-portal.nét/claim", "refunds-portal.n️et/claim", "refunds-pоrtal.nеt",
         "рефанд.рф/claim")
HOSTEL = "Hostel fee refunds are handled by the bursar, see {} for the hostel fee form."
INVISIBLE = ("​", "­", "⁠", "﻿", "️", "。", "｡")


@pytest.mark.parametrize("link", LINKS)
def test_r2_01_detector_sees_every_link_form(link):
    assert U.has_link_or_contact(HOSTEL.format(link))


def test_r2_01_ordinary_sentences_are_still_not_links():
    for s in ("The fee rose.The board met on Monday.", "e.g. the U.S. rate is 4.5% at 10 a.m. today.",
              "Ph.D students pay less.", "Hostel fee refunds are handled by the bursar.", "He said so.Then left.",
              "価格は100円。安い。",
              "東京は大きい。次は大阪です。",
              "Café prices rose.Été is busy."):
        assert not U.has_link_or_contact(s), s


@pytest.mark.parametrize("link", LINKS)
def test_r2_01_verify_and_extractive_never_keep_a_link(link):
    src = HOSTEL.format(link) + " Hostel fee refunds take two weeks to process."
    v = SY.verify(HOSTEL.format(link) + " [1]", [src])
    assert not v.claims and v.dropped[0]["reason"] == "LINK_OR_CONTACT"
    e = SY.extractive("hostel fee refunds bursar form", [src])
    assert all("rtal" not in c.text and "рф" not in c.text for c in e.claims)


def test_r2_01_surface_masks_every_link_form_and_shows_no_invisible_characters():
    answer = [{"text": HOSTEL.format(link), "citations": [1], "quoted": False} for link in LINKS]
    r = {"job_id": "j1", "query": "hostel refunds", "status": P.COMPLETED_WITH_RESULT, "answer": answer[:8],
         "sources": [{"number": 1, "title": "Refunds at " + LINKS[1], "url": "https://uni.example/fees",
                      "record": {"retrieved_at": "z"}, "analysed_scope": "full_text", "injection_flags": []}],
         "conflicts": [{"a": 1, "b": 1, "statement_a": HOSTEL.format(link), "statement_b": "Fees fell."}
                       for link in LINKS[8:11]],
         "providers": [], "dropped_claims": [], "synthesis_method": "brain", "elapsed_s": 1}
    s = build_surface(r)
    require_valid(s.messages(), set(s.actions))
    dump = json.dumps(s.messages(), ensure_ascii=False)
    for bad in ("rtal", "сom", "Xyzq") + INVISIBLE:
        assert bad not in dump, repr(bad)
    assert "uni.example/fees" in dump and "Hostel fee refunds are handled by the bursar, see [link removed] for" in dump
    for link in LINKS[8:]:
        s = build_surface({**r, "answer": [{"text": HOSTEL.format(link), "citations": [1], "quoted": True}],
                           "conflicts": []})
        dump = json.dumps(s.messages(), ensure_ascii=False)
        assert "rtal" not in dump and "рф" not in dump, link


@pytest.mark.parametrize("link_html", ["refunds-portal&#8203;.net/claim", "refunds-portal.Net/claim",
                                       "refunds-p&#246;rtal.net/claim", "refunds&shy;portal.n&shy;et",
                                       "refunds-portal&#12290;net/claim", "refunds-portal.&#1089;om"])
def test_r2_01_research_job_end_to_end_never_shows_the_link(link_html):
    body = (f"<article><p>Hostel fee refunds are handled by the bursar, see {link_html} for the hostel fee refund "
            f"form today.</p><p>Hostel fee refunds take two weeks to process after the form is received.</p></article>")
    f, _ = web({("uni.example", "/fees"): page(body)})
    job = P.ResearchJob(P.ResearchRequest("hostel fee refund form", use_brain=False), fetcher=f,
                        providers=[FakeProvider([("Fees", "https://uni.example/fees", "")])])
    r = job.run()
    assert r.status == P.COMPLETED_WITH_RESULT
    texts = [c["text"] for c in r.to_dict()["answer"]]
    assert texts and all("rtal" not in t and "bursar, see" not in t for t in texts), texts
    s = build_surface(r.to_dict())
    require_valid(s.messages(), set(s.actions))
    dump = json.dumps(s.messages(), ensure_ascii=False)
    for bad in ("rtal", "сom") + INVISIBLE:
        assert bad not in dump, repr(bad)


# ---- R2-02 -----------------------------------------------------------------------------------------------------------

RECOMBINED = [
    ("The tax in Texas was cut by an order of magnitude [1].",
     "The tax in Texas was cut by basis points while the levy in Ohio was cut by an order of magnitude."),
    ("Wages in Texas rose hourly [1].", "Wages in Texas rose quarterly while rents in Ohio rose hourly."),
    ("The levy in Texas was paid over a fortnight [1].",
     "The levy in Texas was paid over a week while the tax in Ohio was paid over a fortnight."),
    ("Rents in Texas peaked in the nineties [1].",
     "Rents in Texas peaked in the eighties while wages in Ohio peaked in the nineties."),
    # no quantity at all: only the structure can tell
    ("The tax in Texas was cut sharply [1].", "The tax in Texas was cut gently while the levy in Ohio was cut sharply."),
    ("The tax in Texas was cut sharply [1].", "The tax in Texas fell gently, the levy in Ohio was cut sharply."),
    ("The bridge reopened before repairs were completed [1].", "The bridge reopened after repairs were completed."),
]


@pytest.mark.parametrize("claim,src", RECOMBINED)
def test_r2_02_recombined_claim_is_quoted_not_reworded(claim, src):
    v = SY.verify(claim, [src])
    assert v.claims and only_source_quotes(v, [src], claim), [(c.text, c.quoted) for c in v.claims]


@pytest.mark.parametrize("claim,src", RECOMBINED[:4])
def test_r2_02_d7_does_not_rest_on_the_quantity_word_list(claim, src, monkeypatch):
    monkeypatch.setattr(SY, "states_quantity", lambda text: False)     # a quantity form no list knows
    v = SY.verify(claim, [src])
    assert v.claims and only_source_quotes(v, [src], claim), [(c.text, c.quoted) for c in v.claims]


@pytest.mark.parametrize("text", ["It fell by an order of magnitude.", "Fees are charged hourly.", "Rents rose quarterly.",
                                  "Rooms are cleaned nightly.", "Fees are 400 per annum.", "It took a fortnight.",
                                  "Each semester costs more.", "It is reviewed biennially.", "It rose last year.",
                                  "Rents peaked in the nineties.", "Rates rose by fifty basis points.",
                                  "A handful of hostels closed.", "The balance was nil."])
def test_r2_02_more_quantity_forms(text):
    assert SY.states_quantity(text)


def test_r2_02_excerpts_and_modifier_drops_are_still_the_brains_words():
    # R5-02 (closure round 5): source words may be left out at a claim's edges only up to clause punctuation, so the
    # leading "On Monday" is set off by a comma here, and dropping the trailing "after a long public consultation"
    # now quotes the source sentence instead (fail closed, as for a gap).
    src = "On Monday, the district board approved the new hostel rules after a long public consultation."
    for claim in ("The district board approved the new hostel rules after consultation [1].",
                  "The district board approved the new hostel rules after a long public consultation [1]."):
        v = SY.verify(claim, [src])
        assert len(v.claims) == 1 and v.claims[0].quoted is False, claim
    v = SY.verify("The district board approved the new hostel rules [1].", [src])
    assert len(v.claims) == 1 and v.claims[0].quoted is True and v.claims[0].text == src
