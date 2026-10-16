"""UI-V2-POSTINT round 3 (Codex R3-01, R3-02): the user's own things and "I meant to ..." are not draft edits; a name
placeholder edit is. The deterministic boundary is the Workspace composer's draft target (mode "command" when set to
the conversation), covered in tests/ws/test_uiv2_f1_draft_integrity.py and uri_ui/test/living/uiv2_postint_test.dart.
"""
import pytest

from uri_operational_intelligence import text_intent as X

LETTER = ("To\nThe Warden\n\nSubject: Seven students left on Monday\n\nRespected Sir,\n\nSeven students left the hostel "
          "on Monday without permission.\n\nYours faithfully,\n[Your Name]")


@pytest.mark.parametrize("text", ["Change the date of my appointment to Friday", "Delete my last message",
                                  "I meant to ask about the weather", "Change your name to Ravi"])
def test_r3_01_the_users_own_things_are_not_the_draft(text):
    r = X.classify(text, has_draft=True, draft_text=LETTER)
    assert r.kind == X.NONE, (text, r.kind, r.reasons)


@pytest.mark.parametrize("text", ["Replace the name with Ravi", "Change the name to Ravi", "No, I meant Tuesday.",
                                  "Change the date to Tuesday", "Fix my letter", "Make that seven"])
def test_r3_02_explicit_edits_of_the_draft_still_edit(text):
    assert X.classify(text, has_draft=True, draft_text=LETTER).kind == X.REVISE, text
