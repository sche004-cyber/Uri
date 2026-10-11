"""Regressions for review R3 of 627f6b9 (finding R3-01). Each fails without its repair.

R1 and R2 fixed the reviewer's example names one by one. These tests build names from a prefix list and a stem list
instead, so a name nobody cited is checked too, in Python and in the in-page layer (real Chromium).
"""
import html
import itertools
import json
import re

import pytest

from uri_assist import access as AC
from uri_assist import perception as PE
from uri_assist import redact as RD

from .test_a0_access_perception import dom_snapshot
from .test_a0_r1_review_regressions import ROOT, _chromium

PREFIXES = ("", "email", "sms", "user", "login", "card", "client", "access", "my", "new", "mobile", "account", "app")
SUFFIXES = ("", "code", "value", "key", "number", "Input")
# Secret stems: the field is sensitive whatever its value.
STEMS = ("otp", "mfa", "2fa", "onetime", "twofactor", "verification", "authenticator", "authentication", "cvv", "cvc",
         "ccv", "token", "secret", "password", "passcode", "passwd", "pwd")
NAME_ONLY = sorted({p + s + x for p, s, x in itertools.product(PREFIXES, STEMS, SUFFIXES)} |
                   {"tfa" + x for x in SUFFIXES} | {"TfaCode", "clientSecret", "AuthToken", "smsOneTimeCode"})
# Short codes: a short all-digit value in a field whose name ends in code or pin.
CODE_ENDINGS = ("code", "pin", "codeno", "pinnumber", "Code", "PIN")
SHORT_CODE = sorted({p + e for p, e in itertools.product(PREFIXES[1:] + ("bank", "wallet", "entry", "card"), CODE_ENDINGS)})

# The 16 names the diagnosis showed leaking at 627f6b9.
REPORTED = ("emailverificationcode", "mfacode", "onetimecode", "twofactorcode", "2facode", "tfacode",
            "authenticatorcode", "authenticationcode", "onetimepin", "smspin", "cardcode", "cardverificationcode",
            "authtoken", "accesstoken", "clientsecret", "secretkey")

# Readable even with an all-digit value.
READABLE = ("hotpot", "footpath", "hotplate", "spinner", "pinnacle", "pincode", "zipcode", "postcode", "countrycode",
            "areacode", "promocode", "couponcode", "vouchercode", "referralcode", "barcode", "sortcode", "ifsccode",
            "swiftcode", "author", "account", "secretary", "nightfall", "camping", "opinion", "quantity", "age",
            "postalCode", "country_code", "Promo code", "PIN code")


@pytest.mark.parametrize("name", REPORTED)
@pytest.mark.parametrize("value", ["482913", "123"])
def test_r3_01_reported_names_are_sensitive(name, value):
    assert RD.field_is_sensitive({"type": "text", "name": name, "value": value})


@pytest.mark.parametrize("name", NAME_ONLY)
def test_r3_01_stem_after_any_prefix_is_sensitive_whatever_the_value(name):
    for value in ("482913", "hunter2", ""):
        assert RD.field_is_sensitive({"type": "text", "name": name, "value": value}), value


@pytest.mark.parametrize("name", SHORT_CODE)
def test_r3_01_short_digit_value_in_a_code_or_pin_field_is_sensitive(name):
    for value in ("737", "9152", "482913", "48291300"):
        assert RD.field_is_sensitive({"type": "text", "name": name, "value": value}), value
    for key in ("label", "placeholder", "aria_label"):
        assert RD.field_is_sensitive({"type": "text", "name": "f1", key: name, "value": "482913"}), key


@pytest.mark.parametrize("label", ["Enter code:", "Card code *", "SMS PIN", "Code (6 digits)", "Your bank PIN"])
def test_r3_01_code_labels_with_punctuation(label):
    assert RD.field_is_sensitive({"type": "text", "name": "f1", "label": label, "value": "482913"})


@pytest.mark.parametrize("name", READABLE)
def test_r3_01_ordinary_names_still_readable(name):
    for value in ("x", "482913", "411001", "12"):
        assert not RD.field_is_sensitive({"type": "text", "name": name, "label": name, "value": value}), value


