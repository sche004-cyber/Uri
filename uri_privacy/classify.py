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

import re
from collections import Counter
from dataclasses import dataclass

from uri_assist import redact as _assist

CREDENTIAL, SECRET_LIKE, GOV_ID, FINANCIAL = "CREDENTIAL", "SECRET_LIKE", "GOV_ID", "FINANCIAL"
CONTACT, ADDRESS, PERSON, CONFIDENTIAL = "CONTACT", "ADDRESS", "PERSON", "CONFIDENTIAL"
LONG_NUMBER = "LONG_NUMBER"
CATEGORIES = (CREDENTIAL, SECRET_LIKE, GOV_ID, FINANCIAL, LONG_NUMBER, CONTACT, ADDRESS, PERSON, CONFIDENTIAL)
TIER = {CREDENTIAL: 4, SECRET_LIKE: 3, GOV_ID: 3, FINANCIAL: 3, LONG_NUMBER: 3, CONTACT: 2, ADDRESS: 2, PERSON: 2,
        CONFIDENTIAL: 1}

# Assist count kinds that are not credentials: cards and Aadhaar are re-detected here with checksums, long_secret is
# SECRET_LIKE (a 40-hex git hash is not a password).
_ASSIST_NON_CREDENTIAL = {"card", "aadhaar", "long_secret"}


@dataclass(frozen=True)
class Finding:
    category: str             # the highest-tier category in the span
    start: int
    end: int
    rule: str
    members: tuple = ()       # every category merged into this span (review S1-02); empty = just `category`

    @property
    def tier(self) -> int:
        return TIER[self.category]

    @property
    def all_categories(self) -> tuple:
        return self.members or (self.category,)


@dataclass
class Classification:
    findings: list            # non-overlapping, sorted by start
    credential_kinds: Counter  # Assist kinds that are credentials (no spans: these are refused, never rewritten)
    residual_encoding: bool = False  # still percent/entity-encoded after _FOLD_PASSES decodes: refused externally
    decoded_only: bool = False      # a sensitive category appears only once encoded sequences are decoded (LDEC-005)

    def categories(self) -> Counter:
        c = Counter(cat for f in self.findings for cat in f.all_categories)
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
# The password label also matches "pass-word", "pass_word" and digit/symbol spellings ("P@ssword", "passw0rd", review
# FB4 R1-06).
_LABELLED = re.compile(
    r"(?i)\b(?:(?:otp|one[- ]time (?:password|code|pin)|verification code|security code|auth(?:entication)? code|"
    r"cvv|cvc|m?pin(?! ?code)|upi pin|atm pin)\b(?:\s*(?:is|was|=|:|-|#)\s*|\s+)(\d{3,8})\b|"
    r"(?:p[a@4][s5$]{2}[ _-]?w[o0]rd|passwd|pwd|passcode|passphrase|api[ _-]?key|secret(?: key)?|access token|auth token|token)"
    r"\s*(?:is|was|=|:)\s*[\"']?([^\s\"',;]{4,})|"
    # "pass: x" / "pass=x" (never "pass is"), and a code word a few words before its digits ("the PIN for the locker
    # is 4821"). A bare "code" needs exactly 6 digits (OTP length) and no zip/postal/error/status/area word before it.
    r"\b(?:pass|pw)\s*[:=]\s*[\"']?([^\s\"',;]{4,})|"
    # Word secrets written without "is"/":" ("password - X", "password -> X", "password X" after a line break) or a few
    # words before it ("the password for wifi is X", review FB1 R1-04). The value must then hold a digit or a symbol,
    # so ordinary prose ("the password policy is strict", "password field is required.") stays readable.
    r"\b(?:p[a@4][s5$]{2}[ _-]?w[o0]rd|passwd|pwd|passcode|passphrase)(?:'s)?(?: ?(?:->|=>|-|–|→) ?| )"
    r"[\"']?(?=[^\s\"',;]*[\d!@#$%^&*()_+=\[\]{}<>?/\\|~])([^\s\"',;]{4,})|"
    # The value before the label ("X is my password", "use X as the password", review FB4 R1-04). Only at the start
    # of a word, so the scan stays linear; the value needs a digit or symbol, as above.
    r"(?<![^\s\"'(])[\"']?(?=[^\s\"',;]*[\d!@#$%^&*()_+=\[\]{}<>?/\\|~])([^\s\"',;]{4,})[\"']? (?:is|was|as|=) "
    r"(?:(?:my|the|our|your|a|new|wifi|login) ){0,2}(?:p[a@4][s5$]{2}[ _-]?w[o0]rd|passwd|pwd|passcode|passphrase|pin)\b|"
    # "pw X" and, after a user/login word, "pass X" (review FB4 R1-04). The value holds a letter and a digit or
    # symbol, so "pass 2026 exams" and "pass COVID tests" stay readable.
    r"(?:\bpw|(?:user(?:name)?|login|id|wifi|account)\b[^\n]{0,30}?\bpass) "
    r"[\"']?(?=[^\s\"',;]*[A-Za-z])(?=[^\s\"',;]*[\d!@#$%^&*()_+=\[\]{}<>?/\\|~])([^\s\"',;]{4,})|"
    r"\b(?:p[a@4][s5$]{2}[ _-]?w[o0]rd|passwd|pwd|passcode|passphrase)\b[^.\n]{1,30}?\b(?:is|:) ?[\"']?"
    r"(?=[^\s\"',;]*[\d!@#$%^&*()_+=\[\]{}<>?/\\|~])([^\s\"',;]{4,})|"
    r"\b(?:otp|m?pin(?! ?code)|passcode|cvv)\b[^.\n\d]{1,30}?\b(?:is|:)\s*(\d{3,8})\b|"
    r"(?<!zip )(?<!postal )(?<!error )(?<!status )(?<!area )(?<!country )\bcode\b\s*(?:is|was|:)?\s*(\d{6})(?!\d))")
