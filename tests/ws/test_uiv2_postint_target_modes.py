"""UIV2-F1 explicit target (2026-10-16): the Workspace composer sends input mode "conversation" by default while a
draft is open (nothing can change it) and mode "draft" only after the user chose the draft. Bridge-level tests with the
scripted fake Runtime v1; the UI side is uri_ui/test/living/uiv2_postint_test.dart.
"""
import json

import pytest

from tests.oi.fake_llama import FakeLlama
from tests.oi.test_oi_orchestrator import FakeCore
from tests.ws.test_ti_desk_bridge import CREATE, REVISE_2, WARDEN, turn
from tests.ws.test_ws_worker_bridge import SID, make
from uri_operational_intelligence import text_input as TI

CONVERSATION = {"schema": TI.SCHEMA, "source": "typed", "mode": "conversation"}
DRAFT = {"schema": TI.SCHEMA, "source": "typed", "mode": "draft"}
NOT_AN_EDIT = {"action": "not_an_edit", "clarification": None, "fact_updates": [], "exclusions_add": [], "edits": [],
               "summary": ""}


@pytest.fixture
def fake():
    with FakeLlama() as f:
        yield f


def _draft(b):
    return b.handle("draft_get", {"command": "draft_get", "session_id": SID})["draft"]


@pytest.mark.parametrize("text", ["Make it more diplomatic and shorten the second paragraph.", "Make my letter shorter",
                                  "Change the date to Tuesday", "Replace the name with Ravi", "undo",
                                  "Say hello in three words"])
def test_conversation_target_never_changes_the_open_draft(fake, tmp_path, text):
    b, frames, _ = make(fake, tmp_path, FakeCore())
    fake.scripts += [{"json": json.dumps(CREATE)}, {"chunks": [("answer", "Sure.")], "finish": "stop"}]
    turn(b, WARDEN)
    before = _draft(b)
    n = len(frames.data("draft.updated"))
    turn(b, text, input=CONVERSATION)
    after = _draft(b)
    assert after["draft_id"] == before["draft_id"] and after["version"] == before["version"]
    assert after["current"] == before["current"] and len(frames.data("draft.updated")) == n


def test_conversation_target_new_document_keeps_the_open_one(fake, tmp_path):
    other = json.loads(json.dumps(CREATE))
    other["blocks"] = [{"role": "body", "text": "The library opens at 8 am from Monday."}]
    b, frames, _ = make(fake, tmp_path, FakeCore())
    fake.scripts += [{"json": json.dumps(CREATE)}, {"json": json.dumps(other)}]
    turn(b, WARDEN)
    letter = _draft(b)
    turn(b, "Draft a new notice that the library will open at 8 am from Monday.", input=CONVERSATION)
    new = _draft(b)
    assert new["draft_id"] != letter["draft_id"] and new["replaced"]["doc_type"] == "letter"
    back = b.handle("draft_op", {"command": "draft_op", "session_id": SID, "op": "undo"})["draft"]
    assert back["draft_id"] == letter["draft_id"] and back["current"] == letter["current"]


def test_conversation_target_drops_an_open_draft_question(fake, tmp_path):
    clar = {"action": "clarify", "clarification": "Which date should the letter use?", "fact_updates": [],
            "exclusions_add": [], "edits": [], "summary": ""}
    b, frames, _ = make(fake, tmp_path, FakeCore())
    fake.scripts += [{"json": json.dumps(CREATE)}, {"json": json.dumps(clar)},
                     {"chunks": [("answer", "Tuesday is a weekday.")], "finish": "stop"}]
    turn(b, WARDEN)
    turn(b, "Change the date", input=DRAFT)
    assert _draft(b)["pending_question"]
    turn(b, "Tuesday", input=CONVERSATION)
    d = _draft(b)
    assert d["pending_question"] is None and d["version"] == 1


def test_draft_target_makes_an_edit_explicit(fake, tmp_path):
    b, frames, _ = make(fake, tmp_path, FakeCore())
    fake.scripts += [{"json": json.dumps(CREATE)}, {"json": json.dumps(REVISE_2)}]
    turn(b, WARDEN)
    turn(b, "Make my letter shorter", input=DRAFT)          # R4-03: an edit, not a new document
    assert _draft(b)["version"] == 2


def test_draft_target_still_answers_what_is_not_an_edit(fake, tmp_path):
    b, frames, _ = make(fake, tmp_path, FakeCore())
    fake.scripts += [{"json": json.dumps(CREATE)}, {"json": json.dumps(NOT_AN_EDIT)},
                     {"chunks": [("answer", "Here is one.")], "finish": "stop"}]
    turn(b, WARDEN)
    turn(b, "Tell me a joke", input=DRAFT)
    assert frames.data("turn.routed")[-1]["route"] == "answer" and _draft(b)["version"] == 1


def test_draft_target_never_lets_an_action_bypass_core(fake, tmp_path):
    core = FakeCore([{"turn_id": "c1", "state": "failed", "code": "REFUSED_NO_CAPABILITY", "message": "No."}])
    b, frames, _ = make(fake, tmp_path, core)
    fake.scripts += [{"json": json.dumps(CREATE)}]
    turn(b, WARDEN)
    turn(b, "Send it to the warden", input=DRAFT)
    assert core.calls and core.calls[-1][0] == "begin" and _draft(b)["version"] == 1


