"""Regressions for review R41 of c85bd83 (findings R41-01, R41-02, R41-03). Each fails without its repair.

R41-01  The ask job re-checks the grant atomically with storing and emitting its result: a Stop, pause or new grant
        that lands after the Brain replied never lets an `assist.answer` with content (or an observation) out.
R41-02  Text inside a withheld field (OTP, plain contenteditable) never reaches the Brain through a heading.
R41-03  URLs written in page text, headings or a shared field value lose userinfo and every secret-naming query value,
        as in the Location line.
"""
import json
import os
import shutil
import subprocess
from collections import Counter

import pytest

from uri_assist import access as AC
from uri_assist import bridge as B
from uri_assist import redact as RD

from .test_a0_access_perception import FakeAdapter, FakeClient, dom_snapshot, grant
from .test_a0_r13_differential_render import RUNNER, ROOT, VH, VW, ask, run_chromium


def _bridge_with_events(client):
    events = []
    ad = FakeAdapter("browser_tab", dom_snapshot(), targets=[{"target_id": "t", "label": "Fee payment",
                                                             "origin": "https://portal.example"}])
    br = B.AssistCommands(adapters={AC.ScopeKind.BROWSER_TAB: ad}, brain_client=client, brain_idle=lambda: True,
                          write_event=events.append)
    return br, events


@pytest.mark.parametrize("step", ["revoke", "pause"])
def test_r41_01_no_answer_event_after_stop_or_pause_that_follows_the_check(step):
    client = FakeClient(text="ANSWER-DERIVED-FROM-PAGE")
    br, events = _bridge_with_events(client)
    grant(br, perms=("observe",))
    real = br.access.check_unchanged
    fired = []

    def check_then_user_acts(stamp, perm):
        g = real(stamp, perm)
        if not fired:              # the user taps Stop / Pause right after the post-answer check passed
            fired.append(1)
            if step == "revoke":
                br.access.revoke("user")
            else:
                br.access.pause()
        return g

    br.access.check_unchanged = check_then_user_acts
    aid = br.handle("assist_ask", {"command": "assist_ask", "question": "What is my balance?",
                                   "use_screenshot": False})["ask_id"]
    br.wait(5)
    assert fired
    answers = [e for e in events if e["type"] == "assist.answer" and e["turn_id"] == aid]
    assert len(answers) == 1
    data = answers[0]["data"]
    assert data["status"] == "CANCELLED" and data["answer"] == "" and data["observation"] is None
    assert "ANSWER-DERIVED" not in json.dumps(events) and "Fee payment" not in json.dumps(answers)
    assert "ANSWER-DERIVED" not in json.dumps(br._answers, default=str)


def test_r41_01_answer_under_the_unchanged_grant_is_still_emitted():
    client = FakeClient(text="ANSWER-DERIVED-FROM-PAGE")
    br, events = _bridge_with_events(client)
    grant(br, perms=("observe",))
    aid = br.handle("assist_ask", {"command": "assist_ask", "question": "q", "use_screenshot": False})["ask_id"]
    br.wait(5)
    data = [e for e in events if e["type"] == "assist.answer" and e["turn_id"] == aid][0]["data"]
    assert data["status"] == "COMPLETE" and data["answer"] == "ANSWER-DERIVED-FROM-PAGE"


# ---- R41-02 / R41-03: real Chromium, snapshot.js + probe.js -> normalise -> Brain body ------------------------------

PAGE = """<!doctype html><html><head><title>Account</title></head>
<body style="background:#fff;margin:8px;font:16px serif">
<h2>Draft: <span contenteditable id="draftbox">PRIVATE-DRAFT-TEXT</span></h2>
<h2>Recovery code: <span contenteditable aria-label="Recovery code">7F3A9-2C1D8</span></h2>
<h3>PIN <span contenteditable autocomplete="one-time-code">482913</span></h3>
<h2>Docs https://carol:Tr0ub4dor@wiki.example/page?session_id=SIDX77</h2>
<p>A: https://api.example.com/cb?client_secret=Zq81xPLm&amp;x=1</p>
<p>B: https://example.com/oauth?refresh_token=r1x9Qa7</p>
<p>C: https://bank.example/verify?otp=559911&amp;pin=4321</p>
<p>D: https://alice:Hunter2pw@db.example.com/admin</p>
<p>H: postgres://admin:S3cretPass@10.0.0.5:5432/main</p>
<p>Plain words stay VISIBLE-OK-1.</p>
<div contenteditable id="comment" style="border:1px solid #888;padding:4px">See https://bob:pa55word@host.example/p?api_key=K9xz1 now</div>
</body></html>"""

