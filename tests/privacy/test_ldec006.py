"""Owner decision LDEC-006 (2026-10-23, "digit budget") and the V3.1 fallback review FB4 of fc9ac0c3
(docs/privacy/reviews/FB4_fallback_review_fc9ac0c3.txt).

Text bound for a non-local destination may not carry 9 or more digits in one run, whatever the grouping, separators
or line breaks; dates, clock times, ISO timestamps and IPv4 addresses are exempt. Generated sweeps, synthetic data.
"""
import itertools
import random
import string

import httpx
import pytest

from uri_privacy import PrivacyRefused
from uri_privacy import classify as C
from uri_privacy.classify import classify, fold
from uri_web import search as S

from .helpers import TGateway
from .synth import NUMBER_BENIGN

EXTERNAL = ("WEB_SEARCH", "EXTERNAL_AGENT", "EXTERNAL_MODEL")
CARD, AMEX, AADHAAR = "4539148803436467", "378282246310005", "234567890124"
STD_SEPS = [" ", "-", ".", "/", ",", ":", " - ", " / ", "\n", "_"]


def send(text, dest):
    """(refused?, text that would leave URI)."""
    try:
        return False, TGateway().prepare(text, requester="t", destination=dest, purpose="p", reversible=False).text
    except PrivacyRefused as exc:
        assert exc.code in ("PRIVACY_DISGUISE_REFUSED", "PRIVACY_REFUSED", "PRIVACY_ENCODING_UNRESOLVED"), exc.code
        return True, ""


def digits(s):
    return "".join(ch for ch in fold(s)[0] if ch.isdigit())


def compositions(n, k_max=4):
    """Every split of n digits into 2..k_max groups."""
    for k in range(2, k_max + 1):
        for cuts in itertools.combinations(range(1, n), k - 1):
            yield [b - a for a, b in zip((0,) + cuts, cuts + (n,))]


def grouped(value, sizes, seps):
    out, i = [], 0
    for j, n in enumerate(sizes):
        out.append(value[i:i + n])
        i += n
        if j < len(sizes) - 1:
            out.append(seps[j % len(seps)])
    return "".join(out)


def leaks(text, value, dest):
    refused, out = send(text, dest)
    return not refused and value in digits(out)


# --- R1-01: every grouping of a card or an Aadhaar, standard separators -------------------------------------------------
@pytest.mark.parametrize("value,label", [(CARD, "card"), (AMEX, "amex card"), (AADHAAR, "my aadhaar is")])
def test_fb4_r1_01_no_grouping_with_standard_separators_leaks(value, label):
    texts = [f"{label} {grouped(value, sizes, [sep])} declined"
             for sizes in compositions(len(value)) for sep in STD_SEPS]
    assert len(texts) > 2000
    bad = [t for t in texts if leaks(t, value, "WEB_SEARCH")]
    assert bad == [], (len(bad), bad[:5])


# --- R1-02: mixed separators, letters and line breaks -------------------------------------------------------------------
def test_fb4_r1_02_mixed_separators_letters_and_newlines_do_not_leak():
    rng = random.Random(6)
    gaps = ["x", "ab", " ", "\n", "*", "..", "x ", " x ", "-\n", "_", "#", "|", ";", "~", "\t"]
    texts = ["card 4539x1488 0343x6467 declined", "card 4539..1488x0343 6467", "card 4539*1488\n0343*6467",
             "my credit card number is 442x9x71798x2174"]
    for _ in range(3000):
        sizes = rng.choice(list(compositions(16, 6)) if rng.random() < 0.02 else list(compositions(16, 4)))
        texts.append("card " + grouped(CARD, sizes, [rng.choice(gaps) for _ in sizes]) + " ok")
    for dest in EXTERNAL + ("LOG",):
        bad = [t for t in texts if leaks(t, CARD, dest) and t != "my credit card number is 442x9x71798x2174"]
        assert bad == [], (dest, len(bad), bad[:5])
    refused, out = send("my credit card number is 442x9x71798x2174", "WEB_SEARCH")
    assert refused or "71798" not in out


