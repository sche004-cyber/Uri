"""Milestone Manager domain model: vocabularies, validation, secret refusal and the deterministic fold.

The fold (``fold``/``apply``) turns events into a projection. It never refuses an event: refusals happen in
service.py before an event is written. Events merged from another host's segment that were built on an older entity
version are applied and recorded as conflicts, so nothing is silently lost or silently preferred.
"""
from __future__ import annotations

import copy
import re

ID_RE = re.compile(r"^[A-Z0-9][A-Z0-9._-]{1,63}$")
# Milestone ids may not look like generated record ids or the reserved subjects: versions and conflicts of all
# entities share one namespace (review R16-02).
RESERVED_MILESTONE_RE = re.compile(r"^(?:(?:RV|AP|BLK|HO|EV|DEC|LDEC|REG)-.*|PROJECT|LEDGER)$")
DEC_RE = re.compile(r"^L?DEC-\d{3,5}$")  # DEC-NNN = owner register numbering; LDEC-NNN = ledger-native
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
    ("stripe key", re.compile(r"\b(?:sk|rk|pk)_(?:live|test)_[A-Za-z0-9]{16,}")),
    ("hugging face token", re.compile(r"\bhf_[A-Za-z0-9]{30,}")),
    ("json web token", re.compile(r"\beyJ[A-Za-z0-9_-]{8,}\.eyJ[A-Za-z0-9_-]{8,}\.[A-Za-z0-9_-]{8,}")),
    ("credentials in URL", re.compile(r"(?i)\b[a-z][a-z0-9+.-]*://[^/\s:@]+:[^/\s@]+@")),
]
# Credential keys are recognised by their words, so prefixes, suffixes, camelCase and quotes do not hide them
# (fallback review FB-01/FB-02): db_password, DB_PASSWORD, myPassword, "api_key", github-token, clientSecret.
CREDENTIAL_WORDS = {"password", "passwd", "pwd", "passphrase", "secret", "secrets", "token", "credential",
                    "credentials", "apikey", "privatekey", "accesskey"}
CREDENTIAL_PAIRS = {("api", "key"), ("access", "key"), ("private", "key"), ("secret", "key"), ("auth", "key")}
# a word after the credential word that makes the key describe the credential rather than hold it
DESCRIPTIVE_WORDS = {"count", "counts", "limit", "limits", "budget", "policy", "policies", "length", "size", "usage",
                     "used", "expiry", "expires", "ttl", "type", "rotation", "rotated", "reset", "hint", "file", "path"}
KEY_SEP_RX = re.compile(r"(?<![A-Za-z0-9_.-])([\"']?)([A-Za-z][A-Za-z0-9_.-]*)\1\s*[:=]")
STATUS_WORDS = {"expired", "rotated", "revoked", "invalid", "valid", "budget", "limit", "count", "present",
                "absent", "stored", "encrypted", "configured", "unavailable", "disabled", "enabled", "hidden"}
PLACEHOLDER_VALUES = {"required", "optional", "none", "null", "redacted", "unset", "set", "missing", "empty",
                      "true", "false", "yes", "no", "n/a", "***", "<redacted>", "xxx", "changeme?"}
CONTEXT_WORDS = {"context", "tokens", "budget", "window"}
ZERO_WIDTH = dict.fromkeys(map(ord, "\u200b\u200c\u200d\u2060\ufeff\u00ad"))

# The only values under a credential key that are not refused: exact references to a variable (${NAME}, %NAME%,
# env:NAME, or an upper-case environment-variable name that itself names a credential, optionally after $), never a
# value that merely starts like one (driver review rounds 4-8 found a bypass in every looser exemption).
REFERENCE_RX = re.compile(r"\$\{[A-Za-z_][A-Za-z0-9_]*\}|%[A-Za-z_][A-Za-z0-9_]*%|env:[A-Za-z_][A-Za-z0-9_]*"
                          r"|<[a-z][a-z _-]{0,40}>")
