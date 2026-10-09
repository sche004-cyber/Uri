"""Scheduling-request interpreter and the worker handoff turn (A-AC4 intake, A-AC6 simple requests stay conversational)."""
import json
from pathlib import Path

import pytest

from uri_operational_intelligence import schedule_intent as SI
from uri_operational_intelligence.events import EVENT_TYPES

OWNER = ("URI, schedule Claude to create a festival GIF two days before each major Indian festival and bring it to me "
         "for approval.")
CAL = json.loads((Path(__file__).resolve().parents[2] / "uri_scheduler" / "data" / "in_festivals.json").read_text(encoding="utf-8"))


def test_owner_request():
    h = SI.interpret(OWNER)
    assert h["domain"] == "scheduler" and h["kind"] == "festival_gif_schedule" and h["interpreter"] == SI.INTERPRETER
    r = h["request"]
    assert r["offset_days"] == 2 and r["time"] == "09:00" and r["festivals"] is None
    assert any("12 national festivals" in a for a in r["assumptions"]) and any("09:00" in a for a in r["assumptions"])


@pytest.mark.parametrize("text,festivals,offset,time", [
    ("Every year make a Diwali and Holi greeting GIF 3 days before, at 8:30 am", ["diwali", "holi"], 3, "08:30"),
    ("schedule a greeting card a week before each Sikkim festival", "sikkim", 7, "09:00"),
    ("Please create festival wishes GIFs four days ahead of every festival at 6 pm", None, 3, "18:00"),
    ("automatically make an animated greeting for Eid ul Fitr and Christmas one day before", ["eid_ul_fitr", "christmas"], 1, "09:00"),
])
def test_variants(text, festivals, offset, time):
    r = SI.interpret(text)["request"]
    if festivals == "sikkim":
        assert set(SI.SIKKIM) <= set(r["festivals"])
    else:
        assert r["festivals"] == festivals
    assert r["offset_days"] == offset and r["time"] == time


def test_unsupported_offset_and_other_harness_are_stated():
    r = SI.interpret("schedule Codex to make festival GIFs 4 days before each festival")["request"]
    assert r["offset_days"] == 3 and any("4 days" in a for a in r["assumptions"])
    assert any("Claude only" in a for a in r["assumptions"])


@pytest.mark.parametrize("text", [
    "When is Diwali this year?", "What festivals are in November?", "schedule a meeting with Ravi tomorrow at 10",
    "make me a Diwali GIF", "Tell me about Losar", "Is Holi a holiday?", "every morning remind me to drink water",
    "", "x" * 3000,
])
def test_ordinary_requests_stay_conversational(text):
    assert SI.interpret(text) is None


def test_every_mapped_key_exists_in_the_calendar():
    keys = {f["festival_key"] for f in CAL["festivals"]}
    assert set(SI.NAMES.values()) <= keys and set(SI.SIKKIM) <= keys and set(SI.MAJOR) <= keys
    from uri_scheduler.a2ui_host import DEFAULT_SELECTION
    assert set(SI.MAJOR) == set(DEFAULT_SELECTION)


def test_handoff_event_is_registered():
    assert "a2ui.handoff" in EVENT_TYPES and "a2ui" in EVENT_TYPES["turn.routed"]


def test_worker_handoff_turn_never_reaches_the_brain_or_core(tmp_path):
    import sys
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
    from tests.oi.fake_llama import FakeLlama
    from tests.oi.test_oi_orchestrator import FakeCore
    from tests.ws.test_ws_worker_bridge import SID, make
    with FakeLlama() as fake:
        core = FakeCore()
        b, frames, _ = make(fake, tmp_path, core)
        r = b.handle("oi_turn", {"command": "oi_turn", "session_id": SID, "text": OWNER, "depth": "auto"})
        b.wait(10)
        t = frames.types(r["turn_id"])
        assert t == ["turn.started", "turn.routed", "a2ui.handoff", "answer.delta", "answer.done", "turn.finished",
                     "companion.state"]
        assert frames.data("a2ui.handoff")[0]["request"]["offset_days"] == 2
        assert fake.requests == [] and core.calls == []                          # no model call, no Core turn
        assert b.pending == {}                                                   # nothing awaits a decision
        # an ordinary question still goes to the answer channel
        fake.scripts.append({"chunks": [("answer", "Nov 8")], "finish": "stop"})
        r2 = b.handle("oi_turn", {"command": "oi_turn", "session_id": SID, "text": "When is Diwali?", "depth": "auto"})
        b.wait(10)
        assert "a2ui.handoff" not in frames.types(r2["turn_id"])