# Aadhaar: written 4-4-4 it is flagged on its Verhoeff check; twelve run-together digits also need an Aadhaar/UID word
# nearby (Verhoeff passes one random 12-digit number in ten: order and tracking numbers stay readable).
_AADHAAR = re.compile(r"(?<![\d.-])([2-9]\d{3})([ .-]?)(\d{4})([ .-]?)(\d{4})(?![\d-]|\.\d)")
_AADHAAR_CTX = re.compile(r"(?i)\b(?:aadhaa?r|uid|uidai|e-?kyc)\b[^\n]{0,25}$")
# Label idiom used below: "<label>[ no|number|#][ :|-] value" with single optional spaces. Folding collapses whitespace
# runs to one space, and no two optional space runs are adjacent, so these patterns cannot backtrack (review S1-04).
_LBL = r"(?: ?(?:no\.?|number|num|card|#))?(?: ?[:\-])? ?"
_PAN = re.compile(r"(?i)\b[a-z]{3}[pchfatbljg][a-z] ?\d{4} ?[a-z]\b|"           # also "ABCPE 1234 F"
                  # upper case with a single space anywhere: "ABCP E123 4F" (review FB4 R1-05)
                  r"\b[A-Z] ?[A-Z] ?[A-Z] ?[PCHFATBLJG] ?[A-Z] ?\d ?\d ?\d ?\d ?[A-Z]\b")
# Known API key prefixes followed by groups split by single spaces or dashes: "AKIA TWII 6XUU IX2C IXU3" (review FB4
# R1-05). The groups together hold at least 16 characters and two digits. A mixed letter/digit group or an
# uppercase-and-digit-only body is key-like; lower-case prose such as "sk-learn tutorial for 2026" stays readable.
_KEY_SPLIT = re.compile(r"(?<![A-Za-z0-9])(?:AKIA|ASIA|AIza|ghp_|gho_|ghs_|ghu_|github_pat_|glpat-|xox[abpr]-|"
                        r"sk-(?:proj-|ant-)?|sk_live_|sk_test_|rk_live_|tvly-)"
                        r"([A-Za-z0-9_]{0,40}(?:[ -][A-Za-z0-9_]{1,12}){1,15})(?![A-Za-z0-9_])")
_SSN_SEP = r" ?[-./,:()] ?|[^\w\n]|_"          # one standard (optionally spaced) or any single punctuation separator
_SSN = re.compile(r"(?<![\d-])(?!000|666|9\d\d)\d{3}-(?!00)\d{2}-(?!0000)\d{4}(?![\d-])|"
                  # labelled: "ssn 123456789", "ssn 123 45 6789", "ssn 123.45.6789" (review S1-05)
                  r"(?i:\b(?:ssn|social security(?: number| no\.?)?)\b" + _LBL + r"(?:is )?)"
                  r"((?!000|666|9\d\d)\d{3}(?:" + _SSN_SEP + r")?(?!00)\d{2}(?:" + _SSN_SEP + r")?(?!0000)\d{4})(?!\d)")
_SSN_BARE = re.compile(r"(?<![\d-])(?!000|666|9\d\d)\d{3}(?:" + _SSN_SEP + r")?(?!00)\d{2}(?:" + _SSN_SEP
                       + r")?(?!0000)\d{4}(?!\d)")
_SSN_CTX_AFTER = re.compile(r"(?i)^[^\n]{0,20}\b(?:ssn|social security)\b")
_PASSPORT = re.compile(r"(?i)\bpassport" + _LBL + r"(?:(?:no|number) )?(?:is )?([A-Z][0-9]{7}|[A-Z0-9]{6,9}\d)\b")
_IBAN = re.compile(r"(?i)\b[A-Z]{2}\d{2}(?: ?[A-Z0-9]{4}){2,7}(?: ?[A-Z0-9]{1,4})?\b")
_ACCOUNT = re.compile(r"(?i)\b(?:a/c|acct|account|bank account)" + _LBL + r"(\d(?:[ -]?\d){7,20})\b")
# Cards written with separators between groups (Assist covers unspaced dots and dashes; reviews S1-05,
# FB1 R1-03, R6-01, R7-01). Folding reduces whitespace on either side of separators to one space. The first group has four digits, so
# thousands groupings ("1,234,567,890") stay readable.
_CARD_SEP = r"[/_,:;|+~·–—•.-]"
_CARD_ALT = re.compile(r"\b\d{4}(?: ?" + _CARD_SEP + r"(?: ?" + _CARD_SEP + r")* ?\d{3,6}){2,4}\b")
_MARKS = "̀-ͯऀ-෿"           # Latin combining accents; Indic blocks (Devanagari .. Sinhala)
_EMAIL = re.compile(r"(?<![\w.+-])[A-Za-z0-9._%+-]+@[A-Za-z0-9-]+(?:\.[A-Za-z0-9-]+)*\.[A-Za-z]{2,}\b|"
                    # internationalised addresses: Unicode local part and domain (review FB3 R1-04)
                    # combining marks inside the local part (Indic vowel signs and viramas, Latin accents) are part of it
                    # (review FB4 R1-06: an address whose local part has a Devanagari vowel sign was cut at the sign)
                    r"(?<![\w.+\-" + _MARKS + r"])[^\W_](?:[\w.%+\-" + _MARKS + r"]*[^\W_])?"
                    r"@[^\W_][\w-]*(?:\.[\w-]+)*\.[^\W\d_]{2,}")
