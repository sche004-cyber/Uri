"""V3.1 fallback review FB10 of bc4c8275 (no STRUCTURAL finding; plan PC-19). Generated sweeps, synthetic values."""
import random

import pytest

from uri_privacy import PrivacyRefused

from .helpers import TGateway


def send(text, dest):
    try:
        return False, TGateway().prepare(text, requester="t", destination=dest, purpose="p", reversible=False).text
    except PrivacyRefused as exc:
        return exc.code, ""


# --- R1-01: key, secret and token labels with every separator form ------------------------------------------------
LABELS = ["api key", "API key", "apikey", "api-key", "secret", "secret key", "token", "access token", "auth token",
          "bearer token", "refresh token", "client secret", "private key", "master key", "session token"]
SEPS = [": ", " is ", " = ", " - ", " -> ", " → ", " – ", " ", " (", ", ", ' "', " => "]


def test_fb10_r1_01_key_labels_with_any_separator_never_carry_the_value():
    rng = random.Random(10)
    alphabet = "abcdefghjkmnpqrstuvwxyzABCDEFGHJKLMNPQRSTUVWXYZ"
    bad = []
    for label in LABELS:
        for sep in SEPS:
            for _ in range(3):
                v = "".join(rng.choice(alphabet) for _ in range(6)) + rng.choice("#$!@%&") + str(rng.randint(10, 99))
                t = f"my {label}{sep}{v}" + (")" if sep.endswith("(") else "") + " stopped working"
                for dest in ("WEB_SEARCH", "LOG"):
                    refused, out = send(t, dest)
                    if not refused and v in out:
                        bad.append((t, dest))
    assert bad == [], (len(bad), bad[:5])


@pytest.mark.parametrize("q", ["token ERC-20 standard", "API key 2024 changes", "api key rotation best practice",
                               "the token expired yesterday", "secret santa 2024", "access token 30d expiry",
                               "refresh token 401 error"])
def test_fb10_r1_01_ordinary_key_phrasings_stay_readable(q):
    assert send(q, "WEB_SEARCH") == (False, q)


# --- R1-02: exempt tokens joined by any separator are not a disguise ----------------------------------------------------
def test_fb10_r1_02_exempt_tokens_with_any_joiner_are_never_refused():
    rng = random.Random(102)
    joiners = [" & ", "; ", "..", " → ", "), (", " / ", " | ", " + ", "; and "]
    refused = []
    for _ in range(600):
        y, mo, d = rng.randint(1990, 2039), rng.randint(1, 12), rng.randint(1, 28)
        tok = lambda: rng.choice([f"{y}-{mo:02d}-{rng.randint(1, 28):02d}", f"{rng.randint(1, 28):02d}/{mo:02d}/{y}",  # noqa: E731
                                  f"{rng.randint(0, 23):02d}:{rng.randint(0, 59):02d}",
                                  ".".join(str(rng.randint(0, 255)) for _ in range(4))])
        q = "on " + rng.choice(joiners).join(tok() for _ in range(rng.randint(2, 4)))
        r, out = send(q, "WEB_SEARCH")
        if r:
            refused.append(q)
    assert refused == [], (len(refused), refused[:5])


def test_fb10_r1_02_a_card_between_exempt_tokens_is_still_caught():
    for q in ("on 2026-10-23 & 4111;1111;1111;1111 & 2026-10-24", "10.0.0.1; 4111*1111*1111*1111; 10.0.0.2"):
        refused, out = send(q, "WEB_SEARCH")
        assert refused or "4111" not in out, (q, out)


# --- R1-03: a postal PIN code is an address ------------------------------------------------------------------------------
@pytest.mark.parametrize("q", ["koramangala pin code 560034", "pin code 560034 bank branches", "PIN Code: 560034 courier",
                               "what area has pin code 110001"])
def test_fb10_r1_03_postal_pin_codes_are_redacted_not_refused(q):
    refused, out = send(q, "WEB_SEARCH")
    assert not refused and "[redacted]" in out and "560034" not in out and "110001" not in out, (q, out)


def test_fb10_r1_03_one_time_codes_are_still_refused():
    for q in ("your verification code 482913", "code 482913", "otp 482913", "pin 4821"):
        assert send(q, "WEB_SEARCH")[0], q
