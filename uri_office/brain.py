"""One Brain call per owner instruction in the Office panel (AC13, AC16).

Same call shape as `uri_operational_intelligence.draft_desk.DraftDesk._call`: Runtime v1 through `BrainClient`, FAST
tier (thinking off, temperature 0), strict JSON schema (`ops.BRAIN_SCHEMA`). The owner's instruction is the only
instruction; the sheet excerpt and the correction history go inside one untrusted-data block. Every returned op is
validated by `ops.to_cell_edits`; invalid ops are reported back, never repaired by guessing.

The Brain host holds the GPU lease (scripts/ws_brain_host.py); this module never starts a Runtime.
"""
from __future__ import annotations

import copy
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
MAX_FINDINGS = 100

SYSTEM = (
    "You are URI's spreadsheet assistant. You change a workbook only by returning ops in the required JSON schema. "
    "Allowed ops: set_values (sheet, range like A1:C3, values as rows), set_formula (sheet, cell, formula starting "
    "with '='){google}. Set every field you do not use to null. Never use formulas that reach the network, other "
    "programs or other files. If the instruction is unclear or cannot be done with these ops, return no ops and say "
    "why in message. Keep message short. " + SYSTEM_RULE)


COPY_TEXT = (
    "copy_range (source id like S1, from_sheet, from_range like A1:D200, sheet, cell = top-left target cell) copies a "
    "reference file's values into the target, for example {\"op\": \"copy_range\", \"source\": \"S1\", "
    "\"from_sheet\": \"Data\", \"from_range\": \"A1:B4\", \"sheet\": \"Summary\", \"cell\": \"A1\"}: source is the "
    "file's id and from_sheet is a sheet name inside that file. To copy every row of a table, end the range without a "
    "row number: \"A1:B\" copies from row 1 to the last used row and \"A2:B\" skips a header row. The target cell may "
    "be just a column letter such as \"A\": the copy then starts at the first empty row below what those columns "
    "already hold, which stacks tables without counting rows. A copy of N rows starting at row R fills rows R to "
    "R+N-1; never write a cell that an earlier op in the same answer already wrote. ")

CHECK_TEXT = (
    "The owner asked you to CHECK the working file: compare it with the reference files where they apply and look for "
    "errors such as wrong values, wrong totals or formulas, missing or duplicated rows and inconsistent entries. Put "
    "every issue in findings (sheet, cell or null, issue in a short sentence). Where the right value is clear, also "
    "return an op that fixes it; where it is not clear, only report it. If nothing is wrong, return no findings and "
    "say so in message. ")


def system_for(engine: str, task: str) -> str:
    """The system prompt when the owner added files with roles (M2-D10/D11)."""
    if engine == "new":
        head = ("You are URI's spreadsheet assistant. You build a NEW workbook from the owner's reference files, only "
                "by returning ops in the required JSON schema. Allowed ops: add_sheet (name), rename_sheet (sheet, "
                "name), set_values (sheet, range like A1:C3, values as rows), set_formula (sheet, cell, formula "
                "starting with '='), and ")
        tail = ("Ops run in order, so add a sheet before writing to it. Formulas may refer only to sheets of the new "
                "workbook. ")
    else:
        head = ("You are URI's spreadsheet assistant. You work on the owner's WORKING file (the workbook shown); the "
                "other files are read-only references. You change the working file only by returning ops in the "
                "required JSON schema. Allowed ops: set_values (sheet, range like A1:C3, values as rows), set_formula "
                "(sheet, cell, formula starting with '='), and ")
        tail = "Formulas may refer only to sheets of the working file. "
    return (head + COPY_TEXT + (CHECK_TEXT if task == "check" else "") + tail
            + "The reference files are only shown in part; use copy_range to move data you have not seen cell by "
              "cell. Set every field you do not use to null. Never use formulas that reach the network, other "
              "programs or other files. If the instruction is unclear or cannot be done with these ops, return no "
              "ops and say why in message. Keep message short. " + SYSTEM_RULE)


