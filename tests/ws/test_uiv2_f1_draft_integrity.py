"""UIV2-F1 (2026-10-16): ordinary conversation never silently modifies an open document draft.

Live finding (UI V2 l9): with a Text Intelligence draft open, "Say hello in three words" typed in the Companion chat
became "Letter (version 2 of 2)". Root causes: (1) the deterministic classifier read any message opening with a
revision-like verb ("say", "write", "call", "it's", "not" ...) as an edit of the open draft; (2) a new document
replaced the open draft with no way back. These tests pin the repaired behaviour; the UI layer (Companion and
dashboard turns go as mode "command" while a draft is open) is covered by the Flutter test
uri_ui/test/living/uiv2_f1_draft_scope_test.dart.
"""
import json

import pytest

from tests.oi.fake_llama import FakeLlama
from tests.oi.test_oi_orchestrator import FakeCore
from tests.ws.test_ti_desk_bridge import CREATE, REVISE_2, WARDEN, last_draft, turn
from tests.ws.test_ws_worker_bridge import SID, make
from uri_operational_intelligence import text_input as TI
from uri_operational_intelligence import text_intent as X
from uri_operational_intelligence import draft_store as DS
from uri_operational_intelligence.draft_desk import DraftDesk

LETTER = "\n\n".join(b["text"] for b in CREATE["blocks"])

ORDINARY_CHAT = [
    "Say hello in three words", "Write a haiku about rain", "Call me Ravi", "It's raining today", "Not now",
    "Leave it", "Use a calm voice please", "Start a timer", "Update me on the weather", "Put some music on",
    "Mark this as done", "Spell necessary", "Make me a plan for the week", "Add milk to my shopping list",
    "Change of plans, let us go to the park", "Summarise the news", "Simplify my life", "Fix my wifi",
    "Tell me a joke", "What is the capital of France?", "Thanks, that is good",
    "Tell me a joke in a formal tone", "Please change your tone", "Not now, but later",
    "It should be sunny tomorrow",
]
DRAFT_EDITS = [
    "Make it shorter", "Shorten it", "Simplify", "Polish it a bit", "Improve grammar", "Add a line about the fee",
    "Change the date to Monday", "Address it to the principal", "Sign it as Principal", "Keep it short",
    "Include the fee amount", "Mention the deadline", "Say 'Respected Sir' instead", "End with 'Yours faithfully'",
    "It's Tuesday, not Monday", "No, I meant Tuesday.", "Sorry, not five students, seven.",
    "Remove the previous sentence.", "Make the second paragraph more formal.", "Keep everything else the same.",
    "Don't mention the student's name.", "isko thoda formal karo",
]


@pytest.mark.parametrize("text", ORDINARY_CHAT)
def test_ordinary_chat_with_an_open_draft_is_not_an_edit(text):
    r = X.classify(text, has_draft=True, draft_text=LETTER)
    assert r.kind not in (X.REVISE, X.DRAFT_NEW, X.CORRECT, X.REWRITE, X.EXPAND), (text, r.kind, r.reasons)


@pytest.mark.parametrize("text", DRAFT_EDITS)
def test_explicit_draft_edits_still_edit(text):
    assert X.classify(text, has_draft=True, draft_text=LETTER).kind == X.REVISE, text


def test_a_correction_reusing_the_documents_own_words_is_anchored():
    assert X.classify("Actually seven students left on Tuesday.", has_draft=True, draft_text=LETTER).kind == X.REVISE
    # the same words without a draft text to compare with stay ordinary conversation
    assert X.classify("Actually seven students left on Tuesday.", has_draft=True).kind == X.NONE


@pytest.fixture
def fake():
    with FakeLlama() as f:
        yield f


def _version(b):
    return b.handle("draft_get", {"command": "draft_get", "session_id": SID})["draft"]


def test_live_l9_say_hello_is_answered_and_the_draft_is_untouched(fake, tmp_path):
    b, frames, _ = make(fake, tmp_path, FakeCore())
    fake.scripts += [{"json": json.dumps(CREATE)}, {"chunks": [("answer", "Hello there, friend.")], "finish": "stop"}]
    turn(b, WARDEN)
    before = _version(b)
    n_updates = len(frames.data("draft.updated"))
    turn(b, "Say hello in three words")
    assert frames.data("turn.routed")[-1]["route"] == "answer"
    after = _version(b)
    assert after["version"] == before["version"] == 1 and after["current"] == before["current"]
    assert len(frames.data("draft.updated")) == n_updates          # no draft event at all


def test_command_mode_from_a_surface_without_the_draft_never_edits_it(fake, tmp_path):
    """The Companion and dashboard composers send mode "command" while a draft is open: even an explicit edit
    request goes to the ordinary path, because the user cannot see the draft there."""
    b, frames, _ = make(fake, tmp_path, FakeCore())
    fake.scripts += [{"json": json.dumps(CREATE)}, {"chunks": [("answer", "Open Workspace to edit it.")],
                                                    "finish": "stop"}]
    turn(b, WARDEN)
    n_updates = len(frames.data("draft.updated"))
    turn(b, "Make it more diplomatic and shorten the second paragraph.",
         input={"schema": TI.SCHEMA, "source": "typed", "mode": "command"})
    assert len(frames.data("draft.updated")) == n_updates and _version(b)["version"] == 1


def test_an_authorised_edit_in_the_workspace_still_works(fake, tmp_path):
    b, frames, _ = make(fake, tmp_path, FakeCore())
    fake.scripts += [{"json": json.dumps(CREATE)}, {"json": json.dumps(REVISE_2)}]
    turn(b, WARDEN)
    turn(b, "Make it more diplomatic and shorten the second paragraph.")
    assert last_draft(frames)["version"] == 2


