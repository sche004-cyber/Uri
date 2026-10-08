"""M35 Batch A2.5 Stage 3 — Realistic Blind Deterministic RAR Challenge Dataset.

Constructed fresh in Stage 3 (not reused from the pre-existing, audit-trail-less
`rar_challenge_fixtures.py` -- see the Stage 3 report section "Existing
Pre-Built Challenge File Found" for why that file was inspected but not
adopted as this batch's frozen benchmark).

Construction discipline (Phase A -> B -> C, see report):
- Phase A: each scenario was written from realistic URI interaction shape
  first (utterance + bounded candidate set + metadata), never by asking
  "how do I defeat rule X."
- Phase B: expected_outcome / expected_candidate_id / expected_ambiguous_candidate_ids
  and a plain-language ground-truth reason were assigned from the supplied
  context alone, immediately after each scenario was written, before any
  execution against the resolver.
- Phase C: this file was not executed against resolve_rar_deterministic_extended
  until every fixture below was written and this docstring's case count was
  final. See the Stage 3 report for the SHA-256 freeze hash taken at that
  point.

Distribution (100 cases + a disjoint order-perturbation subset):
- S3-001..S3-070: Normal realistic references (~70%)
- S3-071..S3-090: Naturally difficult references (~20%)
- S3-091..S3-100: Legitimately unresolvable / ambiguous (~10%)
- S3-ORD-*: order-perturbation pairs, drawn from a subset of the RESOLVED
  cases above with re-ordered candidate tuples; reported separately, not
  counted toward the 100.

Absolute honesty note on "blindness": the same session that wrote this file
had already read `rar_deterministic.py` in full, per this batch's own
Read-First requirement (inspecting the frozen resolver before building the
benchmark is mandatory). True implementation-blind construction is therefore
not achievable within this workflow. Independence from resolver internals
was instead enforced procedurally: fixtures were drafted from realistic
interaction shape and annotated from plain-language plausibility, not by
targeting named rules (TYPE_FILTER, TERM_DISCRIMINATION, etc.) for defeat.
This limitation is restated in the Stage 3 report.
"""

from __future__ import annotations

from typing import List, Tuple

from uri_v1.turn.rar_contracts import (
    RARCandidate,
    RARDeterministicAnchor,
    RAREvidence,
    RARFixture,
    RAROutcome,
    RARQuery,
)


