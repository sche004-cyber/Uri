"""C5 assembled loop: request -> gates -> approval -> ticket -> claim -> local execution ->
independent verification -> settle -> persisted history -> follow-up. Real paired server app
(TestClient), real client persistence, real DPAPI credentials. No-Brain deterministic proposer."""
import json
from pathlib import Path
import sys
import uuid

import pytest
from fastapi.testclient import TestClient

from uri_core.app.paired_server import create_app
from uri_core.client_contracts import ReadQuery
from uri_core.client_runtime.manifest import ClientManifest, provision_client
from uri_core.client_runtime.persistence import ClientPersistence
from uri_core.client_runtime.turn_runner import TurnRunner, TurnError
from uri_core.core.paired_reasoning import ReasoningSelectionPolicy
from uri_core.core.runtime_identity import RuntimeIdentity, RuntimeManifest, dpapi, provision

ROOT = Path(__file__).resolve().parent
NOBRAIN = {"kind": "server_local_model", "provider": "uri-deterministic", "model": None}


def uid():
    return str(uuid.uuid4())


@pytest.fixture
def stack():
    base = ROOT / "work/c1" / ("c5_test_" + uuid.uuid4().hex)
    server_manifest = provision(ROOT, base / "server", Path(sys.executable), 18232, "c2-paired-core")
    runtime = RuntimeIdentity(RuntimeManifest(server_manifest))
    policy = ReasoningSelectionPolicy({("server_local_model", "uri-deterministic", None)})
    app = create_app(runtime, composition={"policy": policy})
    principal = uid()
    cm = ClientManifest(provision_client(server_manifest, base / "client", principal, ["remember_fact"]))
    cred = json.loads(dpapi((Path(cm.data["client_root"]) / "secure/uri-credentials.dpapi").read_bytes(), True))
    with TestClient(app) as http:
        session = http.post("/client/v1/session", json={"server_id": cred["server_id"], "client_id": cred["client_id"]},
            headers={"Authorization": "Bearer " + cred["principal_token"], "X-URI-Pairing": cred["pairing_token"]}).json()
        headers = {"Authorization": "Bearer " + session["token"], "X-URI-Client": cred["client_id"]}
        calls = []
        def call(method, path, body):
            calls.append((method, path))
            r = http.request(method, path, json=body, headers=headers)
            return r.status_code, r.json()
        persistence = ClientPersistence(cm)
        runner = TurnRunner(cm, persistence, call, cm.data["server_public_key"], runtime.generation)
        yield runner, persistence, runtime, app, call, calls, cm


def memory(persistence, session):
    return persistence.snapshot(session, [ReadQuery(store="memory", method="list_all")]).reads[0].result


def history(persistence, session):
    return persistence.snapshot(session, [ReadQuery(store="history", method="get_session", args=[session])]).reads[0].result


def test_authorized_reversible_write_verified_persisted_and_followup(stack):
    runner, persistence, runtime, app, call, calls, cm = stack
    session = uid()
    seen = []
    final = runner.run("remember that my favourite colour is teal", session, NOBRAIN, lambda req: seen.append(req) or True)
    assert final["state"] == "reply" and final["code"] == "SETTLED_VERIFIED"
    assert seen[0]["capability_id"] == "remember_fact" and seen[0]["reversible"] is True
    assert any(m["fact"]["value"] == "my favourite colour is teal" for m in memory(persistence, session))   # independent read
    # order: intent happens before the online claim; claim before settle
    paths = [p.rsplit("/", 1)[-1] for _, p in calls]
    assert paths.index("approval") < paths.index("claim") < paths.index("settle")
    # follow-up in the same session sees prior turn context persisted by the client
    h = history(persistence, session)
    assert len(h) == 1 and h[0]["user_text"].startswith("remember") and "verified" in h[0]["response_text"]
    follow = runner.run("hello again", session, NOBRAIN, lambda req: True)
    assert follow["state"] == "reply" and follow["code"] == "CONVERSATION"
    assert len(history(persistence, session)) == 2


