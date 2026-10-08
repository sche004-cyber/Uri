"""Second review: deliberately corrupt durable state and prove the gates fail closed.

Nothing here repairs state silently: a damaged ledger, key, catalogue or manifest must stop
the action with a machine code, never fall back to an empty/default state that re-authorizes.
"""
import json
from pathlib import Path

import pytest

from test_c5_intent_discovery import NOBRAIN, Stack, say, two_reports
from uri_core.core.runtime_identity import RuntimeIdentity, RuntimeIdentityError, RuntimeManifest


@pytest.fixture
def s():
    stack = Stack(18248)
    yield stack
    stack.close()


def control_root(s):
    return Path(s.runtime.manifest.data["control_root"])


def test_corrupt_turn_ledger_refuses_new_turns_instead_of_starting_empty(s):
    session = two_reports(s)
    say(s, session, "remember that the budget report is due on Friday")
    (control_root(s) / "client_turn_control.json").write_text("{not json")
    with pytest.raises(Exception, match="CONTROL_STORE_UNAVAILABLE"):
        say(s, session, "the Q4 one")
    assert s.memory(session) == []


def test_unreadable_ledger_makes_the_duplicate_guards_fail_closed(s):
    coordinator = s.coordinator
    s.app.state.client_service.path = control_root(s) / "missing" / "client_turn_control.json"
    s.app.state.client_service.path.parent.mkdir()
    s.app.state.client_service.path.write_text("[]")
    assert coordinator._intent_possibly_executed("a" * 32, "t") is True
    assert coordinator._intent_verified("a" * 32) is True
    assert coordinator._ledger_revision("a" * 32) == float("inf")


def test_corrupt_execution_control_ledger_refuses_claims(s):
    session = two_reports(s)
    say(s, session, "remember that the budget report is due on Friday")
    approval = s.runner.confirm(session, NOBRAIN, say(s, session, "the Q4 one"))
    assert approval["state"] == "approval_required"
    path = control_root(s) / "client_execution_control.json"
    turn = s.runner._post(f"/client/v1/turns/{approval['turn_id']}/approval", s.runner._control(
        session, approval, decision="approve", approval_digest=approval["approval_request"]["approval_digest"]))
    path.write_text(json.dumps({"schema_version": "uri.client.v1", "operations": {}, "extra": 1}))
    with pytest.raises(Exception):
        s.runner._post(f"/client/v1/turns/{approval['turn_id']}/claim", s.runner._control(
            session, turn, ticket=turn["ticket"], execution_version=0))
    assert s.memory(session) == []


def test_corrupt_signing_key_refuses_to_start(s):
    key = control_root(s) / "signing_key.dpapi"
    data = bytearray(key.read_bytes())
    data[-3] ^= 0xFF
    key.write_bytes(bytes(data))
    with pytest.raises(RuntimeIdentityError, match="PROTECTED_KEY_UNAVAILABLE"):
        RuntimeIdentity(RuntimeManifest(s.server_manifest, validate=False))


def test_mutated_catalogue_copy_or_manifest_pin_refuses_validation(s):
    state = Path(s.runtime.manifest.data["state_root"])
    catalogue = state / "uri_workspace/capabilities_registry.json"
    RuntimeManifest(s.server_manifest)                                   # valid before tampering
    original = catalogue.read_bytes()
    data = json.loads(original)
    data["active_tools"]["external_harness_task"]["availability"] = "available"
    catalogue.write_text(json.dumps(data))
    with pytest.raises(RuntimeIdentityError, match="CATALOGUE_FIXTURE_MISMATCH"):
        RuntimeManifest(s.server_manifest)
    catalogue.write_bytes(original)
    manifest = json.loads(Path(s.server_manifest).read_text())
    manifest["source_files"]["uri_harness_adapters/__init__.py"] = "0" * 64
    Path(s.server_manifest).write_text(json.dumps(manifest))
    with pytest.raises(RuntimeIdentityError, match="SOURCE_MANIFEST_MISMATCH"):
        RuntimeManifest(s.server_manifest)


def test_mutated_runtime_catalogue_used_by_the_paired_service_refuses_validation(s):
    """Defect found in review: only the uri_workspace copy was pinned; ClientService reads catalogue_root."""
    runtime_copy = Path(s.runtime.manifest.data["catalogue_root"]) / "capabilities_registry.json"
    data = json.loads(runtime_copy.read_bytes())
    data["active_tools"]["gmail_create_draft"]["approval_requirement"] = "none"
    runtime_copy.write_text(json.dumps(data))
    with pytest.raises(RuntimeIdentityError, match="CATALOGUE_FIXTURE_MISMATCH"):
        RuntimeManifest(s.server_manifest)


def test_runtime_catalogue_changed_after_start_permits_nothing(s):
    session = two_reports(s)
    runtime_copy = Path(s.runtime.manifest.data["catalogue_root"]) / "capabilities_registry.json"
    data = json.loads(runtime_copy.read_bytes())
    data["active_tools"]["gmail_create_draft"]["approval_requirement"] = "none"
    runtime_copy.write_text(json.dumps(data))
    assert s.app.state.client_service.registry.list_capabilities() == []
    out = say(s, session, "remember that my favourite colour is teal")
    assert out["state"] == "reply" and out["code"] != "APPROVAL_REQUIRED" and s.memory(session) == []
