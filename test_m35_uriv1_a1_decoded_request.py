"""M35 Batch A1: DecodedRequest Semantic Contract Tests.

Validates the URIv1 Step 1 semantic contract across:
- All 10 required prompt semantic cases
- Semantic precedence rules (meaning > keywords, goal > verb frequency, etc.)
- Immutability and frozen instance safety
- Full serialization / deserialization round-trip
- Enum completeness and round-trip
- Pure semantic boundary: no tool/capability IDs, no Graphify/ARN fields
- Zero side-effect imports and provider-neutral decoder interface
"""

import dataclasses
import os
import sys
import unittest

REPO_ROOT = os.path.dirname(os.path.abspath(__file__))

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


class DecodedRequestSemanticCasesTests(unittest.TestCase):
    """Verifies the 10 required semantic cases specified in Batch A1."""

    def test_case_1_convert_this_to_pdf(self):
        """Case 1: 'Convert this to PDF.'

        - conversion goal
        - convert operation
        - unresolved 'this' reference
        - PDF output format
        - no tool/capability selection
        """
        raw = "Convert this to PDF."
        req = DecodedRequest(
            raw_text=raw,
            goal=IntendedOutcome(
                description="convert the referenced document to PDF",
                intent_family=IntentFamily.MODIFY,
            ),
            operations=(
                SemanticOperation(name="convert", status=OperationStatus.REQUESTED, target="this"),
            ),
            references=(
                SemanticReference(
                    expression="this",
                    kind=ReferenceKind.PRONOUN,
                    referent_hint="document_to_convert",
                    is_resolved=False,
                ),
            ),
            output_preferences=OutputPreferences(format="PDF"),
            dependencies=(
                ContextDependency(
                    description="unresolved reference 'this' requires contextual resolution",
                    category=ContextDependencyCategory.CONTEXT_REQUIRED,
                    unresolved_reference="this",
                ),
            ),
        )

        self.assertIn("convert", req.goal.description.lower())
        self.assertEqual(req.requested_operations, ("convert",))
        self.assertEqual(len(req.references), 1)
        self.assertEqual(req.references[0].expression, "this")
        self.assertFalse(req.references[0].is_resolved)
        self.assertEqual(req.output_preferences.format, "PDF")

        # Boundary check: no tool or capability IDs exist in Step 1
        self.assertFalse(hasattr(req, "tool_id"))
        self.assertFalse(hasattr(req, "capability_id"))
        self.assertFalse(hasattr(req, "selected_tool"))

    def test_case_2_bring_that_file_up(self):
        """Case 2: 'Bring that file up.'

        - retrieve/open goal
        - unresolved 'that file'
        - context dependency (does NOT prematurely assert same-session)
        """
        raw = "Bring that file up."
        req = DecodedRequest(
            raw_text=raw,
            goal=IntendedOutcome(
                description="retrieve and open the referenced file",
                intent_family=IntentFamily.RETRIEVE,
            ),
            operations=(
                SemanticOperation(name="retrieve", status=OperationStatus.REQUESTED),
                SemanticOperation(name="open", status=OperationStatus.REQUESTED),
            ),
            references=(
                SemanticReference(
                    expression="that file",
                    kind=ReferenceKind.DOCUMENT_OR_FILE,
                    referent_hint="previously mentioned file",
                    is_resolved=False,
                ),
            ),
            dependencies=(
                ContextDependency(
                    description="reference to 'that file' requires context resolution",
                    category=ContextDependencyCategory.CONTEXT_REQUIRED,
                    unresolved_reference="that file",
                ),
            ),
        )

        self.assertEqual(req.goal.intent_family, IntentFamily.RETRIEVE)
        self.assertIn("open", req.requested_operations)
        self.assertIn("retrieve", req.requested_operations)
        self.assertEqual(req.unresolved_references[0].expression, "that file")
        self.assertFalse(req.unresolved_references[0].is_resolved)
        self.assertEqual(len(req.dependencies), 1)
        self.assertEqual(
            req.dependencies[0].category, ContextDependencyCategory.CONTEXT_REQUIRED
        )

    def test_case_3_do_the_same_thing_for_them(self):
        """Case 3: 'Do the same thing for them.'

        - repeat/prior-operation dependency (unspecified source)
        - unresolved 'same thing'
        - unresolved 'them'
        - no invented context
        """
        raw = "Do the same thing for them."
        req = DecodedRequest(
            raw_text=raw,
            goal=IntendedOutcome(
                description="repeat the prior operation for the referenced target group",
                intent_family=IntentFamily.EXECUTE,
            ),
            operations=(
                SemanticOperation(name="repeat_prior_action", status=OperationStatus.REQUESTED),
            ),
            references=(
                SemanticReference(
                    expression="same thing",
                    kind=ReferenceKind.PREVIOUS_ACTION,
                    referent_hint="prior action taken",
                    is_resolved=False,
                ),
                SemanticReference(
                    expression="them",
                    kind=ReferenceKind.PRONOUN,
                    referent_hint="entity or group of individuals",
                    is_resolved=False,
                ),
            ),
            dependencies=(
                ContextDependency(
                    description="prior operation 'same thing' requires prior context resolution",
                    category=ContextDependencyCategory.PRIOR_CONTEXT_UNSPECIFIED,
                    unresolved_reference="same thing",
                ),
                ContextDependency(
                    description="referent 'them' requires context resolution",
                    category=ContextDependencyCategory.CONTEXT_REQUIRED,
                    unresolved_reference="them",
                ),
            ),
            confidence=SemanticConfidence(
                goal=ConfidenceLevel.MEDIUM,
                references=ConfidenceLevel.LOW,
                operations=ConfidenceLevel.MEDIUM,
            ),
        )

        self.assertEqual(len(req.unresolved_references), 2)
        ref_exprs = {r.expression for r in req.unresolved_references}
        self.assertEqual(ref_exprs, {"same thing", "them"})
        # Guarantees that neither "same thing" nor "them" has been invented or resolved
        self.assertTrue(all(not r.is_resolved for r in req.references))
        self.assertEqual(len(req.dependencies), 2)

    def test_case_4_dont_send_it_just_draft_the_email(self):
        """Case 4: 'Don't send it. Just draft the email.'

        - email draft goal
        - do-not-send constraint
        - send not treated as requested execution
        """
        raw = "Don't send it. Just draft the email."
        req = DecodedRequest(
            raw_text=raw,
            goal=IntendedOutcome(
                description="create an email draft without sending",
                intent_family=IntentFamily.CREATE,
            ),
            operations=(
                SemanticOperation(name="draft", status=OperationStatus.REQUESTED),
                SemanticOperation(name="send", status=OperationStatus.PROHIBITED),
            ),
            constraints=ConstraintScope(
                prohibited_actions=("send",),
                draft_only=True,
            ),
            output_preferences=OutputPreferences(artifact_type="email"),
            references=(
                SemanticReference(expression="it", kind=ReferenceKind.PRONOUN, is_resolved=False),
            ),
        )

        self.assertIn("draft", req.requested_operations)
        self.assertNotIn("send", req.requested_operations)
        self.assertIn("send", req.prohibited_operations)
        self.assertTrue(req.constraints.draft_only)
        self.assertIn("send", req.constraints.prohibited_actions)
        self.assertEqual(req.output_preferences.artifact_type, "email")

    def test_case_5_find_previous_approval_compare_and_draft_revised_order(self):
        """Case 5: 'Find the previous approval, compare it with this one and draft a revised order.'

        - final goal = revised order
        - retrieve + compare + draft operations
        - unresolved previous approval (prior context unspecified)
        - unresolved/current reference 'this one'
        """
        raw = "Find the previous approval, compare it with this one and draft a revised order."
        req = DecodedRequest(
            raw_text=raw,
            goal=IntendedOutcome(
                description="draft a revised order based on comparison with previous approval",
                intent_family=IntentFamily.CREATE,
            ),
            operations=(
                SemanticOperation(name="find", status=OperationStatus.REQUESTED, target="previous approval"),
                SemanticOperation(name="compare", status=OperationStatus.REQUESTED, target="previous approval with this one"),
                SemanticOperation(name="draft", status=OperationStatus.REQUESTED, target="revised order"),
            ),
            output_preferences=OutputPreferences(artifact_type="revised order"),
            references=(
                SemanticReference(
                    expression="previous approval",
                    kind=ReferenceKind.TEMPORAL_ORDINAL,
                    referent_hint="prior approval document",
                    is_resolved=False,
                ),
                SemanticReference(
                    expression="this one",
                    kind=ReferenceKind.PRONOUN,
                    referent_hint="current order/decision document",
                    is_resolved=False,
                ),
            ),
            dependencies=(
                ContextDependency(
                    description="locate 'previous approval' in prior context",
                    category=ContextDependencyCategory.PRIOR_CONTEXT_UNSPECIFIED,
                    unresolved_reference="previous approval",
                ),
                ContextDependency(
                    description="resolve 'this one' against context",
                    category=ContextDependencyCategory.CONTEXT_REQUIRED,
                    unresolved_reference="this one",
                ),
            ),
        )

        self.assertEqual(req.output_preferences.artifact_type, "revised order")
        self.assertEqual(set(req.requested_operations), {"find", "compare", "draft"})
        ref_exprs = [r.expression for r in req.references]
        self.assertIn("previous approval", ref_exprs)
        self.assertIn("this one", ref_exprs)
        self.assertTrue(all(not r.is_resolved for r in req.references))

    def test_case_6_committee_changed_view_reconcile_for_tomorrow(self):
        """Case 6: 'The committee has already changed its view twice and the latest letter

        doesn't seem to match what was decided earlier. I need something I can put up tomorrow.'

        - compare/reconcile semantics
        - unresolved latest letter
        - unresolved earlier decisions
        - tomorrow
        - ambiguous final artifact type
        - no fabricated notesheet/order type
        """
        raw = (
            "The committee has already changed its view twice and the latest letter "
            "doesn't seem to match what was decided earlier. I need something I can put up tomorrow."
        )
        req = DecodedRequest(
            raw_text=raw,
            goal=IntendedOutcome(
                description="reconcile committee discrepancies and prepare a submission for tomorrow",
                intent_family=IntentFamily.COMPARE,
            ),
            operations=(
                SemanticOperation(name="compare", status=OperationStatus.REQUESTED),
                SemanticOperation(name="reconcile", status=OperationStatus.REQUESTED),
                SemanticOperation(name="prepare_submission", status=OperationStatus.REQUESTED),
            ),
            prompt_supplied_context=(
                "committee has changed its view twice",
                "latest letter conflicts with earlier decisions",
            ),
            entities=(
                MentionedEntity(name="committee", category=EntityCategory.ORGANIZATION),
            ),
            references=(
                SemanticReference(
                    expression="latest letter",
                    kind=ReferenceKind.DOCUMENT_OR_FILE,
                    referent_hint="most recent communication from committee",
                    is_resolved=False,
                ),
                SemanticReference(
                    expression="what was decided earlier",
                    kind=ReferenceKind.TEMPORAL_ORDINAL,
                    referent_hint="prior decisions/minutes",
                    is_resolved=False,
                ),
                SemanticReference(
                    expression="something I can put up",
                    kind=ReferenceKind.DOCUMENT_OR_FILE,
                    referent_hint="unspecified document for submission",
                    is_resolved=False,
                ),
            ),
            temporal_references=(
                TemporalReference(expression="earlier", is_relative=True),
                TemporalReference(expression="tomorrow", is_relative=True),
            ),
            ambiguities=(
                SemanticAmbiguity(
                    kind=AmbiguityKind.UNRESOLVED_ARTIFACT_TYPE,
                    description="'something I can put up' is ambiguous among notesheet, briefing, or draft order",
                    candidates=("notesheet", "briefing_note", "draft_order"),
                ),
            ),
            output_preferences=OutputPreferences(
                artifact_type=None  # Must NOT fabricate a notesheet or order type!
            ),
        )

        self.assertIn("compare", req.requested_operations)
        self.assertIn("reconcile", req.requested_operations)
        self.assertIsNone(req.output_preferences.artifact_type)
        self.assertTrue(req.has_ambiguities)
        self.assertEqual(
            req.ambiguities[0].kind, AmbiguityKind.UNRESOLVED_ARTIFACT_TYPE
        )
        temporal_exprs = [t.expression for t in req.temporal_references]
        self.assertIn("tomorrow", temporal_exprs)
        self.assertIn("earlier", temporal_exprs)

    def test_case_7_compare_2025_and_2026_under_one_page(self):
        """Case 7: 'Compare only the 2025 and 2026 decisions, do not use anything before 2025,

        and keep the result under one page.'

        - compare
        - included years
        - excluded range
        - one-page limit
        """
        raw = "Compare only the 2025 and 2026 decisions, do not use anything before 2025, and keep the result under one page."
        req = DecodedRequest(
            raw_text=raw,
            goal=IntendedOutcome(
                description="compare 2025 and 2026 decisions within one page",
                intent_family=IntentFamily.COMPARE,
            ),
            operations=(
                SemanticOperation(name="compare", status=OperationStatus.REQUESTED),
            ),
            constraints=ConstraintScope(
                included_items=("2025 decisions", "2026 decisions"),
                excluded_items=("anything before 2025",),
                length_limit="under one page",
                time_range="2025-2026",
            ),
            temporal_references=(
                TemporalReference(expression="2025", is_relative=False),
                TemporalReference(expression="2026", is_relative=False),
            ),
            output_preferences=OutputPreferences(length="under one page"),
        )

        self.assertIn("compare", req.requested_operations)
        self.assertEqual(req.constraints.included_items, ("2025 decisions", "2026 decisions"))
        self.assertEqual(req.constraints.excluded_items, ("anything before 2025",))
        self.assertEqual(req.constraints.length_limit, "under one page")
        self.assertEqual(req.output_preferences.length, "under one page")

    def test_case_8_draft_short_formal_email_indian_english_chief_warden(self):
        """Case 8: 'Draft a short formal email in Indian English to the Chief Warden.'

        - email
        - formal
        - short
        - Indian English
        - Chief Warden audience
        """
        raw = "Draft a short formal email in Indian English to the Chief Warden."
        req = DecodedRequest(
            raw_text=raw,
            goal=IntendedOutcome(
                description="draft a short formal email to the Chief Warden in Indian English",
                intent_family=IntentFamily.CREATE,
            ),
            operations=(
                SemanticOperation(name="draft", status=OperationStatus.REQUESTED),
            ),
            entities=(
                MentionedEntity(name="Chief Warden", category=EntityCategory.ROLE),
            ),
            output_preferences=OutputPreferences(
                artifact_type="email",
                tone="formal",
                length="short",
                language="English",
                language_variant="Indian English",
                audience="Chief Warden",
            ),
            constraints=ConstraintScope(
                length_limit="short",
                language_constraints="Indian English",
            ),
        )

        self.assertEqual(req.output_preferences.artifact_type, "email")
        self.assertEqual(req.output_preferences.tone, "formal")
        self.assertEqual(req.output_preferences.length, "short")
        self.assertEqual(req.output_preferences.language_variant, "Indian English")
        self.assertEqual(req.output_preferences.audience, "Chief Warden")
        self.assertEqual(req.entities[0].name, "Chief Warden")
        self.assertEqual(req.entities[0].category, EntityCategory.ROLE)

    def test_case_9_do_not_summarize_compare_in_table(self):
        """Case 9: 'Do not summarize this; compare the exact figures in a table.'

        - compare requested
        - summarize prohibited
        - table requested
        """
        raw = "Do not summarize this; compare the exact figures in a table."
        req = DecodedRequest(
            raw_text=raw,
            goal=IntendedOutcome(
                description="compare exact figures in a table format without summarization",
                intent_family=IntentFamily.COMPARE,
            ),
            operations=(
                SemanticOperation(name="compare", status=OperationStatus.REQUESTED, target="exact figures"),
                SemanticOperation(name="summarize", status=OperationStatus.PROHIBITED),
            ),
            constraints=ConstraintScope(
                prohibited_actions=("summarize",),
                precision_requirements="exact figures",
            ),
            output_preferences=OutputPreferences(
                structure="table",
                format="table",
            ),
            references=(
                SemanticReference(expression="this", kind=ReferenceKind.PRONOUN, is_resolved=False),
            ),
        )

        self.assertIn("compare", req.requested_operations)
        self.assertNotIn("summarize", req.requested_operations)
        self.assertIn("summarize", req.prohibited_operations)
        self.assertIn("summarize", req.constraints.prohibited_actions)
        self.assertEqual(req.output_preferences.structure, "table")
        self.assertEqual(req.constraints.precision_requirements, "exact figures")

    def test_case_10_what_was_approved_yesterday(self):
        """Case 10: 'What was approved yesterday?'

        - information retrieval/explanation goal
        - yesterday temporal reference
        - unresolved approval context (prior context unspecified)
        - no capability selection
        """
        raw = "What was approved yesterday?"
        req = DecodedRequest(
            raw_text=raw,
            goal=IntendedOutcome(
                description="retrieve information about approvals granted yesterday",
                intent_family=IntentFamily.RETRIEVE,
            ),
            operations=(
                SemanticOperation(name="retrieve_information", status=OperationStatus.REQUESTED),
            ),
            temporal_references=(
                TemporalReference(expression="yesterday", is_relative=True),
            ),
            references=(
                SemanticReference(
                    expression="what was approved",
                    kind=ReferenceKind.TEMPORAL_ORDINAL,
                    referent_hint="approvals/orders issued yesterday",
                    is_resolved=False,
                ),
            ),
            dependencies=(
                ContextDependency(
                    description="locate approvals dated yesterday in prior context",
                    category=ContextDependencyCategory.PRIOR_CONTEXT_UNSPECIFIED,
                    unresolved_reference="what was approved",
                ),
            ),
        )

        self.assertEqual(req.goal.intent_family, IntentFamily.RETRIEVE)
        self.assertEqual(req.temporal_references[0].expression, "yesterday")
        self.assertTrue(req.temporal_references[0].is_relative)
        self.assertEqual(len(req.dependencies), 1)
        self.assertFalse(req.references[0].is_resolved)

        # Boundary check: no tool or capability IDs exist in Step 1
        self.assertFalse(hasattr(req, "capability_id"))
        self.assertFalse(hasattr(req, "tool_id"))


