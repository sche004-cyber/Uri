"""Draft desk through the integrated worker bridge, against a scripted fake Runtime v1 (TI-AC1..AC8).

The fake returns the JSON a model would return; these tests check what URI does with it: versioning, locality,
verification flags, clarification, cancellation, degraded Brain, input contract and routing to Core.
"""
import json
import time

import pytest

from tests.oi.fake_llama import FakeLlama
from tests.oi.test_oi_orchestrator import FakeCore
from tests.ws.test_ws_worker_bridge import CFG, SID, make
from uri_operational_intelligence import text_input as TI
from uri_operational_intelligence.worker_bridge import BridgeRefused

WARDEN = ("URI draft a letter to the warden regarding five students, sorry seven students, who left the hostel on "
          "Monday without permission. Make it formal.")
CREATE = {
    "clarification": None,
    "facts": [{"key": "number of students", "value": "seven", "superseded": ["five"]},
              {"key": "day", "value": "Monday", "superseded": []}],
    "exclusions": [], "doc_type": "letter", "tone": "formal",
    "blocks": [
        {"role": "recipient", "text": "To\nThe Warden\n[Hostel Name]"},
        {"role": "subject", "text": "Subject: Seven students leaving the hostel without permission"},
        {"role": "salutation", "text": "Respected Sir/Madam,"},
        {"role": "body", "text": "I am writing to inform you that seven students left the hostel on Monday without "
                                 "permission."},
        {"role": "body", "text": "This is a matter of concern for the safety of the students and the discipline of "
                                 "the hostel, and I request that it be looked into at the earliest so that suitable "
                                 "steps can be taken."},
        {"role": "body", "text": "Thanking you."},
        {"role": "closing", "text": "Yours faithfully,"},
        {"role": "signature", "text": "[Your Name]\n[Designation]"}],
    "missing": ["sender name", "hostel name"], "summary": "A formal letter to the warden about seven students."}
REVISE_1 = {"action": "edit", "clarification": None, "fact_updates": [], "exclusions_add": ["without permission"],
            "edits": [{"op": "replace", "block_id": "b2", "role": "subject",
                       "text": "Subject: Seven students leaving the hostel without recording their departure"},
                      {"op": "replace", "block_id": "b4", "role": "body",
                       "text": "I am writing to inform you that seven students left the hostel on Monday without "
                               "recording their departure in the hostel register."},
                      # An edit to a paragraph the instruction did not touch: must be dropped.
                      {"op": "replace", "block_id": "b6", "role": "body", "text": "Thank you very much."}],
            "summary": "Replaced 'without permission' with the register wording."}
REVISE_2 = {"action": "edit", "clarification": None, "fact_updates": [], "exclusions_add": [],
            "edits": [{"op": "replace", "block_id": "b4", "role": "body",
                       "text": "I would like to bring to your kind notice that seven students left the hostel on "
                               "Monday without recording their departure in the hostel register."},
                      {"op": "replace", "block_id": "b5", "role": "body",
                       "text": "I would be grateful if this could be looked into."}],
            "summary": "Softened the tone and shortened the second paragraph."}


@pytest.fixture
def fake():
    with FakeLlama() as f:
        yield f


def turn(b, text, input=None, depth="auto"):
    cmd = {"command": "oi_turn", "session_id": SID, "text": text, "depth": depth}
    if input is not None:
        cmd["input"] = input
    r = b.handle("oi_turn", cmd)
    b.wait(15)
    return r["turn_id"]


def last_draft(frames):
    return [d for d in frames.data("draft.updated")][-1]["draft"]


def body_texts(draft):
    return [x["text"] for x in draft["current"]["blocks"] if x["role"] == "body"]


