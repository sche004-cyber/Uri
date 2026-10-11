"""Redaction applied to every structured snapshot BEFORE it is used, shown, or sent to the Brain.

Field rules (value removed, field marked `sensitive`):
  * input type password / hidden;
  * autocomplete tokens for passwords, one-time codes and payment cards;
  * name / id / label / automation id that names a secret (password, token, OTP, TAN / mTAN, 2SV / two-step code,
    PIN, CVV, any *key, credential, authorization, recovery / backup code, session, card, account number, national IDs
    such as SSN, Aadhaar, PAN, passport);
  * a short single-token value in a field whose name or label ends in code / pin / key;
  * UI Automation elements flagged IsPassword.
Text rules (masked in any text: page text, selection, field values, labels): JWTs, bearer tokens, HTTP Basic
credentials, API keys with known prefixes (OpenAI/Anthropic sk-, Stripe sk_/rk_/pk_ live/test, GitHub ghp_ /
github_pat_, GitLab glpat-, npm_, Hugging Face hf_, SendGrid SG., AWS AKIA, Slack xox, Google AIza, Tavily tvly-), long hex/base64 secrets, Luhn-valid card numbers, 12-digit Aadhaar-shaped numbers, `key=value` query
secrets. Each redaction is counted by kind; the counts (never the values) are reported.
"""
from __future__ import annotations

import re
from collections import Counter

MASK = "[redacted]"
SENSITIVE_TYPES = {"password", "hidden"}
SENSITIVE_AUTOCOMPLETE = {"current-password", "new-password", "one-time-code", "cc-number", "cc-csc", "cc-exp",
                          "cc-exp-month", "cc-exp-year", "cc-name", "cc-type"}
# Names are split into words first ("smsOtp" -> "sms otp", "OTPCode" -> "otp code", "cvv2" -> "cvv 2",
# "user_pin" -> "user pin") so short tokens such as otp / pin / pw match only as whole words ("hotpot", "spinner",
# "pincode" do not). An all-caps run ending in otp ("SMSOTP" -> "smsotp") is still a one-time code.
_SENSITIVE_WORDS = re.compile(
    r"\b(pass|pw|pwd|[a-z]*otp|mfa|2 ?fa|pin(?! ?code)|mpin|tpin|cvv|cvc|ccv|csc|cvn|ssn|pan|iban|secret|token|cookie|session|auth|"
    r"password|passwd|passcode|passphrase|apikey|aadhar|aadhaar|tan|mtan|smstan|otc|2 ?sv)\b|"
    r"\bapi ?key\b|\btwo ?step\b|\bone ?time\b|\btwo ?factor\b|\bverification ?code\b|\bsecurity ?(code|answer)\b|\bauth ?code\b|"
    r"\bcard ?(number|num|no|expiry|exp|expiration)\b|\bacct ?(number|num|no)\b|\bcc ?(num|number|no)\b|\baccount ?(number|num|no)\b|\bsocial ?security\b|\bpan ?(number|no)\b|"
    r"\bprivate ?key\b")
# Run-together lowercase names ("otpcode", "cardcvv", "newpassword", "upipin", "loginpwd", "userpass", "verifycode"):
# long stems match anywhere in a word; otp only at the start/end of a word or before a known suffix ("footpath",
# "hotpot", "hotplate" stay readable); pin / pass / code only after a known prefix ("pincode", "spinner", "camping",
# "passenger", "compass", "zipcode" stay readable).
_RUN_TOGETHER = re.compile(
    r"password|passwd|passcode|passphrase|pwd|cvv|cvc|ccv|\b(mpin|tpin)|(mpin|tpin)\b|"
    r"\botp|otp\b|otp(code|value|val|number|num|no|input|field|digit|box|text|entry|pin|token)|"
    r"(upi|atm|card|security|secure|login|user|txn|transaction|account|acct|debit|credit|bank|access|mobile|wallet|"
    r"new|old|confirm|current|verify|secret)pin(number|num|no)?\b|\bpin(number|num|no|entry|input|field|value)\b|"
    r"(user|login|admin|account|acct|new|old|confirm|current|root|wifi|txn|master|secret|db)pass\b|"
    r"(verify|verif|sms|email|access|activation|confirmation|confirm|login|signin)code\b")