ENV_NAME_RX = re.compile(r"\$?([A-Z][A-Z0-9]*(?:_[A-Z0-9]+)+)")


def normalise(text: str) -> str:
    """NFKC (fullwidth '=' and similar forms) without zero-width characters, before any secret matching (FB-04)."""
    import unicodedata
    return unicodedata.normalize("NFKC", text).translate(ZERO_WIDTH)


def _key_words(key: str) -> list[str]:
    key = re.sub(r"([a-z0-9])([A-Z])", r"\1 \2", normalise(key).strip().strip("'\""))
    return [w for w in re.split(r"[^A-Za-z0-9]+", key.lower()) if w]


def credential_key(key) -> bool:
    if not isinstance(key, str):
        return False
    words = _key_words(key)
    for i, w in enumerate(words):
        hit = w in CREDENTIAL_WORDS or (i + 1 < len(words) and (w, words[i + 1]) in CREDENTIAL_PAIRS)
        if hit:
            rest = words[i + 2:] if (i + 1 < len(words) and (w, words[i + 1]) in CREDENTIAL_PAIRS) else words[i + 1:]
            if not (rest and rest[-1] in DESCRIPTIVE_WORDS):
                return True
    return False


def _exempt_word(key: str, word: str) -> bool:
    low = word.lower()
    if not word or low in PLACEHOLDER_VALUES or low in STATUS_WORDS or set(word) <= {"*", "x", "X", "."}:
        return True
    if REFERENCE_RX.fullmatch(word):
        return True
    env = ENV_NAME_RX.fullmatch(word)
    if env and credential_key(env.group(1)):
        return True  # $OPENAI_API_KEY, TAVILY_API_KEY, DB_PASSWORD: a variable name, not a value (R1-09)
    if "token" in _key_words(key) and (re.fullmatch(r"\d{1,7}[kKmM]?", word) or low in CONTEXT_WORDS):
        return True  # a context size ("token: 65536", "token: 128k context"), not a credential (R3-07, FB-05)
    return False


def _credential_value_secret(key: str, val: str) -> bool:
    """Default deny: every word of a value under a credential key must be a placeholder, a state word, a mask, an
    exact variable reference or (for token keys) a context size; anything else is a secret."""
    words = [w for w in re.split(r"[\s,]+", normalise(str(val)).strip()) if w.strip("'\"{}()[]")]
    return bool(words) and not all(_exempt_word(key, w) or _exempt_word(key, w.strip("'\"{}()[]")) for w in words)


STRUCT_SEP_RX = re.compile(r"[,;{\[\n]\s*\Z")


def _assignment_secret(text: str) -> bool:
    text = normalise(text)
    marks = list(KEY_SEP_RX.finditer(text))
    for i, m in enumerate(marks):
        if not credential_key(m.group(2)):
            continue
        # the value runs to the next assignment that follows a structural separator ("a: x, b: y", '{"a": 1, "b"'),
        # so "password: env:DB_PASSWORD hunter2" is read whole (driver D2-02)
        nxt = [n for n in marks[i + 1:] if STRUCT_SEP_RX.search(text, 0, n.start())]
        stop = nxt[0].start() if nxt else len(text)
        val = re.split(r"[;\r\n|]", text[m.end():stop], maxsplit=1)[0]
        if _credential_value_secret(m.group(2), val):
            return True
    return False


class ValidationError(Exception):
    def __init__(self, code: str, message: str):
        super().__init__(f"{code}: {message}")
        self.code = code


