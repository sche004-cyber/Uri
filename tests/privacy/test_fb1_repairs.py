"""Regressions for the V3.1 fallback review FB1 of 76f875d1 (docs/privacy/reviews/FB1_fallback_review_76f875d1.txt),
the coordinator's own finding C1-01 (cross-process grant lock) and the OD-1a external-harness gate.

Each test reproduces the reviewer's probe; synthetic data only.
"""
import ast
import json
import multiprocessing
import os
import time
from pathlib import Path

import httpx
import pytest

from uri_privacy import PrivacyRefused
from uri_privacy.classify import classify, fold
from uri_web import search as S

from .helpers import TGateway

ROOT = Path(__file__).resolve().parents[2]
CARD_DIGITS = "4111111111111111"


def capture():
    sent = []

    def handler(req):
        sent.append(req)
        return httpx.Response(200, json={"results": [{"title": "t", "url": "https://example.com/a", "content": "c"}]})
    return sent, httpx.MockTransport(handler)


def wire_digits(req):
    q = json.loads(req.content)["query"]
    return "".join(ch for ch in fold(q)[0] if ch.isdigit())


def search(q):
    sent, t = capture()
    r = S.TavilyProvider(api_key="k", transport=t, privacy=TGateway()).search(q)
    return r, sent


# --- FB1 R1-01: invisible and combining marks -------------------------------------------------------------------------
@pytest.mark.parametrize("mark", ["͏", "️", "́", "̶", "\U000e0100"])
def test_fb1_r1_01_card_with_marks_never_reaches_the_wire(mark):
    r, sent = search(f"card 4111{mark}1111{mark}1111{mark}1111 limit")
    assert all(CARD_DIGITS not in wire_digits(q) for q in sent)


@pytest.mark.parametrize("q", ["pass͏word: Mango#2026", "password️: Mango#2026", "p̶assword: Mango#2026!",
                               "wifi p̶assword: Mango#2026!", "card 41́11 1111 1111 1111"])
def test_fb1_r1_01_disguised_values_are_refused_or_removed(q):
    r, sent = search(q)
    if "Mango" in q:
        assert r.status == S.REFUSED and r.error_code == "PRIVACY_REFUSED" and sent == []
    else:
        assert all(CARD_DIGITS not in wire_digits(x) for x in sent)


def test_fb1_r1_01_marks_on_other_scripts_stay_readable():
    for text in ("नमस्ते दुनिया",   # Devanagari with virama
                 "café crème brûlée"):
        assert not classify(text).categories()
        import unicodedata                                   # what leaves URI is the NFKC (canonical) form
        assert (TGateway().prepare(text, requester="t", destination="WEB_SEARCH", purpose="p").text
                == " ".join(unicodedata.normalize("NFKC", text).split()))


# --- FB1 R1-02: encoded separators / digits after a card ---------------------------------------------------------------
@pytest.mark.parametrize("q", ["card 4111 1111 1111 1111%E2%80%8B9 limit", "card 4111 1111 1111 1111&#8203;9 limit",
                               "card 4111 1111 1111 1111%30", "card 4111 1111 1111 1111&#48; limit"])
def test_fb1_r1_02_encoded_tail_does_not_hide_a_card(q):
    r, sent = search(q)
    assert all("4111 1111 1111 1111" not in json.loads(x.content)["query"] for x in sent)


# --- FB1 R1-03: card separators ---------------------------------------------------------------------------------------
@pytest.mark.parametrize("sep", [",", "·", "—", "|", "+", ":", "~"])
def test_fb1_r1_03_card_separators_are_detected(sep):
    assert "FINANCIAL" in classify(f"card 4111{sep}1111{sep}1111{sep}1111").categories()


def test_fb1_r1_03_thousands_groupings_stay_readable():
    for benign in ("total 1,234,567,890 units", "1,000,000,000,000 rupees", "ratio 1234:567:890", "codes 12:30|14:45"):
        assert "FINANCIAL" not in classify(benign).categories(), benign


