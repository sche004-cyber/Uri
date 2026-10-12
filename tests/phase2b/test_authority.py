"""Authority verification: a signed ticket is the ONLY thing that can become AuthorizedWork, and every binding
field is checked. SYNTHETIC tickets signed by a test-only key (conftest.SyntheticAuthority)."""
import copy

import pytest

from phase2b.conftest import CLAUDE, SyntheticAuthority
from uri_core.client_contracts import digest
from uri_supervisor_bridge.authority import BridgeRefused


def refused(code, fn):
    with pytest.raises(BridgeRefused) as e:
        fn()
    assert e.value.code == code, (e.value.code, code)


def test_valid_ticket_becomes_bounded_work(authority):
    signed, request, now = authority.issue()
    w = authority.verify(signed, request, now=now)
    assert w.task_id == signed["ticket"]["operation_id"] and w.provider == "claude_code" and w.expected_file == "out.txt"
    assert w.deadline_us == signed["ticket"]["deadline"] * 1_000_000 and w.ticket_digest == digest(signed["ticket"])


def test_forged_signature_and_foreign_key_are_refused(authority):
    signed, request, now = authority.issue()
    bad = copy.deepcopy(signed)
    bad["signature"] = ("0" if bad["signature"][0] != "0" else "1") + bad["signature"][1:]
    refused("TICKET_REFUSED", lambda: authority.verify(bad, request, now=now))
    other = SyntheticAuthority(generation=authority.generation)
    other.binding = authority.binding
    refused("TICKET_REFUSED", lambda: other.verify(signed, request, now=now))      # signed by someone else's key


def test_binding_and_generation_mismatch_are_refused(authority):
    signed, request, now = authority.issue()
    for field in ("server_id", "client_id", "principal_id", "session_id"):
        wrong = SyntheticAuthority(authority.key, authority.generation)
        wrong.binding = {**authority.binding, field: "00000000-0000-4000-8000-000000000000"}
        refused("TICKET_REFUSED", lambda: wrong.verify(signed, request, now=now))
    wrong = SyntheticAuthority(authority.key, "11111111-1111-4111-8111-111111111111")
    wrong.binding = authority.binding
    refused("TICKET_REFUSED", lambda: wrong.verify(signed, request, now=now))       # server restarted: new generation


def test_stale_ticket_outside_freshness_window_and_past_deadline(authority):
    signed, request, now = authority.issue()
    refused("TICKET_REFUSED", lambda: authority.verify(signed, request, now=now + 120))
    refused("TICKET_REFUSED", lambda: authority.verify(signed, request, now=now - 30))
    signed, request, now = authority.issue(deadline_s=61)
    # within the issue window but the ticket says its own deadline has passed: refused by the explicit check
    bad = copy.deepcopy(signed)
    refused("TICKET_DEADLINE_PASSED", lambda: authority.verify(bad, request, now=now + 62))


def test_tampered_arguments_are_refused_even_with_a_valid_ticket(authority):
    """Phase 1 verify_ticket checks request.argument_digest; the bridge also hashes request.arguments itself."""
    signed, request, now = authority.issue()
    tampered = copy.deepcopy(request)
    tampered["arguments"]["inputs"]["instruction"] = "delete everything"
    refused("ARGUMENT_DIGEST_MISMATCH", lambda: authority.verify(signed, tampered, now=now))
    tampered = copy.deepcopy(request)
    tampered["arguments"]["inputs"]["expected_file"] = "other.txt"
    refused("ARGUMENT_DIGEST_MISMATCH", lambda: authority.verify(signed, tampered, now=now))
    tampered = copy.deepcopy(request)
    tampered["argument_digest"] = digest({"x": 1})
    refused("TICKET_REFUSED", lambda: authority.verify(signed, tampered, now=now))


