"""C2 adversarial contract/auth/state tests with fresh synthetic stores."""
import copy
import json
from pathlib import Path
import sys
import uuid

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

from uri_core.app.paired_server import create_app
from uri_core.app.route_classification import ROUTE_CLASSIFICATION, USER
from uri_core.client_contracts import Binding, ClientStateSnapshot, ReadQuery, TurnRequest, digest
from uri_core.core.client_pairing import ClientPairingStore
from uri_core.core.client_service import ClientService
from uri_core.core.client_state_ports import ClientStatePorts, NeedsContext, StatePortError, method_contract
from uri_core.core.runtime_identity import RuntimeIdentity, RuntimeManifest, provision

ROOT = Path(__file__).resolve().parent


def uid():
    return str(uuid.uuid4())


@pytest.fixture
def setup():
    state = ROOT / "work/c1" / ("c2_test_" + uuid.uuid4().hex)
    path = provision(ROOT, state, Path(sys.executable), 18032, "c2-paired-core")
    runtime = RuntimeIdentity(RuntimeManifest(path))
    app = create_app(runtime)
    service = app.state.client_service
    principal = uid()
    pair_a = service.pairings.provision(principal, grants=["remember_fact"], mode="office")
    pair_b = service.pairings.provision(principal, grants=[], mode="office")
    with TestClient(app) as http:
        yield http, service, runtime, pair_a, pair_b


def auth(http, pair):
    r = http.post("/client/v1/session", json={"server_id": pair["server_id"], "client_id": pair["client_id"]},
                  headers={"Authorization": "Bearer " + pair["principal_token"], "X-URI-Pairing": pair["pairing_token"]})
    assert r.status_code == 200
    return {"Authorization": "Bearer " + r.json()["token"], "X-URI-Client": pair["client_id"]}


def request(pair, session=None, reads=None):
    binding = {k: pair[k] for k in ("server_id", "client_id", "principal_id")}
    binding["session_id"] = session or uid()
    return {**binding, "request_id": uid(), "idempotency_key": uid(), "text": "private context sentinel",
            "snapshot": {**binding, "reads": reads or []},
            "reasoning": {"kind": "client_external_harness", "provider": "claude_code"}}


def projection(store, method, result, args=None, kwargs=None, version=0):
    return {"query": {"store": store, "method": method, "args": args or [], "kwargs": kwargs or {}},
            "result": result, "result_digest": digest(result), "store_version": version}


def populated(req):
    value = copy.deepcopy(req)
    sid = value["session_id"]
    value["snapshot"]["reads"] = [projection("sessions", "get_session", {"session_id": sid}, [sid]),
                                    projection("history", "get_session", [], [sid])]
    return value


def test_two_clients_same_principal_are_distinct_and_no_private_server_stores(setup):
    http, service, runtime, a, b = setup
    ha, hb = auth(http, a), auth(http, b)
    assert a["principal_id"] == b["principal_id"] and a["client_id"] != b["client_id"]
    assert http.get("/client/v1/capabilities", headers=ha).json()["capabilities"]
    assert http.get("/client/v1/capabilities", headers=hb).json()["capabilities"] == []
    body = request(a)
    started = http.post("/client/v1/turns", json=body, headers=ha)
    assert started.status_code == 200 and started.json()["state"] == "needs_context"
    tid = started.json()["turn_id"]
    assert http.get(f"/client/v1/turns/{tid}/status", headers=hb).status_code == 403
    assert http.get("/client/v1/capabilities", headers={**ha, "X-URI-Client": b["client_id"]}).status_code == 403
    state = Path(runtime.manifest.data["state_root"])
    names = [p.name for p in state.rglob("*") if p.is_file()]
    for forbidden in ["graph.sqlite3", "user_memory.json", "user_profile.json", "identity.json", "approvals.json"]:
        assert forbidden not in names
    assert "private context sentinel" not in service.path.read_text()
    assert a["pairing_token"] not in service.pairings.path.read_text()
    assert ha["Authorization"][7:] not in (service.root / "paired_sessions.json").read_text()


def test_missing_invalid_expired_revoked_and_wrong_principal_auth(setup):
    http, service, runtime, a, b = setup
    assert http.get("/client/v1/capabilities").status_code == 401
    assert http.get("/client/v1/capabilities", headers={"Authorization": "Bearer bogus", "X-URI-Client": a["client_id"]}).status_code == 401
    headers = auth(http, a)
    assert http.get("/runtime/status").status_code == 401
    assert http.get("/runtime/status", headers=headers).status_code == 200
    unrelated = service.pairings.principal_sessions.create(uid())
    wrong = http.post("/client/v1/session", json={"server_id": a["server_id"], "client_id": a["client_id"]},
                      headers={"Authorization": "Bearer " + unrelated, "X-URI-Pairing": a["pairing_token"]})
    assert wrong.status_code == 403
    service.pairings.sessions.revoke(headers["Authorization"][7:])
    assert http.get("/client/v1/capabilities", headers=headers).status_code == 401
    headers = auth(http, a)
    data = service.pairings._load()
    from uri_core.core.client_pairing import token_hash
    data["bindings"][token_hash(headers["Authorization"][7:])]["expires_at"] = 0
    from uri_core.core.runtime_identity import atomic_json
    atomic_json(service.pairings.path, data)
    assert http.get("/client/v1/capabilities", headers=headers).status_code == 401
    headers = auth(http, b)
    service.pairings.revoke(b["client_id"])
    assert http.get("/client/v1/capabilities", headers=headers).status_code == 401