# --- FB1 R1-04: labelled credential idioms and deep encoding -----------------------------------------------------------
@pytest.mark.parametrize("q", ["the password for wifi is Mango#2026", "password\nMango#2026", "password - Mango#2026",
                               "password -> Mango#2026"])
def test_fb1_r1_04_credential_idioms_are_refused(q):
    r, sent = search(q)
    assert r.status == S.REFUSED and sent == []


@pytest.mark.parametrize("benign", ["the password policy is strict", "the password field is required.",
                                    "reset your password - see the help page", "password manager comparison"])
def test_fb1_r1_04_password_prose_stays_readable(benign):
    assert "CREDENTIAL" not in classify(benign).categories(), benign


def test_fb1_r1_04_encoding_deeper_than_folding_is_refused():
    q = "password%25252525253DMango"                          # five levels
    r, sent = search(q)
    assert r.status == S.REFUSED and sent == []
    assert TGateway().prepare(q, requester="t", destination="LOCAL_BRAIN", purpose="p").text == q


def test_fb1_r1_04_three_levels_are_decoded_and_refused():
    r, sent = search("password%25253DMango%25252326")
    assert r.status == S.REFUSED and r.error_code == "PRIVACY_REFUSED" and sent == []


@pytest.mark.parametrize("text,cat", [("ssn 123/45/6789", "GOV_ID"), ("call 98765.43210", "CONTACT")])
def test_fb1_r1_04_other_forms(text, cat):
    assert cat in classify(text).categories()


# --- FB1 R1-05: _STREET bounded ---------------------------------------------------------------------------------------
def test_fb1_r1_05_street_keyword_with_long_token_is_fast():
    t = time.perf_counter()
    TGateway().prepare("flat " + "1" * 4000, requester="t", destination="EXTERNAL_AGENT", purpose="p", reversible=False)
    assert time.perf_counter() - t < 1.0


def test_fb1_r1_05_street_lines_are_still_found():
    assert "ADDRESS" in classify("Flat 12B, 4th Cross Road, Indiranagar").categories()


# --- FB1 R1-06: previous scene not re-audited value by value -----------------------------------------------------------
def test_fb1_r1_06_previous_scene_is_not_sent_through_the_gateway(tmp_path, monkeypatch):
    from tests.scheduler.test_engine import Clock, FakeHarness
    from uri_scheduler.engine import Scheduler
    h = FakeHarness()
    s = Scheduler(tmp_path / "state", harness=h, now_fn=Clock("2026-10-09T10:00:00+05:30")).start()
    try:
        p = s.propose(owner="owner", title="t", template_id="festival_gif.v1",
                      params={"festival": {"key": "diwali", "name": "Diwali"}}, schedule={"kind": "once", "at": "2026-10-09T10:00"})
        s.confirm(p["job_id"], "owner", p["proposal_sha256"])
        s.tick()
        a1 = s.overview()["pending_approvals"][0]["candidates"][0]
        s.review(a1["artifact_id"], "owner", "refine", expected_sha256=a1["sha256"], instruction="More floral energy")
        audit = tmp_path / "state" / "privacy" / "audit.jsonl"
        before = len(audit.read_text(encoding="utf-8").splitlines())
        s.tick()
        added = len(audit.read_text(encoding="utf-8").splitlines()) - before
        assert "More floral energy" in h.calls[-1]["instructions"]
        assert added < 20, added            # owner-typed fields only, not every scalar of the previous scene
    finally:
        s.close()


# --- C1-01: cross-process grant lock ----------------------------------------------------------------------------------
def _hold_lock(path, held, release):
    from uri_privacy.grants import GrantStore
    store = GrantStore(path)
    with store._transaction():
        held.set()
        release.wait(10)


def _consume(path, grant_id, out):
    from uri_privacy.grants import GrantStore
    try:
        out.put(("ok", GrantStore(path).consume([grant_id])))
    except Exception as exc:                                # noqa: BLE001
        out.put(("error", type(exc).__name__))


