"""Risk-aware classification of personal and confidential data. Deterministic: regular expressions plus checksums.

Credentials come from the Assist redaction rules (`uri_assist.redact`, hardened over its review rounds), so URI has one
credential detector, not two. Everything else is detected here with checksums or context words so that ordinary text
(dates, order numbers, prices, version strings, ordinary names) stays readable:

  CREDENTIAL    SECRET    Assist text rules + labelled values ("password: x", "OTP 482913", "PIN is 1234")
  SECRET_LIKE   HIGH      unlabelled long random strings (Assist `long_secret`): maybe a key, maybe a hash
  GOV_ID        HIGH      Aadhaar (Verhoeff), PAN, US SSN, passport number next to "passport"
  FINANCIAL     HIGH      Luhn-valid cards, IBAN (mod 97), account numbers next to account wording
  CONTACT       MODERATE  e-mail, phone numbers
  ADDRESS       MODERATE  PIN / ZIP codes in context, street lines
  PERSON        MODERATE  only the protected terms the caller supplies (ordinary names are not sensitive by default)
  CONFIDENTIAL  LOW       document markers ("confidential", "do not share")
"""
from __future__ import annotations

import bisect
import re
from collections import Counter
from dataclasses import dataclass

from uri_assist import redact as _assist

CREDENTIAL, SECRET_LIKE, GOV_ID, FINANCIAL = "CREDENTIAL", "SECRET_LIKE", "GOV_ID", "FINANCIAL"
CONTACT, ADDRESS, PERSON, CONFIDENTIAL = "CONTACT", "ADDRESS", "PERSON", "CONFIDENTIAL"
CATEGORIES = (CREDENTIAL, SECRET_LIKE, GOV_ID, FINANCIAL, CONTACT, ADDRESS, PERSON, CONFIDENTIAL)
TIER = {CREDENTIAL: 4, SECRET_LIKE: 3, GOV_ID: 3, FINANCIAL: 3, CONTACT: 2, ADDRESS: 2, PERSON: 2, CONFIDENTIAL: 1}

# Assist count kinds that are not credentials: cards and Aadhaar are re-detected here with checksums, long_secret is
# SECRET_LIKE (a 40-hex git hash is not a password).
_ASSIST_NON_CREDENTIAL = {"card", "aadhaar", "long_secret"}


@dataclass(frozen=True)
class Finding:
    category: str
    start: int
    end: int
    rule: str

    @property
    def tier(self) -> int:
        return TIER[self.category]


@dataclass
class Classification:
    findings: list            # non-overlapping, sorted by start
    credential_kinds: Counter  # Assist kinds that are credentials (no spans: these are refused, never rewritten)

    def categories(self) -> Counter:
        c = Counter(f.category for f in self.findings)
        if self.credential_kinds:
            c[CREDENTIAL] += sum(self.credential_kinds.values())
        return c


# --- checksums -------------------------------------------------------------------------------------------------------
_VD = ((0, 1, 2, 3, 4, 5, 6, 7, 8, 9), (1, 2, 3, 4, 0, 6, 7, 8, 9, 5), (2, 3, 4, 0, 1, 7, 8, 9, 5, 6),
       (3, 4, 0, 1, 2, 8, 9, 5, 6, 7), (4, 0, 1, 2, 3, 9, 5, 6, 7, 8), (5, 9, 8, 7, 6, 0, 4, 3, 2, 1),
       (6, 5, 9, 8, 7, 1, 0, 4, 3, 2), (7, 6, 5, 9, 8, 2, 1, 0, 4, 3), (8, 7, 6, 5, 9, 3, 2, 1, 0, 4),
       (9, 8, 7, 6, 5, 4, 3, 2, 1, 0))
_VP = ((0, 1, 2, 3, 4, 5, 6, 7, 8, 9), (1, 5, 7, 6, 2, 8, 3, 0, 9, 4), (5, 8, 0, 3, 7, 9, 6, 1, 4, 2),
       (8, 9, 1, 6, 0, 4, 3, 5, 2, 7), (9, 4, 5, 3, 1, 2, 6, 8, 7, 0), (4, 2, 8, 6, 5, 7, 3, 9, 0, 1),
       (2, 7, 9, 3, 8, 0, 6, 4, 1, 5), (7, 0, 4, 6, 9, 1, 3, 2, 5, 8))


def verhoeff(digits: str) -> bool:
    c = 0
    for i, ch in enumerate(reversed(digits)):
        c = _VD[c][_VP[i % 8][ord(ch) - 48]]
    return c == 0


def iban_ok(raw: str) -> bool:
    s = raw.replace(" ", "").upper()
    if not 15 <= len(s) <= 34:
        return False
    s = s[4:] + s[:4]
    try:
        return int("".join(str(int(ch, 36)) for ch in s)) % 97 == 1
    except ValueError:
        return False


