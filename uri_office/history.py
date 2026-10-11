"""Consented, per-workbook correction history (AC12, OFF-R4).

Off until the owner turns it on for a workbook. When on, it records what changed and why — never a cell value:
  {"id", "at", "workbook_key", "version", "kind", "sheet", "cell", "change_id", "reason"}
  kind ∈ uri_change_rejected | uri_change_edited_by_user | user_change
`reason` is optional text the owner typed or picked (<= 200 chars). Retention: 500 rows and 180 days per workbook.

The rows are scoped to one workbook and are read back only as context for that same workbook (inside the untrusted data
block). They are never written to personal memory, ExperienceStore or anything that learns. Graphify pointer wiring is
owner-gated (OFF-O3); `pointer()` gives the key it would use and nothing reads it yet.
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import time
import uuid
from pathlib import Path

from .errors import OfficeError

KINDS = ("uri_change_rejected", "uri_change_edited_by_user", "user_change")
FIELDS = ("id", "at", "workbook_key", "version", "kind", "sheet", "cell", "change_id", "reason")
MAX_ROWS = 500
MAX_AGE_S = 180 * 86400
_KEY = re.compile(r"^[0-9a-f]{64}$")


def workbook_key(kind: str, ident: str) -> str:
    """Stable key without storing the path or sheet id itself."""
    return hashlib.sha256(f"{kind}:{ident}".encode("utf-8")).hexdigest()


class History:
    def __init__(self, root: Path):
        self.root = Path(root) / "history"
        self.root.mkdir(parents=True, exist_ok=True)

    def _dir(self, key) -> Path:
        if not isinstance(key, str) or not _KEY.match(key):
            raise OfficeError("BAD_WORKBOOK_KEY")
        return self.root / key

    def consented(self, key) -> bool:
        return (self._dir(key) / "consent.json").is_file()

    def set_consent(self, key, on: bool):
        d = self._dir(key)
        if on:
            d.mkdir(exist_ok=True)
            (d / "consent.json").write_text(json.dumps({"on": True, "at": time.time()}), encoding="utf-8")
        else:
            self.delete_all(key)

    def _rows(self, key) -> list:
        f = self._dir(key) / "rows.jsonl"
        if not f.is_file():
            return []
        out = []
        for line in f.read_text(encoding="utf-8").splitlines():
            try:
                r = json.loads(line)
            except ValueError:
                continue
            if isinstance(r, dict) and set(r) == set(FIELDS):
                out.append(r)
        return out

    def _write(self, key, rows):
        d = self._dir(key)
        tmp = d / "rows.jsonl.tmp"
        tmp.write_text("".join(json.dumps(r, ensure_ascii=False) + "\n" for r in rows), encoding="utf-8")
        os.replace(tmp, d / "rows.jsonl")

    def record(self, key, version: int, event: dict, reason: str = "") -> dict | None:
        """Append one row if the owner consented for this workbook; otherwise record nothing."""
        if not self.consented(key):
            return None
        if event.get("kind") not in KINDS:
            raise OfficeError("BAD_HISTORY_KIND")
        reason = reason if isinstance(reason, str) else ""
        row = {"id": uuid.uuid4().hex[:12], "at": time.time(), "workbook_key": key, "version": int(version),
               "kind": event["kind"], "sheet": str(event.get("sheet") or "")[:31], "cell": str(event.get("cell") or "")[:12],
               "change_id": str(event.get("change_id") or "")[:32], "reason": reason.strip()[:200]}
        cutoff = time.time() - MAX_AGE_S
        rows = [r for r in self._rows(key) if r["at"] >= cutoff] + [row]
        self._write(key, rows[-MAX_ROWS:])
        return row

    def view(self, key) -> dict:
        return {"consented": self.consented(key), "rows": self._rows(key) if self.consented(key) else []}

    def recent(self, key, n=20) -> list:
        return self._rows(key)[-n:] if self.consented(key) else []

    def delete(self, key, row_id):
        rows = self._rows(key)
        keep = [r for r in rows if r["id"] != row_id]
        if len(keep) == len(rows):
            raise OfficeError("UNKNOWN_HISTORY_ROW")
        self._write(key, keep)

    def delete_all(self, key):
        d = self._dir(key)
        for name in ("rows.jsonl", "rows.jsonl.tmp", "consent.json"):
            if (d / name).exists():
                (d / name).unlink()
        if d.is_dir() and not any(d.iterdir()):
            d.rmdir()

    @staticmethod
    def pointer(key) -> dict:
        """The Graphify pointer this history would publish once OFF-O3 is decided. Not wired in M1."""
        return {"registry": "office_corrections", "lookup_key": key}