def get_rar_stage3_fixtures() -> Tuple[RARFixture, ...]:
    """Returns the frozen 100-case Stage 3 realistic blind challenge tranche."""
    f: List[RARFixture] = []

    # =====================================================================
    # NORMAL REALISTIC REFERENCES (S3-001 .. S3-070)
    # =====================================================================

    # --- Explicit identifiers / aliases (5) ---
    f.append(RARFixture(
        id="S3-001", name="Pasted office order number", category="normal_explicit_id",
        turn_text="Open order_2026_1187 and check the signature page.",
        query=RARQuery(
            reference_expression="order_2026_1187",
            candidates=(
                RARCandidate(id="order_2026_1187", title="Office_Order_1187_Fee_Revision.pdf", candidate_type="document"),
                RARCandidate(id="order_2026_1188", title="Office_Order_1188_Hostel_Allotment.pdf", candidate_type="document"),
            ),
            deterministic_anchor=RARDeterministicAnchor(exact_id="order_2026_1187"),
        ),
        expected_outcome=RAROutcome.RESOLVED, expected_candidate_id="order_2026_1187",
        description="User pastes the exact object ID verbatim; unambiguous.",
    ))
    f.append(RARFixture(
        id="S3-002", name="Ticket alias reference", category="normal_explicit_id",
        turn_text="Close ticket-2231, the printer issue is fixed.",
        query=RARQuery(
            reference_expression="ticket-2231",
            candidates=(
                RARCandidate(id="wf_printer_2231", title="Printer Fault - 2nd Floor", candidate_type="workflow", exact_aliases=("ticket-2231",)),
                RARCandidate(id="wf_wifi_2232", title="WiFi Outage - Hostel Block C", candidate_type="workflow", exact_aliases=("ticket-2232",)),
            ),
        ),
        expected_outcome=RAROutcome.RESOLVED, expected_candidate_id="wf_printer_2231",
        description="Alias 'ticket-2231' matches exact_aliases of exactly one workflow.",
    ))
    f.append(RARFixture(
        id="S3-003", name="Quotation reference number", category="normal_explicit_id",
        turn_text="Approve QT-4471 for procurement.",
        query=RARQuery(
            reference_expression="QT-4471",
            candidates=(
                RARCandidate(id="quot_4471", title="Quotation_Lab_Equipment_Vendor_A.pdf", candidate_type="document", exact_aliases=("QT-4471",)),
                RARCandidate(id="quot_4472", title="Quotation_Lab_Equipment_Vendor_B.pdf", candidate_type="document", exact_aliases=("QT-4472",)),
            ),
        ),
        expected_outcome=RAROutcome.RESOLVED, expected_candidate_id="quot_4471",
        description="Exact quotation number alias match.",
    ))
    f.append(RARFixture(
        id="S3-004", name="Application roll number reference", category="normal_explicit_id",
        turn_text="Pull up application 21BCE0442's status.",
        query=RARQuery(
            reference_expression="21BCE0442",
            candidates=(
                RARCandidate(id="app_21bce0442", title="Hostel_Application_21BCE0442.pdf", candidate_type="document", exact_aliases=("21BCE0442",)),
                RARCandidate(id="app_21bce0501", title="Hostel_Application_21BCE0501.pdf", candidate_type="document", exact_aliases=("21BCE0501",)),
            ),
        ),
        expected_outcome=RAROutcome.RESOLVED, expected_candidate_id="app_21bce0442",
        description="Exact roll number reference.",
    ))
    f.append(RARFixture(
        id="S3-005", name="Direct filename spoken aloud", category="normal_explicit_id",
        turn_text="Send Minutes_MessCommittee_Sept2026.docx to the warden.",
        query=RARQuery(
            reference_expression="Minutes_MessCommittee_Sept2026.docx",
            candidates=(
                RARCandidate(id="doc_min_sept", title="Minutes_MessCommittee_Sept2026.docx", candidate_type="document"),
                RARCandidate(id="doc_min_aug", title="Minutes_MessCommittee_Aug2026.docx", candidate_type="document"),
            ),
        ),
        expected_outcome=RAROutcome.RESOLVED, expected_candidate_id="doc_min_sept",
        description="Verbatim filename spoken by user matches exactly one title.",
    ))

    # --- Active attachment / active UI (5) ---
    f.append(RARFixture(
        id="S3-006", name="Current turn attachment, simple", category="normal_attachment",
        turn_text="Summarize this attachment for me.",
        query=RARQuery(
            reference_expression="this attachment",
            candidates=(
                RARCandidate(id="att_report_1", title="Lab_Safety_Report.pdf", candidate_type="document", is_attachment=True),
                RARCandidate(id="doc_old_report", title="Lab_Safety_Report_2025.pdf", candidate_type="document"),
            ),
            deterministic_anchor=RARDeterministicAnchor(current_attachment_id="att_report_1"),
        ),
        expected_outcome=RAROutcome.RESOLVED, expected_candidate_id="att_report_1",
        description="Current-turn attachment handle is explicit and deterministic.",
    ))
    f.append(RARFixture(
        id="S3-007", name="Selected UI document, foreground", category="normal_active_ui",
        turn_text="Rename this to something clearer.",
        query=RARQuery(
            reference_expression="this",
            candidates=(
                RARCandidate(id="doc_untitled_1", title="Untitled_Draft.docx", candidate_type="document"),
                RARCandidate(id="doc_notice_a", title="Notice_Library_Hours.docx", candidate_type="document"),
            ),
            deterministic_anchor=RARDeterministicAnchor(selected_ui_id="doc_untitled_1"),
        ),
        expected_outcome=RAROutcome.RESOLVED, expected_candidate_id="doc_untitled_1",
        description="Foreground selected UI object binds deterministically.",
    ))
    f.append(RARFixture(
        id="S3-008", name="Attachment with type-qualified phrasing", category="normal_attachment",
        turn_text="Open the PDF I just attached.",
        query=RARQuery(
            reference_expression="the PDF I just attached",
            candidates=(
                RARCandidate(id="att_budget_pdf", title="Budget_Estimate.pdf", candidate_type="document", is_attachment=True),
                RARCandidate(id="doc_budget_old", title="Budget_Estimate_Old.pdf", candidate_type="document"),
            ),
            local_evidence=RAREvidence(target_type_hint="document"),
            deterministic_anchor=RARDeterministicAnchor(current_attachment_id="att_budget_pdf"),
        ),
        expected_outcome=RAROutcome.RESOLVED, expected_candidate_id="att_budget_pdf",
        description="Attachment anchor short-circuits even with descriptive phrasing.",
    ))
    f.append(RARFixture(
        id="S3-009", name="Selected email in inbox view", category="normal_active_ui",
        turn_text="Forward this to the registrar.",
        query=RARQuery(
            reference_expression="this",
            candidates=(
                RARCandidate(id="email_parent_query", title="Parent Query: Fee Due Date", candidate_type="email"),
                RARCandidate(id="email_vendor_quote", title="Vendor Quotation Follow-up", candidate_type="email"),
            ),
            deterministic_anchor=RARDeterministicAnchor(selected_ui_id="email_parent_query"),
        ),
        expected_outcome=RAROutcome.RESOLVED, expected_candidate_id="email_parent_query",
        description="Selected email in the foreground UI resolves deterministically.",
    ))
    f.append(RARFixture(
        id="S3-010", name="Current attachment among several document types", category="normal_attachment",
        turn_text="Compress this file before sending.",
        query=RARQuery(
            reference_expression="this file",
            candidates=(
                RARCandidate(id="att_photos", title="Event_Photos.zip", candidate_type="document", is_attachment=True),
                RARCandidate(id="doc_notice", title="Event_Notice.docx", candidate_type="document"),
                RARCandidate(id="email_invite", title="Event Invitation", candidate_type="email"),
            ),
            deterministic_anchor=RARDeterministicAnchor(current_attachment_id="att_photos"),
        ),
        expected_outcome=RAROutcome.RESOLVED, expected_candidate_id="att_photos",
        description="Attachment anchor wins over other same-turn candidates.",
    ))

    # --- Unique title match (8) ---
    titled = [
        ("S3-011", "the onboarding workflow", "wf_onboard", "New Student Onboarding", "workflow",
         "Send a reminder for the onboarding workflow.", ("wf_leave_approval", "Leave Approval", "workflow")),
        ("S3-012", "the annual report", "doc_annual", "Annual_Report_2026.pdf", "document",
         "Attach the annual report to the email.", ("doc_qtr_report", "Quarterly_Report_Q2_2026.pdf", "document")),
        ("S3-013", "the fee structure notice", "doc_fee_notice", "Notice_Fee_Structure_2026.pdf", "document",
         "Post the fee structure notice on the board.", ("doc_exam_notice", "Notice_Exam_Schedule_2026.pdf", "document")),
        ("S3-014", "the placement drive email", "email_placement", "Placement Drive - TCS", "email",
         "Reply to the placement drive email.", ("email_internship", "Internship Announcement", "email")),
        ("S3-015", "the library renovation minutes", "doc_lib_min", "Minutes_Library_Renovation_Committee.docx", "document",
         "Circulate the library renovation minutes.", ("doc_sports_min", "Minutes_Sports_Committee.docx", "document")),
        ("S3-016", "the scholarship application", "app_scholar", "Scholarship_Application_Form.pdf", "document",
         "Check the scholarship application for completeness.", ("app_hostel", "Hostel_Application_Form.pdf", "document")),
        ("S3-017", "the vendor payment approval", "doc_vendor_pay", "Vendor_Payment_Approval_Aug.pdf", "document",
         "Sign off on the vendor payment approval.", ("doc_staff_pay", "Staff_Salary_Approval_Aug.pdf", "document")),
        ("S3-018", "the convocation workflow", "wf_convocation", "Convocation 2026 Preparation", "workflow",
         "Update the convocation workflow status.", ("wf_orientation", "Orientation Week Preparation", "workflow")),
    ]
    for fid, ref, cid, title, ctype, turn, distractor in titled:
        f.append(RARFixture(
            id=fid, name=f"Unique title match: {ref}", category="normal_unique_title",
            turn_text=turn,
            query=RARQuery(
                reference_expression=ref,
                candidates=(
                    RARCandidate(id=cid, title=title, candidate_type=ctype),
                    RARCandidate(id=distractor[0], title=distractor[1], candidate_type=distractor[2]),
                ),
            ),
            expected_outcome=RAROutcome.RESOLVED, expected_candidate_id=cid,
            description=f"'{ref}' shares discriminating terms with exactly one candidate's title.",
        ))

    # --- Type-qualified single match among mixed-type distractors (10) ---
    type_cases = [
        ("S3-019", "the email", "email", "email_dean_note", "Dean's Note on Timetable", "email",
         [("doc_syllabus", "Syllabus_CS301.pdf", "document"), ("wf_lab_setup", "Lab Setup Workflow", "workflow")]),
        ("S3-020", "the report", "document", "doc_incident", "Incident_Report_Chemistry_Lab.pdf", "document",
         [("email_incident_note", "RE: Chemistry Lab Incident", "email"), ("wf_incident_review", "Incident Review Workflow", "workflow")]),
        ("S3-021", "the workflow", "workflow", "wf_audit", "Annual Safety Audit", "workflow",
         [("doc_audit_checklist", "Safety_Audit_Checklist.pdf", "document"), ("email_audit_note", "Audit Scheduling", "email")]),
        ("S3-022", "the spreadsheet", "spreadsheet", "sheet_attendance", "Attendance_Tracker_Sem5.xlsx", "spreadsheet",
         [("doc_attendance_policy", "Attendance_Policy.pdf", "document"), ("email_attendance_query", "Attendance Query", "email")]),
        ("S3-023", "the minutes", "document", "doc_senate_min", "Minutes_Senate_Meeting_July.docx", "document",
         [("email_senate_invite", "Senate Meeting Invite", "email"), ("wf_senate_followup", "Senate Follow-up Actions", "workflow")]),
        ("S3-024", "the application", "document", "app_leave", "Leave_Application_Prof_Rao.pdf", "document",
         [("wf_leave_review", "Leave Review Workflow", "workflow"), ("email_leave_note", "RE: Leave Request", "email")]),
        ("S3-025", "the approval", "document", "doc_budget_appr", "Budget_Approval_Signed.pdf", "document",
         [("wf_budget_review", "Budget Review Workflow", "workflow"), ("email_budget_note", "Budget Discussion Thread", "email")]),
        ("S3-026", "the notice", "document", "doc_holiday_notice", "Notice_Holiday_List_2026.pdf", "document",
         [("email_holiday_query", "Holiday List Query", "email"), ("wf_holiday_update", "Holiday List Update Workflow", "workflow")]),
        ("S3-027", "the quotation", "document", "quot_furniture", "Quotation_Furniture_Vendor.pdf", "document",
         [("email_furniture_note", "Furniture Vendor Correspondence", "email"), ("wf_furniture_procure", "Furniture Procurement", "workflow")]),
        ("S3-028", "the committee minutes", "document", "doc_disc_min", "Minutes_Disciplinary_Committee.docx", "document",
         [("email_disc_invite", "Disciplinary Committee Invite", "email"), ("wf_disc_case", "Disciplinary Case Workflow", "workflow")]),
    ]
    for fid, ref, thint, cid, title, ctype, distractors in type_cases:
        cands = [RARCandidate(id=cid, title=title, candidate_type=ctype)]
        cands += [RARCandidate(id=d[0], title=d[1], candidate_type=d[2]) for d in distractors]
        f.append(RARFixture(
            id=fid, name=f"Type-qualified single match: {ref}", category="normal_type_qualified",
            turn_text=f"Open {ref} and check it.",
            query=RARQuery(
                reference_expression=ref, candidates=tuple(cands),
                local_evidence=RAREvidence(target_type_hint=thint),
            ),
            expected_outcome=RAROutcome.RESOLVED, expected_candidate_id=cid,
            description=f"Only one candidate matches the '{thint}' type constraint.",
        ))

    # --- Simple temporal (latest/previous) with clean recency_rank (7) ---
    f.append(RARFixture(
        id="S3-029", name="Latest committee minutes", category="normal_temporal",
        turn_text="Use the latest mess committee minutes for the summary.",
        query=RARQuery(
            reference_expression="the latest mess committee minutes",
            candidates=(
                RARCandidate(id="min_sept", title="Minutes_MessCommittee.docx", candidate_type="document", recency_rank=0),
                RARCandidate(id="min_aug", title="Minutes_MessCommittee.docx", candidate_type="document", recency_rank=1),
            ),
            local_evidence=RAREvidence(target_type_hint="document"),
        ),
        expected_outcome=RAROutcome.RESOLVED, expected_candidate_id="min_sept",
        description="'Latest' with clean recency_rank=0 among two identically titled minutes.",
    ))
    f.append(RARFixture(
        id="S3-030", name="Previous approval", category="normal_temporal",
        turn_text="Compare this with the previous approval.",
        query=RARQuery(
            reference_expression="the previous approval",
            candidates=(
                RARCandidate(id="appr_2026", title="Budget_Approval_2026.pdf", candidate_type="document", recency_rank=0),
                RARCandidate(id="appr_2025", title="Budget_Approval_2025.pdf", candidate_type="document", recency_rank=1),
            ),
            local_evidence=RAREvidence(recency_hint="previous", target_type_hint="document"),
        ),
        expected_outcome=RAROutcome.RESOLVED, expected_candidate_id="appr_2025",
        description="'Previous' with recency_rank=1 unambiguous among two ranked approvals.",
    ))
    f.append(RARFixture(
        id="S3-031", name="Previous email in thread", category="normal_temporal",
        turn_text="Reply referencing the previous email.",
        query=RARQuery(
            reference_expression="the previous email",
            candidates=(
                RARCandidate(id="email_latest", title="RE: Hostel Fee Deadline", candidate_type="email", recency_rank=0),
                RARCandidate(id="email_prior", title="Hostel Fee Deadline", candidate_type="email", recency_rank=1),
            ),
            local_evidence=RAREvidence(recency_hint="previous", target_type_hint="email"),
        ),
        expected_outcome=RAROutcome.RESOLVED, expected_candidate_id="email_prior",
        description="Clean two-item recency chain for email thread.",
    ))
    f.append(RARFixture(
        id="S3-032", name="Earlier draft of order", category="normal_temporal",
        turn_text="What did the earlier version of the order say?",
        query=RARQuery(
            reference_expression="the earlier version of the order",
            candidates=(
                RARCandidate(id="ord_v2", title="Office_Order_Timing.pdf", candidate_type="document", recency_rank=0),
                RARCandidate(id="ord_v1", title="Office_Order_Timing_Draft.pdf", candidate_type="document", recency_rank=1),
            ),
            local_evidence=RAREvidence(recency_hint="earlier", target_type_hint="document"),
        ),
        expected_outcome=RAROutcome.RESOLVED, expected_candidate_id="ord_v1",
        description="'Earlier' maps to the single recency_rank>0 candidate.",
    ))
    f.append(RARFixture(
        id="S3-033", name="Latest quotation among three", category="normal_temporal",
        turn_text="Go with the latest quotation from the printer vendor.",
        query=RARQuery(
            reference_expression="the latest quotation",
            candidates=(
                RARCandidate(id="q_sept", title="Quotation_Printer_Vendor.pdf", candidate_type="document", recency_rank=0),
                RARCandidate(id="q_aug", title="Quotation_Printer_Vendor.pdf", candidate_type="document", recency_rank=1),
                RARCandidate(id="q_jul", title="Quotation_Printer_Vendor.pdf", candidate_type="document", recency_rank=2),
            ),
            local_evidence=RAREvidence(target_type_hint="document"),
        ),
        expected_outcome=RAROutcome.RESOLVED, expected_candidate_id="q_sept",
        description="Three-way recency chain, 'latest' unambiguously recency_rank=0.",
    ))
    f.append(RARFixture(
        id="S3-034", name="Previous notice on same topic", category="normal_temporal",
        turn_text="Check what the previous notice on hostel timings said.",
        query=RARQuery(
            reference_expression="the previous notice on hostel timings",
            candidates=(
                RARCandidate(id="notice_new", title="Notice_Hostel_Timings.pdf", candidate_type="document", recency_rank=0),
                RARCandidate(id="notice_old", title="Notice_Hostel_Timings.pdf", candidate_type="document", recency_rank=1),
            ),
            local_evidence=RAREvidence(recency_hint="previous", target_type_hint="document"),
        ),
        expected_outcome=RAROutcome.RESOLVED, expected_candidate_id="notice_old",
        description="Recency-ranked pair, topic phrase matches both equally, rank breaks tie.",
    ))
    f.append(RARFixture(
        id="S3-035", name="Current (not previous) workflow status", category="normal_temporal",
        turn_text="What's the current status of the onboarding workflow?",
        query=RARQuery(
            reference_expression="the current status of the onboarding workflow",
            candidates=(
                RARCandidate(id="wf_onb_now", title="New Student Onboarding", candidate_type="workflow", recency_rank=0),
                RARCandidate(id="wf_onb_last_yr", title="New Student Onboarding 2025", candidate_type="workflow", recency_rank=1),
            ),
            local_evidence=RAREvidence(target_type_hint="workflow"),
        ),
        expected_outcome=RAROutcome.RESOLVED, expected_candidate_id="wf_onb_now",
        description="No relational qualifier beyond 'current' -- type filter plus token overlap resolves to the active one.",
    ))

    # --- Revision (single revised tag) (5) ---
    f.append(RARFixture(
        id="S3-036", name="Revised hostel order", category="normal_revision",
        turn_text="Send out the revised hostel order.",
        query=RARQuery(
            reference_expression="the revised hostel order",
            candidates=(
                RARCandidate(id="ord_hostel_v2", title="Office_Order_Hostel_Revised.pdf", candidate_type="document", domain_tags=("revised",)),
                RARCandidate(id="ord_hostel_v1", title="Office_Order_Hostel.pdf", candidate_type="document"),
            ),
            local_evidence=RAREvidence(recency_hint="revised", target_type_hint="document"),
        ),
        expected_outcome=RAROutcome.RESOLVED, expected_candidate_id="ord_hostel_v2",
        description="Single candidate tagged 'revised'.",
    ))
    f.append(RARFixture(
        id="S3-037", name="Revised budget draft", category="normal_revision",
        turn_text="Use the revised budget draft, not the original.",
        query=RARQuery(
            reference_expression="the revised budget draft",
            candidates=(
                RARCandidate(id="budget_v2", title="Budget_Draft_Revised.xlsx", candidate_type="spreadsheet", domain_tags=("revised",)),
                RARCandidate(id="budget_v1", title="Budget_Draft.xlsx", candidate_type="spreadsheet"),
            ),
            local_evidence=RAREvidence(recency_hint="revised", target_type_hint="spreadsheet",
                                        negation_spans=("the original",)),
        ),
        expected_outcome=RAROutcome.RESOLVED, expected_candidate_id="budget_v2",
        description="Revision tag plus explicit negation of the original both point the same way.",
    ))
    f.append(RARFixture(
        id="S3-038", name="Revised syllabus document", category="normal_revision",
        turn_text="Publish the revised syllabus.",
        query=RARQuery(
            reference_expression="the revised syllabus",
            candidates=(
                RARCandidate(id="syl_v2", title="Syllabus_CS301_Revised.pdf", candidate_type="document", domain_tags=("revised",)),
                RARCandidate(id="syl_v1", title="Syllabus_CS301.pdf", candidate_type="document"),
            ),
            local_evidence=RAREvidence(recency_hint="revised", target_type_hint="document"),
        ),
        expected_outcome=RAROutcome.RESOLVED, expected_candidate_id="syl_v2",
        description="Clean single-revised-tag match.",
    ))
    f.append(RARFixture(
        id="S3-039", name="Original order, not revised", category="normal_revision",
        turn_text="Actually, use the original order text.",
        query=RARQuery(
            reference_expression="the original order",
            candidates=(
                RARCandidate(id="ord_v2b", title="Office_Order_Fee_Revised.pdf", candidate_type="document", domain_tags=("revised",)),
                RARCandidate(id="ord_v1b", title="Office_Order_Fee.pdf", candidate_type="document", domain_tags=("original",)),
            ),
            local_evidence=RAREvidence(target_type_hint="document"),
        ),
        expected_outcome=RAROutcome.RESOLVED, expected_candidate_id="ord_v1b",
        description="'Original' token uniquely present in one candidate's tags/title context.",
    ))
    f.append(RARFixture(
        id="S3-040", name="Revised minutes after correction", category="normal_revision",
        turn_text="Circulate the revised minutes with the corrected attendance count.",
        query=RARQuery(
            reference_expression="the revised minutes",
            candidates=(
                RARCandidate(id="min_v2", title="Minutes_Faculty_Meeting_Revised.docx", candidate_type="document", domain_tags=("revised",)),
                RARCandidate(id="min_v1", title="Minutes_Faculty_Meeting.docx", candidate_type="document"),
            ),
            local_evidence=RAREvidence(recency_hint="revised", target_type_hint="document"),
        ),
        expected_outcome=RAROutcome.RESOLVED, expected_candidate_id="min_v2",
        description="Single revision-tagged candidate.",
    ))

    # --- Conversational continuation / active pointer (5) ---
    f.append(RARFixture(
        id="S3-041", name="Same document continuation", category="normal_continuation",
        turn_text="Make the same document shorter.",
        query=RARQuery(
            reference_expression="the same document",
            candidates=(
                RARCandidate(id="doc_active_memo", title="Memo_Staff_Meeting.docx", candidate_type="document", domain_tags=("recently_discussed",), recency_rank=0),
                RARCandidate(id="doc_other", title="Notice_Parking.docx", candidate_type="document", recency_rank=3),
            ),
            local_evidence=RAREvidence(recency_hint="same"),
        ),
        expected_outcome=RAROutcome.RESOLVED, expected_candidate_id="doc_active_memo",
        description="'Same' binds to the recently-discussed tagged candidate.",
    ))
    f.append(RARFixture(
        id="S3-042", name="Same email, follow-up", category="normal_continuation",
        turn_text="Send the same email to the new coordinator too.",
        query=RARQuery(
            reference_expression="the same email",
            candidates=(
                RARCandidate(id="email_active", title="Orientation Schedule", candidate_type="email", domain_tags=("recently_discussed",), recency_rank=0),
                RARCandidate(id="email_unrelated", title="Library Fine Reminder", candidate_type="email", recency_rank=4),
            ),
            local_evidence=RAREvidence(recency_hint="same"),
        ),
        expected_outcome=RAROutcome.RESOLVED, expected_candidate_id="email_active",
        description="Active-pointer continuation for an email being drafted/sent.",
    ))
    f.append(RARFixture(
        id="S3-043", name="Same workflow, continued action", category="normal_continuation",
        turn_text="Push the same workflow to the next stage.",
        query=RARQuery(
            reference_expression="the same workflow",
            candidates=(
                RARCandidate(id="wf_active", title="Purchase Order Approval", candidate_type="workflow", domain_tags=("recently_discussed",), recency_rank=0),
                RARCandidate(id="wf_idle", title="Annual Fire Drill", candidate_type="workflow", recency_rank=5),
            ),
            local_evidence=RAREvidence(recency_hint="same"),
        ),
        expected_outcome=RAROutcome.RESOLVED, expected_candidate_id="wf_active",
        description="Continuation on the actively-discussed workflow.",
    ))
    f.append(RARFixture(
        id="S3-044", name="Same spreadsheet, add a row", category="normal_continuation",
        turn_text="Add one more row to the same sheet.",
        query=RARQuery(
            reference_expression="the same sheet",
            candidates=(
                RARCandidate(id="sheet_active", title="Inventory_Lab_Equipment.xlsx", candidate_type="spreadsheet", domain_tags=("recently_discussed",), recency_rank=0),
                RARCandidate(id="sheet_idle", title="Attendance_Tracker.xlsx", candidate_type="spreadsheet", recency_rank=6),
            ),
            local_evidence=RAREvidence(recency_hint="same"),
        ),
        expected_outcome=RAROutcome.RESOLVED, expected_candidate_id="sheet_active",
        description="Continuation binding for spreadsheet under active discussion.",
    ))
    f.append(RARFixture(
        id="S3-045", name="Same order, follow-up correction", category="normal_continuation",
        turn_text="Fix the date on the same order.",
        query=RARQuery(
            reference_expression="the same order",
            candidates=(
                RARCandidate(id="ord_active", title="Office_Order_Exam_Duty.pdf", candidate_type="document", domain_tags=("recently_discussed",), recency_rank=0),
                RARCandidate(id="ord_idle", title="Office_Order_Leave_Policy.pdf", candidate_type="document", recency_rank=2),
            ),
            local_evidence=RAREvidence(recency_hint="same"),
        ),
        expected_outcome=RAROutcome.RESOLVED, expected_candidate_id="ord_active",
        description="Active-pointer continuation for an order under discussion.",
    ))

    # --- Straightforward negation / contrast (5) ---
    f.append(RARFixture(
        id="S3-046", name="Don't send the invoice, send the receipt", category="normal_negation",
        turn_text="Don't send the invoice, send the receipt instead.",
        query=RARQuery(
            reference_expression="the receipt",
            candidates=(
                RARCandidate(id="doc_invoice", title="Invoice_Lab_Equipment.pdf", candidate_type="document"),
                RARCandidate(id="doc_receipt", title="Receipt_Lab_Equipment.pdf", candidate_type="document"),
            ),
            local_evidence=RAREvidence(target_type_hint="document", negation_spans=("the invoice",)),
        ),
        expected_outcome=RAROutcome.RESOLVED, expected_candidate_id="doc_receipt",
        description="Explicit contrast: exclude invoice, request receipt -- both are named and distinct.",
    ))
    f.append(RARFixture(
        id="S3-047", name="Not the minutes, the order", category="normal_negation",
        turn_text="Not the minutes, I need the order.",
        query=RARQuery(
            reference_expression="the order",
            candidates=(
                RARCandidate(id="doc_min_x", title="Minutes_Committee.docx", candidate_type="document"),
                RARCandidate(id="doc_ord_x", title="Office_Order_Signed.pdf", candidate_type="document"),
            ),
            local_evidence=RAREvidence(target_type_hint="document", negation_spans=("the minutes",)),
        ),
        expected_outcome=RAROutcome.RESOLVED, expected_candidate_id="doc_ord_x",
        description="Direct exclusion of one type-distinct document, request for the other.",
    ))
    f.append(RARFixture(
        id="S3-048", name="Use the other attachment", category="normal_negation",
        turn_text="Skip the photo, use the other attachment.",
        query=RARQuery(
            reference_expression="the other attachment",
            candidates=(
                RARCandidate(id="att_photo", title="Event_Photo.jpg", candidate_type="document", is_attachment=True),
                RARCandidate(id="att_report", title="Event_Report.pdf", candidate_type="document", is_attachment=True),
            ),
            local_evidence=RAREvidence(negation_spans=("the photo",)),
        ),
        expected_outcome=RAROutcome.RESOLVED, expected_candidate_id="att_report",
        description="'Other' after excluding one leaves exactly one attachment.",
    ))
    f.append(RARFixture(
        id="S3-049", name="Not the draft, the final version", category="normal_negation",
        turn_text="Not the draft, use the final version.",
        query=RARQuery(
            reference_expression="the final version",
            candidates=(
                RARCandidate(id="doc_draft", title="Proposal_Draft.docx", candidate_type="document"),
                RARCandidate(id="doc_final", title="Proposal_Final.docx", candidate_type="document"),
            ),
            local_evidence=RAREvidence(target_type_hint="document", negation_spans=("the draft",)),
        ),
        expected_outcome=RAROutcome.RESOLVED, expected_candidate_id="doc_final",
        description="Draft explicitly excluded, only final remains.",
    ))
    f.append(RARFixture(
        id="S3-050", name="Don't notify the vendor, notify the committee", category="normal_negation",
        turn_text="Don't notify the vendor, notify the committee instead.",
        query=RARQuery(
            reference_expression="the committee",
            candidates=(
                RARCandidate(id="ent_vendor", title="Furniture Vendor", candidate_type="person"),
                RARCandidate(id="ent_committee", title="Purchase Committee", candidate_type="person"),
            ),
            local_evidence=RAREvidence(negation_spans=("the vendor",)),
        ),
        expected_outcome=RAROutcome.RESOLVED, expected_candidate_id="ent_committee",
        description="Explicit entity-level contrast between two distinct named recipients.",
    ))

    # --- Multi-reference turns, both straightforward (5) ---
    f.append(RARFixture(
        id="S3-051A", name="Multi-ref: attachment", category="normal_multi_reference",
        turn_text="Attach this file and send it to the registrar.",
        query=RARQuery(
            reference_expression="this file",
            candidates=(
                RARCandidate(id="att_form", title="Admission_Form.pdf", candidate_type="document", is_attachment=True),
                RARCandidate(id="doc_other_form", title="Old_Admission_Form.pdf", candidate_type="document"),
            ),
            deterministic_anchor=RARDeterministicAnchor(current_attachment_id="att_form"),
        ),
        expected_outcome=RAROutcome.RESOLVED, expected_candidate_id="att_form",
        description="First reference of a two-reference turn: current attachment.",
    ))
    f.append(RARFixture(
        id="S3-051B", name="Multi-ref: recipient", category="normal_multi_reference",
        turn_text="Attach this file and send it to the registrar.",
        query=RARQuery(
            reference_expression="the registrar",
            candidates=(
                RARCandidate(id="ent_registrar", title="Registrar Office", candidate_type="person"),
                RARCandidate(id="ent_warden", title="Warden", candidate_type="person"),
            ),
        ),
        expected_outcome=RAROutcome.RESOLVED, expected_candidate_id="ent_registrar",
        description="Second reference of the same turn: unique title match for recipient.",
    ))
    f.append(RARFixture(
        id="S3-052A", name="Multi-ref: document", category="normal_multi_reference",
        turn_text="Compare this order with the previous one.",
        query=RARQuery(
            reference_expression="this order",
            candidates=(
                RARCandidate(id="ord_curr", title="Office_Order_Mess_Timing.pdf", candidate_type="document", recency_rank=0),
                RARCandidate(id="ord_prev", title="Office_Order_Mess_Timing.pdf", candidate_type="document", recency_rank=1),
            ),
            deterministic_anchor=RARDeterministicAnchor(selected_ui_id="ord_curr"),
        ),
        expected_outcome=RAROutcome.RESOLVED, expected_candidate_id="ord_curr",
        description="First reference: current foreground order.",
    ))
    f.append(RARFixture(
        id="S3-052B", name="Multi-ref: previous version", category="normal_multi_reference",
        turn_text="Compare this order with the previous one.",
        query=RARQuery(
            reference_expression="the previous one",
            candidates=(
                RARCandidate(id="ord_curr2", title="Office_Order_Mess_Timing.pdf", candidate_type="document", recency_rank=0),
                RARCandidate(id="ord_prev2", title="Office_Order_Mess_Timing.pdf", candidate_type="document", recency_rank=1),
            ),
            local_evidence=RAREvidence(recency_hint="previous", target_type_hint="document"),
        ),
        expected_outcome=RAROutcome.RESOLVED, expected_candidate_id="ord_prev2",
        description="Second reference: previous-ranked candidate.",
    ))
    f.append(RARFixture(
        id="S3-053A", name="Multi-ref: person", category="normal_multi_reference",
        turn_text="Ask the lab officer to check the equipment log.",
        query=RARQuery(
            reference_expression="the lab officer",
            candidates=(
                RARCandidate(id="person_lab_officer", title="Lab Officer - Rajesh Kumar", candidate_type="person"),
                RARCandidate(id="person_hostel_warden", title="Hostel Warden", candidate_type="person"),
            ),
        ),
        expected_outcome=RAROutcome.RESOLVED, expected_candidate_id="person_lab_officer",
        description="First reference of a person+document multi-reference turn.",
    ))
    f.append(RARFixture(
        id="S3-053B", name="Multi-ref: document", category="normal_multi_reference",
        turn_text="Ask the lab officer to check the equipment log.",
        query=RARQuery(
            reference_expression="the equipment log",
            candidates=(
                RARCandidate(id="sheet_equip_log", title="Equipment_Log_Chemistry.xlsx", candidate_type="spreadsheet"),
                RARCandidate(id="sheet_attendance2", title="Attendance_Log.xlsx", candidate_type="spreadsheet"),
            ),
        ),
        expected_outcome=RAROutcome.RESOLVED, expected_candidate_id="sheet_equip_log",
        description="Second reference: unique title-term match for the document.",
    ))

    # --- More unique-title / type-qualified normal cases to round out ~70 (17) ---
    more_normal = [
        ("S3-054", "the parent complaint email", "email", "email_parent_complaint", "Parent Complaint - Mess Food Quality", "email"),
        ("S3-055", "the fire safety report", "document", "doc_fire_safety", "Fire_Safety_Inspection_Report.pdf", "document"),
        ("S3-056", "the alumni newsletter", "document", "doc_alumni_news", "Alumni_Newsletter_Q3.pdf", "document"),
        ("S3-057", "the internship offer email", "email", "email_intern_offer", "Internship Offer - Summer 2026", "email"),
        ("S3-058", "the maintenance workflow", "workflow", "wf_maintenance", "Hostel Block B Maintenance", "workflow"),
        ("S3-059", "the exam duty roster", "document", "doc_exam_roster", "Exam_Duty_Roster_Nov2026.xlsx", "spreadsheet"),
        ("S3-060", "the sports committee report", "document", "doc_sports_report", "Sports_Committee_Annual_Report.pdf", "document"),
        ("S3-061", "the canteen tender notice", "document", "doc_canteen_tender", "Notice_Canteen_Tender_2026.pdf", "document"),
        ("S3-062", "the research grant application", "document", "app_grant", "Research_Grant_Application_DrSharma.pdf", "document"),
        ("S3-063", "the disciplinary case email", "email", "email_disc_case", "Disciplinary Case - Student ID 4471", "email"),
        ("S3-064", "the water supply complaint", "email", "email_water_complaint", "Water Supply Issue - Block D", "email"),
        ("S3-065", "the guest lecture invite", "document", "doc_guest_invite", "Guest_Lecture_Invitation_Letter.pdf", "document"),
        ("S3-066", "the elevator repair quotation", "document", "quot_elevator", "Quotation_Elevator_Repair.pdf", "document"),
        ("S3-067", "the convocation budget sheet", "spreadsheet", "sheet_conv_budget", "Convocation_Budget_2026.xlsx", "spreadsheet"),
        ("S3-068", "the hostel curfew notice", "document", "doc_curfew_notice", "Notice_Hostel_Curfew_Update.pdf", "document"),
        ("S3-069", "the syllabus revision workflow", "workflow", "wf_syllabus_rev", "Syllabus Revision - CS Dept", "workflow"),
        ("S3-070", "the placement statistics report", "document", "doc_placement_stats", "Placement_Statistics_2026.pdf", "document"),
    ]
    for fid, ref, thint, cid, title, ctype in more_normal:
        distractor_type = "email" if ctype != "email" else "document"
        f.append(RARFixture(
            id=fid, name=f"Realistic single-match: {ref}", category="normal_type_qualified",
            turn_text=f"Pull up {ref}.",
            query=RARQuery(
                reference_expression=ref,
                candidates=(
                    RARCandidate(id=cid, title=title, candidate_type=ctype),
                    RARCandidate(id=f"{cid}_distractor", title="Weekly Cafeteria Menu", candidate_type=distractor_type),
                ),
                local_evidence=RAREvidence(target_type_hint=thint),
            ),
            expected_outcome=RAROutcome.RESOLVED, expected_candidate_id=cid,
            description=f"Realistic single-candidate match for '{ref}' against an unrelated distractor.",
        ))

    # =====================================================================
    # NATURALLY DIFFICULT REFERENCES (S3-071 .. S3-090)
    # =====================================================================

    f.append(RARFixture(
        id="S3-071", name="Two similarly named budget documents", category="difficult_lexical_overlap",
        turn_text="Open the budget document for the science block.",
        query=RARQuery(
            reference_expression="the budget document for the science block",
            candidates=(
                RARCandidate(id="budget_science", title="Budget_Science_Block_Renovation.xlsx", candidate_type="spreadsheet"),
                RARCandidate(id="budget_arts", title="Budget_Arts_Block_Renovation.xlsx", candidate_type="spreadsheet"),
            ),
            local_evidence=RAREvidence(target_type_hint="spreadsheet"),
        ),
        expected_outcome=RAROutcome.RESOLVED, expected_candidate_id="budget_science",
        description="'Science block' is the discriminating term against a near-identical 'Arts block' sibling.",
    ))
    f.append(RARFixture(
        id="S3-072", name="Multiple emails from same sender, different topics", category="difficult_sender_overlap",
        turn_text="Reply to the warden's email about the mess timing change.",
        query=RARQuery(
            reference_expression="the warden's email about the mess timing change",
            candidates=(
                RARCandidate(id="email_warden_mess", title="Mess Timing Change - Warden", candidate_type="email", owner="warden"),
                RARCandidate(id="email_warden_curfew", title="Curfew Update - Warden", candidate_type="email", owner="warden"),
            ),
            local_evidence=RAREvidence(target_type_hint="email"),
        ),
        expected_outcome=RAROutcome.RESOLVED, expected_candidate_id="email_warden_mess",
        description="Same sender on both; 'mess timing' is the only discriminating topic term.",
    ))
    f.append(RARFixture(
        id="S3-073", name="Revised vs original with generic overlap", category="difficult_revision_overlap",
        turn_text="I need the revised copy, the numbers changed since the first one.",
        query=RARQuery(
            reference_expression="the revised copy",
            candidates=(
                RARCandidate(id="proj_v2c", title="Project_Estimate_Revised.pdf", candidate_type="document", domain_tags=("revised",)),
                RARCandidate(id="proj_v1c", title="Project_Estimate.pdf", candidate_type="document"),
            ),
            local_evidence=RAREvidence(recency_hint="revised", target_type_hint="document"),
        ),
        expected_outcome=RAROutcome.RESOLVED, expected_candidate_id="proj_v2c",
        description="Revision tag present but wrapped in oblique phrasing ('the numbers changed') rather than a clean 'revised X' template.",
    ))
    f.append(RARFixture(
        id="S3-074", name="Two attachments in one turn, pick by format", category="difficult_multi_attachment",
        turn_text="Use the spreadsheet one, not the PDF.",
        query=RARQuery(
            reference_expression="the spreadsheet one",
            candidates=(
                RARCandidate(id="att_sheet_x", title="Cost_Breakdown.xlsx", candidate_type="spreadsheet", is_attachment=True),
                RARCandidate(id="att_pdf_x", title="Cost_Breakdown.pdf", candidate_type="document", is_attachment=True),
            ),
            local_evidence=RAREvidence(target_type_hint="spreadsheet", negation_spans=("the pdf",)),
        ),
        expected_outcome=RAROutcome.RESOLVED, expected_candidate_id="att_sheet_x",
        description="Two same-turn attachments of the same underlying content, different formats; type hint and negation agree.",
    ))
    f.append(RARFixture(
        id="S3-075", name="Stale conversational pointer", category="difficult_stale_pointer",
        turn_text="Now open the fee notice instead.",
        query=RARQuery(
            reference_expression="the fee notice",
            candidates=(
                RARCandidate(id="doc_memo_stale", title="Memo_Staff_Meeting.docx", candidate_type="document", domain_tags=("recently_discussed",), recency_rank=0),
                RARCandidate(id="doc_fee_notice2", title="Notice_Fee_Structure.pdf", candidate_type="document", recency_rank=1),
            ),
            local_evidence=RAREvidence(target_type_hint="document"),
        ),
        expected_outcome=RAROutcome.RESOLVED, expected_candidate_id="doc_fee_notice2",
        description="User explicitly pivots away from the stale active pointer ('instead'); the named, type-matching, term-matching document must win over the stale 'recently_discussed' tag.",
    ))
    f.append(RARFixture(
        id="S3-076", name="Ownership reference without explicit owner rule", category="difficult_ownership",
        turn_text="Check his application again, the one from last week.",
        query=RARQuery(
            reference_expression="his application",
            candidates=(
                RARCandidate(id="app_amit", title="Hostel_Application_Amit_Verma.pdf", candidate_type="document", owner="Amit Verma"),
                RARCandidate(id="app_sneha", title="Hostel_Application_Sneha_Rao.pdf", candidate_type="document", owner="Sneha Rao"),
            ),
            local_evidence=RAREvidence(target_type_hint="document"),
        ),
        expected_outcome=RAROutcome.AMBIGUOUS,
        expected_ambiguous_candidate_ids=("app_amit", "app_sneha"),
        description="'His' narrows by gender in principle, but the candidate set carries no gender/pronoun-owner field the deterministic stack can use -- both remain type-matched with no discriminating token overlap ('application' is generic); safe abstention is correct since the reference cannot be uniquely bound from supplied metadata alone.",
    ))
    f.append(RARFixture(
        id="S3-077", name="Generic institutional term overlap: approval", category="difficult_generic_terms",
        turn_text="Get the approval signed today.",
        query=RARQuery(
            reference_expression="the approval",
            candidates=(
                RARCandidate(id="appr_travel", title="Travel_Approval_Conference.pdf", candidate_type="document"),
                RARCandidate(id="appr_purchase", title="Purchase_Approval_Lab_Chemicals.pdf", candidate_type="document"),
            ),
            local_evidence=RAREvidence(target_type_hint="document"),
        ),
        expected_outcome=RAROutcome.AMBIGUOUS,
        expected_ambiguous_candidate_ids=("appr_travel", "appr_purchase"),
        description="'The approval' alone is too generic (both share the discriminating word 'approval' itself as their only overlap); no other cue distinguishes them -- safe abstention is correct.",
    ))
    f.append(RARFixture(
        id="S3-078", name="Same subject across document types", category="difficult_cross_type_subject",
        turn_text="Send over the hostel fee thing.",
        query=RARQuery(
            reference_expression="the hostel fee thing",
            candidates=(
                RARCandidate(id="doc_fee_notice3", title="Notice_Hostel_Fee_Revision.pdf", candidate_type="document"),
                RARCandidate(id="sheet_fee_calc", title="Hostel_Fee_Calculation.xlsx", candidate_type="spreadsheet"),
            ),
        ),
        expected_outcome=RAROutcome.AMBIGUOUS,
        expected_ambiguous_candidate_ids=("doc_fee_notice3", "sheet_fee_calc"),
        description="No type hint supplied ('thing' is not type-discriminating), both candidates share the 'hostel fee' subject equally -- genuinely ambiguous without more.",
    ))
    f.append(RARFixture(
        id="S3-079", name="Contrast leaving two remaining candidates", category="difficult_contrast_residual",
        turn_text="Not the July minutes -- one of the more recent ones.",
        query=RARQuery(
            reference_expression="one of the more recent ones",
            candidates=(
                RARCandidate(id="min_july", title="Minutes_Committee_July.docx", candidate_type="document", recency_rank=2),
                RARCandidate(id="min_aug2", title="Minutes_Committee_August.docx", candidate_type="document", recency_rank=1),
                RARCandidate(id="min_sept2", title="Minutes_Committee_September.docx", candidate_type="document", recency_rank=0),
            ),
            local_evidence=RAREvidence(target_type_hint="document", negation_spans=("the july minutes",)),
        ),
        expected_outcome=RAROutcome.AMBIGUOUS,
        expected_ambiguous_candidate_ids=("min_aug2", "min_sept2"),
        description="Excluding July leaves two plausible 'more recent' candidates; the phrase does not name a single one, so exclusion narrows but does not uniquely resolve -- correct behavior is AMBIGUOUS over the remaining two, not a guess.",
    ))
    f.append(RARFixture(
        id="S3-080", name="Two quotations, same vendor type, different amount", category="difficult_lexical_overlap",
        turn_text="Go with the quotation that includes installation.",
        query=RARQuery(
            reference_expression="the quotation that includes installation",
            candidates=(
                RARCandidate(id="quot_with_install", title="Quotation_AC_With_Installation.pdf", candidate_type="document"),
                RARCandidate(id="quot_without_install", title="Quotation_AC_Unit_Only.pdf", candidate_type="document"),
            ),
            local_evidence=RAREvidence(target_type_hint="document"),
        ),
        expected_outcome=RAROutcome.RESOLVED, expected_candidate_id="quot_with_install",
        description="'Installation' is the discriminating term present in exactly one title.",
    ))
    f.append(RARFixture(
        id="S3-081", name="Multi-reference turn, one easy one hard", category="difficult_multi_reference",
        turn_text="Forward this to accounts and also send them the other invoice.",
        query=RARQuery(
            reference_expression="the other invoice",
            candidates=(
                RARCandidate(id="inv_a", title="Invoice_Catering_Sept.pdf", candidate_type="document"),
                RARCandidate(id="inv_b", title="Invoice_Catering_Aug.pdf", candidate_type="document"),
            ),
            local_evidence=RAREvidence(target_type_hint="document"),
        ),
        expected_outcome=RAROutcome.AMBIGUOUS,
        expected_ambiguous_candidate_ids=("inv_a", "inv_b"),
        description="'The other' presupposes a specific first invoice was just discussed, but no active pointer/current-attachment anchor is present in this query's evidence to establish which one 'the other' excludes -- correct behavior is abstention, not a guess between the two.",
    ))
    f.append(RARFixture(
        id="S3-082", name="Ownership overlap, role vs name", category="difficult_ownership",
        turn_text="Forward the warden's approval to accounts.",
        query=RARQuery(
            reference_expression="the warden's approval",
            candidates=(
                RARCandidate(id="appr_warden_mess2", title="Mess_Budget_Approval.pdf", candidate_type="document", owner="warden"),
                RARCandidate(id="appr_warden_hostel2", title="Hostel_Repair_Approval.pdf", candidate_type="document", owner="warden"),
            ),
            local_evidence=RAREvidence(target_type_hint="document"),
        ),
        expected_outcome=RAROutcome.AMBIGUOUS,
        expected_ambiguous_candidate_ids=("appr_warden_mess2", "appr_warden_hostel2"),
        description="Both approvals share the same owner; 'the warden's approval' alone does not distinguish which subject -- and the deterministic stack has no owner-matching rule to even attempt narrowing by owner. Safe abstention.",
    ))
    f.append(RARFixture(
        id="S3-083", name="Similar report titles, different years", category="difficult_lexical_overlap",
        turn_text="Pull the NAAC report we're using for this cycle.",
        query=RARQuery(
            reference_expression="the NAAC report we're using for this cycle",
            candidates=(
                RARCandidate(id="naac_2026", title="NAAC_Self_Study_Report_2026.pdf", candidate_type="document", recency_rank=0),
                RARCandidate(id="naac_2021", title="NAAC_Self_Study_Report_2021.pdf", candidate_type="document", recency_rank=1),
            ),
            local_evidence=RAREvidence(target_type_hint="document"),
        ),
        expected_outcome=RAROutcome.RESOLVED, expected_candidate_id="naac_2026",
        description="'This cycle' has no explicit temporal rule mapping, but token overlap plus recency both favor the 2026 report; margin should clear the discrimination threshold.",
    ))
    f.append(RARFixture(
        id="S3-084", name="Document + its attached counterpart", category="difficult_email_attachment_relation",
        turn_text="Open the PDF attached to that email.",
        query=RARQuery(
            reference_expression="the PDF attached to that email",
            candidates=(
                RARCandidate(id="att_minutes_pdf", title="Minutes_Signed.pdf", candidate_type="document", is_attachment=True),
                RARCandidate(id="doc_minutes_draft", title="Minutes_Draft.docx", candidate_type="document"),
            ),
            local_evidence=RAREvidence(target_type_hint="document"),
        ),
        expected_outcome=RAROutcome.RESOLVED, expected_candidate_id="att_minutes_pdf",
        description="Only one candidate is actually an attachment; 'attached to that email' phrase should favor it even without an explicit parent-email link field.",
    ))
    f.append(RARFixture(
        id="S3-085", name="Two students, same submission type", category="difficult_lexical_overlap",
        turn_text="Check the project report submitted by the mechanical engineering group.",
        query=RARQuery(
            reference_expression="the project report submitted by the mechanical engineering group",
            candidates=(
                RARCandidate(id="proj_mech", title="Project_Report_Mechanical_Group3.pdf", candidate_type="document"),
                RARCandidate(id="proj_civil", title="Project_Report_Civil_Group1.pdf", candidate_type="document"),
            ),
            local_evidence=RAREvidence(target_type_hint="document"),
        ),
        expected_outcome=RAROutcome.RESOLVED, expected_candidate_id="proj_mech",
        description="'Mechanical' is the discriminating department term against a civil-engineering sibling.",
    ))
    f.append(RARFixture(
        id="S3-086", name="Negation leaves ambiguous residual, not unique", category="difficult_contrast_residual",
        turn_text="Not the printed notice, use one of the digital ones.",
        query=RARQuery(
            reference_expression="one of the digital ones",
            candidates=(
                RARCandidate(id="notice_email_ver", title="Notice_Holiday.docx", candidate_type="document", domain_tags=("digital",)),
                RARCandidate(id="notice_pdf_ver", title="Notice_Holiday_Scan.pdf", candidate_type="document", domain_tags=("digital", "scanned")),
                RARCandidate(id="notice_print_ver", title="Notice_Holiday_Print.pdf", candidate_type="document", domain_tags=("printed",)),
            ),
            local_evidence=RAREvidence(target_type_hint="document", negation_spans=("the printed notice",)),
        ),
        expected_outcome=RAROutcome.AMBIGUOUS,
        expected_ambiguous_candidate_ids=("notice_email_ver", "notice_pdf_ver"),
        description="Excluding the printed one leaves two digital-tagged candidates; 'one of' explicitly signals the user hasn't picked a specific one -- AMBIGUOUS is the honest outcome.",
    ))
    f.append(RARFixture(
        id="S3-087", name="Revised minutes vs revised order, shared 'revised'", category="difficult_generic_terms",
        turn_text="I need the revised one from this morning's meeting.",
        query=RARQuery(
            reference_expression="the revised one from this morning's meeting",
            candidates=(
                RARCandidate(id="min_revised_am", title="Minutes_Faculty_Council_Revised.docx", candidate_type="document", domain_tags=("revised",)),
                RARCandidate(id="ord_revised_am", title="Office_Order_Timing_Revised.pdf", candidate_type="document", domain_tags=("revised",)),
            ),
        ),
        expected_outcome=RAROutcome.AMBIGUOUS,
        expected_ambiguous_candidate_ids=("min_revised_am", "ord_revised_am"),
        description="Both candidates are equally 'revised' and equally tied to a meeting context; no type hint or further discriminating term is supplied -- genuinely ambiguous.",
    ))
    f.append(RARFixture(
        id="S3-088", name="Two candidates, one clearly named entity wins", category="difficult_lexical_overlap",
        turn_text="Draft a reply to the query about the physics lab equipment delay.",
        query=RARQuery(
            reference_expression="the query about the physics lab equipment delay",
            candidates=(
                RARCandidate(id="email_physics_delay", title="Query: Physics Lab Equipment Delay", candidate_type="email"),
                RARCandidate(id="email_chem_delay", title="Query: Chemistry Lab Equipment Delay", candidate_type="email"),
            ),
            local_evidence=RAREvidence(target_type_hint="email"),
        ),
        expected_outcome=RAROutcome.RESOLVED, expected_candidate_id="email_physics_delay",
        description="'Physics' is the discriminating department term.",
    ))
    f.append(RARFixture(
        id="S3-089", name="Active context changed mid-conversation", category="difficult_stale_pointer",
        turn_text="Actually, forget that -- open the maintenance request form instead.",
        query=RARQuery(
            reference_expression="the maintenance request form",
            candidates=(
                RARCandidate(id="doc_stale_active", title="Leave_Application_Form.pdf", candidate_type="document", domain_tags=("recently_discussed",), recency_rank=0),
                RARCandidate(id="doc_maint_form", title="Maintenance_Request_Form.pdf", candidate_type="document", recency_rank=1),
            ),
            local_evidence=RAREvidence(target_type_hint="document"),
        ),
        expected_outcome=RAROutcome.RESOLVED, expected_candidate_id="doc_maint_form",
        description="Explicit pivot away from the stale active item; named target with clear token overlap must win over the stale pointer tag.",
    ))
    f.append(RARFixture(
        id="S3-090", name="Ownership plus role overlap between two staff", category="difficult_ownership",
        turn_text="Forward the coordinator's report, not the assistant coordinator's.",
        query=RARQuery(
            reference_expression="the coordinator's report",
            candidates=(
                RARCandidate(id="doc_coord_report", title="Placement_Report_Coordinator.pdf", candidate_type="document", owner="coordinator"),
                RARCandidate(id="doc_asst_coord_report", title="Placement_Report_Assistant_Coordinator.pdf", candidate_type="document", owner="assistant_coordinator"),
            ),
            local_evidence=RAREvidence(target_type_hint="document", negation_spans=("the assistant coordinator's",)),
        ),
        expected_outcome=RAROutcome.RESOLVED, expected_candidate_id="doc_coord_report",
        description="Explicit negation of the assistant coordinator's version, combined with 'coordinator' as a discriminating title token, resolves it -- despite no dedicated owner-matching rule, lexical overlap plus contrast filtering happen to carry this one.",
    ))

    # =====================================================================
    # LEGITIMATELY UNRESOLVABLE / AMBIGUOUS (S3-091 .. S3-100)
    # =====================================================================

    f.append(RARFixture(
        id="S3-091", name="Two equally plausible budget spreadsheets", category="unresolvable_equal_candidates",
        turn_text="Open the budget spreadsheet.",
        query=RARQuery(
            reference_expression="the budget spreadsheet",
            candidates=(
                RARCandidate(id="budget_q1_x", title="Budget_Q1_2026.xlsx", candidate_type="spreadsheet"),
                RARCandidate(id="budget_q2_x", title="Budget_Q2_2026.xlsx", candidate_type="spreadsheet"),
            ),
            local_evidence=RAREvidence(target_type_hint="spreadsheet"),
        ),
        expected_outcome=RAROutcome.AMBIGUOUS,
        expected_ambiguous_candidate_ids=("budget_q1_x", "budget_q2_x"),
        description="No quarter specified; both candidates equally plausible under 'the budget spreadsheet'.",
    ))
    f.append(RARFixture(
        id="S3-092", name="Missing temporal metadata for 'previous'", category="unresolvable_missing_metadata",
        turn_text="Use the previous version of the notice.",
        query=RARQuery(
            reference_expression="the previous version of the notice",
            candidates=(
                RARCandidate(id="notice_no_rank_a", title="Notice_Exam_Hall.pdf", candidate_type="document"),
                RARCandidate(id="notice_no_rank_b", title="Notice_Exam_Hall.pdf", candidate_type="document"),
            ),
            local_evidence=RAREvidence(recency_hint="previous", target_type_hint="document"),
        ),
        expected_outcome=RAROutcome.AMBIGUOUS,
        expected_ambiguous_candidate_ids=("notice_no_rank_a", "notice_no_rank_b"),
        description="Both candidates share recency_rank=0 (default) -- the ordering metadata 'previous' requires is simply absent, so the reference cannot be resolved; safe abstention.",
    ))
    f.append(RARFixture(
        id="S3-093", name="Reference to object absent from candidate set", category="unresolvable_no_candidate",
        turn_text="Pull up the NBA accreditation report.",
        query=RARQuery(
            reference_expression="the NBA accreditation report",
            candidates=(
                RARCandidate(id="naac_report_x", title="NAAC_Self_Study_Report.pdf", candidate_type="document"),
                RARCandidate(id="iso_report_x", title="ISO_Certification_Report.pdf", candidate_type="document"),
            ),
            local_evidence=RAREvidence(target_type_hint="document"),
        ),
        expected_outcome=RAROutcome.UNKNOWN,
        description="User asks for a specific report type (NBA) that simply is not in the candidate pool -- correct behavior is UNKNOWN, not a guess at a similarly-typed sibling.",
    ))
    f.append(RARFixture(
        id="S3-094", name="Ownership cannot distinguish, same role", category="unresolvable_ownership",
        turn_text="Check her application status.",
        query=RARQuery(
            reference_expression="her application",
            candidates=(
                RARCandidate(id="app_priya", title="Scholarship_Application_2026.pdf", candidate_type="document", owner="Priya Nair"),
                RARCandidate(id="app_divya", title="Scholarship_Application_2026.pdf", candidate_type="document", owner="Divya Shah"),
            ),
            local_evidence=RAREvidence(target_type_hint="document"),
        ),
        expected_outcome=RAROutcome.AMBIGUOUS,
        expected_ambiguous_candidate_ids=("app_priya", "app_divya"),
        description="'Her' narrows by gender in principle but not by which specific person; identical titles give zero discriminating terms -- safe abstention.",
    ))
    f.append(RARFixture(
        id="S3-095", name="Pronoun with multiple plausible antecedents, no anchor", category="unresolvable_pronoun",
        turn_text="Send it to the committee.",
        query=RARQuery(
            reference_expression="it",
            candidates=(
                RARCandidate(id="doc_agenda_x", title="Meeting_Agenda.docx", candidate_type="document"),
                RARCandidate(id="doc_minutes_x2", title="Meeting_Minutes.docx", candidate_type="document"),
            ),
        ),
        expected_outcome=RAROutcome.AMBIGUOUS,
        expected_ambiguous_candidate_ids=("doc_agenda_x", "doc_minutes_x2"),
        description="Bare pronoun 'it' with two plausible antecedents and no active pointer, current attachment, or selected UI anchor -- must abstain rather than pick one.",
    ))
    f.append(RARFixture(
        id="S3-096", name="Insufficient context to determine which document", category="unresolvable_no_candidate",
        turn_text="Check the numbers in the report again.",
        query=RARQuery(
            reference_expression="the report",
            candidates=(
                RARCandidate(id="rep_finance", title="Finance_Report_Sept.pdf", candidate_type="document"),
                RARCandidate(id="rep_academic", title="Academic_Performance_Report_Sept.pdf", candidate_type="document"),
                RARCandidate(id="rep_infra", title="Infrastructure_Status_Report_Sept.pdf", candidate_type="document"),
            ),
            local_evidence=RAREvidence(target_type_hint="document"),
        ),
        expected_outcome=RAROutcome.AMBIGUOUS,
        expected_ambiguous_candidate_ids=("rep_finance", "rep_academic", "rep_infra"),
        description="Three equally-plausible reports, no discriminating subject term in the bare phrase 'the report' -- genuine ambiguity across three, not two.",
    ))
    f.append(RARFixture(
        id="S3-097", name="Type hint present but no matching type exists", category="unresolvable_no_candidate",
        turn_text="Forward me the recording of today's meeting.",
        query=RARQuery(
            reference_expression="the recording of today's meeting",
            candidates=(
                RARCandidate(id="doc_meeting_notes", title="Meeting_Notes_Today.docx", candidate_type="document"),
                RARCandidate(id="email_meeting_invite2", title="Meeting Invite - Today", candidate_type="email"),
            ),
            local_evidence=RAREvidence(target_type_hint="media"),
        ),
        expected_outcome=RAROutcome.UNKNOWN,
        description="User asks for a media recording; no candidate of type 'media' exists in the pool -- correct behavior is UNKNOWN, not substituting the notes or the invite.",
    ))
    f.append(RARFixture(
        id="S3-098", name="Two candidates, contrast phrase names neither uniquely", category="unresolvable_contrast",
        turn_text="Not that one, the other version.",
        query=RARQuery(
            reference_expression="the other version",
            candidates=(
                RARCandidate(id="draft_v1_x", title="Notice_Draft.docx", candidate_type="document"),
                RARCandidate(id="draft_v2_x", title="Notice_Draft.docx", candidate_type="document"),
                RARCandidate(id="draft_v3_x", title="Notice_Draft.docx", candidate_type="document"),
            ),
            local_evidence=RAREvidence(target_type_hint="document"),
        ),
        expected_outcome=RAROutcome.AMBIGUOUS,
        expected_ambiguous_candidate_ids=("draft_v1_x", "draft_v2_x", "draft_v3_x"),
        description="'Not that one' does not identify which of the three was rejected (no negation_spans content ties to a specific candidate), so all three remain plausible -- honest ambiguity, not a guess.",
    ))
    f.append(RARFixture(
        id="S3-099", name="Warranty card requested, only adjacent documents exist", category="unresolvable_no_candidate",
        turn_text="Check the warranty card for the spectrometer.",
        query=RARQuery(
            reference_expression="the warranty card",
            candidates=(
                RARCandidate(id="doc_inv2", title="Tax_Invoice_Spectrometer.pdf", candidate_type="document", domain_tags=("invoice",)),
                RARCandidate(id="doc_challan2", title="Delivery_Challan_Spectrometer.pdf", candidate_type="document", domain_tags=("delivery",)),
            ),
            local_evidence=RAREvidence(target_type_hint="document"),
        ),
        expected_outcome=RAROutcome.UNKNOWN,
        description="Warranty card is genuinely absent from the candidate pool; adjacent-but-different documents (invoice, challan) must not be substituted.",
    ))
    f.append(RARFixture(
        id="S3-100", name="Non-existent order number", category="unresolvable_no_candidate",
        turn_text="Review Office Order number 9921.",
        query=RARQuery(
            reference_expression="Office Order number 9921",
            candidates=(
                RARCandidate(id="ord_401x", title="Office_Order_401.pdf", candidate_type="document", exact_aliases=("order-401",)),
                RARCandidate(id="ord_402x", title="Office_Order_402.pdf", candidate_type="document", exact_aliases=("order-402",)),
            ),
            local_evidence=RAREvidence(target_type_hint="document"),
        ),
        expected_outcome=RAROutcome.UNKNOWN,
        description="Order 9921 does not exist among the two candidates present; must abstain rather than pick the nearest-numbered one.",
    ))

    return tuple(f)


def get_rar_stage3_order_perturbation_pairs() -> Tuple[Tuple[str, RARQuery], ...]:
    """Reordered-candidate variants of a subset of RESOLVED Stage 3 fixtures.

    Reported separately from the main 100-case tranche (order-robustness is
    measured, not counted as additional independent semantic cases). Each
    entry is (original_fixture_id, reordered_query) where reordered_query
    is identical to the original except candidates is reversed/shuffled.
    """
    base = {fx.id: fx for fx in get_rar_stage3_fixtures()}
    pairs: List[Tuple[str, RARQuery]] = []
    perturb_ids = [
        "S3-001", "S3-011", "S3-019", "S3-029", "S3-036", "S3-041",
        "S3-046", "S3-051A", "S3-054", "S3-071", "S3-080", "S3-088",
    ]
    for fid in perturb_ids:
        fx = base[fid]
        reversed_candidates = tuple(reversed(fx.query.candidates))
        pairs.append((
            fid,
            RARQuery(
                reference_expression=fx.query.reference_expression,
                candidates=reversed_candidates,
                local_evidence=fx.query.local_evidence,
                deterministic_anchor=fx.query.deterministic_anchor,
            ),
        ))
    return tuple(pairs)
