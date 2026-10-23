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
# Every audited field is checked against an exact allowlist (review R1-03 / R2-03). Content classification is not
# used as the guard: a hash or a passport number does not look sensitive to a classifier, but it is never one of these.
DECISIONS = frozenset({"ALLOW", "PSEUDONYMIZE", "REDACT", "REQUIRE_GRANT", "REFUSE", "RESTORE"})
OUTCOMES = frozenset({"ALLOWED", "SANITIZED", "REFUSED", "RESTORED", "RECOVERED"})
CODES = frozenset({
    "PRIVACY_REFUSED", "PRIVACY_GRANT_REQUIRED", "PRIVACY_GRANT_RACE", "PRIVACY_INTERNAL_ERROR",
    "PRIVACY_INPUT_NOT_TEXT", "PRIVACY_DESTINATION_UNKNOWN", "PRIVACY_REQUESTER_UNKNOWN", "PRIVACY_PURPOSE_UNKNOWN",
    "PRIVACY_RESTORE_NOT_LOCAL", "PRIVACY_RESTORE_FAILED", "PRIVACY_SCOPE_UNKNOWN", "PRIVACY_SCOPE_OWNER_MISMATCH",
    "SCOPE_UNREADABLE", "SCOPE_ID_INVALID", "SCOPE_OWNER_MISMATCH", "FOREIGN_TOKENS",
    "AUDIT_TORN_TAIL_QUARANTINED", "PRIVACY_ENCODING_UNRESOLVED"})
COUNT_KEYS = frozenset({"CREDENTIAL", "SECRET_LIKE", "GOV_ID", "FINANCIAL", "CONTACT", "ADDRESS", "PERSON",
                        "CONFIDENTIAL", "restored", "foreign"})
# Task identifiers URI generates: Lifecycle V3.1 task ids and scheduler attempt keys. Anything else is not recorded.
TASK_ID = re.compile(r"TASK-\d{8}-[0-9a-f]{8}|job_[0-9a-f]{12}:\d{1,9}:\d{1,9}")
GRANT_ID = re.compile(r"GR-[0-9a-f]{12}")
UNTRUSTED = "UNTRUSTED_FIELD"


def _member(value, allowed):
    if value is None:
        return None
    return value if isinstance(value, str) and value in allowed else UNTRUSTED


def _match(value, rx):
    if value is None:
        return None
    return value if isinstance(value, str) and rx.fullmatch(value) else UNTRUSTED


def _h(rec: dict) -> str:
    return hashlib.sha256(json.dumps(rec, sort_keys=True, separators=(",", ":")).encode("utf-8")).hexdigest()


class PrivacyAudit:
    def __init__(self, path=None, *, clock=time.time):
        self.path = Path(path) if path else None
        self.clock = clock
        self._lock = threading.Lock()
        from . import policy as P
        self.requesters, self.purposes = P.KNOWN_REQUESTERS, P.KNOWN_PURPOSES
        self.records = []                                         # memory mode only
        self._seq, self._prev = 0, GENESIS
        recovered = False
        if self.path and self.path.exists():
            v = self.verify()
            if not v["ok"] and v.get("error") == "TORN_OR_CORRUPT_LINE" and v.get("last"):
                # A crash during the last append leaves one torn line (review S1-07). Keep a full copy of the file,
                # drop only that line, continue on the intact chain and record the recovery. Any other damage
                # (a broken chain, a bad line before the end) still refuses.
                self._quarantine_torn_tail(v["count"])
                v, recovered = self.verify(), True
            if not v["ok"]:
                raise RuntimeError("PRIVACY_AUDIT_CORRUPT")            # fail closed: never append to a broken chain
            self._seq, self._prev = v["count"], v["head"]
        if recovered:
            self.write(decision="ALLOW", outcome="RECOVERED", code="AUDIT_TORN_TAIL_QUARANTINED")

    def _quarantine_torn_tail(self, good_lines: int):
        raw = self.path.read_bytes()
        (self.path.parent / f"{self.path.name}.torn-{int(self.clock())}").write_bytes(raw)
        keep = b"".join(raw.splitlines(keepends=True)[:good_lines])
        tmp = self.path.with_name(self.path.name + f".{os.getpid()}.tmp")
        with open(tmp, "wb") as f:
            f.write(keep)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp, self.path)

    def trust(self, requesters, purposes):
        """The gateway's registered requesters and purposes (policy.KNOWN_* plus its wiring's own)."""
        self.requesters = frozenset(requesters)
        self.purposes = frozenset(purposes)

    def _trusted(self, f) -> dict:
        from . import policy as P
        cats = f.get("categories")
        if isinstance(cats, dict):
            cats = {k: v for k, v in cats.items() if k in COUNT_KEYS and type(v) is int and v >= 0} or None
        elif cats is not None:
            cats = None
        gids = f.get("grant_ids")
        gids = [g for g in gids if isinstance(g, str) and GRANT_ID.fullmatch(g)] if isinstance(gids, list) else []
        return {"requester": _member(f.get("requester"), self.requesters),
                "task_id": _match(f.get("task_id"), TASK_ID),
                "purpose": _member(f.get("purpose"), self.purposes),
                "destination": _member(f.get("destination"), {d.value for d in P.Destination}),
                "policy": _member(f.get("policy"), {P.POLICY_ID}),
                "decision": _member(f.get("decision"), DECISIONS),
                "outcome": _member(f.get("outcome"), OUTCOMES),
                "code": _member(f.get("code"), CODES),
                "categories": cats, "grant_ids": gids}

    def write(self, **fields) -> dict:
        unknown = set(fields) - set(FIELDS)
        if unknown:
            raise ValueError("AUDIT_FIELD_UNKNOWN")
        fields = self._trusted(fields)
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
