"""V3.1 fallback review FB11 of f8cc51ce (plan PC-20): two STRUCTURAL findings and the cheap RECALL ones.
Synthetic values only."""
import random
import string
import time

import pytest

from uri_privacy import PrivacyRefused
from uri_privacy import classify as C

from .helpers import TGateway


def send(text, dest):
    try:
        return False, TGateway().prepare(text, requester="t", destination=dest, purpose="p", reversible=False).text
    except PrivacyRefused as exc:
        return exc.code, ""


# --- R1-01 (STRUCTURAL): no piece of a span-less credential reaches the log ----------------------------------------
def test_fb11_r1_01_log_keeps_no_piece_of_a_bearer_token():
    rng = random.Random(11)
    bad = []
    for alphabet, n in ((string.hexdigits.lower()[:16], 24), (string.hexdigits.lower()[:16], 31),
                        (string.ascii_letters + string.digits, 40)):
        for _ in range(150):
            tok = "".join(rng.choice(alphabet) for _ in range(n))
            if alphabet.startswith("0123") and n == 40:
                tok = tok[:12] + "".join(rng.choice(string.digits) for _ in range(10)) + tok[22:]
            for prefix in ("Authorization: Bearer ", "Bearer ", "auth header Bearer "):
                refused, out = send(prefix + tok, "LOG")
                if refused or any(tok[i:i + 6] in out for i in range(len(tok) - 5)):
                    bad.append((prefix + tok, out))
    assert bad == [], (len(bad), bad[:5])


@pytest.mark.parametrize("q", ["xoxb-LRReRrVyio2M4533822254Tm3cxPMPnLOf30",
                               "Authorization%3A%20Bearer%20abcdef1234567890abcdef"])
def test_fb11_r1_01_reviewer_reproductions(q):
    refused, out = send(q, "LOG")
    assert not refused and out == "[redacted]", out


# --- R1-02 (STRUCTURAL): only plain str is text ------------------------------------------------------------------------
class _Sneaky(str):
    def isascii(self):
        return True


def test_fb11_r1_02_str_subclasses_are_refused_by_prepare_and_restore():
    g = TGateway()
    for dest in ("WEB_SEARCH", "LOG", "LOCAL_BRAIN"):
        with pytest.raises(PrivacyRefused) as e:
            g.prepare(_Sneaky("4111a…1111a…1111a…1111"), requester="t", destination=dest, purpose="p")
        assert e.value.code == "PRIVACY_INPUT_NOT_TEXT"
    with pytest.raises(PrivacyRefused):
        g.restore(_Sneaky("x"), "S1", requester="t")


# --- R1-03: the compact date form is exempt only when it is a valid date ------------------------------------------------
def test_fb11_r1_03_invalid_compact_dates_are_not_exempt():
    refused, out = send("logs 20429141T 20777631T 20706311T", "WEB_SEARCH")
    assert refused or sum(c.isdigit() for c in out) < 9, out           # invalid dates: the digit budget applies
    assert send("build 20261023T100000Z ok", "WEB_SEARCH") == (False, "build 20261023T100000Z ok")


# --- R1-06: the disguise patterns are linear on long digit runs ---------------------------------------------------------
@pytest.mark.parametrize("t", ["1" * 65536, "12x" * 21845, "1 " * 32768], ids=["digits", "letter-gaps", "spaces"])
def test_fb11_r1_06_disguise_patterns_are_linear(t):
    t0 = time.perf_counter()
    C._unusual_digit_separators(t)
    assert time.perf_counter() - t0 < 0.5


# --- stated residuals, pinned so that a later change updates the threat model with them ----------------------------------
def test_fb11_residuals_are_as_stated():
    # R1-04: Han numerals have no Unicode digit value and are not counted (threat model 6.12)
    assert send("我的电话是一三九一二三四五六七八",
                "WEB_SEARCH")[0] is False
    # R1-05: an unlabelled secret without a known prefix needs 40+ characters (32 for hex) to be found
    assert send("connect using Q7m2Zp9Lr4Ks8Tv1Wq3E for the webhook", "WEB_SEARCH")[0] is False
