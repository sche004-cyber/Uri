"""Unit tests for M35 URIv1 Batch A2.5 Stage 3: LFM Decoder and Wire.

Tests:
1. LFM Wire Schema structure and required keys.
2. Mode A and Mode B prompt formatting.
3. Normalization from raw JSON wire to typed DecodedRequest.
4. Absolute preservation of model polarity (zero post-hoc semantic repair).
5. Operation binding extraction into SemanticOperation.target.
6. Ambiguity and context dependency mapping.
"""

from __future__ import annotations

import unittest

from uri_v1.turn.active_context import ActiveContext, ArtifactDescriptor, EntityDescriptor
from uri_v1.turn.contracts import (
    AmbiguityKind,
    ConfidenceLevel,
    ContextDependencyCategory,
    DecodedRequest,
    IntentFamily,
    OperationStatus,
)
from uri_v1.turn.lfm_wire import (
    LFM_SYSTEM_PROMPT,
    LFM_WIRE_SCHEMA,
    build_lfm_mode_a_prompt,
    build_lfm_mode_b_prompt,
    normalize_lfm_wire,
)
from uri_v1.turn.turn_frame import TurnFrame


class LFMDecoderWireUnitTests(unittest.TestCase):
    """Offline unit tests for LFM wire and normalization."""

    def test_lfm_wire_schema_conformance(self):
        """Schema must have object type, all properties in required, and additionalProperties=False."""
        self.assertEqual(LFM_WIRE_SCHEMA["type"], "object")
        self.assertFalse(LFM_WIRE_SCHEMA["additionalProperties"])
        props = set(LFM_WIRE_SCHEMA["properties"].keys())
        reqs = set(LFM_WIRE_SCHEMA["required"])
        self.assertEqual(props, reqs, "All properties must be required for OpenAI/LM Studio strict json_schema")

    def test_mode_a_and_mode_b_prompt_generation(self):
        """Mode A prompt excludes RAR anchors; Mode B prompt includes them."""
        from uri_v1.turn.turn_frame_builder import build_turn_frame
        tf = build_turn_frame("Don't send it. Just draft the email.")
        ac = ActiveContext(
            active_artifacts=(ArtifactDescriptor(id="x1", name="Order.docx"),)
        )
        prompt_a = build_lfm_mode_a_prompt(tf.raw_text, turn_frame=tf, active_context=ac)
        self.assertIn("[User Message]", prompt_a)
        self.assertIn("[TurnFrame]", prompt_a)
        self.assertIn("[Active Context]", prompt_a)
        self.assertNotIn("[Deterministic RAR Anchors]", prompt_a)

        rar_facts = {
            "resolved_anchors": {"it": "x1 (Order.docx)"},
            "unresolved": [],
            "ambiguous_candidates": {},
        }
        prompt_b = build_lfm_mode_b_prompt(tf.raw_text, turn_frame=tf, active_context=ac, rar_facts=rar_facts)
        self.assertIn("[Deterministic RAR Anchors]", prompt_b)
        self.assertIn("'it' -> x1 (Order.docx)", prompt_b)

    def test_normalization_preserves_polarity_and_zero_repair(self):
        """Normalizer preserves requested vs prohibited operations without modifying polarity."""
        wire = {
            "goal": "Draft email",
            "intent_family": "create",
            "requested_operations": ["draft"],
            "prohibited_operations": ["send"],
            "operation_bindings": [
                {"operation": "draft", "target_id": "x1"},
                {"operation": "send", "target_id": "x1"},
            ],
            "references": [{"expression": "it", "target_id": "x1"}],
            "temporal_references": [],
            "constraints": {
                "included_items": [],
                "excluded_items": [],
                "length_limit": "",
                "language_constraints": "",
            },
            "output_preferences": {
                "artifact_type": "email",
                "format": "plain text",
                "tone": "formal",
                "structure": "standard",
            },
            "ambiguities": [],
            "context_dependencies": [],
        }

        decoded = normalize_lfm_wire(wire, "Don't send it. Just draft the email.")
        self.assertEqual(decoded.goal.description, "Draft email")
        self.assertEqual(decoded.goal.intent_family, IntentFamily.CREATE)

        # Check requested vs prohibited
        ops = decoded.operations
        self.assertEqual(len(ops), 2)
        req_op = next(op for op in ops if op.status == OperationStatus.REQUESTED)
        proh_op = next(op for op in ops if op.status == OperationStatus.PROHIBITED)

        self.assertEqual(req_op.name, "draft")
        self.assertEqual(req_op.target, "x1")
        self.assertEqual(proh_op.name, "send")
        self.assertEqual(proh_op.target, "x1")

        # References
        self.assertEqual(len(decoded.references), 1)
        self.assertTrue(decoded.references[0].is_resolved)
        self.assertEqual(decoded.references[0].referent_hint, "x1")

    def test_normalization_handles_ambiguities_and_dependencies(self):
        """Normalizer properly creates SemanticAmbiguity and ContextDependency objects."""
        wire = {
            "goal": "Use file",
            "intent_family": "execute",
            "requested_operations": ["use"],
            "prohibited_operations": [],
            "operation_bindings": [],
            "references": [{"expression": "that file", "target_id": ""}],
            "temporal_references": [],
            "constraints": {
                "included_items": [],
                "excluded_items": [],
                "length_limit": "",
                "language_constraints": "",
            },
            "output_preferences": {
                "artifact_type": "",
                "format": "",
                "tone": "",
                "structure": "",
            },
            "ambiguities": [
                {
                    "kind": "multiple_interpretations",
                    "description": "Two matching files",
                    "candidates": ["x1", "x2"],
                }
            ],
            "context_dependencies": [
                {
                    "category": "context_required",
                    "description": "User clarification needed",
                }
            ],
        }

        decoded = normalize_lfm_wire(wire, "Use that file.")
        self.assertEqual(len(decoded.ambiguities), 1)
        self.assertEqual(decoded.ambiguities[0].kind, AmbiguityKind.MULTIPLE_INTERPRETATIONS)
        self.assertEqual(decoded.ambiguities[0].candidates, ("x1", "x2"))
        self.assertEqual(len(decoded.dependencies), 1)
        self.assertEqual(decoded.dependencies[0].category, ContextDependencyCategory.CONTEXT_REQUIRED)


if __name__ == "__main__":
    unittest.main()
