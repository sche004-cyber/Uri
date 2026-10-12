"""Source workbooks for a new workbook (M2-AC1..AC3).

The owner picks one or more .xlsx files and says what each one is for (M2-D10): `reference` (URI reads it), `check`
(URI checks it, lists findings and suggests fixes) or `edit` (URI changes it). Until every file has a role, URI does
not work with them. At most one file is the working file (check or edit) at a time; the others are references. Each
file goes through the M1 path rule (`grants.grant_open`), is copied into the
workbook's work folder (the original is only read, and a file that changes during the copy is refused), and is read
with `xlsx_model.read`. Sources are read-only: nothing here writes to them. The view lists sources by id and label,
never by path.
"""
from __future__ import annotations

import os
import shutil
from dataclasses import dataclass
from pathlib import Path

from . import refs
from . import xlsx_model
from .errors import OfficeError

MAX_SOURCES = 10
EXCERPT_ROWS = 8                 # first rows of each source sheet shown to the Brain
MAX_EXCERPT_CELLS = 400          # across all sources (the new workbook's own excerpt has its own cap)
ROLES = ("reference", "check", "edit")
WORKING_ROLES = ("check", "edit")


@dataclass
class Source:
    sid: str                     # "S1", "S2", ...
    label: str                   # file name, made unique
    workbook: dict               # xlsx_model.read of the copied-in file
    sha256: str                  # of the original at copy-in
    grant_id: str
    role: str | None = None      # None until the owner says: "reference" | "check" | "edit"


def add(grants, work: Path, existing: list, raw_paths) -> list:
    """Copy in and read every path; all or nothing. Returns the new Source list (existing + added)."""
    if not isinstance(raw_paths, list) or not raw_paths:
        raise OfficeError("NO_SOURCES", "pick at least one Excel file")
    if len(existing) + len(raw_paths) > MAX_SOURCES:
        raise OfficeError("TOO_MANY_SOURCES", f"at most {MAX_SOURCES} files per new workbook")
    added: list = []
    grants_made = []
    seen = {_same_file_key(grants.get(s.grant_id, "open").path) for s in existing}
    try:
        for raw in raw_paths:
            g = grants.grant_open(raw)
            grants_made.append(g.grant_id)
            key = _same_file_key(g.path)
            if key in seen:
                # One record per physical file: a second record would go stale when URI saves through the first
                # (Codex R2-02).
                raise OfficeError("DUPLICATE_FILE", f"{g.path.name} is already added")
            seen.add(key)
            n = len(existing) + len(added) + 1
            dest = work / f"source-{n}.xlsx"
            shutil.copy2(g.path, dest)
            sha = xlsx_model.file_sha256(dest)
            if sha != xlsx_model.file_sha256(g.path):
                raise OfficeError("FILE_CHANGING", "a file changed while it was being added; try again", 409)
            wb = xlsx_model.read(dest)
            label = _unique(g.path.name, [s.label for s in existing + added])
            added.append(Source(f"S{n}", label, wb, sha, g.grant_id))
    except Exception:
        for gid in grants_made:
            grants.revoke(gid)
        for i in range(len(existing) + 1, len(existing) + len(raw_paths) + 1):
            (work / f"source-{i}.xlsx").unlink(missing_ok=True)
        raise
    return existing + added


def _same_file_key(path) -> str:
    return os.path.normcase(os.path.realpath(path))


def _unique(name: str, taken: list) -> str:
    if name not in taken:
        return name
    i = 2
    while f"{name} ({i})" in taken:
        i += 1
    return f"{name} ({i})"


def listing(sources: list) -> list:
    """What the view shows: id, label, sheets and sizes. No paths."""
    return [{"id": s.sid, "label": s.label, "role": s.role,
             "sheets": [{"name": sh["name"], "rows": sh["max_row"], "cols": sh["max_col"],
                         "truncated": sh["truncated"]} for sh in s.workbook["sheets"]]} for s in sources]


def excerpt(sources: list, budget: int = MAX_EXCERPT_CELLS) -> list:
    """A bounded view for the Brain: every source sheet's size and its first rows (values; formulas as text), within
    `budget` cells (what is left of the request's total after the workbook's own excerpt, Codex R2-04)."""
    out = []
    for s in sources:
        sheets = []
        for sh in s.workbook["sheets"]:
            cells = {}
            rows = sorted(sh["cells"].items(), key=lambda kv: (refs.parse_cell(kv[0])[1], refs.parse_cell(kv[0])[0]))
            for ref, c in rows:
                if refs.parse_cell(ref)[1] > EXCERPT_ROWS or budget <= 0:
                    continue
                v = c.get("v") if c.get("v") is not None else c.get("f")
                if v is None:
                    continue
                cells[ref] = v
                budget -= 1
            sheets.append({"name": sh["name"], "rows": sh["max_row"], "cols": sh["max_col"], "first_rows": cells})
        out.append({"source": s.sid, "label": s.label, "sheets": sheets})
    return out


def working(sources: list):
    """The source the owner chose to check or edit, or None."""
    return next((s for s in sources if s.role in WORKING_ROLES), None)


def roles_needed(sources: list) -> list:
    return [s.label for s in sources if s.role not in ROLES]


def by_id(sources: list) -> dict:
    return {s.sid: s.workbook for s in sources}