_PHONE = re.compile(r"(?<![\w+])\+\d{1,3}[ -]?\(?\d{1,5}\)?(?:[ -]?\d){5,11}(?![\w])|"
                    r"(?<![\w+-])0?[6-9]\d{4}[ .-]\d{5}(?![\w-])|"                        # mobile, 5-5 grouped
                    r"(?<![\w-])\(0\d{2,4}\)\s?\d{3,4}[ -]?\d{4}(?![\w-])|"              # landline (080) 2345 6789
                    r"(?<![\w-])0\d{2,4}-\d{6,8}(?![\w-])|"                             # landline 080-23456789
                    r"(?<![\w-])1-\d{3}-\d{3}-\d{4}(?![\w-])|"                          # 1-800-555-0199
                    r"(?<![\w-])\(\d{3}\)\s?\d{3}[ .-]\d{4}(?![\w-])|(?<![\w.-])\d{3}[.-]\d{3}[.-]\d{4}(?![\w.-])")
# Ten run-together digits starting 6-9 are an Indian mobile only next to a phone word (else tracking numbers, amounts).
_MOBILE_BARE = re.compile(r"(?<![\w+-])0?[6-9]\d{9}(?![\w-])")
# Spaced domestic phone layouts (review FB3 R1-04): 3-3-4 (US, Indian mobile), UK/Indian landline 0xx(x) xxx(x) xxxx.
_PHONE_SPACED = re.compile(r"(?<![\w+.\-/])(?:\(?\d{3}\)?[ .-]\d{3}[ .-]\d{4}|0\d{2,4} \d{3,4} \d{4})(?![\w.\-/])")
_PHONE_CTX_AFTER = re.compile(r"(?i)^[^\n]{0,20}\b(?:call|phone|mobile|cell|whatsapp|contact|tel|number|sms)\b")
_AADHAAR_CTX_AFTER = re.compile(r"(?i)^[^\n]{0,25}\b(?:aadhaa?r|uid|uidai)\b")
# Spaced one-time and card codes: "OTP is 4 8 2 9 1 3", "cvv: 1 2 3".
_SPACED_CODE = re.compile(r"(?i)\b(?:otp|cvv|cvc|pin|passcode)\b[^.\n\d]{0,20}?((?:\d ){2,7}\d)(?!\d)")
_PHONE_CTX = re.compile(r"(?i)\b(?:call|phone|ph|mob|mobile|cell|whatsapp|contact|tel|telephone|sms|text|reach|"
                        r"number|no)\b[^\n]{0,20}$")
# Luhn-valid IMEI/IMSI and hashes named as such are identifiers of devices and content, not cards or secrets.
_NOT_CARD_CTX = re.compile(r"(?i)\b(?:imei|imsi|meid|serial)\b[^\n]{0,12}$")
_NOT_SECRET_CTX = re.compile(r"(?i)\b(?:commit|sha-?\d*|md5|digest|hash|checksum|revision|rev|build)\b[^\n]{0,12}$")
_PINCODE = re.compile(r"(?i)\b(?:pin ?code|pincode|postal code|post ?code|zip(?: code)?)(?: ?[:\-])? ?(\d{6}|\d{5})\b|"
                      r", ?[A-Z][a-z]+(?: [A-Z][a-z]+)? ?[-–]? ?([1-9]\d{5})\b")
# Bounded unit token (review FB1 R1-05: an unbounded [\w/-]* before the lazy tail was super-linear).
_STREET = re.compile(r"(?i)\b(?:flat|house|h\.? ?no\.?|plot|door|apt|apartment) ?(?:no\.?|#)? ?[\w/-]{0,12}\d[\w/-]{0,12},?"
                     r"[^\n]{0,60}?\b(?:road|rd|street|st|nagar|lane|layout|cross|main|colony|sector|block|avenue|ave)\b\.?")
_CONFIDENTIAL = re.compile(r"(?i)\b(?:strictly\s+)?(?:private\s+(?:and|&)\s+)?confidential\b|"
                           r"\bdo not (?:share|forward|distribute|disclose)\b")
_LONG_SECRET = dict(_assist._TEXT_RULES)["long_secret"]
# LONG_NUMBER: the digit budget, owner decision LDEC-006 (2026-10-23). Text bound for a non-local destination may not
# carry 9 or more digits in one run, whatever the grouping, separators or line breaks. A run is digit groups joined by
# punctuation/whitespace gaps of any length, or gaps of 1-3 characters holding at most 2 letters. Digits that
# are part of a date, a clock time, an ISO-8601 timestamp or an IPv4 address (with port) do not count; they are written
# as such tokens, bounded so that a chain of colon or dot groups is exempt only when the whole chain is one token.
# Replaces LDEC-005's identifier shapes, which five reviews showed could be regrouped around (FB4 R1-01, R1-02).
DIGIT_BUDGET = 9
_DATE = (r"(?<![\d\-/.])(?:(?:19|20)\d{2}([-/.])(?:0?[1-9]|1[0-2])\1(?:0?[1-9]|[12]\d|3[01])|"
         r"(?:0?[1-9]|[12]\d|3[01])([-/.])(?:0?[1-9]|1[0-2])\2(?:19|20)\d{2}|(?:19|20)\d{6}(?=T))(?!\d|[-/.]\d)")
