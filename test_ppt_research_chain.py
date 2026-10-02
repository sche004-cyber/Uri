"""Research-first PPT creation without live network or model calls."""

import base64
import io
from types import SimpleNamespace
from unittest.mock import patch

from pptx import Presentation

from uri_core.core.canonical_execution import _execute_legacy_capability, _ready_read_prefix, run_canonical_for_ask
from uri_core.core.decision_engine import DecisionOutcome
from uri_core.core.tool_schema import LEGACY_TOOL_PARAMETERS
from uri_core.services.office_document_writer import render_pptx_bytes
from uri_core.tools.generate_document import GenerateDocumentTool


PNG = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVQIHWP4z8DwHwAFgAI/ScL/nwAAAABJRU5ErkJggg=="
)


class Directory:
    def describe(self, capability_id):
        return {"action_schemas": {}}


def _contract(first="web_search"):
    return {
        "goal": "Research student welfare and make a PPT", "mode": "multi_action",
        "capability": first,
        "actions": [
            {"name": first, "inputs": {"request_text": "student welfare"}},
            {"name": "generate_document", "capability": "generate_document", "inputs": {}},
        ],
    }


def test_web_research_prefix_runs_and_defers_document():
    contract = _contract()
    brain = SimpleNamespace(
        approval_gate=SimpleNamespace(execute_tool=lambda capability, **kwargs: {
            "status": "success", "data": {"status": "success", "results": [{"title": "Welfare guidance"}]}
        }),
        multi_action_dispatch=None,
        _draft_narrative_safely=lambda **kwargs: None,
    )
    gate = SimpleNamespace(outcome="READY", reasons=[], sub_results=[])
    with patch("uri_core.core.canonical_execution.build_turn_state_and_directory", return_value=(SimpleNamespace(data={}), Directory())), \
         patch("uri_core.core.canonical_execution.propose_decision", return_value=DecisionOutcome(status="ok", contract=contract)), \
         patch("uri_core.core.decision_gates.evaluate_gates", return_value=gate), \
         patch("uri_core.core.canonical_execution.is_allowlisted", return_value=True), \
         patch("uri_core.core.canonical_execution.record_canonical_telemetry"):
        result = run_canonical_for_ask(orchestrator=brain, session_id="s", user_text="research then PPT", principal=None)
    assert result["execution"]["partial_read_only"] is True
    assert result["response"]["results"][0]["title"] == "Welfare guidance"
    assert result["plan"]["deferred_actions"] == [{"capability": "generate_document", "name": "generate_document"}]


def test_non_read_prefix_never_auto_runs():
    gate = SimpleNamespace(outcome="READY")
    with patch("uri_core.core.decision_gates.evaluate_gates", return_value=gate), \
         patch("uri_core.core.canonical_execution.is_allowlisted", return_value=True):
        assert _ready_read_prefix(_contract("generate_document"), Directory(), None, {}) == []


def test_ppt_schema_exposes_user_chosen_design_controls():
    properties = LEGACY_TOOL_PARAMETERS["generate_document"]["properties"]
    assert {"theme", "include_images", "image_queries"} <= properties.keys()


def test_choice_turn_forwards_research_and_design_to_generator():
    captured = {}

    def execute(capability, **kwargs):
        captured.update(kwargs)
        return {"status": "success", "data": {"status": "success"}}

    result = _execute_legacy_capability(
        {"capability": "generate_document", "actions": [{
            "name": "generate_document", "inputs": {
                "request_text": "model replacement is not authoritative",
                "requested_output": "PPTX on student welfare",
                "theme": "academic", "include_images": True,
                "image_queries": ["campus support"],
            },
        }]},
        orchestrator=SimpleNamespace(approval_gate=SimpleNamespace(execute_tool=execute)),
        session_id="s", user_text="Option 2", principal=None,
        recent_conversation=[{"user": "Research", "uri": "Research summary"}],
    )
    assert result["status"] == "success"
    assert captured["request_text"] == "Option 2"
    assert captured["theme"] == "academic"
    assert captured["decision_context"]["recent_conversation"][0]["uri"] == "Research summary"


def test_theme_picture_and_credits():
    data = render_pptx_bytes(
        "# Student welfare\n- Overview\n# Campus support\n- Counselling and peer support",
        theme="academic", images=[{"data": PNG, "credit": "Test creator; CC0; example.test"}],
    )
    deck = Presentation(io.BytesIO(data))
    assert len(deck.slides) == 3
    assert deck.slides[0].background.fill.fore_color.rgb != deck.slides[1].background.fill.fore_color.rgb
    assert any(shape.shape_type == 13 for shape in deck.slides[1].shapes)
    assert "Image credits" in " ".join(shape.text for shape in deck.slides[2].shapes if shape.has_text_frame)


class Composer:
    def compose(self, **kwargs):
        assert kwargs["evidence"]["recent_conversation"][0]["uri"] == "Research summary"
        return {"body": "# Student welfare\n- Support\n# Programmes\n- Counselling", "status": "success", "composed_by": "model"}


def test_image_failure_still_saves_pptx_with_research_context():
    class Store:
        def save(self, **kwargs):
            assert Presentation(io.BytesIO(kwargs["content"]))
            return SimpleNamespace(to_reference=lambda: {"file_id": "saved-file"})

    tool = GenerateDocumentTool(composer=Composer(), file_store=Store())
    with patch("uri_core.services.office_document_writer.requests.get", side_effect=OSError("offline")):
        result = tool.generate(
            request_text="Option 2", requested_output="PPTX student welfare",
            theme="modern", include_images=True, image_queries=["campus"],
            decision_context={"recent_conversation": [{"user": "Research", "uri": "Research summary"}]},
            session_id="s",
        )
    assert result["status"] == "success"
    assert result["images_added"] == 0
    assert result["image_note"]
    assert result["file"]["file_id"]
