"""Value-free, hash-chained privacy audit (plan 2.5).

Each record says who asked, for which task, to send what kinds of data where, under which policy, what was decided and
with which grant. It never holds a value, a span, a token or a hash of a value: identifiers have so few possible values
that their hashes can be reversed. `write` raises on failure; the gateway then refuses the egress.
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import threading
import time
from pathlib import Path

GENESIS = "0" * 64
FIELDS = ("requester", "task_id", "destination", "purpose", "policy", "decision", "categories", "grant_ids", "outcome",
          "code")
_IDENTIFIER = re.compile(r"[A-Za-z][A-Za-z0-9_.:-]{0,95}\Z")


def _safe_identifier(value):
    """Audit labels are identifiers, never caller-supplied content."""
    if value is None:
        return None
    if not isinstance(value, str) or not _IDENTIFIER.fullmatch(value):
        return "UNTRUSTED_IDENTIFIER"
    from .classify import classify
    return value if not classify(value).categories() else "UNTRUSTED_IDENTIFIER"


def _h(rec: dict) -> str:
    return hashlib.sha256(json.dumps(rec, sort_keys=True, separators=(",", ":")).encode("utf-8")).hexdigest()


class PrivacyAudit:
    def __init__(self, path=None, *, clock=time.time):
        self.path = Path(path) if path else None
        self.clock = clock
        self._lock = threading.Lock()
        self.records = []                                         # memory mode only
        self._seq, self._prev = 0, GENESIS
        if self.path and self.path.exists():
            v = self.verify()
            if not v["ok"]:
                raise RuntimeError("PRIVACY_AUDIT_CORRUPT")            # fail closed: never append to a broken chain
            self._seq, self._prev = v["count"], v["head"]

    def write(self, **fields) -> dict:
        unknown = set(fields) - set(FIELDS)
        if unknown:
            raise ValueError("AUDIT_FIELD_UNKNOWN")
        fields = dict(fields)
        for key in ("requester", "task_id", "purpose", "destination", "policy", "decision", "outcome", "code"):
            fields[key] = _safe_identifier(fields.get(key))
        if isinstance(fields.get("grant_ids"), list):
            fields["grant_ids"] = [_safe_identifier(g) for g in fields["grant_ids"]]
        elif fields.get("grant_ids") is not None:
            fields["grant_ids"] = []
        if isinstance(fields.get("categories"), dict):
            fields["categories"] = {_safe_identifier(k): v if isinstance(v, int) and v >= 0 else None
                                    for k, v in fields["categories"].items()}
        elif fields.get("categories") is not None:
            fields["categories"] = None
        with self._lock:
            rec = {"v": 1, "seq": self._seq + 1, "ts": round(self.clock(), 3), "prev": self._prev,
                   **{k: fields.get(k) for k in FIELDS}}
            rec["hash"] = _h(rec)
            if self.path:
                self.path.parent.mkdir(parents=True, exist_ok=True)
                with open(self.path, "a", encoding="utf-8") as f:
                    f.write(json.dumps(rec, sort_keys=True) + "\n")
                    f.flush()
                    os.fsync(f.fileno())
            else:
                self.records.append(rec)
            self._seq, self._prev = rec["seq"], rec["hash"]
            return rec

    def verify(self) -> dict:
        lines = (self.path.read_text(encoding="utf-8").splitlines() if self.path and self.path.exists()
                 else [json.dumps(r) for r in self.records])
        prev, count = GENESIS, 0
        for i, line in enumerate(lines):
            try:
                rec = json.loads(line)
            except ValueError:
                return {"ok": False, "count": count, "head": prev, "error": "TORN_OR_CORRUPT_LINE", "line": i + 1,
                        "last": i == len(lines) - 1}
            body = {k: v for k, v in rec.items() if k != "hash"}
            if rec.get("prev") != prev or rec.get("seq") != count + 1 or _h(body) != rec.get("hash"):
                return {"ok": False, "count": count, "head": prev, "error": "CHAIN_BROKEN", "line": i + 1}
            prev, count = rec["hash"], count + 1
        return {"ok": True, "count": count, "head": prev}