def test_declined_approval_changes_nothing(stack):
    runner, persistence, *_ = stack
    session = uid()
    final = runner.run("remember that the sky is green", session, NOBRAIN, lambda req: False)
    assert final["state"] == "cancelled" and final["code"] == "APPROVAL_DENIED"
    assert memory(persistence, session) == []


def test_ungranted_capability_is_blocked_before_any_ticket(stack):
    runner, persistence, runtime, app, call, calls, cm = stack
    app.state.client_service.pairings.revoke(cm.data["client_id"])
    session = uid()
    with pytest.raises(TurnError):
        runner.run("remember that x is y", session, NOBRAIN, lambda req: True)
    assert not any(p.endswith("/claim") for _, p in calls) and memory(persistence, session) == []


def test_destructive_request_is_refused_safely(stack):
    runner, persistence, *_ = stack
    final = runner.run("delete all my files", uid(), NOBRAIN, lambda req: pytest.fail("must not ask approval"))
    assert final["state"] == "reply" and final["code"].startswith("REFUSED_")


def test_unavailable_selection_does_not_fall_back(stack):
    runner, persistence, *_ = stack
    bad = {"kind": "client_external_harness", "provider": "claude_code", "model": None, "allowed_fallbacks": ["uri-deterministic"]}
    final = runner.run("remember that x", uid(), bad, lambda req: pytest.fail("must not run"))
    assert final["state"] == "failed" and final["code"] == "ADAPTER_NOT_QUALIFIED"


# ---------------------------------------------------------------------------------------------
# Adversarial control-path tests (reuse the stack fixture)
# ---------------------------------------------------------------------------------------------

def _start(runner, session, text="remember that adversarial fact holds"):
    body = {**runner._binding(session), "request_id": uid(), "idempotency_key": uid(), "text": text,
            "snapshot": runner._snapshot(session).model_dump(), "reasoning": NOBRAIN}
    return runner._post("/client/v1/turns", body)


def test_forged_approval_digest_and_unapproved_claim_are_refused(stack):
    runner, persistence, runtime, app, call, calls, cm = stack
    session = uid()
    turn = _start(runner, session)
    assert turn["state"] == "approval_required"
    status, bad = call("POST", f"/client/v1/turns/{turn['turn_id']}/approval", runner._control(
        session, turn, decision="approve", approval_digest="0" * 64))
    assert status == 409 and bad["detail"] == "APPROVAL_DIGEST_MISMATCH"
    # No ticket exists: a claim attempt with a forged ticket cannot dispatch.
    status, _ = call("POST", f"/client/v1/turns/{turn['turn_id']}/claim", runner._control(
        session, turn, ticket={"ticket": {}, "signature": "0" * 128}, execution_version=0))
    assert status in (409, 422) and memory(persistence, session) == []


def test_replayed_claim_never_grants_second_dispatch(stack):
    runner, persistence, runtime, app, call, calls, cm = stack
    session = uid()
    turn = _start(runner, session)
    approved = runner._post(f"/client/v1/turns/{turn['turn_id']}/approval", runner._control(
        session, turn, decision="approve", approval_digest=turn["approval_request"]["approval_digest"]))
    first_body = runner._control(session, approved, ticket=approved["ticket"], execution_version=0)
    first = runner._post(f"/client/v1/turns/{turn['turn_id']}/claim", first_body)
    assert first["claim"]["dispatch"] is True
    # Same idempotency key: stored response replayed (no new control claim).
    assert runner._post(f"/client/v1/turns/{turn['turn_id']}/claim", first_body) == first
    # Fresh key against the already-claimed ticket: turn no longer claimable.
    status, data = call("POST", f"/client/v1/turns/{turn['turn_id']}/claim", runner._control(
        session, first, ticket=approved["ticket"], execution_version=0))
    assert status == 409 and data["detail"] == "TURN_NOT_CLAIMABLE"
    assert app.state.coordinator.control._load()["operations"][approved["ticket"]["ticket"]["operation_id"]]["state"] == "claimed"