def test_owner_demo_sequence_with_versions_locality_and_undo(fake, tmp_path):
    core = FakeCore()
    b, frames, _ = make(fake, tmp_path, core)
    fake.scripts += [{"json": json.dumps(CREATE)}, {"json": json.dumps(REVISE_1)}, {"json": json.dumps(REVISE_2)}]

    t1 = turn(b, WARDEN)
    routed = frames.data("turn.routed")[-1]
    assert routed["route"] == "draft" and routed["triage"]["text_kind"] == "DRAFT_NEW"
    d1 = last_draft(frames)
    assert d1["version"] == 1 and "seven students" in d1["current"]["text"]
    assert "five" not in d1["current"]["text"].lower()
    assert not [f for f in d1["current"]["flags"] if f["severity"] == "error"]
    assert "[Your Name]" in d1["current"]["missing"]
    assert core.calls == []                                # nothing reached Core: no action was requested
    req = fake.requests[-1]
    assert req["response_format"]["type"] == "json_schema" and req["chat_template_kwargs"]["enable_thinking"] is False
    assert frames.data("turn.finished")[-1] == {"status": "ok", "route": "draft", "total_s": frames.data("turn.finished")[-1]["total_s"]}
    assert "Nothing has been sent or saved." in "".join(d["text"] for d in frames.data("answer.delta"))

    turn(b, "Actually, don't say without permission. Say they left without recording their departure in the hostel "
            "register.")
    d2 = last_draft(frames)
    assert d2["version"] == 2 and d2["current"]["op"] == "revised"
    assert sorted(d2["current"]["changed"]) == ["b2", "b4"]          # b6 edit dropped: outside the named phrase
    assert body_texts(d2)[2] == "Thanking you." and body_texts(d2)[1] == body_texts(d1)[1]
    assert "without permission" not in d2["current"]["text"]
    assert any(f["code"] == "EDIT_OUTSIDE_TARGET" for f in d2["current"]["flags"])
    edit_req = json.loads(fake.requests[-1]["messages"][1]["content"])
    assert [x["id"] for x in edit_req["document"]["blocks"]][:2] == ["b1", "b2"]

    turn(b, "Make it more diplomatic and shorten the second paragraph.")
    d3 = last_draft(frames)
    assert d3["version"] == 3 and sorted(d3["current"]["changed"]) == ["b4", "b5"]
    assert "hostel register" in d3["current"]["text"] and "seven students" in d3["current"]["text"]
    assert not [f for f in d3["current"]["flags"] if f["severity"] == "error"], d3["current"]["flags"]

    n_requests = len(fake.requests)
    turn(b, "Undo the last change.")
    d4 = last_draft(frames)
    assert len(fake.requests) == n_requests                           # undo used no model call
    assert d4["version"] == 2 and d4["current"]["text"] == d2["current"]["text"] and d4["can_redo"]
    assert frames.data("draft.updated")[-1]["op"] == "undo"
    assert d4["first"]["text"] == d1["current"]["text"] and d4["original_text"] == WARDEN


def test_buttons_draft_op_and_draft_get(fake, tmp_path):
    b, frames, _ = make(fake, tmp_path, FakeCore())
    fake.scripts += [{"json": json.dumps(CREATE)}, {"json": json.dumps(REVISE_2)}]
    turn(b, WARDEN)
    turn(b, "Make it more diplomatic and shorten the second paragraph.")
    assert b.handle("draft_get", {"command": "draft_get", "session_id": SID})["draft"]["version"] == 2
    r = b.handle("draft_op", {"command": "draft_op", "session_id": SID, "op": "undo"})
    assert r["draft"]["version"] == 1 and r["draft"]["can_redo"]
    assert b.handle("draft_op", {"command": "draft_op", "session_id": SID, "op": "redo"})["draft"]["version"] == 2
    assert b.handle("draft_op", {"command": "draft_op", "session_id": SID, "op": "restore", "version": 1})["draft"][
        "current"]["op"] == "restored"
    for bad in ({"op": "send"}, {"op": "restore"}, {"op": "undo", "version": 1}):
        with pytest.raises(BridgeRefused):
            b.handle("draft_op", {"command": "draft_op", "session_id": SID, **bad})
    assert b.handle("draft_op", {"command": "draft_op", "session_id": SID, "op": "discard"})["draft"] is None
    with pytest.raises(BridgeRefused) as e:
        b.handle("draft_op", {"command": "draft_op", "session_id": SID, "op": "undo"})
    assert e.value.code == "NO_ACTIVE_DRAFT"