SYSTEM_NEW = system_for("new", "build")


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


def excerpt_all(sheets: list) -> dict:
    """New workbook (M2): every sheet's size and non-empty cells, within the same total cap, so URI sees what was
    already accepted on any sheet (the first sheet is often still empty)."""
    out = {"sheets": [], "cells_omitted": 0}
    budget = MAX_EXCERPT_CELLS
    for sh in sheets:
        cells = {}
        rows = sorted(sh["cells"].items(), key=lambda kv: (refs.parse_cell(kv[0])[1], refs.parse_cell(kv[0])[0]))
        for ref, c in rows:
            v = c.get("f") or c.get("v")
            if v is None:
                continue
            if budget <= 0:
                out["cells_omitted"] += 1
                continue
            cells[ref] = v
            budget -= 1
        out["sheets"].append({"name": sh["name"], "rows": sh["max_row"], "cols": sh["max_col"], "cells": cells})
    if not out["cells_omitted"]:
        del out["cells_omitted"]
    return out


def schema_for(engine: str, source_view: list | None, task: str = "build") -> dict:
    """The strict output schema. For a new workbook the source id and source sheet fields are limited to the sources
    that exist, so the decoder cannot put a file id where a sheet name belongs (seen on the PC, 2026-10-12)."""
    if source_view is None:
        return O.BRAIN_SCHEMA
    sch = copy.deepcopy(O.BRAIN_SCHEMA)
    props = sch["properties"]["ops"]["items"]["properties"]
    ids = [x["source"] for x in source_view or []]
    names = sorted({sh["name"] for x in source_view or [] for sh in x["sheets"]})
    props["source"] = {"type": ["string", "null"], "enum": ids + [None]}
    props["from_sheet"] = {"type": ["string", "null"], "enum": names + [None]}
    if task == "check":
        sch["required"] = sch["required"] + ["findings"]
        sch["properties"]["findings"] = {"type": "array", "maxItems": MAX_FINDINGS, "items": {
            "type": "object", "additionalProperties": False, "required": ["sheet", "cell", "issue"],
            "properties": {"sheet": {"type": ["string", "null"]}, "cell": {"type": ["string", "null"]},
                           "issue": {"type": "string"}}}}
    return sch


def build_body(instruction: str, view: dict, history_rows: list, engine: str, source_view: list | None = None,
               task: str = "build") -> dict:
    if source_view is not None:
        system = system_for(engine, task)
        user = (f"Owner instruction:\n{instruction}\n\n"
                + data_block("the new workbook so far" if engine == "new" else "the working file", view) + "\n\n"
                + data_block("reference files (read-only; first rows of each sheet)", source_view))
    else:
        system = SYSTEM.format(google="; for Google Sheets also insert_rows, delete_rows (sheet, at, count), add_sheet "
                                      "(name), rename_sheet (sheet, name)" if engine == "google" else "")
        user = (f"Owner instruction:\n{instruction}\n\n"
                + data_block("workbook", view) + "\n\n"
                + data_block("correction history for this workbook (what changed and why)",
                             [{k: r.get(k) for k in ("kind", "sheet", "cell", "reason")} for r in history_rows]))
    return {"model": "local", "messages": [{"role": "system", "content": system}, {"role": "user", "content": user}],
            "response_format": {"type": "json_schema",
                                "json_schema": {"name": "office_ops", "schema": schema_for(engine, source_view, task),
                                                "strict": True}},
            **tier_params(FAST, use="answer", max_tokens=MAX_TOKENS)}


def _next_row(sheets: list, written: set, sheet: str, c1: int, c2: int) -> int:
    """First row below every non-empty cell of columns c1..c2 of `sheet`: the draft as it is now plus the cells earlier
    ops of the same answer wrote."""
    last = 0
    for sh in sheets:
        if sh["name"] == sheet:
            for ref, c in sh["cells"].items():
                col, row = refs.parse_cell(ref)
                if c1 <= col <= c2 and (c.get("f") or c.get("v") not in (None, "")):
                    last = max(last, row)
    for s_name, ref in written:
        if s_name == sheet:
            col, row = refs.parse_cell(ref)
            if c1 <= col <= c2:
                last = max(last, row)
    return last + 1


