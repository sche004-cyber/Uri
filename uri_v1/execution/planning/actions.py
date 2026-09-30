"""The four slice-1 actions and the capability snapshot they project (Stage 2 §4).

All four are deterministic, pure functions over `officefile` structures, with
typed failure on invalid input: no eval, no arithmetic, no cell values, no
fuzzy matching. Only `report.write` has an effect, and it writes one canonical
JSON file into the run's scratch `files/` directory.

Qualification follows the `uri_v1/edge/registry.py` pattern without importing
or widening it: a pinned JSON record (digest pinned in `qualification.py`, not
here, because the record hashes this file) binds each action to its adapter's
identity, implementation digest and contract shape.
"""
from __future__ import annotations

from dataclasses import dataclass, replace
import hashlib
from pathlib import Path

from uri_v1.execution.officefile import read_workbook_structure
from .contracts import (REPORT_NAME, REPORT_SCHEMA_VERSION, UNQUALIFIED, Approval, CapabilityContract,
                        CapabilitySnapshot, Effect, InputSpec, LiteralSpec, Mechanism, PortType as T, canonical)
from .qualification import qualification_for

# The modules an action adapter relies on; the record binds their digests (`qualification.record_entry`).
IMPLEMENTATION_MODULES = ("uri_v1.execution.planning.actions", "uri_v1.execution.planning.contracts",
                          "uri_v1.execution.officefile")

INSPECT = "uri.plan.workbook.inspect_structure"
SELECT = "uri.plan.structure.select"
COMPARE = "uri.plan.structure.compare"
WRITE = "uri.plan.report.write"


class ActionError(ValueError):
    """Typed action failure; the reason code is the message."""


@dataclass(frozen=True)
class SourceInput:
    source_id: str
    path: Path


@dataclass(frozen=True)
class NodeContext:
    files: Path
    plan_sha256: str
    node_id: str


def inspect_structure(ctx, inputs, literals) -> dict:
    source = inputs["source"]
    structure = read_workbook_structure(source.path)
    return {"structure": {"source_id": source.source_id,
                          "sheets": [{"name": s.name, "header": list(s.header), "error_cells": s.error_cells}
                                     for s in structure.sheets]}}


def select(ctx, inputs, literals) -> dict:
    structure = inputs["structure"]
    by_name = {s["name"]: s for s in structure["sheets"]}
    headers = literals.get("headers")
    chosen = []
    for name in literals["sheets"]:
        sheet = by_name.get(name)          # exact match only: no case folding, no closest name
        if sheet is None: raise ActionError("LITERAL_NOT_IN_SOURCE")
        if headers is not None:
            if any(h not in sheet["header"] for h in headers): raise ActionError("LITERAL_NOT_IN_SOURCE")
            chosen.append({"name": name, "header": list(headers)})
        else:
            chosen.append({"name": name, "header": list(sheet["header"])})
    return {"selection": {"source_id": structure["source_id"], "sheets": chosen}}


def _named(header) -> list:
    out = []
    for h in header:
        if h is not None and h not in out: out.append(h)
    return out


def compare(ctx, inputs, literals) -> dict:
    if literals["match_on"] != "sheet_name": raise ActionError("LITERAL_INVALID")
    left, right = inputs["left"], inputs["right"]
    right_by_name = {s["name"]: s for s in right["sheets"]}
    left_names = [s["name"] for s in left["sheets"]]
    shared = []
    for sheet in left["sheets"]:
        other = right_by_name.get(sheet["name"])
        if other is None: continue
        lh, rh = _named(sheet["header"]), _named(other["header"])
        shared.append({"name": sheet["name"], "shared": [h for h in lh if h in rh],
                       "only_left": [h for h in lh if h not in rh], "only_right": [h for h in rh if h not in lh]})
    return {"comparison": {"match_on": "sheet_name", "left_source_id": left["source_id"], "right_source_id": right["source_id"],
                           "shared_sheets": shared, "only_left_sheets": [n for n in left_names if n not in right_by_name],
                           "only_right_sheets": [s["name"] for s in right["sheets"] if s["name"] not in left_names]}}


def write_report(ctx, inputs, literals) -> dict:
    report = {"schema_version": REPORT_SCHEMA_VERSION, "plan_sha256": ctx.plan_sha256, "node": ctx.node_id,
              "items": [{"ref": item["ref"], "type": item["type"], "value": item["value"]} for item in inputs["items"]]}
    data = canonical(report)
    with open(ctx.files / REPORT_NAME, "xb") as out: out.write(data)
    return {"report": {"relpath": REPORT_NAME, "sha256": hashlib.sha256(data).hexdigest()}}


def _contract(action_id, inputs, outputs, literals, effect, coverage):
    return CapabilityContract(action_id, "1", Mechanism.DETERMINISTIC, inputs, outputs, literals, effect, Approval.NONE,
                              coverage, UNQUALIFIED)


def _unqualified_catalog() -> tuple:
    return (
        (_contract(INSPECT, (("source", InputSpec((T.SOURCE_XLSX,))),), (("structure", T.WORKBOOK_STRUCTURE),), (),
                   Effect.READ_ONLY, "oracle.inspect_structure.v1"), inspect_structure),
        (_contract(SELECT, (("structure", InputSpec((T.WORKBOOK_STRUCTURE,))),), (("selection", T.STRUCTURE_SELECTION),),
                   (("sheets", LiteralSpec("string_list", True)), ("headers", LiteralSpec("string_list", False))),
                   Effect.READ_ONLY, "oracle.select.v1"), select),
        (_contract(COMPARE, (("left", InputSpec((T.STRUCTURE_SELECTION,))), ("right", InputSpec((T.STRUCTURE_SELECTION,)))),
                   (("comparison", T.STRUCTURE_COMPARISON),), (("match_on", LiteralSpec("enum", True, ("sheet_name",))),),
                   Effect.READ_ONLY, "oracle.compare.v1"), compare),
        (_contract(WRITE, (("items", InputSpec((T.STRUCTURE_SELECTION, T.STRUCTURE_COMPARISON), True, 4)),),
                   (("report", T.REPORT_ARTIFACT),), (), Effect.SCRATCH_WRITE, "oracle.report_write.v1"), write_report),
    )


def default_catalog() -> tuple:
    """((CapabilityContract, adapter), ...) for the four approved slice-1 actions. A contract carries the record's
    digest only if the record qualifies that exact adapter under that exact contract shape (fail closed)."""
    return tuple((replace(c, qualification=qualification_for(c, fn)), fn) for c, fn in _unqualified_catalog())


def snapshot(catalog=None) -> CapabilitySnapshot:
    return CapabilitySnapshot(tuple(c for c, _ in (catalog or default_catalog())))


def adapters(catalog=None) -> dict:
    return {(c.action_id, c.version): fn for c, fn in (catalog or default_catalog())}


def renamed(catalog, old_action_id, new_action_id) -> tuple:
    """The same handler re-declared under a new name with identical ports (Stage 2 §2.2, F4 probe)."""
    return tuple((replace(c, action_id=new_action_id) if c.action_id == old_action_id else c, fn) for c, fn in catalog)
