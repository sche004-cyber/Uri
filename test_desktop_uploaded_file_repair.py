"""Offline contract tests for the desktop uploaded-file turn."""

import json
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from uri_core.core.canonical_execution import (
    _canonical_nonexecution_envelope,
    _execute_legacy_capability,
)
from uri_core.core.context_budget import estimate_tokens
from uri_core.core.decision_engine import (
    _BASE_DECISION_PROMPT,
    build_decision_request,
    preselect_candidate_ids,
    propose_decision,
)
from uri_core.core.response_drafting import DraftRequest, draft_response
from uri_core.core.turn_state import assemble_turn_state
from uri_core.tools.read_attached_file import ReadAttachedFileTool


class Directory:
    def __init__(self):
        registry = json.loads(Path("uri_workspace/capabilities_registry.json").read_text(encoding="utf-8"))
        self.entries = registry["active_tools"]

    def summaries(self):
        return [
            {
                "capability_id": name,
                "summary": entry["description"],
                "actions": [name],
                "reads_current_attachments": entry.get("reads_current_attachments", False),
                "available": entry.get("availability") == "available",
            }
            for name, entry in self.entries.items()
        ]

    def describe(self, name):
        return {"actions": [name]} if name in self.entries else None


def _state(attachments):
    state = assemble_turn_state(
        user_text="Summarize the sales report I uploaded",
        session_id="session",
        current_turn_attachments=attachments,
    ).data
    state["capability_summaries"] = Directory().summaries()
    return state


def _decision(mode, capability, clarification=None):
    return json.dumps({
        "goal": "summarize the uploaded sales report",
        "mode": mode,
        "capability": capability,
        "actions": [{"name": capability, "inputs": {}}] if mode == "single_action" else [],
        "clarification": clarification,
        "unsupported_reason": None,
        "requires_approval": False,
        "confidence": "high",
        "reason": "Read the file before answering." if mode == "single_action" else "The file is ambiguous.",
    })


def test_single_upload_decision_dispatch_and_grounded_draft():
    reference = {"file_id": "q3", "filename": "q3_report.txt", "size_bytes": 42}
    directory = Directory()
    state = _state([reference])
    candidate_ids = preselect_candidate_ids(state, directory)
    assert "read_attached_file" in candidate_ids
    assert "summarize" in directory.entries["read_attached_file"]["description"]

    def decide(payload):
        request = json.loads(payload)
        assert request["current_turn_attachments"] == [reference]
        assert any(s["capability_id"] == "read_attached_file" for s in request["capability_summaries"])
        return _decision("single_action", "read_attached_file")

    decision = propose_decision(
        turn_state_data=state, capability_directory=directory,
        model_callable=decide, preselect=True,
    )
    assert decision.status == "ok"
    assert decision.contract["capability"] == "read_attached_file"

    record = SimpleNamespace(file_id="q3", filename="q3_report.txt", session_id="session",
                             media_type="text/plain", size_bytes=42)
    store = SimpleNamespace(get=lambda file_id: record if file_id == "q3" else None,
                            path_for=lambda file_id: "validated-q3-path" if file_id == "q3" else None)
    reader = ReadAttachedFileTool(file_store=store)

    class Gate:
        def execute_tool(self, capability, **kwargs):
            assert capability == "read_attached_file"
            return {"status": "success", "data": reader.execute(**kwargs)}

    with patch("uri_core.tools.read_attached_file.extract_file_text", return_value={
        "status": "success", "text": "Q3 sales total: 120 units. Growth: 10%.", "truncated": False,
    }):
        envelope = _execute_legacy_capability(
            decision.contract, orchestrator=SimpleNamespace(approval_gate=Gate()),
            session_id="session", user_text="Summarize the sales report I uploaded",
            principal=None, current_turn_attachment_ids=["q3"],
        )
    assert envelope["response"]["documents"][0]["text"].startswith("Q3 sales total")

    class Brain:
        config = SimpleNamespace(context_tokens=16384, model="mock")

        def complete(self, **kwargs):
            payload = json.loads(kwargs["user"])
            assert payload["outcome"]["response"]["documents"][0]["text"] == "Q3 sales total: 120 units. Growth: 10%."
            return SimpleNamespace(content="The Q3 report says sales reached 120 units, up 10%.")

    draft = draft_response(DraftRequest(
        user_text="Summarize the sales report I uploaded",
        outcome={"execution": envelope["execution"], "response": envelope["response"]},
        personalization=None, policy_text="URI follows the runtime result.",
    ), provider=Brain())
    assert "120 units" in draft


def test_two_uploads_are_visible_for_brain_clarification_without_reading():
    references = [{"file_id": name, "filename": f"{name}_report.txt"} for name in ("q3", "q4")]
    state = _state(references)
    directory = Directory()

    def decide(payload):
        request = json.loads(payload)
        assert [x["filename"] for x in request["current_turn_attachments"]] == [
            "q3_report.txt", "q4_report.txt"]
        return _decision("clarification", "read_attached_file", {
            "question": "Which report should I summarize, q3_report.txt or q4_report.txt?",
            "missing_field": "filename",
        })

    result = propose_decision(turn_state_data=state, capability_directory=directory,
                              model_callable=decide, preselect=True)
    assert result.status == "ok"
    assert result.contract["mode"] == "clarification"
    assert "q4_report.txt" in result.contract["clarification"]["question"]
    envelope = _canonical_nonexecution_envelope(
        result.contract, SimpleNamespace(outcome="MISSING_PARAMETER", missing_field="filename")
    )
    assert envelope["execution"]["status"] == "not_executed"
    assert envelope["response"]["message"]["question"] == result.contract["clarification"]["question"]
    assert "several" in _BASE_DECISION_PROMPT


def test_realistic_registry_decision_prompt_is_bounded():
    state = _state([{"file_id": "q3", "filename": "q3_report.txt"},
                    {"file_id": "q4", "filename": "q4_report.txt"}])
    directory = Directory()
    ids = preselect_candidate_ids(state, directory)
    request = build_decision_request(state, ids, directory)
    estimate = estimate_tokens(_BASE_DECISION_PROMPT) + estimate_tokens(json.dumps(request, ensure_ascii=False))
    assert len(directory.entries) >= 15
    assert len(ids) <= 9
    assert estimate <= 5300
