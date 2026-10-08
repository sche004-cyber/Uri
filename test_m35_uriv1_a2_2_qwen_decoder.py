"""Synthetic unit tests for Batch A2.2: Qwen Step-1 Semantic Decoder.

These tests run without any external model or HTTP server connection.
They verify:
  - Wire schema contamination checks (schema is strictly semantic, zero tool/capability/routing).
  - Robust JSON parsing and markdown fence stripping.
  - Deterministic normalizer mapping wire dict to deep-frozen DecodedRequest.
  - Operation requested vs. prohibited separation and contradiction rejection.
  - Unresolved reference invariant (Rule 3: is_resolved is strictly False).
  - Deterministic context dependency generation (Rules 3 & 8).
  - Constraint inclusion/exclusion overlap rejection.
"""

from __future__ import annotations

import json
import unittest

from uri_v1.turn.contracts import (
    AttachmentReference,
    ContextDependencyCategory,
    IntentFamily,
    OperationStatus,
    ReferenceKind,
)
from uri_v1.turn.decoder import DecodeInput
from uri_v1.turn.needle_wire import DecodeError, DecodeErrorReason
from uri_v1.turn.qwen_wire import (
    QWEN_WIRE_SCHEMA,
    _strip_markdown_fence,
    normalize_qwen_wire,
    parse_wire_json,
)

PROHIBITED_SUBSTRINGS = (
    "tool",
    "capability",
    "graphify",
    "workflow",
    "provider",
    "decision",
    "plan",
    "route",
    "routing",
    "weather",
    "gmail",
    "calendar",
    "node_id",
    "edge_outcome",
    "escalate",
    "reflex",
)


class QwenWireContaminationTests(unittest.TestCase):
    """Ensures Qwen wire schema carries zero tool/execution/routing concepts."""

    def test_schema_is_clean(self):
        raw = json.dumps(QWEN_WIRE_SCHEMA).lower()
        for forbidden in PROHIBITED_SUBSTRINGS:
            self.assertNotIn(
                forbidden,
                raw,
                f"Forbidden concept {forbidden!r} found in QWEN_WIRE_SCHEMA",
            )


class QwenJsonParsingTests(unittest.TestCase):
    """Tests fence stripping and resilient JSON parsing."""

    def test_clean_json(self):
        raw = '{"goal": "convert file", "intent_family": "create"}'
        data = parse_wire_json(raw)
        self.assertEqual(data["goal"], "convert file")
        self.assertEqual(data["intent_family"], "create")

    def test_markdown_fenced_json(self):
        raw = "```json\n{\n  \"goal\": \"test\",\n  \"intent_family\": \"retrieve\"\n}\n```"
        data = parse_wire_json(raw)
        self.assertEqual(data["goal"], "test")

    def test_text_with_leading_noise(self):
        raw = "Here is the extracted information:\n{\"goal\": \"draft email\", \"intent_family\": \"communicate\"}\nHope this helps!"
        data = parse_wire_json(raw)
        self.assertEqual(data["goal"], "draft email")

    def test_unparseable_string_raises_malformed(self):
        with self.assertRaises(DecodeError) as ctx:
            parse_wire_json("This is not JSON at all.")
        self.assertEqual(ctx.exception.reason, DecodeErrorReason.MALFORMED_OUTPUT)


class QwenNormalizerTests(unittest.TestCase):
    """Tests normalize_qwen_wire mapping logic."""

    def test_valid_full_wire(self):
        wire = {
            "goal": "Convert this document to PDF",
            "intent_family": "create",
            "requested_operations": ["convert"],
            "prohibited_operations": ["print"],
            "references": ["this document"],
            "temporal_references": ["tomorrow"],
            "constraints": {
                "included_items": ["2025"],
                "excluded_items": ["2024"],
                "length_limit": "2 pages",
            },
            "output_preferences": {
                "artifact_type": "PDF",
                "tone": "formal",
            },
            "entities": [{"name": "Report", "category": "document"}],
            "ambiguities": ["missing page numbers"],
        }
        input_data = DecodeInput(
            raw_text="Convert this document to PDF",
            attachments=(AttachmentReference("doc.docx"),),
        )

        decoded = normalize_qwen_wire(wire, input_data)

        self.assertEqual(decoded.raw_text, "Convert this document to PDF")
        self.assertEqual(decoded.goal.description, "Convert this document to PDF")
        self.assertEqual(decoded.goal.intent_family, IntentFamily.CREATE)

        # Operations
        self.assertEqual(len(decoded.operations), 2)
        self.assertEqual(decoded.operations[0].name, "convert")
        self.assertEqual(decoded.operations[0].status, OperationStatus.REQUESTED)
        self.assertEqual(decoded.operations[1].name, "print")
        self.assertEqual(decoded.operations[1].status, OperationStatus.PROHIBITED)

        # References (Rule 3: strictly unresolved)
        self.assertEqual(len(decoded.references), 1)
        self.assertEqual(decoded.references[0].expression, "this document")
        self.assertEqual(decoded.references[0].kind, ReferenceKind.DOCUMENT_OR_FILE)
        self.assertFalse(decoded.references[0].is_resolved)

        # Temporal
        self.assertEqual(len(decoded.temporal_references), 1)
        self.assertEqual(decoded.temporal_references[0].expression, "tomorrow")

        # Constraints & Preferences
        self.assertEqual(decoded.constraints.included_items, ("2025",))
        self.assertEqual(decoded.constraints.excluded_items, ("2024",))
        self.assertEqual(decoded.constraints.length_limit, "2 pages")
        self.assertEqual(decoded.output_preferences.artifact_type, "PDF")
        self.assertEqual(decoded.output_preferences.tone, "formal")

        # Dependencies (Rules 3 & 8)
        self.assertEqual(len(decoded.dependencies), 2)  # 1 ref + 1 attachment
        self.assertEqual(decoded.dependencies[0].category, ContextDependencyCategory.PRIOR_CONTEXT_UNSPECIFIED)
        self.assertEqual(decoded.dependencies[1].category, ContextDependencyCategory.CURRENT_ATTACHMENT)

    def test_missing_goal_raises_missing_structure(self):
        with self.assertRaises(DecodeError) as ctx:
            normalize_qwen_wire({"intent_family": "retrieve"}, None)
        self.assertEqual(ctx.exception.reason, DecodeErrorReason.MISSING_REQUIRED_STRUCTURE)

    def test_operation_contradiction_raises_operation_error(self):
        wire = {
            "goal": "Send email",
            "requested_operations": ["send"],
            "prohibited_operations": ["send"],
        }
        with self.assertRaises(DecodeError) as ctx:
            normalize_qwen_wire(wire, None)
        self.assertEqual(ctx.exception.reason, DecodeErrorReason.OPERATION_ERROR)
        self.assertIn("send", str(ctx.exception))

    def test_constraint_overlap_raises_constraint_error(self):
        wire = {
            "goal": "Filter items",
            "constraints": {
                "included_items": ["itemA", "itemB"],
                "excluded_items": ["itemA"],
            },
        }
        with self.assertRaises(DecodeError) as ctx:
            normalize_qwen_wire(wire, None)
        self.assertEqual(ctx.exception.reason, DecodeErrorReason.CONSTRAINT_ERROR)


if __name__ == "__main__":
    unittest.main()
