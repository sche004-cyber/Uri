"""Provisional C4–C7 components. Synthetic gates never qualify native adapters."""
import copy
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
import sys
from types import SimpleNamespace
import uuid
import zipfile
import hashlib

import pytest
from pydantic import ValidationError

from uri_core.client_contracts import Binding, ClientStateSnapshot, ReasoningSelection, TurnRequest, digest
from uri_core.execution_contracts import ExecutionTicket, ExecutionReceipt
from uri_core.core.client_execution_control import ClientExecutionControl, ExecutionControlError, verify_ticket
from uri_core.client_runtime.execution_journal import ExecutionJournal, ExecutionJournalError
from uri_core.core.runtime_identity import RuntimeIdentity, RuntimeManifest, provision
from uri_core.core.client_state_ports import ClientStatePorts, NeedsContext, StatePortError
from uri_core.core.paired_reasoning import ReasoningSelectionPolicy, ReasoningUnavailable, prepare_canonical_context, validate_canonical_proposal, prepare_for_paired_client
from scripts.phase1_offline_rollback import rehearse

ROOT = Path(__file__).resolve().parent


def uid():
    return str(uuid.uuid4())


@pytest.fixture
def execution():
    path = provision(ROOT, ROOT / "work/c1" / ("c4_offline_" + uuid.uuid4().hex), Path(sys.executable), 18132, "c2-paired-core")
    runtime = RuntimeIdentity(RuntimeManifest(path))
    identity = SimpleNamespace(server_id=runtime.manifest.data["server_id"], client_id=uid(), principal=SimpleNamespace(user_id=uid()))
    binding = {"server_id": identity.server_id, "client_id": identity.client_id,
               "principal_id": identity.principal.user_id, "session_id": uid()}
    clock = [1000]
    ticket = {**binding, "turn_id": uid(), "operation_id": uid(), "ticket_id": uid(), "generation": runtime.generation,
              "capability_id": "remember_fact", "argument_digest": digest({"private_argument": "private-sentinel"}),
              "workspace_handle": uid(), "workspace_version": 2, "approval_digest": "1" * 64,
              "approval_status": "approved", "verifier_id": "synthetic-test-verifier",
              "implementation_digest": "2" * 64, "issued_at": 1000, "expires_at": 1060, "deadline": 1100,
              "cancellation_nonce": "3" * 64}
    authority = [True]
    control = ClientExecutionControl(runtime, authorize=lambda t, i, p: authority[0],
        verify_receipt=lambda t, r: r.evidence == [{"verified_fixture": True}], clock=lambda: clock[0])
    return runtime, identity, binding, ticket, control, clock, authority


def receipt(ticket):
    return {**{k: ticket[k] for k in ("server_id", "client_id", "principal_id", "session_id", "turn_id", "operation_id", "verifier_id", "implementation_digest")},
            "ticket_digest": digest(ExecutionTicket.model_validate(ticket).model_dump()), "run_id": uid(),
            "outcome": "verified", "state_version": 1, "evidence": [{"verified_fixture": True}]}


def test_default_control_cannot_issue_model_authored_ticket(execution):
    runtime, identity, binding, ticket, _, _, _ = execution
    control = ClientExecutionControl(runtime)
    with pytest.raises(ExecutionControlError, match="AUTHORITY_UNAVAILABLE"):
        control.prepare(ticket, identity)
    assert not control.path.exists()


def test_quota_checkpoint_durable_without_private_context_or_provider_substitution(execution):
    from uri_core.core.client_service import ClientService
    from test_c2_client_state import request, populated
    runtime, identity, binding, ticket, _, clock, _ = execution
    service = ClientService(runtime, clock=lambda: clock[0])
    pair = service.pairings.provision(binding["principal_id"], grants=[], mode="office")
    auth = service.pairings.acquire(pair["server_id"], pair["client_id"], pair["principal_token"], pair["pairing_token"])
    paired = service.pairings.resolve(auth["token"], pair["client_id"])
    req = TurnRequest.model_validate(populated(request(pair)))
    started = service.start(req, paired)
    waited = service.record_provider_wait(started["turn_id"], paired, 0, "4" * 64)
    assert waited["code"] == "WAITING_FOR_MODEL"
    clock[0] += 901
    service.expire()
    status = service.status(started["turn_id"], paired)
    assert status["state"] == "waiting_for_model" and status["context_available"] is False
    assert ClientService(runtime).status(started["turn_id"], paired)["state"] == "waiting_for_model"
    assert req.text not in service.path.read_text() and "claude_code" not in service.path.read_text()


