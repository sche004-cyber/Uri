"""One Brain call per owner instruction in the Office panel (AC13, AC16).

Same call shape as `uri_operational_intelligence.draft_desk.DraftDesk._call`: Runtime v1 through `BrainClient`, FAST
tier (thinking off, temperature 0), strict JSON schema (`ops.BRAIN_SCHEMA`). The owner's instruction is the only
instruction; the sheet excerpt and the correction history go inside one untrusted-data block. Every returned op is
validated by `ops.to_cell_edits`; invalid ops are reported back, never repaired by guessing.

The Brain host holds the GPU lease (scripts/ws_brain_host.py); this module never starts a Runtime.
"""
from __future__ import annotations

import json

from uri_operational_intelligence import brain_client as BC
from uri_operational_intelligence.reasoning_policy import FAST, tier_params

from . import ops as O
from . import refs
from . import sources as SRC
from .errors import OfficeError
from .untrusted import SYSTEM_RULE, data_block

TIMEOUT = BC.Deadlines(first_token_s=60.0, idle_s=30.0, total_s=180.0)
MAX_TOKENS = 2000
MAX_EXCERPT_CELLS = 600
MAX_INSTRUCTION = 2000

SYSTEM = (
    "You are URI's spreadsheet assistant. You change a workbook only by returning ops in the required JSON schema. "
    "Allowed ops: set_values (sheet, range like A1:C3, values as rows), set_formula (sheet, cell, formula starting "
    "with '='){google}. Set every field you do not use to null. Never use formulas that reach the network, other "
    "programs or other files. If the instruction is unclear or cannot be done with these ops, return no ops and say "
    "why in message. Keep message short. " + SYSTEM_RULE)


SYSTEM_NEW = (
    "You are URI's spreadsheet assistant. You build a NEW workbook from the owner's source files, only by returning "
    "ops in the required JSON schema. Allowed ops: add_sheet (name), rename_sheet (sheet, name), set_values (sheet, "
    "range like A1:C3, values as rows), set_formula (sheet, cell, formula starting with '=') and copy_range (source "
    "id like S1, from_sheet, from_range like A1:D200, sheet, cell = top-left target cell) which copies the source "
    "range's values into the new workbook. Ops run in order, so add a sheet before writing to it. The sources are "
    "only shown in part; use copy_range to move data you have not seen cell by cell. Formulas may refer only to "
    "sheets of the new workbook. Set every field you do not use to null. Never use formulas that reach the network, "
    "other programs or other files. If the instruction is unclear or cannot be done with these ops, return no ops "
    "and say why in message. Keep message short. " + SYSTEM_RULE)


def excerpt(sheets: list, active: str | None) -> dict:
    """A bounded view: every sheet's name and size, and the active sheet's non-empty cells (values or formulas)."""
    out = {"sheets": [{"name": s["name"], "rows": s["max_row"], "cols": s["max_col"]} for s in sheets], "cells": {}}
    sheet = next((s for s in sheets if s["name"] == active), sheets[0] if sheets else None)
    if sheet is None:
        return out
    out["active_sheet"] = sheet["name"]
    cells = sorted(sheet["cells"].items(), key=lambda kv: (refs.parse_cell(kv[0])[1], refs.parse_cell(kv[0])[0]))
    for ref, c in cells[:MAX_EXCERPT_CELLS]:
        out["cells"][ref] = c.get("f") or c.get("v")
    if len(cells) > MAX_EXCERPT_CELLS:
        out["cells_omitted"] = len(cells) - MAX_EXCERPT_CELLS
    return out


