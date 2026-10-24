"""Regressions for short credentials after explicit arrow and dash separators."""

import json

import httpx
import pytest

from uri_privacy.classify import CREDENTIAL, classify
from uri_web.search import REFUSED, TavilyProvider

from .helpers import TGateway


SHORT_SEPARATED_CREDENTIALS = [
    ("password -> ab", "ab"),
    ("api key - xy", "xy"),
    ("api key - xy,", "xy"),
    ("token -> xy", "xy"),
    ("password - ab", "ab"),
]


@pytest.mark.parametrize("text, value", SHORT_SEPARATED_CREDENTIALS)
def test_r3_01_short_separated_credential_never_reaches_search_transport(text, value):
    requests = []

    def capture(request):
        requests.append(json.loads(request.content)["query"])
        return httpx.Response(200, json={"results": []})

    result = TavilyProvider(api_key="test", transport=httpx.MockTransport(capture),
                            privacy=TGateway()).search(text)
    assert result.status == REFUSED
    assert requests == []
    assert value not in result.query


@pytest.mark.parametrize("text, value", SHORT_SEPARATED_CREDENTIALS)
def test_r3_01_short_separated_credential_is_redacted_from_log(text, value):
    assert CREDENTIAL in classify(text).categories()
    assert value not in TGateway().prepare(text, requester="t", destination="LOG", purpose="p").text


def test_r3_01_dash_followed_by_prose_stays_readable():
    text = "reset your password - see the help page"
    assert TGateway().prepare(text, requester="t", destination="WEB_SEARCH", purpose="p").text == text
