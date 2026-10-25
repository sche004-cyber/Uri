"""Regressions for the M95-PRIVACY-r6 independent review (synthetic values)."""

import json

import httpx
import pytest

from uri_privacy import PrivacyRefused
from uri_privacy.classify import CREDENTIAL, classify
from uri_privacy.vault import TOKEN
from uri_web.search import REFUSED, TavilyProvider

from .helpers import TGateway


# Owner decision LDEC-007 (2026-10-23): letter-only values are credentials when a separator joins label and value, or
# for a key label followed by one 16+ letter token. A bare label directly followed by one letter-only word is a stated
# residual (threat model 6.5): it cannot be told apart from ordinary searches, and refusing it blocked 12 of 13.
LETTER_ONLY_CREDENTIALS = ["API key abcdefghijklmnop", "password: huntertwo", "password is huntertwo",
                           "passcode = wordvalue", "secret key: wordvalue", "access token is alphabetic"]
LETTER_ONLY_RESIDUAL = ["password huntertwo", "password abcd", "secret key wordvalue", "access token alphabetic",
                        "passcode wordvalue"]
ORDINARY_LOGIN_SEARCHES = ["password reset not working", "forgot password help", "how to change password using cmd",
                           "password requirements for gmail", "password protected zip file",
                           "API key rotation best practice", "access token expired error",
                           "secret key generation python", "password manager comparison", "This is my password manager",
                           "Google is my password manager", "wifi password sharing android", "passcode lock settings",
                           "huntertwo is my password manager"]
VALUE_BEFORE_LABEL_WORDS = ("huntertwo", "sunshine", "bluebird", "orchard", "pineapple")
VALUE_BEFORE_LABEL_FORMS = ("{value} is my password", "use {value} as the password",
                            '"{value}" is the wifi password', "{value} was our passcode")


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


@pytest.mark.parametrize("text", LETTER_ONLY_RESIDUAL)
def test_ldec007_bare_label_with_one_letter_only_word_is_the_stated_residual(text):
    # Pinned so the residual is visible: if a later rule catches these, update threat model 6.5 with it.
    assert CREDENTIAL not in classify(text).categories()


@pytest.mark.parametrize("text", ORDINARY_LOGIN_SEARCHES)
def test_ldec007_ordinary_login_searches_are_not_refused(text):
    for destination in ("WEB_SEARCH", "EXTERNAL_AGENT", "EXTERNAL_MODEL"):
        assert TGateway().prepare(text, requester="t", destination=destination, purpose="p").text == text


@pytest.mark.parametrize("value", VALUE_BEFORE_LABEL_WORDS)
@pytest.mark.parametrize("form", VALUE_BEFORE_LABEL_FORMS)
def test_r4_01_alphabetic_value_before_label_is_refused_and_redacted(value, form):
    text = form.format(value=value)
    assert CREDENTIAL in classify(text).categories()
    for destination in ("WEB_SEARCH", "EXTERNAL_AGENT", "EXTERNAL_MODEL", "EXTERNAL_SERVICE"):
        with pytest.raises(PrivacyRefused):
            TGateway().prepare(text, requester="t", destination=destination, purpose="p")
    assert value not in TGateway().prepare(text, requester="t", destination="LOG", purpose="p").text


def test_r4_01_alphabetic_value_before_label_never_reaches_search_transport():
    requests = []

    def capture(request):
        requests.append(json.loads(request.content)["query"])
        return httpx.Response(200, json={"results": []})

    text = "huntertwo is my password"
    result = TavilyProvider(api_key="test", transport=httpx.MockTransport(capture),
                            privacy=TGateway()).search(text)
    assert result.status == REFUSED
    assert requests == []
    assert "huntertwo" not in result.query


@pytest.mark.parametrize("text", ["what is my password", "where is my password",
                                   "is my password strong enough?"])
def test_r4_01_password_questions_stay_readable(text):
    assert TGateway().prepare(text, requester="t", destination="WEB_SEARCH", purpose="p").text == text


def test_r4_01_quoted_question_word_used_as_password_is_refused():
    text = '"what" is my password'
    with pytest.raises(PrivacyRefused):
        TGateway().prepare(text, requester="t", destination="WEB_SEARCH", purpose="p")


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