_TZ = r"(?:Z|[+-](?:0\d|1[0-4]):?[0-5]\d)?"
_CLOCK = r"(?<![\d:.])(?:[01]?\d|2[0-3]):[0-5]\d(?::[0-5]\d(?:[.,]\d{1,9})?)?" + _TZ + r"(?!\d|[:.]\d)"
_CLOCK_COMPACT = r"(?<=\dT)(?:[01]\d|2[0-3])[0-5]\d(?:[0-5]\d)?" + _TZ + r"(?!\d)"
_OCTET = r"(?:25[0-5]|2[0-4]\d|1\d\d|[1-9]?\d)"
_IPV4 = r"(?<![\d.])" + _OCTET + r"(?:\." + _OCTET + r"){3}(?::\d{1,5})?(?!\d|[:.]\d)"
_ISO_DAY = r"(?:19|20)\d{2}-(?:0[1-9]|1[0-2])-(?:0[1-9]|[12]\d|3[01])"
_DATE_RANGE = r"(?<![\d\-/.])" + _ISO_DAY + r"(?:/|--)" + _ISO_DAY + r"(?!\d|[-/.]\d)"    # ISO 8601 interval
_EXEMPT = re.compile("|".join((_DATE_RANGE, _DATE, _CLOCK, _CLOCK_COMPACT, _IPV4)))
_DIGITS = re.compile(r"\d+")


def _exempt_mask(text: str) -> bytearray:
    exempt = bytearray(len(text))
    for m in _EXEMPT.finditer(text):
        exempt[m.start():m.end()] = b"\x01" * (m.end() - m.start())
    return exempt


def _only_exempt_digits(text: str, exempt, s: int, e: int) -> bool:
    return all(exempt[i] for i in range(s, e) if text[i].isdigit())


def _long_number_spans(text: str, exempt=None):
    """(start, end) of every run over the digit budget, from its first to its last counted digit group. Linear."""
    exempt = _exempt_mask(text) if exempt is None else exempt
    out, run, prev_end = [], [], -1

    def close():
        counted = [(s, e) for s, e in run if not exempt[s]]
        if sum(e - s for s, e in counted) >= DIGIT_BUDGET:
            out.append((counted[0][0], counted[-1][1]))
    for m in _DIGITS.finditer(text):
        gap = text[prev_end:m.start()] if run else ""
        if run and not (all(not c.isalnum() for c in gap) or
                        (len(gap) <= 3 and sum(c.isalpha() for c in gap) <= 2)):
            close()
            run = []
        run.append((m.start(), m.end()))
        prev_end = m.end()
    if run:
        close()
    return out
# A card written as one run of digits with letters right after it ("4111111111111111exp", review R8-01).
_CARD_RUN = re.compile(r"(?<![\d.,])\d{13,19}(?!\d)")         # not a decimal fraction ("2.718281828459045")
# Digit groups joined by single standard separators, as a whole run ("234.567.890.124", "4,111,111,111,111,111").
_STD_SEP_PAT = r"(?: ?[-./,:()] ?| ?\) ?\(? ?| )"
_TIME_LIST = re.compile(r"\d{1,2}:\d{2}(?::\d{2})?(?:(?: ?[-,/] ?| )\d{1,2}:\d{2}(?::\d{2})?)*")
_STD_RUN = re.compile(r"(?<![\d.,])\d{1,6}(?:" + _STD_SEP_PAT + r"\d{1,6}){2,}(?![\d])")


def _before(text: str, i: int) -> str:
    """The context window a context rule looks at: the 48 characters before a match (every context pattern needs fewer).
    A bounded window keeps classification linear in the text length."""
    return text[max(0, i - 48):i]