def test_brain_unavailable_changes_nothing_but_undo_still_works(fake, tmp_path):
    b, frames, o = make(fake, tmp_path, FakeCore())
    fake.scripts += [{"json": json.dumps(CREATE)}, {"json": json.dumps(REVISE_2)}]
    turn(b, WARDEN)
    turn(b, "Make it more diplomatic and shorten the second paragraph.")
    from uri_operational_intelligence.runtime_v1 import Readiness
    o.readiness = lambda: Readiness("STOPPED", fake.url, model_id="qwen-test")
    n = len(fake.requests)
    turn(b, "Make the first paragraph shorter.")
    assert frames.data("error")[-1]["code"] == "BRAIN_UNAVAILABLE" and len(fake.requests) == n
    assert b.handle("draft_get", {"command": "draft_get", "session_id": SID})["draft"]["version"] == 2
    turn(b, "Undo the last change.")
    assert last_draft(frames)["version"] == 1


def test_clarification_question_creates_no_version_and_answer_continues(fake, tmp_path):
    b, frames, _ = make(fake, tmp_path, FakeCore())
    clar = {"action": "clarify", "clarification": "Which date should change: the 6th or the 9th?", "fact_updates": [],
            "exclusions_add": [], "edits": [], "summary": ""}
    fake.scripts += [{"json": json.dumps(CREATE)}, {"json": json.dumps(clar)}, {"json": json.dumps(REVISE_2)}]
    turn(b, WARDEN)
    turn(b, "Change the date.")
    assert frames.data("draft.clarify")[-1]["question"].startswith("Which date")
    assert frames.data("turn.finished")[-1]["status"] == "needs_user"
    assert b.handle("draft_get", {"command": "draft_get", "session_id": SID})["draft"]["version"] == 1
    turn(b, "the 9th")                                   # no edit words: still routed to the draft as the answer
    assert frames.data("turn.routed")[-1]["route"] == "draft"
    req = json.loads(fake.requests[-1]["messages"][1]["content"])
    assert req["your_question"].startswith("Which date") and req["instruction"] == "the 9th"
    assert last_draft(frames)["version"] == 2


def test_cancel_during_generation_leaves_draft_unchanged(fake, tmp_path):
    b, frames, _ = make(fake, tmp_path, FakeCore())
    fake.scripts += [{"json": json.dumps(CREATE)}]
    turn(b, WARDEN)
    chunks = [("answer", c) for c in json.dumps(REVISE_2)]
    fake.scripts.append({"chunks": chunks, "finish": "stop", "delay": 0.01})
    r = b.handle("oi_turn", {"command": "oi_turn", "session_id": SID, "text": "Make the first paragraph shorter.",
                             "depth": "auto"})
    time.sleep(0.4)
    assert b.handle("oi_cancel", {"command": "oi_cancel", "turn_id": r["turn_id"]})["cancelled"] is True
    b.wait(15)
    assert frames.data("error")[-1]["code"] == "CANCELLED"
    assert b.handle("draft_get", {"command": "draft_get", "session_id": SID})["draft"]["version"] == 1


