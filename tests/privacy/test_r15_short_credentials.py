"""R1-01: short values after explicit credential separators stay private."""

import json

import httpx
import pytest

from uri_privacy import PrivacyRefused
from uri_privacy.classify import CREDENTIAL, classify
from uri_web.search import REFUSED, TavilyProvider

from .helpers import TGateway


@pytest.mark.parametrize("text,value", [
    ("password: a1!", "a1!"),
    ("api key: x1!", "x1!"),
    ("password is q2", "q2"),
    ("pwd=7", "7"),
    ('{"client_secret": "z7"}', "z7"),
    ("client_secret: z!", "z!"),
])
def test_r1_01_short_labelled_credentials_never_leave(text, value):
    assert CREDENTIAL in classify(text).categories()
    gateway = TGateway()
    for destination in ("WEB_SEARCH", "EXTERNAL_MODEL", "EXTERNAL_AGENT"):
        with pytest.raises(PrivacyRefused):
            gateway.prepare(text, requester="t", destination=destination, purpose="p")
    logged = gateway.prepare(text, requester="t", destination="LOG", purpose="p").text
    assert value not in logged


@pytest.mark.parametrize("text", ["password: a1!", "api key: x1!"])
def test_r1_01_short_labelled_credentials_never_reach_search_transport(text):
    sent = []

    def capture(request):
        sent.append(json.loads(request.content)["query"])
        return httpx.Response(200, json={"results": []})

    result = TavilyProvider(api_key="test", transport=httpx.MockTransport(capture),
                            privacy=TGateway()).search(text)
    assert result.status == REFUSED
    assert sent == []
    assert text not in result.query
