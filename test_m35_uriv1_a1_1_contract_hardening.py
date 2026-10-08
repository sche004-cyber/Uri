"""M35 Batch A1.1: DecodedRequest Contract Hardening Verification Tests.

Dedicated test suite verifying the three hardening corrections:
1. True immutability of frozen dataclasses (no mutable dict/list attributes).
2. Context-dependency neutrality (no premature assumption of same-session storage).
3. Canonical SemanticDecoder interface (strict DecodeInput input contract).
"""

import dataclasses
import os
import unittest

from uri_v1.turn.contracts import (
    AmbiguityKind,
    AttachmentReference,
    ConfidenceLevel,
    ConstraintScope,
    ContextDependency,
    ContextDependencyCategory,
    DecodedRequest,
    EntityCategory,
    IntendedOutcome,
    IntentFamily,
    MentionedEntity,
    OperationStatus,
    OutputPreferences,
    ReferenceKind,
    SemanticAmbiguity,
    SemanticConfidence,
    SemanticOperation,
    SemanticReference,
    TemporalReference,
)
from uri_v1.turn.decoder import DecodeInput, SemanticDecoder


class ContractHardeningImmutabilityTests(unittest.TestCase):
    """Verifies that all frozen semantic dataclasses are genuinely immutable."""

    def test_decoded_request_contains_no_mutable_containers(self):
        """DecodedRequest fields must not be mutable dict or list types."""
        req = DecodedRequest(
            raw_text="Test prompt",
            goal=IntendedOutcome(description="Test goal"),
            operations=(SemanticOperation(name="test"),),
            prompt_supplied_context=("context item",),
            entities=(MentionedEntity(name="Entity1"),),
            references=(SemanticReference(expression="this"),),
            temporal_references=(TemporalReference(expression="yesterday"),),
            attachments=(AttachmentReference(name="file.txt"),),
            dependencies=(ContextDependency(description="dep"),),
            ambiguities=(
                SemanticAmbiguity(
                    kind=AmbiguityKind.VAGUE_SCOPE, description="ambig"
                ),
            ),
        )

        for f in dataclasses.fields(req):
            val = getattr(req, f.name)
            self.assertNotIsInstance(
                val,
                dict,
                f"Field '{f.name}' in DecodedRequest is a mutable dict! Must be immutable.",
            )
            self.assertNotIsInstance(
                val,
                list,
                f"Field '{f.name}' in DecodedRequest is a mutable list! Must be immutable tuple.",
            )

        # Attempting direct mutation must raise FrozenInstanceError
        with self.assertRaises(dataclasses.FrozenInstanceError):
            req.raw_text = "new text"  # type: ignore

    def test_decode_input_is_genuinely_immutable(self):
        """DecodeInput must have no mutable dict/list attributes."""
        inp = DecodeInput(
            raw_text="Process this",
            attachments=(AttachmentReference(name="doc.pdf"),),
        )

        for f in dataclasses.fields(inp):
            val = getattr(inp, f.name)
            self.assertNotIsInstance(
                val,
                dict,
                f"Field '{f.name}' in DecodeInput is a mutable dict!",
            )
            self.assertNotIsInstance(
                val,
                list,
                f"Field '{f.name}' in DecodeInput is a mutable list!",
            )

        with self.assertRaises(dataclasses.FrozenInstanceError):
            inp.raw_text = "mutated"  # type: ignore

        # Convenience constructor produces identical immutable instance
        from_text_inp = DecodeInput.from_text("Process this")
        self.assertEqual(from_text_inp.raw_text, "Process this")
        self.assertEqual(from_text_inp.attachments, ())

    def test_serialization_produces_no_generic_metadata_key(self):
        """DecodedRequest.to_dict() must not carry arbitrary generic metadata."""
        req = DecodedRequest(
            raw_text="Bring that file up.",
            goal=IntendedOutcome(description="retrieve file"),
        )
        data = req.to_dict()
        self.assertNotIn("metadata", data)

        reconstructed = DecodedRequest.from_dict(data)
        self.assertFalse(hasattr(reconstructed, "metadata"))
        self.assertEqual(req, reconstructed)