def test_simulated_transcript_is_labelled_and_raw_kept(fake, tmp_path):
    b, frames, _ = make(fake, tmp_path, FakeCore())
    raw = ("um URI write a letter to the warden about the students leaving hostel yesterday, no wait, on the 6th, and "
           "make it formal")
    created = dict(CREATE, facts=[{"key": "date", "value": "the 6th", "superseded": ["yesterday"]}],
                   blocks=[{"role": "body", "text": "Students left the hostel on the 6th."}])
    fake.scripts.append({"json": json.dumps(created)})
    env = {"schema": TI.SCHEMA, "source": "transcript", "transcript": {"raw": raw, "engine": "simulated",
                                                                         "simulated": True, "language": "en-IN"}}
    turn(b, raw, input=env)
    d = last_draft(frames)
    assert d["source"]["source"] == "transcript" and d["source"]["simulated"] is True and d["original_text"] == raw
    assert frames.data("turn.routed")[-1]["triage"]["source"] == "transcript"
    sent = json.loads(fake.requests[-1]["messages"][1]["content"])
    assert not sent["request"].startswith("um") and sent["input_source"] == "dictated speech" and "note" in sent
    assert not [f for f in d["current"]["flags"] if f["severity"] == "error"]
    # A recogniser that does not say it is simulated is refused when the engine says "simulated".
    with pytest.raises(BridgeRefused) as e:
        b.handle("oi_turn", {"command": "oi_turn", "session_id": SID, "text": raw, "depth": "auto",
                             "input": {**env, "transcript": {**env["transcript"], "simulated": False}}})
    assert e.value.code == "TRANSCRIPT_ENGINE"


def test_supersession_violation_is_flagged_not_hidden(fake, tmp_path):
    b, frames, _ = make(fake, tmp_path, FakeCore())
    bad = dict(CREATE, blocks=[{"role": "body", "text": "Five students left the hostel on Monday, 6 October."}])
    fake.scripts.append({"json": json.dumps(bad)})
    turn(b, WARDEN)
    codes = {f["code"] for f in last_draft(frames)["current"]["flags"]}
    assert {"SUPERSEDED_VALUE_PRESENT", "FACT_MISSING", "NEW_DETAIL"} <= codes
    assert "check(s) need your attention" in "".join(d["text"] for d in frames.data("answer.delta"))


def test_grammar_only_correction_keeps_original_as_version_one(fake, tmp_path):
    b, frames, _ = make(fake, tmp_path, FakeCore())
    edit = {"action": "edit", "clarification": None, "fact_updates": [], "exclusions_add": [],
            "edits": [{"op": "replace", "block_id": "b1", "role": "body",
                       "text": "Ramesh and I went to the market in Pune on 6 March."}], "summary": "Fixed grammar."}
    fake.scripts.append({"json": json.dumps(edit)})
    turn(b, "Correct this: me and Ramesh goes to market in Pune on 6 March")
    d = last_draft(frames)
    assert d["count"] == 2 and d["first"]["text"] == "me and Ramesh goes to market in Pune on 6 March"
    assert d["current"]["op"] == "corrected" and d["current"]["flags"] == []
    assert "grammar-only" in fake.requests[-1]["messages"][0]["content"]


def test_grammar_only_meaning_change_is_flagged(fake, tmp_path):
    b, frames, _ = make(fake, tmp_path, FakeCore())
    edit = {"action": "edit", "clarification": None, "fact_updates": [], "exclusions_add": [],
            "edits": [{"op": "replace", "block_id": "b1", "role": "body",
                       "text": "Ramesh and I went to the market in Mumbai on 7 March."}], "summary": "Fixed grammar."}
    fake.scripts.append({"json": json.dumps(edit)})
    turn(b, "Correct this: me and Ramesh goes to market in Pune on 6 March")
    assert "MEANING_CHANGED" in {f["code"] for f in last_draft(frames)["current"]["flags"]}


