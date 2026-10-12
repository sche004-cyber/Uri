"""Regressions for Codex TI review round 3 (A1, A6, B1, B2, B3) and the model-side action guard."""
import json

import pytest

from tests.oi.fake_llama import FakeLlama
from tests.oi.test_oi_orchestrator import FakeCore
from tests.ws.test_ti_desk_bridge import CREATE, REVISE_2, WARDEN, last_draft, turn
from tests.ws.test_ws_worker_bridge import SID, make
from uri_operational_intelligence import text_intent as X
from uri_operational_intelligence import text_verify as V


@pytest.fixture
def fake():
    with FakeLlama() as f:
        yield f


@pytest.mark.parametrize("text", [
    "Draft a letter: explain the issue. Then email it to the principal.",          # A1: action after the colon
    "Draft a letter asking parents to sign the form, then email it to the principal.",   # B1: comma ends the clause
    "Write the notice about the gate timings and finally print it",
])
def test_sequenced_actions_go_to_core(text):
    assert X.classify(text, has_draft=False).kind == X.NONE


def test_model_side_action_guard_hands_the_turn_to_core(fake, tmp_path):
    core = FakeCore([{"turn_id": "c1", "state": "failed", "code": "REFUSED_NO_CAPABILITY", "message": "No."}])
    b, frames, _ = make(fake, tmp_path, core)
    # The classifier misses this phrasing; the Brain reports the action, the desk hands the turn over.
    fake.scripts.append({"json": json.dumps(dict(CREATE, actions_requested=["email the letter to the principal"]))})
    tid = turn(b, "Draft a letter to the warden about the gate timings, the principal should get it by email too")
    assert not frames.data("draft.updated") and b.desk.snapshot(SID) is None
    routed = [e["data"] for e in frames.events if e["turn_id"] == tid and e["type"] == "turn.routed"]
    assert routed[0]["route"] == "draft" and routed[-1].get("rerouted_from") == "draft"
    types = [e["type"] for e in frames.events if e["turn_id"] == tid]
    assert types.count("turn.started") == 1 and types.count("turn.finished") == 1


def test_a6_user_exclusion_persists_to_later_versions(fake, tmp_path):
    b, frames, _ = make(fake, tmp_path, FakeCore())
    first = dict(CREATE, exclusions=[], facts=[], blocks=[{"role": "body", "text": "The mess is closed for repairs."}])
    leak = {"action": "edit", "clarification": None, "fact_updates": [], "exclusions_add": [],
            "edits": [{"op": "replace", "block_id": "b1", "role": "body", "text": "The mess is closed on Monday."}],
            "summary": "Formal."}
    fake.scripts += [{"json": json.dumps(first)}, {"json": json.dumps(leak)}]
    turn(b, "Draft a notice that the mess is closed for repairs; don't mention Monday in the notice")
    assert "Monday" in last_draft(frames)["current"]["exclusions"]
    turn(b, "Make it formal")
    assert "EXCLUDED_PHRASE_PRESENT" in {f["code"] for f in last_draft(frames)["current"]["flags"]}
    assert V.user_exclusions("don't mention Monday in the letter") == ["Monday"]


def test_b2_new_edit_clears_an_unrelated_open_question(fake, tmp_path):
    b, frames, _ = make(fake, tmp_path, FakeCore())
    clar = {"action": "clarify", "clarification": "Which date?", "fact_updates": [], "exclusions_add": [],
            "edits": [], "summary": ""}
    fake.scripts += [{"json": json.dumps(CREATE)}, {"json": json.dumps(clar)}, {"json": json.dumps(REVISE_2)}]
    turn(b, WARDEN)
    turn(b, "Change the date.")
    turn(b, "Make the salutation Dear Sir")
    req = json.loads(fake.requests[-1]["messages"][1]["content"])
    assert "your_question" not in req


def test_b3_unrelated_detail_stays_required():
    v, u = V.verified_superseded("Draft a report about 17 students on Monday, sorry, Tuesday", ["Monday"])
    assert v == ["Monday"] and u == []
    flags = V.check_user_details("Draft a report about 17 students on Monday, sorry, Tuesday",
                                 "A report about the students on Tuesday.", v)
    assert flags and "17" in flags[0]["detail"] and "monday" not in flags[0]["detail"]
