"""Deterministic checks on Brain-produced text. No model call.

Every Brain result is checked against what the USER said, not against what the model says it did. Findings become
flags shown next to the draft; nothing is rewritten silently.

Flags (severity "error" = probably wrong, "review" = the user should look):
  FACT_UNSOURCED            error   a fact the model reported does not occur in the user's words
  FACT_MISSING              error   a fact the user gave (and the model reported) is absent from the text
  SUPERSEDED_VALUE_PRESENT  error   a value the user corrected away still appears
  EXCLUDED_PHRASE_PRESENT   error   a phrase the user asked to leave out still appears
  MEANING_CHANGED           error   grammar-only correction lost a number, date or name
  NEW_DETAIL                review  a number, date or name appears that the user never gave (possible invention)
  CORRECTION_UNCONFIRMED    review  the user corrected themselves but the model reported no superseded value
  POSSIBLE_MISHEARING       review  the recogniser marked a span as uncertain and it is used in the text
"""
from __future__ import annotations

import re
import unicodedata

_UNITS = ["zero", "one", "two", "three", "four", "five", "six", "seven", "eight", "nine", "ten", "eleven", "twelve",
          "thirteen", "fourteen", "fifteen", "sixteen", "seventeen", "eighteen", "nineteen"]
_TENS = {"twenty": 20, "thirty": 30, "forty": 40, "fifty": 50, "sixty": 60, "seventy": 70, "eighty": 80, "ninety": 90}
_ORD = {"first": 1, "second": 2, "third": 3, "fourth": 4, "fifth": 5, "sixth": 6, "seventh": 7, "eighth": 8,
        "ninth": 9, "tenth": 10, "eleventh": 11, "twelfth": 12, "thirteenth": 13, "fourteenth": 14, "fifteenth": 15,
        "sixteenth": 16, "seventeenth": 17, "eighteenth": 18, "nineteenth": 19, "twentieth": 20, "thirtieth": 30}
# Hindi number words commonly mixed into Indian English speech.
_HINDI = {"ek": 1, "do": 2, "teen": 3, "char": 4, "chaar": 4, "paanch": 5, "panch": 5, "chhe": 6, "chhah": 6,
          "saat": 7, "aath": 8, "nau": 9, "das": 10, "bees": 20, "pachaas": 50, "sau": 100}
_NUMWORD = {w: i for i, w in enumerate(_UNITS)}
_NUMWORD.update(_TENS)
_NUMWORD.update({"hundred": 100, "thousand": 1000, "dozen": 12, "lakh": 100000, "crore": 10000000})
MONTHS = ("january", "february", "march", "april", "may", "june", "july", "august", "september", "october",
          "november", "december")
WEEKDAYS = ("monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday")
_RELATIVE_DAYS = ("yesterday", "today", "tomorrow", "tonight", "kal", "aaj", "parson")

# Capitalised words that are ordinary letter vocabulary, not names or facts.
_COMMON_CAPS = set("""
a an the i to of in on at by for from with and or but if as is are was were be been this that these those it its
dear sir madam respected respectfully subject sub ref reference date yours faithfully sincerely truly regards
thanking thank thanks kind warm best with gratitude obediently obedient sincerely regarding re kindly please
hostel warden principal office school college university department student students parent parents guardian
committee management administration team staff faculty dean director manager head chairperson secretary
notice circular memo memorandum report summary minutes agenda letter email application request complaint
mr mrs ms dr prof shri smt sri miss name your our my his her their we you they he she us them
however therefore further furthermore also moreover accordingly hence thus additionally meanwhile nevertheless
all any each every some no not none one many most more less few several other another such
sub: re: encl enclosure cc bcc
""".split())


def _fold(s):
    s = unicodedata.normalize("NFKC", s or "").lower()
    s = s.replace("’", "'").replace("‘", "'").replace("“", '"').replace("”", '"')
    return s


def _tokens(s):
    return re.findall(r"[a-z0-9]+(?:'[a-z]+)?", _fold(s))


_SCALES = {"hundred": 100, "thousand": 1000, "lakh": 100000, "crore": 10000000}


