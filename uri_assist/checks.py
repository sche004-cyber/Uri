"""Live Assist: deterministic findings about a form, from one redacted observation. Read-only; nothing is changed.

Findings are suggestions with a stable code, the field they concern and a plain explanation. Sensitive fields are
only checked for "required but empty" (their values are never seen).
"""
from __future__ import annotations

import re
from datetime import date

from .perception import Observation

_EMAIL = re.compile(r"^[^@\s]+@[^@\s]+\.[A-Za-z]{2,}$")
_PHONE_CHARS = re.compile(r"^[+()\d\s.-]{6,}$")
_DMY = re.compile(r"^(\d{1,2})[/.-](\d{1,2})[/.-](\d{4})$")
_ISO = re.compile(r"^(\d{4})-(\d{2})-(\d{2})$")
MAX_FINDINGS = 30


def _label(f):
    return (f.get("label") or f.get("name") or f.get("id") or f.get("placeholder") or "field")[:80]


def _kind(f):
    t = (f.get("type") or "").lower()
    key = " ".join(str(f.get(k) or "") for k in ("name", "id", "label", "autocomplete", "placeholder")).lower()
    if t == "email" or "email" in key or "e-mail" in key:
        return "email"
    if t == "tel" or re.search(r"phone|mobile|\btel\b", key):
        return "phone"
    if t == "date" or re.search(r"\bdate\b|\bdob\b|birth", key):
        return "date"
    return "text"


def _valid_date(v):
    m = _ISO.match(v)
    try:
        if m:
            date(int(m[1]), int(m[2]), int(m[3]))
            return True
        m = _DMY.match(v)
        if m:
            date(int(m[3]), int(m[2]), int(m[1]))
            return True
    except ValueError:
        return False
    return False


def findings(obs: Observation) -> list:
    out = []

    def add(code, f, message):
        if len(out) < MAX_FINDINGS:
            out.append({"code": code, "field": _label(f), "field_id": f.get("id") or f.get("automation_id") or None,
                        "message": message})
    for f in obs.fields:
        if f.get("readonly"):
            continue
        if f.get("sensitive"):
            if f.get("required") and not f.get("has_value"):
                add("REQUIRED_EMPTY", f, "This required field is empty.")
            continue
        v = (f.get("value") or "").strip()
        if f.get("required") and not v:
            add("REQUIRED_EMPTY", f, "This required field is empty.")
            continue
        if not v or v == "[redacted]":
            continue
        k = _kind(f)
        if k == "email" and not _EMAIL.match(v):
            add("EMAIL_FORMAT", f, "This doesn't look like a complete e-mail address.")
        elif k == "phone":
            digits = re.sub(r"\D", "", v)
            if not _PHONE_CHARS.match(v) or not 7 <= len(digits) <= 15:
                add("PHONE_FORMAT", f, "This phone number has an unusual number of digits or characters.")
        elif k == "date" and not _valid_date(v):
            add("DATE_FORMAT", f, "This isn't a valid date (expected e.g. 2026-10-10 or 10/10/2026).")
        raw = f.get("value") or ""
        if raw != raw.strip() or "  " in raw:
            add("WHITESPACE", f, "There are extra spaces in this value.")
    # Confirmation pairs: a field named/labelled "confirm/re-enter/repeat/verify ..." is compared with the nearest
    # earlier field of the same kind that is not itself a confirmation field.
    confirm = re.compile(r"confirm|re-?enter|repeat|verify|again")
    prev = {}
    for f in obs.fields:
        if f.get("sensitive"):
            continue
        key = " ".join(str(f.get(k) or "") for k in ("name", "id", "label")).lower()
        k = _kind(f)
        v = (f.get("value") or "").strip()
        if confirm.search(key):
            base = prev.get(k)
            if base is not None and v and (base.get("value") or "").strip().lower() != v.lower():
                add("CONFIRMATION_MISMATCH", f, f"This doesn't match \"{_label(base)}\".")
        elif v:
            prev[k] = f
    return out