def _spans(text: str, protected_terms) -> list:
    out = []

    def add(cat, m, rule, group=None):
        # group None: the first non-empty capture group (labelled patterns); 0: the whole match. Treating 0 as "auto"
        # redacted a separator group instead of the digits (coordinator finding C4-01).
        g = group if group is not None else next((i for i in range(1, (m.re.groups or 0) + 1) if m.group(i)), 0)
        out.append(Finding(cat, m.start(g), m.end(g), rule))

    for m in _LABELLED.finditer(text):
        add(CREDENTIAL, m, "labelled_value")
    for m in _AADHAAR.finditer(text):
        a, s1, b, s2, c = m.groups()
        grouped = bool(s1) and s1 == s2
        if verhoeff(a + b + c) and (grouped or _AADHAAR_CTX.search(_before(text, m.start()))
                                    or _AADHAAR_CTX_AFTER.search(text[m.end():m.end() + 30])):
            out.append(Finding(GOV_ID, m.start(), m.end(), "aadhaar"))
    for m in _PAN.finditer(text):
        add(GOV_ID, m, "pan", 0)
    for m in _SSN.finditer(text):
        add(GOV_ID, m, "ssn", 1 if m.group(1) else 0)
    for m in _SSN_BARE.finditer(text):
        if _SSN_CTX_AFTER.search(text[m.end():m.end() + 30]):
            add(GOV_ID, m, "ssn_label_after", 0)
    for m in _PASSPORT.finditer(text):
        add(GOV_ID, m, "passport", 1)
    for m in _assist._CARD.finditer(text):
        if _NOT_CARD_CTX.search(_before(text, m.start())) or re.fullmatch(r"\d+\.\d+", m.group(0)):
            continue                                    # IMEI context, or one decimal number ("2.718281828459045")
        d = re.sub(r"\D", "", m.group(0))
        if 13 <= len(d) <= 19 and _assist._luhn(d):
            add(FINANCIAL, m, "card", 0)
            continue
        # The greedy match can swallow digits next to a card ("4111 1111 1111 1111 9", review R2-01). Try the runs of
        # whole digit groups inside it; only group-aligned windows, so a long ungrouped number is not searched for a
        # Luhn-valid window by chance.
        groups = [(g.start(), g.end()) for g in re.finditer(r"\d+", m.group(0))]
        hit = None
        for i in range(len(groups)):
            n = 0
            for j in range(i, len(groups)):
                n += groups[j][1] - groups[j][0]
                if n > 19:
                    break
                if n >= 13 and j > i:
                    s0, e0 = m.start() + groups[i][0], m.start() + groups[j][1]
                    if _assist._luhn(re.sub(r"\D", "", text[s0:e0])):
                        hit = (s0, e0)
            if hit:
                break
        if hit:
            out.append(Finding(FINANCIAL, hit[0], hit[1], "card"))
    for m in _CARD_ALT.finditer(text):
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
        if _PHONE_CTX.search(_before(text, m.start())) or _PHONE_CTX_AFTER.search(text[m.end():m.end() + 30]):
            add(CONTACT, m, "mobile", 0)
    for m in _PHONE_SPACED.finditer(text):
        add(CONTACT, m, "phone_spaced", 0)
    for m in _SPACED_CODE.finditer(text):
        add(CREDENTIAL, m, "spaced_code", 1)
    for m in _KEY_SPLIT.finditer(text):
        # Trailing space-separated lower-case words are prose after the key ("... IXU3 leaked"), not key groups.
        g = re.sub(r"(?: [a-z]{4,})+$", "", m.group(1))
        alnum = re.sub(r"[ -]", "", g)
        if (len(alnum) >= 16 and sum(c.isdigit() for c in alnum) >= 2
                and (any(re.search(r"[A-Za-z]", p) and re.search(r"\d", p) for p in re.split(r"[ -]", g))
                     or (re.search(r"[A-Z]", g) and re.fullmatch(r"[A-Z0-9 -]+", g)))):
            out.append(Finding(CREDENTIAL, m.start(), m.start(1) + len(g), "split_key"))
    for m in _PINCODE.finditer(text):
        add(ADDRESS, m, "pincode")
    for m in _STREET.finditer(text):
        add(ADDRESS, m, "street", 0)
    for term in protected_terms or ():
        if isinstance(term, str) and term.strip():
            rx = re.compile(r"(?i)(?<!\w)" + re.escape(term.strip()) + r"(?!\w)")
            for m in rx.finditer(text):
                add(PERSON, m, "protected_term", 0)
    for m in _CONFIDENTIAL.finditer(text):
        add(CONFIDENTIAL, m, "marker", 0)
    for m in _CARD_RUN.finditer(text):
        if _assist._luhn(m.group(0)) and not _NOT_CARD_CTX.search(_before(text, m.start())):
            add(FINANCIAL, m, "card_run", 0)
    for m in _STD_RUN.finditer(text):
        if _TIME_LIST.fullmatch(m.group(0)):
            continue
        d = re.sub(r"\D", "", m.group(0))
        if len(d) == 12 and d[0] in "23456789" and verhoeff(d) and (
                _AADHAAR_CTX.search(_before(text, m.start())) or _AADHAAR_CTX_AFTER.search(text[m.end():m.end() + 30])):
            add(GOV_ID, m, "aadhaar_regrouped", 0)
        elif 13 <= len(d) <= 19 and _assist._luhn(d) and not _NOT_CARD_CTX.search(_before(text, m.start())):
            add(FINANCIAL, m, "card_regrouped", 0)
    # LONG_NUMBER is the catch-all after every specific rule: it is added only where no specific finding already covers
    # the whole run, so a grant for the specific category (an Aadhaar under GOV_ID) still applies to it.
    exempt = _exempt_mask(text)
    out = [f for f in out if not (f.rule in ("card", "card_regrouped", "aadhaar_regrouped", "card_run")
                                  and _only_exempt_digits(text, exempt, f.start, f.end))]
    import bisect
    spec = sorted((f.start, f.end) for f in out)
    starts, reach, best = [s for s, _ in spec], [], -1
    for _, e in spec:                         # reach[i] = furthest end of any finding starting at or before starts[i]
        best = max(best, e)
        reach.append(best)

    def covered(a, b):
        i = bisect.bisect_right(starts, a) - 1
        return i >= 0 and reach[i] >= b
    for s, e in _long_number_spans(text, exempt):
        if not covered(s, e):
            out.append(Finding(LONG_NUMBER, s, e, "digit_budget"))
    return out


def _resolve(findings: list) -> list:
    """Overlapping findings become ONE finding covering their union, with the highest tier's category (the earliest
    on a tie). Keeping only one of two partly overlapping spans would send the other's uncovered part (review R2)."""
    out = []
    for f in sorted((f for f in findings if f.end > f.start), key=lambda f: (f.start, -f.end)):
        if out and f.start < out[-1].end:
            k = out[-1]
            cat, rule = (f.category, f.rule) if f.tier > k.tier else (k.category, k.rule)
            members = tuple(dict.fromkeys(k.all_categories + f.all_categories))
            out[-1] = Finding(cat, k.start, max(k.end, f.end), rule, members)
        else:
            out.append(f)
    return out


