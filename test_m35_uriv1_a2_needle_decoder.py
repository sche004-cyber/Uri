"""M35 Batch A2: Needle wire schema / normalizer unit tests (synthetic, no live Needle).

Covers:
1. wire-schema shape (no tool/capability/routing contamination).
2. deterministic normalization of valid wire payloads.
3. invalid-output handling (missing goal, contradictions, malformed types).
4. attachment propagation from DecodeInput.
5. enum conversion (including unknown-value fallback).
6. confidence mapping (single overall value -> bucket; never fabricated per-field).
7. no history/context dependency in DecodeInput or the wire schema.
"""

import unittest

from uri_v1.turn.contracts import (
    AttachmentReference,
    ConfidenceLevel,
    IntentFamily,
    OperationStatus,
    ReferenceKind,
)
from uri_v1.turn.decoder import DecodeInput
from uri_v1.turn.needle_wire import (
    SYSTEM_PROMPT,
    WIRE_SCHEMA,
    DecodeError,
    DecodeErrorReason,
    normalize_wire,
)


FORBIDDEN_WIRE_TERMS = (
    "tool_name",
    "capability_id",
    "graphify",
    "workflow_id",
    "provider",
    "edge_decision",
    "execution_plan",
    "final_answer",
)


class WireSchemaContaminationTests(unittest.TestCase):
    def test_schema_has_no_routing_or_execution_fields(self):
        import json

        schema_text = json.dumps(WIRE_SCHEMA).lower()
        for term in FORBIDDEN_WIRE_TERMS:
            with self.subTest(term=term):
                self.assertNotIn(term, schema_text)

    def test_schema_required_fields_are_minimal(self):
        self.assertEqual(WIRE_SCHEMA["parameters"]["required"], ["goal"])

    def test_system_prompt_forbids_history_and_execution(self):
        self.assertNotIn("history", SYSTEM_PROMPT.lower())
        self.assertNotIn("graphify", SYSTEM_PROMPT.lower())
        self.assertNotIn("execute", SYSTEM_PROMPT.lower())


class DecodeInputBoundaryTests(unittest.TestCase):
    def test_decode_input_only_carries_current_turn_material(self):
        fields = DecodeInput.__dataclass_fields__.keys()
        self.assertEqual(set(fields), {"raw_text", "attachments"})

    def test_decode_input_is_frozen(self):
        input_data = DecodeInput(raw_text="hello")
        with self.assertRaises(Exception):
            input_data.raw_text = "changed"  # type: ignore[misc]


class NormalizeWireValidCasesTests(unittest.TestCase):
    def test_minimal_valid_wire(self):
        wire = {"goal": "convert to PDF"}
        result = normalize_wire(wire, DecodeInput(raw_text="Convert this to PDF."), raw_confidence=0.9)
        self.assertEqual(result.goal.description, "convert to PDF")
        self.assertEqual(result.confidence.overall, ConfidenceLevel.HIGH)

    def test_full_wire_maps_every_field(self):
        wire = {
            "goal": "draft a revised order",
            "intent_family": "compare",
            "operations": [
                {"name": "retrieve", "status": "requested"},
                {"name": "send", "status": "prohibited"},
            ],
            "references": [{"expression": "this one", "kind": "document_or_file"}],
            "temporal_references": [{"expression": "tomorrow"}],
            "constraints": {
                "included_items": ["2025", "2026"],
                "excluded_items": ["2024"],
                "length_limit": "one page",
                "language_constraints": "Indian English",
            },
            "output_preferences": {"artifact_type": "email", "tone": "formal", "audience": "Chief Warden"},
            "entities": [{"name": "Chief Warden", "category": "role"}],
            "ambiguities": [{"description": "artifact type unclear"}],
        }
        result = normalize_wire(wire, DecodeInput(raw_text="..."), raw_confidence=0.6)
        self.assertEqual(result.goal.intent_family, IntentFamily.COMPARE)
        self.assertIn("retrieve", result.requested_operations)
        self.assertIn("send", result.prohibited_operations)
        self.assertEqual(result.references[0].kind, ReferenceKind.DOCUMENT_OR_FILE)
        self.assertFalse(result.references[0].is_resolved)
        self.assertEqual(result.temporal_references[0].expression, "tomorrow")
        self.assertEqual(result.constraints.included_items, ("2025", "2026"))
        self.assertEqual(result.constraints.excluded_items, ("2024",))
        self.assertEqual(result.output_preferences.artifact_type, "email")
        self.assertEqual(result.entities[0].name, "Chief Warden")
        self.assertTrue(result.has_ambiguities)
        self.assertEqual(result.confidence.overall, ConfidenceLevel.MEDIUM)

    def test_unresolved_reference_produces_context_dependency(self):
        wire = {"goal": "open file", "references": [{"expression": "that file"}]}
        result = normalize_wire(wire, DecodeInput(raw_text="Bring that file up."))
        self.assertTrue(result.has_unresolved_references)
        self.assertTrue(any("that file" in dep.description for dep in result.dependencies))


