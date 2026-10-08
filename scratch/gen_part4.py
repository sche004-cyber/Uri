"""Generator part 4: Fixtures 65 to 80 (Office Ambiguous, Multi-Ref, and Unknowns)."""

import sys
repo_root = r"C:\Users\cheta\Development\Uri\_V1"
sys.path.insert(0, repo_root)

from uri_v1.turn.rar_contracts import (
    RARCandidate,
    RAREvidence,
    RARFixture,
    RAROutcome,
    RARQuery,
)

def get_fixtures_65_to_80():
    f = []
    # -------------------------------------------------------------
    # 9. Office / Institutional: Cross-Reference, Ambiguity & Boundary (S4B-065 .. S4B-074)
    # -------------------------------------------------------------
    f.append(RARFixture(
        id="S4B-065",
        name="Ambiguous reference across two equally plausible department circulars",
        category="office_ambiguous_equal",
        turn_text="Send the circular to all department faculty members.",
        query=RARQuery(
            reference_expression="the circular",
            candidates=(
                RARCandidate(id="circ_dept_eval", title="Continuous_Assessment_Evaluation_Circular.pdf", candidate_type="document", domain_tags=("academic", "circular")),
                RARCandidate(id="circ_dept_fac", title="Department_Faculty_Meeting_Circular.pdf", candidate_type="document", domain_tags=("meeting", "circular")),
            ),
            local_evidence=RAREvidence(target_type_hint="document"),
        ),
        expected_outcome=RAROutcome.AMBIGUOUS,
        expected_ambiguous_candidate_ids=("circ_dept_eval", "circ_dept_fac"),
        description="Two departmental circulars exist with no recency, selection, or specific term distinguishing them.",
    ))

    f.append(RARFixture(
        id="S4B-066",
        name="Request for absent external accreditation agency dossier",
        category="office_unknown_absent",
        turn_text="Where is the ABET accreditation self-study questionnaire?",
        query=RARQuery(
            reference_expression="the ABET accreditation self-study questionnaire",
            candidates=(
                RARCandidate(id="doc_naac_ssr", title="NAAC_Self_Study_Report_2025.pdf", candidate_type="document"),
                RARCandidate(id="doc_nba_sar", title="NBA_Self_Assessment_Report_Tier1.pdf", candidate_type="document"),
                RARCandidate(id="doc_nirf_data", title="NIRF_Institutional_Data_Submission.pdf", candidate_type="document"),
            ),
            local_evidence=RAREvidence(target_type_hint="document"),
        ),
        expected_outcome=RAROutcome.UNKNOWN,
        description="The candidate set contains NAAC, NBA, and NIRF documents; the requested ABET accreditation file is absent.",
    ))

    f.append(RARFixture(
        id="S4B-067",
        name="Unanchored generic pronoun with multiple masculine faculty candidates",
        category="office_ambiguous_pronoun",
        turn_text="Did he approve the lab equipment procurement?",
        query=RARQuery(
            reference_expression="he",
            candidates=(
                RARCandidate(id="person_prof_gupta", title="Prof. R. C. Gupta (Head of Department)", candidate_type="person"),
                RARCandidate(id="person_prof_iyer", title="Prof. S. K. Iyer (Convener Purchase Committee)", candidate_type="person"),
            ),
            local_evidence=RAREvidence(target_type_hint="person"),
        ),
        expected_outcome=RAROutcome.AMBIGUOUS,
        expected_ambiguous_candidate_ids=("person_prof_gupta", "person_prof_iyer"),
        description="Unanchored pronoun 'he' is ambiguous between the two male faculty heads present in the context.",
    ))

    f.append(RARFixture(
        id="S4B-068",
        name="Vague deictic reference to multiple dormitory repair requisitions",
        category="office_ambiguous_deictic",
        turn_text="Process that one next.",
        query=RARQuery(
            reference_expression="that one",
            candidates=(
                RARCandidate(id="wf_maint_roof", title="Hostel 3 Roof Waterproofing Repair Requisition", candidate_type="workflow"),
                RARCandidate(id="wf_maint_paint", title="Hostel 2 Common Room Painting Requisition", candidate_type="workflow"),
                RARCandidate(id="wf_maint_drain", title="Mess Drainage Clearing Emergency Requisition", candidate_type="workflow"),
            ),
            local_evidence=RAREvidence(target_type_hint="workflow"),
        ),
        expected_outcome=RAROutcome.AMBIGUOUS,
        expected_ambiguous_candidate_ids=("wf_maint_roof", "wf_maint_paint", "wf_maint_drain"),
        description="'That one' provides zero distinguishing lexical or structural cues among three plausible maintenance workflows.",
    ))

    f.append(RARFixture(
        id="S4B-069",
        name="Request for absent faculty appointment order",
        category="office_unknown_absent",
        turn_text="Forward appointment letter APT-2026-FAC-044 to the registrar.",
        query=RARQuery(
            reference_expression="APT-2026-FAC-044",
            candidates=(
                RARCandidate(id="apt_fac_041", title="Appointment Letter: Assistant Professor Mathematics (APT-041)", candidate_type="document"),
                RARCandidate(id="apt_fac_042", title="Appointment Letter: Assistant Professor Physics (APT-042)", candidate_type="document"),
            ),
        ),
        expected_outcome=RAROutcome.UNKNOWN,
        description="Appointment reference APT-2026-FAC-044 is not present in the candidate set.",
    ))

    f.append(RARFixture(
        id="S4B-070",
        name="Ambiguous reference to one of multiple identical vendor invoices",
        category="office_ambiguous_equal",
        turn_text="Review the invoice.",
        query=RARQuery(
            reference_expression="the invoice",
            candidates=(
                RARCandidate(id="inv_stationery_jan", title="Invoice_Office_Stationery_Jan.pdf", candidate_type="document", domain_tags=("invoice", "stationery")),
                RARCandidate(id="inv_stationery_feb", title="Invoice_Office_Stationery_Feb.pdf", candidate_type="document", domain_tags=("invoice", "stationery")),
            ),
            local_evidence=RAREvidence(target_type_hint="document"),
        ),
        expected_outcome=RAROutcome.AMBIGUOUS,
        expected_ambiguous_candidate_ids=("inv_stationery_jan", "inv_stationery_feb"),
        description="Two stationery invoices exist with identical relevance to 'the invoice'; ambiguous.",
    ))

    f.append(RARFixture(
        id="S4B-071",
        name="Request for absent external auditor certificate",
        category="office_unknown_absent",
        turn_text="Check the compliance certificate from the statutory auditor.",
        query=RARQuery(
            reference_expression="the compliance certificate",
            candidates=(
                RARCandidate(id="audit_internal_rep", title="Internal_Financial_Audit_Report_2025.pdf", candidate_type="document"),
                RARCandidate(id="audit_asset_reg", title="Annual_Fixed_Asset_Register.xlsx", candidate_type="spreadsheet"),
            ),
            local_evidence=RAREvidence(target_type_hint="document"),
        ),
        expected_outcome=RAROutcome.UNKNOWN,
        description="The candidate set contains internal audit documents, but no statutory auditor compliance certificate.",
    ))

    f.append(RARFixture(
        id="S4B-072",
        name="Distinguishing term isolation for physics laboratory technician",
        category="office_term_discrimination",
        turn_text="Ask the technician to calibrate the spectrometer.",
        query=RARQuery(
            reference_expression="the technician",
            candidates=(
                RARCandidate(id="person_tech_spectro", title="Subhash Pal (Senior Technical Assistant - Spectroscopy Lab)", candidate_type="person", domain_tags=("technician", "spectroscopy")),
                RARCandidate(id="person_prof_head", title="Prof. D. Sen (Head Department of Physics)", candidate_type="person", domain_tags=("faculty", "hod")),
            ),
            local_evidence=RAREvidence(target_type_hint="person"),
        ),
        expected_outcome=RAROutcome.RESOLVED,
        expected_candidate_id="person_tech_spectro",
        description="'The technician' discriminates the technical assistant person_tech_spectro from the professor.",
    ))

    f.append(RARFixture(
        id="S4B-073",
        name="Reference to non-existent campus map file",
        category="office_unknown_absent",
        turn_text="Open the campus master plan CAD drawing.",
        query=RARQuery(
            reference_expression="the campus master plan CAD drawing",
            candidates=(
                RARCandidate(id="doc_estate_summary", title="Campus_Estate_Building_Area_Summary.pdf", candidate_type="document"),
                RARCandidate(id="doc_boundary_survey", title="Land_Survey_Coordinates_Report.pdf", candidate_type="document"),
            ),
            local_evidence=RAREvidence(target_type_hint="document"),
        ),
        expected_outcome=RAROutcome.UNKNOWN,
        description="No CAD drawing or master plan file is present in the candidate pool.",
    ))

    f.append(RARFixture(
        id="S4B-074",
        name="Ambiguous reference across two department annual reports",
        category="office_ambiguous_equal",
        turn_text="Send the annual report to the IQAC director.",
        query=RARQuery(
            reference_expression="the annual report",
            candidates=(
                RARCandidate(id="rep_annual_cse", title="Department_Annual_Report_CSE_2025.pdf", candidate_type="document", domain_tags=("annual_report",)),
                RARCandidate(id="rep_annual_ee", title="Department_Annual_Report_EE_2025.pdf", candidate_type="document", domain_tags=("annual_report",)),
            ),
            local_evidence=RAREvidence(target_type_hint="document"),
        ),
        expected_outcome=RAROutcome.AMBIGUOUS,
        expected_ambiguous_candidate_ids=("rep_annual_cse", "rep_annual_ee"),
        description="Two department annual reports match 'the annual report' equally without department qualification.",
    ))

    # -------------------------------------------------------------
    # 10. Office / Institutional: Multi-Reference Turns Decomposed (S4B-075A/B .. S4B-077A/B)
    # -------------------------------------------------------------
    turn_75 = "Attach the revised fee notice to the syndicate approval email."
    f.append(RARFixture(
        id="S4B-075A",
        name="Multi-reference 1A: revised fee notice attachment",
        category="office_multi_reference",
        turn_text=turn_75,
        query=RARQuery(
            reference_expression="the revised fee notice",
            candidates=(
                RARCandidate(id="notif_fee_orig", title="Tuition_Fee_Revision_Notification.pdf", candidate_type="document", domain_tags=("original",)),
                RARCandidate(id="notif_fee_rev", title="Tuition_Fee_Revision_Notification.pdf", candidate_type="document", domain_tags=("revised",)),
            ),
            local_evidence=RAREvidence(clause_text="Attach the revised fee notice", recency_hint="revised", target_type_hint="document"),
        ),
        expected_outcome=RAROutcome.RESOLVED,
        expected_candidate_id="notif_fee_rev",
        description="First reference of decomposed turn: 'the revised fee notice' uniquely resolves to notif_fee_rev.",
    ))
    f.append(RARFixture(
        id="S4B-075B",
        name="Multi-reference 1B: syndicate approval email target",
        category="office_multi_reference",
        turn_text=turn_75,
        query=RARQuery(
            reference_expression="the syndicate approval email",
            candidates=(
                RARCandidate(id="mail_synd_approval", title="Draft Email: Syndicate Formal Approval of Fee Restructuring", candidate_type="email"),
                RARCandidate(id="mail_finance_query", title="Email: Finance Officer Query on Depreciation", candidate_type="email"),
            ),
            local_evidence=RAREvidence(clause_text="to the syndicate approval email", target_type_hint="email"),
        ),
        expected_outcome=RAROutcome.RESOLVED,
        expected_candidate_id="mail_synd_approval",
        description="Second reference of decomposed turn: 'the syndicate approval email' uniquely matches mail_synd_approval.",
    ))

    turn_76 = "Verify the candidate's degree certificate and submit the verification report."
    f.append(RARFixture(
        id="S4B-076A",
        name="Multi-reference 2A: candidate degree certificate",
        category="office_multi_reference",
        turn_text=turn_76,
        query=RARQuery(
            reference_expression="the candidate's degree certificate",
            candidates=(
                RARCandidate(id="cert_btech_degree", title="Degree_Certificate_Original_Scan_BTech.pdf", candidate_type="document", domain_tags=("certificate", "degree")),
                RARCandidate(id="cert_inter_marksheet", title="Intermediate_Marksheet_Verification.pdf", candidate_type="document", domain_tags=("marksheet",)),
            ),
            local_evidence=RAREvidence(clause_text="Verify the candidate's degree certificate", target_type_hint="document"),
        ),
        expected_outcome=RAROutcome.RESOLVED,
        expected_candidate_id="cert_btech_degree",
        description="First reference of decomposed turn: 'the candidate's degree certificate' resolves to cert_btech_degree.",
    ))
    f.append(RARFixture(
        id="S4B-076B",
        name="Multi-reference 2B: verification report workflow",
        category="office_multi_reference",
        turn_text=turn_76,
        query=RARQuery(
            reference_expression="the verification report",
            candidates=(
                RARCandidate(id="doc_verif_report_draft", title="Credential_Verification_Report_Form.docx", candidate_type="document", domain_tags=("verification_report",)),
                RARCandidate(id="doc_police_verif", title="Police_Character_Verification_Report.pdf", candidate_type="document", domain_tags=("police",)),
            ),
            local_evidence=RAREvidence(clause_text="and submit the verification report", target_type_hint="document"),
        ),
        expected_outcome=RAROutcome.RESOLVED,
        expected_candidate_id="doc_verif_report_draft",
        description="Second reference of decomposed turn: 'the verification report' selects doc_verif_report_draft.",
    ))

    turn_77 = "Compare the hostel allotment list with the warden's room allocation register."
    f.append(RARFixture(
        id="S4B-077A",
        name="Multi-reference 3A: hostel allotment list",
        category="office_multi_reference",
        turn_text=turn_77,
        query=RARQuery(
            reference_expression="the hostel allotment list",
            candidates=(
                RARCandidate(id="sheet_allot_list", title="Hostel_5_Room_Allotment_List_Final.xlsx", candidate_type="spreadsheet"),
                RARCandidate(id="sheet_mess_dues", title="Hostel_5_Mess_Dues_Pending.xlsx", candidate_type="spreadsheet"),
            ),
            local_evidence=RAREvidence(clause_text="Compare the hostel allotment list", target_type_hint="spreadsheet"),
        ),
        expected_outcome=RAROutcome.RESOLVED,
        expected_candidate_id="sheet_allot_list",
        description="First reference of decomposed turn: 'the hostel allotment list' binds to sheet_allot_list.",
    ))
    f.append(RARFixture(
        id="S4B-077B",
        name="Multi-reference 3B: room allocation register",
        category="office_multi_reference",
        turn_text=turn_77,
        query=RARQuery(
            reference_expression="the warden's room allocation register",
            candidates=(
                RARCandidate(id="reg_warden_alloc", title="Warden_Physical_Room_Allocation_Register.pdf", candidate_type="document", owner="Chief Warden"),
                RARCandidate(id="reg_estate_keys", title="Estate_Office_Key_Issue_Register.pdf", candidate_type="document", owner="Estate Officer"),
            ),
            local_evidence=RAREvidence(clause_text="with the warden's room allocation register", target_type_hint="document"),
        ),
        expected_outcome=RAROutcome.RESOLVED,
        expected_candidate_id="reg_warden_alloc",
        description="Second reference of decomposed turn: 'the warden's room allocation register' matches reg_warden_alloc.",
    ))

    return f

print("Loaded fixtures 65 to 80.")
