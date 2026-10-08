"""Generator part 7: Fixtures 126 to 135 (Cross-Domain / Mixed Context)."""

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

def get_fixtures_126_to_135():
    f = []
    # -------------------------------------------------------------
    # Cross-Domain / Mixed Context: S4B-126 .. S4B-135 (10 cases)
    # -------------------------------------------------------------
    f.append(RARFixture(
        id="S4B-126",
        name="Mixed context: office travel grant vs personal vacation ticket",
        category="cross_domain_travel",
        turn_text="Send the conference travel ticket to the accounts section.",
        query=RARQuery(
            reference_expression="the conference travel ticket",
            candidates=(
                RARCandidate(id="tkt_conf_vienna", title="Air_India_Delhi_Vienna_Conference_Ticket.pdf", candidate_type="document", domain_tags=("office", "conference", "travel")),
                RARCandidate(id="tkt_vacation_bali", title="Singapore_Airlines_Bali_Family_Holiday.pdf", candidate_type="document", domain_tags=("personal", "vacation", "travel")),
            ),
            local_evidence=RAREvidence(target_type_hint="document"),
        ),
        expected_outcome=RAROutcome.RESOLVED,
        expected_candidate_id="tkt_conf_vienna",
        description="'The conference travel ticket' cleanly discriminates the official academic conference flight from the family vacation ticket.",
    ))

    f.append(RARFixture(
        id="S4B-127",
        name="Mixed context: office reimbursement claim vs personal home repair bill",
        category="cross_domain_finance",
        turn_text="Submit the internet bill for office reimbursement.",
        query=RARQuery(
            reference_expression="the internet bill",
            candidates=(
                RARCandidate(id="bill_home_office_wifi", title="Airtel_Broadband_Tax_Invoice_Home_Office.pdf", candidate_type="document", domain_tags=("office", "reimbursement", "internet")),
                RARCandidate(id="bill_parent_landline", title="BSNL_Landline_Parents_Home.pdf", candidate_type="document", domain_tags=("personal", "utility")),
                RARCandidate(id="doc_claim_form", title="Faculty_Telephone_Reimbursement_Form.pdf", candidate_type="document", domain_tags=("office", "form")),
            ),
            local_evidence=RAREvidence(target_type_hint="document"),
        ),
        expected_outcome=RAROutcome.RESOLVED,
        expected_candidate_id="bill_home_office_wifi",
        description="Target type document with 'internet bill' matches the home office broadband invoice.",
    ))

    f.append(RARFixture(
        id="S4B-128",
        name="Mixed context: university email vs personal Gmail account",
        category="cross_domain_email",
        turn_text="Check the email from Dr. Sen.",
        query=RARQuery(
            reference_expression="the email from Dr. Sen",
            candidates=(
                RARCandidate(id="mail_univ_sen", title="Institutional Email: PhD Thesis Advisory Committee Schedule", candidate_type="email", owner="Dr. A. Sen"),
                RARCandidate(id="mail_personal_clinic", title="Personal Gmail: Dental Clinic Appointment Confirmation", candidate_type="email", owner="Dr. M. Sen Dental"),
            ),
            local_evidence=RAREvidence(target_type_hint="email"),
        ),
        expected_outcome=RAROutcome.AMBIGUOUS,
        expected_ambiguous_candidate_ids=("mail_univ_sen", "mail_personal_clinic"),
        description="Both university and personal inboxes contain an email from a 'Dr. Sen'; without further context, 'the email from Dr. Sen' is ambiguous.",
    ))

    f.append(RARFixture(
        id="S4B-129",
        name="Mixed context: institutional NAAC report vs personal tax return file",
        category="cross_domain_contrast",
        turn_text="Not the tax return file, open the institutional quality report.",
        query=RARQuery(
            reference_expression="the institutional quality report",
            candidates=(
                RARCandidate(id="doc_itr_filing", title="ITR_V_Income_Tax_Acknowledgment_AY26.pdf", candidate_type="document", domain_tags=("personal", "tax")),
                RARCandidate(id="doc_naac_quality", title="IQAC_Annual_Quality_Assurance_Report_2025.pdf", candidate_type="document", domain_tags=("office", "quality", "naac")),
            ),
            local_evidence=RAREvidence(
                negation_spans=("Not the tax return file",),
                target_type_hint="document",
            ),
        ),
        expected_outcome=RAROutcome.RESOLVED,
        expected_candidate_id="doc_naac_quality",
        description="Negation explicitly rules out the tax return; 'the institutional quality report' resolves to doc_naac_quality.",
    ))

    f.append(RARFixture(
        id="S4B-130",
        name="Mixed context: active UI selection on work laptop vs personal phone sync",
        category="cross_domain_ui_anchor",
        turn_text="Print this document on the department network printer.",
        query=RARQuery(
            reference_expression="this document",
            candidates=(
                RARCandidate(id="doc_syll_course", title="CS401_Advanced_Algorithms_Syllabus.pdf", candidate_type="document"),
                RARCandidate(id="doc_car_insurance", title="Car_Insurance_Renewal_Policy.pdf", candidate_type="document"),
            ),
            deterministic_anchor=RARDeterministicAnchor(selected_ui_id="doc_syll_course"),
        ),
        expected_outcome=RAROutcome.RESOLVED,
        expected_candidate_id="doc_syll_course",
        description="Active UI selection anchor uniquely resolves 'this document' to the course syllabus.",
    ))

    f.append(RARFixture(
        id="S4B-131",
        name="Mixed context: absent university housing lease extension",
        category="cross_domain_unknown",
        turn_text="Attach the campus staff quarter lease renewal agreement.",
        query=RARQuery(
            reference_expression="the campus staff quarter lease renewal agreement",
            candidates=(
                RARCandidate(id="doc_personal_flat_lease", title="Private_Apartment_Rental_Agreement_Tenant.pdf", candidate_type="document", domain_tags=("personal", "rental")),
                RARCandidate(id="doc_dept_allotment", title="Department_Lab_Room_Allotment_Order.pdf", candidate_type="document", domain_tags=("office", "estate")),
            ),
            local_evidence=RAREvidence(target_type_hint="document"),
        ),
        expected_outcome=RAROutcome.UNKNOWN,
        description="The user requests the campus staff quarter lease renewal agreement, which is absent from the candidate pool.",
    ))

    f.append(RARFixture(
        id="S4B-132",
        name="Mixed context: continuation pointer to work project in mixed session",
        category="cross_domain_active_pointer",
        turn_text="Share the same presentation with the research collaborators.",
        query=RARQuery(
            reference_expression="the same presentation",
            candidates=(
                RARCandidate(id="pres_grant_defense", title="SERB_CRG_Research_Grant_Defense.pptx", candidate_type="presentation", domain_tags=("recently_discussed", "office")),
                RARCandidate(id="pres_wedding_slideshow", title="Family_Anniversary_Photo_Slideshow.pptx", candidate_type="presentation", recency_rank=4),
            ),
            local_evidence=RAREvidence(recency_hint="same", target_type_hint="presentation"),
        ),
        expected_outcome=RAROutcome.RESOLVED,
        expected_candidate_id="pres_grant_defense",
        description="'The same presentation' points directly to the recently discussed research grant defense deck.",
    ))

    f.append(RARFixture(
        id="S4B-133",
        name="Mixed context: latest version between academic preprint and personal book draft",
        category="cross_domain_temporal_latest",
        turn_text="Open the latest manuscript draft.",
        query=RARQuery(
            reference_expression="the latest manuscript draft",
            candidates=(
                RARCandidate(id="draft_paper_ieee_v3", title="IEEE_Transaction_Paper_Draft.docx", candidate_type="document", recency_rank=0),
                RARCandidate(id="draft_paper_ieee_v2", title="IEEE_Transaction_Paper_Draft.docx", candidate_type="document", recency_rank=1),
                RARCandidate(id="draft_novel_fiction", title="Personal_Fiction_Novel_Chapter_4.docx", candidate_type="document", recency_rank=2),
            ),
            local_evidence=RAREvidence(recency_hint="latest", target_type_hint="document"),
        ),
        expected_outcome=RAROutcome.RESOLVED,
        expected_candidate_id="draft_paper_ieee_v3",
        description="'The latest manuscript draft' with recency_rank 0 identifies draft_paper_ieee_v3.",
    ))

    # Multi-reference mixed context turn
    turn_134 = "Email the conference flight ticket to the university accounts clerk."
    f.append(RARFixture(
        id="S4B-134A",
        name="Mixed context multi-ref A: conference flight ticket",
        category="cross_domain_multi_ref",
        turn_text=turn_134,
        query=RARQuery(
            reference_expression="the conference flight ticket",
            candidates=(
                RARCandidate(id="tkt_indigo_conf", title="IndiGo_Flight_Ticket_BLR_CCU_Conference.pdf", candidate_type="document", domain_tags=("travel", "conference")),
                RARCandidate(id="tkt_movie_pvr", title="PVR_Inox_Movie_Ticket_Weekend.pdf", candidate_type="document", domain_tags=("personal", "entertainment")),
            ),
            local_evidence=RAREvidence(clause_text="Email the conference flight ticket", target_type_hint="document"),
        ),
        expected_outcome=RAROutcome.RESOLVED,
        expected_candidate_id="tkt_indigo_conf",
        description="First reference in decomposed turn: matches conference flight ticket.",
    ))
    f.append(RARFixture(
        id="S4B-134B",
        name="Mixed context multi-ref B: accounts clerk recipient",
        category="cross_domain_multi_ref",
        turn_text=turn_134,
        query=RARQuery(
            reference_expression="the university accounts clerk",
            candidates=(
                RARCandidate(id="person_clerk_accounts", title="Shri S. K. Verma (Upper Division Clerk - Accounts)", candidate_type="person", domain_tags=("office", "accounts")),
                RARCandidate(id="person_agent_travel", title="Rohit Sharma (Personal Travel Agent)", candidate_type="person", domain_tags=("personal", "travel")),
            ),
            local_evidence=RAREvidence(clause_text="to the university accounts clerk", target_type_hint="person"),
        ),
        expected_outcome=RAROutcome.RESOLVED,
        expected_candidate_id="person_clerk_accounts",
        description="Second reference in decomposed turn: matches university accounts clerk.",
    ))

    return f

print("Loaded fixtures 126 to 135.")
