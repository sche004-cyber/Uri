"""Closed, hashed acceptance criteria evaluated only by URI verifiers.

Criteria are data, never code: every item kind is a closed vocabulary entry and
every path is a workspace-relative POSIX path. The SHA-256 of the canonical
form is what a run, a capsule and a verifier report all refer to.
"""
from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
import re

ACCEPTANCE_SCHEMA_VERSION = "m37.acceptance.v1"
_REL = re.compile(r"^(?!/)(?!.*(?:^|/)\.\.(?:/|$))[A-Za-z0-9 ._()\-/]{1,200}$")
_NAME_LIMIT = 128
_ITEMS = {
    # kind: (required keys, optional keys)
    "script_exit_zero": (("script",), ("args", "timeout_s")),
    "output_workbook_exists": (("path",), ()),
    "workbook_has_sheets": (("path", "sheets"), ()),
    "workbook_has_columns": (("path", "sheet", "columns"), ()),
    "no_formula_errors": (("path",), ()),
    "only_changed": (("paths",), ()),
    "report_recomputes": (("path", "task_class"), ()),
}


def workspace_relpath(value: str) -> str:
    if not isinstance(value, str) or not _REL.fullmatch(value) or "//" in value or value.endswith("/"):
        raise ValueError("INVALID_WORKSPACE_PATH")
    return value


def _name(value: str) -> str:
    if not isinstance(value, str) or not value or len(value) > _NAME_LIMIT or any(ord(c) < 32 for c in value):
        raise ValueError("INVALID_NAME")
    return value


def _item(raw) -> dict:
    if not isinstance(raw, dict) or raw.get("kind") not in _ITEMS:
        raise ValueError("UNKNOWN_ACCEPTANCE_ITEM")
    required, optional = _ITEMS[raw["kind"]]
    keys = set(raw) - {"kind"}
    if not set(required) <= keys or keys - set(required) - set(optional):
        raise ValueError("ACCEPTANCE_ITEM_SHAPE")
    item = {"kind": raw["kind"]}
    for key in ("script", "path"):
        if key in raw: item[key] = workspace_relpath(raw[key])
    if "paths" in raw:
        if not isinstance(raw["paths"], (list, tuple)) or len(raw["paths"]) > 64: raise ValueError("ACCEPTANCE_ITEM_SHAPE")
        item["paths"] = sorted({workspace_relpath(p) for p in raw["paths"]})
    for key in ("sheets", "columns"):
        if key in raw:
            if not isinstance(raw[key], (list, tuple)) or not raw[key] or len(raw[key]) > 64: raise ValueError("ACCEPTANCE_ITEM_SHAPE")
            item[key] = [_name(x) for x in raw[key]]
    if "sheet" in raw: item["sheet"] = _name(raw["sheet"])
    if "task_class" in raw: item["task_class"] = _name(raw["task_class"])
    if "args" in raw:
        if not isinstance(raw["args"], (list, tuple)) or len(raw["args"]) > 16: raise ValueError("ACCEPTANCE_ITEM_SHAPE")
        item["args"] = [_name(x) for x in raw["args"]]
    if "timeout_s" in raw:
        if type(raw["timeout_s"]) is not int or not 1 <= raw["timeout_s"] <= 600: raise ValueError("ACCEPTANCE_ITEM_SHAPE")
        item["timeout_s"] = raw["timeout_s"]
    return item


@dataclass(frozen=True)
class AcceptanceCriteria:
    revision: int
    items: tuple
    schema_version: str = ACCEPTANCE_SCHEMA_VERSION

    def __post_init__(self):
        if self.schema_version != ACCEPTANCE_SCHEMA_VERSION: raise ValueError("ACCEPTANCE_SCHEMA")
        if type(self.revision) is not int or self.revision < 1: raise ValueError("ACCEPTANCE_REVISION")
        if not isinstance(self.items, (list, tuple)) or not 1 <= len(self.items) <= 32: raise ValueError("ACCEPTANCE_ITEMS")
        items = tuple(_item(dict(x)) for x in self.items)
        if sum(1 for x in items if x["kind"] == "only_changed") > 1: raise ValueError("ACCEPTANCE_ITEMS")
        object.__setattr__(self, "items", items)

    def to_dict(self) -> dict:
        return {"schema_version": self.schema_version, "revision": self.revision, "items": [dict(x) for x in self.items]}

    @classmethod
    def from_dict(cls, raw) -> "AcceptanceCriteria":
        if not isinstance(raw, dict) or set(raw) != {"schema_version", "revision", "items"}:
            raise ValueError("ACCEPTANCE_SHAPE")
        return cls(raw["revision"], tuple(raw["items"]), raw["schema_version"])

    def canonical(self) -> bytes:
        return json.dumps(self.to_dict(), sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")

    @property
    def sha256(self) -> str:
        return hashlib.sha256(self.canonical()).hexdigest()