def test_fb4_r1_02_final_text_is_rechecked_after_whitespace_collapse():
    # A direct WEB_SEARCH prepare() collapses whitespace; the result must not be something the gateway refuses as input.
    for q in ("card 4539*1488\n0343*6467", "pay 4539x1488\n\n0343x6467 now"):
        refused, out = send(q, "WEB_SEARCH")
        assert refused or CARD not in digits(out)
        if not refused:                       # what is sent is something the gateway itself accepts as input
            assert not send(out, "WEB_SEARCH")[0], (q, out)


def test_fb4_r1_06_value_split_around_another_value_is_refused():
    for dest in EXTERNAL:
        assert send("card 4111 1111 a@b.co 1111 1111 limit", dest)[0], dest


# --- R1-03: combining marks that NFKC composes ---------------------------------------------------------------------------
def test_fb4_r1_03_no_combining_mark_hides_a_password_label():
    bad = []
    for cp in range(0x0300, 0x0370):
        for i in range(1, len("password") + 1):
            t = "password"[:i] + chr(cp) + "password"[i:] + ": Mango#2026!"
            for dest in ("WEB_SEARCH", "EXTERNAL_AGENT"):
                refused, out = send(t, dest)
                if not refused and "Mango#2026" in out:
                    bad.append((hex(cp), i, dest))
    assert bad == [], bad[:10]
    assert send("pásswörd: Mango#2026!", "WEB_SEARCH")[0]


def test_fb4_r1_03_accented_prose_is_unchanged():
    for q in ("café au lait near München", "naïve résumé tips", "São Paulo weather"):
        refused, out = send(q, "WEB_SEARCH")
        assert not refused and out == q


# --- R1-04: credential phrasings, SSN label after, contiguous phones --------------------------------------------------
@pytest.mark.parametrize("q", ["use phwngv31# as the password", "phwngv31# is my password", "my password's phwngv31#",
                               "user asha pass Mango#2026", "wifi pw Mango#2026", "\"Mango#2026\" is the wifi password",
                               "login asha pass Mango#2026 thanks"])
def test_fb4_r1_04_value_before_label_credentials_are_refused(q):
    for dest in EXTERNAL:
        assert send(q, dest)[0], (q, dest)
    assert "Mango#2026" not in send(q, "LOG")[1] and "phwngv31" not in send(q, "LOG")[1]


@pytest.mark.parametrize("q,value", [("123456789 is my ssn", "123456789"), ("123-45-6789 is my SSN", "123456789"),
                                     ("tel 4155550199", "4155550199"), ("call 9876 543 210", "9876543210"),
                                     ("call 98 7654 3210", "9876543210")])
def test_fb4_r1_04_ssn_and_phone_forms_do_not_leak(q, value):
    for dest in EXTERNAL:
        assert not leaks(q, value, dest), (q, dest)


@pytest.mark.parametrize("q", ["how to pass 2026 exams", "pass COVID tests at the airport", "the password policy is strict",
                               "password field is required.", "sk-learn tutorial for beginners", "the pin is on the map",
                               "is my password strong enough?"])
def test_fb4_r1_04_ordinary_phrasings_stay_readable(q):
    refused, out = send(q, "WEB_SEARCH")
    assert not refused and out == q, (q, out)


# --- R1-05: split keys and PANs ----------------------------------------------------------------------------------------
def _split(s, n, sep):
    return sep.join(s[i:i + n] for i in range(0, len(s), n))


