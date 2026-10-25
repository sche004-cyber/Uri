"""Regressions for short credentials after explicit arrow and dash separators."""

import json

import httpx
import pytest

from uri_privacy.classify import CREDENTIAL, classify
from uri_web.search import REFUSED, TavilyProvider

from .helpers import TGateway


# Short values with a digit or symbol after an arrow or a dash are credentials. Letter-only values there are the
# LDEC-007 residual: "forgot password - help" and "token -> refresh flow" cannot be told apart from "password - ab"
# (coordinator review of the r15 repairs, plan PC-22).
SHORT_SEPARATED_CREDENTIALS = [
    ("password -> a1", "a1"),
    ("api key - x9", "x9"),
    ("api key - x9,", "x9"),
    ("token -> x!", "x!"),
    ("password - a#", "a#"),
]
LETTER_ONLY_RESIDUAL = ["password -> ab", "api key - xy", "token -> xy", "password - ab", "forgot password - help",
                        "token -> refresh flow explained", "reset password - faq", "token is a JWT", "password is ok"]


@pytest.mark.parametrize("text", LETTER_ONLY_RESIDUAL)
def test_pc22_letter_only_after_an_arrow_or_dash_is_the_ldec007_residual(text):
    assert TGateway().prepare(text, requester="t", destination="WEB_SEARCH", purpose="p").text == text


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
