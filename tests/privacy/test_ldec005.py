"""Owner decision LDEC-005 (2026-10-23, "refuse on doubt"; long-number rule narrowed to identifier shapes) and the V3.1
fallback review FB3 of 06166f33 (D:/uri-dev/m95-evidence/FB3_fallback_review_06166f33.txt).

The disguise classes keep producing new members, so these tests are generated sweeps, not example lists. Synthetic data.
"""
import string
import sys
import unicodedata

import httpx
import pytest
import json

from uri_privacy import PrivacyRefused
from uri_privacy import classify as C
from uri_privacy.classify import classify, fold
from uri_web import search as S

from .helpers import TGateway

EXTERNAL = ("WEB_SEARCH", "EXTERNAL_AGENT", "EXTERNAL_MODEL")
CARD, AADHAAR = "4111111111111111", "234567890124"


def send(text, dest):
    """(refused?, text that would leave URI)."""
    try:
        return False, TGateway().prepare(text, requester="t", destination=dest, purpose="p", reversible=False).text
    except PrivacyRefused as exc:
        assert exc.code in ("PRIVACY_DISGUISE_REFUSED", "PRIVACY_REFUSED", "PRIVACY_ENCODING_UNRESOLVED"), exc.code
        return True, ""


def digits(s):
    return "".join(ch for ch in fold(s)[0] if ch.isdigit())


def separators():
    seps = set()
    for ch in string.punctuation + " \t":
        seps.update({ch, ch * 2, ch * 3, f" {ch} ", f"{ch} ", f" {ch}", f"{ch}{ch}{ch}{ch}"})
    seps.update({"_", "__", "x", "ab", "  ", " - - ", "--", "-.-", " - . ", "\u2010", "\u2013", "\u2014", "\u2212",
                 "\u00b7", "\u2022", "\u2236", "\u3002", ";-/", "%", "%%"})
    return sorted(seps)


# --- FB3 R1-02: separator sweep ----------------------------------------------------------------------------------------
@pytest.mark.parametrize("sep", separators())
@pytest.mark.parametrize("dest", EXTERNAL)
def test_fb3_r1_02_no_separator_puts_a_card_or_aadhaar_on_the_wire(sep, dest):
    for text, core in ((f"card 4111{sep}1111{sep}1111{sep}1111 declined", CARD),
                       (f"aadhaar 2345{sep}6789{sep}0124 update", AADHAAR)):
        refused, out = send(text, dest)
        assert refused or core not in digits(out), (repr(sep), out)


@pytest.mark.parametrize("sep", ["-", " ", ".", "/", "\u2010", " - "])
def test_fb3_r1_02_labelled_ssn_never_raw(sep):
    refused, out = send(f"ssn 123{sep}45{sep}6789", "WEB_SEARCH")
    assert refused or "123456789" not in digits(out)


@pytest.mark.parametrize("q", ["aadhaar 234.567.890.124 update", "card 4,111,111,111,111,111 declined",
                               "card 4111111111111111\u200b9 declined", "card 9\u200b4111111111111111",
                               "card 4111111111111111\u00ad7", "aadhaar 234567890124\u200b5",
                               "my number 4111%1111%1111%1111", "card 4111 1111 1111 11119"])
@pytest.mark.parametrize("dest", EXTERNAL)
def test_fb3_reported_forms(q, dest):
    refused, out = send(q, dest)
    assert refused or (CARD not in digits(out) and AADHAAR not in digits(out)), out


def test_fb3_r1_01_log_line_in_doubt_is_fully_redacted():
    out = TGateway().prepare("card 4111111111111111\u200b9 declined", requester="t", destination="LOG", purpose="p").text
    assert out == "[redacted]"