def test_approval_digest_binds_turn_operation_capability_arguments_and_intent(authority):
    signed, request, now = authority.issue()
    t = copy.deepcopy(request)
    t["approval_digest"] = digest({"x": 2})
    refused("APPROVAL_DIGEST_MISMATCH", lambda: authority.verify(signed, t, now=now))
    t = copy.deepcopy(request)
    t["intent_digest"] = digest({"other": "intent"})          # a different confirmed intent cannot ride this ticket
    refused("APPROVAL_DIGEST_MISMATCH", lambda: authority.verify(signed, t, now=now))
    t = copy.deepcopy(request)
    t["intent_digest"] = None                                  # dropping the intent binding also fails
    refused("APPROVAL_DIGEST_MISMATCH", lambda: authority.verify(signed, t, now=now))
    t = copy.deepcopy(request)
    t["intent_digest"] = "not-a-digest"
    refused("INTENT_DIGEST_SHAPE", lambda: authority.verify(signed, t, now=now))
    # a ticket whose approval digest was computed over a different operation id does not verify for this one
    signed2, request2, now2 = authority.issue(approval_digest=signed["ticket"]["approval_digest"],
                                              intent_digest=request["intent_digest"])
    refused("APPROVAL_DIGEST_MISMATCH", lambda: authority.verify(signed2, request2, now=now2))


def test_unapproved_or_wrong_capability_or_wrong_verifier_is_refused(authority):
    signed, request, now = authority.issue()
    r = {**request, "capability_id": "remember_fact"}
    refused("CAPABILITY_NOT_SUPPORTED", lambda: authority.verify(signed, r, now=now))
    signed, request, now = authority.issue(capability="remember_fact")
    refused("CAPABILITY_NOT_SUPPORTED", lambda: authority.verify(signed, request, now=now))
    signed, request, now = authority.issue(verifier_id="uri.client.memory_readback.v1")
    refused("VERIFIER_MISMATCH", lambda: authority.verify(signed, request, now=now))


@pytest.mark.parametrize("reasoning,code", [
    ({"kind": "server_local_model", "provider": "uri-deterministic", "model": None}, "REASONING_KIND_NOT_HARNESS"),
    ({"kind": "client_external_harness", "provider": "../claude", "model": None}, "PROVIDER_ID_INVALID"),
    ({"kind": "client_external_harness", "provider": "claude code", "model": None}, "PROVIDER_ID_INVALID"),
    ({"kind": "client_external_harness", "provider": "--dangerously-skip-permissions", "model": None}, "PROVIDER_ID_INVALID"),
    ({"kind": "client_external_harness", "provider": "claude_code", "model": "-m"}, "MODEL_ID_INVALID"),
    ({"kind": "client_external_harness", "provider": "claude_code", "model": "--dangerously-skip-permissions"}, "MODEL_ID_INVALID"),
    ({"kind": "client_external_harness", "provider": "claude_code", "model": "x y"}, "MODEL_ID_INVALID"),
    ({"kind": "client_external_harness", "provider": "claude_code", "model": 5}, "MODEL_ID_INVALID"),
])
def test_executor_selection_is_validated_as_data(authority, reasoning, code):
    signed, request, now = authority.issue()
    refused(code, lambda: authority.verify(signed, request, reasoning=reasoning, now=now))


@pytest.mark.parametrize("name", ["../x.txt", "..\\x.txt", "C:\\x.txt", "/etc/passwd", ".hidden", "a/b.txt", "con", "NUL.txt",
                                  "x" * 200, "", "out.txt.", "out .txt", "ou\0t.txt", "out.txt\n"])
def test_expected_file_must_be_a_bare_safe_name(authority, name):
    signed, request, now = authority.issue(expected_file=name)
    with pytest.raises(BridgeRefused) as e:
        authority.verify(signed, request, now=now)
    assert e.value.code in ("EXPECTED_FILE_INVALID", "ARGUMENTS_NOT_PUBLIC")


def test_instruction_bounds(authority):
    signed, request, now = authority.issue(instruction="   ")
    refused("INSTRUCTION_INVALID", lambda: authority.verify(signed, request, now=now))
    signed, request, now = authority.issue(instruction="x" * (64 * 1024 + 1))
    refused("INSTRUCTION_INVALID", lambda: authority.verify(signed, request, now=now))


def test_malformed_ticket_or_request_shapes(authority):
    signed, request, now = authority.issue()
    refused("TICKET_SHAPE", lambda: authority.verify({"ticket": {}}, request, now=now))
    refused("TICKET_SHAPE", lambda: authority.verify({**signed, "extra": 1}, request, now=now))
    refused("REQUEST_SHAPE", lambda: authority.verify(signed, None, now=now))
    refused("REQUEST_SHAPE", lambda: authority.verify(signed, request, reasoning=None, now=now))
    bad = copy.deepcopy(signed)
    bad["ticket"]["approval_status"] = "pending"
    refused("TICKET_SHAPE", lambda: authority.verify(bad, request, now=now))      # Literal["approved"] fails first
