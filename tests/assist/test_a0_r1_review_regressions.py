"""Regressions for review R1 of 8019d41 (findings R1-02 and R1-04). Each fails without its repair."""
import json
import os
import shutil
import subprocess
from collections import Counter
from pathlib import Path

import pytest

from uri_assist import access as AC
from uri_assist import perception as PE
from uri_assist import redact as RD

from .test_a0_access_perception import dom_snapshot

ROOT = Path(__file__).resolve().parents[2]
FIX = Path(__file__).parent / "fixtures"

# ---- R1-02: acronym->Word and letter<->digit names, plus mpin/tpin/ccv/acct/card expiry ---------------------------

R1_SENSITIVE_NAMES = ("OTPCode", "SMSOTP", "smsOTPCode", "cvv2", "CVV2", "cvc2", "ccv", "mpin", "MPIN", "tpin",
                      "acctNumber", "acct_no", "cardExpiry", "passcode2", "pwd1", "2FA", "user2faCode")


@pytest.mark.parametrize("name", R1_SENSITIVE_NAMES)
def test_r1_02_sensitive_names(name):
    assert RD.field_is_sensitive({"type": "text", "name": name, "value": "12345678"})


@pytest.mark.parametrize("name", ["hotpot", "spinner", "pinnacle", "pincode", "address2", "line1", "author",
                                  "passenger", "fullName", "HTMLTitle", "account", "cardholderName", "zip5"])
def test_r1_02_ordinary_names_still_readable(name):
    assert not RD.field_is_sensitive({"type": "text", "name": name, "value": "x"})


def test_r1_02_values_never_reach_the_brain_request():
    fields = [{"type": "text", "name": n, "label": "x", "value": f"7{i:05d}", "rect": {"x": 1, "y": 1, "w": 2, "h": 2}}
              for i, n in enumerate(("OTPCode", "cvv2", "MPIN", "acctNumber"))]
    obs = PE.normalise(dom_snapshot(fields=fields), AC.Stamp("g", 1, "t", "dom", 0.0))
    raw = json.dumps([f for f in obs.fields])
    for i in range(4):
        assert f"7{i:05d}" not in raw
    assert all(f["sensitive"] for f in obs.fields)


def _chromium(page, url=None):
    node = shutil.which("node")
    if node is None:
        pytest.skip("BLOCKED: node not installed")
    env = dict(os.environ, NODE_PATH=os.environ.get("NODE_PATH", "/opt/node22/lib/node_modules"))
    if url:
        env["SNAPSHOT_URL"] = url
    p = subprocess.run([node, str(FIX / "run_snapshot.cjs"), str(ROOT / "uri_assist/browser_extension/snapshot.js"),
                        str(FIX / page)], capture_output=True, text=True, env=env, timeout=120)
    if p.returncode != 0 and "Cannot find module" in p.stderr:
        pytest.skip("BLOCKED: playwright not installed")
    assert p.returncode == 0, p.stderr[-500:]
    return json.loads(p.stdout)


def test_r1_02_in_page_layer_hides_new_names_and_matches_python():
    s = _chromium("tricky_fields.html")["snapshot"]
    raw = json.dumps(s)
    for secret in ("710001", "710002", "713", "714", "715", "7106", "7107", "71000008", "71000009", "07/31",
                   "pc71011", "pw71012"):
        assert f'"{secret}"' not in raw, secret
    js_sensitive = {f["id"] or f["name"] for f in s["fields"] if f["sensitive"]}
    assert {f"m{i}" for i in range(1, 13)} <= js_sensitive
    py = PE.normalise({**s}, AC.Stamp("g", 1, "t", "dom", 0.0))
    assert js_sensitive == {f.get("id") or f.get("name") for f in py.fields if f.get("sensitive")}


# ---- R1-04: title, headings, labels, placeholders and the URL are masked inside the page ----------------------------

PAGE_SECRETS = ("eyJhbGciOiJIUzI1NiJ9", "4111 1111 1111 1111", "sk-abcdefghijklmnopqrstuv",
                "ghp_abcdefghijklmnopqrstuvwxyz1234", "AKIAABCDEFGHIJKLMNOP")


