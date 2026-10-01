"""Tool catalogue for the Edge specialist-pair experiments.

The action tools are a typed projection of the 17 actions registered in
``uri_workspace/capabilities_registry.json`` (names, effect types and approval
requirements copied from that file). The live tools mostly take one free-text
``request_text``; the typed parameters here are an experimental projection so
that argument copying can be scored. Nothing here is executed against a real
service.
"""
from __future__ import annotations


def _t(name, description, props=None, required=None, effect="read_only", approval="none"):
    props = props or {}
    return {
        "name": name,
        "description": description,
        "parameters": {
            "type": "object",
            "properties": props,
            "required": list(required if required is not None else props.keys()),
        },
        "_effect": effect,
        "_approval": approval,
    }


S = {"type": "string"}

ACTIONS = {t["name"]: t for t in [
    _t("extract_student_records", "Retrieve a student's academic record by roll number from the indexed institutional spreadsheets.", {"roll_number": S}),
    _t("fetch_drive_spreadsheet", "Read rows from a Google Sheets spreadsheet by spreadsheet ID and cell range.", {"spreadsheet_id": S, "range": S}),
    _t("draft_institutional_note", "Draft an institutional office note (noting) for a stated purpose. Local draft only.", {"purpose": S}, effect="local_write"),
    _t("draft_institutional_order", "Draft an institutional office order (appointment, transfer, duty) for a stated purpose. Local draft only.", {"purpose": S}, effect="local_write"),
    _t("generate_document", "Generate a new Office file (docx, xlsx, pptx or pdf) with a given title.", {"format": {"type": "string", "enum": ["docx", "xlsx", "pptx", "pdf"]}, "title": S}, effect="local_write"),
    _t("system_performance", "Report this PC's current CPU, memory, swap and disk usage.", {}),
    _t("remember_fact", "Save a fact the user explicitly asks URI to remember.", {"fact": S}, effect="local_write"),
    _t("recall_memory", "Answer a question about what URI already remembers about the user.", {"question": S}),
    _t("convert_document", "Convert an attached document into another file format.", {"attachment_name": S, "target_format": {"type": "string", "enum": ["docx", "pdf"]}}, effect="local_write"),
    _t("read_attached_file", "Read the text of a file the user attached to this conversation, by its file name.", {"attachment_name": S}),
    _t("gmail_search", "Search the user's Gmail messages with a search query.", {"query": S}),
    _t("gmail_find_draft", "Search the user's existing Gmail drafts with a search query.", {"query": S}),
    _t("web_search", "Search the public Internet for current information.", {"query": S}),
    _t("drive_search", "Search the user's Google Drive files by name or content.", {"query": S}),
    _t("gmail_create_draft", "Create a Gmail draft (never sends) to a recipient with a subject.", {"recipient": S, "subject": S}, effect="external_write", approval="user_approval_required"),
    _t("drive_upload", "Upload a named local or attached file to Google Drive.", {"file_name": S}, effect="external_write", approval="user_approval_required"),
    _t("fetch_url", "Fetch one web page or document by URL and extract its text.", {"url": S}),
]}

# Explicit abstention tools, used only in prompt condition P1 (Stage-1 root cause
# RC-1: the models had no way to express abstention other than silence).
CONTROLS = {t["name"]: t for t in [
    _t("ask_clarification", "Use when the request is missing required information, is ambiguous, or refers to something not identified."),
    _t("escalate_to_main_brain", "Use when the request needs several steps, open-ended reasoning, comparison, analysis or composition."),
    _t("decline_unsupported", "Use when no offered tool performs the requested operation, or the request is forbidden or explicitly negated."),
]}
CONTROL_CLASS = {"ask_clarification": "CLARIFY", "escalate_to_main_brain": "ESCALATE", "decline_unsupported": "DECLINE"}

ROUTES = {t["name"]: t for t in [
    _t("route_direct_tool", "The request is one explicit operation that one available tool performs with arguments stated in the request."),
    _t("route_extraction", "The request asks to pull specific fields or values out of supplied text."),
    _t("route_drafting", "The request asks to compose or write new text such as a letter, note, order or email body."),
    _t("route_multi_step", "The request needs two or more operations, or planning, comparison or analysis."),
    _t("route_clarify", "The request is missing required information, is ambiguous, or refers to something unidentified."),
    _t("route_unsupported", "The request asks for something forbidden, destructive, or not available, or it is explicitly negated."),
]}


def public(tool: dict) -> dict:
    """Tool definition as shown to a model (private metadata removed)."""
    return {k: v for k, v in tool.items() if not k.startswith("_")}


def lookup(name: str) -> dict | None:
    return ACTIONS.get(name) or CONTROLS.get(name) or ROUTES.get(name)