def _phrase_value(toks, i):
    """Parse an English number phrase starting at toks[i] ("one hundred and five", "eighty five thousand").
    Returns (value, next_index, word_count) or None."""
    total, cur, j, used = 0, 0, i, 0
    while j < len(toks):
        w = toks[j]
        if w in _UNITS:
            cur += _NUMWORD[w]
        elif w in _TENS:
            cur += _TENS[w]
        elif w in _SCALES and (cur or total):
            if w == "hundred":
                cur = (cur or 1) * 100
            else:
                total += (cur or 1) * _SCALES[w]
                cur = 0
        elif w == "and" and used and j + 1 < len(toks) and toks[j + 1] in _NUMWORD and toks[j + 1] not in _SCALES:
            j += 1
            continue
        else:
            break
        used += 1
        j += 1
    if not used:
        return None
    return total + cur, j, used


def canonical_numbers(s) -> set:
    """All numbers mentioned in s, as ints (digits, number words incl. 'twenty-five', ordinals, Hindi words)."""
    out = set()
    f = _fold(s)
    for m in re.finditer(r"\b(\d{1,9})(?:st|nd|rd|th)?\b", f.replace(",", "")):
        out.add(int(m.group(1)))
    toks = re.findall(r"[a-z]+", f)
    i = 0
    while i < len(toks):
        w = toks[i]
        ph = _phrase_value(toks, i) if (w in _UNITS or w in _TENS) else None
        if ph and ph[2] > 1:                        # "one hundred and five", "twenty five", "eighty five thousand"
            out.add(ph[0])
            i = ph[1]
            continue
        if w in _NUMWORD and w not in ("one",):     # "one" is too often a pronoun ("the one who ...")
            out.add(_NUMWORD[w])
        elif w in _ORD and w not in ("second",):    # "second" is too often "a second time" / "second paragraph"
            out.add(_ORD[w])
        elif w in _HINDI and w not in ("do", "ek", "das", "char", "sau", "nau"):
            out.add(_HINDI[w])
        i += 1
    return out


def _value_present(value, text) -> bool:
    """Is a fact value present in text? Token containment, with number words and digits treated as equal."""
    vt, tt = _tokens(value), _tokens(text)
    if not vt:
        return True
    tset = set(tt)
    vnums = canonical_numbers(value)
    if vnums:
        tnums = canonical_numbers(text)
        if not vnums <= tnums:
            return False
        rest = [t for t in vt if not canonical_numbers(t) and t not in ("st", "nd", "rd", "th") and t not in _COMMON_CAPS]
        if not rest:
            return True
        return _contiguous_or_all(rest, tt, tset)
    return _contiguous_or_all(vt, tt, tset)


def _stem(t):
    for suf in ("ing", "ed", "es", "s"):
        if len(t) > len(suf) + 2 and t.endswith(suf):
            return t[:-len(suf)]
    return t


def _contiguous_or_all(vt, tt, tset):
    content = [t for t in vt if t not in _COMMON_CAPS or len(vt) == 1]
    if not content:
        content = vt
    stems = {_stem(t) for t in tset}
    hits = sum(1 for t in content if t in tset or _stem(t) in stems)
    if len(content) <= 3:
        return hits == len(content)
    # A long dictated phrase may be reworded by a tone change; most of its content words must survive.
    return hits >= 0.7 * len(content)


def _phrase_present(phrase, text) -> bool:
    p = " ".join(_tokens(phrase))
    if not p:
        return False
    t = " " + " ".join(_tokens(text)) + " "
    if (" " + p + " ") in t:
        return True
    pn = canonical_numbers(phrase)
    if pn and len(_tokens(phrase)) == 1:
        return bool(pn & canonical_numbers(text))
    return False


def _flag(code, severity, detail):
    return {"code": code, "severity": severity, "detail": detail}


def check_facts(facts, text, source_text) -> list:
    flags = []
    for f in facts or ():
        value = str(f.get("value") or "").strip()
        key = str(f.get("key") or "").strip()
        if value and not _value_present(value, source_text):
            flags.append(_flag("FACT_UNSOURCED", "error", "%s: %s" % (key, value)))
        if value and not _value_present(value, text):
            flags.append(_flag("FACT_MISSING", "error", "%s: %s" % (key, value)))
        for old in f.get("superseded") or ():
            old = str(old).strip()
            if old and _fold(old) != _fold(value) and not _value_present(old, value) and _phrase_present(old, text):
                flags.append(_flag("SUPERSEDED_VALUE_PRESENT", "error", "%s: '%s' was corrected to '%s'" % (key, old, value)))
    return flags