def test_r1_04_every_text_leaving_the_page_is_masked():
    url = ("https://portal.example/reset/eyJhbGciOiJIUzI1NiJ9.eyJzdWIiOiIxIn0.c2lnbmF0dXJlLXZhbHVl"
           "/ghp_abcdefghijklmnopqrstuvwxyz1234?token=abcdef123456&lang=en")
    s = _chromium("text_surfaces.html", url=url)["snapshot"]
    for key in ("title", "headings", "fields", "url"):
        raw = json.dumps(s[key])
        for secret in PAGE_SECRETS + ("abcdef123456",):
            assert secret not in raw, (key, secret)
    assert s["url"].startswith("https://portal.example/reset/") and "lang=en" in s["url"]
    assert s["url"].count("[redacted]") == 3            # JWT, GitHub token, token= (counted once each)
    assert s["redactions"]["query_secret"] == 1
    # Parity: Python's second layer leaves what the page sent unchanged (nothing more to mask).
    c = Counter()
    for t in [s["title"], s["url"], *s["headings"], *(f[k] for f in s["fields"] for k in ("label", "placeholder"))]:
        assert RD.redact_text(t, c) == t


# ---- R2-01: lowercase run-together OTP / CVV / PIN / password names, in both layers ---------------------------------

R2_SENSITIVE_NAMES = ("otpcode", "smsotpcode", "otpvalue", "otpnumber", "cvvcode", "cvvnumber", "cardcvv", "cardcvc",
                      "userpassword", "newpassword", "confirmpassword", "loginpassword", "txnpassword", "upipin",
                      "atmpin", "cardpin", "securitypin", "loginpwd", "userpass", "verifycode")
R2_READABLE_NAMES = ("hotpot", "footpath", "hotplate", "camping", "compass", "bypass", "passenger", "zipcode",
                     "spinach", "opinion")


@pytest.mark.parametrize("name", R2_SENSITIVE_NAMES)
def test_r2_01_run_together_names_are_sensitive(name):
    assert RD.field_is_sensitive({"type": "text", "name": name, "value": "482913"})


@pytest.mark.parametrize("name", R2_READABLE_NAMES + ("pincode", "spinner", "pinnacle", "author", "account"))
def test_r2_01_ordinary_run_together_names_still_readable(name):
    assert not RD.field_is_sensitive({"type": "text", "name": name, "value": "x"})


def test_r2_01_values_never_reach_the_brain_request():
    fields = [{"type": "text", "name": n, "label": "x", "value": f"82{i:04d}", "rect": {"x": 1, "y": 1, "w": 2, "h": 2}}
              for i, n in enumerate(R2_SENSITIVE_NAMES, 1)]
    obs = PE.normalise(dom_snapshot(fields=fields), AC.Stamp("g", 1, "t", "dom", 0.0))
    raw = json.dumps(list(obs.fields))
    for i in range(1, len(R2_SENSITIVE_NAMES) + 1):
        assert f"82{i:04d}" not in raw
    assert all(f["sensitive"] for f in obs.fields)


def test_r2_01_in_page_pattern_is_the_python_pattern():
    import re
    js = (ROOT / "uri_assist/browser_extension/snapshot.js").read_text()
    m = re.search(r"const RUN_TOGETHER = /(.*)/;", js)
    assert m and m.group(1) == RD._RUN_TOGETHER.pattern


def test_r2_01_in_page_layer_hides_run_together_names_and_matches_python():
    s = _chromium("tricky_fields.html")["snapshot"]
    raw = json.dumps(s)
    for i in range(1, len(R2_SENSITIVE_NAMES) + 1):
        assert f'"82{i:04d}"' not in raw, R2_SENSITIVE_NAMES[i - 1]
    js_sensitive = {f["id"] or f["name"] for f in s["fields"] if f["sensitive"]}
    assert {f"r{i}" for i in range(1, len(R2_SENSITIVE_NAMES) + 1)} <= js_sensitive
    assert not {f"q{i}" for i in range(1, len(R2_READABLE_NAMES) + 1)} & js_sensitive
    py = PE.normalise({**s}, AC.Stamp("g", 1, "t", "dom", 0.0))
    assert js_sensitive == {f.get("id") or f.get("name") for f in py.fields if f.get("sensitive")}
