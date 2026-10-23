"""Regressions for driver round R2 (Codex, on bce706ca) and the imported subagent review S1 (on 32ed8594).

Each test reproduces the reviewer's own probe; synthetic data only.
"""
import json
import os
import time

import httpx
import pytest

from uri_privacy import PrivacyRefused
from uri_privacy.audit import PrivacyAudit
from uri_privacy.classify import classify
from uri_web import search as S

from .helpers import TGateway

CARD = "4111 1111 1111 1111"
windows = pytest.mark.skipif(os.name != "nt", reason="DPAPI is Windows-only")


def capture():
    sent = []

    def handler(req):
        sent.append(req)
        return httpx.Response(200, json={"results": [{"title": "t", "url": "https://example.com/a", "content": "c"}]})
    return sent, httpx.MockTransport(handler)


def wire_query(req):
    return json.loads(req.content)["query"]


def prep(g, text, dest="WEB_SEARCH", **kw):
    return g.prepare(text, requester=kw.pop("requester", "t"), destination=dest, purpose=kw.pop("purpose", "p"), **kw)


# --- R2-01: a disguised value next to a detected one ------------------------------------------------------------------
def test_r2_01_second_card_hidden_by_zero_width_characters_is_removed():
    q = f"card {CARD}​9 and card 4111​1111​1111​1111 limit"
    try:
        out = prep(TGateway(), q).text
    except PrivacyRefused as exc:                 # LDEC-005: invisible characters among digits are refused
        assert exc.code == "PRIVACY_DISGUISE_REFUSED"
        return
    assert "4111" not in out.replace("​", "")


# --- R2-02: encodings -------------------------------------------------------------------------------------------------
@pytest.mark.parametrize("q", ["password%3DMango%232026", "password%3AMango%232026", "password%253AMango%25232026",
                               "password&#58;Mango#2026", "password&colon; Mango#2026"])
def test_r2_02_encoded_credentials_never_reach_web_search(q):
    sent, t = capture()
    r = S.TavilyProvider(api_key="k", transport=t, privacy=TGateway()).search(q)
    assert r.status == S.REFUSED and r.error_code in ("PRIVACY_REFUSED", "PRIVACY_DISGUISE_REFUSED") and sent == []


# --- R2-03 / R1-03: audit fields ---------------------------------------------------------------------------------------
@pytest.mark.parametrize("requester", ["sha256:" + "ab" * 32, "A1234567", "asha@example.in"])
def test_r2_03_unregistered_requester_is_refused_and_never_recorded(tmp_path, requester):
    a = PrivacyAudit(tmp_path / "audit.jsonl")
    g = TGateway(audit=a)
    with pytest.raises(PrivacyRefused) as e:
        g.prepare("hello", requester=requester, destination="WEB_SEARCH", purpose="p")
    assert e.value.code == "PRIVACY_REQUESTER_UNKNOWN"
    assert requester not in (tmp_path / "audit.jsonl").read_text(encoding="utf-8")


@pytest.mark.parametrize("task_id", ["sha256:" + "cd" * 32, "A1234567", "4111 1111 1111 1111", "T1"])
def test_r2_03_unrecognized_task_ids_are_not_recorded(tmp_path, task_id):
    g = TGateway(audit=PrivacyAudit(tmp_path / "a.jsonl"))
    g.prepare("hello", requester="t", destination="WEB_SEARCH", purpose="p", task_id=task_id)
    raw = (tmp_path / "a.jsonl").read_text(encoding="utf-8")
    assert task_id not in raw and json.loads(raw)["task_id"] == "UNTRUSTED_FIELD"


def test_r2_03_every_audit_field_is_allowlisted():
    a = PrivacyAudit()
    rec = a.write(requester="t", task_id="job_0123456789ab:3:1", destination="NOWHERE", purpose="hash:abc",
                  policy="x", decision="ALLOW; asha@example.in", outcome="fine", code="A1234567",
                  categories={"asha@example.in": 1, "CONTACT": 2, "GOV_ID": "x"}, grant_ids=["GR-0123456789ab", "x"])
    assert rec["task_id"] == "job_0123456789ab:3:1" and rec["categories"] == {"CONTACT": 2}
    assert rec["grant_ids"] == ["GR-0123456789ab"]
    for k in ("requester", "destination", "purpose", "policy", "decision", "outcome", "code"):
        assert rec[k] == "UNTRUSTED_FIELD", k                 # "t" is not registered on a bare PrivacyAudit


