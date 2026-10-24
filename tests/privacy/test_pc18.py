"""V3.1 fallback review FB9 of 14099d1b and owner decision LDEC-011 (structural bar) - plan PC-18.
Generated sweeps, synthetic values only."""
import json
import random
import unicodedata

import httpx
import pytest

from uri_privacy import PrivacyRefused
from uri_privacy import classify as C
from uri_web.search import TavilyProvider

from .helpers import TGateway

DESTS = ("WEB_SEARCH", "EXTERNAL_AGENT", "EXTERNAL_MODEL", "LOG")


def send(text, dest):
    try:
        return False, TGateway().prepare(text, requester="t", destination=dest, purpose="p", reversible=False).text
    except PrivacyRefused as exc:
        return exc.code, ""


def digits(s):              # independent of the code under test
    return "".join(str(unicodedata.digit(c)) for c in unicodedata.normalize("NFKC", s)
                   if unicodedata.digit(c, None) is not None)


def _luhn_card(rng):
    d = [4] + [rng.randint(0, 9) for _ in range(14)]
    total = 0
    for i, x in enumerate(reversed(d)):
        y = x * 2 if i % 2 == 0 else x
        total += y - 9 if y > 9 else y
    return "".join(map(str, d)) + str((10 - total % 10) % 10)


def _maps_to(ch):
    return [chr(c) for c in range(0x80, 0x30000) if C._punct_ascii(chr(c)) == ch
            and unicodedata.normalize("NFKC", chr(c)) == chr(c)]


# --- R1-01: a decoy number that both readings see -------------------------------------------------------------------
DECOYS = ("ref 123456789 ", "order 1234567890123 ", "ids 987654321, ", "tracking 555123456789 / ", "")


def test_fb9_r1_01_a_decoy_never_masks_a_value_only_the_original_reading_places():
    rng = random.Random(9)
    dots, colons = _maps_to("."), _maps_to(":") + [":"]
    bad = []
    for _ in range(400):
        card = _luhn_card(rng)
        d, c = rng.choice(dots), rng.choice(colons)
        layout = f"{card[:2]}{d}{card[2:5]}{d}{card[5:8]}{d}{card[8:11]}{c}{card[11:]}"
        for decoy in DECOYS:
            t = decoy + layout + " declined"
            for dest in DESTS:
                refused, out = send(t, dest)
                if not refused and card in digits(out):
                    bad.append((t, dest))
    assert bad == [], (len(bad), bad[:5])


def test_fb9_r1_01_reviewer_reproductions_never_reach_the_wire():
    for q in ("ref 123456789 41۔111۔111۔111:11111", "aadhaar ref 123456789 234۔56۔78۔90:124"):
        sent = []

        def capture(request):
            sent.append(json.loads(request.content)["query"])
            return httpx.Response(200, json={"results": []})
        TavilyProvider(api_key="test", transport=httpx.MockTransport(capture), privacy=TGateway()).search(q)
        assert all(len(digits(s)) < 9 for s in sent), sent


# --- R1-02: an Assist credential in the egress form does not skip the original's reading ---------------------------
@pytest.mark.parametrize("q", ["Authorization: Bearer abcDEF123456ghiJKL789012mnoPQR 41۔111۔111۔111:11111",
                               "AKIAIOSFODNN7EXAMPLE 41۔111۔111۔111:11111"])
def test_fb9_r1_02_log_never_keeps_a_value_next_to_a_credential(q):
    refused, out = send(q, "LOG")
    assert not refused and "4111111111111111" not in digits(out), out
    for dest in ("WEB_SEARCH", "EXTERNAL_AGENT"):
        assert send(q, dest)[0], dest


# --- the sent text is clean in both readings ----------------------------------------------------------------------------
def test_pc18_output_is_clean_in_both_readings_on_generated_mixed_text():
    rng = random.Random(18)
    pool = ["café", "ＡＢＣ", "x‐y", " ", "ﬁle", "今日", "नमस्ते"]
    vals = ["mail a.b@example.in", "card 4111 1111 1111 1111", "call +91 98450 12345", "ssn 123-45-6789"]
    for _ in range(300):
        t = " ".join(rng.choice(pool) for _ in range(3)) + " " + rng.choice(vals) + " " + rng.choice(pool)
        for dest in ("WEB_SEARCH", "EXTERNAL_MODEL"):
            refused, out = send(t, dest)
            if refused:
                continue
            for reading in (out, C.egress_form(out)[0]):
                cats = C.classify(reading).categories()
                assert not cats, (t, dest, out, cats)


# --- RECALL items fixed (LDEC-011: cheap) ---------------------------------------------------------------------------
@pytest.mark.parametrize("q", ["Authorization: Basic dXNlcjpwYXNz", "curl -H 'Authorization: Basic dXNlcjpwYXNz' https://api.example.com",
                               "recovery code 12345678", "backup code: 4821-9375", "2fa codes 123 456 789"])
def test_fb9_recall_credentials_are_refused(q):
    for dest in ("WEB_SEARCH", "EXTERNAL_AGENT"):
        assert send(q, dest)[0], (q, dest)


@pytest.mark.parametrize("q", ["recovery codes for gmail", "basic authorization header example", "backup code generator"])
def test_fb9_recall_ordinary_phrasings_stay_readable(q):
    assert send(q, "WEB_SEARCH") == (False, q)


def test_fb9_r1_05_defanged_local_part_is_redacted_whole():
    refused, out = send("john[.]doe[@]example[.]com", "WEB_SEARCH")
    assert not refused and "john" not in out and "doe" not in out, out
