"""AC-4, AC-7, AC-8: grants, value-free records, persistence, crash recovery."""
import json
import inspect
import os
import threading

import pytest

from .helpers import TGateway
from uri_privacy import PrivacyGateway, PrivacyRefused
from uri_privacy.audit import PrivacyAudit
from uri_privacy.grants import GrantError, GrantStore
from uri_privacy.vault import PersistentVaultStore, VaultError

AADHAAR, EMAIL = "2345 6789 0124", "asha.rao7@example.in"
windows = pytest.mark.skipif(os.name != "nt", reason="DPAPI is Windows-only")
_AUTHENTICATED_OWNER = object()


def _verify_principal(principal):
    return "owner" if principal is _AUTHENTICATED_OWNER else None


class Clock:
    def __init__(self):
        self.t = 1_000_000.0

    def __call__(self):
        return self.t


def store(tmp_path=None, clock=None):
    kwargs = {"clock": clock or Clock()}
    if "principal_verifier" in inspect.signature(GrantStore).parameters:
        kwargs["principal_verifier"] = _verify_principal
    return GrantStore(tmp_path / "grants.json" if tmp_path else None, **kwargs)


def grant(s, **kw):
    args = dict(requester="uri_web.search.tavily", categories=["GOV_ID"], purpose="web_research",
                destination="WEB_SEARCH", authorized_by="user:owner")
    if "principal" in inspect.signature(s.grant).parameters:
        args["principal"] = _AUTHENTICATED_OWNER
    args.update(kw)
    return s.grant(**args)


# --- AC-7 grants -------------------------------------------------------------------------------------------------------
def test_grant_allows_exactly_its_scope_once():
    s = store()
    g = TGateway(grants=s)
    gr = grant(s)
    e = g.prepare(f"status of Aadhaar {AADHAAR}", requester="uri_web.search.tavily", destination="WEB_SEARCH",
                  purpose="web_research")
    assert AADHAAR in e.text and e.grant_ids == [gr.grant_id]
    again = g.prepare(f"status of Aadhaar {AADHAAR}", requester="uri_web.search.tavily", destination="WEB_SEARCH",
                      purpose="web_research")
    assert AADHAAR not in again.text                           # single use


@pytest.mark.parametrize("field,value", [("requester", "uri_web.search.brave"), ("purpose", "other"),
                                         ("destination", "EXTERNAL_MODEL")])
def test_grant_does_not_match_another_scope(field, value):
    s = store()
    grant(s)
    q = dict(requester="uri_web.search.tavily", destination="WEB_SEARCH", purpose="web_research")
    q[field] = value
    e = TGateway(grants=s).prepare(f"Aadhaar {AADHAAR}", **q)
    assert AADHAAR not in e.text


def test_grant_does_not_cover_other_categories():
    s = store()
    grant(s)
    e = TGateway(grants=s).prepare(f"Aadhaar {AADHAAR} mail {EMAIL}", requester="uri_web.search.tavily",
                                         destination="WEB_SEARCH", purpose="web_research")
    assert AADHAAR in e.text and EMAIL not in e.text


def test_expiry_and_revocation_are_immediate():
    c = Clock()
    s = store(clock=c)
    g = TGateway(grants=s)
    a = grant(s, ttl_s=60, uses=5)
    c.t += 61
    assert s.match(requester=a.requester, category="GOV_ID", purpose=a.purpose, destination="WEB_SEARCH") is None
    b = grant(s, uses=5)
    assert s.revoke(b.grant_id)
    e = g.prepare(f"Aadhaar {AADHAAR}", requester=b.requester, destination="WEB_SEARCH", purpose=b.purpose)
    assert AADHAAR not in e.text
    grant(s, uses=5)
    assert s.revoke_requester("uri_web.search.tavily") == 1 and s.list() == []


@pytest.mark.parametrize("who", ["uri_web", "component:x", "", None, "user:", "admin:owner"])
def test_components_cannot_grant_themselves(who):
    with pytest.raises(GrantError) as e:
        grant(store(), authorized_by=who)
    assert e.value.code == "USER_AUTHORIZATION_REQUIRED"


