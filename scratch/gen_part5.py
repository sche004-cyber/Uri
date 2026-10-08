"""Generator part 5: Fixtures 81 to 105 (General Work / Productivity)."""

import sys
repo_root = r"C:\Users\cheta\Development\Uri\_V1"
sys.path.insert(0, repo_root)

from uri_v1.turn.rar_contracts import (
    RARCandidate,
    RARDeterministicAnchor,
    RAREvidence,
    RARFixture,
    RAROutcome,
    RARQuery,
)

def get_fixtures_81_to_105():
    f = []
    # -------------------------------------------------------------
    # General Work / Productivity: S4B-081 .. S4B-105 (25 cases)
    # -------------------------------------------------------------
    f.append(RARFixture(
        id="S4B-081",
        name="Sprint planning board card reference",
        category="work_project_management",
        turn_text="Move the authentication refactor ticket to in progress.",
        query=RARQuery(
            reference_expression="the authentication refactor ticket",
            candidates=(
                RARCandidate(id="tkt_auth_refactor", title="PROJ-108: OAuth2 and Session Refactor", candidate_type="workflow", domain_tags=("auth", "backend")),
                RARCandidate(id="tkt_ui_dashboard", title="PROJ-109: Analytics Dashboard Redesign", candidate_type="workflow", domain_tags=("ui", "frontend")),
                RARCandidate(id="tkt_db_migration", title="PROJ-110: Postgres 16 Version Upgrade", candidate_type="workflow", domain_tags=("database", "devops")),
            ),
            local_evidence=RAREvidence(target_type_hint="workflow"),
        ),
        expected_outcome=RAROutcome.RESOLVED,
        expected_candidate_id="tkt_auth_refactor",
        description="'The authentication refactor ticket' matches PROJ-108 OAuth2 and session refactor.",
    ))

    f.append(RARFixture(
        id="S4B-082",
        name="Client quarterly business review slide deck",
        category="work_presentation",
        turn_text="Open the Q3 client presentation deck.",
        query=RARQuery(
            reference_expression="the Q3 client presentation deck",
            candidates=(
                RARCandidate(id="deck_q3_client", title="Acme_Corp_Q3_Business_Review.pptx", candidate_type="presentation", domain_tags=("q3", "client")),
                RARCandidate(id="deck_internal_allhands", title="Engineering_All_Hands_Q3.pptx", candidate_type="presentation", domain_tags=("q3", "internal")),
                RARCandidate(id="sheet_q3_revenue", title="Q3_Revenue_Forecast_Model.xlsx", candidate_type="spreadsheet", domain_tags=("q3", "finance")),
            ),
            local_evidence=RAREvidence(target_type_hint="presentation"),
        ),
        expected_outcome=RAROutcome.RESOLVED,
        expected_candidate_id="deck_q3_client",
        description="Target type presentation combined with 'client' uniquely resolves deck_q3_client.",
    ))

    f.append(RARFixture(
        id="S4B-083",
        name="Architecture decision record identifier reference",
        category="work_engineering_docs",
        turn_text="Review ADR-0024 regarding our event streaming broker choice.",
        query=RARQuery(
            reference_expression="ADR-0024",
            candidates=(
                RARCandidate(id="adr_0024", title="ADR-0024_Kafka_vs_Pulsar_Evaluation.md", candidate_type="document", exact_aliases=("ADR-0024",)),
                RARCandidate(id="adr_0025", title="ADR-0025_Schema_Registry_Protobuf.md", candidate_type="document", exact_aliases=("ADR-0025",)),
            ),
            deterministic_anchor=RARDeterministicAnchor(exact_id="adr_0024"),
        ),
        expected_outcome=RAROutcome.RESOLVED,
        expected_candidate_id="adr_0024",
        description="Exact architectural identifier ADR-0024 maps unambiguously to adr_0024.",
    ))

    f.append(RARFixture(
        id="S4B-084",
        name="Shared team sprint retrospective notes document",
        category="work_meeting_notes",
        turn_text="Add an action item to the retro notes.",
        query=RARQuery(
            reference_expression="the retro notes",
            candidates=(
                RARCandidate(id="doc_retro_sprint_14", title="Sprint_14_Retrospective_Action_Items.docx", candidate_type="document", domain_tags=("retrospective", "notes")),
                RARCandidate(id="doc_planning_sprint_15", title="Sprint_15_Planning_Goals.docx", candidate_type="document", domain_tags=("planning",)),
            ),
            local_evidence=RAREvidence(target_type_hint="document"),
        ),
        expected_outcome=RAROutcome.RESOLVED,
        expected_candidate_id="doc_retro_sprint_14",
        description="'The retro notes' corresponds cleanly to doc_retro_sprint_14.",
    ))

    f.append(RARFixture(
        id="S4B-085",
        name="Ambiguous reference across two product roadmap drafts",
        category="work_ambiguous_drafts",
        turn_text="Share the roadmap draft with marketing.",
        query=RARQuery(
            reference_expression="the roadmap draft",
            candidates=(
                RARCandidate(id="doc_roadmap_mobile", title="Mobile_App_Product_Roadmap_H2.docx", candidate_type="document", domain_tags=("roadmap", "draft")),
                RARCandidate(id="doc_roadmap_web", title="Web_Platform_Product_Roadmap_H2.docx", candidate_type="document", domain_tags=("roadmap", "draft")),
            ),
            local_evidence=RAREvidence(target_type_hint="document"),
        ),
        expected_outcome=RAROutcome.AMBIGUOUS,
        expected_ambiguous_candidate_ids=("doc_roadmap_mobile", "doc_roadmap_web"),
        description="Both mobile and web roadmap drafts match 'the roadmap draft' with no differentiator.",
    ))

    f.append(RARFixture(
        id="S4B-086",
        name="Customer discovery call audio recording",
        category="work_media_interview",
        turn_text="Transcribe the customer interview recording from yesterday.",
        query=RARQuery(
            reference_expression="the customer interview recording",
            candidates=(
                RARCandidate(id="media_interview_fintech", title="User_Research_Call_Fintech_Lead.m4a", candidate_type="media", domain_tags=("interview", "recording")),
                RARCandidate(id="doc_interview_notes", title="User_Research_Synthesized_Notes.docx", candidate_type="document"),
            ),
            local_evidence=RAREvidence(target_type_hint="media"),
        ),
        expected_outcome=RAROutcome.RESOLVED,
        expected_candidate_id="media_interview_fintech",
        description="Type media combined with 'interview recording' isolates the audio recording candidate.",
    ))

    f.append(RARFixture(
        id="S4B-087",
        name="Request for absent competitor benchmark matrix",
        category="work_unknown_absent",
        turn_text="Where is the Gartner Magic Quadrant competitor matrix?",
        query=RARQuery(
            reference_expression="the Gartner Magic Quadrant competitor matrix",
            candidates=(
                RARCandidate(id="sheet_pricing_matrix", title="Internal_Tiered_Pricing_Matrix.xlsx", candidate_type="spreadsheet"),
                RARCandidate(id="doc_feature_checklist", title="Product_Feature_Checklist_Q2.docx", candidate_type="document"),
            ),
            local_evidence=RAREvidence(target_type_hint="spreadsheet"),
        ),
        expected_outcome=RAROutcome.UNKNOWN,
        description="The requested Gartner competitor analysis matrix is not present in the candidate pool.",
    ))

    f.append(RARFixture(
        id="S4B-088",
        name="Active UI selected pull request in review dashboard",
        category="work_ui_anchor",
        turn_text="Approve this pull request and leave a comment to merge after CI passes.",
        query=RARQuery(
            reference_expression="this pull request",
            candidates=(
                RARCandidate(id="pr_512_caching", title="PR #512: Implement Redis Cluster Session Store", candidate_type="workflow"),
                RARCandidate(id="pr_513_metrics", title="PR #513: Add Prometheus Latency Histograms", candidate_type="workflow"),
            ),
            deterministic_anchor=RARDeterministicAnchor(selected_ui_id="pr_512_caching"),
        ),
        expected_outcome=RAROutcome.RESOLVED,
        expected_candidate_id="pr_512_caching",
        description="The active UI selection anchor resolves 'this pull request' to PR #512.",
    ))

    f.append(RARFixture(
        id="S4B-089",
        name="Latest project budget financial forecast model",
        category="work_temporal_latest",
        turn_text="Open the latest financial projection model.",
        query=RARQuery(
            reference_expression="the latest financial projection model",
            candidates=(
                RARCandidate(id="sheet_model_v4", title="Project_Titan_Financial_Model.xlsx", candidate_type="spreadsheet", recency_rank=0),
                RARCandidate(id="sheet_model_v3", title="Project_Titan_Financial_Model.xlsx", candidate_type="spreadsheet", recency_rank=1),
                RARCandidate(id="sheet_model_v2", title="Project_Titan_Financial_Model.xlsx", candidate_type="spreadsheet", recency_rank=2),
            ),
            local_evidence=RAREvidence(recency_hint="latest", target_type_hint="spreadsheet"),
        ),
        expected_outcome=RAROutcome.RESOLVED,
        expected_candidate_id="sheet_model_v4",
        description="'The latest' with recency_rank 0 uniquely resolves sheet_model_v4 among identically-titled models.",
    ))

    f.append(RARFixture(
        id="S4B-090",
        name="Contrastive selection between design mockups",
        category="work_contrast",
        turn_text="Not the dark theme mockup, show the client the other mockup.",
        query=RARQuery(
            reference_expression="the other mockup",
            candidates=(
                RARCandidate(id="fig_mock_dark", title="Mobile_Home_Screen_Dark_Theme.png", candidate_type="media", domain_tags=("dark", "mockup")),
                RARCandidate(id="fig_mock_light", title="Mobile_Home_Screen_Light_Theme.png", candidate_type="media", domain_tags=("light", "mockup")),
            ),
            local_evidence=RAREvidence(
                negation_spans=("Not the dark theme mockup",),
                recency_hint="other",
                target_type_hint="media",
            ),
        ),
        expected_outcome=RAROutcome.RESOLVED,
        expected_candidate_id="fig_mock_light",
        description="Negation explicitly rejects the dark theme; 'the other mockup' resolves to the light theme.",
    ))

    f.append(RARFixture(
        id="S4B-091",
        name="Engineering postmortem document shortened reference",
        category="work_shortened_name",
        turn_text="Email the postmortem to the incident response channel.",
        query=RARQuery(
            reference_expression="the postmortem",
            candidates=(
                RARCandidate(id="doc_postmortem_outage", title="Postmortem_Payment_Gateway_Outage_March.docx", candidate_type="document", domain_tags=("postmortem", "incident")),
                RARCandidate(id="doc_runbook_deploy", title="Deployment_Rollback_Runbook.md", candidate_type="document"),
            ),
            local_evidence=RAREvidence(target_type_hint="document"),
        ),
        expected_outcome=RAROutcome.RESOLVED,
        expected_candidate_id="doc_postmortem_outage",
        description="'The postmortem' unambiguously identifies the incident postmortem document.",
    ))

    f.append(RARFixture(
        id="S4B-092",
        name="Ambiguous reference across two customer contracts",
        category="work_ambiguous_contracts",
        turn_text="Check the liability clause in the contract.",
        query=RARQuery(
            reference_expression="the contract",
            candidates=(
                RARCandidate(id="doc_contract_apex", title="Master_Services_Agreement_Apex_Systems.pdf", candidate_type="document", domain_tags=("contract",)),
                RARCandidate(id="doc_contract_zenith", title="Master_Services_Agreement_Zenith_Media.pdf", candidate_type="document", domain_tags=("contract",)),
            ),
            local_evidence=RAREvidence(target_type_hint="document"),
        ),
        expected_outcome=RAROutcome.AMBIGUOUS,
        expected_ambiguous_candidate_ids=("doc_contract_apex", "doc_contract_zenith"),
        description="Two client MSA contracts exist; without naming Apex or Zenith, 'the contract' is ambiguous.",
    ))

    f.append(RARFixture(
        id="S4B-093",
        name="Current attachment in email client composition window",
        category="work_attachment_anchor",
        turn_text="Send this attachment to the legal counsel.",
        query=RARQuery(
            reference_expression="this attachment",
            candidates=(
                RARCandidate(id="att_nda_draft", title="Mutual_Non_Disclosure_Agreement_Draft.docx", candidate_type="document", is_attachment=True),
                RARCandidate(id="doc_nda_template", title="Standard_Company_NDA_Template.docx", candidate_type="document", is_attachment=False),
            ),
            deterministic_anchor=RARDeterministicAnchor(current_attachment_id="att_nda_draft"),
        ),
        expected_outcome=RAROutcome.RESOLVED,
        expected_candidate_id="att_nda_draft",
        description="Active attachment anchor links 'this attachment' to the attached draft NDA.",
    ))

    f.append(RARFixture(
        id="S4B-094",
        name="Request for absent Kubernetes deployment manifest",
        category="work_unknown_absent",
        turn_text="Apply the Redis production statefulset YAML.",
        query=RARQuery(
            reference_expression="the Redis production statefulset YAML",
            candidates=(
                RARCandidate(id="cfg_k8s_api", title="production-api-deployment.yaml", candidate_type="document"),
                RARCandidate(id="cfg_k8s_worker", title="production-worker-deployment.yaml", candidate_type="document"),
            ),
            local_evidence=RAREvidence(target_type_hint="document"),
        ),
        expected_outcome=RAROutcome.UNKNOWN,
        description="The candidate set contains API and worker deployment manifests, but the Redis statefulset is absent.",
    ))

    f.append(RARFixture(
        id="S4B-095",
        name="Continuation reference to recently discussed project brief",
        category="work_active_pointer",
        turn_text="Share the same project brief with the onboarding contractor.",
        query=RARQuery(
            reference_expression="the same project brief",
            candidates=(
                RARCandidate(id="doc_brief_falcon", title="Project_Falcon_Executive_Brief.docx", candidate_type="document", domain_tags=("recently_discussed",)),
                RARCandidate(id="doc_brief_orion", title="Project_Orion_Executive_Brief.docx", candidate_type="document", recency_rank=3),
            ),
            local_evidence=RAREvidence(recency_hint="same", target_type_hint="document"),
        ),
        expected_outcome=RAROutcome.RESOLVED,
        expected_candidate_id="doc_brief_falcon",
        description="'The same project brief' binds to the recently discussed Project Falcon brief.",
    ))

    f.append(RARFixture(
        id="S4B-096",
        name="Revised product requirements specification document",
        category="work_revision_relation",
        turn_text="Review the revised spec with the front-end engineering lead.",
        query=RARQuery(
            reference_expression="the revised spec",
            candidates=(
                RARCandidate(id="prd_checkout_orig", title="PRD_One_Click_Checkout.docx", candidate_type="document", domain_tags=("original",)),
                RARCandidate(id="prd_checkout_rev", title="PRD_One_Click_Checkout.docx", candidate_type="document", domain_tags=("revised",)),
            ),
            local_evidence=RAREvidence(recency_hint="revised", target_type_hint="document"),
        ),
        expected_outcome=RAROutcome.RESOLVED,
        expected_candidate_id="prd_checkout_rev",
        description="'The revised spec' targets the revised version of the checkout PRD.",
    ))

    f.append(RARFixture(
        id="S4B-097",
        name="Ambiguous reference across two sales pipeline spreadsheets",
        category="work_ambiguous_sheets",
        turn_text="Export the sales pipeline numbers.",
        query=RARQuery(
            reference_expression="the sales pipeline",
            candidates=(
                RARCandidate(id="sheet_pipeline_us", title="Enterprise_Sales_Pipeline_North_America.xlsx", candidate_type="spreadsheet"),
                RARCandidate(id="sheet_pipeline_eu", title="Enterprise_Sales_Pipeline_EMEA.xlsx", candidate_type="spreadsheet"),
            ),
            local_evidence=RAREvidence(target_type_hint="spreadsheet"),
        ),
        expected_outcome=RAROutcome.AMBIGUOUS,
        expected_ambiguous_candidate_ids=("sheet_pipeline_us", "sheet_pipeline_eu"),
        description="Two regional sales pipeline spreadsheets match 'the sales pipeline'; ambiguous.",
    ))

    f.append(RARFixture(
        id="S4B-098",
        name="Employee performance review dossier by manager",
        category="work_ownership_relation",
        turn_text="Pull up Sarah's appraisal review.",
        query=RARQuery(
            reference_expression="Sarah's appraisal review",
            candidates=(
                RARCandidate(id="doc_eval_sarah", title="Annual_Performance_Appraisal_2025.docx", candidate_type="document", owner="Sarah Jenkins"),
                RARCandidate(id="doc_eval_marcus", title="Annual_Performance_Appraisal_2025.docx", candidate_type="document", owner="Marcus Vance"),
            ),
            local_evidence=RAREvidence(target_type_hint="document"),
        ),
        expected_outcome=RAROutcome.RESOLVED,
        expected_candidate_id="doc_eval_sarah",
        description="Owner metadata matches 'Sarah Jenkins' for doc_eval_sarah.",
    ))

    f.append(RARFixture(
        id="S4B-099",
        name="Generic deictic reference to project tickets",
        category="work_ambiguous_deictic",
        turn_text="Assign it to the release engineer.",
        query=RARQuery(
            reference_expression="it",
            candidates=(
                RARCandidate(id="tkt_bug_gateway", title="Bug 809: Payment Gateway Timeout on Checkout", candidate_type="workflow"),
                RARCandidate(id="tkt_bug_webhook", title="Bug 810: Stripe Webhook Dropping Payload", candidate_type="workflow"),
            ),
            local_evidence=RAREvidence(target_type_hint="workflow"),
        ),
        expected_outcome=RAROutcome.AMBIGUOUS,
        expected_ambiguous_candidate_ids=("tkt_bug_gateway", "tkt_bug_webhook"),
        description="Unanchored pronoun 'it' between two active bug tickets in the queue is ambiguous.",
    ))

    f.append(RARFixture(
        id="S4B-100",
        name="Single person entity distinction for VP of Engineering",
        category="work_person_entity",
        turn_text="Send the weekly executive summary to Alex.",
        query=RARQuery(
            reference_expression="Alex",
            candidates=(
                RARCandidate(id="person_alex_vp", title="Alex Rivera (VP of Engineering)", candidate_type="person"),
                RARCandidate(id="doc_alex_notes", title="Alex_Rivera_1on1_Notes.md", candidate_type="document"),
            ),
            local_evidence=RAREvidence(target_type_hint="person"),
        ),
        expected_outcome=RAROutcome.RESOLVED,
        expected_candidate_id="person_alex_vp",
        description="The reference 'Alex' as a person entity isolates Alex Rivera from his 1-on-1 meeting notes file.",
    ))

    # Multi-reference work cases
    turn_101 = "Export the customer revenue dashboard and email it to the product manager."
    f.append(RARFixture(
        id="S4B-101A",
        name="Work multi-ref 1A: revenue dashboard",
        category="work_multi_reference",
        turn_text=turn_101,
        query=RARQuery(
            reference_expression="the customer revenue dashboard",
            candidates=(
                RARCandidate(id="doc_dash_rev", title="SaaS_Customer_Revenue_Dashboard.pdf", candidate_type="document", domain_tags=("revenue", "dashboard")),
                RARCandidate(id="doc_dash_usage", title="Platform_API_Usage_Dashboard.pdf", candidate_type="document", domain_tags=("usage",)),
            ),
            local_evidence=RAREvidence(clause_text="Export the customer revenue dashboard", target_type_hint="document"),
        ),
        expected_outcome=RAROutcome.RESOLVED,
        expected_candidate_id="doc_dash_rev",
        description="First reference in decomposed turn: matches SaaS customer revenue dashboard.",
    ))
    f.append(RARFixture(
        id="S4B-101B",
        name="Work multi-ref 1B: product manager person recipient",
        category="work_multi_reference",
        turn_text=turn_101,
        query=RARQuery(
            reference_expression="the product manager",
            candidates=(
                RARCandidate(id="person_pm_elena", title="Elena Rostova (Lead Product Manager)", candidate_type="person"),
                RARCandidate(id="person_em_david", title="David Chen (Engineering Manager)", candidate_type="person"),
            ),
            local_evidence=RAREvidence(clause_text="and email it to the product manager", target_type_hint="person"),
        ),
        expected_outcome=RAROutcome.RESOLVED,
        expected_candidate_id="person_pm_elena",
        description="Second reference in decomposed turn: matches lead product manager Elena Rostova.",
    ))

    turn_102 = "Review the architecture proposal and compare it with the previous RFC."
    f.append(RARFixture(
        id="S4B-102A",
        name="Work multi-ref 2A: architecture proposal",
        category="work_multi_reference",
        turn_text=turn_102,
        query=RARQuery(
            reference_expression="the architecture proposal",
            candidates=(
                RARCandidate(id="doc_prop_mesh", title="Service_Mesh_Migration_Proposal.docx", candidate_type="document", domain_tags=("architecture", "proposal")),
                RARCandidate(id="doc_prop_hiring", title="Q4_Engineering_Hiring_Plan.docx", candidate_type="document", domain_tags=("hiring",)),
            ),
            local_evidence=RAREvidence(clause_text="Review the architecture proposal", target_type_hint="document"),
        ),
        expected_outcome=RAROutcome.RESOLVED,
        expected_candidate_id="doc_prop_mesh",
        description="First reference: matches service mesh migration architecture proposal.",
    ))
    f.append(RARFixture(
        id="S4B-102B",
        name="Work multi-ref 2B: previous RFC document",
        category="work_multi_reference",
        turn_text=turn_102,
        query=RARQuery(
            reference_expression="the previous RFC",
            candidates=(
                RARCandidate(id="rfc_mesh_v2", title="RFC-104: Service Mesh Evaluation.md", candidate_type="document", recency_rank=0),
                RARCandidate(id="rfc_mesh_v1", title="RFC-104: Service Mesh Evaluation.md", candidate_type="document", recency_rank=1),
            ),
            local_evidence=RAREvidence(clause_text="compare it with the previous RFC", recency_hint="previous", target_type_hint="document"),
        ),
        expected_outcome=RAROutcome.RESOLVED,
        expected_candidate_id="rfc_mesh_v1",
        description="Second reference: targets the previous version (recency_rank 1) of RFC-104.",
    ))

    f.append(RARFixture(
        id="S4B-103",
        name="Work brand style guide verbatim title",
        category="work_verbatim_title",
        turn_text="Download Brand_Identity_Guidelines_2026.pdf.",
        query=RARQuery(
            reference_expression="Brand_Identity_Guidelines_2026.pdf",
            candidates=(
                RARCandidate(id="doc_brand_guide", title="Brand_Identity_Guidelines_2026.pdf", candidate_type="document"),
                RARCandidate(id="doc_brand_assets", title="Brand_Logo_Vector_Pack.zip", candidate_type="document"),
            ),
        ),
        expected_outcome=RAROutcome.RESOLVED,
        expected_candidate_id="doc_brand_guide",
        description="Verbatim title matches brand identity guidelines PDF.",
    ))

    return f

print("Loaded fixtures 81 to 105.")