def test_revoked_grant_between_approval_and_claim_blocks_dispatch(stack):
    runner, persistence, runtime, app, call, calls, cm = stack
    session = uid()
    turn = _start(runner, session)
    approved = runner._post(f"/client/v1/turns/{turn['turn_id']}/approval", runner._control(
        session, turn, decision="approve", approval_digest=turn["approval_request"]["approval_digest"]))
    app.state.client_service.pairings.revoke(cm.data["client_id"])
    status, _ = call("POST", f"/client/v1/turns/{turn['turn_id']}/claim", runner._control(
        session, approved, ticket=approved["ticket"], execution_version=0))
    assert status in (401, 403, 409) and memory(persistence, session) == []


def test_interrupted_executor_is_uncertain_and_never_redispatched(stack, monkeypatch):
    runner, persistence, runtime, app, call, calls, cm = stack
    session = uid()
    def crash(self, session, request, reasoning=None):
        raise KeyboardInterrupt("executor killed mid-run")
    monkeypatch.setattr(TurnRunner, "_run_local", crash)
    with pytest.raises(KeyboardInterrupt):
        runner.run("remember that interrupted fact", session, NOBRAIN, lambda req: True)
    # Client restarts: journal recovery marks the claimed operation uncertain; dispatch stays False.
    records = runner.journal.recover()
    assert [r["state"] for r in records] == ["execution_uncertain"] and all(r["dispatch"] is False for r in records)
    # Replaying the same ticket claim at the server is refused (already claimed) -> no duplicate side effect.
    ops = app.state.coordinator.control._load()["operations"]
    assert [o["state"] for o in ops.values()] == ["claimed"]
    assert memory(persistence, session) == []
    monkeypatch.undo()
    stale = call("GET", f"/client/v1/turns/{calls[-1][1].split('/')[4]}/status", None)[1]
    assert stale["state"] == "executing"   # server still shows the claimed, unsettled turn
    cancelled = runner._post(f"/client/v1/turns/{stale['turn_id']}/cancel", runner._control(session, stale))
    # Never relabelled "cancelled": the claimed turn stays execution_uncertain; the session is released.
    assert cancelled["state"] == "execution_uncertain" and cancelled["code"] == "EXECUTION_UNCERTAIN_NOT_CANCELLED"
    # The only way forward is a new, freshly approved turn (user decision), not an automatic retry.
    again = runner.run("remember that interrupted fact", session, NOBRAIN, lambda req: True)
    assert again["code"] == "SETTLED_VERIFIED"


# ---------------------------------------------------------------------------------------------
# External harness through the same gated loop, using the CANONICAL shared catalogue entry and the
# real mode allow-lists (the former synthetic overlay and mode monkeypatch were removed).
# ---------------------------------------------------------------------------------------------
from uri_core.client_runtime import harness as hx
from uri_harness_adapters import default_registry

FAKE = [sys.executable, str(ROOT / "fixtures/c4_harness/fake_harness.py")]


@pytest.fixture
def harness_stack(monkeypatch):
    base = ROOT / "work/c1" / ("c5h_test_" + uuid.uuid4().hex)
    server_manifest = provision(ROOT, base / "server", Path(sys.executable), 18233, "c2-paired-core")
    runtime = RuntimeIdentity(RuntimeManifest(server_manifest))
    rows = {("client_external_harness", "claude_code", None), ("client_external_harness", "codex_cli", None)}
    policy = ReasoningSelectionPolicy(rows | {("server_local_model", "uri-deterministic", None)})
    app = create_app(runtime, composition={"policy": policy, "qualified": ("remember_fact", "external_harness_task")})
    principal = uid()
    cm = ClientManifest(provision_client(server_manifest, base / "client", principal, ["remember_fact"]))
    pairings = app.state.client_service.pairings
    with pairings.lock:
        data = pairings._load(); data["clients"][cm.data["client_id"]]["grants"].append("external_harness_task")
        from uri_core.core.runtime_identity import atomic_json
        atomic_json(pairings.path, data)
    cred = json.loads(dpapi((Path(cm.data["client_root"]) / "secure/uri-credentials.dpapi").read_bytes(), True))
    registry = default_registry({"claude_code": FAKE, "codex_cli": FAKE}, auth_probe=lambda hid: True)
    registry.qualify("claude_code", "FIXTURE_ONLY", "a" * 64); registry.qualify("codex_cli", "FIXTURE_ONLY", "b" * 64)
    with TestClient(app) as http:
        s = http.post("/client/v1/session", json={"server_id": cred["server_id"], "client_id": cred["client_id"]},
            headers={"Authorization": "Bearer " + cred["principal_token"], "X-URI-Pairing": cred["pairing_token"]}).json()
        headers = {"Authorization": "Bearer " + s["token"], "X-URI-Client": cred["client_id"]}
        def call(method, path, body):
            r = http.request(method, path, json=body, headers=headers); return r.status_code, r.json()
        persistence = ClientPersistence(cm)
        runner = TurnRunner(cm, persistence, call, cm.data["server_public_key"], runtime.generation, harness=registry)
        yield runner, persistence, app, call, cm


