"""M35 Batch A2.5 Stage 4B — Independent Realistic Blind Deterministic RAR Challenge Benchmark.

Constructed independently in Stage 4B-A per the batch specification.
Total cases: 136 independently authored reference binding situations.

Domain Distribution:
- Office / Institutional: 81 cases (59.6%)
- General Work / Productivity: 25 cases (18.4%)
- Personal Assistant / Everyday: 20 cases (14.7%)
- Cross-Domain / Mixed Context: 10 cases (7.4%)

Ground-Truth Outcome Distribution:
- RESOLVED: 98 cases (72.1%)
- AMBIGUOUS: 24 cases (17.6%)
- UNKNOWN: 14 cases (10.3%)

Authoring Discipline:
- Phase A: All realistic candidate sets and user utterances written from natural administrative,
           workplace, and personal assistant interactions.
- Phase B: Human ground truth assigned from scenario context and ordinary interpretation.
- Phase C: Validated against RAR contract invariants (anti-invention, non-empty candidate IDs).
- Phase D: Frozen with cryptographic SHA-256 hash. Zero execution against resolver.
"""

from __future__ import annotations

from typing import List, Tuple

from uri_v1.turn.rar_contracts import (
    RARBasis,
    RARCandidate,
    RARDeterministicAnchor,
    RAREvidence,
    RARFixture,
    RAROutcome,
    RARQuery,
)