def find_secret(value) -> str | None:
    """Return the name of the first secret pattern found anywhere in ``value`` (str/list/dict), else None."""
    def walk(part, keys: tuple[str, ...]) -> str | None:
        if isinstance(part, (str, int, float)) and not isinstance(part, bool):
            for key in keys:
                if credential_key(key) and _credential_value_secret(key, str(part).strip()):
                    return "credential assignment"
            if isinstance(part, str):
                text = normalise(part)
                for name, rx in SECRET_PATTERNS:
                    if rx.search(text):
                        return name
                return "credential assignment" if _assignment_secret(text) else None
            return None
        if isinstance(part, dict):
            for key, item in part.items():
                # under a credential key, a dict key that carries no value of its own is the value
                # (FB-03: {"password": {"hunter2": None}}); a key over content is structure ({"value": [...]})
                leaf = item is None or isinstance(item, bool) or item in ({}, [], (), "")
                hit = walk(key, keys if leaf and any(credential_key(k) for k in keys) else ())
                if hit:
                    return hit
                hit = walk(item, keys + (key,) if isinstance(key, str) else keys)
                if hit:
                    return hit
        elif isinstance(part, (list, tuple)):
            for item in part:
                hit = walk(item, keys)
                if hit:
                    return hit
        return None

    return walk(value, ())


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
            "versions": {}, "duplicates": [], "pending_batches": {}, "last_key": None, "events": 0}


def norm_id(value) -> str:
    """Identity comparison form for actors and reviewers (case- and whitespace-insensitive)."""
    return " ".join(str(value or "").split()).casefold()


def independent_accept_reviews(p: dict, m: dict) -> list[dict]:
    """Current qualifying reviews, including independence from every recorded implementer."""
    implementers = {norm_id(a) for a in m["implementers"]}
    return [r for r in p["reviews"].values()
            if r["subject"] == m["id"] and r["commit"] == m.get("candidate_commit")
            and r["result_class"] == "COMPLETED_WITH_RESULT" and r["verdict"] in POSITIVE_VERDICTS
            and r["blocking_open"] == 0 and r["assurance"] in QUALIFYING_ASSURANCE
            and norm_id(r["reviewer"]["id"]) not in implementers]


# Creation kinds whose ``data.id`` names a record in a projection collection (and the field holding its origin).
CREATION = {"MILESTONE_CREATED": ("milestones", "created"), "REVIEW_RECORDED": ("reviews", "recorded"),
            "DECISION_RECORDED": ("decisions", "recorded"), "APPROVAL_REQUESTED": ("approvals", "requested"),
            "BLOCKER_ADDED": ("blockers", "opened"), "HANDOFF_RECORDED": ("handoffs", "recorded"),
            "RECORD_IMPORTED": ("records", "recorded")}


CONFLICT_DETAIL_KEYS = ("type", "entity", "subject", "subjects", "kind", "expected", "actual", "missing", "kept",
                        "duplicate", "lost", "anchor_problems", "unknown_previous", "adopted", "batch")


def conflict_fingerprint(c) -> str:
    """Digest of a conflict's recorded detail fields (only the keys it has, so adding a key to the code never changes
    existing fingerprints, review R18-03). A resolution binds to it, so a conflict whose content grows after a later
    sync (e.g. VERSION expected 2 / actual 3 becoming actual 4) is open again (review R17-01). Cached on the conflict
    (its detail fields never change after it is raised), review R18-02."""
    fp = c.get("_fp")
    if fp is None:
        import hashlib as _h
        import json as _j
        body = _j.dumps({k: c[k] for k in CONFLICT_DETAIL_KEYS if k in c}, sort_keys=True, separators=(",", ":"),
                        default=str)
        fp = c["_fp"] = _h.sha256(body.encode("utf-8")).hexdigest()[:16]
    return fp


def conflict_id(c) -> str:
    """The event part of a conflict id: the first 12 hex digits of the event hash that raised it."""
    return c["event"]["hash"][:12]


def display_id(open_conflicts, c) -> str:
    """The id users see and must type: ``<event hash 12>.<check 6>``. The check digests the content of every open
    conflict that event raised on that entity, so an id read before a sync changed them is refused as stale
    (review R18-01)."""
    import hashlib as _h
    group = sorted(conflict_fingerprint(x) for x in open_conflicts
                   if x["entity"] == c["entity"] and x["event"]["hash"] == c["event"]["hash"])
    return f"{conflict_id(c)}.{_h.sha256(','.join(group).encode()).hexdigest()[:6]}"