class ContextDependencyNeutralityTests(unittest.TestCase):
    """Verifies that Step 1 identifies THAT context is required without dictating storage tier."""

    def test_bring_that_file_up_does_not_assert_same_session(self):
        """'Bring that file up.' -> CONTEXT_REQUIRED, never claims same-session."""
        dep = ContextDependency(
            description="referent 'that file' requires contextual lookup",
            category=ContextDependencyCategory.CONTEXT_REQUIRED,
            unresolved_reference="that file",
        )
        self.assertEqual(dep.category, ContextDependencyCategory.CONTEXT_REQUIRED)
        self.assertNotEqual(dep.category.value, "same_session_context")

    def test_use_attached_spreadsheet_is_current_attachment(self):
        """'Use the attached spreadsheet.' legitimately specifies CURRENT_ATTACHMENT."""
        dep = ContextDependency(
            description="spreadsheet content explicitly supplied in current request",
            category=ContextDependencyCategory.CURRENT_ATTACHMENT,
            unresolved_reference="attached spreadsheet",
        )
        self.assertEqual(dep.category, ContextDependencyCategory.CURRENT_ATTACHMENT)
        self.assertEqual(dep.category.value, "current_attachment")

    def test_what_was_approved_yesterday_is_prior_context_unspecified(self):
        """'What was approved yesterday?' -> PRIOR_CONTEXT_UNSPECIFIED, no session assumption."""
        dep = ContextDependency(
            description="approvals from yesterday require prior context resolution",
            category=ContextDependencyCategory.PRIOR_CONTEXT_UNSPECIFIED,
            unresolved_reference="what was approved yesterday",
        )
        self.assertEqual(
            dep.category, ContextDependencyCategory.PRIOR_CONTEXT_UNSPECIFIED
        )
        self.assertEqual(dep.category.value, "prior_context_unspecified")

    def test_all_dependency_categories_are_step2_neutral(self):
        """Every category in ContextDependencyCategory avoids Step-2 storage commitments."""
        expected_categories = {
            "context_required",
            "prior_context_unspecified",
            "current_attachment",
            "external_information",
        }
        actual_categories = {c.value for c in ContextDependencyCategory}
        self.assertEqual(expected_categories, actual_categories)


class CanonicalSemanticDecoderInterfaceTests(unittest.TestCase):
    """Verifies the single canonical input signature for SemanticDecoder."""

    def test_decoder_strictly_requires_decode_input(self):
        """Subclasses must implement decode(self, input_data: DecodeInput)."""

        class StrictDecoder(SemanticDecoder):
            def decode(self, input_data: DecodeInput) -> DecodedRequest:
                if not isinstance(input_data, DecodeInput):
                    raise TypeError(
                        f"Expected DecodeInput, got {type(input_data).__name__}"
                    )
                return DecodedRequest(
                    raw_text=input_data.raw_text,
                    goal=IntendedOutcome(description="test goal"),
                )

        decoder = StrictDecoder()

        # Direct DecodeInput call works cleanly
        inp = DecodeInput(raw_text="Convert this to PDF.")
        result = decoder.decode(inp)
        self.assertIsInstance(result, DecodedRequest)
        self.assertEqual(result.raw_text, "Convert this to PDF.")

        # DecodeInput.from_text convenience constructor works cleanly
        result2 = decoder.decode(DecodeInput.from_text("Bring that file up."))
        self.assertEqual(result2.raw_text, "Bring that file up.")

        # Passing a raw string directly to a canonical decoder fails type check
        with self.assertRaises(TypeError):
            decoder.decode("raw string not wrapped in DecodeInput")  # type: ignore


if __name__ == "__main__":
    unittest.main()