def test_c1_01_a_waiting_process_neither_crashes_nor_overconsumes(tmp_path):
    from uri_privacy.grants import GrantStore
    owner = object()
    path = tmp_path / "grants.json"
    store = GrantStore(path, principal_verifier=lambda p: "owner" if p is owner else None)
    g = store.grant(requester="t", categories=["CONTACT"], purpose="p", destination="WEB_SEARCH",
                    authorized_by="user:owner", principal=owner)
    ctx = multiprocessing.get_context("spawn")
    held, release, out = ctx.Event(), ctx.Event(), ctx.Queue()
    holder = ctx.Process(target=_hold_lock, args=(path, held, release))
    holder.start()
    try:
        assert held.wait(30)
        waiter = ctx.Process(target=_consume, args=(path, g.grant_id, out))
        waiter.start()
        time.sleep(1.0)                                     # the waiter is now blocked on the held lock
        assert out.empty()
        release.set()
        assert out.get(timeout=30) == ("ok", True)
        waiter.join(timeout=30)
    finally:
        release.set()
        holder.join(timeout=30)
    assert GrantStore(path).list() == []


# --- OD-1a: external-harness turns ------------------------------------------------------------------------------------
def _harness_private():
    src = (ROOT / "scripts" / "run_uri_integrated_worker.py").read_text(encoding="utf-8")
    tree = ast.parse(src)
    nodes = [n for n in tree.body if (isinstance(n, ast.FunctionDef) and n.name == "harness_private")
             or (isinstance(n, ast.Assign) and any(getattr(t, "id", "") == "HARNESS_TURNS" for t in n.targets))]
    ns = {}
    exec(compile(ast.Module(nodes, []), "harness_private", "exec"), ns)
    return ns["harness_private"], src


class TurnError(Exception):
    def __init__(self, code):
        super().__init__(code)
        self.code = code


HARNESS = {"kind": "client_external_harness", "provider": "codex", "model": "gpt"}


@pytest.fixture
def private(monkeypatch, tmp_path):
    monkeypatch.setenv("URI_PRIVACY_HOME", str(tmp_path / "privacy"))
    import uri_privacy.gateway as G
    monkeypatch.setattr(G, "_default", None)
    fn, _ = _harness_private()
    return fn


def test_od1a_credentials_refuse_a_harness_turn(private):
    with pytest.raises(TurnError) as e:
        private("turn_start", {"command": "turn_start", "session_id": "s", "reasoning": HARNESS,
                               "text": "deploy it, the db password: Tr0ub4dor&3"}, TurnError)
    assert e.value.code == "PRIVACY_REFUSED"


def test_od1a_identifiers_are_removed_from_a_harness_turn(private, tmp_path):
    cmd = {"command": "turn_intent", "session_id": "s", "reasoning": HARNESS, "intent_decision": {},
           "text": "email the summary to asha.rao7@example.in and card 4111 1111 1111 1111"}
    out = private("turn_intent", cmd, TurnError)
    assert "asha.rao7" not in out["text"] and "4111" not in out["text"] and "summary" in out["text"]
    assert set(out) == set(cmd)                             # the command schema is unchanged
    assert "asha" not in (tmp_path / "privacy" / "audit.jsonl").read_text(encoding="utf-8")


@pytest.mark.parametrize("reasoning", [{"kind": "server_local_model", "provider": "llamacpp-runtime-v1"},
                                       {"kind": "deterministic"}, None])
def test_od1a_local_and_deterministic_turns_are_untouched(private, reasoning):
    cmd = {"command": "turn_start", "session_id": "s", "reasoning": reasoning,
           "text": "remember my phone is +91 98450 12345"}
    assert private("turn_start", cmd, TurnError) is cmd


def test_od1a_is_wired_before_the_supervised_path():
    _, src = _harness_private()
    assert "turns.handle(kind, harness_private(kind, command, TurnError))" in src
