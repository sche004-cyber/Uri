"""Repairs after the V3.1 fallback review FB5 of daa0ec58 (docs/privacy/reviews/FB5_fallback_review_daa0ec58.txt) and
coordinator finding C5-01 (plan PC-14). Generated sweeps, synthetic values only."""
import json
import random
import string
import time
import unicodedata

import httpx
import pytest

from uri_privacy import PrivacyRefused
from uri_privacy import classify as C
from uri_web.search import TavilyProvider

from .helpers import TGateway

EXTERNAL = ("WEB_SEARCH", "EXTERNAL_AGENT", "EXTERNAL_MODEL", "EXTERNAL_SERVICE")
CARD, AADHAAR = "4539148803436467", "234567890124"


def send(text, dest):
    try:
        return False, TGateway().prepare(text, requester="t", destination=dest, purpose="p", reversible=False).text
    except PrivacyRefused as exc:
        return exc.code, ""


def digits(s):
    # Independent of the code under test (C.fold would hide exactly the digits it fails to read): every character with
    # a digit value, NFKC first so that circled or full-width forms count too.
    return "".join(str(unicodedata.digit(c)) for c in unicodedata.normalize("NFKC", s)
                   if unicodedata.digit(c, None) is not None)


def wire(text):
    sent = []

    def capture(request):
        sent.append(json.loads(request.content)["query"])
        return httpx.Response(200, json={"results": []})
    TavilyProvider(api_key="test", transport=httpx.MockTransport(capture), privacy=TGateway()).search(text)
    return sent


# --- R1-01: every character with a digit value, decimal or not ---------------------------------------------------------
def _digit_families():
    fams = {}
    for cp in range(0x110000):
        ch = chr(cp)
        d = unicodedata.digit(ch, None)
        if d is None or ch.isascii():
            continue
        name = unicodedata.name(ch, "")
        key = name.rsplit(" ", 1)[0] if name else hex(cp)
        fams.setdefault(key, {})[d] = ch
    return {k: v for k, v in fams.items() if len(v) == 10 or (len(v) == 9 and 0 not in v)}


def test_fb5_r1_01_no_digit_valued_character_carries_a_card_or_aadhaar():
    fams = _digit_families()
    assert len(fams) > 20
    bad = []
    for name, m in fams.items():
        enc = lambda s: "".join(m.get(int(c), c) for c in s)          # noqa: E731 - a missing 0 stays ASCII
        for value, label in ((CARD, "card"), (AADHAAR, "my aadhaar is")):
            text = f"{label} {enc(value[:4])} {enc(value[4:8])} {enc(value[8:12])} {enc(value[12:])}".rstrip()
            for dest in EXTERNAL + ("LOG",):
                refused, out = send(text, dest)
                if not refused and value in digits(out):
                    bad.append((name, value[:4], dest))
    assert bad == [], bad[:5]


def test_fb5_r1_01_dingbat_card_never_reaches_the_wire():
    q = "card ❹❺❸❾ ❶❹❽❽ ⓿❸❹❸ ❻❹❻❼"
    assert all(CARD not in digits(s) for s in wire(q))


# --- R1-02: latency on non-ASCII text; pathological inputs ----------------------------------------------------------------
NON_ASCII = {"hindi": "यह एक साधारण वाक्य है। ",
             "japanese": "今日はとても良い天気ですね。東京の駅。",
             "arabic": "هذه جملة عادية لا تحتوي. "}


@pytest.mark.parametrize("script", sorted(NON_ASCII))
def test_fb5_r1_02_ordinary_non_ascii_query_is_read_once_and_fast(script):
    q = (NON_ASCII[script] * 40)[:400]
    assert not C._needs_readings(q)              # one reading: nothing in it reads differently another way
    g = TGateway()
    g.prepare(q, requester="t", destination="WEB_SEARCH", purpose="p")
    t0 = time.perf_counter()
    for _ in range(20):
        g.prepare(q, requester="t", destination="WEB_SEARCH", purpose="p")
    assert (time.perf_counter() - t0) / 20 < 0.05                  # generous for CI; measured p95 in measurements.json


def test_fb5_r1_02_readings_are_still_taken_when_they_can_differ():
    for q in ("card 4111​1111", "pa̶ssword: x", "a%20b", "x&amp;y", "अ‍क á"):
        assert C._needs_readings(q), q


def test_fb5_r1_02_pathological_input_is_refused_fast_and_redacted_in_logs():
    for t in ("a/" * 8192, "a+" * 32768):
        t0 = time.perf_counter()
        assert send(t, "WEB_SEARCH")[0] == "PRIVACY_INPUT_TOO_COMPLEX"
        assert time.perf_counter() - t0 < 0.5
        assert send(t, "LOG") == (False, "[redacted]")
    assert send("a/" * 200, "WEB_SEARCH")[0] is False                  # a live-size query is classified normally


def test_fb5_r1_02_linear_long_secret_spans_cover_the_assist_rule():
    rng = random.Random(3)
    alphabet = string.ascii_letters + string.digits + "+/=_-. :"
    for _ in range(3000):
        t = "".join(rng.choice(alphabet) for _ in range(rng.randint(30, 200)))
        mine = C._long_secret_spans(t)
        for m in C._LONG_SECRET.finditer(t):
            assert any(a <= m.start() and m.end() <= b for a, b in mine), (t, m.group(0))