# Secret stems inside a word, whatever comes before or after them. Matched on each word of _tokens() (split at
# separators and camelCase, not at digits: "2facode" stays one word) after the readable words in _READABLE are cut
# out, so a stem never spans two words of a label ("not familiar" has no "tfa") and "keyboard" / "monkey" stay
# readable. R3-01 and R4-01 showed that lists of cited names leak the next name, so this is a class of stems:
# one-time and 2FA codes, card security codes, passwords, any *key (api, access, signing, master, pass, priv ...),
# tokens (a personal access token is a "pat"), secrets, credentials, recovery material, session/cookie/CSRF values and national IDs. otp not before
# a/h/l/o ("footpath", "hotpot", "hotplate"); tfa only at the start of a word ("nightfall"); secret not in
# "secretary".
_STEMS = re.compile(
    r"otp(?![ahlo])|mfa|2fa|\btfa|onetime|twofactor|twostep|verification|authenticat|authoriz|cvv|cvc|ccv|token|secret(?!ar)|"
    r"password|passwd|passcode|passphrase|pwd|key|credential|recovery|mnemonic|seedphrase|aadhaa?r|\bssn|ssn\b|"
    r"passport|iban|jwt|csrf|xsrf|bearer|cookie|session|pat\b|psk\b|maiden")
_READABLE = re.compile(r"keyboard|keyword|keynote|keystone|keyframe|monkey|donkey|turkey|hockey|jockey|whiskey|"
                       r"possession|obsession|expat")
# Secret phrases written as several words ("Recovery code", "backup_code", "Social security number"), matched on
# the whole name with everything but letters and digits removed.
_PHRASES = re.compile(r"backupcode|resetcode|unlockcode|recoverycode|seedphrase|secretphrase|socialsecurity|"
                      r"cardnumber|cardnum|ccnumber|ccnum|accountnumber|accountnum|acctnumber|acctnum|sessionid|"
                      r"privatekey|apikey|securitycode|securityanswer|authcode|nationalid|taxid|routingnumber|bankaccount|sessid|"
                      r"nonce")
# A short single-token value (3-32 letters, digits, _ or -) is a code / PIN / key when a name, label or placeholder
# ENDS with code, pin or key ("cardcode", "smspin", "Enter code:"; "7f3a9-2c1d8" as well as "482913", R4-01),
# checked on the name with everything but letters and digits removed; postal, country, area, promo, coupon,
# voucher, referral, bar, sort, IFSC, SWIFT, currency, language and locale codes stay readable.
_CODE_END = re.compile(r"(code|pin|key)(number|num|no)?$")
_CODE_EXCLUDE = re.compile(r"postal|zip|postcode|pincode|country|area|promo|coupon|voucher|referral|barcode|sortcode|"
                           r"ifsc|swift|currency|language|locale")

def _words(v: str) -> str:
    v = re.sub(r"(?<=[a-z])(?=[A-Z])|(?<=[A-Z])(?=[A-Z][a-z])|(?<=[A-Za-z])(?=\d)|(?<=\d)(?=[A-Za-z])", " ", v)
    return re.sub(r"[_\-.:/]+", " ", v).lower()


def _tokens(v: str) -> str:
    v = re.sub(r"(?<=[a-z])(?=[A-Z])|(?<=[A-Z])(?=[A-Z][a-z])", " ", v)
    return re.sub(r"[^A-Za-z0-9]+", " ", v).lower()


def _joined(v: str) -> str:
    return re.sub(r"[^a-z0-9]+", "", v.lower())


