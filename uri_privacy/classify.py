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
CATEGORIES = (CREDENTIAL, SECRET_LIKE, GOV_ID, FINANCIAL, CONTACT, ADDRESS, PERSON, CONFIDENTIAL)
TIER = {CREDENTIAL: 4, SECRET_LIKE: 3, GOV_ID: 3, FINANCIAL: 3, CONTACT: 2, ADDRESS: 2, PERSON: 2, CONFIDENTIAL: 1}

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
_LABELLED = re.compile(
    r"(?i)\b(?:(?:otp|one[- ]time (?:password|code|pin)|verification code|security code|auth(?:entication)? code|"
    r"cvv|cvc|m?pin(?! ?code)|upi pin|atm pin)\b(?:\s*(?:is|was|=|:|-|#)\s*|\s+)(\d{3,8})\b|"
    r"(?:password|passwd|pwd|passcode|passphrase|api[ _-]?key|secret(?: key)?|access token|auth token|token)"
    r"\s*(?:is|was|=|:)\s*[\"']?([^\s\"',;]{4,})|"
    # "pass: x" / "pass=x" (never "pass is"), and a code word a few words before its digits ("the PIN for the locker
    # is 4821"). A bare "code" needs exactly 6 digits (OTP length) and no zip/postal/error/status/area word before it.
    r"\bpass\s*[:=]\s*[\"']?([^\s\"',;]{4,})|"
    # Word secrets written without "is"/":" ("password - X", "password -> X", "password X" after a line break) or a few
    # words before it ("the password for wifi is X", review FB1 R1-04). The value must then hold a digit or a symbol,
    # so ordinary prose ("the password policy is strict", "password field is required.") stays readable.
    r"\b(?:password|passwd|pwd|passcode|passphrase)(?: ?(?:->|=>|-|–|→) ?| )"
    r"[\"']?(?=[^\s\"',;]*[\d!@#$%^&*()_+=\[\]{}<>?/\\|~])([^\s\"',;]{4,})|"
    r"\b(?:password|passwd|pwd|passcode|passphrase)\b[^.\n]{1,30}?\b(?:is|:) ?[\"']?"
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
_PAN = re.compile(r"(?i)\b[a-z]{3}[pchfatbljg][a-z]\d{4}[a-z]\b")
_SSN = re.compile(r"(?<![\d-])(?!000|666|9\d\d)\d{3}-(?!00)\d{2}-(?!0000)\d{4}(?![\d-])|"
                  # labelled: "ssn 123456789", "ssn 123 45 6789", "ssn 123.45.6789" (review S1-05)
                  r"(?i:\b(?:ssn|social security(?: number| no\.?)?)\b" + _LBL + r"(?:is )?)"
                  r"((?!000|666|9\d\d)\d{3}[ ./\u2013\u2014-]?(?!00)\d{2}[ ./\u2013\u2014-]?(?!0000)\d{4})(?!\d)")
_PASSPORT = re.compile(r"(?i)\bpassport" + _LBL + r"([A-Z][0-9]{7}|[A-Z0-9]{6,9}\d)\b")
_IBAN = re.compile(r"(?i)\b[A-Z]{2}\d{2}(?: ?[A-Z0-9]{4}){2,7}(?: ?[A-Z0-9]{1,4})?\b")
_ACCOUNT = re.compile(r"(?i)\b(?:a/c|acct|account|bank account)" + _LBL + r"(\d(?:[ -]?\d){7,20})\b")
# Cards written with other separators between groups (the Assist rule covers spaces, dots and dashes; reviews S1-05,
# FB1 R1-03). The first group must have four digits, so thousands groupings ("1,234,567,890") stay readable.
_CARD_ALT = re.compile(r"\b\d{4}(?:[/_,:;|+~·–—•]\d{3,6}){2,4}\b")
_EMAIL = re.compile(r"(?<![\w.+-])[A-Za-z0-9._%+-]+@[A-Za-z0-9-]+(?:\.[A-Za-z0-9-]+)*\.[A-Za-z]{2,}\b")
_PHONE = re.compile(r"(?<![\w+])\+\d{1,3}[ -]?\(?\d{1,5}\)?(?:[ -]?\d){5,11}(?![\w])|"
                    r"(?<![\w+-])0?[6-9]\d{4}[ .-]\d{5}(?![\w-])|"                        # mobile, 5-5 grouped
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
_PINCODE = re.compile(r"(?i)\b(?:pin ?code|pincode|postal code|post ?code|zip(?: code)?)(?: ?[:\-])? ?(\d{6}|\d{5})\b|"
                      r", ?[A-Z][a-z]+(?: [A-Z][a-z]+)? ?[-–]? ?([1-9]\d{5})\b")
# Bounded unit token (review FB1 R1-05: an unbounded [\w/-]* before the lazy tail was super-linear).
_STREET = re.compile(r"(?i)\b(?:flat|house|h\.? ?no\.?|plot|door|apt|apartment) ?(?:no\.?|#)? ?[\w/-]{0,12}\d[\w/-]{0,12},?"
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
        add(GOV_ID, m, "pan", 0)
    for m in _SSN.finditer(text):
        add(GOV_ID, m, "ssn", 1 if m.group(1) else 0)
    for m in _PASSPORT.finditer(text):
        add(GOV_ID, m, "passport", 1)
    for m in _assist._CARD.finditer(text):
        if _NOT_CARD_CTX.search(_before(text, m.start())):
            continue
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
        if _PHONE_CTX.search(_before(text, m.start())):
            add(CONTACT, m, "mobile", 0)
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
                      r"|[^\x00-\x7f]|\s{2,}|[\t\n\r\f\v]")
_FOLD_PASSES = 4          # deeper encoding is reported (Classification.residual_encoding) and refused externally
_ENCODED = re.compile(r"%[0-9A-Fa-f]{2}|&(?:#[0-9]{1,7}|#[xX][0-9A-Fa-f]{1,6}|[A-Za-z][A-Za-z0-9]{1,31});")
_NEEDS_READINGS = re.compile(r"[^\x00-\x7f]|%[0-9A-Fa-f]{2}|&[#A-Za-z]")
# Default-ignorable code points outside category Cf (Unicode DerivedCoreProperties): combining grapheme joiner, Hangul
# fillers, Khmer inherent vowels, Mongolian and other variation selectors (review FB1 R1-01).
_DI_RANGES = ((0x034F, 0x034F), (0x115F, 0x1160), (0x17B4, 0x17B5), (0x180B, 0x180F), (0x3164, 0x3164),
              (0xFE00, 0xFE0F), (0xFFA0, 0xFFA0), (0x1BCA0, 0x1BCA3), (0xE0100, 0xE01EF))


def _invisible(ch: str) -> bool:
    import unicodedata
    if unicodedata.category(ch) == "Cf":
        return True
    o = ord(ch)
    return any(a <= o <= b for a, b in _DI_RANGES)


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
        else:
            out.append(c if c.isascii() else _CONF.get(c, c))
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
            if encoded == "space":
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
        readings += [(" ", "decode"), (" ", "space")]
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
        if folded is not text:
            spans = [Finding(f.category, S[f.start], E[f.end - 1], f.rule, f.members) for f in spans]
        found.extend(spans)
    return Classification(_resolve(found), cred, residual)
