"""Mock Datasets and Storage for URI Dynamic Planning Benchmark.
Contains multi-source tables, gate pass records, attendance tables,
and documents for testing Levels 1 through 5.
"""
from __future__ import annotations
from typing import Any, Dict, List

MOCK_WORKBOOKS = {
    "budget_2026.xlsx": {
        "file_id": "file_budget_2026",
        "sheets": {
            "Summary": [
                ["Category", "Allocated", "Spent", "Remaining"],
                ["Hardware", 50000, 32000, 18000],
                ["Software", 20000, 14500, 5500],
                ["Travel", 15000, 12200, 2800],
                ["Contingency", 10000, 2100, 7900]
            ],
            "Q1_Details": [
                ["Item", "Date", "Cost"],
                ["Edge Server", "2026-01-15", 32000],
                ["Cloud License", "2026-02-10", 14500]
            ]
        }
    },
    "inventory.xlsx": {
        "file_id": "file_inventory_xls",
        "sheets": {
            "Hardware": [
                ["SKU", "Item", "Quantity", "Location"],
                ["HW-01", "Mini PC N100", 12, "Lab 1"],
                ["HW-02", "SSD 1TB", 25, "Store A"],
                ["HW-03", "RAM 32GB DDR5", 18, "Store B"]
            ]
        }
    }
}

MOCK_DOCUMENTS = {
    "file_policy_doc": {
        "filename": "rebate_policy.txt",
        "content": (
            "Line 1: National Institute Mess Rebate Policy 2026.\n"
            "Line 2: Students taking sanctioned leave of 3 or more consecutive days qualify for mess fee rebate.\n"
            "Line 3: Daily rebate rate is Rs. 145 per day.\n"
            "Line 4: Overlapping gate-pass entries must be merged into continuous intervals.\n"
            "Line 5: Mess attendance records must be updated with deduction status APPROVED."
        )
    },
    "file_meeting_notes": {
        "filename": "council_meeting.txt",
        "content": (
            "Meeting Date: 2026-09-15. Attendees: Dean, Warden, Mess Secretary.\n"
            "Agreed that all pending rebate adjustments for August must be submitted by month end."
        )
    }
}

# Gate Pass Table with real-world messiness: duplicates, overlapping dates, lowercase roll numbers
GATE_PASS_RECORDS = [
    {"gate_pass_id": "GP-101", "roll_no": "b260001ai", "student_name": "Aditya Kumar", "leave_start": "01/08/2026", "leave_end": "05/08/2026", "reason": "Home Visit"},
    {"gate_pass_id": "GP-101", "roll_no": "B260001AI", "student_name": "Aditya Kumar", "leave_start": "2026-08-01", "leave_end": "2026-08-05", "reason": "Home Visit"},  # duplicate
    {"gate_pass_id": "GP-102", "roll_no": "B260001AI", "student_name": "Aditya Kumar", "leave_start": "04/08/2026", "leave_end": "10/08/2026", "reason": "Extension"},   # overlapping!
    {"gate_pass_id": "GP-103", "roll_no": "B260002AI", "student_name": "Akshaya Diggi", "leave_start": "12/08/2026", "leave_end": "14/08/2026", "reason": "Medical"},     # 3 days -> qualifies
    {"gate_pass_id": "GP-104", "roll_no": "B260003", "student_name": "Ankita Mondal", "leave_start": "20/08/2026", "leave_end": "21/08/2026", "reason": "Personal"},     # 2 days -> does not qualify (< 3 days)
    {"gate_pass_id": "GP-105", "roll_no": "b260004cs", "student_name": "Vikram Rao", "leave_start": "05/08/2026", "leave_end": "12/08/2026", "reason": "Conference"},     # 8 days -> qualifies
    {"gate_pass_id": "GP-106", "roll_no": "UNKNOWN_STUDENT", "student_name": "Mystery Guest", "leave_start": "01/08/2026", "leave_end": "04/08/2026", "reason": "Unknown"} # ambiguous identity
]

MESS_ATTENDANCE_TABLE = [
    {"roll_no": "B260001AI", "name": "Aditya Kumar", "august_billed_days": 31, "current_rebate_days": 0, "status": "PENDING"},
    {"roll_no": "B260002AI", "name": "Akshaya Diggi", "august_billed_days": 31, "current_rebate_days": 0, "status": "PENDING"},
    {"roll_no": "B260003", "name": "Ankita Mondal", "august_billed_days": 31, "current_rebate_days": 0, "status": "PENDING"},
    {"roll_no": "B260004CS", "name": "Vikram Rao", "august_billed_days": 31, "current_rebate_days": 0, "status": "PENDING"}
]

TRANSACTIONS_TABLE = [
    {"tx_id": "TX-01", "category": "Office Supplies", "amount": 1200.0, "status": "COMPLETED"},
    {"tx_id": "TX-02", "category": "Hardware", "amount": 45000.0, "status": "COMPLETED"},
    {"tx_id": "TX-03", "category": "Office Supplies", "amount": 850.0, "status": "COMPLETED"},
    {"tx_id": "TX-04", "category": "Travel", "amount": 14200.0, "status": "PENDING"},
    {"tx_id": "TX-05", "category": "Hardware", "amount": 12000.0, "status": "COMPLETED"},
    {"tx_id": "TX-06", "category": "Office Supplies", "amount": 2300.0, "status": "COMPLETED"},
]

STUDENT_ROSTER_A = [
    {"roll_no": "B260001", "name": "Aditya Kumar", "branch": "AI"},
    {"roll_no": "B260002", "name": "Akshaya Diggi", "branch": "AI"},
    {"roll_no": "B260003", "name": "Ankita Mondal", "branch": "ECE"},
    {"roll_no": "B260004", "name": "Vikram Rao", "branch": "CSE"}
]

STUDENT_ROSTER_B = [
    {"roll_no": "B260001", "name": "Aditya Kumar", "hostel": "B1"},
    {"roll_no": "B260002", "name": "Akshaya Diggi", "hostel": "B2"},
    {"roll_no": "B260003", "name": "Ankita Mondal", "hostel": "G1"},
    {"roll_no": "B260005", "name": "Pooja Sharma", "hostel": "G2"}  # missing in Roster A
]
