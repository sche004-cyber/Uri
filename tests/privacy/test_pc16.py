"""V3.1 fallback review FB7 of fdeeec13 (plan PC-16): the digit budget is also counted on the text as written.
Generated sweeps, synthetic values only."""
import random
import unicodedata

import pytest

from uri_privacy import PrivacyRefused
from uri_privacy import classify as C

from .helpers import TGateway

CARD, AADHAAR, SSN, MOBILE = "4111111111111111", "234567890124", "123456789", "9876543210"


def send(text, dest):
    try:
        return False, TGateway().prepare(text, requester="t", destination=dest, purpose="p", reversible=False).text
    except PrivacyRefused as exc:
        return exc.code, ""


def digits(s):              # independent of the code under test
    return "".join(str(unicodedata.digit(c)) for c in unicodedata.normalize("NFKC", s)
                   if unicodedata.digit(c, None) is not None)


def leaks(text, value, dest):
    refused, out = send(text, dest)
    return not refused and value in digits(out)


def joined(value, sizes, gap):
    out, i = [], 0
    for n in sizes:
        out.append(value[i:i + n])
        i += n
    return gap.join(out)


def protected(gap):
    """The LDEC-006 contract shape, as written: 1-3 characters with at most 2 letters, or no letter or digit."""
    return all(not ch.isalnum() for ch in gap) or (len(gap) <= 3 and sum(ch.isalpha() for ch in gap) <= 2)


def _nfkc_changing():
    return [chr(c) for c in range(0x80, 0x30000) if unicodedata.normalize("NFKC", chr(c)) != chr(c)
            and not chr(c).isspace() and not any(x.isdigit() for x in unicodedata.normalize("NFKC", chr(c)))]


def _stable_symbols():
    return [chr(c) for c in range(0x80, 0x30000) if unicodedata.category(chr(c))[0] in "PS"
            and unicodedata.normalize("NFKC", chr(c)) == chr(c)]


# --- R1-01: compatibility characters, alone or next to one or two letters ----------------------------------------------
def test_fb7_r1_01_compatibility_characters_with_letters_do_not_carry_a_value():
    bad = []
    for c in _nfkc_changing():
        for form in (c, "a" + c, "ab" + c, c + "a"):
            if not protected(form):
                continue                            # 3+ letters as written: the stated residual
            if leaks("card " + joined(CARD, (4, 4, 4, 4), form) + " lost", CARD, "WEB_SEARCH"):
                bad.append((hex(ord(c)), form))
            if leaks("aadhaar " + joined(AADHAAR, (4, 4, 4), form) + " ok", AADHAAR, "LOG"):
                bad.append((hex(ord(c)), form, "LOG"))
    assert bad == [], (len(bad), bad[:5])


# --- R1-02: symbols that fold into letters -----------------------------------------------------------------------------
def test_fb7_r1_02_symbols_inside_a_protected_gap_do_not_carry_a_value():
    bad = []
    for c in _stable_symbols():
        for form in ("ab" + c, "a" + c + c, c + c + c):
            if not protected(form):
                continue
            if leaks("card " + joined(CARD, (4, 4, 4, 4), form) + " lost", CARD, "WEB_SEARCH"):
                bad.append((hex(ord(c)), form))
    assert bad == [], (len(bad), bad[:5])


@pytest.mark.parametrize("q,value", [("card 4111a…1111a…1111a…1111 lost", CARD),
                                     ("aadhaar 2345a…6789a…0124 status", AADHAAR),
                                     ("ssn 123a…45a…6789 check", SSN), ("call 98765a…43210", MOBILE),
                                     ("card 4111ab×1111ab×1111ab×1111 lost", CARD),
                                     ("aadhaar 2345ab।6789ab।0124", AADHAAR),
                                     ("call 98765ab∞43210", MOBILE), ("card 4111㏂1111㏂1111㏂1111", CARD)])
def test_fb7_reviewer_reproductions_never_leave(q, value):
    for dest in ("WEB_SEARCH", "EXTERNAL_MODEL", "EXTERNAL_AGENT", "LOG"):
        assert not leaks(q, value, dest), (q, dest)


def test_fb7_random_mixed_gaps_in_the_protected_shape_do_not_leak():
    rng = random.Random(777)
    pool = list(" -._/,:x|") + ["…", "×", "।", "∞", "│", "㏂", "－", " ", "‐"]
    bad = []
    for _ in range(2000):
        sizes = rng.choice([(4, 4, 4, 4), (4, 6, 6), (8, 8), (3, 3, 3, 3, 4)])
        gaps = []
        for _ in sizes:
            g = "".join(rng.choice(pool) for _ in range(rng.randint(1, 3)))
            if sum(ch.isalpha() for ch in g) > 2:
                g = g[0]
            gaps.append(g)
        out, i = [], 0
        for j, n in enumerate(sizes):
            out.append(CARD[i:i + n])
            i += n
            if j < len(sizes) - 1:
                out.append(gaps[j])
        t = "card " + "".join(out) + " ok"
        for dest in ("WEB_SEARCH", "LOG"):
            if leaks(t, CARD, dest):
                bad.append((t, dest))
    assert bad == [], (len(bad), bad[:5])


# --- R1-03: ordinary CJK text is not refused -------------------------------------------------------------------------
def _cjk_benign(rng):
    fw = lambda w: "".join(chr(ord(ch) + 0xFEE0) for ch in w)                       # noqa: E731 full-width Latin
    hw = "ｶﾀｶﾅ ﾃｽﾄ ｻｰﾋﾞｽ"
    unit = rng.choice(["㎒", "㍱", "㎉", "㎏", "㎡", "℃"])
    n = lambda: str(rng.randint(1, 999))                                              # noqa: E731
    return rng.choice([
        f"価格 {fw('PDF')} {n()} {fw('USB')} {n()} {fw('RAM')} {n()}",
        f"{fw('ABC')} {n()} {fw('DEF')} {n()} {fw('GHI')} {n()}",
        f"{hw.split()[0]} {n()} {hw.split()[1]} {n()} {hw.split()[2]} {n()}",
        f"周波数 {n()}{unit} {n()}{unit} {n()}{unit}",
        f"№ {n()} № {n()} № {n()}", f"Ⅻ {n()} Ⅺ {n()} Ⅹ {n()} clock",
    ])


def test_fb7_r1_03_ordinary_cjk_text_is_never_refused():
    rng = random.Random(20261024)
    refused = []
    for _ in range(600):
        q = _cjk_benign(rng)
        for dest in ("WEB_SEARCH", "EXTERNAL_AGENT"):
            r, _ = send(q, dest)
            if r:
                refused.append((q, dest, r))
    assert refused == [], (len(refused), refused[:5])


@pytest.mark.parametrize("q", ["ＡＢＣ 123 ＤＥＦ 456 ＧＨＩ 789",
                               "ﾃｽﾄ 123 ﾃｽﾄ 456 ﾃｽﾄ 789",
                               "สวัสดี 2026", "ﬁle 12 … 34"])
def test_fb7_r1_03_words_between_numbers_leave_unchanged(q):
    assert send(q, "WEB_SEARCH") == (False, q)


def test_fb7_r1_03_a_unit_list_over_the_budget_is_redacted_not_refused():
    refused, out = send("周波数 100㎒ 200㎒ 300㎒", "WEB_SEARCH")
    assert not refused and "[redacted]" in out


def test_as_written_view_keeps_one_character_per_code_point():
    t = "a…❹०b㏂"
    v = C._as_written_view(t)
    assert len(v) == len(t) and v == "a…40b㏂"