def test_signed_ticket_claim_linearization_and_receipt_replay(execution):
    runtime, identity, binding, ticket, control, clock, _ = execution
    signed = control.prepare(ticket, identity)
    verified = verify_ticket(signed, runtime.manifest.data["public_key"], binding, generation=runtime.generation,
        now=1000, argument_digest=ticket["argument_digest"], workspace_handle=ticket["workspace_handle"], workspace_version=2)
    assert verified.ticket.operation_id == ticket["operation_id"]
    assert control.claim(signed, identity, 0, "a" * 16)["dispatch"] is True
    assert control.claim(signed, identity, 0, "a" * 16)["dispatch"] is False
    value = receipt(ticket)
    assert control.settle(signed, value, identity)["state"] == "verified"
    assert control.settle(signed, value, identity)["state"] == "verified"
    altered = {**value, "run_id": uid()}
    with pytest.raises(ExecutionControlError, match="RECEIPT_CONFLICT"):
        control.settle(signed, altered, identity)
    assert "private-sentinel" not in control.path.read_text() and "verified_fixture" not in control.path.read_text()


@pytest.mark.parametrize("change", ["signature", "scope", "generation", "args", "workspace", "expiry", "bool_version", "unknown"])
def test_tickets_refuse_tampering_or_wrong_local_scope(execution, change):
    runtime, identity, binding, ticket, control, clock, _ = execution
    signed = control.prepare(ticket, identity)
    kwargs = dict(generation=runtime.generation, now=1000, argument_digest=ticket["argument_digest"],
                  workspace_handle=ticket["workspace_handle"], workspace_version=2)
    if change == "signature": signed["signature"] = "0" * 128
    elif change == "scope": binding = {**binding, "client_id": uid()}
    elif change == "generation": kwargs["generation"] = uid()
    elif change == "args": kwargs["argument_digest"] = "0" * 64
    elif change == "workspace": kwargs["workspace_version"] = 3
    elif change == "expiry": kwargs["now"] = 1066
    elif change == "bool_version": signed["ticket"]["workspace_version"] = True
    else: signed["ticket"]["extra"] = "private-sentinel"
    with pytest.raises(ExecutionControlError, match="TICKET_REFUSED"):
        verify_ticket(signed, runtime.manifest.data["public_key"], binding, **kwargs)


@pytest.mark.parametrize("change", ["revoked", "expired", "cancelled", "foreign", "version", "restart"])
def test_claim_rechecks_authority_and_no_repeat_dispatch(execution, change):
    runtime, identity, binding, ticket, control, clock, authority = execution
    signed = control.prepare(ticket, identity)
    version = 0
    if change == "revoked": authority[0] = False
    elif change == "expired": clock[0] = 1061
    elif change == "cancelled": control.cancel(signed, identity, 0)
    elif change == "foreign": identity = SimpleNamespace(server_id=identity.server_id, client_id=uid(), principal=identity.principal)
    elif change == "version": version = True
    else: runtime.generation = uid()
    with pytest.raises(ExecutionControlError):
        control.claim(signed, identity, version, "a" * 16)


def test_concurrent_claim_one_dispatch_and_cancel_uncertain(execution):
    runtime, identity, binding, ticket, control, clock, _ = execution
    signed = control.prepare(ticket, identity)
    with ThreadPoolExecutor(max_workers=8) as pool:
        results = list(pool.map(lambda _: control.claim(signed, identity, 0, "a" * 16), range(8)))
    assert sum(r["dispatch"] for r in results) == 1
    assert control.cancel(signed, identity, 1)["state"] == "execution_uncertain"
    with pytest.raises(ExecutionControlError):
        control.claim(signed, identity, 0, "a" * 16)


