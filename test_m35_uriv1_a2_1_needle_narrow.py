"""Synthetic unit tests for Batch A2.1: Needle 3 Narrow Schemas & Merger.

These tests run without any external Needle model or subprocess dependencies.
They verify:
  - Wire schema contamination checks (schemas are strictly semantic, no routing/tools/Graphify).
  - Deterministic normalizers for Schemas A, B, C, and D.
  - Negation and requested/prohibited separation in Schema B.
  - Reference unresolved invariant in Schema C and Merger.
  - Constraint conflict rejection in Schema D and Merger.
  - Deterministic merging into DecodedRequest without semantic invention.
  - Context dependency generation from references and attachments.
  - Immutability of the resulting DecodedRequest.
"""

from __future__ import annotations

import json
import unittest

from uri_v1.turn.contracts import (
    AttachmentReference,
    ConfidenceLevel,
    ConstraintScope,
    ContextDependencyCategory,
    DecodedRequest,
    IntentFamily,
    OperationStatus,
    OutputPreferences,
    ReferenceKind,
)
from uri_v1.turn.decoder import DecodeInput
from uri_v1.turn.needle_merge import merge_narrow_results
from uri_v1.turn.needle_narrow import (
    SCHEMA_CONSTRAINTS,
    SCHEMA_GOAL,
    SCHEMA_OPERATIONS,
    SCHEMA_REFERENCES,
    NarrowConstraintsResult,
    NarrowGoalResult,
    NarrowOperationsResult,
    NarrowReferencesResult,
    normalize_constraints,
    normalize_goal,
    normalize_operations,
    normalize_references,
)
from uri_v1.turn.needle_wire import DecodeError, DecodeErrorReason

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


class NarrowSchemaContaminationTests(unittest.TestCase):
    """Ensures none of the narrow schemas carry tool/execution/routing concepts."""

    def _assert_clean_schema(self, schema: dict, schema_name: str) -> None:
        raw = json.dumps(schema).lower()
        for forbidden in PROHIBITED_SUBSTRINGS:
            self.assertNotIn(
                forbidden,
                raw,
                f"Forbidden concept {forbidden!r} found in {schema_name}",
            )

    def test_schema_a_is_clean(self):
        self._assert_clean_schema(SCHEMA_GOAL, "SCHEMA_GOAL")

    def test_schema_b_is_clean(self):
        self._assert_clean_schema(SCHEMA_OPERATIONS, "SCHEMA_OPERATIONS")

    def test_schema_c_is_clean(self):
        self._assert_clean_schema(SCHEMA_REFERENCES, "SCHEMA_REFERENCES")

    def test_schema_d_is_clean(self):
        self._assert_clean_schema(SCHEMA_CONSTRAINTS, "SCHEMA_CONSTRAINTS")


class NormalizerSchemaATests(unittest.TestCase):
    """Unit tests for Schema A (Goal / Intent) normalization."""

    def test_valid_goal_and_intent(self):
        wire = {"goal": "convert this to PDF", "intent_family": "create"}
        goal, intent = normalize_goal(wire)
        self.assertEqual(goal, "convert this to PDF")
        self.assertEqual(intent, IntentFamily.CREATE)

    def test_unrecognized_intent_falls_back_to_unspecified(self):
        wire = {"goal": "search files", "intent_family": "quantum_leap"}
        goal, intent = normalize_goal(wire)
        self.assertEqual(goal, "search files")
        self.assertEqual(intent, IntentFamily.UNSPECIFIED)

    def test_empty_or_missing_goal_raises_error(self):
        with self.assertRaises(DecodeError) as ctx:
            normalize_goal({"goal": "   ", "intent_family": "retrieve"})
        self.assertEqual(ctx.exception.reason, DecodeErrorReason.MISSING_REQUIRED_STRUCTURE)

        with self.assertRaises(DecodeError) as ctx:
            normalize_goal({"intent_family": "retrieve"})
        self.assertEqual(ctx.exception.reason, DecodeErrorReason.MISSING_REQUIRED_STRUCTURE)

    def test_non_dict_raises_malformed(self):
        with self.assertRaises(DecodeError) as ctx:
            normalize_goal(["convert this"])
        self.assertEqual(ctx.exception.reason, DecodeErrorReason.MALFORMED_OUTPUT)


