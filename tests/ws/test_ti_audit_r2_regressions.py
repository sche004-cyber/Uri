"""Regressions for Codex TI review round 2 (A1, A2, A6, B1, B2, B3; C1 is covered in Dart)."""
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


# A1: an action in a separate sentence of the instruction goes to Core.
@pytest.mark.parametrize("text", ["Draft a letter to the warden. Email the principal.",
                                  "Write a notice about the water cut; then upload it.",
                                  "Write a letter to warden and send it"])
def test_a1_separate_sentence_action_goes_to_core(text):
    assert X.classify(text, has_draft=False).kind == X.NONE


# B1: action words inside the document's content stay with the desk.
@pytest.mark.parametrize("text", [
    "Draft a notice asking parents to sign it and send the consent form",
    "Draft a circular requesting all staff to fill in the form and submit it and email the office by Monday",
    "Write a notice: Please send the documents by Friday.",
])
def test_b1_content_actions_are_drafts(text):
    assert X.classify(text, has_draft=False).kind == X.DRAFT_NEW


# A2: "it" after a named part refers to that part.
def test_a2_it_refers_back_to_the_named_part():
    assert X.targets_for("Change the first paragraph and make it shorter")["global"] is False
    assert X.targets_for("Make it more diplomatic and shorten the second paragraph.")["global"] is True
    assert X.targets_for("Shorten the second paragraph and make the whole letter more diplomatic")["global"] is True


# A6: the user's literal exclusions are checked even when the model reports none.
def test_a6_user_exclusion_checked_without_model_list(fake, tmp_path):
    b, frames, _ = make(fake, tmp_path, FakeCore())
    leaky = dict(CREATE, exclusions=[], blocks=[{"role": "body", "text": "The mess is closed on Monday."}],
                 facts=[], missing=[])
    fake.scripts.append({"json": json.dumps(leaky)})
    turn(b, "Draft a notice that the mess is closed for repairs; don't mention Monday")
    codes = {f["code"] for f in last_draft(frames)["current"]["flags"]}
    assert "EXCLUDED_PHRASE_PRESENT" in codes
    assert V.user_exclusions("Don't mention the student's name.") == []


# B3 (revised after Codex TI round 7): a corrected value is excused only when the model reports the correction AND
# the user's words show it. Without the model's report the old value stays required: a REVIEW flag (accepted noise),
# never a silent omission.
def test_b3_self_correction_reported_by_model_has_no_missing_flag(fake, tmp_path):
    b, frames, _ = make(fake, tmp_path, FakeCore())
    ok = dict(CREATE, blocks=[{"role": "body", "text": "Seven students left the hostel on Monday."}])
    fake.scripts.append({"json": json.dumps(ok)})
    turn(b, WARDEN)
    flags = last_draft(frames)["current"]["flags"]
    assert [(f["code"], f["severity"]) for f in flags] == [("DETAIL_DROPPED", "info")]   # "five" shown as replaced


def test_b3_unreported_self_correction_is_review_noise_not_silence(fake, tmp_path):
    b, frames, _ = make(fake, tmp_path, FakeCore())
    ok = dict(CREATE, facts=[], blocks=[{"role": "body", "text": "Seven students left the hostel on Monday."}])
    fake.scripts.append({"json": json.dumps(ok)})
    turn(b, WARDEN)
    flags = {f["code"]: f for f in last_draft(frames)["current"]["flags"]}
    assert set(flags) == {"USER_DETAIL_MISSING", "CORRECTION_UNCONFIRMED"}
    assert all(f["severity"] == "review" for f in flags.values())


# B2: an open question lives one turn and can be dropped explicitly.
def test_b2_dropped_question_does_not_capture_later_turns(fake, tmp_path):
    b, frames, _ = make(fake, tmp_path, FakeCore())
    ask = dict(CREATE, clarification="Which hostel?", blocks=[])
    fake.scripts += [{"json": json.dumps(ask)}, {"chunks": [("answer", "Hi!")], "finish": "stop"}]
    turn(b, WARDEN)
    assert SID in b.desk.pending_new
    n = len(fake.requests)
    turn(b, "Never mind that question")
    assert SID not in b.desk.pending_new and len(fake.requests) == n
    assert "dropped that question" in "".join(d["text"] for d in frames.data("answer.delta"))
    turn(b, "yes")
    assert frames.data("turn.routed")[-1]["route"] == "answer"         # not the old request


def test_b2_unrelated_turn_drops_the_question(fake, tmp_path):
    b, frames, _ = make(fake, tmp_path, FakeCore())
    ask = dict(CREATE, clarification="Which hostel?", blocks=[])
    fake.scripts += [{"json": json.dumps(ask)}, {"chunks": [("answer", "Paris.")], "finish": "stop"}]
    turn(b, WARDEN)
    turn(b, "What is the capital of France?")
    assert SID not in b.desk.pending_new
