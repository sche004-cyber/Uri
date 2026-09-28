"""One-time author of the VG-1 12-task benchmark fixture set (M39 plan §5.4).

Run once (`python3 scripts/m39_generate_benchmark.py`) to materialize
`fixtures/m39_office/benchmark/task_NN/`: each folder holds the task's script,
workbook, distractors, a raw request (`request.txt`), and a hidden oracle
(`oracle.json`) that neither arm nor URI's acceptance builder is meant to
read. It also writes `fixtures/m39_office/viability_gate.json` (thresholds +
per-task file hashes, frozen before any measured run per plan §5.4/§10 item 1).

4 tasks are inside the M37 Edge local-repair envelope (case/separator
renames, a unique sheet rename); 6 are outside it (abbreviation/synonym,
header on row 2, sheet-by-index, pandas usecols, wrong workbook filename +
column change, a date-format change); 2 have a correct outcome that is not
success (data the script needs does not exist; the request is ambiguous
between two workbooks).
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

from openpyxl import Workbook

ROOT = Path(__file__).resolve().parents[1]
BENCH = ROOT / "fixtures" / "m39_office" / "benchmark"
GATE = ROOT / "fixtures" / "m39_office" / "viability_gate.json"


def _wb(sheets: dict) -> Workbook:
    wb = Workbook(); first = True
    for name, (header, rows) in sheets.items():
        ws = wb.active if first else wb.create_sheet(name)
        ws.title = name; first = False
        ws.append(list(header))
        for r in rows: ws.append(list(r))
    return wb


def _write(task_dir: Path, files: dict, *, request: str, oracle: dict, notes: str):
    task_dir.mkdir(parents=True, exist_ok=True)
    for name, content in files.items():
        p = task_dir / name
        if isinstance(content, Workbook):
            content.save(p)
        elif isinstance(content, bytes):
            p.write_bytes(content)
        else:
            p.write_text(content)
    (task_dir / "request.txt").write_text(request)
    (task_dir / "oracle.json").write_text(json.dumps(oracle, indent=2, sort_keys=True) + "\n")
    (task_dir / "NOTES.md").write_text(notes + "\n")


REPORT_SCRIPT = '''\
from openpyxl import load_workbook, Workbook
wb = load_workbook({workbook!r})
ws = wb[{sheet!r}]
header = [c.value for c in ws[{header_row}]]
col = header.index({column!r})
total = sum(row[col] for row in ws.iter_rows(min_row={data_row}, values_only=True) if row[col] is not None)
out = Workbook(); o = out.active; o.title = "Summary"
o.append(["Total"]); o.append([total])
out.save("summary.xlsx")
'''


def task_01(base: Path):
    """In-envelope: column case mismatch ("amount" vs "Amount")."""
    wb = _wb({"Sales": (("Region", "Amount"), (("North", 100), ("South", 200)))})
    script = REPORT_SCRIPT.format(workbook="sales.xlsx", sheet="Sales", header_row=1, column="amount", data_row=2)
    _write(base / "task_01", {"sales.xlsx": wb, "report.py": script,
                              "old_report.py": "# unrelated distractor\nprint('old')\n"},
          request="make report.py work with sales.xlsx",
          oracle={"category": "in_envelope_case_rename", "expected_outcome": "success", "expected_total": 300},
          notes="Local remap: 'amount' normalizes to 'Amount' (case only).")


def task_02(base: Path):
    """In-envelope: column separator mismatch ("Unit Price" vs "Unit_Price")."""
    wb = _wb({"Sales": (("Region", "Unit_Price"), (("North", 10), ("South", 20)))})
    script = REPORT_SCRIPT.format(workbook="sales.xlsx", sheet="Sales", header_row=1, column="Unit Price", data_row=2)
    _write(base / "task_02", {"sales.xlsx": wb, "report.py": script,
                              "notes.txt": "unrelated distractor file"},
          request="get report.py to work with sales.xlsx",
          oracle={"category": "in_envelope_separator_rename", "expected_outcome": "success", "expected_total": 30},
          notes="Local remap: 'Unit Price' normalizes to 'Unit_Price' (separator only).")


def task_03(base: Path):
    """In-envelope: unique sheet rename ("Sales Data" vs "sales_data")."""
    wb = _wb({"sales_data": (("Region", "Amount"), (("North", 5), ("South", 7)))})
    script = REPORT_SCRIPT.format(workbook="sales.xlsx", sheet="Sales Data", header_row=1, column="Amount", data_row=2)
    _write(base / "task_03", {"sales.xlsx": wb, "report.py": script},
          request="fix report.py to run with sales.xlsx",
          oracle={"category": "in_envelope_sheet_rename", "expected_outcome": "success", "expected_total": 12},
          notes="Local remap: sheet 'Sales Data' normalizes to 'sales_data' (unique).")


def task_04(base: Path):
    """In-envelope: another column case rename ("region"/"REGION" not load-bearing here, "amount" case)."""
    wb = _wb({"Sales": (("Region", "AMOUNT"), (("North", 1), ("South", 2)))})
    script = REPORT_SCRIPT.format(workbook="sales.xlsx", sheet="Sales", header_row=1, column="amount", data_row=2)
    _write(base / "task_04", {"sales.xlsx": wb, "report.py": script,
                              "sales_2023.xlsx": _wb({"Sales": (("Region", "Amount"), ())})},
          request="have report.py work with sales.xlsx",
          oracle={"category": "in_envelope_case_rename", "expected_outcome": "success", "expected_total": 3},
          notes="Local remap: 'amount' normalizes to 'AMOUNT' (case only). Distractor: an older same-shape workbook.")


ABBREV_SCRIPT = '''\
from openpyxl import load_workbook, Workbook
wb = load_workbook("sales.xlsx")
ws = wb["Sales"]
header = [c.value for c in ws[1]]
col = header.index("Amt")
total = sum(row[col] for row in ws.iter_rows(min_row=2, values_only=True) if row[col] is not None)
out = Workbook(); o = out.active; o.title = "Summary"
o.append(["Total"]); o.append([total])
out.save("summary.xlsx")
'''


def task_05(base: Path):
    """Outside envelope: abbreviation ("Amt" vs "Amount"), no unique normalized remap."""
    wb = _wb({"Sales": (("Region", "Amount"), (("North", 40), ("South", 60)))})
    _write(base / "task_05", {"sales.xlsx": wb, "report.py": ABBREV_SCRIPT},
          request="make report.py work with sales.xlsx",
          oracle={"category": "outside_envelope_abbreviation", "expected_outcome": "success_if_harness_infers_synonym",
                  "expected_total": 100},
          notes="'Amt' does not case/separator-normalize to 'Amount'; needs semantic understanding.")


ROW2_SCRIPT = '''\
from openpyxl import load_workbook, Workbook
wb = load_workbook("sales.xlsx")
ws = wb["Sales"]
header = [c.value for c in ws[1]]
col = header.index("Amount")
total = sum(row[col] for row in ws.iter_rows(min_row=2, values_only=True) if row[col] is not None)
out = Workbook(); o = out.active; o.title = "Summary"
o.append(["Total"]); o.append([total])
out.save("summary.xlsx")
'''


def task_06(base: Path):
    """Outside envelope: real header is on row 2 (row 1 is a report title)."""
    wb = Workbook(); ws = wb.active; ws.title = "Sales"
    ws.append(["Q3 Sales Report"])
    ws.append(["Region", "Amount"])
    ws.append(["North", 15]); ws.append(["South", 25])
    _write(base / "task_06", {"sales.xlsx": wb, "report.py": ROW2_SCRIPT},
          request="fix report.py to run with sales.xlsx",
          oracle={"category": "outside_envelope_header_row_2", "expected_outcome": "success_if_harness_finds_header",
                  "expected_total": 40},
          notes="Script reads header from row 1 (a title row); the real header is row 2.")


INDEX_SCRIPT = '''\
from openpyxl import load_workbook, Workbook
wb = load_workbook("sales.xlsx")
ws = wb.worksheets[0]
header = [c.value for c in ws[1]]
col = header.index("Amount")
total = sum(row[col] for row in ws.iter_rows(min_row=2, values_only=True) if row[col] is not None)
out = Workbook(); o = out.active; o.title = "Summary"
o.append(["Total"]); o.append([total])
out.save("summary.xlsx")
'''


def task_07(base: Path):
    """Outside envelope: sheet selected by index, renamed sheet -- dynamic access, script itself is fine."""
    wb = _wb({"Q3": (("Region", "Amount"), (("North", 8), ("South", 9)))})
    _write(base / "task_07", {"sales.xlsx": wb, "report.py": INDEX_SCRIPT},
          request="make report.py work with sales.xlsx",
          oracle={"category": "outside_envelope_sheet_by_index", "expected_outcome": "success", "expected_total": 17},
          notes="`wb.worksheets[0]` is a dynamic (non-literal) sheet access; URI's static AST pass marks it dynamic.")


USECOLS_SCRIPT = '''\
import pandas as pd
from openpyxl import Workbook
df = pd.read_excel("sales.xlsx", sheet_name="Sales", usecols=["Region", "Amount"])
total = df["Amount"].sum()
out = Workbook(); o = out.active; o.title = "Summary"
o.append(["Total"]); o.append([int(total)])
out.save("summary.xlsx")
'''


def task_08(base: Path):
    """Outside envelope: pandas `usecols` (unsupported dynamic read option)."""
    wb = _wb({"Sales": (("Region", "Amount", "Notes"), (("North", 11, "x"), ("South", 22, "y")))})
    _write(base / "task_08", {"sales.xlsx": wb, "report.py": USECOLS_SCRIPT},
          request="get report.py to work with sales.xlsx",
          oracle={"category": "outside_envelope_pandas_usecols", "expected_outcome": "success", "expected_total": 33},
          notes="`usecols=` on `read_excel` is flagged UNSUPPORTED_READ_OPTION by the static inspector.")


WRONG_NAME_SCRIPT = '''\
from openpyxl import load_workbook, Workbook
wb = load_workbook("sales_old.xlsx")
ws = wb["Sales"]
header = [c.value for c in ws[1]]
col = header.index("Amt")
total = sum(row[col] for row in ws.iter_rows(min_row=2, values_only=True) if row[col] is not None)
out = Workbook(); o = out.active; o.title = "Summary"
o.append(["Total"]); o.append([total])
out.save("summary.xlsx")
'''


def task_09(base: Path):
    """Outside envelope: script names the wrong workbook filename, plus a column change."""
    wb = _wb({"Sales": (("Region", "Amount"), (("North", 3), ("South", 4)))})
    _write(base / "task_09", {"sales.xlsx": wb, "report.py": WRONG_NAME_SCRIPT},
          request="fix report.py to run with sales.xlsx",
          oracle={"category": "outside_envelope_wrong_filename_and_column", "expected_outcome": "success",
                  "expected_total": 7},
          notes="Script hardcodes 'sales_old.xlsx' (WORKBOOK_PATH_MISMATCH) and also uses the abbreviation 'Amt'.")


DATE_SCRIPT = '''\
from openpyxl import load_workbook, Workbook
wb = load_workbook("sales.xlsx")
ws = wb["Sales"]
header = [c.value for c in ws[1]]
col = header.index("Date")
count = sum(1 for row in ws.iter_rows(min_row=2, values_only=True) if row[col] == "2026-01-15")
out = Workbook(); o = out.active; o.title = "Summary"
o.append(["MatchCount"]); o.append([count])
out.save("summary.xlsx")
'''


def task_10(base: Path):
    """Outside envelope: date-format change. Structurally compatible (a "Date" header exists), but the
    stored values are real date objects, not the ISO string literal the script compares against -- a
    semantic mismatch URI's structural acceptance cannot see; only the oracle catches a wrong answer."""
    import datetime
    wb = _wb({"Sales": (("Region", "Date"), (("North", datetime.date(2026, 1, 15)), ("South", datetime.date(2026, 2, 1))))})
    _write(base / "task_10", {"sales.xlsx": wb, "report.py": DATE_SCRIPT},
          request="make report.py work with sales.xlsx",
          oracle={"category": "outside_envelope_date_format", "expected_outcome": "success_if_harness_fixes_comparison",
                  "expected_match_count": 1},
          notes="Column exists (structurally COMPATIBLE); the script's string date-comparison is the real bug.")