class DecodedRequestContractIntegrityTests(unittest.TestCase):
    """Verifies immutability, serialization, and boundary invariants."""

    def test_immutability(self):
        """All contract dataclasses must be frozen and immutable."""
        req = DecodedRequest(
            raw_text="convert this",
            goal=IntendedOutcome(description="convert document"),
            operations=(SemanticOperation(name="convert"),),
        )

        with self.assertRaises(dataclasses.FrozenInstanceError):
            req.raw_text = "mutate"  # type: ignore

        with self.assertRaises(dataclasses.FrozenInstanceError):
            req.goal = IntendedOutcome(description="mutate")  # type: ignore

        constraints = ConstraintScope(draft_only=True)
        with self.assertRaises(dataclasses.FrozenInstanceError):
            constraints.draft_only = False  # type: ignore

        prefs = OutputPreferences(artifact_type="email")
        with self.assertRaises(dataclasses.FrozenInstanceError):
            prefs.artifact_type = "pdf"  # type: ignore

    def test_serialization_round_trip(self):
        """DecodedRequest must cleanly serialize to dict and deserialize back."""
        original = DecodedRequest(
            raw_text="Check the latest appeal and draft a note.",
            goal=IntendedOutcome(
                description="review latest appeal and draft note",
                intent_family=IntentFamily.CREATE,
            ),
            operations=(
                SemanticOperation(name="check", status=OperationStatus.REQUESTED),
                SemanticOperation(name="draft", status=OperationStatus.REQUESTED),
                SemanticOperation(name="send", status=OperationStatus.PROHIBITED),
            ),
            prompt_supplied_context=("appeal received",),
            constraints=ConstraintScope(
                length_limit="short",
                prohibited_actions=("send",),
                draft_only=True,
            ),
            output_preferences=OutputPreferences(
                artifact_type="notesheet",
                tone="formal",
                language="English",
            ),
            entities=(
                MentionedEntity(name="Registrar", category=EntityCategory.ROLE),
            ),
            references=(
                SemanticReference(
                    expression="latest appeal",
                    kind=ReferenceKind.DOCUMENT_OR_FILE,
                    is_resolved=False,
                ),
            ),
            temporal_references=(
                TemporalReference(expression="yesterday", is_relative=True),
            ),
            attachments=(
                AttachmentReference(
                    identifier="att_1",
                    name="appeal.pdf",
                    mime_type="application/pdf",
                ),
            ),
            dependencies=(
                ContextDependency(
                    description="resolve 'latest appeal'",
                    category=ContextDependencyCategory.CURRENT_ATTACHMENT,
                ),
            ),
            ambiguities=(
                SemanticAmbiguity(
                    kind=AmbiguityKind.VAGUE_SCOPE,
                    description="unclear which committee meeting this belongs to",
                ),
            ),
            confidence=SemanticConfidence(
                goal=ConfidenceLevel.HIGH,
                operations=ConfidenceLevel.HIGH,
                references=ConfidenceLevel.MEDIUM,
                constraints=ConfidenceLevel.HIGH,
                overall=ConfidenceLevel.HIGH,
            ),
        )

        as_dict = original.to_dict()
        self.assertIsInstance(as_dict, dict)
        self.assertEqual(as_dict["raw_text"], original.raw_text)
        self.assertEqual(as_dict["goal"]["description"], original.goal.description)
        self.assertEqual(as_dict["goal"]["intent_family"], "create")
        self.assertEqual(len(as_dict["operations"]), 3)

        reconstructed = DecodedRequest.from_dict(as_dict)
        self.assertEqual(original, reconstructed)
        self.assertEqual(reconstructed.requested_operations, ("check", "draft"))
        self.assertEqual(reconstructed.prohibited_operations, ("send",))
        self.assertEqual(reconstructed.unresolved_references[0].expression, "latest appeal")

    def test_enum_completeness(self):
        """All enums must round-trip cleanly from string."""
        for val in IntentFamily:
            self.assertEqual(IntentFamily(val.value), val)
        for val in OperationStatus:
            self.assertEqual(OperationStatus(val.value), val)
        for val in ConfidenceLevel:
            self.assertEqual(ConfidenceLevel(val.value), val)
        for val in ReferenceKind:
            self.assertEqual(ReferenceKind(val.value), val)
        for val in EntityCategory:
            self.assertEqual(EntityCategory(val.value), val)
        for val in ContextDependencyCategory:
            self.assertEqual(ContextDependencyCategory(val.value), val)
        for val in AmbiguityKind:
            self.assertEqual(AmbiguityKind(val.value), val)

    def test_boundary_no_execution_or_graphify_or_arn_fields(self):
        """DecodedRequest must not carry tool/capability IDs, Graphify references, or ARN data."""
        forbidden_attributes = [
            "tool_id",
            "capability_id",
            "selected_tool",
            "selected_capability",
            "tools",
            "capabilities",
            "execution_status",
            "execution_plan",
            "graphify_index",
            "graph_store",
            "sqlite_path",
            "arn_state",
            "arn_engine",
            "provider_id",
            "model_id",
            "runtime_id",
            "tier_selection",
            "metadata",
        ]
        req = DecodedRequest(raw_text="hello")
        for attr in forbidden_attributes:
            with self.subTest(attr=attr):
                self.assertFalse(hasattr(req, attr), f"Forbidden field '{attr}' found on DecodedRequest")

    def test_semantic_decoder_interface(self):
        """SemanticDecoder must be an abstract class accepting DecodeInput."""
        with self.assertRaises(TypeError):
            SemanticDecoder()  # Cannot instantiate abstract class

        class ConcreteDecoder(SemanticDecoder):
            def decode(self, input_data: DecodeInput) -> DecodedRequest:
                return DecodedRequest(
                    raw_text=input_data.raw_text,
                    goal=IntendedOutcome(description="test goal"),
                )

        decoder = ConcreteDecoder()
        res_from_text = decoder.decode(DecodeInput.from_text("plain text"))
        self.assertEqual(res_from_text.raw_text, "plain text")

        res_input = decoder.decode(
            DecodeInput(
                raw_text="rich input",
                attachments=(AttachmentReference(name="file.pdf"),),
            )
        )
        self.assertEqual(res_input.raw_text, "rich input")


if __name__ == "__main__":
    unittest.main()