CLAUDE = {"kind": "client_external_harness", "provider": "claude_code", "model": None}
CODEX = {"kind": "client_external_harness", "provider": "codex_cli", "model": None}


def test_user_selected_harness_executes_and_urI_verifies_independently(harness_stack, monkeypatch):
    runner, persistence, app, call, cm = harness_stack
    monkeypatch.setenv("URI_FAKE_SCENARIO", "honest")
    session = uid()
    final = runner.run("use the harness to write a greeting into out.txt", session, CLAUDE, lambda req: req["capability_id"] == "external_harness_task")
    assert final["code"] == "SETTLED_VERIFIED"
    results = list((Path(cm.data["client_root"]) / "workspace/results").rglob("out.txt"))
    assert len(results) == 1 and results[0].read_text().startswith("hello from harness")


def test_harness_false_claim_is_not_verified(harness_stack, monkeypatch):
    runner, persistence, app, call, cm = harness_stack
    monkeypatch.setenv("URI_FAKE_SCENARIO", "false_claim")
    final = runner.run("use the harness to write a greeting into out.txt", uid(), CLAUDE, lambda req: True)
    # The harness RAN and its claim was false: nothing is copied out, but URI cannot show the harness had no
    # other effect, so the attempt is uncertain, never a retry-unlocking "failed" (review decision 3).
    assert final["code"] == "SETTLED_EXECUTION_UNCERTAIN" and not list((Path(cm.data["client_root"]) / "workspace").glob("results/*/out.txt"))


def test_quota_preserves_task_then_user_chooses_other_provider(harness_stack, monkeypatch):
    runner, persistence, app, call, cm = harness_stack
    session = uid()
    monkeypatch.setenv("URI_FAKE_SCENARIO", "quota")
    paused = runner.run("use the harness to write a greeting into out.txt", session, CLAUDE, lambda req: True)
    assert paused["code"] == "WAITING_FOR_MODEL" and "choose another" in paused["message"].lower()
    cp = Path(cm.data["client_root"]) / "control/checkpoints"
    assert len(list(cp.glob("*.json"))) == 1 and not list((Path(cm.data["client_root"]) / "workspace").glob("results/*/out.txt"))
    # No silent substitution: same provider is refused; a different explicit choice proceeds with a fresh approval.
    with pytest.raises(TurnError, match="SAME_PROVIDER"):
        runner.continue_waiting(session, paused["turn_id"], CLAUDE, lambda req: True)
    monkeypatch.setenv("URI_FAKE_SCENARIO", "honest")
    approvals = []
    final = runner.continue_waiting(session, paused["turn_id"], CODEX, lambda req: approvals.append(1) or True)
    assert final["code"] == "SETTLED_VERIFIED" and approvals == [1]
    assert len(list((Path(cm.data["client_root"]) / "workspace").glob("results/*/out.txt"))) == 1   # exactly one effect


def test_unusable_harness_is_refused_without_fallback(harness_stack, monkeypatch):
    runner, persistence, app, call, cm = harness_stack
    runner.harness.qualified.pop("claude_code")   # no longer qualified client-side
    final = runner.run("use the harness to write a greeting into out.txt", uid(), CLAUDE, lambda req: True)
    assert final["code"] == "SETTLED_FAILED"
    assert not list((Path(cm.data["client_root"]) / "workspace").glob("results/*/out.txt"))