def test_r3_01_values_never_reach_the_brain_request():
    names = REPORTED + tuple(NAME_ONLY) + tuple(SHORT_CODE)
    fields = [{"type": "text", "name": n, "label": "x", "value": f"9{i:05d}", "rect": {"x": 1, "y": 1, "w": 2, "h": 2}}
              for i, n in enumerate(names)]
    obs = PE.normalise(dom_snapshot(fields=fields), AC.Stamp("g", 1, "t", "dom", 0.0))
    raw = json.dumps(list(obs.fields))
    for i, n in enumerate(names):
        assert f"9{i:05d}" not in raw, n
    assert all(f["sensitive"] for f in obs.fields)


def test_r3_01_in_page_patterns_are_the_python_patterns():
    js = (ROOT / "uri_assist/browser_extension/snapshot.js").read_text()
    for js_name, rx in (("STEMS", RD._STEMS), ("CODE_END", RD._CODE_END), ("CODE_EXCLUDE", RD._CODE_EXCLUDE),
                        ("SENSITIVE_WORDS", RD._SENSITIVE_WORDS), ("RUN_TOGETHER", RD._RUN_TOGETHER)):
        m = re.search(rf"\b{js_name} = /(.*?)/[,;]", js)
        assert m and m.group(1) == rx.pattern, js_name
    assert re.search(r"SHORT_CODE = /(.*?)/,", js).group(1) == RD._SHORT_CODE.pattern


def test_r3_01_in_page_layer_hides_reported_names_in_fixture():
    s = _chromium("tricky_fields.html")["snapshot"]
    raw = json.dumps(s)
    for i in range(1, 15):
        assert f'"93{i:04d}"' not in raw, i
    js_sensitive = {f["id"] or f["name"] for f in s["fields"] if f.get("withheld") == "sensitive"}  # D8: by reason
    assert {f"s{i}" for i in range(1, 15)} <= js_sensitive
    py = PE.normalise({**s}, AC.Stamp("g", 1, "t", "dom", 0.0))
    assert js_sensitive == {f.get("id") or f.get("name") for f in py.fields if f.get("withheld") == "sensitive"}


def _generated_pages(tmp_path):
    """All generated names as fixture pages of at most 190 fields (snapshot.js keeps the first 200)."""
    secret = REPORTED + tuple(NAME_ONLY) + tuple(SHORT_CODE)
    rows = [(f"s{i}", n, str(91000000 + i)) for i, n in enumerate(secret)]
    rows += [(f"o{i}", n, str(482900 + i)) for i, n in enumerate(READABLE)]
    for k in range(0, len(rows), 190):
        page = tmp_path / f"generated_{k}.html"
        page.write_text("<!doctype html><html><body><form>" + "\n".join(
            f'<label for="{fid}">{html.escape(n) if fid[0] == "o" else "Entry"}</label>'
            f'<input id="{fid}" name="{html.escape(n)}" value="{v}">' for fid, n, v in rows[k:k + 190])
            + "</form></body></html>")
        yield page, rows[k:k + 190]


def test_r3_01_in_page_layer_hides_generated_names(tmp_path):
    checked = 0
    for page, rows in _generated_pages(tmp_path):
        s = _chromium(str(page))["snapshot"]
        by_id = {f["id"]: f for f in s["fields"]}
        raw = json.dumps(s)
        py = {f["id"]: f for f in PE.normalise({**s}, AC.Stamp("g", 1, "t", "dom", 0.0)).fields}
        for fid, n, v in rows:
            if fid[0] == "s":
                assert f'"{v}"' not in raw and by_id[fid]["sensitive"] is True, n
                assert py[fid]["sensitive"] is True or py[fid]["value"] == "", n
            else:
                assert (by_id[fid].get("withheld") is None and by_id[fid]["value"] == v) if RD.SHAREABLE_NAME.match(RD._joined(n)) \
                    else (by_id[fid].get("withheld") == "not_shared" and by_id[fid]["value"] == ""), n   # D8
                assert (py[fid].get("withheld") is None and py[fid]["value"] == v) if RD.SHAREABLE_NAME.match(RD._joined(n)) \
                    else (py[fid].get("withheld") == "not_shared" and "value" not in py[fid]), n
            checked += 1
    assert checked == len(REPORTED) + len(NAME_ONLY) + len(SHORT_CODE) + len(READABLE)