def test_unknown_mode_is_refused():
    with pytest.raises(TI.InputRejected):
        TI.parse({"schema": TI.SCHEMA, "source": "typed", "mode": "edit"}, "x")


def test_draft_target_name_placeholder_edit(fake, tmp_path):
    """R4-02: 'Replace my name with Ravi in the draft' said to the draft is an edit of it."""
    b, frames, _ = make(fake, tmp_path, FakeCore())
    sign = {"action": "edit", "clarification": None, "fact_updates": [], "exclusions_add": [],
            "edits": [{"op": "replace", "block_id": "b8", "role": "signature", "text": "Ravi, Warden's office"}],
            "summary": "Signed as Ravi."}
    fake.scripts += [{"json": json.dumps(CREATE)}, {"json": json.dumps(sign)}]
    turn(b, WARDEN)
    turn(b, "Replace my name with Ravi in the draft", input=DRAFT)
    assert _draft(b)["version"] == 2


def test_conversation_target_rewrite_without_text_is_answered_not_refused(fake, tmp_path):
    """Live l8: 'Make it shorter and tell me a joke' in conversation mode reached the desk without text
    (TEXT_MISSING). Without text it refers to the conversation: the ordinary path answers; the draft is unchanged."""
    b, frames, _ = make(fake, tmp_path, FakeCore())
    fake.scripts += [{"json": json.dumps(CREATE)}, {"chunks": [("answer", "A short joke.")], "finish": "stop"}]
    turn(b, WARDEN)
    before = _draft(b)
    turn(b, "Make it shorter and tell me a joke in a formal tone.", input=CONVERSATION)
    assert frames.data("turn.routed")[-1]["route"] == "answer"
    assert _draft(b)["current"] == before["current"]


def _notice(text):
    other = json.loads(json.dumps(CREATE))
    other["blocks"] = [{"role": "body", "text": text}]
    return other


def test_two_new_documents_keep_both_earlier_drafts_reachable_by_undo(fake, tmp_path):
    """C1-01: a second new document must not drop the first draft."""
    b, frames, _ = make(fake, tmp_path, FakeCore())
    fake.scripts += [{"json": json.dumps(CREATE)}, {"json": json.dumps(_notice("Library opens at 8 am."))},
                     {"json": json.dumps(_notice("Mess closed on Sunday."))}]
    turn(b, WARDEN)
    letter = _draft(b)
    turn(b, "Draft a new notice that the library will open at 8 am from Monday.", input=CONVERSATION)
    first_notice = _draft(b)
    turn(b, "Draft a new notice that the mess will be closed on Sunday.", input=CONVERSATION)
    back1 = b.handle("draft_op", {"command": "draft_op", "session_id": SID, "op": "undo"})["draft"]
    assert back1["draft_id"] == first_notice["draft_id"] and back1["can_undo"] is True
    back2 = b.handle("draft_op", {"command": "draft_op", "session_id": SID, "op": "undo"})["draft"]
    assert back2["draft_id"] == letter["draft_id"] and back2["current"] == letter["current"]
    fwd = b.handle("draft_op", {"command": "draft_op", "session_id": SID, "op": "redo"})["draft"]
    assert fwd["draft_id"] == first_notice["draft_id"]


def test_closing_a_replacing_draft_brings_the_replaced_one_back(fake, tmp_path):
    """C1-04: Close on a draft that replaced another must not lose that one."""
    b, frames, _ = make(fake, tmp_path, FakeCore())
    fake.scripts += [{"json": json.dumps(CREATE)}, {"json": json.dumps(_notice("Library opens at 8 am."))}]
    turn(b, WARDEN)
    letter = _draft(b)
    turn(b, "Draft a new notice that the library will open at 8 am from Monday.", input=CONVERSATION)
    after = b.handle("draft_op", {"command": "draft_op", "session_id": SID, "op": "discard"})["draft"]
    assert after["draft_id"] == letter["draft_id"] and after["current"] == letter["current"]
    assert b.handle("draft_op", {"command": "draft_op", "session_id": SID, "op": "discard"})["draft"] is None


def test_typed_close_emits_the_restored_draft_and_describes_it(fake, tmp_path):
    """A typed Close must give the UI the same draft the worker now holds."""
    b, frames, _ = make(fake, tmp_path, FakeCore())
    fake.scripts += [{"json": json.dumps(CREATE)}, {"json": json.dumps(_notice("Library opens at 8 am."))}]
    turn(b, WARDEN)
    letter = _draft(b)
    turn(b, "Draft a new notice that the library will open at 8 am from Monday.", input=CONVERSATION)

    turn(b, "Close draft", input=DRAFT)
    restored = _draft(b)
    assert restored["draft_id"] == letter["draft_id"]
    assert frames.data("draft.updated")[-1] == {"op": "discard", "draft": restored}
    assert "earlier letter draft is back" in frames.data("answer.delta")[-1]["text"]

    turn(b, "Close draft", input=DRAFT)
    assert _draft(b) is None
    assert frames.data("draft.updated")[-1] == {"op": "discard", "draft": None}