def test_fb4_r1_05_split_api_keys_and_pans_do_not_leak():
    rng = random.Random(7)
    alnum = string.ascii_uppercase + string.digits
    bad, n = [], 0
    for prefix, body_len in (("AKIA", 16), ("AIza", 35), ("ghp_", 36), ("glpat-", 20), ("xoxb-", 24), ("sk-", 40),
                             ("tvly-", 32), ("sk_live_", 24)):
        for _ in range(30):
            body = "".join(rng.choice(alnum + "abcdefghijk") for _ in range(body_len))
            if sum(c.isdigit() for c in body) < 3 or not any(c.isalpha() for c in body):
                body = "7Q9" + body[3:]
            for g, sep in ((4, " "), (4, "-"), (5, " "), (6, " ")):
                key = prefix + _split(body, g, sep)
                n += 1
                for dest in EXTERNAL:                     # a known-prefix key is CREDENTIAL: refused
                    if not send(f"key {key} leaked", dest)[0]:
                        bad.append((dest, key))
    assert n > 900 and bad == [], bad[:5]
    for pan in ("ABCP E123 4F", "ABCPE 1234 F", "A B C P E 1 2 3 4 F", "ABC PE12 34F"):
        for dest in EXTERNAL:
            refused, out = send(f"my PAN is {pan}", dest)
            assert refused or "ABCP" not in out.replace(" ", ""), (pan, dest, out)


# --- R1-07: the digit budget, and its exempt classes -------------------------------------------------------------------
# These NUMBER_BENIGN queries carry 9+ digits in one run and are redacted by decision. Pinned, so the exempt filter
# in test_ldec005 cannot quietly widen.
BUDGET_REDACTED = {
    "amazon order 171-5550123-9876543", "order #402-1234567-1234567", "invoice INV-2026-000123-4567",
    "uuid 123e4567-e89b-12d3-a456-426614174000", "timestamps 1698000000 1698003600",
    "lottery numbers 04 11 23 35 42 48 07 19", "sequence 1, 2, 3, 4, 5, 6, 7, 8, 9, 10", "pi 3.14159265358979323846",
    "e 2.718281828459045", "total 1,234,567,890 units", "near 12.9716, 77.5946", "ISBN 978-0-306-40615-7",
    "version 10.0.26200.6584 build", "item code 4006381333931", "IMEI 490154203237518 on the box",
    "batch 4500012345 failed QC",
    "base dddd13d302b06505e4afadeaa91678c62a71792766fdf3f886804ebc30def938",   # SECRET_LIKE as well
}


def test_ldec006_budget_classes_are_exactly_the_pinned_ones():
    hit = {q for q in NUMBER_BENIGN if C._long_number_spans(fold(q)[0])}
    assert hit == BUDGET_REDACTED, (hit - BUDGET_REDACTED, BUDGET_REDACTED - hit)
    for q in BUDGET_REDACTED:
        refused, out = send(q, "WEB_SEARCH")
        assert not refused and "[redacted]" in out, (q, out)


def _gen_exempt(rng):
    y, mo, d = rng.randint(1990, 2039), rng.randint(1, 12), rng.randint(1, 28)
    h, mi, s = rng.randint(0, 23), rng.randint(0, 59), rng.randint(0, 59)
    ip = ".".join(str(rng.randint(0, 255)) for _ in range(4))
    return rng.choice([
        f"meeting {y}-{mo:02d}-{d:02d} {h:02d}:{mi:02d}:{s:02d} in room {rng.randint(1, 99)}",
        f"due {y}-{mo:02d}-{d:02d}T{h:02d}:{mi:02d}:{s:02d}+05:30 local",
        f"logged {y}-{mo:02d}-{d:02d}T{h:02d}:{mi:02d}:{s:02d}.{rng.randint(0, 999999):06d}Z",
        f"server {ip}:{rng.randint(1, 65535)} is down", f"ping {ip} and {'.'.join(str(rng.randint(0, 255)) for _ in range(4))}",
        f"on {d:02d}/{mo:02d}/{y} at {h:02d}:{mi:02d}", f"from {d:02d}.{mo:02d}.{y} to {d:02d}.{mo:02d}.{y + 1}",
        f"slots {h:02d}:{mi:02d}-{(h + 1) % 24:02d}:{mi:02d}, {(h + 2) % 24:02d}:00-{(h + 3) % 24:02d}:30",
        f"stay {y}-{mo:02d}-{d:02d}/{y}-{mo:02d}-{d + 1:02d}", f"build {y}{mo:02d}{d:02d}T{h:02d}{mi:02d}{s:02d}Z",
        f"train {rng.randint(10000, 99999)} at {h:02d}:{mi:02d} on {y}-{mo:02d}-{d:02d}",
        f"top {rng.randint(2, 99)} movies of {y}", f"price {rng.randint(1, 99999)}.{rng.randint(0, 99):02d} rupees",
    ])