def check_exclusions(exclusions, text) -> list:
    return [_flag("EXCLUDED_PHRASE_PRESENT", "error", e) for e in exclusions or () if e and _phrase_present(e, text)]


def protected_tokens(text) -> dict:
    """Numbers, months, weekdays, relative days, e-mail addresses and mid-sentence capitalised words."""
    f = _fold(text)
    words = set(re.findall(r"[a-z]+", f))
    caps = set()
    for m in re.finditer(r"\b([A-Z][a-zA-Z]{1,})\b", text):
        w = m.group(1)
        start = m.start(1)
        prev = text[:start].rstrip()
        honorific = re.search(r"\b(?:Mr|Mrs|Ms|Dr|Prof|Shri|Smt|Sri)\.?$", prev)
        if not prev or (prev[-1] in ".!?:\n\"“" and not honorific):
            continue
        if w.lower() in _COMMON_CAPS or w.lower() in MONTHS or w.lower() in WEEKDAYS:
            continue
        caps.add(w.lower())
    return {"numbers": canonical_numbers(text), "months": {m for m in MONTHS if m in words},
            "weekdays": {d for d in WEEKDAYS if d in words}, "relative": {d for d in _RELATIVE_DAYS if d in words},
            "emails": set(re.findall(r"[\w.+-]+@[\w-]+\.[\w.]+", f)), "names": caps}


def check_meaning_preserved(original, corrected) -> list:
    """Grammar-only: every protected token of the original must survive; no new number/date may appear."""
    a, b = protected_tokens(original), protected_tokens(corrected)
    bwords = set(_tokens(corrected))
    lost = []
    for k in ("numbers", "months", "weekdays", "relative", "emails"):
        lost += sorted(str(x) for x in a[k] - b[k])
    lost += sorted(n for n in a["names"] if n not in bwords)
    added = sorted(str(x) for x in (b["numbers"] - a["numbers"]) | (b["months"] - a["months"]) |
                   (b["weekdays"] - a["weekdays"]))
    awords = set(_tokens(original))
    added_names = sorted(n for n in b["names"] if n not in awords)
    flags = []
    if lost:
        flags.append(_flag("MEANING_CHANGED", "error", "missing after correction: " + ", ".join(lost)))
    if added_names:
        flags.append(_flag("MEANING_CHANGED", "error", "name added by the correction: " + ", ".join(added_names)))
    if added:
        flags.append(_flag("NEW_DETAIL", "review", "added by the correction: " + ", ".join(added)))
    return flags


def check_new_details(text, known_text) -> list:
    """Numbers, dates and capitalised names in `text` that never occur in `known_text` (the user's words plus the
    previous version). Bracketed placeholders like [Your Name] are ignored: they mark missing information."""
    body = re.sub(r"\[[^\]]{1,80}\]", " ", text)
    a, k = protected_tokens(body), protected_tokens(known_text)
    kwords = set(_tokens(known_text))
    new = sorted(str(x) for x in a["numbers"] - k["numbers"])
    new += sorted((a["months"] - k["months"]) | (a["weekdays"] - k["weekdays"]))
    new += sorted(n for n in a["names"] if n not in kwords)
    return [_flag("NEW_DETAIL", "review", "not in your words: " + ", ".join(new))] if new else []


def _details(text):
    p = protected_tokens(text)
    return ({str(x) for x in p["numbers"]} | p["months"] | p["weekdays"] | p["relative"] | p["emails"] | p["names"])


def _covered(detail, texts):
    return any(t and (_phrase_present(detail, t) or detail in _tokens(t)) for t in texts)


_EXCLUDE = re.compile(r"\b(?:don'?t|do not|dont|never|without)\s+(?:mention(?:ing)?|say(?:ing)?|use|using|include|including|"
                      r"write|writing|name|naming)\s+[\"'“‘]?([^.,;!?\"”’]{2,60})", re.I)
_GENERIC = re.compile(r"\b(?:name|names|details?|number|numbers|date|dates|amount|reason|anything|that|this|it|"
                      r"his|her|their|the student'?s?|the person'?s?)\b", re.I)


