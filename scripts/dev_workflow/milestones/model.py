"""Milestone Manager domain model: vocabularies, validation, secret refusal and the deterministic fold.

The fold (``fold``/``apply``) turns events into a projection. It never refuses an event: refusals happen in
service.py before an event is written. Events merged from another host's segment that were built on an older entity
version are applied and recorded as conflicts, so nothing is silently lost or silently preferred.
"""
from __future__ import annotations

import copy
import re

ID_RE = re.compile(r"^[A-Z0-9][A-Z0-9._-]{1,63}$")
DEC_RE = re.compile(r"^DEC-\d{3,5}$")
SHA_RE = re.compile(r"^[0-9a-f]{40}$")
SHA256_RE = re.compile(r"^[0-9a-f]{64}$")

STATUSES = ("PLANNED", "IN_PROGRESS", "PAUSED", "ACCEPTED", "INTEGRATED", "DONE", "CANCELLED", "SUPERSEDED")
PHASES = ("RESEARCH", "DISCOVERY", "ARCHITECTURE", "IMPLEMENTATION", "TESTING", "REVIEW", "REPAIR", "ACCEPTANCE",
          "INTEGRATION", "CLOSED")
VERDICTS = ("ACCEPT", "ACCEPT WITH FINDINGS", "REVISE", "REJECT", "BLOCKED")
POSITIVE_VERDICTS = ("ACCEPT", "ACCEPT WITH FINDINGS")
ASSURANCE = ("DRIVER_VERIFIED", "SUBAGENT", "SESSION", "OWNER_ATTESTED", "UNVERIFIED")
QUALIFYING_ASSURANCE = ("DRIVER_VERIFIED", "SUBAGENT", "SESSION", "OWNER_ATTESTED")
REVIEWER_KINDS = ("codex_cli", "claude_cli", "subagent", "session", "owner", "lifecycle_driver", "other")
RESULT_CLASSES = ("COMPLETED_WITH_RESULT", "PENDING", "RUNNING", "FAILED", "KILLED", "TIMED_OUT", "CANCELLED",
                  "NO_OUTPUT", "BLOCKED")
EVIDENCE_KINDS = ("test_run", "gate", "review_record", "receipt", "log", "live_run", "document", "commit", "other")
APPROVAL_KINDS = ("INTEGRATION", "POLICY", "SCOPE", "DECISION", "PROTECTED_ACTION", "OTHER")
APPROVAL_OUTCOMES = ("APPROVED", "DENIED", "WITHDRAWN")
EVIDENCE_CLASSES = ("REPO-RECORD", "MEMORY-ONLY", "OWNER-PROMPT", "ANTIGRAVITY-RECOMMENDATION", "AGENT-RECORD",
                    "OTHER")
BLOCKER_KINDS = ("TECHNICAL", "REVIEWER_UNAVAILABLE", "RESOURCE", "DEPENDENCY", "OWNER", "INTEGRITY", "OTHER")
RECORD_TYPES = ("capability", "roadmap", "defect", "next_action", "open_question", "other")
COLORS = ("GREEN", "BLUE", "YELLOW", "RED", "WHITE")

MAX_TEXT = 4000
MAX_LIST = 200
MILESTONE_FIELDS = ("title", "objective", "priority", "phase", "next_action", "worktree", "branch", "base_commit",
                    "candidate_commit", "acceptance_ref")

