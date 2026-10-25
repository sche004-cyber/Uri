"""Driver run M95-PRIVACY-r8 (Codex R1, repair 1fa3e46e) and V3.1 fallback review FB6 of 1fa3e46e (plan PC-15).
Generated sweeps, synthetic values only."""
import json
import unicodedata

import httpx
import pytest

from uri_privacy import PrivacyRefused
from uri_web.search import TavilyProvider

from .helpers import TGateway

VALUES = (("4111111111111111", (4, 4, 4, 4)), ("234567890124", (4, 4, 4)), ("123456789", (3, 2, 4)),
          ("9876543210", (5, 5)))


def send(text, dest):
    try:
        return False, TGateway().prepare(text, requester="t", destination=dest, purpose="p", reversible=False).text
    except PrivacyRefused as exc:
        return exc.code, ""


def digits(s):              # independent of the code under test (see test_pc14.digits)
    return "".join(str(unicodedata.digit(c)) for c in unicodedata.normalize("NFKC", s)
                   if unicodedata.digit(c, None) is not None)


def _compat_separators():
    return [chr(c) for c in range(0x80, 0x30000)
            if unicodedata.normalize("NFKC", chr(c)) != chr(c) and not chr(c).isspace()]


# --- FB6 R3-01: one compatibility code point between digit groups -------------------------------------------------------
def test_fb6_r3_01_no_compatibility_character_between_digit_groups_carries_a_value():
    seps = _compat_separators()
    assert len(seps) > 4000
    bad = []
    for sep in seps:
        for value, groups in VALUES:
            parts, i = [], 0
            for n in groups:
                parts.append(value[i:i + n])
                i += n
            text = "my number " + sep.join(parts) + " thanks"
            for dest in ("WEB_SEARCH", "LOG"):
                refused, out = send(text, dest)
                if not refused and value in digits(out):
                    bad.append((hex(ord(sep)), value, dest))
    assert bad == [], bad[:5]


@pytest.mark.parametrize("q", ["card 4111㏂1111㏂1111㏂1111 lost", "aadhaar 2345ﷺ6789ﷺ0124 status",
                               "ssn 123㌇45㌇6789 check"])
def test_fb6_r3_01_reviewer_reproductions_never_reach_the_wire(q):
    sent = []

    def capture(request):
        sent.append(json.loads(request.content)["query"])
        return httpx.Response(200, json={"results": []})
    TavilyProvider(api_key="test", transport=httpx.MockTransport(capture), privacy=TGateway()).search(q)
    assert all(len(digits(s)) < 9 for s in sent), sent
    for dest in ("EXTERNAL_AGENT", "EXTERNAL_MODEL", "LOG"):            # redacted or refused, never sent (PC-16)
        refused, out = send(q, dest)
        assert refused or len(digits(out)) < 9, (dest, out)


@pytest.mark.parametrize("q", ["㏂ at 10:30 meeting", "ﷺ محمد 2026", "㌖ 2 ㌕ 5 ㎡",
                               "電話０３－１２３４", "ｶﾀｶﾅ 12 3"])
def test_fb6_r3_01_compatibility_characters_in_ordinary_text_are_not_refused(q):
    for dest in ("WEB_SEARCH", "EXTERNAL_AGENT"):
        assert not send(q, dest)[0], (q, dest)


# --- r8 R1-01 (repair 1fa3e46e): clean decomposed text and spacing --------------------------------------------------
def test_r8_r1_01_clean_decomposed_text_and_spacing_leave_as_written():
    for q in ("café near me", "näive question"):
        for dest in ("WEB_SEARCH", "EXTERNAL_AGENT", "EXTERNAL_MODEL"):
            assert send(q, dest) == (False, q), dest
    assert send("weather  tomorrow", "WEB_SEARCH") == (False, "weather  tomorrow")
    assert send("pássword: Mango#2026!", "WEB_SEARCH")[0]        # a disguised label is still refused