# --- folding (review R1-01 / R2-01 / R2-02) ---------------------------------------------------------------------------
# Detectors are written for plain text. Before detection the text is folded: percent-encoded and HTML-entity sequences
# are decoded, every character is NFKC-normalized, format controls (zero-width spaces, joiners, bidi marks) are removed,
# every Unicode decimal digit becomes an ASCII digit and characters that look like ASCII letters or digits
# (`uri_web.confusables_ascii`, Unicode UTS #39 data) become those letters. Two passes, so a doubly encoded value
# ("%253A") is decoded too. Each folded character keeps the [start, end) range of the original characters it came from,
# so a finding in the folded text maps back to an exact original span: the original text is what gets rewritten.
# Whitespace runs and tabs/newlines fold to one space as well, so a value spread over several spaces or lines is found
# (review S1-01 / S1-05) and no detector sees a long run of spaces (S1-04).
_SPECIAL = re.compile(r"(?:%[0-9A-Fa-f]{2})+|&(?:#[0-9]{1,7}|#[xX][0-9A-Fa-f]{1,6}|[A-Za-z][A-Za-z0-9]{1,31});"
                      r"|[^\x00-\x7f]|\s{2,}|[\t\n\r\f\v]|[\x00-\x08\x0e-\x1f\x7f]")
_FOLD_PASSES = 4          # deeper encoding is reported (Classification.residual_encoding) and refused externally
_ENCODED = re.compile(r"%[0-9A-Fa-f]{2}|&(?:#[0-9]{1,7}|#[xX][0-9A-Fa-f]{1,6}|[A-Za-z][A-Za-z0-9]{1,31});")
_NEEDS_READINGS = re.compile(r"[^\x00-\x7f]|%[0-9A-Fa-f]{2}|&[#A-Za-z]|[\x00-\x08\x0e-\x1f\x7f]")
# Default-ignorable code points outside category Cf (Unicode DerivedCoreProperties): combining grapheme joiner, Hangul
# fillers, Khmer inherent vowels, Mongolian and other variation selectors (review FB1 R1-01).
_DI_RANGES = ((0x034F, 0x034F), (0x115F, 0x1160), (0x17B4, 0x17B5), (0x180B, 0x180F), (0x3164, 0x3164),
              (0xFE00, 0xFE0F), (0xFFA0, 0xFFA0), (0x1BCA0, 0x1BCA3), (0xE0100, 0xE01EF))


_ASCII_CONTROL = re.compile(r"[\x00-\x08\x0e-\x1f\x7f]")
# Characters that render as blank but are not whitespace (review FB2 R1-01: U+2800 Braille blank).
_BLANKS = frozenset({0x2800, 0x3164, 0x115F, 0x1160, 0xFFA0, 0x2063})


def _invisible(ch: str) -> bool:
    """True for anything a reader cannot see that is not ordinary whitespace: format controls (Cf), control characters
    (Cc other than tab/newline/CR/FF/VT), private-use (Co) and unassigned (Cn) code points, default-ignorables and
    blank-rendering characters. Reviews R1-01, FB1 R1-01 and FB2 R1-01 each found one more of these categories, so the
    rule is stated by category, not as a list of examples."""
    import unicodedata
    if ch.isspace():
        return False
    if unicodedata.category(ch) in ("Cf", "Cc", "Co", "Cn"):
        return True
    o = ord(ch)
    return o in _BLANKS or any(a <= o <= b for a, b in _DI_RANGES)


# --- egress form and disguise signals (owner decision LDEC-005, 2026-10-23: "refuse on doubt") ------------------------
# Reading through disguises did not converge (14 rejecting review rounds). For a non-local destination the gateway now
# sends a canonical form and REFUSES text that carries a disguise signal, instead of trying to see through it.
DOUBT_INVISIBLE = "INVISIBLE_IN_ASCII_OR_DIGITS"
DOUBT_SEPARATOR = "UNUSUAL_DIGIT_SEPARATOR"
DOUBT_ENCODED = "SENSITIVE_ONLY_WHEN_DECODED"
# Invisible characters that shape emoji and scripts (ZWJ, ZWNJ, VS15, VS16) are kept when neither neighbour is an
# ASCII letter or any digit: emoji sequences, Persian/Indic shaping (review FB3 R1-06).
_SHAPING = frozenset({0x200C, 0x200D, 0xFE0E, 0xFE0F})


def _punct_ascii(ch: str):
    """ASCII stand-in for a punctuation look-alike (review FB3 R1-03), by Unicode name, so the whole class is covered:
    hyphens, dashes and minus signs, colon and ratio signs, full stops, commercial at, slashes, low lines, quotes."""
    import unicodedata
    if ch.isascii():
        return None
    cat = unicodedata.category(ch)
    if not (cat.startswith("P") or cat.startswith("S") or cat == "Lm"):
        return None
    name = unicodedata.name(ch, "")
    for words, rep in ((("HYPHEN", "DASH", "MINUS"), "-"), (("COLON", "RATIO"), ":"), (("FULL STOP",), "."),
                       (("COMMERCIAL AT",), "@"), (("SOLIDUS", "SLASH"), "/"), (("LOW LINE",), "_"),
                       (("QUOTATION MARK",), '"'), (("APOSTROPHE", "SINGLE QUOTATION", "PRIME"), "'"),
                       (("SEMICOLON",), ";"), (("COMMA",), ",")):
        if any(w in name for w in words) and "MULTIPLICATION" not in name:
            return rep
    return None


