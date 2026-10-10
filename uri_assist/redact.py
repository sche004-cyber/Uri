"""Redaction applied to every structured snapshot BEFORE it is used, shown, or sent to the Brain.

Field rules (value removed, field marked `sensitive`):
  * input type password / hidden;
  * autocomplete tokens for passwords, one-time codes and payment cards;
  * name / id / label / automation id that names a secret (password, token, OTP, PIN, CVV, card, account number,
    national IDs such as SSN, Aadhaar, PAN);
  * UI Automation elements flagged IsPassword.
Text rules (masked in any text: page text, selection, field values, labels): JWTs, bearer tokens, common API-key
prefixes, long hex/base64 secrets, Luhn-valid card numbers, 12-digit Aadhaar-shaped numbers, `key=value` query
secrets. Each redaction is counted by kind; the counts (never the values) are reported.
"""
from __future__ import annotations

import re
from collections import Counter

MASK = "[redacted]"
SENSITIVE_TYPES = {"password", "hidden"}
SENSITIVE_AUTOCOMPLETE = {"current-password", "new-password", "one-time-code", "cc-number", "cc-csc", "cc-exp",
                          "cc-exp-month", "cc-exp-year", "cc-name", "cc-type"}
_SENSITIVE_NAME = re.compile(r"(?i)(pass(word|wd|code|phrase)|(?<![a-z])pass(?![a-z])|pwd|secret|token|api[_-]?key|(?<![a-z])otp(?![a-z])|one[_-]?time|(?<![a-z])pin(?![a-z])|"
                             r"cvv|cvc|csc|card[_-]?(number|no)|cc[_-]?(num|number)|account[_-]?(number|no)|iban|"
                             r"\bssn\b|social[_-]?security|aadh?aar|\bpan\b|pan[_-]?(number|no)|security[_-]?(code|answer)|"
                             r"auth(?!or)|session|cookie|private[_-]?key)")
_TEXT_RULES = (
    ("jwt", re.compile(r"\beyJ[A-Za-z0-9_-]{8,}\.[A-Za-z0-9_-]{8,}\.[A-Za-z0-9_-]{8,}\b")),
    ("bearer", re.compile(r"(?i)\bbearer\s+[A-Za-z0-9._~+/=-]{16,}")),
    ("api_key", re.compile(r"\b(?:sk|pk|rk)-[A-Za-z0-9_-]{16,}\b|\bgh[pousr]_[A-Za-z0-9]{20,}\b|\bAKIA[0-9A-Z]{16}\b|"
                           r"\bxox[abpr]-[A-Za-z0-9-]{10,}\b|\btvly-[A-Za-z0-9_-]{8,}\b|\bAIza[0-9A-Za-z_-]{30,}\b")),
    ("query_secret", re.compile(r"(?i)\b((?:access_?token|token|api_?key|key|secret|password|pwd|sig|signature|code)=)[^&\s\"'<>]{6,}")),
    ("long_secret", re.compile(r"\b(?=[A-Fa-f0-9]*[A-Fa-f])(?=[A-Fa-f0-9]*\d)[A-Fa-f0-9]{32,}\b|"
                               r"\b(?=[A-Za-z0-9+/]*\d)(?=[A-Za-z0-9+/]*[A-Z])(?=[A-Za-z0-9+/]*[a-z])[A-Za-z0-9+/]{40,}={0,2}")),
    ("aadhaar", re.compile(r"(?<!\d)(?<!\d[ -])[2-9]\d{3}[ -]?\d{4}[ -]?\d{4}(?![ -]?\d)")),
)
_CARD = re.compile(r"\b(?:\d[ -]?){12,18}\d\b")


def _luhn(digits: str) -> bool:
    total, alt = 0, False
    for ch in reversed(digits):
        d = ord(ch) - 48
        if alt:
            d *= 2
            if d > 9:
                d -= 9
        total += d
        alt = not alt
    return total % 10 == 0


def redact_text(text, counts: Counter) -> str:
    if not isinstance(text, str) or not text:
        return text if isinstance(text, str) else ""

    def card(m):
        digits = re.sub(r"\D", "", m.group(0))
        if 13 <= len(digits) <= 19 and _luhn(digits):
            counts["card"] += 1
            return MASK
        return m.group(0)
    out = _CARD.sub(card, text)
    for kind, rx in _TEXT_RULES:
        def sub(m, kind=kind):
            counts[kind] += 1
            return (m.group(1) + MASK) if kind == "query_secret" else MASK
        out = rx.sub(sub, out)
    return out


def field_is_sensitive(f: dict) -> bool:
    if str(f.get("type", "")).lower() in SENSITIVE_TYPES:
        return True
    if f.get("is_password") is True:
        return True
    ac = set(str(f.get("autocomplete", "")).lower().split())
    if ac & SENSITIVE_AUTOCOMPLETE:
        return True
    for k in ("name", "id", "label", "automation_id", "placeholder", "aria_label"):
        v = f.get(k)
        if isinstance(v, str) and _SENSITIVE_NAME.search(v):
            return True
    return False


def redact_field(f: dict, counts: Counter) -> dict:
    out = {k: (redact_text(v, counts) if isinstance(v, str) else v) for k, v in f.items() if k != "value"}
    if field_is_sensitive(f):
        out["sensitive"] = True
        out["has_value"] = bool(f.get("value"))
        if f.get("value"):
            counts["sensitive_field"] += 1
        return out
    out["sensitive"] = False
    out["value"] = redact_text(f.get("value") if isinstance(f.get("value"), str) else "", counts)
    return out
