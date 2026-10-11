"""W1-A0 closure review (R1) regressions for Web Intelligence.

R1-01: link / contact text the detector missed (a bare domain, 'xhttps://', 'hxxps://evil[.]example', fullwidth
       '＠' and '：') was kept by the extractive answer and verify() and rendered on the research surface.
R1-02: a quantity word the D7 detector missed ('tenfold') and words recombined from one source sentence were shown in
       the Brain's own words.
R1-05: research did not yield the Brain: no cancel token reached the Brain call, Cancel during synthesis still ended
       COMPLETED_WITH_RESULT, an expired deadline still called the Brain, and the worker only yielded Assist work and
       only on oi_turn.
R1-06: a sentence kept every citation, including one to a source that does not state it.

Self-contained: helpers come from test modules that existed before the repair; pages are built here.
"""
import json
import threading
import time
from pathlib import Path

import pytest

from uri_a2ui.validate import require_valid
from uri_web import bridge as B
from uri_web import pipeline as P
from uri_web import synthesize as SY
from uri_web import untrusted as U
from uri_web.local_brain import make_complete
from uri_web.surface import build_surface

from .d7_invariant import only_source_quotes
from .test_w1_pipeline_citations_injection import SRC1, FakeProvider, page, web

ROOT = Path(__file__).resolve().parents[2]

# ---- R1-01 -----------------------------------------------------------------------------------------------------------

LINKS = ("refunds-portal.net/claim", "xhttps://evil.example/pay", "hxxps://evil[.]example", "bursar＠evil-mail.com",
         "https：//evil.example/claim")
HOSTEL = "Hostel fee refunds are handled by the bursar, see {} for the hostel fee form."


@pytest.mark.parametrize("link", LINKS)
def test_r1_01_detector_sees_every_link_form(link):
    assert U.has_link_or_contact(HOSTEL.format(link))


def test_r1_01_ordinary_sentences_are_not_links():
    for s in ("The fee rose.The board met on Monday.", "e.g. the U.S. rate is 4.5% at 10 a.m. today.",
              "Ph.D students pay less.", "Hostel fee refunds are handled by the bursar."):
        assert not U.has_link_or_contact(s), s


@pytest.mark.parametrize("link", LINKS)
def test_r1_01_verify_and_extractive_never_keep_a_link(link):
    src = HOSTEL.format(link) + " Hostel fee refunds take two weeks to process."
    v = SY.verify(HOSTEL.format(link) + " [1]", [src])
    assert not v.claims and v.dropped[0]["reason"] == "LINK_OR_CONTACT"
    e = SY.extractive("hostel fee refunds bursar form", [src])
    assert all("evil" not in c.text and "portal" not in c.text for c in e.claims)


def test_r1_01_surface_masks_every_link_form():
    answer = [{"text": HOSTEL.format(link), "citations": [1], "quoted": False} for link in LINKS]
    r = {"job_id": "j1", "query": "hostel refunds", "status": P.COMPLETED_WITH_RESULT, "answer": answer,
         "sources": [{"number": 1, "title": "Refunds at refunds-portal.net", "url": "https://uni.example/fees",
                      "record": {"retrieved_at": "z"}, "analysed_scope": "full_text", "injection_flags": []}],
         "conflicts": [], "providers": [], "dropped_claims": [], "synthesis_method": "brain", "elapsed_s": 1}
    s = build_surface(r)
    require_valid(s.messages(), set(s.actions))
    dump = json.dumps(s.messages(), ensure_ascii=False)
    for bad in ("://", "refunds-portal", "evil", "＠", "："):
        assert bad not in dump, bad
    assert "uni.example/fees" in dump and "Hostel fee refunds are handled by the bursar" in dump


# ---- R1-02 -----------------------------------------------------------------------------------------------------------

def test_r1_02_tenfold_is_quoted_not_reworded():
    src = "Wages in Ohio rose tenfold over the period while rents in Texas also rose sharply."
    claim = "Rents in Texas rose tenfold [1]."
    v = SY.verify(claim, [src])
    assert only_source_quotes(v, [src], claim)


@pytest.mark.parametrize("text", ["Rents rose tenfold.", "Rates rose by two percentage points.",
                                  "Prices doubled over a decade.", "A couple of hostels closed.", "Phase V begins."])
def test_r1_02_quantity_words(text):
    assert SY.states_quantity(text)


def test_r1_02_recombined_words_are_quoted_not_reworded():
    src = "Wages in Texas rose sharply while rents in Ohio fell."
    claim = "Rents in Texas rose sharply [1]."
    v = SY.verify(claim, [src])
    assert only_source_quotes(v, [src], claim)


# ---- R1-06 -----------------------------------------------------------------------------------------------------------

def test_r1_06_unrelated_cited_source_is_not_kept():
    hostel = "The district board approved the new hostel rules after consultation with students."
    mango = "Mango exports from the district grew strongly this season, the board said."
    v = SY.verify("The district board approved the new hostel rules after consultation [1][2].", [hostel, mango])
    assert [c.citations for c in v.claims] == [[1]]