# Digit groups joined by anything other than one standard separator (space, -, ., /, ',', ':', optionally padded by one
# space each side), or by single letters, that hold 10 or more digits: "4111****1111", "2345__6789__0124",
# "4111;1111", "4111%1111", "2345 - - 6789", "2345x6789x0124" (reviews R3..R8, FB3 R1-02).
_SEP_RUN = re.compile(r"\d+(?:(?:[^\w\n]|_){1,6}\d+)+")            # separators: punctuation, spaces, underscores
_LETTER_RUN = re.compile(r"(?<![^\W\d_])\d{2,}(?:[^\W\d_]{1,4}\d{2,}){2,}")      # 2345x6789x0124, any script
_STD_SEP = re.compile(_STD_SEP_PAT)


# ISO-8601 date-times are a standard format, not a disguise ("2026-10-09T10:00:00+05:30": scheduler metadata).
# 32+ hex characters: MD5/SHA digests. A value disguised by the letter rule (gaps of at most 4 letters) is at most
# 16 + 3x4 = 28 characters for a card and 20 for an Aadhaar, so this exemption cannot hide either.
_HEX_TOKEN = re.compile(r"(?<![0-9A-Za-z])[0-9a-fA-F]{32,}(?![0-9A-Za-z])")
_ISO_DATETIME = re.compile(r"\d{4}-\d{2}-\d{2}[T ]\d{2}:\d{2}(?::\d{2}(?:\.\d{1,9})?)?(?:Z|[+-]\d{2}:?\d{2})?")


def _unusual_digit_separators(text: str) -> bool:
    text = _ISO_DATETIME.sub(" ", text)
    for m in _SEP_RUN.finditer(text):
        run = m.group(0)
        if sum(c.isdigit() for c in run) < 9:          # 9: an SSN is the shortest identifier this covers
            continue
        if any(not _STD_SEP.fullmatch(s) for s in re.split(r"\d+", run)[1:-1]):
            return True
    # Digest-like hex tokens are not letter-separated digits (see _HEX_TOKEN for why 32 is safe).
    text = _HEX_TOKEN.sub(" ", text)
    return any(sum(c.isdigit() for c in m.group(0)) >= 9 for m in _LETTER_RUN.finditer(text))


def egress_form(text: str):
    """(text to send, disguise signals). The text to send is NFKC with punctuation look-alikes as ASCII and line or
    paragraph separators as newlines; invisible characters are removed except emoji/script shaping between non-ASCII
    characters. The gateway classifies, rewrites and re-checks exactly this string. A signal means refuse."""
    import unicodedata
    signals = set()
    if text.isascii() and not _ASCII_CONTROL.search(text):
        if _unusual_digit_separators(text):
            signals.add(DOUBT_SEPARATOR)
        return text, signals
    src = unicodedata.normalize("NFKC", text)
    out = []
    skip = 0
    for i, ch in enumerate(src):
        if skip:
            skip -= 1
            continue
        cat = unicodedata.category(ch)
        prev = src[i - 1] if i else ""
        nxt = src[i + 1] if i + 1 < len(src) else ""

        def ascii_or_digit(c):
            return bool(c) and ((c.isascii() and c.isalnum()) or unicodedata.category(c) == "Nd")
        if cat in ("Zl", "Zp"):
            out.append("\n")
            continue
        if ch in "0123456789#*" and src[i + 1:i + 3] in ("\ufe0f\u20e3", "\u20e3"):
            keycap = 3 if src[i + 1:i + 3] == "\ufe0f\u20e3" else 2       # RGI keycap 1\ufe0f\u20e3 (FB4 R1-08)
            out.append(src[i:i + keycap])
            skip = keycap - 1
            continue
        mark_off_letter = cat in ("Mn", "Me") and not (prev and unicodedata.category(prev)[0] in "LM")
        if _invisible(ch) or (cat in ("Mn", "Me") and ascii_or_digit(prev)) or mark_off_letter:
            if ord(ch) in _SHAPING and not ascii_or_digit(prev) and not ascii_or_digit(nxt):
                out.append(ch)                     # emoji / script shaping, kept as written
            elif cat in ("Mn", "Me") and not ascii_or_digit(prev) and not mark_off_letter:
                out.append(ch)
            else:
                signals.add(DOUBT_INVISIBLE)       # removed from what is sent, and the egress is refused
            continue
        rep = _punct_ascii(ch)
        out.append(rep if rep is not None else ch)
    sent = "".join(out)
    if _unusual_digit_separators(sent):
        signals.add(DOUBT_SEPARATOR)
    return sent, signals


def canonical(text: str) -> str:
    """The text a non-local destination receives (see egress_form)."""
    return egress_form(text)[0]


def _confusables():
    try:
        from uri_web.confusables_ascii import CONFUSABLE_ASCII
        return CONFUSABLE_ASCII
    except Exception:                          # noqa: BLE001 - folding still covers NFKC, digits and format controls
        return {}


_CONF = _confusables()