# --- R2-04: research query recorded before the privacy decision --------------------------------------------------------
def test_r2_04_research_command_sanitizes_before_any_event(monkeypatch, tmp_path):
    monkeypatch.setenv("URI_PRIVACY_HOME", str(tmp_path / "privacy"))
    import uri_privacy.gateway as G
    monkeypatch.setattr(G, "_default", None)
    from uri_web import bridge as B
    events = []
    web = B.WebResearch(write_event=events.append, brain_complete=None, brain_idle=lambda: True,
                        providers_factory=lambda: [], defer_start=True)
    with pytest.raises(B.Refused) as e:
        web._web_research({"query": "bank login fails, password: Tr0ub4dor&3", "urls": [], "feeds": [],
                           "use_brain": False})
    assert e.value.code == "PRIVACY_REFUSED" and "Tr0ub4dor" not in json.dumps(events)
    assert B.WebResearch._private_query("refund for asha.rao7@example.in order") == "refund for [redacted] order"


# --- S1-01: rewriting must not assemble a value -----------------------------------------------------------------------
@pytest.mark.parametrize("q", ["card 4111 1111 a@b.co 1111 1111 limit", "card 4111  1111  1111  1111",
                               "card 4111\n1111\n1111\n1111"])
def test_s1_01_no_card_is_assembled_on_the_wire(q):
    sent, t = capture()
    r = S.TavilyProvider(api_key="k", transport=t, privacy=TGateway()).search(q)
    for req in sent:
        assert not classify(wire_query(req)).categories().get("FINANCIAL")
    assert r.status in (S.OK, S.REFUSED)


def test_s1_01_protected_term_with_odd_spacing_is_found():
    e = prep(TGateway(), "Ask Asha  Kumar about it", protected_terms=["Asha Kumar"])
    assert "Kumar" not in e.text and e.categories == {"PERSON": 1}


def test_s1_01_output_is_rechecked_before_it_leaves(monkeypatch):
    """Even if a rewrite produced a disallowed value, the residual check refuses (defence in depth)."""
    g = TGateway()
    monkeypatch.setattr(type(g), "_rewrite", lambda self, text, *a, **k: (f"card {CARD}", None))
    with pytest.raises(PrivacyRefused) as e:
        prep(g, "nothing sensitive here")
    assert e.value.code == "PRIVACY_REFUSED"


# --- S1-02: overlapping detections ------------------------------------------------------------------------------------
def test_s1_02_address_containing_an_account_is_redacted_whole():
    out = prep(TGateway(), "deliver to flat 12B, Lakeview Apartments, a/c 123456789012, MG road").text
    assert "Lakeview" not in out and "MG road" not in out and "123456789012" not in out


def test_s1_02_a_grant_for_one_category_never_releases_another_in_the_same_span():
    from uri_privacy.grants import GrantStore
    owner = object()
    grants = GrantStore(principal_verifier=lambda p: "owner" if p is owner else None)
    grants.grant(requester="t", categories=["ADDRESS"], purpose="p", destination="WEB_SEARCH",
                 authorized_by="user:owner", principal=owner, uses=5)
    out = prep(TGateway(grants=grants), "flat 12, mail asha@example.in or ring +91 98765 43210, MG road").text
    assert "asha@example.in" not in out and "98765" not in out


# --- S1-03: scope ids --------------------------------------------------------------------------------------------------
@pytest.mark.parametrize("bad", ["../../victim", "..\\..\\victim", "a/b", "x\n", "", "a" * 97])
def test_s1_03_invalid_scope_ids_are_refused_everywhere(tmp_path, bad):
    from uri_privacy.vault import MemoryVaultStore, VaultError
    victim = tmp_path / "victim.ref"
    victim.write_bytes(b"keep me")
    v = MemoryVaultStore()
    for call in (lambda: v.get(bad), lambda: v.close(bad), lambda: v.open(bad, 60)):
        with pytest.raises(VaultError):
            call()
    with pytest.raises(PrivacyRefused):
        TGateway(vault=v).restore("x", bad, requester="t")
    assert victim.read_bytes() == b"keep me"