def test_r1_06_both_sources_kept_when_both_state_it():
    # R5-02 / D14 (closure rounds 5-6): a claim in the Brain's words runs from the sentence start (determiners aside)
    # to its end, so both sources state exactly the claim; b lacks the leading determiner.
    a = "The district board approved the new hostel rules after consultation."
    b = "District board approved the new hostel rules after consultation."
    v = SY.verify("The district board approved the new hostel rules after consultation [1][2].", [a, b])
    assert [c.citations for c in v.claims] == [[1, 2]]


# ---- R1-05 -----------------------------------------------------------------------------------------------------------

def _routes():
    return {("a.example", "/"): page(f"<p>{SRC1}</p>")}


def test_r1_05_cancel_during_the_brain_call_ends_cancelled():
    f, _ = web(_routes())
    in_call, cancelled = threading.Event(), threading.Event()

    def brain(messages, **_kw):
        in_call.set()
        cancelled.wait(5)
        return "COMPLETE", "The district board approved a fee increase of 4.5% for the 2027 academic year [1]."
    job = P.ResearchJob(P.ResearchRequest("fee increase", use_brain=True), fetcher=f,
                        providers=[FakeProvider([("A", "https://a.example/", "")])], complete=brain)
    out = {}
    t = threading.Thread(target=lambda: out.setdefault("r", job.run()))
    t.start()
    assert in_call.wait(5)
    job.cancel()
    cancelled.set()
    t.join(5)
    assert out["r"].status == P.CANCELLED and not out["r"].answer


def test_r1_05_expired_deadline_does_not_call_the_brain():
    t = [0.0]

    def clock():
        t[0] += 50.0
        return t[0]
    calls = []
    f, _ = web(_routes())
    job = P.ResearchJob(P.ResearchRequest("fee increase", use_brain=True, budget=P.Budget(deadline_s=60)), fetcher=f,
                        providers=[FakeProvider([("A", "https://a.example/", "")])],
                        complete=lambda m, **kw: calls.append(m) or ("COMPLETE", "x [1]."), clock=clock)
    r = job.run()
    assert r.status == P.TIMED_OUT and calls == []


def test_r1_05_user_turn_stops_the_research_brain_call():
    events = []
    f, _ = web(_routes())
    in_call = threading.Event()
    seen = {}

    def brain(messages, *, cancel=None, timeout_s=None):
        seen["timeout_s"] = timeout_s
        in_call.set()
        t0 = time.monotonic()
        while time.monotonic() - t0 < 5:
            if cancel is not None and cancel.cancelled:
                return "CANCELLED", ""
            time.sleep(0.01)
        return "COMPLETE", "The district board approved a fee increase of 4.5% for the 2027 academic year [1]."
    br = B.WebResearch(write_event=events.append, fetcher_factory=lambda: f,
                       providers_factory=lambda: [FakeProvider([("A", "https://a.example/", "")])], brain_complete=brain)
    jid = br.handle("web_research", {"command": "web_research", "query": "fee increase", "urls": [], "feeds": [],
                                     "use_brain": True})["job_id"]
    assert in_call.wait(5)
    t0 = time.monotonic()
    br.cancel_brain_work("user_turn")
    br.wait(5)
    assert time.monotonic() - t0 < 2
    res = br.handle("web_research_status", {"command": "web_research_status", "job_id": jid})["result"]
    assert res["status"] == P.COMPLETED_WITH_RESULT and res["brain_status"] == "CANCELLED"
    assert res["synthesis_method"] == "extractive_fallback" and 0 < seen["timeout_s"] <= 90


def test_r1_05_local_brain_call_is_cancellable_and_bounded():
    from uri_operational_intelligence import brain_client as BC

    class Client:
        base_url = "http://127.0.0.1:18470"

        def stream_chat(self, body, *, cancel=None, deadlines=None):
            self.deadlines = deadlines
            t0 = time.monotonic()
            while time.monotonic() - t0 < 5:
                if cancel.cancelled:
                    return BC.CallResult(status=BC.CANCELLED)
                time.sleep(0.01)
            return BC.CallResult(status=BC.COMPLETE, text="late")

        def complete_json(self, body, timeout_s):
            raise AssertionError("the cancellable path must be used")

    class Flag:
        cancelled = False
    c, flag = Client(), Flag()
    threading.Timer(0.2, lambda: setattr(flag, "cancelled", True)).start()
    t0 = time.monotonic()
    assert make_complete(c)([{"role": "user", "content": "x"}], cancel=flag, timeout_s=7.5) == ("CANCELLED", "")
    assert time.monotonic() - t0 < 2 and c.deadlines.total_s == 7.5


def test_r1_05_worker_yields_research_and_assist_brain_on_every_brain_turn():
    src = (ROOT / "scripts/run_uri_integrated_worker.py").read_text(encoding="utf-8")
    assert 'BRAIN_TURNS = frozenset({"oi_turn", "oi_confirm", "oi_decide"})' in src
    hook = src.index("if kind in BRAIN_TURNS and WB.valid(kind, command):")
    handle = src.index("result = oi.handle(kind, command)")
    assert hook < src.index('web.cancel_brain_work("user_turn")') < handle
    assert hook < src.index('assist.cancel_brain_work("user_turn")') < handle