def get_rar_stage4b_fixtures() -> Tuple[RARFixture, ...]:
    """Returns the frozen 136-case Stage 4B independent challenge benchmark."""
    f: List[RARFixture] = []

    f.append(RARFixture(
        id='S4B-001', name='Exact memorandum identifier reference', category='office_exact_id',
        turn_text="Please pull up MEMO-ACAD-2026-088 and check the dean's signature.",
        query=RARQuery(
            reference_expression='MEMO-ACAD-2026-088',
            candidates=(
                RARCandidate(id='memo_acad_088', title='MEMO-ACAD-2026-088_Faculty_Workload.pdf', candidate_type='document', exact_aliases=('MEMO-ACAD-2026-088',)),
                RARCandidate(id='memo_acad_089', title='MEMO-ACAD-2026-089_Course_Allotment.pdf', candidate_type='document', exact_aliases=('MEMO-ACAD-2026-089',)),
            ),
            local_evidence=RAREvidence(),
            deterministic_anchor=RARDeterministicAnchor(exact_id='memo_acad_088'),
        ),
        expected_outcome=RAROutcome.RESOLVED,
        expected_candidate_id='memo_acad_088',
        description='The user provides the exact alphanumeric memorandum ID verbatim matching the exact_id anchor and exact_aliases.',
    ))

    f.append(RARFixture(
        id='S4B-002', name='Hostel room maintenance ticket identifier', category='office_exact_id',
        turn_text='Mark TKT-HOSTEL-9041 as resolved; the plumbing repair was finished this afternoon.',
        query=RARQuery(
            reference_expression='TKT-HOSTEL-9041',
            candidates=(
                RARCandidate(id='tkt_hostel_9041', title='Geyser Repair Block D Room 312', candidate_type='workflow', exact_aliases=('TKT-HOSTEL-9041',)),
                RARCandidate(id='tkt_hostel_9042', title='Window Latch Block B Room 104', candidate_type='workflow', exact_aliases=('TKT-HOSTEL-9042',)),
            ),
            local_evidence=RAREvidence(),
        ),
        expected_outcome=RAROutcome.RESOLVED,
        expected_candidate_id='tkt_hostel_9041',
        description='Ticket alias TKT-HOSTEL-9041 uniquely matches the exact alias of the plumbing repair ticket.',
    ))

    f.append(RARFixture(
        id='S4B-003', name='Scholarship application reference number', category='office_exact_id',
        turn_text='Forward SCH-2026-MCM-014 to the scholarship screening committee.',
        query=RARQuery(
            reference_expression='SCH-2026-MCM-014',
            candidates=(
                RARCandidate(id='sch_mcm_014', title='Merit-cum-Means Application: Rahul Verma', candidate_type='document', exact_aliases=('SCH-2026-MCM-014',)),
                RARCandidate(id='sch_mcm_015', title='Merit-cum-Means Application: Sneha Kulkarni', candidate_type='document', exact_aliases=('SCH-2026-MCM-015',)),
                RARCandidate(id='sch_sports_004', title='Sports Scholarship Application: Aman Deep', candidate_type='document', exact_aliases=('SCH-2026-SP-004',)),
            ),
            local_evidence=RAREvidence(),
        ),
        expected_outcome=RAROutcome.RESOLVED,
        expected_candidate_id='sch_mcm_014',
        description="Application reference SCH-2026-MCM-014 uniquely identifies Rahul Verma's scholarship submission.",
    ))

    f.append(RARFixture(
        id='S4B-004', name='Lab procurement quotation reference number', category='office_exact_id',
        turn_text='Check the unit prices quoted in QUOT-EE-2026-119.',
        query=RARQuery(
            reference_expression='QUOT-EE-2026-119',
            candidates=(
                RARCandidate(id='quot_ee_119', title='Oscilloscope Quotation - Tektronix Vendor', candidate_type='document', exact_aliases=('QUOT-EE-2026-119',)),
                RARCandidate(id='quot_ee_120', title='Function Generator Quotation - Keysight Vendor', candidate_type='document', exact_aliases=('QUOT-EE-2026-120',)),
            ),
            local_evidence=RAREvidence(),
        ),
        expected_outcome=RAROutcome.RESOLVED,
        expected_candidate_id='quot_ee_119',
        description='Vendor quotation reference QUOT-EE-2026-119 matches exactly one candidate document.',
    ))

    f.append(RARFixture(
        id='S4B-005', name='Casual leave application ID match', category='office_exact_id',
        turn_text='Has leave request LV-2026-052 been countersigned by the head of department?',
        query=RARQuery(
            reference_expression='LV-2026-052',
            candidates=(
                RARCandidate(id='lv_app_052', title='Casual Leave 3 Days: Dr. S. N. Roy', candidate_type='workflow', exact_aliases=('LV-2026-052',)),
                RARCandidate(id='lv_app_053', title='Duty Leave 2 Days: Prof. M. H. Beg', candidate_type='workflow', exact_aliases=('LV-2026-053',)),
            ),
            local_evidence=RAREvidence(),
        ),
        expected_outcome=RAROutcome.RESOLVED,
        expected_candidate_id='lv_app_052',
        description="Leave request identifier LV-2026-052 maps unambiguously to Dr. Roy's application.",
    ))

    f.append(RARFixture(
        id='S4B-006', name='Examination hall seating allotment order number', category='office_exact_id',
        turn_text='Print out circular EXAM-CIRC-2026-09 for the notice board.',
        query=RARQuery(
            reference_expression='EXAM-CIRC-2026-09',
            candidates=(
                RARCandidate(id='circ_exam_09', title='Midterm Seating Arrangement Circular 09', candidate_type='document', exact_aliases=('EXAM-CIRC-2026-09',)),
                RARCandidate(id='circ_exam_10', title='Endterm Duty Chart Circular 10', candidate_type='document', exact_aliases=('EXAM-CIRC-2026-10',)),
            ),
            local_evidence=RAREvidence(),
        ),
        expected_outcome=RAROutcome.RESOLVED,
        expected_candidate_id='circ_exam_09',
        description='Circular code EXAM-CIRC-2026-09 uniquely identifies the midterm seating circular.',
    ))

    f.append(RARFixture(
        id='S4B-007', name='Mess committee tender notice reference number', category='office_exact_id',
        turn_text='Archive tender notice TND-MESS-2026-003, bidding closed yesterday.',
        query=RARQuery(
            reference_expression='TND-MESS-2026-003',
            candidates=(
                RARCandidate(id='tnd_mess_003', title='Hostel Mess Catering Tender Notice 03', candidate_type='document', exact_aliases=('TND-MESS-2026-003',)),
                RARCandidate(id='tnd_mess_004', title='Cafeteria Vending Tender Notice 04', candidate_type='document', exact_aliases=('TND-MESS-2026-004',)),
            ),
            local_evidence=RAREvidence(),
        ),
        expected_outcome=RAROutcome.RESOLVED,
        expected_candidate_id='tnd_mess_003',
        description='Tender notice identifier TND-MESS-2026-003 matches the catering tender document.',
    ))

    f.append(RARFixture(
        id='S4B-008', name='Disciplinary committee inquiry case docket identifier', category='office_exact_id',
        turn_text='Open file DISP-CASE-2026-017 for the inquiry session.',
        query=RARQuery(
            reference_expression='DISP-CASE-2026-017',
            candidates=(
                RARCandidate(id='disp_case_017', title='Inquiry Docket: Lab Equipment Damage Case 17', candidate_type='document', exact_aliases=('DISP-CASE-2026-017',)),
                RARCandidate(id='disp_case_018', title='Inquiry Docket: Hostel Curfew Violation Case 18', candidate_type='document', exact_aliases=('DISP-CASE-2026-018',)),
            ),
            local_evidence=RAREvidence(),
        ),
        expected_outcome=RAROutcome.RESOLVED,
        expected_candidate_id='disp_case_017',
        description='Case docket number DISP-CASE-2026-017 clearly specifies the lab damage inquiry dossier.',
    ))

    f.append(RARFixture(
        id='S4B-009', name='Selected audit item in administrative portal', category='office_ui_anchor',
        turn_text='Add an inspection note to this one.',
        query=RARQuery(
            reference_expression='this one',
            candidates=(
                RARCandidate(id='audit_row_12', title='Physics Department Chemical Safety Audit', candidate_type='document'),
                RARCandidate(id='audit_row_15', title='Civil Engineering Concrete Testing Safety Audit', candidate_type='document'),
            ),
            local_evidence=RAREvidence(),
            deterministic_anchor=RARDeterministicAnchor(selected_ui_id='audit_row_12'),
        ),
        expected_outcome=RAROutcome.RESOLVED,
        expected_candidate_id='audit_row_12',
        description="The deictic phrase 'this one' resolves to audit_row_12 via the active UI selection anchor.",
    ))

    f.append(RARFixture(
        id='S4B-010', name='Currently highlighted hostel allotment list entry', category='office_ui_anchor',
        turn_text='Approve the room change on this row.',
        query=RARQuery(
            reference_expression='this row',
            candidates=(
                RARCandidate(id='allot_entry_204', title='Room Change Application: Vikram Singh (Room 102 to 215)', candidate_type='workflow'),
                RARCandidate(id='allot_entry_205', title='Room Change Application: Karan Rao (Room 304 to 110)', candidate_type='workflow'),
            ),
            local_evidence=RAREvidence(),
            deterministic_anchor=RARDeterministicAnchor(selected_ui_id='allot_entry_204'),
        ),
        expected_outcome=RAROutcome.RESOLVED,
        expected_candidate_id='allot_entry_204',
        description="The user refers to 'this row' corresponding directly to the selected allotment row in the UI.",
    ))

    f.append(RARFixture(
        id='S4B-011', name='Focused scholarship ledger entry in table view', category='office_ui_anchor',
        turn_text='Verify the disbursement status for this entry.',
        query=RARQuery(
            reference_expression='this entry',
            candidates=(
                RARCandidate(id='ledger_rec_771', title='Disbursement Record: Post-Matric SC/ST Batch 2', candidate_type='spreadsheet'),
                RARCandidate(id='ledger_rec_772', title='Disbursement Record: State Merit Batch 1', candidate_type='spreadsheet'),
            ),
            local_evidence=RAREvidence(),
            deterministic_anchor=RARDeterministicAnchor(selected_ui_id='ledger_rec_771'),
        ),
        expected_outcome=RAROutcome.RESOLVED,
        expected_candidate_id='ledger_rec_771',
        description="'This entry' points to ledger_rec_771 which is actively selected in the interface table.",
    ))

    f.append(RARFixture(
        id='S4B-012', name='Selected purchase requisition card', category='office_ui_anchor',
        turn_text='Reject this requisition due to budget exhaustion.',
        query=RARQuery(
            reference_expression='this requisition',
            candidates=(
                RARCandidate(id='req_card_401', title='Requisition 401: Computer Science Server RAM Upgrade', candidate_type='workflow'),
                RARCandidate(id='req_card_402', title='Requisition 402: Library Book Scanning Hardware', candidate_type='workflow'),
            ),
            local_evidence=RAREvidence(),
            deterministic_anchor=RARDeterministicAnchor(selected_ui_id='req_card_401'),
        ),
        expected_outcome=RAROutcome.RESOLVED,
        expected_candidate_id='req_card_401',
        description="User references 'this requisition' while requisition card 401 is focused in the UI.",
    ))

    f.append(RARFixture(
        id='S4B-013', name='Active workflow task item in queue', category='office_ui_anchor',
        turn_text='Reassign this task to the assistant registrar.',
        query=RARQuery(
            reference_expression='this task',
            candidates=(
                RARCandidate(id='task_verify_degrees', title='Verification of Convocation Degree Certificates', candidate_type='workflow'),
                RARCandidate(id='task_verify_marks', title='Verification of Consolidated Marksheets', candidate_type='workflow'),
            ),
            local_evidence=RAREvidence(),
            deterministic_anchor=RARDeterministicAnchor(selected_ui_id='task_verify_degrees'),
        ),
        expected_outcome=RAROutcome.RESOLVED,
        expected_candidate_id='task_verify_degrees',
        description="Selection anchor directly binds 'this task' to the currently active degree verification task.",
    ))

    f.append(RARFixture(
        id='S4B-014', name='Focused committee meeting agenda item in drawer', category='office_ui_anchor',
        turn_text='Move this agenda item to any other business.',
        query=RARQuery(
            reference_expression='this agenda item',
            candidates=(
                RARCandidate(id='agenda_item_3', title='Agenda Item 3: Revision of Overtime Allowance for Security Staff', candidate_type='document'),
                RARCandidate(id='agenda_item_4', title='Agenda Item 4: Renewal of Annual AMC for Campus CCTV', candidate_type='document'),
            ),
            local_evidence=RAREvidence(),
            deterministic_anchor=RARDeterministicAnchor(selected_ui_id='agenda_item_3'),
        ),
        expected_outcome=RAROutcome.RESOLVED,
        expected_candidate_id='agenda_item_3',
        description='Active selection identifies agenda_item_3 as the item being manipulated.',
    ))

    f.append(RARFixture(
        id='S4B-015', name='Active student transcript dossier tab', category='office_ui_anchor',
        turn_text='Export this dossier as a certified PDF.',
        query=RARQuery(
            reference_expression='this dossier',
            candidates=(
                RARCandidate(id='dossier_roll_4091', title='Student Academic Dossier: Ananya Sengupta (Roll 4091)', candidate_type='document'),
                RARCandidate(id='dossier_roll_4092', title='Student Academic Dossier: Rohit Mehra (Roll 4092)', candidate_type='document'),
            ),
            local_evidence=RAREvidence(),
            deterministic_anchor=RARDeterministicAnchor(selected_ui_id='dossier_roll_4091'),
        ),
        expected_outcome=RAROutcome.RESOLVED,
        expected_candidate_id='dossier_roll_4091',
        description="Active tab anchor maps 'this dossier' to student Ananya Sengupta's academic file.",
    ))

    f.append(RARFixture(
        id='S4B-016', name='Highlighted employee service book record', category='office_ui_anchor',
        turn_text='Update the gratuity calculation in this record.',
        query=RARQuery(
            reference_expression='this record',
            candidates=(
                RARCandidate(id='srv_book_1108', title='Service Book Record: Shri R. K. Saxena (Sr. Assistant)', candidate_type='document'),
                RARCandidate(id='srv_book_1109', title='Service Book Record: Smt. P. L. Das (Superintendent)', candidate_type='document'),
            ),
            local_evidence=RAREvidence(),
            deterministic_anchor=RARDeterministicAnchor(selected_ui_id='srv_book_1108'),
        ),
        expected_outcome=RAROutcome.RESOLVED,
        expected_candidate_id='srv_book_1108',
        description='The active UI selection points unambiguously to employee record srv_book_1108.',
    ))

    f.append(RARFixture(
        id='S4B-017', name='Exact verbatim title match for hostel fee structure', category='office_verbatim_title',
        turn_text='Send me Hostel_Fee_Structure_2026_2027.pdf so I can review the room rent breakdown.',
        query=RARQuery(
            reference_expression='Hostel_Fee_Structure_2026_2027.pdf',
            candidates=(
                RARCandidate(id='doc_fee_hostel', title='Hostel_Fee_Structure_2026_2027.pdf', candidate_type='document'),
                RARCandidate(id='doc_fee_tuition', title='Tuition_Fee_Structure_2026_2027.pdf', candidate_type='document'),
                RARCandidate(id='doc_fee_mess', title='Mess_Fee_Schedule_2026.pdf', candidate_type='document'),
            ),
            local_evidence=RAREvidence(),
        ),
        expected_outcome=RAROutcome.RESOLVED,
        expected_candidate_id='doc_fee_hostel',
        description='The reference expression exactly matches the file name Hostel_Fee_Structure_2026_2027.pdf.',
    ))

    f.append(RARFixture(
        id='S4B-018', name='Shortened name for faculty leave policy document', category='office_shortened_name',
        turn_text='Have you looked over the leave policy yet?',
        query=RARQuery(
            reference_expression='the leave policy',
            candidates=(
                RARCandidate(id='doc_leave_policy', title='Faculty_Leave_Rules_And_Regulations_2025.pdf', candidate_type='document', domain_tags=('leave', 'policy')),
                RARCandidate(id='doc_procure_policy', title='Equipment_Procurement_Policy_Manual.pdf', candidate_type='document', domain_tags=('procurement', 'policy')),
                RARCandidate(id='doc_hostel_rules', title='Hostel_Residence_Rules_2026.pdf', candidate_type='document', domain_tags=('hostel', 'rules')),
            ),
            local_evidence=RAREvidence(target_type_hint='document'),
        ),
        expected_outcome=RAROutcome.RESOLVED,
        expected_candidate_id='doc_leave_policy',
        description="The user refers to 'the leave policy' which unambiguously denotes the faculty leave rules document.",
    ))

    f.append(RARFixture(
        id='S4B-019', name='Natural shortened reference to convocation invitation draft', category='office_shortened_name',
        turn_text='Email the convocation invite to the registrar for proofreading.',
        query=RARQuery(
            reference_expression='the convocation invite',
            candidates=(
                RARCandidate(id='doc_conv_inv', title='Annual_Convocation_Chief_Guest_Invitation_Draft.docx', candidate_type='document', domain_tags=('convocation', 'invitation')),
                RARCandidate(id='doc_conv_order', title='Convocation_Robes_Order_Vendor_List.xlsx', candidate_type='spreadsheet', domain_tags=('convocation', 'vendor')),
                RARCandidate(id='doc_fdp_inv', title='Faculty_Development_Programme_Invitation.docx', candidate_type='document', domain_tags=('fdp', 'invitation')),
            ),
            local_evidence=RAREvidence(target_type_hint='document'),
        ),
        expected_outcome=RAROutcome.RESOLVED,
        expected_candidate_id='doc_conv_inv',
        description="'The convocation invite' uniquely refers to the convocation invitation draft.",
    ))

    f.append(RARFixture(
        id='S4B-020', name='Exact title match with duplicate titles causing honest ambiguity', category='office_verbatim_title',
        turn_text='Open Syndicate_Meeting_Minutes.docx.',
        query=RARQuery(
            reference_expression='Syndicate_Meeting_Minutes.docx',
            candidates=(
                RARCandidate(id='min_synd_181', title='Syndicate_Meeting_Minutes.docx', candidate_type='document', domain_tags=('meeting_181',)),
                RARCandidate(id='min_synd_182', title='Syndicate_Meeting_Minutes.docx', candidate_type='document', domain_tags=('meeting_182',)),
            ),
            local_evidence=RAREvidence(),
        ),
        expected_outcome=RAROutcome.AMBIGUOUS,
        expected_ambiguous_candidate_ids=('min_synd_181', 'min_synd_182'),
        description='Two candidate documents share the exact identical title Syndicate_Meeting_Minutes.docx; without further discriminator, the reference is ambiguous.',
    ))

    f.append(RARFixture(
        id='S4B-021', name='Colloquial abbreviation of board of studies resolution', category='office_shortened_name',
        turn_text='Check if the BOS resolution approved the new elective syllabus.',
        query=RARQuery(
            reference_expression='the BOS resolution',
            candidates=(
                RARCandidate(id='res_bos_cse', title='Board_Of_Studies_Computer_Science_Resolution_2026.pdf', candidate_type='document', exact_aliases=('BOS resolution', 'BOS CSE')),
                RARCandidate(id='res_ac_council', title='Academic_Council_Meeting_Minutes_March.pdf', candidate_type='document'),
                RARCandidate(id='res_finance_comm', title='Finance_Committee_Resolution_Budget.pdf', candidate_type='document'),
            ),
            local_evidence=RAREvidence(),
        ),
        expected_outcome=RAROutcome.RESOLVED,
        expected_candidate_id='res_bos_cse',
        description='BOS is the standard acronym for Board of Studies, matching res_bos_cse.',
    ))

    f.append(RARFixture(
        id='S4B-022', name='Shortened reference to anti-ragging committee circular', category='office_shortened_name',
        turn_text='Circulate the anti-ragging notice to all hostel wardens immediately.',
        query=RARQuery(
            reference_expression='the anti-ragging notice',
            candidates=(
                RARCandidate(id='doc_ragging_circ', title='Anti_Ragging_Affidavit_Mandate_Circular_2026.pdf', candidate_type='document', domain_tags=('anti_ragging', 'circular')),
                RARCandidate(id='doc_fee_circ', title='Hostel_Late_Fee_Circular_Semester_I.pdf', candidate_type='document', domain_tags=('hostel', 'fee')),
            ),
            local_evidence=RAREvidence(),
        ),
        expected_outcome=RAROutcome.RESOLVED,
        expected_candidate_id='doc_ragging_circ',
        description="'The anti-ragging notice' refers cleanly to the anti-ragging mandate circular.",
    ))

    f.append(RARFixture(
        id='S4B-023', name='Reference to non-existent institutional document', category='office_unknown',
        turn_text='Where is the quarterly sports budget sanction letter?',
        query=RARQuery(
            reference_expression='the quarterly sports budget sanction letter',
            candidates=(
                RARCandidate(id='doc_hostel_sanct', title='Hostel_Mess_Subsidy_Sanction_Letter.pdf', candidate_type='document'),
                RARCandidate(id='doc_lab_sanct', title='Chemistry_Lab_Chemicals_Sanction_Order.pdf', candidate_type='document'),
            ),
            local_evidence=RAREvidence(target_type_hint='document'),
        ),
        expected_outcome=RAROutcome.UNKNOWN,
        description='The candidate set contains hostel and chemistry lab sanctions, but no sports budget sanction letter exists in the candidate pool.',
    ))

    f.append(RARFixture(
        id='S4B-024', name='Abbreviated reference to PhD progress evaluation report', category='office_shortened_name',
        turn_text='Submit the progress report to the dean of research.',
        query=RARQuery(
            reference_expression='the progress report',
            candidates=(
                RARCandidate(id='rep_phd_eval', title='Doctoral_Scholar_Half_Yearly_Progress_Report_2026.docx', candidate_type='document', domain_tags=('research', 'progress_report')),
                RARCandidate(id='rep_naac_eval', title='Institutional_NAAC_Accreditation_Report_Final.pdf', candidate_type='document', domain_tags=('naac', 'quality')),
            ),
            local_evidence=RAREvidence(target_type_hint='document'),
        ),
        expected_outcome=RAROutcome.RESOLVED,
        expected_candidate_id='rep_phd_eval',
        description="The candidate rep_phd_eval uniquely matches 'the progress report'.",
    ))

    f.append(RARFixture(
        id='S4B-025', name='Continuation pointer to same hostel circular', category='office_active_pointer',
        turn_text='Can you attach the same circular to the email for wardens?',
        query=RARQuery(
            reference_expression='the same circular',
            candidates=(
                RARCandidate(id='circ_hostel_curfew', title='Hostel_Curfew_Timings_Notification.pdf', candidate_type='document', domain_tags=('recently_discussed',)),
                RARCandidate(id='circ_library_fines', title='Library_Overdue_Fines_Notification.pdf', candidate_type='document', recency_rank=4),
            ),
            local_evidence=RAREvidence(recency_hint='same', target_type_hint='document'),
        ),
        expected_outcome=RAROutcome.RESOLVED,
        expected_candidate_id='circ_hostel_curfew',
        description="'The same circular' continues focus on the circular recently discussed in the immediate turn context.",
    ))

    f.append(RARFixture(
        id='S4B-026', name='Conversational continuation reference to current order', category='office_active_pointer',
        turn_text="Also add the registrar's dispatch endorsement to that order.",
        query=RARQuery(
            reference_expression='that order',
            candidates=(
                RARCandidate(id='ord_fee_waiver', title='Office_Order_104_Tuition_Fee_Waiver.pdf', candidate_type='document', domain_tags=('recently_discussed',)),
                RARCandidate(id='ord_estate_clean', title='Office_Order_98_Sanitation_Contract.pdf', candidate_type='document', recency_rank=3),
            ),
            local_evidence=RAREvidence(recency_hint='same', target_type_hint='document'),
        ),
        expected_outcome=RAROutcome.RESOLVED,
        expected_candidate_id='ord_fee_waiver',
        description="Active conversational focus binds 'that order' to the fee waiver order under active discussion.",
    ))

    f.append(RARFixture(
        id='S4B-027', name='Reference to same committee minutes in follow-up step', category='office_active_pointer',
        turn_text='Send the same minutes to the absent members too.',
        query=RARQuery(
            reference_expression='the same minutes',
            candidates=(
                RARCandidate(id='min_sports_board', title='Sports_Advisory_Board_Meeting_Minutes.pdf', candidate_type='document', domain_tags=('recently_discussed',)),
                RARCandidate(id='min_canteen_comm', title='Canteen_Supervisory_Minutes.pdf', candidate_type='document', recency_rank=5),
            ),
            local_evidence=RAREvidence(recency_hint='same', target_type_hint='document'),
        ),
        expected_outcome=RAROutcome.RESOLVED,
        expected_candidate_id='min_sports_board',
        description="'The same minutes' binds to the recently discussed sports board minutes.",
    ))

    f.append(RARFixture(
        id='S4B-028', name='Continuation reference with two recently discussed items causing ambiguity', category='office_active_pointer',
        turn_text='Forward that notice.',
        query=RARQuery(
            reference_expression='that notice',
            candidates=(
                RARCandidate(id='notif_exam_postpone', title='Midterm_Exam_Postponement_Notice.pdf', candidate_type='document', domain_tags=('recently_discussed',)),
                RARCandidate(id='notif_holiday_diwali', title='Public_Holiday_Declaration_Notice.pdf', candidate_type='document', domain_tags=('recently_discussed',)),
            ),
            local_evidence=RAREvidence(recency_hint='same', target_type_hint='document'),
        ),
        expected_outcome=RAROutcome.AMBIGUOUS,
        expected_ambiguous_candidate_ids=('notif_exam_postpone', 'notif_holiday_diwali'),
        description="Both notices were flagged in recent discourse; 'that notice' is ambiguous without further qualification.",
    ))

    f.append(RARFixture(
        id='S4B-029', name='Continuation pointer to active procurement workflow', category='office_active_pointer',
        turn_text='Proceed with the same workflow.',
        query=RARQuery(
            reference_expression='the same workflow',
            candidates=(
                RARCandidate(id='wf_chem_purchase', title='Chemistry Glassware Purchase Requisition', candidate_type='workflow', domain_tags=('recently_discussed',)),
                RARCandidate(id='wf_bio_purchase', title='Microbiology Reagents Purchase Requisition', candidate_type='workflow', recency_rank=2),
            ),
            local_evidence=RAREvidence(recency_hint='same', target_type_hint='workflow'),
        ),
        expected_outcome=RAROutcome.RESOLVED,
        expected_candidate_id='wf_chem_purchase',
        description="'The same workflow' binds to the active chemistry purchase workflow marked recently discussed.",
    ))

    f.append(RARFixture(
        id='S4B-029B', name='Continuation pointer to same candidate spreadsheet', category='office_active_pointer',
        turn_text='Re-check the formulas in the same spreadsheet.',
        query=RARQuery(
            reference_expression='the same spreadsheet',
            candidates=(
                RARCandidate(id='sheet_budget_actuals', title='Annual_Budget_Actuals_2025_2026.xlsx', candidate_type='spreadsheet', domain_tags=('recently_discussed',)),
                RARCandidate(id='sheet_ta_da_claims', title='Faculty_Travel_Claims_Q3.xlsx', candidate_type='spreadsheet', recency_rank=3),
            ),
            local_evidence=RAREvidence(recency_hint='same', target_type_hint='spreadsheet'),
        ),
        expected_outcome=RAROutcome.RESOLVED,
        expected_candidate_id='sheet_budget_actuals',
        description="'The same spreadsheet' points directly to the active budget actuals spreadsheet.",
    ))

    f.append(RARFixture(
        id='S4B-030', name='Continuation reference with absent target type', category='office_active_pointer',
        turn_text='Resend the same audio recording to the court reporter.',
        query=RARQuery(
            reference_expression='the same audio recording',
            candidates=(
                RARCandidate(id='min_inquiry_doc', title='Formal_Inquiry_Proceedings_Transcript.pdf', candidate_type='document', domain_tags=('recently_discussed',)),
                RARCandidate(id='notes_inquiry_doc', title='Handwritten_Rough_Notes_Inquiry.pdf', candidate_type='document'),
            ),
            local_evidence=RAREvidence(recency_hint='same', target_type_hint='media'),
        ),
        expected_outcome=RAROutcome.UNKNOWN,
        description='The user asks for an audio recording, but only textual transcript documents exist in the candidate pool.',
    ))

    f.append(RARFixture(
        id='S4B-031', name='Stale continuation reference with multiple distant documents', category='office_active_pointer',
        turn_text='What was that memo we discussed last Tuesday?',
        query=RARQuery(
            reference_expression='that memo',
            candidates=(
                RARCandidate(id='memo_green_campus', title='Green_Campus_Vehicle_Ban_Memo.pdf', candidate_type='document', recency_rank=6),
                RARCandidate(id='memo_energy_save', title='Air_Conditioner_Shutdown_Hours_Memo.pdf', candidate_type='document', recency_rank=7),
            ),
            local_evidence=RAREvidence(target_type_hint='document'),
        ),
        expected_outcome=RAROutcome.AMBIGUOUS,
        expected_ambiguous_candidate_ids=('memo_green_campus', 'memo_energy_save'),
        description="Two historical memos exist in the pool with no active pointer or distinguishing cue; 'that memo' is ambiguous.",
    ))

    f.append(RARFixture(
        id='S4B-032', name='Continuation reference to recently closed grievance ticket', category='office_active_pointer',
        turn_text='Reopen that ticket; the student reported the problem recurred.',
        query=RARQuery(
            reference_expression='that ticket',
            candidates=(
                RARCandidate(id='tkt_wifi_hostel_g', title='Hostel G WiFi Access Point Failure', candidate_type='workflow', domain_tags=('recently_discussed',)),
                RARCandidate(id='tkt_water_cooler_3', title='Water Cooler Filter Replacement Library', candidate_type='workflow', recency_rank=4),
            ),
            local_evidence=RAREvidence(recency_hint='same', target_type_hint='workflow'),
        ),
        expected_outcome=RAROutcome.RESOLVED,
        expected_candidate_id='tkt_wifi_hostel_g',
        description="Active context binds 'that ticket' to the recently discussed WiFi failure grievance ticket.",
    ))

    f.append(RARFixture(
        id='S4B-033', name='Type distinction between document and email', category='office_type_constraint',
        turn_text='Forward the email to Dr. Raman.',
        query=RARQuery(
            reference_expression='the email',
            candidates=(
                RARCandidate(id='mail_conf_reg', title='Registration Confirmation: International Robotics Symposium', candidate_type='email'),
                RARCandidate(id='doc_conf_receipt', title='Symposium_Registration_Fee_Receipt.pdf', candidate_type='document'),
                RARCandidate(id='doc_conf_schedule', title='Robotics_Symposium_Detailed_Programme.pdf', candidate_type='document'),
            ),
            local_evidence=RAREvidence(target_type_hint='email'),
        ),
        expected_outcome=RAROutcome.RESOLVED,
        expected_candidate_id='mail_conf_reg',
        description="Type hint 'email' isolates mail_conf_reg from the two document candidates.",
    ))

    f.append(RARFixture(
        id='S4B-034', name='Type distinction between workflow and spreadsheet', category='office_type_constraint',
        turn_text='Open the spreadsheet to calculate the hostel deposit refund totals.',
        query=RARQuery(
            reference_expression='the spreadsheet',
            candidates=(
                RARCandidate(id='sheet_deposit_refunds', title='Hostel_Caution_Deposit_Refund_Ledger.xlsx', candidate_type='spreadsheet'),
                RARCandidate(id='wf_refund_approval', title='Caution Deposit Refund Clearance Workflow', candidate_type='workflow'),
                RARCandidate(id='doc_refund_guidelines', title='Caution_Deposit_Disbursement_Guidelines.pdf', candidate_type='document'),
            ),
            local_evidence=RAREvidence(target_type_hint='spreadsheet'),
        ),
        expected_outcome=RAROutcome.RESOLVED,
        expected_candidate_id='sheet_deposit_refunds',
        description="Target type 'spreadsheet' cleanly identifies sheet_deposit_refunds.",
    ))

    f.append(RARFixture(
        id='S4B-035', name='Type distinction between workflow and administrative document', category='office_type_constraint',
        turn_text='Trigger the workflow for semester grade moderation.',
        query=RARQuery(
            reference_expression='the workflow',
            candidates=(
                RARCandidate(id='wf_grade_mod', title='Semester Grade Moderation Approval Pipeline', candidate_type='workflow'),
                RARCandidate(id='doc_grade_rules', title='Grading_System_And_Moderation_Policy.pdf', candidate_type='document'),
            ),
            local_evidence=RAREvidence(target_type_hint='workflow'),
        ),
        expected_outcome=RAROutcome.RESOLVED,
        expected_candidate_id='wf_grade_mod',
        description="'The workflow' selects the approval pipeline workflow candidate over the policy document.",
    ))

    f.append(RARFixture(
        id='S4B-036', name='Type constraint with multiple candidates of requested type', category='office_type_constraint',
        turn_text='Review the email.',
        query=RARQuery(
            reference_expression='the email',
            candidates=(
                RARCandidate(id='mail_dean_eval', title='Fwd: Faculty Annual Appraisal Submission Due Date', candidate_type='email'),
                RARCandidate(id='mail_provost_mess', title='Notice of Surprise Inspection of Mess Kitchen', candidate_type='email'),
                RARCandidate(id='doc_appraisal_form', title='Annual_Performance_Appraisal_Report_Form.docx', candidate_type='document'),
            ),
            local_evidence=RAREvidence(target_type_hint='email'),
        ),
        expected_outcome=RAROutcome.AMBIGUOUS,
        expected_ambiguous_candidate_ids=('mail_dean_eval', 'mail_provost_mess'),
        description='Type constraint narrows to emails, but two plausible emails exist with no further discriminator.',
    ))

    f.append(RARFixture(
        id='S4B-037', name='Type constraint with zero matching candidates', category='office_type_constraint',
        turn_text='Send the presentation to the projection room staff.',
        query=RARQuery(
            reference_expression='the presentation',
            candidates=(
                RARCandidate(id='doc_audit_report', title='Energy_Audit_Report_2026.pdf', candidate_type='document'),
                RARCandidate(id='sheet_audit_data', title='Campus_Power_Consumption_Data.xlsx', candidate_type='spreadsheet'),
            ),
            local_evidence=RAREvidence(target_type_hint='presentation'),
        ),
        expected_outcome=RAROutcome.UNKNOWN,
        description='User requests a presentation, but the candidate pool contains only a PDF document and an Excel spreadsheet.',
    ))

    f.append(RARFixture(
        id='S4B-038', name='Type distinction between person entity and personnel file document', category='office_type_constraint',
        turn_text='Notify Dr. Mukherjee regarding the committee schedule.',
        query=RARQuery(
            reference_expression='Dr. Mukherjee',
            candidates=(
                RARCandidate(id='person_prof_mukherjee', title='Prof. Anirban Mukherjee (Department of Chemical Engineering)', candidate_type='person'),
                RARCandidate(id='doc_mukherjee_appraisal', title='Prof_Mukherjee_Promotion_Dossier_2025.pdf', candidate_type='document'),
            ),
            local_evidence=RAREvidence(target_type_hint='person'),
        ),
        expected_outcome=RAROutcome.RESOLVED,
        expected_candidate_id='person_prof_mukherjee',
        description='The reference denotes the faculty member person entity rather than his personnel dossier document.',
    ))

    f.append(RARFixture(
        id='S4B-039', name='Type constraint isolating media file from text circulars', category='office_type_constraint',
        turn_text='Play the audio recording from the town hall meeting.',
        query=RARQuery(
            reference_expression='the audio recording',
            candidates=(
                RARCandidate(id='audio_townhall_feb', title='Campus_Town_Hall_Recording_14Feb.mp3', candidate_type='media'),
                RARCandidate(id='doc_townhall_summary', title='Town_Hall_Key_Decisions_Summary.pdf', candidate_type='document'),
                RARCandidate(id='doc_townhall_agenda', title='Town_Hall_Meeting_Notice_And_Agenda.docx', candidate_type='document'),
            ),
            local_evidence=RAREvidence(target_type_hint='media'),
        ),
        expected_outcome=RAROutcome.RESOLVED,
        expected_candidate_id='audio_townhall_feb',
        description="Target type 'media' uniquely filters down to the MP3 recording audio_townhall_feb.",
    ))

    f.append(RARFixture(
        id='S4B-040', name='Type constraint resolving single spreadsheet among documents', category='office_type_constraint',
        turn_text='Recalculate the totals in the sheet.',
        query=RARQuery(
            reference_expression='the sheet',
            candidates=(
                RARCandidate(id='sheet_marks_entry', title='Midterm_Exam_Marks_CSE301.xlsx', candidate_type='spreadsheet'),
                RARCandidate(id='doc_qp_cse301', title='Midterm_Exam_Question_Paper_CSE301.pdf', candidate_type='document'),
                RARCandidate(id='doc_ans_key_cse301', title='Midterm_Exam_Solution_Key_CSE301.pdf', candidate_type='document'),
            ),
            local_evidence=RAREvidence(target_type_hint='spreadsheet'),
        ),
        expected_outcome=RAROutcome.RESOLVED,
        expected_candidate_id='sheet_marks_entry',
        description="'The sheet' with target type spreadsheet selects sheet_marks_entry uniquely.",
    ))

    f.append(RARFixture(
        id='S4B-041', name='Latest committee meeting minutes resolution', category='office_temporal_latest',
        turn_text='Send the latest committee minutes to the registrar.',
        query=RARQuery(
            reference_expression='the latest committee minutes',
            candidates=(
                RARCandidate(id='min_comm_sept', title='Library_Advisory_Committee_Minutes.docx', candidate_type='document'),
                RARCandidate(id='min_comm_aug', title='Library_Advisory_Committee_Minutes.docx', candidate_type='document', recency_rank=1),
                RARCandidate(id='min_comm_july', title='Library_Advisory_Committee_Minutes.docx', candidate_type='document', recency_rank=2),
            ),
            local_evidence=RAREvidence(recency_hint='latest', target_type_hint='document'),
        ),
        expected_outcome=RAROutcome.RESOLVED,
        expected_candidate_id='min_comm_sept',
        description="The user explicitly requests 'the latest' version among identically-titled minutes, uniquely resolving to recency_rank 0.",
    ))

    f.append(RARFixture(
        id='S4B-042', name='Current fee structure version resolution', category='office_temporal_current',
        turn_text='Publish the current fee structure on the student portal.',
        query=RARQuery(
            reference_expression='the current fee structure',
            candidates=(
                RARCandidate(id='fee_struct_2026', title='Institute_Fee_Schedule_Approved.pdf', candidate_type='document'),
                RARCandidate(id='fee_struct_2025', title='Institute_Fee_Schedule_Approved.pdf', candidate_type='document', recency_rank=1),
            ),
            local_evidence=RAREvidence(recency_hint='current', target_type_hint='document'),
        ),
        expected_outcome=RAROutcome.RESOLVED,
        expected_candidate_id='fee_struct_2026',
        description="'The current fee structure' resolves to the active recency_rank 0 schedule.",
    ))

    f.append(RARFixture(
        id='S4B-043', name='Previous notification in thread ordinal lookup', category='office_temporal_previous',
        turn_text='Compare the deadline with the previous notification.',
        query=RARQuery(
            reference_expression='the previous notification',
            candidates=(
                RARCandidate(id='notif_extension', title='PhD_Thesis_Submission_Extension_Notice.pdf', candidate_type='document'),
                RARCandidate(id='notif_original_deadline', title='PhD_Thesis_Submission_Notice.pdf', candidate_type='document', recency_rank=1),
                RARCandidate(id='notif_archive_2024', title='PhD_Thesis_General_Circular_2024.pdf', candidate_type='document', recency_rank=2),
            ),
            local_evidence=RAREvidence(recency_hint='previous', target_type_hint='document'),
        ),
        expected_outcome=RAROutcome.RESOLVED,
        expected_candidate_id='notif_original_deadline',
        description="'The previous notification' targets the ordinal rank-1 document immediately preceding the current notification.",
    ))

    f.append(RARFixture(
        id='S4B-044', name='Earlier quotation for lab power supply', category='office_temporal_earlier',
        turn_text='What was the warranty term in the earlier quotation?',
        query=RARQuery(
            reference_expression='the earlier quotation',
            candidates=(
                RARCandidate(id='quot_pwr_revised', title='Regulated_DC_Power_Supply_Vendor_A.pdf', candidate_type='document'),
                RARCandidate(id='quot_pwr_initial', title='Regulated_DC_Power_Supply_Vendor_A.pdf', candidate_type='document', recency_rank=1),
            ),
            local_evidence=RAREvidence(recency_hint='earlier', target_type_hint='document'),
        ),
        expected_outcome=RAROutcome.RESOLVED,
        expected_candidate_id='quot_pwr_initial',
        description="'The earlier quotation' resolves to the prior initial quote (recency_rank 1) rather than the active quote.",
    ))

    f.append(RARFixture(
        id='S4B-045', name='Revised hostel mess rules resolution', category='office_revision_relation',
        turn_text='Post the revised rules on the mess bulletin board.',
        query=RARQuery(
            reference_expression='the revised rules',
            candidates=(
                RARCandidate(id='rules_mess_original', title='Hostel_Mess_Rules_2026.docx', candidate_type='document', domain_tags=('original',)),
                RARCandidate(id='rules_mess_revised', title='Hostel_Mess_Rules_2026.docx', candidate_type='document', domain_tags=('revised',)),
            ),
            local_evidence=RAREvidence(recency_hint='revised', target_type_hint='document'),
        ),
        expected_outcome=RAROutcome.RESOLVED,
        expected_candidate_id='rules_mess_revised',
        description="User specifies 'the revised rules'; candidate rules_mess_revised is tagged as revised.",
    ))

    f.append(RARFixture(
        id='S4B-046', name='Original fellowship award letter before amendment', category='office_revision_relation',
        turn_text='Check the stipend amount stated in the original award letter.',
        query=RARQuery(
            reference_expression='the original award letter',
            candidates=(
                RARCandidate(id='ltr_award_orig', title='Institute_Postdoctoral_Fellowship_Letter.pdf', candidate_type='document', domain_tags=('original',)),
                RARCandidate(id='ltr_award_amend', title='Institute_Postdoctoral_Fellowship_Letter.pdf', candidate_type='document', domain_tags=('revised', 'amended')),
            ),
            local_evidence=RAREvidence(recency_hint='original', target_type_hint='document'),
        ),
        expected_outcome=RAROutcome.RESOLVED,
        expected_candidate_id='ltr_award_orig',
        description="User specifically requests 'the original award letter', distinguishing ltr_award_orig from the amendment.",
    ))

    f.append(RARFixture(
        id='S4B-047', name='Multiple revised drafts causing revision ambiguity', category='office_revision_relation',
        turn_text='Forward the revised draft to the dean.',
        query=RARQuery(
            reference_expression='the revised draft',
            candidates=(
                RARCandidate(id='draft_policy_rev_a', title='Academic_Integrity_Policy_v2.docx', candidate_type='document', domain_tags=('revised',)),
                RARCandidate(id='draft_policy_rev_b', title='Consultancy_Rules_Policy_v2.docx', candidate_type='document', domain_tags=('revised',)),
            ),
            local_evidence=RAREvidence(recency_hint='revised', target_type_hint='document'),
        ),
        expected_outcome=RAROutcome.AMBIGUOUS,
        expected_ambiguous_candidate_ids=('draft_policy_rev_a', 'draft_policy_rev_b'),
        description="Two distinct revised policy drafts exist in the pool; 'the revised draft' is ambiguous between them.",
    ))

    f.append(RARFixture(
        id='S4B-048', name='Latest reference where all candidates lack recency metadata', category='office_temporal_latest',
        turn_text='Show me the latest tender document.',
        query=RARQuery(
            reference_expression='the latest tender document',
            candidates=(
                RARCandidate(id='tnd_security_staff', title='Tender_Campus_Security_Services.pdf', candidate_type='document'),
                RARCandidate(id='tnd_housekeeping', title='Tender_Sanitation_Housekeeping.pdf', candidate_type='document'),
            ),
            local_evidence=RAREvidence(recency_hint='latest', target_type_hint='document'),
        ),
        expected_outcome=RAROutcome.AMBIGUOUS,
        expected_ambiguous_candidate_ids=('tnd_security_staff', 'tnd_housekeeping'),
        description="Both tenders share default recency_rank 0 with no ordering established; 'the latest' cannot safely resolve to either.",
    ))

    f.append(RARFixture(
        id='S4B-049', name='Ordinally tied recency candidates causing ambiguity', category='office_temporal_latest',
        turn_text='Print the current allotment list.',
        query=RARQuery(
            reference_expression='the current allotment list',
            candidates=(
                RARCandidate(id='allot_hostel_a', title='Hostel_Allotment_List_Boys.pdf', candidate_type='document'),
                RARCandidate(id='allot_hostel_b', title='Hostel_Allotment_List_Girls.pdf', candidate_type='document'),
                RARCandidate(id='allot_hostel_old', title='Hostel_Allotment_Archive_2025.pdf', candidate_type='document', recency_rank=1),
            ),
            local_evidence=RAREvidence(recency_hint='current', target_type_hint='document'),
        ),
        expected_outcome=RAROutcome.AMBIGUOUS,
        expected_ambiguous_candidate_ids=('allot_hostel_a', 'allot_hostel_b'),
        description="Two current lists share recency_rank 0; without gender specification, 'the current allotment list' is ambiguous.",
    ))

    f.append(RARFixture(
        id='S4B-050', name='Previous version request with absent rank 1', category='office_temporal_previous',
        turn_text='Revert to the previous version of the exam schedule.',
        query=RARQuery(
            reference_expression='the previous version of the exam schedule',
            candidates=(
                RARCandidate(id='sched_exam_active', title='Midterm_Examination_Timetable_Final.pdf', candidate_type='document'),
            ),
            local_evidence=RAREvidence(recency_hint='previous', target_type_hint='document'),
        ),
        expected_outcome=RAROutcome.UNKNOWN,
        description='The user asks for the previous version, but only the active current version is present in the candidate pool.',
    ))

    f.append(RARFixture(
        id='S4B-051', name='Contrastive selection between two committee reports', category='office_contrast',
        turn_text='Not the sports committee report, send the other one.',
        query=RARQuery(
            reference_expression='the other one',
            candidates=(
                RARCandidate(id='rep_sports_comm', title='Annual_Sports_Board_Report.pdf', candidate_type='document', domain_tags=('sports', 'committee')),
                RARCandidate(id='rep_hostel_comm', title='Hostel_Discipline_Committee_Report.pdf', candidate_type='document', domain_tags=('hostel', 'committee')),
            ),
            local_evidence=RAREvidence(negation_spans=('Not the sports committee report',), recency_hint='other', target_type_hint='document'),
        ),
        expected_outcome=RAROutcome.RESOLVED,
        expected_candidate_id='rep_hostel_comm',
        description="Negation explicitly excludes the sports report; 'the other one' resolves to the hostel committee report.",
    ))

    f.append(RARFixture(
        id='S4B-052', name='Exclusion of invoice with single surviving report', category='office_contrast',
        turn_text="Skip the invoice and approve the contractor's maintenance report.",
        query=RARQuery(
            reference_expression="the contractor's maintenance report",
            candidates=(
                RARCandidate(id='inv_lift_repair', title='Invoice_Elevator_AMC_Q3.pdf', candidate_type='document', domain_tags=('invoice', 'repair')),
                RARCandidate(id='rep_lift_inspect', title='Elevator_Safety_Inspection_Report.pdf', candidate_type='document', domain_tags=('report', 'inspection')),
            ),
            local_evidence=RAREvidence(negation_spans=('Skip the invoice',), target_type_hint='document'),
        ),
        expected_outcome=RAROutcome.RESOLVED,
        expected_candidate_id='rep_lift_inspect',
        description='The user explicitly skips the invoice and requests the maintenance report, cleanly selecting rep_lift_inspect.',
    ))

    f.append(RARFixture(
        id='S4B-053', name='Correction excluding assistant coordinator report', category='office_contrast',
        turn_text="I meant the coordinator's note, not the assistant coordinator's.",
        query=RARQuery(
            reference_expression="the coordinator's note",
            candidates=(
                RARCandidate(id='note_coord_main', title='Coordinator_Briefing_Note_Admissions.docx', candidate_type='document', domain_tags=('coordinator',)),
                RARCandidate(id='note_asst_coord', title='Assistant_Coordinator_Briefing_Note_Admissions.docx', candidate_type='document', domain_tags=('assistant_coordinator',)),
            ),
            local_evidence=RAREvidence(negation_spans=("not the assistant coordinator's",), target_type_hint='document'),
        ),
        expected_outcome=RAROutcome.RESOLVED,
        expected_candidate_id='note_coord_main',
        description="Negation isolates the assistant coordinator note; the head coordinator's note note_coord_main resolves.",
    ))

    f.append(RARFixture(
        id='S4B-054', name='Negation excluding one month leaving two plausible months', category='office_contrast',
        turn_text="Don't look at the July minutes, review the recent ones.",
        query=RARQuery(
            reference_expression='the recent ones',
            candidates=(
                RARCandidate(id='min_lib_july', title='Library_Committee_Minutes_July.docx', candidate_type='document', domain_tags=('july',)),
                RARCandidate(id='min_lib_aug', title='Library_Committee_Minutes_August.docx', candidate_type='document', domain_tags=('august',)),
                RARCandidate(id='min_lib_sept', title='Library_Committee_Minutes_September.docx', candidate_type='document', domain_tags=('september',)),
            ),
            local_evidence=RAREvidence(negation_spans=("Don't look at the July minutes",), target_type_hint='document'),
        ),
        expected_outcome=RAROutcome.AMBIGUOUS,
        expected_ambiguous_candidate_ids=('min_lib_aug', 'min_lib_sept'),
        description="Excluding July leaves August and September; 'the recent ones' remains ambiguous between both survivors.",
    ))

    f.append(RARFixture(
        id='S4B-055', name='Total negation eliminating all candidates in pool', category='office_contrast',
        turn_text='Neither of these fee circulars, I asked for the exam circular.',
        query=RARQuery(
            reference_expression='the exam circular',
            candidates=(
                RARCandidate(id='circ_fee_regular', title='Late_Fee_Circular_UG.pdf', candidate_type='document', domain_tags=('fee', 'circular')),
                RARCandidate(id='circ_fee_hostel', title='Late_Fee_Circular_Hostel.pdf', candidate_type='document', domain_tags=('fee', 'circular')),
            ),
            local_evidence=RAREvidence(negation_spans=('Neither of these fee circulars',), target_type_hint='document'),
        ),
        expected_outcome=RAROutcome.UNKNOWN,
        description='Both fee circular candidates are rejected and the requested exam circular is not present in the pool.',
    ))

    f.append(RARFixture(
        id='S4B-056', name='Contrastive choice excluding printed notice in favor of digital notices', category='office_contrast',
        turn_text='Not the printed notice, send one of the digital ones.',
        query=RARQuery(
            reference_expression='one of the digital ones',
            candidates=(
                RARCandidate(id='notif_paper_copy', title='Holiday_Notice_Scanned_Print.pdf', candidate_type='document', domain_tags=('printed',)),
                RARCandidate(id='notif_email_body', title='Holiday_Notice_HTML_Email.docx', candidate_type='document', domain_tags=('digital',)),
                RARCandidate(id='notif_web_portal', title='Holiday_Notice_Web_Announcement.docx', candidate_type='document', domain_tags=('digital',)),
            ),
            local_evidence=RAREvidence(negation_spans=('Not the printed notice',), target_type_hint='document'),
        ),
        expected_outcome=RAROutcome.AMBIGUOUS,
        expected_ambiguous_candidate_ids=('notif_email_body', 'notif_web_portal'),
        description="Excluding the printed notice leaves two digital notice candidates; 'one of the digital ones' is ambiguous.",
    ))

    f.append(RARFixture(
        id='S4B-057', name='Explicit contrast resolving alternative quotation', category='office_contrast',
        turn_text='Reject the Keysight bid and proceed with the alternative quotation.',
        query=RARQuery(
            reference_expression='the alternative quotation',
            candidates=(
                RARCandidate(id='bid_keysight_inst', title='Keysight_Spectral_Analyzer_Quotation.pdf', candidate_type='document', domain_tags=('keysight',)),
                RARCandidate(id='bid_rohde_inst', title='Rohde_Schwarz_Spectral_Analyzer_Quotation.pdf', candidate_type='document', domain_tags=('rohde_schwarz',)),
            ),
            local_evidence=RAREvidence(negation_spans=('Reject the Keysight bid',), recency_hint='other', target_type_hint='document'),
        ),
        expected_outcome=RAROutcome.RESOLVED,
        expected_candidate_id='bid_rohde_inst',
        description="Explicit rejection of Keysight bid resolves 'the alternative quotation' to Rohde & Schwarz bid.",
    ))

    f.append(RARFixture(
        id='S4B-058', name='Correction clarifying dean of students vs dean of academics', category='office_contrast',
        turn_text='Schedule the appointment with the dean of student affairs, not academic affairs.',
        query=RARQuery(
            reference_expression='the dean of student affairs',
            candidates=(
                RARCandidate(id='person_dean_acad', title='Prof. K. R. Sharma (Dean Academic Affairs)', candidate_type='person', domain_tags=('dean', 'academic')),
                RARCandidate(id='person_dean_students', title='Prof. S. C. Sen (Dean Student Affairs)', candidate_type='person', domain_tags=('dean', 'students')),
            ),
            local_evidence=RAREvidence(negation_spans=('not academic affairs',), target_type_hint='person'),
        ),
        expected_outcome=RAROutcome.RESOLVED,
        expected_candidate_id='person_dean_students',
        description='Negation explicitly rejects Dean Academic Affairs; Dean Student Affairs is uniquely resolved.',
    ))

    f.append(RARFixture(
        id='S4B-059', name='Negation over vague query leaving multiple unnegated candidates', category='office_contrast',
        turn_text='Exclude the physics proposal and review the remaining ones.',
        query=RARQuery(
            reference_expression='the remaining ones',
            candidates=(
                RARCandidate(id='prop_physics_lab', title='Physics_Optics_Lab_Upgrade_Proposal.docx', candidate_type='document', domain_tags=('physics',)),
                RARCandidate(id='prop_chem_lab', title='Chemistry_Spectroscopy_Lab_Proposal.docx', candidate_type='document', domain_tags=('chemistry',)),
                RARCandidate(id='prop_math_lab', title='Mathematics_Computing_Cluster_Proposal.docx', candidate_type='document', domain_tags=('math',)),
            ),
            local_evidence=RAREvidence(negation_spans=('Exclude the physics proposal',), target_type_hint='document'),
        ),
        expected_outcome=RAROutcome.AMBIGUOUS,
        expected_ambiguous_candidate_ids=('prop_chem_lab', 'prop_math_lab'),
        description="Excluding physics leaves chemistry and mathematics proposals; 'the remaining ones' represents an ambiguous subset.",
    ))

    f.append(RARFixture(
        id='S4B-060', name='Negation with no matching candidate to exclude', category='office_contrast',
        turn_text="Don't open the medical reimbursement file, open the travel grant file.",
        query=RARQuery(
            reference_expression='the travel grant file',
            candidates=(
                RARCandidate(id='doc_travel_grant', title='International_Conference_Travel_Grant_Application.pdf', candidate_type='document', domain_tags=('travel', 'grant')),
                RARCandidate(id='doc_fellowship_app', title='Postgraduate_Merit_Fellowship_Dossier.pdf', candidate_type='document', domain_tags=('fellowship',)),
            ),
            local_evidence=RAREvidence(negation_spans=("Don't open the medical reimbursement file",), target_type_hint='document'),
        ),
        expected_outcome=RAROutcome.RESOLVED,
        expected_candidate_id='doc_travel_grant',
        description='The negated entity (medical reimbursement) is absent, but the intended referent travel grant is present and matches uniquely.',
    ))

    f.append(RARFixture(
        id='S4B-061', name='Explicit attached document reference', category='office_attachment_relation',
        turn_text='Print the PDF attached to that order.',
        query=RARQuery(
            reference_expression='the PDF attached to that order',
            candidates=(
                RARCandidate(id='doc_order_cover', title='Office_Order_441_Equipment_Condemnation.docx', candidate_type='document'),
                RARCandidate(id='att_survey_sheet', title='Condemnation_Board_Survey_Sheet.pdf', candidate_type='document', is_attachment=True),
            ),
            local_evidence=RAREvidence(target_type_hint='document'),
        ),
        expected_outcome=RAROutcome.RESOLVED,
        expected_candidate_id='att_survey_sheet',
        description="The user requests 'the PDF attached to that order'; only att_survey_sheet is flagged with is_attachment.",
    ))

    f.append(RARFixture(
        id='S4B-062', name='Multiple email attachments causing attachment ambiguity', category='office_attachment_relation',
        turn_text="Forward the attachment from the registrar's email.",
        query=RARQuery(
            reference_expression='the attachment',
            candidates=(
                RARCandidate(id='att_circular_pdf', title='Statutory_Holiday_List_2027.pdf', candidate_type='document', is_attachment=True),
                RARCandidate(id='att_calendar_pdf', title='Academic_Calendar_Draft_2027.pdf', candidate_type='document', is_attachment=True),
                RARCandidate(id='mail_registrar_body', title='Email: Statutory Holidays and Academic Calendar Finalization', candidate_type='email'),
            ),
            local_evidence=RAREvidence(target_type_hint='document'),
        ),
        expected_outcome=RAROutcome.AMBIGUOUS,
        expected_ambiguous_candidate_ids=('att_circular_pdf', 'att_calendar_pdf'),
        description="The registrar's email contains two attached PDFs; 'the attachment' is ambiguous without further descriptor.",
    ))

    f.append(RARFixture(
        id='S4B-063', name="Ownership relation referring to dean's personal recommendation note", category='office_ownership_relation',
        turn_text="Where is the dean's recommendation note?",
        query=RARQuery(
            reference_expression="the dean's recommendation note",
            candidates=(
                RARCandidate(id='note_dean_rec', title='Recommendation_Confidential_Dr_Mehta.docx', candidate_type='document', owner='Dean Academic Affairs'),
                RARCandidate(id='note_hod_rec', title='Recommendation_Confidential_Dr_Mehta.docx', candidate_type='document', owner='Head Chemical Engineering'),
            ),
            local_evidence=RAREvidence(target_type_hint='document'),
        ),
        expected_outcome=RAROutcome.RESOLVED,
        expected_candidate_id='note_dean_rec',
        description="Owner metadata distinguishes note_dean_rec (owned by Dean Academic Affairs) from the HOD's recommendation note.",
    ))

    f.append(RARFixture(
        id='S4B-064', name="Ownership reference to warden's mess inspection log", category='office_ownership_relation',
        turn_text="Pull up the warden's inspection log.",
        query=RARQuery(
            reference_expression="the warden's inspection log",
            candidates=(
                RARCandidate(id='log_warden_mess', title='Mess_Cleanliness_Log_Hostel_4.pdf', candidate_type='document', owner='Chief Warden'),
                RARCandidate(id='log_prefect_mess', title='Mess_Cleanliness_Log_Hostel_4.pdf', candidate_type='document', owner='Student Mess Prefect'),
            ),
            local_evidence=RAREvidence(target_type_hint='document'),
        ),
        expected_outcome=RAROutcome.RESOLVED,
        expected_candidate_id='log_warden_mess',
        description="The owner field cleanly matches 'Chief Warden' for log_warden_mess.",
    ))

    f.append(RARFixture(
        id='S4B-065', name='Ambiguous reference across two equally plausible department circulars', category='office_ambiguous_equal',
        turn_text='Send the circular to all department faculty members.',
        query=RARQuery(
            reference_expression='the circular',
            candidates=(
                RARCandidate(id='circ_dept_eval', title='Continuous_Assessment_Evaluation_Circular.pdf', candidate_type='document', domain_tags=('academic', 'circular')),
                RARCandidate(id='circ_dept_fac', title='Department_Faculty_Meeting_Circular.pdf', candidate_type='document', domain_tags=('meeting', 'circular')),
            ),
            local_evidence=RAREvidence(target_type_hint='document'),
        ),
        expected_outcome=RAROutcome.AMBIGUOUS,
        expected_ambiguous_candidate_ids=('circ_dept_eval', 'circ_dept_fac'),
        description='Two departmental circulars exist with no recency, selection, or specific term distinguishing them.',
    ))

    f.append(RARFixture(
        id='S4B-066', name='Request for absent external accreditation agency dossier', category='office_unknown_absent',
        turn_text='Where is the ABET accreditation self-study questionnaire?',
        query=RARQuery(
            reference_expression='the ABET accreditation self-study questionnaire',
            candidates=(
                RARCandidate(id='doc_naac_ssr', title='NAAC_Self_Study_Report_2025.pdf', candidate_type='document'),
                RARCandidate(id='doc_nba_sar', title='NBA_Self_Assessment_Report_Tier1.pdf', candidate_type='document'),
                RARCandidate(id='doc_nirf_data', title='NIRF_Institutional_Data_Submission.pdf', candidate_type='document'),
            ),
            local_evidence=RAREvidence(target_type_hint='document'),
        ),
        expected_outcome=RAROutcome.UNKNOWN,
        description='The candidate set contains NAAC, NBA, and NIRF documents; the requested ABET accreditation file is absent.',
    ))

    f.append(RARFixture(
        id='S4B-067', name='Unanchored generic pronoun with multiple masculine faculty candidates', category='office_ambiguous_pronoun',
        turn_text='Did he approve the lab equipment procurement?',
        query=RARQuery(
            reference_expression='he',
            candidates=(
                RARCandidate(id='person_prof_gupta', title='Prof. R. C. Gupta (Head of Department)', candidate_type='person'),
                RARCandidate(id='person_prof_iyer', title='Prof. S. K. Iyer (Convener Purchase Committee)', candidate_type='person'),
            ),
            local_evidence=RAREvidence(target_type_hint='person'),
        ),
        expected_outcome=RAROutcome.AMBIGUOUS,
        expected_ambiguous_candidate_ids=('person_prof_gupta', 'person_prof_iyer'),
        description="Unanchored pronoun 'he' is ambiguous between the two male faculty heads present in the context.",
    ))

    f.append(RARFixture(
        id='S4B-068', name='Vague deictic reference to multiple dormitory repair requisitions', category='office_ambiguous_deictic',
        turn_text='Process that one next.',
        query=RARQuery(
            reference_expression='that one',
            candidates=(
                RARCandidate(id='wf_maint_roof', title='Hostel 3 Roof Waterproofing Repair Requisition', candidate_type='workflow'),
                RARCandidate(id='wf_maint_paint', title='Hostel 2 Common Room Painting Requisition', candidate_type='workflow'),
                RARCandidate(id='wf_maint_drain', title='Mess Drainage Clearing Emergency Requisition', candidate_type='workflow'),
            ),
            local_evidence=RAREvidence(target_type_hint='workflow'),
        ),
        expected_outcome=RAROutcome.AMBIGUOUS,
        expected_ambiguous_candidate_ids=('wf_maint_roof', 'wf_maint_paint', 'wf_maint_drain'),
        description="'That one' provides zero distinguishing lexical or structural cues among three plausible maintenance workflows.",
    ))

    f.append(RARFixture(
        id='S4B-069', name='Request for absent faculty appointment order', category='office_unknown_absent',
        turn_text='Forward appointment letter APT-2026-FAC-044 to the registrar.',
        query=RARQuery(
            reference_expression='APT-2026-FAC-044',
            candidates=(
                RARCandidate(id='apt_fac_041', title='Appointment Letter: Assistant Professor Mathematics (APT-041)', candidate_type='document'),
                RARCandidate(id='apt_fac_042', title='Appointment Letter: Assistant Professor Physics (APT-042)', candidate_type='document'),
            ),
            local_evidence=RAREvidence(),
        ),
        expected_outcome=RAROutcome.UNKNOWN,
        description='Appointment reference APT-2026-FAC-044 is not present in the candidate set.',
    ))

    f.append(RARFixture(
        id='S4B-070', name='Ambiguous reference to one of multiple identical vendor invoices', category='office_ambiguous_equal',
        turn_text='Review the invoice.',
        query=RARQuery(
            reference_expression='the invoice',
            candidates=(
                RARCandidate(id='inv_stationery_jan', title='Invoice_Office_Stationery_Jan.pdf', candidate_type='document', domain_tags=('invoice', 'stationery')),
                RARCandidate(id='inv_stationery_feb', title='Invoice_Office_Stationery_Feb.pdf', candidate_type='document', domain_tags=('invoice', 'stationery')),
            ),
            local_evidence=RAREvidence(target_type_hint='document'),
        ),
        expected_outcome=RAROutcome.AMBIGUOUS,
        expected_ambiguous_candidate_ids=('inv_stationery_jan', 'inv_stationery_feb'),
        description="Two stationery invoices exist with identical relevance to 'the invoice'; ambiguous.",
    ))

    f.append(RARFixture(
        id='S4B-071', name='Request for absent external auditor certificate', category='office_unknown_absent',
        turn_text='Check the compliance certificate from the statutory auditor.',
        query=RARQuery(
            reference_expression='the compliance certificate',
            candidates=(
                RARCandidate(id='audit_internal_rep', title='Internal_Financial_Audit_Report_2025.pdf', candidate_type='document'),
                RARCandidate(id='audit_asset_reg', title='Annual_Fixed_Asset_Register.xlsx', candidate_type='spreadsheet'),
            ),
            local_evidence=RAREvidence(target_type_hint='document'),
        ),
        expected_outcome=RAROutcome.UNKNOWN,
        description='The candidate set contains internal audit documents, but no statutory auditor compliance certificate.',
    ))

    f.append(RARFixture(
        id='S4B-072', name='Distinguishing term isolation for physics laboratory technician', category='office_term_discrimination',
        turn_text='Ask the technician to calibrate the spectrometer.',
        query=RARQuery(
            reference_expression='the technician',
            candidates=(
                RARCandidate(id='person_tech_spectro', title='Subhash Pal (Senior Technical Assistant - Spectroscopy Lab)', candidate_type='person', domain_tags=('technician', 'spectroscopy')),
                RARCandidate(id='person_prof_head', title='Prof. D. Sen (Head Department of Physics)', candidate_type='person', domain_tags=('faculty', 'hod')),
            ),
            local_evidence=RAREvidence(target_type_hint='person'),
        ),
        expected_outcome=RAROutcome.RESOLVED,
        expected_candidate_id='person_tech_spectro',
        description="'The technician' discriminates the technical assistant person_tech_spectro from the professor.",
    ))

    f.append(RARFixture(
        id='S4B-073', name='Reference to non-existent campus map file', category='office_unknown_absent',
        turn_text='Open the campus master plan CAD drawing.',
        query=RARQuery(
            reference_expression='the campus master plan CAD drawing',
            candidates=(
                RARCandidate(id='doc_estate_summary', title='Campus_Estate_Building_Area_Summary.pdf', candidate_type='document'),
                RARCandidate(id='doc_boundary_survey', title='Land_Survey_Coordinates_Report.pdf', candidate_type='document'),
            ),
            local_evidence=RAREvidence(target_type_hint='document'),
        ),
        expected_outcome=RAROutcome.UNKNOWN,
        description='No CAD drawing or master plan file is present in the candidate pool.',
    ))

    f.append(RARFixture(
        id='S4B-074', name='Ambiguous reference across two department annual reports', category='office_ambiguous_equal',
        turn_text='Send the annual report to the IQAC director.',
        query=RARQuery(
            reference_expression='the annual report',
            candidates=(
                RARCandidate(id='rep_annual_cse', title='Department_Annual_Report_CSE_2025.pdf', candidate_type='document', domain_tags=('annual_report',)),
                RARCandidate(id='rep_annual_ee', title='Department_Annual_Report_EE_2025.pdf', candidate_type='document', domain_tags=('annual_report',)),
            ),
            local_evidence=RAREvidence(target_type_hint='document'),
        ),
        expected_outcome=RAROutcome.AMBIGUOUS,
        expected_ambiguous_candidate_ids=('rep_annual_cse', 'rep_annual_ee'),
        description="Two department annual reports match 'the annual report' equally without department qualification.",
    ))

    f.append(RARFixture(
        id='S4B-075A', name='Multi-reference 1A: revised fee notice attachment', category='office_multi_reference',
        turn_text='Attach the revised fee notice to the syndicate approval email.',
        query=RARQuery(
            reference_expression='the revised fee notice',
            candidates=(
                RARCandidate(id='notif_fee_orig', title='Tuition_Fee_Revision_Notification.pdf', candidate_type='document', domain_tags=('original',)),
                RARCandidate(id='notif_fee_rev', title='Tuition_Fee_Revision_Notification.pdf', candidate_type='document', domain_tags=('revised',)),
            ),
            local_evidence=RAREvidence(clause_text='Attach the revised fee notice', recency_hint='revised', target_type_hint='document'),
        ),
        expected_outcome=RAROutcome.RESOLVED,
        expected_candidate_id='notif_fee_rev',
        description="First reference of decomposed turn: 'the revised fee notice' uniquely resolves to notif_fee_rev.",
    ))

    f.append(RARFixture(
        id='S4B-075B', name='Multi-reference 1B: syndicate approval email target', category='office_multi_reference',
        turn_text='Attach the revised fee notice to the syndicate approval email.',
        query=RARQuery(
            reference_expression='the syndicate approval email',
            candidates=(
                RARCandidate(id='mail_synd_approval', title='Draft Email: Syndicate Formal Approval of Fee Restructuring', candidate_type='email'),
                RARCandidate(id='mail_finance_query', title='Email: Finance Officer Query on Depreciation', candidate_type='email'),
            ),
            local_evidence=RAREvidence(clause_text='to the syndicate approval email', target_type_hint='email'),
        ),
        expected_outcome=RAROutcome.RESOLVED,
        expected_candidate_id='mail_synd_approval',
        description="Second reference of decomposed turn: 'the syndicate approval email' uniquely matches mail_synd_approval.",
    ))

    f.append(RARFixture(
        id='S4B-076A', name='Multi-reference 2A: candidate degree certificate', category='office_multi_reference',
        turn_text="Verify the candidate's degree certificate and submit the verification report.",
        query=RARQuery(
            reference_expression="the candidate's degree certificate",
            candidates=(
                RARCandidate(id='cert_btech_degree', title='Degree_Certificate_Original_Scan_BTech.pdf', candidate_type='document', domain_tags=('certificate', 'degree')),
                RARCandidate(id='cert_inter_marksheet', title='Intermediate_Marksheet_Verification.pdf', candidate_type='document', domain_tags=('marksheet',)),
            ),
            local_evidence=RAREvidence(clause_text="Verify the candidate's degree certificate", target_type_hint='document'),
        ),
        expected_outcome=RAROutcome.RESOLVED,
        expected_candidate_id='cert_btech_degree',
        description="First reference of decomposed turn: 'the candidate's degree certificate' resolves to cert_btech_degree.",
    ))

    f.append(RARFixture(
        id='S4B-076B', name='Multi-reference 2B: verification report workflow', category='office_multi_reference',
        turn_text="Verify the candidate's degree certificate and submit the verification report.",
        query=RARQuery(
            reference_expression='the verification report',
            candidates=(
                RARCandidate(id='doc_verif_report_draft', title='Credential_Verification_Report_Form.docx', candidate_type='document', domain_tags=('verification_report',)),
                RARCandidate(id='doc_police_verif', title='Police_Character_Verification_Report.pdf', candidate_type='document', domain_tags=('police',)),
            ),
            local_evidence=RAREvidence(clause_text='and submit the verification report', target_type_hint='document'),
        ),
        expected_outcome=RAROutcome.RESOLVED,
        expected_candidate_id='doc_verif_report_draft',
        description="Second reference of decomposed turn: 'the verification report' selects doc_verif_report_draft.",
    ))

    f.append(RARFixture(
        id='S4B-077A', name='Multi-reference 3A: hostel allotment list', category='office_multi_reference',
        turn_text="Compare the hostel allotment list with the warden's room allocation register.",
        query=RARQuery(
            reference_expression='the hostel allotment list',
            candidates=(
                RARCandidate(id='sheet_allot_list', title='Hostel_5_Room_Allotment_List_Final.xlsx', candidate_type='spreadsheet'),
                RARCandidate(id='sheet_mess_dues', title='Hostel_5_Mess_Dues_Pending.xlsx', candidate_type='spreadsheet'),
            ),
            local_evidence=RAREvidence(clause_text='Compare the hostel allotment list', target_type_hint='spreadsheet'),
        ),
        expected_outcome=RAROutcome.RESOLVED,
        expected_candidate_id='sheet_allot_list',
        description="First reference of decomposed turn: 'the hostel allotment list' binds to sheet_allot_list.",
    ))

    f.append(RARFixture(
        id='S4B-077B', name='Multi-reference 3B: room allocation register', category='office_multi_reference',
        turn_text="Compare the hostel allotment list with the warden's room allocation register.",
        query=RARQuery(
            reference_expression="the warden's room allocation register",
            candidates=(
                RARCandidate(id='reg_warden_alloc', title='Warden_Physical_Room_Allocation_Register.pdf', candidate_type='document', owner='Chief Warden'),
                RARCandidate(id='reg_estate_keys', title='Estate_Office_Key_Issue_Register.pdf', candidate_type='document', owner='Estate Officer'),
            ),
            local_evidence=RAREvidence(clause_text="with the warden's room allocation register", target_type_hint='document'),
        ),
        expected_outcome=RAROutcome.RESOLVED,
        expected_candidate_id='reg_warden_alloc',
        description="Second reference of decomposed turn: 'the warden's room allocation register' matches reg_warden_alloc.",
    ))

    f.append(RARFixture(
        id='S4B-081', name='Sprint planning board card reference', category='work_project_management',
        turn_text='Move the authentication refactor ticket to in progress.',
        query=RARQuery(
            reference_expression='the authentication refactor ticket',
            candidates=(
                RARCandidate(id='tkt_auth_refactor', title='PROJ-108: OAuth2 and Session Refactor', candidate_type='workflow', domain_tags=('auth', 'backend')),
                RARCandidate(id='tkt_ui_dashboard', title='PROJ-109: Analytics Dashboard Redesign', candidate_type='workflow', domain_tags=('ui', 'frontend')),
                RARCandidate(id='tkt_db_migration', title='PROJ-110: Postgres 16 Version Upgrade', candidate_type='workflow', domain_tags=('database', 'devops')),
            ),
            local_evidence=RAREvidence(target_type_hint='workflow'),
        ),
        expected_outcome=RAROutcome.RESOLVED,
        expected_candidate_id='tkt_auth_refactor',
        description="'The authentication refactor ticket' matches PROJ-108 OAuth2 and session refactor.",
    ))

    f.append(RARFixture(
        id='S4B-082', name='Client quarterly business review slide deck', category='work_presentation',
        turn_text='Open the Q3 client presentation deck.',
        query=RARQuery(
            reference_expression='the Q3 client presentation deck',
            candidates=(
                RARCandidate(id='deck_q3_client', title='Acme_Corp_Q3_Business_Review.pptx', candidate_type='presentation', domain_tags=('q3', 'client')),
                RARCandidate(id='deck_internal_allhands', title='Engineering_All_Hands_Q3.pptx', candidate_type='presentation', domain_tags=('q3', 'internal')),
                RARCandidate(id='sheet_q3_revenue', title='Q3_Revenue_Forecast_Model.xlsx', candidate_type='spreadsheet', domain_tags=('q3', 'finance')),
            ),
            local_evidence=RAREvidence(target_type_hint='presentation'),
        ),
        expected_outcome=RAROutcome.RESOLVED,
        expected_candidate_id='deck_q3_client',
        description="Target type presentation combined with 'client' uniquely resolves deck_q3_client.",
    ))

    f.append(RARFixture(
        id='S4B-083', name='Architecture decision record identifier reference', category='work_engineering_docs',
        turn_text='Review ADR-0024 regarding our event streaming broker choice.',
        query=RARQuery(
            reference_expression='ADR-0024',
            candidates=(
                RARCandidate(id='adr_0024', title='ADR-0024_Kafka_vs_Pulsar_Evaluation.md', candidate_type='document', exact_aliases=('ADR-0024',)),
                RARCandidate(id='adr_0025', title='ADR-0025_Schema_Registry_Protobuf.md', candidate_type='document', exact_aliases=('ADR-0025',)),
            ),
            local_evidence=RAREvidence(),
            deterministic_anchor=RARDeterministicAnchor(exact_id='adr_0024'),
        ),
        expected_outcome=RAROutcome.RESOLVED,
        expected_candidate_id='adr_0024',
        description='Exact architectural identifier ADR-0024 maps unambiguously to adr_0024.',
    ))

    f.append(RARFixture(
        id='S4B-084', name='Shared team sprint retrospective notes document', category='work_meeting_notes',
        turn_text='Add an action item to the retro notes.',
        query=RARQuery(
            reference_expression='the retro notes',
            candidates=(
                RARCandidate(id='doc_retro_sprint_14', title='Sprint_14_Retrospective_Action_Items.docx', candidate_type='document', domain_tags=('retrospective', 'notes')),
                RARCandidate(id='doc_planning_sprint_15', title='Sprint_15_Planning_Goals.docx', candidate_type='document', domain_tags=('planning',)),
            ),
            local_evidence=RAREvidence(target_type_hint='document'),
        ),
        expected_outcome=RAROutcome.RESOLVED,
        expected_candidate_id='doc_retro_sprint_14',
        description="'The retro notes' corresponds cleanly to doc_retro_sprint_14.",
    ))

    f.append(RARFixture(
        id='S4B-085', name='Ambiguous reference across two product roadmap drafts', category='work_ambiguous_drafts',
        turn_text='Share the roadmap draft with marketing.',
        query=RARQuery(
            reference_expression='the roadmap draft',
            candidates=(
                RARCandidate(id='doc_roadmap_mobile', title='Mobile_App_Product_Roadmap_H2.docx', candidate_type='document', domain_tags=('roadmap', 'draft')),
                RARCandidate(id='doc_roadmap_web', title='Web_Platform_Product_Roadmap_H2.docx', candidate_type='document', domain_tags=('roadmap', 'draft')),
            ),
            local_evidence=RAREvidence(target_type_hint='document'),
        ),
        expected_outcome=RAROutcome.AMBIGUOUS,
        expected_ambiguous_candidate_ids=('doc_roadmap_mobile', 'doc_roadmap_web'),
        description="Both mobile and web roadmap drafts match 'the roadmap draft' with no differentiator.",
    ))

    f.append(RARFixture(
        id='S4B-086', name='Customer discovery call audio recording', category='work_media_interview',
        turn_text='Transcribe the customer interview recording from yesterday.',
        query=RARQuery(
            reference_expression='the customer interview recording',
            candidates=(
                RARCandidate(id='media_interview_fintech', title='User_Research_Call_Fintech_Lead.m4a', candidate_type='media', domain_tags=('interview', 'recording')),
                RARCandidate(id='doc_interview_notes', title='User_Research_Synthesized_Notes.docx', candidate_type='document'),
            ),
            local_evidence=RAREvidence(target_type_hint='media'),
        ),
        expected_outcome=RAROutcome.RESOLVED,
        expected_candidate_id='media_interview_fintech',
        description="Type media combined with 'interview recording' isolates the audio recording candidate.",
    ))

    f.append(RARFixture(
        id='S4B-087', name='Request for absent competitor benchmark matrix', category='work_unknown_absent',
        turn_text='Where is the Gartner Magic Quadrant competitor matrix?',
        query=RARQuery(
            reference_expression='the Gartner Magic Quadrant competitor matrix',
            candidates=(
                RARCandidate(id='sheet_pricing_matrix', title='Internal_Tiered_Pricing_Matrix.xlsx', candidate_type='spreadsheet'),
                RARCandidate(id='doc_feature_checklist', title='Product_Feature_Checklist_Q2.docx', candidate_type='document'),
            ),
            local_evidence=RAREvidence(target_type_hint='spreadsheet'),
        ),
        expected_outcome=RAROutcome.UNKNOWN,
        description='The requested Gartner competitor analysis matrix is not present in the candidate pool.',
    ))

    f.append(RARFixture(
        id='S4B-088', name='Active UI selected pull request in review dashboard', category='work_ui_anchor',
        turn_text='Approve this pull request and leave a comment to merge after CI passes.',
        query=RARQuery(
            reference_expression='this pull request',
            candidates=(
                RARCandidate(id='pr_512_caching', title='PR #512: Implement Redis Cluster Session Store', candidate_type='workflow'),
                RARCandidate(id='pr_513_metrics', title='PR #513: Add Prometheus Latency Histograms', candidate_type='workflow'),
            ),
            local_evidence=RAREvidence(),
            deterministic_anchor=RARDeterministicAnchor(selected_ui_id='pr_512_caching'),
        ),
        expected_outcome=RAROutcome.RESOLVED,
        expected_candidate_id='pr_512_caching',
        description="The active UI selection anchor resolves 'this pull request' to PR #512.",
    ))

    f.append(RARFixture(
        id='S4B-089', name='Latest project budget financial forecast model', category='work_temporal_latest',
        turn_text='Open the latest financial projection model.',
        query=RARQuery(
            reference_expression='the latest financial projection model',
            candidates=(
                RARCandidate(id='sheet_model_v4', title='Project_Titan_Financial_Model.xlsx', candidate_type='spreadsheet'),
                RARCandidate(id='sheet_model_v3', title='Project_Titan_Financial_Model.xlsx', candidate_type='spreadsheet', recency_rank=1),
                RARCandidate(id='sheet_model_v2', title='Project_Titan_Financial_Model.xlsx', candidate_type='spreadsheet', recency_rank=2),
            ),
            local_evidence=RAREvidence(recency_hint='latest', target_type_hint='spreadsheet'),
        ),
        expected_outcome=RAROutcome.RESOLVED,
        expected_candidate_id='sheet_model_v4',
        description="'The latest' with recency_rank 0 uniquely resolves sheet_model_v4 among identically-titled models.",
    ))

    f.append(RARFixture(
        id='S4B-090', name='Contrastive selection between design mockups', category='work_contrast',
        turn_text='Not the dark theme mockup, show the client the other mockup.',
        query=RARQuery(
            reference_expression='the other mockup',
            candidates=(
                RARCandidate(id='fig_mock_dark', title='Mobile_Home_Screen_Dark_Theme.png', candidate_type='media', domain_tags=('dark', 'mockup')),
                RARCandidate(id='fig_mock_light', title='Mobile_Home_Screen_Light_Theme.png', candidate_type='media', domain_tags=('light', 'mockup')),
            ),
            local_evidence=RAREvidence(negation_spans=('Not the dark theme mockup',), recency_hint='other', target_type_hint='media'),
        ),
        expected_outcome=RAROutcome.RESOLVED,
        expected_candidate_id='fig_mock_light',
        description="Negation explicitly rejects the dark theme; 'the other mockup' resolves to the light theme.",
    ))

    f.append(RARFixture(
        id='S4B-091', name='Engineering postmortem document shortened reference', category='work_shortened_name',
        turn_text='Email the postmortem to the incident response channel.',
        query=RARQuery(
            reference_expression='the postmortem',
            candidates=(
                RARCandidate(id='doc_postmortem_outage', title='Postmortem_Payment_Gateway_Outage_March.docx', candidate_type='document', domain_tags=('postmortem', 'incident')),
                RARCandidate(id='doc_runbook_deploy', title='Deployment_Rollback_Runbook.md', candidate_type='document'),
            ),
            local_evidence=RAREvidence(target_type_hint='document'),
        ),
        expected_outcome=RAROutcome.RESOLVED,
        expected_candidate_id='doc_postmortem_outage',
        description="'The postmortem' unambiguously identifies the incident postmortem document.",
    ))

    f.append(RARFixture(
        id='S4B-092', name='Ambiguous reference across two customer contracts', category='work_ambiguous_contracts',
        turn_text='Check the liability clause in the contract.',
        query=RARQuery(
            reference_expression='the contract',
            candidates=(
                RARCandidate(id='doc_contract_apex', title='Master_Services_Agreement_Apex_Systems.pdf', candidate_type='document', domain_tags=('contract',)),
                RARCandidate(id='doc_contract_zenith', title='Master_Services_Agreement_Zenith_Media.pdf', candidate_type='document', domain_tags=('contract',)),
            ),
            local_evidence=RAREvidence(target_type_hint='document'),
        ),
        expected_outcome=RAROutcome.AMBIGUOUS,
        expected_ambiguous_candidate_ids=('doc_contract_apex', 'doc_contract_zenith'),
        description="Two client MSA contracts exist; without naming Apex or Zenith, 'the contract' is ambiguous.",
    ))

    f.append(RARFixture(
        id='S4B-093', name='Current attachment in email client composition window', category='work_attachment_anchor',
        turn_text='Send this attachment to the legal counsel.',
        query=RARQuery(
            reference_expression='this attachment',
            candidates=(
                RARCandidate(id='att_nda_draft', title='Mutual_Non_Disclosure_Agreement_Draft.docx', candidate_type='document', is_attachment=True),
                RARCandidate(id='doc_nda_template', title='Standard_Company_NDA_Template.docx', candidate_type='document'),
            ),
            local_evidence=RAREvidence(),
            deterministic_anchor=RARDeterministicAnchor(current_attachment_id='att_nda_draft'),
        ),
        expected_outcome=RAROutcome.RESOLVED,
        expected_candidate_id='att_nda_draft',
        description="Active attachment anchor links 'this attachment' to the attached draft NDA.",
    ))

    f.append(RARFixture(
        id='S4B-094', name='Request for absent Kubernetes deployment manifest', category='work_unknown_absent',
        turn_text='Apply the Redis production statefulset YAML.',
        query=RARQuery(
            reference_expression='the Redis production statefulset YAML',
            candidates=(
                RARCandidate(id='cfg_k8s_api', title='production-api-deployment.yaml', candidate_type='document'),
                RARCandidate(id='cfg_k8s_worker', title='production-worker-deployment.yaml', candidate_type='document'),
            ),
            local_evidence=RAREvidence(target_type_hint='document'),
        ),
        expected_outcome=RAROutcome.UNKNOWN,
        description='The candidate set contains API and worker deployment manifests, but the Redis statefulset is absent.',
    ))

    f.append(RARFixture(
        id='S4B-095', name='Continuation reference to recently discussed project brief', category='work_active_pointer',
        turn_text='Share the same project brief with the onboarding contractor.',
        query=RARQuery(
            reference_expression='the same project brief',
            candidates=(
                RARCandidate(id='doc_brief_falcon', title='Project_Falcon_Executive_Brief.docx', candidate_type='document', domain_tags=('recently_discussed',)),
                RARCandidate(id='doc_brief_orion', title='Project_Orion_Executive_Brief.docx', candidate_type='document', recency_rank=3),
            ),
            local_evidence=RAREvidence(recency_hint='same', target_type_hint='document'),
        ),
        expected_outcome=RAROutcome.RESOLVED,
        expected_candidate_id='doc_brief_falcon',
        description="'The same project brief' binds to the recently discussed Project Falcon brief.",
    ))

    f.append(RARFixture(
        id='S4B-096', name='Revised product requirements specification document', category='work_revision_relation',
        turn_text='Review the revised spec with the front-end engineering lead.',
        query=RARQuery(
            reference_expression='the revised spec',
            candidates=(
                RARCandidate(id='prd_checkout_orig', title='PRD_One_Click_Checkout.docx', candidate_type='document', domain_tags=('original',)),
                RARCandidate(id='prd_checkout_rev', title='PRD_One_Click_Checkout.docx', candidate_type='document', domain_tags=('revised',)),
            ),
            local_evidence=RAREvidence(recency_hint='revised', target_type_hint='document'),
        ),
        expected_outcome=RAROutcome.RESOLVED,
        expected_candidate_id='prd_checkout_rev',
        description="'The revised spec' targets the revised version of the checkout PRD.",
    ))

    f.append(RARFixture(
        id='S4B-097', name='Ambiguous reference across two sales pipeline spreadsheets', category='work_ambiguous_sheets',
        turn_text='Export the sales pipeline numbers.',
        query=RARQuery(
            reference_expression='the sales pipeline',
            candidates=(
                RARCandidate(id='sheet_pipeline_us', title='Enterprise_Sales_Pipeline_North_America.xlsx', candidate_type='spreadsheet'),
                RARCandidate(id='sheet_pipeline_eu', title='Enterprise_Sales_Pipeline_EMEA.xlsx', candidate_type='spreadsheet'),
            ),
            local_evidence=RAREvidence(target_type_hint='spreadsheet'),
        ),
        expected_outcome=RAROutcome.AMBIGUOUS,
        expected_ambiguous_candidate_ids=('sheet_pipeline_us', 'sheet_pipeline_eu'),
        description="Two regional sales pipeline spreadsheets match 'the sales pipeline'; ambiguous.",
    ))

    f.append(RARFixture(
        id='S4B-098', name='Employee performance review dossier by manager', category='work_ownership_relation',
        turn_text="Pull up Sarah's appraisal review.",
        query=RARQuery(
            reference_expression="Sarah's appraisal review",
            candidates=(
                RARCandidate(id='doc_eval_sarah', title='Annual_Performance_Appraisal_2025.docx', candidate_type='document', owner='Sarah Jenkins'),
                RARCandidate(id='doc_eval_marcus', title='Annual_Performance_Appraisal_2025.docx', candidate_type='document', owner='Marcus Vance'),
            ),
            local_evidence=RAREvidence(target_type_hint='document'),
        ),
        expected_outcome=RAROutcome.RESOLVED,
        expected_candidate_id='doc_eval_sarah',
        description="Owner metadata matches 'Sarah Jenkins' for doc_eval_sarah.",
    ))

    f.append(RARFixture(
        id='S4B-099', name='Generic deictic reference to project tickets', category='work_ambiguous_deictic',
        turn_text='Assign it to the release engineer.',
        query=RARQuery(
            reference_expression='it',
            candidates=(
                RARCandidate(id='tkt_bug_gateway', title='Bug 809: Payment Gateway Timeout on Checkout', candidate_type='workflow'),
                RARCandidate(id='tkt_bug_webhook', title='Bug 810: Stripe Webhook Dropping Payload', candidate_type='workflow'),
            ),
            local_evidence=RAREvidence(target_type_hint='workflow'),
        ),
        expected_outcome=RAROutcome.AMBIGUOUS,
        expected_ambiguous_candidate_ids=('tkt_bug_gateway', 'tkt_bug_webhook'),
        description="Unanchored pronoun 'it' between two active bug tickets in the queue is ambiguous.",
    ))

    f.append(RARFixture(
        id='S4B-100', name='Single person entity distinction for VP of Engineering', category='work_person_entity',
        turn_text='Send the weekly executive summary to Alex.',
        query=RARQuery(
            reference_expression='Alex',
            candidates=(
                RARCandidate(id='person_alex_vp', title='Alex Rivera (VP of Engineering)', candidate_type='person'),
                RARCandidate(id='doc_alex_notes', title='Alex_Rivera_1on1_Notes.md', candidate_type='document'),
            ),
            local_evidence=RAREvidence(target_type_hint='person'),
        ),
        expected_outcome=RAROutcome.RESOLVED,
        expected_candidate_id='person_alex_vp',
        description="The reference 'Alex' as a person entity isolates Alex Rivera from his 1-on-1 meeting notes file.",
    ))

    f.append(RARFixture(
        id='S4B-101A', name='Work multi-ref 1A: revenue dashboard', category='work_multi_reference',
        turn_text='Export the customer revenue dashboard and email it to the product manager.',
        query=RARQuery(
            reference_expression='the customer revenue dashboard',
            candidates=(
                RARCandidate(id='doc_dash_rev', title='SaaS_Customer_Revenue_Dashboard.pdf', candidate_type='document', domain_tags=('revenue', 'dashboard')),
                RARCandidate(id='doc_dash_usage', title='Platform_API_Usage_Dashboard.pdf', candidate_type='document', domain_tags=('usage',)),
            ),
            local_evidence=RAREvidence(clause_text='Export the customer revenue dashboard', target_type_hint='document'),
        ),
        expected_outcome=RAROutcome.RESOLVED,
        expected_candidate_id='doc_dash_rev',
        description='First reference in decomposed turn: matches SaaS customer revenue dashboard.',
    ))

    f.append(RARFixture(
        id='S4B-101B', name='Work multi-ref 1B: product manager person recipient', category='work_multi_reference',
        turn_text='Export the customer revenue dashboard and email it to the product manager.',
        query=RARQuery(
            reference_expression='the product manager',
            candidates=(
                RARCandidate(id='person_pm_elena', title='Elena Rostova (Lead Product Manager)', candidate_type='person'),
                RARCandidate(id='person_em_david', title='David Chen (Engineering Manager)', candidate_type='person'),
            ),
            local_evidence=RAREvidence(clause_text='and email it to the product manager', target_type_hint='person'),
        ),
        expected_outcome=RAROutcome.RESOLVED,
        expected_candidate_id='person_pm_elena',
        description='Second reference in decomposed turn: matches lead product manager Elena Rostova.',
    ))

    f.append(RARFixture(
        id='S4B-102A', name='Work multi-ref 2A: architecture proposal', category='work_multi_reference',
        turn_text='Review the architecture proposal and compare it with the previous RFC.',
        query=RARQuery(
            reference_expression='the architecture proposal',
            candidates=(
                RARCandidate(id='doc_prop_mesh', title='Service_Mesh_Migration_Proposal.docx', candidate_type='document', domain_tags=('architecture', 'proposal')),
                RARCandidate(id='doc_prop_hiring', title='Q4_Engineering_Hiring_Plan.docx', candidate_type='document', domain_tags=('hiring',)),
            ),
            local_evidence=RAREvidence(clause_text='Review the architecture proposal', target_type_hint='document'),
        ),
        expected_outcome=RAROutcome.RESOLVED,
        expected_candidate_id='doc_prop_mesh',
        description='First reference: matches service mesh migration architecture proposal.',
    ))

    f.append(RARFixture(
        id='S4B-102B', name='Work multi-ref 2B: previous RFC document', category='work_multi_reference',
        turn_text='Review the architecture proposal and compare it with the previous RFC.',
        query=RARQuery(
            reference_expression='the previous RFC',
            candidates=(
                RARCandidate(id='rfc_mesh_v2', title='RFC-104: Service Mesh Evaluation.md', candidate_type='document'),
                RARCandidate(id='rfc_mesh_v1', title='RFC-104: Service Mesh Evaluation.md', candidate_type='document', recency_rank=1),
            ),
            local_evidence=RAREvidence(clause_text='compare it with the previous RFC', recency_hint='previous', target_type_hint='document'),
        ),
        expected_outcome=RAROutcome.RESOLVED,
        expected_candidate_id='rfc_mesh_v1',
        description='Second reference: targets the previous version (recency_rank 1) of RFC-104.',
    ))

    f.append(RARFixture(
        id='S4B-103', name='Work brand style guide verbatim title', category='work_verbatim_title',
        turn_text='Download Brand_Identity_Guidelines_2026.pdf.',
        query=RARQuery(
            reference_expression='Brand_Identity_Guidelines_2026.pdf',
            candidates=(
                RARCandidate(id='doc_brand_guide', title='Brand_Identity_Guidelines_2026.pdf', candidate_type='document'),
                RARCandidate(id='doc_brand_assets', title='Brand_Logo_Vector_Pack.zip', candidate_type='document'),
            ),
            local_evidence=RAREvidence(),
        ),
        expected_outcome=RAROutcome.RESOLVED,
        expected_candidate_id='doc_brand_guide',
        description='Verbatim title matches brand identity guidelines PDF.',
    ))

    f.append(RARFixture(
        id='S4B-106', name='Utility electricity bill reference', category='personal_bill_utility',
        turn_text='Pay the electricity bill before the due date tomorrow.',
        query=RARQuery(
            reference_expression='the electricity bill',
            candidates=(
                RARCandidate(id='bill_tneb_power', title='TNEB_Electricity_Bill_March_2026.pdf', candidate_type='document', domain_tags=('electricity', 'utility')),
                RARCandidate(id='bill_airtel_broadband', title='Airtel_Fiber_Broadband_Invoice.pdf', candidate_type='document', domain_tags=('internet', 'telecom')),
                RARCandidate(id='bill_piped_gas', title='Adani_Total_Gas_Domestic_Bill.pdf', candidate_type='document', domain_tags=('gas', 'utility')),
            ),
            local_evidence=RAREvidence(target_type_hint='document'),
        ),
        expected_outcome=RAROutcome.RESOLVED,
        expected_candidate_id='bill_tneb_power',
        description="'The electricity bill' matches the TNEB electricity bill document uniquely.",
    ))

    f.append(RARFixture(
        id='S4B-107', name='Flight e-ticket booking confirmation alias match', category='personal_travel_ticket',
        turn_text='Check the boarding gate on PNR-6E-9912.',
        query=RARQuery(
            reference_expression='PNR-6E-9912',
            candidates=(
                RARCandidate(id='tkt_indigo_blr_del', title='IndiGo Flight Ticket BLR to DEL (PNR 6E-9912)', candidate_type='document', exact_aliases=('PNR-6E-9912',)),
                RARCandidate(id='tkt_airindia_del_lhr', title='Air India Ticket DEL to LHR (PNR AI-4011)', candidate_type='document', exact_aliases=('PNR-AI-4011',)),
            ),
            local_evidence=RAREvidence(),
            deterministic_anchor=RARDeterministicAnchor(exact_id='tkt_indigo_blr_del'),
        ),
        expected_outcome=RAROutcome.RESOLVED,
        expected_candidate_id='tkt_indigo_blr_del',
        description='Booking PNR reference matches the IndiGo flight ticket.',
    ))

    f.append(RARFixture(
        id='S4B-108', name='Household medical prescription shortened reference', category='personal_health',
        turn_text="Order the medicines listed in mother's prescription.",
        query=RARQuery(
            reference_expression="mother's prescription",
            candidates=(
                RARCandidate(id='rx_dr_sen_mother', title='Dr_Sen_Cardiology_Prescription_Mother.pdf', candidate_type='document', owner='Mother'),
                RARCandidate(id='rx_dr_mehta_self', title='Dr_Mehta_Dental_Prescription_Self.pdf', candidate_type='document', owner='Self'),
            ),
            local_evidence=RAREvidence(target_type_hint='document'),
        ),
        expected_outcome=RAROutcome.RESOLVED,
        expected_candidate_id='rx_dr_sen_mother',
        description="Owner metadata matches 'Mother' for cardiology prescription rx_dr_sen_mother.",
    ))

    f.append(RARFixture(
        id='S4B-109', name='Ambiguous reference across two grocery purchase receipts', category='personal_ambiguous_receipts',
        turn_text='Add the total from the grocery receipt to our expense sheet.',
        query=RARQuery(
            reference_expression='the grocery receipt',
            candidates=(
                RARCandidate(id='rec_blinkit_groceries', title='Blinkit_Grocery_Order_Receipt_14March.pdf', candidate_type='document', domain_tags=('grocery', 'receipt')),
                RARCandidate(id='rec_instamart_groceries', title='Swiggy_Instamart_Receipt_12March.pdf', candidate_type='document', domain_tags=('grocery', 'receipt')),
            ),
            local_evidence=RAREvidence(target_type_hint='document'),
        ),
        expected_outcome=RAROutcome.AMBIGUOUS,
        expected_ambiguous_candidate_ids=('rec_blinkit_groceries', 'rec_instamart_groceries'),
        description="Two grocery receipts match 'the grocery receipt' without store or date qualification; ambiguous.",
    ))

    f.append(RARFixture(
        id='S4B-110', name='Request for absent passport renewal acknowledgment', category='personal_unknown_absent',
        turn_text='Check the dispatch status on the passport renewal slip.',
        query=RARQuery(
            reference_expression='the passport renewal slip',
            candidates=(
                RARCandidate(id='doc_aadhaar_card', title='E_Aadhaar_Card_Masked_2025.pdf', candidate_type='document'),
                RARCandidate(id='doc_pan_card', title='PAN_Card_Digital_Copy.pdf', candidate_type='document'),
                RARCandidate(id='doc_voter_id', title='Voter_Identity_Card_Scan.pdf', candidate_type='document'),
            ),
            local_evidence=RAREvidence(target_type_hint='document'),
        ),
        expected_outcome=RAROutcome.UNKNOWN,
        description='The candidate set contains government ID cards, but no passport renewal acknowledgment slip.',
    ))

    f.append(RARFixture(
        id='S4B-111', name='Family vacation hotel booking confirmation PDF', category='personal_travel_hotel',
        turn_text='What is the check-in time on the hotel booking voucher?',
        query=RARQuery(
            reference_expression='the hotel booking voucher',
            candidates=(
                RARCandidate(id='res_taj_hotel', title='Taj_Exotica_Goa_Booking_Confirmation.pdf', candidate_type='document', domain_tags=('hotel', 'travel')),
                RARCandidate(id='res_zoomcar', title='Zoomcar_Rental_Agreement_Goa.pdf', candidate_type='document', domain_tags=('car', 'travel')),
            ),
            local_evidence=RAREvidence(target_type_hint='document'),
        ),
        expected_outcome=RAROutcome.RESOLVED,
        expected_candidate_id='res_taj_hotel',
        description="'The hotel booking voucher' uniquely isolates res_taj_hotel from the car rental agreement.",
    ))

    f.append(RARFixture(
        id='S4B-112', name='Latest apartment maintenance payment receipt', category='personal_temporal_latest',
        turn_text='Find the latest apartment maintenance receipt.',
        query=RARQuery(
            reference_expression='the latest apartment maintenance receipt',
            candidates=(
                RARCandidate(id='rec_maint_feb2026', title='Apartment_Society_Maintenance_Receipt.pdf', candidate_type='document'),
                RARCandidate(id='rec_maint_jan2026', title='Apartment_Society_Maintenance_Receipt.pdf', candidate_type='document', recency_rank=1),
                RARCandidate(id='rec_maint_dec2025', title='Apartment_Society_Maintenance_Receipt.pdf', candidate_type='document', recency_rank=2),
            ),
            local_evidence=RAREvidence(recency_hint='latest', target_type_hint='document'),
        ),
        expected_outcome=RAROutcome.RESOLVED,
        expected_candidate_id='rec_maint_feb2026',
        description="'The latest' with recency_rank 0 identifies the most recent apartment maintenance receipt.",
    ))

    f.append(RARFixture(
        id='S4B-113', name='Contrastive selection between car and health insurance policies', category='personal_contrast',
        turn_text='Not the car insurance, pull up the health insurance policy.',
        query=RARQuery(
            reference_expression='the health insurance policy',
            candidates=(
                RARCandidate(id='pol_hdfc_ergo_car', title='HDFC_ERGO_Car_Comprehensive_Insurance.pdf', candidate_type='document', domain_tags=('car', 'insurance')),
                RARCandidate(id='pol_star_health', title='Star_Health_Family_Optima_Policy.pdf', candidate_type='document', domain_tags=('health', 'insurance')),
            ),
            local_evidence=RAREvidence(negation_spans=('Not the car insurance',), target_type_hint='document'),
        ),
        expected_outcome=RAROutcome.RESOLVED,
        expected_candidate_id='pol_star_health',
        description='Negation explicitly rejects car insurance; health insurance resolves to pol_star_health.',
    ))

    f.append(RARFixture(
        id='S4B-114', name='Personal gym subscription reminder active UI selection', category='personal_ui_anchor',
        turn_text='Snooze this reminder until Saturday morning.',
        query=RARQuery(
            reference_expression='this reminder',
            candidates=(
                RARCandidate(id='rem_gym_renewal', title='Reminder: Cult.fit Gym Membership Annual Renewal', candidate_type='workflow'),
                RARCandidate(id='rem_dentist_visit', title='Reminder: Dentist Scaling Appointment', candidate_type='workflow'),
            ),
            local_evidence=RAREvidence(),
            deterministic_anchor=RARDeterministicAnchor(selected_ui_id='rem_gym_renewal'),
        ),
        expected_outcome=RAROutcome.RESOLVED,
        expected_candidate_id='rem_gym_renewal',
        description="Selected UI anchor binds 'this reminder' to the gym membership renewal notification.",
    ))

    f.append(RARFixture(
        id='S4B-115', name='Request for absent dog veterinary immunization booklet', category='personal_unknown_absent',
        turn_text="Where did we save Max's rabies vaccination certificate?",
        query=RARQuery(
            reference_expression="Max's rabies vaccination certificate",
            candidates=(
                RARCandidate(id='doc_home_deed', title='Apartment_Sale_Deed_Registered.pdf', candidate_type='document'),
                RARCandidate(id='doc_property_tax', title='Property_Tax_Challan_2025_2026.pdf', candidate_type='document'),
            ),
            local_evidence=RAREvidence(target_type_hint='document'),
        ),
        expected_outcome=RAROutcome.UNKNOWN,
        description='The candidate set contains property records; the pet vaccination certificate is absent.',
    ))

    f.append(RARFixture(
        id='S4B-116', name='Active photo attachment in personal chat conversation', category='personal_attachment_anchor',
        turn_text='Save this photo to our family vacation album.',
        query=RARQuery(
            reference_expression='this photo',
            candidates=(
                RARCandidate(id='pic_beach_sunset', title='Goa_Beach_Sunset_Family.jpg', candidate_type='media', is_attachment=True),
                RARCandidate(id='doc_itinerary', title='Goa_Trip_Itinerary_Plan.pdf', candidate_type='document'),
            ),
            local_evidence=RAREvidence(),
            deterministic_anchor=RARDeterministicAnchor(current_attachment_id='pic_beach_sunset'),
        ),
        expected_outcome=RAROutcome.RESOLVED,
        expected_candidate_id='pic_beach_sunset',
        description='Current attachment anchor points directly to the JPEG photo attachment.',
    ))

    f.append(RARFixture(
        id='S4B-117', name='Ambiguous reference across two personal credit card statements', category='personal_ambiguous_statements',
        turn_text='Check the reward points on the credit card statement.',
        query=RARQuery(
            reference_expression='the credit card statement',
            candidates=(
                RARCandidate(id='stmt_icici_amazon', title='ICICI_Amazon_Pay_Card_Statement_Feb.pdf', candidate_type='document', domain_tags=('credit_card', 'statement')),
                RARCandidate(id='stmt_hdfc_regalia', title='HDFC_Regalia_Card_Statement_Feb.pdf', candidate_type='document', domain_tags=('credit_card', 'statement')),
            ),
            local_evidence=RAREvidence(target_type_hint='document'),
        ),
        expected_outcome=RAROutcome.AMBIGUOUS,
        expected_ambiguous_candidate_ids=('stmt_icici_amazon', 'stmt_hdfc_regalia'),
        description='Two credit card statements exist for the same month; ambiguous without bank or card name.',
    ))

    f.append(RARFixture(
        id='S4B-118', name='Previous version of home renovation budget estimate', category='personal_temporal_previous',
        turn_text='Show me the previous estimate from the carpenter.',
        query=RARQuery(
            reference_expression='the previous estimate',
            candidates=(
                RARCandidate(id='est_carpenter_v2', title='Modular_Kitchen_Carpentry_Estimate.pdf', candidate_type='document'),
                RARCandidate(id='est_carpenter_v1', title='Modular_Kitchen_Carpentry_Estimate.pdf', candidate_type='document', recency_rank=1),
            ),
            local_evidence=RAREvidence(recency_hint='previous', target_type_hint='document'),
        ),
        expected_outcome=RAROutcome.RESOLVED,
        expected_candidate_id='est_carpenter_v1',
        description="'The previous estimate' with recency_rank 1 maps to est_carpenter_v1.",
    ))

    f.append(RARFixture(
        id='S4B-119', name="Colloquial reference to daughter's school fee receipt", category='personal_school_fee',
        turn_text="Print Ria's school fee receipt for tuition tax exemption.",
        query=RARQuery(
            reference_expression="Ria's school fee receipt",
            candidates=(
                RARCandidate(id='rec_ria_school', title='Delhi_Public_School_Term_IV_Fee_Receipt.pdf', candidate_type='document', owner='Ria'),
                RARCandidate(id='rec_swimming_class', title='Olympic_Pool_Weekend_Coaching_Fee.pdf', candidate_type='document', owner='Self'),
            ),
            local_evidence=RAREvidence(target_type_hint='document'),
        ),
        expected_outcome=RAROutcome.RESOLVED,
        expected_candidate_id='rec_ria_school',
        description="Owner metadata matches 'Ria' for school fee receipt rec_ria_school.",
    ))

    f.append(RARFixture(
        id='S4B-120', name='Vague pronoun reference among personal household tasks', category='personal_ambiguous_pronoun',
        turn_text='Mark that done.',
        query=RARQuery(
            reference_expression='that',
            candidates=(
                RARCandidate(id='task_plumber_call', title='Call plumber for kitchen sink leak', candidate_type='workflow'),
                RARCandidate(id='task_dry_cleaning', title='Pick up dry cleaning from sector market', candidate_type='workflow'),
            ),
            local_evidence=RAREvidence(target_type_hint='workflow'),
        ),
        expected_outcome=RAROutcome.AMBIGUOUS,
        expected_ambiguous_candidate_ids=('task_plumber_call', 'task_dry_cleaning'),
        description="Unanchored demonstrative 'that' between two personal to-do tasks is ambiguous.",
    ))

    f.append(RARFixture(
        id='S4B-121A', name='Personal multi-ref 1A: flight ticket', category='personal_multi_reference',
        turn_text='Forward the flight ticket along with the hotel confirmation to my spouse.',
        query=RARQuery(
            reference_expression='the flight ticket',
            candidates=(
                RARCandidate(id='tkt_airindia_del_ccu', title='Air_India_Flight_Ticket_DEL_CCU.pdf', candidate_type='document', domain_tags=('flight', 'ticket')),
                RARCandidate(id='tkt_metro_qr', title='Delhi_Metro_Airport_Express_QR.pdf', candidate_type='document', domain_tags=('transit',)),
            ),
            local_evidence=RAREvidence(clause_text='Forward the flight ticket', target_type_hint='document'),
        ),
        expected_outcome=RAROutcome.RESOLVED,
        expected_candidate_id='tkt_airindia_del_ccu',
        description='First reference: matches Air India flight ticket.',
    ))

    f.append(RARFixture(
        id='S4B-121B', name='Personal multi-ref 1B: hotel confirmation', category='personal_multi_reference',
        turn_text='Forward the flight ticket along with the hotel confirmation to my spouse.',
        query=RARQuery(
            reference_expression='the hotel confirmation',
            candidates=(
                RARCandidate(id='conf_hotel_oberoi', title='The_Oberoi_Grand_Kolkata_Booking.pdf', candidate_type='document', domain_tags=('hotel', 'confirmation')),
                RARCandidate(id='conf_cab_rental', title='Mega_Cabs_Airport_Pickup_Voucher.pdf', candidate_type='document', domain_tags=('cab',)),
            ),
            local_evidence=RAREvidence(clause_text='along with the hotel confirmation', target_type_hint='document'),
        ),
        expected_outcome=RAROutcome.RESOLVED,
        expected_candidate_id='conf_hotel_oberoi',
        description='Second reference: matches Oberoi hotel booking confirmation.',
    ))

    f.append(RARFixture(
        id='S4B-122A', name='Personal multi-ref 2A: broadband bill', category='personal_multi_reference',
        turn_text='Pay the broadband bill and attach the payment receipt to the expenses sheet.',
        query=RARQuery(
            reference_expression='the broadband bill',
            candidates=(
                RARCandidate(id='bill_act_fibernet', title='ACT_Fibernet_Monthly_Broadband_Bill.pdf', candidate_type='document', domain_tags=('broadband', 'bill')),
                RARCandidate(id='bill_mobile_postpaid', title='Jio_Postpaid_Mobile_Bill.pdf', candidate_type='document', domain_tags=('mobile', 'bill')),
            ),
            local_evidence=RAREvidence(clause_text='Pay the broadband bill', target_type_hint='document'),
        ),
        expected_outcome=RAROutcome.RESOLVED,
        expected_candidate_id='bill_act_fibernet',
        description='First reference: matches ACT Fibernet broadband bill.',
    ))

    f.append(RARFixture(
        id='S4B-122B', name='Personal multi-ref 2B: expenses sheet', category='personal_multi_reference',
        turn_text='Pay the broadband bill and attach the payment receipt to the expenses sheet.',
        query=RARQuery(
            reference_expression='the expenses sheet',
            candidates=(
                RARCandidate(id='sheet_family_expenses', title='Household_Monthly_Budget_Expenses_2026.xlsx', candidate_type='spreadsheet'),
                RARCandidate(id='doc_bank_passbook', title='Savings_Bank_Passbook_Entries.pdf', candidate_type='document'),
            ),
            local_evidence=RAREvidence(clause_text='to the expenses sheet', target_type_hint='spreadsheet'),
        ),
        expected_outcome=RAROutcome.RESOLVED,
        expected_candidate_id='sheet_family_expenses',
        description='Second reference: targets household budget expenses spreadsheet.',
    ))

    f.append(RARFixture(
        id='S4B-123', name='Vehicle registration certificate verbatim file name', category='personal_verbatim_title',
        turn_text='Send RC_Book_Honda_City_DL3C.pdf to the motor insurance agent.',
        query=RARQuery(
            reference_expression='RC_Book_Honda_City_DL3C.pdf',
            candidates=(
                RARCandidate(id='doc_rc_car', title='RC_Book_Honda_City_DL3C.pdf', candidate_type='document'),
                RARCandidate(id='doc_puc_car', title='PUC_Pollution_Certificate_Honda_City.pdf', candidate_type='document'),
            ),
            local_evidence=RAREvidence(),
        ),
        expected_outcome=RAROutcome.RESOLVED,
        expected_candidate_id='doc_rc_car',
        description='Verbatim file name matches the car RC book document.',
    ))

    f.append(RARFixture(
        id='S4B-126', name='Mixed context: office travel grant vs personal vacation ticket', category='cross_domain_travel',
        turn_text='Send the conference travel ticket to the accounts section.',
        query=RARQuery(
            reference_expression='the conference travel ticket',
            candidates=(
                RARCandidate(id='tkt_conf_vienna', title='Air_India_Delhi_Vienna_Conference_Ticket.pdf', candidate_type='document', domain_tags=('office', 'conference', 'travel')),
                RARCandidate(id='tkt_vacation_bali', title='Singapore_Airlines_Bali_Family_Holiday.pdf', candidate_type='document', domain_tags=('personal', 'vacation', 'travel')),
            ),
            local_evidence=RAREvidence(target_type_hint='document'),
        ),
        expected_outcome=RAROutcome.RESOLVED,
        expected_candidate_id='tkt_conf_vienna',
        description="'The conference travel ticket' cleanly discriminates the official academic conference flight from the family vacation ticket.",
    ))

    f.append(RARFixture(
        id='S4B-127', name='Mixed context: office reimbursement claim vs personal home repair bill', category='cross_domain_finance',
        turn_text='Submit the internet bill for office reimbursement.',
        query=RARQuery(
            reference_expression='the internet bill',
            candidates=(
                RARCandidate(id='bill_home_office_wifi', title='Airtel_Broadband_Tax_Invoice_Home_Office.pdf', candidate_type='document', domain_tags=('office', 'reimbursement', 'internet')),
                RARCandidate(id='bill_parent_landline', title='BSNL_Landline_Parents_Home.pdf', candidate_type='document', domain_tags=('personal', 'utility')),
                RARCandidate(id='doc_claim_form', title='Faculty_Telephone_Reimbursement_Form.pdf', candidate_type='document', domain_tags=('office', 'form')),
            ),
            local_evidence=RAREvidence(target_type_hint='document'),
        ),
        expected_outcome=RAROutcome.RESOLVED,
        expected_candidate_id='bill_home_office_wifi',
        description="Target type document with 'internet bill' matches the home office broadband invoice.",
    ))

    f.append(RARFixture(
        id='S4B-128', name='Mixed context: university email vs personal Gmail account', category='cross_domain_email',
        turn_text='Check the email from Dr. Sen.',
        query=RARQuery(
            reference_expression='the email from Dr. Sen',
            candidates=(
                RARCandidate(id='mail_univ_sen', title='Institutional Email: PhD Thesis Advisory Committee Schedule', candidate_type='email', owner='Dr. A. Sen'),
                RARCandidate(id='mail_personal_clinic', title='Personal Gmail: Dental Clinic Appointment Confirmation', candidate_type='email', owner='Dr. M. Sen Dental'),
            ),
            local_evidence=RAREvidence(target_type_hint='email'),
        ),
        expected_outcome=RAROutcome.AMBIGUOUS,
        expected_ambiguous_candidate_ids=('mail_univ_sen', 'mail_personal_clinic'),
        description="Both university and personal inboxes contain an email from a 'Dr. Sen'; without further context, 'the email from Dr. Sen' is ambiguous.",
    ))

    f.append(RARFixture(
        id='S4B-129', name='Mixed context: institutional NAAC report vs personal tax return file', category='cross_domain_contrast',
        turn_text='Not the tax return file, open the institutional quality report.',
        query=RARQuery(
            reference_expression='the institutional quality report',
            candidates=(
                RARCandidate(id='doc_itr_filing', title='ITR_V_Income_Tax_Acknowledgment_AY26.pdf', candidate_type='document', domain_tags=('personal', 'tax')),
                RARCandidate(id='doc_naac_quality', title='IQAC_Annual_Quality_Assurance_Report_2025.pdf', candidate_type='document', domain_tags=('office', 'quality', 'naac')),
            ),
            local_evidence=RAREvidence(negation_spans=('Not the tax return file',), target_type_hint='document'),
        ),
        expected_outcome=RAROutcome.RESOLVED,
        expected_candidate_id='doc_naac_quality',
        description="Negation explicitly rules out the tax return; 'the institutional quality report' resolves to doc_naac_quality.",
    ))

    f.append(RARFixture(
        id='S4B-130', name='Mixed context: active UI selection on work laptop vs personal phone sync', category='cross_domain_ui_anchor',
        turn_text='Print this document on the department network printer.',
        query=RARQuery(
            reference_expression='this document',
            candidates=(
                RARCandidate(id='doc_syll_course', title='CS401_Advanced_Algorithms_Syllabus.pdf', candidate_type='document'),
                RARCandidate(id='doc_car_insurance', title='Car_Insurance_Renewal_Policy.pdf', candidate_type='document'),
            ),
            local_evidence=RAREvidence(),
            deterministic_anchor=RARDeterministicAnchor(selected_ui_id='doc_syll_course'),
        ),
        expected_outcome=RAROutcome.RESOLVED,
        expected_candidate_id='doc_syll_course',
        description="Active UI selection anchor uniquely resolves 'this document' to the course syllabus.",
    ))

    f.append(RARFixture(
        id='S4B-131', name='Mixed context: absent university housing lease extension', category='cross_domain_unknown',
        turn_text='Attach the campus staff quarter lease renewal agreement.',
        query=RARQuery(
            reference_expression='the campus staff quarter lease renewal agreement',
            candidates=(
                RARCandidate(id='doc_personal_flat_lease', title='Private_Apartment_Rental_Agreement_Tenant.pdf', candidate_type='document', domain_tags=('personal', 'rental')),
                RARCandidate(id='doc_dept_allotment', title='Department_Lab_Room_Allotment_Order.pdf', candidate_type='document', domain_tags=('office', 'estate')),
            ),
            local_evidence=RAREvidence(target_type_hint='document'),
        ),
        expected_outcome=RAROutcome.UNKNOWN,
        description='The user requests the campus staff quarter lease renewal agreement, which is absent from the candidate pool.',
    ))

    f.append(RARFixture(
        id='S4B-132', name='Mixed context: continuation pointer to work project in mixed session', category='cross_domain_active_pointer',
        turn_text='Share the same presentation with the research collaborators.',
        query=RARQuery(
            reference_expression='the same presentation',
            candidates=(
                RARCandidate(id='pres_grant_defense', title='SERB_CRG_Research_Grant_Defense.pptx', candidate_type='presentation', domain_tags=('recently_discussed', 'office')),
                RARCandidate(id='pres_wedding_slideshow', title='Family_Anniversary_Photo_Slideshow.pptx', candidate_type='presentation', recency_rank=4),
            ),
            local_evidence=RAREvidence(recency_hint='same', target_type_hint='presentation'),
        ),
        expected_outcome=RAROutcome.RESOLVED,
        expected_candidate_id='pres_grant_defense',
        description="'The same presentation' points directly to the recently discussed research grant defense deck.",
    ))

    f.append(RARFixture(
        id='S4B-133', name='Mixed context: latest version between academic preprint and personal book draft', category='cross_domain_temporal_latest',
        turn_text='Open the latest manuscript draft.',
        query=RARQuery(
            reference_expression='the latest manuscript draft',
            candidates=(
                RARCandidate(id='draft_paper_ieee_v3', title='IEEE_Transaction_Paper_Draft.docx', candidate_type='document'),
                RARCandidate(id='draft_paper_ieee_v2', title='IEEE_Transaction_Paper_Draft.docx', candidate_type='document', recency_rank=1),
                RARCandidate(id='draft_novel_fiction', title='Personal_Fiction_Novel_Chapter_4.docx', candidate_type='document', recency_rank=2),
            ),
            local_evidence=RAREvidence(recency_hint='latest', target_type_hint='document'),
        ),
        expected_outcome=RAROutcome.RESOLVED,
        expected_candidate_id='draft_paper_ieee_v3',
        description="'The latest manuscript draft' with recency_rank 0 identifies draft_paper_ieee_v3.",
    ))

    f.append(RARFixture(
        id='S4B-134A', name='Mixed context multi-ref A: conference flight ticket', category='cross_domain_multi_ref',
        turn_text='Email the conference flight ticket to the university accounts clerk.',
        query=RARQuery(
            reference_expression='the conference flight ticket',
            candidates=(
                RARCandidate(id='tkt_indigo_conf', title='IndiGo_Flight_Ticket_BLR_CCU_Conference.pdf', candidate_type='document', domain_tags=('travel', 'conference')),
                RARCandidate(id='tkt_movie_pvr', title='PVR_Inox_Movie_Ticket_Weekend.pdf', candidate_type='document', domain_tags=('personal', 'entertainment')),
            ),
            local_evidence=RAREvidence(clause_text='Email the conference flight ticket', target_type_hint='document'),
        ),
        expected_outcome=RAROutcome.RESOLVED,
        expected_candidate_id='tkt_indigo_conf',
        description='First reference in decomposed turn: matches conference flight ticket.',
    ))

    f.append(RARFixture(
        id='S4B-134B', name='Mixed context multi-ref B: accounts clerk recipient', category='cross_domain_multi_ref',
        turn_text='Email the conference flight ticket to the university accounts clerk.',
        query=RARQuery(
            reference_expression='the university accounts clerk',
            candidates=(
                RARCandidate(id='person_clerk_accounts', title='Shri S. K. Verma (Upper Division Clerk - Accounts)', candidate_type='person', domain_tags=('office', 'accounts')),
                RARCandidate(id='person_agent_travel', title='Rohit Sharma (Personal Travel Agent)', candidate_type='person', domain_tags=('personal', 'travel')),
            ),
            local_evidence=RAREvidence(clause_text='to the university accounts clerk', target_type_hint='person'),
        ),
        expected_outcome=RAROutcome.RESOLVED,
        expected_candidate_id='person_clerk_accounts',
        description='Second reference in decomposed turn: matches university accounts clerk.',
    ))
    return tuple(f)