# --- R1-03: e-mail forms ------------------------------------------------------------------------------------------------
@pytest.mark.parametrize("q", ["mail riya.sharma @ examplemail.com", "mail riya.sharma@ examplemail.com",
                               "mail riya.sharma @examplemail.com", "riya.sharma@\nexamplemail.com",
                               "mail riya(at)example(dot)com", "mail riya [at] example [dot] com", "mail riya{at}example.com",
                               "mail अनिल@उदाहरण.भारत",
                               "mail anil@उदाहरण.in"])
def test_fb5_r1_03_spaced_bracketed_and_indic_domain_emails_are_redacted(q):
    for dest in ("WEB_SEARCH", "EXTERNAL_AGENT"):
        refused, out = send(q, dest)
        assert refused or ("riya" not in out and "anil" not in out and "अन" not in out), (dest, out)


def test_fb5_r1_03_at_in_prose_stays_readable():
    for q in ("meet @ noon", "see you at 5", "look at example.com"):
        assert send(q, "WEB_SEARCH") == (False, q)


# --- R1-04 / C5-01: PAN forms --------------------------------------------------------------------------------------------
def test_fb5_r1_04_pan_with_separators_is_redacted():
    rng = random.Random(9)
    bad = []
    for _ in range(60):
        L = string.ascii_uppercase
        pan = "".join(rng.choice(L) for _ in range(3)) + rng.choice("PCHFATBLJG") + rng.choice(L) + \
            "".join(str(rng.randint(0, 9)) for _ in range(4)) + rng.choice(L)
        if pan[5:9] in [str(y) for y in range(1900, 2100)]:
            continue
        for sep in "-._/,":
            for form in (pan[:5] + sep + pan[5:9] + sep + pan[9], sep.join(pan), pan[:3] + sep + pan[3:5] + sep + pan[5:9] + sep + pan[9],
                         (pan[:5] + sep + pan[5:9] + sep + pan[9]).lower()):
                for dest in ("WEB_SEARCH", "EXTERNAL_AGENT"):
                    refused, out = send(f"my PAN is {form}", dest)
                    if not refused and pan.lower() in out.lower().replace(sep, ""):
                        bad.append((form, dest))
    assert bad == [], bad[:5]


@pytest.mark.parametrize("q", ["hello 2024 a", "graph-2023-a plot", "hotel 2025 b", "place 1234 x", "class of 2024 b"])
def test_c5_01_words_and_years_are_not_a_pan(q):
    assert send(q, "WEB_SEARCH") == (False, q)


# --- R1-05 / R1-07: labels ----------------------------------------------------------------------------------------------
@pytest.mark.parametrize("q", ["pin number 1234", "ATM pin number 4821 blocked", "pin no 4821", "pin no. 4821", "pin # 4821",
                               "otp number 482913", "cvv no 123", "username alice pass is hunter2",
                               "wifi key is Sunflower2026", "network key: Sunflower2026", "wpa2 key = Sunflower2026",
                               "-----BEGIN RSA PRIVATE KEY-----\nMIIBOgIBAAJBAKj34GkxFhD90vcNLYLInFEX6Ppy1tPf9Cnzj4p4WGeKLs1Pt8Qu\nKUpRKfFLfRYC9AIKjbJTWit+CqvjWYzvQwECAwEAAQ\n-----END RSA PRIVATE KEY-----"])
def test_fb5_r1_05_r1_07_labelled_credentials_are_refused(q):
    for dest in ("WEB_SEARCH", "EXTERNAL_AGENT", "EXTERNAL_MODEL"):
        assert send(q, dest)[0], (q, dest)


@pytest.mark.parametrize("q", ["pin number format for atm cards", "network key concepts", "wifi key not working",
                               "how to pass is it hard", "the pin is on the map"])
def test_fb5_r1_05_r1_07_ordinary_phrasings_stay_readable(q):
    assert send(q, "WEB_SEARCH") == (False, q)


# --- R1-06: invisible characters in non-English text ------------------------------------------------------------------
@pytest.mark.parametrize("q", ["สวัสดี​ครับ",
                               "မင်္ဂလာ​ပါ",
                               "日本​語", "नमस्ते​दोस्त",
                               "שלום‏ עולם", "مرحبا‏ بك",
                               "مرح﻿با", "﻿hello world"])
def test_fb5_r1_06_ordinary_non_english_invisibles_are_not_refused(q):
    for dest in ("WEB_SEARCH", "EXTERNAL_AGENT"):
        refused, out = send(q, dest)
        assert not refused, (dest, q)


@pytest.mark.parametrize("q", ["p​assword: Mango#2026!", "card 4111​1111​1111​1111",
                               "अ 4111​1111​1111​1111", "hello​world 4111"])
def test_fb5_r1_06_invisibles_next_to_ascii_or_digits_are_still_refused(q):
    for dest in ("WEB_SEARCH", "EXTERNAL_AGENT"):
        refused, out = send(q, dest)
        assert refused or ("4111111111111111" not in digits(out) and "Mango" not in out), (dest, out)


# --- R1-08: LOG keeps no half of a split key ----------------------------------------------------------------------------
def test_fb5_r1_08_log_redacts_both_halves_of_a_split_key():
    rng = random.Random(4)
    a = "".join(rng.choice(string.ascii_letters + string.digits) for _ in range(20))
    b = "".join(rng.choice(string.ascii_letters + string.digits) for _ in range(20))
    for sep in ("\n", " "):
        out = send(f"sk-proj-{a}{sep}{b}", "LOG")[1]
        assert a not in out and b not in out, out
