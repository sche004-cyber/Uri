"""Regressions for review R42 of 78006f9 (finding R42-01). Each fails without its repair.

R42-01  A URL secret split across inline elements ('?client_secret=<b>VALUE</b>', '<span>client_secret</span>=<span>V
        </span>', 'https://alice:<em>PW</em>@host', a heading with '?session_id=<i>SID</i>') is masked in page text and
        headings as it is in the selection: snapshot.js joins inline-adjacent text nodes of one block into one run
        (one group, no separator) before masking, and both layers fail closed on a URL cut by whitespace.
"""
import json
from collections import Counter

import pytest

from uri_assist import redact as RD

from .test_a0_r13_differential_render import RUNNER, ask, run_chromium

PAGE = """<!doctype html><html><head><title>Links</title></head>
<body style="background:#fff;margin:8px;font:16px serif">
<p>A: https://api.example.com/cb?client_secret=<b>ZqSPLITA81xPLm</b>&amp;x=1</p>
<pre><code><span>https://api.example.com/cb?</span><span>client_secret</span>=<span>ZqSPLITB81x</span></code></pre>
<p><a href="#">https://alice:</a><span>HunterSPLITC@db.example.com</span></p>
<p>https://carol:<em>TroubSPLITD</em>@wiki.example/page</p>
<h2>Docs https://wiki.example/page?session_id=<i>SIDSPLITE77</i></h2>
<p>Plain <b>bold</b> words VISIBLE-OK-2.</p>
<p><span>Line one</span><br><span>LINE-TWO-OK</span></p>
</body></html>"""

SECRETS = ("ZqSPLITA81xPLm", "ZqSPLITB81x", "HunterSPLITC", "TroubSPLITD", "SIDSPLITE77", "alice", "carol")
KEPT = ("client_secret=[redacted]", "https://db.example.com", "wiki.example/page?session_id=[redacted]",
        "Plain bold words VISIBLE-OK-2.", "LINE-TWO-OK")


@pytest.fixture(scope="module")
def runs(tmp_path_factory):
    return run_chromium(tmp_path_factory.mktemp("r42"), PAGE, RUNNER)


@pytest.mark.parametrize("name", ["no_selection", "ctrl_a"])
def test_r42_01_url_secrets_split_across_inline_elements_never_reach_the_brain(runs, name):
    body, user, observation = ask(runs[name])
    leaked = [v for v in SECRETS if v in body]
    assert not leaked, (name, leaked, user)
    text = user.split("On-screen text (pixel-checked)", 1)[1]
    missing = [v for v in KEPT if v not in text]
    assert not missing, (name, missing, user)
    heads = user.split("Headings (pixel-checked): ", 1)[1].split("\n", 1)[0]
    assert "session_id=[redacted]" in heads, heads
    # The in-page layer already removes them (snapshot pieces, legacy text and headings).
    snap = runs[name]["snap"]
    sent = json.dumps(snap["pieces"]) + json.dumps(snap["text"]) + json.dumps(snap["headings"])
    for v in SECRETS:
        assert v not in sent, (name, v)
    assert "Line one\nLINE-TWO-OK" in snap["text"], snap["text"]          # a <br> still separates


@pytest.mark.parametrize("text,secret", [
    ("https://api.example.com/cb?client_secret=\nZqSPLITA81xPLm\n&x=1", "ZqSPLITA81xPLm"),
    ("https://api.example.com/cb?\nclient_secret\n=\nZqSPLITB81x", "ZqSPLITB81x"),
    ("https://api.example.com/cb?client_secret\n=ZqSPLITB81x", "ZqSPLITB81x"),
    ("https://alice:\nHunterSPLITC@db.example.com", "HunterSPLITC"),
    ("https://alice:\nHunterSPLITC@db.example.com", "alice"),
    ("https://carol:\nTroubSPLITD\n@wiki.example/page", "TroubSPLITD"),
    ("Docs https://wiki.example/page?session_id= SIDSPLITE77", "SIDSPLITE77"),
    ("link /verify?otp= 482913&pin=12", "482913"),
])
def test_r42_01_redact_text_masks_url_secrets_cut_by_whitespace(text, secret):
    out = RD.redact_text(text, Counter())
    assert secret not in out, out


def test_r42_01_cut_urls_keep_their_host_and_ordinary_text_stays():
    assert RD.redact_text("https://alice:\nHunterSPLITC@db.example.com/a", Counter()).endswith("db.example.com/a")
    for t in ("https://example.com/search?q=\nfees", "Fee payment due 12 May", "a?b= c and x = y",
              "use promo_code= SUMMER26", "https://example.com:8080/p ok", "see https://example.com/ @team"):
        assert RD.redact_text(t, Counter()) == t
