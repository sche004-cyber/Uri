"""AC-10..AC-13: the gateway in its live consumers (web search, scheduler), loopback Brain clients and D10."""
import ast
import inspect
import json
import os
import secrets
from pathlib import Path

import httpx
import pytest

from uri_privacy import PrivacyGateway
from uri_privacy.grants import GrantStore
from uri_web import search as S

ROOT = Path(__file__).resolve().parents[2]
AADHAAR, EMAIL, CARD = "2345 6789 0124", "asha.rao7@example.in", "4111 1111 1111 1111"


def capture():
    sent = []

    def handler(req):
        sent.append(req)
        return httpx.Response(200, json={"results": [{"title": "t", "url": "https://example.com/a", "content": "c"}],
                                         "web": {"results": []}})
    return sent, httpx.MockTransport(handler)


def body(req):
    return req.content.decode("utf-8") + " " + str(req.url)


# --- AC-10 web search --------------------------------------------------------------------------------------------------
@pytest.mark.parametrize("cls,kw", [(S.TavilyProvider, {"api_key": "k"}), (S.BraveProvider, {"api_key": "k"}),
                                    (S.SearxngProvider, {"base_url": "https://searx.example.org"})])
def test_secret_in_query_is_never_sent(cls, kw):
    sent, t = capture()
    p = cls(transport=t, privacy=PrivacyGateway(), **kw)
    r = p.search("my netbanking password: Mango#2026! why does login fail")
    assert r.status == S.REFUSED and r.error_code == "PRIVACY_REFUSED" and r.query == "" and sent == []


@pytest.mark.parametrize("query", ["password\uff1a Mango#2026!", "card 4111\u200b1111\u200b1111\u200b1111"])
def test_unicode_obfuscated_sensitive_query_never_reaches_transport(query):
    sent, transport = capture()
    result = S.TavilyProvider(api_key="k", transport=transport, privacy=PrivacyGateway()).search(query)
    assert result.status == S.REFUSED and result.query == "" and sent == []


def test_identifiers_are_removed_from_the_sent_query():
    sent, t = capture()
    g = PrivacyGateway()
    r = S.TavilyProvider(api_key="k", transport=t, privacy=g).search(f"refund status card {CARD} mail {EMAIL}")
    assert r.status == S.OK and len(sent) == 1
    wire = body(sent[0])
    assert CARD.replace(" ", "") not in wire.replace(" ", "") and EMAIL not in wire and "refund status" in wire
    assert CARD not in r.query and EMAIL not in r.query
    assert g.audit.records[-1]["requester"] == "uri_web.search.tavily"


def test_ordinary_queries_are_unchanged():
    sent, t = capture()
    q = "diwali 2026 date karnataka holiday list"
    r = S.TavilyProvider(api_key="k", transport=t, privacy=PrivacyGateway()).search(q)
    assert r.query == q and json.loads(sent[0].content)["query"] == q


def test_query_that_is_only_an_identifier_is_refused_not_sent_empty():
    sent, t = capture()
    r = S.TavilyProvider(api_key="k", transport=t, privacy=PrivacyGateway()).search(EMAIL)
    assert r.status == S.REFUSED and r.error_code == "PRIVACY_QUERY_EMPTY" and sent == []


def test_user_grant_allows_the_identifier_once():
    sent, t = capture()
    owner = object()
    if "principal_verifier" in inspect.signature(GrantStore).parameters:
        g = PrivacyGateway(grants=GrantStore(principal_verifier=lambda p: "owner" if p is owner else None))
        proof = {"principal": owner}
    else:
        g, proof = PrivacyGateway(), {}
    g.grants.grant(requester="uri_web.search.tavily", categories=["CONTACT"], purpose="web_research",
                   destination="WEB_SEARCH", authorized_by="user:owner", **proof)
    p = S.TavilyProvider(api_key="k", transport=t, privacy=g)
    p.search(f"who is {EMAIL}")
    p.search(f"who is {EMAIL}")
    assert EMAIL in body(sent[0]) and EMAIL not in body(sent[1])


def test_default_gateway_is_used_when_none_is_injected(monkeypatch):
    sent, t = capture()
    r = S.TavilyProvider(api_key="k", transport=t).search("api key sk-abcdefghijklmnopqrstuvwx leaked?")
    assert r.status == S.REFUSED and sent == []