# --- detectors -------------------------------------------------------------------------------------------------------
# Labelled credential values written in prose. Digit codes (PIN/OTP/CVV) need 3-8 digits; word secrets need an explicit
# separator ("password: x", "password is x") so that "the password policy" stays readable. "PIN code"/"pincode" is
# postal and excluded.
_LABELLED = re.compile(
    r"(?i)\b(?:(?:otp|one[- ]time (?:password|code|pin)|verification code|security code|auth(?:entication)? code|"
    r"cvv|cvc|m?pin(?! ?code)|upi pin|atm pin)\b(?:\s*(?:is|was|=|:|-|#)\s*|\s+)(\d{3,8})\b|"
    r"(?:password|passwd|pwd|passcode|passphrase|api[ _-]?key|secret(?: key)?|access token|auth token|token)"
    r"\s*(?:is|was|=|:)\s*[\"']?([^\s\"',;]{4,})|"
    # "pass: x" / "pass=x" (never "pass is"), and a code word a few words before its digits ("the PIN for the locker
    # is 4821"). A bare "code" needs exactly 6 digits (OTP length) and no zip/postal/error/status/area word before it.
    r"\bpass\s*[:=]\s*[\"']?([^\s\"',;]{4,})|"
    r"\b(?:otp|m?pin(?! ?code)|passcode|cvv)\b[^.\n\d]{1,30}?\b(?:is|:)\s*(\d{3,8})\b|"
    r"(?<!zip )(?<!postal )(?<!error )(?<!status )(?<!area )(?<!country )\bcode\b\s*(?:is|was|:)?\s*(\d{6})(?!\d))")
# Aadhaar: written 4-4-4 it is flagged on its Verhoeff check; twelve run-together digits also need an Aadhaar/UID word
# nearby (Verhoeff passes one random 12-digit number in ten: order and tracking numbers stay readable).
_AADHAAR = re.compile(r"(?<![\d-])([2-9]\d{3})([ -]?)(\d{4})([ -]?)(\d{4})(?![\d-])")
_AADHAAR_CTX = re.compile(r"(?i)\b(?:aadhaa?r|uid|uidai|e-?kyc)\b[^\n]{0,25}$")
_PAN = re.compile(r"\b[A-Z]{3}[PCHFATBLJG][A-Z]\d{4}[A-Z]\b|(?i:\bpan\b\s*(?:no\.?|number|card)?\s*[:\-]?\s*)"
                  r"(?i:([a-z]{3}[pchfatbljg][a-z]\d{4}[a-z]))\b")
_SSN = re.compile(r"(?<![\d-])(?!000|666|9\d\d)\d{3}-(?!00)\d{2}-(?!0000)\d{4}(?![\d-])")
_PASSPORT = re.compile(r"(?i)\bpassport\s*(?:no\.?|number|num|#)?\s*[:\-]?\s*([A-Z][0-9]{7}|[A-Z0-9]{6,9}\d)\b")
_IBAN = re.compile(r"\b[A-Z]{2}\d{2}(?: ?[A-Z0-9]{4}){2,7}(?: ?[A-Z0-9]{1,4})?\b")
_ACCOUNT = re.compile(r"(?i)\b(?:a/c|acct|account|bank account)\s*(?:no\.?|number|num|#)?\s*[:\-]?\s*(\d[\d -]{6,20}\d)\b")
_EMAIL = re.compile(r"(?<![\w.+-])[A-Za-z0-9._%+-]+@[A-Za-z0-9-]+(?:\.[A-Za-z0-9-]+)*\.[A-Za-z]{2,}\b")
_PHONE = re.compile(r"(?<![\w+])\+\d{1,3}[ -]?\(?\d{1,5}\)?(?:[ -]?\d){5,11}(?![\w])|"
                    r"(?<![\w+-])0?[6-9]\d{4}[ -]\d{5}(?![\w-])|"                         # mobile, 5-5 grouped
                    r"(?<![\w-])\(0\d{2,4}\)\s?\d{3,4}[ -]?\d{4}(?![\w-])|"              # landline (080) 2345 6789
                    r"(?<![\w-])0\d{2,4}-\d{6,8}(?![\w-])|"                             # landline 080-23456789
                    r"(?<![\w-])1-\d{3}-\d{3}-\d{4}(?![\w-])|"                          # 1-800-555-0199
                    r"(?<![\w-])\(\d{3}\)\s?\d{3}[ .-]\d{4}(?![\w-])|(?<![\w.-])\d{3}[.-]\d{3}[.-]\d{4}(?![\w.-])")
# Ten run-together digits starting 6-9 are an Indian mobile only next to a phone word (else tracking numbers, amounts).
_MOBILE_BARE = re.compile(r"(?<![\w+-])0?[6-9]\d{9}(?![\w-])")
_PHONE_CTX = re.compile(r"(?i)\b(?:call|phone|ph|mob|mobile|cell|whatsapp|contact|tel|telephone|sms|text|reach|"
                        r"number|no)\b[^\n]{0,20}$")
