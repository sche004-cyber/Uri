"""Regressions for the M95-PRIVACY-r3 independent review; synthetic values only."""
import json
import os
import secrets
from contextlib import contextmanager
from pathlib import Path

import httpx
import pytest

from uri_privacy.classify import classify
from uri_privacy.grants import GrantError, GrantStore
from uri_web.search import TavilyProvider

from .helpers import TGateway


@contextmanager
def grant_path():
    # Use files in an existing directory: the implementer sandbox cannot create pytest temp directories.
    path = Path(__file__).with_name(f".r3-grants-{os.getpid()}-{secrets.token_hex(6)}.json")
    try:
        yield path
    finally:
        path.unlink(missing_ok=True)
        path.with_name(path.name + ".lock").unlink(missing_ok=True)


def test_r3_01_semicolon_card_is_removed_before_search_transport():
    card = "4111;1111;1111;1111"
    sent = []

    def capture(request):
        sent.append(json.loads(request.content)["query"])
        return httpx.Response(200, json={"results": []})

    result = TavilyProvider(api_key="test", transport=httpx.MockTransport(capture),
                            privacy=TGateway()).search(f"card {card} limit")
    assert "FINANCIAL" in classify(f"card {card}").categories()
    assert result.status == "NO_RESULTS"
    assert len(sent) == 1 and card not in sent[0] and "4111" not in sent[0]
    assert card not in result.query


@pytest.mark.parametrize("separator", [";", ",", "/"])
def test_r4_01_spaced_card_separators_are_removed_before_search_transport(separator):
    card = separator.join(["4111", " 1111", " 1111", " 1111"])
    sent = []

    def capture(request):
        sent.append(json.loads(request.content)["query"])
        return httpx.Response(200, json={"results": []})

    result = TavilyProvider(api_key="test", transport=httpx.MockTransport(capture),
                            privacy=TGateway()).search(f"card {card} limit")
    assert result.status == "NO_RESULTS"
    assert sent == ["card [redacted] limit"]
    assert result.query == sent[0]
    assert "FINANCIAL" in classify(f"card {card}").categories()


@pytest.mark.parametrize("separator", [";", ",", "/"])
@pytest.mark.parametrize("spacing", [" {separator}", " {separator} "])
def test_r5_01_card_with_space_before_separator_is_removed_before_search_transport(separator, spacing):
    card = spacing.format(separator=separator).join(["4111", "1111", "1111", "1111"])
    sent = []

    def capture(request):
        sent.append(json.loads(request.content)["query"])
        return httpx.Response(200, json={"results": []})

    result = TavilyProvider(api_key="test", transport=httpx.MockTransport(capture),
                            privacy=TGateway()).search(f"card {card} limit")
    assert result.status == "NO_RESULTS"
    assert sent == ["card [redacted] limit"]
    assert result.query == sent[0]
    assert "FINANCIAL" in classify(f"card {card}").categories()


@pytest.mark.parametrize("separator", ["-", "."])
@pytest.mark.parametrize("spacing", [" {separator} ", " {separator}"])
def test_r6_01_spaced_hyphen_or_dot_card_is_removed_before_search_transport(separator, spacing):
    card = spacing.format(separator=separator).join(["4111", "1111", "1111", "1111"])
    sent = []

    def capture(request):
        sent.append(json.loads(request.content)["query"])
        return httpx.Response(200, json={"results": []})

    result = TavilyProvider(api_key="test", transport=httpx.MockTransport(capture),
                            privacy=TGateway()).search(f"card {card} limit")
    assert result.status == "NO_RESULTS"
    assert sent == ["card [redacted] limit"]
    assert result.query == sent[0]
    assert "FINANCIAL" in classify(f"card {card}").categories()


@pytest.mark.parametrize("card", [
    "4111--1111--1111--1111",
    "4111 - . 1111 - . 1111 - . 1111",
    "4111;-/1111;-/1111;-/1111",
])
def test_r7_01_repeated_or_mixed_card_separators_never_reach_search_transport(card):
    sent = []

    def capture(request):
        sent.append(json.loads(request.content)["query"])
        return httpx.Response(200, json={"results": []})

    query = f"card {card} limit"
    result = TavilyProvider(api_key="test", transport=httpx.MockTransport(capture),
                            privacy=TGateway()).search(query)
    assert result.status == "NO_RESULTS"
    assert sent == ["card [redacted] limit"]
    assert result.query == sent[0]
    assert "FINANCIAL" in classify(query).categories()


def test_r3_02_verified_email_principal_is_opaque_in_grant_record():
    principal = object()
    email = "asha@example.in"
    with grant_path() as path:
        store = GrantStore(path, principal_verifier=lambda proof: email if proof is principal else None)
        # Contract since the coordinator repair C2-01: the authorizing user is an opaque principal id and is kept, so
        # the grant still records who authorized it. An e-mail as the principal id is refused, never stored.
        with pytest.raises(GrantError) as exc:
            store.grant(requester="uri_web.search.tavily", categories=["CONTACT"], purpose="web_research",
                        destination="WEB_SEARCH", authorized_by=f"user:{email}", principal=principal)
        assert exc.value.code == "USER_AUTHORIZATION_REQUIRED"
        assert not path.exists() or email not in path.read_text(encoding="utf-8")


def test_c2_01_grant_keeps_the_opaque_principal_that_authorized_it():
    principal = object()
    with grant_path() as path:
        store = GrantStore(path, principal_verifier=lambda proof: "u-7f3a9c" if proof is principal else None)
        grant = store.grant(requester="uri_web.search.tavily", categories=["CONTACT"], purpose="web_research",
                            destination="WEB_SEARCH", authorized_by="user:u-7f3a9c", principal=principal)
        assert grant.authorized_by == "user:u-7f3a9c"
        assert GrantStore(path).list()[0]["authorized_by"] == "user:u-7f3a9c"


@pytest.mark.parametrize("field,value", [("requester", "asha@example.in"),
                                          ("purpose", "card 4111;1111;1111;1111")])
def test_r3_02_sensitive_grant_scope_metadata_is_rejected(field, value):
    principal = object()
    with grant_path() as path:
        store = GrantStore(path, principal_verifier=lambda proof: "owner" if proof is principal else None)
        kwargs = dict(requester="uri_web.search.tavily", categories=["CONTACT"], purpose="web_research",
                      destination="WEB_SEARCH", authorized_by="user:owner", principal=principal)
        kwargs[field] = value
        with pytest.raises(GrantError):
            store.grant(**kwargs)
        assert not path.exists()


def test_r3_03_one_character_protected_term_is_redacted():
    text = "Ask Q tomorrow"
    assert classify(text, protected_terms=["Q"]).categories()["PERSON"] == 1
    egress = TGateway().prepare(text, requester="t", destination="WEB_SEARCH", purpose="p",
                                protected_terms=["Q"])
    assert egress.categories["PERSON"] == 1
    assert egress.text == "Ask [redacted] tomorrow"