def _fold_char(ch: str, cf: str = "", on_ascii: bool = False) -> str:
    """One character, folded. `cf` replaces invisible characters; a combining mark on a plain ASCII letter or digit only
    disguises it ("p\\u0336assword", "41\\u03011 ...") and is treated the same way; marks on other scripts stay
    (Devanagari vowel signs and viramas are combining marks too)."""
    import unicodedata
    if _invisible(ch):
        return cf
    if on_ascii and unicodedata.category(ch) in ("Mn", "Me"):
        return cf
    out = []
    for c in unicodedata.normalize("NFKC", ch):
        d = unicodedata.decimal(c, None)
        if d is not None:
            out.append(str(d))
        elif _invisible(c):
            out.append(cf)
        elif c.isascii():
            out.append(c)
        else:
            # A precomposed Latin letter whose decomposition is an ASCII letter plus marks is read as that letter, so
            # "pássword:" is a label (review FB4 R1-03: NFKC composes "a" + U+0301 before any mark check sees it).
            base = unicodedata.normalize("NFD", c)
            if base[0].isascii() and base[0].isalpha() and all(unicodedata.category(x) == "Mn" for x in base[1:]):
                out.append(base[0])
            else:
                out.append(_CONF.get(c, c))
    return "".join(out)


def _fold_once(text: str, starts: list, ends: list, cf: str = "", encoded: str = "decode"):
    """`encoded`: "decode" decodes percent and HTML-entity sequences; "space" reads each one as a separator."""
    import html
    chars, S, E, pos = [], [], [], 0
    on_ascii = False                  # the last visible character emitted is an ASCII letter or digit

    def emit(piece, s, e):
        nonlocal on_ascii
        if piece:
            chars.append(piece)
            S.extend([s] * len(piece) if isinstance(s, int) else s)
            E.extend([e] * len(piece) if isinstance(e, int) else e)
            last = piece.rstrip()[-1:] if cf == " " else piece[-1:]
            if last:
                on_ascii = last.isascii() and last.isalnum()

    for m in _SPECIAL.finditer(text):
        if m.start() > pos:
            emit(text[pos:m.start()], starts[pos:m.start()], ends[pos:m.start()])
        tok = m.group(0)
        s, e = starts[m.start()], ends[m.end() - 1]
        if tok.isspace():
            emit(" ", s, e)
        elif tok[0] in "%&":
            if encoded == "literal":
                emit(tok, starts[m.start():m.end()], ends[m.start():m.end()])
            elif encoded == "space":
                emit(" ", s, e)
            else:
                dec = (bytes.fromhex(tok.replace("%", "")).decode("utf-8", "replace") if tok[0] == "%"
                       else html.unescape(tok))
                if dec != tok:
                    dec = "".join(c if c.isascii() else _fold_char(c, cf, on_ascii) for c in dec)
                emit(dec, s, e)
        else:
            dec = _fold_char(tok, cf, on_ascii)
            if dec:
                emit(dec, s, e)
        pos = m.end()
    if pos < len(text):
        emit(text[pos:], starts[pos:], ends[pos:])
    return "".join(chars), S, E


def fold(text: str, cf: str = "", encoded: str = "decode"):
    """(folded text, start map, end map): folded[i] came from text[start[i]:end[i]]. `cf` replaces invisible
    characters (and marks on ASCII); `encoded` says how percent / HTML-entity sequences are read."""
    starts, ends = list(range(len(text))), list(range(1, len(text) + 1))
    for _ in range(_FOLD_PASSES):
        if not _SPECIAL.search(text):
            break
        text, starts, ends = _fold_once(text, starts, ends, cf, encoded)
    return text, starts, ends


def _still_encoded(text: str) -> bool:
    import html
    for m in _ENCODED.finditer(text):
        tok = m.group(0)
        if tok[0] == "%" or html.unescape(tok) != tok:
            return True
    return False


def classify(text: str, protected_terms=()) -> Classification:
    if not isinstance(text, str):
        raise TypeError("text must be str")
    terms = [fold(t)[0] for t in protected_terms or () if isinstance(t, str)]
    # An invisible character or an encoded sequence can join two pieces ("4111<ZWSP>1111") or separate two values
    # ("...1111<ZWSP>9", "...1111%E2%80%8B9"). Every text that holds non-ASCII characters or encoded sequences is read
    # three ways - joined, separated, and with each encoded sequence as a separator - and the findings of all readings
    # are combined (reviews R2-01, FB1 R1-01/R1-02). Deciding this on the raw text missed encoded controls.
    readings = [("", "decode")]
    if _NEEDS_READINGS.search(text):
        readings += [(" ", "decode"), (" ", "space"), ("", "literal")]
    literal_cats, decoded_cats = set(), set()
    found, cred, residual = [], Counter(), False
    for cf, enc in readings:
        folded, S, E = fold(text, cf, enc)
        if enc == "decode" and _still_encoded(folded):
            residual = True
        counts = Counter()
        _assist.redact_text(folded, counts)
        for k, v in counts.items():
            if k not in _ASSIST_NON_CREDENTIAL and v:
                cred[k] = max(cred[k], v)
        spans = _resolve(_spans(folded, terms))
        cats_here = {c for f in spans for c in f.all_categories} | ({CREDENTIAL} if any(
            k not in _ASSIST_NON_CREDENTIAL and v for k, v in counts.items()) else set())
        (literal_cats if enc in ("literal", "space") else decoded_cats).update(cats_here)
        if folded is not text:
            spans = [Finding(f.category, S[f.start], E[f.end - 1], f.rule, f.members) for f in spans]
        found.extend(spans)
    decoded_only = bool(decoded_cats - literal_cats) and len(readings) > 1 and _ENCODED.search(text) is not None
    return Classification(_resolve(found), cred, residual, decoded_only)
