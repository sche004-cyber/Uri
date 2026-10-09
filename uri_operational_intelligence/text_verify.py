"""Deterministic checks on Brain-produced text. No model call.

Every Brain result is checked against what the USER said, not against what the model says it did. Findings become
flags shown next to the draft; nothing is rewritten silently.

Flags (severity "error" = probably wrong, "review" = the user should look, "info" = shown so nothing is silent):
  FACT_UNSOURCED            error   a fact the model reported does not occur in the user's words
  FACT_MISSING              error   a fact the user gave (and the model reported) is absent from the text
  SUPERSEDED_VALUE_PRESENT  error   a value the user corrected away still appears
  EXCLUDED_PHRASE_PRESENT   error   a phrase the user asked to leave out still appears
  MEANING_CHANGED           error   grammar-only correction lost a number, date or name
  NEW_DETAIL                review  a number, date or name appears that the user never gave (possible invention)
  CORRECTION_UNCONFIRMED    review  the user corrected themselves but the model reported no superseded value
  POSSIBLE_MISHEARING       review  the recogniser marked a span as uncertain and it is used in the text
  DETAIL_DROPPED            info    a detail from the user's words is absent because it was corrected or excluded;
                                    shown, never silent, so a wrong attribution by the model is visible
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
    # "warden's" -> "warden" (live finding LQ-10: possessive placeholders such as [Warden's Name])
    return [re.sub(r"'s$", "", t) for t in re.findall(r"[a-z0-9]+(?:'[a-z]+)?", _fold(s))]


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
    if len(content) <= 2:
        return hits == len(content)
    if len(content) == 3:
        return hits >= 2                      # live finding LQ-2: one reworded word in a three-word value
    # A long dictated phrase may be reworded by a tone change; most of its content words must survive.
    return hits >= 0.7 * len(content)


def _phrase_present(phrase, text) -> bool:
    p = " ".join(_tokens(phrase))
    if not p:
        return False
    pn = canonical_numbers(phrase)
    if pn and all(canonical_numbers(t) or t in ("and",) for t in _tokens(phrase)):
        return pn <= canonical_numbers(text)    # live finding LQ-1: "two" must not match inside "forty-two"
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
    # Names include sentence-initial ones ("Anil arrived late" -> "Someone arrived late"), via the wider _details set.
    initial = {d for d in _details(original) if d.isalpha() and d not in a["months"] and d not in a["weekdays"]
               and d not in a["relative"]}
    lost += sorted(n for n in (a["names"] | initial) if n not in bwords)
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


def _lower_title_line(line):
    """A Title Case line ("Subject: Unauthorized Absence of Students") capitalises ordinary words; they are not
    names (live finding LQ-3). Lines where most words are capitalised are lower-cased for the name check only."""
    words = re.findall(r"[A-Za-z][\w'-]*", line)
    if len(words) >= 3 and sum(1 for w in words if w[0].isupper()) >= 0.6 * len(words):
        return line.lower()
    return line


def check_new_details(text, known_text) -> list:
    """Numbers, dates and capitalised names in `text` that never occur in `known_text` (the user's words plus the
    previous version). Bracketed placeholders like [Your Name] are ignored: they mark missing information."""
    body = re.sub(r"\[[^\]]{1,80}\]", " ", text)
    body = "\n".join(_lower_title_line(ln) for ln in body.splitlines())
    a, k = protected_tokens(body), protected_tokens(known_text)
    kwords = set(_tokens(known_text))
    new = sorted(str(x) for x in a["numbers"] - k["numbers"])
    new += sorted((a["months"] - k["months"]) | (a["weekdays"] - k["weekdays"]))
    new += sorted(n for n in a["names"] if n not in kwords)
    return [_flag("NEW_DETAIL", "review", "not in your words: " + ", ".join(new))] if new else []


def _details(text):
    """Details whose ABSENCE is reported. Wider than protected_tokens: a capitalised word at a sentence start or after
    a colon ("Draft a note: Anil arrived") counts too, unless it is ordinary letter vocabulary or a function word.
    (protected_tokens stays narrow because it also drives NEW_DETAIL, where sentence starters would be noise.)"""
    p = protected_tokens(text)
    initial = set()
    for m in re.finditer(r"(?:^|[.!?:\n\"“]\s*)([A-Z][a-zA-Z]{1,})\b", text or ""):
        low = m.group(1).lower()
        if low not in _COMMON_CAPS and low not in _FUNCTION_WORDS and low not in MONTHS and low not in WEEKDAYS \
                and low not in _SENTENCE_STARTERS:
            initial.add(low)
    return ({str(x) for x in p["numbers"]} | p["months"] | p["weekdays"] | p["relative"] | p["emails"] | p["names"]
            | initial)


# Imperatives and openers that begin requests and letters; never names.
_SENTENCE_STARTERS = set("""
draft write compose prepare create generate frame type pen correct proofread fix check improve edit rewrite rephrase
reword paraphrase polish simplify shorten condense summarise summarize expand turn convert develop kindly please
inform informing request requesting regarding sub respected thanking yours dear hello hi uri attendance repairs
""".split())


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


def verified_superseded(user_words, claimed) -> tuple:
    """Split the model's claimed superseded values into (verified, unverified).

    A claim is VERIFIED only when the user's own words contain the value followed closely by a spoken correction
    cue in the same sentence ("five, sorry, seven"; "Tuesday, no, Wednesday"): at most four words between them, no
    sentence break and no other detail in between. No value is ever excused by inference alone (Codex TI rounds 3-7): an unverified claim stays
    required and is shown to the user as a review flag."""
    from .text_input import _CORRECTION_CUES
    text = user_words or ""
    # A cue counts only as a correction, never as an apology or a phrase ("sorry for the late notice", "actually
    # happened"): the words right after it must hold a replacement value of the same kind.
    cues = [(m.start(), m.end()) for m in _CORRECTION_CUES.finditer(text) if not _APOLOGY.match(text, m.start())]
    verified, unverified = [], []
    swapped = [p.lower() for p in user_exclusions(text) + _swap_phrases(text)]
    for value in claimed or ():
        if any(p and p in value.lower() for p in swapped):
            verified.append(value)            # the user said "don't say X" / "replace X with": X is replaced (LQ-4)
            continue
        kind = next((k for k in (_detail_kind(w) for w in re.findall(r"[\w'-]+", value)) if k), None)
        ok = False
        if kind is not None:
            for m in re.finditer(r"(?<![\w])" + re.escape(value.strip()) + r"(?![\w])", text, re.I):
                for c0, c1 in cues:
                    gap = text[m.end():c0]
                    words = re.findall(r"[\w'-]+", gap)
                    after = re.split(r"[.!?;\n]", text[c1:])[0]
                    after_words = re.findall(r"[\w'-]+", after)[:5]
                    # The claimed value must be the LAST detail before the cue ("Anil with 17 students, sorry"
                    # corrects 17, not Anil) and a same-kind value must follow the cue.
                    if c0 >= m.end() and not re.search(r"[.!?;\n]", gap) and len(words) <= 4 and \
                            not any(_detail_kind(w) for w in words) and \
                            any(_detail_kind(w) == kind for w in after_words):
                        ok = True
        (verified if ok else unverified).append(value)
    return verified, unverified


def _swap_phrases(text):
    from .text_intent import _PHRASE_SWAP
    return [next((g for g in m.groups() if g), "").strip(" \"'“”‘’") for m in _PHRASE_SWAP.finditer(text or "")]


_APOLOGY = re.compile(r"sorry\s+(?:for|to|about|that|if|i|we|but)\b|actually\s+(?:happened|is|was|were|did|do|does)\b",
                      re.I)


_ORDINAL_WORD = set(_ORD) | {"1st", "2nd", "3rd"}
# Words that start sentences ("There were 18 students") are never taken as names.
_FUNCTION_WORDS = set("""
there here then now when where what which who whom whose why how that this these those it its they them their we our
you your he him his she her i me my mine yes no not okay ok please sorry actually also so and but or because if
was were is are be been being have has had do does did will would shall should can could may might must
one some any all each every few many more most other another such only just even still yet again
on in at by for from to of with without about after before during until since over under
let lets make made say said tell told give gave take took get got go went come came see saw know knew think
everybody everyone everything nobody nothing somebody someone something anybody anyone anything
""".split())


def _detail_kind(word):
    """'date', 'number', 'name' or None for one word (used only to refuse a supersession claim that skips over
    another detail; never to remove a value)."""
    low = word.lower()
    if low == "may":
        return None                       # "sorry, may I add ..." (Codex TI round 9)
    if low in WEEKDAYS or low in MONTHS or low in _RELATIVE_DAYS or low in _ORDINAL_WORD or \
            re.fullmatch(r"\d{1,2}(?:st|nd|rd|th)", low):
        return "date"
    if canonical_numbers(word) or re.fullmatch(r"\d[\d,]*", word):
        return "number"
    if word[:1].isupper() and low not in _COMMON_CAPS and low not in _FUNCTION_WORDS and len(word) > 1:
        return "name"
    return None


def check_supersession(user_words, claimed) -> list:
    _, unverified = verified_superseded(user_words, claimed)
    return [_flag("SUPERSESSION_UNVERIFIED", "review",
                  "URI treated '%s' as replaced, but you did not seem to correct it; please check" % u)
            for u in unverified]


def _absent(details, text, dropped_ok, code, label):
    """Every absent detail is reported. One the user corrected/excluded/mentioned is an INFO line (visible), every
    other one a REVIEW flag. Nothing is excused silently (Codex TI rounds 3-9)."""
    have = {str(x) for x in canonical_numbers(text)} | set(_tokens(text))
    absent = sorted(d for d in details if d not in have)
    excused = [d for d in absent if _covered(d, dropped_ok)]
    unexcused = [d for d in absent if d not in excused]
    flags = []
    if unexcused:
        flags.append(_flag(code, "review", label + ", ".join(unexcused)))
    if excused:
        flags.append(_flag("DETAIL_DROPPED", "info", "not in the draft because of your correction or instruction: "
                           + ", ".join(excused)))
    return flags


def check_user_details(user_words, text, dropped_ok=()) -> list:
    """Independent of what the model reports: numbers, dates, days and mid-sentence names in the user's words must
    appear in the draft. Absences the user's correction/exclusion explains are still listed (info)."""
    return _absent(_details(user_words), text, dropped_ok, "USER_DETAIL_MISSING", "from your words, not in the draft: ")