@pytest.mark.parametrize("change", ["field", "bool_version", "digest", "private_field", "path", "unknown_method", "cross_session", "cross_client", "duplicate", "mixed_version"])
def test_negative_snapshots_fail_without_echo_or_context_fallback(setup, change):
    http, service, runtime, a, b = setup
    headers = auth(http, a)
    body = populated(request(a))
    reads = body["snapshot"]["reads"]
    if change == "field": body["snapshot"]["credential"] = "never-echo-sentinel"
    elif change == "bool_version": reads[0]["store_version"] = True
    elif change == "digest": reads[0]["result_digest"] = "0" * 64
    elif change == "private_field": reads[0]["result"] = {"password": "never-echo-sentinel"}; reads[0]["result_digest"] = digest(reads[0]["result"])
    elif change == "path": reads[0]["result"] = "C:/private/data"; reads[0]["result_digest"] = digest(reads[0]["result"])
    elif change == "unknown_method": reads[0]["query"]["method"] = "_load"
    elif change == "cross_session": reads[0]["query"]["args"] = [uid()]
    elif change == "cross_client": body["snapshot"]["client_id"] = b["client_id"]
    elif change == "duplicate": reads.append(copy.deepcopy(reads[0]))
    else: reads.append(projection("sessions", "get_session", {}, kwargs={"session_id": body["session_id"]}, version=1))
    response = http.post("/client/v1/turns", json=body, headers=headers)
    assert response.status_code in (400, 403, 422)
    assert "never-echo-sentinel" not in response.text
    assert not service.live


def test_context_continuation_cas_replay_cancel_and_restart(setup):
    http, service, runtime, a, b = setup
    headers = auth(http, a)
    body = request(a)
    first = http.post("/client/v1/turns", json=body, headers=headers).json()
    assert http.post("/client/v1/turns", json=body, headers=headers).json() == first
    changed = copy.deepcopy(body); changed["text"] = "different"
    assert http.post("/client/v1/turns", json=changed, headers=headers).status_code == 409
    url = f"/client/v1/turns/{first['turn_id']}"
    control = {k: body[k] for k in ("server_id", "client_id", "principal_id", "session_id")}
    more = {**control, "expected_version": 0, "idempotency_key": uid(), "snapshot": populated(body)["snapshot"]}
    continued = http.post(url + "/continue", json=more, headers=headers)
    assert continued.status_code == 200 and continued.json()["state"] == "proposal"
    assert http.post(url + "/continue", json=more, headers=headers).json() == continued.json()
    bad = {**more, "idempotency_key": uid()}
    assert http.post(url + "/continue", json=bad, headers=headers).status_code == 409
    restarted = ClientService(runtime)
    identity = restarted.pairings.resolve(headers["Authorization"][7:], a["client_id"])
    result = restarted.start(TurnRequest.model_validate(body), identity)
    assert result["code"] == "CONTEXT_REQUIRED_AFTER_RESTART"
    cancel = {**control, "expected_version": 1, "idempotency_key": uid()}
    response = http.post(url + "/cancel", json=cancel, headers=headers)
    assert response.status_code == 200 and response.json()["state"] == "cancelled"
    assert http.post(url + "/cancel", json=cancel, headers=headers).json() == response.json()
    assert http.post(url + "/continue", json={**more, "expected_version": 2, "idempotency_key": uid()}, headers=headers).status_code == 409


def test_expiry_capacity_and_actual_body_limits(setup):
    http, service, runtime, a, b = setup
    headers = auth(http, a)
    responses = [http.post("/client/v1/turns", json=request(a), headers=headers) for _ in range(4)]
    assert all(r.status_code == 200 for r in responses)
    assert http.post("/client/v1/turns", json=request(a), headers=headers).status_code == 429
    now = service.clock()
    service.clock = lambda: now + 901
    service.expire()
    assert not service.live
    assert http.get(f"/client/v1/turns/{responses[0].json()['turn_id']}/status", headers=headers).json()["state"] == "expired"
    assert http.post("/client/v1/session", content=b"x" * (2 * 1024 * 1024 + 1), headers=headers).status_code == 413


