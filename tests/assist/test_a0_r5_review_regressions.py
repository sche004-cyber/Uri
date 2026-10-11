"""Regressions for review R5 of 52e852d (finding R5-02). Each fails without its repair.

API-key formats with an underscore or vendor prefix (Stripe sk_live_ / rk_live_, GitHub github_pat_, GitLab glpat-,
npm_, Hugging Face hf_, SendGrid SG.), HTTP Basic credentials, and Authorization / TAN / 2SV / two-step fields are
removed in Python, in the in-page layer (real Chromium) and never reach the Brain request.
"""
import html
import json
import re
from collections import Counter

import pytest

from uri_assist import redact as RD

from .test_a0_access_perception import FakeClient, ask_and_wait, dom_snapshot, grant, mk
from .test_a0_r1_review_regressions import ROOT, _chromium

SECRETS = ("sk_live_4eC39HqLyjWDarjtT1zdp7dc", "rk_live_51HxYzAbCdEfGhIjKlMnOp", "pk_test_TYooMQauvdEDq54NiTphI7jx",
           "github_pat_11ABCDEFG0123456789_abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOP",
           "glpat-xYz12AbCdEf34GhIjKlMn", "npm_abcdefghijklmnopqrstuvwxyz0123456789",
           "hf_AbCdEfGhIjKlMnOpQrStUvWxYz012345", "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",
           "Basic dXNlcjpwYXNzd29yZA==")
FIELDS = (("authorization", "Authorization", "Basic dXNlcjpwYXNzd29yZA=="), ("smsTan", "SMS-TAN", "482913"),
          ("mTAN", "mTAN", "482913"), ("tan", "TAN", "482913"), ("otc", "One-time code", "482913"),
          ("2sv", "2SV code", "482913"), ("twoStep", "Two-step code", "482913"),
          ("auth_header", "Authorization header", "Zx9kq7Lm"))
READABLE_TEXT = ("Basic information about the course is below.", "The basic plan costs 5 dollars.",
                 "Use the sk_ prefix for keys.", "npm_install is a script name.", "Sultan tanned in Tanzania.")


@pytest.mark.parametrize("secret", SECRETS)
def test_r5_02_api_key_formats_are_masked(secret):
    out = RD.redact_text(f"Use the key {secret} for the request.", Counter())
    assert secret not in out and RD.MASK in out


@pytest.mark.parametrize("text", READABLE_TEXT)
def test_r5_02_ordinary_text_is_unchanged(text):
    assert RD.redact_text(text, Counter()) == text


@pytest.mark.parametrize("name, label, value", FIELDS)
def test_r5_02_authorization_and_tan_fields_are_sensitive(name, label, value):
    assert RD.field_is_sensitive({"type": "text", "name": name, "value": value})
    assert RD.field_is_sensitive({"type": "text", "name": "f1", "label": label, "value": value})


@pytest.mark.parametrize("name", ("author", "tangent", "sultan", "botched", "stepper", "color"))
def test_r5_02_similar_names_stay_readable(name):
    assert not RD.field_is_sensitive({"type": "text", "name": name, "label": name, "value": "Asha Rao"})


def test_r5_02_in_page_text_rules_are_the_python_rules():
    js = (ROOT / "uri_assist/browser_extension/snapshot.js").read_text()
    for kind, rx in RD._TEXT_RULES:
        if kind == "query_secret":
            continue
        m = re.search(rf'\["{kind}", /(.*?)/g?i?\],', js)
        assert m and m.group(1) == rx.pattern.replace("(?i)", ""), kind
    m = re.search(r"const SENSITIVE_WORDS = /(.*?)/;", js)
    assert m and m.group(1) == RD._SENSITIVE_WORDS.pattern


def test_r5_02_in_page_layer_hides_keys_and_fields(tmp_path):
    page = tmp_path / "r5.html"
    page.write_text("<!doctype html><html><body><p>" + " ".join(html.escape(s) for s in SECRETS) + "</p><form>" +
                    "".join(f'<label for="f{i}">{html.escape(lb)}</label><input id="f{i}" name="{html.escape(n)}" '
                            f'value="{html.escape(v)}">' for i, (n, lb, v) in enumerate(FIELDS)) +
                    "</form></body></html>")
    s = _chromium(str(page))["snapshot"]
    raw = json.dumps(s)
    for secret in SECRETS:
        assert secret.split()[-1] not in raw, secret
    by_id = {f["id"]: f for f in s["fields"]}
    for i, (n, lb, v) in enumerate(FIELDS):
        assert by_id[f"f{i}"]["sensitive"] is True, n


def test_r5_02_values_never_reach_the_brain_request():
    fields = [{"id": f"f{i}", "type": "text", "name": n, "label": lb, "value": v,
               "rect": {"x": 1, "y": 1, "w": 2, "h": 2}} for i, (n, lb, v) in enumerate(FIELDS)]
    client = FakeClient(text="This page asks for credentials.")
    br, _ = mk(snap=dom_snapshot(fields=fields, text="Keys: " + " ".join(SECRETS)), client=client)
    grant(br, perms=("observe",))
    out = ask_and_wait(br, "What does this page need?")
    assert out["status"] == "COMPLETE" and client.bodies
    body = json.dumps(client.bodies)
    for secret in SECRETS:
        assert secret.split()[-1] not in body, secret
    for n, lb, v in FIELDS:
        assert v not in body, n
