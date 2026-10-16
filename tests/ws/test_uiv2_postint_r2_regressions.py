"""UI-V2-POSTINT R2: ordinary Workspace turns cannot revise an unrelated draft."""

import pytest

from tests.ws.test_ti_desk_bridge import CREATE
from tests.ws.test_uiv2_f1_draft_integrity import _memory_draft
from tests.ws.test_ws_worker_bridge import SID
from uri_operational_intelligence import text_intent as X
from uri_operational_intelligence.draft_desk import DraftDesk


LETTER = "\n\n".join(block["text"] for block in CREATE["blocks"])


@pytest.mark.parametrize("text", [
    "Set the time to 9",
    "Set the date to 9",
    "Update the weather report",
    "Change your name to Ravi",
    "Replace 'weather report' with 'forecast'",
])
def test_unrelated_revision_words_do_not_reference_the_open_draft(text):
    intent = X.classify(text, has_draft=True, draft_text=LETTER)
    assert intent.kind == X.NONE, (text, intent.kind, intent.reasons)


def test_phrase_replacement_in_the_open_draft_remains_a_revision():
    assert X.classify("Replace 'without permission' with 'without recording departure'",
                      has_draft=True, draft_text=LETTER).kind == X.REVISE


def test_shared_number_does_not_make_an_unrelated_time_request_a_draft_edit():
    draft_text = LETTER + "\nThe office closes at 9."
    assert X.classify("Set the time to 9", has_draft=True, draft_text=draft_text).kind == X.NONE


@pytest.mark.parametrize("text", ["Nice weather today", "Blue shoes", "Thanks for your help"])
def test_unrelated_short_reply_drops_the_pending_date_question(text):
    desk = DraftDesk(None)
    draft = _memory_draft(desk, "The letter uses Monday.")
    draft.pending_question = "What date should the letter use?"
    intent = desk.classify(text, SID)
    assert intent.kind == X.NONE, (text, intent.kind, intent.reasons)
    assert draft.pending_question is None
    assert draft.current.n == 1


@pytest.mark.parametrize("text", ["the 9th", "Tuesday", "9 October 2026", "tomorrow"])
def test_date_reply_answers_the_pending_date_question(text):
    desk = DraftDesk(None)
    draft = _memory_draft(desk, "The letter uses Monday.")
    draft.pending_question = "What date should the letter use?"
    intent = desk.classify(text, SID)
    assert intent.kind == X.REVISE and intent.reasons == ["answer_to_clarification"]
    assert draft.pending_question == "What date should the letter use?"