def _conflict(p, ctype, entity, ref, kind, subject=None, **extra):
    p["conflicts"].append({"type": ctype, "entity": entity, "subject": subject, "event": ref, "kind": kind,
                           "resolved": False, **extra})


def _bump(p: dict, entity: str) -> None:
    p["versions"][entity] = p["versions"].get(entity, 0) + 1


def _count(p: dict, prefix: str, ident: str) -> None:
    m = re.match(rf"^{re.escape(prefix)}-(\d+)$", ident or "")
    if m:
        p["counters"][prefix] = max(p["counters"].get(prefix, 0), int(m.group(1)))


def event_key(ev: dict) -> list:
    return [ev["ts"], ev["seg"], ev["seq"]]


def apply(p: dict, ev: dict) -> None:
    """Fold one event into ``p`` (in place). Events of a multi-event batch wait until the whole batch is present."""
    p.pop("_cidx", None)  # views' conflict index is derived; any event may change it (review R5-07)
    b = ev.get("batch")
    if isinstance(b, dict) and b.get("n", 1) > 1:
        pend = p.setdefault("pending_batches", {}).setdefault(b["id"], [])
        if any(x["hash"] == ev["hash"] for x in pend):
            return
        pend.append(ev)
        if len(pend) < b["n"]:
            return
        del p["pending_batches"][b["id"]]
        if b["id"] in p.setdefault("abandoned_ids", []):
            # A batch someone declared abandoned turned out complete: apply it and flag it, never drop recorded work
            # silently (review R4-03).
            _conflict(p, "ABANDONED_BATCH_COMPLETED", "LEDGER", {"seg": ev["seg"], "seq": ev["seq"],
                                                                 "hash": ev["hash"], "ts": ev["ts"],
                                                                 "actor": ev["actor"]}, "BATCH", None, batch=b["id"])
        for x in sorted(pend, key=lambda x: x["batch"]["i"]):
            _apply_one(p, x)
        return
    _apply_one(p, ev)


def _find(p, coll, ident, target, ev=None):
    """Record a later event refers to. ``target`` is the creation-event hash (exact even when the same id was
    created on two hosts), or ``"BATCH"`` for a record created by an earlier event of the same batch (review R3-02).
    Without a target (legacy events) the plain id is used."""
    origin = {"approvals": "requested", "blockers": "opened", "decisions": "recorded"}[coll]
    if target == "BATCH":
        key = (p.get("batch_keys", {}).get(((ev or {}).get("batch") or {}).get("id")) or {}).get((coll, ident))
        return (key, p[coll].get(key)) if key else (ident, None)
    rec = p[coll].get(ident)
    if not target or (rec and (rec.get(origin) or {}).get("hash") == target):
        return ident, rec
    for key, r in p[coll].items():
        if (r.get(origin) or {}).get("hash") == target:
            return key, r
    return ident, None


def _subject_of(p, entity):
    for coll in ("reviews", "approvals", "blockers", "handoffs"):
        if entity in p[coll]:
            return p[coll][entity].get("subject")
    return entity if entity in p["milestones"] else None


