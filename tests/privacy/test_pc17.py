"""V3.1 fallback review FB8 of 83334676 (plan PC-17). Generated sweeps, synthetic values only."""
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


def wire(q):
    sent = []

    def capture(request):
        sent.append(json.loads(request.content)["query"])
        return httpx.Response(200, json={"results": []})
    TavilyProvider(api_key="test", transport=httpx.MockTransport(capture), privacy=TGateway()).search(q)
    return sent


# --- R2-01: credentials in config notations ------------------------------------------------------------------------------
KEYS = ["client_secret", "api_secret", "user_password", "db_password", "access_token", "refresh_token", "auth_token",
        "api_token", "bot_token", "AWS_SECRET_ACCESS_KEY", "private_key", "secret_key", "session_token",
        "master_password", "root_password", "clientSecret", "apiKey", "DB_PASSWORD", "x-api-key", "smtp.password",
        "github_token", "slack_bot_token", "credentials", "passphrase", "api-key"]
LAYOUTS = ["{k}: {v}", "{k}:{v}", "{k} = {v}", "{k}={v}", '"{k}": "{v}"', "'{k}': '{v}'", '{{"{k}": "{v}"}}',
           "<{k}>{v}</{k}>", "export {k}={v}", "  {k}: {v}  # yaml", '{k}="{v}"']


def test_fb8_r2_01_config_notations_never_carry_a_credential():
    rng = random.Random(8)
    bad = []
    for k in KEYS:
        for layout in LAYOUTS:
            v = "".join(rng.choice("abcdefghjkmnpqrstuvwxyzABCDEFGHJKLMNPQRSTUVWXYZ") for _ in range(8)) + str(rng.randint(10, 99))
            t = layout.format(k=k, v=v) + " not working"
            for dest in DESTS:
                refused, out = send(t, dest)
                if not refused and v in out:
                    bad.append((t, dest))
    assert bad == [], (len(bad), bad[:5])


def test_fb8_r2_01_reviewer_reproductions_never_reach_the_wire():
    for q in ("client_secret: Q7m2Zp9Lr4Ks8Tv1 invalid_client error", "DB_PASSWORD: hunter2x9 docker compose not working",
              '{"password": "abc123xyz789"}', "<password>abc123xyz</password>"):
        assert wire(q) == [], q


@pytest.mark.parametrize("q", ["client_secret: required field", "refresh_token: string", "access_token: <your token>",
                               "tokenizer: bert-base-uncased", "secret santa gift ideas 2024",
                               "keyboard shortcuts: ctrl+c"])
# ("password: field type" and "api_key: YOUR_API_KEY" are refused: a bare label joined to its value by a separator
# stays a credential under LDEC-007.)
def test_fb8_r2_01_documentation_phrasings_stay_readable(q):
    assert send(q, "WEB_SEARCH") == (False, q)


# --- R2-02: look-alike separators that normalize into an exempt IPv4:port or clock ---------------------------------------
def _maps_to(ch):
    return [chr(c) for c in range(0x80, 0x30000) if C._punct_ascii(chr(c)) == ch
            and unicodedata.normalize("NFKC", chr(c)) == chr(c)]


def test_fb8_r2_02_lookalike_separators_never_build_an_exempt_token_around_a_value():
    dots, colons = _maps_to("."), _maps_to(":")
    assert dots and colons
    bad = []
    for d in dots:
        for c in colons:
            t = f"card 41{d}111{d}111{d}111{c}11111 declined"
            for dest in ("WEB_SEARCH", "LOG"):
                refused, out = send(t, dest)
                if not refused and "4111111111111111" in digits(out):
                    bad.append((hex(ord(d)), hex(ord(c)), dest))
    assert bad == [], (len(bad), bad[:5])


@pytest.mark.parametrize("q", ["ssn 1ː23ː45։6789 form", "my aadhaar 23։45։67։89ː0124",
                               "card 41։111։111։111ː11111 declined"])
def test_fb8_r2_02_reviewer_reproductions_never_leave(q):
    for dest in DESTS:
        refused, out = send(q, dest)
        assert refused or len(digits(out)) < 9, (dest, out)


# --- R2-03: defanged and spaced e-mail ----------------------------------------------------------------------------------
@pytest.mark.parametrize("q", ["john.doe@example[.]com", "john.doe[@]example.com", "john.doe(@)example.com",
                               "john.doe@example(.)com", "john.doe @ example . com", "john.doe@example .com",
                               "john.doe@example. com", "john.doe{@}example{.}com"])
def test_fb8_r2_03_defanged_emails_are_redacted(q):
    for dest in ("WEB_SEARCH", "EXTERNAL_AGENT"):
        refused, out = send("contact " + q, dest)
        assert refused or "john" not in out, (dest, out)
    assert all("john" not in s for s in wire("contact " + q))


# --- R2-04 ---------------------------------------------------------------------------------------------------------------
@pytest.mark.parametrize("q", ["PAN ABCPE 1234-F", "PAN ABCPE.1234 F", "PAN ABCPE-1234 F"])
def test_fb8_r2_04_pan_with_mixed_separators_is_redacted(q):
    refused, out = send(q, "WEB_SEARCH")
    assert refused or "1234" not in out, out


@pytest.mark.parametrize("q", ["cvv2 123", "cvc2: 456", "pin: 12 34", "otp 48 29 13"])
def test_fb8_r2_04_code_word_forms_are_refused(q):
    for dest in ("WEB_SEARCH", "EXTERNAL_AGENT"):
        assert send(q, dest)[0], (q, dest)


def test_fb8_r2_04_short_spaced_numbers_after_pin_stay_readable():
    assert send("pin 1 2 hint", "WEB_SEARCH") == (False, "pin 1 2 hint")
