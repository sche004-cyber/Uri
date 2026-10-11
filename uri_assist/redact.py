"""Redaction applied to every structured snapshot BEFORE it is used, shown, or sent to the Brain.

Field rules (value removed, field marked `sensitive`):
  * input type password / hidden;
  * autocomplete tokens for passwords, one-time codes and payment cards;
  * name / id / label / automation id that names a secret (password, token, OTP, TAN / mTAN, 2SV / two-step code,
    PIN, card security codes (CVV, CVC, CVD, CSV, CAV2, CID), any *key, credential, authorization, recovery / backup
    code, session, card, account number, national IDs such as SSN, Aadhaar, PAN, passport);
  * a short code value (one token, or up to four space-separated groups such as "482 913", 3-32 characters) in a
    field whose name or label ends in code / pin / key;
  * UI Automation elements flagged IsPassword.
Text rules (masked in any text: page text, selection, field values, labels): JWTs, bearer tokens, HTTP Basic
credentials, API keys with known prefixes (OpenAI/Anthropic sk-, Stripe sk_/rk_/pk_ live/test, GitHub ghp_ /
github_pat_, GitLab glpat-, npm_, Hugging Face hf_, SendGrid SG., AWS AKIA, Slack xox, Google AIza, Tavily tvly-), long hex/base64 secrets, Luhn-valid card numbers, 12-digit Aadhaar-shaped numbers, `key=value` query
secrets, and in the page URL the userinfo and the value of every query / fragment key that names a secret
(`redact_url`). Each redaction is counted by kind; the counts (never the values) are reported.
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
    r"\b(pass|pw|pwd|[a-z]*otp|mfa|2 ?fa|pin(?! ?code)|mpin|tpin|cvv|cvc|ccv|csc|cvn|cvd|csv|cid|cav ?2|ssn|pan|iban|secret|token|cookie|session|auth|"
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
    r"otp(?![ahlo])|mfa|2fa|\btfa|onetime|twofactor|twostep|verification|authenticat|authoriz|cvv|cvc|ccv|cvd|cav2|token|secret(?!ar)|"
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
# A short code value (3-32 letters, digits, _ or -, in one token or in up to four groups split by single spaces such
# as "482 913", R6-02) is a code / PIN / key when a name, label or placeholder ENDS with code, pin or key
# ("cardcode", "smspin", "Enter code:"; "7f3a9-2c1d8" as well as "482913", R4-01), checked on the name with everything but letters and digits removed; postal, country, area, promo, coupon,
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
_SHORT_CODE = re.compile(r"^\s*(?=(?:\s?[A-Za-z0-9_-]){3,32}\s*$)[A-Za-z0-9_-]+(?: [A-Za-z0-9_-]+){0,3}\s*$")
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
    # R41-03: a URL written in text (page text, a heading, a label, a field value) gets the Location rule: its userinfo
    # is removed and every secret-naming query or fragment value is masked at any length (same rule in snapshot.js).
    return _split_url_parts(_TOKEN.sub(lambda m: _url_parts(m.group(0), counts), out), counts)


# R1-04: in a URL, the userinfo (user:password@) is removed, and the value of every query or fragment key that names a
# secret is masked whatever its length: the field-name classifier (client_secret, refresh_token, otp, pin, passcode,
# session_id ...), a key ending in code / pin / key, and sig / signature / sid. The same rule is in snapshot.js.
_URL_USERINFO = re.compile(r"(?i)^([a-z][a-z0-9+.-]*://)[^/?#@\s]*@")
_URL_PAIR = re.compile(r"([?#&;])([^=&#;?\s]*)=([^&#;\s]*)")


def _secret_key(k: str) -> bool:
    from urllib.parse import unquote
    k = unquote(k)
    j = _joined(k)
    return bool(_secret_name(k) or (_CODE_END.search(_READABLE.sub("", j)) and not _CODE_EXCLUDE.search(j))
                or j in ("sig", "signature", "sid"))


_TOKEN = re.compile(r"[^\s\"'<>]+")
_TEXT_USERINFO = re.compile(r"(?i)\b([a-z][a-z0-9+.-]*://)[^/?#@\s\"'<>]*@")
_TEXT_PAIR = re.compile(r"(^|[?#&;])([^=&#;?\s]*)=([^&#;\s]*)")


def _url_parts(tok: str, counts: Counter) -> str:
    """One whitespace-free token of text (a URL, part of one, or a bare key=value such as 'client_secret=...')."""
    def userinfo(m):
        counts["url_userinfo"] += 1
        return m.group(1)

    def pair(m):
        if not m.group(3) or m.group(3) == MASK or not _secret_key(m.group(2)):
            return m.group(0)
        counts["query_secret"] += 1
        return f"{m.group(1)}{m.group(2)}={MASK}"
    out = _TEXT_USERINFO.sub(userinfo, tok)
    at = min((i for i in (out.find("?"), out.find("#")) if i >= 0), default=0)
    return out[:at] + _TEXT_PAIR.sub(pair, out[at:])


_KEY_EMPTY = re.compile(r"(?:^|[?#&;])([^=&#;?\s]+)=$")
_KEY_BARE = re.compile(r"(?:^|[?#&;])([^=&#;?\s]+)$")
_VALUE_HEAD = re.compile(r"^[^&#;\s]+")
_SPLIT_USER = re.compile(r"(?i)\b([a-z][a-z0-9+.-]*://)[^/?#@\s\"'<>]*:$")


def _split_url_parts(text: str, counts: Counter) -> str:
    """R42-01: a URL cut by whitespace (text nodes of inline elements joined with a separator, or a gap the user typed)
    fails closed: a secret-naming key with an empty value ('client_secret=' or 'client_secret' '=') masks the value in
    the next token, and 'scheme://user:' followed within two tokens by '...@' loses that userinfo (same rule as
    splitUrlParts in snapshot.js)."""
    toks = [[m.start(), m.group(0), m.group(0)] for m in _TOKEN.finditer(text)]

    def mask_head(k, pre):
        if k >= len(toks):
            return
        body = toks[k][1][len(pre):]
        v = _VALUE_HEAD.match(body)
        if not v or body.startswith(MASK):
            return
        counts["query_secret"] += 1
        toks[k][1] = pre + MASK + body[v.end():]
    for i in range(len(toks)):
        t, nx = toks[i][1], toks[i + 1][1] if i + 1 < len(toks) else ""
        m = _KEY_EMPTY.search(t)
        if m and _secret_key(m.group(1)):
            mask_head(i + 1, "")
        elif nx.startswith("="):
            m = _KEY_BARE.search(t)
            if m and _secret_key(m.group(1)):
                if nx == "=":
                    mask_head(i + 2, "")
                else:
                    mask_head(i + 1, "=")
        u = _SPLIT_USER.search(toks[i][1])
        for k in (i + 1, i + 2) if u else ():
            if k >= len(toks):
                break
            q = toks[k][1]
            at, stop = q.find("@"), re.search(r"[/?#]", q)
            if at < 0 or (stop and stop.start() < at):
                continue
            counts["url_userinfo"] += 1
            toks[i][1] = toks[i][1][:u.start()] + u.group(1)
            for j in range(i + 1, k):
                toks[j][1] = ""
            toks[k][1] = q[at + 1:]
            break
    out, end = [], 0
    for start, new, old in toks:
        out.append(text[end:start] + new)
        end = start + len(old)
    return "".join(out) + text[end:]


def redact_url(url, counts: Counter) -> str:
    if not isinstance(url, str) or not url:
        return url if isinstance(url, str) else ""

    def userinfo(m):
        counts["url_userinfo"] += 1
        return m.group(1)

    def pair(m):
        if not m.group(3) or m.group(3) == MASK or not _secret_key(m.group(2)):
            return m.group(0)
        counts["query_secret"] += 1
        return f"{m.group(1)}{m.group(2)}={MASK}"
    out = _URL_USERINFO.sub(userinfo, redact_text(url, counts))
    at = min((i for i in (out.find("?"), out.find("#")) if i >= 0), default=-1)
    if at >= 0:
        out = out[:at] + _URL_PAIR.sub(pair, out[at:])
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


# Owner decision D8 (2026-10-11): field values are WITHHELD BY DEFAULT (fail closed). A value is shared only for
# checkbox/radio state, search boxes, and fields whose name, id or label is plainly a search, comment, message,
# subject or notes field - and never when the field looks sensitive. Everything else is reported by label and type
# with `has_value`, and masked in screenshots like a sensitive field. The same rule is in browser_extension/snapshot.js.
SHAREABLE_NAME = re.compile(r"^(q|query|search|searchterm|searchquery|searchtext|keyword|keywords|comment|comments|"
                            r"message|feedback|subject|title|description|note|notes|remark|remarks)$")


def value_shareable(f: dict) -> bool:
    ftype = str(f.get("type", "")).lower()
    if ftype in ("checkbox", "radio"):
        return True                      # only "checked" / "unchecked"
    if ftype == "search" or str(f.get("role", "")).lower() in ("searchbox", "search"):
        return True
    if ftype not in ("", "input", "text", "textarea", "contenteditable", "edit", "document"):
        return False
    return any(isinstance(f.get(k), str) and SHAREABLE_NAME.match(_joined(f[k]))
               for k in ("name", "id", "label", "automation_id"))


def redact_field(f: dict, counts: Counter) -> dict:
    out = {k: (redact_text(v, counts) if isinstance(v, str) else v) for k, v in f.items() if k != "value"}
    sensitive = field_is_sensitive(f)
    if sensitive or not value_shareable(f):
        out["sensitive"] = True           # not shared; also masked in screenshots
        out["withheld"] = "sensitive" if sensitive else "not_shared"
        out["has_value"] = bool(f.get("value"))
        if f.get("value"):
            counts["sensitive_field" if sensitive else "withheld_field"] += 1
        return out
    out["sensitive"] = False
    out["value"] = redact_text(f.get("value") if isinstance(f.get("value"), str) else "", counts)
    return out