def _apply_one(p: dict, ev: dict) -> None:
    """Fold one event. Unknown kinds are counted no-ops. Never overwrites a record created by another event."""
    d, kind = ev["data"], ev["kind"]
    ref = {"seg": ev["seg"], "seq": ev["seq"], "hash": ev["hash"], "ts": ev["ts"], "actor": ev["actor"]}
    for entity, seen in (ev.get("base") or {}).items():
        if p["versions"].get(entity, 0) != seen:
            _conflict(p, "VERSION", entity, ref, kind, _subject_of(p, entity), expected=seen,
                      actual=p["versions"].get(entity, 0))
    if kind in CREATION and isinstance(d, dict) and d.get("id") is not None:
        coll, origin = CREATION[kind]
        existing = p[coll].get(d["id"])
        if existing is not None and (existing.get(origin) or {}).get("hash") != ev["hash"]:
            # Same id created by another event (another host, or a merge): keep both, never replace.
            alt = f"{d['id']}@{ev['seg']}.{ev['seq']}"
            subject = d.get("subject") or (d["id"] if kind == "MILESTONE_CREATED" else None)
            _conflict(p, "DUPLICATE_ID", d["id"], ref, kind, subject, kept=d["id"], duplicate=alt,
                      subjects=sorted({s for s in (subject, existing.get("subject")) if s}))
            if kind == "MILESTONE_CREATED":
                p["duplicates"].append({"id": d["id"], "as": alt, "data": d, "event": ref})
                p["events"] += 1
                p["last_key"] = event_key(ev)
                return
            d = {**d, "id": alt, "duplicate_of": d["id"]}
    if kind in CREATION and isinstance(d, dict) and d.get("id") is not None and isinstance(ev.get("batch"), dict):
        coll = CREATION[kind][0]
        p.setdefault("batch_keys", {}).setdefault(ev["batch"]["id"], {})[(coll, ev["data"]["id"])] = d["id"]
    p["events"] += 1
    p["last_key"] = event_key(ev)
    ms = p["milestones"]

    if kind == "MILESTONE_CREATED":
        ms[d["id"]] = {"id": d["id"], "title": d["title"], "objective": d.get("objective"),
                       "priority": d.get("priority"), "phase": d.get("phase") or "RESEARCH",
                       "status": d.get("status") or "PLANNED", "depends_on": list(d.get("depends_on") or []),
                       "acceptance_ref": d.get("acceptance_ref"), "worktree": d.get("worktree"),
                       "branch": d.get("branch"), "base_commit": d.get("base_commit"), "candidate_commit": None,
                       "bound_commit": None, "next_action": d.get("next_action"), "assignment": None, "implementers": [ev["actor"]],
                       "lifecycle": [], "integration": None, "origin": d.get("origin"), "created": ref,
                       "status_history": [{"status": d.get("status") or "PLANNED", "at": ev["ts"],
                                           "by": ev["actor"], "reason": "created"}]}
        _bump(p, d["id"])
    elif kind == "MILESTONE_UPDATED":
        m = ms.get(d["id"])
        if m:
            for k, v in d["fields"].items():
                m[k] = v
            if "candidate_commit" in d["fields"] and m["status"] in POSITIVE_STATUSES and m.get("bound_commit") \
                    and m["candidate_commit"] != m["bound_commit"]:
                # a concurrent host changed the candidate of a milestone accepted elsewhere (review R22-02)
                _conflict(p, "CANDIDATE_CHANGED", d["id"], ref, kind, d["id"], bound=m["bound_commit"],
                          candidate=m["candidate_commit"],
                          problems=[f"candidate set to {m['candidate_commit']} while {m['status']} rests on "
                                    f"{m['bound_commit']}"])
            _bump(p, d["id"])
    elif kind == "MILESTONE_STATUS_SET":
        m = ms.get(d["id"])
        _check_basis(p, d, ref)
        if m:
            m["status"] = d["status"]
            m["status_history"].append({"status": d["status"], "at": ev["ts"], "by": ev["actor"],
                                        "reason": d.get("reason"), "basis": d.get("basis")})
            _check_binding(p, m, d, ref)
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
            if norm_id(d["agent"]) not in map(norm_id, m["implementers"]):
                m["implementers"].append(d["agent"])
                _check_current_basis(p, m, ref, kind)
            _bump(p, d["id"])
    elif kind == "MILESTONE_RELEASED":
        m = ms.get(d["id"])
        if m:
            m["assignment"] = None
            _bump(p, d["id"])
    elif kind == "IMPLEMENTER_RECORDED":
        m = ms.get(d["id"])
        if m and norm_id(d["agent"]) not in map(norm_id, m["implementers"]):
            m["implementers"].append(d["agent"])
            _check_current_basis(p, m, ref, kind)
            _bump(p, d["id"])
    elif kind == "BLOCKER_ADDED":
        _count(p, "BLK", d["id"])
        p["blockers"][d["id"]] = {**d, "status": "OPEN", "opened": ref, "resolution": None}
        _bump(p, d["id"])
    elif kind == "BLOCKER_RESOLVED":
        key, b = _find(p, "blockers", d["id"], d.get("target"))
        if b is None and d.get("target"):
            _conflict(p, "UNBOUND_REFERENCE", d["id"], ref, kind, None)
        if b:
            b["status"] = "RESOLVED"
            b["resolution"] = {"text": d["resolution"], "at": ev["ts"], "by": ev["actor"]}
            _bump(p, key)
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
        key, a = _find(p, "approvals", d["id"], d.get("target"))
        if a is None and d.get("target"):
            _conflict(p, "UNBOUND_REFERENCE", d["id"], ref, kind, None)
        if a:
            a["status"] = d["outcome"]
            a["resolution"] = {**d, "at": ev["ts"], "relayed_by": ev["actor"]}
            _bump(p, key)
    elif kind == "DECISION_RECORDED":
        _count(p, "DEC", d["id"])
        _count(p, "LDEC", d["id"])
        # An imported row starts in the status its source states (e.g. SUPERSEDED without a named successor).
        p["decisions"][d["id"]] = {**d, "status": d.get("source_status") or "ACTIVE", "superseded_by": [],
                                   "supersedes": [],
                                   "corrections": [], "source_revisions": [], "recorded": ref}
        _bump(p, d["id"])
    elif kind == "DECISION_SUPERSEDED":
        okey, old = _find(p, "decisions", d["id"], d.get("target"), ev)
        nkey, new = _find(p, "decisions", d["by"], d.get("by_target"), ev)
        if (old is None and d.get("target")) or (new is None and d.get("by_target")):
            _conflict(p, "UNBOUND_REFERENCE", d["id"], ref, kind, None)
        if old:
            old["superseded_by"].append({"by": nkey, "partial": bool(d.get("partial")), "note": d.get("note"),
                                         "at": ev["ts"]})
            if d.get("link_only"):
                pass
            elif not d.get("partial"):
                old["status"] = "SUPERSEDED"
            elif old["status"] == "ACTIVE":
                old["status"] = "PARTIALLY_SUPERSEDED"
            _bump(p, okey)
        if new:
            new["supersedes"].append({"id": okey, "partial": bool(d.get("partial"))})
            _bump(p, nkey)
    elif kind == "DECISION_CORRECTED":
        key, dec = _find(p, "decisions", d["id"], d.get("target"), ev)
        if dec is None and d.get("target"):
            _conflict(p, "UNBOUND_REFERENCE", d["id"], ref, kind, None)
        if dec:
            dec["corrections"].append({**d, "at": ev["ts"], "by": ev["actor"]})
            _bump(p, key)
    elif kind == "DECISION_SOURCE_REVISED":
        dec = p["decisions"].get(d["id"])
        if dec:
            dec["source_revisions"].append({**d, "at": ev["ts"]})
            _bump(p, d["id"])
    elif kind in ("RECORD_IMPORTED", "RECORD_SOURCE_REVISED"):
        r = p["records"].get(d["id"])
        if r is None or kind == "RECORD_IMPORTED":
            p["records"][d["id"]] = {**d, "revisions": [], "recorded": ref,
                                     "original": {"fields": d.get("fields"), "color": d.get("color"),
                                                  "source": d.get("source")}}
        else:
            # keep the values being replaced, so the original row and every later version stay readable (R5-03)
            r["revisions"].append({"previous": {"fields": r.get("fields"), "color": r.get("color"),
                                                "source": r.get("source")},
                                   "fields": d.get("fields"), "color": d.get("color"), "source": d.get("source"),
                                   "at": ev["ts"]})
            r["fields"], r["color"], r["source"] = d.get("fields"), d.get("color"), d.get("source")
        _bump(p, d["id"])
    elif kind == "IMPORT_RECORDED":
        p["imports"].append({**d, "at": ev["ts"], "by": ev["actor"]})
    elif kind == "HANDOFF_RECORDED":
        _count(p, "HO", d["id"])
        p["handoffs"][d["id"]] = {**d, "recorded": ref}
        m = ms.get(d["subject"])
        if m and norm_id(ev["actor"]) not in map(norm_id, m["implementers"]):
            m["implementers"].append(ev["actor"])
            _check_current_basis(p, m, ref, kind)
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
        named = set(d.get("conflicts") or [])  # exactly the conflicts the resolver saw (review R2-05)
        # (event hash, conflict type) pairs the resolver was shown; a conflict the same event raises only after a
        # later sync has another type and stays open (review R16-01). Older events without "seen" keep the
        # hash-only rule.
        seen = {tuple(x) for x in d["seen"]} if isinstance(d.get("seen"), list) else None
        for c in p["conflicts"]:
            # cheap filters first (review R18-02)
            if c["resolved"] or c["entity"] != d["entity"] or c["event"]["hash"] not in named:
                continue
            # new resolutions store (hash, type, fingerprint); pre-R17 ones (hash, type) - either form must match
            if seen is not None and (c["event"]["hash"], c.get("type"), conflict_fingerprint(c)) not in seen \
                    and (c["event"]["hash"], c.get("type")) not in seen:
                continue
            c["resolved"] = True
            c["resolution"] = {"note": d["note"], "at": ev["ts"], "by": ev["actor"]}
    elif kind == "BATCH_ABANDONED":
        for b in d.get("batches") or []:
            p.setdefault("abandoned_ids", [])
            if b not in p["abandoned_ids"]:
                p["abandoned_ids"].append(b)
            p.get("pending_batches", {}).pop(b, None)
            p.setdefault("abandoned_batches", []).append({"id": b, "at": ev["ts"], "by": ev["actor"],
                                                          "reason": d.get("reason")})
    elif kind == "ANCHORS_RESET":
        p.setdefault("anchor_resets", []).append({"at": ev["ts"], "by": ev["actor"], "reason": d.get("reason"),
                                                  "lost": d.get("lost") or {}})
        if d.get("lost") or d.get("unknown_previous") or d.get("anchor_problems"):
            _conflict(p, "ANCHOR_LOSS", "LEDGER", ref, kind, None, lost=d.get("lost") or {},
                      unknown_previous=bool(d.get("unknown_previous")),
                      **({"anchor_problems": d["anchor_problems"]} if d.get("anchor_problems") else {}))
    elif kind == "STORE_RECOVERED":
        p["recoveries"].append({**d, "at": ev["ts"]})
        if d.get("anchor_problems"):
            _conflict(p, "ANCHOR_LOSS", "LEDGER", ref, kind, None, anchor_problems=d["anchor_problems"])
    elif kind == "LOSS_RECORDED":
        _conflict(p, "ANCHOR_LOSS", "LEDGER", ref, kind, None, anchor_problems=d.get("anchor_problems") or [])
        if d.get("pending_id"):
            p.setdefault("recorded_pending_ids", []).append(d["pending_id"])
    elif kind == "HOST_REGISTERED":
        p.setdefault("hosts", []).append({**d, "at": ev["ts"]})
        if d.get("pending_id"):
            p.setdefault("recorded_pending_ids", []).append(d["pending_id"])
        if d.get("anchor_problems"):
            _conflict(p, "ANCHOR_LOSS", "LEDGER", ref, kind, None, anchor_problems=d["anchor_problems"])
    elif kind == "ANCHORS_ADOPTED":
        _conflict(p, "ANCHOR_LOSS", "LEDGER", ref, kind, None, adopted=d)


