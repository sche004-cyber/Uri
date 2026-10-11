"""R1-04 (W1-A0 closure review): URL query / fragment secrets and userinfo reached the Brain.

Only `code=`, `token=` and a few other exact key names were masked, and only from 6 characters: `client_secret=`,
`refresh_token=`, `reset_token=`, `otp=482913`, `pin=4821`, `session_id=`, `passcode=` and `https://alice:pass@host/`
reached the Brain as the "Location:" line. Now both layers (snapshot.js in the page, redact.redact_url in URI) remove
the userinfo and mask the value of every query or fragment key that names a secret, whatever its length.

Self-contained: the Python cases build their snapshot here; the in-page case runs snapshot.js in real Chromium on a
fixture page that already existed.
"""
import json
from collections import Counter

import pytest

from uri_assist import access as AC
from uri_assist import bridge as B
from uri_assist import redact as RD

from .test_a0_access_perception import FakeAdapter, FakeClient, ask_and_wait, dom_snapshot, grant
from .test_a0_r1_review_regressions import _chromium

URL = ("https://alice:Hunter2pass@x.test/cb?client_secret=s3cr3tValue9&refresh_token=r1a2b3c4d5e6&otp=482913"
       "&pin=4821&session_id=sess77abc&passcode=918273&reset_token=rt9988&lang=en&page=2"
       "#state=x&code=c0d3value&access_token=at55")
SECRETS = ("Hunter2pass", "alice", "s3cr3tValue9", "r1a2b3c4d5e6", "482913", "4821", "sess77abc", "918273", "rt9988",
           "c0d3value", "at55")
KEPT = ("x.test/cb", "lang=en", "page=2", "state=x")


def _brain_body(url):
    client = FakeClient(text="ok")
    br = B.AssistCommands(adapters={AC.ScopeKind.BROWSER_TAB: FakeAdapter(
        "browser_tab", dom_snapshot(url=url), targets=[{"target_id": "t", "label": "Fee"}])}, brain_client=client)
    grant(br, perms=("observe",))
    assert ask_and_wait(br, "What is this?")["status"] == "COMPLETE"
    return json.dumps(client.bodies)


def test_r1_04_url_secrets_and_userinfo_never_reach_the_brain():
    body = _brain_body(URL)
    assert "Location: " in body
    leaked = [s for s in SECRETS if s in body]
    assert not leaked, leaked
    missing = [k for k in KEPT if k not in body]
    assert not missing, missing


@pytest.mark.parametrize("url,secret", [
    ("https://x.test/?client_secret=s3cr3tValue9", "s3cr3tValue9"),
    ("https://x.test/?refresh_token=r1a2b3", "r1a2b3"),
    ("https://x.test/?reset_token=r1a2b3", "r1a2b3"),
    ("https://x.test/?otp=482913", "482913"),
    ("https://x.test/?pin=4821", "4821"),
    ("https://x.test/?session_id=s1", "=s1"),
    ("https://x.test/?passcode=918273", "918273"),
    ("https://alice:Hunter2pass@x.test/", "Hunter2pass"),
    ("https://x.test/#access_token=at55&state=q", "at55"),
])
def test_r1_04_redact_url_masks_each_secret_key(url, secret):
    c = Counter()
    out = RD.redact_url(url, c)
    assert secret not in out and sum(c.values()) >= 1, out


def test_r1_04_readable_query_keys_stay():
    url = "https://x.test/p?q=fees&page=2&lang=en&utm_source=a&ref=b&sort=asc&id=7&promo_code=SUMMER&zip=12345#sec-2"
    c = Counter()
    assert RD.redact_url(url, c) == url and not c


def test_r1_04_in_page_layer_masks_url_secrets():
    url = ("https://portal.example/cb?client_secret=s3cr3tValue9&refresh_token=r1a2b3c4d5e6&otp=482913&pin=4821"
           "&session_id=sess77abc&passcode=918273&lang=en#state=x&access_token=at55")
    s = _chromium("text_surfaces.html", url=url)["snapshot"]
    for secret in ("s3cr3tValue9", "r1a2b3c4d5e6", "482913", "4821", "sess77abc", "918273", "at55"):
        assert secret not in s["url"], (secret, s["url"])
    assert s["url"].startswith("https://portal.example/cb?") and "lang=en" in s["url"] and "state=x" in s["url"]
    # Parity: URI's second layer has nothing more to mask in what the page sent.
    assert RD.redact_url(s["url"], Counter()) == s["url"]