# Secret-looking content is refused in any free-text field (no redaction: the caller must fix the input).
SECRET_PATTERNS = [
    ("openai/anthropic-style key", re.compile(r"\bsk-(?:ant-)?[A-Za-z0-9_-]{20,}")),
    ("github token", re.compile(r"\b(?:ghp|gho|ghu|ghs|ghr)_[A-Za-z0-9]{30,}|\bgithub_pat_[A-Za-z0-9_]{30,}")),
    ("aws access key", re.compile(r"\bAKIA[0-9A-Z]{16}\b")),
    ("google api key", re.compile(r"\bAIza[0-9A-Za-z_-]{35}\b")),
    ("slack token", re.compile(r"\bxox[abprs]-[A-Za-z0-9-]{10,}")),
    ("private key block", re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----")),
    ("bearer token", re.compile(r"(?i)\bbearer\s+[A-Za-z0-9._~+/-]{24,}")),
    ("credential assignment", re.compile(
        r"(?i)\b(?:password|passwd|pwd|secret|api[_-]?key|access[_-]?token|auth[_-]?token)\s*[:=]\s*"
        r"['\"]?(?=[^\s'\"]*[0-9])(?=[^\s'\"]*[A-Za-z])[^\s'\"]{8,}")),
]


class ValidationError(Exception):
    def __init__(self, code: str, message: str):
        super().__init__(f"{code}: {message}")
        self.code = code


def find_secret(value) -> str | None:
    """Return the name of the first secret pattern found anywhere in ``value`` (str/list/dict), else None."""
    if isinstance(value, str):
        for name, rx in SECRET_PATTERNS:
            if rx.search(value):
                return name
        return None
    if isinstance(value, dict):
        for v in value.values():
            hit = find_secret(v)
            if hit:
                return hit
        return None
    if isinstance(value, (list, tuple)):
        for v in value:
            hit = find_secret(v)
            if hit:
                return hit
    return None


def check_text(name: str, value, required: bool = False, limit: int = MAX_TEXT) -> str | None:
    if value is None or value == "":
        if required:
            raise ValidationError("MISSING", f"{name} is required")
        return None
    if not isinstance(value, str):
        raise ValidationError("TYPE", f"{name} must be text")
    if len(value) > limit:
        raise ValidationError("TOO_LONG", f"{name} is {len(value)} characters (limit {limit}); store detail in a "
                                          "file and record it as evidence")
    return value


def check_enum(name: str, value, allowed, required: bool = True):
    if value is None and not required:
        return None
    if value not in allowed:
        raise ValidationError("BAD_VALUE", f"{name} must be one of {', '.join(allowed)} (got {value!r})")
    return value


def check_id(name: str, value, rx=ID_RE) -> str:
    if not isinstance(value, str) or not rx.match(value):
        raise ValidationError("BAD_ID", f"{name} {value!r} must match {rx.pattern}")
    return value


def check_sha(name: str, value, required: bool = False, rx=SHA_RE) -> str | None:
    if value in (None, ""):
        if required:
            raise ValidationError("MISSING", f"{name} is required")
        return None
    if not isinstance(value, str) or not rx.match(value):
        raise ValidationError("BAD_SHA", f"{name} must be a full lowercase hex SHA ({rx.pattern})")
    return value


# --------------------------------------------------------------------------- projection

def empty_projection() -> dict:
    return {"milestones": {}, "decisions": {}, "approvals": {}, "evidence": {}, "reviews": {}, "blockers": {},
            "handoffs": {}, "records": {}, "imports": [], "conflicts": [], "recoveries": [], "counters": {},
            "versions": {}, "last_key": None, "events": 0}


def _bump(p: dict, entity: str) -> None:
    p["versions"][entity] = p["versions"].get(entity, 0) + 1


def _count(p: dict, prefix: str, ident: str) -> None:
    m = re.match(rf"^{re.escape(prefix)}-(\d+)$", ident or "")
    if m:
        p["counters"][prefix] = max(p["counters"].get(prefix, 0), int(m.group(1)))


def event_key(ev: dict) -> list:
    return [ev["ts"], ev["seg"], ev["seq"]]


def apply(p: dict, ev: dict) -> None:
    """Fold one event into projection ``p`` (in place). Unknown kinds are kept as counted no-ops."""
    d, kind = ev["data"], ev["kind"]
    ref = {"seg": ev["seg"], "seq": ev["seq"], "hash": ev["hash"], "ts": ev["ts"], "actor": ev["actor"]}
    for entity, seen in (ev.get("base") or {}).items():
        if p["versions"].get(entity, 0) != seen:
            p["conflicts"].append({"entity": entity, "expected": seen, "actual": p["versions"].get(entity, 0),
                                   "event": ref, "kind": kind, "resolved": False})
    p["events"] += 1
    p["last_key"] = event_key(ev)
    ms = p["milestones"]

    if kind == "MILESTONE_CREATED":
        ms[d["id"]] = {"id": d["id"], "title": d["title"], "objective": d.get("objective"),
                       "priority": d.get("priority"), "phase": d.get("phase") or "RESEARCH",
                       "status": d.get("status") or "PLANNED", "depends_on": list(d.get("depends_on") or []),
                       "acceptance_ref": d.get("acceptance_ref"), "worktree": d.get("worktree"),
                       "branch": d.get("branch"), "base_commit": d.get("base_commit"), "candidate_commit": None,
                       "next_action": d.get("next_action"), "assignment": None, "implementers": [ev["actor"]],
                       "lifecycle": [], "integration": None, "origin": d.get("origin"), "created": ref,
                       "status_history": [{"status": d.get("status") or "PLANNED", "at": ev["ts"],
                                           "by": ev["actor"], "reason": "created"}]}
        _bump(p, d["id"])
    elif kind == "MILESTONE_UPDATED":
        m = ms.get(d["id"])
        if m:
            for k, v in d["fields"].items():
                m[k] = v
            _bump(p, d["id"])
    elif kind == "MILESTONE_STATUS_SET":
        m = ms.get(d["id"])
        if m:
            m["status"] = d["status"]
            m["status_history"].append({"status": d["status"], "at": ev["ts"], "by": ev["actor"],
                                        "reason": d.get("reason"), "basis": d.get("basis")})
            _bump(p, d["id"])
    elif kind == "DEPENDENCY_ADDED":
        m = ms.get(d["id"])
        if m and d["on"] not in m["depends_on"]:
            m["depends_on"].append(d["on"])
            _bump(p, d["id"])
    elif kind == "DEPENDENCY_REMOVED":
        m = ms.get(d["id"])
        if m and d["on"] in m["depends_on"]:
            m["depends_on"].remove(d["on"])
            _bump(p, d["id"])
    elif kind == "MILESTONE_ASSIGNED":
        m = ms.get(d["id"])
        if m:
            m["assignment"] = {"agent": d["agent"], "session": d.get("session"), "worktree": d.get("worktree"),
                               "expires_at": d["expires_at"], "since": ev["ts"], "takeover_of": d.get("takeover_of")}
            if d["agent"] not in m["implementers"]:
                m["implementers"].append(d["agent"])
            _bump(p, d["id"])
    elif kind == "MILESTONE_RELEASED":
        m = ms.get(d["id"])
        if m:
            m["assignment"] = None
            _bump(p, d["id"])
    elif kind == "IMPLEMENTER_RECORDED":
        m = ms.get(d["id"])
        if m and d["agent"] not in m["implementers"]:
            m["implementers"].append(d["agent"])
            _bump(p, d["id"])
    elif kind == "BLOCKER_ADDED":
        _count(p, "BLK", d["id"])
        p["blockers"][d["id"]] = {**d, "status": "OPEN", "opened": ref, "resolution": None}
        _bump(p, d["id"])
    elif kind == "BLOCKER_RESOLVED":
        b = p["blockers"].get(d["id"])
        if b:
            b["status"] = "RESOLVED"
            b["resolution"] = {"text": d["resolution"], "at": ev["ts"], "by": ev["actor"]}
            _bump(p, d["id"])
    elif kind == "EVIDENCE_ADDED":
        p["evidence"].setdefault(d["id"], {**d, "recorded": ref})
        _bump(p, d["id"])
    elif kind == "REVIEW_RECORDED":
        _count(p, "RV", d["id"])
        p["reviews"][d["id"]] = {**d, "recorded": ref}
        _bump(p, d["id"])
    elif kind == "APPROVAL_REQUESTED":
        _count(p, "AP", d["id"])
        p["approvals"][d["id"]] = {**d, "status": "REQUESTED", "requested": ref, "resolution": None}
        _bump(p, d["id"])
    elif kind == "APPROVAL_RESOLVED":
        a = p["approvals"].get(d["id"])
        if a:
            a["status"] = d["outcome"]
            a["resolution"] = {**d, "at": ev["ts"], "relayed_by": ev["actor"]}
            _bump(p, d["id"])
    elif kind == "DECISION_RECORDED":
        _count(p, "DEC", d["id"])
        # An imported row starts in the status its source states (e.g. SUPERSEDED without a named successor).
        p["decisions"][d["id"]] = {**d, "status": d.get("source_status") or "ACTIVE", "superseded_by": [],
                                   "supersedes": [],
                                   "corrections": [], "source_revisions": [], "recorded": ref}
        _bump(p, d["id"])
    elif kind == "DECISION_SUPERSEDED":
        old, new = p["decisions"].get(d["id"]), p["decisions"].get(d["by"])
        if old:
            old["superseded_by"].append({"by": d["by"], "partial": bool(d.get("partial")), "note": d.get("note"),
                                         "at": ev["ts"]})
            if d.get("link_only"):
                pass
            elif not d.get("partial"):
                old["status"] = "SUPERSEDED"
            elif old["status"] == "ACTIVE":
                old["status"] = "PARTIALLY_SUPERSEDED"
            _bump(p, d["id"])
        if new:
            new["supersedes"].append({"id": d["id"], "partial": bool(d.get("partial"))})
            _bump(p, d["by"])
    elif kind == "DECISION_CORRECTED":
        dec = p["decisions"].get(d["id"])
        if dec:
            dec["corrections"].append({**d, "at": ev["ts"], "by": ev["actor"]})
            _bump(p, d["id"])
    elif kind == "DECISION_SOURCE_REVISED":
        dec = p["decisions"].get(d["id"])
        if dec:
            dec["source_revisions"].append({**d, "at": ev["ts"]})
            _bump(p, d["id"])
    elif kind in ("RECORD_IMPORTED", "RECORD_SOURCE_REVISED"):
        r = p["records"].get(d["id"])
        if r is None or kind == "RECORD_IMPORTED":
            p["records"][d["id"]] = {**d, "revisions": [], "recorded": ref}
        else:
            r["revisions"].append({"fields": d.get("fields"), "color": d.get("color"), "source": d.get("source"),
                                   "at": ev["ts"]})
            r["fields"], r["color"], r["source"] = d.get("fields"), d.get("color"), d.get("source")
        _bump(p, d["id"])
    elif kind == "IMPORT_RECORDED":
        p["imports"].append({**d, "at": ev["ts"], "by": ev["actor"]})
    elif kind == "HANDOFF_RECORDED":
        _count(p, "HO", d["id"])
        p["handoffs"][d["id"]] = {**d, "recorded": ref}
        m = ms.get(d["subject"])
        if m and ev["actor"] not in m["implementers"]:
            m["implementers"].append(ev["actor"])
        _bump(p, d["id"])
    elif kind == "LIFECYCLE_LINKED":
        m = ms.get(d["subject"])
        if m and not any(x["state_dir"] == d["state_dir"] for x in m["lifecycle"]):
            m["lifecycle"].append({"state_dir": d["state_dir"], "config_path": d.get("config_path"),
                                   "snapshot": None})
            _bump(p, d["subject"])
    elif kind == "LIFECYCLE_SYNCED":
        m = ms.get(d["subject"])
        if m:
            for x in m["lifecycle"]:
                if x["state_dir"] == d["state_dir"]:
                    x["snapshot"] = {**d["snapshot"], "synced_at": ev["ts"]}
            _bump(p, d["subject"])
    elif kind == "INTEGRATION_RECORDED":
        m = ms.get(d["subject"])
        if m:
            m["integration"] = {**d, "at": ev["ts"], "by": ev["actor"]}
            _bump(p, d["subject"])
    elif kind == "CONFLICT_RESOLVED":
        for c in p["conflicts"]:
            if c["entity"] == d["entity"] and not c["resolved"]:
                c["resolved"] = True
                c["resolution"] = {"note": d["note"], "at": ev["ts"], "by": ev["actor"]}
    elif kind == "STORE_RECOVERED":
        p["recoveries"].append({**d, "at": ev["ts"]})


def fold(events, p: dict | None = None) -> dict:
    p = copy.deepcopy(p) if p is not None else empty_projection()
    for ev in events:
        apply(p, ev)
    return p


def ordered(segments) -> list[dict]:
    evs = [ev for s in segments for ev in s.events]
    evs.sort(key=event_key)
    return evs


def would_cycle(milestones: dict, node: str, on: str) -> bool:
    """True if adding the edge node -> on creates a cycle."""
    stack, seen = [on], set()
    while stack:
        cur = stack.pop()
        if cur == node:
            return True
        if cur in seen:
            continue
        seen.add(cur)
        stack.extend((milestones.get(cur) or {}).get("depends_on", []))
    return False