def test_server_restart_and_client_restart_never_replay(execution):
    runtime, identity, binding, ticket, control, clock, _ = execution
    signed = control.prepare(ticket, identity)
    def validator(value):
        verify_ticket(value, runtime.manifest.data["public_key"], binding, generation=runtime.generation,
            now=clock[0], argument_digest=ticket["argument_digest"], workspace_handle=ticket["workspace_handle"], workspace_version=2)
        return True
    journal = ExecutionJournal(ROOT / "work/c1" / ("c4_client_" + uuid.uuid4().hex), validate_ticket=validator)
    journal.intent(signed)
    with pytest.raises(ExecutionJournalError, match="RECONCILIATION"):
        journal.intent(signed)
    acknowledgement = control.claim(signed, identity, 0, "a" * 16)
    journal.acknowledge(signed, acknowledgement)
    assert all(r["dispatch"] is False for r in journal.recover())
    assert journal.recover()[0]["state"] == "execution_uncertain"
    runtime.generation = uid()
    records = control.reconcile_restart()["operations"]
    assert records[ticket["operation_id"]]["state"] == "execution_uncertain"
    with pytest.raises(ExecutionControlError):
        control.claim(signed, identity, 0, "a" * 16)
    value = receipt(ticket)
    with pytest.raises(ExecutionJournalError, match="RECEIPT_SCOPE"):
        journal.settle({**value, "client_id": uid()})
    assert journal.settle(value)["state"] == "verified"
    assert control.settle(signed, value, identity)["state"] == "verified"


def test_client_journal_default_refuses_and_deadline_uncertain(execution):
    runtime, identity, binding, ticket, control, clock, _ = execution
    signed = control.prepare(ticket, identity)
    journal = ExecutionJournal(ROOT / "work/c1" / ("c4_client_" + uuid.uuid4().hex))
    with pytest.raises(ExecutionJournalError, match="VALIDATION_REQUIRED"):
        journal.intent(signed)
    control.claim(signed, identity, 0, "a" * 16)
    clock[0] = 1101
    assert control.reconcile_restart()["operations"][ticket["operation_id"]]["state"] == "execution_uncertain"


def test_untrusted_receipt_cannot_settle_or_claim_success(execution):
    runtime, identity, binding, ticket, control, clock, _ = execution
    signed = control.prepare(ticket, identity)
    with pytest.raises(ExecutionControlError, match="WITHOUT_CLAIM"):
        control.settle(signed, receipt(ticket), identity)
    control.claim(signed, identity, 0, "a" * 16)
    forged = receipt(ticket); forged["evidence"] = [{"harness_says_success": True}]
    with pytest.raises(ExecutionControlError, match="VERIFIER_UNAVAILABLE"):
        control.settle(signed, forged, identity)
    forged["evidence"] = []
    with pytest.raises(ValidationError):
        ExecutionReceipt.model_validate(forged)


@pytest.mark.parametrize("kind,code", [("server_local_model", "SELECTED_MODEL_UNAVAILABLE"),
    ("client_cloud_model", "CLIENT_PROVIDER_UNAVAILABLE"), ("client_external_harness", "ADAPTER_NOT_QUALIFIED")])
def test_explicit_provider_no_fallback_or_warmup(kind, code):
    policy = ReasoningSelectionPolicy()
    with pytest.raises(ReasoningUnavailable, match=code):
        policy.require({"kind": kind, "provider": "selected-provider", "model": "chosen", "allowed_fallbacks": ["other"]})
    exact = ReasoningSelectionPolicy([(kind, "selected-provider", "chosen")])
    assert exact.require({"kind": kind, "provider": "selected-provider", "model": "chosen"}).provider == "selected-provider"


def test_canonical_preparation_reuses_core_and_exact_private_ports(execution):
    runtime, identity, binding, ticket, control, clock, _ = execution
    from uri_core.core.client_service import ClientService, ExplicitGrants
    from uri_core.core.capability_resolver import CapabilityResolver
    service = ClientService(runtime)
    pair = service.pairings.provision(binding["principal_id"], grants=["remember_fact"], mode="office")
    auth = service.pairings.acquire(pair["server_id"], pair["client_id"], pair["principal_token"], pair["pairing_token"])
    paired = service.pairings.resolve(auth["token"], pair["client_id"])
    binding["client_id"] = pair["client_id"]
    req = TurnRequest(**binding, request_id=uid(), idempotency_key=uid(), text="remember I teach science",
        snapshot=ClientStateSnapshot(**binding), reasoning=ReasoningSelection(kind="client_external_harness", provider="claude_code"))
    ports = ClientStatePorts(req.snapshot, binding)
    with pytest.raises(NeedsContext):
        prepare_canonical_context(ports, req, paired.principal, [])
    reads = []
    for store, value in [("sessions", {"session_id": req.session_id}), ("history", [{"user_text": "client-private", "response_text": "prior"}])]:
        reads.append({"query": {"store": store, "method": "get_session", "args": [req.session_id]},
                      "result": value, "store_version": 0, "result_digest": digest(value)})
    snapshot = ClientStateSnapshot(**binding, reads=reads)
    req = req.model_copy(update={"snapshot": snapshot})
    ports = ClientStatePorts(snapshot, binding)
    descriptors = CapabilityResolver.resolve(paired.principal, service.registry, ExplicitGrants(service.pairings, paired))
    prepared = prepare_canonical_context(ports, req, paired.principal, descriptors)
    assert prepare_for_paired_client(service, req, paired)["request"] == prepared["request"]
    assert prepared["request"]["recent_conversation"][0]["user"] == "client-private"
    assert {r["capability_id"] for r in prepared["directory"].summaries()} == {"remember_fact"}
    assert prepared["graphify"].records and not ports.mutations
    gate = validate_canonical_proposal(prepared, {"mode": "execute", "capability": "invented"}, paired.principal, lambda *_: False)
    assert gate.outcome == "INVALID_PROPOSAL"
    assert not service.path.exists()


