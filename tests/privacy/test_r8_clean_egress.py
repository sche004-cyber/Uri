"""R1-01: clean Unicode and spacing survive the privacy gateway."""

import json

import httpx
import pytest

from uri_web.search import NO_RESULTS, TavilyProvider

from .helpers import TGateway


@pytest.mark.parametrize("destination", ["WEB_SEARCH", "EXTERNAL_AGENT", "EXTERNAL_MODEL",
                                         "EXTERNAL_SERVICE", "LOG"])
def test_clean_decomposed_accent_is_sent_unchanged(destination):
    text = "cafe\u0301"
    result = TGateway().prepare(text, requester="t", destination=destination, purpose="p")
    assert result.categories == {}
    assert result.text == text


def test_clean_web_search_spacing_is_sent_unchanged():
    text = "weather  tomorrow"
    result = TGateway().prepare(text, requester="t", destination="WEB_SEARCH", purpose="p")
    assert result.categories == {}
    assert result.text == text


def test_tavily_sends_decomposed_accent_without_rewriting_it():
    sent = []

    def capture(request):
        sent.append(json.loads(request.content)["query"])
        return httpx.Response(200, json={"results": []})

    result = TavilyProvider(api_key="test", transport=httpx.MockTransport(capture),
                            privacy=TGateway()).search("cafe\u0301")
    assert result.status == NO_RESULTS
    assert sent == ["cafe\u0301"]


def test_tavily_still_normalizes_spacing_before_gateway():
    sent = []

    def capture(request):
        sent.append(json.loads(request.content)["query"])
        return httpx.Response(200, json={"results": []})

    result = TavilyProvider(api_key="test", transport=httpx.MockTransport(capture),
                            privacy=TGateway()).search("weather  tomorrow")
    assert result.status == NO_RESULTS
    assert sent == ["weather tomorrow"]