def test_ldec006_exempt_classes_are_unchanged_on_generated_samples():
    rng = random.Random(11)
    samples = [_gen_exempt(rng) for _ in range(2000)]
    changed = []
    for q in samples:
        refused, out = send(q, "WEB_SEARCH")
        if refused or out != q:
            changed.append((q, out))
    assert changed == [], (len(changed), changed[:5])


def test_ldec006_a_card_hidden_among_exempt_tokens_is_still_counted():
    for q in ("on 2026-10-23 4539 1488 0343 6467 ok", "4539 1488 2026-10-23 0343 6467", "4539 10:30 1488 0343 6467"):
        assert not leaks(q, CARD, "WEB_SEARCH"), q


def test_ldec006_digit_budget_boundary():
    assert not C._long_number_spans("ref 12345678 ok")
    assert C._long_number_spans("ref 123456789 ok")
    assert not C._long_number_spans("ref 1234 and 56789 ok")              # " and " is not a bridging gap
    assert C._long_number_spans("ref 1234 x 56789 ok")


def test_ldec006_linear_on_long_inputs():
    import time
    for text in ("1 " * 50000, "1x" * 50000, "1-" * 30000 + "a" * 30000, "12:34 " * 20000):
        t0 = time.perf_counter()
        C._long_number_spans(text)
        assert time.perf_counter() - t0 < 1.0


# --- R1-08: keycap emoji -------------------------------------------------------------------------------------------------
def test_fb4_r1_08_keycap_emoji_are_not_a_disguise():
    q = "1️⃣ 2️⃣ 3️⃣ steps #️⃣ *⃣"
    for dest in EXTERNAL:
        refused, out = send(q, dest)
        assert not refused and out == q, dest


def test_fb4_r1_08_keycaps_do_not_carry_a_card():
    q = "card " + " ".join(d + "️⃣" for d in CARD)
    for dest in EXTERNAL:
        assert not leaks(q, CARD, dest), dest


# --- end to end: the Tavily wire --------------------------------------------------------------------------------------------
def test_fb4_wire_carries_none_of_the_reproductions():
    sent = []

    def handler(request):
        sent.append(request.content.decode("utf-8", "replace"))
        return httpx.Response(200, json={"results": []})
    provider = S.TavilyProvider(api_key="k", transport=httpx.MockTransport(handler), privacy=TGateway())
    for q in ("card 45391488/03436467 declined", "card 4539:148803436467 declined", "my aadhaar is 234567 890124 update",
              "card 4539x1488 0343x6467 declined", "pássword: Mango#2026!", "AKIA TWII 6XUU IX2C IXU3 leaked",
              "my PAN is ABCP E123 4F", "tel 4155550199"):
        try:
            provider.search(q)
        except Exception:                                    # noqa: BLE001 - a refusal is fine, the wire is what counts
            pass
    wire = "\n".join(sent)
    for v in ("45391488", "03436467", "148803436467", "890124", "Mango#2026", "TWII", "E123", "4155550199"):
        assert v not in wire, v


# --- R1-06: residual classes that were cheap to close --------------------------------------------------------------------
@pytest.mark.parametrize("label", ["P@ssword", "passw0rd", "pass-word", "pass_word", "Pa55word", "PASS WORD"])
def test_fb4_r1_06_password_label_spellings_are_refused(label):
    for dest in EXTERNAL:
        assert send(f"{label}: Mango#2026!", dest)[0], (label, dest)


def test_fb4_r1_06_ordinary_password_words_stay_readable():
    for q in ("reset my pass-word please", "pass word field", "the password policy is strict"):
        assert send(q, "WEB_SEARCH") == (False, q)


def test_fb4_r1_06_indic_local_part_is_redacted_whole():
    q = "contact \u0905\u0928\u093f\u0932@example.in today"
    refused, out = send(q, "WEB_SEARCH")
    assert not refused and out == "contact [redacted] today", out