def test_client_preflight_ui_pending_without_touching_legacy(execution):
    runtime, identity, binding, ticket, control, clock, _ = execution
    from scripts.provision_uri_client import provision_client
    from uri_core.client_runtime.readiness import client_preflight
    root = ROOT / "work/c1" / ("c6_preflight_" + uuid.uuid4().hex)
    path = provision_client(runtime.manifest.path, root, binding["principal_id"], grants=[])
    result = client_preflight(path)
    assert result["ui_build"] == "CLIENT_UI_PENDING_C6"
    assert result["production_cutover"] is False and result["migration"] == "NOT_AUTHORIZED"


@pytest.mark.parametrize("change", ["hash", "outside", "occupied", "traversal", "private", "symlink", "expansion_limit",
                                    "workspace_state", "fixture_data"])
def test_rollback_refuses_unsafe_restore_before_writing(change):
    checkpoint = ROOT / "work/c1/checkpoints"; checkpoint.mkdir(parents=True, exist_ok=True)
    z = checkpoint / ("negative_" + uuid.uuid4().hex + ".zip")
    dest = ROOT / "work/c1" / ("negative_restore_" + uuid.uuid4().hex)
    with zipfile.ZipFile(z, "w") as a:
        name = "test_fixture.py"
        if change == "traversal": name = "../outside.py"
        if change == "private": name = "secure/credentials.dpapi"
        if change == "workspace_state": name = "uri_workspace/sessions/state.json"      # only the catalogue is allowed
        if change == "fixture_data": name = "fixtures/c4_harness/secret.json"           # fixtures: .py only
        if change == "symlink":
            info = zipfile.ZipInfo(name); info.external_attr = 0o120777 << 16; a.writestr(info, "target")
        elif change == "expansion_limit": a.writestr(name, b"x" * (5 * 1024 * 1024), compress_type=zipfile.ZIP_DEFLATED)
        else: a.writestr(name, "value = 1\n")
    sha = hashlib.sha256(z.read_bytes()).hexdigest()
    if change == "hash": sha = "0" * 64
    if change == "outside": dest = ROOT / ("out_of_scope_" + uuid.uuid4().hex)
    if change == "occupied": dest.mkdir()
    with pytest.raises(ValueError): rehearse(z, sha, dest)
    if change != "occupied": assert not dest.exists()


def test_offline_checkpoint_restore_hashes_and_no_application_start():
    z = ROOT / "work/c1/checkpoints/c3-provisional-source.zip"
    evidence = rehearse(z, hashlib.sha256(z.read_bytes()).hexdigest())
    assert evidence["source_files"] == 39 and evidence["application_started"] is False
    assert evidence["private_data_restored"] is False and evidence["production_cutover"] is False


def test_rollback_restores_the_canonical_source_set_including_adapters_and_catalogue():
    checkpoint = ROOT / "work/c1/checkpoints"; checkpoint.mkdir(parents=True, exist_ok=True)
    z = checkpoint / ("canonical_" + uuid.uuid4().hex + ".zip")
    names = ["uri_harness_adapters/__init__.py", "tests/reference_binding/test_x.py",
             "uri_workspace/capabilities_registry.json", "fixtures/c4_harness/fake_harness.py",
             "uri_core/reference_binding/binding.py"]
    with zipfile.ZipFile(z, "w") as a:
        for n in names:
            a.writestr(n, (ROOT / n).read_bytes() if n.endswith(".json") else "value = 1\n")
    evidence = rehearse(z, hashlib.sha256(z.read_bytes()).hexdigest())
    assert evidence["source_files"] == len(names) and evidence["private_data_restored"] is False