def build_body(instruction: str, view: dict, history_rows: list, engine: str, source_view: list | None = None) -> dict:
    if engine == "new":
        system = SYSTEM_NEW
        user = (f"Owner instruction:\n{instruction}\n\n"
                + data_block("the new workbook so far", view) + "\n\n"
                + data_block("source files (read-only; first rows of each sheet)", source_view or []))
    else:
        system = SYSTEM.format(google="; for Google Sheets also insert_rows, delete_rows (sheet, at, count), add_sheet "
                                      "(name), rename_sheet (sheet, name)" if engine == "google" else "")
        user = (f"Owner instruction:\n{instruction}\n\n"
                + data_block("workbook", view) + "\n\n"
                + data_block("correction history for this workbook (what changed and why)",
                             [{k: r.get(k) for k in ("kind", "sheet", "cell", "reason")} for r in history_rows]))
    return {"model": "local", "messages": [{"role": "system", "content": system}, {"role": "user", "content": user}],
            "response_format": {"type": "json_schema",
                                "json_schema": {"name": "office_ops", "schema": O.BRAIN_SCHEMA, "strict": True}},
            **tier_params(FAST, use="answer", max_tokens=MAX_TOKENS)}


class OfficeBrain:
    def __init__(self, client):
        self.client = client

    def plan(self, instruction: str, *, sheets: list, active: str | None, engine: str, locked: dict,
             history_rows: list, cancel=None, sources: list | None = None) -> dict:
        if not isinstance(instruction, str) or not instruction.strip():
            raise OfficeError("EMPTY_INSTRUCTION")
        if len(instruction) > MAX_INSTRUCTION:
            raise OfficeError("INSTRUCTION_TOO_LONG")
        body = build_body(instruction.strip(), excerpt(sheets, active), history_rows, engine,
                          SRC.excerpt(sources or []) if engine == "new" else None)
        res = self.client.stream_chat(body, cancel=cancel or BC.CancelToken(), deadlines=TIMEOUT)
        if res.status == BC.CANCELLED:
            raise OfficeError("CANCELLED", "Stopped. Nothing was changed.")
        if res.status == BC.UNREACHABLE:
            raise OfficeError("BRAIN_UNAVAILABLE", "The local Brain is not running; nothing was changed.", 503)
        if res.status != BC.COMPLETE:
            raise OfficeError("BRAIN_" + res.status, "The local Brain did not finish; nothing was changed.", 503)
        try:
            data = json.loads(res.text)
        except ValueError:
            raise OfficeError("BRAIN_OUTPUT_INVALID", "The Brain's answer was not usable; nothing was changed.") from None
        if not isinstance(data, dict) or not isinstance(data.get("ops"), list):
            raise OfficeError("BRAIN_OUTPUT_INVALID", "The Brain's answer was not usable; nothing was changed.")
        names = [s["name"] for s in sheets]
        src = SRC.by_id(sources or [])
        edits, refused = [], []
        notes = {"uncalculated": 0, "not_copied": 0}
        for i, op in enumerate(data["ops"][:20]):
            if isinstance(op, dict):
                op = {k: v for k, v in op.items() if v is not None}
            try:
                if engine == "new" and isinstance(op, dict) and op.get("op") in O.SOURCE_OPS:
                    got, unc, skipped = O.copy_edits(op, sources=src, sheets=names)
                    notes["uncalculated"] += unc
                    notes["not_copied"] += skipped
                else:
                    got = O.to_cell_edits(op, engine=engine, sheets=names, locked=locked)
                edits += got
                for e in got:            # later ops in the same answer see the sheets earlier ops made (M2-D4)
                    if e.get("op") == "add_sheet":
                        names.append(e["name"])
                    elif e.get("op") == "rename_sheet":
                        names = [e["name"] if n == e["sheet"] else n for n in names]
            except OfficeError as exc:
                refused.append({"index": i, "code": exc.code, "detail": exc.detail})
        msg = data.get("message") if isinstance(data.get("message"), str) else ""
        return {"message": msg[:1000], "edits": edits, "refused": refused, "notes": notes,
                "metrics": {"ttft_s": res.ttft_s, "total_s": res.total_s,
                            "predicted_per_second": (res.timings or {}).get("predicted_per_second")}}