@pytest.mark.parametrize("kw", [dict(ttl_s=0), dict(ttl_s=24 * 3600 + 1), dict(uses=0), dict(categories=[]),
                                dict(categories=["CREDENTIAL"]), dict(destination="LOCAL_BRAIN")])
def test_grant_limits(kw):
    with pytest.raises((GrantError, ValueError)):
        grant(store(), **kw)


def test_concurrent_consumption_never_exceeds_uses():
    s = store()
    gr = grant(s, uses=3)
    wins = []

    def use():
        if s.consume([gr.grant_id]):
            wins.append(1)
    ts = [threading.Thread(target=use) for _ in range(50)]
    [t.start() for t in ts]
    [t.join() for t in ts]
    assert len(wins) == 3


def test_grants_persist_and_revocation_survives_restart(tmp_path):
    s = store(tmp_path)
    a = grant(s, uses=2)
    s2 = store(tmp_path)
    assert s2.match(requester=a.requester, category="GOV_ID", purpose=a.purpose, destination="WEB_SEARCH") == a.grant_id
    s2.revoke(a.grant_id)
    assert store(tmp_path).list() == []


def test_malformed_grant_file_fails_closed(tmp_path):
    (tmp_path / "grants.json").write_text("{not json", encoding="utf-8")
    with pytest.raises(ValueError):
        store(tmp_path)


# --- AC-4 / AC-8 audit -------------------------------------------------------------------------------------------------
def test_audit_is_value_free_and_chained(tmp_path):
    a = PrivacyAudit(tmp_path / "audit.jsonl")
    g = TGateway(audit=a)
    g.prepare(f"Aadhaar {AADHAAR} mail {EMAIL}", requester="r", destination="EXTERNAL_MODEL", purpose="p", task_id="TASK-20261022-b00805ff")
    with pytest.raises(PrivacyRefused):
        g.prepare("password: Tr0ub4dor&3", requester="r", destination="WEB_SEARCH", purpose="p")
    raw = (tmp_path / "audit.jsonl").read_text(encoding="utf-8")
    for v in (AADHAAR, EMAIL, "Tr0ub4dor", "[[", "asha"):
        assert v not in raw
    recs = [json.loads(x) for x in raw.splitlines()]
    assert recs[0]["task_id"] == "TASK-20261022-b00805ff" and recs[0]["decision"] == "PSEUDONYMIZE" and recs[0]["policy"] == "m95.policy.v1"
    assert recs[1]["outcome"] == "REFUSED"
    assert a.verify() == {"ok": True, "count": 2, "head": recs[1]["hash"]}


def test_tampered_or_torn_audit_is_detected_and_not_appended(tmp_path):
    p = tmp_path / "audit.jsonl"
    a = PrivacyAudit(p)
    for i in range(3):
        a.write(requester="r", destination="LOG", purpose="p", policy="x", decision="ALLOW", outcome="ALLOWED")
    lines = p.read_text(encoding="utf-8").splitlines()
    rec = json.loads(lines[1])
    rec["decision"] = "REFUSE"
    p.write_text("\n".join([lines[0], json.dumps(rec), lines[2]]) + "\n", encoding="utf-8")
    assert PrivacyAudit.verify(a)["error"] == "CHAIN_BROKEN"
    with pytest.raises(RuntimeError):
        PrivacyAudit(p)
    # A bad line that is NOT the last one is damage, not a crash: still refused.
    p.write_bytes((lines[0] + "\n" + lines[1][:20] + "\n" + lines[2] + "\n").encode())
    with pytest.raises(RuntimeError):
        TGateway(audit=PrivacyAudit(p))
    # A torn LAST line (crash during an append) is quarantined with a full copy kept; the chain continues and the
    # recovery is itself recorded (review S1-07: one crash must not block every later egress).
    p.write_bytes((lines[0] + "\n" + lines[1][:20]).encode())
    v = PrivacyAudit(None)
    v.path = p
    assert v.verify()["error"] == "TORN_OR_CORRUPT_LINE"
    recovered = PrivacyAudit(p)
    assert recovered.verify()["ok"] and recovered.verify()["count"] == 2
    last = json.loads(p.read_text(encoding="utf-8").splitlines()[-1])
    assert last["outcome"] == "RECOVERED" and last["code"] == "AUDIT_TORN_TAIL_QUARANTINED"
    copies = list(tmp_path.glob("audit.jsonl.torn-*"))
    assert len(copies) == 1 and copies[0].read_bytes() == (lines[0] + "\n" + lines[1][:20]).encode()


