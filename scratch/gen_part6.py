"""Generator part 6: Fixtures 106 to 125 (Personal Assistant / Everyday)."""

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

def get_fixtures_106_to_125():
    f = []
    # -------------------------------------------------------------
    # Personal Assistant / Everyday: S4B-106 .. S4B-125 (20 cases)
    # -------------------------------------------------------------
    f.append(RARFixture(
        id="S4B-106",
        name="Utility electricity bill reference",
        category="personal_bill_utility",
        turn_text="Pay the electricity bill before the due date tomorrow.",
        query=RARQuery(
            reference_expression="the electricity bill",
            candidates=(
                RARCandidate(id="bill_tneb_power", title="TNEB_Electricity_Bill_March_2026.pdf", candidate_type="document", domain_tags=("electricity", "utility")),
                RARCandidate(id="bill_airtel_broadband", title="Airtel_Fiber_Broadband_Invoice.pdf", candidate_type="document", domain_tags=("internet", "telecom")),
                RARCandidate(id="bill_piped_gas", title="Adani_Total_Gas_Domestic_Bill.pdf", candidate_type="document", domain_tags=("gas", "utility")),
            ),
            local_evidence=RAREvidence(target_type_hint="document"),
        ),
        expected_outcome=RAROutcome.RESOLVED,
        expected_candidate_id="bill_tneb_power",
        description="'The electricity bill' matches the TNEB electricity bill document uniquely.",
    ))

    f.append(RARFixture(
        id="S4B-107",
        name="Flight e-ticket booking confirmation alias match",
        category="personal_travel_ticket",
        turn_text="Check the boarding gate on PNR-6E-9912.",
        query=RARQuery(
            reference_expression="PNR-6E-9912",
            candidates=(
                RARCandidate(id="tkt_indigo_blr_del", title="IndiGo Flight Ticket BLR to DEL (PNR 6E-9912)", candidate_type="document", exact_aliases=("PNR-6E-9912",)),
                RARCandidate(id="tkt_airindia_del_lhr", title="Air India Ticket DEL to LHR (PNR AI-4011)", candidate_type="document", exact_aliases=("PNR-AI-4011",)),
            ),
            deterministic_anchor=RARDeterministicAnchor(exact_id="tkt_indigo_blr_del"),
        ),
        expected_outcome=RAROutcome.RESOLVED,
        expected_candidate_id="tkt_indigo_blr_del",
        description="Booking PNR reference matches the IndiGo flight ticket.",
    ))

    f.append(RARFixture(
        id="S4B-108",
        name="Household medical prescription shortened reference",
        category="personal_health",
        turn_text="Order the medicines listed in mother's prescription.",
        query=RARQuery(
            reference_expression="mother's prescription",
            candidates=(
                RARCandidate(id="rx_dr_sen_mother", title="Dr_Sen_Cardiology_Prescription_Mother.pdf", candidate_type="document", owner="Mother"),
                RARCandidate(id="rx_dr_mehta_self", title="Dr_Mehta_Dental_Prescription_Self.pdf", candidate_type="document", owner="Self"),
            ),
            local_evidence=RAREvidence(target_type_hint="document"),
        ),
        expected_outcome=RAROutcome.RESOLVED,
        expected_candidate_id="rx_dr_sen_mother",
        description="Owner metadata matches 'Mother' for cardiology prescription rx_dr_sen_mother.",
    ))

    f.append(RARFixture(
        id="S4B-109",
        name="Ambiguous reference across two grocery purchase receipts",
        category="personal_ambiguous_receipts",
        turn_text="Add the total from the grocery receipt to our expense sheet.",
        query=RARQuery(
            reference_expression="the grocery receipt",
            candidates=(
                RARCandidate(id="rec_blinkit_groceries", title="Blinkit_Grocery_Order_Receipt_14March.pdf", candidate_type="document", domain_tags=("grocery", "receipt")),
                RARCandidate(id="rec_instamart_groceries", title="Swiggy_Instamart_Receipt_12March.pdf", candidate_type="document", domain_tags=("grocery", "receipt")),
            ),
            local_evidence=RAREvidence(target_type_hint="document"),
        ),
        expected_outcome=RAROutcome.AMBIGUOUS,
        expected_ambiguous_candidate_ids=("rec_blinkit_groceries", "rec_instamart_groceries"),
        description="Two grocery receipts match 'the grocery receipt' without store or date qualification; ambiguous.",
    ))

    f.append(RARFixture(
        id="S4B-110",
        name="Request for absent passport renewal acknowledgment",
        category="personal_unknown_absent",
        turn_text="Check the dispatch status on the passport renewal slip.",
        query=RARQuery(
            reference_expression="the passport renewal slip",
            candidates=(
                RARCandidate(id="doc_aadhaar_card", title="E_Aadhaar_Card_Masked_2025.pdf", candidate_type="document"),
                RARCandidate(id="doc_pan_card", title="PAN_Card_Digital_Copy.pdf", candidate_type="document"),
                RARCandidate(id="doc_voter_id", title="Voter_Identity_Card_Scan.pdf", candidate_type="document"),
            ),
            local_evidence=RAREvidence(target_type_hint="document"),
        ),
        expected_outcome=RAROutcome.UNKNOWN,
        description="The candidate set contains government ID cards, but no passport renewal acknowledgment slip.",
    ))

    f.append(RARFixture(
        id="S4B-111",
        name="Family vacation hotel booking confirmation PDF",
        category="personal_travel_hotel",
        turn_text="What is the check-in time on the hotel booking voucher?",
        query=RARQuery(
            reference_expression="the hotel booking voucher",
            candidates=(
                RARCandidate(id="res_taj_hotel", title="Taj_Exotica_Goa_Booking_Confirmation.pdf", candidate_type="document", domain_tags=("hotel", "travel")),
                RARCandidate(id="res_zoomcar", title="Zoomcar_Rental_Agreement_Goa.pdf", candidate_type="document", domain_tags=("car", "travel")),
            ),
            local_evidence=RAREvidence(target_type_hint="document"),
        ),
        expected_outcome=RAROutcome.RESOLVED,
        expected_candidate_id="res_taj_hotel",
        description="'The hotel booking voucher' uniquely isolates res_taj_hotel from the car rental agreement.",
    ))

    f.append(RARFixture(
        id="S4B-112",
        name="Latest apartment maintenance payment receipt",
        category="personal_temporal_latest",
        turn_text="Find the latest apartment maintenance receipt.",
        query=RARQuery(
            reference_expression="the latest apartment maintenance receipt",
            candidates=(
                RARCandidate(id="rec_maint_feb2026", title="Apartment_Society_Maintenance_Receipt.pdf", candidate_type="document", recency_rank=0),
                RARCandidate(id="rec_maint_jan2026", title="Apartment_Society_Maintenance_Receipt.pdf", candidate_type="document", recency_rank=1),
                RARCandidate(id="rec_maint_dec2025", title="Apartment_Society_Maintenance_Receipt.pdf", candidate_type="document", recency_rank=2),
            ),
            local_evidence=RAREvidence(recency_hint="latest", target_type_hint="document"),
        ),
        expected_outcome=RAROutcome.RESOLVED,
        expected_candidate_id="rec_maint_feb2026",
        description="'The latest' with recency_rank 0 identifies the most recent apartment maintenance receipt.",
    ))

    f.append(RARFixture(
        id="S4B-113",
        name="Contrastive selection between car and health insurance policies",
        category="personal_contrast",
        turn_text="Not the car insurance, pull up the health insurance policy.",
        query=RARQuery(
            reference_expression="the health insurance policy",
            candidates=(
                RARCandidate(id="pol_hdfc_ergo_car", title="HDFC_ERGO_Car_Comprehensive_Insurance.pdf", candidate_type="document", domain_tags=("car", "insurance")),
                RARCandidate(id="pol_star_health", title="Star_Health_Family_Optima_Policy.pdf", candidate_type="document", domain_tags=("health", "insurance")),
            ),
            local_evidence=RAREvidence(
                negation_spans=("Not the car insurance",),
                target_type_hint="document",
            ),
        ),
        expected_outcome=RAROutcome.RESOLVED,
        expected_candidate_id="pol_star_health",
        description="Negation explicitly rejects car insurance; health insurance resolves to pol_star_health.",
    ))

    f.append(RARFixture(
        id="S4B-114",
        name="Personal gym subscription reminder active UI selection",
        category="personal_ui_anchor",
        turn_text="Snooze this reminder until Saturday morning.",
        query=RARQuery(
            reference_expression="this reminder",
            candidates=(
                RARCandidate(id="rem_gym_renewal", title="Reminder: Cult.fit Gym Membership Annual Renewal", candidate_type="workflow"),
                RARCandidate(id="rem_dentist_visit", title="Reminder: Dentist Scaling Appointment", candidate_type="workflow"),
            ),
            deterministic_anchor=RARDeterministicAnchor(selected_ui_id="rem_gym_renewal"),
        ),
        expected_outcome=RAROutcome.RESOLVED,
        expected_candidate_id="rem_gym_renewal",
        description="Selected UI anchor binds 'this reminder' to the gym membership renewal notification.",
    ))

    f.append(RARFixture(
        id="S4B-115",
        name="Request for absent dog veterinary immunization booklet",
        category="personal_unknown_absent",
        turn_text="Where did we save Max's rabies vaccination certificate?",
        query=RARQuery(
            reference_expression="Max's rabies vaccination certificate",
            candidates=(
                RARCandidate(id="doc_home_deed", title="Apartment_Sale_Deed_Registered.pdf", candidate_type="document"),
                RARCandidate(id="doc_property_tax", title="Property_Tax_Challan_2025_2026.pdf", candidate_type="document"),
            ),
            local_evidence=RAREvidence(target_type_hint="document"),
        ),
        expected_outcome=RAROutcome.UNKNOWN,
        description="The candidate set contains property records; the pet vaccination certificate is absent.",
    ))

    f.append(RARFixture(
        id="S4B-116",
        name="Active photo attachment in personal chat conversation",
        category="personal_attachment_anchor",
        turn_text="Save this photo to our family vacation album.",
        query=RARQuery(
            reference_expression="this photo",
            candidates=(
                RARCandidate(id="pic_beach_sunset", title="Goa_Beach_Sunset_Family.jpg", candidate_type="media", is_attachment=True),
                RARCandidate(id="doc_itinerary", title="Goa_Trip_Itinerary_Plan.pdf", candidate_type="document", is_attachment=False),
            ),
            deterministic_anchor=RARDeterministicAnchor(current_attachment_id="pic_beach_sunset"),
        ),
        expected_outcome=RAROutcome.RESOLVED,
        expected_candidate_id="pic_beach_sunset",
        description="Current attachment anchor points directly to the JPEG photo attachment.",
    ))

    f.append(RARFixture(
        id="S4B-117",
        name="Ambiguous reference across two personal credit card statements",
        category="personal_ambiguous_statements",
        turn_text="Check the reward points on the credit card statement.",
        query=RARQuery(
            reference_expression="the credit card statement",
            candidates=(
                RARCandidate(id="stmt_icici_amazon", title="ICICI_Amazon_Pay_Card_Statement_Feb.pdf", candidate_type="document", domain_tags=("credit_card", "statement")),
                RARCandidate(id="stmt_hdfc_regalia", title="HDFC_Regalia_Card_Statement_Feb.pdf", candidate_type="document", domain_tags=("credit_card", "statement")),
            ),
            local_evidence=RAREvidence(target_type_hint="document"),
        ),
        expected_outcome=RAROutcome.AMBIGUOUS,
        expected_ambiguous_candidate_ids=("stmt_icici_amazon", "stmt_hdfc_regalia"),
        description="Two credit card statements exist for the same month; ambiguous without bank or card name.",
    ))

    f.append(RARFixture(
        id="S4B-118",
        name="Previous version of home renovation budget estimate",
        category="personal_temporal_previous",
        turn_text="Show me the previous estimate from the carpenter.",
        query=RARQuery(
            reference_expression="the previous estimate",
            candidates=(
                RARCandidate(id="est_carpenter_v2", title="Modular_Kitchen_Carpentry_Estimate.pdf", candidate_type="document", recency_rank=0),
                RARCandidate(id="est_carpenter_v1", title="Modular_Kitchen_Carpentry_Estimate.pdf", candidate_type="document", recency_rank=1),
            ),
            local_evidence=RAREvidence(recency_hint="previous", target_type_hint="document"),
        ),
        expected_outcome=RAROutcome.RESOLVED,
        expected_candidate_id="est_carpenter_v1",
        description="'The previous estimate' with recency_rank 1 maps to est_carpenter_v1.",
    ))

    f.append(RARFixture(
        id="S4B-119",
        name="Colloquial reference to daughter's school fee receipt",
        category="personal_school_fee",
        turn_text="Print Ria's school fee receipt for tuition tax exemption.",
        query=RARQuery(
            reference_expression="Ria's school fee receipt",
            candidates=(
                RARCandidate(id="rec_ria_school", title="Delhi_Public_School_Term_IV_Fee_Receipt.pdf", candidate_type="document", owner="Ria"),
                RARCandidate(id="rec_swimming_class", title="Olympic_Pool_Weekend_Coaching_Fee.pdf", candidate_type="document", owner="Self"),
            ),
            local_evidence=RAREvidence(target_type_hint="document"),
        ),
        expected_outcome=RAROutcome.RESOLVED,
        expected_candidate_id="rec_ria_school",
        description="Owner metadata matches 'Ria' for school fee receipt rec_ria_school.",
    ))

    f.append(RARFixture(
        id="S4B-120",
        name="Vague pronoun reference among personal household tasks",
        category="personal_ambiguous_pronoun",
        turn_text="Mark that done.",
        query=RARQuery(
            reference_expression="that",
            candidates=(
                RARCandidate(id="task_plumber_call", title="Call plumber for kitchen sink leak", candidate_type="workflow"),
                RARCandidate(id="task_dry_cleaning", title="Pick up dry cleaning from sector market", candidate_type="workflow"),
            ),
            local_evidence=RAREvidence(target_type_hint="workflow"),
        ),
        expected_outcome=RAROutcome.AMBIGUOUS,
        expected_ambiguous_candidate_ids=("task_plumber_call", "task_dry_cleaning"),
        description="Unanchored demonstrative 'that' between two personal to-do tasks is ambiguous.",
    ))

    # Multi-reference personal cases
    turn_121 = "Forward the flight ticket along with the hotel confirmation to my spouse."
    f.append(RARFixture(
        id="S4B-121A",
        name="Personal multi-ref 1A: flight ticket",
        category="personal_multi_reference",
        turn_text=turn_121,
        query=RARQuery(
            reference_expression="the flight ticket",
            candidates=(
                RARCandidate(id="tkt_airindia_del_ccu", title="Air_India_Flight_Ticket_DEL_CCU.pdf", candidate_type="document", domain_tags=("flight", "ticket")),
                RARCandidate(id="tkt_metro_qr", title="Delhi_Metro_Airport_Express_QR.pdf", candidate_type="document", domain_tags=("transit",)),
            ),
            local_evidence=RAREvidence(clause_text="Forward the flight ticket", target_type_hint="document"),
        ),
        expected_outcome=RAROutcome.RESOLVED,
        expected_candidate_id="tkt_airindia_del_ccu",
        description="First reference: matches Air India flight ticket.",
    ))
    f.append(RARFixture(
        id="S4B-121B",
        name="Personal multi-ref 1B: hotel confirmation",
        category="personal_multi_reference",
        turn_text=turn_121,
        query=RARQuery(
            reference_expression="the hotel confirmation",
            candidates=(
                RARCandidate(id="conf_hotel_oberoi", title="The_Oberoi_Grand_Kolkata_Booking.pdf", candidate_type="document", domain_tags=("hotel", "confirmation")),
                RARCandidate(id="conf_cab_rental", title="Mega_Cabs_Airport_Pickup_Voucher.pdf", candidate_type="document", domain_tags=("cab",)),
            ),
            local_evidence=RAREvidence(clause_text="along with the hotel confirmation", target_type_hint="document"),
        ),
        expected_outcome=RAROutcome.RESOLVED,
        expected_candidate_id="conf_hotel_oberoi",
        description="Second reference: matches Oberoi hotel booking confirmation.",
    ))

    turn_122 = "Pay the broadband bill and attach the payment receipt to the expenses sheet."
    f.append(RARFixture(
        id="S4B-122A",
        name="Personal multi-ref 2A: broadband bill",
        category="personal_multi_reference",
        turn_text=turn_122,
        query=RARQuery(
            reference_expression="the broadband bill",
            candidates=(
                RARCandidate(id="bill_act_fibernet", title="ACT_Fibernet_Monthly_Broadband_Bill.pdf", candidate_type="document", domain_tags=("broadband", "bill")),
                RARCandidate(id="bill_mobile_postpaid", title="Jio_Postpaid_Mobile_Bill.pdf", candidate_type="document", domain_tags=("mobile", "bill")),
            ),
            local_evidence=RAREvidence(clause_text="Pay the broadband bill", target_type_hint="document"),
        ),
        expected_outcome=RAROutcome.RESOLVED,
        expected_candidate_id="bill_act_fibernet",
        description="First reference: matches ACT Fibernet broadband bill.",
    ))
    f.append(RARFixture(
        id="S4B-122B",
        name="Personal multi-ref 2B: expenses sheet",
        category="personal_multi_reference",
        turn_text=turn_122,
        query=RARQuery(
            reference_expression="the expenses sheet",
            candidates=(
                RARCandidate(id="sheet_family_expenses", title="Household_Monthly_Budget_Expenses_2026.xlsx", candidate_type="spreadsheet"),
                RARCandidate(id="doc_bank_passbook", title="Savings_Bank_Passbook_Entries.pdf", candidate_type="document"),
            ),
            local_evidence=RAREvidence(clause_text="to the expenses sheet", target_type_hint="spreadsheet"),
        ),
        expected_outcome=RAROutcome.RESOLVED,
        expected_candidate_id="sheet_family_expenses",
        description="Second reference: targets household budget expenses spreadsheet.",
    ))

    f.append(RARFixture(
        id="S4B-123",
        name="Vehicle registration certificate verbatim file name",
        category="personal_verbatim_title",
        turn_text="Send RC_Book_Honda_City_DL3C.pdf to the motor insurance agent.",
        query=RARQuery(
            reference_expression="RC_Book_Honda_City_DL3C.pdf",
            candidates=(
                RARCandidate(id="doc_rc_car", title="RC_Book_Honda_City_DL3C.pdf", candidate_type="document"),
                RARCandidate(id="doc_puc_car", title="PUC_Pollution_Certificate_Honda_City.pdf", candidate_type="document"),
            ),
        ),
        expected_outcome=RAROutcome.RESOLVED,
        expected_candidate_id="doc_rc_car",
        description="Verbatim file name matches the car RC book document.",
    ))

    return f

print("Loaded fixtures 106 to 125.")
