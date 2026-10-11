"""Regressions for review R6 of 08a4569 (finding R6-02). Each fails without its repair.

A code value written in space-separated groups ("482 913") in a field labelled or named "... code", and card
security code fields named CVD / CSV / CAV2 / CID (as well as CVV / CVC), are sensitive in Python, in the in-page layer
(real Chromium) and never reach the Brain request.
"""
import html
import json
import re

import pytest

from uri_assist import redact as RD

from .test_a0_access_perception import FakeClient, ask_and_wait, dom_snapshot, grant, mk
from .test_a0_r1_review_regressions import ROOT, _chromium

FIELDS = (("sms_code", "SMS code", "482 913"), ("code", "Code", "482 913"), ("otp_entry", "Enter code", "48 29 13"),
          ("verify_code", "Verification code", "482 913"), ("backup_code", "Backup code", "a7f3 9k2d 1m8x"),
          ("cvd_value", "CVD", "371"), ("csv", "CSV", "372"), ("cav2", "CAV2", "373"), ("cid", "CID", "3741"),
          ("cardCvd", "Card CVD", "374"), ("cvc2", "CVC2", "375"), ("cvv2", "CVV2", "376"))
# Values that are not codes, and fields with no secret signal, stay readable.
READABLE = (("company_code", "Company code", "Asha Rao and Partners of the North Region Ltd"),
            ("comments", "Comments", "481 000"), ("postal_code", "Postal code", "560 001"),
            ("promo_code", "Promo code", "SAVE 20"), ("city", "City", "New Delhi"),
            ("description", "Description", "Price 371 rupees"))


@pytest.mark.parametrize("name, label, value", FIELDS)
def test_r6_02_spaced_codes_and_card_codes_are_sensitive(name, label, value):
    assert RD.field_is_sensitive({"type": "text", "name": name, "value": value})
    assert RD.field_is_sensitive({"type": "text", "name": "f1", "label": label, "value": value})


@pytest.mark.parametrize("name, label, value", READABLE)
def test_r6_02_ordinary_fields_stay_readable(name, label, value):
    assert not RD.field_is_sensitive({"type": "text", "name": name, "label": label, "value": value})


def test_r6_02_in_page_rules_are_the_python_rules():
    js = (ROOT / "uri_assist/browser_extension/snapshot.js").read_text()
    assert re.search(r"const SENSITIVE_WORDS = /(.*?)/;", js).group(1) == RD._SENSITIVE_WORDS.pattern
    assert re.search(r"const STEMS = /(.*?)/;", js).group(1) == RD._STEMS.pattern
    assert re.search(r"SHORT_CODE = /(.*?)/,", js).group(1) == RD._SHORT_CODE.pattern


def test_r6_02_in_page_layer_hides_the_values(tmp_path):
    page = tmp_path / "r6.html"
    page.write_text("<!doctype html><html><body><form>" +
                    "".join(f'<label for="f{i}">{html.escape(lb)}</label><input id="f{i}" name="{html.escape(n)}" '
                            f'value="{html.escape(v)}">' for i, (n, lb, v) in enumerate(FIELDS)) +
                    "".join(f'<label for="r{i}">{html.escape(lb)}</label><input id="r{i}" name="{html.escape(n)}" '
                            f'value="{html.escape(v)}">' for i, (n, lb, v) in enumerate(READABLE)) +
                    "</form></body></html>")
    s = _chromium(str(page))["snapshot"]
    by_id = {f["id"]: f for f in s["fields"]}
    for i, (n, lb, v) in enumerate(FIELDS):
        assert by_id[f"f{i}"]["sensitive"] is True and by_id[f"f{i}"]["value"] == "", n
    for i, (n, lb, v) in enumerate(READABLE):
        assert (by_id[f"r{i}"].get("withheld") is None and by_id[f"r{i}"]["value"] == v) if RD.SHAREABLE_NAME.match(RD._joined(n)) \
            else (by_id[f"r{i}"].get("withheld") == "not_shared" and by_id[f"r{i}"]["value"] == ""), n   # D8
    raw = json.dumps(s)
    for n, lb, v in FIELDS:
        assert f'"{v}"' not in raw, n


def test_r6_02_values_never_reach_the_brain_request():
    fields = [{"id": f"f{i}", "type": "text", "name": n, "label": lb, "value": v,
               "rect": {"x": 1, "y": 1, "w": 2, "h": 2}} for i, (n, lb, v) in enumerate(FIELDS)]
    client = FakeClient(text="This page asks for a code.")
    br, _ = mk(snap=dom_snapshot(fields=fields, text="Enter the code we sent you."), client=client)
    grant(br, perms=("observe",))
    out = ask_and_wait(br, "What does this page need?")
    assert out["status"] == "COMPLETE" and client.bodies
    body = json.dumps(client.bodies)
    for n, lb, v in FIELDS:
        assert f"{lb}: {v}" not in body and v not in body, n