_TEXT_RULES = (
    ("jwt", re.compile(r"\beyJ[A-Za-z0-9_-]{8,}\.[A-Za-z0-9_-]{8,}\.[A-Za-z0-9_-]{8,}\b")),
    ("bearer", re.compile(r"(?i)\bbearer\s+[A-Za-z0-9._~+/=-]{16,}")),
    ("basic_auth", re.compile(r"(?i)\bbasic\s+(?=[A-Za-z0-9+/]*[0-9+/=])[A-Za-z0-9+/]{12,}={0,2}")),
    ("api_key", re.compile(r"\b(?:sk|pk|rk)-[A-Za-z0-9_-]{16,}\b|\b(?:sk|pk|rk)_(?:live|test)_[A-Za-z0-9]{16,}\b|"
                           r"\bgithub_pat_[A-Za-z0-9_]{40,}|\bglpat-[A-Za-z0-9_-]{20,}|\bnpm_[A-Za-z0-9]{36}\b|"
                           r"\bhf_[A-Za-z0-9]{30,}\b|\bSG\.[A-Za-z0-9_-]{16,}\.[A-Za-z0-9_-]{16,}|\bgh[pousr]_[A-Za-z0-9]{20,}\b|\bAKIA[0-9A-Z]{16}\b|"
                           r"\bxox[abpr]-[A-Za-z0-9-]{10,}\b|\btvly-[A-Za-z0-9_-]{8,}\b|\bAIza[0-9A-Za-z_-]{30,}\b")),
    ("query_secret", re.compile(r"(?i)\b((?:access_?token|token|api_?key|key|secret|password|pwd|sig|signature|code)=)[^&\s\"'<>]{6,}")),
    ("long_secret", re.compile(r"\b(?=[A-Fa-f0-9]*[A-Fa-f])(?=[A-Fa-f0-9]*\d)[A-Fa-f0-9]{32,}\b|"
                               r"\b(?=[A-Za-z0-9+/]*\d)(?=[A-Za-z0-9+/]*[A-Z])(?=[A-Za-z0-9+/]*[a-z])[A-Za-z0-9+/]{40,}={0,2}")),
    ("aadhaar", re.compile(r"(?<!\d)(?<!\d[ -])[2-9]\d{3}[ -]?\d{4}[ -]?\d{4}(?![ -]?\d)")),
)
_CARD = re.compile(r"\b(?:\d[ .\u00a0\u2007\u202f-]?){12,18}\d\b")
_SHORT_CODE = re.compile(r"^\s*[A-Za-z0-9_-]{3,32}\s*$")
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


def _short_code_label(v: str) -> bool:
    if _POSTAL.search(v) or _CODE_EXCLUDE.search(_joined(v)):
        return False
    return bool(_CODE_LABEL.search(_words(v)) or _CODE_END.search(_READABLE.sub("", _joined(v))))


def _secret_name(v: str) -> bool:
    return bool(_SENSITIVE_WORDS.search(_words(v)) or _RUN_TOGETHER.search(_words(v)) or
                any(_STEMS.search(_READABLE.sub("", t)) for t in _tokens(v).split()) or _PHRASES.search(_joined(v)))


def field_is_sensitive(f: dict) -> bool:
    ftype = str(f.get("type", "")).lower()
    if ftype in SENSITIVE_TYPES:
        return True
    # A short single-token value in a field labelled "... code" / ending in code, pin or key is a one-time, recovery
    # or access code (F5, R3-01, R4-01). Checkbox and radio values are only checked/unchecked.
    if ftype not in ("checkbox", "radio") and isinstance(f.get("value"), str) and _SHORT_CODE.match(f["value"]) and any(
            isinstance(f.get(k), str) and _short_code_label(f[k])
            for k in ("label", "name", "placeholder", "aria_label")):
        return True
    if f.get("is_password") is True:
        return True
    ac = set(str(f.get("autocomplete", "")).lower().split())
    if ac & SENSITIVE_AUTOCOMPLETE:
        return True
    for k in ("name", "id", "label", "automation_id", "placeholder", "aria_label"):
        v = f.get(k)
        if isinstance(v, str) and _secret_name(v):
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