# --- AC-11 scheduler ---------------------------------------------------------------------------------------------------
@pytest.fixture
def sched(tmp_path):
    from tests.scheduler.test_engine import Clock, FakeHarness
    from uri_scheduler.engine import Scheduler
    h = FakeHarness()
    s = Scheduler(tmp_path / "state", harness=h, now_fn=Clock("2026-10-09T10:00:00+05:30")).start()
    yield s, h, tmp_path
    s.close()


def _job(s, params):
    p = s.propose(owner="owner", title="t", template_id="festival_gif.v1", params=params,
                  schedule={"kind": "once", "at": "2026-10-09T10:00"})
    s.confirm(p["job_id"], "owner", p["proposal_sha256"])
    return s.tick()


def test_scheduler_redacts_contact_details_before_the_harness(sched):
    s, h, tmp = sched
    _job(s, {"festival": {"key": "diwali", "name": "Diwali"}, "audience": f"family; reply to {EMAIL}"})
    assert len(h.calls) == 1 and EMAIL not in h.calls[0]["instructions"]
    task = next((tmp / "state" / "work").rglob("task.json")).read_text(encoding="utf-8")
    assert EMAIL not in task and "family" in task
    audit = (tmp / "state" / "privacy" / "audit.jsonl").read_text(encoding="utf-8")
    assert EMAIL not in audit and "uri_scheduler.festival_gif.v1" in audit


def test_scheduler_refuses_credentials_before_any_attempt(sched):
    s, h, _ = sched
    out = _job(s, {"festival": {"key": "diwali", "name": "Diwali"}, "audience": "friends, wifi password: Tr0ub4dor&3"})
    assert h.calls == []
    assert out[0]["result"] == "NEEDS_ATTENTION" and out[0]["reason"] == "PRIVACY_REFUSED:PRIVACY_REFUSED"
    assert s.store.q1("SELECT COUNT(*) FROM attempt")[0] == 0
    ev = [e for e in s.store.events() if e["kind"] == "occurrence.privacy_refused"]
    assert ev and "Tr0ub4dor" not in json.dumps(ev)


@pytest.mark.parametrize("festival,refused", [(f"Diwali {EMAIL}", False),
                                            ("Diwali password: Mango#2026!", True)])
def test_scheduler_prepares_calendar_metadata_before_attempt(sched, festival, refused):
    s, h, tmp = sched
    proposal = s.propose(owner="owner", title="t", template_id="festival_gif.v1",
                         params={"festival": {"key": "diwali", "name": "Diwali"}},
                         schedule={"kind": "once", "at": "2026-10-09T10:00"})
    s.confirm(proposal["job_id"], "owner", proposal["proposal_sha256"])
    with s.store.tx() as db:
        row = db.execute("SELECT occ_id,meta_json FROM occurrence WHERE job_id=?", (proposal["job_id"],)).fetchone()
        meta = json.loads(row["meta_json"] or "{}")
        meta.update(festival=festival, calendar_record={"name": festival})
        db.execute("UPDATE occurrence SET meta_json=? WHERE occ_id=?", (json.dumps(meta), row["occ_id"]))
    outcome = s.tick()
    if refused:
        assert outcome[0]["result"] == "NEEDS_ATTENTION"
        assert h.calls == [] and s.store.q1("SELECT COUNT(*) FROM attempt")[0] == 0
        assert not (tmp / "state" / "work").exists()
    else:
        task = next((tmp / "state" / "work").rglob("task.json")).read_text(encoding="utf-8")
        assert EMAIL not in task and len(h.calls) == 1


def test_scheduler_revision_instruction_is_sanitized(sched):
    s, h, _ = sched
    _job(s, {"festival": {"key": "diwali", "name": "Diwali"}})
    a1 = s.overview()["pending_approvals"][0]["candidates"][0]
    s.review(a1["artifact_id"], "owner", "refine", expected_sha256=a1["sha256"],
             instruction=f"More floral energy, sign it from {EMAIL}")
    s.tick()
    assert "More floral energy" in h.calls[-1]["instructions"] and EMAIL not in h.calls[-1]["instructions"]


# --- AC-12 loopback Brain clients ---------------------------------------------------------------------------------------
@pytest.mark.parametrize("url", ["http://10.0.0.5:18470", "http://example.com", "http://localhost.evil.test:1",
                                 "file:///etc/passwd", "", None, "http://[::ffff:8.8.8.8]:80"])
