"""Mock Data Store for Adversarial Generalization Battery.
Provides completely new domains, entities, tables, and files:
1. Equipment Fleet Loans & Rental Ledger
2. Purchase Requisitions & Vendor Master
3. Corporate Training Logs & Expense Reimbursements
4. IT Hardware Asset Dispatch & Return Logs
5. Fellowship Grant Applicants & Award Roster
6. Commercial Invoices & Bank Remittances
"""
from __future__ import annotations
from typing import Any, Dict, List

# 1. Equipment Fleet Loans (Overlapping checkout intervals and duplicate entries)
EQUIPMENT_LOANS_TABLE: List[Dict[str, Any]] = [
    {"loan_id": "LN-001", "asset_tag": "CRANE-701", "operator_id": "OP-881", "start_date": "2026-09-01", "end_date": "2026-09-05", "rate_code": "HEAVY"},
    {"loan_id": "LN-002", "asset_tag": "CRANE-701", "operator_id": "OP-881", "start_date": "2026-09-04", "end_date": "2026-09-08", "rate_code": "HEAVY"},  # Overlapping
    {"loan_id": "LN-003", "asset_tag": "CRANE-701", "operator_id": "op-881", "start_date": "2026-09-01", "end_date": "2026-09-05", "rate_code": "HEAVY"},  # Duplicate / lowercase
    {"loan_id": "LN-004", "asset_tag": "LOADER-302", "operator_id": "OP-412", "start_date": "2026-09-02", "end_date": "2026-09-04", "rate_code": "LIGHT"},
    {"loan_id": "LN-005", "asset_tag": "LOADER-302", "operator_id": "OP-412", "start_date": "2026-09-10", "end_date": "2026-09-15", "rate_code": "LIGHT"},
    {"loan_id": "LN-006", "asset_tag": "GENERATOR-99", "operator_id": "OP-UNKNOWN", "start_date": "2026-09-05", "end_date": "2026-09-07", "rate_code": "STANDBY"},  # Ambiguous operator
]

EQUIPMENT_RENTAL_RATES: List[Dict[str, Any]] = [
    {"rate_code": "HEAVY", "daily_fee": 450.0, "insurance_daily": 50.0},
    {"rate_code": "LIGHT", "daily_fee": 180.0, "insurance_daily": 20.0},
    {"rate_code": "STANDBY", "daily_fee": 85.0, "insurance_daily": 10.0}
]

# 2. Purchase Requisitions & Vendor Master
PURCHASE_REQUISITIONS_TABLE: List[Dict[str, Any]] = [
    {"req_id": "PR-501", "vendor_id": "v-101", "item_desc": "Industrial Lathe", "amount": 12500.0, "status": "APPROVED"},
    {"req_id": "PR-502", "vendor_id": "V-101", "item_desc": "Industrial Lathe", "amount": 12500.0, "status": "APPROVED"},  # Duplicate
    {"req_id": "PR-503", "vendor_id": "V-205", "item_desc": "Hydraulic Seals", "amount": 3400.0, "status": "APPROVED"},
    {"req_id": "PR-504", "vendor_id": "V-309", "item_desc": "Pneumatic Valves", "amount": 890.0, "status": "REJECTED"},
    {"req_id": "PR-505", "vendor_id": "V-999_UNREGISTERED", "item_desc": "Special Sensor", "amount": 4200.0, "status": "APPROVED"},  # Unmatched
]

VENDOR_MASTER_TABLE: List[Dict[str, Any]] = [
    {"vendor_id": "V-101", "vendor_name": "Apex Tooling Ltd", "tax_tier": "DOMESTIC", "discount_pct": 5.0},
    {"vendor_id": "V-205", "vendor_name": "FluidPower Inc", "tax_tier": "DOMESTIC", "discount_pct": 2.5},
    {"vendor_id": "V-309", "vendor_name": "ValveTech Global", "tax_tier": "EXPORT", "discount_pct": 0.0}
]

# 3. Training Attendance & Reimbursements
TRAINING_LOGS_TABLE: List[Dict[str, Any]] = [
    {"session_id": "TRN-1", "badge_no": "emp-101", "hours_logged": 16, "completion_status": "PASSED"},
    {"session_id": "TRN-2", "badge_no": "EMP-101", "hours_logged": 16, "completion_status": "PASSED"},  # Duplicate
    {"session_id": "TRN-3", "badge_no": "EMP-204", "hours_logged": 8, "completion_status": "PASSED"},
    {"session_id": "TRN-4", "badge_no": "EMP-305", "hours_logged": 4, "completion_status": "INCOMPLETE"},
    {"session_id": "TRN-5", "badge_no": "EMP-UNKNOWN", "hours_logged": 16, "completion_status": "PASSED"}
]

REIMBURSEMENT_SCHEDULE_TABLE: List[Dict[str, Any]] = [
    {"badge_no": "EMP-101", "travel_allowance": 350.0, "per_diem": 120.0},
    {"badge_no": "EMP-204", "travel_allowance": 150.0, "per_diem": 60.0},
    {"badge_no": "EMP-305", "travel_allowance": 0.0, "per_diem": 0.0}
]

