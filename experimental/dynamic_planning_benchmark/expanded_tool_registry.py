"""Expanded Tool Registry for Dynamic Multi-Tool Planning Benchmark.
Provides schemas and deterministic implementations for all required capabilities.
Enforces that deterministic tasks (joins, deduplication, interval merging, math)
are executed deterministically in URI Core without model hallucinations.
"""
from __future__ import annotations

import datetime
import json
import re
from typing import Any, Dict, List, Optional, Tuple
from experimental.dynamic_planning_benchmark.mock_data_store import (
    MOCK_WORKBOOKS,
    MOCK_DOCUMENTS,
    GATE_PASS_RECORDS,
    MESS_ATTENDANCE_TABLE,
    TRANSACTIONS_TABLE,
    STUDENT_ROSTER_A,
    STUDENT_ROSTER_B
)

EXPANDED_TOOL_DEFINITIONS = [
    {
        "type": "function",
        "function": {
            "name": "find_file",
            "description": "Find a workbook, document, or dataset file by name or pattern.",
            "parameters": {
                "type": "object",
                "properties": {
                    "name_or_pattern": {"type": "string", "description": "Filename or wildcard pattern"}
                },
                "required": ["name_or_pattern"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "get_file_metadata",
            "description": "Get file metadata (size, format, sheet count or line count).",
            "parameters": {
                "type": "object",
                "properties": {
                    "file_id": {"type": "string", "description": "Verified file identifier"}
                },
                "required": ["file_id"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "inspect_spreadsheet",
            "description": "Inspect structural summary (sheets, row/col counts) of a workbook.",
            "parameters": {
                "type": "object",
                "properties": {
                    "file_id": {"type": "string", "description": "Spreadsheet file handle"}
                },
                "required": ["file_id"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "list_sheet_names",
            "description": "List the names of all worksheets in a workbook.",
            "parameters": {
                "type": "object",
                "properties": {
                    "file_id": {"type": "string", "description": "Spreadsheet file handle"}
                },
                "required": ["file_id"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "read_sheet_range",
            "description": "Read cell range from a worksheet (e.g. A1:D5).",
            "parameters": {
                "type": "object",
                "properties": {
                    "file_id": {"type": "string", "description": "Spreadsheet file handle"},
                    "sheet": {"type": "string", "description": "Sheet name"},
                    "range": {"type": "string", "description": "Range address (e.g. 'A1:D5')"}
                },
                "required": ["file_id", "sheet", "range"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "read_table",
            "description": "Read a structured tabular dataset by table name.",
            "parameters": {
                "type": "object",
                "properties": {
                    "table_name": {"type": "string", "description": "Name of the table ('gate_pass', 'mess_attendance', 'transactions', 'roster_a', 'roster_b')"}
                },
                "required": ["table_name"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "filter_rows",
            "description": "Filter rows matching column criteria.",
            "parameters": {
                "type": "object",
                "properties": {
                    "table_handle": {"type": "string", "description": "Table identifier or data handle"},
                    "criteria": {"type": "object", "description": "Key-value dictionary of filter constraints"}
                },
                "required": ["table_handle", "criteria"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "sort_rows",
            "description": "Sort table rows by one or more columns.",
            "parameters": {
                "type": "object",
                "properties": {
                    "table_handle": {"type": "string", "description": "Table handle"},
                    "by_column": {"type": "string", "description": "Column to sort by"},
                    "ascending": {"type": "boolean", "description": "Sort ascending if true"}
                },
                "required": ["table_handle", "by_column"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "group_rows",
            "description": "Group tabular records by key column.",
            "parameters": {
                "type": "object",
                "properties": {
                    "table_handle": {"type": "string", "description": "Table handle"},
                    "key_column": {"type": "string", "description": "Column name to group by"}
                },
                "required": ["table_handle", "key_column"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "join_tables",
            "description": "Join two tables on a shared key column.",
            "parameters": {
                "type": "object",
                "properties": {
                    "left_table": {"type": "string", "description": "Handle to left table"},
                    "right_table": {"type": "string", "description": "Handle to right table"},
                    "on_key": {"type": "string", "description": "Shared key column (e.g. 'roll_no')"},
                    "how": {"type": "string", "enum": ["inner", "left", "outer"], "description": "Join type"}
                },
                "required": ["left_table", "right_table", "on_key"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "deduplicate_rows",
            "description": "Remove duplicate rows based on unique key columns.",
            "parameters": {
                "type": "object",
                "properties": {
                    "table_handle": {"type": "string", "description": "Table handle"},
                    "subset_keys": {"type": "array", "items": {"type": "string"}, "description": "Columns defining uniqueness"}
                },
                "required": ["table_handle", "subset_keys"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "normalize_date",
            "description": "Convert dates in a table column or text into ISO-8601 YYYY-MM-DD.",
            "parameters": {
                "type": "object",
                "properties": {
                    "text_or_date": {"type": "string", "description": "Date string to parse"}
                },
                "required": ["text_or_date"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "normalize_identifier",
            "description": "Normalize identifiers (e.g. roll numbers) into standardized uppercase format.",
            "parameters": {
                "type": "object",
                "properties": {
                    "identifier": {"type": "string", "description": "Raw identifier string"}
                },
                "required": ["identifier"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "merge_date_intervals",
            "description": "Merge contiguous or overlapping date intervals [start, end] into disjoint continuous periods.",
            "parameters": {
                "type": "object",
                "properties": {
                    "intervals": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "start": {"type": "string"},
                                "end": {"type": "string"}
                            },
                            "required": ["start", "end"]
                        }
                    }
                },
                "required": ["intervals"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "calculate_date_span",
            "description": "Calculate day count between start and end dates (inclusive).",
            "parameters": {
                "type": "object",
                "properties": {
                    "start_date": {"type": "string", "description": "Start date (YYYY-MM-DD)"},
                    "end_date": {"type": "string", "description": "End date (YYYY-MM-DD)"}
                },
                "required": ["start_date", "end_date"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "calculate",
            "description": "Execute deterministic arithmetic on numbers.",
            "parameters": {
                "type": "object",
                "properties": {
                    "expression": {"type": "string", "description": "Math expression (e.g. '145 * 10')"}
                },
                "required": ["expression"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "aggregate",
            "description": "Calculate sum, mean, min, max, or count on a table column.",
            "parameters": {
                "type": "object",
                "properties": {
                    "table_handle": {"type": "string", "description": "Table handle"},
                    "column": {"type": "string", "description": "Numeric column name"},
                    "operation": {"type": "string", "enum": ["sum", "mean", "min", "max", "count"]}
                },
                "required": ["table_handle", "column", "operation"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "local_search",
            "description": "Search text documents for keywords.",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "Search keyword"}
                },
                "required": ["query"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "read_text_range",
            "description": "Read lines from start to end in a text document.",
            "parameters": {
                "type": "object",
                "properties": {
                    "file_id": {"type": "string", "description": "Document handle"},
                    "start": {"type": "integer", "description": "Start line number"},
                    "end": {"type": "integer", "description": "End line number"}
                },
                "required": ["file_id", "start", "end"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "extract_fields",
            "description": "Extract grounded entities from unstructured text.",
            "parameters": {
                "type": "object",
                "properties": {
                    "text": {"type": "string", "description": "Text to extract from"}
                },
                "required": ["text"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "fill_template",
            "description": "Fill named placeholders in a document template.",
            "parameters": {
                "type": "object",
                "properties": {
                    "template_id": {"type": "string", "description": "Template identifier"},
                    "values": {"type": "object", "description": "Placeholder values"}
                },
                "required": ["template_id", "values"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "create_output_draft",
            "description": "Create a new verified output report or summary.",
            "parameters": {
                "type": "object",
                "properties": {
                    "title": {"type": "string", "description": "Title of output artifact"},
                    "content": {"type": "string", "description": "Formatted body text"}
                },
                "required": ["title", "content"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "validate_schema",
            "description": "Validate that a dataset conforms to required columns and data types.",
            "parameters": {
                "type": "object",
                "properties": {
                    "table_handle": {"type": "string", "description": "Table handle"},
                    "required_columns": {"type": "array", "items": {"type": "string"}}
                },
                "required": ["table_handle", "required_columns"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "compare_datasets",
            "description": "Compare two datasets and identify matching, missing, or mismatched records.",
            "parameters": {
                "type": "object",
                "properties": {
                    "table_a": {"type": "string", "description": "Handle to first table"},
                    "table_b": {"type": "string", "description": "Handle to second table"},
                    "key_column": {"type": "string", "description": "Unique key to compare"}
                },
                "required": ["table_a", "table_b", "key_column"]
            }
        }
    }
]

TOOL_DEF_MAP = {t["function"]["name"]: t for t in EXPANDED_TOOL_DEFINITIONS}


class DeterministicExecutionEngine:
    """Executes deterministic capabilities with exact algorithms."""

    def __init__(self):
        self.table_store: Dict[str, List[Dict[str, Any]]] = {
            "gate_pass": [dict(r) for r in GATE_PASS_RECORDS],
            "mess_attendance": [dict(r) for r in MESS_ATTENDANCE_TABLE],
            "transactions": [dict(r) for r in TRANSACTIONS_TABLE],
            "roster_a": [dict(r) for r in STUDENT_ROSTER_A],
            "roster_b": [dict(r) for r in STUDENT_ROSTER_B]
        }
        self.handle_counter = 0

    def _new_handle(self, prefix: str = "tbl") -> str:
        self.handle_counter += 1
        return f"{prefix}_{self.handle_counter:03d}"

    def execute(self, tool_name: str, args: Dict[str, Any]) -> Dict[str, Any]:
        if tool_name == "find_file":
            pattern = args.get("name_or_pattern", "").lower()
            for fname, info in MOCK_WORKBOOKS.items():
                if pattern in fname.lower() or fname.lower() in pattern:
                    return {"status": "ok", "found": True, "file_id": info["file_id"], "name": fname}
            for fid, info in MOCK_DOCUMENTS.items():
                if pattern in info["filename"].lower():
                    return {"status": "ok", "found": True, "file_id": fid, "name": info["filename"]}
            return {"status": "ok", "found": False}

        elif tool_name == "get_file_metadata":
            fid = args.get("file_id")
            for fname, info in MOCK_WORKBOOKS.items():
                if info["file_id"] == fid:
                    return {"status": "ok", "file_id": fid, "type": "workbook", "sheets": len(info["sheets"])}
            if fid in MOCK_DOCUMENTS:
                return {"status": "ok", "file_id": fid, "type": "text", "lines": len(MOCK_DOCUMENTS[fid]["content"].splitlines())}
            return {"status": "error", "error": "file_not_found"}

        elif tool_name == "inspect_spreadsheet":
            fid = args.get("file_id")
            for fname, info in MOCK_WORKBOOKS.items():
                if info["file_id"] == fid:
                    return {"status": "ok", "file_id": fid, "sheets": list(info["sheets"].keys())}
            return {"status": "error", "error": "file_not_found"}

        elif tool_name == "list_sheet_names":
            fid = args.get("file_id")
            for fname, info in MOCK_WORKBOOKS.items():
                if info["file_id"] == fid:
                    return {"status": "ok", "file_id": fid, "sheet_names": list(info["sheets"].keys())}
            return {"status": "error", "error": "file_not_found"}

        elif tool_name == "read_sheet_range":
            fid = args.get("file_id")
            sheet = args.get("sheet")
            for fname, info in MOCK_WORKBOOKS.items():
                if info["file_id"] == fid:
                    if sheet in info["sheets"]:
                        return {"status": "ok", "file_id": fid, "sheet": sheet, "cells": info["sheets"][sheet]}
            return {"status": "error", "error": "sheet_not_found"}

        elif tool_name == "read_table":
            tname = args.get("table_name", "").lower()
            for k in self.table_store:
                if tname in k or k in tname:
                    h = self._new_handle("tbl")
                    self.table_store[h] = [dict(r) for r in self.table_store[k]]
                    return {"status": "ok", "table_handle": h, "rows_count": len(self.table_store[h]), "columns": list(self.table_store[h][0].keys()) if self.table_store[h] else []}
            return {"status": "error", "error": f"Table '{tname}' not found"}

        elif tool_name == "filter_rows":
            h = args.get("table_handle")
            crit = args.get("criteria", {})
            rows = self.table_store.get(h, [])
            filtered = []
            for r in rows:
                match = True
                for ck, cv in crit.items():
                    if str(r.get(ck, "")).strip().lower() != str(cv).strip().lower():
                        match = False
                        break
                if match:
                    filtered.append(r)
            out_h = self._new_handle("filtered")
            self.table_store[out_h] = filtered
            return {"status": "ok", "table_handle": out_h, "count": len(filtered), "rows": filtered}

        elif tool_name == "sort_rows":
            h = args.get("table_handle")
            col = args.get("by_column")
            asc = args.get("ascending", True)
            rows = list(self.table_store.get(h, []))
            rows.sort(key=lambda x: x.get(col, 0), reverse=not asc)
            out_h = self._new_handle("sorted")
            self.table_store[out_h] = rows
            return {"status": "ok", "table_handle": out_h, "rows": rows}

        elif tool_name == "group_rows":
            h = args.get("table_handle")
            key = args.get("key_column")
            rows = self.table_store.get(h, [])
            groups: Dict[str, List[Dict[str, Any]]] = {}
            for r in rows:
                k_val = str(r.get(key, ""))
                groups.setdefault(k_val, []).append(r)
            return {"status": "ok", "group_count": len(groups), "groups": groups}

        elif tool_name == "deduplicate_rows":
            h = args.get("table_handle")
            keys = args.get("subset_keys", [])
            rows = self.table_store.get(h, [])
            seen = set()
            deduped = []
            for r in rows:
                k_tuple = tuple(str(r.get(k, "")).strip().lower() for k in keys)
                if k_tuple not in seen:
                    seen.add(k_tuple)
                    deduped.append(r)
            out_h = self._new_handle("deduped")
            self.table_store[out_h] = deduped
            return {"status": "ok", "table_handle": out_h, "removed": len(rows) - len(deduped), "count": len(deduped), "rows": deduped}

        elif tool_name == "join_tables":
            left_h = args.get("left_table")
            right_h = args.get("right_table")
            on_k = args.get("on_key")
            how = args.get("how", "inner")
            left_rows = self.table_store.get(left_h, [])
            right_rows = self.table_store.get(right_h, [])
            right_map = {str(r.get(on_k, "")).strip().upper(): r for r in right_rows}

            joined = []
            unmatched_left = []
            for lr in left_rows:
                k_val = str(lr.get(on_k, "")).strip().upper()
                if k_val in right_map:
                    merged = dict(lr)
                    merged.update(right_map[k_val])
                    joined.append(merged)
                else:
                    unmatched_left.append(lr)
                    if how == "left":
                        joined.append(dict(lr))
            out_h = self._new_handle("joined")
            self.table_store[out_h] = joined
            return {"status": "ok", "table_handle": out_h, "joined_count": len(joined), "unmatched_count": len(unmatched_left), "rows": joined}

        elif tool_name == "normalize_date":
            raw = str(args.get("text_or_date", ""))
            # Support DD/MM/YYYY or YYYY-MM-DD
            d_obj = None
            for fmt in ["%d/%m/%Y", "%Y-%m-%d", "%d-%m-%Y"]:
                try:
                    d_obj = datetime.datetime.strptime(raw.strip(), fmt).date()
                    break
                except ValueError:
                    pass
            if d_obj:
                return {"status": "ok", "iso_date": d_obj.isoformat()}
            return {"status": "error", "error": f"Invalid date: {raw}"}

        elif tool_name == "normalize_identifier":
            raw = str(args.get("identifier", ""))
            clean = raw.strip().upper()
            return {"status": "ok", "normalized": clean}

        elif tool_name == "merge_date_intervals":
            intervals = args.get("intervals", [])
            # Parse intervals into (start, end) dates
            parsed = []
            for item in intervals:
                s_str = item.get("start")
                e_str = item.get("end")
                try:
                    s_d = datetime.date.fromisoformat(s_str)
                    e_d = datetime.date.fromisoformat(e_str)
                    parsed.append((s_d, e_d))
                except Exception:
                    pass
            if not parsed:
                return {"status": "ok", "merged": [], "total_span_days": 0}

            # Sort by start date
            parsed.sort(key=lambda x: x[0])
            merged = [parsed[0]]
            for curr_start, curr_end in parsed[1:]:
                prev_start, prev_end = merged[-1]
                # If contiguous or overlapping (curr_start <= prev_end + 1 day)
                if curr_start <= prev_end + datetime.timedelta(days=1):
                    merged[-1] = (prev_start, max(prev_end, curr_end))
                else:
                    merged.append((curr_start, curr_end))

            total_days = sum((e - s).days + 1 for s, e in merged)
            res_list = [{"start": s.isoformat(), "end": e.isoformat(), "days": (e - s).days + 1} for s, e in merged]
            return {"status": "ok", "merged": res_list, "total_span_days": total_days}

        elif tool_name == "calculate_date_span":
            s_str = args.get("start_date")
            e_str = args.get("end_date")
            s = datetime.date.fromisoformat(s_str)
            e = datetime.date.fromisoformat(e_str)
            span = (e - s).days + 1
            return {"status": "ok", "days": span}

        elif tool_name == "calculate":
            expr = args.get("expression", "")
            # Safe math evaluation using basic arithmetic
            allowed = re.compile(r"^[\d\s\+\-\*\/\(\)\.]+$")
            if allowed.match(expr):
                val = eval(expr)
                return {"status": "ok", "result": val}
            return {"status": "error", "error": "Invalid arithmetic expression"}

        elif tool_name == "aggregate":
            h = args.get("table_handle")
            col = args.get("column")
            op = args.get("operation", "sum")
            rows = self.table_store.get(h, [])
            vals = [float(r[col]) for r in rows if col in r and isinstance(r[col], (int, float))]
            if not vals:
                return {"status": "ok", "value": 0}
            if op == "sum":
                ans = sum(vals)
            elif op == "mean":
                ans = sum(vals) / len(vals)
            elif op == "min":
                ans = min(vals)
            elif op == "max":
                ans = max(vals)
            elif op == "count":
                ans = len(vals)
            else:
                ans = sum(vals)
            return {"status": "ok", "operation": op, "column": col, "value": ans}

        elif tool_name == "local_search":
            query = args.get("query", "").lower()
            matches = []
            for fid, doc in MOCK_DOCUMENTS.items():
                if query in doc["content"].lower():
                    matches.append({"file_id": fid, "filename": doc["filename"]})
            return {"status": "ok", "matches": matches, "found": len(matches) > 0}

        elif tool_name == "read_text_range":
            fid = args.get("file_id")
            s = int(args.get("start", 1))
            e = int(args.get("end", 5))
            if fid in MOCK_DOCUMENTS:
                lines = MOCK_DOCUMENTS[fid]["content"].splitlines()
                slice_lines = lines[s - 1:e]
                return {"status": "ok", "file_id": fid, "lines": slice_lines}
            return {"status": "error", "error": "doc_not_found"}

        elif tool_name == "extract_fields":
            text = args.get("text", "")
            # Extraction
            return {"status": "ok", "extracted": {"text_length": len(text)}}

        elif tool_name == "fill_template":
            tpl = args.get("template_id", "")
            vals = args.get("values", {})
            return {"status": "ok", "rendered": f"Template {tpl} populated with {len(vals)} keys."}

        elif tool_name == "create_output_draft":
            title = args.get("title", "Draft")
            content = args.get("content", "")
            return {"status": "ok", "artifact_title": title, "bytes": len(content)}

        elif tool_name == "compare_datasets":
            ta_h = args.get("table_a")
            tb_h = args.get("table_b")
            k_col = args.get("key_column")
            ta = self.table_store.get(ta_h, [])
            tb = self.table_store.get(tb_h, [])
            keys_a = {str(r.get(k_col, "")).strip().upper() for r in ta}
            keys_b = {str(r.get(k_col, "")).strip().upper() for r in tb}
            matched = list(keys_a.intersection(keys_b))
            only_in_a = list(keys_a - keys_b)
            only_in_b = list(keys_b - keys_a)
            return {"status": "ok", "matched_count": len(matched), "only_in_a": only_in_a, "only_in_b": only_in_b}

        elif tool_name == "validate_schema":
            h = args.get("table_handle")
            req = args.get("required_columns", [])
            rows = self.table_store.get(h, [])
            if not rows:
                return {"status": "ok", "valid": True}
            missing = [c for c in req if c not in rows[0]]
            return {"status": "ok", "valid": len(missing) == 0, "missing": missing}

        return {"status": "error", "error": f"Unknown tool: {tool_name}"}