def test_one_runner_executes_several_turns_with_distinct_tickets(stack):
    """Regression (found in live run): journal ticket validation must be per-turn, not first-turn."""
    runner, persistence, *_ = stack
    session = uid()
    for fact in ("first distinct fact", "second distinct fact", "third distinct fact"):
        assert runner.run("remember that " + fact, session, NOBRAIN, lambda req: True)["code"] == "SETTLED_VERIFIED"
    assert {m["fact"]["value"] for m in memory(persistence, session)} == {"first distinct fact", "second distinct fact", "third distinct fact"}


def test_quota_after_tool_activity_is_uncertain_not_a_clean_pause(harness_stack, monkeypatch):
    """Fourth review: the harness requested a tool action (tool_use) and THEN hit the quota. The client
    runtime knew it (claim.usage.tool_calls == 1) but still closed the attempt as a no-effect 'cancelled'
    pause ("Nothing was changed"), which re-ran the same task on another provider. Workspace isolation is
    the only containment and it is not qualified beyond the workspace, so this is execution_uncertain."""
    runner, persistence, app, call, cm = harness_stack
    session = uid()
    monkeypatch.setenv("URI_FAKE_SCENARIO", "quota_after_tool")
    final = runner.run("use the harness to write a greeting into out.txt", session, CLAUDE, lambda req: True)
    assert final["code"] == "SETTLED_EXECUTION_UNCERTAIN" and final["state"] == "execution_uncertain", final
    record = app.state.client_service._load()["turns"][final["turn_id"]]
    assert record["dispatched"] is True and not record.get("execution_closed")
    assert not list((Path(cm.data["client_root"]) / "control/checkpoints").glob("*.json"))   # no quota checkpoint
    assert not list((Path(cm.data["client_root"]) / "workspace").glob("results/*/out.txt"))
    with pytest.raises(Exception):     # nothing to continue: no checkpoint, no silent re-run elsewhere
        runner.continue_waiting(session, final["turn_id"], CODEX, lambda req: True)


def test_quota_checkpoint_is_one_continuation_not_a_standing_retry(harness_stack, monkeypatch):
    """Fifth review: T1 paused cleanly (codex-shaped first-call quota), the user continued on another provider
    and THAT attempt became execution_uncertain (quota after tool activity). The T1 checkpoint still allowed a
    third run of the same task with a fresh approval, bypassing the later attempt's uncertainty. A checkpoint
    is consumed by its first dispatched continuation."""
    runner, persistence, app, call, cm = harness_stack
    session = uid()
    monkeypatch.setenv("URI_FAKE_SCENARIO", "quota")
    paused = runner.run("use the harness to write a greeting into out.txt", session, CODEX, lambda req: True)
    assert paused["code"] == "WAITING_FOR_MODEL"
    monkeypatch.setenv("URI_FAKE_SCENARIO", "quota_after_tool")
    second = runner.continue_waiting(session, paused["turn_id"], CLAUDE, lambda req: True)
    assert second["code"] == "SETTLED_EXECUTION_UNCERTAIN"
    monkeypatch.setenv("URI_FAKE_SCENARIO", "honest")
    with pytest.raises(TurnError, match="CHECKPOINT_CONSUMED"):
        runner.continue_waiting(session, paused["turn_id"], CLAUDE, lambda req: pytest.fail("must not ask approval"))
    assert not list((Path(cm.data["client_root"]) / "workspace").glob("results/*/out.txt"))   # no third effect
    # A continuation that itself pauses cleanly leaves its OWN checkpoint, so the task is still continuable.
    monkeypatch.setenv("URI_FAKE_SCENARIO", "quota")
    p2 = runner.run("use the harness to write a greeting into out.txt", session, CODEX, lambda req: True)
    assert p2["code"] == "WAITING_FOR_MODEL"
    monkeypatch.setenv("URI_FAKE_SCENARIO", "quota")
    again = runner.continue_waiting(session, p2["turn_id"], CLAUDE, lambda req: True)
    assert again["code"] == "WAITING_FOR_MODEL" and again["turn_id"] != p2["turn_id"]
    monkeypatch.setenv("URI_FAKE_SCENARIO", "honest")
    final = runner.continue_waiting(session, again["turn_id"], CODEX, lambda req: True)
    assert final["code"] == "SETTLED_VERIFIED"
