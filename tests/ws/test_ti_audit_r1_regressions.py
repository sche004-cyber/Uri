"""Regressions for Codex TI review round 1 (findings F1..F8)."""
import json

import pytest

from tests.oi.fake_llama import FakeLlama
from tests.oi.test_oi_orchestrator import FakeCore
from tests.ws.test_ti_desk_bridge import CREATE, WARDEN, last_draft, turn
from tests.ws.test_ws_worker_bridge import SID, make
from uri_operational_intelligence import text_input as TI
from uri_operational_intelligence import text_intent as X
from uri_operational_intelligence import text_verify as V


@pytest.fixture
def fake():
    with FakeLlama() as f:
        yield f


# F1: an action anywhere in the request goes to Core.
@pytest.mark.parametrize("text", [
    "Draft a letter to the warden and email the principal",
    "Write a notice about the mess timings then print it for the board",
    "Draft a letter to the warden about the students. " + "The students were seen near the gate. " * 12
    + "Also send it to the principal.",
])
def test_f1_chained_action_anywhere_goes_to_core(text):
    assert X.classify(text, has_draft=False).kind == X.NONE


def test_f1_coordination_inside_content_is_still_a_draft():
    assert X.classify("Draft a notice asking the parents to sign and send the consent form by Friday",
                      has_draft=False).kind == X.DRAFT_NEW


# F2: explicit parts win; an unknown part is asked about, never widened.
def test_f2_keep_everything_else_stays_local():
    t = X.targets_for("Make the first paragraph shorter and keep everything else the same")
    assert t["body"] == [0] and t["global"] is False
    assert X.targets_for("Make it more diplomatic and shorten the second paragraph.")["global"] is True


def test_f2_unresolved_part_asks_without_a_model_call(fake, tmp_path):
    b, frames, _ = make(fake, tmp_path, FakeCore())
    fake.scripts.append({"json": json.dumps(CREATE)})
    turn(b, WARDEN)
    n = len(fake.requests)
    turn(b, "Make the fifth paragraph shorter.")
    assert len(fake.requests) == n
    assert "could not find the fifth paragraph" in frames.data("draft.clarify")[-1]["question"]
    assert b.handle("draft_get", {"command": "draft_get", "session_id": SID})["draft"]["version"] == 1


# F3 + F4: an open create question survives a failure and accepts "yes".
def test_f3_f4_pending_create_survives_failure_and_yes_answers(fake, tmp_path):
    b, frames, o = make(fake, tmp_path, FakeCore())
    ask = dict(CREATE, clarification="Should the letter name the students?", blocks=[])
    fake.scripts += [{"json": json.dumps(ask)}, {"status": 500}, {"json": json.dumps(CREATE)}]
    turn(b, WARDEN)
    assert frames.data("turn.finished")[-1]["status"] == "needs_user"
    turn(b, "yes")                                       # Brain fails (HTTP 500): request must not be lost
    assert frames.data("error")[-1]["code"].startswith("BRAIN_")
    assert SID in b.desk.pending_new
    turn(b, "yes")                                       # retry answers the same question
    assert frames.data("turn.routed")[-1]["triage"]["text_kind"] == "DRAFT_NEW"
    assert last_draft(frames)["version"] == 1 and SID not in b.desk.pending_new
    req = json.loads(fake.requests[-1]["messages"][1]["content"])
    assert "Should the letter name the students?" in req["request"]


# F5: a desk turn handed to the ordinary path is ONE turn.
def test_f5_fallback_is_one_coherent_turn(fake, tmp_path):
    b, frames, _ = make(fake, tmp_path, FakeCore())
    fake.scripts += [{"json": json.dumps(CREATE)},
                     {"json": json.dumps({"action": "not_an_edit", "clarification": None, "fact_updates": [],
                                          "exclusions_add": [], "edits": [], "summary": ""})},
                     {"chunks": [("answer", "Registers record exits.")], "finish": "stop"}]
    turn(b, WARDEN)
    # Anchored to the draft (UIV2-F1: unanchored chat no longer reaches the desk); the model says it is no edit.
    tid = turn(b, "Make sense of why the letter mentions registers")
    types = [e["type"] for e in frames.events if e["turn_id"] == tid]
    assert types.count("turn.started") == 1 and types.count("turn.finished") == 1
    routed = [e["data"] for e in frames.events if e["turn_id"] == tid and e["type"] == "turn.routed"]
    assert routed[0]["route"] == "draft" and routed[-1].get("rerouted_from") == "draft"


# F6: independent of the model's fact list.
def test_f6_user_detail_omitted_from_draft_and_facts_is_flagged(fake, tmp_path):
    b, frames, _ = make(fake, tmp_path, FakeCore())
    silent = dict(CREATE, facts=[], blocks=[{"role": "body", "text": "Some students left the hostel."}])
    fake.scripts.append({"json": json.dumps(silent)})
    turn(b, WARDEN)
    codes = {f["code"]: f["detail"] for f in last_draft(frames)["current"]["flags"]}
    assert "USER_DETAIL_MISSING" in codes and "monday" in codes["USER_DETAIL_MISSING"]


def test_f6_added_name_in_grammar_only_is_meaning_change():
    flags = V.check_meaning_preserved("Ramesh went to Pune", "Ramesh and Suresh went to Pune.")
    assert flags and flags[0]["code"] == "MEANING_CHANGED" and "suresh" in flags[0]["detail"]


def test_f6_revision_that_drops_a_detail_is_flagged():
    assert V.check_details_kept("Seven students left on Monday.", "Some students left.", ["make it vaguer"])[0][
        "code"] == "DETAIL_REMOVED"
    # Removed because the instruction mentioned it: still listed, as an info line (round 9: nothing silent).
    assert [f["severity"] for f in V.check_details_kept("Seven students left on Monday.", "Seven students left.",
                                                         ["remove monday"])] == ["info"]


# F7: number phrases compare by value.
def test_f7_number_phrases():
    assert V.canonical_numbers("one hundred and five boys") == {105}
    assert V.canonical_numbers("eighty five thousand rupees") == {85000}
    assert V.check_meaning_preserved("one hundred and five boys came", "105 boys came.") == []


# F8: a supplied `uncertain` must be a list.
@pytest.mark.parametrize("bad", [None, "", False, 0])
def test_f8_uncertain_not_coerced(bad):
    env = {"schema": TI.SCHEMA, "source": "transcript",
           "transcript": {"raw": "a b", "engine": "simulated", "simulated": True, "uncertain": bad}}
    with pytest.raises(TI.InputRejected) as e:
        TI.parse(env, "a b")
    assert e.value.code == "TRANSCRIPT_UNCERTAIN"
