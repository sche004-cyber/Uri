"""Regressions for Codex TI review round 4 (findings 1-6)."""
import json

import pytest

from tests.oi.fake_llama import FakeLlama
from tests.oi.test_oi_orchestrator import FakeCore
from tests.ws.test_ti_desk_bridge import CREATE, WARDEN, last_draft, turn
from tests.ws.test_ws_worker_bridge import SID, make
from uri_operational_intelligence import text_intent as X
from uri_operational_intelligence import text_verify as V


@pytest.fixture
def fake():
    with FakeLlama() as f:
        yield f


def test_1_action_guard_wins_over_a_pending_question(fake, tmp_path):
    core = FakeCore([{"turn_id": "c1", "state": "failed", "code": "REFUSED_NO_CAPABILITY", "message": "No."}])
    b, frames, _ = make(fake, tmp_path, core)
    clar = {"actions_requested": [], "action": "clarify", "clarification": "Which date?", "fact_updates": [],
            "exclusions_add": [], "edits": [], "summary": ""}
    answer_with_action = {"actions_requested": ["email the letter to the principal"], "action": "edit",
                          "clarification": None, "fact_updates": [], "exclusions_add": [],
                          "edits": [{"op": "replace", "block_id": "b4", "role": "body", "text": "On Tuesday."}],
                          "summary": "Date."}
    fake.scripts += [{"json": json.dumps(CREATE)}, {"json": json.dumps(clar)}, {"json": json.dumps(answer_with_action)}]
    turn(b, WARDEN)
    turn(b, "Change the date.")
    tid = turn(b, "Tuesday; the principal should get it by email too")
    assert b.handle("draft_get", {"command": "draft_get", "session_id": SID})["draft"]["version"] == 1   # no edit
    routed = [e["data"] for e in frames.events if e["turn_id"] == tid and e["type"] == "turn.routed"]
    assert routed[-1].get("rerouted_from") == "draft"
    assert b.desk.active(SID).pending_question is None


@pytest.mark.parametrize("words,kept,dropped", [
    ("17 students on Monday, sorry, 18 students", ["Monday", "18"], ["17"]),
    ("17 students on Monday, sorry, Tuesday", ["17", "Tuesday"], ["Monday"]),
    ("paid by Anil, I mean Sunil Verma, on Friday", ["Sunil", "Friday"], ["Anil"]),
    ("leaving hostel yesterday, no wait, on the 6th", ["6th"], ["yesterday"]),
    ("the fee of 4500, sorry, 5400 rupees", ["5400"], ["4500"]),
])
def test_2_only_the_same_kind_value_is_superseded(words, kept, dropped):
    s = V.strip_corrected(words)
    assert all(k in s for k in kept), s
    assert all(d not in s for d in dropped), s


def test_2_an_unrelated_fact_stays_required():
    s = V.strip_corrected("Report 17 students on Monday, sorry, 18 students")
    flags = V.check_user_details(s, "Eighteen students were reported.")
    assert flags and "monday" in flags[0]["detail"]


def test_3_dictated_sequence_inside_content_stays_a_draft():
    assert X.classify("Draft a notice: Parents must sign the form, then send the form to the office",
                      has_draft=False).kind == X.DRAFT_NEW
    assert X.classify("Draft a letter: explain the issue. Then email it to the principal.",
                      has_draft=False).kind == X.NONE


def test_4_create_fallback_clears_pending_create(fake, tmp_path):
    core = FakeCore([{"turn_id": "c1", "state": "failed", "code": "REFUSED_NO_CAPABILITY", "message": "No."}])
    b, frames, _ = make(fake, tmp_path, core)
    ask = dict(CREATE, clarification="Which hostel?", blocks=[])
    fake.scripts += [{"json": json.dumps(ask)},
                     {"json": json.dumps(dict(CREATE, actions_requested=["send it to the warden"]))}]
    turn(b, WARDEN)
    turn(b, "Block C, and the warden should get it right away")
    assert SID not in b.desk.pending_new


def test_5_exclusion_keeps_its_own_words():
    assert V.user_exclusions("Don't mention the flood in Assam") == ["the flood in Assam"]
    assert V.user_exclusions("don't mention Monday in the letter") == ["Monday"]
    assert V.check_exclusions(["the flood in Assam"], "The flood caused damage.") == []


def test_6_please_marks_an_instruction_to_uri():
    assert X.classify("Draft a notice asking parents to sign the form and please email it to the principal",
                      has_draft=False).kind == X.NONE


# Codex TI round 5, finding 7: a sentence-initial function word is never paired as a name.
def test_r5_7_function_word_is_not_a_name():
    s = V.strip_corrected("Report for Anil with 17 students, sorry, There were 18 students")
    assert "Anil" in s and "17" not in s and "18" in s