def test_audit_rejects_unknown_fields():
    with pytest.raises(ValueError):
        PrivacyAudit().write(requester="r", value="leak")


# --- vault persistence (DPAPI) -----------------------------------------------------------------------------------------
@windows
def test_persistent_vault_is_ciphertext_with_dpapi_key_and_survives_restart(tmp_path):
    v = PersistentVaultStore(tmp_path)
    g = TGateway(vault=v)
    e = g.prepare(f"mail {EMAIL}", requester="r", destination="EXTERNAL_MODEL", purpose="p", scope="task-1")
    for f in tmp_path.rglob("*"):
        if f.is_file():
            assert EMAIL.encode() not in f.read_bytes() and b"asha" not in f.read_bytes()
    assert (tmp_path / "vault-key.dpapi").exists()
    g2 = TGateway(vault=PersistentVaultStore(tmp_path))
    with pytest.raises(PrivacyRefused) as wrong_owner:
        g2.restore(e.text, "task-1", requester="outsider")
    assert wrong_owner.value.code == "PRIVACY_SCOPE_OWNER_MISMATCH"
    assert g2.restore(e.text, "task-1", requester="r") == f"mail {EMAIL}"


@windows
def test_corrupted_vault_file_is_quarantined_and_refused(tmp_path):
    v = PersistentVaultStore(tmp_path)
    g = TGateway(vault=v)
    e = g.prepare(f"mail {EMAIL}", requester="r", destination="EXTERNAL_MODEL", purpose="p", scope="task-2")
    f = next((tmp_path / "refs").glob("*.ref"))
    f.write_bytes(f.read_bytes()[:-5] + b"xxxxx")
    g2 = TGateway(vault=PersistentVaultStore(tmp_path))
    with pytest.raises(PrivacyRefused) as x:
        g2.restore(e.text, "task-2", requester="r")
    assert x.value.code == "SCOPE_UNREADABLE"
    assert list((tmp_path / "quarantine").iterdir()) and not list((tmp_path / "refs").glob("*.ref"))


@windows
def test_expired_references_and_interrupted_writes_are_cleaned(tmp_path):
    c = Clock()
    v = PersistentVaultStore(tmp_path, clock=c)
    TGateway(vault=v).prepare(f"mail {EMAIL}", requester="r", destination="EXTERNAL_MODEL", purpose="p",
                                    scope="old", ttl_s=10)
    (tmp_path / "refs" / "x.ref.123.tmp").write_bytes(b"partial")
    c.t += 11
    assert PersistentVaultStore(tmp_path, clock=c).purge_expired() == 1
    assert not list((tmp_path / "refs").iterdir())


@windows
def test_dpapi_key_file_is_not_the_key(tmp_path):
    from uri_privacy.keys import KeyUnavailable, persistent_key
    k = persistent_key(tmp_path / "k.dpapi")
    assert len(k) == 32 and k not in (tmp_path / "k.dpapi").read_bytes()
    assert persistent_key(tmp_path / "k.dpapi") == k                     # D10: same secret on the next start
    (tmp_path / "k.dpapi").write_bytes(b"garbage")
    with pytest.raises(KeyUnavailable):
        persistent_key(tmp_path / "k.dpapi")                             # never silently replaced


def test_scope_ids_are_validated():
    with pytest.raises(PrivacyRefused) as e:
        TGateway().prepare(EMAIL, requester="r", destination="EXTERNAL_MODEL", purpose="p", scope="../../etc")
    assert e.value.code == "PRIVACY_INTERNAL_ERROR"
    assert isinstance(VaultError("X"), RuntimeError)
