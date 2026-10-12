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
# Names are split into words first ("smsOtp" -> "sms otp", "user_pin" -> "user pin") so short tokens such as
# otp / pin / pw match only as whole words ("hotpot", "spinner", "pincode" do not).
_SENSITIVE_WORDS = re.compile(
    r"\b(pass|pw|pwd|otp|totp|hotp|mfa|2fa|pin(?! ?code)|cvv|cvc|csc|cvn|ssn|pan|iban|secret|token|cookie|session|auth|"
    r"password|passwd|passcode|passphrase|apikey|aadhar|aadhaar)\b|"
    r"\bapi ?key\b|\bone ?time\b|\btwo ?factor\b|\bverification ?code\b|\bsecurity ?(code|answer)\b|\bauth ?code\b|"
    r"\bcard ?(number|num|no)\b|\bcc ?(num|number|no)\b|\baccount ?(number|num|no)\b|\bsocial ?security\b|\bpan ?(number|no)\b|"
    r"\bprivate ?key\b")


def _words(v: str) -> str:
    v = re.sub(r"(?<=[a-z])(?=[A-Z])", " ", v)
    return re.sub(r"[_\-.:/]+", " ", v).lower()


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
_CARD = re.compile(r"\b(?:\d[ .\u00a0\u2007\u202f-]?){12,18}\d\b")
_SHORT_CODE = re.compile(r"^\s*\d{4,8}\s*$")
_CODE_LABEL = re.compile(r"(?i)\bcode\b")
_POSTAL = re.compile(r"(?i)postal|zip|post ?code|pin ?code")


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
    # A short all-digit value in a field labelled "... code" is treated as a one-time code (F5).
    if isinstance(f.get("value"), str) and _SHORT_CODE.match(f["value"]) and any(
            isinstance(f.get(k), str) and _CODE_LABEL.search(_words(f[k])) and not _POSTAL.search(f[k])
            for k in ("label", "name", "placeholder", "aria_label")):
        return True
    if f.get("is_password") is True:
        return True
    ac = set(str(f.get("autocomplete", "")).lower().split())
    if ac & SENSITIVE_AUTOCOMPLETE:
        return True
    for k in ("name", "id", "label", "automation_id", "placeholder", "aria_label"):
        v = f.get(k)
        if isinstance(v, str) and _SENSITIVE_WORDS.search(_words(v)):
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