def user_exclusions(user_words) -> list:
    """Literal phrases the USER asked to leave out ("don't mention Monday"), found without the model. A description
    rather than a literal ("don't mention the student's name") is left to the model's exclusion list."""
    out = []
    for m in _EXCLUDE.finditer(user_words or ""):
        phrase = m.group(1).strip()
        phrase = re.split(r"\b(?:and|but|instead|say|write|use|anywhere|at all|please|either)\b", phrase,
                          flags=re.I)[0].strip()
        phrase = re.sub(r"\s+(?:in|from|within|inside)\s+(?:the|this|my|our|that)\s+(?:letter|e-?mail|mail|draft|notice|"
                        r"note|document|text|message|circular|report|memo|reply|application)\b.*$", "", phrase,
                        flags=re.I).strip()
        if phrase and not _GENERIC.search(phrase) and len(phrase.split()) <= 6:
            out.append(phrase)
    return out


def strip_corrected(user_words) -> str:
    """Remove the few words just before each spoken correction cue ("five, sorry, seven" -> "seven"), so a value
    the user replaced is not demanded in the draft even when the model did not report the correction."""
    from .text_input import _CORRECTION_CUES
    text = user_words or ""
    for m in reversed(list(_CORRECTION_CUES.finditer(text))):
        after = list(re.finditer(r"[\w'-]+", text[m.end():]))[:4]
        kind = next((k for k in (_detail_kind(w.group(0)) for w in after) if k), None)
        if kind is None:
            continue                      # the replacement is not a typed detail: keep everything, flag for review
        before = list(re.finditer(r"[\w'-]+", text[:m.start()]))[-6:]
        # The replaced value is the nearest earlier detail of the SAME kind ("17 students on Monday, sorry, 18
        # students": 17, not Monday). Other details stay required.
        for w in reversed(before):
            if _detail_kind(w.group(0)) == kind:
                text = text[:w.start()] + " " + text[w.end():]
                break
    return text


_ORDINAL_WORD = set(_ORD) | {"1st", "2nd", "3rd"}


def _detail_kind(word):
    low = word.lower()
    if low in WEEKDAYS or low in MONTHS or low in _RELATIVE_DAYS or low in _ORDINAL_WORD or \
            re.fullmatch(r"\d{1,2}(?:st|nd|rd|th)", low):
        return "date"
    if canonical_numbers(word) or re.fullmatch(r"\d[\d,]*", word):
        return "number"
    if word[:1].isupper() and low not in _COMMON_CAPS and len(word) > 1:
        return "name"
    return None


def check_user_details(user_words, text, dropped_ok=()) -> list:
    """Independent of what the model reports: numbers, dates, days and mid-sentence names in the user's words must
    appear in the draft, unless the user corrected or excluded them."""
    have = {str(x) for x in canonical_numbers(text)} | set(_tokens(text))
    missing = sorted(d for d in _details(user_words) if d not in have and not _covered(d, dropped_ok))
    return [_flag("USER_DETAIL_MISSING", "review", "from your words, not in the draft: " + ", ".join(missing))] if missing else []


def check_details_kept(old_text, new_text, dropped_ok=()) -> list:
    """Revision: numbers, dates, days and names of the previous version that disappeared, unless the user's
    instruction mentioned them or they were corrected/excluded."""
    have = {str(x) for x in canonical_numbers(new_text)} | set(_tokens(new_text))
    gone = sorted(d for d in _details(old_text) if d not in have and not _covered(d, dropped_ok))
    return [_flag("DETAIL_REMOVED", "review", "no longer in the draft: " + ", ".join(gone))] if gone else []


def check_correction_accounted(cues, facts, clarification) -> list:
    if not cues or clarification:
        return []
    if any(f.get("superseded") for f in facts or ()):
        return []
    return [_flag("CORRECTION_UNCONFIRMED", "review",
                  "you corrected yourself (%s); check that the draft uses the value you meant" % ", ".join(cues[:3]))]


def check_uncertain(uncertain, text) -> list:
    return [_flag("POSSIBLE_MISHEARING", "review", "'%s' may have been misheard; please confirm" % u)
            for u in uncertain or () if _phrase_present(u, text)]


def placeholders(text) -> list:
    return sorted(set(re.findall(r"\[([^\]]{1,80})\]", text or "")))
