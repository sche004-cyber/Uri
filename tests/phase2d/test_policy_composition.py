"""Phase 2 server-side reasoning policy: explicit file-backed rows, deterministic row always present, fail closed on
malformed input; and the frozen default composition is untouched."""
import json

import pytest

from uri_core.app.paired_server import default_composition
from uri_core.core.paired_reasoning import ReasoningUnavailable
from uri_supervisor_bridge.composition import (DETERMINISTIC_ROW, POLICY_SCHEMA, PolicyError, load_policy_rows,
                                               phase2_server_composition, write_policy)


def test_absent_policy_equals_frozen_default(tmp_path):
    rows = load_policy_rows(tmp_path / "missing.json")
    assert rows == {DETERMINISTIC_ROW} == default_composition()["policy"].supported


def test_valid_policy_adds_only_harness_rows(tmp_path):
    p = write_policy(tmp_path / "policy.json", {("client_external_harness", "codex_cli", "gpt-6-sol")})
    comp = phase2_server_composition(p)
    assert comp["policy"].supported == {DETERMINISTIC_ROW, ("client_external_harness", "codex_cli", "gpt-6-sol")}
    assert comp["qualified"] == ("remember_fact", "external_harness_task")
    sel = comp["policy"].require({"kind": "client_external_harness", "provider": "codex_cli", "model": "gpt-6-sol"})
    assert sel.provider == "codex_cli"
    with pytest.raises(ReasoningUnavailable, match="ADAPTER_NOT_QUALIFIED"):
        comp["policy"].require({"kind": "client_external_harness", "provider": "codex_cli", "model": "gpt-6.1-sol"})
    with pytest.raises(ReasoningUnavailable, match="ADAPTER_NOT_QUALIFIED"):
        comp["policy"].require({"kind": "client_external_harness", "provider": "claude_code", "model": None})


@pytest.mark.parametrize("body,code", [
    ("not json", "POLICY_UNREADABLE"),
    ("[]", "POLICY_SCHEMA"),
    (json.dumps({"schema": "wrong", "rows": []}), "POLICY_SCHEMA"),
    (json.dumps({"schema": POLICY_SCHEMA, "rows": [{"kind": "client_external_harness", "provider": "codex_cli"}]}), "POLICY_ROW_SHAPE"),
    (json.dumps({"schema": POLICY_SCHEMA, "rows": [{"kind": "client_cloud_model", "provider": "openai", "model": "x"}]}), "POLICY_KIND_NOT_ALLOWED"),
    (json.dumps({"schema": POLICY_SCHEMA, "rows": [{"kind": "client_external_harness", "provider": "Bad Id", "model": None}]}), "POLICY_PROVIDER_INVALID"),
    (json.dumps({"schema": POLICY_SCHEMA, "rows": [{"kind": "client_external_harness", "provider": "codex_cli", "model": "a b"}]}), "POLICY_MODEL_INVALID"),
])
def test_malformed_policy_fails_closed_as_a_whole(tmp_path, body, code):
    p = tmp_path / "policy.json"
    p.write_text(body, encoding="utf-8")
    with pytest.raises(PolicyError, match=code):
        load_policy_rows(p)
    with pytest.raises(PolicyError):
        phase2_server_composition(p)


def test_write_policy_refuses_invalid_rows(tmp_path):
    with pytest.raises(PolicyError):
        write_policy(tmp_path / "p.json", {("server_local_model", "something", None)})
    assert not (tmp_path / "p.json").exists()