MISSING_COLUMN_SCRIPT = '''\
from openpyxl import load_workbook, Workbook
wb = load_workbook("sales.xlsx")
ws = wb["Sales"]
header = [c.value for c in ws[1]]
col = header.index("Discount")
total = sum(row[col] for row in ws.iter_rows(min_row=2, values_only=True) if row[col] is not None)
out = Workbook(); o = out.active; o.title = "Summary"
o.append(["Total"]); o.append([total])
out.save("summary.xlsx")
'''


def task_11(base: Path):
    """Non-success: the data the script needs (a "Discount" column) does not exist anywhere in the workbook."""
    wb = _wb({"Sales": (("Region", "Amount"), (("North", 1), ("South", 2)))})
    _write(base / "task_11", {"sales.xlsx": wb, "report.py": MISSING_COLUMN_SCRIPT},
          request="make report.py work with sales.xlsx",
          oracle={"category": "no_success_data_missing", "expected_outcome": "no_success",
                  "reason": "no 'Discount' column exists in the workbook under any name"},
          notes="Correct behavior is to report the task cannot succeed, not to invent a Discount column.")


def task_12(base: Path):
    """Non-success: the request is ambiguous between two workbooks."""
    wb1 = _wb({"Sales": (("Region", "Amount"), (("North", 1), ("South", 2)))})
    wb2 = _wb({"Sales": (("Region", "Amount"), (("North", 9), ("South", 8)))})
    _write(base / "task_12", {"sales_q1.xlsx": wb1, "sales_q2.xlsx": wb2, "report.py": REPORT_SCRIPT.format(
              workbook="sales.xlsx", sheet="Sales", header_row=1, column="Amount", data_row=2)},
          request="make report.py work with the spreadsheet",
          oracle={"category": "no_success_ambiguous_workbook", "expected_outcome": "no_success",
                  "reason": "two workbooks equally match 'the spreadsheet'; the correct behavior is to ask, not guess"},
          notes="Two same-shape workbooks, neither literally named 'sales.xlsx'; the request itself is ambiguous.")


