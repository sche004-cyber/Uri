"""Batch 4 guidance and Brain contract boundary regressions."""
import json
from types import SimpleNamespace

from uri_core.core.canonical_execution import _canonical_nonexecution_envelope
from uri_core.core.decision_engine import DECISION_CONTRACT_SYSTEM_PROMPT, propose_decision
from uri_core.core.model_reasoning_adapter import REASONING_SYSTEM_PROMPT
from uri_core.core.tool_schema import LEGACY_TOOL_PARAMETERS
from pathlib import Path



def test_prompts_leave_capability_questions_to_the_brain():
    for prompt in (DECISION_CONTRACT_SYSTEM_PROMPT, REASONING_SYSTEM_PROMPT):
        assert "capability question" in prompt.lower()
        assert "web_search" in prompt and "fetch_url" in prompt
        assert "generate_document" in prompt and "google_workspace_create" in prompt
        assert "slides" in prompt.lower()


def test_tool_descriptions_distinguish_web_and_presentation_routing():
    schema = LEGACY_TOOL_PARAMETERS
    search = schema["web_search"]["properties"]["request_text"]["description"].lower()
    fetch = schema["fetch_url"]["properties"]["request_text"]["description"].lower()
    ppt = schema["generate_document"]["properties"]["request_text"]["description"].lower()
    slides = schema["google_workspace_create"]["properties"]["kind"]["description"].lower()
    registry = json.loads(Path("uri_workspace/capabilities_registry.json").read_text(encoding="utf-8"))["active_tools"]
    assert "no specific url" in search and "exact url" in fetch
    assert "pptx" in ppt and "slides" in slides
    assert "web research" in registry["web_search"]["description"].lower()
    assert "exact url" in registry["fetch_url"]["description"].lower()
    assert "pptx" in registry["generate_document"]["description"].lower()
    assert "google slides" in registry["google_workspace_create"]["description"].lower()


def test_brain_contract_is_not_rewritten_by_capability_question_text():
    contract = {
        "goal": "Can you create a PPT?", "mode": "unsupported", "capability": None,
        "actions": [], "clarification": None,
        "unsupported_reason": "This is the Brain's own decision.",
        "requires_approval": False, "confidence": "high", "reason": "Brain reasoning",
    }
    outcome = propose_decision(
        turn_state_data={
            "turn": {"user_text": "Can you create a PPT?"},
            "capability_summaries": [], "recent_conversation": [],
            "active_pointer": None, "session_facts": [], "attempt_history": [],
        },
        capability_directory=None, model_callable=lambda _: json.dumps(contract),
    )
    assert outcome.status == "ok"
    assert outcome.contract == contract


def test_disconnected_message_requires_capability_in_brain_contract():
    gate = SimpleNamespace(outcome="DISCONNECTED", capability_id="gmail_search")
    unnamed = {"mode": "unsupported", "capability": None, "unsupported_reason": "Brain reason"}
    assert _canonical_nonexecution_envelope(unnamed, gate)["response"]["message"] == "Brain reason"
    unnamed["mode"] = "single_action"
    unnamed["unsupported_reason"] = None
    assert _canonical_nonexecution_envelope(unnamed, gate)["response"]["message"] == "URI cannot perform that request with an available capability."
    named = {"mode": "single_action", "capability": "gmail_search"}
    assert _canonical_nonexecution_envelope(named, gate)["response"]["message"] == "That capability is not connected right now."
    named["mode"] = "unsupported"
    assert _canonical_nonexecution_envelope(named, gate)["response"]["message"] == "URI cannot perform that request with an available capability."


def test_google_registry_text_tracks_live_connection():
    registry = json.loads(Path("uri_workspace/capabilities_registry.json").read_text(encoding="utf-8"))["active_tools"]
    for capability in (
        "gmail_search", "gmail_find_draft", "gmail_create_draft",
        "drive_search", "fetch_drive_spreadsheet", "drive_upload",
    ):
        entry = registry[capability]
        copy = (entry["description"] + " " + entry["limitations"]).lower()
        assert "current google connection" in copy and "setup steps" in copy
        assert "credentials are missing" not in copy
        assert "requires a stored google oauth token" not in copy
        assert entry["availability"] == "available"