POSITIVE_STATUSES = ("ACCEPTED", "INTEGRATED", "DONE")


def _check_binding(p, m, d, ref) -> None:
    """Keep the commit a positive status rests on (``bound_commit``) and compare every record of the basis with the
    candidate in the merged history: a host that changed the candidate concurrently must not leave the milestone
    ACCEPTED/INTEGRATED on an unreviewed commit (review R22-02)."""
    if d["status"] not in POSITIVE_STATUSES:
        m["bound_commit"] = None
        return
    basis = d.get("basis") or {}
    cand = m.get("candidate_commit")
    bound = basis.get("commit") or m.get("bound_commit")
    if not bound and d["status"] == "INTEGRATED":
        bound = (m.get("integration") or {}).get("candidate_commit")
    problems = []
    if bound and cand != bound:
        problems.append(f"candidate {cand} is not the commit {bound} that {d['status']} rests on")
    for r in basis.get("reviews") or []:
        rc = (p["reviews"].get(r) or {}).get("commit")
        if rc and rc != (bound or cand):
            problems.append(f"review {r} is on {rc}")
    for a in basis.get("approvals") or []:
        ac = (p["approvals"].get(a) or {}).get("commit")
        if ac != (bound or cand):
            problems.append(f"approval {a} is bound to {ac}")
    if d["status"] == "INTEGRATED":
        ic = (m.get("integration") or {}).get("candidate_commit")
        if ic != (bound or cand):
            problems.append(f"integration record is for {ic}")
    m["bound_commit"] = bound or cand
    if problems:
        _conflict(p, "CANDIDATE_CHANGED", m["id"], ref, "MILESTONE_STATUS_SET", m["id"], bound=m["bound_commit"],
                  candidate=cand, problems=problems)


