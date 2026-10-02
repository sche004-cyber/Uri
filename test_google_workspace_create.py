"""No-network checks for approved Google Workspace creation."""

import json
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from uri_core.capabilities.base import EffectType
from uri_core.capabilities.registry import LegacyCapabilityAdapter
from uri_core.core.capability_registry import CapabilityRegistry
from uri_core.core.tool_schema import LEGACY_TOOL_PARAMETERS
from uri_core.core.approval_gate import ApprovalGate
from uri_core.core.canonical_execution import _execute_legacy_capability
from uri_core.services.google_errors import classify_google_error
from uri_core.tools.google_workspace_create import GoogleWorkspaceCreateTool


@pytest.fixture
def google():
    drive, sheets, docs, slides, forms = (MagicMock() for _ in range(5))
    drive.files.return_value.list.return_value.execute.return_value = {"files": []}
    drive.files.return_value.create.return_value.execute.return_value = {"id": "new-id", "name": "New", "webViewLink": "https://drive.google.com/new-id"}
    forms.forms.return_value.create.return_value.execute.return_value = {"formId": "new-form"}
    drive.files.return_value.get.return_value.execute.return_value = {"parents": ["old-root"]}
    clients = {"drive": drive, "sheets": sheets, "docs": docs, "slides": slides, "forms": forms}
    build = lambda api, version, **kwargs: clients[api]
    tool = GoogleWorkspaceCreateTool(user_id="u1", build_service=build, credential_loader=lambda **kwargs: object())
    return tool, clients


@pytest.mark.parametrize("arguments", [
    {}, {"kind": "bad", "title": "X"}, {"kind": "folder", "title": " "},
    {"kind": "sheet", "title": "X", "headers": []},
    {"kind": "sheet", "title": "X", "headers": ["A"], "empty_rows": -1},
    {"kind": "sheet", "title": "X", "headers": ["A"], "empty_rows": True},
    {"kind": "form", "title": "X", "questions": [{"title": "Q", "required": "yes"}]},
    {"kind": "doc", "title": "X", "body": 3},
])
def test_invalid_arguments_create_nothing(google, arguments):
    tool, clients = google
    assert tool.generate(**arguments)["status"] == "input_required"
    assert not clients["drive"].files.return_value.create.called


@pytest.mark.parametrize("reuse", [True, False])
def test_folder_reuse_or_create(google, reuse):
    tool, clients = google
    drive = clients["drive"].files.return_value
    if reuse:
        drive.list.return_value.execute.side_effect = [
            {"files": [{"id": "existing-folder", "name": "URI Test"}]}, {"files": []}]
    result = tool.generate(kind="sheet", title="Contacts", folder_name="URI Test", headers=["SL", "Name"], empty_rows=5)
    assert result["status"] == "success"
    creates = [call.kwargs["body"] for call in drive.create.call_args_list]
    if reuse:
        assert len(creates) == 1 and creates[0]["parents"] == ["existing-folder"]
    else:
        assert len(creates) == 2 and creates[0]["mimeType"].endswith("folder")
    assert not drive.delete.called
    assert not drive.update.called


def test_sheet_headers_and_professional_format(google):
    tool, clients = google
    result = tool.generate(kind="sheet", title="Contacts", headers=["SL", "Name", "Mobile Number", "Gmail Address"], empty_rows=20)
    assert result["status"] == "success" and result["file_id"] == "new-id"
    request = clients["sheets"].spreadsheets.return_value.batchUpdate.call_args.kwargs["body"]["requests"]
    assert [v["userEnteredValue"]["stringValue"] for v in request[1]["updateCells"]["rows"][0]["values"]] == ["SL", "Name", "Mobile Number", "Gmail Address"]
    assert request[0]["updateSheetProperties"]["properties"]["gridProperties"]["frozenRowCount"] == 1
    assert request[0]["updateSheetProperties"]["properties"]["gridProperties"]["rowCount"] == 21
    assert request[2]["repeatCell"]["cell"]["userEnteredFormat"]["textFormat"]["bold"] is True
    assert any("addBanding" in item for item in request)


def test_folder_link_and_no_content_api(google):
    tool, clients = google
    clients["drive"].files.return_value.create.return_value.execute.return_value = {"id": "folder-id", "name": "URI Test"}
    result = tool.generate(kind="folder", title="URI Test")
    assert result["webViewLink"] == "https://drive.google.com/drive/folders/folder-id"
    assert not clients["sheets"].spreadsheets.called