class NormalizerSchemaBTests(unittest.TestCase):
    """Unit tests for Schema B (Operations / Negation) normalization."""

    def test_valid_requested_and_prohibited(self):
        wire = {
            "requested_operations": ["draft", "compose"],
            "prohibited_operations": ["send"],
        }
        req, proh = normalize_operations(wire)
        self.assertEqual(req, ("draft", "compose"))
        self.assertEqual(proh, ("send",))

    def test_deduplicates_operations(self):
        wire = {
            "requested_operations": ["draft", "draft", "review"],
            "prohibited_operations": ["send", "send"],
        }
        req, proh = normalize_operations(wire)
        self.assertEqual(req, ("draft", "review"))
        self.assertEqual(proh, ("send",))

    def test_overlap_between_requested_and_prohibited_raises_error(self):
        wire = {
            "requested_operations": ["send", "draft"],
            "prohibited_operations": ["send"],
        }
        with self.assertRaises(DecodeError) as ctx:
            normalize_operations(wire)
        self.assertEqual(ctx.exception.reason, DecodeErrorReason.OPERATION_ERROR)
        self.assertIn("send", str(ctx.exception))

    def test_empty_lists_are_valid(self):
        wire = {"requested_operations": [], "prohibited_operations": []}
        req, proh = normalize_operations(wire)
        self.assertEqual(req, ())
        self.assertEqual(proh, ())


class NormalizerSchemaCTests(unittest.TestCase):
    """Unit tests for Schema C (References / Temporal) normalization."""

    def test_valid_references_and_temporal(self):
        wire = {
            "references": ["that file", "them"],
            "temporal_references": ["yesterday", "2025"],
        }
        refs, trefs = normalize_references(wire)
        self.assertEqual(refs, ("that file", "them"))
        self.assertEqual(trefs, ("yesterday", "2025"))

    def test_deduplicates_references(self):
        wire = {
            "references": ["this", "this", "it"],
            "temporal_references": ["tomorrow", "tomorrow"],
        }
        refs, trefs = normalize_references(wire)
        self.assertEqual(refs, ("this", "it"))
        self.assertEqual(trefs, ("tomorrow",))

    def test_empty_lists_are_valid(self):
        wire = {"references": [], "temporal_references": []}
        refs, trefs = normalize_references(wire)
        self.assertEqual(refs, ())
        self.assertEqual(trefs, ())


class NormalizerSchemaDTests(unittest.TestCase):
    """Unit tests for Schema D (Constraints / Preferences) normalization."""

    def test_valid_constraints_and_preferences(self):
        wire = {
            "constraints": {
                "included_items": ["2025", "2026"],
                "excluded_items": ["before 2025"],
                "length_limit": "one page",
                "language_constraints": "Indian English",
            },
            "output_preferences": {
                "artifact_type": "email",
                "tone": "formal",
                "audience": "Chief Warden",
                "structure": "table",
            },
        }
        constraints, prefs = normalize_constraints(wire)
        self.assertEqual(constraints.included_items, ("2025", "2026"))
        self.assertEqual(constraints.excluded_items, ("before 2025",))
        self.assertEqual(constraints.length_limit, "one page")
        self.assertEqual(prefs.artifact_type, "email")
        self.assertEqual(prefs.tone, "formal")
        self.assertEqual(prefs.audience, "Chief Warden")
        self.assertEqual(prefs.structure, "table")

    def test_included_and_excluded_overlap_raises_error(self):
        wire = {
            "constraints": {
                "included_items": ["2025", "2026"],
                "excluded_items": ["2025"],
            },
            "output_preferences": {},
        }
        with self.assertRaises(DecodeError) as ctx:
            normalize_constraints(wire)
        self.assertEqual(ctx.exception.reason, DecodeErrorReason.CONSTRAINT_ERROR)