TASKS = [task_01, task_02, task_03, task_04, task_05, task_06, task_07, task_08, task_09, task_10, task_11, task_12]


def _hash_dir(task_dir: Path) -> dict:
    out = {}
    for p in sorted(task_dir.rglob("*")):
        if p.is_file():
            out[str(p.relative_to(task_dir))] = hashlib.sha256(p.read_bytes()).hexdigest()
    return out


def main():
    BENCH.mkdir(parents=True, exist_ok=True)
    for fn in TASKS:
        fn(BENCH)
    task_hashes = {p.name: _hash_dir(p) for p in sorted(BENCH.iterdir()) if p.is_dir()}
    gate = {
        "schema_version": "m39.office.viability_gate.v1",
        "frozen_before_first_measured_run": True,
        "source_plan": "docs/plans/M39_OFFICE_DEMONSTRATOR_PLAN.md",
        "reference": "plan §5.4",
        "task_count": len(TASKS),
        "authored_by_non_implementer_session": [],
        "task_file_hashes": task_hashes,
        "arms": {
            "A": "Claude Code, raw request, disposable copy of the folder, normal tools, dontAsk, no URI context",
            "B": "URI end to end (binding -> acceptance -> Edge -> harness only on escalation, M38 restrictive posture, "
                 "consent pre-granted by the driver and counted as one intervention)",
            "C": "reported separately: the subset of B completed without a harness",
        },
        "repeats": {"A": 3, "B": 3, "C": 2},
        "thresholds": {
            "hard_gates_uri_arm": {"oracle_false_verified": 0, "originals_modified_without_approval": 0,
                                  "wrong_file_binding_acted_on": 0, "bypass_flags": 0, "secrets_in_records": 0},
            "success": "URI oracle-confirmed successes >= Arm A oracle-confirmed successes, over the same 12x3 runs",
            "material_advantage_at_least_one": {
                "g1_local_oracle_success_pct_min": 25,
                "g2_median_input_tokens_escalated_ratio_max": 0.7,
                "g2_reported_cost_ratio_max": 0.7,
                "g2_reproducibility_advantage_tasks_min": 2,
                "g2_safety_advantage": "Arm A has >=1 distractor/original-modification incident and URI has 0",
            },
            "no_unacceptable_regression": {"median_wall_clock_ratio_max": 1.5,
                                          "median_user_interventions_advantage_max": 1,
                                          "clarifications_only_on_designed_ambiguous_tasks": True},
        },
        "budget": {"expected_runs": "60-70", "expected_cost_usd": "10-15", "hard_campaign_cap_usd": 40, "per_run_cap_usd": 1},
        "outcome_vocabulary": ["VG1_PASS", "VG1_FAIL", "VG1_INCOMPLETE"],
    }
    GATE.write_text(json.dumps(gate, indent=2, sort_keys=True) + "\n")
    print(f"Wrote {len(TASKS)} tasks under {BENCH} and {GATE}")


if __name__ == "__main__":
    main()