def test_not_an_edit_falls_back_to_the_ordinary_answer(fake, tmp_path):
    b, frames, _ = make(fake, tmp_path, FakeCore())
    fake.scripts += [{"json": json.dumps(CREATE)},
                     {"json": json.dumps({"action": "not_an_edit", "clarification": None, "fact_updates": [],
                                          "exclusions_add": [], "edits": [], "summary": ""})},
                     {"chunks": [("answer", "Hostel registers record entry and exit.")], "finish": "stop"}]
    turn(b, WARDEN)
    turn(b, "Make sense of why hostels keep registers")
    assert frames.data("turn.routed")[-1]["route"] == "answer"            # the ordinary path took over
    assert frames.data("turn.finished")[-1]["route"] in ("answer", "core+answer")
    assert b.handle("draft_get", {"command": "draft_get", "session_id": SID})["draft"]["version"] == 1


def test_action_in_same_request_goes_to_core_not_desk(fake, tmp_path):
    core = FakeCore([{"turn_id": "c1", "state": "failed", "code": "REFUSED_NO_CAPABILITY", "message": "No."}])
    b, frames, _ = make(fake, tmp_path, core)
    turn(b, "Draft a letter to the principal and send it to him")
    assert core.calls and core.calls[0][0] == "begin"
    assert frames.data("turn.routed")[-1]["route"] == "core" and not frames.data("draft.updated")


def test_greeting_keeps_fast_path(fake, tmp_path):
    fake.scripts.append({"chunks": [("answer", "Hello!")], "finish": "stop"})
    b, frames, _ = make(fake, tmp_path, FakeCore())
    turn(b, "hello")
    assert frames.data("turn.routed")[-1]["route"] == "answer" and not frames.data("draft.updated")
    assert "response_format" not in fake.requests[-1]


def test_draft_get_open_while_busy_and_draft_op_refused(fake, tmp_path):
    b, frames, _ = make(fake, tmp_path, FakeCore())
    fake.scripts.append({"json": json.dumps(CREATE), "first_delay": 0.8})
    r = b.handle("oi_turn", {"command": "oi_turn", "session_id": SID, "text": WARDEN, "depth": "auto"})
    time.sleep(0.1)
    assert b.handle("draft_get", {"command": "draft_get", "session_id": SID})["draft"] is None
    with pytest.raises(BridgeRefused) as e:
        b.handle("draft_op", {"command": "draft_op", "session_id": SID, "op": "undo"})
    assert e.value.code == "TURN_IN_PROGRESS"
    b.wait(15)


# ---- L-2: dictation versus commands -------------------------------------------------------------------------------
REFUSE = [{"turn_id": "c1", "state": "failed", "code": "REFUSED_NO_CAPABILITY", "message": "No."}]


def _edit(text, actions=()):
    return {"json": json.dumps({"action": "edit", "clarification": None, "fact_updates": [], "exclusions_add": [],
                                "actions_requested": list(actions),
                                "edits": [{"op": "replace", "block_id": "b1", "role": "body", "text": text}],
                                "summary": "Corrected."})}


def test_l2_write_marker_makes_a_dictated_command_content_never_core(fake, tmp_path):
    core = FakeCore(REFUSE)
    b, frames, _ = make(fake, tmp_path, core)
    fake.scripts.append(_edit("Send this letter to the director.", actions=["send this letter"]))
    turn(b, "Write: send this letter to the director.")
    assert frames.data("turn.routed")[-1]["route"] == "draft" and core.calls == []
    d = last_draft(frames)
    assert d["current"]["text"] == "Send this letter to the director."
    codes = {f["code"]: f for f in d["current"]["flags"]}
    assert codes["DICTATED_INSTRUCTION"]["severity"] == "info" and "send this letter" in codes["DICTATED_INSTRUCTION"]["detail"]
    req = fake.requests[-1]["messages"]
    assert "grammar-only" in req[0]["content"] and "Dictated content" in req[1]["content"]


