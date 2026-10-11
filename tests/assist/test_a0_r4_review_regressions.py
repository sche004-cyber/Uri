"""Regressions for review R4 of 1615512 (finding R4-01). Each fails without its repair.

R1-R3 closed the reviewer's example names and built their corpus from the implementation's own stem list, so a stem
the rules lacked could never appear in it. The corpus here is written independently of uri_assist/redact.py: secret
field names as vendors, password managers and identity forms spell them (environment-variable style API keys, key
material, recovery and backup codes, session values, national IDs), each in snake_case, camelCase, kebab-case,
UPPER_SNAKE and run-together lowercase, with alphanumeric values. It is checked in Python, in the in-page layer (real
Chromium) and in the Brain request body that assist_ask sends.
"""
import html
import json
import re

import pytest

from uri_assist import access as AC
from uri_assist import perception as PE
from uri_assist import redact as RD

from .test_a0_access_perception import FakeClient, ask_and_wait, dom_snapshot, grant, mk
from .test_a0_r1_review_regressions import ROOT, _chromium

# Secret field names, as word lists (not regex stems). Sources: vendor credential names (Stripe, OpenAI, Anthropic,
# AWS, GitHub, Slack, Twilio, SendGrid, Google), password-manager / OWASP sensitive-field names, 2FA recovery flows and
# national-ID forms. The names cited in R4-01 are included.
SECRET_WORDS = (
    ("stripe", "api", "key"), ("stripe", "secret", "key"), ("stripe", "publishable", "key"), ("openai", "api", "key"),
    ("anthropic", "api", "key"), ("google", "api", "key"), ("sendgrid", "api", "key"), ("my", "api", "key"),
    ("user", "api", "key"), ("x", "api", "key"), ("api", "key"), ("aws", "access", "key", "id"),
    ("aws", "secret", "access", "key"), ("access", "key"), ("access", "key", "id"), ("github", "token"),
    ("github", "pat"), ("personal", "access", "token"), ("slack", "bot", "token"), ("twilio", "auth", "token"),
    ("refresh", "token"), ("id", "token"), ("bearer", "token"), ("csrf", "token"), ("xsrf", "token"), ("jwt",),
    ("client", "secret"), ("webhook", "secret"), ("signing", "secret"), ("signing", "key"), ("encryption", "key"),
    ("master", "key"), ("session", "key"), ("client", "key"), ("hmac", "key"), ("shared", "key"),
    ("license", "key"), ("product", "key"), ("private", "key"), ("private", "key", "pem"), ("priv", "key"),
    ("ssh", "key"), ("pgp", "private", "key"), ("passkey",), ("wifi", "psk"), ("pre", "shared", "key"),
    ("credential",), ("credentials",), ("db", "credentials"), ("seed", "phrase"), ("mnemonic",),
    ("wallet", "mnemonic"), ("recovery", "phrase"), ("recovery", "code"), ("recovery", "codes"), ("recovery", "key"),
    ("backup", "code"), ("backup", "codes"), ("reset", "code"), ("unlock", "code"), ("session", "id"),
    ("session", "token"), ("cookie",), ("auth", "cookie"), ("ssn",), ("social", "security", "number"),
    ("aadhaar", "number"), ("aadhar", "no"), ("passport", "number"), ("iban",), ("card", "number"),
    ("account", "number"), ("security", "answer"), ("mothers", "maiden", "name"), ("totp", "secret"),
    ("authenticator", "secret"), ("one", "time", "password"), ("national", "id"), ("tax", "id"),
    ("routing", "number"), ("bank", "account"), ("sess", "id"), ("nonce",),
)


def _forms(words):
    cap = [w.capitalize() for w in words]
    return {"_".join(words), words[0] + "".join(cap[1:]), "-".join(words), "_".join(words).upper(), "".join(words)}


SECRET_NAMES = sorted({n for w in SECRET_WORDS for n in _forms(w)})
# Labels a recovery / backup / access code field shows, with a code that is not all digits (R4-01).
CODE_LABELS = ("Recovery code", "Backup code", "Enter code", "Enter the 8-character code", "Security key",
               "Verification code", "Your access key", "Gift card PIN", "Unlock key")
CODE_VALUES = ("7f3a9-2c1d8", "Zx9-kq_7Lm", "Aa11Bb22Cc", "ABCD-EFGH", "kq7lm")
# Ordinary fields (not derived from any rule list) that must stay readable with ordinary values.
READABLE = (("firstName", "Asha"), ("last_name", "Rao"), ("email", "asha@example.org"), ("city", "Pune"),
            ("street_address", "12 MG Road"), ("company", "Acme"), ("search", "laptop bags"), ("q", "weather"),
            ("keyword", "laptop"), ("keywords", "laptop bag"), ("keyboard_layout", "US"), ("notes", "call after 5"),
            ("message", "Hello there"), ("title", "Dr"), ("quantity", "3"), ("promoCode", "SUMMER25"),
            ("countryCode", "IN"), ("currency_code", "INR"), ("language_code", "en-GB"), ("zipcode", "411001"),
            ("postalCode", "SW1A1AA"), ("author", "Tagore"), ("account", "personal"), ("hotpot", "spicy"),
            ("footpath", "left"), ("monkey", "capuchin"), ("turkey", "roast"), ("nightfall", "late"),
            ("secretary", "Mr Iyer"), ("username", "asha_r"))