# --- FB3 R1-03: every punctuation look-alike, by Unicode name ----------------------------------------------------------
def lookalikes():
    out = []
    for cp in range(0xA0, 0x30000):
        ch = chr(cp)
        cat = unicodedata.category(ch)
        name = unicodedata.name(ch, "")
        if (cat.startswith("P") or cat.startswith("S") or cat == "Lm") and any(
                w in name for w in ("HYPHEN", "DASH", "MINUS", "COLON", "RATIO", "FULL STOP", "COMMERCIAL AT")) \
                and "MULTIPLICATION" not in name:
            out.append(cp)
    return out


LOOKALIKES = lookalikes()


def test_fb3_r1_03_the_lookalike_sweep_is_not_empty():
    assert len(LOOKALIKES) > 60 and 0x2236 in LOOKALIKES and 0x2010 in LOOKALIKES and 0x3002 in LOOKALIKES


@pytest.mark.parametrize("cp", LOOKALIKES)
def test_fb3_r1_03_lookalike_punctuation_never_hides_a_credential_or_ssn(cp):
    ch = chr(cp)
    name = unicodedata.name(ch, "")
    texts = []
    label_sep = (any(w in name.split() for w in ("COLON", "RATIO", "HYPHEN", "DASH", "MINUS"))
                 and "SEMICOLON" not in name and "LOW LINE" not in name)
    if label_sep:                                                                   # a label separator: "password: X"
        texts.append(f"password{ch} Mango#2026! reset")
    if "FULL STOP" in name:
        refused, out = send(f"mail john@example{ch}com today", "WEB_SEARCH")
        assert refused or "john@example" not in out, (hex(cp), out)
    if label_sep and any(w in name.split() for w in ("HYPHEN", "DASH", "MINUS")):
        texts.append(f"key sk{ch}abcdefghijklmnop0123456789 invalid")      # only a dash makes "sk-" a key prefix
    for text in texts:
        refused, out = send(text, "WEB_SEARCH")
        assert refused and out == "", (hex(cp), text)
    refused, out = send(f"ssn 123{ch}45{ch}6789", "WEB_SEARCH")
    assert refused or "123456789" not in digits(out), hex(cp)


def test_fb3_r1_03_lookalikes_are_sent_as_ascii():
    assert C.canonical("call 415\u2010555\u20100199 or mail john@example\u3002com") == "call 415-555-0199 or mail john@example.com"


# --- FB3 R1-04: standard-form recall -----------------------------------------------------------------------------------
@pytest.mark.parametrize("text,cat", [
    ("call 987 654 3210", "CONTACT"), ("phone 415 555 0199", "CONTACT"), ("020 7946 0958", "CONTACT"),
    ("9876543210 call me", "CONTACT"), ("write to jos\u00e9@example.com", "CONTACT"),
    ("j\u00fcrgen.m\u00fcller@example.de", "CONTACT"), ("mail ravi@ex\u00e4mple.in", "CONTACT"),
    ("pw: Mango#2026!", "CREDENTIAL"), ("OTP is 4 8 2 9 1 3", "CREDENTIAL"), ("cvv: 1 2 3", "CREDENTIAL"),
    ("my passport is A1234567", "GOV_ID"), ("ABCPE 1234 F", "GOV_ID"), ("234567890124 is my aadhaar", "GOV_ID"),
])
def test_fb3_r1_04_standard_forms_are_detected(text, cat):
    assert cat in classify(text).categories(), text


# --- FB3 R1-05: the narrowed long-number rule keeps ordinary queries ---------------------------------------------------
NUMBER_BENIGN = [
    "amazon order 171-5550123-9876543", "order #402-1234567-1234567", "invoice INV-2026-000123-4567",
    "uuid 123e4567-e89b-12d3-a456-426614174000", "timestamps 1698000000 1698003600", "time 10:30-11:45, 12:00-13:15",
    "dates 01.02.2026 03.04.2026", "lottery numbers 04 11 23 35 42 48 07 19", "sequence 1, 2, 3, 4, 5, 6, 7, 8, 9, 10",
    "pi 3.14159265358979323846", "e 2.718281828459045", "total 1,234,567,890 units", "1,23,45,678 rupees",
    "near 12.9716, 77.5946", "ISBN 978-0-306-40615-7", "meeting 2026-10-22 14:30:00", "server 192.168.100.200",
    "pages 12345 to 67890", "between 2020 and 2026 we sold 15000 units", "train 12627 at 19:20 on 2026-10-22",
    "(080) 2345 6789 is closed today?", "resolution 1920x1080 at 60fps", "version 10.0.26200.6584 build",
    "flight UK 812 on 23/10/2026 at 06:05", "temperature 23.5 C at 10:15:44", "phone 1-800 support hours 9-17",
    "item code 4006381333931", "IMEI 490154203237518 on the box", "batch 4500012345 failed QC",
]
DOCUMENTED_EXCEPTIONS = {"(080) 2345 6789 is closed today?"}       # a phone number: CONTACT, redacted by design