def test_l2_dictation_mode_never_reaches_core_even_when_the_model_reports_actions(fake, tmp_path):
    core = FakeCore(REFUSE)
    b, frames, _ = make(fake, tmp_path, core)
    fake.scripts.append(_edit("Delete the previous paragraph. Send the form by Friday.", actions=["send the form"]))
    turn(b, "delete the previous paragraph send the form by friday",
         input={"schema": TI.SCHEMA, "source": "typed", "mode": "dictation"})
    assert core.calls == [] and frames.data("turn.routed")[-1]["triage"]["reasons"] == ["dictation_mode"]
    d = last_draft(frames)
    assert d["current"]["op"] == "corrected" and d["source"]["mode"] == "dictation"
    assert d["first"]["text"] == "delete the previous paragraph send the form by friday"


def test_l2_dictation_transcript_with_rewrite_scope(fake, tmp_path):
    b, frames, _ = make(fake, tmp_path, FakeCore(REFUSE))
    fake.scripts.append(_edit("Please submit the form by Friday."))
    raw = "um send the form by friday"
    turn(b, raw, input={"schema": TI.SCHEMA, "source": "transcript", "mode": "dictation", "scope": "rewrite",
                        "transcript": {"raw": raw, "engine": "simulated", "simulated": True}})
    d = last_draft(frames)
    assert d["current"]["op"] == "rewritten" and d["source"]["scope"] == "rewrite" and d["source"]["raw"] == raw
    assert "MODE: rewrite" in fake.requests[-1]["messages"][0]["content"]


def test_l2_command_mode_goes_to_the_ordinary_path_never_a_draft(fake, tmp_path):
    core = FakeCore(REFUSE)
    b, frames, _ = make(fake, tmp_path, core)
    turn(b, "Send the form to the office", input={"schema": TI.SCHEMA, "source": "typed", "mode": "command"})
    assert core.calls and core.calls[0][0] == "begin" and not frames.data("draft.updated")


def test_l2_ambiguous_action_sentence_asks_without_a_model_call_then_write_it_in(fake, tmp_path):
    core = FakeCore(REFUSE)
    b, frames, _ = make(fake, tmp_path, core)
    turn(b, "Write a notice. Send the form by Friday.")
    assert frames.data("draft.clarify")[-1]["question"].startswith("Should “Send the form by Friday”")
    assert fake.requests == [] and core.calls == [] and not frames.data("draft.updated")
    notice = dict(CREATE, actions_requested=["send the form"], doc_type="notice",
                  blocks=[{"role": "subject", "text": "Notice"},
                          {"role": "body", "text": "Send the form to the office by Friday."}])
    fake.scripts.append({"json": json.dumps(notice)})
    turn(b, "Write it in")
    assert core.calls == []                                  # the user's choice: content, so no reroute to Core
    d = last_draft(frames)
    assert "Send the form" in d["current"]["text"]
    assert "DICTATED_INSTRUCTION" in {f["code"] for f in d["current"]["flags"]}
    assert "dictated_sentences" in fake.requests[-1]["messages"][1]["content"]


def test_l2_ambiguous_then_do_it_hands_the_original_request_to_core(fake, tmp_path):
    core = FakeCore(REFUSE)
    b, frames, _ = make(fake, tmp_path, core)
    turn(b, "Write a notice. Send the form by Friday.")
    turn(b, "Do it")
    assert core.calls and core.calls[0][0] == "begin" and core.calls[0][1] == "Write a notice. Send the form by Friday."
    assert not frames.data("draft.updated") and fake.requests == []


def test_l2_send_this_letter_is_a_command_and_the_draft_is_untouched(fake, tmp_path):
    core = FakeCore(REFUSE)
    b, frames, _ = make(fake, tmp_path, core)
    fake.scripts.append({"json": json.dumps(CREATE)})
    turn(b, WARDEN)
    turn(b, "Send this letter to the director.")
    assert core.calls and core.calls[-1][0] == "begin"        # Core decides (and here refuses: no capability)
    assert b.handle("draft_get", {"command": "draft_get", "session_id": SID})["draft"]["version"] == 1


