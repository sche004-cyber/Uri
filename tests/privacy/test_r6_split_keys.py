"""R1-01: synthetic known-prefix keys with separate letter and digit groups."""
import json
import random
import string

import httpx

from uri_privacy import PrivacyRefused
from uri_privacy.classify import CREDENTIAL, classify
from uri_web.search import REFUSED, TavilyProvider

from .helpers import TGateway


def _grouped_keys():
    yield "AKIA ABCD EFGH 1234 5678"
    yield "AKIA-ABCD-EFGH-1234-5678"
    rng = random.Random(95)
    for _ in range(200):
        letters = "".join(rng.choices(string.ascii_uppercase, k=8))
        digits = "".join(rng.choices(string.digits, k=8))
        yield f"AKIA {letters[:4]} {letters[4:]} {digits[:4]} {digits[4:]}"


def test_r1_01_separate_letter_and_digit_groups_are_credentials():
    for key in _grouped_keys():
        query = f"key {key} leaked"
        findings = classify(query).findings
        assert any(f.category == CREDENTIAL and key in query[f.start:f.end] for f in findings), key
        for destination in ("WEB_SEARCH", "EXTERNAL_MODEL", "EXTERNAL_AGENT"):
            try:
                TGateway().prepare(f"key {key} leaked", requester="t", destination=destination, purpose="p")
            except PrivacyRefused:
                pass
            else:
                raise AssertionError((destination, key))
        outgoing = TGateway().prepare(f"key {key} leaked", requester="t", destination="LOG", purpose="p").text
        assert key not in outgoing and "[redacted]" in outgoing, key


def test_r1_01_grouped_key_never_reaches_tavily_transport():
    captured = []

    def handler(request):
        captured.append(json.loads(request.content)["query"])
        return httpx.Response(200, json={"results": []})

    query = "search " + next(_grouped_keys())
    result = TavilyProvider(api_key="k", transport=httpx.MockTransport(handler), privacy=TGateway()).search(query)
    assert result.status == REFUSED
    assert captured == []


def test_r1_01_lowercase_prose_after_key_like_prefix_stays_readable():
    query = "sk-learn tutorial for 2026 beginners"
    assert TGateway().prepare(query, requester="t", destination="WEB_SEARCH", purpose="p").text == query
