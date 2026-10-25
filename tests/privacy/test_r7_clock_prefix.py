"""R7-01: a clock-shaped prefix cannot exempt a longer labelled number."""

import random
import unicodedata

import pytest

from uri_privacy import PrivacyRefused

from .helpers import TGateway
from .synth import verhoeff_digit


DESTINATIONS = ("WEB_SEARCH", "EXTERNAL_AGENT", "LOG")


def _digits(text):
    return "".join(str(unicodedata.digit(ch)) for ch in unicodedata.normalize("NFKC", text)
                   if unicodedata.digit(ch, None) is not None)


def _clock_prefixed_values():
    rng = random.Random(701)
    for _ in range(40):
        ssn = f"1{rng.randrange(60):02d}{rng.randrange(10**6):06d}"
        yield "SSN", ssn, f"{ssn[0]}:{ssn[1:3]} {ssn[3:]}"

        body = f"2{rng.randrange(60):02d}{rng.randrange(60):02d}{rng.randrange(10**6):06d}"
        aadhaar = body + verhoeff_digit(body)
        yield "Aadhaar", aadhaar, f"{aadhaar[0]}:{aadhaar[1:3]}:{aadhaar[3:5]} {aadhaar[5:]}"

        mobile = f"9{rng.randrange(60):02d}{rng.randrange(10**7):07d}"
        yield "phone", mobile, f"{mobile[0]}:{mobile[1:3]} {mobile[3:]}"

        compact_mobile = f"9{rng.randrange(24):02d}{rng.randrange(60):02d}{rng.randrange(10**5):05d}"
        yield "phone", compact_mobile, f"{compact_mobile[0]}T{compact_mobile[1:5]} {compact_mobile[5:]}"


@pytest.mark.parametrize("destination", DESTINATIONS)
def test_r7_01_clock_prefixed_identifiers_never_leave_intact(destination):
    gateway = TGateway()
    for label, value, disguised in _clock_prefixed_values():
        try:
            outgoing = gateway.prepare(f"{label} {disguised}", requester="t", destination=destination,
                                       purpose="p", reversible=False).text
        except PrivacyRefused:
            continue
        assert value not in _digits(outgoing), (destination, label, disguised, outgoing)


@pytest.mark.parametrize("query", ["at 10:30", "time 10:30-11:45, 12:00-13:15",
                                     "on 2026-10-23 at 10:30:45", "server 10.0.0.1:8080"])
def test_r7_01_standalone_exempt_tokens_remain_readable(query):
    outgoing = TGateway().prepare(query, requester="t", destination="WEB_SEARCH", purpose="p",
                                  reversible=False).text
    assert outgoing == query
