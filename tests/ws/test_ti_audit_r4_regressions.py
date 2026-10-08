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


@pytest.mark.parametrize("words,claimed,verified", [
    ("17 students on Monday, sorry, 18 students", ["17"], []),          # ambiguous: stays required (review)
    ("17 students on Monday, sorry, Tuesday", ["Monday"], ["Monday"]),
    ("paid by Anil, I mean Sunil Verma, on Friday", ["Anil"], ["Anil"]),
    ("leaving hostel yesterday, no wait, on the 6th", ["yesterday"], ["yesterday"]),
    ("the fee of 4500, sorry, 5400 rupees", ["4500"], ["4500"]),
    # A claim the user's words do not support is NOT excused (Codex TI round 7).
    ("Draft a report: The meeting is on Monday. Attendance was 17, sorry, by Tuesday it was 18.", ["Monday", "17"],
     ["17"]),
    ("Report for Anil with 17 students, sorry, Everybody counted 18 students", ["Anil"], []),
    # Codex TI round 8: an apology is not a correction; a same-kind replacement must follow the cue.
    ("Draft a report: The meeting is on Monday, sorry for the late notice, and attendance was 18 on Tuesday.",
     ["Monday"], []),
    ("The meeting is on Monday, sorry, the hall is booked", ["Monday"], []),
])
def test_2_only_verifiable_supersessions_are_excused(words, claimed, verified):
    assert V.verified_superseded(words, claimed)[0] == verified


def test_2_unverified_supersession_is_flagged_and_value_stays_required(fake, tmp_path):
    b, frames, _ = make(fake, tmp_path, FakeCore())
    wrong = dict(CREATE, facts=[{"key": "attendance", "value": "18", "superseded": ["17"]},
                                {"key": "day", "value": "Tuesday", "superseded": ["Monday"]}],
                 blocks=[{"role": "body", "text": "The meeting is on Tuesday; attendance is 18."}])
    fake.scripts.append({"json": json.dumps(wrong)})
    turn(b, "Draft a report: The meeting is on Monday. Attendance was 17, sorry, by Tuesday it was 18.")
    flags = {f["code"]: f["detail"] for f in last_draft(frames)["current"]["flags"]}
    assert "SUPERSESSION_UNVERIFIED" in flags and "Monday" in flags["SUPERSESSION_UNVERIFIED"]
    assert "monday" in flags["USER_DETAIL_MISSING"]


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


# Codex TI rounds 5-7: no sentence-initial word or nearby date can excuse an unrelated value.
@pytest.mark.parametrize("words", ["Draft a report for Anil with 17 students, sorry, Everybody counted 18 students",
                                   "Report for Anil with 17 students, sorry, There were 18 students"])
def test_r5_r7_unrelated_values_stay_required(words):
    v, _ = V.verified_superseded(words, ["17"])
    assert v == ["17"]
    assert "anil" in V.check_user_details(words, "Everybody counted 18 students.", v)[0]["detail"]
