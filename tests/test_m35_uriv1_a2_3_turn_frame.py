"""Unit tests for TurnFrame and deterministic turn preprocessor (Batch A2.3).

Verifies that TurnFrame extracts purely observational surface features:
- Clauses, candidate actions, candidate references, negation cues.
- Formats, numbers, temporal spans, entities, attachments.
- Frozen immutability.
- ZERO semantic inference (no goal choice, no requested/prohibited decision).
"""

from __future__ import annotations

import pytest

from uri_v1.turn.contracts import AttachmentReference
from uri_v1.turn.turn_frame import CandidateAction, CandidateReference, TurnFrame
from uri_v1.turn.turn_frame_builder import build_turn_frame


BASELINE_PROMPTS = [
    ("P1", "Convert report.pdf to text format"),
    ("P2", "Draft an email to Prof. Rao about the meeting tomorrow, but do not send it"),
    ("P3", "Summarize the attached PDF and highlight key findings"),
    ("P4", "Compare the quarterly figures in 2025 vs 2026"),
    ("P5", "Find all files modified yesterday in the project folder"),
    ("P6", "Schedule a sync with the team for next Tuesday at 10 AM"),
    ("P7", "Rewrite this paragraph to make it more professional"),
    ("P8", "Don't submit the form yet; first check for errors"),
    ("P9", "Explain how the authentication middleware works"),
    ("P10", "Translate the welcome message to Spanish and French"),
    ("P11", "Archive all logs older than 30 days"),
    ("P12", "Send the weekly status update to the engineering lead"),
    ("P13", "Generate a bar chart showing monthly revenue"),
    ("P14", "Please don't delete the backup files, just move them"),
    ("P15", "Review this code for potential security vulnerabilities"),
    ("P16", "Create a markdown table comparing product features"),
    ("P17", "Shorten the introduction section to under 200 words"),
    ("P18", "Do not reply to this email under any circumstances"),
]

CONTEXT_PROMPTS = [
    ("C1", "Send the invoice we discussed earlier to finance"),
    ("C2", "Update the hostel allocation order with the new roll numbers"),
    ("C3", "Revise it to sound more formal and add Dean's approval note"),
    ("C4", "Can you check if there are any conflicts in the schedule we drafted?"),
    ("C5", "Don't send the revised letter yet; wait for Prof. Rao's confirmation"),
    ("C6", "Export that table to CSV and share it with the team"),
]


def test_turn_frame_immutability():
    frame = build_turn_frame("Draft an email but do not send it")
    assert isinstance(frame, TurnFrame)
    with pytest.raises(Exception):
        frame.raw_text = "changed"  # type: ignore[misc]
    with pytest.raises(Exception):
        frame.candidate_actions = ()  # type: ignore[misc]


def test_turn_frame_negation_detection():
    # P2: "do not send it"
    frame = build_turn_frame("Draft an email to Prof. Rao about the meeting tomorrow, but do not send it")
    assert frame.has_negation
    assert any("not" in s for s in frame.negation_spans)

    # P8: "Don't submit the form yet; first check for errors"
    frame8 = build_turn_frame("Don't submit the form yet; first check for errors")
    assert frame8.has_negation
    assert any("don't" in s.lower() or "dont" in s.lower() for s in frame8.negation_spans)

    # P1: no negation
    frame1 = build_turn_frame("Convert report.pdf to text format")
    assert not frame1.has_negation
    assert frame1.negation_spans == ()


def test_turn_frame_candidate_actions():
    # P2: draft and send
    frame = build_turn_frame("Draft an email to Prof. Rao about the meeting tomorrow, but do not send it")
    verbs = frame.candidate_action_spans
    assert "draft" in verbs
    assert "send" in verbs
    # Check IDs are assigned
    for act in frame.candidate_actions:
        assert act.id.startswith("a")
        assert act.verb in ("draft", "send")

    # P14: delete and move
    frame14 = build_turn_frame("Please don't delete the backup files, just move them")
    verbs14 = frame14.candidate_action_spans
    assert "delete" in verbs14
    assert "move" in verbs14


def test_turn_frame_candidate_references():
    # P7: "this paragraph", "it"
    frame7 = build_turn_frame("Rewrite this paragraph to make it more professional")
    assert frame7.has_candidate_references
    ref_spans = frame7.candidate_reference_spans
    assert any("this" in r or "it" in r for r in ref_spans)
    for ref in frame7.candidate_references:
        assert ref.id.startswith("r")

    # C3: "it"
    frame_c3 = build_turn_frame("Revise it to sound more formal and add Dean's approval note")
    assert any(r.expression == "it" for r in frame_c3.candidate_references)


def test_turn_frame_output_cues():
    # P1: explicit format "text"
    frame1 = build_turn_frame("Convert report.pdf to text format")
    assert frame1.has_output_cues
    assert "text" in frame1.explicit_formats or "pdf" in frame1.explicit_formats

    # P17: number "200"
    frame17 = build_turn_frame("Shorten the introduction section to under 200 words")
    assert frame17.has_output_cues
    assert "200" in frame17.explicit_numbers


def test_turn_frame_all_baseline_prompts():
    """Verify TurnFrame builds cleanly and without error on all 18 baseline prompts."""
    for pid, prompt in BASELINE_PROMPTS:
        frame = build_turn_frame(prompt)
        assert frame.raw_text == prompt
        assert len(frame.clauses) >= 1
        # Structural properties should never raise
        _ = frame.has_candidate_actions
        _ = frame.has_candidate_references
        _ = frame.has_negation
        _ = frame.has_output_cues


def test_turn_frame_all_context_prompts():
    """Verify TurnFrame builds cleanly on all 6 context prompts."""
    for cid, prompt in CONTEXT_PROMPTS:
        frame = build_turn_frame(prompt)
        assert frame.raw_text == prompt
        assert len(frame.clauses) >= 1


def test_turn_frame_attachments_preserved():
    att = AttachmentReference(identifier="att1", name="document.docx", mime_type="application/docx")
    frame = build_turn_frame("Check this file", attachments=(att,))
    assert frame.attachments == (att,)
