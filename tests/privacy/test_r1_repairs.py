"""Regressions for the first independent M95 privacy review."""
import json
import inspect
import multiprocessing

import pytest

from uri_privacy import PrivacyGateway, PrivacyRefused

from .helpers import TGateway
from uri_privacy.audit import PrivacyAudit
from uri_privacy.grants import GrantError, GrantStore


EMAIL = "asha@example.in"


def _consume_from_process(path, grant_id, ready, go, results):
    store = GrantStore(path)
    ready.put(True)
    if go.wait(10):
        results.put(store.consume([grant_id]))


def _grant_for_consumption(path, owner):
    # Keep the regression runnable on the reviewed SHA's original API.
    if "principal_verifier" in inspect.signature(GrantStore).parameters:
        store = GrantStore(path, principal_verifier=lambda p: "owner" if p is owner else None)
        proof = {"principal": owner}
    else:
        store, proof = GrantStore(path), {}
    grant = store.grant(requester="r", categories=["CONTACT"], purpose="p", destination="WEB_SEARCH",
                        authorized_by="user:owner", **proof)
    return store, grant


def test_unverified_user_label_cannot_create_a_disclosure_grant():
    grants = GrantStore()
    with pytest.raises(GrantError) as exc:
        grants.grant(requester="r", categories=["CONTACT"], purpose="p", destination="WEB_SEARCH",
                     authorized_by="user:owner")
    assert exc.value.code == "USER_AUTHORIZATION_REQUIRED"
    assert grants.list() == []


def test_audit_replaces_content_in_caller_supplied_identifiers(tmp_path):
    path = tmp_path / "audit.jsonl"
    gateway = PrivacyGateway(audit=PrivacyAudit(path))
    # Stricter since the R2 repair: an unregistered requester is refused and only the marker is recorded.
    with pytest.raises(PrivacyRefused) as exc:
        gateway.prepare("ordinary text", requester=EMAIL, task_id="4111 1111 1111 1111",
                        destination="WEB_SEARCH", purpose="password: Mango#2026!")
    assert exc.value.code == "PRIVACY_REQUESTER_UNKNOWN"
    raw = path.read_text(encoding="utf-8")
    assert EMAIL not in raw and "4111 1111 1111 1111" not in raw and "Mango#2026!" not in raw
    record = json.loads(raw)
    assert record["requester"] == record["task_id"] == record["purpose"] == "UNTRUSTED_FIELD"
    assert gateway.audit.verify()["ok"]


def test_scope_restoration_requires_original_requester():
    gateway = TGateway()
    egress = gateway.prepare(EMAIL, requester="owner", destination="EXTERNAL_MODEL", purpose="p", scope="scope-a")
    with pytest.raises(PrivacyRefused) as exc:
        gateway.restore(egress.text, egress.scope, requester="outsider")
    assert exc.value.code == "PRIVACY_SCOPE_OWNER_MISMATCH"
    assert gateway.restore(egress.text, egress.scope, requester="owner") == EMAIL
    with pytest.raises(PrivacyRefused):
        gateway.prepare(EMAIL, requester="outsider", destination="EXTERNAL_MODEL", purpose="p", scope="scope-a")


def test_persisted_single_use_cannot_be_consumed_by_stale_store(tmp_path):
    owner = object()
    path = tmp_path / "grants.json"
    first, grant = _grant_for_consumption(path, owner)
    second = GrantStore(path)
    assert first.consume([grant.grant_id])
    assert not second.consume([grant.grant_id])
    assert GrantStore(path).list() == []


def test_persisted_grant_has_one_winner_across_processes(tmp_path):
    owner = object()
    path = tmp_path / "grants.json"
    _, grant = _grant_for_consumption(path, owner)
    ctx = multiprocessing.get_context("spawn")
    ready, results, go = ctx.Queue(), ctx.Queue(), ctx.Event()
    children = [ctx.Process(target=_consume_from_process, args=(path, grant.grant_id, ready, go, results))
                for _ in range(2)]
    try:
        for child in children:
            child.start()
        for _ in children:
            assert ready.get(timeout=10)
        go.set()
        assert sorted(results.get(timeout=10) for _ in children) == [False, True]
    finally:
        go.set()
        for child in children:
            child.join(timeout=10)
            if child.is_alive():
                child.terminate()
                child.join(timeout=10)
    assert all(child.exitcode == 0 for child in children)