def _check_current_basis(p, m, ref, kind) -> None:
    if m["status"] in POSITIVE_STATUSES and not independent_accept_reviews(p, m):
        _check_basis(p, {"id": m["id"], "status": m["status"],
                         "basis": m["status_history"][-1].get("basis")}, ref, kind)


def _check_basis(p, d, ref, kind="MILESTONE_STATUS_SET") -> None:
    """A positive status must name records that exist in the fold; otherwise flag it (forged cache or merge)."""
    basis = d.get("basis") or {}
    bad = []
    if d.get("status") in POSITIVE_STATUSES:
        names = basis.get("reviews") or []
        implementers = {norm_id(a) for a in (p["milestones"].get(d["id"]) or {}).get("implementers", [])}
        bad = [r for r in names if (p["reviews"].get(r) or {}).get("subject") != d["id"]
               or p["reviews"][r].get("verdict") not in POSITIVE_VERDICTS
               # independence re-checked in the merged history: an implementer recorded concurrently (another
               # host) can make the named reviewer non-independent (review R17-01)
               or norm_id((p["reviews"][r].get("reviewer") or {}).get("id")) in implementers]
        if not names:
            bad = ["(no review named)"]
    if d.get("status") == "INTEGRATED":
        names = basis.get("approvals") or []
        bad += [a for a in names if (p["approvals"].get(a) or {}).get("status") != "APPROVED"]
        if not names:
            bad.append("(no approval named)")
    if bad:
        _conflict(p, "BASIS_INVALID", d["id"], ref, kind, d["id"], missing=bad)


def fold(events, p: dict | None = None) -> dict:
    p = copy.deepcopy(p) if p is not None else empty_projection()
    for ev in events:
        apply(p, ev)
    return p


def ordered(segments) -> list[dict]:
    """Merge segments by (ts, seg, seq) while never reordering events inside one segment (review R2-06): a host
    clock that stepped back cannot move a later event of that host before an earlier one."""
    import heapq
    heads, out = [], []
    lists = [s.valid_events for s in segments]
    for n, evs in enumerate(lists):
        if evs:
            heapq.heappush(heads, (event_key(evs[0]), n, 0))
    while heads:
        _, n, i = heapq.heappop(heads)
        out.append(lists[n][i])
        if i + 1 < len(lists[n]):
            heapq.heappush(heads, (event_key(lists[n][i + 1]), n, i + 1))
    return out


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