def check_details_kept(old_text, new_text, dropped_ok=()) -> list:
    """Revision: numbers, dates, days and names of the previous version that disappeared. Ones the instruction
    mentioned or the user corrected/excluded are listed as info ("Keep Monday" + Monday removed is visible)."""
    return _absent(_details(old_text), new_text, dropped_ok, "DETAIL_REMOVED", "no longer in the draft: ")


_ESCALATION = re.compile(r"\b(?:disciplinary|punish\w*|penalt\w*|misconduct|serious breach|breach|violation|"
                         r"violat\w+|strict action|stern action|suspend\w*|expel\w*|rusticat\w*|inquiry|enquiry|"
                         r"investigat\w*)\b", re.I)


def check_escalation(text, user_words) -> list:
    """Words that make the matter more serious than the user did (live finding LQ-11: the model sometimes asks
    for disciplinary action although the prompt forbids it). Shown for review, never removed silently."""
    said = {m.group(0).lower()[:6] for m in _ESCALATION.finditer(user_words or "")}
    added = sorted({m.group(0).lower() for m in _ESCALATION.finditer(text or "") if m.group(0).lower()[:6] not in said})
    return [_flag("ESCALATION_ADDED", "review", "stronger than your words: " + ", ".join(added))] if added else []


def date_mentions(text) -> list:
    """Distinct day/date expressions ("the 5th", "15th", "Monday", "6 October")."""
    found = re.findall(r"\b(?:the\s+)?(\d{1,2}(?:st|nd|rd|th)|monday|tuesday|wednesday|thursday|friday|saturday|sunday|"
                       r"\d{1,2}\s+(?:january|february|march|april|june|july|august|september|october|november|"
                       r"december))\b", (text or "").lower())
    return list(dict.fromkeys(found))


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