def _value(i):
    return f"Qv{i:03d}Lm-x7"


@pytest.mark.parametrize("name", SECRET_NAMES)
def test_r4_01_secret_names_are_sensitive_with_alphanumeric_values(name):
    for value in ("Zx9-kq_7Lm", "sk_live_51HxYz", "hunter2", ""):
        assert RD.field_is_sensitive({"type": "text", "name": name, "value": value}), value
    for key in ("label", "placeholder", "aria_label", "id"):
        assert RD.field_is_sensitive({"type": "text", "name": "f1", key: name, "value": "Zx9-kq_7Lm"}), key


@pytest.mark.parametrize("label", CODE_LABELS)
def test_r4_01_alphanumeric_codes_in_code_or_key_fields_are_sensitive(label):
    for value in CODE_VALUES:
        assert RD.field_is_sensitive({"type": "text", "name": "f1", "label": label, "value": value}), value


@pytest.mark.parametrize("name, value", READABLE)
def test_r4_01_ordinary_fields_stay_readable(name, value):
    assert not RD.field_is_sensitive({"type": "text", "name": name, "label": name, "value": value})


def test_r4_01_code_label_does_not_hide_checkbox_state():
    assert not RD.field_is_sensitive({"type": "checkbox", "name": "agree", "label": "I accept the code of conduct",
                                      "value": "checked"})


def test_r4_01_in_page_patterns_are_the_python_patterns():
    js = (ROOT / "uri_assist/browser_extension/snapshot.js").read_text()
    for js_name, rx in (("STEMS", RD._STEMS), ("PHRASES", RD._PHRASES), ("CODE_END", RD._CODE_END),
                        ("CODE_EXCLUDE", RD._CODE_EXCLUDE)):
        m = re.search(rf"\b{js_name} = /(.*?)/[,;]", js)
        assert m and m.group(1) == rx.pattern, js_name
    assert re.search(r"\bREADABLE = /(.*?)/g;", js).group(1) == RD._READABLE.pattern
    assert re.search(r"SHORT_CODE = /(.*?)/,", js).group(1) == RD._SHORT_CODE.pattern


def _rows():
    rows = [(f"s{i}", n, "Entry", _value(i)) for i, n in enumerate(SECRET_NAMES)]
    rows += [(f"c{i}", "f", lb, v) for i, (lb, v) in enumerate((lb, v) for lb in CODE_LABELS for v in CODE_VALUES)]
    rows += [(f"o{i}", n, n, v) for i, (n, v) in enumerate(READABLE)]
    return rows


def _pages(tmp_path, rows):
    for k in range(0, len(rows), 190):          # snapshot.js keeps the first 200 fields
        page = tmp_path / f"r4_{k}.html"
        page.write_text("<!doctype html><html><body><form>" + "\n".join(
            f'<label for="{fid}">{html.escape(lb)}</label>'
            f'<input id="{fid}" name="{html.escape(n)}" value="{html.escape(v)}">' for fid, n, lb, v in rows[k:k + 190])
            + "</form></body></html>")
        yield page, rows[k:k + 190]


def test_r4_01_in_page_layer_hides_corpus_and_matches_python(tmp_path):
    rows, checked = _rows(), 0
    for page, part in _pages(tmp_path, rows):
        s = _chromium(str(page))["snapshot"]
        raw = json.dumps(s)
        by_id = {f["id"]: f for f in s["fields"]}
        py = {f["id"]: f for f in PE.normalise({**s}, AC.Stamp("g", 1, "t", "dom", 0.0)).fields}
        for fid, n, lb, v in part:
            if fid[0] in "sc":
                assert json.dumps(v) not in raw and by_id[fid]["sensitive"] is True, (n, lb, v)
                # A code-labelled field reaches Python with its value already removed, so only the name rule can fire.
                assert py[fid]["sensitive"] is True or (fid[0] == "c" and py[fid]["value"] == ""), (n, lb)
            else:
                assert by_id[fid]["sensitive"] is False and by_id[fid]["value"] == v, n
                assert py[fid]["sensitive"] is False and py[fid]["value"] == v, n
            checked += 1
    assert checked == len(rows)


def test_r4_01_values_never_reach_the_brain_request():
    secret = [r for r in _rows() if r[0][0] in "sc"]
    fields = [{"id": fid, "type": "text", "name": n, "label": lb, "value": v, "rect": {"x": 1, "y": 1, "w": 2, "h": 2}}
              for fid, n, lb, v in secret]
    client = FakeClient(text="This page asks for credentials.")
    br, _ = mk(snap=dom_snapshot(fields=fields), client=client)
    grant(br, perms=("observe",))
    out = ask_and_wait(br, "What does this form need?")
    assert out["status"] == "COMPLETE" and client.bodies
    body = json.dumps(client.bodies)
    for fid, n, lb, v in secret:
        assert v not in body, (n, lb)