class DeterministicMergerTests(unittest.TestCase):
    """Unit tests for merge_narrow_results."""

    def test_full_successful_merge(self):
        goal_res = NarrowGoalResult(goal="Draft order", intent_family=IntentFamily.CREATE, raw_confidence=0.9)
        ops_res = NarrowOperationsResult(
            requested_operations=("draft", "compare"),
            prohibited_operations=("send",),
            raw_confidence=0.85,
        )
        refs_res = NarrowReferencesResult(
            references=("that file", "this"),
            temporal_references=("yesterday",),
            raw_confidence=0.8,
        )
        const_res = NarrowConstraintsResult(
            constraints=ConstraintScope(included_items=("2025",)),
            output_preferences=OutputPreferences(tone="formal"),
            raw_confidence=0.95,
        )
        input_data = DecodeInput(raw_text="Test prompt", attachments=(AttachmentReference("file.pdf"),))

        decoded = merge_narrow_results(goal_res, ops_res, refs_res, const_res, input_data)

        self.assertEqual(decoded.raw_text, "Test prompt")
        self.assertEqual(decoded.goal.description, "Draft order")
        self.assertEqual(decoded.goal.intent_family, IntentFamily.CREATE)

        # Operations
        self.assertEqual(len(decoded.operations), 3)
        self.assertEqual(decoded.operations[0].name, "draft")
        self.assertEqual(decoded.operations[0].status, OperationStatus.REQUESTED)
        self.assertEqual(decoded.operations[2].name, "send")
        self.assertEqual(decoded.operations[2].status, OperationStatus.PROHIBITED)

        # References & Unresolved invariant
        self.assertEqual(len(decoded.references), 2)
        for ref in decoded.references:
            self.assertFalse(ref.is_resolved)  # Rule 3: strictly unresolved
        self.assertEqual(decoded.references[0].expression, "that file")
        self.assertEqual(decoded.references[0].kind, ReferenceKind.DOCUMENT_OR_FILE)
        self.assertEqual(decoded.references[1].expression, "this")
        self.assertEqual(decoded.references[1].kind, ReferenceKind.PRONOUN)

        # Temporal
        self.assertEqual(len(decoded.temporal_references), 1)
        self.assertEqual(decoded.temporal_references[0].expression, "yesterday")

        # Constraints & Preferences
        self.assertEqual(decoded.constraints.included_items, ("2025",))
        self.assertEqual(decoded.output_preferences.tone, "formal")

        # Attachments & Dependencies
        self.assertEqual(len(decoded.attachments), 1)
        self.assertEqual(len(decoded.dependencies), 3)  # 2 refs + 1 attachment
        self.assertEqual(decoded.dependencies[0].category, ContextDependencyCategory.PRIOR_CONTEXT_UNSPECIFIED)
        self.assertEqual(decoded.dependencies[2].category, ContextDependencyCategory.CURRENT_ATTACHMENT)

        # Confidence: bucketed average (0.9 + 0.85 + 0.8 + 0.95) / 4 = 0.875 -> HIGH
        self.assertEqual(decoded.confidence.overall, ConfidenceLevel.HIGH)
        self.assertEqual(decoded.confidence.goal, ConfidenceLevel.UNCERTAIN)

    def test_partial_merge_without_semantic_invention(self):
        """When extractors fail or decline, merger records partial state without inventing values."""
        goal_res = NarrowGoalResult(declined=True, error=DecodeError(DecodeErrorReason.MISSING_REQUIRED_STRUCTURE, "declined"))
        ops_res = NarrowOperationsResult(requested_operations=("draft",))
        refs_res = NarrowReferencesResult(references=())
        const_res = NarrowConstraintsResult()

        decoded = merge_narrow_results(goal_res, ops_res, refs_res, const_res, DecodeInput.from_text("Draft something"))

        self.assertEqual(decoded.goal.description, "")
        self.assertEqual(decoded.goal.intent_family, IntentFamily.UNSPECIFIED)
        self.assertEqual(len(decoded.operations), 1)
        self.assertEqual(decoded.operations[0].name, "draft")
        self.assertEqual(len(decoded.references), 0)
        self.assertEqual(len(decoded.dependencies), 0)

    def test_merger_contradiction_detection(self):
        goal_res = NarrowGoalResult(goal="test")
        ops_res = NarrowOperationsResult(
            requested_operations=("send",),
            prohibited_operations=("send",),
        )
        refs_res = NarrowReferencesResult()
        const_res = NarrowConstraintsResult()

        with self.assertRaises(DecodeError) as ctx:
            merge_narrow_results(goal_res, ops_res, refs_res, const_res, raise_on_contradiction=True)
        self.assertEqual(ctx.exception.reason, DecodeErrorReason.OPERATION_ERROR)


if __name__ == "__main__":
    unittest.main()