def _create_principal():
    other = json.loads(json.dumps(CREATE))
    other["blocks"] = [{"role": "subject", "text": "Subject: Library timings"},
                       {"role": "body", "text": "The library will open at 8 am from Monday."}]
    other["summary"] = "A note to the principal about the library."
    return other


def test_a_new_document_keeps_the_replaced_draft_and_undo_brings_it_back(fake, tmp_path):
    b, frames, _ = make(fake, tmp_path, FakeCore())
    fake.scripts += [{"json": json.dumps(CREATE)}, {"json": json.dumps(REVISE_2)},
                     {"json": json.dumps(_create_principal())}]
    turn(b, WARDEN)
    turn(b, "Make it more diplomatic and shorten the second paragraph.")
    warden = _version(b)
    assert warden["version"] == 2
    turn(b, "Draft a new letter to the principal about the library")
    new = _version(b)
    assert new["draft_id"] != warden["draft_id"] and new["position"] == 1
    assert new["can_undo"] is True and new["replaced"] == {"doc_type": "letter", "version": 2}
    back = b.handle("draft_op", {"command": "draft_op", "session_id": SID, "op": "undo"})["draft"]
    assert back["draft_id"] == warden["draft_id"] and back["current"] == warden["current"]   # nothing lost
    assert back["can_redo"] is True
    fwd = b.handle("draft_op", {"command": "draft_op", "session_id": SID, "op": "redo"})["draft"]
    assert fwd["draft_id"] == new["draft_id"] and fwd["current"] == new["current"]
    # undo inside the restored draft still walks its own versions
    b.handle("draft_op", {"command": "draft_op", "session_id": SID, "op": "undo"})
    v1 = b.handle("draft_op", {"command": "draft_op", "session_id": SID, "op": "undo"})["draft"]
    assert v1["draft_id"] == warden["draft_id"] and v1["version"] == 1


def test_an_edit_after_going_back_ends_the_way_forward(fake, tmp_path):
    b, frames, _ = make(fake, tmp_path, FakeCore())
    fake.scripts += [{"json": json.dumps(CREATE)}, {"json": json.dumps(_create_principal())},
                     {"json": json.dumps(REVISE_2)}]
    turn(b, WARDEN)
    turn(b, "Draft a new letter to the principal about the library")
    back = b.handle("draft_op", {"command": "draft_op", "session_id": SID, "op": "undo"})["draft"]
    assert back["position"] == 1 and back["can_redo"] is True
    turn(b, "Make it more diplomatic and shorten the second paragraph.")
    d = _version(b)
    assert d["version"] == 2 and d["can_redo"] is False


def _memory_draft(desk, label):
    draft = DS.Draft(session_id=SID, doc_type="letter", tone="formal", source={}, original_text=label)
    draft.push(blocks=[DS.Block("b1", "body", label)], facts=[], exclusions=[], missing=[], op="created",
               instruction=label, summary=label, changed=["b1"], removed=[], flags=[])
    desk._set(SID, draft)
    return draft


@pytest.mark.parametrize("text", ["Tell me a joke", "Start a timer", "It should be sunny tomorrow"])
def test_unrelated_reply_drops_an_open_draft_question(text):
    desk = DraftDesk(None)
    draft = _memory_draft(desk, "The letter uses Monday.")
    draft.pending_question = "What date should the letter use?"
    intent = desk.classify(text, SID)
    assert intent.kind == X.NONE
    assert draft.pending_question is None
    assert draft.current.n == 1


@pytest.mark.parametrize("text", ["the 9th", "Tuesday; the principal should get it by email too"])
def test_short_reply_to_a_pending_date_question_stays_in_the_draft(text):
    desk = DraftDesk(None)
    draft = _memory_draft(desk, "The letter uses Monday.")
    draft.pending_question = "What date should the letter use?"
    intent = desk.classify(text, SID)
    assert intent.kind == X.REVISE and intent.reasons == ["answer_to_clarification"]
    assert draft.pending_question == "What date should the letter use?"


def test_redo_returns_to_new_document_from_replaced_drafts_undone_version():
    desk = DraftDesk(None)
    first = _memory_draft(desk, "Draft A")
    first.push(blocks=[DS.Block("b1", "body", "Draft A revised")], facts=[], exclusions=[], missing=[],
               op="revised", instruction="Revise A", summary="Revised", changed=["b1"], removed=[], flags=[])
    first.undo()
    second = _memory_draft(desk, "Draft B")
    assert desk.op(SID, "undo")["draft_id"] == first.draft_id
    assert first.cursor == 0 and first.can_redo
    assert desk.op(SID, "redo")["draft_id"] == second.draft_id


def test_edit_at_replacement_boundary_clears_redo_to_new_document():
    desk = DraftDesk(None)
    first = _memory_draft(desk, "Draft A")
    first.push(blocks=[DS.Block("b1", "body", "Draft A revised")], facts=[], exclusions=[], missing=[],
               op="revised", instruction="Revise A", summary="Revised", changed=["b1"], removed=[], flags=[])
    first.undo()
    _memory_draft(desk, "Draft B")
    desk.op(SID, "undo")
    first.push(blocks=[DS.Block("b1", "body", "Draft A edited again")], facts=[], exclusions=[], missing=[],
               op="revised", instruction="Edit A", summary="Edited", changed=["b1"], removed=[], flags=[])
    assert not first.can_redo