# 4. IT Hardware Asset Dispatch & Return Logs
ASSET_DISPATCH_TABLE: List[Dict[str, Any]] = [
    {"dispatch_id": "DSP-01", "asset_id": "HW-8801", "user_id": "USR-A", "checkout_date": "2026-07-01", "expected_return": "2026-07-15"},
    {"dispatch_id": "DSP-02", "asset_id": "HW-8802", "user_id": "USR-B", "checkout_date": "2026-07-05", "expected_return": "2026-07-20"},
    {"dispatch_id": "DSP-03", "asset_id": "HW-8803", "user_id": "USR-C", "checkout_date": "2026-07-10", "expected_return": "2026-07-25"}
]

ASSET_INTAKE_TABLE: List[Dict[str, Any]] = [
    {"intake_id": "INT-01", "asset_id": "HW-8801", "actual_return": "2026-07-14", "condition": "GOOD"},
    {"intake_id": "INT-02", "asset_id": "HW-8802", "actual_return": "2026-07-28", "condition": "LATE"}
    # HW-8803 is missing (unreturned)
]

# 5. Fellowship Grant Applicants & Awardees
APPLICANT_REGISTRY_TABLE: List[Dict[str, Any]] = [
    {"app_no": "FLW-10", "candidate_id": "cid-901", "score": 94.5, "department": "AERO"},
    {"app_no": "FLW-11", "candidate_id": "CID-901", "score": 94.5, "department": "AERO"},  # Duplicate
    {"app_no": "FLW-12", "candidate_id": "CID-902", "score": 88.0, "department": "MECH"},
    {"app_no": "FLW-13", "candidate_id": "CID-903", "score": 72.0, "department": "CIVIL"}
]

FELLOW_AWARDS_TABLE: List[Dict[str, Any]] = [
    {"award_id": "AWD-01", "candidate_id": "CID-901", "stipend": 45000.0, "tenure_months": 12},
    {"award_id": "AWD-02", "candidate_id": "CID-902", "stipend": 45000.0, "tenure_months": 12},
    {"award_id": "AWD-03", "candidate_id": "CID-999_NOT_IN_APPLICANTS", "stipend": 50000.0, "tenure_months": 24}
]

# 6. Commercial Billing Invoices & Remittances
BILLING_INVOICES_TABLE: List[Dict[str, Any]] = [
    {"inv_id": "INV-1001", "client_code": "CL-Alpha", "billed_total": 8500.0, "status": "UNPAID"},
    {"inv_id": "INV-1002", "client_code": "CL-Beta", "billed_total": 14200.0, "status": "UNPAID"},
    {"inv_id": "INV-1003", "client_code": "CL-Gamma", "billed_total": 3100.0, "status": "PAID"}
]

BANK_REMITTANCES_TABLE: List[Dict[str, Any]] = [
    {"remittance_id": "REM-991", "inv_id": "INV-1001", "received_amount": 8500.0, "clearing_date": "2026-09-12"},
    {"remittance_id": "REM-992", "inv_id": "INV-1002", "received_amount": 10000.0, "clearing_date": "2026-09-14"}  # Underpaid
]

# Mock Workbooks & Documents in New Domains
ADVERSARIAL_WORKBOOKS: Dict[str, Any] = {
    "equipment_rentals_q3.xlsx": {
        "file_id": "file_equip_q3",
        "sheets": {
            "Rate_Schedule": [
                ["Rate Code", "Daily Fee", "Insurance"],
                ["HEAVY", 450.0, 50.0],
                ["LIGHT", 180.0, 20.0],
                ["STANDBY", 85.0, 10.0]
            ],
            "Fleet_Summary": [
                ["Category", "Count", "Utilization"],
                ["Heavy Cranes", 12, "82%"],
                ["Loaders", 8, "75%"]
            ]
        }
    },
    "commercial_procurement_fy26.xlsx": {
        "file_id": "file_procure_fy26",
        "sheets": {
            "Budget_Caps": [
                ["Department", "Allocated_Cap", "Spent"],
                ["Tooling", 50000.0, 25000.0],
                ["Hydraulics", 20000.0, 3400.0]
            ]
        }
    }
}

ADVERSARIAL_DOCUMENTS: Dict[str, Any] = {
    "doc_equipment_policy": {
        "filename": "fleet_rental_guidelines.md",
        "content": (
            "# Fleet Rental Guidelines FY26\n"
            "Section 1: Operating Period Calculation\n"
            "Consecutive or overlapping checkout periods for the same machinery tag must be consolidated into a single continuous duration.\n"
            "Section 2: Maintenance Surcharge\n"
            "Usage exceeding 10 continuous calendar days is subject to a 15% fleet maintenance credit.\n"
            "Section 3: Discretionary Surcharges\n"
            "Any unscheduled field adjustments require executive VP approval.\n"
        )
    }
}