FIELD_SECRETS = ("PRIVATE-DRAFT-TEXT", "7F3A9-2C1D8", "482913")
URL_SECRETS = ("Tr0ub4dor", "SIDX77", "Zq81xPLm", "r1x9Qa7", "559911", "4321", "Hunter2pw", "S3cretPass", "pa55word",
               "K9xz1", "carol", "alice", "admin:", "bob:")
KEPT = ("Draft:", "Recovery code:", "PIN", "wiki.example/page?session_id=[redacted]",
        "client_secret=[redacted]", "refresh_token=[redacted]", "otp=[redacted]", "https://db.example.com/admin",
        "postgres://10.0.0.5:5432/main", "VISIBLE-OK-1", "https://host.example/p?api_key=[redacted]")


@pytest.fixture(scope="module")
def runs(tmp_path_factory):
    return run_chromium(tmp_path_factory.mktemp("r41"), PAGE, RUNNER)


@pytest.mark.parametrize("name", ["no_selection", "ctrl_a"])
def test_r41_02_03_field_text_and_url_secrets_never_reach_the_brain(runs, name):
    body, user, observation = ask(runs[name])
    leaked = [v for v in FIELD_SECRETS + URL_SECRETS if v in body]
    assert not leaked, (name, leaked, user)
    missing = [v for v in KEPT if v not in body]
    assert not missing, (name, missing, user)
    heads = user.split("Headings (pixel-checked): ", 1)[1].split("\n", 1)[0]
    assert "Draft:" in heads and "Recovery code:" in heads, heads
    # The in-page layer already removes them (nothing to undo later).
    snap = json.dumps(runs[name]["snap"]["pieces"]) + json.dumps(runs[name]["snap"]["fields"])
    for v in FIELD_SECRETS + URL_SECRETS:
        assert v not in snap, (name, v)


def test_r41_02_python_layer_drops_field_text_the_page_layer_put_in_a_heading(tmp_path):
    """The URI side does not rely on snapshot.js: a heading piece drawn inside a withheld field's box is dropped."""
    node = shutil.which("node")
    assert node is not None, "BLOCKED: node not installed"
    src = (ROOT / "uri_assist/browser_extension/snapshot.js").read_text()
    lax = src.replace("!inField(n) && textVisible(n)) {", "textVisible(n)) {")   # an in-page layer without R41-02
    (tmp_path / "snapshot.js").write_text(lax)
    (tmp_path / "page.html").write_text(PAGE)
    (tmp_path / "run.cjs").write_text(RUNNER)
    env = dict(os.environ, NODE_PATH=os.environ.get("NODE_PATH", "/opt/node22/lib/node_modules"))
    p = subprocess.run([node, str(tmp_path / "run.cjs"), str(tmp_path / "snapshot.js"),
                        str(ROOT / "uri_assist/browser_extension/probe.js"), str(tmp_path / "page.html"), str(VW),
                        str(VH)], capture_output=True, text=True, env=env, timeout=300)
    assert p.returncode == 0, p.stderr[-800:]
    run = json.loads(p.stdout)["no_selection"]
    assert "PRIVATE-DRAFT-TEXT" in json.dumps(run["snap"]["pieces"]["headings"])     # the lax layer sent it
    body, user, _ = ask(run)
    for v in FIELD_SECRETS:
        assert v not in body, v
    heads = user.split("Headings (pixel-checked): ", 1)[1].split("\n", 1)[0]
    assert "Draft:" in heads and "Recovery code:" in heads, heads


@pytest.mark.parametrize("text,secret", [
    ("https://api.example.com/cb?client_secret=Zq81xPLm&x=1", "Zq81xPLm"),
    ("https://example.com/oauth?refresh_token=r1x9Qa7abc", "r1x9Qa7abc"),
    ("https://alice:Hunter2pw@db.example.com/admin", "Hunter2pw"),
    ("go to postgres://admin:S3cretPass@10.0.0.5/db now", "S3cretPass"),
    ("link /verify?otp=482913&pin=12", "482913"),
    ("link /verify?otp=482913&pin=12", "pin=12"),
    ("https://x.example/s#session_id=ab12", "ab12"),
    ("client_secret=Zq81xPLm", "Zq81xPLm"),
])
def test_r41_03_redact_text_masks_secrets_in_urls_in_text(text, secret):
    out = RD.redact_text(text, Counter())
    assert secret not in out, out


def test_r41_03_ordinary_urls_and_text_stay_readable():
    for t in ("https://example.com/search?q=fees&page=2#top", "Fee payment due 12 May", "a?b=c and x=y",
              "postal code 560001", "use promo_code=SUMMER26 or zip_code=560001",
              "https://x.test/p?q=fees&page=2&lang=en&promo_code=SUMMER26&zip=12345#sec-2"):
        assert RD.redact_text(t, Counter()) == t
