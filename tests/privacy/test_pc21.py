"""V3.1 fallback review FB12 of a39c2fc4 (no STRUCTURAL finding; plan PC-21). Generated sweeps, synthetic values."""
import random

import pytest

from uri_privacy import PrivacyRefused

from .helpers import TGateway

DESTS = ("WEB_SEARCH", "EXTERNAL_AGENT", "LOG")


def send(text, dest):
    try:
        return False, TGateway().prepare(text, requester="t", destination=dest, purpose="p", reversible=False).text
    except PrivacyRefused as exc:
        return exc.code, ""


def _value(rng):
    letters = "abcdefghjkmnpqrstuvwxyzABCDEFGHJKLMNPQRSTUVWXYZ"
    return "".join(rng.choice(letters) for _ in range(6)) + rng.choice("#$!@%&") + str(rng.randint(10, 99))


# --- R1-01: compound / config keys with every separator ---------------------------------------------------------------
KEYS = ["DB_PASSWORD", "client_secret", "clientSecret", "AWS_SECRET_ACCESS_KEY", "mypassword", "api_key", "authToken",
        "SMTP_PASS", "private_key", "github_token", "db.password", "x-api-key"]
SEPS = [" is ", " was ", " - ", " -> ", " → ", " – ", " ", "\n", "\t", ", ", " (", " => "]


def test_fb12_r1_01_compound_keys_with_any_separator_never_carry_the_value():
    rng = random.Random(12)
    bad = []
    for key in KEYS:
        for sep in SEPS:
            v = _value(rng)
            t = f"the {key}{sep}{v}" + (")" if sep.endswith("(") else "") + " please"
            for dest in DESTS:
                refused, out = send(t, dest)
                if not refused and v in out:
                    bad.append((t, dest))
    assert bad == [], (len(bad), bad[:5])


@pytest.mark.parametrize("form", ["{v} is the DB_PASSWORD.", "{v} was our client_secret", "export DB_PASSWORD {v}"])
def test_fb12_r1_01_value_before_a_compound_key_and_export_forms(form):
    v = "Hunt3r2!xyz"
    for dest in DESTS:
        refused, out = send(form.format(v=v), dest)
        assert refused or v not in out, (form, dest, out)


# --- R1-02: "set / changed / reset my password to X" ------------------------------------------------------------------
def test_fb12_r1_02_set_or_changed_to_a_value_never_carries_it():
    rng = random.Random(122)
    verbs = ["I changed my {l} to {v}", "reset the {l} to {v} yesterday", "set my {l} to {v}", "updated the {l} as {v}",
             "changing the {l} to {v} did not help"]
    labels = ["password", "PIN", "passcode", "passphrase", "api key", "secret key", "token"]
    bad = []
    for _ in range(200):
        v = _value(rng) if rng.random() < 0.8 else str(rng.randint(1000, 999999))
        t = rng.choice(verbs).format(l=rng.choice(labels), v=v)
        for dest in DESTS:
            refused, out = send(t, dest)
            if not refused and v in out:
                bad.append((t, dest))
    assert bad == [], (len(bad), bad[:5])


@pytest.mark.parametrize("q", ["change password to something stronger", "set the timer to 10:30",
                               "reset password to default settings", "DB_PASSWORD environment variable not set",
                               "client_secret rotation guide", "export DB_PASSWORD from vault"])
def test_fb12_r1_01_r1_02_ordinary_phrasings_stay_readable(q):
    assert send(q, "WEB_SEARCH") == (False, q)


# --- R1-03: clock times and URLs after a password word are not label separators ----------------------------------------
def test_fb12_r1_03_login_help_with_times_and_urls_is_not_refused():
    rng = random.Random(123)
    refused = []
    for _ in range(400):
        when = rng.choice([f"{rng.randint(0, 23):02d}:{rng.randint(0, 59):02d}:{rng.randint(0, 59):02d}",
                           f"{rng.randint(0, 23):02d}:{rng.randint(0, 59):02d}", "https://example.com/help?q=reset"])
        q = f"{rng.choice(['password', 'passcode', 'my password manager'])} {rng.choice(['reset failed', 'not working', 'crashed'])} " \
            f"{rng.choice(['at', 'since', 'see'])} {when}"
        r, _ = send(q, "WEB_SEARCH")
        if r:
            refused.append(q)
    assert refused == [], (len(refused), refused[:5])


def test_fb12_r1_03_a_real_label_separator_still_counts():
    assert send("password reset: Hunt3r2!xyz", "WEB_SEARCH")[0]


# --- R1-04: Cyrillic ka, Greek kappa and tau in a label ----------------------------------------------------------------
@pytest.mark.parametrize("q", ["my api кey: Hunt3r2!xyzQ ok", "my api_кey=Hunt3r2!xyzQ", "api κey: Hunt3r2!xyzQ",
                               "τoken: Hunt3r2!xyzQ"])
def test_fb12_r1_04_lookalike_letters_in_key_labels_are_read(q):
    for dest in ("WEB_SEARCH", "LOG"):
        refused, out = send(q, dest)
        assert refused or "Hunt3r2" not in out, (q, dest, out)