@pytest.mark.parametrize("q", NUMBER_BENIGN)
def test_fb3_r1_05_number_shaped_benign_queries_are_unchanged(q):
    refused, out = send(q, "WEB_SEARCH")
    if q in DOCUMENTED_EXCEPTIONS:
        return
    assert not refused and out == " ".join(q.split()), (q, out)


def test_fb3_r1_05_card_layout_is_still_redacted():
    assert send("range 1000-2000-3000-4000 meters", "WEB_SEARCH")[1] == "range [redacted] meters"   # 4-4-4-4 by design


# --- FB3 R1-06: emoji and script shaping survive ------------------------------------------------------------------------
@pytest.mark.parametrize("text", ["Make a festive card with \u2764\ufe0f for the family",
                                  "family \U0001F468\u200d\U0001F469\u200d\U0001F467",
                                  "\u0645\u06cc\u200c\u062e\u0648\u0627\u0647\u0645 \u0628\u0631\u0648\u0645",
                                  "\u0d28\u0d3f\u0d7c\u0d2e\u0d4d\u0d2e\u0d3e\u0d23\u0d02"])
def test_fb3_r1_06_shaping_characters_are_kept_and_not_refused(text):
    refused, out = send(text, "EXTERNAL_AGENT")
    assert not refused and out == unicodedata.normalize("NFKC", text)


def test_fb3_r1_06_harness_approval_accepts_emoji_and_nbsp(monkeypatch, tmp_path):
    from tests.privacy.test_c3_repairs import FakeTurns, TurnError, _worker_fns, approval
    monkeypatch.setenv("URI_PRIVACY_HOME", str(tmp_path / "privacy"))
    import uri_privacy.gateway as G
    monkeypatch.setattr(G, "_default", None)
    fns = _worker_fns()[0]
    for instr in ("Make a festive card with \u2764\ufe0f into out.txt", "write\u00a0a summary into out.txt"):
        ok = approval(instr)
        assert fns["harness_approval_private"]("turn_start", ok, FakeTurns(), TurnError) is ok


# --- decoded-only and literal readings ----------------------------------------------------------------------------------
def test_encoded_sensitive_value_is_refused_but_ordinary_urls_pass():
    assert send("password%3DMango%232026", "WEB_SEARCH")[0]
    refused, out = send("docs at https://example.com/a%20b?x=1&amp;y=2", "WEB_SEARCH")
    assert not refused and "%20" in out


# --- C4-01: whole-match spans --------------------------------------------------------------------------------------------
def test_c4_01_id_shape_redacts_the_digits_not_the_separator():
    out = send("card 4111 1111 1111 11119", "WEB_SEARCH")[1]
    assert out in ("card [redacted]", "")


# --- local destinations stay exact --------------------------------------------------------------------------------------
@pytest.mark.parametrize("q", ["card 4111\u200b1111\u200b1111\u200b1111", "password\u2236 Mango#2026!",
                               "aadhaar_2345_6789_0124.pdf", "\u2764\ufe0f"])
def test_local_destinations_are_unchanged(q):
    for dest in ("LOCAL_BRAIN", "LOCAL_TOOL"):
        assert TGateway().prepare(q, requester="t", destination=dest, purpose="p").text == q
