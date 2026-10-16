"""UI-V2-POSTINT: a revision must identify the open draft as its object."""

import json

import pytest

from tests.oi.fake_llama import FakeLlama
from tests.oi.test_oi_orchestrator import FakeCore
from tests.ws.test_ti_desk_bridge import CREATE, WARDEN, turn
from tests.ws.test_uiv2_f1_draft_integrity import _memory_draft
from tests.ws.test_ws_worker_bridge import SID, make
from uri_operational_intelligence import text_intent as X
from uri_operational_intelligence.draft_desk import DraftDesk


LETTER = "\n\n".join(block["text"] for block in CREATE["blocks"])


@pytest.mark.parametrize("text,draft_text", [
    ("Change the date of my appointment to Friday", LETTER + "\nAppointment records are attached."),
    ("Delete my last message", LETTER + "\nThe last message was received."),
    ("Delete the last message", LETTER),
    ("Shorten the last message", LETTER),
    ("Change the subject of our meeting to budgets", LETTER),
    ("Change the date of my note to Friday", LETTER),
    ("I meant to ask about the weather", LETTER),
    ("No, I meant Ravi.", LETTER),
    ("Replace the weather report with a forecast", LETTER + "\nThe weather data is attached."),
])
def test_unrelated_object_does_not_become_the_open_draft(text, draft_text):
    result = X.classify(text, has_draft=True, draft_text=draft_text)
    assert result.kind == X.NONE, (text, result.kind, result.reasons)


@pytest.mark.parametrize("text", [
    "Change the date of my appointment to Friday",
    "Delete the last message",
    "Change the subject of our meeting to budgets",
    "Change the date of my note to Friday",
])
def test_workspace_desk_routes_unrelated_requests_away_from_revision(text):
    desk = DraftDesk(None)
    draft = _memory_draft(desk, LETTER + "\nAppointment records and meeting notes are attached.")
    before = draft.current.n
    assert desk.classify(text, SID).kind == X.NONE
    assert draft.current.n == before


@pytest.mark.parametrize("text", ["Delete the last message", "Change the subject of our meeting to budgets"])
def test_workspace_turn_keeps_the_draft_and_routes_to_conversation(text, tmp_path):
    with FakeLlama() as fake:
        bridge, frames, _ = make(fake, tmp_path, FakeCore())
        fake.scripts += [{"json": json.dumps(CREATE)}, {"chunks": [("answer", "I can help with that.")],
                                                       "finish": "stop"}]
        turn(bridge, WARDEN)
        before = bridge.handle("draft_get", {"command": "draft_get", "session_id": SID})["draft"]
        updates = len(frames.data("draft.updated"))
        turn(bridge, text)
        after = bridge.handle("draft_get", {"command": "draft_get", "session_id": SID})["draft"]
        assert frames.data("turn.routed")[-1]["route"] == "answer"
        assert after["version"] == before["version"] and after["current"] == before["current"]
        assert len(frames.data("draft.updated")) == updates


@pytest.mark.parametrize("text", ["Replace the name with Ravi", "Change the name to Ravi"])
def test_name_edit_resolves_to_the_draft_placeholder(text):
    assert X.classify(text, has_draft=True, draft_text=LETTER).kind == X.REVISE
    assert X.classify(text, has_draft=True, draft_text=LETTER.replace("[Your Name]", "[Signature]")).kind == X.NONE


def test_document_noun_must_match_the_open_draft_type():
    text = "Change the date of my note to Friday"
    assert X.classify(text, has_draft=True, draft_text=LETTER, draft_type="letter").kind == X.NONE
    assert X.classify(text, has_draft=True, draft_text="Note: The review is on Monday.",
                      draft_type="note").kind == X.REVISE