# Luhn-valid IMEI/IMSI and hashes named as such are identifiers of devices and content, not cards or secrets.
_NOT_CARD_CTX = re.compile(r"(?i)\b(?:imei|imsi|meid|serial)\b[^\n]{0,12}$")
_NOT_SECRET_CTX = re.compile(r"(?i)\b(?:commit|sha-?\d*|md5|digest|hash|checksum|revision|rev|build)\b[^\n]{0,12}$")
_PINCODE = re.compile(r"(?i)\b(?:pin ?code|pincode|postal code|post ?code|zip(?: code)?)\s*[:\-]?\s*(\d{6}|\d{5})\b|"
                      r",\s*[A-Z][a-z]+(?: [A-Z][a-z]+)?\s*[-–]?\s*([1-9]\d{5})\b")
_STREET = re.compile(r"(?i)\b(?:flat|house|h\.? ?no\.?|plot|door|apt|apartment)\s*(?:no\.?|#)?\s*[\w/-]*\d[\w/-]*,?"
                     r"[^\n]{0,60}?\b(?:road|rd|street|st|nagar|lane|layout|cross|main|colony|sector|block|avenue|ave)\b\.?")
_CONFIDENTIAL = re.compile(r"(?i)\b(?:strictly\s+)?(?:private\s+(?:and|&)\s+)?confidential\b|"
                           r"\bdo not (?:share|forward|distribute|disclose)\b")
_LONG_SECRET = dict(_assist._TEXT_RULES)["long_secret"]


def _before(text: str, i: int) -> str:
    """The context window a context rule looks at: the 48 characters before a match (every context pattern needs fewer).
    A bounded window keeps classification linear in the text length."""
    return text[max(0, i - 48):i]


def _spans(text: str, protected_terms) -> list:
    out = []

    def add(cat, m, rule, group=0):
        g = group or next((i for i in range(1, (m.re.groups or 0) + 1) if m.group(i)), 0)
        out.append(Finding(cat, m.start(g), m.end(g), rule))

    for m in _LABELLED.finditer(text):
        add(CREDENTIAL, m, "labelled_value")
    for m in _AADHAAR.finditer(text):
        a, s1, b, s2, c = m.groups()
        grouped = bool(s1) and s1 == s2
        if verhoeff(a + b + c) and (grouped or _AADHAAR_CTX.search(_before(text, m.start()))):
            out.append(Finding(GOV_ID, m.start(), m.end(), "aadhaar"))
    for m in _PAN.finditer(text):
        add(GOV_ID, m, "pan", 1 if m.group(1) else 0)
    for m in _SSN.finditer(text):
        add(GOV_ID, m, "ssn", 0)
    for m in _PASSPORT.finditer(text):
        add(GOV_ID, m, "passport", 1)
    for m in _assist._CARD.finditer(text):
        d = re.sub(r"\D", "", m.group(0))
        if 13 <= len(d) <= 19 and _assist._luhn(d) and not _NOT_CARD_CTX.search(_before(text, m.start())):
            add(FINANCIAL, m, "card", 0)
    for m in _IBAN.finditer(text):
        if iban_ok(m.group(0)):
            add(FINANCIAL, m, "iban", 0)
    for m in _ACCOUNT.finditer(text):
        add(FINANCIAL, m, "account", 1)
    for m in _LONG_SECRET.finditer(text):
        if not _NOT_SECRET_CTX.search(_before(text, m.start())):
            add(SECRET_LIKE, m, "long_secret", 0)
    for m in _EMAIL.finditer(text):
        add(CONTACT, m, "email", 0)
    for m in _PHONE.finditer(text):
        add(CONTACT, m, "phone", 0)
    for m in _MOBILE_BARE.finditer(text):
        if _PHONE_CTX.search(_before(text, m.start())):
            add(CONTACT, m, "mobile", 0)
    for m in _PINCODE.finditer(text):
        add(ADDRESS, m, "pincode")
    for m in _STREET.finditer(text):
        add(ADDRESS, m, "street", 0)
    for term in protected_terms or ():
        if isinstance(term, str) and len(term.strip()) >= 2:
            rx = re.compile(r"(?i)(?<!\w)" + re.escape(term.strip()) + r"(?!\w)")
            for m in rx.finditer(text):
                add(PERSON, m, "protected_term", 0)
    for m in _CONFIDENTIAL.finditer(text):
        add(CONFIDENTIAL, m, "marker", 0)
    return out


def _resolve(findings: list) -> list:
    """Overlaps keep the highest tier, then the longest span, then the earliest."""
    starts, ends, kept = [], [], []                    # kept spans, sorted by start (non-overlapping)
    for f in sorted(findings, key=lambda f: (-f.tier, -(f.end - f.start), f.start)):
        if f.end <= f.start:
            continue
        i = bisect.bisect_left(starts, f.start)
        if (i < len(starts) and starts[i] < f.end) or (i > 0 and ends[i - 1] > f.start):
            continue
        starts.insert(i, f.start)
        ends.insert(i, f.end)
        kept.insert(i, f)
    return kept


def classify(text: str, protected_terms=()) -> Classification:
    if not isinstance(text, str):
        raise TypeError("text must be str")
    counts = Counter()
    _assist.redact_text(text, counts)
    cred = Counter({k: v for k, v in counts.items() if k not in _ASSIST_NON_CREDENTIAL and v})
    return Classification(_resolve(_spans(text, protected_terms)), cred)