def test_l2_delete_the_previous_paragraph_edits_the_draft_only(fake, tmp_path):
    core = FakeCore(REFUSE)
    b, frames, _ = make(fake, tmp_path, core)
    fake.scripts += [{"json": json.dumps(CREATE)},
                     {"json": json.dumps({"action": "edit", "clarification": None, "fact_updates": [],
                                          "exclusions_add": [], "edits": [{"op": "delete", "block_id": "b5"}],
                                          "summary": "Removed the second paragraph."})}]
    turn(b, WARDEN)
    turn(b, "Delete the previous paragraph.")
    assert core.calls == [] and frames.data("turn.routed")[-1]["route"] == "draft"


# ---- L-4: value reassignment ----------------------------------------------------------------------------------------
FEES = dict(CREATE, facts=[], doc_type="note",
            blocks=[{"role": "body", "text": "Ravi paid Rs 500 and Sita paid Rs 700 for the trip."}])


def test_l4_swapped_values_get_an_advisory_flag_and_nothing_is_reverted(fake, tmp_path):
    b, frames, _ = make(fake, tmp_path, FakeCore(REFUSE))
    fake.scripts += [{"json": json.dumps(FEES)}, _edit("Ravi paid Rs 700 and Sita paid Rs 500 for the school trip.")]
    turn(b, "Write a note: Ravi paid Rs 500 and Sita paid Rs 700 for the trip.")
    turn(b, "Make it clearer that it was the school trip.")
    d = last_draft(frames)
    f = [x for x in d["current"]["flags"] if x["code"] == "VALUE_REASSIGNED"]
    assert f and f[0]["severity"] == "review" and "Ravi" in f[0]["detail"] and "Sita" in f[0]["detail"]
    assert "Rs 700 and Sita paid Rs 500" in d["current"]["text"]            # shown, not reverted
    assert d["previous"]["text"] == "Ravi paid Rs 500 and Sita paid Rs 700 for the trip."   # Changes view basis


def test_l4_an_asked_for_reassignment_is_shown_as_asked(fake, tmp_path):
    b, frames, _ = make(fake, tmp_path, FakeCore(REFUSE))
    fake.scripts += [{"json": json.dumps(FEES)}, _edit("Ravi paid Rs 700 and Sita paid Rs 500 for the trip.")]
    turn(b, "Write a note: Ravi paid Rs 500 and Sita paid Rs 700 for the trip.")
    turn(b, "Actually Ravi paid 700 and Sita paid 500.")
    codes = {x["code"]: x["severity"] for x in last_draft(frames)["current"]["flags"]}
    assert codes.get("VALUE_REASSIGNED_AS_ASKED") == "info" and "VALUE_REASSIGNED" not in codes


@pytest.mark.parametrize("answer", ["No, not in the text; do it", "No, don't do it", "Write it in, or do it"])
def test_l2_negated_or_conflicting_answers_are_asked_again_never_guessed(fake, tmp_path, answer):
    core = FakeCore(REFUSE)
    b, frames, _ = make(fake, tmp_path, core)
    turn(b, "Write a notice. Send the form by Friday.")
    turn(b, answer)
    assert core.calls == [] and fake.requests == [] and not frames.data("draft.updated")   # nothing guessed
    assert frames.data("draft.clarify")[-1]["question"].startswith("I could not tell which you meant")
    turn(b, "Do it")                                   # the question is still open: a clear answer now decides
    assert core.calls and core.calls[0][1] == "Write a notice. Send the form by Friday."


@pytest.mark.parametrize("answer", ["dont do it", "yes", "no", "No, not in the text, do it", "do it in the text"])
def test_l2_only_an_exact_choice_decides_the_dictation_question(fake, tmp_path, answer):
    core = FakeCore(REFUSE)
    b, frames, _ = make(fake, tmp_path, core)
    turn(b, "Write a notice. Send the form by Friday.")
    turn(b, answer)
    assert core.calls == [] and fake.requests == [] and not frames.data("draft.updated")
    assert frames.data("draft.clarify")[-1]["question"].startswith("I could not tell which you meant")


