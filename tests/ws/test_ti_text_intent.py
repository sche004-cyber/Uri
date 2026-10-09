"""Text intelligence routing (TI-AC1): deterministic, biased to fall through to the existing path."""
import time

import pytest

from uri_operational_intelligence import text_intent as X

NO_DRAFT = [
    # (text, expected kind)
    ("URI draft a letter to the warden regarding five students, sorry seven students, who left the hostel on Monday "
     "without permission. Make it formal.", X.DRAFT_NEW),
    ("URI write a letter to the warden about the students leaving hostel yesterday, no wait, on the 6th, and make it "
     "formal.", X.DRAFT_NEW),
    ("Write a notice for students that the mess will be closed on Sunday", X.DRAFT_NEW),
    ("Draft an email to Priya about the budget meeting", X.DRAFT_NEW),
    ("Please prepare an office note on the delay in fee collection", X.DRAFT_NEW),
    ("Can you write a circular about the new library timings", X.DRAFT_NEW),
    ("I need a leave application for three days", X.DRAFT_NEW),
    ("Draft a notice to remind the students that hostel gates close at 9 pm", X.DRAFT_NEW),
    ("Write a letter to the manager of the store about a refund", X.DRAFT_NEW),
    ("principal ko ek leave application likho, kal se teen din ki chutti", X.DRAFT_NEW),
    ("warden ke liye ek formal letter bana do", X.DRAFT_NEW),
    ("Correct this: me and him goes to market yesterday", X.CORRECT),
    ("Fix the grammar in this: their going too the meeting", X.CORRECT),
    ("Proofread: The comittee have decided to postpone the meeting", X.CORRECT),
    ("Rewrite politely: send me the report now", X.REWRITE),
    ("Make this more formal: we cant come tomorrow", X.REWRITE),
    ("Expand these notes into a circular: mess closed sunday, repairs, reopen monday", X.EXPAND),
    # Not text tasks: unchanged fast paths
    ("hello", X.NONE), ("Thanks!", X.NONE), ("good morning uri", X.NONE),
    ("What is the capital of France?", X.NONE),
    ("How do I write a letter to the warden?", X.NONE),
    ("Compare the two hostel fee options", X.NONE),
    # Core-only: an action in the same request goes to Core
    ("Draft a letter to the principal and send it to him", X.NONE),
    ("Write the meeting notes in the shared folder", X.NONE),
    ("Write a letter to the warden and save it as a PDF", X.NONE),
    ("Remember that my sister's birthday is on 5 May", X.NONE),
    ("Send an email to the warden", X.NONE),
    ("Can you summarize my emails", X.NONE),
    ("Fix the bug in my Python script", X.NONE),
    ("Undo the last change.", X.NONE),          # no draft: nothing to undo, not captured
]

WITH_DRAFT = [
    ("Actually, don't say without permission. Say they left without recording their departure in the hostel register.",
     X.REVISE),
    ("Make it more diplomatic and shorten the second paragraph.", X.REVISE),
    ("Make the first paragraph shorter.", X.REVISE),
    ("No, I meant Tuesday.", X.REVISE),
    ("Actually, replace that with 'during the evening'.", X.REVISE),
    ("Sorry, not five students, seven.", X.REVISE),
    ("Remove the previous sentence.", X.REVISE),
    ("Make the second paragraph more formal.", X.REVISE),
    ("Keep everything else the same.", X.REVISE),
    ("Don't mention the student's name.", X.REVISE),
    ("Improve grammar", X.REVISE),
    ("isko thoda formal karo", X.REVISE),
    ("doosra paragraph chhota karo", X.REVISE),
    ("Undo the last change.", X.UNDO), ("undo", X.UNDO), ("Undo that correction.", X.UNDO),
    ("Go back to the previous version", X.UNDO), ("pehle wala wapas lao", X.UNDO),
    ("redo", X.REDO), ("Show me the original", X.ORIGINAL), ("Show the original transcript", X.ORIGINAL),
    ("Discard the draft", X.DISCARD), ("Show the draft", X.SHOW),
    ("Draft a new letter to the principal about the library", X.DRAFT_NEW),
    # Still not draft edits while a draft is open
    ("hello", X.NONE), ("thanks", X.NONE),
    ("What is the capital of France?", X.NONE),
    ("Delete the file report.docx", X.NONE),
    ("Remember that the warden's name is Mr. Rao", X.NONE),
    ("Send it to the warden", X.NONE),
    ("Save it to my desktop", X.NONE),
    ("Delete my calendar reminders", X.NONE),
]


@pytest.mark.parametrize("text,kind", NO_DRAFT)
def test_without_draft(text, kind):
    assert X.classify(text, has_draft=False).kind == kind


@pytest.mark.parametrize("text,kind", WITH_DRAFT)
def test_with_active_draft(text, kind):
    assert X.classify(text, has_draft=True).kind == kind