class OfficeBrain:
    def __init__(self, client):
        self.client = client

    def plan(self, instruction: str, *, sheets: list, active: str | None, engine: str, locked: dict,
             history_rows: list, cancel=None, sources: list | None = None, task: str = "build") -> dict:
        """`sources` (M2): the reference files when the owner added files with roles; `task` is build (no working
        file: a new workbook), edit or check (the working file)."""
        if not isinstance(instruction, str) or not instruction.strip():
            raise OfficeError("EMPTY_INSTRUCTION")
        if len(instruction) > MAX_INSTRUCTION:
            raise OfficeError("INSTRUCTION_TOO_LONG")
        with_files = sources is not None
        view = excerpt_all(sheets) if with_files or engine == "new" else excerpt(sheets, active)
        # One budget for the whole request: the reference files get what the workbook's excerpt left (Codex R2-04).
        used = sum(len(sh["cells"]) for sh in view.get("sheets", ())) if with_files else 0
        body = build_body(instruction.strip(), view, history_rows, engine,
                          SRC.excerpt(sources, max(0, MAX_EXCERPT_CELLS - used)) if with_files else None, task)
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
        written: set = set()                 # cells written by earlier ops of this answer
        for i, op in enumerate(data["ops"][:20]):
            if isinstance(op, dict):
                op = {k: v for k, v in op.items() if v is not None}
            try:
                if with_files and isinstance(op, dict) and op.get("op") in O.SOURCE_OPS:
                    got, unc, skipped = O.copy_edits(op, sources=src, sheets=names, locked=locked,
                                                     next_free_row=lambda sh, a, b: _next_row(sheets, written, sh, a, b))
                    notes["uncalculated"] += unc
                    notes["not_copied"] += skipped
                else:
                    got = O.to_cell_edits(op, engine=engine, sheets=names, locked=locked)
                # An op that would overwrite a cell an earlier op of the same answer wrote is a planning slip (for example
                # a total placed on a copied row): it is refused and reported, never merged or moved.
                hit = next((e for e in got if "cell" in e and (e["sheet"], e["cell"]) in written), None)
                if hit is not None:
                    raise OfficeError("OVERLAPS_EARLIER_OP", f"{hit['sheet']}!{hit['cell']} was already written by an "
                                                             "earlier change in this answer")
                written.update((e["sheet"], e["cell"]) for e in got           # an empty value loses nothing
                               if "cell" in e and (e.get("formula") or e.get("value") not in (None, "")))
                edits += got
                for e in got:            # later ops in the same answer see the sheets earlier ops made (M2-D4)
                    if e.get("op") == "add_sheet":
                        names.append(e["name"])
                    elif e.get("op") == "rename_sheet":
                        names = [e["name"] if n == e["sheet"] else n for n in names]
            except OfficeError as exc:
                refused.append({"index": i, "code": exc.code, "detail": exc.detail})
        msg = data.get("message") if isinstance(data.get("message"), str) else ""
        out_findings = None
        if task == "check":
            out_findings = []
            for f in (data.get("findings") or [])[:MAX_FINDINGS]:
                if not isinstance(f, dict) or not isinstance(f.get("issue"), str) or not f["issue"].strip():
                    continue
                sheet = f.get("sheet") if f.get("sheet") in names else None
                try:
                    cell = refs.canonical_cell(f["cell"]) if sheet and f.get("cell") else None
                except OfficeError:
                    cell = None
                out_findings.append({"sheet": sheet, "cell": cell, "issue": f["issue"].strip()[:300]})
        return {"message": msg[:1000], "edits": edits, "refused": refused, "notes": notes, "findings": out_findings,
                "metrics": {"ttft_s": res.ttft_s, "total_s": res.total_s,
                            "predicted_per_second": (res.timings or {}).get("predicted_per_second")}}