@windows
def test_s1_03_persistent_scope_files_do_not_collide_or_escape(tmp_path):
    from uri_privacy.vault import PersistentVaultStore
    home = tmp_path / "vault"
    outside = tmp_path / "victim.ref"
    outside.write_bytes(b"keep me")
    g = TGateway(vault=PersistentVaultStore(home, key=b"k" * 32))
    a = g.prepare("mail alice@example.in", requester="alice", destination="EXTERNAL_MODEL", purpose="p", scope="task:1")
    g2 = TGateway(vault=PersistentVaultStore(home, key=b"k" * 32))
    for sid in ("task_1", "Task:1", "TASK:1"):
        g2.prepare("mail bob@example.in", requester="bob", destination="EXTERNAL_MODEL", purpose="p", scope=sid)
    g3 = TGateway(vault=PersistentVaultStore(home, key=b"k" * 32))
    assert g3.restore(a.text, "task:1", requester="alice") == "mail alice@example.in"
    with pytest.raises(PrivacyRefused):
        g3.close_scope("../victim")
    assert outside.read_bytes() == b"keep me"
    assert not list((home / "quarantine").glob("*")) if (home / "quarantine").exists() else True


# --- S1-04: no catastrophic backtracking ------------------------------------------------------------------------------
@pytest.mark.parametrize("label", ["account", "passport", "pan", "ssn", "pincode", "password", "otp"])
def test_s1_04_label_followed_by_a_long_space_run_is_fast(label):
    text = label + " " * 5000 + "x"
    t = time.perf_counter()
    prep(TGateway(), text, dest="EXTERNAL_AGENT", reversible=False)
    assert time.perf_counter() - t < 0.5


def test_s1_04_m95_detectors_are_linear_on_adversarial_shapes():
    from uri_privacy import classify as C
    # The reviewer's shape: a label, then a long run of spaces, run through the raw patterns (without folding).
    for label, rx in (("account", C._ACCOUNT), ("passport", C._PASSPORT), ("pan", C._PAN), ("ssn", C._SSN),
                      ("pincode", C._PINCODE), ("otp", C._LABELLED), ("flat 1", C._STREET)):
        text = label + " " * 600 + "x"
        t = time.perf_counter()
        list(rx.finditer(text))
        assert time.perf_counter() - t < 0.25, label


# --- S1-05: recall gaps -----------------------------------------------------------------------------------------------
@pytest.mark.parametrize("text,cat", [
    ("my ssn is 123456789", "GOV_ID"), ("ssn 123 45 6789", "GOV_ID"), ("ssn 123.45.6789", "GOV_ID"),
    ("ssn 123–45–6789", "GOV_ID"),
    ("card ٤١١١١١١١١١١١١١١١", "FINANCIAL"),
    ("card 4111/1111/1111/1111", "FINANCIAL"), ("card 4111_1111_1111_1111", "FINANCIAL"),
    ("card 4111  1111  1111  1111", "FINANCIAL"), ("card 4111\n1111\n1111\n1111", "FINANCIAL"),
    ("aadhaar 2345.6789.0124", "GOV_ID"), ("iban gb82 west 1234 5698 7654 32", "FINANCIAL"),
    ("pan abcpe1234f", "GOV_ID"), ("abcpe1234f", "GOV_ID"),
])
def test_s1_05_common_forms_are_detected(text, cat):
    assert cat in classify(text).categories()


def test_s1_05_new_rules_keep_ordinary_numbers_readable():
    for benign in ("dates 2026/10/22 and 2026_10_23", "version 1.2.3.4",          # a 13-digit total: LDEC-006
                   "price 4,500.00", "order 12345678"):
        assert not classify(benign).categories(), benign


# --- S1-06: grants are not burnt by a failed egress -------------------------------------------------------------------
def test_s1_06_failed_rewrite_does_not_consume_the_grant():
    from uri_privacy.grants import GrantStore
    owner = object()
    grants = GrantStore(principal_verifier=lambda p: "owner" if p is owner else None)
    gr = grants.grant(requester="t", categories=["FINANCIAL"], purpose="p", destination="EXTERNAL_MODEL",
                      authorized_by="user:owner", principal=owner)
    with pytest.raises(PrivacyRefused):
        prep(TGateway(grants=grants), f"card {CARD} mail a@b.co", dest="EXTERNAL_MODEL", scope="bad scope/!")
    assert [g for g in grants.list() if g["grant_id"] == gr.grant_id][0]["uses_left"] == 1