def test_doc_slides_form_content(google):
    tool, clients = google
    tool.generate(kind="doc", title="Memo", heading="Overview", body="Hello")
    doc_requests = clients["docs"].documents.return_value.batchUpdate.call_args.kwargs["body"]["requests"]
    assert doc_requests[0]["insertText"]["text"] == "Overview\nHello"
    assert doc_requests[1]["updateParagraphStyle"]["paragraphStyle"]["namedStyleType"] == "HEADING_1"
    tool.generate(kind="slides", title="Deck", slide_titles=["First", "Second"])
    slide_requests = clients["slides"].presentations.return_value.batchUpdate.call_args.kwargs["body"]["requests"]
    assert [x["insertText"]["text"] for x in slide_requests if "insertText" in x] == ["First", "Second"]
    result = tool.generate(kind="form", title="Survey", questions=[{"title": "Name", "required": True}])
    assert result["file_id"] == "new-form"
    form_requests = clients["forms"].forms.return_value.batchUpdate.call_args.kwargs["body"]["requests"]
    assert form_requests[0]["createItem"]["item"]["questionItem"]["question"]["required"] is True


def test_duplicate_and_ambiguous_folder_are_not_written(google):
    tool, clients = google
    drive = clients["drive"].files.return_value
    drive.list.return_value.execute.return_value = {"files": [{"id": "existing", "name": "Memo"}]}
    assert tool.generate(kind="doc", title="Memo")["status"] == "already_exists"
    assert not drive.create.called
    drive.list.return_value.execute.return_value = {"files": [{"id": "a"}, {"id": "b"}]}
    assert tool.generate(kind="doc", title="Memo", folder_name="Ambiguous")["status"] == "input_required"
    assert not drive.update.called and not drive.delete.called


def test_form_moves_only_newly_created_file(google):
    tool, clients = google
    drive = clients["drive"].files.return_value
    drive.list.return_value.execute.side_effect = [{"files": [{"id": "folder-id"}]}, {"files": []}]
    tool.generate(kind="form", title="Survey", folder_name="URI Test")
    assert drive.update.call_args.kwargs["fileId"] == "new-form"
    assert drive.update.call_args.kwargs["removeParents"] == "old-root"
    assert not drive.delete.called


def test_approval_effect_and_brain_schema():
    raw = json.loads((Path(__file__).parent / "uri_workspace/capabilities_registry.json").read_text(encoding="utf-8"))["active_tools"]["google_workspace_create"]
    assert raw["approval_requirement"] == "user_approval_required"
    assert raw["effect_type"] == "external_write"
    action = LegacyCapabilityAdapter.from_descriptor({"id": "google_workspace_create", **raw}).actions["google_workspace_create"]
    assert action.effect_type is EffectType.EXTERNAL_WRITE
    assert CapabilityRegistry().describe_status("google_workspace_create") is not None
    assert LEGACY_TOOL_PARAMETERS["google_workspace_create"]["required"] == ["kind", "title"]


def test_creation_waits_for_approval():
    store = MagicMock()
    store.propose.return_value.action_id = "approval-1"
    dispatcher = MagicMock()
    gate = ApprovalGate(dispatcher=dispatcher, approval_store=store, audit_trail=MagicMock())
    result = gate.execute_tool("google_workspace_create", session_id="s1", request_text="Create a spreadsheet in my Google Drive", kind="sheet", title="Contacts", headers=["Name"])
    assert result["status"] == "awaiting_approval"
    dispatcher.execute_tool.assert_not_called()


def test_canonical_path_preserves_inputs_and_runtime_authority():
    gate = MagicMock()
    gate.execute_tool.return_value = {"status": "awaiting_approval", "action_id": "a1"}
    orchestrator = MagicMock(approval_gate=gate)
    principal = object()
    contract = {"capability": "google_workspace_create", "actions": [{"name": "google_workspace_create", "inputs": {"kind": "sheet", "title": "Contacts", "headers": ["Name"], "session_id": "spoof", "principal": "spoof"}}]}
    result = _execute_legacy_capability(contract, orchestrator=orchestrator, session_id="real-session", user_text="Create Contacts", principal=principal)
    assert result["execution"]["status"] == "awaiting_approval"
    kwargs = gate.execute_tool.call_args.kwargs
    assert kwargs["title"] == "Contacts" and kwargs["headers"] == ["Name"]
    assert kwargs["session_id"] == "real-session" and kwargs["principal"] is principal


def test_disabled_api_error_is_actionable(google):
    tool, clients = google
    clients["sheets"].spreadsheets.return_value.batchUpdate.return_value.execute.side_effect = RuntimeError("Sheets API has not been used in project 123 before or it is disabled")
    result = tool.generate(kind="sheet", title="Contacts", headers=["Name"])
    assert result["error"] == "api_disabled" and "sheets.googleapis.com" in result["message"]
    assert result["file_id"] == "new-id"
    assert classify_google_error("insufficient authentication scopes", "forms")["kind"] == "insufficient_scope"