def test_targets_local_vs_global():
    t = X.targets_for("Make the first paragraph shorter.")
    assert t["body"] == [0] and not t["global"]
    t = X.targets_for("Make it more diplomatic and shorten the second paragraph.")
    assert t["body"] == [1] and t["global"]
    t = X.targets_for("Actually, don't say without permission. Say they left without recording their departure.")
    assert t["phrases"] == ["without permission"] and not t["global"]
    assert X.targets_for("Change the subject line to Hostel register entries")["roles"] == ["subject"]
    assert X.targets_for("paragraph 3 should mention the date")["body"] == [2]
    assert X.targets_for("make the last paragraph warmer")["body"] == [-1]


def test_payload_split():
    i = X.classify("Correct this: me and him goes to market", has_draft=False)
    assert i.payload == "me and him goes to market" and i.instruction == "Correct this"
    i = X.classify("Rewrite politely\nsend me the report now", has_draft=False)
    assert i.payload == "send me the report now"
    assert X.classify("Correct this", has_draft=False).payload is None


def test_fast_enough_for_every_turn():
    t0 = time.perf_counter()
    for _ in range(200):
        for text, _k in NO_DRAFT:
            X.classify(text, has_draft=False)
    per_call_ms = (time.perf_counter() - t0) * 1000 / (200 * len(NO_DRAFT))
    assert per_call_ms < 2.0, per_call_ms


# ---- L-2: dictation versus commands (owner examples, 2026-10-09) ----------------------------------------------------
@pytest.mark.parametrize("text,has_draft,kind,reason", [
    ("Prepare the office order for tomorrow.", False, X.DRAFT_NEW, "create_document"),
    ("Send this letter to the director.", False, X.NONE, "core_only_request"),
    ("Send this letter to the director.", True, X.NONE, "core_only_request"),
    ("Delete the previous paragraph.", True, X.REVISE, "draft_revision"),
    ("Delete the previous paragraph.", False, X.NONE, "not_a_text_task"),
    ("Write: send this letter to the director.", False, X.CORRECT, "dictated_content"),
    ("Write: Delete all files.", True, X.CORRECT, "dictated_content"),
    ("URI, write: Dear Sir, please send the fee receipt.", False, X.CORRECT, "dictated_content"),
    ("Write a notice. Send the form by Friday.", False, X.DRAFT_NEW, "ambiguous_action_sentences"),
    ("Write a notice. Email the parents.", False, X.NONE, "core_only_request"),     # names someone: an action (r2 A1)
    ("Write a circular. Forward the list to the office.", False, X.DRAFT_NEW, "ambiguous_action_sentences"),
    # the document itself, a sequence, a destination or a coordinated action stays an action for Core
    ("Draft a letter to the warden. Send it to him.", False, X.NONE, "core_only_request"),
    ("Draft a letter to the warden and send it to him.", False, X.NONE, "core_only_request"),
    ("Draft a notice about the water cut. Then email it to all staff.", False, X.NONE, "core_only_request"),
    ("Write a notice. Save it to my desktop.", False, X.NONE, "core_only_request"),
    ("Note down: my car is in slot 4", False, X.NONE, "core_only_request"),          # memory: Core
    ("Write a notice: Send the form by Friday.", False, X.DRAFT_NEW, "create_document"),
])
def test_l2_owner_examples_route(text, has_draft, kind, reason):
    r = X.classify(text, has_draft=has_draft)
    assert (r.kind, r.reasons[0]) == (kind, reason)


def test_l2_dictated_payload_and_ambiguous_sentences_are_exact():
    assert X.classify("Write: send this letter to the director.", has_draft=False).payload == \
        "send this letter to the director."
    assert X.classify("Write a notice. Send the form by Friday.", has_draft=False).ambiguous == ["Send the form by Friday"]
    assert X.action_sentences("Dear all. Send the form by Friday. Thanks.") == ["Send the form by Friday"]


# LV-1 (live finding, kept as a limitation): "ghar mein function hai" is a family event, but any use of "function"
# routes to the ordinary path (safe direction). Three narrower exemptions were rejected by Codex TIWS r6-r8 because
# each let some code-action request reach the desk, so the accepted round-5 routing stays.
@pytest.mark.parametrize("text", [
    "Principal ko leave application likho: kal se teen din ki chutti chahiye, ghar mein function hai.",
    "bug report likho aur bug fix karo", "is function ka note likho aur function ko badlo",
    "Ek function hai, usko run karo aur application likho", "Functions ko run karo aur application likho",
    "Scripts ka summary likho aur bugs fix karo"])
def test_lv1_any_code_word_including_plurals_keeps_the_code_route(text):
    assert X.classify(text, has_draft=False).reasons == ["code_work"]
