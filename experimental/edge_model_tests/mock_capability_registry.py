"""Mock Capability Registry for URI Edge Tool Calling Qualification.

Defines 16 bounded Edge mock tools with full OpenAI/Ollama function calling schemas
and deterministic mock execution responses.
"""
from __future__ import annotations

import json
from typing import Any, Dict, List, Tuple


MOCK_TOOL_DEFINITIONS = [
    {
        "type": "function",
        "function": {
            "name": "find_file",
            "description": "Locate a local file by exact name or wildcard pattern.",
            "parameters": {
                "type": "object",
                "properties": {
                    "name_or_pattern": {"type": "string", "description": "The filename or pattern to search for (e.g. 'budget.xlsx')"}
                },
                "required": ["name_or_pattern"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "get_file_metadata",
            "description": "Retrieve file metadata (size, last modified date, extension) using a resolved file_id.",
            "parameters": {
                "type": "object",
                "properties": {
                    "file_id": {"type": "string", "description": "The unique file ID"}
                },
                "required": ["file_id"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "read_text_range",
            "description": "Read a range of lines from a plain text file.",
            "parameters": {
                "type": "object",
                "properties": {
                    "file_id": {"type": "string", "description": "The unique file ID"},
                    "start": {"type": "integer", "description": "Starting line number (1-indexed)"},
                    "end": {"type": "integer", "description": "Ending line number (inclusive)"}
                },
                "required": ["file_id", "start", "end"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "inspect_spreadsheet",
            "description": "Inspect structural summary (sheet count, sheet names, row/col bounds) of a spreadsheet.",
            "parameters": {
                "type": "object",
                "properties": {
                    "file_id": {"type": "string", "description": "The unique file ID of the spreadsheet"}
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
                    "file_id": {"type": "string", "description": "The unique file ID"}
                },
                "required": ["file_id"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "read_sheet_range",
            "description": "Read cell values from an Excel worksheet given a range address.",
            "parameters": {
                "type": "object",
                "properties": {
                    "file_id": {"type": "string", "description": "The unique file ID"},
                    "sheet": {"type": "string", "description": "Worksheet name (e.g. 'Sheet1')"},
                    "range": {"type": "string", "description": "A1-style range address (e.g. 'B2:D8')"}
                },
                "required": ["file_id", "sheet", "range"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "filter_rows",
            "description": "Filter tabular rows matching specified key-value criteria.",
            "parameters": {
                "type": "object",
                "properties": {
                    "file_id": {"type": "string", "description": "The unique file ID"},
                    "sheet": {"type": "string", "description": "Worksheet name"},
                    "filters": {"type": "object", "description": "Dictionary of column-to-value filters"}
                },
                "required": ["file_id", "sheet", "filters"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "extract_fields",
            "description": "Extract structured entities and fields from unstructured text according to a schema.",
            "parameters": {
                "type": "object",
                "properties": {
                    "text": {"type": "string", "description": "The input text to extract from"},
                    "schema": {"type": "object", "description": "Field definitions schema"}
                },
                "required": ["text", "schema"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "parse_date",
            "description": "Normalize a natural language or regional date string into ISO-8601 YYYY-MM-DD format.",
            "parameters": {
                "type": "object",
                "properties": {
                    "text": {"type": "string", "description": "The date string to parse (e.g. '28/09/2026')"}
                },
                "required": ["text"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "parse_amount",
            "description": "Extract numeric value and currency symbol/code from a currency string.",
            "parameters": {
                "type": "object",
                "properties": {
                    "text": {"type": "string", "description": "The formatted amount (e.g. '₹12,450.50')"}
                },
                "required": ["text"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "normalize_filename",
            "description": "Clean, trim, and standardize a proposed filename for local filesystem safety.",
            "parameters": {
                "type": "object",
                "properties": {
                    "text": {"type": "string", "description": "Raw input filename string"}
                },
                "required": ["text"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "local_search",
            "description": "Search local documents or metadata for keywords.",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "Search terms"},
                    "scope": {"type": "string", "description": "Scope of search (e.g. 'local', 'documents')"}
                },
                "required": ["query", "scope"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "create_draft",
            "description": "Create a local in-memory text draft from verified facts.",
            "parameters": {
                "type": "object",
                "properties": {
                    "content": {"type": "string", "description": "Draft body text"},
                    "format": {"type": "string", "description": "Format type ('paragraph', 'markdown', 'bullets')"}
                },
                "required": ["content", "format"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "fill_template",
            "description": "Populate an approved fixed template with key-value fields.",
            "parameters": {
                "type": "object",
                "properties": {
                    "template_id": {"type": "string", "description": "Approved template ID"},
                    "fields": {"type": "object", "description": "Values to fill into template slots"}
                },
                "required": ["template_id", "fields"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "propose_rename",
            "description": "Propose a safe filename change proposal without executing modification on disk.",
            "parameters": {
                "type": "object",
                "properties": {
                    "file_id": {"type": "string", "description": "Target file ID"},
                    "new_name": {"type": "string", "description": "Proposed new name"}
                },
                "required": ["file_id", "new_name"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "summarize_text",
            "description": "Produce a concise grounded summary of short input text up to max_sentences.",
            "parameters": {
                "type": "object",
                "properties": {
                    "text": {"type": "string", "description": "Input text to summarize"},
                    "max_sentences": {"type": "integer", "description": "Maximum number of sentences allowed"}
                },
                "required": ["text", "max_sentences"]
            }
        }
    }
]

VALID_TOOL_NAMES = {t["function"]["name"] for t in MOCK_TOOL_DEFINITIONS}


class MockToolExecutor:
    """Simulates deterministic runtime execution of mock Edge capabilities."""

    def execute(self, tool_name: str, arguments: Dict[str, Any]) -> Dict[str, Any]:
        if tool_name not in VALID_TOOL_NAMES:
            return {"status": "error", "error": f"Tool '{tool_name}' not registered in capability registry."}

        if tool_name == "find_file":
            pat = arguments.get("name_or_pattern", "")
            if "budget" in pat.lower():
                return {"status": "ok", "file_id": "file_budget_2026", "name": "budget.xlsx", "path": "documents/budget.xlsx", "found": True}
            elif "inventory" in pat.lower():
                return {"status": "ok", "file_id": "file_inventory_99", "name": "inventory.xlsx", "path": "data/inventory.xlsx", "found": True}
            elif "nonexistent" in pat.lower():
                return {"status": "ok", "found": False, "matches": []}
            return {"status": "ok", "file_id": f"file_{pat.replace('.', '_')}", "name": pat, "path": f"files/{pat}", "found": True}

        elif tool_name == "get_file_metadata":
            fid = arguments.get("file_id", "")
            return {
                "status": "ok",
                "file_id": fid,
                "size_bytes": 45120,
                "modified": "2026-09-15T08:30:00Z",
                "mime": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            }

        elif tool_name == "read_text_range":
            fid = arguments.get("file_id", "")
            s = arguments.get("start", 1)
            e = arguments.get("end", 10)
            return {
                "status": "ok",
                "file_id": fid,
                "lines": [f"Line {i}: data entry {i}" for i in range(s, min(e + 1, s + 5))],
                "count": min(e - s + 1, 5)
            }

        elif tool_name == "inspect_spreadsheet":
            fid = arguments.get("file_id", "")
            return {
                "status": "ok",
                "file_id": fid,
                "sheets": ["Sheet1", "Summary"],
                "total_rows": 150,
                "total_columns": 8
            }

        elif tool_name == "list_sheet_names":
            fid = arguments.get("file_id", "")
            return {
                "status": "ok",
                "file_id": fid,
                "sheet_names": ["Sheet1", "Orders", "Archive"]
            }

        elif tool_name == "read_sheet_range":
            fid = arguments.get("file_id", "")
            sheet = arguments.get("sheet", "")
            rng = arguments.get("range", "")
            if sheet == "InvalidSheet":
                return {"status": "error", "error": "sheet_not_found"}
            return {
                "status": "ok",
                "file_id": fid,
                "sheet": sheet,
                "range": rng,
                "cells": [["B2", "C2", "D2"], ["B3", "C3", "D3"]]
            }

        elif tool_name == "filter_rows":
            fid = arguments.get("file_id", "")
            sheet = arguments.get("sheet", "")
            flt = arguments.get("filters", {})
            return {
                "status": "ok",
                "file_id": fid,
                "sheet": sheet,
                "applied_filters": flt,
                "matched_rows": 4,
                "sample": [{"id": 101, "status": "pending", "region": "West", "amount": 250.0}]
            }

        elif tool_name == "extract_fields":
            text = arguments.get("text", "")
            schema = arguments.get("schema", {})
            return {
                "status": "ok",
                "extracted": {
                    "name": "John",
                    "date": "2026-05-01",
                    "amount": "$500"
                }
            }

        elif tool_name == "parse_date":
            txt = arguments.get("text", "")
            return {"status": "ok", "input": txt, "iso_date": "2026-09-28"}

        elif tool_name == "parse_amount":
            txt = arguments.get("text", "")
            return {"status": "ok", "input": txt, "currency": "INR", "symbol": "₹", "amount_numeric": 12450.50}

        elif tool_name == "normalize_filename":
            txt = arguments.get("text", "")
            return {"status": "ok", "original": txt, "normalized": "my_document_1.pdf"}

        elif tool_name == "local_search":
            q = arguments.get("query", "")
            if "hostel rebate" in q.lower():
                return {
                    "status": "ok",
                    "query": q,
                    "matches": [{"file_id": "file_rebate_doc", "snippet": "Hostel rebate approved for spring term.", "line": 12}]
                }
            elif "annual report" in q.lower():
                return {
                    "status": "ok",
                    "query": q,
                    "matches": [{"file_id": "file_annual_report_txt", "snippet": "Annual report executive overview.", "line": 1}]
                }
            return {"status": "ok", "query": q, "matches": []}

        elif tool_name == "create_draft":
            cnt = arguments.get("content", "")
            fmt = arguments.get("format", "paragraph")
            return {"status": "ok", "draft_id": "draft_temp_01", "length": len(cnt), "format": fmt}

        elif tool_name == "fill_template":
            tid = arguments.get("template_id", "")
            flds = arguments.get("fields", {})
            return {"status": "ok", "template_id": tid, "rendered_text": f"Template {tid} rendered with {flds}"}

        elif tool_name == "propose_rename":
            fid = arguments.get("file_id", "")
            new_n = arguments.get("new_name", "")
            return {"status": "ok", "proposal_id": "prop_rename_01", "file_id": fid, "proposed_name": new_n, "executed": False}

        elif tool_name == "summarize_text":
            txt = arguments.get("text", "")
            max_s = arguments.get("max_sentences", 2)
            return {"status": "ok", "summary": "URI operates deterministically. Models serve as untrusted proposers.", "sentences": 2}

        return {"status": "error", "error": "unhandled_tool_execution"}