class NormalizeWireInvalidCasesTests(unittest.TestCase):
    def test_missing_goal_raises_missing_required_structure(self):
        with self.assertRaises(DecodeError) as ctx:
            normalize_wire({}, DecodeInput(raw_text="x"))
        self.assertEqual(ctx.exception.reason, DecodeErrorReason.MISSING_REQUIRED_STRUCTURE)

    def test_empty_goal_string_raises(self):
        with self.assertRaises(DecodeError) as ctx:
            normalize_wire({"goal": "   "}, DecodeInput(raw_text="x"))
        self.assertEqual(ctx.exception.reason, DecodeErrorReason.MISSING_REQUIRED_STRUCTURE)

    def test_non_dict_wire_raises_malformed_output(self):
        with self.assertRaises(DecodeError) as ctx:
            normalize_wire("not a dict", DecodeInput(raw_text="x"))  # type: ignore[arg-type]
        self.assertEqual(ctx.exception.reason, DecodeErrorReason.MALFORMED_OUTPUT)

    def test_operation_requested_and_prohibited_contradiction_raises(self):
        wire = {
            "goal": "x",
            "operations": [
                {"name": "send", "status": "requested"},
                {"name": "send", "status": "prohibited"},
            ],
        }
        with self.assertRaises(DecodeError) as ctx:
            normalize_wire(wire, DecodeInput(raw_text="x"))
        self.assertEqual(ctx.exception.reason, DecodeErrorReason.OPERATION_ERROR)

    def test_reference_claiming_resolved_is_context_invention(self):
        wire = {"goal": "x", "references": [{"expression": "that file", "is_resolved": True}]}
        with self.assertRaises(DecodeError) as ctx:
            normalize_wire(wire, DecodeInput(raw_text="x"))
        self.assertEqual(ctx.exception.reason, DecodeErrorReason.CONTEXT_INVENTION)

    def test_included_excluded_overlap_raises_constraint_error(self):
        wire = {"goal": "x", "constraints": {"included_items": ["2025"], "excluded_items": ["2025"]}}
        with self.assertRaises(DecodeError) as ctx:
            normalize_wire(wire, DecodeInput(raw_text="x"))
        self.assertEqual(ctx.exception.reason, DecodeErrorReason.CONSTRAINT_ERROR)

    def test_malformed_constraints_type_raises(self):
        with self.assertRaises(DecodeError):
            normalize_wire({"goal": "x", "constraints": "nope"}, DecodeInput(raw_text="x"))


class EnumNormalizationTests(unittest.TestCase):
    def test_unknown_intent_family_falls_back_to_unspecified(self):
        result = normalize_wire({"goal": "x", "intent_family": "not_a_real_value"}, DecodeInput(raw_text="x"))
        self.assertEqual(result.goal.intent_family, IntentFamily.UNSPECIFIED)

    def test_unknown_operation_status_falls_back_to_requested(self):
        wire = {"goal": "x", "operations": [{"name": "op", "status": "not_a_real_status"}]}
        result = normalize_wire(wire, DecodeInput(raw_text="x"))
        self.assertEqual(result.operations[0].status, OperationStatus.REQUESTED)

    def test_unknown_reference_kind_falls_back_to_other(self):
        wire = {"goal": "x", "references": [{"expression": "it", "kind": "not_a_real_kind"}]}
        result = normalize_wire(wire, DecodeInput(raw_text="x"))
        self.assertEqual(result.references[0].kind, ReferenceKind.OTHER)


class ConfidenceMappingTests(unittest.TestCase):
    def test_high_confidence_bucket(self):
        result = normalize_wire({"goal": "x"}, DecodeInput(raw_text="x"), raw_confidence=0.95)
        self.assertEqual(result.confidence.overall, ConfidenceLevel.HIGH)

    def test_low_confidence_bucket(self):
        result = normalize_wire({"goal": "x"}, DecodeInput(raw_text="x"), raw_confidence=0.3)
        self.assertEqual(result.confidence.overall, ConfidenceLevel.LOW)

    def test_missing_confidence_is_uncertain(self):
        result = normalize_wire({"goal": "x"}, DecodeInput(raw_text="x"), raw_confidence=None)
        self.assertEqual(result.confidence.overall, ConfidenceLevel.UNCERTAIN)

    def test_per_aspect_confidence_never_fabricated(self):
        """Needle exposes exactly one overall confidence value; per-aspect
        confidence must never be derived from it (see needle_wire.py docstring
        on _confidence_bucket and A2 spec section 13)."""
        result = normalize_wire({"goal": "x"}, DecodeInput(raw_text="x"), raw_confidence=0.99)
        self.assertEqual(result.confidence.goal, ConfidenceLevel.UNCERTAIN)
        self.assertEqual(result.confidence.operations, ConfidenceLevel.UNCERTAIN)
        self.assertEqual(result.confidence.references, ConfidenceLevel.UNCERTAIN)
        self.assertEqual(result.confidence.constraints, ConfidenceLevel.UNCERTAIN)


class AttachmentPropagationTests(unittest.TestCase):
    def test_attachments_propagate_from_decode_input_not_wire(self):
        attachment = AttachmentReference(identifier="a1", name="spreadsheet.xlsx")
        input_data = DecodeInput(raw_text="Compare the attached PDF with this spreadsheet.", attachments=(attachment,))
        result = normalize_wire({"goal": "compare"}, input_data)
        self.assertEqual(result.attachments, (attachment,))
        self.assertTrue(any("spreadsheet.xlsx" in dep.description for dep in result.dependencies))

    def test_no_attachments_means_no_attachment_dependency(self):
        result = normalize_wire({"goal": "x"}, DecodeInput(raw_text="x"))
        self.assertEqual(result.attachments, ())


class NoCapabilityOrToolContaminationTests(unittest.TestCase):
    def test_normalized_result_never_carries_capability_or_tool_ids(self):
        wire = {"goal": "x", "operations": [{"name": "send_email", "status": "requested"}]}
        result = normalize_wire(wire, DecodeInput(raw_text="x"))
        # SemanticOperation has no capability_id/tool_id field at all.
        from uri_v1.turn.contracts import SemanticOperation

        self.assertEqual(
            set(SemanticOperation.__dataclass_fields__.keys()),
            {"name", "status", "target"},
        )
        self.assertNotIn("capability_id", vars(result.operations[0]))


if __name__ == "__main__":
    unittest.main()