# --- S1-07: failures are privacy refusals -----------------------------------------------------------------------------
def test_s1_07_corrupt_privacy_home_refuses_the_search_without_raising(monkeypatch, tmp_path):
    home = tmp_path / "privacy"
    home.mkdir()
    (home / "grants.json").write_text("{not json", encoding="utf-8")
    monkeypatch.setenv("URI_PRIVACY_HOME", str(home))
    import uri_privacy.gateway as G
    monkeypatch.setattr(G, "_default", None)
    sent, t = capture()
    r = S.TavilyProvider(api_key="k", transport=t).search("weather in Kochi")
    assert r.status == S.REFUSED and r.error_code == "PRIVACY_INTERNAL_ERROR" and sent == []


def test_s1_07_restore_failure_of_any_kind_is_audited(monkeypatch):
    g = TGateway()
    e = prep(g, "mail a@b.co", dest="EXTERNAL_MODEL")
    monkeypatch.setattr(type(g.vault), "get", lambda self, sid: (_ for _ in ()).throw(OSError("disk")))
    with pytest.raises(PrivacyRefused) as x:
        g.restore(e.text, e.scope, requester="t")
    assert x.value.code == "PRIVACY_RESTORE_FAILED" and g.audit.records[-1]["outcome"] == "REFUSED"


# --- S1-08: scheduler edges -------------------------------------------------------------------------------------------
@pytest.fixture
def sched(tmp_path):
    from tests.scheduler.test_engine import Clock, FakeHarness
    from uri_scheduler.engine import Scheduler
    h = FakeHarness()
    s = Scheduler(tmp_path / "state", harness=h, now_fn=Clock("2026-10-09T10:00:00+05:30")).start()
    yield s, h
    s.close()


def _job(s, params):
    p = s.propose(owner="owner", title="t", template_id="festival_gif.v1", params=params,
                  schedule={"kind": "once", "at": "2026-10-09T10:00"})
    s.confirm(p["job_id"], "owner", p["proposal_sha256"])
    return s.tick()


def test_s1_08_numbers_that_would_be_redacted_refuse_the_task(sched):
    """The template only accepts festival/style/audience params today, so the guard is exercised directly: a nested
    number that the gateway would rewrite cannot be passed through unchanged."""
    s, _ = sched
    with pytest.raises(PrivacyRefused):
        s._sanitize_for_harness({"festival": {"calendar_record": {"n": 4111111111111111}}},
                                requester="uri_scheduler.festival_gif.v1", task_id=None)
    assert s._sanitize_for_harness({"n": 2026, "ok": True}, requester="uri_scheduler.festival_gif.v1",
                                   task_id=None) == {"n": 2026, "ok": True}


def test_s1_08_owner_cancel_wins_over_a_privacy_refusal(sched, monkeypatch):
    s, h = sched
    real = s._sanitize_for_harness

    def cancel_then_refuse(value, **kw):
        for occ in s.store.q("SELECT occ_id FROM occurrence"):
            s.store.db.execute("UPDATE occurrence SET reason='CANCEL_REQUESTED' WHERE occ_id=?", (occ["occ_id"],))
        raise PrivacyRefused("PRIVACY_REFUSED")
    monkeypatch.setattr(s, "_sanitize_for_harness", cancel_then_refuse)
    out = _job(s, {"festival": {"key": "diwali", "name": "Diwali"}})
    assert out[0]["result"] == "CANCELLED" and h.calls == []
    assert real is not None


def test_s1_08_server_secret_survives_a_volume_without_hard_links(tmp_path, monkeypatch):
    if os.name != "nt":
        pytest.skip("DPAPI is Windows-only")
    from tests.privacy.test_integrations import _server_persistent_secret
    fn, _, _ = _server_persistent_secret()
    monkeypatch.setattr(os, "link", lambda *a, **k: (_ for _ in ()).throw(OSError(1, "not supported")))
    p = tmp_path / "secure" / "s.dpapi"
    assert fn(p) == fn(p) and p.exists()
