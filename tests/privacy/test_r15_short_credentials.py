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


SHORT_CREDENTIALS = (
    "password: abc",
    "password is ab",
    "api key: xy",
    "password: a-",
    "password: a.",
    "password: z",
)


@pytest.mark.parametrize("text", SHORT_CREDENTIALS)
def test_r2_01_short_separated_credentials_are_refused_and_redacted(text):
    assert CREDENTIAL in classify(text).categories()
    with pytest.raises(PrivacyRefused):
        TGateway().prepare(text, requester="t", destination="WEB_SEARCH", purpose="p")
    assert TGateway().prepare(text, requester="t", destination="LOG", purpose="p").text == "[redacted]"


@pytest.mark.parametrize("text", SHORT_CREDENTIALS)
def test_r2_01_short_separated_credentials_never_reach_search_transport(text):
    requests = []

    def capture(request):
        requests.append(json.loads(request.content)["query"])
        return httpx.Response(200, json={"results": []})

    result = TavilyProvider(api_key="test", transport=httpx.MockTransport(capture),
                            privacy=TGateway()).search(text)
    assert result.status == REFUSED
    assert requests == []
    assert text not in result.query


@pytest.mark.parametrize("text", ("password ab", "password issue", "password wasp"))
def test_r2_01_bare_or_partial_separator_stays_readable(text):
    assert TGateway().prepare(text, requester="t", destination="WEB_SEARCH", purpose="p").text == text


@pytest.mark.parametrize("text,value", [
    ("password; Hunt3r2!xyz", "Hunt3r2!xyz"),
    ("api key; Hunt3r2!xyz", "Hunt3r2!xyz"),
    ("password / Hunt3r2!xyz", "Hunt3r2!xyz"),
    ("api key / x1!", "x1!"),
])
def test_r1_01_semicolon_or_slash_labelled_credential_never_leaves(text, value):
    assert CREDENTIAL in classify(text).categories()
    gateway = TGateway()
    for destination in ("WEB_SEARCH", "EXTERNAL_MODEL", "EXTERNAL_AGENT"):
        with pytest.raises(PrivacyRefused):
            gateway.prepare(text, requester="t", destination=destination, purpose="p")
    assert value not in gateway.prepare(text, requester="t", destination="LOG", purpose="p").text


@pytest.mark.parametrize("text", ["password; Hunt3r2!xyz", "api key / x1!"])
def test_r1_01_semicolon_or_slash_credential_never_reaches_search_transport(text):
    sent = []

    def capture(request):
        sent.append(json.loads(request.content)["query"])
        return httpx.Response(200, json={"results": []})

    result = TavilyProvider(api_key="test", transport=httpx.MockTransport(capture),
                            privacy=TGateway()).search(text)
    assert result.status == REFUSED
    assert sent == []


@pytest.mark.parametrize("text", ["password / reset help", "api key; rotation guide"])
def test_r1_01_separator_followed_by_prose_stays_readable(text):
    assert TGateway().prepare(text, requester="t", destination="WEB_SEARCH", purpose="p").text == text
