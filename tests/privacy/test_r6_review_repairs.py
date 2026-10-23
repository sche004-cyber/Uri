"""Regressions for the M95-PRIVACY-r6 independent review (synthetic values)."""

import json

import httpx
import pytest

from uri_privacy import PrivacyRefused
from uri_privacy.classify import CREDENTIAL, classify
from uri_privacy.vault import TOKEN
from uri_web.search import REFUSED, TavilyProvider

from .helpers import TGateway


LETTER_ONLY_CREDENTIALS = ["API key abcdefghijklmnop", "password huntertwo", "password abcd",
                           "secret key wordvalue", "access token alphabetic", "passcode wordvalue"]


@pytest.mark.parametrize("text", LETTER_ONLY_CREDENTIALS)
@pytest.mark.parametrize("destination", ["WEB_SEARCH", "EXTERNAL_AGENT", "EXTERNAL_MODEL", "EXTERNAL_SERVICE"])
def test_r3_01_letter_only_labelled_credentials_are_refused(text, destination):
    assert CREDENTIAL in classify(text).categories()
    with pytest.raises(PrivacyRefused):
        TGateway().prepare(text, requester="t", destination=destination, purpose="p")


@pytest.mark.parametrize("text", LETTER_ONLY_CREDENTIALS)
def test_r3_01_letter_only_labelled_credentials_are_redacted_from_log(text):
    assert text not in TGateway().prepare(text, requester="t", destination="LOG", purpose="p").text


@pytest.mark.parametrize("text", LETTER_ONLY_CREDENTIALS)
def test_r3_01_letter_only_labelled_credentials_never_reach_search_transport(text):
    requests = []

    def capture(request):
        requests.append(json.loads(request.content)["query"])
        return httpx.Response(200, json={"results": []})

    result = TavilyProvider(api_key="test", transport=httpx.MockTransport(capture),
                            privacy=TGateway()).search(text)
    assert result.status == REFUSED
    assert requests == []
    assert text not in result.query


def test_r3_02_forced_random_collision_cannot_restore_another_scopes_value(monkeypatch):
    from uri_privacy import vault

    monkeypatch.setattr(vault.secrets, "choice", lambda alphabet: "a")
    gateway = TGateway()
    a = gateway.prepare("alice@example.in", requester="t", destination="EXTERNAL_MODEL", purpose="p", scope="A")
    b = gateway.prepare("bob@example.in", requester="t", destination="EXTERNAL_MODEL", purpose="p", scope="B")
    assert TOKEN.search(a.text) and TOKEN.search(b.text)
    assert a.text != b.text
    assert gateway.restore(a.text, "B", requester="t") == a.text
    assert gateway.restore(b.text, "A", requester="t") == b.text
    assert gateway.restore(a.text, "A", requester="t") == "alice@example.in"
    assert gateway.restore(b.text, "B", requester="t") == "bob@example.in"


def test_r3_02_maximum_scope_id_round_trips_without_exposing_value():
    gateway = TGateway()
    scope = "S" * 96
    outgoing = gateway.prepare("alice@example.in", requester="t", destination="EXTERNAL_MODEL", purpose="p",
                               scope=scope)
    assert TOKEN.fullmatch(outgoing.text)
    assert "alice" not in outgoing.text
    assert gateway.restore(outgoing.text, scope, requester="t") == "alice@example.in"


def test_r3_02_legacy_unscoped_collision_is_treated_as_foreign():
    from uri_privacy.vault import Scope

    old_token = "[[CONTACT_aaaaaaaaaaaaaaaa]]"
    scope = Scope("B", 2**62, {old_token: ("CONTACT", "bob@example.in")})
    assert scope.restore(old_token) == (old_token, 0, 1)