def test_exact_state_reads_mutations_and_all_major_method_dispositions(setup):
    http, service, runtime, a, b = setup
    body = request(a)
    reads = [projection("memory", "list_all", []), projection("graph", "list_nodes", []),
             projection("files", "list_for_session", [], [body["session_id"]]), projection("approvals", "list_pending", [])]
    body["snapshot"]["reads"] = reads
    request_obj = TurnRequest.model_validate(body)
    binding = {k: body[k] for k in ("server_id", "client_id", "principal_id", "session_id")}
    ports = ClientStatePorts(request_obj.snapshot, binding)
    assert ports.read("memory", "list_all") == []
    assert ports.read("graph", "list_nodes") == []
    assert ports.read("approvals", "list_pending") == []
    with pytest.raises(NeedsContext): ports.read("memory", "get", uid())
    known = [r.model_dump() for r in ports.reads.values() if r.query.store == "memory"]
    previous = digest(sorted(known, key=lambda r: digest(r["query"])))
    mutation = ports.propose("memory", "add", kwargs={"category": "preference", "content": "test"}, base_version=0, previous_digest=previous)
    assert ports.mutation_set(uid(), uid()).mutations == [mutation]
    assert ports.read("memory", "list_all") == []  # no persistence before C3 CAS receipt
    with pytest.raises(StatePortError): ports.read("credentials", "has_credential", a["principal_id"], "x")
    with pytest.raises(StatePortError): ports.read("files", "path_for", uid())
    with pytest.raises(StatePortError): ports.propose("memory", "add", base_version=1, previous_digest=previous)
    import ast
    for entry in method_contract().values():
        tree = ast.parse((ROOT / entry["source"]).read_text(encoding="utf-8-sig"))
        cls = next(n for n in tree.body if isinstance(n, ast.ClassDef) and n.name == entry["class"])
        actual = {n.name for n in cls.body if isinstance(n, ast.FunctionDef) and not n.name.startswith("_")}
        dispositions = entry["reads"] + entry["writes"] + entry["local_only"]
        assert actual == set(dispositions) and len(dispositions) == len(set(dispositions))


def test_every_paired_route_is_classified_and_snapshot_bounds(setup):
    http, service, runtime, a, b = setup
    for route in http.app.routes:
        for method in getattr(route, "methods", ()):
            if method in {"HEAD", "OPTIONS"}: continue
            assert (method, route.path) in ROUTE_CLASSIFICATION
            if route.path.startswith("/client/v1/"):
                assert ROUTE_CLASSIFICATION[(method, route.path)] == USER
    body = request(a)
    body["snapshot"]["reads"] = [projection("memory", "list_all", "x" * (256 * 1024))]
    with pytest.raises(ValidationError): TurnRequest.model_validate(body)


def test_independent_pairing_controllers_do_not_lose_records(setup):
    http,service,runtime,a,b=setup
    from concurrent.futures import ThreadPoolExecutor
    def provision_one(_):
        controller=ClientPairingStore(service.root,runtime.manifest.data['server_id'])
        return controller.provision(a['principal_id'],grants=[],mode='office')['client_id']
    with ThreadPoolExecutor(max_workers=4) as pool:
        created=list(pool.map(provision_one,range(8)))
    data=service.pairings._load()
    assert set(created)<=set(data['clients']) and len(data['clients'])==10


def test_cancel_refuses_settled_turn(setup):
    """Claude audit D1: cancel must not relabel reply/failed/expired turns."""
    http, service, runtime, pair_a, pair_b = setup
    headers = auth(http, pair_a)
    started = http.post("/client/v1/turns", json=request(pair_a), headers=headers).json()
    turn_id = started["turn_id"]
    if True:
        data = service._load()
        for state in ("reply", "failed", "expired"):
            data["turns"][turn_id]["state"] = state
            from uri_core.core.runtime_identity import atomic_json
            atomic_json(service.path, data)
            body = {k: pair_a[k] for k in ("server_id", "client_id", "principal_id")}
            body.update(session_id=started["session_id"], idempotency_key=uid(),
                        expected_version=data["turns"][turn_id]["version"])
            r = http.post(f"/client/v1/turns/{turn_id}/cancel", json=body, headers=headers)
            assert r.status_code == 409 and r.json()["detail"] == "TURN_TERMINAL"
            assert service._load()["turns"][turn_id]["state"] == state


def test_cancel_never_relabels_claimed_or_uncertain_execution(setup):
    """Second-pass audit of the D1 slice: a claimed (executing) or execution_uncertain turn may have
    effects; cancel must never relabel it "cancelled" (that would also bypass the C5 no-duplicate guard)."""
    http, service, runtime, pair_a, pair_b = setup
    headers = auth(http, pair_a)
    started = http.post("/client/v1/turns", json=request(pair_a), headers=headers).json()
    turn_id = started["turn_id"]
    from uri_core.core.runtime_identity import atomic_json
    for state in ("executing", "execution_uncertain"):
        data = service._load()
        data["turns"][turn_id]["state"] = state
        atomic_json(service.path, data)
        body = {k: pair_a[k] for k in ("server_id", "client_id", "principal_id")}
        body.update(session_id=started["session_id"], idempotency_key=uid(),
                    expected_version=data["turns"][turn_id]["version"])
        r = http.post(f"/client/v1/turns/{turn_id}/cancel", json=body, headers=headers)
        assert r.status_code == 200 and r.json()["code"] == "EXECUTION_UNCERTAIN_NOT_CANCELLED"
        assert service._load()["turns"][turn_id]["state"] == "execution_uncertain"   # never "cancelled"