def test_brain_client_refuses_non_loopback(url):
    from uri_operational_intelligence import brain_client as BC
    with pytest.raises(BC.NotLoopback):
        BC.BrainClient(url)


def test_brain_client_ignores_proxies(monkeypatch):
    from uri_operational_intelligence import brain_client as BC
    monkeypatch.setenv("HTTP_PROXY", "http://127.0.0.1:9")
    c = BC.BrainClient("http://127.0.0.1:18470")._get()
    assert c._trust_env is False
    for ipv6 in ("http://[::1]:18470",):
        BC.BrainClient(ipv6)


def test_office_refuses_a_remote_brain_url(tmp_path, capsys):
    from uri_office import service
    with pytest.raises(SystemExit) as e:
        service.main(["run", "--state", str(tmp_path), "--owner", "owner", "--brain-url", "http://192.168.1.20:18470"])
    assert e.value.code == 2 and "BRAIN_ENDPOINT_NOT_LOOPBACK" in capsys.readouterr().err


# --- AC-13 D10 ---------------------------------------------------------------------------------------------------------
def _server_persistent_secret():
    """The launcher refuses to import outside isolated mode, so its function is compiled on its own."""
    src = (ROOT / "scripts" / "run_uri_integrated_server.py").read_text(encoding="utf-8")
    fn = next(n for n in ast.parse(src).body if isinstance(n, ast.FunctionDef) and n.name == "persistent_secret")
    from uri_core.core.runtime_identity import RuntimeIdentityError, dpapi
    ns = {"Path": Path, "os": os, "secrets": secrets, "dpapi": dpapi, "RuntimeIdentityError": RuntimeIdentityError}
    exec(compile(ast.Module([fn], []), "persistent_secret", "exec"), ns)
    return ns["persistent_secret"], RuntimeIdentityError, src


def test_launcher_no_longer_generates_a_secret_per_start():
    _, _, src = _server_persistent_secret()
    assert "token_hex(32)" not in src.split("def main", 1)[1]
    assert 'persistent_secret(state / "secure" / "provider-key-secret.dpapi")' in src


@pytest.mark.skipif(os.name != "nt", reason="DPAPI is Windows-only")
def test_launcher_secret_is_stable_protected_and_never_replaced(tmp_path):
    fn, err, _ = _server_persistent_secret()
    p = tmp_path / "secure" / "provider-key-secret.dpapi"
    a = fn(p)
    assert fn(p) == a and len(a) == 64 and bytes.fromhex(a) not in p.read_bytes()
    p.write_bytes(b"not a dpapi blob")
    with pytest.raises(err):
        fn(p)
    assert p.read_bytes() == b"not a dpapi blob"


@pytest.mark.skipif(os.name != "nt", reason="DPAPI is Windows-only")
def test_provider_keys_survive_a_restart_with_the_persistent_secret(tmp_path, monkeypatch):
    """The D10 symptom end to end: a key saved before a restart is readable after it (and was not with a per-start
    random secret)."""
    fn, _, _ = _server_persistent_secret()
    from uri_core.core import provider_keys as PK
    monkeypatch.setattr(PK, "user_scoped_path", lambda uid, name: str(tmp_path / "users" / uid / name))
    uid, synthetic_key = "0b5c1d2e-3f40-4a5b-8c6d-7e8f90a1b2c3", "sk-synthetic-" + "x" * 24
    secret_file = tmp_path / "secure" / "provider-key-secret.dpapi"
    monkeypatch.setenv("URI_PROVIDER_KEY_SECRET", fn(secret_file))                     # first start
    PK.ProviderKeyStore(uid).set_key("openai", synthetic_key)
    monkeypatch.setenv("URI_PROVIDER_KEY_SECRET", fn(secret_file))                     # restart
    assert PK.ProviderKeyStore(uid).get_key_for_use("openai") == synthetic_key
    monkeypatch.setenv("URI_PROVIDER_KEY_SECRET", secrets.token_hex(32))              # old behaviour: new secret
    try:
        lost = PK.ProviderKeyStore(uid).get_key_for_use("openai")
    except Exception:                                                                    # noqa: BLE001
        lost = None
    assert lost != synthetic_key