def test_l2_a_new_request_drops_the_dictation_question(fake, tmp_path):
    core = FakeCore(REFUSE)
    b, frames, _ = make(fake, tmp_path, core)
    fake.scripts.append({"chunks": [("answer", "Paris.")], "finish": "stop"})
    turn(b, "Write a notice. Send the form by Friday.")
    turn(b, "What is the capital of France?")
    assert frames.data("turn.routed")[-1]["route"] == "answer" and core.calls == []
    turn(b, "Do it")                 # the question was dropped: "do it" alone is no longer an answer to it
    assert not any(c[1] == "Write a notice. Send the form by Friday." for c in core.calls)


@pytest.mark.parametrize("answer", ["Write it in", "ok, write it in please", "Do it", "yes, do it"])
def test_l2_exact_choices_with_politeness_decide(fake, tmp_path, answer):
    core = FakeCore(REFUSE)
    b, frames, _ = make(fake, tmp_path, core)
    notice = dict(CREATE, doc_type="notice", blocks=[{"role": "body", "text": "Send the form by Friday."}])
    fake.scripts.append({"json": json.dumps(notice)})
    turn(b, "Write a notice. Send the form by Friday.")
    turn(b, answer)
    if "do it" in answer.lower():
        assert core.calls and core.calls[0][1] == "Write a notice. Send the form by Friday."
    else:
        assert core.calls == [] and frames.data("draft.updated")


# ---- TI x A2UI (canonical 1587449): the scheduling handoff and the draft desk -------------------------------------
FESTIVAL = ("URI, schedule Claude to create a festival GIF two days before each major Indian festival and bring it to "
            "me for approval.")


def test_a2ui_handoff_still_precedes_the_desk_in_auto_mode(fake, tmp_path):
    core = FakeCore(REFUSE)
    b, frames, _ = make(fake, tmp_path, core)
    turn(b, FESTIVAL)
    assert frames.data("turn.routed")[-1]["route"] == "a2ui" and frames.data("a2ui.handoff")
    assert fake.requests == [] and core.calls == [] and not frames.data("draft.updated")


def test_a2ui_dictated_schedule_request_is_content_never_a_handoff(fake, tmp_path):
    core = FakeCore(REFUSE)
    b, frames, _ = make(fake, tmp_path, core)
    fake.scripts.append(_edit(FESTIVAL.replace("URI, schedule", "Schedule")))
    turn(b, FESTIVAL, input={"schema": TI.SCHEMA, "source": "typed", "mode": "dictation"})
    assert not frames.data("a2ui.handoff") and core.calls == []
    assert frames.data("turn.routed")[-1]["route"] == "draft" and last_draft(frames)["current"]["op"] == "corrected"


def test_a2ui_transcript_handoff_reads_the_cleaned_words(fake, tmp_path):
    b, frames, _ = make(fake, tmp_path, FakeCore(REFUSE))
    raw = "um uri, schedule Claude to to create a festival GIF two days before each major Indian festival and bring it to me for approval"
    turn(b, raw, input={"schema": TI.SCHEMA, "source": "transcript",
                        "transcript": {"raw": raw, "engine": "simulated", "simulated": True}})
    h = frames.data("a2ui.handoff")
    assert h and h[0]["request"]["offset_days"] == 2


def test_a2ui_handoff_drops_an_open_draft_question(fake, tmp_path):
    core = FakeCore(REFUSE)
    b, frames, _ = make(fake, tmp_path, core)
    turn(b, "Write a notice. Send the form by Friday.")           # TI question is open
    turn(b, FESTIVAL)                                              # a new request: the scheduler handoff
    assert frames.data("a2ui.handoff")
    turn(b, "Do it")                                               # no longer an answer to the TI question
    assert not any(c[1] == "Write a notice. Send the form by Friday." for c in core.calls)
